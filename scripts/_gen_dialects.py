#!/usr/bin/env python
"""One-shot generator for the dialect knowledge bases.

Diacritics are written as explicit unicode escapes so the codepoints are
unambiguous regardless of editor behavior, then serialized UTF-8 with
ensure_ascii=False. A diacritic is meaning, not cosmetic: Vietnamese tone marks
(pho/bo), Portuguese/French accents, Spanish enye all carry semantic weight.

This is a seed generator. Rows encode the analyst summary findings; rows that
need fuller analyst detail are marked confidence="medium" with a usage_note
saying so. Regional-trap terms are category="trap" (highest curation value).

Run once, then the JSONL files are the source of truth. Kept in-repo for
regeneration/audit.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "localization" / "dialect"

# unicode building blocks (explicit escapes, no reliance on editor encoding)
ENYE = "\u00f1"          # n with tilde
A_AC = "\u00e1"          # a acute
E_AC = "\u00e9"          # e acute
I_AC = "\u00ed"          # i acute
O_AC = "\u00f3"          # o acute
U_AC = "\u00fa"          # u acute
A_GR = "\u00e0"          # a grave
E_GR = "\u00e8"          # e grave
E_CIRC = "\u00ea"        # e circumflex
A_TIL = "\u00e3"         # a tilde
O_TIL = "\u00f5"         # o tilde
C_CED = "\u00e7"         # c cedilla
E_TREMA = "\u00eb"       # e diaeresis
# vietnamese
O_HORN_HOOK = "\u1edf"   # o-horn with hook above (in "ph\u1edf" pho)
O_CIRC_GRAVE = "\u1ed3"  # not used but kept for reference
PHO = "ph" + O_HORN_HOOK          # pho (noodle soup)
BO = "b\u00f2"                    # bo (beef) - o with grave
BANH = "b\u00e1nh"               # banh (cake/bread) - a acute
CA_PHE = "c\u00e0 ph\u00ea"      # ca phe (coffee) - a grave + e circumflex


def rows_es_sw():
    return [
        ("hotcakes", "panqueques", "Southwest US Spanish (Mexican-heritage) uses 'hotcakes' for pancakes, not 'panqueques'. The single highest-value brand-fit term for Kodiak in the SW market.", "trap", "high"),
        ("desayuno", "desayuno", "Breakfast. Standard and SW usage agree; sweet-and-savory morning framing works.", "breakfast", "high"),
        ("harina para hotcakes", "mezcla para panqueques", "Pancake mix as 'harina para hotcakes' in SW. Pair with the hotcakes trap term for on-brand product naming.", "food", "medium"),
        ("avena", "avena", "Oatmeal / oats. Consistent across dialects; safe for Kodiak oat products.", "food", "high"),
        ("chile verde", "chile verde", "Green chile is a defining SW (New Mexico / Las Cruces) breakfast ingredient. High resonance for a savory flapjack spin.", "food", "medium"),
        ("moras azules", "ar\u00e1ndanos", "Blueberries often 'moras azules' in SW usage; 'ar" + A_AC + "ndanos' also understood (accent on the a).", "food", "medium"),
        ("miel de maple", "jarabe de arce", "Maple syrup: SW/Mexican usage favors 'miel de maple' over Iberian 'jarabe de arce'.", "trap", "medium"),
        ("prote\u00edna", "prote\u00edna", "Protein, accent on the i (prote" + I_AC + "na). Diacritic is orthographic-standard.", "register", "high"),
        ("ni\u00f1o", "ni\u00f1o", "Child (ni" + ENYE + "o). Enye is semantic: ni" + ENYE + "o (child) vs nino (misspelling). Exercises enye round-trip.", "trap", "high"),
        ("integral", "integral", "Whole-grain as 'integral' (harina integral). Core to the 100% whole grains claim.", "food", "high"),
        ("listo en minutos", "listo en minutos", "'Ready in minutes' convenience register fitting the on-the-go Kodiak line.", "register", "medium"),
        ("se" + ENYE + "or", "se" + ENYE + "or", "Honorific with enye; seeded to lock a second enye round-trip case.", "register", "medium"),
    ]


def rows_es_fl_cuban():
    # DELIBERATELY CONTRADICTS es-SW: keep separate. Cuban-FL INVERTS to panqueque.
    return [
        ("panqueque", "panqueques", "Cuban-FL Spanish uses 'panqueque' (singular-leaning) and does NOT use 'hotcakes'. This directly INVERTS the SW dialect — the two Spanish KBs must stay separate.", "trap", "high"),
        ("tortilla", "omelette", "TRAP: in Cuban-FL usage 'tortilla' means an egg omelette, not a flatbread. Using 'tortilla' for a wrap/flatbread misfires here.", "trap", "high"),
        ("cafecito", "caf\u00e9", "Cafecito: small sweet Cuban espresso, a morning ritual. Accent on the e in caf" + E_AC + ". Strong breakfast-adjacency for Kodiak morning creative.", "breakfast", "high"),
        ("colada", "caf\u00e9 para compartir", "Colada: shared Cuban espresso served with small cups; a social morning ritual. High cultural-fit signal in Miami-Cuban market.", "breakfast", "high"),
        ("desayuno", "desayuno", "Breakfast. Shared term, but the ritual (cafecito/colada) is the localization hook.", "breakfast", "high"),
        ("tostada cubana", "tostada", "Cuban toast pressed with butter; a canonical Cuban breakfast bread item.", "food", "medium"),
        ("mantequilla", "mantequilla", "Butter. Stable.", "food", "high"),
        ("ar\u00e1ndanos", "ar\u00e1ndanos", "Blueberries, accent on the a (ar" + A_AC + "ndanos). Cuban-FL keeps the standard term rather than 'moras azules'.", "food", "medium"),
        ("az\u00facar", "az\u00facar", "Sugar (az" + U_AC + "car), accent on the u. Cafecito is notably sweet — sugar framing lands.", "food", "high"),
        ("proteina", "prote\u00edna", "Protein; casual Miami text often drops the accent, standard is prote" + I_AC + "na.", "register", "medium"),
        ("ni\u00f1o", "ni\u00f1o", "Child (ni" + ENYE + "o); enye round-trip case for the Cuban file.", "trap", "high"),
        ("integral", "integral", "Whole-grain 'integral'; shared with SW but re-seeded so this file stands alone.", "food", "high"),
    ]


def rows_ht_fl():
    # Haitian Creole in Florida. Do NOT default to French.
    return [
        ("manje maten", "petit-d\u00e9jeuner", "TRAP: Haitian Creole for breakfast is 'manje maten' (lit. morning food), NOT the French 'petit-d" + E_AC + "jeuner'. Do not default to French.", "trap", "high"),
        ("pen", "pain", "TRAP: bread is 'pen' in Kreyol, NOT French 'pain'. A common French-default failure.", "trap", "high"),
        ("krep", "cr\u00eape", "Pancake/crepe as 'krep' in Kreyol orthography (phonetic), vs French cr" + E_CIRC + "pe. Kreyol spells by sound.", "food", "high"),
        ("dlo", "eau", "Water is 'dlo'. Illustrates Kreyol is its own language, not accented French.", "food", "medium"),
        ("kafe", "caf\u00e9", "Coffee 'kafe' (phonetic), vs French caf" + E_AC + ". Morning ritual term.", "breakfast", "high"),
        ("diri", "riz", "Rice 'diri'; staple, savory-meal context.", "food", "medium"),
        ("ze", "oeuf", "Egg 'ze'. Savory breakfast component.", "food", "medium"),
        ("bon", "bon", "Good 'bon' — one of the few tokens that overlaps French spelling; note the overlap is coincidental, treat Kreyol as primary.", "register", "medium"),
        ("pwoteyin", "prot\u00e9ine", "Protein rendered phonetically 'pwoteyin' in Kreyol vs French prot" + E_AC + "ine.", "register", "medium"),
        ("timoun", "enfant", "Child 'timoun' (ti moun = little person). Family-audience register.", "register", "medium"),
        ("byen vit", "rapidement", "'Real quick' / fast — convenience register for on-the-go framing.", "register", "medium"),
        ("farin", "farine", "Flour 'farin' (no final e), vs French farine. Product-ingredient term.", "food", "medium"),
    ]


def rows_vi_seattle():
    # Vietnamese in Seattle. Diacritics are semantic. Savory-first breakfast.
    return [
        (PHO, "noodle soup", "TRAP: 'ph" + O_HORN_HOOK + "' (pho) needs its tone mark — without it the word changes. Savory noodle soup is a common Vietnamese breakfast, breakfast is not sweet-first here.", "trap", "high"),
        (BO, "beef", "TRAP: 'b" + "\u00f2" + "' (bo, beef) tone mark is semantic; wrong/absent tone = different word entirely.", "trap", "high"),
        (BANH, "cake / bread", "'b" + "\u00e1" + "nh' (banh) = cake or bread depending on compound (banh mi, banh xeo). Accent required.", "food", "high"),
        (CA_PHE, "coffee", "'c" + A_GR + " ph" + E_CIRC + "' (ca phe) coffee, often ca phe sua (with condensed milk) at breakfast.", "breakfast", "high"),
        ("b\u1eefa s\u00e1ng", "breakfast", "'b" + "\u1eef" + "a s" + A_AC + "ng' = morning meal; savory-first, not a sweet-pancake default.", "breakfast", "high"),
        ("tr\u1ee9ng", "egg", "'tr" + "\u1ee9" + "ng' (trung) egg; savory breakfast component.", "food", "medium"),
        ("y\u1ebfn m\u1ea1ch", "oats", "'y" + "\u1ebf" + "n m" + "\u1ea1" + "ch' oats/oatmeal; the diacritics on both syllables are load-bearing.", "food", "medium"),
        ("protein", "protein", "Protein commonly kept as the English loanword in Seattle Vietnamese-American register.", "register", "medium"),
        ("nhanh", "quick", "'nhanh' fast/quick — convenience register for on-the-go.", "register", "medium"),
        ("ch\u00e1o", "rice porridge", "'ch" + A_AC + "o' savory rice porridge, a common Vietnamese breakfast; reinforces savory-first morning, not sweet-pancake default.", "breakfast", "medium"),
        ("ngon", "delicious", "'ngon' tasty; food-appeal register that lands in social captions.", "register", "medium"),
        ("s\u1eefa", "milk", "'s" + "\u1eef" + "a' milk; ca phe sua and cereal-milk contexts. Tone mark semantic.", "food", "medium"),
    ]


def rows_fr_vt():
    # Quebec-influenced French in Vermont. dejeuner = BREAKFAST.
    return [
        ("d\u00e9jeuner", "petit-d\u00e9jeuner", "TRAP: in Quebec/VT French 'd" + E_AC + "jeuner' means BREAKFAST, not lunch. In France French d" + E_AC + "jeuner = lunch. This inversion is the top trap for the VT market.", "trap", "high"),
        ("bleuets", "myrtilles", "TRAP: blueberries are 'bleuets' in Quebec French, NOT 'myrtilles' (France). Kodiak blueberry products must use bleuets in VT.", "trap", "high"),
        ("cr\u00eape", "cr\u00eape", "Pancake/crepe cr" + E_CIRC + "pe; circumflex on the e is orthographic-standard.", "food", "high"),
        ("sirop d'\u00e9rable", "sirop d'\u00e9rable", "Maple syrup sirop d'" + E_AC + "rable — Vermont/Quebec is maple country, extremely high local resonance.", "food", "high"),
        ("d\u00eener", "d\u00eener", "In Quebec 'd\u00eener' (circumflex i) traditionally = midday meal, shifting the whole meal-name system vs France. Flag when mapping meal times.", "trap", "medium"),
        ("avoine", "avoine", "Oats/oatmeal 'avoine'. Stable across French variants.", "food", "high"),
        ("beurre", "beurre", "Butter 'beurre'. Stable.", "food", "high"),
        ("caf\u00e9", "caf\u00e9", "Coffee caf" + E_AC + "; accent on the e. Morning ritual.", "breakfast", "high"),
        ("prot\u00e9ine", "prot\u00e9ine", "Protein prot" + E_AC + "ine, accent on the first e.", "register", "high"),
        ("cr\u00e8me", "cr\u00e8me", "Cream cr" + E_GR + "me, grave accent. Food-styling term.", "food", "medium"),
        ("bl\u00e9 entier", "bl\u00e9 entier", "Whole wheat/grain bl" + E_AC + " entier. Core to the whole-grain claim.", "food", "high"),
        ("enfant", "enfant", "Child 'enfant'; family register.", "register", "medium"),
    ]


def rows_pt_parkcity():
    # Brazilian Portuguese in Park City. NOT European Portuguese.
    return [
        ("caf\u00e9 da manh\u00e3", "pequeno-almo\u00e7o", "TRAP: Brazilian Portuguese breakfast is 'caf" + E_AC + " da manh" + A_TIL + "', NOT European 'pequeno-almo" + C_CED + "o'. The a-tilde on manh" + A_TIL + " is semantic.", "trap", "high"),
        ("suco", "sumo", "TRAP: juice is 'suco' in Brazilian Portuguese, NOT European 'sumo'. Common EU/BR divergence.", "trap", "high"),
        ("panqueca", "panqueca", "Pancake 'panqueca' in Brazilian usage. No diacritic but distinct from Spanish panqueque.", "food", "high"),
        ("aveia", "aveia", "Oats/oatmeal 'aveia'. Stable.", "food", "high"),
        ("mirtilo", "mirtilo", "Blueberry 'mirtilo' (Brazilian). Distinct from the Spanish/French terms.", "food", "medium"),
        ("manteiga", "manteiga", "Butter 'manteiga'. Stable.", "food", "high"),
        ("prote\u00edna", "prote\u00edna", "Protein prote" + I_AC + "na, accent on the i.", "register", "high"),
        ("a\u00e7\u00facar", "a\u00e7\u00facar", "Sugar a" + C_CED + U_AC + "car — cedilla on the c AND acute on the u; two diacritics in one word, strong round-trip test.", "food", "high"),
        ("p\u00e3o", "p\u00e3o", "Bread p" + A_TIL + "o, a-tilde is semantic (pao without it is a misspelling).", "food", "high"),
        ("gr\u00e3o integral", "gr\u00e3o integral", "Whole grain gr" + A_TIL + "o integral; a-tilde on gr" + A_TIL + "o. Core whole-grain claim.", "food", "high"),
        ("crian\u00e7a", "crian\u00e7a", "Child crian" + C_CED + "a, cedilla; family register.", "register", "medium"),
        ("r\u00e1pido", "r\u00e1pido", "Fast/quick r" + A_AC + "pido; convenience register for on-the-go.", "register", "medium"),
    ]


FILES = {
    ("US-SW", "es"): ("dialect-es-sw.jsonl", rows_es_sw()),
    ("US-FL-CUBAN", "es"): ("dialect-es-fl-cuban.jsonl", rows_es_fl_cuban()),
    ("US-FL", "ht"): ("dialect-ht-fl.jsonl", rows_ht_fl()),
    ("US-SEATTLE", "vi"): ("dialect-vi-seattle.jsonl", rows_vi_seattle()),
    ("US-VT", "fr"): ("dialect-fr-vt.jsonl", rows_fr_vt()),
    ("US-PARKCITY", "pt"): ("dialect-pt-parkcity.jsonl", rows_pt_parkcity()),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for (region, lang), (fname, rows) in FILES.items():
        path = OUT / fname
        with path.open("w", encoding="utf-8") as fh:
            for term_local, term_standard, note, category, confidence in rows:
                obj = {
                    "region": region,
                    "lang_code": lang,
                    "term_local": term_local,
                    "term_standard": term_standard,
                    "usage_note": note,
                    "category": category,
                    "confidence": confidence,
                }
                fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        print(f"wrote {path.relative_to(REPO)}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
