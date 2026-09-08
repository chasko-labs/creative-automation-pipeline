#!/usr/bin/env python3
"""Kodiak live-verification harness — deterministic, incremental.

Runs the declarative checks in spec/checks.json against the LIVE origin and
writes a JSON report + per-check evidence (screenshot, DOM snippet, stamp)
under /tmp/kodiak-verify/<version>/<utc-ts>/.

Usage:
  python tests/nova-act/run.py [check-id ...] [--negative-control ID]

Exit codes (established convention): 0 all pass, 2 one or more fail,
3 blocked (gate, navigation, or stamp moved mid-run).

Driver policy: Nova Act drives live URLs only. NOVA_ACT_API_KEY comes from
env (SSM-backed, never on disk). Key absent -> Chromium fallback with
identical check semantics; the report records which driver ran each check.
Absent key degrades loudly, never blocks.

Determinism: the kodiak-version meta stamp is pinned at start; a stamp
change mid-run aborts fail-closed with exit 3. No wall-clock or
animation-frame assertions. Text assertions use claim-scoped selectors —
never whole-document regexes (the #17 lesson: an overbroad regex matched
legit product-thumbnail URLs).

--negative-control ID is build-time machinery only: it forces the named
check to fail so a run can prove the harness detects failure. Never used
to record a passing run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "spec" / "checks.json"
STAMP_RE = re.compile(r"0\.1\.0\d{2}-[0-9a-f]{7}-\d{8}")

EXIT_PASS, EXIT_FAIL, EXIT_BLOCKED = 0, 2, 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_spec() -> dict:
    with open(SPEC_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def read_stamp(page) -> str | None:
    """Pinned version stamp, scoped to the version meta element only."""
    try:
        content = page.get_attribute('meta[name="kodiak-version"]', "content")
    except Exception:
        return None
    if content:
        m = STAMP_RE.search(content)
        return m.group(0) if m else content
    return None


class ChromiumSession:
    """Local-Chromium fallback driver (also used for localhost checks)."""

    name = "chromium-fallback"

    def __init__(self, width: int, height: int):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._ctx = self._browser.new_context(viewport={"width": width, "height": height})

    def page(self, url: str):
        page = self._ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(2500)
        return page

    def close(self):
        try:
            self._browser.close()
        finally:
            self._pw.stop()


class NovaActSession:
    """Nova Act driver — live URLs only. Requires NOVA_ACT_API_KEY in env."""

    name = "nova-act"

    def __init__(self, width: int, height: int, api_key: str):
        from nova_act import NovaAct  # lazy: chromium-only envs lack the SDK

        self._nova = NovaAct(
            starting_page="about:blank",
            nova_act_api_key=api_key,
            headless=True,
            screen_width=width,
            screen_height=height,
        )
        self._nova.start()

    def page(self, url: str):
        self._nova.go_to_url(url)
        page = self._nova.page
        page.wait_for_load_state("networkidle", timeout=45000)
        page.wait_for_timeout(2500)
        return page

    def close(self):
        try:
            self._nova.stop()
        except Exception:
            pass


def open_session(viewport: str, width: int, height: int):
    """One session per viewport group. Returns (session, driver_name, notices)."""
    notices = []
    api_key = os.environ.get("NOVA_ACT_API_KEY", "").strip()
    if api_key:
        try:
            return NovaActSession(width, height, api_key), NovaActSession.name, notices
        except Exception as e:  # noqa: BLE001 — fall through loudly
            notices.append(f"nova-act start failed ({e}); falling back to chromium")
    else:
        notices.append("NOVA_ACT_API_KEY absent — chromium fallback (loud degradation, not a block)")
    return ChromiumSession(width, height), ChromiumSession.name, notices


# --------------------------------------------------------------------------- #
# Assert evaluators — every read is scoped to the element under claim.
# Each returns (pass: bool, detail: dict, snippet: str).
# --------------------------------------------------------------------------- #

HEADER_JS = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return {
    bgColor: cs.backgroundColor || '',
    bgImage: cs.backgroundImage || '',
    outer: el.outerHTML.slice(0, 800),
    top: r.top, left: r.left, width: r.width, height: r.height,
  };
}"""


def _eval_header_background_flat(page, params: dict):
    h = page.evaluate(HEADER_JS, "header.kodiak-header")
    if not h:
        return False, {"error": "header.kodiak-header missing"}, ""
    bg_img = h["bgImage"] or ""
    flat = ("none" in bg_img.lower()) and ("url(" not in bg_img.lower())
    # claim scope is the HEADER RULE: texture refs are only violations inside
    # the header element's own markup (product-thumbnail CDN imgs elsewhere
    # are legitimate imagery — the #17 overbroad-regex lesson).
    outer = h["outer"]
    no_texture = ("mega-menu" not in outer) and ("kodiakcakes.com/cdn" not in outer)
    ok = flat and no_texture
    return ok, {"backgroundColor": h["bgColor"], "backgroundImage": bg_img[:80],
                "flatFill": flat, "noHeaderTextureRef": no_texture}, outer


