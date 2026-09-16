#!/usr/bin/env python3
"""Precompute the localization cache into DynamoDB kodiak-creatives-localization-memory.

Populates the 219 precomputed variants (73 markets x 3: en source + top 2 non-English per
market) so POST /localize resolves from the precomputed cache instead of calling live MT
every request. This is the WRITER side of the contract localize_memory.get_precomputed reads.

It reuses the existing seams verbatim — nothing about translation routing or key shape is
reimplemented here:
  - key shape  -> localize_memory.build_key(market, lang, text) / message_key(text)
  - routing    -> localize_service.{AMAZON_TRANSLATE_LANGS, BEDROCK_GAP_LANGS,
                   HUMAN_REQUIRED_LANGS, _amazon_translate, _bedrock_translate}

So a precomputed value matches exactly what live MT would produce, and the reader lands on
the same item. Language routing per market mirrors pipeline.py: each top_languages entry
carries translate_code or lang_code (prefer translate_code, fall back to lang_code), top 2.

Inputs (verified):
  data/localization/localization-table-seed.json  — DynamoDB-typed rows; market.S is the
      market id, message.S is the English SOURCE campaign message for that market.
  data/localization/market-languages.json          — { markets: [ { market,
      top_languages: [ { translate_code|lang_code, ... } ] } ] }; each market's targets.

Per (market, target_lang):
  - en (source)          -> store the source message verbatim, provider="precomputed"
  - AMAZON_TRANSLATE_LANGS -> _amazon_translate, provider="amazon-translate"
  - BEDROCK_GAP_LANGS      -> _bedrock_translate, provider="bedrock"
  - HUMAN_REQUIRED_LANGS (nv, zip) -> SKIP entirely (never machine translate, never fake)
  - en duplicates in top_languages -> skip (en is written once, from the seed)

Every written item carries: pk (S), sk (S), text (S = translated string), provider (S),
source (S = "dynamodb"), plus provenance market (S), lang (S), updated_at (S). text /
provider / source are the attributes get_precomputed reads.

Run (real — the anchor runs this AFTER the table + IAM deploy, not from CI):
  cd /home/bryanchasko/code/chasko-labs/creative-automation-pipeline
  AWS_PROFILE=bryanchasko-kiro uv run python scripts/precompute-localization.py

Flags:
  --dry-run        translate + print, write nothing
  --only-missing   get_item first, skip markets/langs already present
  --region REGION  DynamoDB region (default us-east-1)
  --limit N        process only the first N markets (test slice)
  --table NAME     override table name (default from localize_memory)

Idempotent: keys are deterministic, put_item overwrites cleanly. A single translate failure
logs and continues — one bad market never aborts the batch. Prints a summary at the end.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

from creative_automation import localize_memory
from creative_automation.localize_service import (
    AMAZON_TRANSLATE_LANGS,
    BEDROCK_GAP_LANGS,
    HUMAN_REQUIRED_LANGS,
    _amazon_translate,
    _bedrock_translate,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
SEED = REPO / "data" / "localization" / "localization-table-seed.json"
MARKET_LANGS = REPO / "data" / "localization" / "market-languages.json"

LOG = "[precompute]"


def _load_json(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))


def load_markets() -> list[dict]:
    """Join seed rows (market + source message) to market-languages top_languages.

    Returns [{market, message, langs: [lang_code, ...]}] where langs is the top 2 target
    codes for the market (en is handled separately from the seed message). Markets with no
    entry in market-languages still get their en source row written.
    """
    seed = _load_json(SEED)
    ml = _load_json(MARKET_LANGS)
    ml_markets = ml.get("markets", []) if isinstance(ml, dict) else []

    lang_index: dict[str, list[str]] = {}
    for m in ml_markets:
        market = m.get("market")
        if not market:
            continue
        # pipeline.py handling: prefer translate_code, fall back to lang_code, top 2
        codes = [
            lang.get("translate_code") or lang.get("lang_code")
            for lang in m.get("top_languages", [])
        ][:2]
        lang_index[market] = [c for c in codes if c]

    out: list[dict] = []
    for row in seed:
        market = row.get("market", {}).get("S")
        message = row.get("message", {}).get("S")
        if not market or not message:
            print(f"{LOG} skip seed row missing market/message: {row!r}", file=sys.stderr)
            continue
        out.append({"market": market, "message": message, "langs": lang_index.get(market, [])})
    return out


def translate_for(message: str, market: str, lang: str) -> tuple[str | None, str | None]:
    """Return (text, provider) for a (market, lang) using the SAME routing as live MT.

    en          -> (message verbatim, "precomputed")
    amazon lang -> (_amazon_translate, "amazon-translate")
    gap lang    -> (_bedrock_translate, "bedrock")
    otherwise   -> (None, None)  — unrouted; caller skips (human-required handled upstream)
    """
    if lang == "en":
        return message, "precomputed"
    if lang in AMAZON_TRANSLATE_LANGS:
        return _amazon_translate(message, lang), "amazon-translate"
    if lang in BEDROCK_GAP_LANGS:
        return _bedrock_translate(message, lang, market), "bedrock"
    return None, None


def _client(region: str):
    """DynamoDB client for writes. Import-guarded so --dry-run works with no boto3."""
    import boto3

    return boto3.client("dynamodb", region_name=region)


def _exists(client, table: str, key: dict[str, str]) -> bool:
    resp = client.get_item(
        TableName=table, Key={"pk": {"S": key["pk"]}, "sk": {"S": key["sk"]}}
    )
    return bool(resp.get("Item"))


def put(
    client, table: str, market: str, lang: str, source_message: str, text: str, provider: str
) -> None:
    """Write one precomputed item.

    The key hashes the SOURCE English message (what the reader passes to get_precomputed),
    not the translated text, so reads and writes land on the same item. source is always
    'dynamodb'.
    """
    key = localize_memory.build_key(market, lang, source_message)
    item = {
        "pk": {"S": key["pk"]},
        "sk": {"S": key["sk"]},
        "text": {"S": text},
        "provider": {"S": provider},
        "source": {"S": "dynamodb"},
        "market": {"S": market},
        "lang": {"S": lang},
        "updated_at": {"S": datetime.datetime.now(datetime.UTC).isoformat()},
    }
    client.put_item(TableName=table, Item=item)


def run(args) -> int:
    markets = load_markets()
    if args.limit is not None:
        markets = markets[: args.limit]

    table = args.table or localize_memory.LOCALIZATION_MEMORY_TABLE
    client = None if args.dry_run else _client(args.region)

    n_markets = 0
    n_written = 0
    n_skipped_human = 0
    n_skipped_en_dup = 0
    n_skipped_present = 0
    n_skipped_unrouted = 0
    n_failures = 0

    for m in markets:
        market, message, langs = m["market"], m["message"], m["langs"]
        n_markets += 1

        # variants to produce: en source first, then the market's top-2 targets
        variants = ["en", *langs]
        seen: set[str] = set()

        for lang in variants:
            # dedup: en is written once from the seed, so a top_languages "en" is a
            # duplicate; any repeated code within a market is also skipped
            if lang in seen:
                n_skipped_en_dup += 1
                continue
            seen.add(lang)

            # ethics guard — never machine translate nv/zip, never write a fake
            if lang in HUMAN_REQUIRED_LANGS:
                n_skipped_human += 1
                print(f"{LOG} skip human-required {market}/{lang} (never machine translated)")
                continue

            # --only-missing: get_item first, skip if the item already exists
            if args.only_missing and client is not None:
                key = localize_memory.build_key(market, lang, message)
                try:
                    if _exists(client, table, key):
                        n_skipped_present += 1
                        continue
                except Exception as e:  # noqa: BLE001 — presence check failure -> attempt write
                    print(f"{LOG} only-missing check failed {market}/{lang}: {e}", file=sys.stderr)

            try:
                text, provider = translate_for(message, market, lang)
            except Exception as e:  # noqa: BLE001 — one lang's failure never aborts the batch
                n_failures += 1
                print(f"{LOG} translate ERROR {market}/{lang}: {e}", file=sys.stderr)
                continue

            if provider is None:
                # unrouted language (not amazon, not gap, not human, not en) — skip cleanly
                n_skipped_unrouted += 1
                print(f"{LOG} skip unrouted lang {market}/{lang}")
                continue
            if not text:
                # translate transport miss — report and continue, do not write empty
                n_failures += 1
                print(f"{LOG} translate MISS {market}/{lang} (no text returned)", file=sys.stderr)
                continue

            if args.dry_run:
                key = localize_memory.build_key(market, lang, message)
                print(
                    f"{LOG} DRY {market}/{lang} provider={provider} "
                    f"pk={key['pk']} sk={key['sk']} text={text!r}"
                )
                n_written += 1
                continue

            try:
                put(client, table, market, lang, message, text, provider)
                n_written += 1
            except Exception as e:  # noqa: BLE001 — one put failure never aborts the batch
                n_failures += 1
                print(f"{LOG} put_item ERROR {market}/{lang}: {e}", file=sys.stderr)

    print(
        f"{LOG} SUMMARY table={table} region={args.region} dry_run={args.dry_run} "
        f"markets={n_markets} written={n_written} "
        f"skipped_human={n_skipped_human} skipped_en_dup={n_skipped_en_dup} "
        f"skipped_present={n_skipped_present} skipped_unrouted={n_skipped_unrouted} "
        f"failures={n_failures}"
    )
    # non-zero exit only on a total wipeout (nothing written and failures present); a few
    # per-market failures are expected-and-logged, not a batch abort
    return 1 if (n_written == 0 and n_failures > 0) else 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Precompute the localization cache into DynamoDB (reuses build_key + live MT routing)"
    )
    ap.add_argument("--dry-run", action="store_true", help="translate + print, write nothing")
    ap.add_argument(
        "--only-missing", action="store_true", help="get_item first, skip items already present"
    )
    ap.add_argument("--region", default="us-east-1", help="DynamoDB region (default us-east-1)")
    ap.add_argument("--limit", type=int, default=None, help="process only the first N markets")
    ap.add_argument(
        "--table", default=None, help="override table name (default from localize_memory)"
    )
    args = ap.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
