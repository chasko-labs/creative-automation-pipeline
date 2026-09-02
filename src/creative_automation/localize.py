"""Message localization — Bedrock Nova Micro with offline fallback."""
from __future__ import annotations

import os

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None  # type: ignore

BEDROCK_REGION = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
NOVA_TEXT_MODEL = os.getenv("BEDROCK_NOVA_TEXT_MODEL", "amazon.nova-micro-v1:0")

# offline dictionary for demo
OFFLINE = {
    "fr": {
        "Hydrate your glow, wherever you are.": "Hydratez votre éclat, où que vous soyez.",
        "Glow starts with hydration.": "L'éclat commence par l'hydratation.",
    },
    "es": {
        "Hydrate your glow, wherever you are.": "Hidrata tu brillo, estés donde estés.",
        "Glow starts with hydration.": "El brillo comienza con la hidratación.",
    },
    "de": {
        "Hydrate your glow, wherever you are.": "Pflege deinen Glow, wo immer du bist.",
    },
    "ja": {
        "Hydrate your glow, wherever you are.": "どこでも、うるおい輝く肌へ。",
    },
}


def _try_bedrock_translate(text: str, target_lang: str, region: str) -> str | None:
    if boto3 is None or target_lang == "en":
        return None
    try:
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        # Converse API — unified format, explicit maxTokens per skill guidance
        resp = client.converse(
            modelId=NOVA_TEXT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": f"Translate this social ad headline to {target_lang} for market {region}. "
                            f"Keep it punchy, under 60 chars, preserve brand voice. Return ONLY the translation, no quotes.\nText: {text}"
                        }
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 256, "temperature": 0.3},
        )
        out = resp["output"]["message"]["content"][0]["text"].strip().strip('"').strip("'")
        return out if out else None
    except (ClientError, BotoCoreError, Exception) as e:
        print(f"[localize] Bedrock translate fallback: {e}")
        return None


def localize_message(text: str, lang: str, region: str, explicit_map: dict | None = None) -> tuple[str, str]:
    """Return (localized_text, source)."""
    if explicit_map and region in explicit_map:
        return explicit_map[region], "brief"
    if explicit_map and lang in explicit_map:
        return explicit_map[lang], "brief"
    if lang == "en":
        return text, "original"
    # try bedrock
    tr = _try_bedrock_translate(text, lang, region)
    if tr:
        return tr, "bedrock:nova-micro"
    # offline
    if lang in OFFLINE and text in OFFLINE[lang]:
        return OFFLINE[lang][text], "mock:dictionary"
    # fallback: return original with lang tag
    return text, "mock:passthrough"
