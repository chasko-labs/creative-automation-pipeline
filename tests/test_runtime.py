"""AgentCore runtime wrap tests (agentcore C1) — the invocable seam + local fallback.

Offline + deterministic: no creds, no Nova call (render defaults off). The core contract
is that handle_campaign_request returns a JSON-serializable dict — json.dumps must
succeed with no stray callables (the context pack's to_prompt_text closure must not leak).
"""
import json

from creative_automation.runtime import handle_campaign_request, main


def _atlanta_event() -> dict:
    return {
        "brief": {
            "market": "US-SE-ATL",
            "campaign_message": "Protein-packed whole grains for your frontier.",
            "products": [
                {"id": "power-cakes", "name": "Buttermilk Power Cakes", "description": "flapjack waffle mix"}
            ],
            "retailers": ["Publix"],
        },
        "month": "2026-09",
    }


def test_handle_campaign_request_returns_json_serializable_dict():
    resp = handle_campaign_request(_atlanta_event())
    assert resp["ok"] is True
    # the hard contract: the whole response round-trips through json.dumps with no
    # stray callables (to_prompt_text etc must have been stripped)
    dumped = json.dumps(resp)
    assert isinstance(dumped, str) and dumped
    # and it carries the campaign summary
    assert resp["campaign"]["market"] == "US-SE-ATL"
    assert resp["summary"]["asset_count"] > 0
    assert "assets" in resp and resp["assets"]
    assert "recipe_cards" in resp
    assert "lockups" in resp


def test_handle_campaign_request_no_callables_anywhere():
    resp = handle_campaign_request(_atlanta_event())

    def _assert_no_callables(node):
        if isinstance(node, dict):
            for k, v in node.items():
                assert not callable(v), f"callable leaked at key {k}"
                _assert_no_callables(v)
        elif isinstance(node, list):
            for v in node:
                _assert_no_callables(v)

    _assert_no_callables(resp)


def test_handle_campaign_request_accepts_full_brief_dict():
    event = {
        "brief": {
            "market": "US-SE-ATL",
            "campaign_message": "Protein-packed whole grains for your frontier.",
            "products": [
                {"id": "power-cakes", "name": "Buttermilk Power Cakes", "description": "flapjack waffle mix"}
            ],
            "retailers": ["Publix"],
        },
        "month": "2026-09",
    }
    resp = handle_campaign_request(event)
    assert resp["ok"] is True
    json.dumps(resp)  # must not raise
    assert resp["campaign"]["ingredient"] == "muscadine grapes"


def test_handle_campaign_request_bad_event_returns_error_not_raise():
    assert handle_campaign_request({})["ok"] is False
    assert handle_campaign_request("not-a-dict")["ok"] is False  # type: ignore[arg-type]
    # unknown market degrades inside run_campaign but still serializes ok=True
    resp = handle_campaign_request({"market": "US-XX-NOWHERE"})
    assert resp["ok"] is True
    json.dumps(resp)


def test_runtime_main_cli_shim(capsys):
    rc = main([json.dumps({"market": "US-SE-ATL", "month": "2026-09"})])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)  # the printed output is valid JSON
    assert payload["ok"] is True
    assert payload["campaign"]["market"] == "US-SE-ATL"


def test_runtime_main_bad_json_returns_nonzero(capsys):
    rc = main(["{not valid json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
