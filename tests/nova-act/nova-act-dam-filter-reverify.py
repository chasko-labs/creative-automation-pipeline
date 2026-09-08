#!/usr/bin/env python3
"""
Focused re-verification of the two DAM filter checks that FAILED last run (1c, 1d).

Chromium fallback path (NOVA_ACT_API_KEY absent): drives the LIVE CloudFront
origin with Playwright chromium, mirroring the Nova Act page.* / act() semantics.

Root cause of the previous FAIL: content-visibility:auto on .ff-dam-grid paint-
contained the subtree so display toggles never reflowed; the counter also counted
HIDDEN nodes. Fix under test: filter toggles the `hidden` attribute +
.ff-dam-tile[hidden]{display:none!important}, content-visibility removed.

This run measures VISIBLE tiles only — a tile counts as visible iff it is NOT
[hidden] AND its computed display is not 'none' AND offsetParent is not null.

CHECK 1c — Type facet "Bars" filters the grid (visible set must shrink to bars).
CHECK 1d — search "muffin" filters (visible set shrinks; first visible is a muffin);
           Load more still appends.

Usage:
  .venv/bin/python scripts/nova-act-dam-filter-reverify.py --headless \
      --out /tmp/kodiak-dam-reverify.json --shot-dir /tmp/kodiak-dam-reverify-shots
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LIVE_URL = "https://d37333alc7ojpl.cloudfront.net/"
# No query-param bypass (#234 removed ?cakes=1): bare URL + sessionStorage seed.
ENTRY_URL = LIVE_URL
EXPECTED_STAMP = "0.1.025-aaf77f2-20260907"
STAMP_RE = re.compile(r"0\.1\.0\d{2}-[0-9a-f]{7}-\d{8}")
# anything strictly older than 025 => stale, reload once after 60s
STALE_RE = re.compile(r"0\.1\.0(0\d|1\d|2[0-4])-")

# JS that returns the visible-only tile info. A tile is visible iff:
#   not [hidden]  AND  getComputedStyle(display) !== 'none'  AND  offsetParent !== null
VISIBLE_JS = r"""
() => {
  const panel = document.querySelector('#damPanel') || document;
  const tiles = Array.from(panel.querySelectorAll('.ff-dam-tile'));
  const isVisible = (el) => {
    if (el.hasAttribute('hidden')) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (el.offsetParent === null && cs.position !== 'fixed') return false;
    return true;
  };
  const label = (el) => {
    let t = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').replace(/✓/g, '').trim();
    const half = Math.floor(t.length / 2);
    if (half > 4 && t.slice(0, half).trim() === t.slice(half).trim()) t = t.slice(0, half).trim();
    return t.slice(0, 60);
  };
  const vis = tiles.filter(isVisible);
  return {
    total: tiles.length,
    visible: vis.length,
    visibleLabels: vis.slice(0, 12).map(label),
  };
}
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _shot(page, shot_dir: Path, name: str, full_page: bool = False):
    try:
        shot_dir.mkdir(parents=True, exist_ok=True)
        p = str(shot_dir / f"{name}.png")
        page.screenshot(path=p, full_page=full_page)
        return p
    except Exception as e:  # noqa: BLE001
        print(f"[warn] screenshot {name} failed: {e}", file=sys.stderr)
        return None


def _read_stamp(page):
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    m = STAMP_RE.search(title)
    if m:
        return m.group(0)
    try:
        c = page.get_attribute('meta[name="kodiak-version"]', "content")
        if c:
            m = STAMP_RE.search(c)
            return m.group(0) if m else c
    except Exception:
        pass
    return None


def _panel(page):
    return page.locator("#damPanel")


def _vis(page) -> dict:
    """Visible-only tile snapshot via computed style + hidden attr + offsetParent."""
    try:
        return page.evaluate(VISIBLE_JS)
    except Exception as e:  # noqa: BLE001
        return {"total": -1, "visible": -1, "visibleLabels": [], "error": str(e)}


def _click_tab(page, name: str) -> bool:
    panel = _panel(page)
    for sel in [f"[role='tab']:has-text('{name}')",
                f".ff-dam-tab:has-text('{name}')",
                f"button:has-text('{name}')",
                f"text={name}"]:
        try:
            loc = panel.locator(sel).first
            if loc.count() > 0:
                loc.click(timeout=3000)
                time.sleep(1.0)
                return True
        except Exception:
            continue
    return False


