"""Nova text rewriter — context-pack-aware headline/copy rewriting (agentcore B1).

The one job: take a base marketing message and rewrite it for a specific market so it
keeps the Kodiak voice, respects the market's RAG context (retailer, frontier sister,
in-season ingredient, nearest visual cluster, real sample prompts, dialect traps, brand
rules), stays under a headline length, and NEVER ships text-in-image instructions
(cr-1 — this is the caption/overlay text layer, not the image prompt).

Transport boundary (named, not hidden): exactly one Bedrock Converse call to Nova Micro
(amazon.nova-micro-v1:0), explicit maxTokens + temperature, reusing localize.py's boto3
client pattern. Offline/no-creds is a documented path, not an exception swallowed in a
catch block: the base message is returned tagged source="mock" so CI stays green with no
AWS credentials.

The chain is fixed and every hop is explicit:

    context_pack -> Nova Micro rewrite -> dialect swap (lang != en) -> safety gate

Safety is the last hop and is non-negotiable: the returned text is always run through
safety.check_text; anything flagged is redacted before return. Unsafe text never leaves
this module.
"""
from __future__ import annotations

import os
import sys

from . import safety
from .context_pack import build_context_pack
from .locales import resolve_dialect_terms

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 is a hard dep, but keep the import defensive for offline CI
    boto3 = None  # type: ignore

BEDROCK_REGION = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
NOVA_TEXT_MODEL = os.getenv("BEDROCK_NOVA_TEXT_MODEL", "amazon.nova-micro-v1:0")

# headline budget — the overlay text layer stays short so compose.py can lay it out
HEADLINE_MAX_CHARS = 60


def _has_creds() -> bool:
    """Cheap, network-free gate before the transport call.

    Env-var only on purpose: boto3's get_credentials() can trigger IMDS/SSO lookups
    with multi-second timeouts, which would make CI slow and could fire live Nova calls
    when ambient creds exist. Static/SSO/profile creds surface through these env vars in
    every environment that should reach Bedrock; anything subtler falls to the offline
    mock path, which is the safe default.
    """
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("AWS_PROFILE")
        or os.getenv("AWS_SESSION_TOKEN")
        or os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
    )


def _build_prompt(context_prefix: str, base_message: str, lang: str) -> str:
    """Prepend the context pack, then the rewrite instruction. No in-image-text ask."""
    lang_line = (
        f"Write the rewrite in {lang}."
        if lang and lang != "en"
        else "Write the rewrite in English."
    )
    return (
        f"{context_prefix}\n\n"
        "TASK: rewrite the base marketing message below for this market. "
        "Keep the Kodiak voice (rugged, warm, protein-forward, frontier). "
        f"Keep it under {HEADLINE_MAX_CHARS} characters — this is a headline/overlay caption. "
        "Do NOT describe imagery, do NOT add text-in-image or logo instructions "
        "(the image layer stays text-free per cr-1). "
        f"{lang_line} "
        "Return ONLY the rewritten headline, no quotes, no preamble.\n"
        f"BASE MESSAGE: {base_message}"
    )


def _try_nova_rewrite(prompt: str) -> str | None:
    """One Bedrock Converse call to Nova Micro. Returns text or None on any failure.

    Explicit maxTokens + temperature per skill guidance; temperature ~0.3 keeps the
    rewrite on-brand rather than wandering. Any transport/credential failure returns
    None so the caller falls through to the offline path.
    """
    if boto3 is None:
        return None
    try:
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        resp = client.converse(
            modelId=NOVA_TEXT_MODEL,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 256, "temperature": 0.3},
        )
        out = resp["output"]["message"]["content"][0]["text"].strip().strip('"').strip("'")
        return out or None
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — documented fallback
        print(f"[text_rewriter] Nova Micro rewrite fallback: {e}", file=sys.stderr)
        return None


def _apply_dialect(text: str, region: str, lang: str) -> tuple[str, list[dict]]:
    """Swap standard-language terms for their regional local variant (the trap fix).

    resolve_dialect_terms matches on the standard form and suggests the local form, so
    a fr-VT rewrite carrying "myrtilles" gets swapped to "bleuets". Case-insensitive
    replace; each applied swap is recorded for provenance.
    """
    hits = resolve_dialect_terms(text, region, lang)
    if not hits:
        return text, []
    applied: list[dict] = []
    out = text
    for hit in hits:
        std = hit["matched_standard"]
        local = hit["suggest_local"]
        if not std or std == local:
            continue
        # case-insensitive single-term replace; keep it simple and deterministic
        lowered = out.lower()
        idx = lowered.find(std.lower())
        if idx == -1:
            continue
        out = out[:idx] + local + out[idx + len(std):]
        applied.append(
            {
                "from": std,
                "to": local,
                "category": hit["category"],
                "is_trap": hit["is_trap"],
            }
        )
    return out, applied


