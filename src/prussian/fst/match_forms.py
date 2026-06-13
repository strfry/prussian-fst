#!/usr/bin/env python3
"""Wörterbuch-Coverage: flektierte Twanksta-Formen ∘ FST (nominal + verbal).

Dünner CLI-Wrapper um ``report.dict_coverage`` — Kernlogik + Per-Paradigma-
Statistik leben dort und speisen auch das Dashboard.

CLI:  match_forms.py [main_fst] [lenient_fst]
"""

import sys
from pathlib import Path

from pyfoma import FST

from prussian.report import dict_coverage

ROOT = Path(__file__).resolve().parent.parent.parent.parent
MAIN_FST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/analyser.fst"
LENIENT_FST = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build/lenient.fst"


def _report(name: str, r: dict) -> None:
    rec = r["direct"] + r["ortho"]
    tot = r["total"]
    print(f"\n{'='*65}\n{name}: {tot} Formen")
    if not tot:
        return
    print(f"  Direkt:   {r['direct']:6d}  ({100*r['direct']/tot:5.1f}%)")
    print(f"  Ortho:    {r['ortho']:6d}  ({100*r['ortho']/tot:5.1f}%)")
    print(f"  Kein:     {r['no']:6d}  ({100*r['no']/tot:5.1f}%)")
    print(f"  ERKANNT:  {rec:6d}  ({100*rec/tot:5.1f}%)")
    print("\n--- Per paradigm (≥10 Formen) ---")
    rows = []
    for par, s in r["par_stats"].items():
        if s["total"] >= 10:
            r2 = s["direct"] + s["ortho"]
            rows.append((par, s["total"], r2, 100 * r2 / s["total"],
                         s["ortho"], s["no"]))
    rows.sort(key=lambda x: x[3])
    for par, t, r2, pct, ortho, no in rows:
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  P{par:5s} {bar} {r2:5d}/{t:5d} ({pct:5.1f}%)  "
              f"ortho={ortho:4d} unmatched={no:5d}")


def main() -> None:
    main_fst = FST.load(str(MAIN_FST))
    lenient_fst = FST.load(str(LENIENT_FST))
    print(f"Main FST: {len(main_fst.states)} states")
    print(f"Lenient FST: {len(lenient_fst.states)} states")

    _report("Nominal (P9–P70)", dict_coverage.run_nominal(main_fst, lenient_fst))
    _report("Verbal (P71+)", dict_coverage.run_verbal(main_fst, lenient_fst))


if __name__ == "__main__":
    main()
