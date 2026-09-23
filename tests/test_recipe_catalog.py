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
        steps = r.get("instructions") or []
        assert isinstance(steps, list) and len(steps) >= 2, (
            f"{rid}: enriched record lost serving-shape instructions list "
            "(cards read instructions, not directions)"
        )
        page = r.get("kodiak_page") or ""
        assert page.startswith("https://kodiakcakes.com/blogs/recipes/"), (
            f"{rid}: enriched record lost brand page link"
        )


def test_season_served_records_carry_course():
    # QA sweep: every record the season tables can serve must carry a course
    # so browse/filter never renders a blank (caramel-apple-pie served two
    # October markets courseless until backfilled).
    from creative_automation import season_pairing as sp

    recs = {r.get("id"): r for r in _catalog()}
    served = {sp.DEFAULT_PAIRING["recipe_id"]}
    served.update(e["recipe_id"] for e in sp.SEASON_RECIPE_PAIRINGS.values())
    served.update(e["recipe_id"] for e in sp.HOLIDAY_RECIPE_PAIRINGS.values())
    missing = sorted(rid for rid in served if not (recs.get(rid) or {}).get("course"))
    assert not missing, f"season-served records lack course: {missing}"
