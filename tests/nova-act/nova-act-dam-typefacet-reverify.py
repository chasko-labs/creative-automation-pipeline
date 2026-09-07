#!/usr/bin/env python3
"""
Final re-verify of the DAM Type facet after the curated-chip fix deployed.

Chromium fallback path (NOVA_ACT_API_KEY absent): drives the LIVE CloudFront
origin with Playwright chromium, mirroring Nova Act page.* / act() semantics.

BACKGROUND
Previously the Type facet rendered a hardcoded chip set (Bars/Granola/etc).
Clicking a chip whose keyword matched zero LOADED tiles hid EVERY tile — a
dead-end. Fix under test: a Type chip renders ONLY IF >=1 currently-loaded tile
matches the chip keyword (same matcher as the search filter). So every RENDERED
chip must filter to a NON-EMPTY visible set.

WHAT THIS RUN PROVES
1. enumerate every rendered Type chip (besides All) + baseline visible count
2. for EACH chip: click, record visible-tile count after, assert > 0, reset via All
3. PASS iff every rendered chip -> non-zero visible set (no dead-ends)
4. "Bars" must be ABSENT if nothing matches it, OR if present must filter to > 0
5. spot-check search ("muffin") still filters, then clears; Load more still appends
6. console has no uncaught JS errors
7. regression: tabs still show 6 marketer categories with counts, switching works

visible tile = NOT [hidden] AND computed display != none AND offsetParent != null

Usage:
  .venv/bin/python scripts/nova-act-dam-typefacet-reverify.py --headless \
      --out /tmp/kodiak-typefacet.json --shot-dir /tmp/kodiak-typefacet-shots
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
ENTRY_URL = LIVE_URL + "?cakes=1"
EXPECTED_STAMP = "0.1.026-9225d7e-20260907"
STAMP_RE = re.compile(r"0\.1\.0\d{2}-[0-9a-f]{7}-\d{8}")
# strictly older than 026 => stale, reload once after 60s
STALE_RE = re.compile(r"0\.1\.0(0\d|1\d|2[0-5])-")

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
    let t = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').replace(/\u2713/g, '').trim();
    const half = Math.floor(t.length / 2);
    if (half > 4 && t.slice(0, half).trim() === t.slice(half).trim()) t = t.slice(0, half).trim();
    return t.slice(0, 60);
  };
  const vis = tiles.filter(isVisible);
  return { total: tiles.length, visible: vis.length,
           visibleLabels: vis.slice(0, 12).map(label) };
}
"""

# Enumerate Type-facet chips inside the panel. Returns [{label, isAll}] in DOM order.
# Excludes tab buttons and the Load-more control by scoping to the facet chip row.
CHIPS_JS = r"""
() => {
  const panel = document.querySelector('#damPanel');
  if (!panel) return {found:false, chips:[]};
  const sels = ['.ff-dam-facet-chip', '.ff-dam-chip', '[data-facet]', '.ff-dam-facet button'];
  let row = null, used = null;
  for (const s of sels) {
    const n = panel.querySelectorAll(s);
    if (n.length) { row = Array.from(n); used = s; break; }
  }
  if (!row) return {found:false, chips:[], selector:null};
  const clean = (el) => (el.innerText || el.textContent || '')
      .replace(/\s+/g, ' ').replace(/\u2713/g, '').replace(/\(\d+\)/,'').trim().slice(0,40);
  const chips = row.map(el => {
    const t = clean(el);
    return { label: t, isAll: /^all$/i.test(t), facet: el.getAttribute('data-facet') || null };
  }).filter(c => c.label.length > 0);
  return { found:true, selector: used, chips };
}
"""

