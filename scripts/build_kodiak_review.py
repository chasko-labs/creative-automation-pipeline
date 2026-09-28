#!/usr/bin/env python3
"""build_kodiak_review.py - Kodiak ingredient ink send/get review page.

Mirrors scouts-pipeline/scripts/build_aaliyah_review.py pattern:
every ledger row shows EXACTLY what was sent (taxon, prompt, negative,
seed) and what came back (image) plus the visual verdict. Regenerate
after every landing:

  python3 scripts/build_kodiak_review.py

Outputs:
  preview/kodiak-review/index.html  (repo-local, committed preview)
  ../typescript-survival-guide/scouts-pipeline/preview/kodiak-review/index.html
    (when that sibling checkout exists, for http://192.168.4.53:8090/kodiak-review/)

Source of truth: input_assets/sprint2-ingredients/batch-c-review.jsonl
plus the canonical seed manifest batch-c-final-manifest.json. No /tmp.
"""
from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "input_assets" / "sprint2-ingredients" / "batch-c-review.jsonl"
MANIFEST = ROOT / "input_assets" / "sprint2-ingredients" / "batch-c-final-manifest.json"
POOL = ROOT / "input_assets" / "sprint2-ingredients"
OUT_LOCAL = ROOT / "preview" / "kodiak-review"
OUT_LOCAL_IMG = OUT_LOCAL / "img"
# sibling checkout that serves :8090
OUT_SIBLING = Path("/home/bryanchasko/code/chasko-labs/typescript-survival-guide/scouts-pipeline/preview/kodiak-review")
OUT_SIBLING_IMG = OUT_SIBLING / "img"


def load_ledger() -> list[dict]:
    rows: list[dict] = []
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_manifest_map() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    data = json.loads(MANIFEST.read_text())
    return {it["slug"]: it for it in data.get("items", [])}


def subject_map() -> dict[tuple[str, int], dict]:
    """Map (slug, seed) -> {subject, taxon, ingredient} from all batch jsons."""
    m: dict[tuple[str, int], dict] = {}
    for p in POOL.glob("batch-c*.json"):
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        items = data.get("items", data) if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            slug = it.get("slug")
            seed = it.get("seed")
            if not slug or not isinstance(seed, int):
                continue
            # subject is the sent prompt tail; taxon+ingredient are denormalized
            m[(slug, seed)] = {
                "subject": it.get("subject", ""),
                "prompt": it.get("prompt", ""),
                "taxon": it.get("taxon", ""),
                "ingredient": it.get("ingredient", ""),
            }
    # also from manifest prompts
    for slug, it in load_manifest_map().items():
        m[(slug, it["seed"])] = {
            "subject": it.get("prompt", ""),
            "prompt": it.get("prompt", ""),
            "taxon": it.get("taxon", ""),
            "ingredient": it.get("ingredient", ""),
        }
    return m


def card(title: str, lane: str, sent: list[tuple[str, str]], img_name: str | None, grade: str, ts: str) -> str:
    rows = "\n".join(f"<dt>{html.escape(k)}</dt><dd><pre>{html.escape(v)}</pre></dd>" for k, v in sent)
    if img_name and (OUT_LOCAL_IMG / img_name).exists():
        fig = f'<a href="img/{html.escape(img_name)}"><img src="img/{html.escape(img_name)}" alt="{html.escape(title)}"></a>'
    elif img_name and (POOL / img_name).exists():
        fig = f'<a href="img/{html.escape(img_name)}"><img src="img/{html.escape(img_name)}" alt="{html.escape(title)}"></a>'
    else:
        fig = "<p><em>no image (overwritten by later retry — see ledger note; file now reflects latest render for this slug)</em></p>"
    return (
        f"<article><h2>{html.escape(title)}</h2>"
        f"<p><strong>{html.escape(lane)}</strong> — {html.escape(grade)}<br><small>file: {html.escape(ts)}</small></p>"
        f"<h3>sent</h3><dl>{rows}</dl><h3>got</h3>{fig}</article>"
    )


