#!/usr/bin/env python3
"""Generate verb_participle_stems.lexc from Twanksta data.

For each verb, extract present, past, and passive participle forms
from twanksta_entries.json.
"""

import json
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
OUT = Path("verb_participle_stems.lexc")

def lexc_esc(s):
    return s.replace(" ", "% ")

def classify_participles(parts):
    """Extract participle forms from the parts list.
    Returns dict: cat -> form where cat in {present, past, passive}."""
    forms = {}
    for p in parts:
        frm = p.get("form", "")
        ptype = p.get("type", "")
        bare = frm[:-3] if frm.endswith(" si") else frm
        if " " in bare:
            continue
        if ptype.lower() == "present" and bare.endswith("s"):
            forms["present"] = bare
        elif ptype.lower() == "past" and bare.endswith("uns"):
            forms["past"] = bare
        elif ptype.lower() == "passive" and bare.endswith("s"):
            forms["passive"] = bare
    return forms

def main():
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
    
    # Collect participles per lemma
    verb_forms = {}
    for e in raw:
        parts = e.get("forms", {}).get("participles")
        if not parts:
            continue
        word = e["word"]
        core = word[:-3] if word.endswith(" si") else word
        if " " in core:
            continue
        forms = classify_participles(parts)
        if not forms:
            continue
        verb_forms.setdefault(word, {}).update(forms)
    
    out = []
    out.append("! Participle stems — generated from Twanksta data")
    out.append(f"! Source: {TWANKSTA}")
    out.append("")
    out.append("LEXICON PtcpStems")
    
    stats = {"present": 0, "past": 0, "passive": 0, "passive_soft": 0, "Mob": 0, "Bar": 0}
    
    for lemma in sorted(verb_forms):
        forms = verb_forms[lemma]
        lem = lexc_esc(lemma)
        
        # Present participle (stem = form minus final 's')
        if "present" in forms:
            stem = forms["present"][:-1]
            cls = "Mob"  # default for Twanksta-only verbs
            stats["Mob"] += 1
            out.append(f"  {lem}+V+Part+Pres:{lexc_esc(stem)}  PtcpPres{cls} ;")
            stats["present"] += 1
        
        # Past participle (stem = form minus 'uns')
        if "past" in forms:
            stem = forms["past"][:-3]
            out.append(f"  {lem}+V+Part+Pret:{lexc_esc(stem)}  PtcpPast ;")
            stats["past"] += 1
        
        # Passive participle
        if "passive" in forms:
            form = forms["passive"]
            if form.endswith("ts"):
                stem = form[:-1]
                cls = "Mob"  # default
                stats["Mob"] += 1
                out.append(f"  {lem}+V+Part+Pass:{lexc_esc(stem)}  PtcpPass{cls} ;")
                stats["passive"] += 1
            else:
                # soft/vowel-stem passive: citation only
                out.append(f"  {lem}+V+Part+Pass+Masc+Sg+Nom:{lexc_esc(form)}  # ;")
                stats["passive_soft"] += 1
    
    out.append("")
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  present={stats['present']} past={stats['past']} "
          f"passive={stats['passive']} passive_soft={stats['passive_soft']}")

if __name__ == "__main__":
    main()
