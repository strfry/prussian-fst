#!/usr/bin/env python3
"""Generate verb_stems.lexc from Twanksta entries JSON.

For each verb, extract:
- Present/preterite full forms (from forms.indicative)
- Participle stems (from forms.participles, with correction for -intun verbs)
Routes participle stems to PtcpPres/PtcpPast/PtcpPass paradigms.
"""

import json
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
OUT = Path("verb_stems.lexc")

PERSON_TAGS = ["P1+Sg", "P2+Sg", "P3+Sg", "P1+Pl", "P2+Pl", "P3+Pl"]
FORM_KEYS = ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]

def lexc_esc(s):
    return s.replace(" ", "% ")

def classify_participles(parts, lemma):
    """Extract participle stems from the parts list.
    Returns dict: cat -> stem where cat in {present, past, passive}."""
    result = {}
    inf_base = lemma.replace('tun', '').replace('twei', '')
    
    for p in parts:
        frm = p.get("form", "").strip()
        if " " in frm or "/" in frm or "\n" in frm:
            continue
        bare = frm[:-3] if frm.endswith(" si") else frm
        if " " in bare:
            continue
        
        # Classify by ending
        if bare.endswith("uns"):
            # Past participle: stem = form minus "uns"
            stem = bare[:-3]
            # Correct for -īntun verbs: use infinitive stem instead of present stem
            if inf_base.endswith('īn') and stem.endswith(stem[-1] * 2):
                stem = inf_base
            result["past"] = stem
        
        elif bare.endswith("nts"):
            # Present active participle: stem = form minus final -s
            stem = bare[:-1]
            result["present"] = stem
        
        elif bare.endswith("ts"):
            # Hard passive participle: stem = form minus "ts"
            stem = bare[:-2]
            result["passive"] = stem
        
        elif bare.endswith("s") and len(bare) > 3:
            # Other -s ending: default to present
            stem = bare[:-1]
            result.setdefault("present", stem)
    
    return result

def main():
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
    
    out = []
    out.append("! Verb stems — generated from Twanksta entries JSON")
    out.append(f"! Source: {TWANKSTA}")
    out.append("")
    out.append("LEXICON Verbs")
    
    verbs = []
    for e in raw:
        word = e.get("word", "")
        if not word or " " in word or "/" in word:
            continue
        par = e.get("paradigm", "")
        if not par:
            continue
        
        indic = e.get("forms", {}).get("indicative", [])
        parts_raw = e.get("forms", {}).get("participles", [])
        
        if not indic and not parts_raw:
            continue
        
        # Extract present/preterite forms (only single-word forms, no " si")
        pres_forms = {}
        pret_forms = {}
        for tense_entry in indic:
            tname = tense_entry.get("tense", "")
            for entry in tense_entry.get("forms", []):
                f = entry.get("form", "").strip()
                if " " in f or "/" in f or "\n" in f:
                    continue
                pronoun = entry.get("pronoun", "")
                # Map pronoun to our position
                if "as" == pronoun and "tū" not in pronoun:
                    idx = 0
                elif "tū" in pronoun:
                    idx = 1
                elif "tāns" in pronoun or "tenā" in pronoun or "tennan" in pronoun:
                    idx = 2
                elif "mes" in pronoun:
                    idx = 3
                elif "jūs" in pronoun:
                    idx = 4
                elif "tenēi" in pronoun or "tennas" in pronoun:
                    idx = 5
                else:
                    continue
                
                if tname == "Present":
                    pres_forms[idx] = f
                elif tname == "Past":
                    pret_forms[idx] = f
        
        verbs.append((word, pres_forms, pret_forms, parts_raw))
    
    for lemma, pres, pret, parts_raw in sorted(verbs, key=lambda x: x[0]):
        upper = lexc_esc(lemma)
        
        # Emit present forms
        for idx, tag_key in enumerate(PERSON_TAGS):
            f = pres.get(idx, "")
            if f:
                out.append(f"  {upper}+V+Pres+{tag_key}:{lexc_esc(f)}  # ;")
        
        # Emit preterite forms
        for idx, tag_key in enumerate(PERSON_TAGS):
            f = pret.get(idx, "")
            if f:
                out.append(f"  {upper}+V+Pret+{tag_key}:{lexc_esc(f)}  # ;")
        
        # Emit participle stems
        parts = classify_participles(parts_raw, lemma)
        
        if "present" in parts:
            stem = parts["present"]
            out.append(f"  {upper}+V+Part+Pres:{lexc_esc(stem)}  PtcpPresMob ;")
        
        if "past" in parts:
            stem = parts["past"]
            out.append(f"  {upper}+V+Part+Pret:{lexc_esc(stem)}  PtcpPast ;")
        
        if "passive" in parts:
            stem = parts["passive"]
            out.append(f"  {upper}+V+Part+Pass:{lexc_esc(stem)}  PtcpPassMob ;")
    
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    
    total = len(verbs)
    with_pres = sum(1 for _, p, _, _ in verbs if p)
    with_pret = sum(1 for _, _, p, _ in verbs if p)
    with_parts = sum(1 for _, _, _, p in verbs if p)
    print(f"Wrote {OUT}")
    print(f"  {total} verbs total")
    print(f"  With present: {with_pres}")
    print(f"  With preterite: {with_pret}")
    print(f"  With participles: {with_parts}")

if __name__ == "__main__":
    main()
