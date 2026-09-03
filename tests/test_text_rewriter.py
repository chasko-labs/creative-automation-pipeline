"""Nova text rewriter (agentcore B1) — offline path.

No AWS credentials in CI, so every test exercises the mock fallback: the rewrite chain
still runs context_pack -> (no Nova) -> dialect swap -> safety, and the returned text is
always safe. Atlanta (US-SE-ATL) is the reference market. The fr-VT dialect trap
(myrtilles -> bleuets) is the highest-value assertion — it proves the dialect hop fires
after the rewrite and before safety.
"""
from creative_automation import text_rewriter
from creative_automation.text_rewriter import rewrite_campaign_copy, rewrite_headline


def test_atlanta_rewrite_returns_safe_on_brand_string():
    result = rewrite_headline(
        "Protein-packed whole grains for your family's frontier.",
        "US-SE-ATL",
        product={"name": "Buttermilk Power Cakes", "description": "flapjack waffle mix"},
        month="2026-09",
    )
    assert result["text"]
    assert result["safety"]["clean"] is True
    # offline CI -> mock source, base message preserved
    assert result["source"] == "mock"


def test_profanity_base_comes_back_redacted():
    result = rewrite_headline(
        "This damn breakfast is the best, no bullshit.",
        "US-SE-ATL",
        month="2026-09",
    )
    # never return unsafe text — flagged terms are redacted and the result is clean
    assert "damn" not in result["text"].lower()
    assert "bullshit" not in result["text"].lower()
    assert "[redacted]" in result["text"]
    assert result["safety"]["clean"] is True


def test_political_base_comes_back_redacted():
    result = rewrite_headline(
        "Vote for the best pancakes this election.",
        "US-SE-ATL",
        month="2026-09",
    )
    assert "vote for" not in result["text"].lower()
    assert result["safety"]["clean"] is True


def test_fr_vt_rewrite_swaps_myrtilles_to_bleuets():
    # force the mock path so the base text carries the standard-French term unchanged,
    # then assert the dialect hop swaps it to the Quebec/VT local form
    result = rewrite_headline(
        "Petit-déjeuner aux myrtilles pour la frontière.",
        "US-NE-BURLINGTON",
        lang="fr",
        region="US-VT",
        month="2026-09",
    )
    assert "bleuets" in result["text"]
    assert "myrtilles" not in result["text"]
    swaps = {(s["from"], s["to"]) for s in result["dialect_applied"]}
    assert ("myrtilles", "bleuets") in swaps
    assert result["safety"]["clean"] is True


def test_offline_fallback_with_no_creds(monkeypatch):
    # simulate a no-credentials environment: the chain must still return the base text
    monkeypatch.setattr(text_rewriter, "_has_creds", lambda: False)
    base = "Fuel your morning with whole grains."
    result = rewrite_headline(base, "US-SE-ATL", month="2026-09")
    assert result["source"] == "mock"
    assert result["text"] == base
    assert result["safety"]["clean"] is True


def test_english_rewrite_records_no_dialect_swaps():
    result = rewrite_headline("Keep it wild.", "US-SE-ATL", lang="en", month="2026-09")
    assert result["dialect_applied"] == []


def test_rewrite_campaign_copy_per_language():
    brief = {
        "market": "US-SE-ATL",
        "campaign_message": "Protein-packed whole grains for your frontier.",
        "products": [{"name": "Buttermilk Power Cakes", "description": "flapjack waffle mix"}],
    }
    out = rewrite_campaign_copy(brief, ["en", "es"], month="2026-09")
    assert set(out.keys()) == {"en", "es"}
    for lang, res in out.items():
        assert res["text"]
        assert res["safety"]["clean"] is True