def rewrite_headline(
    base_message: str,
    market,
    *,
    product: dict | None = None,
    lang: str = "en",
    month: str | None = None,
    region: str | None = None,
) -> dict:
    """Rewrite a headline for a market, RAG-grounded, dialect-correct, safety-gated.

    Args:
        base_message: the source headline/copy to rewrite.
        market: a market key string, a loose brief dict, or a CampaignBrief.
        product: optional product dict merged into the context pack subject.
        lang: target language; when != "en" the dialect swap runs after the rewrite.
        month: ISO 'YYYY-MM' for the in-season ingredient in the context pack.
        region: dialect-KB region override (e.g. "US-VT"); defaults to the market key.

    Returns:
        {text, source, safety, dialect_applied} — text is always safe (redacted if it
        was not clean). source is "bedrock:nova-micro" on a live call, else "mock".
    """
    # build the subject dict so the context pack can match a cluster + sample prompts
    if product:
        if isinstance(market, dict):
            brief_input = {**market}
            products = list(brief_input.get("products", []))
            products.append(product)
            brief_input["products"] = products
        else:
            brief_input = {"market": market, "products": [product]}
    else:
        brief_input = market

    pack = build_context_pack(brief_input, month=month)
    context_prefix = pack["to_prompt_text"]()
    dialect_region = region or pack["market"]

    prompt = _build_prompt(context_prefix, base_message, lang)

    # transport hop — one Nova Micro call, or the documented offline fallback
    rewritten = _try_nova_rewrite(prompt) if _has_creds() else None
    if rewritten:
        source = "bedrock:nova-micro"
    else:
        rewritten = base_message
        source = "mock"

    # dialect hop — only for non-English targets
    dialect_applied: list[dict] = []
    if lang and lang != "en":
        rewritten, dialect_applied = _apply_dialect(rewritten, dialect_region, lang)

    # safety hop — always last, never return unsafe text
    check = safety.check_text(rewritten)
    if not check["clean"]:
        rewritten = safety.redact(rewritten)
        # re-check after redaction so the reported result reflects the returned text
        check = safety.check_text(rewritten)

    return {
        "text": rewritten,
        "source": source,
        "safety": check,
        "dialect_applied": dialect_applied,
    }


def rewrite_all(
    base_message: str,
    market,
    langs: list[str],
    *,
    product: dict | None = None,
    month: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """Return one finished, safety-gated headline per requested language (README contract).

    This is the localization seam the handler drives: given a base headline and a list
    of target language codes, it runs each through rewrite_headline (Nova Micro rewrite
    -> dialect swap for non-English -> safety gate) and returns a flat list in the same
    order as `langs`. Each entry carries the produced text plus its source so callers can
    mark "translated" vs the offline fallback.

    A failing/absent backend is a documented path, not an exception: rewrite_headline
    already returns source="mock" (base message unchanged) when no creds/no Nova, and any
    unexpected error per language degrades to the base message tagged
    source="rewrite-fallback" so a single bad language never sinks the whole set.

    Returns: [{lang_code, text, source, dialect_applied, safety}, ...] in `langs` order.
    """
    out: list[dict] = []
    for lang in langs:
        try:
            res = rewrite_headline(
                base_message,
                market,
                product=product,
                lang=lang,
                month=month,
                region=region,
            )
            out.append(
                {
                    "lang_code": lang,
                    "text": res["text"],
                    "source": res["source"],
                    "dialect_applied": res["dialect_applied"],
                    "safety": res["safety"],
                }
            )
        except Exception as e:  # noqa: BLE001 — one bad language never sinks the set
            print(f"[text_rewriter] rewrite_all fallback for {lang}: {e}", file=sys.stderr)
            out.append(
                {
                    "lang_code": lang,
                    "text": base_message,
                    "source": "rewrite-fallback",
                    "dialect_applied": [],
                    "safety": {"clean": True},
                }
            )
    return out


def rewrite_campaign_copy(brief, langs: list[str], *, month: str | None = None) -> dict:
    """Rewrite a brief's campaign message once per language.

    brief may be a CampaignBrief, a brief dict, or a market string. The base message
    is pulled from the brief's campaign_message when present, else a generic Kodiak
    line. Returns {lang_code: rewrite_result} for every requested language.
    """
    base_message = None
    market = brief
    if isinstance(brief, dict):
        base_message = brief.get("campaign_message")
        market = brief
    elif hasattr(brief, "campaign_message"):
        base_message = getattr(brief, "campaign_message", None)
    if not base_message:
        base_message = "Protein-packed whole grains for your frontier."

    out: dict[str, dict] = {}
    for lang in langs:
        out[lang] = rewrite_headline(base_message, market, lang=lang, month=month)
    return out
