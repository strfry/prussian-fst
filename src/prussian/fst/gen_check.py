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

from prussian.fst.oracle import case_normalize, resolve_stem
from prussian.fst.tags import (
    ADV_CELL_TAG, ADV_POS_TAG, CELL_TAG, DEF_TAG, GENDER_TAG, SUPERL_TAG,
    _paradigm_kind, _pos, split_suffix,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
FST_PATH = ROOT / "build/analyser.fst"
GOLD_PATH = ROOT / "data/gold/goldstandard.json"


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
