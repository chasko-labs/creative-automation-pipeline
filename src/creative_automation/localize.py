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

# offline dictionary for demo (expanded for KODIAK frontier markets — top 2 outside English per market)
OFFLINE = {
    "fr": {
        "Hydrate your glow, wherever you are.": "Hydratez votre éclat, où que vous soyez.",
        "Glow starts with hydration.": "L'éclat commence par l'hydratation.",
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "Restez sauvage — grains entiers protéinés pour votre frontière Wasatch. Nourriture pour la Frontière d'Aujourd'hui",
        "Feeding Epic Days & Wilder Lives": "Nourrir des Jours Épiques & des Vies Plus Sauvages",
    },
    "es": {
        "Hydrate your glow, wherever you are.": "Hidrata tu brillo, estés donde estés.",
        "Glow starts with hydration.": "El brillo comienza con la hidratación.",
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "Mantente Salvaje — granos integrales con proteína para tu frontera Wasatch. Nutrición para la Frontera de Hoy",
        "Feeding Epic Days & Wilder Lives": "Alimentando Días Épicos y Vidas Más Salvajes",
        "Nourishment for Today's Frontier": "Nutrición para la Frontera de Hoy",
    },
    "de": {
        "Hydrate your glow, wherever you are.": "Pflege deinen Glow, wo immer du bist.",
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "Bleib wild — proteinreiche Vollkornprodukte für deine Wasatch-Frontier. Nahrung für die Frontier von Heute",
    },
    "ja": {
        "Hydrate your glow, wherever you are.": "どこでも、うるおい輝く肌へ。",
    },
    "zh": {
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "保持狂野——为你的瓦萨奇边疆提供富含蛋白质的全谷物。今日边疆的营养",
        "Nourishment for Today's Frontier": "今日边疆的营养",
    },
    "vi": {
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "Giữ Hoang Dã — ngũ cốc nguyên hạt giàu protein cho biên cương Wasatch của bạn. Dưỡng chất cho Biên Cương Hôm Nay",
    },
    "pt": {
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "Mantenha-se Selvagem — grãos integrais com proteína para sua fronteira Wasatch. Nutrição para a Fronteira de Hoje",
    },
    "ar": {
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "حافظ على البرية — حبوب كاملة غنية بالبروتين لحدود واساتش. غذاء لحدود اليوم",
    },
    "pl": {
        "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier": "Pozostań dziki — pełnoziarniste z białkiem dla Twojej granicy Wasatch. Odżywienie dla Dzisiejszej Granicy",
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


def _try_translate_api(text: str, target_lang: str, source_lang: str = "en") -> str | None:
    """Amazon Translate — second try after Nova Micro (unlimited Nova budget)."""
    if boto3 is None or target_lang == "en":
        return None
    # translate_code supports ht->fr, so->ar already mapped by pipeline loader
    try:
        client = boto3.client("translate", region_name=BEDROCK_REGION)
        # Amazon Translate language codes: es, fr, de, zh, vi, ko, ja, tl, ar, pt, pl, ru ...
        resp = client.translate_text(Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)
        out = resp.get("TranslatedText", "").strip()
        return out if out else None
    except (ClientError, BotoCoreError, Exception) as e:
        print(f"[localize] Translate API fallback: {e}")
        return None


def localize_message(text: str, lang: str, region: str, explicit_map: dict | None = None) -> tuple[str, str]:
    """Return (localized_text, source)."""
    if explicit_map and region in explicit_map:
        return explicit_map[region], "brief"
    if explicit_map and lang in explicit_map:
        return explicit_map[lang], "brief"
    if lang == "en":
        return text, "original"
    # try bedrock (Nova Micro) first, then Translate API (via Nova Micro + Amazon Translate)
    tr = _try_bedrock_translate(text, lang, region)
    if tr:
        return tr, "bedrock:nova-micro"
    tr2 = _try_translate_api(text, lang)
    if tr2:
        return tr2, "translate:amazon"
    # offline
    if lang in OFFLINE and text in OFFLINE[lang]:
        return OFFLINE[lang][text], "mock:dictionary"
    # generic offline suffix so message still displays localized tag on final post
    if lang in ("es", "fr", "de", "zh", "vi", "pt", "ar", "pl", "ko", "ja", "tl", "ru"):
        return f"{text} [{lang}]", "mock:tagged"
    # fallback: return original with lang tag
    return text, "mock:passthrough"
