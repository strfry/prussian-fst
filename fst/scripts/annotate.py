#!/usr/bin/env python3
"""Corpus sentence annotation via FST string dump.

1. Pre-built: hfst-fst2strings → /tmp/twanksta_strings.txt
2. This script: load strings → dict, annotate corpus sentences
"""

import json
import re
import unicodedata
import sys
from collections import defaultdict
from pathlib import Path

FST_STRINGS = Path("/tmp/twanksta_strings_v2.txt")
CORPUS = Path("/home/strfry/projekte/prussian-corpus/parsed/youtube_corpus_sentences.json")
SKIP_VIDEOS = {"qLwBCWtMuH8"}

def fold(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", s.lower())

def extract_prussian_tokens(text):
    if re.match(r'^[A-Z]{2,5}:', text):
        if not text.startswith('PR:'):
            return []
        text = text[3:].lstrip()
    text = text.split("//")[0]
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'\([^)]*\)', '', text)
    tokens = []
    for tok in text.split():
        tok = tok.lstrip('=/')
        tok = tok.strip('.,!?;:()[]{}«»\"\' \t')
        if tok and len(tok) >= 2 and tok.isalpha():
            tokens.append(tok)
    return tokens

def load_fst():
    print("Loading FST strings...", file=sys.stderr)
    pairs = defaultdict(list)
    for line in FST_STRINGS.open():
        line = line.strip()
        if not line or ':' not in line:
            continue
        # Format: analysis:surface
        analysis, surface = line.rsplit(':', 1)
        pairs[surface].append(analysis)
    print(f"  {len(pairs)} surface forms, {sum(len(v) for v in pairs.values())} analyses", file=sys.stderr)
    return pairs

def main():
    pairs = load_fst()

    print("Loading corpus...", file=sys.stderr)
    raw = json.loads(CORPUS.read_text(encoding="utf-8"))
    print(f"  {len(raw)} entries", file=sys.stderr)

    stats = {"sentences": 0, "tokens": 0, "covered": 0, "oov": 0}
    oov_by_token = defaultdict(int)

    for e in raw:
        sources = e.get("sources", [])
        if sources and all(s.get("video_id") in SKIP_VIDEOS for s in sources):
            continue

        text = e.get("text", "")
        tokens = extract_prussian_tokens(text)
        if not tokens:
            continue

        stats["sentences"] += 1
        hasil = []

        for tok in tokens:
            stats["tokens"] += 1
            res = pairs.get(tok) or pairs.get(tok.lower())
            if res:
                stats["covered"] += 1
                hasil.append((tok, res[:3]))
            else:
                stats["oov"] += 1
                hasil.append((tok, ["❌ OOV"]))
                oov_by_token[tok.lower()] += 1

        # Print every 10th sentence or if OOV
        # if any(a[0] == "❌ OOV" for _, a in hasil):
        print(f"\n  {text[:90]}")
        for tok, ans in hasil:
            print(f"    {tok:<20} → {'; '.join(ans):<50}")

    print(f"\n{'#'*60}")
    print(f"  SUMMARY")
    print(f"{'#'*60}")
    print(f"  Sentences: {stats['sentences']}")
    print(f"  Tokens:    {stats['tokens']}")
    print(f"  Covered:   {stats['covered']} ({stats['covered']/stats['tokens']*100:.1f}%)")
    print(f"  OOV:       {stats['oov']} ({stats['oov']/stats['tokens']*100:.1f}%)")
    print(f"\n  Top OOV:")
    for tok, cnt in sorted(oov_by_token.items(), key=lambda x: -x[1])[:20]:
        print(f"    {tok:<20} {cnt:>5}x")

if __name__ == "__main__":
    main()
