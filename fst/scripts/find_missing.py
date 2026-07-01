#!/usr/bin/env python3
"""Find corpus tokens NOT in Twanksta, with lemma suggestions.

Uses the raw `text` field from youtube_corpus_sentences.json,
strips English translations (//...), annotations ([...], (...)),
punctuation, and leading /= markers.
"""

import json
import unicodedata
import re
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../prussian-corpus/parsed/twanksta_entries.json")
TWANKSTA_VERBS = Path("../twanksta")
CORPUS_SENTENCES = Path("../../prussian-corpus/parsed/youtube_corpus_sentences.json")

def fold(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", s.lower())

def extract_prussian_tokens(text):
    """Strip the raw text field to get clean Prussian tokens."""
    # Skip non-Prussian language segments
    if re.match(r'^[A-Z]{2,5}:', text):
        if not text.startswith('PR:'):
            return []  # skip LT:, EN:, etc.
        text = text[3:].lstrip()  # strip PR: prefix
    # Remove everything after // (English/translation part)
    text = text.split("//")[0]

    # Remove [...]-annotations (editorial)
    text = re.sub(r'\[[^\]]*\]', '', text)
    # Remove (...)-annotations (parenthetical glosses)
    text = re.sub(r'\([^)]*\)', '', text)

    tokens = []
    for tok in text.split():
        # Strip leading = or /
        tok = tok.lstrip('=/')
        # Strip trailing punctuation
        tok = tok.strip('.,!?;:()[]{}«»\"\' \t')
        if not tok:
            continue
        tokens.append(tok)
    return tokens

def load_twanksta_all_forms():
    forms = set()
    lemma_forms = defaultdict(set)

    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
    for e in raw:
        word = e.get("word", "")
        if not word or " " in word or "/" in word:
            continue
        forms.add(fold(word))
        lemma_forms[word].add(word)
        decl = e.get("forms", {}).get("declension", [])
        for g in decl:
            for c in g.get("cases", []):
                for num in ("singular", "plural"):
                    f = c.get(num, "")
                    if f and " " not in f and "/" not in f:
                        forms.add(fold(f))
                        lemma_forms[word].add(f)
        parts = e.get("forms", {}).get("participles", [])
        for p in parts:
            f = p.get("form", "")
            if f and " " not in f and "/" not in f:
                forms.add(fold(f))
                lemma_forms[word].add(f)

        # Verb forms (indicative, optative, imperative, subjunctive)
        for mood in ("indicative", "optative", "imperative", "subjunctive"):
            val = e.get("forms", {}).get(mood)
            if isinstance(val, list):
                for tense_entry in val:
                    if isinstance(tense_entry, dict):
                        # indicative: [{"tense": "Present", "forms": [{"pronoun":...,"form":...}]}]
                        for entry in tense_entry.get("forms", []):
                            f = entry.get("form", "")
                            if f and " " not in f and "/" not in f and "\n" not in f:
                                f = f.strip()
                                forms.add(fold(f))
                                lemma_forms[word].add(f)
                        # imperative/subjunctive: [{"pronoun":...,"form":...}]
                        f = tense_entry.get("form", "")
                        if f and " " not in f and "/" not in f and "\n" not in f:
                            f = f.strip()
                            forms.add(fold(f))
                            lemma_forms[word].add(f)
            elif isinstance(val, str):
                # optative: single string like "birbinsei"
                f = val.strip()
                if f and " " not in f and "/" not in f and "\n" not in f:
                    forms.add(fold(f))
                    lemma_forms[word].add(f)

    for d in sorted(TWANKSTA_VERBS.iterdir()):
        if not d.name[0].isdigit():
            continue
        vj = d / "verb.json"
        if not vj.exists():
            continue
        vdata = json.loads(vj.read_text(encoding="utf-8"))
        lemma = vdata["lemma"]
        lemma_forms[lemma].add(lemma)
        forms.add(fold(lemma))
        for tense in ("present", "preterite"):
            for key in ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl"):
                f = vdata["forms"].get(tense, {}).get(key, "")
                if f and " " not in f and "/" not in f and "\n" not in f:
                    f = f.strip()
                    forms.add(fold(f))
                    lemma_forms[lemma].add(f)

    return forms, lemma_forms

SKIP_VIDEOS = {"qLwBCWtMuH8"}  # unreliable live-translated segments

def load_corpus_tokens():
    raw = json.loads(CORPUS_SENTENCES.read_text(encoding="utf-8"))
    folded_to_orig = {}
    for e in raw:
        # Skip entries that only appear in unreliable videos
        sources = e.get("sources", [])
        if sources and all(s.get("video_id") in SKIP_VIDEOS for s in sources):
            continue
        text = e.get("text", "")
        for tok in extract_prussian_tokens(text):
            folded_to_orig.setdefault(fold(tok), tok)
    return folded_to_orig

def gemination_variants(form):
    results = []
    # double -> single
    for m in re.finditer(r'(.)\1', form):
        alt = form[:m.start()] + m.group(1) + form[m.end():]
        results.append((alt, f"double->single({m.group(1)})"))
    # single -> double
    for i in range(len(form)):
        if i+1 < len(form) and form[i] == form[i+1]:
            continue
        alt = form[:i+1] + form[i] + form[i+1:]
        results.append((alt, f"single->double({form[i]})"))
    return results

def vowel_variants(form):
    vpairs = {'a':'ā','ā':'a','e':'ē','ē':'e','i':'ī','ī':'i',
              'o':'ō','ō':'o','u':'ū','ū':'u'}
    results = []
    for i, ch in enumerate(form):
        if ch in vpairs:
            alt = form[:i] + vpairs[ch] + form[i+1:]
            results.append((alt, f"vowel {ch}->{vpairs[ch]}"))
    return results

def main():
    print("Loading Twanksta forms...")
    tw_forms, lemma_forms = load_twanksta_all_forms()
    print(f"  {len(tw_forms)} forms, {len(lemma_forms)} lemmas")

    print("Loading corpus tokens (raw text, stripped)...")
    corpus = load_corpus_tokens()
    print(f"  {len(corpus)} tokens")

    tw_folded = set()
    lemma_by_folded = defaultdict(list)
    form_by_folded = {}
    for lemma, forms in lemma_forms.items():
        for f in forms:
            ff = fold(f)
            tw_folded.add(ff)
            lemma_by_folded[ff].append(lemma)
            form_by_folded[ff] = f

    not_found = [(orig, ftok) for ftok, orig in sorted(corpus.items()) if ftok not in tw_folded]
    print(f"  Not in Twanksta: {len(not_found)}")

    has_suggestion = 0
    findings_by_type = defaultdict(list)

    for orig, ftok in not_found:
        if len(ftok) <= 2:
            continue
        matched = False
        for v, kind in gemination_variants(ftok):
            if v in tw_folded:
                tw_form = form_by_folded.get(v, "?")
                lemma = lemma_by_folded[v][0]
                findings_by_type[kind].append((orig, tw_form, lemma))
                matched = True
                break
        if matched:
            has_suggestion += 1
            continue
        for v, kind in vowel_variants(ftok):
            if v in tw_folded:
                tw_form = form_by_folded.get(v, "?")
                lemma = lemma_by_folded[v][0]
                findings_by_type[kind].append((orig, tw_form, lemma))
                matched = True
                break
        if matched:
            has_suggestion += 1

    print(f"\n{'─'*80}")
    print(f"  Corpus             Twanksta            Lemma                Match")
    print(f"{'─'*80}")
    for kind in sorted(findings_by_type):
        items = sorted(findings_by_type[kind])
        count = len(items)
        print(f"\n  ── {kind} ({count}x) ──")
        for orig, tw_form, lemma in items:
            print(f"  {orig:<16} → {tw_form:<18} → {lemma:<20}")

    print(f"\n{'─'*80}")
    print(f"  Total missing from Twanksta: {len(not_found)}  |  With suggestion: {has_suggestion}")
    print(f"{'─'*80}")

if __name__ == "__main__":
    main()
