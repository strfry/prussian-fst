#!/usr/bin/env python3
"""Validiert den nominalen FST gegen die Gold-Formen aus goldstandard.json.

Generiert alle Zellen (Tags → Oberflaeche) und vergleicht sie mit den
erwarteten Formen, die direkt aus goldstandard.json berechnet werden
(dieselbe resolve_stem-Logik wie in build_fst.py).

Tag-Format: +N+Msc+Sg+Nom  (Giella konform)
"""

import json
from pathlib import Path

from pyfoma import FST

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FST_PATH = HERE / "nominals.fst"
GOLD_PATH = ROOT / "goldstandard.json"

# --- Copied from build_fst.py ---

LONG = {"A": "ā", "E": "ē", "I": "ī", "O": "ō", "U": "ū"}
SHORT = {"A": "a", "E": "e", "I": "i", "O": "o", "U": "u"}
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}
VOWELS = set("aeiouāēīōūAEIOU")

GENDER_TAG = {"m": "+Msc", "f": "+Fem", "n": "+Neut"}

# Pronoun paradigms (P9-P20), numeral paradigms (P21-P24),
# and adjective paradigms (P25-P31, P30a)
PRON_PARADIGMS = set(str(i) for i in range(9, 21))
NUM_PARADIGMS = set(str(i) for i in range(21, 25))
ADJ_PARADIGMS = set(str(i) for i in range(25, 32)) | {"30a"}


def _paradigm_base(paradigm: str) -> str:
    """Strip 'def'/'sup'/'adv' and '_suppl'/'_suppl2' suffixes."""
    base = paradigm
    for sfx in ("_suppl2", "_suppl"):
        if base.endswith(sfx):
            base = base[:-len(sfx)]
            break
    for sfx in ("def", "sup", "adv"):
        if base.endswith(sfx):
            base = base[:-len(sfx)]
            break
    return base


def _paradigm_kind(paradigm: str) -> str:
    rest = paradigm
    if paradigm.endswith("_suppl") or paradigm.endswith("_suppl2"):
        rest = paradigm[:paradigm.rfind("_")]
    for kind in ("adv", "def", "sup"):
        if rest.endswith(kind):
            return kind
    return ""


def _pos(paradigm: str) -> str:
    base = _paradigm_base(paradigm)
    if base in PRON_PARADIGMS:
        return "+Pron"
    if base in NUM_PARADIGMS:
        return "+Num"
    if base in ADJ_PARADIGMS:
        return "+A"
    return "+N"

ADV_CELL_TAG = {
    "Pos": "+Pos",
    "Comp": "+Comp",
    "Superl": "+Superl",
}

DEF_TAG = "+Def"
SUPERL_TAG = "+Superl"
ADV_POS_TAG = "+Adv"

CELL_TAG = {
    "Nom sg": "+Sg+Nom", "Nom pl": "+Pl+Nom",
    "Gen sg": "+Sg+Gen", "Gen pl": "+Pl+Gen",
    "Dat sg": "+Sg+Dat", "Dat pl": "+Pl+Dat",
    "Akk sg": "+Sg+Acc", "Akk pl": "+Pl+Acc",
}


def _last_consonant_idx(s: str) -> int | None:
    for i in range(len(s) - 1, -1, -1):
        if s[i] not in VOWELS:
            return i
    return None


def resolve_stem(stamm: str, betont: bool, palatize: bool) -> str:
    vmap = LONG if betont else SHORT
    stem = "".join(vmap.get(c, c.lower()) for c in stamm)
    if palatize and stem:
        idx = _last_consonant_idx(stem)
        if idx is not None and stem[idx] in PALATAL:
            stem = stem[:idx] + PALATAL[stem[idx]] + stem[idx + 1 :]
    return stem


def split_suffix(suffix: str) -> tuple[str, str | None]:
    """Doublette 'a/stan' -> ('a', 'stan'); 'as' -> ('as', None)."""
    if "/" in suffix:
        std, var = suffix.split("/", 1)
        return std, var
    return suffix, None