def _find_facet_row(page):
    for sel in [".ff-dam-facet-chip", ".ff-dam-facet", ".dam-facet", "[data-facet]",
                ".ff-dam-facets button", ".ff-dam-chip"]:
        try:
            if _panel(page).locator(sel).count() > 0:
                return sel
        except Exception:
            continue
    return None


def _facet_texts(page, sel) -> list[str]:
    out = []
    try:
        loc = _panel(page).locator(sel)
        for i in range(min(loc.count(), 15)):
            t = (loc.nth(i).inner_text() or "").strip()
            if t:
                out.append(t)
    except Exception:
        pass
    return out


def _click_facet(page, sel, value) -> bool:
    for chip_sel in [f"{sel}[data-facet='{value}']",
                     f"{sel}:has-text('{value}')"]:
        try:
            loc = _panel(page).locator(chip_sel).first
            if loc.count() > 0:
                loc.click(timeout=3000)
                time.sleep(1.3)
                return True
        except Exception:
            continue
    return False


def run(headless: bool, out_path: Path, shot_dir: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        report = {
            "url": ENTRY_URL, "generated_at": _now(),
            "blocked": "playwright not installed (Chromium fallback path)",
        }
        out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 3

    console_errors: list[str] = []
    page_errors: list[str] = []
    report: dict = {
        "url": ENTRY_URL,
        "generated_at": _now(),
        "measurement": "visible-only (not [hidden] AND display!=none AND offsetParent!=null)",
        "build_stamp_seen": None,
        "check_1c": None,
        "check_1d": None,
        "load_more": None,
        "console_state": "unknown",
        "screenshot": None,
        "overall": "UNKNOWN",
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=["--ignore-certificate-errors"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 2200},
                                  ignore_https_errors=True)
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        # ---- navigate + stamp gate ----
        try:
            page.goto(ENTRY_URL, wait_until="networkidle", timeout=45000)
        except Exception as e:  # noqa: BLE001
            report["overall"] = "BLOCKED"
            report["blocked"] = f"navigation failed: {e}"
            report["screenshot"] = _shot(page, shot_dir, "00-goto-error")
            return _finish(report, out_path, browser, console_errors, page_errors)
        time.sleep(2)
        # #234: no URL bypass. Seed the sessionStorage gate token the page
        # honors, then reload past the courtesy screen.
        try:
            page.evaluate("try{sessionStorage.setItem('kodiak_gate','cakes')}catch(e){}")
        except Exception:
            pass
        try:
            page.reload(wait_until="networkidle")
        except Exception:
            pass
        time.sleep(2)

        if _panel(page) and page.locator("text=Request access").count() > 0:
            report["overall"] = "BLOCKED"
            report["blocked"] = "courtesy screen still mounted despite sessionStorage seeding"
            report["screenshot"] = _shot(page, shot_dir, "00-gate")
            return _finish(report, out_path, browser, console_errors, page_errors)

        stamp = _read_stamp(page)
        if stamp != EXPECTED_STAMP and stamp and STALE_RE.match(stamp):
            print(f"[info] stale stamp {stamp}; wait 60s + reload once", file=sys.stderr)
            time.sleep(60)
            page.reload(wait_until="networkidle")
            time.sleep(2)
            stamp = _read_stamp(page)
        report["build_stamp_seen"] = stamp
        if stamp != EXPECTED_STAMP:
            report["overall"] = "BLOCKED"
            report["blocked"] = (f"expected {EXPECTED_STAMP}, saw {stamp or 'none'} "
                                 f"after one reload — not judging wrong build")
            report["screenshot"] = _shot(page, shot_dir, "00-stamp")
            return _finish(report, out_path, browser, console_errors, page_errors)
        print(f"[info] build stamp confirmed: {stamp}", file=sys.stderr)

        # ---- open DAM panel, ensure Products tab ----
        opened = False
        for sel in ["#damBrowseTrigger", ".ff-dam-trigger", "text=Browse past assets"]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.click(timeout=4000)
                    opened = True
                    break
            except Exception:
                continue
        time.sleep(1.5)
        try:
            _panel(page).wait_for(state="visible", timeout=5000)
        except Exception:
            pass
        # wait out the async "Loading…" state
        for _ in range(40):
            try:
                body_txt = page.locator("#damBody").inner_text()[:40]
            except Exception:
                body_txt = ""
            if "Loading" not in body_txt and _panel(page).locator("[role='tab']").count() > 0:
                break
            time.sleep(0.5)
        time.sleep(0.8)
        if not opened or _panel(page).count() == 0:
            report["overall"] = "BLOCKED"
            report["blocked"] = "could not open Browse past assets panel"
            report["screenshot"] = _shot(page, shot_dir, "00-open-fail", full_page=True)
            return _finish(report, out_path, browser, console_errors, page_errors)
        _click_tab(page, "Products")
        time.sleep(0.8)

        facet_row = _find_facet_row(page)
        facet_chips = _facet_texts(page, facet_row) if facet_row else []

        # =================== CHECK 1c — Type facet "Bars" ===================
        before = _vis(page)
        c1c = {
            "facet_chips": facet_chips[:12],
            "visible_before": before["visible"],
            "total_nodes_before": before["total"],
            "first_labels_before": before["visibleLabels"][:5],
        }
        if not facet_row:
            c1c["verdict"] = "FAIL"
            c1c["note"] = "no Type facet chip row found on Products tab"
        else:
            clicked = _click_facet(page, facet_row, "Bars")
            after = _vis(page)
            c1c["clicked_bars"] = clicked
            c1c["visible_after"] = after["visible"]
            c1c["total_nodes_after"] = after["total"]
            c1c["first_labels_after"] = after["visibleLabels"][:5]
            first_after = (after["visibleLabels"][0].lower()
                           if after["visibleLabels"] else "")
            all_match = (bool(after["visibleLabels"]) and
                         all("bar" in lbl.lower() for lbl in after["visibleLabels"]))
            shrank = (after["visible"] >= 0 and before["visible"] >= 0 and
                      after["visible"] < before["visible"])
            first_is_bar = "bar" in first_after
            if clicked and shrank and first_is_bar and all_match:
                c1c["verdict"] = "PASS"
                c1c["note"] = (f"visible {before['visible']}->{after['visible']}; "
                               f"first visible now '{after['visibleLabels'][0]}'; "
                               f"all visible tiles match bars")
            elif clicked and shrank and first_is_bar:
                c1c["verdict"] = "PASS"
                c1c["note"] = (f"visible {before['visible']}->{after['visible']}; "
                               f"first visible '{after['visibleLabels'][0]}' matches bars "
                               f"(some non-bar visible: {after['visibleLabels'][:5]})")
            else:
                c1c["verdict"] = "FAIL"
                c1c["note"] = (f"visible {before['visible']}->{after['visible']} "
                               f"(clicked={clicked}, shrank={shrank}, "
                               f"first_is_bar={first_is_bar}); "
                               f"after_labels={after['visibleLabels'][:5]}")
            _shot(page, shot_dir, "1c-after-bars")
            # reset to All
            _click_facet(page, facet_row, "All")
            time.sleep(0.6)
        report["check_1c"] = c1c

        # =================== CHECK 1d — search "muffin" ===================
        # ensure All facet cleared already; snapshot before
        before_s = _vis(page)
        c1d = {
            "visible_before": before_s["visible"],
            "total_nodes_before": before_s["total"],
            "first_labels_before": before_s["visibleLabels"][:5],
        }
        search_sel = None
        for sel in ["input.ff-dam-filter-input",
                    "input[placeholder*='Search this stack']",
                    "#damSearch", ".ff-dam-search input",
                    "input[type='search']", "input[placeholder*='Search']"]:
            try:
                if _panel(page).locator(sel).count() > 0:
                    search_sel = sel
                    break
            except Exception:
                continue
        if not search_sel:
            c1d["verdict"] = "FAIL"
            c1d["note"] = "no search box found"
        else:
            box = _panel(page).locator(search_sel).first
            box.click()
            box.type("muffin", delay=60)
            time.sleep(1.6)
            after_s = _vis(page)
            c1d["visible_after"] = after_s["visible"]
            c1d["total_nodes_after"] = after_s["total"]
            c1d["first_labels_after"] = after_s["visibleLabels"][:5]
            first_after = (after_s["visibleLabels"][0].lower()
                           if after_s["visibleLabels"] else "")
            shrank = (after_s["visible"] >= 0 and before_s["visible"] >= 0 and
                      after_s["visible"] < before_s["visible"])
            first_is_muffin = "muffin" in first_after
            all_match = (bool(after_s["visibleLabels"]) and
                         all("muffin" in lbl.lower() for lbl in after_s["visibleLabels"]))
            _shot(page, shot_dir, "1d-after-muffin")  # the requested filtered-grid shot
            report["screenshot"] = str(shot_dir / "1d-after-muffin.png")
            if shrank and first_is_muffin and all_match:
                c1d["verdict"] = "PASS"
                c1d["note"] = (f"visible {before_s['visible']}->{after_s['visible']}; "
                               f"first visible '{after_s['visibleLabels'][0]}'; "
                               f"all visible match muffin")
            elif shrank and first_is_muffin:
                c1d["verdict"] = "PASS"
                c1d["note"] = (f"visible {before_s['visible']}->{after_s['visible']}; "
                               f"first visible '{after_s['visibleLabels'][0]}' is muffin "
                               f"(non-muffin visible present: {after_s['visibleLabels'][:5]})")
            else:
                c1d["verdict"] = "FAIL"
                c1d["note"] = (f"visible {before_s['visible']}->{after_s['visible']} "
                               f"(shrank={shrank}, first_is_muffin={first_is_muffin}); "
                               f"after_labels={after_s['visibleLabels'][:5]}")
            # clear search
            try:
                box.fill("")
                time.sleep(0.8)
            except Exception:
                pass
        report["check_1d"] = c1d

        # =================== Load more still works ===================
        lm = {}
        cleared = _vis(page)
        lm["visible_before"] = cleared["visible"]
        clicked_lm = False
        for sel in ["button:has-text('Load more')", "#damLoadMore",
                    ".ff-dam-loadmore", "text=Load more"]:
            try:
                loc = _panel(page).locator(sel).first
                if loc.count() > 0:
                    loc.click(timeout=3000)
                    clicked_lm = True
                    time.sleep(1.5)
                    break
            except Exception:
                continue
        after_lm = _vis(page)
        lm["visible_after"] = after_lm["visible"]
        lm["clicked"] = clicked_lm
        if not clicked_lm:
            lm["verdict"] = "FAIL"
            lm["note"] = "no Load more button found"
        elif after_lm["visible"] > cleared["visible"]:
            lm["verdict"] = "PASS"
            lm["note"] = f"tiles appended {cleared['visible']}->{after_lm['visible']}"
        else:
            lm["verdict"] = "FAIL"
            lm["note"] = f"no append {cleared['visible']}->{after_lm['visible']}"
        report["load_more"] = lm

        # console assertion
        report["console_state"] = (_console_summary(console_errors, page_errors))

        return _finish(report, out_path, browser, console_errors, page_errors)


def _console_summary(console_errors, page_errors) -> str:
    if not console_errors and not page_errors:
        return "clean — no uncaught JS errors, no console errors during filtering"
    parts = []
    if page_errors:
        parts.append("UNCAUGHT: " + " | ".join(page_errors[:5]))
    if console_errors:
        parts.append("CONSOLE.ERROR: " + " | ".join(console_errors[:5]))
    return " ;; ".join(parts)


def _finish(report, out_path, browser, console_errors, page_errors) -> int:
    try:
        browser.close()
    except Exception:
        pass
    if report.get("console_state") in (None, "unknown"):
        report["console_state"] = _console_summary(console_errors, page_errors)
    verdicts = [report.get(k, {}).get("verdict") if isinstance(report.get(k), dict) else None
                for k in ("check_1c", "check_1d", "load_more")]
    if report["overall"] == "BLOCKED":
        code = 3
    elif "FAIL" in verdicts:
        report["overall"] = "FAIL"
        code = 2
    elif all(v == "PASS" for v in verdicts if v is not None) and any(verdicts):
        report["overall"] = "PASS"
        code = 0
    else:
        report["overall"] = "MIXED"
        code = 2
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--out", default="/tmp/kodiak-dam-reverify.json")
    ap.add_argument("--shot-dir", default="/tmp/kodiak-dam-reverify-shots")
    args = ap.parse_args()
    return run(args.headless, Path(args.out), Path(args.shot_dir))


if __name__ == "__main__":
    sys.exit(main())
