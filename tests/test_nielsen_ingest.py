"""Nielsen ingest writes for real: ok:true means persisted, table-disabled
means ok:false, transport failure raises (route reports 500)."""

from __future__ import annotations

from creative_automation import localize_memory


class _FakeTable:
    def __init__(self, fail: bool = False) -> None:
        self.items: list[dict] = []
        self.fail = fail

    def put_item(self, TableName: str, Item: dict) -> dict:
        if self.fail:
            raise RuntimeError("boom")
        assert TableName == localize_memory.LOCALIZATION_MEMORY_TABLE
        self.items.append(Item)
        return {}


def test_record_persists_event(monkeypatch) -> None:
    fake = _FakeTable()
    monkeypatch.setattr(localize_memory, "_client", lambda: fake)
    out = localize_memory.record_nielsen_event(
        "US-SE-ATL", "30301", {"market": "US-SE-ATL", "sales": 7}
    )
    assert out is not None and out["persisted"] is True
    assert len(fake.items) == 1
    item = fake.items[0]
    assert item["pk"] == {"S": "MARKET#US-SE-ATL"}
    assert item["zip"] == {"S": "30301"}
    assert item["source"] == {"S": "nielsen-ingest"}


def test_record_none_when_table_disabled(monkeypatch) -> None:
    monkeypatch.setattr(localize_memory, "_client", lambda: None)
    assert (
        localize_memory.record_nielsen_event("US-SE-ATL", "30301", {"x": 1})
        is None
    )


def test_record_raises_on_transport_failure(monkeypatch) -> None:
    monkeypatch.setattr(localize_memory, "_client", lambda: _FakeTable(fail=True))
    try:
        localize_memory.record_nielsen_event("US-SE-ATL", "30301", {"x": 1})
    except RuntimeError:
        return
    raise AssertionError("transport failure must raise, never false-ok")
