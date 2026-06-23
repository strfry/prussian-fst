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
ROOT = HERE
MAIN_FST = HERE / "fst/nominals.fst"
ORTHO_FST = HERE / "fst/ortho.fst"
DICT = ROOT / "prussian_dictionary.json"
GOLD = ROOT / "goldstandard.json"
WORDLIST = ROOT / "wordlist.json"

def main() -> None:
    main_fst = FST.load(str(MAIN_FST))
    ortho_fst = FST.load(str(ORTHO_FST))
    print(f"Main FST: {len(main_fst.states)} states")
    print(f"Ortho FST: {len(ortho_fst.states)} states")

    def analyze(form: str) -> list[str]:
        f = form.lower()
        results = list(main_fst.analyze(f))
        for norm in ortho_fst.analyze(f):
            for r in main_fst.analyze(norm):
                if r not in results:
                    results.append(r)
        return results


    words = []
    for i in sys.argv[1:]:
        words.extend(i.split(' '))


    for word in words:
    	word = word.lower()
    	result = analyze(word)
    	print(result)


if __name__ == "__main__":
    main()
