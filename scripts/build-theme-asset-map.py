#!/usr/bin/env python3
"""Offline theme -> real lifestyle photo mapper for the on-load prompt chips.

The frontier-frontend prompt chips (#promptChips in
web/kodiak-posts-for-todays-frontier/index.html) each carry a campaign brief.
Today every chip composes on the same power-cakes pack-shot because there is no
theme->asset routing. This map fixes that: each of the 6 chip themes resolves to
a small pool of REAL on-theme Kodiak lifestyle photography in the DAM, so the
live generator composes each chip on the right kind of scene.

Deterministic keyword / metadata scorer — NO vector cosine, NO network by
default. Same inputs -> byte-identical output. The optional S3 existence check
is skippable via --no-verify so the script runs in CI without credentials.

Mirrors scripts/build-sku-photo-map.py exactly for structure, determinism,
DAM-key reconciliation, and channel weighting. The differences from the sku map:
  - the query is a fixed set of theme match-tokens (not product-derived)
  - each theme keeps a pool of up to 5 photo_keys (chips rotate; sku picks 1+2)
  - the "bears" theme applies a NEGATIVE weight guardrail (see BEARS_ below)

Inputs (read-only):
  data/vectors/kodiak-embeddings.jsonl   image rows w/ metadata (gitignored, S3-hosted)
  (theme definitions are declared inline below — they are the product spec)

Output (committed, reproducible via --no-verify):
  data/products/theme-asset-map.json

Run:
  uv run python scripts/build-theme-asset-map.py --no-verify --dam-keys /tmp/dam-real-keys.txt
  AWS_PROFILE=bryanchasko-kiro uv run python scripts/build-theme-asset-map.py \
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
OUT = pathlib.Path("data/products/theme-asset-map.json")
DEFAULT_DAM_KEYS = pathlib.Path("/tmp/dam-real-keys.txt")

# embeddings metadata image_file carries a rendered size variant suffix
# (e.g. "..._1200x1200.jpg") that the actual DAM object key does not have.
# reconcile() strips it — but only when the exact name is NOT already a real
# key (a few real keys, e.g. "..._520x500.jpg", carry the suffix natively).
VARIANT_SUFFIX_RE = re.compile(r"_\d+x\d+(?=\.[a-z0-9]+$)", re.IGNORECASE)

DAM_PREFIX = "brands/kodiak/raw-ingest/kodiakcakes/images/"
DAM_BUCKET = "chasko-creative-dam-946179428633-us-east-1"

MODEL_NOTE = (
    "deterministic keyword+metadata overlap scoring (no vector cosine); "
    "each theme scored against a fixed match-token set over caption/hashtags/"
    "image_file, channel-weighted toward blog/instagram lifestyle over catalog "
    "pack-shots; bears theme applies a negative captive-bear-closeup guardrail; "
    "zac-efron theme applies an additive athlete/lifestyle filename boost so "
    "real licensed brand-athlete photography ranks first (rights-clean, no "
    "likeness synthesis); primaries are globally de-duped in a fixed priority "
    "order (zac-efron first, then alphabetical) so all themes carry distinct "
    "primary photo_keys; top-1 + up to 4 fallbacks per theme, all reconciled "
    "to real DAM keys"
)

POOL_SIZE = 5  # 1 primary + up to 4 fallbacks — chips rotate over a small pool

# lifestyle channels carry real prepared-food + frontier scenes; catalog/amazon
# are pack-shots. a decent lifestyle match should beat a pack-shot, hence spread.
# (identical weights to the sku map so the two artifacts stay consistent.)
CHANNEL_WEIGHT = {
    "blog": 3.0,
    "instagram": 3.0,
    "tiktok": 2.5,
    "amazon": 1.0,
    "catalog": 0.6,
}
DEFAULT_CHANNEL_WEIGHT = 1.0

# metadata field -> weight for token overlap. caption is the curated,
# human-written thematic signal (instagram rows carry "Wasatch dawn",
# "grizzly meadow", "Costco frontier"); hashtags reinforce campaign intent;
# image_file basename is weak filename-derived signal (matches the sku map's
# low image_file weight so a real caption match beats a filename coincidence).
FIELD_WEIGHTS = {
    "caption": 3.0,
    "hashtags": 2.0,
    "image_file": 0.5,
}

TOKEN_RE = re.compile(r"[a-z0-9]+")
HEX_RE = re.compile(r"^[0-9a-f]{6,}$")  # drop uuid / hash fragments in filenames

# tokens too generic to carry theme signal: brand words + packaging noise.
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
    "photoshop",
    "rework",
    "final",
    "image",
    "variant",
    "header",
}

# ---------------------------------------------------------------------------
# THEME DEFINITIONS — this block is the product spec. Each theme maps a chip
# (by slug) to its brief and the match-tokens that describe its real DAM pool.
# slugs match the brief; order here fixes summary/iteration order.
# ---------------------------------------------------------------------------
THEMES: list[dict] = [
    {
        "slug": "zac-efron",
        "brief": (
            "Zac Efron athletic-morning energy — high-protein pre-trail fuel, "
            "aspirational active lifestyle. Keep It Wild."
        ),
        # ATHLETIC-LIFESTYLE pool: real Kodiak athlete + cooking-with-Zac +
        # outdoor family-lifestyle photography. NO synthesized Efron likeness —
        # these are real brand athlete/lifestyle shots.
        "tokens": [
            "athlete",
            "schweizer",
            "harrington",
            "olson",
            "watson",
            "lichter",
            "zac",
            "cooking",
            "outdoor",
            "lifestyle",
            "family",
            "morning",
            "active",
        ],
    },
    {
        "slug": "bears",
        "brief": (
            "Bears + Keep It Wild — lean into the KODIAK Bear, wild frontier "
            "tone, protein for epic days."
        ),
        # GRIZZLY-SAFE / KEEP-IT-WILD pool: wild-habitat, trail, meadow,
        # landscape cues. Bear-shaped product (Bear Bites) is fine.
        "tokens": [
            "grizzly",
            "trail",
            "meadow",
            "wild",
            "wasatch",
            "outdoor",
            "habitat",
            "frontier",
            "pine",
            "landscape",
            "vital",
            "ground",
            "corridor",
        ],
    },
    {
        "slug": "recipe-cards",
        "brief": (
            "Recipe cards for Park City families — protein-packed whole grain "
            "recipes styled as shareable cards. Keep It Wild."
        ),
        # recipe / social-recipe pool: the Web_Recipes_from_Social_* set.
        "tokens": [
            "recipe",
            "recipes",
            "social",
            "web",
            "card",
            "shareable",
        ],
    },
    {
        "slug": "localized-costco",
        "brief": (
            "Localized Costco campaign — bulk Family Size value for the "
            "warehouse aisle, Park City / Wasatch Back framing."
        ),
        # bulk / family-size / value pool; falls back to hero product shots
        # if sparse (handled by resolve_ranked walking the ranked list).
        "tokens": [
            "costco",
            "bulk",
            "value",
            "warehouse",
            "membership",
            "family",
            "size",
            "grizzly",
            "pantry",
            "stock",
        ],
    },
    {
        "slug": "riff-on-past-content",
        "brief": (
            "Riff on past content — remix our existing heroes into fresh "
            "variants across all three ratios."
        ),
        # remix pool: best-performing hero / lifestyle shots broadly. general
        # lifestyle — lean on cast-iron-stack, morning, frontier hero cues.
        # (FLAG 2: leans remix-of-hero-food to diverge from keep-it-wild's
        # conservation/landscape lean; de-dup rule is the hard guarantee.)
        "tokens": [
            "hero",
            "stack",
            "cast",
            "iron",
            "waffle",
            "flapjack",
            "remix",
            "cups",
            "brownie",
            "scones",
        ],
    },
    {
        "slug": "keep-it-wild-program",
        "brief": (
            "Keep It Wild program — brand campaign tying protein-packed whole "
            "grains to the outdoor frontier lifestyle."
        ),
        # Wasatch-dawn + conservation landscape pool.
        # (FLAG 2: leans conservation/alpenglow/mountain/grizzly-habitat to
        # diverge from riff-on-past-content's hero-food-remix lean.)
        "tokens": [
            "wasatch",
            "dawn",
            "alpenglow",
            "conservation",
            "wild",
            "mountain",
            "landscape",
            "pine",
            "grizzly",
            "habitat",
        ],
    },
]

# BEARS GUARDRAIL (PETA 2022 brand guardrail): the "bears" theme must never
# route to a captive-bear close-up / live-bear portrait. Any embeddings row
# whose caption strongly implies a live captive-bear portrait is penalized
# hard (effectively excluded) so it can never surface as the chosen asset or a
# fallback. Wild-habitat / trail / landscape cues and the Bear Bites product
# (bear-shaped food) are explicitly NOT penalized. In the current DAM none of
# the resolvable rows are captive-bear portraits, so this guardrail is
# defensive — it protects against future ingest adding such a row.
BEARS_CAPTIVE_TOKENS = {
    "captive",
    "zoo",
    "enclosure",
    "cage",
    "caged",
    "cub",
    "cubs",
    "portrait",
    "closeup",
    "close",  # "close-up" tokenizes to close + up
    "petting",
    "handler",
    "sanctuary",
}
BEARS_HABITAT_TOKENS = {"trail", "meadow", "habitat", "wild", "landscape", "corridor"}
BEARS_CAPTIVE_PENALTY = 1000.0  # dominant negative weight -> effective exclusion

# ZAC-EFRON FILENAME BOOST (FLAG 1): the 21 real brand-athlete / lifestyle
# assets (Schweizer, Harrington, Caleb Olson, Sam Watson, Jennifer Lichter,
# Cooking-with-Zac, Outdoor-Cooking-Family-Lifestyle, Climbing-Lifestyle,
# Athlete_Image, Zac-Waffle) carry the athlete signal ONLY in their filename —
# their embedding rows land on the catalog channel (weight 0.6) with a caption
# that merely echoes the filename, so a caption-rich instagram food shot
# (weight 3.0) outscores them and a generic granola pack wins the primary.
# For the zac-efron theme SPECIFICALLY we add a large additive filename boost
# when a row's image_file matches an athlete/ambassador signal token, so real
# licensed brand-athlete photography ranks first. Theme-scoped so it never
# distorts the other five themes.
# RIGHTS-CLEAN: these are real licensed brand-athlete photos already in the DAM;
# no likeness synthesis, no scraped stills — we only surface assets that exist.
ZAC_FILENAME_SIGNAL_TOKENS = (
    "athlete",
    "schweizer",
    "harrington",
    "olson",
    "watson",
    "lichter",
    "cooking-with-zac",
    "cooking_with_zac",
    "outdoor-cooking-family",
    "family-lifestyle",
    "climbing-lifestyle",
    "athlete_image",
    "zac",
    "efron",
)
ZAC_FILENAME_BOOST = 50.0  # dominant additive bonus -> real athlete photo wins primary


def tokenize(text: str) -> list[str]:
    """Lowercase alnum tokens, dropping stopwords, hex/uuid fragments, 1-char noise."""
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


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(v) for v in value)
    return str(value)


def score_row(qtokens: set[str], meta: dict) -> float:
    """Weighted token-overlap score of theme tokens against a row's metadata."""
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


