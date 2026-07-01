#!/usr/bin/env python3
"""Find likely errors in Twanksta data by comparing with YouTube corpus.

Only flags:
- Twanksta lemmas whose LEMMA (dictionary form) appears in the corpus
- Then checks each inflected form of that lemma against the corpus
- If the form doesn't appear, looks for near-matches
"""

import json
import unicodedata
import re
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
YOUTUBE = Path("../../prussian-corpus/parsed/youtube_corpus_sentences.json")

def fold(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", s.lower())

def load_twanksta():
    """Return {lemma: {inflected_forms}}"""
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
    lemma_forms = {}
    for e in raw:
        word = e.get("word", "")
        if not word or " " in word or "/" in word:
            continue
        forms = set()
        forms.add(word)
        decl = e.get("forms", {}).get("declension", [])
        for g in decl:
            for c in g.get("cases", []):
                for num in ("singular", "plural"):
                    f = c.get(num, "")
                    if f and " " not in f and "/" not in f:
                        forms.add(f)
        parts = e.get("forms", {}).get("participles", [])
        for p in parts:
            f = p.get("form", "")
            if f and " " not in f and "/" not in f:
                forms.add(f)
        verb = e.get("forms", {}).get("verb", {})
        for tense in ("present", "preterite"):
            for person in ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl"):
                f = verb.get(tense, {}).get(person, "")
                if f and " " not in f and "/" not in f and "\n" not in f:
                    forms.add(f.strip())
        lemma_forms[word] = forms
    return lemma_forms

def load_corpus():
    """Return (set of folded tokens, dict: folded->original)."""
    raw = json.loads(YOUTUBE.read_text(encoding="utf-8"))
    folded_to_orig = {}
    for e in raw:
        for key in ("text_clean", "text", "text_norm"):
            t = e.get(key, "")
            if t:
                for tok in t.split():
                    tok = tok.strip(",.!?;:()[]\"'-")
                    if tok:
                        f = fold(tok)
                        if f not in folded_to_orig:
                            folded_to_orig[f] = tok
    return folded_to_orig

def gemination_alternatives(form):
    """Generate variants with gemination changes."""
    results = set()
    # Double -> single
    for m in re.finditer(r'(.)\1', form):
        alt = form[:m.start()] + m.group(1) + form[m.end():]
        results.add(alt)
    # Single -> double
    for i in range(len(form)):
        if i+1 < len(form) and form[i] == form[i+1]:
            continue  # already double
        alt = form[:i+1] + form[i] + form[i+1:]
        if alt != form:
            results.add(alt)
    return results

def vowel_alternatives(form):
    """Generate variants with vowel length changes."""
    vpairs = {'a':'ā','ā':'a','e':'ē','ē':'e','i':'ī','ī':'i',
              'o':'ō','ō':'o','u':'ū','ū':'u'}
    results = set()
    for i, ch in enumerate(form):
        if ch in vpairs:
            alt = form[:i] + vpairs[ch] + form[i+1:]
            results.add(alt)
    return results

def main():
    print("Loading data...")
    lemma_forms = load_twanksta()
    corpus = load_corpus()
    print(f"  Twanksta: {len(lemma_forms)} lemmas")
    print(f"  Corpus: {len(corpus)} unique tokens")
    
    # Find lemmas whose LEMMA appears in corpus
    attested_lemmas = {}
    for lemma in lemma_forms:
        ff = fold(lemma)
        if ff in corpus:
            attested_lemmas[lemma] = lemma_forms[lemma]
    
    print(f"  Lemmas attested in corpus (lemma form matches): {len(attested_lemmas)}")
    
    # For each attested lemma, check all its forms against corpus
    errors = defaultdict(list)
    exact_matches = 0
    
    for lemma, forms in sorted(attested_lemmas.items()):
        lemma_errors = []
        for tw_form in sorted(forms):
            ftw = fold(tw_form)
            if ftw in corpus:
                exact_matches += 1
                continue
            
            # Form not in corpus. Try gemination variants
            found = False
            for alt in gemination_alternatives(ftw):
                if alt in corpus:
                    lemma_errors.append((tw_form, corpus[alt], "Gemination"))
                    found = True
                    break
            if found:
                continue
            
            # Try vowel length variants
            for alt in vowel_alternatives(ftw):
                if alt in corpus:
                    lemma_errors.append((tw_form, corpus[alt], "Vokallänge"))
                    found = True
                    break
            if found:
                continue
            
            # Try 1-char difference
            for ct, co in sorted(corpus.items()):
                if abs(len(ftw) - len(ct)) > 1:
                    continue
                if len(ftw) == len(ct):
                    diffs = sum(1 for a, b in zip(ftw, ct) if a != b)
                    if diffs == 1:
                        lemma_errors.append((tw_form, co, "1-Zeichen"))
                        found = True
                        break
            if found:
                continue
            
            # Try missing/extra character
            if len(ftw) > 3:
                for i in range(len(ftw)):
                    alt = ftw[:i] + ftw[i+1:]
                    if alt in corpus:
                        lemma_errors.append((tw_form, corpus[alt], f"Extra-Zeichen '{ftw[i]}'"))
                        found = True
                        break
                if found:
                    continue
                for i in range(len(ftw) + 1):
                    for ch in "aeiouāēīōūbcdfghjklmnprstvwz":
                        alt = ftw[:i] + ch + ftw[i:]
                        if alt in corpus:
                            lemma_errors.append((tw_form, corpus[alt], f"Fehlendes Zeichen '{ch}'"))
                            found = True
                            break
        
        if lemma_errors:
            errors[lemma] = lemma_errors
    
    print(f"  Exact matches: {exact_matches}")
    print(f"  Lemmas with potential errors: {len(errors)}")
    
    # Print results grouped by error type
    for lemma, errs in sorted(errors.items()):
        print(f"\n{lemma}:")
        for tw_form, corpus_form, etype in errs:
            print(f"  {tw_form:<30} → {corpus_form:<25} ({etype})")

if __name__ == "__main__":
    main()
