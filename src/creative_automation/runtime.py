"""AgentCore runtime wrap (agentcore C1) — the invocable entry surface.

C1 is the hosting seam, not the hosting itself. This module exposes run_campaign (D1)
as a clean event-in / JSON-out handler so it can LATER be hosted on Bedrock AgentCore
Runtime (or a Lambda) without touching the campaign logic. Per the backlog, the C-epic
is parallel and NOT on the critical path: the local pipeline is the always-present live
fallback, and AgentCore hosting (Runtime / Gateway / Memory / Browser / Identity) is the
planned wrap layered on top — none of that is built here. This is only the invocable
seam plus its local fallback.

Event shape (what an AgentCore Runtime / Lambda would pass in):

    {
      "market": "US-SE-ATL",        # or "brief": {<full brief dict>}
      "month": "2026-09",           # optional ISO YYYY-MM
      "platforms": {...} | [...],   # optional; default STANDARD_PLATFORMS
      "languages": ["en", ...],     # optional; default EN + market top-N
      "render": false               # optional; default false (offline-safe, no Nova call)
    }

Response shape (always JSON-serializable — json.dumps must succeed):

    {
      "ok": true,
      "campaign": {...}, "assets": [...], "recipe_cards": [...],
      "lockups": [...], "summary": {...}
    }
    # on a bad event:
    {"ok": false, "error": "<message>"}

The response is sanitized so no stray callables (e.g. the context pack's to_prompt_text)
survive into the payload — prompt text is returned as a string, never a lambda.

Local fallback: `python -m creative_automation.runtime '{"market":"US-SE-ATL"}'`.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from .campaign import run_campaign


def _json_safe(value: Any) -> Any:
    """Recursively drop anything json.dumps cannot serialize.

    Callables (the context pack's to_prompt_text closure and friends) are dropped
    entirely; Paths and other non-primitives fall back to str(). Dicts/lists recurse.
    This is the guarantee behind the "no stray callables in the response" contract.
    """
    if callable(value):
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if callable(v):
                continue  # drop callable-valued keys outright (to_prompt_text etc)
            out[str(k)] = _json_safe(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Path, set, or any other object -> string form
    return str(value)


def handle_campaign_request(event: dict) -> dict:
    """Validate an incoming event, run the campaign, return a JSON-serializable dict.

    This is the shape an AgentCore Runtime / Lambda invokes. Validation is defensive:
    a bad event yields {"ok": false, "error": ...} rather than raising, so the hosting
    surface can return a clean error response.
    """
    if not isinstance(event, dict):
        return {"ok": False, "error": f"event must be a dict, got {type(event).__name__}"}

    brief = event.get("brief") or event.get("market") or event.get("target_market")
    if not brief:
        return {"ok": False, "error": "event must carry a 'brief' dict or a 'market' key"}

    month = event.get("month")
    platforms = event.get("platforms")
    languages = event.get("languages")
    render = bool(event.get("render", False))
    out_dir = event.get("out_dir")

    try:
        result = run_campaign(
            brief,
            out_dir=out_dir,
            month=month,
            platforms=platforms,
            languages=languages,
            render=render,
        )
    except (ValueError, TypeError) as e:
        return {"ok": False, "error": str(e)}

    payload = _json_safe(result)
    payload["ok"] = True
    return payload


def main(argv: list[str] | None = None) -> int:
    """CLI shim — the local fallback. Reads one JSON event arg, prints the response.

    Usage:
        python -m creative_automation.runtime '{"market":"US-SE-ATL","month":"2026-09"}'
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            json.dumps(
                {"ok": False, "error": "usage: python -m creative_automation.runtime '<json event>'"}
            )
        )
        return 1
    try:
        event = json.loads(argv[0])
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid JSON event: {e}"}))
        return 1

    response = handle_campaign_request(event)
    # json.dumps here is also the live proof the response carries no stray callables
    print(json.dumps(response, indent=2))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
