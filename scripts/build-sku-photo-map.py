#!/usr/bin/env python3
"""Offline SKU -> real lifestyle photo mapper for the Kodiak catalog.

Maps each catalog product (by handle) to the single best-matching REAL lifestyle
photo in the DAM, so the live generator can render real Kodiak scene photography
(blog / social style) per product instead of a pack-shot on a solid ellipse.

Deterministic keyword / metadata scorer — NO vector cosine, NO network by default.
Same inputs -> byte-identical output. The optional S3 existence check is skippable
via --no-verify so the script runs in CI without credentials.

Inputs (read-only):
  data/vectors/kodiak-embeddings.jsonl   image rows w/ metadata (gitignored, S3-hosted)
  data/products/kodiak-full-catalog.json catalog products keyed by handle

Output (committed, reproducible via --no-verify):
  data/products/sku-photo-map.json

Run:
  uv run python scripts/build-sku-photo-map.py --no-verify
  AWS_PROFILE=bryanchasko-kiro uv run python scripts/build-sku-photo-map.py \
      --profile bryanchasko-kiro --region us-east-1
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from collections import Counter

EMBEDDINGS = pathlib.Path("data/vectors/kodiak-embeddings.jsonl")
CATALOG = pathlib.Path("data/products/kodiak-full-catalog.json")
OUT = pathlib.Path("data/products/sku-photo-map.json")
DEFAULT_DAM_KEYS = pathlib.Path("/tmp/dam-real-keys.txt")

# embeddings metadata image_file carries a rendered size variant suffix
# (e.g. "..._1200x1200.jpg") that the actual DAM object key does not have.
# reconcile() strips it — but only when the exact name is NOT already a real
# key (a few real keys, e.g. "..._480x480.jpg", carry the suffix natively).
VARIANT_SUFFIX_RE = re.compile(r"_\d+x\d+(?=\.[a-z0-9]+$)", re.IGNORECASE)

DAM_PREFIX = "brands/kodiak/raw-ingest/kodiakcakes/images/"
DAM_BUCKET = "chasko-creative-dam-946179428633-us-east-1"

MODEL_NOTE = (
    "deterministic keyword+metadata overlap scoring (no vector cosine); "
    "channel-weighted toward blog/instagram lifestyle scenes over catalog pack-shots"
)

# lifestyle channels carry real prepared-food scenes; catalog/amazon are pack-shots.
# a decent lifestyle match should beat a perfect pack-shot match, hence the spread.
CHANNEL_WEIGHT = {
    "blog": 3.0,
    "instagram": 3.0,
    "tiktok": 2.5,
    "amazon": 1.0,
    "catalog": 0.6,
}
DEFAULT_CHANNEL_WEIGHT = 1.0
KNOWN_CHANNELS = set(CHANNEL_WEIGHT)

# score>=this counts as a real match in the summary and in the "matched" flag.
MATCH_THRESHOLD = 2.0

# tokens too generic to carry signal: brand words + packaging/format noise.
# kept out of the query so "kodiak cakes mix" does not match every pack-shot.
STOPWORDS = {
    "kodiak",
    "cakes",
    "cake",
    "mix",
    "the",
    "and",
    "with",
    "for",
    "oz",
    "pack",
    "count",
    "ct",
    "gift",
    "card",
    "photoshop",
    "rework",
    "final",
    "image",
    "variant",
    "photography",
    "photostack",
    "header",
    "sale",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")
HEX_RE = re.compile(r"^[0-9a-f]{6,}$")  # drop uuid / hash fragments in filenames


def tokenize(text: str) -> list[str]:
    """Lowercase alnum tokens, dropping stopwords, hex/uuid fragments, and 1-char noise."""
    out = []
    for tok in TOKEN_RE.findall((text or "").lower()):
        if len(tok) < 2:
            continue
        if tok in STOPWORDS:
            continue
        if HEX_RE.match(tok):
            continue
        if tok.isdigit():
            continue
        out.append(tok)
    return out


def query_tokens(product: dict) -> set[str]:
    """Match query from product name + category + handle tokens."""
    parts = [
        product.get("name", ""),
        product.get("category", "").replace("-", " "),
        product.get("handle", "").replace("-", " "),
    ]
    return set(tokenize(" ".join(parts)))


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(v) for v in value)
    return str(value)


# metadata field -> weight for token overlap. strong signal fields (real, curated
# product/title/recipe text) score higher than filename-derived caption/product on
# catalog rows and than the raw image_file basename.
FIELD_WEIGHTS = {
    "product": 3.0,
    "title": 3.0,
    "recipe": 2.5,
    "recipe_id": 2.0,
    "tags": 2.0,
    "alt_texts": 1.5,
    "caption": 1.5,
    "description": 1.5,
    "og_description": 1.0,
    "hashtags": 1.5,
    "dietary": 1.0,
    "slug": 1.5,
    "section": 0.5,
    "image_file": 0.5,
}


def score_row(qtokens: set[str], meta: dict) -> float:
    """Weighted token-overlap score of query tokens against a row's metadata text."""
    if not qtokens:
        return 0.0
    total = 0.0
    for field, weight in FIELD_WEIGHTS.items():
        ftoks = set(tokenize(_as_text(meta.get(field))))
        if not ftoks:
            continue
        overlap = qtokens & ftoks
        if overlap:
            total += weight * len(overlap)
    return total


