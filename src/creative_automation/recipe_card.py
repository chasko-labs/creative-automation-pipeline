"""Recipe-card generator — monthly local ingredient -> on-brand card (agentcore B4).

Given a market + month, produce a recipe card whose TEXT layer is safety-gated and
dialect-correct (via B1's rewriter) and whose IMAGE layer stays text-free (cr-1). The
card is a two-layer composition: a text-free hero panel on top, an overlay/layout panel
with the title + ingredient line + steps underneath. Text lives only in the layout
layer — the image never carries baked-in words.

The ingredient is never fabricated: locales.resolve_this_month is the single source of
truth. A month with no seeded ingredient returns a clear no-ingredient result rather
than inventing one, matching the honesty contract the context pack already holds.

Chain per text block:

    build_recipe_card -> resolve_this_month -> pick recipe -> B1 rewrite (each block)
                       -> compose text-free-image card -> iso name

Every emitted text block passes safety.check_text because it flows through B1, which
gates on safety as its last hop.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import naming, safety
from . import season_pairing as _seasons
from ._datapaths import data_path
from .locales import resolve_seasonal_moments, resolve_this_month
from .platform_copy import clean_brand_copy
from .recipe_i18n import translate_recipe_texts
from .text_rewriter import rewrite_headline

# Composed cards publish here so the recipes DAM tab (extra_prefixes) picks
# them up among past assets. Publish is opt-in and never fails a card.
DAM_RECIPES_PREFIX = "brands/kodiak/recipes/"

# Repo checkout and Lambda image resolve data/ differently (pip install . does
# not bundle data/); data_path picks the layout that actually exists.
_ROOT = Path(__file__).parents[2]
RECIPES_PATH = data_path("recipes", "kodiak-recipes.json")
RECIPE_CARD_TEMPLATE_PATH = _ROOT / "references" / "templates" / "recipe-card.json"
DEFAULT_OUT_DIR = _ROOT / "output" / "recipe-cards"

# recipe-card.json schema this module reads geometry from. Every physical value
# in the template is {"value": N, "unit": "in|mm|pt|fraction"}; geometry is read
# from the template, never duplicated as Python literals.
RECIPE_CARD_SCHEMA = "kodiak/recipe-card@v1"

# recipe-card@v1 DATA contract (gh #304): the versioned object that flows
# LLM-authoring hop -> renderer -> validation -> asset pack, documented at
# data/recipes/recipe-card-v1.schema.json. Distinct from RECIPE_CARD_SCHEMA
# above, which describes print-geometry zones, not card data.
RECIPE_CARD_DATA_SCHEMA = "recipe-card@v1"
RECIPE_CARD_V1_SCHEMA_PATH = data_path("recipes", "recipe-card-v1.schema.json")
# Variant enum. Provisional single value (the implemented two-layer
# hero-plus-layout composition); gh #303 owns the full taxonomy and may
# extend this tuple — the schema enum must stay in sync (test-pinned).
RECIPE_CARD_VARIANTS = ("hero-plus-layout",)
FRONTIERS_PATH = data_path("localization", "market-featured-frontiers.json")
_REQUIRED_TEMPLATE_SECTIONS = (
    "schema",
    "tokens_ref",
    "page",
    "printer_safe",
    "columns",
    "header",
    "meta_bar",
    "zones",
    "substrates",
    "production_specs",
    "wireframe",
    "validation",
)
_REQUIRED_ZONE_IDS = (
    "corner_accent_left",
    "corner_accent_right",
    "raw_ingredient_sketch",
    "technique_sketch",
    "finished_plate_sketch",
)
# art zones carry an opaque white base coat; corner accents do not
_ART_ZONE_IDS = (
    "raw_ingredient_sketch",
    "technique_sketch",
    "finished_plate_sketch",
)
_VALID_UNITS = frozenset({"in", "mm", "pt", "fraction"})

# Bear Brown / Blaze Orange / Frontier Green — same anchors the context pack carries
BEAR_BROWN = (0x3B, 0x23, 0x16)
BLAZE_ORANGE = (0xE8, 0x53, 0x0E)
CARD_W, CARD_H = 1080, 1080  # 1x1 social card
HERO_H = 560  # top region is the text-free image layer

_STOP = frozenset(
    {"the", "and", "for", "with", "your", "kodiak", "cakes", "mix", "a", "of", "to",
     "in", "on", "power", "cup", "cups", "box", "pouch", "flapjack", "waffle"}
)


def _tokens(text: str) -> set[str]:
    raw = re.split(r"[^a-z0-9]+", str(text).lower())
    return {t for t in raw if len(t) > 2 and t not in _STOP}


def _load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        return []
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# recipe-card.json template: load, validate, resolve geometry.
# Geometry is READ from the template; no physical value is duplicated here as a
# Python literal. Every physical value is {"value": N, "unit": U}.
# --------------------------------------------------------------------------- #


def load_recipe_card_template(path: str | Path | None = None) -> dict:
    """Load the recipe-card template JSON. Defaults to the repo template
    (references/templates/recipe-card.json), mirroring how RECIPES_PATH anchors
    off _ROOT. Raises FileNotFoundError if the path is missing so callers get a
    clear signal rather than a silent empty dict."""
    p = Path(path) if path is not None else RECIPE_CARD_TEMPLATE_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _read_dim(node: object) -> tuple[float, str] | None:
    """Unit-aware accessor: {"value": N, "unit": U} -> (N, U). Returns None for
    anything that is not a value+unit pair. Never coerces a bare number into a
    dimension — a missing unit is a validation problem, not a default."""
    if isinstance(node, dict) and "value" in node and "unit" in node:
        value = node["value"]
        unit = node["unit"]
        if isinstance(value, (int, float)) and isinstance(unit, str):
            return float(value), unit
    return None


def validate_recipe_card_template(tmpl: dict) -> list[str]:
    """Return a list of problems with the template (empty list = valid).

    Checks: schema id, all required top-level sections present, zone ids unique,
    required zones present, and that every physical dimension it inspects carries
    a unit. Numbers are read from the template, never assumed."""
    problems: list[str] = []
    if not isinstance(tmpl, dict):
        return ["template is not a JSON object"]

    if tmpl.get("schema") != RECIPE_CARD_SCHEMA:
        problems.append(
            f"schema is {tmpl.get('schema')!r}, expected {RECIPE_CARD_SCHEMA!r}"
        )

    for section in _REQUIRED_TEMPLATE_SECTIONS:
        if section not in tmpl:
            problems.append(f"missing required section: {section}")

    zones = tmpl.get("zones")
    if not isinstance(zones, list):
        problems.append("zones is not an array")
        zones = []

    ids = [z.get("id") for z in zones if isinstance(z, dict)]
    if len(ids) != len(set(ids)):
        problems.append("zone ids are not unique")

    id_set = set(ids)
    for required in _REQUIRED_ZONE_IDS:
        if required not in id_set:
            problems.append(f"missing required zone: {required}")

    # every physical dimension we inspect must carry a unit
    for z in zones:
        if not isinstance(z, dict):
            continue
        zid = z.get("id", "<unknown>")
        for key in ("width", "height"):
            if key in z and _read_dim(z[key]) is None:
                problems.append(f"zone {zid} {key} missing value+unit")

    page = tmpl.get("page")
    if isinstance(page, dict):
        for key in ("width", "height"):
            if key in page and _read_dim(page[key]) is None:
                problems.append(f"page {key} missing value+unit")

    ceiling = (tmpl.get("production_specs") or {}).get("ink_coverage_ceiling")
    if isinstance(ceiling, dict) and _read_dim(ceiling) is None:
        problems.append("ink_coverage_ceiling missing value+unit")

    return problems


def resolve_geometry(tmpl: dict) -> dict:
    """Resolve template geometry into a compact structure: page, printer_safe,
    columns, and zones keyed by id. Every physical value is exposed as (value,
    unit) via the unit-aware accessor — bare numbers are never fabricated.

    The accessor is attached under "read_dim" so callers can pull additional
    dimensions with the same unit-safe semantics."""
    page = tmpl.get("page") or {}
    printer_safe = tmpl.get("printer_safe") or {}
    columns = tmpl.get("columns") or {}
    zones = tmpl.get("zones") or []

    def dims(node: dict, *keys: str) -> dict:
        out: dict[str, tuple[float, str] | None] = {}
        for k in keys:
            out[k] = _read_dim(node.get(k)) if isinstance(node, dict) else None
        return out

    zones_by_id: dict[str, dict] = {}
    for z in zones:
        if not isinstance(z, dict) or "id" not in z:
            continue
        zid = z["id"]
        zones_by_id[zid] = {
            "id": zid,
            "column": z.get("column"),
            "base_coat": bool(z.get("base_coat", False)),
            "width": _read_dim(z.get("width")),
            "height": _read_dim(z.get("height")),
            "clearance": _read_dim(z.get("clearance")),
        }

    usable = printer_safe.get("usable_area") or {}
    outer = printer_safe.get("outer_margin") or {}
    divider = columns.get("center_divider") or {}

    return {
        "read_dim": _read_dim,
        "page": dims(page, "width", "height"),
        "printer_safe": {
            "outer_margin": {
                side: _read_dim(outer.get(side))
                for side in ("top", "right", "bottom", "left")
            },
            "usable_area": dims(usable, "width", "height"),
        },
        "columns": {
            "count": columns.get("count"),
            "column_width": _read_dim(columns.get("column_width")),
            "center_divider_stroke": _read_dim(divider.get("stroke_weight")),
            "text_clearance": _read_dim(columns.get("text_clearance")),
        },
        "zones": zones_by_id,
    }


# --------------------------------------------------------------------------- #
# recipe-card@v1 contract: frontier lookup, render metadata, validation,
# and object -> render. Every value traces to a real source (mapping file,
# module canvas constants, template zone ids); unknowns are None, never
# guessed.
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _frontier_mapping() -> dict:
    """market -> frontier_market from the generated mapping mirror. Empty on
    any read failure so a missing file degrades to frontier_market None."""
    try:
        return json.loads(FRONTIERS_PATH.read_text(encoding="utf-8")).get(
            "markets", {}
        )
    except (OSError, ValueError):
        return {}


def frontier_market_for(market: str) -> str | None:
    """Featured-frontier code for a market, or None when unmapped. Never
    raises, never fabricates."""
    try:
        entry = _frontier_mapping().get(market) or {}
        code = entry.get("frontier_market")
        return str(code) if code else None
    except AttributeError:
        return None


def render_block() -> dict:
    """Render target metadata for the v1 contract: canvas dimensions and the
    text vs text-free region split. Dimensions come from the module canvas
    constants (the values _compose_card actually renders); zone ids from the
    template art-zone ids. No geometry is duplicated as a new literal."""
    return {
        "variant": RECIPE_CARD_VARIANTS[0],
        "canvas": {"width": CARD_W, "height": CARD_H, "unit": "px"},
        "hero_region": {"height": HERO_H, "text_free": True},
        "layout_region": {"carries_text": True},
        "text_regions": ["title", "ingredient_line", "steps"],
        "text_free_regions": ["hero"],
    }


_PAIRING_SOURCES = frozenset(
    {
        "none",
        "ingredient-featured",
        "ingredient-overlap",
        "ingredient-rotation",
        "season-table",
        "static-default",
        "legacy-image-fallback",
    }
)
_CARD_LANGS = frozenset({"en", "es", "pt"})
_CARD_SEASONS = frozenset({"spring", "summer", "fall", "winter"})
_MONTH_RE = re.compile(r"^[0-9]{4}-[0-9]{2}$")


def validate_recipe_card_v1(card: dict) -> list[str]:
    """Check a build_recipe_card_data object against the recipe-card@v1
    contract (data/recipes/recipe-card-v1.schema.json). Returns problems
    (empty = valid). Structural only: required keys, the schema/variant/lang
    markers, recipe-ref shape, month/season formats, and the no-ingredient
    rule (ingredient null requires an explicit reason with null recipe and
    title — never an invented pick)."""
    problems: list[str] = []
    if not isinstance(card, dict):
        return ["card is not a JSON object"]
    if card.get("schema") != RECIPE_CARD_DATA_SCHEMA:
        problems.append(
            f"schema is {card.get('schema')!r}, expected {RECIPE_CARD_DATA_SCHEMA!r}"
        )
    if card.get("variant") not in RECIPE_CARD_VARIANTS:
        problems.append(
            f"variant {card.get('variant')!r} not in {list(RECIPE_CARD_VARIANTS)}"
        )
    market = card.get("market")
    if not market or not isinstance(market, str):
        problems.append("market must be a non-empty string")
    month = card.get("month")
    if month is not None and (
        not isinstance(month, str) or not _MONTH_RE.match(month)
    ):
        problems.append(f"month {month!r} is not ISO YYYY-MM")
    if card.get("lang") not in _CARD_LANGS:
        problems.append(f"lang {card.get('lang')!r} not in {sorted(_CARD_LANGS)}")
    season = card.get("season")
    if season is not None and season not in _CARD_SEASONS:
        problems.append(f"season {season!r} not in {sorted(_CARD_SEASONS)}")
    fm = card.get("frontier_market")
    if fm is not None and not isinstance(fm, str):
        problems.append("frontier_market must be a string or null")

    recipe = card.get("recipe")
    if recipe is not None:
        if not isinstance(recipe, dict):
            problems.append("recipe must be an object or null")
        else:
            if not recipe.get("id") or not isinstance(recipe.get("id"), str):
                problems.append("recipe.id must be a non-empty string")
            if not recipe.get("name") or not isinstance(
                recipe.get("name"), str
            ):
                problems.append("recipe.name must be a non-empty string")

    ingredient = card.get("ingredient")
    if ingredient is not None and (
        not isinstance(ingredient, str) or not ingredient.strip()
    ):
        problems.append("ingredient must be a non-empty string or null")
    if ingredient is None:
        if not card.get("reason") or not isinstance(card.get("reason"), str):
            problems.append("no-ingredient result must carry an explicit reason")
        if recipe is not None:
            problems.append("no-ingredient result must not carry a recipe")
        if card.get("title") is not None:
            problems.append("no-ingredient result must not carry a title")
    else:
        if recipe is not None and not card.get("title"):
            problems.append("card with a recipe must carry a title")
        steps = card.get("steps")
        if recipe is not None and (
            not isinstance(steps, list)
            or not steps
            or not all(isinstance(s, str) and s.strip() for s in steps)
        ):
            problems.append("card with a recipe must carry non-empty steps")

    for key in ("meta", "provenance", "art", "render"):
        if not isinstance(card.get(key), dict):
            problems.append(f"{key} must be an object")
    pairing = (card.get("provenance") or {}).get("pairing")
    if pairing is not None:
        if not isinstance(pairing, dict):
            problems.append("provenance.pairing must be an object")
        elif pairing.get("source") not in _PAIRING_SOURCES:
            problems.append(
                f"pairing.source {pairing.get('source')!r} not in "
                f"{sorted(_PAIRING_SOURCES)}"
            )
    return problems


def render_recipe_card_data(
    card: dict, out_dir: str | Path | None = None
) -> str | None:
    """Render a recipe-card@v1 DATA object to a PNG (object -> render).

    Consumes exactly what build_recipe_card_data emits: validates the
    contract first (ValueError with the problems on violation), resolves the
    recipe ref against the catalog (ValueError when the id is not on file —
    a dangling ref is never rendered), then composes the text-free hero plus
    text-only layout layer via the same helpers build_recipe_card uses.
    A valid no-ingredient object returns None (explicit empty state, never an
    invented card). Returns the PNG path as a string.
    """
    problems = validate_recipe_card_v1(card)
    if problems:
        raise ValueError(f"not a recipe-card@v1 object: {'; '.join(problems)}")
    recipe_ref = card.get("recipe") or {}
    if card.get("ingredient") is None or not recipe_ref:
        return None
    recipe = _recipe_by_id(str(recipe_ref.get("id") or ""))
    if recipe is None:
        raise ValueError(
            f"recipe ref {recipe_ref.get('id')!r} is not in the catalog"
        )
    market = str(card.get("market") or "")
    text_blocks = {
        "title": str(card.get("title") or recipe.get("name") or "recipe"),
        "ingredient_line": f"Local pick: {card.get('ingredient')}",
        "steps": [str(s) for s in (card.get("steps") or [])],
    }
    hero = _hero_panel(recipe, (CARD_W, HERO_H))
    iso_name = naming.build_iso_name(
        product="power-cakes",
        region=market,
        locality=naming.slugify(
            str(card.get("frontier_market") or market)
        ),
        channel="recipe-card",
        ratio="1x1",
    )
    out_root = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    return str(_compose_card(hero, text_blocks, out_root / iso_name))


def _names_ingredient(recipe: dict, ingredient: str) -> bool:
    """True when the recipe genuinely names the ingredient (substring,
    case-insensitive) in its name, ingredient lines, or tags — the strong
    matches a variety rotation may choose between."""
    low = (ingredient or "").lower().strip()
    if not low:
        return False
    fields = [str(recipe.get("name", "") or "")]
    fields += [str(x) for x in recipe.get("ingredients", []) or []]
    fields += [str(x) for x in recipe.get("tags", []) or []]
    return low in " ".join(fields).lower()


def _recipe_by_id(recipe_id: str) -> dict | None:
    """Catalog record by id, or None when the id is not on file. Never raises."""
    for r in _load_recipes():
        if r.get("id") == recipe_id:
            return r
    return None


def _season_fallback_recipe(season: str | None, month: str = "") -> dict | None:
    """Season-indexed pairing table with static default as last resort.

    A dropdown-style request (season key, month name, or holiday) that hits
    the pairing table serves its record directly; otherwise resolves the
    effective season (explicit structured request wins, else the month) and
    returns that table's recipe; an unresolvable season lands on the static
    default. Returns None only when the catalog itself lacks the paired
    record (caller keeps the legacy image-bearing fallback then). Free brief
    text is never consulted — it is display-only for pairing.
    """
    direct = _seasons.pairing_for_season(season)
    if direct["source"] == "season-table":
        recipe = _recipe_by_id(direct["recipe_id"])
        if recipe is not None:
            return recipe
        # Paired record missing from the catalog: fall through to the
        # resolve/default chain below (ends on the static default).
    resolved = _seasons.resolve_season(season, month or None)
    pairing = _seasons.pairing_for_season(resolved["season"])
    recipe = _recipe_by_id(pairing["recipe_id"])
    if recipe is not None:
        return recipe
    if pairing["source"] != "static-default":
        return _recipe_by_id(_seasons.DEFAULT_PAIRING["recipe_id"])
    return None


def _table_pairing_for(table_recipe: dict, table_pairing: dict) -> dict:
    """Honest pairing label for a served fallback recipe.

    When the served recipe IS the paired record, the table pairing stands. When
    the paired record is missing from the catalog and the static default was
    served instead, the label says static-default rather than claiming a table
    hit for a record that never shipped.
    """
    if table_recipe.get("id") == table_pairing.get("recipe_id"):
        return table_pairing
    return {
        "recipe_id": table_recipe.get("id"),
        "reason": _seasons.DEFAULT_PAIRING["reason"],
        "source": "static-default",
    }


def _pick_recipe_detail(
    ingredient: str,
    product: str | None,
    market: str = "",
    month: str = "",
    season: str | None = None,
) -> tuple[dict | None, dict]:
    """Single source of truth for recipe picking + pairing provenance.

    Same mechanics as the legacy _pick_recipe (featured_for curation, overlap
    scoring, deterministic market+month rotation), except the no-token-match
    fallback is now the season-indexed pairing table with the static default as
    last resort (legacy image-bearing fallback only when the paired record is
    missing from the catalog). Returns (recipe|None, pairing) where pairing is
    {"season", "source", "recipe_id", "reason"} — the reason is surfaced in card
    provenance. Free brief text is never an input (display-only for pairing).

    Pairing source values: none | ingredient-featured | ingredient-overlap |
    ingredient-rotation | season-table | static-default | legacy-image-fallback.
    """
    recipes = _load_recipes()
    resolved = _seasons.resolve_season(season, month or None)
    # Dropdown-style request (season key, month name, holiday) that hits the
    # pairing table directly (gh #313); otherwise the month/ISO-derived season.
    # table_season is the label downstream surfaces; table_pairing names the
    # record + reason. A direct table hit wins over the resolved season so
    # holidays (which resolve to no meteorological season) still pair.
    direct = _seasons.pairing_for_season(season)
    if direct["source"] == "season-table":
        table_pairing: dict = direct
        table_season: str | None = _seasons.pairing_season_label(season)
    else:
        table_pairing = _seasons.pairing_for_season(resolved["season"])
        table_season = resolved["season"]
    if not recipes:
        return None, {
            "season": resolved["season"],
            "source": "none",
            "recipe_id": None,
            "reason": "no recipe catalog available — no pairing attempted",
        }
    if ingredient:
        import re

        def _norm(s: str) -> str:
            return re.sub(r"\s*\(.*\)", "", str(s)).strip().lower()

        norm_low = _norm(ingredient)
        low_tokens = set(re.findall(r"[a-z]+", norm_low))
        pinned = sorted(
            (r.get("id", ""), r)
            for r in recipes
            for f in (r.get("featured_for") or [])
            if f
            and (
                _norm(f) in norm_low
                or norm_low in _norm(f)
                or bool(
                    set(re.findall(r"[a-z]+", _norm(f))) & low_tokens
                )
            )
        )
        if pinned:
            recipe = pinned[0][1]
            return recipe, {
                "season": resolved["season"],
                "source": "ingredient-featured",
                "recipe_id": recipe.get("id"),
                "reason": (
                    f"ingredient-curated: {recipe.get('id')} lists the "
                    "in-season ingredient in featured_for"
                ),
            }
    subject = _tokens(ingredient)
    if product:
        subject |= _tokens(product)
    if not subject:
        # DECISION (sprint-2 items 8+9; gh #313): an empty ingredient+product
        # still serves the season-table pick when a season resolves (explicit
        # request, month name, holiday, or month, including full YYYY-MM-DD
        # dates) instead of (None, "none"). With no resolvable season there is
        # nothing to pair, so the honest (None, "none") stands rather than
        # inventing a pick.
        if table_season is not None:
            table_recipe = _season_fallback_recipe(season, month)
            if table_recipe is not None:
                pairing = _table_pairing_for(table_recipe, table_pairing)
                return table_recipe, {
                    "season": table_season,
                    "source": pairing["source"],
                    "recipe_id": table_recipe.get("id"),
                    "reason": pairing["reason"],
                }
        return None, {
            "season": resolved["season"],
            "source": "none",
            "recipe_id": None,
            "reason": "empty ingredient and product — no pairing attempted",
        }

    scored: list[tuple[int, int, str, dict]] = []
    for r in recipes:
        hay = " ".join(
            str(r.get(k, "") or "")
            for k in ("name", "product", "base", "category", "course", "description")
        )
        loc = r.get("localize", {}) or {}
        hay += " " + " ".join(str(v) for v in loc.values())
        hay += " " + " ".join(str(x) for x in r.get("ingredients", []) or [])
        hay += " " + " ".join(str(x) for x in r.get("tags", []) or [])
        overlap = len(subject & _tokens(hay))
        has_image = 1 if r.get("image") else 0
        scored.append((overlap, has_image, r.get("id", ""), r))

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    best_overlap, _hi, _id, best = scored[0]
    if best_overlap == 0:
        # no token match — season-indexed pairing table first, static default as
        # last resort. Never fabricated: both point at real catalog records.
        table_recipe = _season_fallback_recipe(season, month)
        if table_recipe is not None:
            pairing = _table_pairing_for(table_recipe, table_pairing)
            return table_recipe, {
                "season": table_season,
                "source": pairing["source"],
                "recipe_id": table_recipe.get("id"),
                "reason": pairing["reason"],
            }
        # paired record missing from the catalog: keep the legacy image-bearing
        # fallback rather than returning nothing.
        with_image = [r for r in recipes if r.get("image")]
        legacy = with_image[0] if with_image else recipes[0]
        return legacy, {
            "season": resolved["season"],
            "source": "legacy-image-fallback",
            "recipe_id": legacy.get("id"),
            "reason": "season-paired record missing from catalog; kept legacy image-bearing fallback",
        }
    if market or month:
        strong = sorted(
            (r for (_ov, _hh, _ii, r) in scored if _ov > 0 and _names_ingredient(r, ingredient)),
            key=lambda r: r.get("id", ""),
        )
        if len(strong) > 1:
            digest = hashlib.sha256(
                f"{market}|{month}|{ingredient}".encode("utf-8")
            ).hexdigest()
            winner = strong[int(digest, 16) % len(strong)]
            return winner, {
                "season": resolved["season"],
                "source": "ingredient-rotation",
                "recipe_id": winner.get("id"),
                "reason": (
                    f"ingredient rotation: {winner.get('id')} chosen deterministically "
                    f"for {market}|{month} among recipes naming the ingredient"
                ),
            }
    return best, {
        "season": resolved["season"],
        "source": "ingredient-overlap",
        "recipe_id": best.get("id"),
        "reason": (
            f"ingredient overlap: {best.get('id')} has the best token overlap "
            "with the in-season ingredient"
        ),
    }


def pick_recipe_with_provenance(
    ingredient: str,
    product: str | None,
    market: str = "",
    month: str = "",
    season: str | None = None,
) -> tuple[dict | None, dict]:
    """Pick the recipe and report WHY: (recipe|None, {"season", "source",
    "recipe_id", "reason"}). Thin delegate of _pick_recipe_detail; the reason
    is surfaced in card provenance. Free brief text is never an input."""
    return _pick_recipe_detail(ingredient, product, market, month, season)


def _pick_recipe(
    ingredient: str, product: str | None, market: str = "", month: str = "", *, season: str | None = None
) -> dict | None:
    """Best recipe for the in-season ingredient, nearest by token overlap.

    Overlap is scored across name/localize/ingredients/tags. Recipes that carry a real
    hero image field sort ahead of image-less ones on a tie so the card gets a usable
    hero (the compote-over-power-cakes style the Atlanta muscadine case wants). Fully
    deterministic: final tie-break is the recipe id.

    Explicit curation wins first: a recipe listing the ingredient (substring,
    case-insensitive) in "featured_for" is chosen ahead of overlap scoring,
    lowest recipe id among featured matches. This is the lever for pairings
    where overlap ties on one token and the id lottery picks badly (pumpkin
    pinwheels, tuscan chicken). Curated, auditable, no silent reshuffle.

    Variety rotation: when several recipes genuinely name the ingredient and a
    market+month context is given, the winner rotates deterministically
    (sha256 of market|month|ingredient over id-sorted strong matches) so markets
    sharing an in-season ingredient do not all show the same card. Single
    strong match, weak-only matches, or no market context keep the legacy
    best-overlap winner exactly.

    season: optional structured season request (spring|summer|fall|winter). Only
    consulted when nothing matches the ingredient (zero token overlap, or an
    empty ingredient+product with a resolvable season): the season-indexed
    pairing table serves the pick, with the static default as last resort.
    Free brief text is never consulted (display-only for pairing).
    """
    recipe, _pairing = _pick_recipe_detail(ingredient, product, market, month, season)
    return recipe


def _hero_panel(recipe: dict, target: tuple[int, int]) -> Image.Image:
    """Text-free hero panel (cr-1). Uses a local recipe image if present, else a clean
    brand-color block. Remote URLs are not fetched here (no network boundary); a remote
    image field degrades to the clean block so the card stays deterministic offline."""
    w, h = target
    src = recipe.get("image")
    if src and not str(src).startswith(("http://", "https://")):
        p = Path(src)
        if not p.is_absolute():
            p = _ROOT / p
        if p.exists():
            try:
                img = Image.open(p).convert("RGB")
                # cover-fit into the hero region, no text drawn
                scale = max(w / img.width, h / img.height)
                img = img.resize((int(img.width * scale), int(img.height * scale)))
                left = (img.width - w) // 2
                top = (img.height - h) // 2
                return img.crop((left, top, left + w, top + h))
            except (OSError, ValueError):
                # unreadable/corrupt local image: fall through to the brand block
                print(f"[recipe-card] hero image unusable, using brand block: {p}")
    # clean, text-free brand-color hero block with a subtle accent band
    panel = Image.new("RGB", (w, h), BEAR_BROWN)
    draw = ImageDraw.Draw(panel)
    draw.rectangle([0, h - 12, w, h], fill=BLAZE_ORANGE)
    return panel


def _load_font(size: int):
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            # missing host font: try the next candidate, bitmap default last
            print(f"[recipe-card] host font missing, trying next: {cand}")
            continue
    return ImageFont.load_default()


def _compose_card(hero: Image.Image, text_blocks: dict, out_path: Path) -> Path:
    """Lay out the card: text-free hero on top, text panel below. Text is ONLY in the
    layout layer, never composited into the hero image (cr-1)."""
    card = Image.new("RGB", (CARD_W, CARD_H), "white")
    card.paste(hero, (0, 0))

    draw = ImageDraw.Draw(card)
    title_font = _load_font(48)
    ing_font = _load_font(30)
    step_font = _load_font(26)

    y = HERO_H + 28
    pad = 48
    draw.text((pad, y), text_blocks["title"][:40], fill=BEAR_BROWN, font=title_font)
    y += 64
    draw.text((pad, y), text_blocks["ingredient_line"][:60], fill=BLAZE_ORANGE, font=ing_font)
    y += 46
    for step in text_blocks["steps"]:
        draw.text((pad, y), f"- {step[:64]}", fill=(40, 40, 40), font=step_font)
        y += 38

    out_path.parent.mkdir(parents=True, exist_ok=True)
    card.save(out_path, "PNG")
    return out_path


def _clean_step(raw: str) -> str:
    """Collapse whitespace/newlines in a raw recipe instruction to a single tidy line."""
    return re.sub(r"\s+", " ", str(raw).replace("\r", " ").replace("\t", " ")).strip()


def publish_card(card_path: str | Path) -> str | None:
    """Upload a composed card PNG so the recipes DAM tab lists it. Returns the
    full DAM key, or None when DAM is unconfigured or the upload fails. Never
    throws — publishing must never fail a campaign.

    s3_upload_and_presign joins keys to the configured DAM prefix, so the key
    is relativized against it (brands/kodiak/recipes/x.jpg under the standard
    brands/kodiak/ prefix uploads as recipes/x.jpg and reads back verbatim).
    """
    try:
        from . import dam as _dam

        full = DAM_RECIPES_PREFIX + Path(card_path).name
        _, prefix = _dam._s3_bucket_and_prefix()
        rel = full[len(prefix):] if prefix and full.startswith(prefix) else full.lstrip("/")
        if _dam.s3_upload_and_presign(str(card_path), rel) is None:
            return None
        return full
    except Exception:  # noqa: BLE001 — any DAM/network/import failure degrades to None by contract
        return None


def _resolve_substrate(tmpl: dict, requested: str) -> tuple[str, bool]:
    """Pick a valid substrate key, falling back to the template default on an
    unknown request. Returns (substrate_key, white_base_coat_applied).

    white_base_coat_applied reflects whether the art zones carry an opaque white
    base coat under the chosen substrate — read from the substrate definition,
    not assumed. Geometry does NOT change with substrate; only surface treatment
    does."""
    substrates = tmpl.get("substrates") or {}
    default = tmpl.get("default_substrate") or "kraft"
    key = requested if requested in substrates else default
    sub = substrates.get(key) or {}
    base_coat_text = str(sub.get("art_zone_base_coat", "")).lower()
    white_base = "white base coat" in base_coat_text
    # any art zone flagged base_coat true in the template confirms the structure
    zones = tmpl.get("zones") or []
    zone_base = any(
        isinstance(z, dict) and z.get("id") in _ART_ZONE_IDS and z.get("base_coat")
        for z in zones
    )
    return key, bool(white_base and zone_base)


def _recipe_card_meta(
    tmpl: dict | None,
    *,
    substrate: str,
    ingredient: str | None,
    pairing: dict | None = None,
) -> dict:
    """Build the deterministic recipe-card metadata block. No timestamps: same
    input + template yields identical metadata. When the template is missing or
    invalid, meta degrades to safe defaults rather than fabricating geometry."""
    pairing_block = dict(pairing) if isinstance(pairing, dict) else {
        "season": None,
        "source": "none",
        "recipe_id": None,
        "reason": "no pairing attempted",
    }
    if not isinstance(tmpl, dict):
        return {
            "template_schema_version": None,
            "substrate_selected": substrate,
            "zones_emitted": [],
            "zones_empty": [],
            "art_assets_used": [],
            "white_base_coat_applied": False,
            "provenance": {
                "values_from_source": [],
                "values_proposed": [],
                "values_unknown": ["prices", "nutrition", "times", "temperatures"],
                "pairing": pairing_block,
            },
            "passed_physical_zone_validation": False,
        }

    problems = validate_recipe_card_template(tmpl)
    geometry = resolve_geometry(tmpl)
    substrate_key, white_base = _resolve_substrate(tmpl, substrate)

    zone_ids = list(geometry["zones"].keys())
    # art zones are placeholders in this specimen — empty unless a real asset
    # path exists (none are wired for the placeholder card, so all art zones are
    # empty and art_assets_used is empty)
    art_assets_used: list[str] = []
    zones_empty = [
        zid for zid in zone_ids if zid in _ART_ZONE_IDS and zid not in art_assets_used
    ]

    # provenance: the ingredient is source-confirmed via locales; the "over
    # Kodiak Power Cakes" framing is a proposed adaptation; prices/nutrition have
    # no verified source and are never fabricated
    values_from_source = [ingredient] if ingredient else []

    return {
        "template_schema_version": tmpl.get("schema"),
        "substrate_selected": substrate_key,
        "zones_emitted": zone_ids,
        "zones_empty": zones_empty,
        "art_assets_used": art_assets_used,
        "white_base_coat_applied": white_base,
        "provenance": {
            "values_from_source": values_from_source,
            "values_proposed": ["over Kodiak Power Cakes"],
            "values_unknown": ["prices", "nutrition", "times", "temperatures"],
            "pairing": pairing_block,
        },
        "passed_physical_zone_validation": not problems,
    }


def _no_pairing(reason: str, season: str | None, month: str | None) -> dict:
    """Honest pairing block for card paths that never pick a recipe."""
    resolved = _seasons.resolve_season(season, month)
    return {
        "season": resolved["season"],
        "source": "none",
        "recipe_id": None,
        "reason": reason,
    }


def build_recipe_card(
    market: str,
    *,
    month: str | None = None,
    lang: str = "en",
    out_dir: str | Path | None = None,
    publish: bool = False,
    substrate: str = "kraft",
    season: str | None = None,
) -> dict:
    """Generate a recipe card for a market + month.

    Returns:
        {card_path, ingredient, recipe, text_blocks, safety[, dam_key]} on
        success, or a no-ingredient result {ingredient: None, reason, ...} when
        the month has no seeded local ingredient (never fabricated).
        publish=True also uploads the PNG to the DAM recipes prefix (best
        effort — dam_key None when DAM is unavailable).

    Also carries a deterministic `meta` block resolved from the recipe-card
    template (schema kodiak/recipe-card@v1): template_schema_version, the
    selected substrate, emitted/empty zones, art assets used, white-base-coat
    flag, a source/proposed/unknown provenance map, and the physical-zone
    validation result. substrate defaults to "kraft" so existing callers are
    unaffected; an unknown substrate falls back to the template default.
    Geometry does not change with substrate.
    season: optional structured season request (spring|summer|fall|winter) for
    the pairing fallback; free brief text is display-only and never steers the
    pick. meta.provenance carries the pairing {season, source, recipe_id,
    reason} block.
    """
    # Load the template best-effort so metadata resolves from the source of
    # truth; a missing/broken template degrades meta to safe defaults rather
    # than failing the card or fabricating geometry.
    try:
        _tmpl: dict | None = load_recipe_card_template()
    except (OSError, ValueError):
        _tmpl = None

    resolved = resolve_this_month(market, ym=month)
    if resolved is None:
        return {
            "schema": RECIPE_CARD_DATA_SCHEMA,
            "variant": RECIPE_CARD_VARIANTS[0],
            "card_path": None,
            "ingredient": None,
            "recipe": None,
            "text_blocks": {},
            "safety": {"clean": True, "flagged": []},
            "reason": f"no retailer-frontier pair seeded for {market}",
            "meta": _recipe_card_meta(
                _tmpl,
                substrate=substrate,
                ingredient=None,
                pairing=_no_pairing(
                    "no retailer-frontier pair seeded — no pairing attempted", season, month
                ),
            ),
        }

    ingredient = resolved["ingredient"]
    resolved_month = resolved["month"]
    if not ingredient:
        return {
            "schema": RECIPE_CARD_DATA_SCHEMA,
            "variant": RECIPE_CARD_VARIANTS[0],
            "card_path": None,
            "ingredient": None,
            "recipe": None,
            "text_blocks": {},
            "safety": {"clean": True, "flagged": []},
            "reason": f"no in-season ingredient on file for {market} {resolved_month}",
            "meta": _recipe_card_meta(
                _tmpl,
                substrate=substrate,
                ingredient=None,
                pairing=_no_pairing(
                    "no in-season ingredient on file — no pairing attempted", season, resolved_month
                ),
            ),
        }

    product = "Buttermilk Power Cakes"
    recipe, pairing = pick_recipe_with_provenance(
        ingredient, product, market=market, month=resolved_month, season=season
    )
    if recipe is None:
        return {
            "schema": RECIPE_CARD_DATA_SCHEMA,
            "variant": RECIPE_CARD_VARIANTS[0],
            "card_path": None,
            "ingredient": ingredient,
            "recipe": None,
            "text_blocks": {},
            "safety": {"clean": True, "flagged": []},
            "reason": "no recipe catalog available",
            "meta": _recipe_card_meta(
                _tmpl, substrate=substrate, ingredient=ingredient, pairing=pairing
            ),
        }

    # ---- text blocks via B1: on-brand + safety-gated + dialect-correct ---- #
    subject = {"name": product, "description": recipe.get("name", "")}
    title = rewrite_headline(
        f"{ingredient.title()} over Kodiak Power Cakes",
        market,
        product=subject,
        lang=lang,
        month=resolved_month,
    )
    ing_line = rewrite_headline(
        f"This month's local pick: {ingredient}",
        market,
        product=subject,
        lang=lang,
        month=resolved_month,
    )

    raw_steps = recipe.get("instructions") or recipe.get("ingredients") or []
    step_texts: list[str] = []
    step_results: list[dict] = []
    for raw in raw_steps[:5]:
        cleaned = _clean_step(raw)
        if not cleaned:
            continue
        res = rewrite_headline(cleaned[:80], market, product=subject, lang=lang, month=resolved_month)
        step_texts.append(res["text"])
        step_results.append(res)

    # Standing copy law: bare KODIAK never ships on a card (logo lockups only).
    text_blocks = {
        "title": clean_brand_copy(title["text"]),
        "ingredient_line": clean_brand_copy(ing_line["text"]),
        "steps": [clean_brand_copy(s) for s in step_texts],
    }

    # aggregate safety across every emitted block — all flow through B1, so all are
    # already clean/redacted; re-assert here so the card carries an explicit verdict
    all_text = " ".join([title["text"], ing_line["text"], *step_texts])
    card_safety = safety.check_text(all_text)

    # ---- compose: text-free hero + text-only layout layer ---- #
    hero = _hero_panel(recipe, (CARD_W, HERO_H))
    iso_name = naming.build_iso_name(
        product="power-cakes",
        region=market,
        locality=naming.slugify(resolved["frontier_sister"] or market),
        channel="recipe-card",
        ratio="1x1",
    )
    out_root = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    card_path = _compose_card(hero, text_blocks, out_root / iso_name)

    dam_key = publish_card(card_path) if publish else None
    return {
        "schema": RECIPE_CARD_DATA_SCHEMA,
        "variant": RECIPE_CARD_VARIANTS[0],
        "card_path": str(card_path),
        "ingredient": ingredient,
        "recipe": {"id": recipe.get("id"), "name": recipe.get("name")},
        "text_blocks": text_blocks,
        "safety": card_safety,
        "month": resolved_month,
        "step_results": step_results,
        "dam_key": dam_key,
        "meta": _recipe_card_meta(
            _tmpl, substrate=substrate, ingredient=ingredient, pairing=pairing
        ),
    }



# --------------------------------------------------------------------------- #
# card-DATA builder (no image): structured object matching recipe-card.json
# zones, for an offline frontend to render into existing HTML/CSS. Reuses the
# same helpers build_recipe_card uses (resolve_this_month,
# pick_recipe_with_provenance, _clean_step, rewrite_headline, clean_brand_copy,
# load_recipe_card_template, _resolve_substrate). Non-fabrication is strict: times/serves/cost come ONLY
# from real recipe fields, else null; prices attach only from a verified
# recipe-level cost record, else null.
# --------------------------------------------------------------------------- #

# real recipe fields that back the meta bar. est_cost appears only with a
# verified recipe-level cost record, else null and listed under values_unknown.
_META_SOURCE_FIELDS = {
    "prep": "prepTime",
    "cook": "cookTime",
    "serves": "yield",
}

# leading-verb detection: uppercase a real leading action word only. No verb is
# fabricated — if the step opens with a non-word token, it is left untouched.
_LEADING_WORD_RE = re.compile(r"^([A-Za-z][A-Za-z'-]*)(.*)$", re.DOTALL)


def _bold_action_step(text: str) -> str:
    """Uppercase the step's real leading word so it reads as a bold action verb.

    Only the first genuine word is uppercased; nothing is added. A step that does
    not start with a word (e.g. a quantity) is returned unchanged — no cooking
    action is invented.
    """
    m = _LEADING_WORD_RE.match(text.strip())
    if not m:
        return text.strip()
    lead, rest = m.group(1), m.group(2)
    return f"{lead.upper()}{rest}"


def _recipe_costs(recipe: dict | None, lines: list[str]) -> list[str] | None:
    """Return verified per-line prices aligned to ingredient lines, else None.

    A cost record counts only when recipe.ingredient_costs is a complete,
    same-length, non-blank parallel list. Partial cost data degrades to null
    rather than guessing which line a price belongs to.
    """
    r = recipe or {}
    costs = r.get("ingredient_costs")
    if not isinstance(costs, list) or len(costs) != len(lines):
        return None
    cleaned: list[str] = []
    for cost in costs:
        if cost is None:
            return None
        text = str(cost).strip()
        if not text:
            return None
        cleaned.append(text)
    return cleaned


def _recipe_meta_bar(
    recipe: dict | None, lines: list[str] | None = None
) -> tuple[dict, list[str]]:
    """Build the four-column meta bar from real recipe fields only.

    Returns (meta, unknown_keys). Any column with no backing recipe field is
    null and its logical group is reported unknown. est_cost and prices stay
    unknown unless the recipe carries a verified est_cost plus a complete
    ingredient_costs record.
    """
    meta: dict = {"prep": None, "cook": None, "serves": None, "est_cost": None}
    unknown: list[str] = []
    r = recipe or {}
    for col, field in _META_SOURCE_FIELDS.items():
        val = r.get(field)
        meta[col] = str(val).strip() if val not in (None, "", []) else None
    if meta["prep"] is None and meta["cook"] is None:
        unknown.append("times")
    if meta["serves"] is None:
        unknown.append("serves")
    # est_cost and prices are never fabricated: they appear only with a
    # verified recipe-level cost record.
    est = r.get("est_cost")
    est_text = str(est).strip() if est not in (None, "", []) else None
    prices = _recipe_costs(recipe, lines or [])
    meta["est_cost"] = est_text if est_text and prices else None
    if meta["est_cost"] is None:
        unknown.append("prices")
    unknown.append("temperatures")
    return meta, unknown


# the three art zones the recipe card renders hand-drawn line-art into. Keyed
# short-names (no _sketch suffix) match recipe_art.ZONES and the seed art map.
_ART_KEYS = ("raw_ingredient", "technique", "finished_plate")


def _normalize_art(art: dict[str, str | None] | None) -> dict[str, str | None]:
    """Return a {raw_ingredient, technique, finished_plate} url map with all three
    keys present. Missing/None input degrades to all-null so the frontend never
    KeyErrors — a null url signals fall-back to the existing SVG placeholder."""
    src = art or {}
    return {k: (src.get(k) or None) for k in _ART_KEYS}


def _overlay_recipe_art(
    art_block: dict[str, str | None], recipe: dict
) -> dict[str, str | None]:
    """Prefer the picked recipe's own published art over shared ingredient art.

    A recipe carrying art_slug (e.g. winter-squash-griddle-cakes) wins per zone
    wherever that slug has a published drawing; unpublished zones keep the
    ingredient-level url. Markets sharing an ingredient but rotating to
    different recipes therefore render different drawings instead of identical
    cards. Offline / no-creds: exists checks read False and the block passes
    through untouched. Never throws.
    """
    slug = str(recipe.get("art_slug") or "").strip()
    if not slug:
        return art_block
    try:
        from . import dam as _dam

        out = dict(art_block)
        for zone in _ART_KEYS:
            if _dam.recipe_art_exists(slug, zone):
                out[zone] = _dam.recipe_art_site_url(slug, zone)
        return out
    except Exception:  # noqa: BLE001 — art overlay is best-effort
        return art_block


def build_recipe_card_data(
    market: str,
    *,
    month: str | None = None,
    lang: str = "en",
    substrate: str = "kraft",
    art: dict[str, str | None] | None = None,
    season: str | None = None,
) -> dict:
    """Build a structured recipe-card DATA object (no image composed).

    The shape mirrors the recipe-card.json zones so an offline frontend can render
    it into existing HTML/CSS. Ingredient comes from locales.resolve_this_month
    (single source of truth, never fabricated). Non-fabrication is strict:
    prep/cook/serves come only from a matched recipe's real prepTime/cookTime/yield
    fields; est_cost and ingredient prices appear only from a verified
    recipe-level cost record, else null and listed in
    provenance.values_unknown. Steps derive from the recipe instructions
    (falling back to ingredients like build_recipe_card) with the real leading word
    uppercased as a bold action verb — no cooking action is invented.

    lang: "en" passes through untouched; other languages machine-translate the
    title, ingredient lines, and steps (recipe_i18n) with an allergen fail-safe
    that falls back to English per line. Prices, meta, and recipe identity stay
    put; provenance.translation records providers and fallback lines.

    art (optional): a {"raw_ingredient": url|None, "technique": url|None,
    "finished_plate": url|None} map of Nova-Canvas-generated hand-drawn line-art
    URLs (from recipe_cards_emit.seed_recipe_art). When a zone url is present the
    frontend renders the drawing; when None (offline, no art seeded, or a rejected
    render) the frontend falls back to its existing SVG placeholder. Every card
    carries a normalized `art` block with all three keys so the frontend never
    KeyErrors — missing input degrades to all-null, never crashes.

    No-pair / no-ingredient months return an honest shape carrying `reason` and
    ingredient:null rather than crashing, mirroring build_recipe_card's early
    returns.

    season (optional): structured season request (spring|summer|fall|winter).
    Only consulted when nothing matches the in-season ingredient — the
    season-indexed pairing table serves the pick, with the static default as
    last resort. Free brief text is display-only and never steers the pick.
    provenance carries the pairing {season, source, recipe_id, reason} block.
    """
    art_block = _normalize_art(art)
    try:
        tmpl: dict | None = load_recipe_card_template()
    except (OSError, ValueError):
        tmpl = None
    substrate_key = (
        _resolve_substrate(tmpl, substrate)[0] if isinstance(tmpl, dict) else substrate
    )

    seasonal = resolve_seasonal_moments(market)

    def _empty(reason: str, *, resolved_month: str | None, ingredient: str | None) -> dict:
        pairing = _no_pairing(reason, season, resolved_month)
        return {
            "schema": RECIPE_CARD_DATA_SCHEMA,
            "variant": RECIPE_CARD_VARIANTS[0],
            "market": market,
            "frontier_market": frontier_market_for(market),
            "month": resolved_month,
            "season": pairing["season"],
            "lang": lang,
            "substrate": substrate_key,
            "title": None,
            "meta": {"prep": None, "cook": None, "serves": None, "est_cost": None},
            "ingredients": [],
            "steps": [],
            "sketch_zones": list(_ART_ZONE_IDS),
            "seasonal_moment": seasonal,
            "provenance": {
                "values_from_source": [ingredient] if ingredient else [],
                "values_proposed": [],
                "values_unknown": ["times", "temperatures", "prices", "serves"],
                "pairing": pairing,
            },
            "ingredient": ingredient,
            "recipe": None,
            "reason": reason,
            "art": art_block,
            "render": render_block(),
        }

    resolved = resolve_this_month(market, ym=month)
    if resolved is None:
        return _empty(
            f"no retailer-frontier pair seeded for {market}",
            resolved_month=None,
            ingredient=None,
        )

    ingredient = resolved["ingredient"]
    resolved_month = resolved["month"]
    if not ingredient:
        return _empty(
            f"no in-season ingredient on file for {market} {resolved_month}",
            resolved_month=resolved_month,
            ingredient=None,
        )

    product = "Buttermilk Power Cakes"
    recipe, pairing = pick_recipe_with_provenance(
        ingredient, product, market=market, month=resolved_month, season=season
    )
    if recipe is None:
        return _empty(
            "no recipe catalog available",
            resolved_month=resolved_month,
            ingredient=ingredient,
        )

    # title is the recipe's real catalog name — never a rewritten marketing
    # variant. Market + month ride as their own factual fields on the card,
    # so the title cannot disagree with the recipe it names.
    art_block = _overlay_recipe_art(art_block, recipe)
    title_text = clean_brand_copy(str(recipe.get("name", "") or "recipe"))

    # steps are the recipe's real instructions, cleaned and verb-bolded only.
    # No rewrite pass: the rewriter turns instructions into exclamatory ad
    # copy ("CASTROVILLE'S ... Delight!") that reads as fabricated content.
    raw_steps = recipe.get("instructions") or recipe.get("ingredients") or []
    steps: list[str] = []
    for raw in raw_steps:
        cleaned = _clean_step(raw)
        if not cleaned:
            continue
        step = clean_brand_copy(cleaned)
        if step:
            steps.append(_bold_action_step(step))

    raw_lines = [
        str(line).strip()
        for line in (recipe.get("ingredients") or [])
        if str(line).strip()
    ]
    meta, unknown = _recipe_meta_bar(recipe, raw_lines)
    prices = _recipe_costs(recipe, raw_lines)

    # ingredients: the matched recipe's real ingredient lines (quantities
    # included, verbatim from the catalog record); prices attach only from a
    # complete verified cost record. Falls back to the lone in-season pick
    # only when the recipe carries no ingredient list of its own.
    if raw_lines and prices:
        ingredients = [
            {"qty_name": line, "price": price}
            for line, price in zip(raw_lines, prices)
        ]
    else:
        ingredients = [
            {"qty_name": line, "price": None} for line in raw_lines
        ] or [{"qty_name": ingredient, "price": None}]

    # lang: English passes through untouched; other languages travel the
    # machine-translation chain with an allergen fail-safe (recipe_i18n).
    # Prices and meta stay universal; the recipe identity stays English.
    i18n = translate_recipe_texts(
        title_text,
        [entry["qty_name"] for entry in ingredients],
        steps,
        lang,
        market,
    )
    ingredients = [
        {"qty_name": text, "price": entry["price"]}
        for text, entry in zip(i18n["ingredients"], ingredients)
    ]
    provenance: dict = {
        "values_from_source": [ingredient],
        "values_proposed": ["over Kodiak Power Cakes"],
        "values_unknown": unknown,
        "pairing": pairing,
    }
    # the emitted matrix is English throughout: only non-English cards carry
    # a translation block, so today's payload stays byte-identical.
    if lang != "en":
        provenance["translation"] = i18n["provenance"]

    return {
        "schema": RECIPE_CARD_DATA_SCHEMA,
        "variant": RECIPE_CARD_VARIANTS[0],
        "market": market,
        "frontier_market": frontier_market_for(market),
        "month": resolved_month,
        "season": pairing["season"],
        "lang": lang,
        "substrate": substrate_key,
        "title": i18n["title"],
        "meta": meta,
        "ingredients": ingredients,
        "steps": i18n["steps"],
        "sketch_zones": list(_ART_ZONE_IDS),
        "seasonal_moment": seasonal,
        "provenance": provenance,
        "ingredient": ingredient,
        "recipe": {"id": recipe.get("id"), "name": recipe.get("name")},
        "art": art_block,
        "render": render_block(),
    }
