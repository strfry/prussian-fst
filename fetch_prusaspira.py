#!/usr/bin/env python3
"""Fetch prusaspira.org inflection tables for every tabula paradigm lemma.

Fuer jedes Lemma wird zunaechst der exakte Begriff gesucht. Schlaegt das
fehl, werden Fallback-Kandidaten durchprobiert (s.u.).

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


# ── Fallback-Strategien ──────────────────────────────────────────────────

MANUAL = {
    "sēnts": "swents",
    "staūs": "stas",
    "mīstan": "mēstan",
    "pannin": "pannu",
    "amzin": "amzjan",
    "spigsnā": "spēgsnā",
    "zmūi": "zmōi",
    "mūti": "māti",
    "klīts": "klēts",
    "klākis": "tlākis",
    "auktimmisku": "auktimmiskan",
    "interwallin": "interwallan",
    "gēistun": "gēistwei",
    "wertun": "auwertun",
    "aistwei": "āistwei",
}


def alternate_inf(word: str) -> str | None:
    if word.endswith("tun"):
        return word[:-3] + "twei"
    if word.endswith("twei"):
        return word[:-4] + "tun"
    return None


def search_candidates(lemma: str):
    """Generiere Suchkandidaten in der Reihenfolge der Praeferenz."""
    yield lemma
    # Manuelle Uebersetzung
    if lemma in MANUAL:
        yield MANUAL[lemma]
    # Verb-Endung wechseln (-tun ↔ -twei)
    alt = alternate_inf(lemma)
    if alt:
        yield alt


# ── Hilfen ────────────────────────────────────────────────────────────────


def strip_macron(s: str) -> str:
    return s.translate(str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU"))


def found_word(raw: str, cand: str) -> bool:
    """Prüfe ob die Seite tatsächlich ein Ergebnis für cand enthält.

    Prusaspira spuckt manchmal ein verstecktes <span> mit 'Nika ni pastāne'
    aus, selbst wenn ein Treffer da ist — daher reicht ein simpler
    Text-Scan nicht.  Stattdessen prüfen wir auf die typische
    Ergebniskennung.

    Manche Einträge hängen Partikel an (z.B. 'smeītun si'), daher
    reicht ein Prefix-Match des <wirds>-Tags.

    Die Suche ist Makron-agnostisch — Prusaspira gibt Wörter teils mit
    und teils ohne Makron zurück.
    """
    cand_norm = strip_macron(cand).lower()
    return bool(re.search(
        r"<b\s+class='wirds'>([^<]+)</b>",
        raw,
    )) and any(
        strip_macron(w).lower().startswith(cand_norm)
        for w in re.findall(r"<b class='wirds'>([^<]+)</b>", raw)
    )


def parse_text(raw: str) -> str:
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.I)
    txt = re.sub(r"<[^>]+>", " ", h)
    txt = H.unescape(txt)
    return "\n".join(l.strip() for l in txt.splitlines() if l.strip())


# ── Main ──────────────────────────────────────────────────────────────────

summary = []
for i, (num, lemma) in enumerate(pairs, 1):
    best = None
    for cand in search_candidates(lemma):
        q = dict(PARAMS, wirds=cand)
        url = f"{BASE}?{urllib.parse.urlencode(q)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
            if found_word(raw, cand):
                best = (cand, raw)
                break
        except Exception as e:
            pass
        time.sleep(1.0)

    if best:
        cand, raw = best
        (OUT / f"{num}_{lemma}.html").write_text(raw, encoding="utf-8")
        txt = parse_text(raw)
        (OUT / f"{num}_{lemma}.txt").write_text(txt, encoding="utf-8")
        status = "OK" if cand == lemma else f"FALLBACK({cand})"
        summary.append((num, lemma, status, len(raw)))
        print(f"[{i:2}/{len(pairs)}] {num:5} {lemma:16} {status} ({len(raw)} B)")
    else:
        summary.append((num, lemma, "NOT FOUND", 0))
        print(f"[{i:2}/{len(pairs)}] {num:5} {lemma:16} NOT FOUND")

    if i < len(pairs):
        time.sleep(1.0)

json.dump(summary, open(OUT / "_summary.json", "w"), ensure_ascii=False, indent=2)
nf = [s for s in summary if s[2] != "OK"]
fb = [s for s in summary if s[2].startswith("FALLBACK")]
print(f"\nDone: {len(pairs)} fetched, {len(nf)} not OK, {len(fb)} via fallback")
for s in nf:
    print(f"  {s[0]:5} {s[1]:16} {s[2]}")
