"""AgentCore Gateway tools (agentcore C2) — a uniform tool registry over the done lookups.

C2 exposes the already-built local lookups as uniform, agent-callable tools so a Bedrock
AgentCore agent (or any MCP client) can invoke them by name with a JSON argument object and
get a JSON-serializable result back. Per the backlog, the C-epic is the wrap layered on top
of the always-present local pipeline — this module builds NO new lookup logic. Every tool is a
thin wrapper that composes an existing unit (context_pack, retailers, dam, asset_library,
recipe_card, locales) or the C1 runtime handler; the wrapper's only jobs are shaping the input,
calling the done code, and sanitizing the output.

Contract (mirrors runtime.handle_campaign_request):

  dispatch_tool(name, arguments) -> {"ok": true, "result": <json-safe>}     # success
                                 -> {"ok": false, "error": "<message>"}     # bad name / bad args / caught error

  list_tools() -> [{"name", "description", "input_schema"}, ...]            # what an MCP client discovers

Sanitization reuses runtime._json_safe, so no callables (the context pack's to_prompt_text
closure), Paths, sets, or dataclasses leak into a payload — every dispatch result round-trips
through json.dumps. Tools that lean on S3/creds (asset_library_browse, dam_hero_lookup) degrade
to an empty/None result plus a note rather than raising, so the whole registry stays offline-safe.

Local shim:
    uv run python -m creative_automation.gateway list
    uv run python -m creative_automation.gateway call context_pack '{"market":"US-SE-ATL","month":"2026-09"}'
    echo '{"tool":"retailer_lookup","arguments":{"name":"publix"}}' | uv run python -m creative_automation.gateway
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import locales
from .asset_library import AssetKind, AssetLibrary
from .context_pack import build_context_pack
from .dam import find_hero_asset
from .recipe_card import build_recipe_card
from .retailers import resolve_retailer
from .runtime import _json_safe, handle_campaign_request

# default DAM root — same local fallback the pipeline uses when no S3 bucket is set
_ROOT = Path(__file__).parents[2]
_DEFAULT_DAM_ROOT = _ROOT / "input_assets"
_LIBRARY_PREFIX = "brands/kodiak/library/"


# --------------------------------------------------------------------------- #
# tool handlers — each composes ONE done unit and returns a plain dict.
# Sanitization to json-safe happens once in dispatch_tool, not per-handler.
# --------------------------------------------------------------------------- #
def _h_context_pack(args: dict) -> dict:
    """build_context_pack over a market key or full brief; strip the to_prompt_text callable."""
    brief_or_market = args.get("brief") or args.get("market")
    pack = build_context_pack(
        brief_or_market,
        month=args.get("month"),
        top_n_languages=int(args.get("top_n_languages", 2)),
        max_sample_prompts=int(args.get("max_sample_prompts", 3)),
    )
    # drop the closure explicitly; prompt_text (string) already carries the rendered form.
    # _json_safe would drop it anyway, but removing it here keeps the intent obvious.
    pack.pop("to_prompt_text", None)
    return pack


def _h_retailer_lookup(args: dict) -> dict:
    """resolve_retailer(name, store_address) -> flat lockup dict (Paths -> str via _json_safe)."""
    logo = resolve_retailer(args["name"], store_address=args.get("store_address"))
    return {
        "name": logo.name,
        "asset_path": str(logo.asset_path) if logo.asset_path else None,
        "svg_path": str(logo.svg_path),
        "png_path": str(logo.png_path),
        "svg_exists": logo.svg_exists,
        "png_exists": logo.png_exists,
        "store_address": logo.store_address,
        "missing": logo.missing,
        "notes": list(logo.notes),
    }


def _h_dam_hero_lookup(args: dict) -> dict:
    """find_hero_asset(product_id, dam_root) -> resolved hero path or null. Offline-safe.

    No S3 env set -> the S3 branch inside dam is skipped, so this is a pure local
    input_assets lookup. A miss returns hero_path None plus a note, never raises.
    """
    product_id = args["product_id"]
    dam_root = Path(args["dam_root"]) if args.get("dam_root") else _DEFAULT_DAM_ROOT
    hero = find_hero_asset(product_id, dam_root, explicit=args.get("explicit"))
    return {
        "product_id": product_id,
        "dam_root": str(dam_root),
        "hero_path": str(hero) if hero else None,
        "found": hero is not None,
        "note": None
        if hero is not None
        else f"no local hero under {dam_root / product_id}; drop hero.png there or set DAM_S3_BUCKET",
    }


def _h_asset_library_browse(args: dict) -> dict:
    """AssetLibrary.list_assets(kind) -> list of AssetRef dicts. Offline-safe.

    When boto3/creds are absent the library runs in no-s3 mode and list_assets returns
    an empty page — we surface that as an empty list plus a note, never a crash.
    """
    bucket = args.get("bucket") or "chasko-creative-dam-946179428633-us-east-1"
    kind_arg = args.get("kind")
    try:
        kind_enum = AssetKind(kind_arg) if kind_arg else None
    except ValueError:
        valid = [k.value for k in AssetKind]
        raise ValueError(f"unknown asset kind {kind_arg!r}; valid: {valid}")

    lib = AssetLibrary(bucket=bucket, prefix=_LIBRARY_PREFIX)
    # s3_enabled is True whenever a boto3 client object exists, even without creds. A live
    # list_objects_v2 can still fail on missing credentials / endpoint — that is the "backend
    # needs S3/creds and none present" case the tool must survive: degrade to empty + note,
    # never crash. A real ValueError (bad kind) is raised earlier, so this catch is backend-only.
    try:
        page = lib.list_assets(kind=kind_enum, limit=int(args.get("limit", 100)), cursor=args.get("cursor"))
    except Exception as e:  # noqa: BLE001 — backend unreachable degrades to empty list (NoCredentialsError, ClientError, etc)
        return {
            "items": [],
            "next_cursor": None,
            "count": 0,
            "s3_enabled": False,
            "note": f"asset library backend unreachable ({type(e).__name__}) — returning empty list",
        }
    items = [ref.to_dict() for ref in page.items]
    return {
        "items": items,
        "next_cursor": page.next_cursor,
        "count": len(items),
        "s3_enabled": lib.s3_enabled,
        "note": None
        if lib.s3_enabled
        else "asset library in no-s3 mode (boto3/creds unavailable) — returning empty list",
    }


def _h_recipe_card_plan(args: dict) -> dict:
    """build_recipe_card metadata (ingredient/recipe/text_blocks/safety). No PNG unless out_dir given.

    Default path returns the plan only. build_recipe_card renders a PNG when it resolves an
    ingredient, so to keep the default tool path render-free we only pass out_dir when the
    caller explicitly supplies one; otherwise we drop the card_path from the returned plan.
    """
    out_dir = args.get("out_dir")
    card = build_recipe_card(
        args["market"],
        month=args.get("month"),
        lang=args.get("lang", "en"),
        out_dir=out_dir,
    )
    if not out_dir:
        # metadata-only contract: do not surface a rendered artifact path in the plan
        card = {k: v for k, v in card.items() if k != "card_path"}
        card["rendered"] = False
    else:
        card["rendered"] = card.get("card_path") is not None
    return card


def _h_monthly_ingredient(args: dict) -> dict:
    """locales.resolve_this_month(market, month) -> {ingredient, frontier_sister, retailers}.

    resolve_this_month returns None for an unseeded market and carries a live FrontierPair
    dataclass under 'pair'; we shape a flat, json-safe dict and never leak the dataclass.
    """
    market = args["market"]
    resolved = locales.resolve_this_month(market, ym=args.get("month"))
    if resolved is None:
        return {
            "market": market,
            "month": args.get("month"),
            "ingredient": None,
            "frontier_sister": None,
            "retailers": [],
            "has_pair": False,
            "note": f"no retailer-frontier pair seeded for {market}",
        }
    return {
        "market": resolved["market"],
        "month": resolved["month"],
        "ingredient": resolved["ingredient"],
        "frontier_sister": resolved["frontier_sister"],
        "farmers_market_url": resolved.get("farmers_market_url"),
        "retailers": list(resolved["retailers"]),
        "has_pair": True,
    }


def _h_run_campaign_tool(args: dict) -> dict:
    """Thin passthrough to the C1 handler — runs a full campaign through the gateway.

    handle_campaign_request already validates + sanitizes and returns {"ok": ...}. We hand
    its whole payload back as the tool result so the gateway can drive a full campaign too.
    """
    event = args.get("event") if isinstance(args.get("event"), dict) else args
    return handle_campaign_request(event)


# --------------------------------------------------------------------------- #
# TOOLS registry — name / description / input_schema (JSON Schema) / handler / required
# input_schema mirrors the MCP manifest's inputSchema exactly (.agents/mcp-kodiak-gateway.json).
# --------------------------------------------------------------------------- #
TOOLS: list[dict[str, Any]] = [
    {
        "name": "context_pack",
        "description": (
            "Build the offline RAG context pack for a market or full brief — retailers, "
            "frontier sister, this-month local ingredient, dialect traps, nearest visual "
            "cluster, sample Kodiak copy, brand rules. Composes context_pack.build_context_pack; "
            "the to_prompt_text closure is stripped, prompt_text string is kept."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "Market key e.g. US-SE-ATL"},
                "brief": {"type": "object", "description": "Full CampaignBrief dict (alternative to market)"},
                "month": {"type": "string", "description": "ISO YYYY-MM; defaults to current month"},
                "top_n_languages": {"type": "integer", "default": 2},
                "max_sample_prompts": {"type": "integer", "default": 3},
            },
        },
        "required": [],  # market OR brief — checked in handler via build_context_pack's own guard
        "handler": _h_context_pack,
    },
    {
        "name": "retailer_lookup",
        "description": (
            "Resolve a retailer name to its logo lockup asset (SVG preferred, PNG fallback) plus "
            "an optional local store address for the overlay. Reports which files are present/missing "
            "— never fabricates a logo. Composes retailers.resolve_retailer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "costco, publix, or target"},
                "store_address": {"type": "string", "description": "Optional store address string for the lockup"},
            },
            "required": ["name"],
        },
        "required": ["name"],
        "handler": _h_retailer_lookup,
    },
    {
        "name": "dam_hero_lookup",
        "description": (
            "Resolve a product hero image path. S3-first when DAM_S3_BUCKET is set, else pure local "
            "input_assets/<product_id>/hero.* fallback. Offline-safe: a miss returns hero_path null + "
            "a note, never raises. Composes dam.find_hero_asset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "e.g. power-cakes, bear-bites, oatmeal-cup"},
                "dam_root": {"type": "string", "description": "DAM root dir; default input_assets"},
                "explicit": {"type": "string", "description": "Explicit local or s3:// path override"},
            },
            "required": ["product_id"],
        },
        "required": ["product_id"],
        "handler": _h_dam_hero_lookup,
    },
    {
        "name": "asset_library_browse",
        "description": (
            "Browse the DAM asset library (optionally filtered by kind: raster/vector/doc/copy) and "
            "return AssetRef dicts. Offline-safe: with no S3/creds the library runs in no-s3 mode and "
            "returns an empty list + a note. Composes asset_library.AssetLibrary.list_assets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["raster", "vector", "doc", "copy"]},
                "limit": {"type": "integer", "default": 100},
                "cursor": {"type": "string", "description": "Opaque pagination cursor"},
                "bucket": {"type": "string", "description": "Override DAM bucket"},
            },
        },
        "required": [],
        "handler": _h_asset_library_browse,
    },
    {
        "name": "recipe_card_plan",
        "description": (
            "Plan a monthly recipe card for a market — the metadata (ingredient, recipe, text_blocks, "
            "safety) with NO PNG render by default. Pass out_dir to also render the card PNG. Ingredient "
            "is never fabricated. Composes recipe_card.build_recipe_card."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "Market key e.g. US-SE-ATL"},
                "month": {"type": "string", "description": "ISO YYYY-MM; defaults to current month"},
                "lang": {"type": "string", "default": "en"},
                "out_dir": {"type": "string", "description": "If set, also render the card PNG here"},
            },
            "required": ["market"],
        },
        "required": ["market"],
        "handler": _h_recipe_card_plan,
    },
    {
        "name": "monthly_ingredient",
        "description": (
            "Resolve a market + month to its in-season local ingredient, frontier sister place, and "
            "retailer set. Never fabricates — an unseeded market returns ingredient null + a note. "
            "Composes locales.resolve_this_month."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "description": "Market key e.g. US-SE-ATL"},
                "month": {"type": "string", "description": "ISO YYYY-MM; defaults to current month"},
            },
            "required": ["market"],
        },
        "required": ["market"],
        "handler": _h_monthly_ingredient,
    },
    {
        "name": "run_campaign_tool",
        "description": (
            "Run a full campaign through the C1 runtime handler. Pass an event dict (market or brief, "
            "optional month/platforms/languages/render) either flat or under 'event'. Returns the C1 "
            "payload with its own ok flag. Thin passthrough to runtime.handle_campaign_request."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event": {"type": "object", "description": "Full C1 event dict (alternative to flat args)"},
                "market": {"type": "string", "description": "Market key (flat form)"},
                "brief": {"type": "object", "description": "Full brief dict (flat form)"},
                "month": {"type": "string"},
                "render": {"type": "boolean", "default": False},
            },
        },
        "required": [],
        "handler": _h_run_campaign_tool,
    },
]

# name -> tool dict, built once
_TOOLS_BY_NAME: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOLS}


def list_tools() -> list[dict[str, Any]]:
    """Return the discoverable tool definitions (name + description + input_schema).

    This is what an AgentCore agent / MCP client sees at discovery time — the handler
    callable is intentionally omitted so the result is JSON-serializable.
    """
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in TOOLS
    ]


def dispatch_tool(name: str, arguments: dict | None = None) -> dict:
    """Validate + invoke a tool by name; return {"ok", "result"} or {"ok": False, "error"}.

    Defensive by contract (mirrors runtime.handle_campaign_request): an unknown tool name,
    non-dict arguments, a missing required arg, or any error raised inside the handler all
    resolve to {"ok": false, "error": ...} — this function never raises. The result is passed
    through _json_safe so it always round-trips through json.dumps (no callables/Paths leak).
    """
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        known = ", ".join(sorted(_TOOLS_BY_NAME))
        return {"ok": False, "error": f"unknown tool {name!r}; known tools: {known}"}

    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return {"ok": False, "error": f"arguments must be a dict, got {type(arguments).__name__}"}

    missing = [key for key in tool.get("required", []) if key not in arguments or arguments[key] in (None, "")]
    if missing:
        return {"ok": False, "error": f"missing required argument(s) for {name!r}: {', '.join(missing)}"}

    try:
        result = tool["handler"](arguments)
    except (ValueError, TypeError, KeyError) as e:
        return {"ok": False, "error": f"{name} failed: {e}"}
    except Exception as e:  # noqa: BLE001 — last-resort guard; a tool must never crash the gateway
        return {"ok": False, "error": f"{name} raised {type(e).__name__}: {e}"}

    return {"ok": True, "result": _json_safe(result)}


# --------------------------------------------------------------------------- #
# __main__ shim — the local stdio/JSON convention for MCP-style use.
#   list                       -> print list_tools()
#   call <name> <json-args>    -> print dispatch_tool(name, args)
#   (no argv, stdin has JSON)  -> read {"tool": ..., "arguments": ...} from stdin, dispatch
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # no args: read a single JSON request from stdin (the simple stdio convention)
    if not argv:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"ok": False, "error": "usage: gateway list | call <name> <json> | echo '{\"tool\":..,\"arguments\":..}' | gateway"}))
            return 1
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"invalid JSON request: {e}"}))
            return 1
        response = dispatch_tool(req.get("tool", ""), req.get("arguments") or {})
        print(json.dumps(response, indent=2))
        return 0 if response.get("ok") else 1

    cmd = argv[0]
    if cmd == "list":
        print(json.dumps({"tools": list_tools()}, indent=2))
        return 0

    if cmd == "call":
        if len(argv) < 2:
            print(json.dumps({"ok": False, "error": "usage: gateway call <name> '<json args>'"}))
            return 1
        name = argv[1]
        args: dict = {}
        if len(argv) >= 3 and argv[2].strip():
            try:
                args = json.loads(argv[2])
            except json.JSONDecodeError as e:
                print(json.dumps({"ok": False, "error": f"invalid JSON args: {e}"}))
                return 1
        response = dispatch_tool(name, args)
        print(json.dumps(response, indent=2))
        return 0 if response.get("ok") else 1

    print(json.dumps({"ok": False, "error": f"unknown command {cmd!r}; use: list | call"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
