#!/usr/bin/env python3
"""Fetch raw verb data from Prusaspira and Twanksta for P71–144.

For each paradigm (from verb_paradigms.json) tries search terms in order:
  1. exact lemma
  2. alternate infinitive ending (-tun ↔ -twei)
  3. any word from wordlist with same paradigm + matching stem
  4. any word from wordlist with same paradigm

Paradigms absent from wordlist are skipped.

Saves raw response data only (no parsing).  Rate-limited to 1 req/s.

Outputs:
  prusaspira/{num}_{lemma}.html       — raw Prusaspira GET response
  prusaspira/{num}_{lemma}.txt        — HTML-stripped plain text
  twanksta/{num}_{lemma}/search.html  — Twanksta search GET response
  twanksta/{num}_{lemma}/forms.html   — Twanksta forms POST response
  twanksta/{num}_{lemma}/forms.txt    — HTML-stripped forms text
"""
import argparse
import html as H
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

PRUSASPIRA_BASE = "https://www.prusaspira.org/wirdeins"
TWANKSTA_SEARCH = "https://wirdeins.twanksta.org/search/"
TWANKSTA_FORMS  = "https://wirdeins.twanksta.org/more/"

PRUSASPIRA_OUT = Path("prusaspira")
TWANKSTA_OUT   = Path("twanksta")
VERB_PARADIGMS = Path("data/gold/verb_paradigms.json")
WORDLIST       = Path("data/external/twanksta_entries.json")

UA = "Mozilla/5.0"

PREFIXES = ["ap", "at", "au", "eb", "en", "et", "iz", "ka", "pa", "po",
            "pra", "prei", "sen", "skre", "sur", "tra", "us", "wal"]


# ── helpers ────────────────────────────────────────────────────────────

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    })
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def strip_html(raw):
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.I)
    txt = re.sub(r"<[^>]+>", " ", h)
    txt = H.unescape(txt)
    return "\n".join(l.strip() for l in txt.splitlines() if l.strip())


def strip_diacritics(word):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", word)
                   if not unicodedata.combining(c))


def alternate_inf(word):
    if word.endswith("tun"):
        return word[:-3] + "twei"
    if word.endswith("twei"):
        return word[:-4] + "tun"
    return None


def stem_of(word):
    lower = word.lower()
    for p in sorted(PREFIXES, key=len, reverse=True):
        if lower.startswith(p):
            return word[len(p):]
    return word


# ── wordlist index ──────────────────────────────────────────────────────

def build_wordlist_index():
    wl = json.loads(WORDLIST.read_text(encoding="utf-8"))
    by_paradigm = defaultdict(list)
    for e in wl:
        pn = e.get("paradigm", "")
        if pn.isdigit():
            by_paradigm[pn].append(e)
    return dict(by_paradigm)


# ── candidates ──────────────────────────────────────────────────────────

def search_candidates(num, lemma, wl_entries):
    yield lemma
    stripped = strip_diacritics(lemma)
    if stripped != lemma:
        yield stripped
    alt = alternate_inf(lemma)
    if alt:
        yield alt
    stem = stem_of(lemma)
    pref = [e["word"] for e in wl_entries
            if stem_of(e["word"]) == stem and e["word"] not in (lemma, alt)]
    for w in pref:
        yield w
    for e in wl_entries:
        w = e["word"]
        if w not in (lemma, alt) and w not in pref:
            yield w


