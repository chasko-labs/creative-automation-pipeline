"""Military language quarantine — warm agricultural frontier only."""
import src.creative_automation.generate as g

def test_sanitize_strips_listen_up():
    out = g._sanitize_military_headline("Listen Up, Kid. Summer In San Diego Peaches")
    assert out is not None
    assert "listen" not in out.lower()
    assert "Summer" in out

def test_sanitize_preserves_clean():
    out = g._sanitize_military_headline("Summer Peachy Flapjack Magic In San Diego")
    assert out == "Summer Peachy Flapjack Magic In San Diego"

def test_sanitize_none_on_unrecoverable():
    out = g._sanitize_military_headline("Attention Recruits Fall Harvest")
    assert out is None

def test_sanitize_recruit_triggers_none_or_stripped():
    out = g._sanitize_military_headline("Listen Up, Recruit! Fall Harvest Apples")
    # either stripped clean or None, but never contains recruit/listen
    if out is not None:
        assert "recruit" not in out.lower()
        assert "listen" not in out.lower()

def test_headline_for_filters_military():
    # Direct call to _headline_for with mocked director returning military line should fall through
    # We test the sanitizer directly; full pipeline test would need Bedrock mock
    assert g._sanitize_military_headline("ALRIGHT, LISTEN UP, KID. PEACHES ARE THE ONLY THING") is None or "LISTEN" not in (g._sanitize_military_headline("ALRIGHT, LISTEN UP, KID. PEACHES ARE THE ONLY THING") or "").upper()