def bears_guardrail_penalty(meta: dict) -> float:
    """Negative weight for a row that risks reading as a captive-bear close-up.

    Returns a large penalty when the caption carries captive/portrait cues
    WITHOUT offsetting wild-habitat cues. Rows that pair a bear reference with
    trail/meadow/habitat/landscape context (the on-brand Keep It Wild shots)
    are NOT penalized. See BEARS_ constants above for the PETA-2022 rationale.
    """
    cap_toks = set(tokenize(_as_text(meta.get("caption"))))
    cap_toks |= set(tokenize(_as_text(meta.get("hashtags"))))
    captive_hits = cap_toks & BEARS_CAPTIVE_TOKENS
    if not captive_hits:
        return 0.0
    # habitat context present -> treat as an on-brand wild scene, no penalty
    if cap_toks & BEARS_HABITAT_TOKENS:
        return 0.0
    return -BEARS_CAPTIVE_PENALTY


def zac_filename_boost(meta: dict) -> float:
    """Additive boost for zac-efron when image_file carries an athlete signal.

    Matches against the raw lowercased image_file (substring) so hyphen/
    underscore-joined signals like "cooking-with-zac" and "athlete_image" hit
    even though tokenize() would split them. See ZAC_ constants for the
    rights-clean rationale (real licensed brand-athlete photos only).
    """
    fn = (meta.get("image_file") or "").lower()
    if not fn:
        return 0.0
    for sig in ZAC_FILENAME_SIGNAL_TOKENS:
        if sig in fn:
            return ZAC_FILENAME_BOOST
    return 0.0


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
            if not meta.get("image_file"):
                continue
            rows.append(meta)
    return rows