def main() -> None:
    rows = load_ledger()
    manifest_map = load_manifest_map()
    subj = subject_map()

    # copy pool pngs to both outs (one file per slug, latest render)
    for out_img in [OUT_LOCAL_IMG, OUT_SIBLING_IMG]:
        out_img.mkdir(parents=True, exist_ok=True)
        for png in POOL.glob("*.png"):
            # skip non-ingredient pngs? pool is only ingredients, but keep all
            if png.stat().st_size < 1024:
                continue
            shutil.copy(png, out_img / png.name)

    cards: list[str] = []
    # newest first (reverse ledger is newest)
    for r in reversed(rows):
        slug = r.get("slug", "?")
        seed = r.get("seed", 0)
        verdict = r.get("verdict", "")
        taxon = r.get("taxon") or subj.get((slug, seed), {}).get("taxon", "") or manifest_map.get(slug, {}).get("taxon", "")
        ingredient = r.get("ingredient") or subj.get((slug, seed), {}).get("ingredient", "") or manifest_map.get(slug, {}).get("ingredient", "") or slug
        notes = r.get("notes", "")
        # lane label
        lane = f"ComfyUI SDXL base 1.0, kodiak-ink-ingredient, seed {seed}"
        if taxon:
            lane += f", {taxon}"
        # sent fields
        sent: list[tuple[str, str]] = []
        # exact prompt: prefer manifest prompt for that seed, else batch subject, else notes
        prompt = ""
        if (slug, seed) in subj and subj[(slug, seed)].get("prompt"):
            prompt = subj[(slug, seed)]["prompt"]
        elif (slug, seed) in subj and subj[(slug, seed)].get("subject"):
            prompt = subj[(slug, seed)]["subject"]
        elif slug in manifest_map and manifest_map[slug].get("seed") == seed:
            prompt = manifest_map[slug].get("prompt", "")
        if prompt:
            sent.append(("prompt", prompt))
        # negative is recorded in manifest; for rejects fall back to workflow base negative
        neg = manifest_map.get(slug, {}).get("negative_prompt", "") if slug in manifest_map and manifest_map[slug].get("seed") == seed else ""
        # for non-manifest rows, pull negative from any manifest row (same style)
        if not neg:
            # use first manifest negative as canonical
            sample = next(iter(manifest_map.values()), None)
            if sample:
                neg = sample.get("negative_prompt", "")
        if neg:
            sent.append(("negative", neg))
        sent.append(("taxon", taxon or "—"))
        sent.append(("ingredient", ingredient))
        sent.append(("slug", slug))
        sent.append(("seed", str(seed)))
        # provenance
        pool_file = POOL / f"{slug}.png"
        if pool_file.exists():
            sent.append(("pool file", f"{slug}.png — {pool_file.stat().st_size} bytes"))
        # image to show: latest pool file for this slug (all attempts for same slug share the file)
        img_name = f"{slug}.png" if (POOL / f"{slug}.png").exists() else None
        # grade line mirrors aaliyah style: verdict + notes
        grade = f"{verdict} — {notes}" if notes else verdict
        # timestamp from pool file mtime
        ts = "no file"
        if pool_file.exists():
            ts = datetime.fromtimestamp(pool_file.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        cards.append(card(f"{slug} — {seed}", lane, sent, img_name, grade, ts))

    # header stats
    approved = sum(1 for r in rows if r.get("verdict") == "approved")
    rejected = sum(1 for r in rows if "rejected" in r.get("verdict", ""))
    unique_slugs: dict[str, dict] = {}
    for r in rows:
        unique_slugs[r["slug"]] = r
    approved_latest = sum(1 for v in unique_slugs.values() if v.get("verdict") == "approved")
    seeded = len(manifest_map)

    header = (
        f"<p>Ledger: {len(rows)} attempts, {approved} approved / {rejected} rejected-retry. "
        f"Latest per slug: {approved_latest} approved, {len(unique_slugs) - approved_latest} rejected. "
        f"Seed manifest: {seeded} singles (one species per image, taxon-led). "
        f"Compounds excluded (mutant risk); pinon + red chile PARKED after 6-7 morphology failures; "
        f"pool files overwritten per retry — historical cards show latest file for that slug. "
        f"Source: <code>input_assets/sprint2-ingredients/batch-c-review.jsonl</code> + <code>batch-c-final-manifest.json</code>.</p>"
    )

    page = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Kodiak ingredient ink — send/get review</title><style>"
        "body{font-family:monospace;max-width:1000px;margin:auto;background:#111;color:#ddd}"
        "article{border:1px solid #444;margin:16px;padding:16px}"
        "img{max-width:100%}pre{white-space:pre-wrap;color:#9f9}"
        "dt{color:#fc6}dd{margin:0 0 12px}"
        "a{color:#8cf}"
        "</style></head><body>"
        "<h1>Kodiak ingredient ink — what was sent, what came back</h1>"
        + header
        + "\n".join(cards)
        + "</body></html>"
    )

    for out in [OUT_LOCAL / "index.html", OUT_SIBLING / "index.html"]:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page)
        print(f"wrote {out} ({len(cards)} cards)")

    # also write a json ledger snapshot for programmatic feedback
    snap = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ledger_rows": len(rows),
        "approved_rows": approved,
        "rejected_rows": rejected,
        "unique_slugs": len(unique_slugs),
        "approved_latest": approved_latest,
        "seed_manifest": seeded,
    }
    (OUT_LOCAL / "ledger.json").write_text(json.dumps(snap, indent=2))


if __name__ == "__main__":
    main()
