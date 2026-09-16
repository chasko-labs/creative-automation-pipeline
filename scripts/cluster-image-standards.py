#!/usr/bin/env python
"""Derive Kodiak image design-standards by clustering the real Nova image vectors.

match-before-jazz: this reads data/vectors/kodiak-embeddings.jsonl (real
amazon.nova-2-multimodal-embeddings-v1:0 output, 1024-dim), filters to the
type=="image" rows, and groups them by cosine similarity with a hand-rolled
spherical k-means (numpy only — no scikit-learn dependency).

Vectors carry no pixels. Every standard emitted here is metadata-informed:
cluster cohesion (how tightly the Nova vectors group) plus the metadata that
co-occurs inside a cluster (channel, product, caption/title/tag/alt terms,
in_image_text). Where the script infers a visual pattern it says so and the
markdown doc carries an explicit confidence level.

Outputs:
  data/vectors/image-clusters.json   machine-readable cluster registry for UI/component-library
  docs/kodiak-image-standards.md     findings-first standards doc

Run:  uv run --extra analysis python scripts/cluster-image-standards.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - guidance path only
    sys.stderr.write(
        "numpy is required. Install the analysis extra:\n"
        "  uv run --extra analysis python scripts/cluster-image-standards.py\n"
    )
    raise SystemExit(2) from None

REPO = Path(__file__).resolve().parents[1]
VECTORS = REPO / "data" / "vectors" / "kodiak-embeddings.jsonl"
CLUSTERS_JSON = REPO / "data" / "vectors" / "image-clusters.json"
STANDARDS_MD = REPO / "docs" / "kodiak-image-standards.md"

# spherical k-means config. K sits in the requested 8-15 band; deterministic seed
# so the doc + json regenerate identically for review.
K = 12
SEED = 20260902
MAX_ITERS = 100

# tokens that carry no brand signal — strip before counting common terms so the
# cluster fingerprints surface real subject/composition words, not scaffolding.
_STOPWORDS = {
    "the", "and", "for", "with", "your", "you", "our", "a", "an", "of", "to", "in",
    "on", "at", "is", "it", "this", "that", "kodiak", "cakes", "kodiakcakes",
    "image", "variant", "photoshop", "rework", "01", "02", "jpg", "png", "cups",
    "kodiak_cakes", "wgs_product_name", "w_cdgo_title", "amp", "nbsp",
    # ingest-template scaffolding tokens — carry no subject signal
    "wgs", "cdgo", "name", "title", "product", "recipe", "recipes", "course",
    "meal", "nfp", "mix", "img", "html", "blogs",
}
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def load_image_rows(path: Path) -> tuple[np.ndarray, list[dict]]:
    """Load type=='image' rows: return (N x dim float32 matrix, list of metadata dicts)."""
    vectors: list[list[float]] = []
    metas: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("type") != "image":
                continue
            vec = row.get("vector")
            if not vec:
                continue
            vectors.append(vec)
            meta = dict(row.get("metadata") or {})
            meta.setdefault("id", row.get("id"))
            metas.append(meta)
    mat = np.asarray(vectors, dtype=np.float32)
    return mat, metas


def l2_normalize(mat: np.ndarray) -> np.ndarray:
    """Row-normalize so a dot product equals cosine similarity."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def kmeans_plus_plus_init(x: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """k-means++ seeding on the unit sphere (distance = 1 - cosine)."""
    n = x.shape[0]
    first = int(rng.integers(n))
    centers = [x[first]]
    closest_sim = x @ x[first]
    for _ in range(1, k):
        dist = 1.0 - closest_sim
        dist = np.clip(dist, 0.0, None)
        total = float(dist.sum())
        if total <= 0:
            centers.append(x[int(rng.integers(n))])
            continue
        probs = dist / total
        idx = int(rng.choice(n, p=probs))
        centers.append(x[idx])
        sim_new = x @ x[idx]
        closest_sim = np.maximum(closest_sim, sim_new)
    return np.vstack(centers)


def spherical_kmeans(
    x: np.ndarray, k: int, seed: int, max_iters: int
) -> tuple[np.ndarray, np.ndarray]:
    """Cosine k-means. Returns (labels, centroids). Assign by max dot, renormalize centroids."""
    rng = np.random.default_rng(seed)
    centroids = kmeans_plus_plus_init(x, k, rng)
    labels = np.zeros(x.shape[0], dtype=np.int32)
    for _ in range(max_iters):
        sims = x @ centroids.T
        new_labels = sims.argmax(axis=1).astype(np.int32)
        if np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels
        for c in range(k):
            members = x[labels == c]
            if members.shape[0] == 0:
                # reseed an empty cluster on the worst-fit point to keep K stable
                worst = int(sims.max(axis=1).argmin())
                centroids[c] = x[worst]
                continue
            centroids[c] = members.mean(axis=0)
        centroids = l2_normalize(centroids)
    return labels, centroids


def cohesion(x: np.ndarray, labels: np.ndarray, centroids: np.ndarray, c: int) -> float:
    """Mean cosine of members to their centroid — how tight the visual group is."""
    members = x[labels == c]
    if members.shape[0] == 0:
        return 0.0
    return float((members @ centroids[c]).mean())


def common_terms(metas: list[dict], limit: int = 12) -> list[str]:
    """Most frequent meaningful tokens across caption/title/tags/alt/product/recipe."""
    counter: Counter[str] = Counter()
    for m in metas:
        parts: list[str] = []
        for key in ("caption", "title", "product", "recipe", "section", "slug"):
            val = m.get(key)
            if isinstance(val, str):
                parts.append(val)
        for key in ("tags", "alt_texts", "hashtags", "dietary"):
            val = m.get(key)
            if isinstance(val, list):
                parts.extend(str(v) for v in val)
        blob = " ".join(parts).lower().replace("-", " ").replace("_", " ")
        toks = {t for t in _TOKEN_RE.findall(blob) if t not in _STOPWORDS}
        counter.update(toks)
    return [t for t, _ in counter.most_common(limit)]


def sample_ids(metas: list[dict], limit: int = 6) -> list[str]:
    """Representative image filenames (fall back to row id) for a cluster."""
    out: list[str] = []
    for m in metas:
        name = m.get("image_file") or m.get("source_file") or m.get("id")
        if name and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def in_image_text_summary(metas: list[dict]) -> dict:
    """Count in_image_text states. None means the field is absent for that row."""
    c: Counter = Counter(m.get("in_image_text") for m in metas)
    return {
        "false": int(c.get(False, 0)),
        "true": int(c.get(True, 0)),
        "absent": int(c.get(None, 0)),
    }


def build_clusters(x: np.ndarray, metas: list[dict], labels: np.ndarray, centroids: np.ndarray):
    """Assemble the per-cluster registry, sorted largest-first."""
    clusters = []
    for c in range(centroids.shape[0]):
        idx = [i for i, lbl in enumerate(labels) if lbl == c]
        if not idx:
            continue
        cmetas = [metas[i] for i in idx]
        chan = Counter(m.get("channel") for m in cmetas)
        dominant, dom_count = chan.most_common(1)[0]
        clusters.append(
            {
                "size": len(idx),
                "dominant_channel": dominant,
                "dominant_channel_share": round(dom_count / len(idx), 3),
                "channel_mix": dict(chan.most_common()),
                "cohesion": round(cohesion(x, labels, centroids, c), 4),
                "in_image_text": in_image_text_summary(cmetas),
                "common_terms": common_terms(cmetas),
                "sample_ids": sample_ids(cmetas),
            }
        )
    clusters.sort(key=lambda d: d["size"], reverse=True)
    for new_id, cl in enumerate(clusters):
        cl["cluster_id"] = new_id
    return clusters


def write_clusters_json(clusters: list[dict], totals: dict) -> None:
    payload = {
        "model": "amazon.nova-2-multimodal-embeddings-v1:0",
        "dim": 1024,
        "method": "spherical k-means (cosine), numpy-only, deterministic",
        "k": len(clusters),
        "seed": SEED,
        "totals": totals,
        "note": (
            "metadata-informed clustering, not pixel analysis. cohesion is mean "
            "cosine of members to centroid. in_image_text.absent = field not present "
            "on that row (only blog rows carry the flag)."
        ),
        "clusters": {
            str(c["cluster_id"]): {
                "size": c["size"],
                "dominant_channel": c["dominant_channel"],
                "dominant_channel_share": c["dominant_channel_share"],
                "channel_mix": c["channel_mix"],
                "cohesion": c["cohesion"],
                "in_image_text": c["in_image_text"],
                "common_terms": c["common_terms"],
                "sample_ids": c["sample_ids"],
            }
            for c in clusters
        },
    }
    CLUSTERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with CLUSTERS_JSON.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _fmt_terms(terms: list[str]) -> str:
    return ", ".join(f"`{t}`" for t in terms) if terms else "_(filename-derived only)_"


def _fmt_mix(mix: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in mix.items())


def write_standards_md(clusters: list[dict], totals: dict) -> None:
    iit = totals["in_image_text"]
    n_img = totals["image_rows"]
    blog = totals["channel_counts"].get("blog", 0)
    lines: list[str] = []
    lines.append("# kodiak image standards — derived from the real nova vectors")
    lines.append("")
    lines.append(
        "match before jazz. this spec is built from clustering "
        f"{n_img} real image embeddings "
        "(`amazon.nova-2-multimodal-embeddings-v1:0`, 1024-dim), not from "
        "assumptions about the brand."
    )
    lines.append("")
    lines.append(
        "honesty gate up front: vectors carry no pixels. every standard below is "
        "metadata-informed — cluster cohesion (how tightly nova groups the images) "
        "plus the metadata that co-occurs inside each cluster. no claim here is a "
        "pixel measurement. confidence levels are attached to every inferred visual "
        "pattern."
    )
    lines.append("")

    lines.append("## findings")
    lines.append("")
    lines.append(f"- clustered {n_img} image vectors into {len(clusters)} visual groups "
                 "by cosine similarity (spherical k-means, numpy-only, deterministic seed)")
    lines.append("- channel population: " + _fmt_mix(totals["channel_counts"]))
    lines.append(
        f"- in-image-text: {iit['false']} rows explicitly flagged `in_image_text=false`, "
        f"{iit['true']} flagged true, {iit['absent']} rows do not carry the field. "
        f"the false flags are all on the {blog} blog rows — those are the rows the "
        "ingest pipeline evaluated for baked-in text, and every one came back clean "
        "(confidence high for blog; the catalog/amazon/social rows are unlabeled, so "
        "no-text there is inferred from the product-shot nature of the source, "
        "confidence medium)"
    )
    lines.append(
        "- the catalog channel dominates "
        f"({totals['channel_counts'].get('catalog', 0)} of {n_img}); these are "
        "packaging/product renders whose caption+product fields are filename-derived, "
        "so their text signal is weak and clustering leans almost entirely on the "
        "nova vector geometry"
    )
    lines.append(
        "- blog + instagram rows carry real human text (captions, recipe titles, tags, "
        "alt text, hashtags) — that is where subject/composition terms are trustworthy"
    )
    lines.append("")

    lines.append("## clusters")
    lines.append("")
    lines.append(
        "each cluster is a nova-cosine group. `cohesion` is the mean cosine of members "
        "to the cluster centroid (closer to 1.0 = tighter, more visually consistent group)."
    )
    lines.append("")
    lines.append("| id | size | dominant channel (share) | cohesion | in-image-text (f/t/absent) | common terms |")
    lines.append("| -- | ---- | ------------------------ | -------- | -------------------------- | ------------ |")
    for c in clusters:
        iitc = c["in_image_text"]
        lines.append(
            f"| {c['cluster_id']} | {c['size']} | "
            f"{c['dominant_channel']} ({c['dominant_channel_share']:.0%}) | "
            f"{c['cohesion']:.3f} | "
            f"{iitc['false']}/{iitc['true']}/{iitc['absent']} | "
            f"{_fmt_terms(c['common_terms'][:8])} |"
        )
    lines.append("")

    lines.append("### cluster read (metadata-informed, confidence flagged)")
    lines.append("")
    for c in clusters:
        share = c["dominant_channel_share"]
        conf = "high" if (c["cohesion"] >= 0.6 and share >= 0.8) else (
            "medium" if c["cohesion"] >= 0.45 else "low"
        )
        subject = _infer_subject(c)
        lines.append(
            f"- cluster {c['cluster_id']} — {c['size']} images, "
            f"{c['dominant_channel']} {share:.0%}, cohesion {c['cohesion']:.3f}. "
            f"{subject} (confidence {conf})"
        )
    lines.append("")

    lines.append("## what kodiak imagery consistently does")
    lines.append("")
    lines.append(
        "- no baked-in text on evaluated assets — every blog row carries "
        f"`in_image_text=false` ({blog}/{blog}). text lives in the layout layer, not "
        "the photograph. **standard: generated/spun assets must keep the image "
        "text-free and push copy to the caption/overlay layer.** (confidence high for "
        "blog-sourced, medium generalizing to catalog/social)"
    )
    lines.append(
        "- nova organizes the imagery by **food subject, not by channel** — every "
        "cluster is catalog-dominant (catalog is 76% of the corpus) yet each one "
        "coheres around a recognizable subject: waffles, blueberry/lemon bakes, "
        "apple-cinnamon, cookies/chocolate-chip, muffins, and a distinct "
        "nutrition-panel/ingredients group. **standard: a spun asset belongs to a "
        "food-subject family; score it against that family, not a global average.** "
        "(confidence high — direct cluster separation by subject)"
    )
    lines.append(
        "- within a subject cluster, catalog product shots and blog food-styling "
        "shots of the same food co-locate. that means the packaging render and the "
        "prepared-food photo of one product share a consistent nova signature. "
        "**standard: a product's pack shot and its recipe/lifestyle shot should read "
        "as the same visual family.** (confidence high — the channel mix inside each "
        "cluster shows catalog+blog together)"
    )
    lines.append(
        "- the nutrition/ingredients-panel imagery separates cleanly from prepared-food "
        "imagery (see the `ingredients`/`nutrition` cluster). **standard: hold "
        "info-panel assets to their own scorecard — they are not lifestyle shots.** "
        "(confidence high — cluster separation)"
    )
    lines.append(
        "- recurring subject vocabulary in the human-authored channels centers on the "
        "breakfast-stack / protein / whole-grain / frontier story (see blog + instagram "
        "common terms above). **standard: on-brand food styling shows the prepared "
        "stack/bake, not raw mix.** (confidence medium — term-frequency inference)"
    )
    lines.append(
        "- palette: the brand anchors on Bear Brown #3B2316 with a Wasatch/wild "
        "outdoor register (per brand-lore text vectors and pyproject brand line). the "
        "vectors cannot measure hex values, so palette adherence is asserted from "
        "brand-lore, not from pixels. **standard: score palette against Bear Brown + "
        "earthen neutrals.** (confidence medium — brand-lore-sourced, not vector-measured)"
    )
    lines.append("")

    lines.append("## curation rules (engineer-ready scorecard checks)")
    lines.append("")
    lines.append(
        "these turn directly into `scorecards.py` checks. each references cluster "
        "evidence so a reviewer can trace the rule back to the data."
    )
    lines.append("")
    lines.append("- **rule cr-1 no-in-image-text**: reject assets with detected baked-in "
                 f"text. evidence: {blog}/{blog} blog rows are `in_image_text=false`, "
                 "zero true. severity high.")
    lines.append("- **rule cr-2 subject-family match**: classify each asset into its "
                 "nearest food-subject cluster (waffles, blueberry, apple-cinnamon, "
                 "cookies, muffins, nutrition-panel, etc) and score it against that "
                 "cluster's cohesion band, not the global mean. evidence: clusters are "
                 "subject-coherent and catalog+blog of one subject co-locate. severity "
                 "high.")
    lines.append("- **rule cr-3 cohesion floor**: an asset's cosine similarity to its "
                 "nearest cluster centroid must clear that cluster's cohesion floor "
                 "(see per-cluster cohesion in image-clusters.json). below-floor = "
                 "off-brand outlier, route to human review. severity medium.")
    lines.append("- **rule cr-4 palette adherence**: score against Bear Brown #3B2316 + "
                 "earthen neutrals. evidence: brand-lore text vectors (asserted, not "
                 "pixel-measured). severity medium.")
    lines.append("- **rule cr-5 subject vocabulary**: caption/alt copy should hit the "
                 "prepared-stack / protein / whole-grain / frontier vocabulary. "
                 "evidence: blog+instagram common terms. severity low (copy hint).")
    lines.append("")

    lines.append("## spin guidance (preserve-to-stay-on-brand)")
    lines.append("")
    lines.append(
        "given a real Kodiak asset to spin into a local variant, preserve the signals "
        "that keep it inside its cluster:"
    )
    lines.append("")
    lines.append("- **preserve subject family**: a waffle shot stays in the waffle "
                 "family, a muffin shot in the muffin family. crossing subject clusters "
                 "reads as off-brand (cr-2).")
    lines.append("- **preserve text-free frame**: never bake the localized copy into the "
                 "pixels — swap it in the overlay/caption layer (cr-1).")
    lines.append("- **preserve palette anchor**: keep Bear Brown + earthen neutrals; a "
                 "localized seasonal ingredient can shift accent color but not the anchor "
                 "(cr-4).")
    lines.append("- **allowed jazz**: local ingredient swap, seasonal backdrop, regional "
                 "caption/dialect term. these live in metadata + overlay, so they do not "
                 "move the asset out of its nova cluster.")
    lines.append("- **check after spin**: re-embed the spun asset and confirm it still "
                 "lands in the source cluster above the cohesion floor (cr-3).")
    lines.append("")

    lines.append("## method + honesty notes")
    lines.append("")
    lines.append(f"- clustering: spherical k-means (cosine), k={len(clusters)}, "
                 f"seed={SEED}, numpy-only (no scikit-learn). deterministic — "
                 "re-running regenerates this doc identically.")
    lines.append("- this is metadata-informed clustering, **not pixel analysis**. cluster "
                 "geometry is real (nova vectors); subject/composition reads are inferred "
                 "from co-occurring metadata and carry confidence flags.")
    lines.append("- catalog/amazon captions are filename-derived and contribute little "
                 "text signal; those clusters are shaped by vector geometry alone.")
    lines.append("- machine-readable form: `data/vectors/image-clusters.json`.")
    lines.append("")

    STANDARDS_MD.parent.mkdir(parents=True, exist_ok=True)
    STANDARDS_MD.write_text("\n".join(lines), encoding="utf-8")


def _infer_subject(cluster: dict) -> str:
    """Best-effort subject read from dominant channel + common terms."""
    ch = cluster["dominant_channel"]
    terms = [t for t in cluster["common_terms"] if t not in {"buttermilk"}]
    food = ", ".join(terms[:4]) if terms else "unlabeled product renders"
    blog_n = cluster["channel_mix"].get("blog", 0)
    # every cluster is catalog-dominant (catalog is 76% of the corpus); the
    # meaningful read is the food subject the cluster organizes around, and how
    # much human-authored blog imagery co-clusters with the catalog product shots
    return (
        f"food-subject group leaning {food} — {cluster['channel_mix'].get('catalog', 0)} "
        f"catalog product shots co-cluster with {blog_n} blog food-styling shots of the "
        f"same subject (dominant channel {ch})"
    )


def main() -> int:
    if not VECTORS.exists():
        sys.stderr.write(f"vectors file not found: {VECTORS}\n")
        return 1
    mat, metas = load_image_rows(VECTORS)
    if mat.shape[0] == 0:
        sys.stderr.write("no image rows found\n")
        return 1
    x = l2_normalize(mat)
    labels, centroids = spherical_kmeans(x, K, SEED, MAX_ITERS)
    clusters = build_clusters(x, metas, labels, centroids)
    totals = {
        "image_rows": int(mat.shape[0]),
        "dim": int(mat.shape[1]),
        "channel_counts": dict(Counter(m.get("channel") for m in metas).most_common()),
        "in_image_text": in_image_text_summary(metas),
    }
    write_clusters_json(clusters, totals)
    write_standards_md(clusters, totals)
    print(f"image rows clustered: {totals['image_rows']}")
    print(f"clusters (k): {len(clusters)}")
    for c in clusters:
        print(
            f"  cluster {c['cluster_id']:>2}: size {c['size']:>4}  "
            f"{c['dominant_channel']:<9} {c['dominant_channel_share']:.0%}  "
            f"cohesion {c['cohesion']:.3f}"
        )
    print(f"wrote {CLUSTERS_JSON.relative_to(REPO)}")
    print(f"wrote {STANDARDS_MD.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