def load_dam_keys(path: pathlib.Path) -> set[str]:
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
      c. loose reconcile: repeatedly strip trailing variant suffixes -> re-check
    Identical logic to the sku map's reconcile_basename.
    """
    if not image_file:
        return None
    if image_file in real_keys:
        return image_file
    stripped = VARIANT_SUFFIX_RE.sub("", image_file)
    if stripped != image_file and stripped in real_keys:
        return stripped
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
    for field in ("caption", "image_file"):
        val = _as_text(meta.get(field)).strip()
        if val:
            return val
    return ""


def rank_for_theme(theme: dict, images: list[dict]) -> list[tuple[float, dict]]:
    """Ranked (weighted_score, meta) for a theme. Stable: score desc, image_file asc.

    Applies channel weighting and, for the bears theme, the captive-bear
    guardrail penalty. Rows scoring <= 0 after weighting are dropped.
    """
    qtokens = set(theme["tokens"])
    is_bears = theme["slug"] == "bears"
    is_zac = theme["slug"] == "zac-efron"
    scored = []
    for meta in images:
        base = score_row(qtokens, meta)
        if base <= 0:
            continue
        weight = CHANNEL_WEIGHT.get(meta.get("channel"), DEFAULT_CHANNEL_WEIGHT)
        total = base * weight
        if is_bears:
            total += bears_guardrail_penalty(meta)
        if is_zac:
            # theme-scoped additive filename boost (FLAG 1): promote real
            # licensed brand-athlete / lifestyle photography above caption-rich
            # generic food shots. never applied to any other theme.
            total += zac_filename_boost(meta)
        if total <= 0:
            continue
        scored.append((total, meta))
    scored.sort(key=lambda t: (-t[0], t[1].get("image_file", "")))
    return scored


def resolve_pool(
    ranked: list[tuple[float, dict]],
    real_keys: set[str],
    claimed_primaries: set[str],
) -> tuple[dict, float, str, list[str]]:
    """Pick the best RESOLVABLE, UNCLAIMED candidate + reconciled pool for a theme.

    Walks the ranked list; the first candidate whose image_file reconciles to a
    real DAM key AND is not already another theme's PRIMARY becomes this theme's
    primary (FLAG 2 global de-dup). Up to POOL_SIZE-1 further resolvable, deduped
    candidates become the fallback pool — a key claimed as another theme's
    primary MAY still appear here; only PRIMARIES must be globally unique.

    Every theme MUST resolve a unique primary — if nothing in the ranked list
    resolves to an unclaimed real key, RuntimeError (loud failure over a null or
    duplicate photo_key).

    Returns (chosen_meta, chosen_score, resolved_primary, resolved_fallbacks).
    """
    resolved: list[tuple[float, dict, str]] = []
    seen: set[str] = set()
    for score, meta in ranked:
        rk = reconcile_basename(meta.get("image_file", ""), real_keys)
        if rk is None or rk in seen:
            continue
        resolved.append((score, meta, rk))
        seen.add(rk)
        if len(resolved) >= POOL_SIZE:
            break

    if not resolved:
        raise RuntimeError(
            "theme has zero resolvable on-theme assets against the --dam-keys "
            "set; every theme must resolve a real photo_key"
        )

    # FLAG 2: primary must be the best-ranked resolvable key NOT already claimed
    # as another theme's primary. fall to next-best when the top is claimed.
    primary_idx = None
    for i, (_, _, rk) in enumerate(resolved):
        if rk not in claimed_primaries:
            primary_idx = i
            break
    if primary_idx is None:
        raise RuntimeError(
            "theme has no unclaimed resolvable primary candidate (all top "
            f"{len(resolved)} on-theme assets are already other themes' "
            "primaries); widen the theme token set or DAM pool"
        )

    top_score, top_meta, top_key = resolved[primary_idx]
    # fallback pool = every resolved key except the chosen primary, order stable
    fbs = [rk for j, (_, _, rk) in enumerate(resolved) if j != primary_idx]
    return top_meta, top_score, top_key, fbs


def build(no_verify: bool, profile: str, region: str, real_keys: set[str]) -> dict:
    images = load_images(EMBEDDINGS)

    result_map: dict[str, dict] = {}
    chan_dist: Counter[str] = Counter()

    # FLAG 2 de-dup: process themes in a FIXED deterministic priority order so
    # primary claiming is reproducible byte-for-byte. zac-efron goes first
    # (its athlete/lifestyle primary is the most constrained requirement), then
    # the remaining themes alphabetically by slug. A theme's primary is the
    # best-ranked resolvable key not already claimed by an earlier theme.
    PRIMARY_ORDER = ["zac-efron"] + sorted(
        t["slug"] for t in THEMES if t["slug"] != "zac-efron"
    )
    themes_by_slug = {t["slug"]: t for t in THEMES}
    claimed_primaries: set[str] = set()

    for slug in PRIMARY_ORDER:
        theme = themes_by_slug[slug]
        ranked = rank_for_theme(theme, images)
        top_meta, top_score, primary_key, fb_keys = resolve_pool(
            ranked, real_keys, claimed_primaries
        )
        claimed_primaries.add(primary_key)
        pool = [primary_key] + fb_keys
        entry = {
            "theme": theme["slug"],
            "brief": theme["brief"],
            "photo_key": DAM_PREFIX + primary_key,
            "image_file": primary_key,
            "channel": top_meta.get("channel"),
            "caption": caption_for(top_meta),
            "score": round(float(top_score), 4),
            "pool": [DAM_PREFIX + k for k in pool],
        }
        if theme["slug"] == "bears":
            entry["guardrail"] = (
                "captive-bear-closeup excluded (PETA 2022): rows with "
                "captive/zoo/portrait caption cues and no offsetting wild-habitat "
                "context are penalized out; prefers trail/meadow/landscape/wild"
            )
        chan_dist[entry["channel"]] += 1
        result_map[theme["slug"]] = entry

    output = {
        "metadata": {
            "generated": "deterministic",
            "source": {"embeddings": str(EMBEDDINGS)},
            "themes": [t["slug"] for t in THEMES],
            "pool_size": POOL_SIZE,
            "channel_distribution": dict(sorted(chan_dist.items())),
            "model_note": MODEL_NOTE,
            "reconciled_to_real_keys": True,
        },
        "map": {slug: result_map[slug] for slug in sorted(result_map)},
    }

    if not no_verify:
        keys: list[str] = []
        for entry in output["map"].values():
            keys.extend(entry["pool"])
        missing = verify_keys(sorted(set(keys)), profile, region)
        output["metadata"]["verified"] = True
        output["metadata"]["missing_keys"] = sorted(missing)
        if missing:
            print(f"WARNING: {len(missing)} photo_key(s) not found in DAM", file=sys.stderr)

    return output


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


def write_output(output: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    OUT.write_text(text, encoding="utf-8")


def print_summary(output: dict) -> None:
    meta = output["metadata"]
    m = output["map"]
    print("=== theme-asset-map summary ===")
    print(f"themes:            {len(m)}")
    print(f"channel distribution of chosen photos: {meta['channel_distribution']}")
    print("--- per-theme (slug -> image_file | pool | channel | caption) ---")
    for slug in meta["themes"]:
        e = m[slug]
        cap = (e["caption"] or "")[:70]
        pooln = len(e["pool"])
        weak = "  <-- WEAK POOL" if pooln < 2 else ""
        print(
            f"  {slug} -> {e['image_file']}\n"
            f"      ch={e['channel']} score={e['score']} pool={pooln}{weak}\n"
            f"      caption: {cap}"
        )
        if "guardrail" in e:
            print(f"      guardrail: {e['guardrail']}")


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

    dam_keys_path = pathlib.Path(args.dam_keys)
    if not dam_keys_path.exists():
        print(
            f"ERROR: --dam-keys file {dam_keys_path} not found. Every theme must "
            "reconcile to a real DAM key; regenerate it (e.g. aws s3 ls of the "
            f"'{DAM_PREFIX}' prefix, basenames one per line) before building.",
            file=sys.stderr,
        )
        return 2

    real_keys = load_dam_keys(dam_keys_path)
    print(f"loaded {len(real_keys)} real DAM keys from {dam_keys_path}")

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
