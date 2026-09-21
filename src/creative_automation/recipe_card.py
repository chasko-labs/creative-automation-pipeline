"""Recipe-card generator — monthly local ingredient -> on-brand card (agentcore B4).

Two-layer composition (cr-1): a text-FREE hero image on top and a text-ONLY layout
panel underneath (title + ingredient line + steps). Text never ships baked into pixels;
layout owns all type so the hero stays deterministic/offline-safe.

Ingredient source — never fabricated
-------------------------------------
``data/localization/retailer-frontier-pairs.json`` is the single source of truth.
Each entry pairs a metro retailer location with a ``frontier_sister`` and a
``monthly_ingredients: {YYYY-MM: ingredient}`` map. ``locales.resolve_this_month``
reads that file (via ``_datapaths.data_path`` so it works in a repo checkout and
inside the Lambda image) and returns ``{ingredient, month, frontier_sister}`` or
``None`` when the market has no seeded pair / the month has no seeded ingredient.
Callers return an honest ``{ingredient: None, reason}`` rather than inventing one,
matching the context-pack honesty contract.

AgentCore hop — why every text block flows through B1
-------------------------------------------------------
``build_recipe_card`` rewrites *each* block (title, ingredient line, every step)
through ``text_rewriter.rewrite_headline`` (B1). B1 is the AgentCore transport
boundary: it builds a RAG context pack (retailer, frontier sister, in-season
ingredient, nearest visual cluster, dialect traps, brand rules), makes exactly one
Bedrock Converse call to Nova Micro (``amazon.nova-micro-v1:0``), applies the
regional dialect swap when ``lang != "en"``, then gates on ``safety.check_text``
and redacts if needed. Offline / no-creds degrades to ``source="mock"`` (base
message unchanged) so CI stays green. Because every block rides B1, every block
is on-brand, dialect-correct, and safety-gated; ``build_recipe_card`` re-asserts
``safety.check_text`` over the joined output and carries the verdict in ``safety``.

Recipe selection — graceful degradation chain
---------------------------------------------
``pick_recipe_with_provenance`` / ``_pick_recipe_detail`` (single source of truth;
``_pick_recipe`` is the legacy thin wrapper) picks against ``data/recipes/
kodiak-recipes.json`` in this order — each step only runs when the previous
produced no winner, and every step cites a real catalog record or returns None:

1. ``featured_for`` curation — when the ingredient appears (case-insensitive
   substring) in a recipe's ``featured_for`` list, the lowest ``id`` among those
   curated matches wins. This is the auditable lever for pairings where token
   overlap ties badly (e.g. pumpkin pinwheels). Source ``ingredient-featured``.

2. Token-overlap scoring — ``_tokens(ingredient) ∪ _tokens(product="Buttermilk
   Power Cakes")`` vs ``_tokens(name+product+base+category+course+description
   + localize.* + ingredients + tags)``. Highest overlap wins; ties break by
   ``has_image`` (image-bearing recipes sort ahead so the hero has a real asset)
   then lexicographically lowest ``id`` — fully deterministic. Source
   ``ingredient-overlap``.

3. Variety rotation — when several recipes *genuinely name* the ingredient
   (``_names_ingredient`` substring across name/ingredients/tags) and both
   ``market`` and ``month`` are present, the winner rotates deterministically
   via ``sha256("market|month|ingredient") % len(strong)`` over id-sorted
   strong matches so co-seasonal markets do not all show the same card. Single
   strong match or no market context keeps the overlap winner.

4. Season pairing — when overlap is zero or ``ingredient+product`` yielded no
   tokens, the season-indexed table in ``season_pairing`` serves the pick:
   explicit season/month-name/holiday requests hit ``season-table`` directly
   (10 holidays + 4 seasons + 12 month names → 26 options, gh #313); otherwise
   the month-derived meteorological season is used. Failing that, the
   ``static-default`` (``apple-cinnamon-compote``) serves as last resort. Both
   point at real catalog records; a missing paired record falls through to the
   static default, and only a catalog missing that record keeps the legacy
   image-bearing fallback. Sources ``season-table`` / ``static-default`` /
   ``legacy-image-fallback``. Free brief text (``campaign_message``) is never
   consulted — it is display-only; season words are stripped only for display
   helpers.

Why layout is AgentCore's job
------------------------------
Geometry lives in ``references/templates/recipe-card.json`` (schema
``kodiak/recipe-card@v1``) as ``{"value": N, "unit": "in|mm|pt|fraction"}``; the
module *reads* every physical value via ``_read_dim``/``resolve_geometry`` and
never duplicates a literal. The ``recipe-card@v1`` *data* contract
(``data/recipes/recipe-card-v1.schema.json``) flows LLM hop → renderer →
validation → asset pack. Keeping layout inside this AgentCore-owned module
(``_compose_card`` / ``_hero_panel`` / ``render_block``) enforces cr-1
(text lives ONLY in the layout layer), keeps the DAM upload opt-in, honors
``substrates``/``white_base_coat``/``printer_safe`` without callers guessing
dimensions, and preserves the non-fabrication guarantee (prices/meta/temps only
when a real recipe field backs them).

Chain per text block (B4):

    build_recipe_card -> locales.resolve_this_month  (retailer-frontier-pairs.json)
                       -> pick_recipe_with_provenance (featured_for → overlap
                          → rotation → season-table/static-default)
                       -> text_rewriter.rewrite_headline per block (context pack
                          → Nova Micro → dialect → safety)
                       -> _hero_panel (text-free, no remote fetch)
                       -> _compose_card (text-only layout layer, cr-1)
                       -> naming.build_iso_name
                       -> publish_card (opt-in DAM upload)

``build_recipe_card_data`` reuses the same pick + non-fabrication logic but
emits no image — structured data for an offline frontend that renders into the
existing HTML/CSS zones.
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
# them up among past assets. Publish is opt-in and never fails a card — the
# AgentCore B4 hop owns the DAM side-effect; callers pass publish=True to opt
# in and a failure degrades to dam_key=None without throwing.
DAM_RECIPES_PREFIX = "brands/kodiak/recipes/"

# Repo checkout and Lambda image resolve data/ differently (pip install . does
# not bundle data/); data_path picks the layout that actually exists. Every
# file that derives from data/localization/retailer-frontier-pairs.json (via
# locales.resolve_this_month) or data/recipes/kodiak-recipes.json goes through
# this helper so the single source of truth survives packaging.
_ROOT = Path(__file__).parents[2]
RECIPES_PATH = data_path("recipes", "kodiak-recipes.json")  # recipe corpus for token-overlap / featured_for / season pairing
RECIPE_CARD_TEMPLATE_PATH = _ROOT / "references" / "templates" / "recipe-card.json"  # print-geometry master — read, never duplicated
DEFAULT_OUT_DIR = _ROOT / "output" / "recipe-cards"  # local compose output; iso name is appended per card

# recipe-card.json schema this module reads geometry from. Every physical value
# in the template is {"value": N, "unit": "in|mm|pt|fraction"}; geometry is read
# from the template, never duplicated as Python literals. Layout is AgentCore's
# job precisely so this file stays the one place dimensions are authored.
RECIPE_CARD_SCHEMA = "kodiak/recipe-card@v1"

# recipe-card@v1 DATA contract (gh #304): the versioned object that flows
# LLM-authoring hop -> renderer -> validation -> asset pack, documented at
# data/recipes/recipe-card-v1.schema.json. Distinct from RECIPE_CARD_SCHEMA
# above, which describes print-geometry zones, not card data. Both schemas are
# read/validated, never re-authored in Python.
RECIPE_CARD_DATA_SCHEMA = "recipe-card@v1"
RECIPE_CARD_V1_SCHEMA_PATH = data_path("recipes", "recipe-card-v1.schema.json")  # JSON Schema for the data contract (validate_recipe_card_v1 checks it structurally)
# Variant enum. Provisional single value (the implemented two-layer
# hero-plus-layout composition); gh #303 owns the full taxonomy and may
# extend this tuple — the schema enum must stay in sync (test-pinned).
# Single value today because AgentCore only ships the hero-plus-layout; more
# variants would be new layout branches inside _compose_card/render_block.
RECIPE_CARD_VARIANTS = ("hero-plus-layout",)
FRONTIERS_PATH = data_path("localization", "market-featured-frontiers.json")  # market -> frontier_market mirror (generated from retailer-frontier-pairs.json)
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

# Bear Brown / Blaze Orange / Frontier Green — same anchors the context pack carries;
# kept here because _hero_panel/_compose_card paint the actual PNG bytes (AgentCore
# owns layout, so these are the only color literals). Values match the brand tokens.
BEAR_BROWN = (0x3B, 0x23, 0x16)  # Kodiak Bear Brown — hero fallback + title ink
BLAZE_ORANGE = (0xE8, 0x53, 0x0E)  # Kodiak Blaze Orange — accent band + ingredient line ink
CARD_W, CARD_H = 1080, 1080  # 1x1 social card canvas (PX) — mirrors render_block() canvas contract
HERO_H = 560  # top region is the text-free image layer (cr-1); remainder is the text-only layout

# Stopwords stripped by _tokens() before overlap scoring. Brand/product generics
# (kodiak, cakes, mix, flapjack, waffle, power, cup/box/pouch) are excluded so the
# local ingredient drives the match, not the product name. Length ≤2 also dropped.
_STOP = frozenset(
    {"the", "and", "for", "with", "your", "kodiak", "cakes", "mix", "a", "of", "to",
     "in", "on", "power", "cup", "cups", "box", "pouch", "flapjack", "waffle"}
)


def _tokens(text: str) -> set[str]:
    """Tokenize for overlap scoring: lowercase, split on non-alphanum, drop
    stopwords and short tokens. Used to compare ingredient+product against every
    recipe's searchable haystack (name/product/base/category/course/description +
    localize.* + ingredients + tags). Deterministic, no stemming, no embedding."""
    raw = re.split(r"[^a-z0-9]+", str(text).lower())
    return {t for t in raw if len(t) > 2 and t not in _STOP}


def _load_recipes() -> list[dict]:
    """Load ``data/recipes/kodiak-recipes.json`` (via ``data_path``) or ``[]`` when
    absent. Every recipe is a candidate for the degradation chain: ``featured_for``
    curation → token overlap → season pairing → static default. Never raises."""
    if not RECIPES_PATH.exists():
        return []
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# recipe-card.json template: load, validate, resolve geometry.
# Geometry is READ from the template; no physical value is duplicated here as a
# Python literal. Every physical value is {"value": N, "unit": U}.
# --------------------------------------------------------------------------- #


def load_recipe_card_template(path: str | Path | None = None) -> dict:
    """Load the print-geometry template (``references/templates/recipe-card.json``).

    This is the *layout* source of truth that AgentCore owns: every physical
    dimension (page, printer_safe, columns, zones) is authored here as
    ``{"value": N, "unit": "in|mm|pt|fraction"}`` and read via ``_read_dim`` /
    ``resolve_geometry`` — never duplicated as a Python literal. Defaults to the
    repo template (anchored off ``_ROOT`` like ``RECIPES_PATH``). Raises
    ``FileNotFoundError`` if the path is missing so callers get a clear signal
    rather than a silent empty dict that would fabricate geometry.
    """
    p = Path(path) if path is not None else RECIPE_CARD_TEMPLATE_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _read_dim(node: object) -> tuple[float, str] | None:
    """Unit-aware accessor: ``{"value": N, "unit": U}`` → ``(N, U)``. Returns
    ``None`` for anything that is not a value+unit pair. Never coerces a bare
    number into a dimension — a missing unit is a validation problem (reported by
    ``validate_recipe_card_template``), not a silent default. This is how layout
    stays AgentCore-owned: geometry is *read* from the template, never assumed.
    """
    if isinstance(node, dict) and "value" in node and "unit" in node:
        value = node["value"]
        unit = node["unit"]
        if isinstance(value, (int, float)) and isinstance(unit, str):
            return float(value), unit
    return None


def validate_recipe_card_template(tmpl: dict) -> list[str]:
    """Return a list of problems with the print-geometry template (empty = valid).

    Checks: ``schema == RECIPE_CARD_SCHEMA``, all required top-level sections
    (``_REQUIRED_TEMPLATE_SECTIONS``), zone ids unique, required art/accent zones
    (``_REQUIRED_ZONE_IDS``) present, and that every physical dimension inspected
    carries a ``value+unit`` pair via ``_read_dim``. Numbers are *read* from the
    template, never assumed — AgentCore layout correctness depends on this gate.
    """
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
    """Resolve the print-geometry template into ``{page, printer_safe, columns,
    zones}`` keyed by id. Every physical value is exposed as ``(value, unit)``
    via ``_read_dim`` — bare numbers are never fabricated.

    The accessor is attached under ``"read_dim"`` so callers can pull additional
    dimensions with the same unit-safe semantics. This is the only place physical
    geometry is materialized; callers that need a dimension must go through this
    resolver rather than hard-coding a literal.
    """
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
    """Cached ``market -> {frontier_market, ...}`` from the generated mirror
    ``data/localization/market-featured-frontiers.json`` (itself derived from
    ``data/localization/retailer-frontier-pairs.json``). Empty on any read failure
    so a missing file degrades gracefully to ``frontier_market=None`` rather than
    raising. The upstream single source of truth remains retailer-frontier-pairs.json
    via ``locales.resolve_this_month``; this mirror only enriches ``frontier_market``
    codes on the emitted card.
    """
    try:
        return json.loads(FRONTIERS_PATH.read_text(encoding="utf-8")).get(
            "markets", {}
        )
    except (OSError, ValueError):
        return {}


def frontier_market_for(market: str) -> str | None:
    """Featured-frontier code (e.g. ``US-GA-SENOIA``) for a market, or ``None``
    when unmapped. Reads ``_frontier_mapping()`` (which mirrors
    retailer-frontier-pairs.json). Never raises, never fabricates — unmapped
    markets surface ``frontier_market=None`` on the card.
    """
    try:
        entry = _frontier_mapping().get(market) or {}
        code = entry.get("frontier_market")
        return str(code) if code else None
    except AttributeError:
        return None


def render_block() -> dict:
    """Render-target metadata for the ``recipe-card@v1`` data contract: canvas
    dimensions and the text vs text-free region split.

    Dimensions come from the module canvas constants (``CARD_W``/``CARD_H``/
    ``HERO_H``) — the values ``_compose_card`` / ``_hero_panel`` actually render —
    and zone ids from ``_ART_ZONE_IDS``. No geometry is duplicated as a new
    literal; layout stays AgentCore-owned and this block merely describes it for
    the data contract / frontend renderer.
    """
    return {
        "variant": RECIPE_CARD_VARIANTS[0],
        "canvas": {"width": CARD_W, "height": CARD_H, "unit": "px"},
        "hero_region": {"height": HERO_H, "text_free": True},
        "layout_region": {"carries_text": True},
        "text_regions": ["title", "ingredient_line", "steps"],
        "text_free_regions": ["hero"],
    }


# Pairing provenance sources — every card's ``provenance.pairing.source`` must be
# one of these. They narrate the degradation chain: featured_for curation → token
# overlap → deterministic rotation → season-table → static-default → legacy fallback.
# ``none`` means no pairing was attempted (no catalog or no resolvable season).
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
_CARD_LANGS = frozenset({"en", "es", "pt"})  # card ``lang`` enum — keep in sync with recipe-card-v1.schema.json
_CARD_SEASONS = frozenset({"spring", "summer", "fall", "winter"})  # meteorological seasons for pairing display
_MONTH_RE = re.compile(r"^[0-9]{4}-[0-9]{2}$")  # ISO YYYY-MM for ``month`` fields


def validate_recipe_card_v1(card: dict) -> list[str]:
    """Check a ``build_recipe_card_data`` object against the ``recipe-card@v1``
    data contract (``data/recipes/recipe-card-v1.schema.json``).

    Returns ``problems`` (empty = valid). Structural only — no I/O, no LLM call:
    required keys, ``schema == RECIPE_CARD_DATA_SCHEMA``, ``variant`` in
    ``RECIPE_CARD_VARIANTS``, ``market``/``lang``/``month``/``season`` formats,
    ``recipe`` ref shape, and the no-ingredient rule (``ingredient is None``
    requires an explicit ``reason`` with ``recipe is None`` and ``title is None``
    — never an invented pick). This is the AgentCore validation gate before
    ``render_recipe_card_data`` composes pixels.
    """
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
    """Render a ``recipe-card@v1`` DATA object to a PNG (object → render).

    AgentCore's image boundary: consumes exactly what ``build_recipe_card_data``
    emits (which itself derived the ingredient from
    ``data/localization/retailer-frontier-pairs.json`` via
    ``locales.resolve_this_month``). Validates the data contract first
    (``ValueError`` with joined problems on violation), resolves the recipe ref
    against the catalog (``ValueError`` when the id is not on file — a dangling
    ref is never rendered), then composes the text-free hero (``_hero_panel``)
    plus text-only layout layer (``_compose_card``, cr-1) via the same helpers
    ``build_recipe_card`` uses. A valid no-ingredient object returns ``None``
    (explicit empty state, never an invented card). Returns the PNG path string.
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
    """True when the recipe *genuinely names* the ingredient (case-insensitive
    substring) in its ``name``, ``ingredients`` lines, or ``tags``.

    Used to separate *strong* matches (eligible for deterministic
    ``ingredient-rotation``) from weak overlap-only matches. A recipe that
    merely shares a token via overlap but does not name the ingredient is not
    strong and never enters the rotation lottery.
    """
    low = (ingredient or "").lower().strip()
    if not low:
        return False
    fields = [str(recipe.get("name", "") or "")]
    fields += [str(x) for x in recipe.get("ingredients", []) or []]
    fields += [str(x) for x in recipe.get("tags", []) or []]
    return low in " ".join(fields).lower()


