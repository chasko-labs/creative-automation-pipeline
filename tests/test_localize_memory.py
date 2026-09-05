"""kodiak-creatives-localization-memory key shape + offline guard.

The key shape is a contract the precompute writer and the /localize reader must share.
These tests pin it so a drift on either side is caught. No AWS is touched — the offline
guard returns None when boto3 / creds are absent.
"""
from creative_automation import localize_memory
from creative_automation.localize_memory import build_key, get_precomputed, message_key


def test_message_key_is_stable_and_whitespace_normalized():
    assert message_key("Nourishment for Today's Frontier") == message_key("  Nourishment for Today's Frontier  ")
    assert len(message_key("anything")) == 16


def test_build_key_shape():
    key = build_key("US-SW-LASCRUCES", "es", "Nourishment for Today's Frontier")
    assert key["pk"] == "MARKET#US-SW-LASCRUCES"
    assert key["sk"].startswith("LANG#es#MSG#")
    # sort key carries the stable message hash
    assert key["sk"].endswith(message_key("Nourishment for Today's Frontier"))


def test_get_precomputed_offline_returns_none(monkeypatch):
    # no creds -> table disabled -> None (documented offline fallback, never raises)
    monkeypatch.setattr(localize_memory, "_has_creds", lambda: False)
    assert get_precomputed("any text", "US-SW-LASCRUCES", "es") is None


def test_get_precomputed_hit_maps_item(monkeypatch):
    # simulate a live client returning a DynamoDB item; assert it maps to the response shape
    class _FakeClient:
        def get_item(self, TableName, Key):
            return {
                "Item": {
                    "text": {"S": "Nutrición para la Frontera de Hoy"},
                    "provider": {"S": "precomputed"},
                    "source": {"S": "dynamodb"},
                }
            }

    monkeypatch.setattr(localize_memory, "_client", lambda: _FakeClient())
    res = get_precomputed("Nourishment for Today's Frontier", "US-SW-LASCRUCES", "es")
    assert res == {
        "text": "Nutrición para la Frontera de Hoy",
        "provider": "precomputed",
        "source": "dynamodb",
    }


def test_get_precomputed_miss_returns_none(monkeypatch):
    class _FakeClient:
        def get_item(self, TableName, Key):
            return {}  # no Item

    monkeypatch.setattr(localize_memory, "_client", lambda: _FakeClient())
    assert get_precomputed("missing", "US-SW-LASCRUCES", "es") is None
