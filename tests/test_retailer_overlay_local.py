"""Diamond sprint Phase 1 (retail): local-logo overlay end-to-end + SF/Park City pins.

#40: the canonical logo dir (input_assets/retailer-logos/) carries real PNG
marks (costco/publix/target). These tests prove the overlay resolve hits the
local PNGs end to end on a dev box with no DAM/creds: Pillow-decodes, DAM-miss
falls through to the repo-local file, the lockup compositor takes the PNG
source path (not the text band), and the generate overlay mark resolves.
No mocks — real files, real functions. SVG vectors are still absent; vector
sourcing + provenance is a tracked follow-up, not asserted here.

#198: pins the live SF + Park City retailer strings (read from the repo's own
store-finder-markets.json, not hardcoded copies) against the chooser contract:
Target surfaces; Walmart/Smith's/Whole Foods/Safeway never become chooser
cards (Walmart stays in market data strings only, per the recorded decision).

OFFLINE, cred-free.
"""
from __future__ import annotations

import json
import pathlib

from PIL import Image

from creative_automation import lockup
from creative_automation import retailers
from creative_automation.asset_pack import market_retailers
from creative_automation.retailers import (
    LOGO_DIR,
    missing_logos,
    resolve_retailer,
    resolve_retailer_logo,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


def _store_strings() -> dict[str, dict]:
    data = json.loads(
        (REPO / "data" / "localization" / "store-finder-markets.json").read_text()
    )
    return {m["market"]: m for m in data["markets"]}


# ---- #40: local PNG marks exist and decode --------------------------------- #

def test_local_png_marks_exist_and_decode():
    for slug in ("costco", "publix", "target"):
        path = LOGO_DIR / f"{slug}.png"
        assert path.exists(), f"missing local mark {path}"
        assert path.stat().st_size > 0
        with Image.open(path) as im:
            im.load()  # raises on truncated/garbage bytes


def test_overlay_resolve_hits_local_png_end_to_end():
    # dev box: no DAM creds, so the DAM-first fetch misses and the resolve
    # must land on the repo-local PNG (exercises the full function, both tiers).
    for slug in ("costco", "publix", "target"):
        hit = resolve_retailer_logo(slug)
        assert hit is not None, f"{slug} did not resolve"
        assert hit == LOGO_DIR / f"{slug}.png"
        with Image.open(hit) as im:
            im.load()


def test_overlay_resolve_alias_and_variant_forms():
    assert resolve_retailer_logo("Costco Wholesale") == LOGO_DIR / "costco.png"
    assert resolve_retailer_logo("Publix") == LOGO_DIR / "publix.png"


def test_overlay_resolve_never_fabricates():
    # copy-only retailers, subscription (fulfillment, never a mark), and
    # unknown names resolve to None so the render ships clean.
    for name in ("kroger", "HEB", "Whole Foods", "subscription", "Safeway", "nope"):
        assert resolve_retailer_logo(name) is None, name


def test_missing_logos_is_subscription_only_by_design():
    # subscription is the DTC fulfillment entry — it carries no logo file.
    # every chain grocer on the chooser must have a local mark.
    assert missing_logos() == ["subscription"]


def test_resolve_retailer_reports_png_present_svg_absent():
    for slug in ("costco", "publix", "target"):
        resolved = resolve_retailer(slug)
        assert resolved.png_exists and not resolved.missing
        assert not resolved.svg_exists  # vector sourcing is the follow-up


def test_publix_lockup_uses_real_mark_not_text_band(tmp_path):
    base = tmp_path / "hero.png"
    Image.new("RGB", (1080, 1080), (120, 160, 140)).save(base, "PNG")
    result = lockup.compose_retailer_lockup(base, "publix")
    assert result["logo_source"] == "png"
    assert result["out_path"].exists()


def test_generate_retailer_mark_resolves_publix():
    from creative_automation import generate as _generate

    hit = _generate._resolve_retailer_mark("publix")
    assert hit is not None and hit.exists()


# ---- #198: SF + Park City string pins -------------------------------------- #

def test_sf_string_surfaces_target_only():
    markets = _store_strings()
    rec = markets["US-W-SF"]
    assert rec["retailer"] == "Target, Whole Foods, Safeway"
    assert retailers.surface_retailers(rec["retailer"], "US-W-SF", rec["place"]) == [
        "target"
    ]
    assert market_retailers(rec["retailer"]) == ["target"]


def test_park_city_string_surfaces_target_only():
    markets = _store_strings()
    rec = markets["US-MW-PARKCITY-84098"]
    assert rec["retailer"] == (
        "Target (Kimball Junction), Walmart (Kimball Junction), "
        "Smith's Food & Drug (Park City)"
    )
    assert retailers.surface_retailers(
        rec["retailer"], "US-MW-PARKCITY-84098", rec["place"]
    ) == ["target"]
    assert market_retailers(rec["retailer"]) == ["target"]


def test_walmart_never_becomes_a_chooser_card():
    # recorded decision: Walmart stays in market data strings only.
    assert retailers.normalize_retailer("walmart") is None
    assert retailers.normalize_retailer("Walmart (Kimball Junction)") is None
    assert "walmart" not in retailers.SUPPORTED_RETAILERS
    for field in (
        "Target, Walmart",
        "Target (Kimball Junction), Walmart (Kimball Junction), Smith's Food & Drug (Park City)",
        "Timberon General Store, Cloudcroft Mercantile, Alamogordo Walmart",
    ):
        assert "walmart" not in retailers.surface_retailers(field, "US-XX", "")
        assert "walmart" not in market_retailers(field)


def test_rural_market_gets_subscription_trailing():
    assert retailers.surface_retailers(
        "Oakley Farmers Market (Rodeo Grounds) + Kamas Valley Market — no commercial retail",
        "US-UT-KAMASVALLEY",
        "Kamas Valley rural",
    ) == ["subscription"]
