#!/usr/bin/env python3
"""Generate nom_stems.lexc from Twanksta data.

For each lemma, extract ALL forms from the Twanksta JSON's declension data.
Each lemma gets its own full forms. No shared paradigms.
"""

import json
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
OUT = Path("nom_stems.lexc")

def lexc_esc(s):
    return s.replace(" ", "% ")

CASE_MAP = {
    "Nominative": "Nom", "Genitive": "Gen",
    "Dative": "Dat", "Accusative": "Akk",
}

GENDER_MAP = {"masc": "+Masc", "fem": "+Fem", "neut": "+Neut", "": ""}

def inflected_forms(entry):
    """Extract (tag, form) tuples from a Twanksta entry."""
    decl = entry.get("forms", {}).get("declension", [])
    results = []
    for gen_decl in decl:
        g = gen_decl.get("gender", "masc")
        g_tag = GENDER_MAP.get(g, "")
        for case_entry in gen_decl.get("cases", []):
            c = case_entry.get("case", "")
            c_tag = CASE_MAP.get(c, c[:3])
            for num_attr, num_tag in [("singular", "Sg"), ("plural", "Pl")]:
                form = case_entry.get(num_attr, "")
                if form and " " not in form and "/" not in form:
                    results.append((f"+{num_tag}+{c_tag}{g_tag}", form))
    return results

def emit_entries(all_lines, entries, pos_tag):
    """Emit lexc lines for a list of (word, paradigm, gender, forms) entries."""
    for word, gender, forms in entries:
        g = GENDER_MAP.get(gender, "")
        upper = f"{lexc_esc(word)}+{pos_tag}"
        if not forms:
            all_lines.append(f"  {upper}+Sg+Nom{g}:{lexc_esc(word)}  # ;")
        else:
            for tag, form in forms:
                all_lines.append(f"  {upper}{tag}:{lexc_esc(form)}  # ;")

def main():
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
    
    # Group by POS
    nouns = defaultdict(list)
    adjectives = defaultdict(list)
    pronouns = defaultdict(list)
    numerals = defaultdict(list)
    stats = defaultdict(int)
    
    for e in raw:
        word = e.get("word", "")
        if not word or " " in word or "/" in word:
            continue
        par = e.get("paradigm", "")
        if not par:
            continue
        gender = e.get("gender", "")
        forms = inflected_forms(e)
        
        if par in {"25","26","27","28","29","30","30a","31"}:
            adjectives[par].append((word, gender, forms))
        elif par in {"9","10","11","12","13","14","15","16","17","18","19","20","21","3"}:
            pronouns[par].append((word, gender, forms))
        elif par in {"22","23","24"}:
            numerals[par].append((word, gender, forms))
        elif par == "70":
            pass  # Part70 handled elsewhere
        else:
            nouns[par].append((word, gender, forms))
    
    # Build output
    all_lines = []
    all_lines.append("! Nominal stems — generated from Twanksta data")
    all_lines.append(f"! Source: {TWANKSTA}")
    all_lines.append("")
    all_lines.append("LEXICON Nouns")
    for par in sorted(nouns, key=lambda x: int(x) if x.isdigit() else 999):
        all_lines.append(f"  N{par}_stems ;")
    all_lines.append("")
    all_lines.append("LEXICON Adjectives")
    for par in sorted(adjectives, key=lambda x: int(x) if x.isdigit() else 999):
        all_lines.append(f"  A{par}_stems ;")
    all_lines.append("")

    
    # Emit noun lexicons
    for par in sorted(nouns, key=lambda x: int(x) if x.isdigit() else 999):
        entries = nouns[par]
        all_lines.append(f"! N{par} — {len(entries)} entries")
        all_lines.append(f"LEXICON N{par}_stems")
        emit_entries(all_lines, entries, "N")
        all_lines.append("")
    
    # Emit adjective lexicons
    for par in sorted(adjectives, key=lambda x: int(x) if x.isdigit() else 999):
        entries = adjectives[par]
        all_lines.append(f"! A{par} — {len(entries)} entries")
        all_lines.append(f"LEXICON A{par}_stems")
        emit_entries(all_lines, entries, "Adj")
        all_lines.append("")
    

    
    OUT.write_text("\n".join(all_lines) + "\n", encoding="utf-8")
    
    total_nouns = sum(len(v) for v in nouns.values())
    total_adj = sum(len(v) for v in adjectives.values())
    print(f"Wrote {OUT}")
    print(f"  Nouns: {total_nouns} entries in {len(nouns)} paradigms")
    print(f"  Adjectives: {total_adj} entries in {len(adjectives)} paradigms")
    print(f"  Total lines: {len(all_lines)}")

if __name__ == "__main__":
    main()
