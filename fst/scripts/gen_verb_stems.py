#!/usr/bin/env python3
"""Generate verb_stems.lexc from Twanksta verb.json data.

Generate FULL forms for each verb (no shared paradigms).
Each verb lemma has 12 verb form entries (6 present + 6 preterite).
"""

import json
from collections import defaultdict
from pathlib import Path

TWANKSTA_DIR = Path("../twanksta")
OUT = Path("verb_stems.lexc")

PERSON_TAGS = ["P1+Sg", "P2+Sg", "P3+Sg", "P1+Pl", "P2+Pl", "P3+Pl"]
FORM_KEYS = ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]

def lexc_esc(s):
    return s.replace(" ", "% ")

def main():
    verb_data = []
    for d in sorted(TWANKSTA_DIR.iterdir()):
        if not d.name[0].isdigit():
            continue
        vj = d / "verb.json"
        if not vj.exists():
            continue
        data = json.loads(vj.read_text(encoding="utf-8"))
        lemma = data["lemma"]
        forms = data["forms"]
        pres = forms["present"]
        pret = forms["preterite"]
        verb_data.append((lemma, pres, pret))
    
    out = []
    out.append("! Verb stems — generated from Twanksta verb.json data")
    out.append(f"! Source: {TWANKSTA_DIR}")
    out.append("")
    out.append("LEXICON Verbs")
    
    # Emit full form entries
    for lemma, pres, pret in sorted(verb_data):
        upper = f"{lexc_esc(lemma)}+V"
        for tag_key, form_key in zip(PERSON_TAGS, FORM_KEYS):
            f = pres.get(form_key, "")
            if f and " " not in f and "/" not in f and "\n" not in f:
                out.append(f"  {upper}+Pres+{tag_key}:{lexc_esc(f.strip())}  # ;")
        for tag_key, form_key in zip(PERSON_TAGS, FORM_KEYS):
            f = pret.get(form_key, "")
            if f and " " not in f and "/" not in f and "\n" not in f:
                out.append(f"  {upper}+Pret+{tag_key}:{lexc_esc(f.strip())}  # ;")
    
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  {len(verb_data)} verbs with full forms")

if __name__ == "__main__":
    main()
