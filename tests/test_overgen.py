#!/usr/bin/env python3
"""Test 1: Overgeneration test for verb generation.

For a sample of verb lemmas with forms.indicative:
  generate all tense×person forms via a single hfst-lookup pipe
  and compare against the expected forms from the dictionary.
"""

import json
import subprocess
import sys
import random
import tempfile
import os


PRON_TO_PERS = {
    "as": "1sg", "tū": "2sg", "tāns/tenā/tennan": "3sg",
    "mes": "1pl", "jūs": "2pl", "tenēi/tennas": "3pl",
}

TAG_MAP = {
    ("present", "1sg"): "Pres+P1+Sg",
    ("present", "2sg"): "Pres+P2+Sg",
    ("present", "3sg"): "Pres+P3+Sg",
    ("present", "1pl"): "Pres+P1+Pl",
    ("present", "2pl"): "Pres+P2+Pl",
    ("present", "3pl"): "Pres+P3+Pl",
    ("preterite", "1sg"): "Pret+P1+Sg",
    ("preterite", "2sg"): "Pret+P2+Sg",
    ("preterite", "3sg"): "Pret+P3+Sg",
    ("preterite", "1pl"): "Pret+P1+Pl",
    ("preterite", "2pl"): "Pret+P2+Pl",
    ("preterite", "3pl"): "Pret+P3+Pl",
}


def main():
    fst_path = "fst/build/prusaspira.hfst"

    with open("data/external/prusaspira_entries.json") as f:
        pr = json.load(f)

    verbs = []
    for e in pr:
        try:
            p = int(e.get("paradigm", 0))
        except ValueError:
            continue
        if not (71 <= p <= 144):
            continue
        if e.get("forms", {}).get("indicative"):
            verbs.append(e)

    random.seed(42)
    sample_size = min(200, len(verbs))
    sample = random.sample(verbs, sample_size)

    # Build all queries and expected forms
    queries = []
    expected_map = {}  # query -> expected_form

    for e in sample:
        word = e["word"]
        is_reflexive = word.endswith(" si")
        ind = e["forms"]["indicative"]
        present = past = None
        for item in ind:
            if item["tense"] == "Present":
                present = item
            elif item["tense"] == "Past":
                past = item
        if not present or not past:
            continue

        for tense_data, tense_key in [(present, "present"), (past, "preterite")]:
            for pf in tense_data["forms"]:
                pers = PRON_TO_PERS.get(pf["pronoun"])
                if not pers:
                    continue
                expected = pf["form"].split("/")[0].strip()
                if not expected:
                    continue
                # Strip reflexive " si" from expected form for comparison
                # (si is a clitic, not part of the verb paradigm)
                expected_clean = expected[:-3] if expected.endswith(" si") else expected

                tag = TAG_MAP[(tense_key, pers)]
                query = f"{word}+V+{tag}"
                queries.append(query)
                expected_map[query] = expected_clean

    # Run hfst-lookup in batch
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        for q in queries:
            tf.write(q + "\n")
        query_file = tf.name

    try:
        result = subprocess.run(
            ["hfst-lookup", "-q", fst_path],
            stdin=open(query_file),
            capture_output=True, text=True, timeout=30,
        )
    finally:
        os.unlink(query_file)

    # Parse results: "query\tFORM\tweight"
    generated_map = {}  # query -> list of forms
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            q = parts[0].strip()
            form = parts[1].strip()
            if q not in generated_map:
                generated_map[q] = []
            generated_map[q].append(form)

    # Compare
    total = len(queries)
    correct = 0
    overgen = 0
    missing = 0
    wrong = 0

    overgen_ex = []
    missing_ex = []
    wrong_ex = []

    for q in queries:
        expected = expected_map[q]
        generated = generated_map.get(q, [])

        if not generated:
            missing += 1
            if len(missing_ex) < 5:
                missing_ex.append(f"{q}: expected={expected!r}, got nothing")
        elif expected in generated:
            correct += 1
            if len(generated) > 1:
                extra = [g for g in generated if g != expected]
                if extra:  # only count if there are actually DIFFERENT extra forms
                    overgen += 1
                    if len(overgen_ex) < 8:
                        overgen_ex.append(f"{q}: OK={expected!r} + extra={extra}")
        else:
            wrong += 1
            if len(wrong_ex) < 8:
                wrong_ex.append(f"{q}: expected={expected!r}, got={generated}")

    pct_correct = correct / total * 100 if total else 0
    pct_overgen = overgen / total * 100 if total else 0
    pct_missing = missing / total * 100 if total else 0
    pct_wrong = wrong / total * 100 if total else 0

    print(f"Getestet: {total} Zellen aus {sample_size} Verben")
    print(f"  Richtig:         {correct:>5d} ({pct_correct:.1f}%)")
    print(f"  Davon überproduziert: {overgen:>5d} ({pct_overgen:.1f}%)")
    print(f"  Fehlend:         {missing:>5d} ({pct_missing:.1f}%)")
    print(f"  Falscher Stamm:  {wrong:>5d} ({pct_wrong:.1f}%)")

    if overgen_ex:
        print(f"\n  Überproduktion:")
        for ex in overgen_ex:
            print(f"    {ex}")
    if missing_ex:
        print(f"\n  Fehlend:")
        for ex in missing_ex:
            print(f"    {ex}")
    if wrong_ex:
        print(f"\n  Falsch:")
        for ex in wrong_ex:
            print(f"    {ex}")

    exit_code = 0
    if pct_wrong > 5:
        print(f"\n✗ {pct_wrong:.1f}% falsche Formen (>5%)")
        exit_code = 1
    else:
        print(f"\n✓ OK")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
