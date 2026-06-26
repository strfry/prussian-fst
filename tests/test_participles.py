#!/usr/bin/env python3
"""Test 3: Participle declension coverage.

For every verb in prusaspira_entries.json that carries declined participles,
generate each attested cell (gender × case × number, all three participle types)
through the FST and check the attested surface is among the generated variants.

Present/passive decline with two stress-graded stems chosen by the lexeme's
accent class (Rinkevičius 2009): a mobile stem de-accents under a strong ending,
a barytone stem keeps its accent. Each cell therefore generates exactly one form.

Pass criterion: ≥ 95 % of attested cells covered. The residual (~4–5 %) is the
soft -tas vowel-stem passive (modelled as citation-only, Standardvariation), one
corrupt source cell (present Fem-Dat-Pl, rendered with `ț`), and a handful of
verbs whose participle stem diverges between the two sources.
"""

import json
import subprocess
import sys
from collections import Counter

FST = "fst/build/prusaspira.hfst"
GENDER = {"m": "Masc", "f": "Fem", "n": "Neut"}
CASE = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Akk"}
TYPE = {"Present": "Pres", "Past": "Pret", "Passive": "Pass"}
THRESHOLD = 95.0


def collect_pairs():
    with open("data/external/prusaspira_entries.json", encoding="utf-8") as f:
        data = json.load(f)
    pairs = []
    for e in data:
        word = e["word"]
        core = word[:-3] if word.endswith(" si") else word
        if " " in core:                       # multiword lemma — not modelled
            continue
        for part in e.get("forms", {}).get("participles", []):
            t = part.get("type")
            if t not in TYPE:
                continue
            form = part.get("form", "")
            if form.endswith(" si"):
                form = form[:-3]
            end_ok = form.endswith("uns") if t == "Past" else form.endswith("s")
            if not end_ok or " " in form:
                continue
            for g in part.get("full_declension", []):
                gen = GENDER.get(g["gender"])
                if not gen:
                    continue
                for cs in g["cases"]:
                    c = CASE.get(cs["case"])
                    for num, tag in (("singular", "Sg"), ("plural", "Pl")):
                        cf = cs.get(num, "")
                        if not cf or " " in cf:
                            continue
                        ana = f"{word}+V+Part+{TYPE[t]}+{gen}+{tag}+{c}"
                        pairs.append((ana, cf, t))
    return pairs


def main():
    pairs = collect_pairs()
    inp = "\n".join(a for a, _, _ in pairs) + "\n"
    out = subprocess.run(["hfst-lookup", "-q", FST], input=inp,
                         capture_output=True, text=True, timeout=120).stdout
    gen = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        f = line.split("\t")
        if len(f) >= 2 and not f[1].endswith("+?"):
            gen.setdefault(f[0], set()).add(f[1])

    by_type = Counter(t for *_, t in pairs)
    ok = Counter()
    nogen = 0
    for ana, att, t in pairs:
        outs = gen.get(ana)
        if not outs:
            nogen += 1
            continue
        if att in outs:
            ok[t] += 1
    total = len(pairs)
    covered = sum(ok.values())
    pct = covered / total * 100 if total else 0.0

    print(f"Getestet: {total} Partizip-Zellen aus prusaspira full_declension")
    for t in ("Past", "Present", "Passive"):
        n = by_type[t]
        print(f"  {t:8s}: {ok[t]}/{n} ({ok[t]/n*100:.1f}%)" if n else f"  {t}: -")
    print(f"  Nicht generiert (soft-Passiv u.ä.): {nogen}")
    print(f"\n  Abdeckung gesamt: {covered}/{total} ({pct:.1f}%)")

    if pct >= THRESHOLD:
        print(f"\n✓ OK (≥ {THRESHOLD:.0f}%)")
        return 0
    print(f"\n✗ Abdeckung unter {THRESHOLD:.0f}%")
    return 1


if __name__ == "__main__":
    sys.exit(main())
