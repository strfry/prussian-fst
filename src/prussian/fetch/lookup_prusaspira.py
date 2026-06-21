#!/usr/bin/env python3
"""Look up prusaspira lemmata (from filenames) in twanksta_entries.json
and save matching entries to prusaspira_lookup/."""
import json
import re
from pathlib import Path

PRUSASPIRA = Path("prusaspira")
DICT = Path("data/external/twanksta_entries.json")
OUT = Path("prusaspira_lookup")

OUT.mkdir(exist_ok=True)

dict_entries = json.loads(DICT.read_bytes())
by_word = {}
for e in dict_entries:
    w = e.get("word", "")
    by_word.setdefault(w, []).append(e)

txt_files = sorted(PRUSASPIRA.glob("*.txt"))
summary = {}

for fp in txt_files:
    if fp.name.startswith("_"):
        continue
    m = re.match(r"(\d+[a-z]?)_(.+)\.txt$", fp.name)
    if not m:
        continue
    num, lemma = m.group(1), m.group(2)
    matches = by_word.get(lemma, [])
    summary[fp.name] = {
        "num": num,
        "lemma": lemma,
        "found": len(matches),
    }
    if matches:
        out = OUT / fp.stem
        out.mkdir(parents=True, exist_ok=True)
        (out / "lemma.json").write_text(
            json.dumps(matches, ensure_ascii=False, indent=2)
        )
        words = [e["word"] for e in matches]
        (out / "words.txt").write_text("\n".join(words) + "\n")

(OUT / "_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2)
)

found = sum(1 for v in summary.values() if v["found"])
total = len(summary)
print(f"{total} files, {found} lemmata found in dictionary")
for fp, v in summary.items():
    status = "✓" if v["found"] else "✗"
    print(f"  {status} {fp} → lemma '{v['lemma']}' ({v['found']} hit(s))")
