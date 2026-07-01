#!/usr/bin/env python3
"""Find potential errors in Twanksta data by cross-referencing with YouTube corpus.

For each Twanksta form that doesn't appear in the corpus, look for near-matches.
A near-match is a corpus token that differs by at most 1 character
(especially gemination errors like birbinna -> birbina).
"""

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
YOUTUBE = Path("../../prussian-corpus/parsed/youtube_corpus_sentences.json")

def fold(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", s.lower())

def load_twanksta_forms():
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
    forms = {}  # folded -> [(orig, lemma)]
    for e in raw:
        word = e.get("word", "")
        if not word:
            continue
        forms.setdefault(fold(word), []).append((word, word))
        decl = e.get("forms", {}).get("declension", [])
        for g in decl:
            for c in g.get("cases", []):
                for num in ("singular", "plural"):
                    f = c.get(num, "")
                    if f and " " not in f:
                        forms.setdefault(fold(f), []).append((f, word))
        parts = e.get("forms", {}).get("participles", [])
        for p in parts:
            f = p.get("form", "")
            if f and " " not in f:
                forms.setdefault(fold(f), []).append((f, word))
        # verb forms
        vf = e.get("forms", {}).get("verb", {})
        for tense in ("present", "preterite"):
            for person in ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl"):
                f = vf.get(tense, {}).get(person, "")
                if f and " " not in f:
                    forms.setdefault(fold(f), []).append((f, word))
    return forms

def load_corpus_tokens():
    raw = json.loads(YOUTUBE.read_text(encoding="utf-8"))
    tokens = set()
    for e in raw:
        for key in ("text_clean", "text", "text_norm"):
            t = e.get(key, "")
            if t:
                for tok in t.split():
                    tok = tok.strip(",.!?;:()[]\"'-")
                    if tok:
                        tokens.add(tok)
    return {fold(t): t for t in tokens}

def main():
    import time
    t0 = time.time()
    
    print("Loading data...")
    tw_forms = load_twanksta_forms()
    corpus = load_corpus_tokens()
    print(f"  Twanksta: {len(tw_forms)} folded forms")
    print(f"  Corpus: {len(corpus)} folded tokens")
    
    # Find forms NOT in corpus
    not_found = []
    for folded, sources in sorted(tw_forms.items()):
        if folded not in corpus:
            not_found.append((folded, sources[0][0], sources[0][1]))
    
    print(f"\n=== Forms not in corpus: {len(not_found)} ===\n")
    
    # For each not-found form, find similar corpus tokens
    # Look for: gemination differences (single/double consonant)
    import re
    
    suggestions = []
    for folded, orig, lemma in not_found:
        if len(folded) < 3:
            continue
        
        # Find candidates with edit distance 1
        for cf, co in sorted(corpus.items()):
            # Quick filter: similar length
            if abs(len(folded) - len(cf)) > 2:
                continue
            
            # Frequency of same letters
            same = sum(1 for a, b in zip(folded, cf) if a == b)
            if same < min(len(folded), len(cf)) - 1:
                continue
            
            # Check if one has double consonant where other has single
            # Pattern: find doubled consonants
            tw_doubles = re.findall(r'(.)\1', folded)
            co_doubles = re.findall(r'(.)\1', cf)
            
            # Check if the main difference is gemination
            diff = abs(len(folded) - len(cf))
            if diff <= 1:
                suggestions.append((folded, orig, lemma, cf, co, diff))
    
    # Deduplicate and sort
    seen_pairs = set()
    unique = []
    for folded, orig, lemma, cf, co, diff in suggestions:
        key = (folded, cf)
        if key not in seen_pairs:
            seen_pairs.add(key)
            unique.append((orig, lemma, cf, co, diff))
    
    # Show likely gemination errors
    print("=== Likely gemination errors (double -> single) ===")
    for orig, lemma, cf, co, diff in sorted(unique, key=lambda x: x[4]):
        if diff == 0:
            # Same folded but different diacritics
            print(f"  DIAC: {orig:<25} [{lemma:<20}] -> corpus: {co}")
        elif diff == 1:
            print(f"  DIST1: {orig:<25} [{lemma:<20}] -> corpus: {co}")
    
    t1 = time.time()
    print(f"\nTime: {t1-t0:.1f}s")

if __name__ == "__main__":
    main()
