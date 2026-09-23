"""Build coach/knowledge.md from committed repo sources (deterministic).

Reads data/products/theme-asset-map.json (theme briefs) plus the retailer copy
framings, brand copy law, past-post voice digests from data/raw-ingest, and the
pipeline-tool map (already encoded in youtube-deep.json), then appends
coach/knowledge-static.md (how-to-steer recipes). A test asserts the committed
knowledge.md regenerates byte-identical, so grounding can never drift from the
shipped themes.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parents[1]
MAP = ROOT / "data" / "products" / "theme-asset-map.json"
STATIC = ROOT / "coach" / "knowledge-static.md"
OUT = ROOT / "coach" / "knowledge.md"
INGEST = ROOT / "data" / "raw-ingest" / "kodiakcakes"

# Retailer copy framings, mirrored from _THEME_COPY_HINT in generate.py.
COPY_HINTS = {
    "localized-costco": "bulk Family Size value — warehouse-club aisle, stock-up trip",
    "localized-publix": "neighborhood warmth — southern family table",
    "localized-target": "everyday-family aisle — one-trip basket, modern everyday value",
    "kodiak-subscription": "subscription cadence — front-door delivery, pantry always stocked",
}


def _clean(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _voice_lines() -> list[str]:
    """Deterministic past-post voice digest from committed raw-ingest deeps."""
    lines = ["", "## Past social voice (observed @kodiakcakes — steer toward this)"]
    try:
        insta = json.loads((INGEST / "insta-deep.json").read_text(encoding="utf-8"))
    except OSError:
        return lines
    lines.append(f"- instagram {insta.get('handle', '')} ({insta.get('followers', 0):,} followers): {_clean(insta.get('bio'), 120)}")
    tags = insta.get("hashtag_families", {}) or {}
    lines.append(f"- primary tags: {' '.join(tags.get('primary_brand', [])[:4])}".rstrip())
    lines.append(f"- secondary tags: {' '.join(tags.get('secondary_brand', [])[:6])}".rstrip())
    when = insta.get("when_they_post", {}) or {}
    if when.get("time_of_day"):
        lines.append(f"- post window: {_clean(when['time_of_day'], 140)}")
    cadence = (insta.get("posting_cadence", {}) or {}).get("observed_dates_2026", [])
    if cadence:
        lines.append(f"- recent cadence ({len(cadence)} observed): {'; '.join(cadence[:3])}")
    for name in ("tiktok-deep", "facebook-deep"):
        try:
            deep = json.loads((INGEST / f"{name}.json").read_text(encoding="utf-8"))
        except OSError:
            continue
        handle = deep.get("handle") or deep.get("title", "")
        bio = _clean(deep.get("bio"), 100)
        lines.append(f"- {deep.get('platform', name)} {handle}: {bio}".rstrip())
    return lines


def _pack_lines() -> list[str]:
    """Deterministic half of context_pack.py fused at build time (no network).

    Brand rules are parsed (ast) from the module constant so they cannot drift;
    image-cluster topics, sample-prompt voice, and market-language coverage are
    digested from the same committed files the pack reads per request.
    """
    import ast as _ast

    lines = ["", "## Context pack (deterministic grounding, fused at build)"]
    try:
        tree = _ast.parse((ROOT / "src" / "creative_automation" / "context_pack.py").read_text(encoding="utf-8"))
        consts: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, _ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], _ast.Name):
                try:
                    val = _ast.literal_eval(node.value)
                except ValueError:
                    continue
                if isinstance(val, str):
                    consts[node.targets[0].id] = val
        rules = consts.get("BRAND_RULES", "")
        if not rules:
            # BRAND_RULES is a tuple of literals with one f-string seam
            # (PALETTE_ANCHOR); join it the way the module does.
            for node in tree.body:
                if isinstance(node, _ast.Assign) and getattr(node.targets[0], "id", "") == "BRAND_RULES":
                    parts = []
                    elts = node.value.elts if isinstance(node.value, _ast.Tuple) else [node.value]
                    for e in elts:
                        if isinstance(e, _ast.Constant):
                            parts.append(str(e.value))
                        elif isinstance(e, _ast.JoinedStr):
                            for v in e.values:
                                if isinstance(v, _ast.Constant):
                                    parts.append(str(v.value))
                                elif isinstance(v, _ast.FormattedValue) and isinstance(v.value, _ast.Name):
                                    parts.append(consts.get(v.value.id, ""))
                    rules = "".join(parts)
        if rules:
            lines.append(f"- brand rules: {_clean(rules, 400)}")
    except (OSError, SyntaxError):
        pass
    try:
        clusters = json.loads((ROOT / "data" / "vectors" / "image-clusters.json").read_text(encoding="utf-8"))
        subs = []
        for cid in sorted(clusters.get("clusters", {}), key=int):
            c = clusters["clusters"][cid]
            terms = ", ".join((c.get("common_terms") or [])[:5])
            subs.append(f"c{cid} (n={c.get('size', 0)}, {c.get('dominant_channel', '?')}): {terms}")
        lines.append(f"- image topics ({clusters.get('k', 0)} clusters): {'; '.join(subs)}"[:1200])
    except (OSError, ValueError, KeyError):
        pass
    try:
        prompts = (ROOT / "data" / "prompts" / "blog-sample-prompts.jsonl").read_text(encoding="utf-8").splitlines()
        for i, line in enumerate([p for p in prompts if p.strip()][:2]):
            prompt = json.loads(line).get("prompt", "")
            lines.append(f"- sample voice {i + 1}: {_clean(prompt, 160)}")
    except (OSError, ValueError):
        pass
    try:
        meta = json.loads((ROOT / "data" / "localization" / "market-languages.json").read_text(encoding="utf-8")).get("metadata", {})
        lines.append(f"- market languages: {meta.get('total_markets', '?')} markets, {meta.get('total_localized_variants', '?')} localized variants")
    except (OSError, ValueError):
        pass
    return lines


def _pipeline_lines() -> list[str]:
    """Pipeline-tool map, mirrored from the committed youtube-deep mapping."""
    lines = ["", "## Pipeline tools the counsel can steer toward"]
    try:
        mapping = json.loads((INGEST / "youtube-deep.json").read_text(encoding="utf-8")).get("pipeline_mapping", {})
    except OSError:
        mapping = {}
    ratios = mapping.get("compose_ratios", {}) or {}
    for ratio in sorted(ratios):
        lines.append(f"- {ratio}: {_clean(ratios[ratio], 140)}")
    if mapping.get("asset_reuse"):
        lines.append(f"- asset reuse: {_clean(mapping['asset_reuse'], 160)}")
    lines.append("- compliance: src/creative_automation/compliance.py — caption, hashtag, scrim checks run per creative")
    lines.append("- recipe cards: Nova-authored copy with deterministic fallback; card template runs in full mode")
    return lines


COPY_LAW_LINES = [
    "",
    "## Brand standards (copy law — hard rules, never negotiable)",
    "- the word KODIAK (all caps) never ships in copy, except inside a hashtag token",
    "- title-case Kodiak only as Kodiak Cakes or Kodiak Park City; bare Kodiak appears nowhere",
    "- social voice uses #kodiakcakes-style hashtags, never invented translations or frontier data",
    "- thin-month event suggestions are UNVERIFIED until confirmed — say so plainly",
    "- canon: tests/test_atlanta_copy_law.py, src/creative_automation/platform_copy.py",
]


def build() -> str:
    data = json.loads(MAP.read_text(encoding="utf-8"))["map"]
    lines = ["# Kodiak campaign creator — coach knowledge", ""]
    lines.append("## Themes (chip slug: brief)")
    for slug in sorted(data):
        brief = re.sub(r"\s+", " ", str(data[slug].get("brief", ""))).strip()
        lines.append(f"- {slug}: {brief}")
    lines += ["", "## Retailer copy framings (ship in the copy sidecar)"]
    for slug in sorted(COPY_HINTS):
        lines.append(f"- {slug}: {COPY_HINTS[slug]}")
    lines += COPY_LAW_LINES
    lines += _voice_lines()
    lines += _pack_lines()
    lines += _pipeline_lines()
    lines += ["", STATIC.read_text(encoding="utf-8").rstrip(), ""]
    return "\n".join(lines)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
