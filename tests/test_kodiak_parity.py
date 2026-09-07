"""kodiak-parity gate: token copies match canonical, logo pinned, briefs valid.

Extends tests/test_token_drift.py (which guards kodiak.json -> styles.css):
 1. Every known tree copy of the brand hexes still carries the canonical
    value. A drifted copy fails; a deliberate canonical change fails here
    too, listing each copy to update -- that is the parity contract.
 2. The three kodiak-primary-logo.png copies are byte-identical and match
    the pinned sha256. A swapped logo fails.
 3. Every briefs/*.yaml|json validates against the CampaignBrief schema
    (src/creative_automation/brief.py); KODIAK briefs must also carry
    exactly the three canonical brand_colors.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")

BRAND_KEYS = (
    "color.brand.bearBrown",
    "color.brand.blazeOrange",
    "color.brand.frontierGreen",
    "color.brand.signalRed",
)

# file -> brand hexes that must be present (lowercased). Verified 2026-09-07;
# update alongside any deliberate palette change.
EXPECTED_COPIES = {
    "web/kodiak-posts-for-todays-frontier/design/components.css": {"#3b2316", "#e8530e", "#b51e14"},
    "web/kodiak-posts-for-todays-frontier/index.html": {"#3b2316", "#e8530e", "#b51e14"},
    "web/kodiak-posts-for-todays-frontier/js/data-core.js": {"#3b2316", "#e8530e"},
    "web/kodiak-posts-for-todays-frontier/webmcp.json": {"#3b2316"},
    "src/creative_automation/scorecards.py": {"#3b2316", "#e8530e", "#1a3c34"},
    "src/creative_automation/enhance.py": {"#3b2316", "#e8530e"},
    "src/creative_automation/lockup.py": {"#3b2316", "#e8530e"},
    "src/creative_automation/generate.py": {"#3b2316", "#e8530e", "#1a3c34", "#1a1110cc"},
    "src/creative_automation/api.py": {"#3b2316", "#e8530e", "#1a3c34"},
}

LOGO_FILES = [
    "web/kodiak-posts-for-todays-frontier/assets/kodiak-primary-logo.png",
    "web/kodiak-posts-for-todays-frontier/assets/kodiak-primary-logo_optimized.png",
    "src/creative_automation/brand_assets/kodiak-primary-logo.png",
]
LOGO_SHA256 = "9275a959e71f557f186bfaf8971d2341fb73c8ccae6e38f7e5f240ce250e7ea6"


def _canonical_brand() -> set[str]:
    tokens = json.loads((REPO_ROOT / "design" / "tokens" / "kodiak.json").read_text(encoding="utf-8"))
    node = tokens["kodiak"]
    out = set()
    for dotted in BRAND_KEYS + ("color.semantic.overlay.scrim",):
        sub = node
        for seg in dotted.split("."):
            sub = sub[seg]
        out.add(sub["$value"].lower())
    return out


def test_brand_copies_match_canonical():
    canonical = _canonical_brand()
    for rel, expected in EXPECTED_COPIES.items():
        text = (REPO_ROOT / rel).read_text(encoding="utf-8").lower()
        for hx in expected:
            assert hx in text, f"{rel} lost its {hx} copy (drift?)"
            assert hx in canonical, f"{rel} expects {hx} which left canonical -- update EXPECTED_COPIES"


def test_logo_hash_pinned():
    digests = set()
    for rel in LOGO_FILES:
        data = (REPO_ROOT / rel).read_bytes()
        digests.add(hashlib.sha256(data).hexdigest())
    assert len(digests) == 1, f"logo copies diverged: {digests}"
    assert digests.pop() == LOGO_SHA256, "logo bytes changed -- deliberate swaps update LOGO_SHA256"


def test_briefs_validate_against_schema():
    from creative_automation.brief import load_brief

    canonical_trio = {"#3b2316", "#e8530e", "#1a3c34"}
    seen = 0
    for path in sorted((REPO_ROOT / "briefs").glob("*.yaml")) + sorted((REPO_ROOT / "briefs").glob("*.json")):
        brief = load_brief(path)
        seen += 1
        if brief.brand.upper() == "KODIAK":
            colors = {c.lower() for c in (brief.brand_colors or [])}
            assert colors == canonical_trio, f"{path.name}: KODIAK brand_colors drifted: {sorted(colors)}"
    assert seen > 0, "no briefs found to validate"