# ── main ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Fetch raw verb data from Prusaspira and Twanksta")
    ap.add_argument("--force", action="store_true", help="Re-fetch existing data")
    args = ap.parse_args()

    wl_by_pn = build_wordlist_index()
    vp = json.loads(VERB_PARADIGMS.read_text(encoding="utf-8"))
    paradigms = vp["paradigms"]

    def sort_key(n):
        m = re.match(r"(\d+)([a-z]*)", n)
        return (int(m.group(1)), m.group(2) or "")

    items = sorted(paradigms.items(), key=lambda kv: sort_key(kv[0]))
    PRUSASPIRA_OUT.mkdir(exist_ok=True)
    TWANKSTA_OUT.mkdir(exist_ok=True)

    skipped = prus_ok = twank_ok = no_wl = 0
    total = len(items)
    lemma_map: dict[str, dict[str, str | None]] = {}

    for i, (num, entry) in enumerate(items, 1):
        lemma = entry["lemma"]
        prus_html_file = PRUSASPIRA_OUT / f"{num}_{lemma}.html"
        prus_txt_file  = PRUSASPIRA_OUT / f"{num}_{lemma}.txt"
        twank_dir      = TWANKSTA_OUT / f"{num}_{lemma}"
        twank_search   = twank_dir / "search.html"
        twank_forms    = twank_dir / "forms.html"
        twank_txt      = twank_dir / "forms.txt"
        lemma_map[f"{num}_{lemma}"] = {"prusaspira": None, "twanksta": None}

        wl_entries = wl_by_pn.get(num, [])
        if not wl_entries:
            no_wl += 1

        need_prus = args.force or not prus_html_file.exists()
        need_twank = args.force or not twank_forms.exists()
        if not need_prus and not need_twank:
            skipped += 1
            continue

        print(f"[{i}/{total}] P{num} {lemma}", end="")

        # ── Prusaspira ──
        if need_prus:
            done = False
            for cand in search_candidates(num, lemma, wl_entries):
                try:
                    url = f"{PRUSASPIRA_BASE}?{urllib.parse.urlencode({'wirds': cand, 'akc': 'Iz', 'bila': '1'})}"
                    raw = get(url)
                    prus_html_file.write_text(raw, encoding="utf-8")
                    prus_txt_file.write_text(strip_html(raw), encoding="utf-8")
                    done = True
                    lemma_map[f"{num}_{lemma}"]["prusaspira"] = cand if cand != lemma else None
                    prus_ok += 1
                    label = "P✓" if cand == lemma else f"P✓({cand})"
                    print(f" {label}", end="")
                    break
                except Exception:
                    pass
                time.sleep(1.0)
            if not done:
                print(" P✗", end="")
        else:
            print(" P✓(c)", end="")

        # ── Twanksta ──
        if need_twank:
            done = False
            for cand in search_candidates(num, lemma, wl_entries):
                try:
                    # search
                    search_url = f"{TWANKSTA_SEARCH}?dia=semba&s={urllib.parse.quote(cand)}&language=engl"
                    search_raw = get(search_url)
                    # find matching entry
                    if f"<span class='word'>{cand}</span>" not in search_raw and \
                       f"> {cand}</span>" not in search_raw:
                        time.sleep(1.0)
                        continue
                    # extract desc
                    m = re.search(r"<span class='desc'>([^<]+)</span>", search_raw)
                    desc = m.group(1) if m else f"[{cand}]"
                    m2 = re.search(r"<span class='numb'>([^<]+)</span>", search_raw)
                    numb = m2.group(1) if m2 else num
                    time.sleep(1.0)
                    # forms POST
                    forms_raw = post(TWANKSTA_FORMS, {
                        "word": cand, "numb": numb, "desc": desc, "dia": "semba",
                    })
                    twank_dir.mkdir(exist_ok=True)
                    twank_search.write_text(search_raw, encoding="utf-8")
                    twank_forms.write_text(forms_raw, encoding="utf-8")
                    twank_txt.write_text(strip_html(forms_raw), encoding="utf-8")
                    done = True
                    lemma_map[f"{num}_{lemma}"]["twanksta"] = cand if cand != lemma else None
                    twank_ok += 1
                    label = "T✓" if cand == lemma else f"T✓({cand})"
                    print(f" {label}", end="")
                    break
                except Exception:
                    pass
                time.sleep(1.0)
            if not done:
                print(" T✗", end="")
        else:
            print(" T✓(c)", end="")

        print()

    # Für gecachte Einträge: None → Lemma (wenn Datei existiert)
    for key, m in lemma_map.items():
        num, lemma = key.split("_", 1)
        if m["prusaspira"] is None:
            prus_f = PRUSASPIRA_OUT / f"{key}.html"
            if prus_f.exists():
                m["prusaspira"] = lemma
        if m["twanksta"] is None:
            twank_f = TWANKSTA_OUT / key / "forms.html"
            if twank_f.exists():
                m["twanksta"] = lemma

    Path("data/gold/_lemma_map.json").write_text(
        json.dumps(lemma_map, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDone: {total} total, {no_wl} no-wordlist, {skipped} cached")
    print(f"  Prusaspira: {prus_ok} OK")
    print(f"  Twanksta:   {twank_ok} OK")
    print("  Lemma-map saved to _lemma_map.json")


if __name__ == "__main__":
    main()