def _recipe_by_id(recipe_id: str) -> dict | None:
    """Catalog record by ``id`` from ``data/recipes/kodiak-recipes.json``, or
    ``None`` when the id is not on file. Lookup is linear scan via
    ``_load_recipes()`` — catalog is small. Never raises; missing ids degrade to
    ``None`` so callers can fall through to ``static-default`` / legacy fallback.
    """
    for r in _load_recipes():
        if r.get("id") == recipe_id:
            return r
    return None


def _season_fallback_recipe(season: str | None, month: str = "") -> dict | None:
    """Season-indexed pairing table with ``static-default`` as last resort.

    The tail of the degradation chain (after ``featured_for`` → overlap → rotation
    have failed). A dropdown-style request (season key, month name, or holiday)
    that hits ``season_pairing.pairing_for_season`` serves its record directly;
    otherwise resolves the effective season via ``season_pairing.resolve_season``
    (explicit structured request wins, else the month's meteorological season)
    and returns that table's recipe; an unresolvable season lands on the static
    default (``apple-cinnamon-compote``). Returns ``None`` only when the catalog
    itself lacks the paired record — caller then keeps the legacy image-bearing
    fallback. Free brief text is never consulted (display-only for pairing).
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

    When the served recipe *is* the paired record, the table pairing stands. When
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

    Implements the full graceful-degradation chain against
    ``data/recipes/kodiak-recipes.json``. The ingredient itself comes from
    ``data/localization/retailer-frontier-pairs.json`` via
    ``locales.resolve_this_month`` — this function never invents one.

    Order (each step only when the previous yielded no winner):

    1. ``featured_for`` curation (``ingredient-featured``) — ingredient substring
       in a recipe's ``featured_for`` list; lowest ``id`` wins.
    2. Token overlap (``ingredient-overlap``) — ``_tokens(ingredient ∪ product)``
       vs recipe haystack; best overlap wins with ``has_image`` then ``id`` tie-break.
    3. Variety rotation (``ingredient-rotation``) — when multiple *strong*
       (``_names_ingredient``) matches exist and ``market+month`` are present,
       deterministic ``sha256(market|month|ingredient)`` rotation.
    4. Season pairing — on zero overlap or empty ``ingredient+product``, the
       season-indexed table (``season_pairing``: 4 seasons + 12 months + 10
       holidays, gh #313) serves the pick; ``static-default`` as last resort;
       only a catalog missing that record keeps ``legacy-image-fallback``.

    Returns ``(recipe|None, pairing)`` where ``pairing`` is
    ``{"season", "source", "recipe_id", "reason"}`` — ``reason`` is surfaced
    in ``meta.provenance`` / ``provenance`` so the card narrates *why* it paired.
    ``pairing["source"]`` is one of ``_PAIRING_SOURCES``. Free brief text is never
    an input (display-only for pairing); ``season`` is the only structured season
    signal (spring|summer|fall|winter, month names, holidays).
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
    """Pick the recipe and report *why*: ``(recipe|None, {"season", "source",
    "recipe_id", "reason"})``. Thin public delegate of ``_pick_recipe_detail``
    (which documents the full degradation chain).

    The ingredient is the in-season value from
    ``data/localization/retailer-frontier-pairs.json`` via
    ``locales.resolve_this_month`` — never fabricated. ``product`` is typically
    ``"Buttermilk Power Cakes"`` (so "power cakes" tokens do not swamp the
    ingredient). ``market``/``month`` enable deterministic rotation; ``season``
    (season key / month name / holiday) steers the season-table fallback. Free
    brief text is never an input; ``reason`` is surfaced in card provenance.
    """
    return _pick_recipe_detail(ingredient, product, market, month, season)


def _pick_recipe(
    ingredient: str, product: str | None, market: str = "", month: str = "", *, season: str | None = None
) -> dict | None:
    """Best recipe for the in-season ingredient — legacy thin wrapper.

    Delegates to ``_pick_recipe_detail`` and returns only the recipe (provenance
    discarded). Kept for callers that need just the pick. The degradation chain
    (``featured_for`` → overlap → rotation → season-table/static-default) is
    documented on ``_pick_recipe_detail`` / ``pick_recipe_with_provenance``.
    Ingredient comes from ``data/localization/retailer-frontier-pairs.json`` via
    ``locales.resolve_this_month`` — never fabricated. Free brief text is never
    consulted; ``season`` is the only structured season signal.

    Best recipe for the in-season ingredient, nearest by token overlap.

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
    """Text-free hero panel (cr-1) — the *image* half of the AgentCore two-layer card.

    Uses a local ``recipe["image"]`` file if present (cover-fit, center-cropped,
    no text drawn); otherwise a clean brand-color block (``BEAR_BROWN`` with a
    ``BLAZE_ORANGE`` accent band). Remote URLs are *never* fetched here (no network
    boundary) — a remote ``image`` field degrades to the clean block so the card
    stays deterministic offline. Text lives ONLY in ``_compose_card``'s layout layer;
    this panel never carries words, satisfying cr-1.
    """
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
    """Load a host TTF for the layout layer, falling back to PIL's bitmap default.

    Tries DejaVuSans-Bold then DejaVuSans; missing fonts degrade silently so card
    composition never throws for a font. All type lives in the layout layer
    (AgentCore owns placement), never in ``_hero_panel``.
    """
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
    """Lay out the two-layer card: text-free hero on top, text panel below.

    AgentCore owns layout: the hero (from ``_hero_panel``) is pasted at ``(0,0)``
    with height ``HERO_H`` (``CARD_W × HERO_H``), then title / ingredient line /
    steps are drawn *only* in the layout layer below it (``BEAR_BROWN`` title,
    ``BLAZE_ORANGE`` ingredient line, neutral steps). This enforces cr-1 — text
    is never composited into the hero image. The canvas (``CARD_W × CARD_H``)
    and regions are described for the data contract by ``render_block()``.
    """
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
    """Collapse whitespace/newlines in a raw recipe instruction to a single tidy
    line. Used before B1 rewriting (``build_recipe_card``) and before verb-bolding
    (``build_recipe_card_data``) so multi-line catalog instructions become one
    layout-ready line. No content invented.
    """
    return re.sub(r"\s+", " ", str(raw).replace("\r", " ").replace("\t", " ")).strip()


