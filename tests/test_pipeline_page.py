import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "web" / "kodiak-posts-for-todays-frontier" / "pipeline.html"
FLAVOR = ROOT / "data" / "localization" / "local-flavor.json"


def _grid_region() -> str:
    text = PAGE.read_text(encoding="utf-8")
    m = re.search(r"GRID-GENERATED-START -->(.*?)<!-- GRID-GENERATED-END", text, re.S)
    assert m, "grid markers missing from pipeline.html"
    return m.group(1)


def test_full_grid_covers_every_market():
    import html as _html

    markets = {
        c: m
        for c, m in json.loads(FLAVOR.read_text(encoding="utf-8"))["markets"].items()
        if not c.startswith("_")
    }
    region = _html.unescape(_grid_region())
    rows = re.findall(r"<tr><td><b>(.*?)</b>", region)
    assert len(rows) == len(markets), f"{len(rows)} rows vs {len(markets)} markets"
    for code, m in markets.items():
        assert m["place"] in region, f"market missing from grid: {code}"


def test_contract_sample_rows_intact():
    text = PAGE.read_text(encoding="utf-8")
    for snippet in [
        "<b>Las Cruces NM</b></td><td>&mdash;</td><td>Hatch green chile (Aug+)</td>",
        "<b>Sandersville GA</b></td><td>&mdash;</td><td>Georgia peaches</td>",
    ]:
        assert snippet in text, f"contract sample changed: {snippet[:40]}"


def test_schema_card_names_sources():
    text = PAGE.read_text(encoding="utf-8")
    for snippet in [
        "data/localization/local-flavor.json",
        "data/recipes/kodiak-recipes.json",
        "kodiak-creatives-localization-memory",
        "kodiak-creatives-retail-network",
        "DAM_S3_BUCKET",
    ]:
        assert snippet in text, f"schema card missing: {snippet}"
