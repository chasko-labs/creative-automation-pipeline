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

# === EXHAUSTIVE FLOW: ingredients/seasons -> translations -> web =================
# Source month ingredient: data/localization/retailer-frontier-pairs.json
#   monthly_ingredients: {YYYY-MM: ingredient} per frontier, authored from
#   farmers-market calendars (Ohio: Lebanon orchard belt, SoCal: Julian mountain
#   apples / Oceanside coast, Georgia: Senoia farm stands). Example with
#   qualifiers: "tomatoes (late harvest)" (Dayton Sep), "Vidalia onions (early)"
#   (Atlanta Apr), "heirloom tomatoes (late harvest)" (Oceanside Sep), "pumpkins
#   (Julian)" (San Diego Oct), "strawberries (late)" (Cincinnati/Dayton Jun).
#   Qualifiers are display truth on the card but are STRIPPED and LOWER-CASED
#   before recipe picking (see recipe_card._pick_recipe_detail fix) so that
#   "tomatoes (late harvest)" -> "tomatoes" matches featured_for "tomatoes".
#
# Card build: creative_automation.recipe_card.build_recipe_card_data(market,
#   month, lang, art):
#   - locales.resolve_this_month(market, ym=month) -> ingredient (or honest null)
#   - locales.resolve_seasonal_moments(market) -> seasonal flavor context
#   - pick_recipe_with_provenance(ingredient, "Buttermilk Power Cakes", market, month)
#     curates with resilient exact-match (normalized ingredient vs normalized
#     featured_for). Ohio Cincinnati/Dayton share US-OH-LEBANON, SoCal SD maps
#     to US-CA-JULIAN / Oceanside self, Georgia ATL maps to US-GA-SENOIA — the
#     normalization makes the shared frontier ingredients resilient to qualifier
#     variants across those markets.
#   - Steps/ingredients come verbatim from data/recipes/kodiak-recipes.json
#     (cleaned + verb-bolded, not rewritten), meta from real fields only.
#   - This module's translate_recipe_texts(title, ingredients, steps, lang,
#     market) is called ONLY when lang != "en". It delegates per-line to
#     translate.translate_with_provenance(text, lang, market) through the
#     provider chain, then gates allergen lines with allergen_ok(). Costs/
#     meta (est_cost, prep/cook/serves values) are never translated — only
#     the meta LABELS are baked separately per language by bake_recipe_i18n_js.
#
# Batch bake: creative_automation.recipe_cards_emit.bake_recipe_i18n_js(
#   markets, months):
#   - For every market in sorted order (deterministic), resolve_target_languages(
#     market) -> [en, top2]; e.g. ATL en+es+zh, Oceanside en+es+zh,
#     Cincy/Dayton en+es (default), Senoia en+es variant. Non-English only.
#   - For each market×month with ingredient (honest gap skipped), calls
#     build_recipe_card_data twice: once en (to capture en meta), once per lang
#     (which triggers this module's allergen-checked translation). The book's
#     per-lang entry stores {title, ingredients, steps, meta{prep,cook,serves},
#     translation}. Translation calls are memoized on (source text, lang) so
#     Ohio/SoCal/Georgia cards sharing a recipe share one translation per line.
#   - Also bakes window.KODIAK_RECIPE_META_LABELS: for each distinct lang,
#     translates the fuller phrases _META_LABEL_SOURCE ("Prep time" etc.) so
#     short English labels never clip verbs in the frontend.
#   - Writes web/.../js/recipe-i18n-data.js as two assignments:
#     window.KODIAK_RECIPE_I18N = {market:{month:{lang:{title,ingredients,
#     steps,meta,translation}}}};
#     window.KODIAK_RECIPE_META_LABELS = {lang:{prep,cook,serves,est_cost,...}};
#     Byte-identical for same markets×months; offline toggle swaps languages
#     via file:// without a live /localize endpoint.
#
# Safety: provider chain is translate._try_aws_translate -> _try_bedrock_translate
#   -> offline dict -> passthrough suffix. _ALLERGENS glossary (below) maps
#   English allergen term -> expected target translations; unsupported languages
#   fail closed on allergen lines only (line falls back to English). human_
#   reviewed is always False (machine), flagged in provenance so the UI badges
#   it. The glossary is intentionally over-strict: a missed translation only
#   loses the line's translation, never its safety.
#
# Resilient market notes:
#  - Ohio Cincy US-OH-CINCINNATI / Dayton US-OH-DAYTON both -> frontier
#    US-OH-LEBANON (Lebanon Farmers Market, Irons/Hidden Valley orchards).
#    Ingredients "tomatoes (late harvest)", "strawberries (late)", "maple syrup
#    (late run)" all normalize cleanly for curated matching.
#  - SoCal SD US-W-SD -> US-CA-JULIAN (4200 ft apple country, pie/cider), OCEAN
#    US-CA-OCEANSIDE self-coast (Mandarins Jan, heirloom tomatoes Aug/Sep).
#    Varietal/venue qualifiers "(Julian)", "(Temecula/Valley Center)",
#    "(late harvest)", "(early/peak/late spring)" are the qualifier class
#    handled here.
#  - Georgia ATL US-SE-ATL -> US-GA-SENOIA (Senoia Farmers Market, Thompson/
#    Dickey/Pearson/Durham farms). "(early)" on Vidalia onions is the canonical
#    early vs standard contrast.
"""

from __future__ import annotations

import re  # allergen word-boundary matching, qualifier stripping note (recipe_card side)

from .translate import translate_with_provenance  # provider chain entry point (AWS Translate -> Nova Micro -> offline dict)

# source term (lowercase, matched on word boundaries) -> expected target terms
# per language (lowercase substrings). Major allergens plus honey (infant risk).
# Used by allergen_ok() to verify that a mistranslated line still names the
# allergen in the target language; if not, the line falls back to English.
# Languages outside these keys cannot be verified -> unsupported-lang path
# which fails closed on allergen lines only (safe: allergen line falls back to
# English, non-allergen line passes). Mirrors the safety contract in the
# recipe_card → recipe_i18n → translate chain so a printed keepsake never
# drops a milk/egg/peanut/honey warning due to a bad MT call.
_ALLERGENS: dict[str, dict[str, tuple[str, ...]]] = {
    "milk": {"es": ("leche",), "ar": ("حليب",), "pt": ("leite",), "fr": ("lait",)},
    "egg": {"es": ("huevo",), "ar": ("بيض",), "pt": ("ovo",), "fr": ("œuf",)},  # singular covers "egg" token, plural "eggs" listed separately
    "eggs": {"es": ("huevo",), "ar": ("بيض",), "pt": ("ovo",), "fr": ("œuf",)},  # plural form -> same glossary entry as singular
    "butter": {"es": ("mantequilla", "manteca"), "ar": ("زبدة",), "pt": ("manteiga",), "fr": ("beurre",)},
    "honey": {"es": ("miel",), "ar": ("عسل",), "pt": ("mel",), "fr": ("miel",)},  # infant botulism risk, treated as allergen-class
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
    """Allergen keys named by an English line (word-boundary match).

    # Scans the lowercased English source line for each allergen key with
    # re.search(r"\b" + re.escape(key) + r"\b", low) so "nut" doesn't false-
    # hit "donut" but "egg" hits inside "2 large eggs" (word boundary after).
    # Returns the list of matched keys (e.g. ["milk", "butter"]) so the
    # caller knows which glossary entries to require in the translation.
    # This is the English-side detector; the target-side verifier is
    # allergen_ok() which checks that each expected term appears.
    """
    low = line.lower()
    return [key for key in _ALLERGENS if re.search(r"\b" + re.escape(key) + r"\b", low)]


def allergen_ok(source_line: str, translated_line: str, lang: str) -> bool:
    """True when every allergen the source names appears in the translation.

    Languages outside the glossary cannot be verified — they fail closed only
    for lines that name an allergen (those fall back to English); allergen-free
    lines pass through with provider provenance.

    # Semantics:
    #   - If source names no allergen (_source_allergens == []), always True
    #     (even for unsupported languages — no safety claim is at stake).
    #   - For each source allergen key, look up expected target terms
    #     _ALLERGENS[key].get(lang). If the language has no entry for that
    #     allergen, return False -> caller falls back to English for that line
    #     (fail-closed: we cannot prove the translation preserved the warning).
    #   - Otherwise check that at least one expected substring appears in the
    #     lowercased translation. All keys must be satisfied.
    #   So a line "1/2 cup milk" translated to Spanish must contain "leche";
    #   "T-1/2 cup milk" (tagged passthrough) would lack it and be rejected.
    #   This is the same gate used by bake_recipe_i18n_js._meta_value for the
    #   meta-bar values (prep/cook/serves) and for every title/ingredient/step
    #   line below.
    """
    keys = _source_allergens(source_line)
    if not keys:
        return True  # allergen-free line -> always ok, even for unsupported lang
    low = translated_line.lower()
    for key in keys:
        expected = _ALLERGENS[key].get(lang)
        if expected is None:
            return False  # unsupported lang for this allergen -> fail closed (fallback to English)
        if not any(term in low for term in expected):
            return False  # allergen term missing in translation -> unsafe
    return True  # every allergen the source named appears correctly in target


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

    # Contract (mirrors recipe_card.build_recipe_card_data integration):
    #   - Inputs title/ingredients/steps are the English card texts derived
    #     from the picked recipe (kodiak-recipes.json, verbatim + cleaned).
    #     They travel through recipe_cards_emit.bake_recipe_i18n_js which
    #     rebuilds the card per non-English lang and collects the per-lang
    #     {title, ingredients, steps, translation} block into
    #     window.KODIAK_RECIPE_I18N. This function is the inner translator for
    #     each card (and for the meta-label table via the caller's memoized
    #     wrapper).
    #   - Provider chain: translate_with_provenance(text, lang, market) tries
    #     AWS Translate (if creds), else Nova Micro (Bedrock), else offline
    #     dictionary, else tagged passthrough (text + language suffix) — always
    #     returns (translated_text, provider, nova_proven). The per-card
    #     "providers" list de-dups providers used across the card's lines.
    #   - Allergen gate: for each line, if out != text (i.e. actually translated)
    #     and not allergen_ok(source, out, lang), the line falls back to the
    #     English source and the label (e.g. "ingredient:1", "step:3", "title")
    #     is pushed to fallbacks. The provenance records machine_translated
    #     True, human_reviewed False, allergen_check "glossary" or
    #     "unsupported-lang" (when lang not in any allergen's glossary),
    #     plus the fallback line list so the UI can badge.
    #   - Meta/costs are NOT translated here (universal figures). bake wraps
    #     this with its own _meta_value helper that reuses the same allergen
    #     gate for prep/cook/serves values; costs never reach here.
    #   - Resilience: monthly ingredients with qualifiers (Ohio "tomatoes (late
    #     harvest)", SoCal "pumpkins (Julian)") have already been normalized at
    #     the recipe-picking layer (recipe_card: strip parens + lowercase before
    #     comparing featured_for), so by the time ingredients[] arrives here the
    #     card's recipe is already the correct curated pick and translation
    #     just renders its texts.
    #   - English short-circuit: lang == "en" or falsy returns the English
    #     texts verbatim with provenance {machine_translated False, human_reviewed
    #     True, allergen_check "source-language"} — useful for building the
    #     English matrix that bake treats as byte-identical source.
    """
    if not lang or lang == "en":
        # English is the source language: no provider calls, no glossary, no
        # fallback list. This keeps the English matrix (emit) untouched and
        # provenance marks it as the human-level source (human_reviewed True).
        return {
            "title": title,
            "ingredients": list(ingredients),  # defensive copy so caller never mutates source
            "steps": list(steps),
            "provenance": {
                "lang": "en",
                "providers": ["original:en"],  # single provider tag naming the source
                "machine_translated": False,  # not machine output
                "human_reviewed": True,  # source is the authored recipe text
                "allergen_check": "source-language",  # glossary not applied to English
                "allergen_fallback_lines": [],
            },
        }
    providers: list[str] = []  # de-duped providers used for this card's lines
    fallbacks: list[str] = []  # labels of lines that failed the allergen check and fell back to English

    def _one(label: str, text: str) -> str:
        # Translate one line via the memoized or real provider chain, record
        # the provider, and fail-safe allergen lines back to English.
        out, provider, _proven = translate_with_provenance(text, lang, market)  # market is region hint for Nova
        if provider not in providers:
            providers.append(provider)  # keep provider list unique and ordered by first appearance
        if out != text and not allergen_ok(text, out, lang):
            # Line was translated but the glossary check failed (expected allergen
            # term missing, or lang not in glossary for that allergen) -> fall
            # back to English source for safety and record the label.
            fallbacks.append(label)  # e.g. "ingredient:1" or "title"
            return text  # English source, not the unsafe translation
        return out  # either untranslated (passthrough) or gloss-verified translation

    # Title + each ingredient line + each step travel the same _one path so
    # every line is individually allergen-checked and provider-recorded.
    # Labels use 1-based indexing matching the card's ingredient/step order
    # so provenance.allergen_fallback_lines is human-readable.
    new_title = _one("title", title)
    new_ingredients = [_one(f"ingredient:{i + 1}", line) for i, line in enumerate(ingredients)]
    new_steps = [_one(f"step:{i + 1}", line) for i, line in enumerate(steps)]
    return {
        "title": new_title,
        "ingredients": new_ingredients,
        "steps": new_steps,
        "provenance": {
            "lang": lang,
            "providers": providers,  # e.g. ["aws_translate"] or ["stub"] in tests
            "machine_translated": True,  # all non-English cards are machine output
            "human_reviewed": False,  # never true for machine output (UI badges it)
            "allergen_check": "glossary"
            if lang in {code for per_lang in _ALLERGENS.values() for code in per_lang}
            else "unsupported-lang",  # when lang not in any glossary entry, allergen lines fail closed
            "allergen_fallback_lines": fallbacks,  # exact labels that fell back to English
        },
    }
