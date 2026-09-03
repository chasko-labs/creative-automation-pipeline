"""AgentCore Gateway tools (agentcore C2) — uniform tool registry over the done lookups.

Every assertion is offline and cred-free: the gateway composes already-built local units,
so these run with no S3, no boto3 creds, no model call. Atlanta (US-SE-ATL / 2026-09 /
muscadine grapes) is the reference market, the same fixture context_pack + recipe_card lean on.

Contract under test:
  - list_tools discovers all 7 tools, each with a JSON-schema input_schema and no handler leak
  - dispatch_tool returns {"ok": True, "result": ...} on success, {"ok": False, "error": ...} on failure
  - every dispatch result round-trips through json.dumps (no stray callables / Paths)
  - bad tool name and missing required arg both return ok:False WITHOUT raising
"""
import json

from creative_automation.gateway import TOOLS, dispatch_tool, list_tools

_EXPECTED_TOOLS = {
    "context_pack",
    "retailer_lookup",
    "dam_hero_lookup",
    "asset_library_browse",
    "recipe_card_plan",
    "monthly_ingredient",
    "run_campaign_tool",
}


def test_list_tools_returns_all_seven_with_schemas():
    tools = list_tools()
    assert len(tools) == 7
    assert {t["name"] for t in tools} == _EXPECTED_TOOLS
    for t in tools:
        assert t["description"]
        assert t["input_schema"]["type"] == "object"
        assert "properties" in t["input_schema"]
        # discovery payload must not leak the handler callable
        assert "handler" not in t
    # discovery output must be json-serializable
    assert json.loads(json.dumps({"tools": tools}))


def test_registry_and_discovery_stay_in_sync():
    assert {t["name"] for t in TOOLS} == _EXPECTED_TOOLS
    disc = {t["name"]: t["input_schema"] for t in list_tools()}
    for t in TOOLS:
        assert disc[t["name"]] is t["input_schema"]


def test_context_pack_dispatch_carries_retailers_and_ingredient():
    resp = dispatch_tool("context_pack", {"market": "US-SE-ATL", "month": "2026-09"})
    assert resp["ok"] is True
    result = resp["result"]
    assert result["market"] == "US-SE-ATL"
    assert "Publix" in result["retailers"]["retailers"]
    assert result["ingredient"]["ingredient"] == "muscadine grapes"
    # the to_prompt_text closure must be gone; prompt_text string must remain
    assert "to_prompt_text" not in result
    assert isinstance(result["prompt_text"], str) and result["prompt_text"]
    # whole result round-trips
    assert json.loads(json.dumps(resp))


def test_retailer_lookup_resolves_publix():
    resp = dispatch_tool("retailer_lookup", {"name": "publix"})
    assert resp["ok"] is True
    assert resp["result"]["name"] == "publix"
    # asset_path is a string or None — never a Path object leaking through
    assert resp["result"]["asset_path"] is None or isinstance(resp["result"]["asset_path"], str)
    assert json.loads(json.dumps(resp))


def test_monthly_ingredient_returns_muscadine_grapes():
    resp = dispatch_tool("monthly_ingredient", {"market": "US-SE-ATL", "month": "2026-09"})
    assert resp["ok"] is True
    result = resp["result"]
    assert result["ingredient"] == "muscadine grapes"
    assert result["has_pair"] is True
    assert isinstance(result["retailers"], list)
    assert json.loads(json.dumps(resp))


def test_dam_hero_lookup_offline_safe_returns_json():
    # unknown product with no local asset -> found False + note, never raises
    resp = dispatch_tool("dam_hero_lookup", {"product_id": "does-not-exist-xyz"})
    assert resp["ok"] is True
    assert resp["result"]["found"] is False
    assert resp["result"]["hero_path"] is None
    assert json.loads(json.dumps(resp))


def test_asset_library_browse_offline_safe_empty_list():
    resp = dispatch_tool("asset_library_browse", {"kind": "raster"})
    assert resp["ok"] is True
    result = resp["result"]
    assert isinstance(result["items"], list)
    # no creds in the offline test env -> no-s3 mode, empty list + note
    if not result["s3_enabled"]:
        assert result["items"] == []
        assert result["note"]
    assert json.loads(json.dumps(resp))


def test_recipe_card_plan_metadata_only_no_render():
    resp = dispatch_tool("recipe_card_plan", {"market": "US-SE-ATL", "month": "2026-09"})
    assert resp["ok"] is True
    result = resp["result"]
    assert result["ingredient"] == "muscadine grapes"
    assert result["rendered"] is False
    # default (no out_dir) path must not surface a rendered artifact path
    assert "card_path" not in result
    assert "text_blocks" in result and "safety" in result
    assert json.loads(json.dumps(resp))


def test_unknown_tool_name_returns_not_ok_without_raising():
    resp = dispatch_tool("no_such_tool", {"market": "US-SE-ATL"})
    assert resp["ok"] is False
    assert "unknown tool" in resp["error"]
    assert json.loads(json.dumps(resp))


def test_missing_required_arg_returns_not_ok():
    # retailer_lookup requires 'name'
    resp = dispatch_tool("retailer_lookup", {})
    assert resp["ok"] is False
    assert "missing required argument" in resp["error"]
    assert json.loads(json.dumps(resp))


def test_bad_arguments_type_returns_not_ok():
    resp = dispatch_tool("monthly_ingredient", "not-a-dict")  # type: ignore[arg-type]
    assert resp["ok"] is False
    assert "must be a dict" in resp["error"]


def test_every_tool_dispatch_round_trips_through_json_dumps():
    calls = {
        "context_pack": {"market": "US-SE-ATL", "month": "2026-09"},
        "retailer_lookup": {"name": "target"},
        "dam_hero_lookup": {"product_id": "power-cakes"},
        "asset_library_browse": {},
        "recipe_card_plan": {"market": "US-SE-ATL", "month": "2026-09"},
        "monthly_ingredient": {"market": "US-SE-ATL", "month": "2026-09"},
        "run_campaign_tool": {"market": "US-SE-ATL", "month": "2026-09", "render": False},
    }
    for name, args in calls.items():
        resp = dispatch_tool(name, args)
        # proof there are no stray callables/Paths in ANY tool result
        dumped = json.dumps(resp)
        assert json.loads(dumped) == resp
        assert resp["ok"] is True, f"{name} dispatch not ok: {resp.get('error')}"