def strip_macron(s):
    return s.translate(str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU"))


def case_normalize(s):
    return strip_macron(s).lower()


def main() -> None:
    fst = FST.load(str(FST_PATH))
    print(f"Loaded FST: {len(fst.states)} states")

    entries = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    print(f"Goldstandard entries: {len(entries)}")

    total = 0
    matched = 0
    mismatches: list[tuple] = []
    case_mismatches: list[tuple] = []
    no_gen: list[tuple] = []
    variants_total = 0
    variants_matched = 0
    missing_variants: list[tuple] = []

    for entry in entries:
        par = entry["paradigm"]
        lemma = entry["lemma"]
        gender = entry["gender"]
        stamm = entry["stamm"]
        gtag = GENDER_TAG.get(gender, "")

        for cell, v in entry["suffixe"].items():
            betont = v["betont"]
            pal = v.get("palatize", False)
            std_suffix, variant_full = split_suffix(v["suffix"])
            prefix = v.get("prefix", "")

            expected = prefix + resolve_stem(stamm, betont, pal) + std_suffix

            is_adv = cell in ADV_CELL_TAG
            cell_tag = ADV_CELL_TAG[cell] if is_adv else CELL_TAG[cell]

            kind = _paradigm_kind(par)
            if kind == "adv":
                tag = f"{lemma}{_pos(par)}{ADV_POS_TAG}{cell_tag}"
            elif kind == "def":
                tag = f"{lemma}{_pos(par)}{DEF_TAG}{gtag}{cell_tag}"
            elif kind == "sup":
                tag = f"{lemma}{_pos(par)}{SUPERL_TAG}{gtag}{cell_tag}"
            else:
                tag = f"{lemma}{_pos(par)}{gtag}{cell_tag}"
            total += 1

            results = list(fst.generate(tag))

            if not results:
                no_gen.append((par, lemma, gender, cell, tag, expected))
                continue

            # Standardform: Mengen-Mitgliedschaft (Slash-Zellen liefern 2 Formen)
            if expected in results:
                matched += 1
            elif any(case_normalize(r) == case_normalize(expected) for r in results):
                case_mismatches.append((par, lemma, gender, cell, expected, results))
                matched += 1
            else:
                mismatches.append((par, lemma, gender, cell, tag, expected, results))

            # Doubletten-Vollform: muss ebenfalls generiert werden
            if variant_full is not None:
                variants_total += 1
                if variant_full in results:
                    variants_matched += 1
                else:
                    missing_variants.append((par, lemma, gender, cell, variant_full, results))

    print()
    print(f"Total cells tested: {total}")
    print(f"Exact matches:      {matched - len(case_mismatches)}")
    print(f"Case-only diffs:    {len(case_mismatches)}")
    print(f"No generation:      {len(no_gen)}")
    print(f"True mismatches:    {len(mismatches)}")
    print(f"Variant forms:      {variants_matched}/{variants_total} matched")

    if case_mismatches:
        print("\n--- Case-only differences ---")
        for par, lemma, gender, cell, expected, results in case_mismatches:
            print(f"  P{par} {lemma} {gender} {cell}: expected={expected!r} got={results!r}")

    if no_gen:
        print("\n--- No generation (missing from FST) ---")
        for par, lemma, gender, cell, tag, expected in no_gen:
            print(f"  P{par} {lemma} {gender} {cell}: tag={tag} expected={expected!r}")

    if missing_variants:
        print("\n--- MISSING VARIANT FORMS ---")
        for par, lemma, gender, cell, variant, results in missing_variants:
            print(f"  P{par} {lemma} {gender} {cell}: variant={variant!r} not in {results!r}")

    if mismatches:
        print("\n--- TRUE MISMATCHES ---")
        for par, lemma, gender, cell, tag, expected, results in mismatches:
            print(f"  P{par} {lemma} {gender} {cell}: expected={expected!r} got={results!r}")
    else:
        print("\n  *** ALL CELLS MATCH (except case-only) ***")

    # Spot-check analysis
    print("\n--- Analysis spot-check ---")
    spot_checks = [
        ("wāiks", "wāiks+N+Msc+Sg+Nom"),
        ("waikāi", "wāiks+N+Msc+Pl+Nom"),
        ("kūģu", "kūgis+N+Msc+Sg+Dat"),
        ("kūgemans", "kūgis+N+Msc+Pl+Dat"),
        ("spīgsnas", "spigsnā+N+Fem+Pl+Nom"),
        ("māldaišu", "māldaisis+A+Msc+Sg+Dat"),
        ("māldaišai", "māldaisis+A+Msc+Pl+Nom"),
        ("wīrs", "wīrs+N+Msc+Sg+Nom"),
        ("rikīs", "rikīs+N+Msc+Sg+Nom"),
        ("rikkijmans", "rikīs+N+Msc+Pl+Dat"),
        ("sūns", "sūns+N+Msc+Sg+Nom"),
        ("sūnuns", "sūns+N+Msc+Pl+Acc"),
        ("debīks", "debīks+A+Msc+Sg+Nom"),
        ("debīkai", "debīks+A+Msc+Pl+Nom"),
        ("labs", "labs+A+Msc+Sg+Nom"),
        ("labāi", "labs+A+Msc+Pl+Nom"),
    ]
    for form, expected in spot_checks:
        results = list(fst.analyze(form))
        ok = expected in results
        status = "OK" if ok else f"FAIL (got {results})"
        print(f"  {status:12s} {form:20s} → {expected}")

    if mismatches or no_gen or missing_variants:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