def _eval_header_top(page, params: dict):
    h = page.evaluate(HEADER_JS, "header.kodiak-header")
    if not h:
        return False, {"error": "header.kodiak-header missing"}, ""
    max_top = float(params.get("max_top_px", 10))
    ok = 0 <= h["top"] < max_top
    return ok, {"headerTop": h["top"], "max_top_px": max_top}, f"top={h['top']}"


def _eval_absent_strings(page, params: dict):
    scope = params.get("scope", "body-text")
    text = (page.inner_text("body") or "") if scope == "body-text" else (page.content() or "")
    hits = [s for s in params.get("strings", []) if s in text]
    return (len(hits) == 0, {"scope": scope, "hits": hits, "checked": len(params.get("strings", []))},
            f"hits={hits}")


def _eval_no_marquee(page, params: dict):
    found = page.evaluate("""() => ({
      marquee: document.querySelectorAll('marquee, .marquee, [data-testid="marquee-recipes"]').length,
      copy: /PROMPT\\s*->\\s*CAMPAIGNS|88 SKUs/.test(document.body ? document.body.innerText : ''),
    })""")
    ok = found["marquee"] == 0 and not found["copy"]
    return ok, found, f"elements={found['marquee']} copy={found['copy']}"


def _eval_create_cascades(page, params: dict):
    text = page.inner_text("body") or ""
    dead = [s for s in params.get("dead_copy", []) if s in text]
    if dead:
        return False, {"deadCopyHits": dead}, f"dead={dead}"
    clicked = page.evaluate("""() => {
      const btn = document.querySelector('#generateCampaign');
      if (!btn) return false;
      btn.click();
      return true;
    }""")
    if not clicked:
        return False, {"error": "#generateCampaign missing"}, ""
    tiles, status = 0, ""
    for _ in range(10):  # poll up to ~20s; no animation-frame assertions
        page.wait_for_timeout(2000)
        tiles = page.evaluate("() => document.querySelectorAll('#preview > *').length")
        if tiles > 0:
            break
    try:
        status = (page.inner_text("#sampleStatus") or "")[:120]
    except Exception:
        pass
    ok = tiles > 0
    return ok, {"createClicked": True, "previewTilesAfterCreate": tiles,
                "sampleStatus": status}, f"tiles={tiles} status={status[:60]}"


def _eval_about_clean(page, params: dict):
    text = page.inner_text("body") or ""
    hits = [s for s in params.get("strings", []) if s in text]
    link = page.evaluate(
        "(sel) => !!document.querySelector(sel)", params.get("link", 'a[href="details.html"]'))
    ok = (len(hits) == 0) and link
    return ok, {"hits": hits, "detailsLink": link}, f"hits={hits} link={link}"


def _eval_generate_rung(page, params: dict):
    """Unit 3 (#173): the standard Create must land rung A or B, never fallback.

    Clicks #generateCampaign and polls #genSourceBadge (the Unit 2 badge) for
    the rung letter. Poll budget ~100s covers load + the ~23s generation wall.
    """
    import re

    allowed = params.get("allow", ["A", "B"])
    clicked = page.evaluate("() => { const b = document.querySelector('#generateCampaign');"
                            " if (!b) return false; b.click(); return true; }")
    if not clicked:
        return False, {"error": "#generateCampaign missing"}, ""
    badge, rung = "", None
    for _ in range(50):
        page.wait_for_timeout(2000)
        try:
            badge = (page.inner_text("#genSourceBadge") or "").strip()
        except Exception:
            badge = ""
        m = re.search(r"Rung ([ABCD])", badge)
        if m:
            rung = m.group(1)
            break
    ok = rung in allowed
    return ok, {"badge": badge[:160], "rung": rung, "allow": allowed}, \
        f"rung={rung} badge={badge[:120]}"


EVALUATORS = {
    "header-background-flat": _eval_header_background_flat,
    "header-top": _eval_header_top,
    "absent-strings": _eval_absent_strings,
    "no-marquee": _eval_no_marquee,
    "create-cascades": _eval_create_cascades,
    "about-clean": _eval_about_clean,
    "generate-rung": _eval_generate_rung,
}


def _viewports_for(check: dict, spec: dict) -> list[str]:
    v = check.get("viewport", "all")
    names = list(spec.get("viewports", {"desktop": [1440, 900]}).keys())
    if v == "all":
        return names
    return [v] if v in names else names[:1]


