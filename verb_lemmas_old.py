#!/usr/bin/env python3
"""Extract verb paradigm lemmata (Inf forms) from tabula.html (P71–144).

Outputs paradigm→lemma mapping as JSON for downstream Prusaspira/Twanksta fetching.
Excludes abstract sub-paradigm templates (leading dash or K: 75a, 75b, 80, 80a, 101, 103, 104).
"""
import json
import re
from pathlib import Path

TABULA = Path("tabula.html")
OUT = Path("/tmp/verb_lemmas.json")

def load_tabula():
    """Extract verb paradigms (71–144) from HTML."""
    html = TABULA.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.DOTALL):
        text = re.sub(r"<[^>]*>", "", m.group(1))
        text = text.replace("&nbsp;", " ").replace("&ndash;", "-").replace("–", "-")
        text = " ".join(text.split())
        if len(text) < 3:
            continue
        mm = re.match(r"^(\d+[a-z]?)\s+([mfn/]+)?\s*:?\s*(.*)", text)
        if not mm:
            continue
        num = mm.group(1)
        try:
            base_num = int(re.match(r"\d+", num).group())
            if not (71 <= base_num <= 144):
                continue
        except:
            continue
        rest = mm.group(3)
        if not rest:
            continue
        out.setdefault(num, []).append(rest)
    return out

def extract_verb_lemmata(paradigms):
    """Extract (num, lemma) pairs from paradigm texts."""
    pairs = []
    abstract = []  # Paradigms without concrete lemmas

    for num in sorted(paradigms.keys(), key=lambda x: (int(re.match(r"\d+", x).group()), x)):
        texts = paradigms[num]
        for text in texts:
            # First token is the infinitive (may contain -tun/-twei variants)
            toks = text.split()
            if not toks:
                continue
            inf = toks[0]
            # Skip abstract templates (leading dash or K)
            if inf.startswith("-") or inf.startswith("K"):
                abstract.append(num)
                continue
            pairs.append((num, inf))
            break  # Only first text entry per paradigm

    return pairs, abstract

paradigms = load_tabula()
pairs, abstract = extract_verb_lemmata(paradigms)

output = {"pairs": pairs, "abstract": list(set(abstract))}
OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Extracted {len(pairs)} concrete verb lemmata (P71–144)")
print(f"Excluded {len(set(abstract))} abstract sub-paradigms: {sorted(set(abstract))}")
print(f"Written to {OUT}")

# Also write lemmas in the format expected by fetch_prusaspira.py
lemmas_for_fetch = pairs
Path("/tmp/lemmas.json").write_text(json.dumps(lemmas_for_fetch, ensure_ascii=False), encoding="utf-8")
print(f"Also wrote {len(lemmas_for_fetch)} lemmas to /tmp/lemmas.json (for fetch_prusaspira.py)")
