"""Sprint-1 runbook coverage — OFFLINE, cred-free.

Pins docs/sprints/sprint-1-runbook.md to the shipped code: one section per
shipped item, copy-only retailers named with their asset store toolkit pointers, and
overlay marks present on disk. If an item ships without a runbook section, or
a copy-only retailer gains pixels without enablement, this fails loudly.
"""
from __future__ import annotations

from pathlib import Path

from creative_automation import retailers

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "sprints" / "sprint-1-runbook.md"
LOGO_DIR = ROOT / "input_assets" / "retailer-logos"

# one anchor per shipped item at 9332fab (runbook headings, in order).
SHIPPED_ITEMS = (
    "staged-asset store seed_key",
    "campaign carousel",
    "engine-key contract",
    "similarity gate",
    "multi-theme combination",
    "brand_copy source",
    "season pairing",
    "retailer overlay wiring",
    "copy-only retailers",
    "voice enablement receipts",
    "five-tile preview pads",
    "retailer-frontier-pairs dedupe",
)


def _text() -> str:
    assert RUNBOOK.exists(), f"runbook missing: {RUNBOOK}"
    return RUNBOOK.read_text()


def test_runbook_covers_every_shipped_item():
    body = _text().lower()
    for item in SHIPPED_ITEMS:
        assert item.lower() in body, f"runbook missing item: {item}"


def test_runbook_records_copy_only_toolkit_pointers():
    body = _text()
    assert set(retailers.COPY_ONLY_RETAILERS) == {"kroger", "heb", "whole-foods"}
    for slug in retailers.COPY_ONLY_RETAILERS:
        asset_key = retailers.asset_key_for_retailer(slug)
        assert slug in body, f"runbook never names copy-only retailer: {slug}"
        assert asset_key in body, f"runbook missing toolkit pointer {asset_key}"
        # copy-only slugs must never be promised pixels in the runbook.
        assert retailers.resolve_retailer_logo(slug, logo_dir=LOGO_DIR) is None


def test_runbook_overlay_marks_present_on_disk():
    body = _text()
    assert set(retailers.OVERLAY_RETAILERS) == {"costco", "publix", "target", "walmart"}
    for slug in retailers.OVERLAY_RETAILERS:
        assert slug in body, f"runbook never names overlay retailer: {slug}"
        local = LOGO_DIR / f"{slug}.png"
        assert local.exists() and local.stat().st_size > 0, f"overlay mark missing: {local}"
