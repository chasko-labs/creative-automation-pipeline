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

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import naming, safety
from .locales import resolve_seasonal_moments, resolve_this_month
from .platform_copy import clean_brand_copy
from .text_rewriter import rewrite_headline

# Composed cards publish here so the recipes DAM tab (extra_prefixes) picks
# them up among past assets. Publish is opt-in and never fails a card.
DAM_RECIPES_PREFIX = "brands/kodiak/recipes/"

_ROOT = Path(__file__).parents[2]
RECIPES_PATH = _ROOT / "data" / "recipes" / "kodiak-recipes.json"
RECIPE_CARD_TEMPLATE_PATH = _ROOT / "references" / "templates" / "recipe-card.json"
DEFAULT_OUT_DIR = _ROOT / "output" / "recipe-cards"

# recipe-card.json schema this module reads geometry from. Every physical value
# in the template is {"value": N, "unit": "in|mm|pt|fraction"}; geometry is read
# from the template, never duplicated as Python literals.
RECIPE_CARD_SCHEMA = "kodiak/recipe-card@v1"
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


def _pick_recipe(ingredient: str, product: str | None) -> dict | None:
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
    """
    recipes = _load_recipes()
    if not recipes:
        return None
    if ingredient:
        low = ingredient.lower()
        pinned = sorted(
            (r.get("id", ""), r)
            for r in recipes
            for f in (r.get("featured_for") or [])
            if f and str(f).lower() in low
        )
        if pinned:
            return pinned[0][1]
    subject = _tokens(ingredient)
    if product:
        subject |= _tokens(product)
    if not subject:
        return None

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
        # no token match — fall back to a recipe that at least has a hero image,
        # preferring a compote/fruit style, else the first recipe. Never fabricate.
        with_image = [r for r in recipes if r.get("image")]
        return with_image[0] if with_image else recipes[0]
    return best


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
            except Exception:
                pass
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
        except Exception:
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
    except Exception:
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
) -> dict:
    """Build the deterministic recipe-card metadata block. No timestamps: same
    input + template yields identical metadata. When the template is missing or
    invalid, meta degrades to safe defaults rather than fabricating geometry."""
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
        },
        "passed_physical_zone_validation": not problems,
    }


def build_recipe_card(
    market: str,
    *,
    month: str | None = None,
    lang: str = "en",
    out_dir: str | Path | None = None,
    publish: bool = False,
    substrate: str = "kraft",
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
            "card_path": None,
            "ingredient": None,
            "recipe": None,
            "text_blocks": {},
            "safety": {"clean": True, "flagged": []},
            "reason": f"no retailer-frontier pair seeded for {market}",
            "meta": _recipe_card_meta(_tmpl, substrate=substrate, ingredient=None),
        }

    ingredient = resolved["ingredient"]
    resolved_month = resolved["month"]
    if not ingredient:
        return {
            "card_path": None,
            "ingredient": None,
            "recipe": None,
            "text_blocks": {},
            "safety": {"clean": True, "flagged": []},
            "reason": f"no in-season ingredient on file for {market} {resolved_month}",
            "meta": _recipe_card_meta(_tmpl, substrate=substrate, ingredient=None),
        }

    product = "Buttermilk Power Cakes"
    recipe = _pick_recipe(ingredient, product)
    if recipe is None:
        return {
            "card_path": None,
            "ingredient": ingredient,
            "recipe": None,
            "text_blocks": {},
            "safety": {"clean": True, "flagged": []},
            "reason": "no recipe catalog available",
            "meta": _recipe_card_meta(_tmpl, substrate=substrate, ingredient=ingredient),
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
        "card_path": str(card_path),
        "ingredient": ingredient,
        "recipe": {"id": recipe.get("id"), "name": recipe.get("name")},
        "text_blocks": text_blocks,
        "safety": card_safety,
        "month": resolved_month,
        "step_results": step_results,
        "dam_key": dam_key,
        "meta": _recipe_card_meta(_tmpl, substrate=substrate, ingredient=ingredient),
    }



# --------------------------------------------------------------------------- #
# card-DATA builder (no image): structured object matching recipe-card.json
# zones, for an offline frontend to render into existing HTML/CSS. Reuses the
# same helpers build_recipe_card uses (resolve_this_month, _pick_recipe,
# _clean_step, rewrite_headline, clean_brand_copy, load_recipe_card_template,
# _resolve_substrate). Non-fabrication is strict: times/serves/cost come ONLY
# from real recipe fields, else null; prices are always null (no source).
# --------------------------------------------------------------------------- #

# real recipe fields that back the meta bar. est_cost has NO backing field in
# the catalog, so it is always null and always listed under values_unknown.
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


def _recipe_meta_bar(recipe: dict | None) -> tuple[dict, list[str]]:
    """Build the four-column meta bar from real recipe fields only.

    Returns (meta, unknown_keys). Any column with no backing recipe field is
    null and its logical group is reported unknown. est_cost has no source field
    in the catalog, so it is always null / always unknown.
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
    # est_cost never has a source; prices are never fabricated
    meta["est_cost"] = None
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


