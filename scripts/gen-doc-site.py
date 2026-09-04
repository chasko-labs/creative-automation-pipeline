#!/usr/bin/env python3
"""Render the whole markdown doc tree to a self-contained, offline, navigable HTML site.

Reviewers open the zip and read every doc rendered + cross-linked LOCALLY — no GitHub,
no private-repo 404s, no network. Each .md becomes a sibling .html with the marked
parser (MIT) inlined and the markdown embedded as text. A client-side link rewriter
runs in each page so links navigate within the zip:

  - https://github.com/chasko-labs/creative-automation-pipeline/blob/main/docs/X.md -> docs/X.html
  - https://github.com/.../blob/main/PATH.py|.json|.html -> the local PATH (viewable as-is)
  - relative  ./foo.md / ../docs/bar.md -> foo.html / ../docs/bar.html
  - anything else (real external URLs) left untouched

Usage:
  python scripts/gen-doc-site.py <ROOT_DIR> [MARKED_JS]

ROOT_DIR is the staged package root (e.g. the reviewer-package export). Every *.md
under it (recursively) is rendered to *.html next to it. README.md -> README.html.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

REPO = "chasko-labs/creative-automation-pipeline"

# Single source of truth for the palette is design/tokens/kodiak.json (Panda CSS
# emitTokensOnly). The doc-site is offline/self-contained (git-archive export, no
# network), so we cannot link the generated stylesheet at runtime — instead we READ
# the canonical token VALUES at generation time and inject them as the :root vars.
# This kills palette drift: the doc-site renders in the exact app palette, with zero
# duplicated hex. Keep the var NAMES the templates already use (--bear/--blaze/--pine/
# --parch/--kraft/--ink/--muted); only their VALUES now come from the token file.
TOKEN_PATH = ("design", "tokens", "kodiak.json")

# Map doc-site var name -> token path under kodiak.color in kodiak.json.
_TOKEN_MAP = {
    "bear": ("brand", "bearBrown"),   # #3B2316
    "blaze": ("brand", "blazeOrange"),  # #E8530E
    "pine": ("brand", "frontierGreen"),  # #1A3C34
    "parch": ("neutral", "50"),        # #FFF8F0 parchment (was drifted #faf6ef)
    "kraft": ("neutral", "100"),       # #F4EDE6 oatmeal/kraft (was drifted #efe7db)
    "ink": ("neutral", "900"),         # #1A1110 ink
    "muted": ("neutral", "600"),       # #6B5A53 canyon / muted body
}

# Corrected canonical literals — used ONLY when kodiak.json is absent at gen time
# (e.g. a partial export). These are the token values, NOT the old drifted ones:
# parch #FFF8F0 (not #faf6ef), kraft #F4EDE6 (not #efe7db).
_TOKEN_FALLBACK = {
    "bear": "#3B2316", "blaze": "#E8530E", "pine": "#1A3C34",
    "parch": "#FFF8F0", "kraft": "#F4EDE6", "ink": "#1A1110", "muted": "#6B5A53",
}


def _find_token_file(root: Path) -> Path | None:
    """Locate design/tokens/kodiak.json: prefer one inside the staged ROOT (the
    export carries the token file), else walk up from the script location (dev runs
    against a scratch dir that has no tokens)."""
    candidates = [root / Path(*TOKEN_PATH)]
    here = Path(__file__).resolve().parent
    for base in (here, *here.parents):
        candidates.append(base / Path(*TOKEN_PATH))
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_palette(root: Path) -> dict[str, str]:
    """Return the doc-site palette (var name -> hex), sourced from kodiak.json when
    present, falling back to the corrected canonical literals otherwise."""
    token_file = _find_token_file(root)
    if token_file is None:
        return dict(_TOKEN_FALLBACK)
    try:
        color = json.loads(token_file.read_text(encoding="utf-8"))["kodiak"]["color"]
    except (OSError, ValueError, KeyError) as e:  # noqa: BLE001
        print(f"[gen-doc-site] token read failed ({e}); using canonical fallback", file=sys.stderr)
        return dict(_TOKEN_FALLBACK)
    palette: dict[str, str] = {}
    for var, (group, key) in _TOKEN_MAP.items():
        try:
            palette[var] = color[group][key]["$value"]
        except (KeyError, TypeError):
            palette[var] = _TOKEN_FALLBACK[var]
    return palette


def root_css(root: Path) -> str:
    """Build the :root custom-property block from the derived palette. This exact
    block is shared with build-reviewer-package.sh via --emit-root-css so the
    START-HERE launcher and the doc-site never drift apart."""
    p = load_palette(root)
    return (
        ":root {\n"
        f"  --bear: {p['bear']}; --blaze: {p['blaze']}; --pine: {p['pine']};\n"
        f"  --kraft: {p['kraft']}; --parch: {p['parch']}; --ink: {p['ink']}; --muted: {p['muted']};\n"
        "}"
    )


# STYLE carries everything EXCEPT the :root block; the palette block is prepended at
# generation time from root_css() so the values come from the design system.
STYLE_BODY = """
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--parch); color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.65;
}
.wrap { max-width: 880px; margin: 0 auto; padding: 2rem 1.5rem 5rem; }
.topbar { background: var(--bear); color: var(--parch); padding: .8rem 1.5rem; font-weight: 700; letter-spacing: .01em; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: .5rem; }
.topbar a { color: var(--parch); text-decoration: none; opacity: .85; font-weight: 600; font-size: .88rem; }
.topbar a:hover { opacity: 1; }
.topbar .nav a { margin-left: 1rem; }
.bar { height: 5px; background: var(--blaze); }
h1, h2, h3, h4 { color: var(--bear); line-height: 1.25; margin: 1.8rem 0 .7rem; }
h1 { font-size: 1.9rem; border-bottom: 3px solid var(--blaze); padding-bottom: .4rem; }
h2 { font-size: 1.4rem; border-bottom: 1px solid #e2d6c3; padding-bottom: .3rem; }
h3 { font-size: 1.15rem; }
a { color: var(--blaze); }
blockquote { margin: 1.2rem 0; padding: .7rem 1.2rem; background: #fff; border-left: 4px solid var(--blaze); border-radius: 6px; color: var(--muted); }
code { background: var(--kraft); padding: .12rem .4rem; border-radius: 4px; font-size: .88em; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre { background: var(--bear); color: #f4ede2; padding: 1.1rem 1.3rem; border-radius: 10px; overflow-x: auto; }
pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1.2rem 0; font-size: .93rem; }
th, td { border: 1px solid #e2d6c3; padding: .55rem .8rem; text-align: left; }
th { background: var(--kraft); color: var(--bear); }
tr:nth-child(even) td { background: #fff; }
img { max-width: 100%; height: auto; border-radius: 6px; }
hr { border: none; border-top: 1px solid #e2d6c3; margin: 2rem 0; }
ul, ol { padding-left: 1.4rem; }
.footnote { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e2d6c3; color: var(--muted); font-size: .85rem; }
.brokenlink { color: var(--muted); text-decoration: line-through; cursor: not-allowed; }
"""

# {rel_to_root} is the relative path prefix from this page back to the package root
# (e.g. "" for README.html, "../" for docs/X.html) so START-HERE + assets resolve.
TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>{style}</style>
<script>{marked}</script>
</head>
<body>
<div class="topbar">
  <span>KODIAK&reg; &mdash; Creative Automation Pipeline</span>
  <span class="nav">
    <a href="{rel_to_root}START-HERE.html">Start here</a>
    <a href="{rel_to_root}README.html">README</a>
    <a href="https://kodiak.bryanchasko.com/" target="_blank" rel="noopener">Live site &rarr;</a>
  </span>
</div>
<div class="bar"></div>
<div class="wrap">
  <div id="content">Rendering&hellip;</div>
  <div class="footnote">Rendered offline from {srcname}. All in-project links resolve locally within this package &mdash; no network required.</div>
</div>
<script id="md" type="text/markdown">{markdown}</script>
<script>
  (function () {{
    var REPO = "{repo}";
    var src = document.getElementById("md").textContent;
    var target = document.getElementById("content");
    try {{
      marked.setOptions({{ gfm: true, breaks: false }});
      target.innerHTML = marked.parse(src);
    }} catch (e) {{
      var pre = document.createElement("pre"); pre.textContent = src;
      target.innerHTML = ""; target.appendChild(pre);
      return;
    }}
    // Rewrite links so the doc set is navigable LOCALLY inside the zip.
    var blob = "https://github.com/" + REPO + "/blob/main/";
    var raw = "https://raw.githubusercontent.com/" + REPO + "/main/";
    target.querySelectorAll("a[href]").forEach(function (a) {{
      var href = a.getAttribute("href");
      if (!href) return;
      // 1) private GitHub blob/raw links -> local path
      var localPath = null;
      if (href.indexOf(blob) === 0) localPath = href.slice(blob.length);
      else if (href.indexOf(raw) === 0) localPath = href.slice(raw.length);
      if (localPath !== null) {{
        localPath = localPath.split("#")[0].split("?")[0];
        if (/\\.md$/i.test(localPath)) localPath = localPath.replace(/\\.md$/i, ".html");
        a.setAttribute("href", "{rel_to_root}" + localPath);
        return;
      }}
      // 2) relative .md links -> .html (skip anchors, absolute, mailto, real external http)
      if (/^(https?:|mailto:|#|\\/)/i.test(href)) return;
      var base = href.split("#")[0].split("?")[0];
      if (/\\.md$/i.test(base)) {{
        var anchor = href.slice(base.length);
        a.setAttribute("href", base.replace(/\\.md$/i, ".html") + anchor);
      }}
    }});
  }})();
</script>
</body>
</html>
"""


def rel_to_root(md_path: Path, root: Path) -> str:
    """Depth-based ../ prefix from an md file's location back to root."""
    depth = len(md_path.relative_to(root).parts) - 1
    return "../" * depth


def main() -> int:
    # --emit-root-css [ROOT_DIR]: print just the :root token block and exit. Lets
    # build-reviewer-package.sh inject the SAME derived palette into START-HERE.html
    # so the launcher and the doc-site share one source of truth (the token file).
    if len(sys.argv) >= 2 and sys.argv[1] == "--emit-root-css":
        root = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path.cwd()
        print(root_css(root))
        return 0
    if len(sys.argv) < 2:
        print("usage: gen-doc-site.py <ROOT_DIR> [MARKED_JS]", file=sys.stderr)
        print("       gen-doc-site.py --emit-root-css [ROOT_DIR]", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    marked_js = (
        Path(sys.argv[2]) if len(sys.argv) > 2
        else Path(__file__).resolve().parent / "vendor" / "marked.min.js"
    )
    if not root.is_dir():
        print(f"[gen-doc-site] not a dir: {root}", file=sys.stderr)
        return 1
    if not marked_js.exists():
        print(f"[gen-doc-site] missing marked lib: {marked_js}", file=sys.stderr)
        return 1

    marked = marked_js.read_text(encoding="utf-8")
    # Derive the palette once from the design tokens, prepend to the static rules.
    style = root_css(root) + "\n" + STYLE_BODY
    md_files = sorted(root.rglob("*.md"))
    count = 0
    for md in md_files:
        try:
            markdown = md.read_text(encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"[gen-doc-site] skip {md}: {e}", file=sys.stderr)
            continue
        safe_md = markdown.replace("</script>", "<\\/script>")
        out = md.with_suffix(".html")
        title = f"KODIAK - {md.stem}"
        out.write_text(
            TEMPLATE.format(
                title=html.escape(title),
                style=style,
                marked=marked,
                markdown=safe_md,
                repo=REPO,
                rel_to_root=rel_to_root(md, root),
                srcname=md.name,
            ),
            encoding="utf-8",
        )
        count += 1
    print(f"[gen-doc-site] rendered {count} markdown files to HTML under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
