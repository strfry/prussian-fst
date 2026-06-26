#!/usr/bin/env python3
"""Test 2: Dictionary coverage.

Checks how many Wörterbuch entries are covered by the lexc FST,
at paradigm and lemma level.
"""

import json
import sys
from collections import defaultdict


def load_dict(path):
    with open(path) as f:
        return json.load(f)


def load_defined_paradigms(lexc_path):
    """Extract paradigm numbers from a lexc file."""
    defined = set()
    with open(lexc_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("LEXICON V") and "_stems" in line:
                p = line.split("_")[0].replace("LEXICON V", "")
                defined.add(p)
            elif line.startswith("LEXICON N") and "_stems" in line:
                p = line.split("_")[0].replace("LEXICON N", "")
                defined.add(p)
            elif line.startswith("LEXICON A") and "_stems" in line:
                p = line.split("_")[0].replace("LEXICON A", "")
                defined.add(p)
            elif line.startswith("LEXICON P") and "_stems" in line:
                p = line.split("_")[0].replace("LEXICON P", "")
                defined.add(p)
            elif line.startswith("LEXICON Num") and "_stems" in line:
                p = line.split("_")[0].replace("LEXICON Num", "")
                defined.add(p)
            elif line.startswith("LEXICON Part") and "_stems" in line:
                p = line.split("_")[0].replace("LEXICON Part", "")
                defined.add(p)
    return defined


def main():
    pr = load_dict("data/external/prusaspira_entries.json")
    tw = load_dict("data/external/twanksta_entries.json")

    # Merge dictionary entries
    dict_entries = defaultdict(set)
    for data in [pr, tw]:
        for e in data:
            word = e.get("word", "").strip()
            paradigm = str(e.get("paradigm", "?"))
            if word and paradigm != "?":
                dict_entries[paradigm].add(word)

    # Load defined paradigms from all stem files
    defined = set()
    for f in ["fst/nom_stems.lexc", "fst/verb_stems.lexc"]:
        defined |= load_defined_paradigms(f)

    def pnum(p):
        """Extract numeric paradigm base from string like '75b'."""
        p_clean = p.rstrip("abcdeosyz")
        return int(p_clean) if p_clean.isdigit() else 0

    # Analyze by word class
    classes = {
        "Nomina":      lambda p: 9 <= pnum(p) <= 70 and pnum(p) not in {68, 69, 70},
        "Adjektive":   lambda p: 25 <= pnum(p) <= 31,
        "Pronomen":    lambda p: 1 <= pnum(p) <= 24,
        "Verben":      lambda p: 71 <= pnum(p) <= 144 and pnum(p) not in {115, 118},
        "Partizipien": lambda p: pnum(p) in {68, 69, 70, 115, 118},
        "Sonstige":    lambda p: True,
    }

    grand_total = 0
    grand_covered = 0
    exit_code = 0

    for cls_name, cls_test in classes.items():
        cls_total = 0
        cls_covered = 0
        missing_p = []

        for p in sorted(dict_entries.keys(),
                        key=lambda x: (int(x.rstrip("abc")) if x.rstrip("abc").isdigit() else 9999, x)):
            if not cls_test(p):
                continue
            count = len(dict_entries[p])
            cls_total += count
            if p in defined:
                cls_covered += count
            elif count >= 3:
                missing_p.append((p, count))

        pct = cls_covered / cls_total * 100 if cls_total else 0
        status = "✓" if pct > 95 else ("⚠" if pct > 80 else "✗")
        print(f"{status} {cls_name:<15s}: {cls_covered:>5d}/{cls_total:<5d} ({pct:.1f}%)")
        if missing_p:
            print(f"   Fehlende Paradigmen: {', '.join(f'P{p}({c})' for p, c in missing_p[:8])}")
            if pct < 90:
                exit_code = 1

        grand_total += cls_total
        grand_covered += cls_covered

    pct = grand_covered / grand_total * 100 if grand_total else 0
    print(f"\n   Gesamt: {grand_covered}/{grand_total} ({pct:.1f}%)")

    if grand_covered < grand_total * 0.95:
        print(f"\n✗ Abdeckung unter 95%")
        exit_code = 1
    else:
        print(f"\n✓ Abdeckung >= 95%")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
