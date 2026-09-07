"""POST /localize seam — resolution-ordered localization for the translation-surfacing UI.

The one job: given (text, market, target_lang), return the best localized string with an
honest provenance tag the frontend can surface. The resolution order is a fixed contract
the frontend depends on — every hop is explicit, not a swallowed fallback:

    1. PRECOMPUTED  -> DynamoDB kodiak-creatives-localization-memory  (provider=precomputed, source=dynamodb)
    2. LIVE MT on miss, routed by language:
         a. Amazon-Translate langs  -> Amazon Translate  (provider=amazon-translate, source=live)
         b. machine-able gaps        -> Bedrock Converse  (provider=bedrock, source=live, low_confidence)
         c. nv (Navajo) / zip (Zapotec) -> NO machine translation, original text
                                        (provider=human-required, source=original, human_pending)
    3. OFFLINE / no-creds -> original text  (provider=offline-dictionary, source=mock)

Ethics rule (from SPEC-translation-resources-and-fonts.md): nv and zip are never machine
translated. Shipping fake MT for a language with no reliable MT is worse than surfacing
"human translation pending", so those codes short-circuit BEFORE any transport call.

Safety is the last hop and non-negotiable: the returned text always runs through
safety.check_text; anything flagged is redacted before return. Reuses localize.py's boto3
client pattern (env-driven region, defensive import) and text_rewriter._has_creds() as the
network-free gate before any live call.
"""
from __future__ import annotations

import os
import sys

from . import localize_memory, safety
from .text_rewriter import _has_creds

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional — offline path returns source="mock"
    boto3 = None  # type: ignore

# env-driven region / model — same resolution order as localize.py and dam.py
BEDROCK_REGION = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
TRANSLATE_REGION = os.getenv("TRANSLATE_REGION", BEDROCK_REGION)
# larger model than Nova Micro for low-resource gap-language quality (per spec)
BEDROCK_TRANSLATE_MODEL = os.getenv("BEDROCK_TRANSLATE_MODEL", "amazon.nova-pro-v1:0")

# ---- language routing groups (SPEC-translation-resources-and-fonts.md) --------------
# 16 languages Amazon Translate supports for this program
AMAZON_TRANSLATE_LANGS = frozenset(
    {"am", "ar", "bs", "de", "es", "fr", "ht", "ja", "ko", "pl", "pt", "ru", "so", "tl", "vi", "zh"}
)
# machine-able gaps: no Amazon Translate coverage, route to a larger Bedrock model,
# flagged lower-confidence so the UI can badge them
BEDROCK_GAP_LANGS = frozenset({"ilo", "my", "ne", "pct"})
# human-required — two distinct rationales coexist in this set:
#   nv/zip: ethics rule — never machine-translate these, honest "human pending" only
#   hmn:    quality/reachability — nova-pro (the only Bedrock model family this account
#           can invoke; explicit IAM deny on Claude/Llama/Mistral) produces incoherent
#           Hmong with English words left untranslated, verified by back-translation
#           2026-09-07. honest English-source beats broken MT, same net outcome as nv/zip.
#           real Hmong MT needs expanded (non-Nova) Bedrock access or a human translator.
HUMAN_REQUIRED_LANGS = frozenset({"nv", "zip", "hmn"})


def _finish(text: str, source: str, provider: str, lang: str, **extra) -> dict:
    """Run text through the safety gate (last hop) and assemble the response contract.

    Anything flagged is redacted before return; the returned text is always clean. `extra`
    carries optional flags (low_confidence, human_pending) the UI surfaces.
    """
    check = safety.check_text(text)
    if not check["clean"]:
        text = safety.redact(text)
    out = {"text": text, "source": source, "provider": provider, "lang": lang}
    out.update(extra)
    return out


def _amazon_translate(text: str, target_lang: str, source_lang: str = "en") -> str | None:
    """One Amazon Translate call. Returns translated text or None on any failure."""
    if boto3 is None:
        return None
    try:
        client = boto3.client("translate", region_name=TRANSLATE_REGION)
        resp = client.translate_text(
            Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang
        )
        out = resp.get("TranslatedText", "").strip()
        return out or None
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — documented fallback
        print(f"[localize_service] Amazon Translate fallback ({target_lang}): {e}", file=sys.stderr)
        return None


def _bedrock_translate(text: str, target_lang: str, market: str) -> str | None:
    """One Bedrock Converse call for a gap language (larger model for low-resource quality).

    Returns translated text or None on any failure. Explicit maxTokens + low temperature
    per skill guidance keeps the translation faithful rather than wandering.
    """
    if boto3 is None:
        return None
    try:
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        resp = client.converse(
            modelId=BEDROCK_TRANSLATE_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                f"Translate this social ad headline to the language with ISO code "
                                f"'{target_lang}' for market {market}. Preserve meaning and brand voice, "
                                f"keep it punchy. Return ONLY the translation, no quotes, no notes.\n"
                                f"Text: {text}"
                            )
                        }
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 512, "temperature": 0.2},
        )
        out = resp["output"]["message"]["content"][0]["text"].strip().strip('"').strip("'")
        return out or None
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — documented fallback
        print(f"[localize_service] Bedrock translate fallback ({target_lang}): {e}", file=sys.stderr)
        return None


def localize(text: str, market: str, target_lang: str) -> dict:
    """Resolve a localized variant for (text, market, target_lang) per the fixed contract.

    Returns {text, source, provider, lang} — plus optional flags:
      - low_confidence=True for Bedrock gap-language machine translation
      - human_pending=True for nv/zip (returned unchanged, never machine translated)

    text is always safety-gated (redacted if flagged) as the last hop.
    """
    lang = target_lang

    # English is the source — no localization needed, but still safety-gated
    if lang == "en":
        return _finish(text, source="original", provider="passthrough", lang=lang)

    # 1) PRECOMPUTED — the scale path. Most reads should hit here.
    hit = localize_memory.get_precomputed(text, market, lang)
    if hit:
        return _finish(hit["text"], source=hit["source"], provider=hit["provider"], lang=lang)

    # 2c) ETHICS GUARD — never machine-translate Navajo (nv) or Zapotec (zip).
    #     Short-circuit BEFORE any transport call so no fake MT is ever produced.
    if lang in HUMAN_REQUIRED_LANGS:
        return _finish(
            text, source="original", provider="human-required", lang=lang, human_pending=True
        )

    # offline / no-creds — documented mock path so CI stays green with no AWS creds
    if not _has_creds():
        return _finish(text, source="mock", provider="offline-dictionary", lang=lang)

    # 2a) Amazon-Translate-supported languages
    if lang in AMAZON_TRANSLATE_LANGS:
        translated = _amazon_translate(text, lang)
        if translated:
            return _finish(translated, source="live", provider="amazon-translate", lang=lang)
        # transport failure — fall through to the offline mock rather than silent-fail
        return _finish(text, source="mock", provider="offline-dictionary", lang=lang)

    # 2b) machine-able gap languages — Bedrock, flagged lower-confidence
    if lang in BEDROCK_GAP_LANGS:
        translated = _bedrock_translate(text, lang, market)
        if translated:
            return _finish(
                translated, source="live", provider="bedrock", lang=lang, low_confidence=True
            )
        return _finish(text, source="mock", provider="offline-dictionary", lang=lang)

    # unknown / unrouted language — offline mock passthrough
    return _finish(text, source="mock", provider="offline-dictionary", lang=lang)