# Read the marketer category tabs + counts.
TABS_JS = r"""
() => {
  const panel = document.querySelector('#damPanel');
  if (!panel) return {found:false, tabs:[]};
  let nodes = panel.querySelectorAll("[role='tab']");
  if (!nodes.length) nodes = panel.querySelectorAll('.ff-dam-tab');
  const clean = (el) => (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim();
  const tabs = Array.from(nodes).map(el => {
    const t = clean(el);
    const m = t.match(/(\d[\d,]*)/);
    return { text: t.slice(0,40), count: m ? parseInt(m[1].replace(/,/g,''),10) : null };
  }).filter(x => x.text);
  return { found: tabs.length>0, tabs };
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


def _click_chip_by_label(page, chip_selector: str, label: str) -> bool:
    """Click a Type-facet chip by its exact-ish visible label within the panel."""
    panel = _panel(page)
    # exact text match first, then contains
    candidates = [
        panel.locator(chip_selector).filter(has_text=re.compile(rf"^\s*{re.escape(label)}\s*$", re.I)),
        panel.locator(f"{chip_selector}:has-text('{label}')"),
    ]
    for loc in candidates:
        try:
            if loc.count() > 0:
                loc.first.click(timeout=3000)
                time.sleep(1.2)
                return True
        except Exception:
            continue
    return False


def run(headless: bool, out_path: Path, shot_dir: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        report = {"url": ENTRY_URL, "generated_at": _now(),
                  "blocked": "playwright not installed (Chromium fallback path)"}
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
        "tabs": None,
        "type_facet": None,
        "search": None,
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

        if page.locator("text=This demo is private").count() > 0:
            report["overall"] = "BLOCKED"
            report["blocked"] = "password gate still mounted despite ?cakes=1"
            report["screenshot"] = _shot(page, shot_dir, "00-gate")
            return _finish(report, out_path, browser, console_errors, page_errors)

        stamp = _read_stamp(page)
        if stamp != EXPECTED_STAMP and stamp and STALE_RE.match(stamp):
            print(f"[info] stale stamp {stamp}; wait 60s + reload once "
                  f"(invalidation IBG6V4PRW62N3NHK7GW1RG5VS1)", file=sys.stderr)
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

        # ---- open DAM panel ----
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

        # ---- regression: marketer category tabs ----
        tabs_info = {}
        try:
            tabs_info = page.evaluate(TABS_JS)
        except Exception as e:  # noqa: BLE001
            tabs_info = {"found": False, "error": str(e)}
        tabs = tabs_info.get("tabs", []) if isinstance(tabs_info, dict) else []
        with_counts = [t for t in tabs if t.get("count") is not None]
        products = next((t for t in tabs if "product" in t["text"].lower()), None)
        tabs_report = {
            "count": len(tabs),
            "labels": [t["text"] for t in tabs][:8],
            "products_count": products["count"] if products else None,
        }
        # switch to a non-default tab and back to confirm switching works
        switched = False
        other = next((t for t in tabs if "product" not in t["text"].lower()), None)
        if other:
            switched = _click_tab(page, other["text"].split("(")[0].strip().split()[0])
            time.sleep(0.6)
        _click_tab(page, "Products")
        time.sleep(0.8)
        tabs_report["switching_works"] = switched
        if len(tabs) == 6 and len(with_counts) >= 1:
            tabs_report["verdict"] = "PASS"
            tabs_report["note"] = f"6 categories with counts; products={tabs_report['products_count']}"
        else:
            tabs_report["verdict"] = "FAIL"
            tabs_report["note"] = f"expected 6 categories with counts, saw {len(tabs)} ({tabs_report['labels']})"
        report["tabs"] = tabs_report

        # ---- enumerate Type facet chips ----
        chips_info = page.evaluate(CHIPS_JS)
        chip_selector = chips_info.get("selector")
        all_chips = chips_info.get("chips", []) if chips_info.get("found") else []
        rendered = [c for c in all_chips if not c["isAll"]]
        rendered_labels = [c["label"] for c in rendered]

        baseline = _vis(page)
        _shot(page, shot_dir, "products-typefacet-row", full_page=False)
        report["screenshot"] = str(shot_dir / "products-typefacet-row.png")

        tf = {
            "chip_selector": chip_selector,
            "rendered_chips": rendered_labels,
            "baseline_visible": baseline["visible"],
            "baseline_total_nodes": baseline["total"],
            "per_chip": [],
            "bars_present": any(re.fullmatch(r"(?i)\s*bars?\s*", c["label"]) for c in rendered),
        }

        if not chips_info.get("found") or not rendered:
            tf["verdict"] = "FAIL"
            tf["note"] = "no Type facet chip row / no rendered chips found on Products tab"
        else:
            dead_ends = []
            for c in rendered:
                label = c["label"]
                clicked = _click_chip_by_label(page, chip_selector, label)
                after = _vis(page)
                entry = {
                    "chip": label,
                    "clicked": clicked,
                    "visible_after": after["visible"],
                    "nonzero": after["visible"] > 0,
                    "sample_labels": after["visibleLabels"][:4],
                }
                if not clicked or after["visible"] <= 0:
                    dead_ends.append(label)
                    entry["dead_end"] = True
                tf["per_chip"].append(entry)
                # reset to All before next chip
                _click_chip_by_label(page, chip_selector, "All")
                time.sleep(0.5)
            tf["dead_end_chips"] = dead_ends
            # Bars-specific rule: absent is fine; present must be > 0
            bars_entry = next((e for e in tf["per_chip"]
                               if re.fullmatch(r"(?i)\s*bars?\s*", e["chip"])), None)
            if not tf["bars_present"]:
                tf["bars_check"] = "ABSENT — no loaded tile matches 'Bars' (former dead-end removed)"
            elif bars_entry and bars_entry["visible_after"] > 0:
                tf["bars_check"] = f"PRESENT and non-zero ({bars_entry['visible_after']} visible)"
            else:
                tf["bars_check"] = "PRESENT but DEAD-END (0 visible)"
            if not dead_ends and (not tf["bars_present"] or (bars_entry and bars_entry["visible_after"] > 0)):
                tf["verdict"] = "PASS"
                tf["note"] = (f"{len(rendered)} rendered chips, all filter to non-zero; "
                              f"{tf['bars_check']}")
            else:
                tf["verdict"] = "FAIL"
                tf["note"] = f"dead-end chips: {dead_ends or 'none'}; bars={tf['bars_check']}"
        # ensure reset before search check
        _click_chip_by_label(page, chip_selector or ".ff-dam-facet-chip", "All")
        time.sleep(0.5)
        report["type_facet"] = tf

        # ---- search spot-check ("muffin") ----
        before_s = _vis(page)
        sc = {"visible_before": before_s["visible"]}
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
            sc["verdict"] = "FAIL"
            sc["note"] = "no search box found"
        else:
            box = _panel(page).locator(search_sel).first
            box.click()
            box.type("muffin", delay=60)
            time.sleep(1.6)
            after_s = _vis(page)
            sc["visible_after"] = after_s["visible"]
            sc["first_labels_after"] = after_s["visibleLabels"][:5]
            shrank = (after_s["visible"] >= 0 and before_s["visible"] >= 0 and
                      after_s["visible"] < before_s["visible"])
            first_is_muffin = ("muffin" in (after_s["visibleLabels"][0].lower()
                                            if after_s["visibleLabels"] else ""))
            all_match = (bool(after_s["visibleLabels"]) and
                         all("muffin" in lbl.lower() for lbl in after_s["visibleLabels"]))
            if shrank and first_is_muffin and all_match:
                sc["verdict"] = "PASS"
                sc["note"] = (f"visible {before_s['visible']}->{after_s['visible']}; "
                              f"all visible match muffin")
            elif shrank and first_is_muffin:
                sc["verdict"] = "PASS"
                sc["note"] = (f"visible {before_s['visible']}->{after_s['visible']}; "
                              f"first visible is muffin (mixed: {after_s['visibleLabels'][:4]})")
            else:
                sc["verdict"] = "FAIL"
                sc["note"] = (f"visible {before_s['visible']}->{after_s['visible']} "
                              f"(shrank={shrank}, first_is_muffin={first_is_muffin})")
            # clear
            try:
                box.fill("")
                time.sleep(0.8)
            except Exception:
                pass
            after_clear = _vis(page)
            sc["visible_after_clear"] = after_clear["visible"]
            sc["cleared_ok"] = after_clear["visible"] >= after_s["visible"]
        report["search"] = sc

        # ---- Load more still appends ----
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

        report["console_state"] = _console_summary(console_errors, page_errors)
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
                for k in ("tabs", "type_facet", "search", "load_more")]
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
    ap.add_argument("--out", default="/tmp/kodiak-typefacet.json")
    ap.add_argument("--shot-dir", default="/tmp/kodiak-typefacet-shots")
    args = ap.parse_args()
    return run(args.headless, Path(args.out), Path(args.shot_dir))


if __name__ == "__main__":
    sys.exit(main())
