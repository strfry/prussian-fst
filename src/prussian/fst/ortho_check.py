#!/usr/bin/env python3
"""Validiert den Orthographie-Normalisierungs-FST gegen Quellformen.

Testet:
  1. Alle -j- Variant-Paare aus goldstandard.json:
     ortho_fst.analyze(variant) → standard
  2. Pipeline: ortho_fst.analyze + main_fst.analyze → korrekte Morph-Analyse
  3. Reale Twanksta-Formen aus vergleich.json
"""

import json
import re
import unicodedata
from pathlib import Path

from pyfoma import FST

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAIN_FST = HERE / "nominals.fst"
ORTHO_FST = HERE / "ortho.fst"
GOLD = ROOT / "goldstandard.json"
VERGLEICH = ROOT / "vergleich.json"

from fst.ortho_rules import variant_suffix

LONG = {"A": "ā", "E": "ē", "I": "ī", "O": "ō", "U": "ū"}
SHORT = {"A": "a", "E": "e", "I": "i", "O": "o", "U": "u"}
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}
VOWELS = set("aeiouāēīōūAEIOU")

GENDER_TAG = {"m": "+Msc", "f": "+Fem", "n": "+Neut"}

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


def strip_macron(s):
    return s.translate(str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU"))


def analyze_with_ortho(main_fst: FST, ortho_fst: FST, form: str) -> list[str]:
    """Analyse mit Ortho-Normalisierung.

    Liefert ALLE Ergebnisse (direkt + via ortho-FST).
    Normalisiert Gross-/Kleinschreibung vor der Analyse.
    """
    form_lower = form.lower()
    results = list(main_fst.analyze(form_lower))
    for norm in ortho_fst.analyze(form_lower):
        for r in main_fst.analyze(norm):
            if r not in results:
                results.append(r)
    return results


def main() -> None:
    main_fst = FST.load(str(MAIN_FST))
    ortho_fst = FST.load(str(ORTHO_FST))
    print(f"Loaded main FST: {len(main_fst.states)} states")
    print(f"Loaded ortho FST: {len(ortho_fst.states)} states")

    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))

    # ── Test 1: Ortho-FST round-trip ──
    print("\n── Test 1: Ortho-FST analyzer(variant) → standard ──")
    failures_1 = 0
    pairs_tested = 0
    for e in gs_data:
        stamm = e["stamm"]
        for cell, v in e["suffixe"].items():
            suffix = v["suffix"]
            betont = v["betont"]
            pal = v.get("palatize", False)

            jvar = variant_suffix(suffix)
            if jvar is None:
                continue

            standard = resolve_stem(stamm, betont, pal) + suffix
            variant = resolve_stem(stamm, betont, False) + jvar

            if standard != variant:
                pairs_tested += 1
                results = list(ortho_fst.analyze(variant))
                if standard not in results:
                    failures_1 += 1
                    print(f"  FAIL  {variant} → {results}, expected {standard}")

    print(f"  {pairs_tested - failures_1}/{pairs_tested} OK  ({failures_1} failures)")

    # ── Test 2: Full pipeline (variant → morphology) ──
    print("\n── Test 2: Pipeline variant → ortho-FST → main-FST → morph ──")
    failures_2 = 0
    tested_2 = 0
    for e in gs_data:
        lemma = e["lemma"]
        gtag = GENDER_TAG[e["gender"]]
        stamm = e["stamm"]
        for cell, v in e["suffixe"].items():
            suffix = v["suffix"]
            betont = v["betont"]
            pal = v.get("palatize", False)

            jvar = variant_suffix(suffix)
            if jvar is None:
                continue

            standard = resolve_stem(stamm, betont, pal) + suffix
            expected_tag = f"{lemma}+N{gtag}{CELL_TAG[cell]}"

            variant = resolve_stem(stamm, betont, False) + jvar
            if standard != variant:
                tested_2 += 1
                results = analyze_with_ortho(main_fst, ortho_fst, variant)
                if expected_tag not in results:
                    failures_2 += 1
                    if failures_2 <= 15:
                        print(f"  FAIL  {variant} → {results}, expected {expected_tag}")

    print(f"  {tested_2 - failures_2}/{tested_2} OK  ({failures_2} failures)")

    # ── Test 3: Reale Twanksta -j- Formen aus vergleich.json ──
    print("\n── Test 3: Reale Twanksta -j- Formen aus vergleich.json ──")
    vergleich = json.loads(VERGLEICH.read_text(encoding="utf-8"))
    twanksta_forms: dict[str, str] = {}
    for par_key, e in vergleich.items():
        for g_key in e.get("Twanksta", {}):
            for cell, form in e["Twanksta"][g_key].items():
                form = form.strip()
                if form and form != "—":
                    twanksta_forms.setdefault(form, f"{par_key} {e['lemma']} {g_key} {cell}")

    found = 0
    not_found = 0
    for form, info in sorted(twanksta_forms.items()):
        results = analyze_with_ortho(main_fst, ortho_fst, form)
        if results:
            found += 1
        else:
            not_found += 1
            if not_found <= 20:
                print(f"  NOT FOUND  {form:30s}  ({info})")

    print(f"  {found}/{found + not_found} recognized  ({not_found} unrecognized)")

    # ── Test 4: Spot-check -jan Varianten aus GOLDSTANDARD.md ──
    print("\n── Test 4: Spot-check GOLDSTANDARD.md Twanksta -jan Formen ──")
    spot_checks = [
        ("kūgjan", "kūgis+N+Msc+Sg+Acc"),
        ("kūgjans", "kūgis+N+Msc+Pl+Acc"),
        ("kūgjas", "kūgis+N+Msc+Sg+Gen"),      # Gen sg variant
        ("kūgjai", "kūgis+N+Msc+Pl+Nom"),      # Nom pl variant
        ("āngjan", "āngus+N+Fem+Pl+Gen"),
        ("āngjas", "āngus+N+Fem+Pl+Nom"),
        ("līgjan", "līgus+N+Fem+Sg+Acc"),
        ("līgjans", "līgus+N+Fem+Pl+Acc"),
        ("māldaisjan", "māldaisis+N+Msc+Sg+Acc"),
        ("māldaisjans", "māldaisis+N+Msc+Pl+Acc"),
        ("buccjas", "buccis+N+Msc+Sg+Gen"),
        ("buccjai", "buccis+N+Msc+Pl+Nom"),
        ("dulzjas", "dulzis+N+Msc+Sg+Gen"),
        ("dulzjai", "dulzis+N+Msc+Pl+Nom"),
        ("pannjan", "pannin+N+Neut+Sg+Nom"),
        ("pannjans", "pannin+N+Neut+Pl+Acc"),
        ("gīrbjan", "gīrbis+N+Msc+Sg+Acc"),
        ("gīrbjai", "gīrbis+N+Msc+Pl+Nom"),
    ]
    spot_ok = 0
    spot_fail = 0
    for form, expected_tag in spot_checks:
        results = analyze_with_ortho(main_fst, ortho_fst, form)
        ok = expected_tag in results
        if ok:
            spot_ok += 1
        else:
            spot_fail += 1
            print(f"  FAIL  {form:20s} → {results}, expected {expected_tag}")
    print(f"  {spot_ok}/{spot_ok + spot_fail} OK  ({spot_fail} failures)")

    if failures_1 or failures_2 or spot_fail:
        raise SystemExit(1)
    print("\nDone.")


if __name__ == "__main__":
    main()
