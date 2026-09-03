#!/usr/bin/env python3
"""Build the REAL Nova multimodal training corpus for Kodiak.

Walks every ingested Kodiak source — Instagram, TikTok, YouTube, the full catalog/recipe
image library, the kodiakcakes.com blog (news/recipes/athletes/ambassador — the GOLD STANDARD
imagery we learn from and reproduce), and brand/regional/hashtag text — and produces real
amazon.nova-2-multimodal-embeddings-v1:0 vectors (1024 dim) into
data/vectors/kodiak-embeddings.jsonl, each row carrying rich provenance metadata for
downstream clustering.

The blog source also emits data/prompts/blog-sample-prompts.jsonl — the sample-prompt library
the UI reads and the pipeline tests against (one row per blog/recipe description).

No third-party models. No sampling — cost is not a concern; embed everything.

Run (real, SSO must be valid):
  cd /home/bryanchasko/code/chasko-labs/creative-automation-pipeline
  AWS_PROFILE=bryanchasko-kiro uv run python scripts/embed-social-corpus.py --out data/vectors

Flags:
  --out DIR         output dir (default data/vectors)
  --dim N           embedding dimension (default from embeddings.EMBED_DIM = 1024)
  --images-limit    cap catalog image count (default: no cap — embed all)
  --skip-images     skip the large catalog image walk (social + text only)
  --skip-blog       skip the blog gold-standard imagery source
  --no-blog-download embed only blog heroes already on disk (no network fetch)
  --sync-s3 URI     after write, aws s3 sync the out dir to this s3:// prefix

Exit 0 on success; writes manifest.json with real model id + true count.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import pathlib
import re
import urllib.parse

from creative_automation.embeddings import embed_batch, EMBED_MODEL, EMBED_DIM

REPO = pathlib.Path(__file__).resolve().parents[1]
INGEST = REPO / "data" / "raw-ingest" / "kodiakcakes"
IMAGES = INGEST / "images"
AMAZON_IMAGES = INGEST / "amazon-images"
PAGES = INGEST / "pages"
BLOG_IMAGES = INGEST / "blog-images"
RECIPES_JSON = REPO / "data" / "recipes" / "kodiak-recipes.json"
PROMPTS_OUT = REPO / "data" / "prompts" / "blog-sample-prompts.jsonl"

# Nova 2 image formats: png|jpeg|gif|webp (jpg normalized to jpeg in embeddings.embed_image)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Only these blog sections carry an editorial hero worth learning from.
BLOG_SECTIONS = ("news", "recipes", "athletes", "ambassador")

# Chrome / nav / logo / icon image src fragments to drop before we treat an <img> as content.
CHROME_IMG_FRAGMENTS = (
    "logo.svg", "primary-logo", "favicon", "apple-touch-icon", "safari-pinned-tab",
    "mega-menu", "brown-texture", "icon-", "kc-icon", "site.webmanifest", "placeholder",
    "spinner", "loading", "sprite", "payment", "badge",
)
# Chrome <img> class fragments to drop (Kodiak Shopify theme markup).
CHROME_IMG_CLASSES = ("header__logo", "kc-icon", "card__image", "icon", "logo")


def _load_json(p: pathlib.Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[corpus] skip unreadable {p.name}: {e}")
        return None


def _resolve_image(name: str) -> pathlib.Path | None:
    """Map an Instagram/TikTok image or media_url reference to a local file under images/."""
    if not name:
        return None
    cand = IMAGES / name
    if cand.exists():
        return cand
    cand = AMAZON_IMAGES / name
    if cand.exists():
        return cand
    return None


def collect_instagram() -> list[dict]:
    """25 Instagram posts — embed the post IMAGE, caption+hashtags+cue ride in metadata."""
    items: list[dict] = []
    data = _load_json(INGEST / "instagram.json") or []
    for post in data:
        img_ref = post.get("image") or post.get("media_url")
        p = _resolve_image(img_ref)
        pid = post.get("id", img_ref or "unknown")
        meta = {
            "channel": "instagram",
            "handle": post.get("handle") or f"@{post.get('username', 'kodiakcakes')}",
            "caption": post.get("caption"),
            "hashtags": post.get("hashtags"),
            "timestamp": post.get("timestamp"),
            "permalink": post.get("permalink"),
            "cue": post.get("cue"),
            "provenance": post.get("provenance"),
            "media_type": post.get("media_type"),
        }
        if p is not None:
            items.append({
                "id": f"instagram:{pid}",
                "type": "image",
                "path": str(p),
                "text": post.get("caption"),  # caption -> metadata, image is what gets embedded
                "metadata": {**meta, "modality": "image", "image_file": p.name},
            })
        else:
            # image missing locally — fall back to a text embedding of the caption so the post is
            # still represented, flagged in metadata so downstream knows it is not a pixel embedding
            print(f"[corpus] instagram {pid}: local image not found for {img_ref!r}; embedding caption text")
            items.append({
                "id": f"instagram:{pid}",
                "type": "text",
                "text": " ".join(filter(None, [post.get("caption"), " ".join(post.get("hashtags") or [])])),
                "metadata": {**meta, "modality": "text", "image_missing": img_ref},
            })
    return items


def collect_tiktok() -> list[dict]:
    """TikTok owned videos — embed local cover/thumb image if present, else the description text."""
    items: list[dict] = []
    data = _load_json(INGEST / "tiktok.json") or []
    for i, vid in enumerate(data):
        thumb = vid.get("thumb") or vid.get("cover_image")
        p = _resolve_image(thumb) if thumb else None
        base_meta = {
            "channel": "tiktok",
            "handle": "@kodiakcakes",
            "title": vid.get("title"),
            "description": vid.get("description"),
            "url": vid.get("url"),
        }
        if p is not None:
            items.append({
                "id": f"tiktok:{i}:{p.stem}",
                "type": "image",
                "path": str(p),
                "text": vid.get("description"),
                "metadata": {**base_meta, "modality": "image", "image_file": p.name},
            })
        else:
            txt = " ".join(filter(None, [vid.get("title"), vid.get("description")]))
            items.append({
                "id": f"tiktok:{i}",
                "type": "text",
                "text": txt,
                "metadata": {**base_meta, "modality": "text", "thumb_missing": thumb},
            })
    return items


def _srt_to_text(p: pathlib.Path) -> str:
    """Flatten an .srt transcript to deduped spoken text (drop indices, timecodes, blank cues)."""
    lines: list[str] = []
    prev = None
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if not s or s.isdigit() or "-->" in s:
            continue
        if s != prev:  # srt often repeats each caption across two cues
            lines.append(s)
            prev = s
    return " ".join(lines)


def collect_youtube() -> list[dict]:
    """YouTube — embed transcript-derived text per video; also the deep channel/content summary."""
    items: list[dict] = []
    deep = _load_json(INGEST / "youtube-deep.json")
    if deep:
        # top_content summaries as text rows (thumbnails are not downloaded locally; use rich text)
        for c in deep.get("top_content", []) or []:
            txt = " ".join(filter(None, [
                c.get("title"), c.get("type"), c.get("creative"),
                c.get("pipeline_asset") or c.get("pipeline_note"),
                " ".join(c.get("hashtags") or []),
            ]))
            if not txt.strip():
                continue
            items.append({
                "id": f"youtube:content:{c.get('rank', c.get('title', 'x'))}",
                "type": "text",
                "text": txt,
                "metadata": {
                    "channel": "youtube",
                    "handle": deep.get("channel", {}).get("handle", "@Kodiakcakes"),
                    "modality": "text",
                    "title": c.get("title"),
                    "views": c.get("views"),
                    "athlete_tag": c.get("athlete_tag"),
                    "hashtags": c.get("hashtags"),
                    "content_type": c.get("type"),
                },
            })
    # transcripts
    ydir = INGEST / "youtube-deep"
    if ydir.is_dir():
        for srt in sorted(ydir.glob("*.srt")):
            text = _srt_to_text(srt)
            if not text.strip():
                continue
            vid_id = srt.name.split(".")[0]
            items.append({
                "id": f"youtube:transcript:{vid_id}",
                "type": "text",
                "text": text,
                "metadata": {
                    "channel": "youtube",
                    "handle": "@Kodiakcakes",
                    "modality": "text",
                    "video_id": vid_id,
                    "source_kind": "transcript",
                },
            })
    return items


def collect_catalog_images(limit: int | None) -> list[dict]:
    """Every catalog/recipe/product image under images/ and amazon-images/ — real pixel embeddings."""
    items: list[dict] = []
    for base, channel in ((IMAGES, "catalog"), (AMAZON_IMAGES, "amazon")):
        if not base.is_dir():
            continue
        files = sorted(p for p in base.glob("*") if p.suffix.lower() in IMAGE_EXTS)
        for i, p in enumerate(files):
            if limit is not None and len(items) >= limit:
                break
            caption = p.stem.replace("_", " ").replace("-", " ")
            items.append({
                "id": f"{channel}-image:{p.name}",
                "type": "image",
                "path": str(p),
                "text": caption,
                "metadata": {
                    "channel": channel,
                    "modality": "image",
                    "image_file": p.name,
                    "caption": caption,
                    "product": caption,
                },
            })
    return items


def collect_brand_text() -> list[dict]:
    """Brand lore, regional/market localization, hashtag lookup — re-embedded REAL as text rows."""
    items: list[dict] = []

    # brand lore knowledge base jsonl
    lore = INGEST / "brand-lore" / "kodiak-brand-lore-knowledge-base.jsonl"
    if lore.exists():
        for i, line in enumerate(lore.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            j = _try_loads(line)
            txt = (j.get("text") if isinstance(j, dict) else None) or line
            items.append({
                "id": f"brand-lore:{i}",
                "type": "text",
                "text": txt[:8192],
                "metadata": {"channel": "brand-lore", "modality": "text",
                             "source": "kodiak-brand-lore-knowledge-base.jsonl"},
            })

    # regional localization training data
    for name in ("localization-training-data.jsonl", "hashtag-lookup.jsonl"):
        p = REPO / "data" / "localization" / name
        if not p.exists():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            j = _try_loads(line)
            md = j.get("metadata", {}) if isinstance(j, dict) else {}
            txt = (j.get("text") if isinstance(j, dict) else None) or line
            items.append({
                "id": f"localization:{md.get('market', name)}:{i}",
                "type": "text",
                "text": txt[:8192],
                "metadata": {"channel": "localization", "modality": "text",
                             "market": md.get("market"), "place": md.get("place"),
                             "retailer": md.get("retailer"), "cue": md.get("cue"),
                             "source": name},
            })

    # market languages + hashtag lookup json (single docs)
    for name, chan in (("market-languages.json", "market-languages"),
                       ("hashtag-lookup.json", "hashtag-lookup")):
        p = REPO / "data" / "localization" / name
        j = _load_json(p) if p.exists() else None
        if j is not None:
            items.append({
                "id": f"reference:{chan}",
                "type": "text",
                "text": json.dumps(j)[:8192],
                "metadata": {"channel": chan, "modality": "text", "source": name},
            })

    # brand palette / voice anchor row (kept from prior corpus, re-embedded real)
    items.append({
        "id": "design:palette-story",
        "type": "text",
        "text": ("Kodiak palette Bear Brown #3B2316 Blaze Orange #E8530E Frontier Green #1A3C34 "
                 "Parchment #FFF8F0 - Wasatch dawn, brown kraft box with growling bear, Keep It Wild "
                 "with Vital Ground, 14g protein 100% whole grains"),
        "metadata": {"channel": "design", "modality": "text", "source": "brand-palette"},
    })
    return items


def _try_loads(line: str):
    try:
        return json.loads(line)
    except Exception:  # noqa: BLE001
        return line


# --- blog (kodiakcakes.com/blogs/*) — the GOLD STANDARD imagery source -------------------
# Kodiak editorial photography is the imagery we want to learn from and reproduce. Each blog
# post gives us a clean image + a human-written description; that description becomes a
# sample prompt in the UI and a test case for the pipeline.

_META_RE = re.compile(
    r"""<meta\s+[^>]*?(?:name|property)\s*=\s*["']([^"']+)["'][^>]*?content\s*=\s*["'](.*?)["']""",
    re.IGNORECASE | re.DOTALL,
)
# og:image content sometimes precedes the property attr; capture both attribute orders.
_META_CONTENT_FIRST_RE = re.compile(
    r"""<meta\s+[^>]*?content\s*=\s*["'](.*?)["'][^>]*?(?:name|property)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE | re.DOTALL,
)
_CANONICAL_RE = re.compile(
    r"""<link\s+[^>]*?rel\s*=\s*["']canonical["'][^>]*?href\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_IMG_TAG_RE = re.compile(r"<img\b([^>]*)>", re.IGNORECASE)
_ATTR_RE = re.compile(r"""(\w[\w:-]*)\s*=\s*["'](.*?)["']""", re.IGNORECASE | re.DOTALL)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str | None:
    """Unescape HTML entities, drop residual tags, collapse whitespace."""
    if not text:
        return None
    t = _TAG_STRIP_RE.sub(" ", text)
    t = _html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def _parse_meta(html: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for k, v in _META_RE.findall(html):
        meta.setdefault(k.strip().lower(), v)
    for v, k in _META_CONTENT_FIRST_RE.findall(html):
        meta.setdefault(k.strip().lower(), v)
    return meta


def _is_chrome_img(attrs: dict[str, str]) -> bool:
    src = (attrs.get("src") or attrs.get("data-src") or "").lower()
    cls = (attrs.get("class") or "").lower()
    if any(frag in src for frag in CHROME_IMG_FRAGMENTS):
        return True
    if any(frag in cls for frag in CHROME_IMG_CLASSES):
        return True
    if src.endswith(".svg"):
        return True
    return False


def _content_alts(html: str, limit: int = 24) -> list[str]:
    """Alt texts of content <img> tags, skipping nav/logo/icon/product-card chrome."""
    alts: list[str] = []
    seen: set[str] = set()
    for raw_attrs in _IMG_TAG_RE.findall(html):
        attrs = {k.lower(): v for k, v in _ATTR_RE.findall(raw_attrs)}
        if _is_chrome_img(attrs):
            continue
        alt = _clean(attrs.get("alt"))
        if not alt or alt.lower() in seen:
            continue
        seen.add(alt.lower())
        alts.append(alt)
        if len(alts) >= limit:
            break
    return alts


def _slug_and_section(filename: str) -> tuple[str | None, str | None]:
    """From e.g. 687_blogs_news_how-do-u-make-flapjack-mix.html -> ("news", "how-do-u-make-flapjack-mix")."""
    stem = filename[:-5] if filename.endswith(".html") else filename
    m = re.search(r"_blogs_(" + "|".join(BLOG_SECTIONS) + r")_(.+)$", stem)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _prefer_https(url: str | None) -> str | None:
    if not url:
        return None
    return url.replace("http://", "https://", 1) if url.startswith("http://") else url


def _hero_local_path(image_url: str) -> pathlib.Path:
    """Deterministic local filename for a hero image URL (idempotent target for downloads)."""
    parsed = urllib.parse.urlparse(image_url)
    base = pathlib.PurePosixPath(parsed.path).name or "hero"
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    if not any(base.lower().endswith(ext) for ext in IMAGE_EXTS):
        base += ".jpg"
    return BLOG_IMAGES / base


def _download_hero(image_url: str, dest: pathlib.Path) -> bool:
    """Idempotent Amazon-only download. Skip if present. Returns True if a local file exists after."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        import httpx  # already a dependency

        BLOG_IMAGES.mkdir(parents=True, exist_ok=True)
        with httpx.Client(follow_redirects=True, timeout=20.0) as client:
            r = client.get(image_url, headers={"User-Agent": "kodiak-corpus/1.0"})
        if r.status_code == 200 and r.content:
            dest.write_bytes(r.content)
            return True
        print(f"[corpus] blog hero {image_url} -> HTTP {r.status_code}; skipping image")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"[corpus] blog hero {image_url} download failed: {e}; skipping image")
        return False


def _load_recipe_index() -> dict[str, dict]:
    """Map kodiak_page URL -> recipe record, for cross-linking blog posts to recipes."""
    data = _load_json(RECIPES_JSON) or []
    idx: dict[str, dict] = {}
    for rec in data:
        page = (rec.get("kodiak_page") or "").rstrip("/")
        if page:
            idx[page] = rec
    return idx


def collect_blog(download: bool = True) -> tuple[list[dict], list[dict]]:
    """Walk ingested blog HTML, emit image/text embedding items + sample-prompt rows.

    Returns (embedding_items, prompt_rows). prompt_rows are written to
    data/prompts/blog-sample-prompts.jsonl separately from the vectors jsonl.
    """
    items: list[dict] = []
    prompts: list[dict] = []
    recipe_idx = _load_recipe_index()

    if not PAGES.is_dir():
        print(f"[corpus] blog: pages dir missing {PAGES}")
        return items, prompts

    seen_heroes: set[str] = set()
    n_html = n_image = n_text = 0

    for p in sorted(PAGES.glob("*blogs*.html")):
        section, slug = _slug_and_section(p.name)
        if not section or not slug:
            continue  # blog index/listing page, not a single article
        n_html += 1
        html = p.read_text(encoding="utf-8", errors="ignore")
        meta = _parse_meta(html)

        description = _clean(meta.get("description"))
        og_description = _clean(meta.get("og:description"))
        title = _clean(meta.get("og:title")) or _clean(_first(_H1_RE.findall(html))) \
            or _clean(_first(_TITLE_RE.findall(html)))
        blog_url = _clean(meta.get("og:url")) or _clean(_first(_CANONICAL_RE.findall(html))) \
            or f"https://kodiakcakes.com/blogs/{section}/{slug}"
        hero_url = _prefer_https(meta.get("og:image:secure_url") or meta.get("og:image"))
        alt_texts = _content_alts(html)

        # the meta description is the sample prompt; fall back to og:description if absent
        prompt_text = description or og_description
        recipe = recipe_idx.get((blog_url or "").rstrip("/"))

        base_meta = {
            "channel": "blog",
            "section": section,
            "slug": slug,
            "blog_url": blog_url,
            "title": title,
            "description": prompt_text,
            "og_description": og_description,
            "alt_texts": alt_texts,
            "in_image_text": False,  # brand standard: Kodiak imagery carries no baked-in text
            "prompt_candidate": bool(prompt_text),
            "source_file": p.name,
        }
        if recipe is not None:
            base_meta["recipe"] = recipe.get("name")
            base_meta["recipe_id"] = recipe.get("id")
            base_meta["product"] = recipe.get("product")
            base_meta["tags"] = recipe.get("tags")
            base_meta["dietary"] = recipe.get("dietary")

        hero_ok = False
        local_hero: pathlib.Path | None = None
        if hero_url:
            local_hero = _hero_local_path(hero_url)
            if download:
                hero_ok = _download_hero(hero_url, local_hero)
            else:
                hero_ok = local_hero.exists() and local_hero.stat().st_size > 0

        if hero_ok and local_hero is not None:
            seen_heroes.add(str(local_hero))
            n_image += 1
            items.append({
                "id": f"blog:{section}:{slug}",
                "type": "image",
                "path": str(local_hero),
                "text": prompt_text,
                "metadata": {**base_meta, "modality": "image",
                             "hero_url": hero_url, "image_file": local_hero.name},
            })
        else:
            # hero missing/failed -> embed the description text so the post is still represented
            n_text += 1
            items.append({
                "id": f"blog:{section}:{slug}",
                "type": "text",
                "text": prompt_text or title or slug.replace("-", " "),
                "metadata": {**base_meta, "modality": "text",
                             "hero_url": hero_url, "image_missing": hero_url or "no-og-image"},
            })

        if prompt_text:
            prompts.append({
                "id": f"blog:{section}:{slug}",
                "prompt": prompt_text,
                "source_url": blog_url,
                "hero_image": str(local_hero) if (hero_ok and local_hero) else None,
                "product": (recipe or {}).get("product") if recipe else None,
                "recipe": (recipe or {}).get("name") if recipe else None,
                "tags": (recipe or {}).get("tags") if recipe else [],
                "section": section,
                "in_image_text": False,
            })

    print(f"[corpus] blog: {n_html} posts parsed -> {n_image} image + {n_text} text items, "
          f"{len(prompts)} prompt candidates")

    # cross-link the recipes that carry a real article image URL (112 of 444)
    rc_image = rc_prompt = 0
    for rec in (_load_json(RECIPES_JSON) or []):
        img_url = _prefer_https(rec.get("image"))
        if not img_url or "http" not in img_url:
            continue
        # a blog post already covered this exact image — its hero embedding wins; skip duplicate
        local_hero = _hero_local_path(img_url)
        if str(local_hero) in seen_heroes:
            continue
        prompt_text = _clean(rec.get("name"))
        tags = rec.get("tags") or []
        meta = {
            "channel": "blog",
            "section": "recipes",
            "recipe": rec.get("name"),
            "recipe_id": rec.get("id"),
            "product": rec.get("product"),
            "blog_url": rec.get("kodiak_page"),
            "tags": tags,
            "dietary": rec.get("dietary"),
            "description": prompt_text,
            "in_image_text": False,
            "prompt_candidate": True,
            "source": "kodiak-recipes.json",
        }
        hero_ok = False
        if download:
            hero_ok = _download_hero(img_url, local_hero)
        else:
            hero_ok = local_hero.exists() and local_hero.stat().st_size > 0

        if hero_ok:
            seen_heroes.add(str(local_hero))
            rc_image += 1
            items.append({
                "id": f"recipe-image:{rec.get('id')}",
                "type": "image",
                "path": str(local_hero),
                "text": " ".join(filter(None, [prompt_text, " ".join(tags)])),
                "metadata": {**meta, "modality": "image",
                             "hero_url": img_url, "image_file": local_hero.name},
            })
        else:
            items.append({
                "id": f"recipe-image:{rec.get('id')}",
                "type": "text",
                "text": " ".join(filter(None, [prompt_text, " ".join(tags)])) or rec.get("id"),
                "metadata": {**meta, "modality": "text",
                             "hero_url": img_url, "image_missing": img_url},
            })
        rc_prompt += 1
        prompts.append({
            "id": f"recipe-image:{rec.get('id')}",
            "prompt": prompt_text,
            "source_url": rec.get("kodiak_page"),
            "hero_image": str(local_hero) if hero_ok else None,
            "product": rec.get("product"),
            "recipe": rec.get("name"),
            "tags": tags,
            "section": "recipes",
            "in_image_text": False,
        })

    print(f"[corpus] blog recipe cross-link: {rc_image} image items, {rc_prompt} prompt rows")
    return items, prompts


def _first(seq):
    return seq[0] if seq else None


def _write_prompts(prompts: list[dict]) -> pathlib.Path:
    PROMPTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with PROMPTS_OUT.open("w", encoding="utf-8") as f:
        for row in prompts:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[corpus] wrote {len(prompts)} sample prompts -> {PROMPTS_OUT}")
    return PROMPTS_OUT


def main() -> None:
    ap = argparse.ArgumentParser(description="Embed the full Kodiak social + brand corpus with Nova 2 multimodal")
    ap.add_argument("--out", default="data/vectors")
    ap.add_argument("--dim", type=int, default=EMBED_DIM)
    ap.add_argument("--images-limit", type=int, default=None, help="cap catalog images (default: all)")
    ap.add_argument("--skip-images", action="store_true", help="skip the large catalog image walk")
    ap.add_argument("--skip-blog", action="store_true", help="skip the blog gold-standard imagery source")
    ap.add_argument("--no-blog-download", action="store_true",
                    help="do not fetch blog hero images; embed only heroes already on disk")
    ap.add_argument("--sync-s3", default=None, help="s3:// prefix to aws s3 sync the out dir into after write")
    args = ap.parse_args()

    items: list[dict] = []
    prompts: list[dict] = []

    ig = collect_instagram()
    print(f"[corpus] instagram: {len(ig)} items")
    items.extend(ig)

    tk = collect_tiktok()
    print(f"[corpus] tiktok: {len(tk)} items")
    items.extend(tk)

    yt = collect_youtube()
    print(f"[corpus] youtube: {len(yt)} items")
    items.extend(yt)

    bt = collect_brand_text()
    print(f"[corpus] brand/regional/hashtag text: {len(bt)} items")
    items.extend(bt)

    if not args.skip_images:
        ci = collect_catalog_images(limit=args.images_limit)
        print(f"[corpus] catalog images: {len(ci)} items"
              + (f" (capped at {args.images_limit})" if args.images_limit else " (all)"))
        items.extend(ci)

    if not args.skip_blog:
        bl, prompts = collect_blog(download=not args.no_blog_download)
        print(f"[corpus] blog (gold standard): {len(bl)} embedding items, {len(prompts)} prompt rows")
        items.extend(bl)
        _write_prompts(prompts)

    print(f"[corpus] TOTAL {len(items)} items -> model {EMBED_MODEL} dim {args.dim} out {args.out}")
    print("[corpus] embedding now (real Nova 2 calls, one per item)...")
    jsonl = embed_batch(items, out_dir=args.out, dim=args.dim)
    manifest = pathlib.Path(args.out) / "manifest.json"
    print(f"[corpus] wrote {jsonl} ({jsonl.stat().st_size} bytes); manifest {manifest}")

    if args.sync_s3:
        import subprocess
        cmd = ["aws", "s3", "sync", str(pathlib.Path(args.out)) + "/", args.sync_s3, "--region", "us-east-1"]
        print(f"[corpus] s3 sync: {' '.join(cmd)}")
        rc = subprocess.call(cmd)
        print(f"[corpus] s3 sync exit {rc}")


if __name__ == "__main__":
    main()
