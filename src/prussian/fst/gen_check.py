#!/usr/bin/env python3
"""Validiert den FST gegen die Gold-Formen (nominal + verbal).

Dünner CLI-Wrapper um ``report.generation.run`` — die eigentliche
Zell-Klassifikation (exact/case_only/no_gen/true_mismatch + Doubletten) lebt
dort und speist auch das Dashboard. Hier zusätzlich ein paar Analyse-Spot-Checks.

Tag-Format: +N+Msc+Sg+Nom  (Giella konform)
"""

import json
from pathlib import Path

from pyfoma import FST

from prussian.report import generation

ROOT = Path(__file__).resolve().parent.parent.parent.parent
FST_PATH = ROOT / "build/analyser.fst"
GOLD_PATH = ROOT / "data/gold/goldstandard.json"
VERB_GOLD_PATH = ROOT / "data/gold/goldstandard_verben_fst.json"


def _print_slice(name: str, b: dict) -> None:
    print(f"\n=== {name} ===")
    print(f"Total cells tested: {b['cells']}")
    print(f"Exact matches:      {b['exact']}")
    print(f"Case-only diffs:    {b['case_only']}")
    print(f"No generation:      {b['no_gen']}")
    print(f"True mismatches:    {b['true_mismatch']}")
    print(f"Variant forms:      {b['variants_matched']}/{b['variants_total']} matched")
    for s in b["no_gen_samples"]:
        print(f"  NO-GEN  P{s['paradigm']} {s['lemma']}: tag={s['tag']} exp={s['expected']!r}")
    for s in b["mismatch_samples"]:
        print(f"  MISMATCH P{s['paradigm']} {s['lemma']}: exp={s['expected']!r} got={s['got']!r}")


def main() -> None:
    fst = FST.load(str(FST_PATH))
    print(f"Loaded FST: {len(fst.states)} states")

    gold_nom = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    gold_verb = json.loads(VERB_GOLD_PATH.read_text(encoding="utf-8"))
    result = generation.run(fst, gold_nom, gold_verb)
    _print_slice("Nominal", result["nominal"])
    _print_slice("Verbal", result["verbal"])

    print("\n--- Analysis spot-check ---")
    spot_checks = [
        ("wāiks", "wāiks+N+Msc+Sg+Nom"),
        ("waikāi", "wāiks+N+Msc+Pl+Nom"),
        ("kūģu", "kūgis+N+Msc+Sg+Dat"),
        ("spīgsnas", "spigsnā+N+Fem+Pl+Nom"),
        ("wīrs", "wīrs+N+Msc+Sg+Nom"),
        ("sūnuns", "sūns+N+Msc+Pl+Acc"),
        ("debīks", "debīks+A+Msc+Sg+Nom"),
        ("labāi", "labs+A+Msc+Pl+Nom"),
    ]
    for form, expected in spot_checks:
        results = list(fst.analyze(form))
        status = "OK" if expected in results else f"FAIL (got {results})"
        print(f"  {status:12s} {form:20s} → {expected}")

    bad = sum(result[s]["no_gen"] + result[s]["true_mismatch"]
              for s in ("nominal", "verbal"))
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
