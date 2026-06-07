#!/usr/bin/env python3
"""Use wirdeins.twanksta.org API to find correct dictionary lemmata."""
import json, re, urllib.request, urllib.parse
from pathlib import Path

PRUSASPIRA = Path("prusaspira")
TWANKSTA = Path("twanksta")
URL = "https://wirdeins.twanksta.org/search/"

def search_twanksta(query, lang="engl"):
    params = {"dia": "semba", "s": query, "language": lang}
    url = f"{URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "replace")
    except Exception as e:
        return []
    results = []
    for m in re.finditer(r'<span class=\'word\'>([^<]+)</span>', raw):
        word = m.group(1)
        # find desc
        after = raw[m.end():m.end()+500]
        dm = re.search(r'<span class=\'desc\'>([^<]+)</span>', after)
        desc = dm.group(1) if dm else ""
        results.append({"word": word, "desc": desc})
    return results

def extract_source(desc):
    m = re.search(r'\[([^\]]+)\]', desc)
    return m.group(1) if m else ""

def extract_info_from_prusaspira(num, lemma):
    fp = PRUSASPIRA / f"{num}_{lemma}.txt"
    if not fp.exists():
        return {}
    content = fp.read_text(encoding="utf-8")
    m = re.search(r'prūsiskai:\s+\S+\s+\S+\s+\S*\s*ēngliskai:\s+([^.]*?)\s*\[([^\]]*)\]', content)
    if m:
        return {"engl": m.group(1).strip(), "source": f"[{m.group(2).strip()}]"}
    return {}

# Find entries where twanksta entry differs from expected
pairs = []
for fp in sorted(PRUSASPIRA.glob("*.txt")):
    if fp.name.startswith("_"):
        continue
    m = re.match(r"(\d+[a-z]?)_(.+)\.txt$", fp.name)
    if m:
        pairs.append((m.group(1), m.group(2)))

results = []
for num, lemma in pairs:
    info = extract_info_from_prusaspira(num, lemma)
    if not info:
        continue
    eng = info.get("engl", "")
    src = info.get("source", "")
    if not eng:
        continue

    # Check what's current in twanksta dir
    twa_dir = TWANKSTA / f"{num}_{lemma}"
    twa_entries = []
    twa_file = twa_dir / "lemma.json"
    if twa_file.exists():
        try:
            twa_data = json.loads(twa_file.read_bytes())
            if isinstance(twa_data, list):
                for e in twa_data:
                    twa_entries.append({"word": e.get("word", ""), "desc": e.get("desc", "")})
        except:
            pass

    cur_src = ""
    for te in twa_entries:
        s = extract_source(te.get("desc", ""))
        if s:
            cur_src = te["desc"]
            break

    # Search API by English meaning
    api_results = search_twanksta(eng[:40])
    best = None
    for r in api_results:
        if src and src in r["desc"]:
            best = r
            break
    # if no source match, search by prusaspira word
    if not best:
        alt_results = search_twanksta(lemma)
        for r in alt_results:
            if src and src in r["desc"]:
                best = r
                break

    results.append({
        "num": num,
        "lemma": lemma,
        "engl": eng,
        "source": src,
        "current": [e["word"] for e in twa_entries],
        "api_found": best,
    })

# Summary
print(f"{'Par':5} {'Lemma':16} {'English':30} {'Source':20} {'Current':20} {'API best':20}")
print("-" * 120)
for r in results:
    cur = ", ".join(r["current"]) if r["current"] else "-"
    api = r["api_found"]["word"] if r["api_found"] else "-"
    print(f"{r['num']:5} {r['lemma']:16} {r['engl']:30} {r['source']:20} {cur:20} {api:20}")

mismatches = [r for r in results if r["api_found"] and r["api_found"]["word"] not in r["current"]]
print(f"\n{mismatches} potential mismatches found:")
for r in mismatches:
    print(f"  {r['num']} {r['lemma']}: current={r['current']}, api_suggests={r['api_found']['word']}")
