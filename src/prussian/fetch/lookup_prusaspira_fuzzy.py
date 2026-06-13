#!/usr/bin/env python3
"""Second pass: fuzzy + manually curated search for unmatched lemmata."""
import json, re, unicodedata
from pathlib import Path
from difflib import SequenceMatcher

PRUSASPIRA = Path("prusaspira")
DICT = Path("data/external/prussian_dictionary.json")
OUT = Path("prusaspira_lookup")

dict_entries = json.loads(DICT.read_bytes())
all_words = [e.get("word", "") for e in dict_entries]

def strip_diacritics(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def norm(s):
    return strip_diacritics(s).lower()

word_norms = [(norm(w), w) for w in all_words]
THRESHOLD = 0.75

MANUAL = {
    "weselīngis": "wesselingi",
    "sēnts": "swents",
    "mīstan": "mēstan",
    "pannin": "pannu",
    "staūs": "stas",
    "amzin": "amzjan",
    "spigsnā": "spēgsnā",
    "zmūi": "zmōi",
    "mūti": "māti",
    "klīts": "klēts",
    "klākis": "tlākis",
    "auktimmisku": "auktimmiskan",
}

results = []

for fp in sorted(PRUSASPIRA.glob("*.txt")):
    if fp.name.startswith("_"):
        continue
    m = re.match(r"(\d+[a-z]?)_(.+)\.txt$", fp.name)
    if not m:
        continue
    num, lemma = m.group(1), m.group(2)
    target_dir = OUT / fp.stem
    existing = target_dir / "lemma.json"
    if existing.exists():
        continue

    method = "fuzzy"
    best_word = None

    if lemma in MANUAL:
        best_word = MANUAL[lemma]
        method = "manual"
    else:
        lemma_norm = norm(lemma)
        scores = [(SequenceMatcher(None, lemma_norm, wn).ratio(), w) for wn, w in word_norms]
        scores = [(r, w) for r, w in scores if r >= THRESHOLD]
        scores.sort(key=lambda x: -x[0])
        if scores:
            best_word = scores[0][1]

    if best_word:
        matches = [e for e in dict_entries if e.get("word") == best_word]
        target_dir.mkdir(parents=True, exist_ok=True)
        ratio = SequenceMatcher(None, norm(lemma), norm(best_word)).ratio() if method == "fuzzy" else 1.0
        out = {
            "query": lemma,
            "match": best_word,
            "score": round(ratio, 4),
            "method": method,
            "entries": matches,
        }
        (target_dir / "lemma.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        words = [e["word"] for e in matches]
        (target_dir / "words.txt").write_text("\n".join(words) + "\n")
        results.append((fp.name, lemma, best_word, f"{ratio:.2f}", method))
    else:
        results.append((fp.name, lemma, "—", "—", "NONE"))

print(f"Fuzzy pass: {len(results)} lemmata")
for fn, q, m, sc, kind in results:
    print(f"  {kind:6} {fn} → '{q}' → '{m}' ({sc})")
