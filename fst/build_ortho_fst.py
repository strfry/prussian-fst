#!/usr/bin/env python3
"""Baut einen Orthographie-Normalisierungs-FST aus goldstandard.json.

Erzeugt fst/ortho.fst: einen Transducer der Twanksta-Orthographie-Varianten
(mit explizitem Palatalisierungs-j) auf die Goldstandard-Formen abbildet.

Mažiulis §§21-25 (Palatalisierung), §122 Fn54 (weiche Endung):
  Twanksta: kūgjan → Goldstandard: kūgin
  Twanksta: āngjas → Goldstandard: ānges
  Twanksta: kūgjai → Goldstandard: kūgei
  Twanksta: buccjas → Goldstandard: buccas   (j-Einschub auch bei hartem Vokal)

Der FST ist obere/untere-Seite: standard:variant.
  .analyze("kūgjan") → ["kūgin"]   (Variant → Standard)
  .generate("kūgin") → ["kūgjan"]  (Standard → Variant)

Fuer die Analyse-Pipeline: erst normalize (ortho-FST), dann Haupt-FST.
Die Generation bleibt unveraendert (Haupt-FST direkt).
"""

import json
from pathlib import Path

from pyfoma import FST

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GOLD = ROOT / "goldstandard.json"
ORTHO_FST = HERE / "ortho.fst"

from fst.ortho_rules import variant_suffix

# --- Kopiert aus build_fst.py (resolve_stem) ---

LONG = {"A": "ā", "E": "ē", "I": "ī", "O": "ō", "U": "ū"}
SHORT = {"A": "a", "E": "e", "I": "i", "O": "o", "U": "u"}
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}
VOWELS = set("aeiouāēīōūAEIOU")


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


def build_pairs(entries: list[dict]) -> list[tuple[str, str]]:
    """Generate (standard, variant) form pairs from goldstandard.

    Two cases:
      1. pal=False: same stem, j-inserted suffix (vowel-initial only)
      2. pal=True:  standard has palatalized stem + plain suffix;
                    variant has unpalatalized stem + j-suffix
    """
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for e in entries:
        stamm = e["stamm"]
        for _cell, v in e["suffixe"].items():
            suffix = v["suffix"]
            betont = v["betont"]
            pal = v.get("palatize", False)

            jvar = variant_suffix(suffix)
            if jvar is None:
                continue

            standard = resolve_stem(stamm, betont, pal) + suffix

            if not pal:
                variant = resolve_stem(stamm, betont, False) + jvar
            else:
                variant = resolve_stem(stamm, betont, False) + jvar

            if standard != variant and (standard, variant) not in seen:
                seen.add((standard, variant))
                pairs.append((standard, variant))

    return pairs


def main() -> None:
    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))
    print(f"Loaded {len(gs_data)} goldstandard entries from {GOLD}")

    pairs = build_pairs(gs_data)
    print(f"Ortho variant pairs: {len(pairs)}")

    fst = FST.from_strings(pairs)
    n_states = len(fst.states)
    print(f"Compiled ortho FST: {n_states} states")

    fst.save(str(ORTHO_FST))
    print(f"Saved {ORTHO_FST}")

    # Quick sanity checks
    tests = [
        ("kūgjan", "kūgin"),      # soft ending, pal=False
        ("āngjan", "āngin"),      # soft ending, pal=False
        ("āngjas", "ānges"),      # soft ending, pal=False
        ("kūgjai", "kūgei"),      # soft ending, pal=False
        ("māldaisjan", "māldaisin"),  # soft ending
        ("buccjas", "buccas"),    # hard vowel, pal=False (P40c)
        ("buccjai", "buccai"),    # hard vowel, pal=False (P40c)
        ("buccjamans", "buccamans"),  # hard vowel, pal=False
        ("dulzjai", "dulžai"),    # pal=True → unpal stem + j-suffix
        ("dulzjas", "dulžas"),    # pal=True
        ("dulzju", "dulžu"),      # pal=True
        ("dulzjamans", "dulžamans"),  # pal=True
        ("garkītjamans", "garkītemans"),  # soft ending
    ]
    for variant, expected in tests:
        results = list(fst.analyze(variant))
        ok = expected in results
        print(f"  {'OK' if ok else 'FAIL'}  analyze({variant!r}) = {results}  expected={expected!r}")

    print("Done.")


if __name__ == "__main__":
    main()
