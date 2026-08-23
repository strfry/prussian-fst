#!/usr/bin/env python3
"""Export preposition rection and verb valence from twanksta_entries.json.

Best-effort structured export of the free-text ``desc`` field:

- prepositions: governed case(s), full coverage (all 29 entries).
- verbs: only ~200 of ~1900 verbs carry any valence hint in ``desc``;
  mostly prepositional rection like ``(en acc)``. The raw desc is
  included in every record so consumers can audit the parse.

Output: ../valence.json
"""

import json
import re
from pathlib import Path

# Kanonisches Dictionary aus dem corpus-Repo (keine Kopie im fst-Repo).
TWANKSTA = Path(__file__).resolve().parents[2].parent / "corpus/parsed/twanksta_entries.json"
OUT = Path(__file__).resolve().parents[2] / "build/valence.json"

CASE_NAMES = {"acc": "Acc", "akk": "Acc", "dat": "Dat", "gen": "Gen"}


def desc_gram(desc: str) -> str:
    return re.sub(r"\[.*?\]", "", desc).strip()


def main():
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))

    # ── Prepositions: desc "prp acc" / "prp dat" ──
    prepositions: dict[str, list[str]] = {}
    for e in raw:
        g = desc_gram(e.get("desc", ""))
        if not g.startswith("prp"):
            continue
        word = e.get("word", "")
        cases = prepositions.setdefault(word, [])
        for tok, name in (("acc", "Acc"), ("dat", "Dat")):
            if re.search(rf"\b{tok}\b", g) and name not in cases:
                cases.append(name)

    prep_words = set(prepositions)

    # ── Verbs: best-effort parse of the desc grammatical part ──
    prep_rection_re = re.compile(
        r"\(?\s*([\wĀ-ſ]+)\s*\+?\s*(acc|akk|dat|gen)\s*\)?", re.I)

    verbs = []
    for e in raw:
        if "indicative" not in e.get("forms", {}):
            continue
        g = desc_gram(e.get("desc", ""))
        if not g:
            continue

        rec = {"lemma": e.get("word", ""), "desc": e.get("desc", ""),
               "gram": g}
        rest = g

        prep_rection = []
        for m in prep_rection_re.finditer(g):
            prep, case = m.group(1).lower(), CASE_NAMES[m.group(2).lower()]
            if prep in prep_words or prep in ("en", "prei", "sen", "per",
                                              "surgi", "zurgi"):
                prep_rection.append({"prep": prep, "case": case})
                rest = rest.replace(m.group(0), " ")
        if prep_rection:
            rec["prep_rection"] = prep_rection

        obj_cases = []
        for m in re.finditer(r"\b(acc|akk|dat|gen)\b", rest, re.I):
            name = CASE_NAMES[m.group(1).lower()]
            if name not in obj_cases:
                obj_cases.append(name)
        if obj_cases:
            rec["obj_cases"] = obj_cases

        if re.search(r"\bitr\b", g, re.I):
            rec["intransitive"] = True
        elif re.search(r"\btr\b", g, re.I):
            rec["transitive"] = True
        if re.search(r"\bif\b", g, re.I):
            rec["takes_infinitive"] = True

        if len(rec) > 3:  # only records with at least one parsed feature
            verbs.append(rec)

    out = {
        "_source": str(TWANKSTA.name),
        "_note": ("Best-effort parse of the Twanksta desc field. "
                  "Preposition rection is complete; verb valence covers only "
                  "the verbs annotated in the dictionary. Impersonal verbs "
                  "are not encoded in Twanksta at all."),
        "prepositions": dict(sorted(prepositions.items())),
        "verbs": sorted(verbs, key=lambda r: r["lemma"]),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"Wrote {OUT}: {len(prepositions)} prepositions, "
          f"{len(verbs)} verbs with valence info")


if __name__ == "__main__":
    main()
