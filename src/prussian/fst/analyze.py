#!/usr/bin/env python3
"""Alle flektierten Twanksta-Formen aus prussian_dictionary.json gegen den
Haupt-FST + Ortho-Normalisierungs-FST matchen.

Nur Paradigmen im FST-Bereich (P9–P67) werden geprueft.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from pyfoma import FST

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAIN_FST = HERE / "nominals.fst"
ORTHO_FST = HERE / "ortho.fst"
DICT = ROOT / "prussian_dictionary.json"
GOLD = ROOT / "goldstandard.json"
WORDLIST = ROOT / "wordlist.json"

CASE_MAP = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Acc"}
NUM_MAP = {"singular": "sg", "plural": "pl"}
GENDER_MAP = {"masc": "m", "fem": "f", "neut": "n"}


def main() -> None:
    main_fst = FST.load(str(MAIN_FST))
    ortho_fst = FST.load(str(ORTHO_FST))
    print(f"Main FST: {len(main_fst.states)} states")
    print(f"Ortho FST: {len(ortho_fst.states)} states")

    sentence = sys.argv[1]

    def analyze(form: str) -> list[str]:
        f = form.lower()
        results = list(main_fst.analyze(f))
        for norm in ortho_fst.analyze(f):
            for r in main_fst.analyze(norm):
                if r not in results:
                    results.append(r)
        return results

    for word in sentence.split(' '):
        word = word.lower()
        result = list(main_fst.analyze(word))
        print(result)

if __name__ == "__main__":
    main()
