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
ROOT = HERE.parent.parent.parent
# Überschreibbar per CLI: match_forms.py [main_fst] [lenient_fst]
MAIN_FST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build/analyser.fst"
LENIENT_FST = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build/lenient.fst"
DICT = ROOT / "data/external/prussian_dictionary.json"
GOLD = ROOT / "data/gold/goldstandard.json"
WORDLIST = ROOT / "data/external/wordlist.json"

CASE_MAP = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Acc"}
NUM_MAP = {"singular": "sg", "plural": "pl"}
GENDER_MAP = {"masc": "m", "fem": "f", "neut": "n"}


def count_total() -> int:
    """Count total forms to process (for progress bar)."""
    with open(DICT, encoding="utf-8") as f:
        words = json.load(f)
    total = 0
    for w in words:
        par = w.get("paradigm", "")
        if par not in ALL_FST_PARS:
            continue
        if "forms" not in w or "declension" not in w["forms"]:
            continue
        for decl in w["forms"]["declension"]:
            for case_info in decl.get("cases", []):
                if case_info.get("case", "") not in CASE_MAP:
                    continue
                for num_name in ("singular", "plural"):
                    form = case_info.get(num_name, "").strip()
                    if form and form != "—":
                        total += 1
    return total


def main() -> None:
    main_fst = FST.load(str(MAIN_FST))
    lenient_fst = FST.load(str(LENIENT_FST))
    print(f"Main FST: {len(main_fst.states)} states")
    print(f"Lenient FST: {len(lenient_fst.states)} states")

    def analyze(form: str) -> list[str]:
        f = form.lower()
        results = list(main_fst.analyze(f))
        if not results:
            results = list(lenient_fst.analyze(f))
        return results

    with open(DICT, encoding="utf-8") as f:
        words = json.load(f)

    total_expected = count_total()
    print(f"Forms to process (FST paradigms): {total_expected}")

    total = 0
    direct_match = 0
    ortho_match = 0
    no_match = 0
    par_stats: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "direct": 0, "ortho": 0, "no": 0}
    )
    no_match_samples: list[tuple] = []

    for wi, w in enumerate(words):
        par = w.get("paradigm", "")
        if par not in ALL_FST_PARS:
            continue
        if "forms" not in w or "declension" not in w["forms"]:
            continue

        lemma = w["word"]

        for decl in w["forms"]["declension"]:
            gender_key = decl.get("gender", "")
            gender = GENDER_MAP.get(gender_key, "")
            for case_info in decl.get("cases", []):
                case_name = case_info.get("case", "")
                case_short = CASE_MAP.get(case_name)
                if not case_short:
                    continue
                for num_name, num_short in NUM_MAP.items():
                    form = case_info.get(num_name, "").strip()
                    if not form or form == "—":
                        continue

                    total += 1
                    par_stats[par]["total"] += 1

                    results = analyze(form)
                    if results:
                        direct = list(main_fst.analyze(form.lower()))
                        if direct:
                            direct_match += 1
                            par_stats[par]["direct"] += 1
                        else:
                            ortho_match += 1
                            par_stats[par]["ortho"] += 1
                    else:
                        no_match += 1
                        par_stats[par]["no"] += 1
                        if len(no_match_samples) < 30:
                            no_match_samples.append(
                                (form, lemma, par, gender_key, case_name, num_name)
                            )

        # Progress every 100 words
        if (wi + 1) % 100 == 0:
            pct = 100 * total / total_expected if total_expected else 0
            sys.stderr.write(
                f"\r  {wi+1:5d}/{len(words)} lemmas, "
                f"{total:6d} forms  ({pct:5.1f}%)  "
                f"dir={direct_match} ortho={ortho_match} no={no_match}"
            )
            sys.stderr.flush()

    sys.stderr.write("\r" + " " * 80 + "\r")
    sys.stderr.flush()

    # ── Report ──
    total_rec = direct_match + ortho_match
    print(f"\n{'='*65}")
    print(f"Total inflected forms (FST paradigms): {total}")
    print(f"  Direct match:       {direct_match:6d}  ({100*direct_match/total:5.1f}%)")
    print(f"  Via ortho FST:      {ortho_match:6d}  ({100*ortho_match/total:5.1f}%)")
    print(f"  No match:           {no_match:6d}  ({100*no_match/total:5.1f}%)")
    print(f"  TOTAL RECOGNIZED:   {total_rec:6d}  ({100*total_rec/total:5.1f}%)")

    print(f"\n--- Per paradigm ---")
    par_list = []
    for par, stats in par_stats.items():
        if stats["total"] >= 10:
            rec = stats["direct"] + stats["ortho"]
            pct = 100 * rec / stats["total"]
            par_list.append(
                (par, stats["total"], rec, pct, stats["ortho"], stats["no"])
            )

    par_list.sort(key=lambda x: x[3])
    for par, tot, rec, pct, ortho, no in par_list:
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(
            f"  P{par:5s} {bar} {rec:5d}/{tot:5d} ({pct:5.1f}%)  "
            f"ortho={ortho:4d} unmatched={no:5d}"
        )

    print(f"\n--- Unmatched samples ---")
    for form, lemma, par, gender, case_name, num_name in no_match_samples[:25]:
        print(
            f"  {form:30s} ← {lemma:25s} P{par:4s} {gender:5s} "
            f"{case_name:10s} {num_name}"
        )

    print(f"\n--- Ortho-only match samples ---")
    ortho_samples = _gather_ortho_samples(words, main_fst, lenient_fst, max_samples=20)
    for form, lemma, par, norm in ortho_samples:
        print(f"  {form:30s} → {norm:25s} ← {lemma} P{par}")

    if not no_match and not ortho_match:
        print("(no ortho matches or unmatched forms)")


def _gather_ortho_samples(
    words: list, main_fst: FST, ortho_fst: FST, max_samples: int = 20
) -> list:
    samples = []
    for w in words:
        par = w.get("paradigm", "")
        if par not in ALL_FST_PARS:
            continue
        if "forms" not in w or "declension" not in w["forms"]:
            continue
        lemma = w["word"]
        for decl in w["forms"]["declension"]:
            for case_info in decl.get("cases", []):
                if case_info.get("case", "") not in CASE_MAP:
                    continue
                for num_name in ("singular", "plural"):
                    form = case_info.get(num_name, "").strip()
                    if not form or form == "—":
                        continue
                    f_lower = form.lower()
                    direct = list(main_fst.analyze(f_lower))
                    if direct:
                        continue
                    analyses = list(ortho_fst.analyze(f_lower))
                    if analyses:
                        samples.append((form, lemma, par, analyses[0]))
                        if len(samples) >= max_samples:
                            return samples
    return samples


# ── Build FST paradigm set: P9-P70 (what the FST morphology covers) ──
_fst_pars = set()

def _par_int(p: str) -> int:
    try:
        return int(p.rstrip("abcdefghijklmnopqrstuvwxyz"))
    except ValueError:
        return 999

for _e in json.loads(GOLD.read_text(encoding="utf-8")):
    _fst_pars.add(_e["paradigm"])

for _w in json.loads(WORDLIST.read_text(encoding="utf-8")):
    if _w["paradigm"] and _par_int(_w["paradigm"]) <= 70:
        _fst_pars.add(_w["paradigm"])

ALL_FST_PARS = _fst_pars

if __name__ == "__main__":
    main()
