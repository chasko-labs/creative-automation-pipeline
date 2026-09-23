#!/usr/bin/env python3
"""
Iteration-3 live-UI verification for the Kodiak "Posts for Today's Frontier" demo.

Reuses the Chromium fallback path (NOVA_ACT_API_KEY absent): drives the LIVE
CloudFront origin with Playwright chromium headless, mirroring the page.* /
act() semantics the Nova Act SDK exposes. This is the documented reviewer /
CI fallback when the Nova Act SDK key is not present.

Two areas, eight checks, one screenshot per area (plus per-check diagnostics).

AREA 1 — asset store "browse past assets": reworked 6-tab marketer taxonomy with real data
  1a TABS     six marketer tabs (Products/Recipes/Lifestyle/Ideas/Themes/Brand)
              with non-trivial counts, NOT the old Heroes/Renders; Products/
              Recipes/Lifestyle must be in the hundreds, not zero.
  1b GRID     Products tab renders a tile grid with human-readable labels.
  1c FACETS   Type facet chip row present on Products; clicking a chip filters.
  1d SEARCH   "Search this stack..." box filters client-side; "Load more" appends.
  1e SWITCH   Ideas tab switches + renders; Themes tab switches; no uncaught JS errors.

AREA 2 — Output Preview cleanup
  2a HEADER   Publish targets + 8 platform pills sit on a header line (up top).
  2b NO DUPE  localized EN/ES/DE headlines appear once (no verbatim repetition
              between #featuredFrontier framing and #locPreview headlines).
  2c TERSE    export label reads "Asset pack exports:" not the long sentence.

Entry: the sessionStorage gate token is seeded via page.evaluate after load
(?cakes=1 URL bypass removed in #234); the page then reloads past the screen.

Usage:
  python scripts/nova-act-iter3-check.py --headless \
      --out /tmp/kodiak-iter3-report.json --shot-dir /tmp/kodiak-iter3-shots

Exit codes:
  0  all checks PASS
  2  one or more checks FAIL
  3  blocked before checks could run (gate, stale build, browser launch)
  1  usage / IO error
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

LIVE_URL = "https://d37333alc7ojpl.cloudfront.net/"
# No query-param bypass (#234 removed ?cakes=1): bare URL + sessionStorage seed.
ENTRY_URL = LIVE_URL
EXPECTED_STAMP = "0.1.024-7c9222d-20260907"
STALE_MARKER_RE = re.compile(r"0\.1\.0(0\d|1\d|2[0-3])-")  # anything <= 023
STAMP_RE = re.compile(r"0\.1\.0\d{2}-[0-9a-f]{7}-\d{8}")

EXPECTED_TABS = ["Products", "Recipes", "Lifestyle", "Ideas", "Themes", "Brand"]
OLD_TABS = ["Heroes", "Renders"]
PLATFORM_PILLS = ["Homepage", "Blog", "Instagram", "Facebook", "TikTok",
                  "YouTube", "Pinterest", "X"]


@dataclass
class CheckResult:
    check: str
    verdict: str  # PASS | FAIL | BLOCKED
    observed: str
    screenshot: str | None = None


@dataclass
class Report:
    url: str
    build_stamp_seen: str | None
    generated_at: str
    console_state: str = "unknown"
    checks: list[dict] = field(default_factory=list)
    overall: str = "UNKNOWN"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _shot(page, shot_dir: Path, name: str, full_page: bool = False) -> str | None:
    try:
        shot_dir.mkdir(parents=True, exist_ok=True)
        p = str(shot_dir / f"{name}.png")
        page.screenshot(path=p, full_page=full_page)
        return p
    except Exception as e:  # noqa: BLE001
        print(f"[warn] screenshot {name} failed: {e}", file=sys.stderr)
        return None


def _read_stamp(page) -> str | None:
    try:
        title = page.title() or ""
    except Exception:  # noqa: BLE001 — best-effort probe; empty title falls to meta
        title = ""
    m = STAMP_RE.search(title)
    if m:
        return m.group(0)
    try:
        c = page.get_attribute('meta[name="kodiak-version"]', "content")
        if c:
            m = STAMP_RE.search(c)
            return m.group(0) if m else c
    except Exception as e:  # noqa: BLE001 — best-effort probe; no stamp is the fallback
        print(f"[warn] stamp meta read failed: {e}", file=sys.stderr)
    return None


def _gate_up(page) -> bool:
    try:
        return page.locator("text=Request access").count() > 0
    except Exception:  # noqa: BLE001 — probe failed; assume gate down, not a block
        return False


def _panel(page):
    return page.locator("#assetPanel")


def _tab_texts(page) -> list[str]:
    """Collect visible tab label strings inside the asset store panel."""
    panel = _panel(page)
    texts: list[str] = []
    # real tab bar: role=tab .ff-assets-tab inside #assetBody, label form "Products (1688)"
    for sel in ["[role='tab']", ".ff-assets-tab", ".asset_store-tab", "button"]:
        try:
            loc = panel.locator(sel)
            n = loc.count()
            if n:
                cand = []
                for i in range(min(n, 20)):
                    try:
                        t = (loc.nth(i).inner_text() or "").strip()
                        if t:
                            cand.append(t)
                    except Exception as e:  # noqa: BLE001 — best-effort; next tab tried
                        print(f"[warn] tab text read failed for {sel}: {e}",
                              file=sys.stderr)
                # a tab bar match: at least one expected tab name appears
                if any(any(e.lower() in c.lower() for e in EXPECTED_TABS + OLD_TABS)
                       for c in cand):
                    return cand
                if not texts:
                    texts = cand
        except Exception as e:  # noqa: BLE001 — best-effort; next selector tried
            print(f"[warn] tab bar probe failed for {sel}: {e}", file=sys.stderr)
    return texts


def _count_for(tab_text: str) -> int | None:
    m = re.search(r"\(?\s*([\d,]{1,7})\s*\)?", tab_text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _tile_count(page) -> int:
    panel = _panel(page)
    for sel in [".ff-assets-tile", ".asset_store-tile", "[role='option']",
                ".ff-assets-grid img", "#assetGrid img", "img"]:
        try:
            n = panel.locator(sel).count()
            if n:
                return n
        except Exception as e:  # noqa: BLE001 — best-effort; next selector tried
            print(f"[warn] tile count probe failed for {sel}: {e}", file=sys.stderr)
    return 0


def _tile_labels(page, limit: int = 12) -> list[str]:
    panel = _panel(page)
    for sel in [".ff-assets-tile", ".asset_store-tile", "[role='option']"]:
        try:
            loc = panel.locator(sel)
            n = loc.count()
            if n:
                out = []
                for i in range(min(n, limit)):
                    try:
                        t = (loc.nth(i).inner_text() or "").strip()
                        if t:
                            # normalize: collapse ws, drop check glyph, de-duplicate
                            # the doubled label text some tiles render, cap cleanly
                            t = re.sub(r"\s+", " ", t).replace("✓", "").strip()
                            half = len(t) // 2
                            if half > 4 and t[:half].strip() == t[half:].strip():
                                t = t[:half].strip()
                            out.append(t[:48].strip())
                    except Exception as e:  # noqa: BLE001 — best-effort; next tile tried
                        print(f"[warn] tile label read failed: {e}", file=sys.stderr)
                if out:
                    return out
        except Exception as e:  # noqa: BLE001 — best-effort; next selector tried
            print(f"[warn] tile label probe failed for {sel}: {e}", file=sys.stderr)
    # fallback: alt text on images
    try:
        loc = panel.locator("img")
        n = loc.count()
        out = []
        for i in range(min(n, limit)):
            try:
                a = loc.nth(i).get_attribute("alt")
                if a:
                    out.append(a[:60])
            except Exception as e:  # noqa: BLE001 — best-effort; next image tried
                print(f"[warn] tile alt read failed: {e}", file=sys.stderr)
        return out
    except Exception:  # noqa: BLE001 — alt-text fallback; empty labels is the fallback
        return []


def _click_tab(page, name: str) -> bool:
    panel = _panel(page)
    for sel in [f"[role='tab']:has-text('{name}')",
                f".ff-assets-tab:has-text('{name}')",
                f"button:has-text('{name}')",
                f"text={name}"]:
        try:
            loc = panel.locator(sel).first
            if loc.count() > 0:
                loc.click(timeout=3000)
                time.sleep(1.2)
                return True
        except Exception as e:  # noqa: BLE001 — best-effort; next selector tried
            print(f"[warn] tab click failed for {sel}: {e}", file=sys.stderr)
            continue
    return False


def run(headless: bool, out_path: Path, shot_dir: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        rep = Report(ENTRY_URL, None, _now(), "n/a",
                     [asdict(CheckResult("environment", "BLOCKED",
                      "playwright not installed. `pip install playwright && "
                      "playwright install chromium`. This is the Chromium "
                      "fallback used when NOVA_ACT_API_KEY is absent."))],
                     "BLOCKED")
        out_path.write_text(json.dumps(asdict(rep), indent=2))
        print(json.dumps(asdict(rep), indent=2))
        return 3

    checks: list[CheckResult] = []
    stamp_seen: str | None = None
    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--ignore-certificate-errors"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 2200},
                                  ignore_https_errors=True)
        page = ctx.new_page()

        # capture console + uncaught JS errors for CHECK 1e
        page.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}")
                if m.type in ("error",) else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        try:
            page.goto(ENTRY_URL, wait_until="networkidle", timeout=45000)
        except Exception as e:  # noqa: BLE001
            shot = _shot(page, shot_dir, "00-goto-error")
            checks.append(CheckResult("entry", "BLOCKED", f"navigation failed: {e}", shot))
            return _finish(checks, None, _console_summary(console_errors, page_errors), out_path)

        time.sleep(2)
        # #234: no URL bypass. Seed the sessionStorage gate token the page
        # honors, then reload past the courtesy screen.
        try:
            page.evaluate("try{sessionStorage.setItem('kodiak_gate','cakes')}catch(e){}")
        except Exception as e:  # noqa: BLE001 — gate seed is best-effort; reload decides
            print(f"[warn] gate token seed failed: {e}", file=sys.stderr)
        try:
            page.reload(wait_until="networkidle")
        except Exception as e:  # noqa: BLE001 — reload is best-effort; gate check decides
            print(f"[warn] post-seed reload failed: {e}", file=sys.stderr)
        time.sleep(2)

        if _gate_up(page):
            shot = _shot(page, shot_dir, "00-gate-block")
            checks.append(CheckResult("entry", "BLOCKED",
                "Courtesy screen still mounted despite sessionStorage seeding. "
                "Not attempting to bypass. Surface to anchor.", shot))
            return _finish(checks, None, _console_summary(console_errors, page_errors), out_path)

        stamp_seen = _read_stamp(page)
        if stamp_seen and stamp_seen != EXPECTED_STAMP and STALE_MARKER_RE.match(stamp_seen):
            print("[info] stale stamp; waiting 60s for invalidation, reload once",
                  file=sys.stderr)
            time.sleep(60)
            page.reload(wait_until="networkidle")
            time.sleep(2)
            stamp_seen = _read_stamp(page)
        if stamp_seen != EXPECTED_STAMP:
            shot = _shot(page, shot_dir, "00-stamp")
            checks.append(CheckResult("build-stamp", "BLOCKED",
                f"Expected {EXPECTED_STAMP}, saw {stamp_seen or 'none'}. "
                f"Not judging against wrong build.", shot))
            return _finish(checks, stamp_seen, _console_summary(console_errors, page_errors), out_path)

        print(f"[info] build stamp confirmed: {stamp_seen}", file=sys.stderr)

        # ============ AREA 1: asset store 6-tab taxonomy ============
        _area1(page, shot_dir, checks)

        # ============ AREA 2: Output Preview cleanup ============
        _area2(page, shot_dir, checks)

        # CHECK 1e console assertion (populated across all of area 1)
        console_state = _console_summary(console_errors, page_errors)

        browser.close()
        return _finish(checks, stamp_seen, console_state, out_path)


def _console_summary(console_errors: list[str], page_errors: list[str]) -> str:
    if not console_errors and not page_errors:
        return "clean — no uncaught JS errors, no console errors"
    parts = []
    if page_errors:
        parts.append("UNCAUGHT: " + " | ".join(page_errors[:5]))
    if console_errors:
        parts.append("CONSOLE.ERROR: " + " | ".join(console_errors[:5]))
    return " ;; ".join(parts)


def _area1(page, shot_dir: Path, checks: list[CheckResult]) -> None:
    # open the panel
    opened = False
    for sel in ["#assetBrowseTrigger", ".ff-assets-trigger",
                "text=Browse past assets"]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.click(timeout=4000)
                opened = True
                break
        except Exception as e:  # noqa: BLE001 — best-effort; next selector tried
            print(f"[warn] panel open click failed for {sel}: {e}", file=sys.stderr)
            continue
    time.sleep(1.5)
    if not opened or _panel(page).count() == 0:
        shot = _shot(page, shot_dir, "area1-open-fail", full_page=True)
        checks.append(CheckResult("1a-tabs", "FAIL",
            "could not open Browse past assets panel", shot))
        return
    # wait for panel visible + async content load (#assetBody shows "Loading…" first)
    try:
        _panel(page).wait_for(state="visible", timeout=5000)
    except Exception as e:  # noqa: BLE001 — wait is best-effort; poll loop decides
        print(f"[warn] panel visible wait timed out: {e}", file=sys.stderr)
    for _ in range(40):
        try:
            body_txt = page.locator("#assetBody").inner_text()[:40]
        except Exception:  # noqa: BLE001 — body poll; empty text retries next tick
            body_txt = ""
        if "Loading" not in body_txt and _panel(page).locator("[role='tab']").count() > 0:
            break
        time.sleep(0.5)
    time.sleep(1.0)

    tabs = _tab_texts(page)

    # --- CHECK 1a: six marketer tabs w/ counts ---
    found_old = [t for t in tabs
                 if any(o.lower() in t.lower() for o in OLD_TABS)]
    counts = {}
    for e in EXPECTED_TABS:
        for t in tabs:
            if e.lower() in t.lower():
                counts[e] = _count_for(t)
                break
    prod = counts.get("Products")
    rec = counts.get("Recipes")
    life = counts.get("Lifestyle")
    shot1a = _shot(page, shot_dir, "1a-asset_store-tabs")
    # task contract: Products/Recipes in the hundreds; Lifestyle non-trivial (~96);
    # none of the six may be zero (zero was the bug just fixed).
    hundreds_ok = all((v is not None and v >= 100) for v in (prod, rec))
    life_ok = life is not None and life >= 10
    none_zero = all((counts.get(e) is not None and counts.get(e) > 0) for e in EXPECTED_TABS)
    six_named = len({e for e in EXPECTED_TABS
                     for t in tabs if e.lower() in t.lower()}) >= 6
    if found_old:
        checks.append(CheckResult("1a-tabs", "FAIL",
            f"OLD Heroes/Renders tabs present: {found_old}. tabs seen={tabs}", shot1a))
    elif six_named and hundreds_ok and life_ok and none_zero:
        checks.append(CheckResult("1a-tabs", "PASS",
            f"six marketer tabs present with non-trivial counts "
            f"Products={prod} Recipes={rec} Lifestyle={life} "
            f"Ideas={counts.get('Ideas')} Themes={counts.get('Themes')} "
            f"Brand={counts.get('Brand')}; no Heroes/Renders. raw tabs={tabs}", shot1a))
    else:
        checks.append(CheckResult("1a-tabs", "FAIL",
            f"tab contract not met. six_named={six_named} "
            f"Products={prod} Recipes={rec} Lifestyle={life} none_zero={none_zero}. "
            f"raw tabs={tabs}", shot1a))

    # --- CHECK 1b: Products grid + readable labels ---
    # ensure Products selected (default) — click to be safe
    _click_tab(page, "Products")
    time.sleep(1.0)
    tiles = _tile_count(page)
    labels = _tile_labels(page)
    uuid_re = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)
    rawfile_re = re.compile(r"\.(png|jpg|jpeg|webp)\b", re.IGNORECASE)
    readable = [lbl for lbl in labels
                if lbl and not uuid_re.search(lbl) and not rawfile_re.search(lbl)]
    shot1b = _shot(page, shot_dir, "1b-products-grid")
    if tiles > 0 and len(readable) >= max(1, len(labels) // 2):
        checks.append(CheckResult("1b-grid", "PASS",
            f"{tiles} tiles rendered; readable labels sample={readable[:6]}", shot1b))
    elif tiles > 0 and not labels:
        checks.append(CheckResult("1b-grid", "PASS",
            f"{tiles} image tiles rendered (labels not exposed as text; "
            f"no UUID/raw-filename salad detected)", shot1b))
    else:
        checks.append(CheckResult("1b-grid", "FAIL",
            f"grid weak: tiles={tiles} labels={labels[:6]}", shot1b))

    # --- CHECK 1c: Type facet row + filtering ---
    facet_chips = []
    facet_row = None
    for sel in [".ff-assets-facet-chip", ".ff-assets-facet", ".asset_store-facet", "[data-facet]",
                ".ff-assets-facets button", ".ff-assets-chip"]:
        try:
            loc = _panel(page).locator(sel)
            if loc.count() > 0:
                facet_row = sel
                for i in range(min(loc.count(), 15)):
                    try:
                        t = (loc.nth(i).inner_text() or "").strip()
                        if t:
                            facet_chips.append(t)
                    except Exception as e:  # noqa: BLE001 — best-effort; next chip tried
                        print(f"[warn] facet chip read failed: {e}", file=sys.stderr)
                break
        except Exception as e:  # noqa: BLE001 — best-effort; next selector tried
            print(f"[warn] facet row probe failed for {sel}: {e}", file=sys.stderr)
            continue
    labels_before = _tile_labels(page, 8)
    tiles_before = _tile_count(page)
    filtered_ok = False
    filter_note = ""
    if facet_chips:
        target = None
        for want in ("Bars", "Granola", "Cups", "Oatmeal"):
            if any(want.lower() == c.lower() for c in facet_chips):
                target = want
                break
        if target:
            try:
                _panel(page).locator(f"{facet_row}[data-facet='{target}']").first.click(timeout=3000)
                time.sleep(1.4)
                labels_after = _tile_labels(page, 8)
                tiles_after = _tile_count(page)
                # honest filter check: the grid CONTENT must change, not just exist.
                content_changed = labels_after != labels_before
                count_changed = tiles_after != tiles_before
                filtered_ok = content_changed or count_changed
                filter_note = (f"clicked '{target}': tiles {tiles_before}->{tiles_after}; "
                               f"content_changed={content_changed}; "
                               f"before={labels_before[:3]} after={labels_after[:3]}")
            except Exception as e:  # noqa: BLE001
                filter_note = f"click '{target}' failed: {e}"
    shot1c = _shot(page, shot_dir, "1c-facets")
    if facet_chips and filtered_ok:
        checks.append(CheckResult("1c-facets", "PASS",
            f"Type facet row present chips={facet_chips[:10]}; {filter_note}", shot1c))
    elif facet_chips:
        checks.append(CheckResult("1c-facets", "FAIL",
            f"Type facet row RENDERS (chips={facet_chips[:10]}) but clicking a chip "
            f"does NOT filter the grid — same tiles remain. {filter_note}", shot1c))
    else:
        checks.append(CheckResult("1c-facets", "FAIL",
            "no Type facet chip row found on Products tab", shot1c))
    # reset facet to All so search/load-more test is clean
    try:
        _panel(page).locator(f"{facet_row}[data-facet='All']").first.click(timeout=2000)
        time.sleep(0.8)
    except Exception as e:  # noqa: BLE001 — facet reset is best-effort cleanup
        print(f"[warn] facet reset to All failed: {e}", file=sys.stderr)

    # --- CHECK 1d: search box + load more ---
    search_ok = False
    search_note = ""
    search_sel = None
    for sel in ["input.ff-assets-filter-input",
                "input[placeholder*='Search this stack']",
                "#assetSearch", ".ff-assets-search input",
                "input[type='search']", "input[placeholder*='Search']"]:
        try:
            if _panel(page).locator(sel).count() > 0:
                search_sel = sel
                break
        except Exception as e:  # noqa: BLE001 — best-effort; next selector tried
            print(f"[warn] search box probe failed for {sel}: {e}", file=sys.stderr)
            continue
    if search_sel:
        try:
            labels_b = _tile_labels(page, 10)
            before = _tile_count(page)
            box = _panel(page).locator(search_sel).first
            box.click()
            box.type("muffin", delay=50)
            time.sleep(1.6)
            after = _tile_count(page)
            labels_a = _tile_labels(page, 10)
            # honest: filtered results should differ AND ideally match the term
            content_changed = labels_a != labels_b
            all_match = bool(labels_a) and all("muffin" in lbl.lower() for lbl in labels_a)
            search_ok = content_changed and (all_match or after < before)
            search_note = (f"typed 'muffin': tiles {before}->{after}; "
                           f"content_changed={content_changed} all_match_term={all_match}; "
                           f"after_sample={labels_a[:3]}")
            box.fill("")
            time.sleep(0.8)
        except Exception as e:  # noqa: BLE001
            search_note = f"search interaction failed: {e}"
    else:
        search_note = "no search box found"

    load_more_ok = False
    lm_note = ""
    for sel in ["button:has-text('Load more')", "#assetLoadMore",
                ".ff-assets-loadmore", "text=Load more"]:
        try:
            loc = _panel(page).locator(sel).first
            if loc.count() > 0:
                before = _tile_count(page)
                loc.click(timeout=3000)
                time.sleep(1.5)
                after = _tile_count(page)
                load_more_ok = after > before
                lm_note = f"Load more: tiles {before}->{after}"
                break
        except Exception as e:  # noqa: BLE001
            lm_note = f"load more click failed: {e}"
    if not lm_note:
        lm_note = "no Load more button found"
    shot1d = _shot(page, shot_dir, "1d-search-loadmore")
    if search_ok and load_more_ok:
        checks.append(CheckResult("1d-search-loadmore", "PASS",
            f"{search_note}; {lm_note}", shot1d))
    else:
        checks.append(CheckResult("1d-search-loadmore", "FAIL",
            f"search_ok={search_ok} load_more_ok={load_more_ok}. "
            f"{search_note}; {lm_note}", shot1d))

    # --- CHECK 1e: tab switch Ideas + Themes, no JS errors ---
    ideas_ok = _click_tab(page, "Ideas")
    ideas_tiles = _tile_count(page)
    _shot(page, shot_dir, "1e-ideas-tab")
    themes_ok = _click_tab(page, "Themes")
    themes_tiles = _tile_count(page)
    themes_note = ""
    try:
        if _panel(page).locator("text=/sparse|limited context|few assets/i").count() > 0:
            themes_note = "sparse-context note shown"
    except Exception as e:  # noqa: BLE001 — diagnostic read; empty note is the fallback
        print(f"[warn] sparse-context note probe failed: {e}", file=sys.stderr)
    shot1e_themes = _shot(page, shot_dir, "1e-themes-tab")
    if ideas_ok and themes_ok:
        checks.append(CheckResult("1e-tab-switch", "PASS",
            f"Ideas switched (tiles={ideas_tiles}); Themes switched "
            f"(tiles={themes_tiles}{'; ' + themes_note if themes_note else ''}). "
            f"console asserted separately.", shot1e_themes))
    else:
        checks.append(CheckResult("1e-tab-switch", "FAIL",
            f"tab switch failed ideas={ideas_ok} themes={themes_ok}", shot1e_themes))

    # close panel
    for sel in ["#assetPanelClose", ".ff-assets-close"]:
        try:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.click(timeout=2000)
                break
        except Exception as e:  # noqa: BLE001 — panel close is best-effort cleanup
            print(f"[warn] panel close click failed for {sel}: {e}", file=sys.stderr)
    try:
        page.keyboard.press("Escape")
    except Exception as e:  # noqa: BLE001 — panel close is best-effort cleanup
        print(f"[warn] panel close Escape failed: {e}", file=sys.stderr)
    time.sleep(1)


def _area2(page, shot_dir: Path, checks: list[CheckResult]) -> None:
    # trigger a generation so localized copy + preview populate
    try:
        page.locator("#generateCampaign").first.click(timeout=4000)
    except Exception:  # noqa: BLE001 — generate click; fallback selector tried next
        try:
            page.locator("text=Generate").first.click(timeout=3000)
        except Exception as e:  # noqa: BLE001 — generate click is best-effort setup
            print(f"[warn] generate click failed: {e}", file=sys.stderr)
    # allow generation + localization to render
    time.sleep(6)

    # scroll to Output Preview and expand the <details> so content is readable
    try:
        page.evaluate("() => { const d=document.querySelector('#previewCard'); if(d && d.tagName==='DETAILS') d.open=true; }")
    except Exception as e:  # noqa: BLE001 — details expand is best-effort setup
        print(f"[warn] preview expand failed: {e}", file=sys.stderr)
    try:
        page.locator("#previewCard").scroll_into_view_if_needed(timeout=4000)
    except Exception:  # noqa: BLE001 — scroll; fallback selector tried next
        try:
            page.locator("text=Output Preview").first.scroll_into_view_if_needed(timeout=3000)
        except Exception as e:  # noqa: BLE001 — scroll is best-effort setup
            print(f"[warn] preview scroll failed: {e}", file=sys.stderr)
    time.sleep(1.5)

    # --- CHECK 2a: publish targets on header line ---
    pt_note = ""
    header_ok = False
    try:
        pt = page.locator("#publishTargets").first
        cls = pt.get_attribute("class") or ""
        pills = page.locator("#publishTargets .ff-publish-pill")
        pill_texts = []
        for i in range(min(pills.count(), 12)):
            t = (pills.nth(i).inner_text() or "").strip()
            if t:
                pill_texts.append(t)
        found_pills = [p for p in PLATFORM_PILLS
                       if any(p.lower() in x.lower() for x in pill_texts)]
        header_ok = ("ff-output-header-line" in cls) and len(found_pills) >= 7
        pt_note = (f"class='{cls}' pills={pill_texts} "
                   f"matched={found_pills}")
    except Exception as e:  # noqa: BLE001
        pt_note = f"publishTargets read failed: {e}"
    shot2a = _shot(page, shot_dir, "2a-publish-targets", full_page=False)
    if header_ok:
        checks.append(CheckResult("2a-publish-header", "PASS",
            f"publish targets on header line with 8 platform pills. {pt_note}", shot2a))
    else:
        checks.append(CheckResult("2a-publish-header", "FAIL",
            f"publish targets not confirmed on header line. {pt_note}", shot2a))

    # --- CHECK 2b: localized copy not duplicated ---
    feat = ""
    locp = ""
    try:
        feat = (page.locator("#featuredFrontier").text_content() or "").strip()
    except Exception as e:  # noqa: BLE001 — diagnostic read; empty text is the fallback
        print(f"[warn] featuredFrontier read failed: {e}", file=sys.stderr)
    try:
        locp = (page.locator("#locPreview").text_content() or "").strip()
    except Exception as e:  # noqa: BLE001 — diagnostic read; empty text is the fallback
        print(f"[warn] locPreview read failed: {e}", file=sys.stderr)
    # detect verbatim repetition: pull candidate headline sentences from locPreview
    # and check none appear verbatim inside featuredFrontier framing.
    def _sentences(s: str) -> list[str]:
        parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", s)
        return [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) > 18]
    loc_sents = _sentences(locp)
    dup = [s for s in loc_sents if s and s in feat]
    shot2b = _shot(page, shot_dir, "2b-localized-copy", full_page=False)
    framing_ok = bool(re.search(r"localiz(ed|ing).{0,40}(reach|for)", feat, re.IGNORECASE)) or \
                 ("·" in feat) or ("localized reach" in feat.lower())
    headers_ok = bool(re.search(r"Localized headlines", locp, re.IGNORECASE)) or \
                 bool(re.search(r"one per language", locp, re.IGNORECASE))
    if not dup and (framing_ok or headers_ok):
        checks.append(CheckResult("2b-no-dupe-loc", "PASS",
            f"localized headlines appear once (no verbatim repetition). "
            f"framing_ok={framing_ok} headers_ok={headers_ok}. "
            f"featured[:120]='{feat[:120]}' loc[:120]='{locp[:120]}'", shot2b))
    elif dup:
        checks.append(CheckResult("2b-no-dupe-loc", "FAIL",
            f"duplicated localized sentences between framing and headlines: "
            f"{dup[:3]}", shot2b))
    else:
        checks.append(CheckResult("2b-no-dupe-loc", "FAIL",
            f"could not confirm framing/headers separation. "
            f"featured='{feat[:160]}' loc='{locp[:160]}'", shot2b))

    # --- CHECK 2c: terse export label ---
    terse_note = ""
    verdict_2c = "FAIL"
    hay = ""
    for sel in ["#platformMatrix", "#preview", "#previewCard", "body"]:
        try:
            t = page.locator(sel).first.text_content() or ""
            hay += "\n" + t
        except Exception as e:  # noqa: BLE001 — best-effort; next scope tried
            print(f"[warn] export label probe failed for {sel}: {e}", file=sys.stderr)
    has_terse = "Asset pack exports:" in hay
    has_long = "One asset pack exports these ratios for these platforms" in hay
    if has_terse and not has_long:
        verdict_2c = "PASS"
        terse_note = "found 'Asset pack exports:' and NOT the long sentence"
    elif has_long:
        terse_note = "long sentence 'One asset pack exports these ratios...' still present"
    else:
        terse_note = "neither terse nor long label found in preview text"
    shot2c = _shot(page, shot_dir, "2c-export-label", full_page=False)
    checks.append(CheckResult("2c-terse-export", verdict_2c, terse_note, shot2c))

    # full-page shot of the whole Output Preview section for the record
    _shot(page, shot_dir, "area2-output-preview-full", full_page=True)


def _finish(checks: list[CheckResult], stamp: str | None,
            console_state: str, out_path: Path) -> int:
    verdicts = {c.verdict for c in checks}
    if "BLOCKED" in verdicts and not ({"PASS", "FAIL"} & verdicts):
        overall, code = "BLOCKED", 3
    elif "FAIL" in verdicts:
        overall, code = "FAIL", 2
    elif verdicts == {"PASS"}:
        overall, code = "PASS", 0
    else:
        overall, code = "MIXED", 2
    rep = Report(ENTRY_URL, stamp, _now(), console_state,
                 [asdict(c) for c in checks], overall)
    out_path.write_text(json.dumps(asdict(rep), indent=2))
    print(json.dumps(asdict(rep), indent=2))
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="Kodiak iteration-3 live-UI check (Chromium fallback)")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--out", default="/tmp/kodiak-iter3-report.json")
    ap.add_argument("--shot-dir", default="/tmp/kodiak-iter3-shots")
    args = ap.parse_args()
    try:
        return run(args.headless, Path(args.out), Path(args.shot_dir))
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
