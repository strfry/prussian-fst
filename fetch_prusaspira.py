#!/usr/bin/env python3
"""Fetch prusaspira.org inflection tables for every tabula paradigm lemma.

Rate-limited to 1 request/second. Saves raw HTML and a parsed text table
per paradigm under prusaspira/.
"""
import json
import re
import time
import html as H
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.prusaspira.org/wirdeins"
PARAMS = {"akc": "Iz", "tap": "W", "bila": "1"}
OUT = Path("prusaspira")
OUT.mkdir(exist_ok=True)

pairs = json.load(open("/tmp/lemmas.json", encoding="utf-8"))


def parse_text(raw: str) -> str:
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.I)
    txt = re.sub(r"<[^>]+>", " ", h)
    txt = H.unescape(txt)
    return "\n".join(l.strip() for l in txt.splitlines() if l.strip())


summary = []
for i, (num, lemma) in enumerate(pairs, 1):
    q = dict(PARAMS, wirds=lemma)
    url = f"{BASE}?{urllib.parse.urlencode(q)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        (OUT / f"{num}_{lemma}.html").write_text(raw, encoding="utf-8")
        txt = parse_text(raw)
        (OUT / f"{num}_{lemma}.txt").write_text(txt, encoding="utf-8")
        found = "Nika ni pastāne" not in txt  # "nothing found" marker
        status = "OK" if found else "NOT FOUND"
        summary.append((num, lemma, status, len(raw)))
        print(f"[{i:2}/{len(pairs)}] {num:5} {lemma:16} {status} ({len(raw)} B)")
    except Exception as e:
        summary.append((num, lemma, f"ERROR {e}", 0))
        print(f"[{i:2}/{len(pairs)}] {num:5} {lemma:16} ERROR {e}")
    if i < len(pairs):
        time.sleep(1.0)

json.dump(summary, open(OUT / "_summary.json", "w"), ensure_ascii=False, indent=2)
nf = [s for s in summary if s[2] != "OK"]
print(f"\nDone: {len(pairs)} fetched, {len(nf)} not OK")
for s in nf:
    print(f"  {s[0]:5} {s[1]:16} {s[2]}")
