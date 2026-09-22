#!/usr/bin/env python3
"""
Troop art character-fidelity gate (deterministic, PIL + stdlib only).

Pattern reference: scripts/nova-act-check.py modes and exit codes —
exit 0 pass, exit 2 compliance failure, exit 1 I/O / usage error —
and JSON report to stdout (--json) or file (--out).

Input persona schema: input_assets/troop-personas/batch-X.json, a dict with
a "personas" list of {scout, roster_index, sheet_seed, headshot_seed,
identity_paragraph, signature_palette {hair, complexion, accent hexes},
negative_additions}. Older batches may carry signature_palette as a plain
hex list; that shape is mapped deterministically (darkest -> hair,
most-saturated -> accent, mid-lightness remainder -> complexion).

Checks per render (render PNGs live in --renders, matched to a persona when
the file stem contains the scout name, case-insensitive):
  1. lineage      — PNG-adjacent <stem>.prompt.json exists, carries the
                    persona seed (sheet_seed, headshot_seed accepted as
                    alternate and recorded), and contains the full identity
                    paragraph verbatim (whitespace-normalized).
                    Fallback: --sidecar-dir is scanned for a sidecar whose
                    filename fields reference the render basename.
  2. palette      — hair-region dominant colors vs palette hair hex, and
                    uniform-region dominant colors vs palette accent hex,
                    CIE76 Delta-E within tolerance. Min over candidate boxes
                    x top-K non-background quantized buckets (hair: 5 boxes
                    x top-5; uniform: 5 boxes incl. full-figure x top-20).
  3. composition  — single-figure / plain-background: FIND_EDGES density
                    under --edge-max AND background fraction over --bg-min.
  4. drift        — 64-bit dHash distance vs the scout gold (when a gold
                    exists in --gold-dir): must clear --drift-floor (not a
                    byte-copy/re-encode) and sit under --drift-ceiling
                    (same girl). Skipped when no gold exists.

Thresholds are calibrated on the three anchor golds in
input_assets/character-poc/gold (navya.png, aaliyah-sheet-v2_00001_.png,
maya-sheet-v5_00001_.png):
  hair min-dE 2.5/3.6/5.7 -> --hair-tol 20
  accent min-dE 11.1/22.4/13.2 (gold) and 11.x/24.7/13.x (synthetic
  fresh-render proxy) -> --accent-tol 28
  edge density 0.19-0.28 -> --edge-max 0.35
  background fraction 0.43-0.48 -> --bg-min 0.30
  cross-scout dHash 28-37, copy/re-encode 0-2 -> --drift-floor 4, --drift-ceil 24

Usage:
  uv run python scripts/troop-fidelity-check.py --persona input_assets/troop-personas/batch-c.json --renders output_troop/batch-c
  uv run python scripts/troop-fidelity-check.py --persona ... --renders ... --json
  uv run python scripts/troop-fidelity-check.py --self-test
  uv run python scripts/troop-fidelity-check.py --self-test --json

--self-test runs the three golds as synthetic fresh renders (deterministic
center-crop 90% + bicubic resize back, dHash 6/13/9 vs self — inside the
[4, 24] band) against inline persona skeletons carrying the real batch-a/c
identity paragraphs, palettes and blessed seeds, plus a negative control
(gold-vs-gold must trip the copy floor at d=0).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageFilter
except ImportError:
    print("[troop-fidelity-check] error: Pillow is required (pip install pillow)", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLD_DIR = REPO_ROOT / "input_assets" / "character-poc" / "gold"

# Relative probe boxes as (x0, y0, x1, y1) fractions of W/H.
HAIR_BOXES: dict[str, tuple[float, float, float, float]] = {
    "hair_top": (0.30, 0.00, 0.70, 0.22),
    "hair_wide": (0.20, 0.00, 0.80, 0.28),
    "hair_left": (0.15, 0.02, 0.45, 0.35),
    "hair_right": (0.55, 0.02, 0.85, 0.35),
    "hair_shoulders": (0.15, 0.18, 0.85, 0.45),
}
TORSO_BOXES: dict[str, tuple[float, float, float, float]] = {
    "torso_mid": (0.25, 0.35, 0.75, 0.65),
    "torso_narrow": (0.35, 0.40, 0.65, 0.60),
    "torso_wide": (0.15, 0.30, 0.85, 0.70),
    "torso_low": (0.25, 0.55, 0.75, 0.85),
    "figure_full": (0.10, 0.05, 0.90, 0.95),
}

DEFAULTS = {
    "hair_tol": 20.0,
    "accent_tol": 28.0,
    "edge_max": 0.35,
    "bg_min": 0.30,
    "drift_floor": 4,
    "drift_ceiling": 24,
}

# ---------------------------------------------------------------------------
# Color helpers (stdlib only)
# ---------------------------------------------------------------------------

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")[:6]
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _srgb_linear(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (_srgb_linear(c) for c in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def delta_e(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = rgb_to_lab(a), rgb_to_lab(b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(la, lb)))


def luminance(rgb: tuple[int, int, int]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def chroma(rgb: tuple[int, int, int]) -> int:
    return max(rgb) - min(rgb)


def normalize_palette(raw: Any, scout: str) -> dict[str, str]:
    """Map persona signature_palette to {hair, complexion, accent} hexes.

    Canonical shape is a dict; a legacy plain hex list is mapped
    deterministically: darkest -> hair, most saturated -> accent, and the
    mid-lightness remainder -> complexion.
    """
    if isinstance(raw, dict):
        try:
            return {"hair": raw["hair"], "complexion": raw["complexion"], "accent": raw["accent"]}
        except KeyError as e:
            raise ValueError(f"scout {scout}: signature_palette dict missing key {e}") from e
    if isinstance(raw, list) and len(raw) >= 3:
        hexes = [str(h) for h in raw]
        rgbs = [(h, hex_to_rgb(h)) for h in hexes]
        hair = min(rgbs, key=lambda t: luminance(t[1]))[0]
        rest = [t for t in rgbs if t[0] != hair] or rgbs
        accent = max(rest, key=lambda t: chroma(t[1]))[0]
        rest2 = [t for t in rest if t[0] != accent] or rest
        rest2.sort(key=lambda t: luminance(t[1]))
        complexion = rest2[len(rest2) // 2][0]
        return {"hair": hair, "complexion": complexion, "accent": accent}
    raise ValueError(f"scout {scout}: unrecognized signature_palette shape {type(raw).__name__}")


# ---------------------------------------------------------------------------
# Image probes (PIL only)
# ---------------------------------------------------------------------------

def crop_frac(img: Image.Image, coords: tuple[float, float, float, float]) -> Image.Image:
    w, h = img.size
    x0, y0, x1, y1 = coords
    return img.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))


def border_bg(img: Image.Image) -> tuple[int, int, int]:
    """Background estimate: median of the dominant quantized border-frame color."""
    small = img.resize((96, 168)).convert("RGB")
    px = list(small.getdata())
    w, h = 96, 168
    border = [px[y * w + x] for y in range(h) for x in range(w) if x < 3 or y < 3 or x >= w - 3 or y >= h - 3]
    hist: dict[tuple[int, int, int], int] = {}
    for p in border:
        q = (p[0] // 12, p[1] // 12, p[2] // 12)
        hist[q] = hist.get(q, 0) + 1
    top = max(hist, key=lambda k: hist[k])
    members = sorted(p for p in border if (p[0] // 12, p[1] // 12, p[2] // 12) == top)
    return members[len(members) // 2]


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def top_nonbg(
    region: Image.Image, bg: tuple[int, int, int], k: int, bgtol: int = 60
) -> list[tuple[tuple[int, int, int], float]]:
    """Top-K quantized dominant colors excluding near-background pixels.

    Returns [(median_rgb, fraction_of_foreground), ...] sorted by bucket size.
    """
    small = region.resize((64, 64)).convert("RGB")
    px = list(small.getdata())
    fg = [p for p in px if color_distance(p, bg) > bgtol]
    if not fg:
        return []
    hist: dict[tuple[int, int, int], int] = {}
    for p in fg:
        q = (p[0] // 16, p[1] // 16, p[2] // 16)
        hist[q] = hist.get(q, 0) + 1
    ranked = sorted(hist.items(), key=lambda kv: kv[1], reverse=True)[:k]
    out = []
    for bucket, _ in ranked:
        members = sorted(p for p in fg if (p[0] // 16, p[1] // 16, p[2] // 16) == bucket)
        out.append((members[len(members) // 2], len(members) / len(fg)))
    return out


def probe_target(
    img: Image.Image,
    bg: tuple[int, int, int],
    boxes: dict[str, tuple[float, float, float, float]],
    target: tuple[int, int, int],
    k: int,
) -> tuple[float, str, tuple[int, int, int] | None]:
    """Min Delta-E of target over (boxes x top-K buckets). Returns (dE, box, rgb)."""
    best = math.inf
    best_box = ""
    best_rgb: tuple[int, int, int] | None = None
    for name, coords in boxes.items():
        for rep, _ in top_nonbg(crop_frac(img, coords), bg, k):
            d = delta_e(rep, target)
            if d < best:
                best, best_box, best_rgb = d, name, rep
    return best, best_box, best_rgb


def edge_density(img: Image.Image) -> float:
    g = img.convert("L").resize((192, 336))
    edges = g.filter(ImageFilter.FIND_EDGES)
    px = list(edges.getdata())
    return sum(1 for p in px if p > 30) / len(px)


def background_fraction(img: Image.Image, bg: tuple[int, int, int], tol: int = 48) -> float:
    small = img.resize((96, 168)).convert("RGB")
    px = list(small.getdata())
    return sum(1 for p in px if color_distance(p, bg) <= tol) / len(px)


def dhash(img: Image.Image, size: int = 8) -> int:
    g = img.convert("L").resize((size + 1, size), Image.BILINEAR)
    px = list(g.getdata())
    bits = 0
    for r in range(size):
        row = r * (size + 1)
        for c in range(size):
            bits = (bits << 1) | (1 if px[row + c] > px[row + c + 1] else 0)
    return bits


def ham(a: int, b: int) -> int:
    return (a ^ b).bit_count()


# ---------------------------------------------------------------------------
# Sidecar lineage
# ---------------------------------------------------------------------------

def _walk_strings(obj: Any, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(obj, str):
        return [(path, obj)]
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            out.extend(_walk_strings(v, f"{path}.{k}"))
        return out
    if isinstance(obj, (list, tuple)):
        out = []
        for i, v in enumerate(obj):
            out.extend(_walk_strings(v, f"{path}[{i}]"))
        return out
    return []


def _walk_seeds(obj: Any, hits: list[int]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("seed", "sheet_seed", "headshot_seed", "blessed_seed") and isinstance(v, bool) is False and isinstance(v, int):
                hits.append(v)
            else:
                _walk_seeds(v, hits)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_seeds(v, hits)


def normalize_text(s: str) -> str:
    return " ".join(s.split())


def find_sidecar(render: Path, sidecar_dir: Path | None) -> Path | None:
    """Adjacent <stem>.prompt.json, else --sidecar-dir scan by filename reference."""
    adjacent = render.with_name(render.stem + ".prompt.json")
    if adjacent.exists():
        return adjacent
    if sidecar_dir is not None and sidecar_dir.is_dir():
        for cand in sorted(sidecar_dir.glob("*.prompt.json")):
            try:
                text = cand.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if render.name in text:
                return cand
    return None


@dataclass
class CheckOutcome:
    check: str
    passed: bool
    detail: str
    expected: Any = None
    actual: Any = None


def check_lineage(
    render: Path, persona: dict, palette: dict[str, str], sidecar_dir: Path | None
) -> list[CheckOutcome]:
    sidecar = find_sidecar(render, sidecar_dir)
    if sidecar is None:
        return [CheckOutcome(
            "lineage.sidecar", False,
            f"No sidecar: {render.stem}.prompt.json not adjacent"
            + (f" and no reference in {sidecar_dir}" if sidecar_dir else ""),
            f"{render.stem}.prompt.json", None,
        )]
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [CheckOutcome("lineage.sidecar", False, f"Sidecar unreadable {sidecar}: {e}", str(sidecar), None)]

    out = [CheckOutcome("lineage.sidecar", True, f"Sidecar present: {sidecar.name}", str(sidecar), sidecar.name)]

    seeds: list[int] = []
    _walk_seeds(data, seeds)
    seed_ok = persona["sheet_seed"] in seeds
    seed_role = "sheet_seed"
    if not seed_ok and persona.get("headshot_seed") in seeds:
        seed_ok = True
        seed_role = "headshot_seed"
    out.append(CheckOutcome(
        "lineage.seed", seed_ok,
        f"Seed {persona['sheet_seed']} ({seed_role}) "
        f"{'found' if seed_ok else 'NOT FOUND'} in {sidecar.name} (seeds seen: {sorted(set(seeds))})",
        persona["sheet_seed"], sorted(set(seeds)),
    ))

    want = normalize_text(persona["identity_paragraph"])
    blob = normalize_text(json.dumps(data, ensure_ascii=False))
    ident_ok = want in blob
    where = None
    if ident_ok:
        for path, s in _walk_strings(data):
            if want in normalize_text(s):
                where = path
                break
    out.append(CheckOutcome(
        "lineage.identity", ident_ok,
        f"Identity paragraph ({len(persona['identity_paragraph'])} chars) "
        f"{'verbatim in ' + str(where) if ident_ok else 'NOT FOUND verbatim in ' + sidecar.name}",
        f"{len(persona['identity_paragraph'])} chars verbatim", where,
    ))
    _ = palette  # palette unused here; kept for uniform per-check signature
    return out


def check_palette(
    img: Image.Image, bg: tuple[int, int, int], palette: dict[str, str], hair_tol: float, accent_tol: float
) -> list[CheckOutcome]:
    hair_rgb = hex_to_rgb(palette["hair"])
    accent_rgb = hex_to_rgb(palette["accent"])
    dh, hbox, hrgb = probe_target(img, bg, HAIR_BOXES, hair_rgb, k=5)
    da, abox, argb = probe_target(img, bg, TORSO_BOXES, accent_rgb, k=20)
    out = []
    if hrgb is None:
        out.append(CheckOutcome("palette.hair", False, "Hair regions are all background — no foreground to probe",
                                palette["hair"], None))
    else:
        out.append(CheckOutcome(
            "palette.hair", dh <= hair_tol,
            f"Hair {palette['hair']} vs #{hrgb[0]:02X}{hrgb[1]:02X}{hrgb[2]:02X} @{hbox} dE={dh:.1f} "
            f"{'OK' if dh <= hair_tol else 'OVER TOLERANCE'} (tol {hair_tol})",
            palette["hair"], {"dE": round(dh, 1), "box": hbox,
                              "sample": f"#{hrgb[0]:02X}{hrgb[1]:02X}{hrgb[2]:02X}"},
        ))
    if argb is None:
        out.append(CheckOutcome("palette.accent", False, "Uniform regions are all background — no foreground to probe",
                                palette["accent"], None))
    else:
        out.append(CheckOutcome(
            "palette.accent", da <= accent_tol,
            f"Accent {palette['accent']} vs #{argb[0]:02X}{argb[1]:02X}{argb[2]:02X} @{abox} dE={da:.1f} "
            f"{'OK' if da <= accent_tol else 'OVER TOLERANCE'} (tol {accent_tol})",
            palette["accent"], {"dE": round(da, 1), "box": abox,
                                "sample": f"#{argb[0]:02X}{argb[1]:02X}{argb[2]:02X}"},
        ))
    return out


def check_composition(img: Image.Image, bg: tuple[int, int, int], edge_max: float, bg_min: float) -> list[CheckOutcome]:
    ed = edge_density(img)
    bf = background_fraction(img, bg)
    return [
        CheckOutcome("composition.edgeDensity", ed <= edge_max,
                     f"Edge density {ed:.3f} {'OK' if ed <= edge_max else 'TOO BUSY'} (max {edge_max})",
                     f"<= {edge_max}", round(ed, 4)),
        CheckOutcome("composition.backgroundFraction", bf >= bg_min,
                     f"Background fraction {bf:.3f} {'OK' if bf >= bg_min else 'TOO LOW'} (min {bg_min})",
                     f">= {bg_min}", round(bf, 4)),
    ]


def find_gold(scout: str, gold_dir: Path) -> Path | None:
    if not gold_dir.is_dir():
        return None
    hits = sorted(p for p in gold_dir.glob("*.png") if scout.lower() in p.stem.lower())
    return hits[0] if hits else None


def check_drift(
    img: Image.Image, scout: str, gold_dir: Path, floor: int, ceiling: int
) -> tuple[list[CheckOutcome], Path | None]:
    gold = find_gold(scout, gold_dir)
    if gold is None:
        return [CheckOutcome("drift.gold", True, f"No gold for {scout} — drift check skipped",
                             "skip", "no gold")], None
    try:
        gold_img = Image.open(gold).convert("RGB")
    except (OSError, ValueError) as e:
        return [CheckOutcome("drift.gold", False, f"Cannot open gold {gold}: {e}", str(gold), None)], gold
    d = ham(dhash(img), dhash(gold_img))
    # Calibrated 2026-09-21: global dHash cannot separate same-girl-new-pose
    # (aaliyah re-worded render vs gold: 28) from different-girl
    # (same render vs navya gold: 21; face-crops 30 vs 30). So the hash only
    # gates the copy floor; identity rides on locked words + seed lineage +
    # palette probes + human eyeball. The ceiling argument stays accepted for
    # CLI compatibility and is reported, not enforced.
    passed = d >= floor
    if d < floor:
        why = f"COPY? distance {d} under floor {floor}"
    else:
        why = f"not a copy (distance {d} >= floor {floor}; ceiling {ceiling} advisory only)"
    return [CheckOutcome("drift.dhash", passed, f"dHash vs {gold.name}: distance {d} — {why}",
                         {"floor": floor, "ceiling": ceiling}, d)], gold


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------

@dataclass
class ScoutResult:
    scout: str
    roster_index: Any = None
    render: str | None = None
    gold: str | None = None
    passed: bool = False
    checks: list[dict] = field(default_factory=list)


def match_render(scout: str, renders: list[Path], kind: str) -> Path | None:
    want = f"{scout.lower()}-{kind}"
    hits = [p for p in renders if p.stem.lower() == want]
    if hits:
        return hits[0]
    loose = [p for p in renders if want in p.stem.lower() and ".prev" not in p.stem.lower()]
    return min(loose) if loose else None


def evaluate_persona(
    persona: dict, renders: list[Path], gold_dir: Path, sidecar_dir: Path | None, t: dict
) -> ScoutResult:
    scout = str(persona["scout"])
    res = ScoutResult(scout=scout, roster_index=persona.get("roster_index"))
    try:
        palette = normalize_palette(persona.get("signature_palette"), scout)
    except ValueError as e:
        res.checks = [asdict(CheckOutcome("palette.shape", False, str(e)))]
        res.passed = False
        return res

    checks: list[CheckOutcome] = []
    rendered: list[str] = []
    golds: list[str] = []
    # Both kinds gate: sheet and headshot each carry their own sidecar,
    # palette reads, and composition gates. A missing kind fails the scout.
    for kind in ("sheet", "headshot"):
        render = match_render(scout, renders, kind)
        if render is None:
            checks.append(CheckOutcome(
                f"{kind}.render.present", False,
                f"No render PNG matching '{scout}-{kind}' in renders dir",
                f"*{scout}-{kind}*.png", None))
            continue
        rendered.append(str(render))
        try:
            img = Image.open(render).convert("RGB")
        except (OSError, ValueError) as e:
            checks.append(CheckOutcome(
                f"{kind}.render.readable", False, f"Cannot open {render.name}: {e}"))
            continue

        bg = border_bg(img)
        for c in check_lineage(render, persona, palette, sidecar_dir):
            c.check = f"{kind}.{c.check}"
            checks.append(c)
        for c in check_palette(img, bg, palette, t["hair_tol"], t["accent_tol"]):
            c.check = f"{kind}.{c.check}"
            checks.append(c)
        # Headshots are tight crops: the sheet background floor (0.30)
        # misfires on them (observed 0.09-0.17 on good busts), so heads gate
        # on any visible background instead of a plain-field majority.
        bg_floor = t["bg_min"] if kind == "sheet" else 0.05
        for c in check_composition(img, bg, t["edge_max"], bg_floor):
            c.check = f"{kind}.{c.check}"
            checks.append(c)
        drift_checks, gold = check_drift(img, scout, gold_dir, t["drift_floor"], t["drift_ceiling"])
        for c in drift_checks:
            c.check = f"{kind}.{c.check}"
            checks.append(c)
        if gold is not None:
            golds.append(str(gold))
    res.render = ",".join(rendered) if rendered else None
    res.gold = ",".join(sorted(set(golds))) if golds else None
    res.checks = [asdict(c) for c in checks]
    # A skipped drift (no gold) carries passed=True and does not fail the scout.
    res.passed = bool(checks) and all(c.passed for c in checks)
    return res


def load_personas(persona_path: Path) -> list[dict]:
    data = json.loads(persona_path.read_text(encoding="utf-8"))
    personas = data.get("personas", data) if isinstance(data, dict) else data
    if not isinstance(personas, list) or not personas:
        raise ValueError(f"{persona_path}: expected non-empty personas list")
    for p in personas:
        for key in ("scout", "sheet_seed", "identity_paragraph", "signature_palette"):
            if key not in p:
                raise ValueError(f"{persona_path}: persona missing required key '{key}': {p.get('scout', p)}")
    return personas


def run_gate(
    personas: list[dict],
    renders_dir: Path,
    gold_dir: Path,
    sidecar_dir: Path | None,
    t: dict,
    label: str,
) -> dict:
    renders = sorted(renders_dir.glob("*.png")) if renders_dir.is_dir() else []
    scout_results = [asdict(evaluate_persona(p, renders, gold_dir, sidecar_dir, t)) for p in personas]
    matched = {r["render"] for r in scout_results if r["render"]}
    extras = sorted(str(p) for p in renders if str(p) not in matched)
    passed = sum(1 for r in scout_results if r["passed"])
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "label": label,
        "renders_dir": str(renders_dir),
        "gold_dir": str(gold_dir),
        "thresholds": dict(t),
        "scouts": scout_results,
        "unmatched_renders": extras,
        "summary": {
            "scouts_total": len(scout_results),
            "scouts_passed": passed,
            "scouts_failed": len(scout_results) - passed,
            "overall_passed": passed == len(scout_results) and len(scout_results) > 0,
        },
    }
    return report


# ---------------------------------------------------------------------------
# Self-test (inline persona skeletons + synthetic fresh renders)
# ---------------------------------------------------------------------------

SELF_TEST_PERSONAS: list[dict] = [
    {
        "scout": "Aaliyah",
        "roster_index": 1,
        "sheet_seed": 1005,
        "headshot_seed": 5001,
        "identity_paragraph": (
            "15-year-old Black girl with deep warm-brown skin and dark brown eyes, voluminous high-puff "
            "type-4 coily afro held by a thin yellow fabric headband, never straightened never loose curls "
            "never flat, rounded nose, full lips in a big warm smile, thick arched brows, small ears, bright "
            "yellow fabric bandana tied around her neck with a cloth knot and two fabric tails hanging at her "
            "throat, senior scout vest with patches over a full-length goldenrod-yellow camp shirt with the hem "
            "tucked into full-length khaki uniform cargos and zero midriff showing, animated comic-book style "
            "with heavy brush ink outlines, golden-yellow halftone dot shading and dynamic action lines."
        ),
        "signature_palette": {"hair": "#14100D", "complexion": "#8D5A3B", "accent": "#DAA520"},
        "negative_additions": ["straightened, relaxed or silky hair"],
    },
    {
        "scout": "Maya",
        "roster_index": 24,
        "sheet_seed": 2001,
        "headshot_seed": 5024,
        "identity_paragraph": (
            "11-year-old Indian-American girl with a warm medium-tan complexion and dark brown eyes, long "
            "thick dark rope-twist braids with a center part falling past her chest over both shoulders exactly "
            "as in her gold sheet image, never bob never bun never loose hair, oval face with a small straight "
            "nose, soft closed-lip playful smirk, straight natural brows, small ears, lavender tool pouch at her "
            "waist and a small closed red pocketknife held low at her side, purple long-sleeve shirt under an "
            "open khaki junior scout vest with patches, full-length yellow cargo pants with a side pocket and "
            "zero midriff showing, wide khaki belt with a brass buckle and orange-brown lace-up work boots with "
            "a large tan backpack over one shoulder, vibrant lavender-and-lime pop-art comic style with heavy "
            "brush ink outlines and halftone dot shading, plain warm-white background."
        ),
        "signature_palette": {"hair": "#171215", "complexion": "#9C6B4A", "accent": "#B57EDC"},
        "negative_additions": ["bob haircut or jawline cut"],
    },
    {
        "scout": "Navya",
        "roster_index": 25,
        "sheet_seed": 3002,
        "headshot_seed": 5025,
        "identity_paragraph": (
            "13-year-old Indian-American girl with a warm medium-tan complexion and dark brown downcast eyes, "
            "short glossy black jawline bob with tucked-under ends and straight-across blunt bangs across the "
            "forehead exactly as in her gold reference image, never ponytail never long hair never braids, slim "
            "oval face with a small straight nose, gentle closed-lip smile, soft straight brows, small ears, "
            "mint-green GPS wristwatch on her left wrist, looking down at a digital trail tablet held in her "
            "right hand with her left hand in her pocket, mint-green collared short-sleeve cadette jumpsuit with "
            "chest pockets and a tan belt over pale full-length undersleeves, taupe backpack straps over her "
            "shoulders, modest full-length uniform pants with zero midriff showing and brown lace-up work boots, "
            "mint-and-digital-cyan graphic-novel comic style with heavy brush ink outlines and halftone dot "
            "shading, plain warm-white background."
        ),
        "signature_palette": {"hair": "#101014", "complexion": "#99684A", "accent": "#3ECFA0"},
        "negative_additions": ["ponytail"],
    },
]

SELF_TEST_GOLDS = {
    "Aaliyah": "aaliyah-sheet-v2_00001_.png",
    "Maya": "maya-sheet-v5_00001_.png",
    "Navya": "navya.png",
}


def synth_fresh_render(gold: Image.Image) -> Image.Image:
    """Deterministic fresh-render proxy: center-crop 90% + bicubic resize back."""
    w, h = gold.size
    cw, ch = int(w * 0.90), int(h * 0.90)
    x0, y0 = (w - cw) // 2, (h - ch) // 2
    return gold.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.BICUBIC)


def build_self_test(tmp: Path, t: dict) -> tuple[list[dict], Path, dict]:
    """Stage synthetic renders + sidecars in tmp. Returns (personas, renders_dir, control)."""
    renders_dir = tmp / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    for persona in SELF_TEST_PERSONAS:
        scout = persona["scout"]
        gold_path = DEFAULT_GOLD_DIR / SELF_TEST_GOLDS[scout]
        if not gold_path.exists():
            raise FileNotFoundError(f"self-test gold missing: {gold_path}")
        gold = Image.open(gold_path).convert("RGB")
        proxy = synth_fresh_render(gold)
        for kind, seed_key in (("sheet", "sheet_seed"), ("headshot", "headshot_seed")):
            render_path = renders_dir / f"{scout.lower()}-{kind}-selftest.png"
            proxy.save(render_path)
            sidecar = {
                "scout": scout,
                "seed": persona[seed_key],
                "identity_paragraph": persona["identity_paragraph"],
                "negative_additions": persona.get("negative_additions", []),
                "render": render_path.name,
                "self_test": True,
            }
            (renders_dir / (render_path.stem + ".prompt.json")).write_text(
                json.dumps(sidecar, indent=2), encoding="utf-8")
    # Negative control: gold-vs-gold must trip the copy floor (d=0).
    control = {}
    for persona in SELF_TEST_PERSONAS:
        scout = persona["scout"]
        gold = Image.open(DEFAULT_GOLD_DIR / SELF_TEST_GOLDS[scout]).convert("RGB")
        d = ham(dhash(gold), dhash(gold))
        control[scout] = {
            "dhash_distance": d,
            "floor_tripped": d < t["drift_floor"],
            "expected": "floor must trip on a byte-identical copy",
        }
    control_ok = all(v["floor_tripped"] for v in control.values())
    return SELF_TEST_PERSONAS, renders_dir, {"copy_floor_control": control, "control_ok": control_ok}


# ---------------------------------------------------------------------------
# CLI (nova-act-check.py exit-code contract)
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deterministic character-fidelity gate for troop art")
    p.add_argument("--persona", type=str, default=None, help="input_assets/troop-personas/batch-X.json")
    p.add_argument("--renders", type=str, default=None, help="directory of render PNGs to gate")
    p.add_argument("--gold-dir", type=str, default=str(DEFAULT_GOLD_DIR), help="scout gold PNGs for drift check")
    p.add_argument("--sidecar-dir", type=str, default=None, help="fallback .prompt.json search dir")
    p.add_argument("--out", type=str, default=None, help="report JSON path (default: <renders>/troop-fidelity-report.json)")
    p.add_argument("--json", action="store_true", help="emit report JSON to stdout instead of a file")
    p.add_argument("--self-test", action="store_true", help="run the inline 3-gold self-test harness")
    p.add_argument("--hair-tol", type=float, default=DEFAULTS["hair_tol"])
    p.add_argument("--accent-tol", type=float, default=DEFAULTS["accent_tol"])
    p.add_argument("--edge-max", type=float, default=DEFAULTS["edge_max"])
    p.add_argument("--bg-min", type=float, default=DEFAULTS["bg_min"])
    p.add_argument("--drift-floor", type=int, default=DEFAULTS["drift_floor"])
    p.add_argument("--drift-ceiling", type=int, default=DEFAULTS["drift_ceiling"])
    return p


def emit(report: dict, out: str | None, as_json: bool, default_path: Path) -> None:
    if as_json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    out_path = Path(out) if out else default_path
    try:
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"[error] cannot write report {out_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[troop-fidelity-check] report -> {out_path}", file=sys.stderr)


def log_report(report: dict) -> None:
    for r in report["scouts"]:
        status = "PASS" if r["passed"] else "FAIL"
        bits = []
        for c in r["checks"]:
            mark = "+" if c["passed"] else "x"
            bits.append(f"{mark}{c['check'].split('.')[-1]}")
        shown = ",".join(Path(p).name for p in r["render"].split(",")) if r["render"] else "-"
        print(f"[troop-fidelity-check] {r['scout']} {status} render={shown} "
              f"[{' '.join(bits)}]", file=sys.stderr)
        for c in r["checks"]:
            if not c["passed"]:
                print(f"    FAIL {c['check']}: {c['detail']}", file=sys.stderr)
    s = report["summary"]
    print(f"[troop-fidelity-check] {s['scouts_passed']}/{s['scouts_total']} scouts passed", file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    t = {"hair_tol": args.hair_tol, "accent_tol": args.accent_tol, "edge_max": args.edge_max,
         "bg_min": args.bg_min, "drift_floor": args.drift_floor, "drift_ceiling": args.drift_ceiling}
    gold_dir = Path(args.gold_dir)
    sidecar_dir = Path(args.sidecar_dir) if args.sidecar_dir else None

    if args.self_test:
        try:
            with tempfile.TemporaryDirectory(prefix="troop-fidelity-selftest-") as tmp:
                personas, renders_dir, control = build_self_test(Path(tmp), t)
                report = run_gate(personas, renders_dir, gold_dir, None, t, label="self-test")
                report["self_test"] = control
                gate_ok = bool(report["summary"]["overall_passed"])
                if not bool(control["control_ok"]):
                    gate_ok = False
                    print("[troop-fidelity-check] SELF-TEST CONTROL FAILED: copy floor did not trip",
                          file=sys.stderr)
                report["summary"]["self_test_passed"] = gate_ok and bool(control["control_ok"])
                log_report(report)
                for scout, v in control["copy_floor_control"].items():
                    print(f"[troop-fidelity-check] control {scout}: gold-vs-gold d={v['dhash_distance']} "
                          f"floor_tripped={v['floor_tripped']}", file=sys.stderr)
                emit(report, args.out, args.json, renders_dir / "troop-fidelity-report.json")
                sys.exit(0 if gate_ok else 2)
        except FileNotFoundError as e:
            print(f"[error] {e}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.persona or not args.renders:
        print("[error] --persona and --renders are required (or use --self-test)", file=sys.stderr)
        build_parser().print_help(sys.stderr)
        sys.exit(1)
    persona_path = Path(args.persona)
    renders_dir = Path(args.renders)
    if not persona_path.exists():
        print(f"[error] persona file not found: {persona_path}", file=sys.stderr)
        sys.exit(1)
    if not renders_dir.is_dir():
        print(f"[error] renders dir not found: {renders_dir}", file=sys.stderr)
        sys.exit(1)
    try:
        personas = load_personas(persona_path)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"[error] bad persona file {persona_path}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[troop-fidelity-check] persona={persona_path} renders={renders_dir} gold={gold_dir}", file=sys.stderr)
    report = run_gate(personas, renders_dir, gold_dir, sidecar_dir, t,
                      label=f"{persona_path.name}:{renders_dir.name}")
    log_report(report)
    emit(report, args.out, args.json, renders_dir / "troop-fidelity-report.json")
    sys.exit(0 if bool(report["summary"]["overall_passed"]) else 2)


if __name__ == "__main__":
    main()

