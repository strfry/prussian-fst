#!/usr/bin/env python3
"""Cross-reference Twanksta forms against the YouTube corpus.

Identifies forms in Twanksta that don't appear in the corpus,
and finds near-matches that suggest spelling errors.
"""

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
YOUTUBE_SENTENCES = Path("../../prussian-corpus/parsed/youtube_corpus_sentences.json")

def fold(s: str) -> str:
    """Fold to NFC, lowercase, remove diacritics."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", s.lower())

def load_twanksta_forms():
    """Extract all unique inflected forms from Twanksta entries."""
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
    forms = set()
    lemma_forms = {}  # lemma -> list of forms
    for e in raw:
        word = e.get("word", "")
        if not word:
            continue
        forms.add(word)
        lemma_forms.setdefault(word, []).append(word)
        decl = e.get("forms", {}).get("declension", [])
        for g in decl:
            for c in g.get("cases", []):
                for num in ("singular", "plural"):
                    f = c.get(num, "")
                    if f and " " not in f:
                        forms.add(f)
                        lemma_forms.setdefault(word, []).append(f)
        parts = e.get("forms", {}).get("participles", [])
        for p in parts:
            f = p.get("form", "")
            if f and " " not in f:
                forms.add(f)
                lemma_forms.setdefault(word, []).append(f)
    return forms, lemma_forms

def load_corpus_tokens():
    """Extract all unique tokens from YouTube corpus sentences."""
    raw = json.loads(YOUTUBE_SENTENCES.read_text(encoding="utf-8"))
    tokens = set()
    for e in raw:
        for key in ("text_clean", "text", "text_norm"):
            t = e.get(key, "")
            if t:
                for tok in t.split():
                    tok = tok.strip(",.!?;:()[]\"'-")
                    if tok:
                        tokens.add(tok)
    return tokens

def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = min(
                prev + (0 if a[i-1] == b[j-1] else 1),
                dp[j] + 1,
                dp[j-1] + 1,
            )
            prev = temp
    return dp[n]

def main():
    print("Loading Twanksta forms...")
    tw_forms, lemma_forms = load_twanksta_forms()
    print(f"  {len(tw_forms)} unique forms from {len(lemma_forms)} lemmas")

    print("Loading YouTube corpus tokens...")
    corpus_tokens = load_corpus_tokens()
    print(f"  {len(corpus_tokens)} unique tokens")

    # Fold both for comparison
    tw_folded = {fold(f): f for f in tw_forms}
    corpus_folded = {fold(t): t for t in corpus_tokens}

    # Report forms with no corpus match
    print(f"\n=== Twanksta forms NOT found in YouTube corpus ===")
    no_match = []
    for folded, orig in sorted(tw_folded.items()):
        if folded not in corpus_folded:
            no_match.append(orig)

    no_match = sorted(set(no_match))
    print(f"  {len(no_match)} forms not attested in corpus")

    # Near-miss search: for each unmatched form, find closest corpus word
    print(f"\n=== Near-misses (edit distance 1-2) ===")
    near_misses = []
    for form in no_match:
        folded_form = fold(form)
        # Skip very short forms
        if len(folded_form) <= 2:
            continue
        candidates = []
        for ct in sorted(corpus_tokens):
            folded_ct = fold(ct)
            if abs(len(folded_form) - len(folded_ct)) > 2:
                continue
            d = edit_distance(folded_form, folded_ct)
            if 1 <= d <= 2:
                candidates.append((d, ct))
        candidates.sort()
        if candidates:
            near_misses.append((form, candidates[:3]))

    for form, cands in sorted(near_misses, key=lambda x: x[0]):
        cand_str = "; ".join(f"'{c[1]}' (dist={c[0]})" for c in cands)
        # Find lemma
        for lemma, flist in sorted(lemma_forms.items()):
            if form in flist:
                print(f"  {form}  [{lemma}]  → {cand_str}")
                break
        else:
            print(f"  {form}  → {cand_str}")

    # Also check: corpus forms that DON'T appear in Twanksta
    print(f"\n=== Corpus forms NOT in Twanksta (first 100) ===")
    corpus_only = sorted(corpus_folded.keys() - tw_folded.keys())
    print(f"  {len(corpus_only)} corpus tokens not in Twanksta")
    for folded_ct in sorted(corpus_only)[:100]:
        orig = corpus_folded[folded_ct]
        print(f"  {orig}")

if __name__ == "__main__":
    main()