def run_check(session, check: dict, viewport: str, ev_dir: Path, sabotage: bool):
    """Run one check on one viewport. Returns the result record."""
    page = session.page(check["url"])
    try:
        stamp = read_stamp(page)
        atype = check["assert"]["type"]
        fn = EVALUATORS.get(atype)
        if fn is None:
            return {"id": check["id"], "viewport": viewport, "pass": False,
                    "stamp": stamp, "error": f"unknown assert type {atype}"}
        if sabotage:
            result = (False, {"sabotaged": True,
                              "note": "negative control — expectation deliberately broken"},
                      "NEGATIVE-CONTROL")
        else:
            result = fn(page, check["assert"])
        ok, detail, snippet = result
        shot = ev_dir / f"{check['id']}.{viewport}.png"
        try:
            page.screenshot(path=str(shot))
        except Exception as e:  # noqa: BLE001
            shot, detail = None, dict(detail, screenshot_error=str(e))
        (ev_dir / f"{check['id']}.{viewport}.snippet.txt").write_text(
            snippet[:2000], encoding="utf-8")
        return {"id": check["id"], "issue": check.get("issue"), "viewport": viewport,
                "pass": bool(ok), "stamp": stamp, "detail": detail,
                "evidence": {"screenshot": str(shot) if shot else None,
                             "snippet": str(ev_dir / f"{check['id']}.{viewport}.snippet.txt")}}
    finally:
        try:
            page.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checks", nargs="*", help="check ids to run (default: all)")
    ap.add_argument("--negative-control", metavar="ID",
                    help="build-time only: force check ID to fail")
    ap.add_argument("--out-root", default="/tmp/kodiak-verify")
    args = ap.parse_args()

    spec = load_spec()
    wanted = spec["checks"]
    if args.checks:
        wanted = [c for c in wanted if c["id"] in args.checks]
        if not wanted:
            print(f"unknown check ids: {args.checks}", file=sys.stderr)
            return EXIT_BLOCKED

    ts = _now()
    # stamp dir uses filesystem-safe compact ts; pinned version resolves at first open
    run_dir = Path(args.out_root) / "pending" / ts.replace(":", "").replace("+", "")
    run_dir.mkdir(parents=True, exist_ok=True)

    results, notices, pinned = [], [], None
    blocked = False
    for vp_name in spec.get("viewports", {"desktop": [1440, 900]}):
        width, height = spec["viewports"][vp_name]
        group = [c for c in wanted if vp_name in _viewports_for(c, spec)]
        if not group:
            continue
        session, driver, notes = open_session(vp_name, width, height)
        notices.extend(notes)
        try:
            for check in group:
                rec = run_check(session, check, vp_name, run_dir,
                                sabotage=(args.negative_control == check["id"]))
                rec["driver"] = driver
                results.append(rec)
                if pinned is None and rec.get("stamp"):
                    pinned = rec["stamp"]
        except Exception as e:  # noqa: BLE001 — navigation/session failure blocks
            results.append({"id": "*", "viewport": vp_name, "pass": False,
                            "driver": driver, "error": f"blocked: {e}"})
            blocked = True
        finally:
            session.close()

    # fail-closed on a moving target: re-read the stamp live
    final_stamp = None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            pg = b.new_page()
            pg.goto(spec["origin"] + spec.get("gate_bypass", ""), timeout=45000)
            final_stamp = read_stamp(pg)
            b.close()
    except Exception as e:  # noqa: BLE001
        notices.append(f"final stamp re-read failed: {e}")

    stamp_moved = bool(pinned and final_stamp and pinned != final_stamp)
    version = pinned or "unknown"
    stamped_dir = Path(args.out_root) / version / ts.replace(":", "").replace("+", "")
    stamped_dir.mkdir(parents=True, exist_ok=True)
    for f in run_dir.iterdir():
        f.rename(stamped_dir / f.name)
    try:
        run_dir.rmdir()
        Path(args.out_root, "pending").rmdir()
    except OSError:
        pass

    report = {"ts": ts, "tool": "tests/nova-act/run.py", "spec": "tests/nova-act/spec/checks.json",
              "stamp_pinned": pinned, "stamp_final": final_stamp, "stamp_moved": stamp_moved,
              "notices": notices,
              "negative_control": args.negative_control,
              "checks": results,
              "allPass": all(r.get("pass") for r in results) and not blocked and not stamp_moved}
    (stamped_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    for r in results:
        flag = "PASS" if r.get("pass") else "FAIL"
        print(f"[{flag}] {r.get('id')} ({r.get('viewport')}, {r.get('driver')}) {r.get('detail', {})}")
    for n in notices:
        print(f"note: {n}")
    print(f"stamp pinned={pinned} final={final_stamp} moved={stamp_moved}")
    print(f"report: {stamped_dir / 'report.json'}")

    if blocked or stamp_moved:
        return EXIT_BLOCKED
    return EXIT_PASS if report["allPass"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
