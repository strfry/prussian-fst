#!/usr/bin/env python3
"""CLI-Analysator: Wörter/Sätze gegen analyser.fst + lenient.fst analysieren.

Aufruf:  python -m prussian.fst.analyze "kūgjan mestāi wīrs"

Standard-Analysen kommen aus build/analyser.fst; Formen in
Quellvarianten-Orthographie (Twanksta-j, elaktr-) fängt build/lenient.fst
auf und werden mit '~' markiert.
"""

import sys
from pathlib import Path

from pyfoma import FST

ROOT = Path(__file__).resolve().parent.parent.parent.parent
MAIN_FST = ROOT / "build/analyser.fst"
LENIENT_FST = ROOT / "build/lenient.fst"


def main() -> None:
    main_fst = FST.load(str(MAIN_FST))
    lenient_fst = FST.load(str(LENIENT_FST))

    for word in " ".join(sys.argv[1:]).split():
        w = word.lower()
        results = sorted(set(main_fst.analyze(w)))
        marker = ""
        if not results:
            results = sorted(set(lenient_fst.analyze(w)))
            marker = "~"  # nur über Variantenorthographie erkannt
        if results:
            for r in results:
                print(f"{word}\t{marker}{r}")
        else:
            print(f"{word}\t?")


if __name__ == "__main__":
    main()