def build_recipe_card_data(
    market: str,
    *,
    month: str | None = None,
    lang: str = "en",
    substrate: str = "kraft",
    art: dict[str, str | None] | None = None,
) -> dict:
    """Build a structured recipe-card DATA object (no image composed).

    The shape mirrors the recipe-card.json zones so an offline frontend can render
    it into existing HTML/CSS. Ingredient comes from locales.resolve_this_month
    (single source of truth, never fabricated). Non-fabrication is strict:
    prep/cook/serves come only from a matched recipe's real prepTime/cookTime/yield
    fields; est_cost and ingredient prices are always null (no verified source) and
    listed in provenance.values_unknown. Steps derive from the recipe instructions
    (falling back to ingredients like build_recipe_card) with the real leading word
    uppercased as a bold action verb — no cooking action is invented.

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
        return {
            "market": market,
            "month": resolved_month,
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
            },
            "ingredient": ingredient,
            "recipe": None,
            "reason": reason,
            "art": art_block,
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
    recipe = _pick_recipe(ingredient, product)
    if recipe is None:
        return _empty(
            "no recipe catalog available",
            resolved_month=resolved_month,
            ingredient=ingredient,
        )

    subject = {"name": product, "description": recipe.get("name", "")}
    title = rewrite_headline(
        f"{ingredient.title()} over Kodiak Power Cakes",
        market,
        product=subject,
        lang=lang,
        month=resolved_month,
    )
    title_text = clean_brand_copy(title["text"])

    # steps derive from real recipe instructions (fall back to ingredients like
    # build_recipe_card). Only a real leading word is bolded — no verb invented.
    raw_steps = recipe.get("instructions") or recipe.get("ingredients") or []
    steps: list[str] = []
    for raw in raw_steps[:5]:
        cleaned = _clean_step(raw)
        if not cleaned:
            continue
        res = rewrite_headline(
            cleaned[:80], market, product=subject, lang=lang, month=resolved_month
        )
        step = clean_brand_copy(res["text"])
        if step:
            steps.append(_bold_action_step(step))

    meta, unknown = _recipe_meta_bar(recipe)

    # ingredients: the in-season pick is the source-backed line; prices have no
    # verified source, so price is always null.
    ingredients = [{"qty_name": ingredient, "price": None}]

    return {
        "market": market,
        "month": resolved_month,
        "substrate": substrate_key,
        "title": title_text,
        "meta": meta,
        "ingredients": ingredients,
        "steps": steps,
        "sketch_zones": list(_ART_ZONE_IDS),
        "seasonal_moment": seasonal,
        "provenance": {
            "values_from_source": [ingredient],
            "values_proposed": ["over Kodiak Power Cakes"],
            "values_unknown": unknown,
        },
        "ingredient": ingredient,
        "recipe": {"id": recipe.get("id"), "name": recipe.get("name")},
        "art": art_block,
    }
