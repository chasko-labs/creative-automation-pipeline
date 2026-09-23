"""Recipe catalog enrichment contract.

Records enriched from brand pages (source == 'brand_json_ld') must carry the
full verbatim set: a dish name, non-empty ingredients and directions, and the
brand page they were taken from. This pins the stub-enrichment work so a later
edit cannot silently strip an enriched record back to a stub.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "recipes" / "kodiak-recipes.json"


def _catalog():
    return json.loads(CATALOG.read_text())


def test_brand_enriched_records_carry_verbatim_fields():
    recs = _catalog()
    enriched = [r for r in recs if r.get("source") == "brand_json_ld"]
    assert enriched, "enrichment backlog lost all brand_json_ld records"
    for r in enriched:
        rid = r.get("id")
        assert (r.get("dish") or "").strip(), f"{rid}: enriched record lost dish"
        assert r.get("ingredients"), f"{rid}: enriched record lost ingredients"
        assert (r.get("directions") or "").strip(), f"{rid}: enriched record lost directions"
        page = r.get("kodiak_page") or ""
        assert page.startswith("https://kodiakcakes.com/blogs/recipes/"), (
            f"{rid}: enriched record lost brand page link"
        )