def load_images(path: pathlib.Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") != "image":
                continue
            meta = rec.get("metadata", {}) or {}
            image_file = meta.get("image_file")
            if not image_file:
                continue
            rows.append(meta)
    return rows


def load_dam_keys(path: pathlib.Path) -> set[str]:
    """Load the real DAM object basenames (one per line) into a set."""
    keys: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            name = line.strip()
            if name:
                keys.add(name)
    return keys


def reconcile_basename(image_file: str, real_keys: set[str]) -> str | None:
    """Resolve an embeddings image_file to a REAL DAM basename, or None.

    Order (a real key with a native size suffix must win before we strip):
      a. exact match in real_keys -> use as-is
      b. strip a "_NNNNxNNNN" variant suffix before the extension -> re-check
      c. loose reconcile: strip ANY trailing "_<digits>x<digits>" variant -> re-check
    Steps b and c collapse to the same single-suffix strip here, but c is kept
    explicit so a future multi-suffix filename still gets one more attempt.
    """
    if not image_file:
        return None
    # a. already a real key (covers native "_480x480" style keys)
    if image_file in real_keys:
        return image_file
    # b. strip the size variant suffix once
    stripped = VARIANT_SUFFIX_RE.sub("", image_file)
    if stripped != image_file and stripped in real_keys:
        return stripped
    # c. looser: repeatedly strip trailing variant suffixes (handles stacked ones)
    loose = image_file
    while True:
        nxt = VARIANT_SUFFIX_RE.sub("", loose)
        if nxt == loose:
            break
        loose = nxt
        if loose in real_keys:
            return loose
    return None


def caption_for(meta: dict) -> str:
    """Best available human-readable caption for eyeballing quality."""
    for field in ("caption", "title", "recipe", "description", "product"):
        val = _as_text(meta.get(field)).strip()
        if val:
            return val
    return ""


def best_lifestyle_fallback(images: list[dict]) -> dict:
    """A generic real Kodiak lifestyle scene, used when a SKU has no keyword match."""
    lifestyle = [
        m for m in images if m.get("channel") in ("blog", "instagram")
    ]
    # deterministic: prefer instagram (pure scene), then blog, then image_file asc
    order = {"instagram": 0, "blog": 1}
    lifestyle.sort(key=lambda m: (order.get(m.get("channel"), 9), m.get("image_file", "")))
    return lifestyle[0] if lifestyle else images[0]


def photo_entry(meta: dict, score: float, resolved_file: str, fallback_files: list[str]) -> dict:
    """Build an entry from already-reconciled real basenames.

    resolved_file / fallback_files MUST be real DAM basenames (post-reconcile).
    """
    return {
        "photo_key": DAM_PREFIX + resolved_file,
        "image_file": resolved_file,
        "channel": meta.get("channel"),
        "caption": caption_for(meta),
        "score": round(float(score), 4),
        "fallbacks": [DAM_PREFIX + f for f in fallback_files],
    }


def rank_for_product(product: dict, images: list[dict]) -> list[tuple[float, dict]]:
    """Ranked (weighted_score, meta) for a product. Stable: score desc, image_file asc."""
    qtokens = query_tokens(product)
    scored = []
    for meta in images:
        base = score_row(qtokens, meta)
        if base <= 0:
            continue
        weight = CHANNEL_WEIGHT.get(meta.get("channel"), DEFAULT_CHANNEL_WEIGHT)
        scored.append((base * weight, meta))
    scored.sort(key=lambda t: (-t[0], t[1].get("image_file", "")))
    return scored


def resolve_ranked(
    ranked: list[tuple[float, dict]],
    real_keys: set[str],
    generic: dict,
) -> tuple[dict, float, str, list[str]]:
    """Pick the best RESOLVABLE candidate + reconciled fallbacks for a SKU.

    Walks the ranked list; the first candidate whose image_file reconciles to a
    real DAM key becomes the primary. Up to two further resolvable candidates
    (deduped by resolved key) become fallbacks. If NOTHING in the ranked list
    resolves, falls to the generic lifestyle photo (itself reconciled).

    Returns (chosen_meta, chosen_score, resolved_primary, resolved_fallbacks).
    Raises RuntimeError only if even the generic cannot resolve — an unusable
    DAM key set, which must fail loudly rather than emit a broken artifact.
    """
    resolved: list[tuple[float, dict, str]] = []
    for score, meta in ranked:
        rk = reconcile_basename(meta.get("image_file", ""), real_keys)
        if rk is None:
            continue
        resolved.append((score, meta, rk))
        if len(resolved) >= 3:  # 1 primary + 2 fallbacks is all we emit
            break

    if resolved:
        top_score, top_meta, top_key = resolved[0]
        seen = {top_key}
        fbs: list[str] = []
        for _, _, rk in resolved[1:]:
            if rk not in seen:
                fbs.append(rk)
                seen.add(rk)
        return top_meta, top_score, top_key, fbs

    # nothing ranked resolved: generic lifestyle fallback, reconciled
    grk = reconcile_basename(generic.get("image_file", ""), real_keys)
    if grk is None:
        raise RuntimeError(
            "generic lifestyle fallback does not resolve to a real DAM key; "
            "the --dam-keys set is unusable"
        )
    return generic, 0.0, grk, []


def verify_keys(keys: list[str], profile: str, region: str) -> list[str]:
    """Optional S3 existence check. Returns list of missing keys (empty if all present)."""
    missing = []
    for key in keys:
        cmd = [
            "aws", "s3api", "head-object",
            "--bucket", DAM_BUCKET,
            "--key", key,
            "--profile", profile,
            "--region", region,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            missing.append(key)
    return missing


def build(no_verify: bool, profile: str, region: str, real_keys: set[str] | None) -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    products = catalog["products"]
    images = load_images(EMBEDDINGS)

    generic = best_lifestyle_fallback(images)

    # reconcile is a no-op passthrough only when there is no key set (warned upstream).
    # in that degraded mode we accept the raw image_file so the script still runs,
    # but the emitted keys are UNRECONCILED and may 404 — CI must build with the file.
    reconciled = real_keys is not None

    result_map: dict[str, dict] = {}
    matched = 0
    chan_dist: Counter[str] = Counter()

    # fixed iteration order: sorted by handle
    for product in sorted(products, key=lambda p: p["handle"]):
        handle = product["handle"]
        ranked = rank_for_product(product, images)

        if reconciled:
            top_meta, top_score, resolved_file, fb_files = resolve_ranked(
                ranked, real_keys, generic
            )
            # matched flag tracks a real keyword hit at/above threshold, unchanged
            is_match = bool(ranked) and ranked[0][0] >= MATCH_THRESHOLD and (
                resolved_file == reconcile_basename(ranked[0][1].get("image_file", ""), real_keys)
            )
            entry = photo_entry(top_meta, top_score, resolved_file, fb_files)
            entry["matched"] = is_match
            if is_match:
                matched += 1
        else:
            # degraded, unreconciled mode: preserve prior behavior (raw basenames)
            if ranked and ranked[0][0] >= MATCH_THRESHOLD:
                top_score, top_meta = ranked[0]
                fb_files = [m["image_file"] for _, m in ranked[1:3]]
                entry = photo_entry(top_meta, top_score, top_meta["image_file"], fb_files)
                entry["matched"] = True
                matched += 1
            elif ranked:
                top_score, top_meta = ranked[0]
                fb_files = [m["image_file"] for _, m in ranked[1:3]]
                entry = photo_entry(top_meta, top_score, top_meta["image_file"], fb_files)
                entry["matched"] = False
            else:
                entry = photo_entry(generic, 0.0, generic["image_file"], [])
                entry["matched"] = False

        chan_dist[entry["channel"]] += 1
        result_map[handle] = entry

    output = {
        "metadata": {
            "generated": "deterministic",
            "source": {
                "embeddings": str(EMBEDDINGS),
                "catalog": str(CATALOG),
            },
            "total_skus": len(products),
            "matched": matched,
            "match_threshold": MATCH_THRESHOLD,
            "channel_distribution": dict(sorted(chan_dist.items())),
            "model_note": MODEL_NOTE,
            "reconciled_to_real_keys": reconciled,
        },
        "map": {h: result_map[h] for h in sorted(result_map)},
    }

    if not no_verify:
        keys = [entry["photo_key"] for entry in output["map"].values()]
        missing = verify_keys(keys, profile, region)
        output["metadata"]["verified"] = True
        output["metadata"]["missing_keys"] = sorted(missing)
        if missing:
            print(f"WARNING: {len(missing)} photo_key(s) not found in DAM", file=sys.stderr)

    return output


def write_output(output: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys + fixed separators + trailing newline => byte-identical across runs
    text = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")


def print_summary(output: dict) -> None:
    meta = output["metadata"]
    m = output["map"]
    print("=== sku-photo-map summary ===")
    print(f"total SKUs:        {meta['total_skus']}")
    print(f"matched (>= {meta['match_threshold']}): {meta['matched']}")
    print(f"unmatched:         {meta['total_skus'] - meta['matched']}")
    print(f"channel distribution of chosen photos: {meta['channel_distribution']}")
    print("--- 5 examples (handle -> image_file | caption) ---")
    for handle in sorted(m)[:5]:
        e = m[handle]
        cap = (e["caption"] or "")[:80]
        print(f"  {handle} -> {e['image_file']} | ch={e['channel']} score={e['score']} | {cap}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--no-verify",
        action="store_true",
        help="skip the S3 existence check (offline / CI, no creds needed)",
    )
    ap.add_argument("--profile", default="bryanchasko-kiro", help="AWS profile for --verify")
    ap.add_argument("--region", default="us-east-1", help="AWS region for --verify")
    ap.add_argument(
        "--dam-keys",
        default=str(DEFAULT_DAM_KEYS),
        help=(
            "file of real DAM object basenames (one per line) used to reconcile "
            "embeddings image_file variant suffixes to real keys "
            f"(default {DEFAULT_DAM_KEYS})"
        ),
    )
    args = ap.parse_args()

    if not EMBEDDINGS.exists():
        print(
            f"ERROR: {EMBEDDINGS} not found. It is gitignored (S3-hosted); "
            "sync it locally before building.",
            file=sys.stderr,
        )
        return 2
    if not CATALOG.exists():
        print(f"ERROR: {CATALOG} not found.", file=sys.stderr)
        return 2

    dam_keys_path = pathlib.Path(args.dam_keys)
    real_keys: set[str] | None = None
    if dam_keys_path.exists():
        real_keys = load_dam_keys(dam_keys_path)
        print(f"loaded {len(real_keys)} real DAM keys from {dam_keys_path}")
    elif args.no_verify:
        print(
            "=" * 72 + "\n"
            f"WARNING: --dam-keys file {dam_keys_path} not found and --no-verify set.\n"
            "Emitting UNRECONCILED image_file basenames — photo_key values may 404\n"
            "against the DAM. The committed sku-photo-map.json MUST be rebuilt with\n"
            "the real-key file present so every key resolves.\n" + "=" * 72,
            file=sys.stderr,
        )
    else:
        print(
            f"ERROR: --dam-keys file {dam_keys_path} not found. Provide it, or pass "
            "--no-verify to run in degraded (unreconciled) mode.",
            file=sys.stderr,
        )
        return 2

    output = build(
        no_verify=args.no_verify,
        profile=args.profile,
        region=args.region,
        real_keys=real_keys,
    )
    write_output(output)
    print_summary(output)
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