def publish_card(card_path: str | Path) -> str | None:
    """Upload a composed card PNG so the recipes DAM tab lists it (opt-in side-effect).

    Returns the full DAM key (``DAM_RECIPES_PREFIX + filename``) or ``None`` when
    DAM is unconfigured or the upload fails. Never throws — publishing must never
    fail a campaign or card. ``dam.s3_upload_and_presign`` joins keys to the
    configured DAM prefix, so the key is relativized against it
    (``brands/kodiak/recipes/x.jpg`` under the standard ``brands/kodiak/`` prefix
    uploads as ``recipes/x.jpg`` and reads back verbatim). Only
    ``build_recipe_card`` calls this, gated on ``publish=True``.
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
    """Pick a valid substrate key for the print-geometry template.

    Falls back to ``template["default_substrate"]`` (``"kraft"``) on an unknown
    request. Returns ``(substrate_key, white_base_coat_applied)`` where
    ``white_base_coat_applied`` reflects whether the art zones carry an opaque
    white base coat under the chosen substrate — *read* from
    ``substrates[key].art_zone_base_coat`` *and* the ``base_coat`` flag on
    ``_ART_ZONE_IDS``, not assumed. Geometry does NOT change with substrate;
    only surface treatment does — layout stays AgentCore-owned and
    substrate-agnostic.
    """
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
    """Build the deterministic ``meta`` block for ``build_recipe_card`` / data cards.

    No timestamps: same input + template yields identical metadata (reproducible
    AgentCore output). When the template is missing or invalid, meta degrades to
    safe defaults (``white_base_coat_applied=False``, ``passed_physical_zone_…=False``)
    rather than fabricating geometry. ``pairing`` (``{"season", "source",
    "recipe_id", "reason"}`` from ``_pick_recipe_detail``) is surfaced under
    ``provenance.pairing`` so the card narrates *why* it paired; ``ingredient``
    (from ``data/localization/retailer-frontier-pairs.json`` via
    ``locales.resolve_this_month``) goes in ``values_from_source``.
    """
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
    """Honest ``{"season", "source": "none", "recipe_id": None, "reason"}`` for
    card paths that never pick a recipe (no pair seeded / no ingredient on file /
    no catalog). Resolves the display ``season`` via ``season_pairing.resolve_season``
    so the empty card still carries the season it *would* have used.
    """
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
    """Generate a recipe card PNG for a market + month (AgentCore B4 entrypoint).

    Ingredient source: ``data/localization/retailer-frontier-pairs.json`` via
    ``locales.resolve_this_month(market, ym=month)`` — the single source of truth.
    A market with no seeded pair or a month with no seeded ingredient returns an
    honest ``{ingredient: None, reason, ...}`` (never fabricated) with
    ``provenance.pairing.source == "none"``.

    Recipe selection: ``pick_recipe_with_provenance`` — the full degradation
    chain ``featured_for`` curation → token overlap (``_tokens``) → deterministic
    ``market|month|ingredient`` rotation → season-table / ``static-default``
    (``season_pairing``) → legacy image-bearing fallback. See
    ``_pick_recipe_detail`` for the order and provenance ``source`` values.

    AgentCore hop: every emitted text block (title, ingredient line, each step)
    flows through ``text_rewriter.rewrite_headline`` (B1) — RAG context pack →
    one Bedrock Nova Micro call → dialect swap when ``lang != "en"`` →
    ``safety.check_text`` gate + redaction. ``clean_brand_copy`` enforces the
    standing copy law (bare ``KODIAK`` never ships). Safety is re-asserted over
    the joined output and returned as ``safety``.

    Layout (why AgentCore owns it): the two-layer composition keeps the hero
    image text-free (``_hero_panel``, cr-1) and draws all type only in the
    layout layer (``_compose_card``). Geometry is *read* from
    ``references/templates/recipe-card.json`` via ``resolve_geometry`` / ``_read_dim``
    and never duplicated. The deterministic ``meta`` block carries that geometry
    (substrate, zones, ``white_base_coat``, ``provenance``, validation) for the
    asset pack.

    Args:
        market: market key (e.g. ``"US-SE-ATL"``) — looked up in retailer-frontier-pairs.json.
        month: ISO ``"YYYY-MM"``; defaults to current UTC month when ``None``.
        lang: ``"en"`` (passthrough) or ``"es"``/``"pt"`` (B1 dialect swap).
        out_dir: override output dir; defaults to ``output/recipe-cards/``.
        publish: when ``True``, opt-in DAM upload via ``publish_card`` (best-effort,
            ``dam_key`` is ``None`` on failure; never throws).
        substrate: print substrate key (e.g. ``"kraft"``); unknown falls back to
            the template default. Geometry does not change with substrate.
        season: optional structured season request (season key, month name, or
            holiday — the 26 seasonal dropdown options, gh #313); only consulted
            on the season-pairing fallback path. Free brief text is display-only
            and never steers the pick.

    Returns:
        On success: ``{schema, variant, card_path, ingredient, recipe, text_blocks,
        safety, month, step_results, dam_key, meta}`` where ``meta.provenance``
        carries ``pairing {season, source, recipe_id, reason}``. On no-ingredient
        / no-catalog: ``{ingredient: None, reason, ...}`` with ``card_path is None``.
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
# Real recipe fields that back the meta bar. ``est_cost`` appears only with a
# verified recipe-level cost record, else ``None`` and listed under values_unknown.
# Non-fabrication is strict: times/serves come ONLY from these fields, else null.
_META_SOURCE_FIELDS = {
    "prep": "prepTime",   # recipe.prepTime → meta.prep (else null, "times" unknown)
    "cook": "cookTime",   # recipe.cookTime → meta.cook (else null, "times" unknown)
    "serves": "yield",    # recipe.yield    → meta.serves (else null, "serves" unknown)
}

# Leading-verb detection for _bold_action_step: uppercase a *real* leading action
# word only. No verb is fabricated — if the step opens with a non-word token
# (quantity, number), it is left untouched so the card never invents a cooking action.
_LEADING_WORD_RE = re.compile(r"^([A-Za-z][A-Za-z'-]*)(.*)$", re.DOTALL)


def _bold_action_step(text: str) -> str:
    """Uppercase the step's real leading word so it reads as a bold action verb.

    Only the first genuine word is uppercased; nothing is added or invented. A
    step that does not start with a word (e.g. a quantity like "2 cups …") is
    returned unchanged — no cooking action is fabricated. Used by
    ``build_recipe_card_data`` after ``clean_brand_copy`` so the frontend can
    style the verb without the data inventing one.
    """
    m = _LEADING_WORD_RE.match(text.strip())
    if not m:
        return text.strip()
    lead, rest = m.group(1), m.group(2)
    return f"{lead.upper()}{rest}"


def _recipe_costs(recipe: dict | None, lines: list[str]) -> list[str] | None:
    """Return verified per-line prices aligned to ingredient lines, else ``None``.

    A cost record counts only when ``recipe.ingredient_costs`` is a complete,
    same-length, non-blank parallel list to ``lines`` (the recipe's real
    ``ingredients``). Partial or mismatched cost data degrades to ``None`` rather
    than guessing which line a price belongs to — non-fabrication for the
    price-carrying card path. Both ``_recipe_meta_bar`` and
    ``build_recipe_card_data`` use this gate.
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
    """Build the four-column meta bar from *real* recipe fields only (non-fabrication).

    Returns ``(meta, unknown_keys)`` where ``meta`` is
    ``{prep, cook, serves, est_cost}``. Any column with no backing recipe field
    is ``None`` and its logical group (``"times"`` / ``"serves"`` / ``"prices"`` /
    ``"temperatures"``) is reported in ``unknown_keys`` / ``provenance.values_unknown``.
    ``est_cost`` and per-line ``prices`` appear only when the recipe carries both
    a verified ``est_cost`` *and* a complete ``ingredient_costs`` record
    (``_recipe_costs`` gate); otherwise they stay ``None`` and ``"prices"`` is
    listed unknown. Temperatures are always unknown (not authored on recipes).
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


# The three art zones the recipe card renders hand-drawn line-art into. Keyed
# by short-names (no ``_sketch`` suffix) matching ``recipe_art.ZONES`` and the
# seed art map. Every ``build_recipe_card_data`` card carries all three keys
# (via ``_normalize_art``) so the frontend never KeyErrors — ``None`` means
# fall back to the SVG placeholder. Layout stays AgentCore-owned; art is optional.
_ART_KEYS = ("raw_ingredient", "technique", "finished_plate")


def _normalize_art(art: dict[str, str | None] | None) -> dict[str, str | None]:
    """Return a ``{raw_ingredient, technique, finished_plate}`` URL map with all three
    keys present. Missing/``None`` input degrades to all-``None`` so the frontend
    never ``KeyError``s — a ``None`` URL signals fall-back to the existing SVG
    placeholder. Every card carries this normalized block; art is optional and
    layout never depends on it.
    """
    src = art or {}
    return {k: (src.get(k) or None) for k in _ART_KEYS}


def _overlay_recipe_art(
    art_block: dict[str, str | None], recipe: dict
) -> dict[str, str | None]:
    """Prefer the picked recipe's own published art over shared ingredient art.

    A recipe carrying ``art_slug`` (e.g. ``winter-squash-griddle-cakes``) wins
    per zone wherever that slug has a published drawing (checked via
    ``dam.recipe_art_exists``); unpublished zones keep the ingredient-level URL.
    Markets sharing an in-season ingredient but rotating (``ingredient-rotation``)
    to different recipes therefore render *different* drawings instead of
    identical cards. Offline / no-creds: exists checks read ``False`` and the
    block passes through untouched. Never throws — art is best-effort and layout
    never depends on it.
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
    """Build a structured ``recipe-card@v1`` DATA object (no image composed).

    The shape mirrors the ``recipe-card.json`` zones so an offline frontend can
    render it into existing HTML/CSS — layout stays AgentCore-owned but this
    path emits *data only* (no ``_hero_panel`` / ``_compose_card`` call).

    Ingredient source: ``data/localization/retailer-frontier-pairs.json`` via
    ``locales.resolve_this_month`` — single source of truth, never fabricated.
    No-pair / no-ingredient months return an honest shape carrying ``reason``
    and ``ingredient: None`` rather than crashing, mirroring
    ``build_recipe_card``'s early returns.

    Recipe selection: same degradation chain as ``build_recipe_card`` —
    ``pick_recipe_with_provenance`` (``featured_for`` curation → token overlap →
    deterministic rotation → season-table / ``static-default``). See
    ``_pick_recipe_detail`` for the order and ``provenance.pairing.source``
    values. Free brief text is display-only; ``season`` (season key / month
    name / holiday) is the only structured season signal.

    Non-fabrication is strict: ``prep``/``cook``/``serves`` come only from a
    matched recipe's real ``prepTime``/``cookTime``/``yield`` fields (via
    ``_recipe_meta_bar``); ``est_cost`` and per-line ``price`` appear only from
    a verified recipe-level cost record (``_recipe_costs`` gate), else ``None``
    and listed in ``provenance.values_unknown``. Steps derive from the recipe's
    real ``instructions`` (falling back to ``ingredients`` like ``build_recipe_card``)
    with the real leading word uppercased as a bold action verb
    (``_bold_action_step``) — no cooking action is invented.

    i18n: ``lang == "en"`` passes through untouched; other languages
    machine-translate the title, ingredient lines, and steps via
    ``recipe_i18n.translate_recipe_texts`` with an allergen fail-safe that falls
    back to English per line. Prices, meta, and recipe identity stay put;
    ``provenance.translation`` records providers and fallback lines.

    Art (optional): a ``{"raw_ingredient": url|None, "technique": url|None,
    "finished_plate": url|None}`` map of Nova-Canvas hand-drawn line-art URLs
    (from ``recipe_cards_emit.seed_recipe_art``). When a zone URL is present the
    frontend renders the drawing; when ``None`` (offline, no art seeded, or a
    rejected render) it falls back to its SVG placeholder. Every card carries a
    normalized ``art`` block with all three keys (``_normalize_art``) so the
    frontend never ``KeyError``s; ``_overlay_recipe_art`` prefers the picked
    recipe's own published art (``art_slug``) over shared ingredient art.

    Returns a ``recipe-card@v1`` object (validate with ``validate_recipe_card_v1``)
    carrying ``render`` (``render_block()``), ``provenance`` (including
    ``pairing {season, source, recipe_id, reason}``), ``seasonal_moment``
    (``locales.resolve_seasonal_moments``), and ``art``.
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
