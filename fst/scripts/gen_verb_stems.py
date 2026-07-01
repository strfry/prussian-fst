#!/usr/bin/env python3
"""Generate verb_stems.lexc from Twanksta entries JSON.

For each verb, extract:
- Infinitive
- Present/preterite full forms (from forms.indicative)
- Optative, imperative, subjunctive forms
- Participle stems (from forms.participles, with correction for -intun verbs)
Routes participle stems to PtcpPres/PtcpPast/PtcpPass paradigms.
"""

import json
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
OUT = Path("verb_stems.lexc")

PERSON_TAGS = ["P1+Sg", "P2+Sg", "P3+Sg", "P1+Pl", "P2+Pl", "P3+Pl"]

def lexc_esc(s):
    return s.replace(" ", "% ")

PRONOUN_MAP = {
    "as": 0, "tū": 1,
    "tāns/tenā/tennan": 2, "tāns": 2, "tenā": 2, "tennan": 2,
    "mes": 3, "jūs": 4,
    "tenēi/tennas": 5, "tenēi": 5, "tennas": 5,
    "(tū)": 1, "(mes)": 3, "(jūs)": 4,
}

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
        
        if bare.endswith("uns"):
            stem = bare[:-3]
            if inf_base.endswith('īn') and stem.endswith(stem[-1] * 2):
                stem = inf_base
            result["past"] = stem
        elif bare.endswith("nts"):
            stem = bare[:-1]
            result["present"] = stem
        elif bare.endswith("ts"):
            stem = bare[:-2]
            result["passive"] = stem
        elif bare.endswith("s") and len(bare) > 3:
            stem = bare[:-1]
            result.setdefault("present", stem)
    
    return result

def extract_verb_forms(entry):
    """Extract all inflectional forms from a Twanksta verb entry.
    Returns dict: tag_string -> surface_form."""
    result = {}
    word = entry.get("word", "")
    forms = entry.get("forms", {})
    
    # Infinitive
    upper = lexc_esc(word)
    result[f"{upper}+V+Inf:{lexc_esc(word)}"] = True
    
    # Indicative (present/past)
    indic = forms.get("indicative", [])
    for tense_entry in indic:
        tname = tense_entry.get("tense", "")
        mood = "Pres" if tname == "Present" else "Pret" if tname == "Past" else None
        if not mood:
            continue
        for entry in tense_entry.get("forms", []):
            f = entry.get("form", "").strip()
            if " " in f or "/" in f or "\n" in f:
                continue
            idx = PRONOUN_MAP.get(entry.get("pronoun", ""))
            if idx is None:
                continue
            result[f"{upper}+V+{mood}+{PERSON_TAGS[idx]}:{lexc_esc(f)}"] = True
    
    # Optative (single string form)
    opt = forms.get("optative")
    if isinstance(opt, str) and opt.strip():
        f = opt.strip()
        if " " not in f and "/" not in f and "\n" not in f:
            result[f"{upper}+V+Opt+P3+Sg:{lexc_esc(f)}"] = True
    
    # Imperative
    imp = forms.get("imperative", [])
    if isinstance(imp, list):
        for entry in imp:
            f = entry.get("form", "").strip()
            if " " in f or "/" in f or "\n" in f:
                continue
            idx = PRONOUN_MAP.get(entry.get("pronoun", ""))
            if idx is None or idx not in (1, 4):  # P2+Sg, P2+Pl
                continue
            tag = "P2+Sg" if idx == 1 else "P2+Pl"
            result[f"{upper}+V+Imp+{tag}:{lexc_esc(f)}"] = True
    
    # Subjunctive
    subj = forms.get("subjunctive", [])
    if isinstance(subj, list):
        for entry in subj:
            f = entry.get("form", "").strip()
            if " " in f or "/" in f or "\n" in f:
                continue
            idx = PRONOUN_MAP.get(entry.get("pronoun", ""))
            if idx is None:
                continue
            result[f"{upper}+V+Subj+{PERSON_TAGS[idx]}:{lexc_esc(f)}"] = True
    
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
        verbs.append(e)
    
    stats = {"inf": 0, "pres": 0, "p1sg": 0, "pret": 0, "opt": 0, "imp": 0, "subj": 0, "part_pres": 0, "part_past": 0, "part_pass": 0}
    
    for e in sorted(verbs, key=lambda x: x["word"]):
        lemma = e["word"]
        
        # Emit inflectional full forms
        verb_forms = extract_verb_forms(e)
        for line in sorted(verb_forms):
            if "+Inf:" in line: stats["inf"] += 1
            elif "+Pres+" in line: stats["pres"] += 1
            elif "+Pret+" in line: stats["pret"] += 1
            elif "+Opt+" in line: stats["opt"] += 1
            elif "+Imp+" in line: stats["imp"] += 1
            elif "+Subj+" in line: stats["subj"] += 1
            out.append(f"  {line}  # ;")
        
        # Emit participle stems
        parts = classify_participles(e.get("forms", {}).get("participles", []), lemma)
        upper = lexc_esc(lemma)
        
        if "present" in parts:
            out.append(f"  {upper}+V+Part+Pres:{lexc_esc(parts['present'])}  PtcpPresMob ;")
            stats["part_pres"] += 1
        if "past" in parts:
            out.append(f"  {upper}+V+Part+Pret:{lexc_esc(parts['past'])}  PtcpPast ;")
            stats["part_past"] += 1
        if "passive" in parts:
            out.append(f"  {upper}+V+Part+Pass:{lexc_esc(parts['passive'])}  PtcpPassMob ;")
            stats["part_pass"] += 1
    
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    
    print(f"Wrote {OUT}")
    print(f"  {len(verbs)} verbs")
    print(f"  Inf: {stats['inf']}  Pres: {stats['pres']}  Pret: {stats['pret']}")
    print(f"  Opt: {stats['opt']}  Imp: {stats['imp']}  Subj: {stats['subj']}")
    print(f"  Part: pres={stats['part_pres']} past={stats['part_past']} pass={stats['part_pass']}")

if __name__ == "__main__":
    main()
