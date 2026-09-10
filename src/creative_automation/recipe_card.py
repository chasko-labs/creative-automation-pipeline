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
from .locales import resolve_this_month
from .platform_copy import clean_brand_copy
from .text_rewriter import rewrite_headline

# Composed cards publish here so the recipes DAM tab (extra_prefixes) picks
# them up among past assets. Publish is opt-in and never fails a card.
DAM_RECIPES_PREFIX = "brands/kodiak/recipes/"

_ROOT = Path(__file__).parents[2]
RECIPES_PATH = _ROOT / "data" / "recipes" / "kodiak-recipes.json"
DEFAULT_OUT_DIR = _ROOT / "output" / "recipe-cards"

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


def _pick_recipe(ingredient: str, product: str | None) -> dict | None:
    """Best recipe for the in-season ingredient, nearest by token overlap.

    Overlap is scored across name/localize/ingredients/tags. Recipes that carry a real
    hero image field sort ahead of image-less ones on a tie so the card gets a usable
    hero (the compote-over-power-cakes style the Atlanta muscadine case wants). Fully
    deterministic: final tie-break is the recipe id.
    """
    recipes = _load_recipes()
    if not recipes:
        return None
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


def build_recipe_card(
    market: str,
    *,
    month: str | None = None,
    lang: str = "en",
    out_dir: str | Path | None = None,
    publish: bool = False,
) -> dict:
    """Generate a recipe card for a market + month.

    Returns:
        {card_path, ingredient, recipe, text_blocks, safety[, dam_key]} on
        success, or a no-ingredient result {ingredient: None, reason, ...} when
        the month has no seeded local ingredient (never fabricated).
        publish=True also uploads the PNG to the DAM recipes prefix (best
        effort — dam_key None when DAM is unavailable).
    """
    resolved = resolve_this_month(market, ym=month)
    if resolved is None:
        return {
            "card_path": None,
            "ingredient": None,
            "recipe": None,
            "text_blocks": {},
            "safety": {"clean": True, "flagged": []},
            "reason": f"no retailer-frontier pair seeded for {market}",
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
    }
