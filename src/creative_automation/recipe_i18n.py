"""Machine translation for recipe-card text blocks — no human review loop.

Card bodies travel the existing provider chain (translate.translate_with_provenance:
AWS Translate -> Nova Micro -> offline dictionary -> tagged passthrough), then
every translated line runs an allergen-glossary check: a line whose English
source names an allergen must carry the expected target-language term, else that
line falls back to English and is listed in provenance. Failing safe toward
English keeps a mistranslated allergen off a printed keepsake; an over-strict
glossary only costs a line its translation, never its safety.

Provenance per card: {lang, providers, machine_translated, human_reviewed,
allergen_check, allergen_fallback_lines}. human_reviewed is always False for
machine output — the UI badges it. Costs and meta values are never translated
(figures and counts are universal); meta labels stay with the frontend.
"""

from __future__ import annotations

import re

from .translate import translate_with_provenance

# source term (lowercase, matched on word boundaries) -> expected target terms
# per language (lowercase substrings). Major allergens plus honey (infant risk).
_ALLERGENS: dict[str, dict[str, tuple[str, ...]]] = {
    "milk": {"es": ("leche",), "ar": ("حليب",), "pt": ("leite",), "fr": ("lait",)},
    "egg": {"es": ("huevo",), "ar": ("بيض",), "pt": ("ovo",), "fr": ("œuf",)},
    "eggs": {"es": ("huevo",), "ar": ("بيض",), "pt": ("ovo",), "fr": ("œuf",)},
    "butter": {"es": ("mantequilla", "manteca"), "ar": ("زبدة",), "pt": ("manteiga",), "fr": ("beurre",)},
    "honey": {"es": ("miel",), "ar": ("عسل",), "pt": ("mel",), "fr": ("miel",)},
    "wheat": {"es": ("trigo",), "ar": ("قمح",), "pt": ("trigo",), "fr": ("blé",)},
    "flour": {"es": ("harina",), "ar": ("دقيق", "طحين"), "pt": ("farinha",), "fr": ("farine",)},
    "peanut": {"es": ("maní", "cacahuate", "cacahuete"), "ar": ("فول سوداني",), "pt": ("amendoim",), "fr": ("cacahuète",)},
    "almond": {"es": ("almendra",), "ar": ("لوز",), "pt": ("amêndoa",), "fr": ("amande",)},
    "walnut": {"es": ("nuez",), "ar": ("جوز",), "pt": ("noz",), "fr": ("noix",)},
    "pecan": {"es": ("pacana", "nuez"), "ar": ("جوز البقان", "جوز"), "pt": ("noz-pecã", "noz"), "fr": ("pacane", "noix")},
    "nut": {"es": ("nuez", "fruto seco"), "ar": ("مكسرات", "جوز"), "pt": ("noz", "castanha"), "fr": ("noix",)},
    "soy": {"es": ("soja", "soya"), "ar": ("صويا",), "pt": ("soja",), "fr": ("soja",)},
    "fish": {"es": ("pescado",), "ar": ("سمك",), "pt": ("peixe",), "fr": ("poisson",)},
    "shrimp": {"es": ("camarón", "gamba"), "ar": ("جمبري", "روبيان"), "pt": ("camarão",), "fr": ("crevette",)},
    "sesame": {"es": ("sésamo", "ajonjolí"), "ar": ("سمسم",), "pt": ("gergelim",), "fr": ("sésame",)},
    "cheese": {"es": ("queso",), "ar": ("جبن", "جبنة"), "pt": ("queijo",), "fr": ("fromage",)},
    "coconut": {"es": ("coco",), "ar": ("جوز الهند",), "pt": ("coco",), "fr": ("coco",)},
}


def _source_allergens(line: str) -> list[str]:
    """Allergen keys named by an English line (word-boundary match)."""
    low = line.lower()
    return [key for key in _ALLERGENS if re.search(r"\b" + re.escape(key) + r"\b", low)]


def allergen_ok(source_line: str, translated_line: str, lang: str) -> bool:
    """True when every allergen the source names appears in the translation.

    Languages outside the glossary cannot be verified — they fail closed only
    for lines that name an allergen (those fall back to English); allergen-free
    lines pass through with provider provenance.
    """
    keys = _source_allergens(source_line)
    if not keys:
        return True
    low = translated_line.lower()
    for key in keys:
        expected = _ALLERGENS[key].get(lang)
        if expected is None:
            return False
        if not any(term in low for term in expected):
            return False
    return True


def translate_recipe_texts(
    title: str,
    ingredients: list[str],
    steps: list[str],
    lang: str,
    market: str = "US",
) -> dict:
    """Translate a card's text blocks, with allergen fail-safe + provenance.

    Returns {title, ingredients, steps, provenance}. English passes through
    untouched. Any translated line that fails the allergen check falls back to
    its English source and is listed in provenance.allergen_fallback_lines.
    """
    if not lang or lang == "en":
        return {
            "title": title,
            "ingredients": list(ingredients),
            "steps": list(steps),
            "provenance": {
                "lang": "en",
                "providers": ["original:en"],
                "machine_translated": False,
                "human_reviewed": True,
                "allergen_check": "source-language",
                "allergen_fallback_lines": [],
            },
        }
    providers: list[str] = []
    fallbacks: list[str] = []

    def _one(label: str, text: str) -> str:
        out, provider, _proven = translate_with_provenance(text, lang, market)
        if provider not in providers:
            providers.append(provider)
        if out != text and not allergen_ok(text, out, lang):
            fallbacks.append(label)
            return text
        return out

    new_title = _one("title", title)
    new_ingredients = [_one(f"ingredient:{i + 1}", line) for i, line in enumerate(ingredients)]
    new_steps = [_one(f"step:{i + 1}", line) for i, line in enumerate(steps)]
    return {
        "title": new_title,
        "ingredients": new_ingredients,
        "steps": new_steps,
        "provenance": {
            "lang": lang,
            "providers": providers,
            "machine_translated": True,
            "human_reviewed": False,
            "allergen_check": "glossary"
            if lang in {code for per_lang in _ALLERGENS.values() for code in per_lang}
            else "unsupported-lang",
            "allergen_fallback_lines": fallbacks,
        },
    }
