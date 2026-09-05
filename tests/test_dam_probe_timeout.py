"""Bounded S3 probe fan-out — the 503 repair (unmapped-SKU power-cakes).

Live root cause: an unmapped SKU misses every S3 key, and the seed/packshot probe
runs ~50 SERIAL S3 HeadObject/GetObject misses with a no-timeout boto3 client, so the
Lambda runs ~37s and API Gateway 503s at the 30s edge. This test proves the probe
phase is now BOUNDED: with an always-miss S3 (monkeypatched _s3_download -> False), the
loop-level deadline (DAM_PROBE_FLOOR_MS) abandons the fan-out mid-flight rather than
walking all ~50 candidates, and generate_hero still returns rung C/D real pixels well
inside the soft budget. No AWS is touched — the S3 primitives are monkeypatched.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import dam
from creative_automation import generate as generate_mod


def _distinct_colors(path: Path) -> int:
    with Image.open(path) as img:
        colors = img.convert("RGB").getcolors(maxcolors=200000)
    return len(colors) if colors else 1


def test_unmapped_sku_probe_is_bounded_and_lands_rung_cd(tmp_path, monkeypatch):
    # S3 is "enabled" (bucket set) so the fan-out is entered, but every key misses.
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")
    # count every S3 candidate attempt; always-miss so the loop keeps trying.
    miss_calls = {"n": 0}

    def _always_miss(bucket, key, dest):
        miss_calls["n"] += 1
        return False

    monkeypatch.setattr(dam, "_s3_download", _always_miss)
    # step-2 list is also an always-miss (no Contents) so the product-asset fan-out
    # cannot resolve via listing either.
    monkeypatch.setattr(
        dam, "_s3_client",
        lambda: type("C", (), {"list_objects_v2": lambda self, **k: {"Contents": []}})(),
    )
    # no theme / sku-mapped seed -> the ladder reaches the disk/S3 fan-out probe.
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_dam_photo", lambda pid: None)

    # SQUEEZE the loop floor up to the full soft budget so _deadline_exceeded fires on
    # the FIRST probe iteration — this is the "budget already thin" state that must abandon
    # the fan-out immediately instead of walking all ASSET_EXTS x HERO_NAMES candidates.
    monkeypatch.setattr(dam, "DAM_PROBE_FLOOR_MS", 999999)

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )

    # the probe abandoned mid-fan-out: it did NOT walk the full ~50-key candidate set.
    # hero-real/hero x 4 exts (fetch_hero_to_tmp) + HERO_NAMES x ASSET_EXTS (product asset)
    # would be dozens of _s3_download calls; the deadline floor caps it at 0.
    assert miss_calls["n"] == 0, f"probe did not abandon — {miss_calls['n']} S3 misses ran"

    # never a 503: the ladder still returns real pixels on rung C (if a seed) or D (floor).
    assert result.exists()
    assert prov["rung"] in ("C", "D")
    assert _distinct_colors(result) > 5  # real Kodiak pixels, not a flat error fill
    assert "503" not in str(source)
    # returned inside the soft budget — the whole point of the repair.
    assert prov["elapsed_ms"] <= generate_mod.GENERATE_SOFT_BUDGET_MS
