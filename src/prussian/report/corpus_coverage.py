"""Korpus-Coverage: Token aus den deklarierten Quellen (data/corpus/manifest.json)
tokenisieren, gegen den FST klassifizieren und pro Quelle auszählen.

Buckets je nicht-ignoriertem Token:
  analyzed  Haupt-FST liefert eine Analyse
  ortho     nur lenient.fst (Schreibvariante)
  variant   beide leer, Token ist eine bekannte Wörterbuch-Form (Flexionslücke)
  propn     beide leer, großgeschrieben & nicht satzinitial (Eigenname-Heuristik)
  oov       Rest (unbekanntes Lemma)
coverage = (analyzed + ortho) / (nicht-ignorierte Token)

Spam-Filter (nur für Quellen mit "clean": false): Dokumente, deren Anteil
erkannter Token (analyzed+ortho) unter SPAM_THRESHOLD liegt, gelten als
nicht-prußisch (1xbet-/Promo-Seiten ≈ 0) und werden verworfen + separat gezählt.
"""

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
MANIFEST = ROOT / "data/corpus/manifest.json"
DICT = ROOT / "data/external/twanksta_entries.json"
OUT = ROOT / "data/derived/corpus_coverage.json"

SPAM_THRESHOLD = 0.12       # Doc gilt als Spam, wenn recognized_share darunter
SPAM_MIN_TOKENS = 8         # erst ab so vielen Token überhaupt filtern

_PUNCT_EDGE = re.compile(r"^[„“”'‘’(\[{]+|[.!?;,:\"„“”'‘’)\]}…—–\-]+$")
_HAS_LETTER = re.compile(r"[a-zA-ZāēīōūĀĒĪŌŪŗṛśšžč]")
_SENT_END = re.compile(r"[.!?…]$")
_URLISH = re.compile(r"https?://|www\.|@|\.com|\.ru|\.az")


def iter_tokens(text: str):
    """(roh_token, ist_satzinitial) — Casing erhalten; Ignorierbares fällt raus."""
    initial = True
    for raw in text.split():
        ended_sentence = bool(_SENT_END.search(raw))
        tok = _PUNCT_EDGE.sub("", raw)
        tok = _PUNCT_EDGE.sub("", tok)  # zweite Kante
        was_initial = initial
        initial = ended_sentence
        if not tok or not _HAS_LETTER.search(tok) or _URLISH.search(tok):
            continue
        if tok.isdigit():
            continue
        yield tok, was_initial


def dict_surface_set(words: list[dict]) -> set[str]:
    """Alle bekannten Oberflächen (Lemmata + flektierte Formen), lowercased."""
    surfaces: set[str] = set()
    for w in words:
        surfaces.add(w["word"].lower())
        forms = w.get("forms")
        if not isinstance(forms, dict):
            continue
        for decl in forms.get("declension", []):
            for case_info in decl.get("cases", []):
                for k in ("singular", "plural"):
                    f = case_info.get(k, "").strip()
                    if f and f != "—":
                        surfaces.add(f.lower())
        for block in forms.get("indicative", []):
            for slot in block.get("forms", []):
                f = slot.get("form", "").strip()
                if f and f != "—":
                    surfaces.add(f.lower())
    return surfaces


def _read_docs(source: dict):
    """(doc_id, text) je Quelle, je nach Format."""
    path = ROOT / source["path"]
    fmt = source["format"]
    if fmt == "tsv_prg":
        with open(path, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="\t"):
                if len(row) >= 3 and row[1] == "prg":
                    yield row[0], row[2]
    elif fmt == "jsonl":
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("lang", "prg") != "prg":
                    continue
                yield obj.get("title", ""), obj.get("text", "")
    else:
        raise ValueError(f"Unbekanntes Format: {fmt}")


def _empty_source(source: dict) -> dict:
    return {
        "id": source["id"], "name": source["name"],
        "tokens": 0, "analyzed": 0, "ortho": 0,
        "variant": 0, "propn": 0, "oov": 0,
        "dropped_docs": 0, "dropped_words": 0,
    }


def run(main_fst, lenient_fst, words: list[dict] | None = None,
        progress: bool = False) -> dict:
    words = words if words is not None else json.loads(DICT.read_text(encoding="utf-8"))
    surfaces = dict_surface_set(words)
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]

    fst_cache: dict[str, str] = {}
    oov_counter: Counter = Counter()
    variant_counter: Counter = Counter()

    def fst_bucket(lower: str) -> str:
        hit = fst_cache.get(lower)
        if hit is None:
            if list(main_fst.analyze(lower)):
                hit = "analyzed"
            elif list(lenient_fst.analyze(lower)):
                hit = "ortho"
            else:
                hit = "none"
            fst_cache[lower] = hit
        return hit

    per_source: list[dict] = []
    for source in sources:
        s = _empty_source(source)
        clean = source.get("clean", True)
        for di, (_doc_id, text) in enumerate(_read_docs(source)):
            doc = {"tokens": 0, "recognized": 0,
                   "buckets": {"analyzed": 0, "ortho": 0,
                               "variant": 0, "propn": 0, "oov": 0}}
            for tok, is_initial in iter_tokens(text):
                doc["tokens"] += 1
                lower = tok.lower()
                bucket = fst_bucket(lower)
                if bucket == "analyzed":
                    doc["buckets"]["analyzed"] += 1
                    doc["recognized"] += 1
                elif bucket == "ortho":
                    doc["buckets"]["ortho"] += 1
                    doc["recognized"] += 1
                elif lower in surfaces:
                    doc["buckets"]["variant"] += 1
                    doc["_variant_tokens"] = doc.get("_variant_tokens", []) + [lower]
                elif tok[:1].isupper() and not is_initial:
                    doc["buckets"]["propn"] += 1
                else:
                    doc["buckets"]["oov"] += 1
                    doc["_oov_tokens"] = doc.get("_oov_tokens", []) + [lower]

            share = doc["recognized"] / doc["tokens"] if doc["tokens"] else 0.0
            is_spam = (not clean and doc["tokens"] >= SPAM_MIN_TOKENS
                       and share < SPAM_THRESHOLD)
            if is_spam:
                s["dropped_docs"] += 1
                s["dropped_words"] += doc["tokens"]
                continue
            s["tokens"] += doc["tokens"]
            for k, v in doc["buckets"].items():
                s[k] += v
            variant_counter.update(doc.get("_variant_tokens", []))
            oov_counter.update(doc.get("_oov_tokens", []))
            if progress and (di + 1) % 200 == 0:
                sys.stderr.write(f"\r  {source['id']}: {di+1} docs")
                sys.stderr.flush()
        if progress:
            sys.stderr.write("\r" + " " * 60 + "\r")
        per_source.append(s)

    totals = {k: sum(s[k] for s in per_source)
              for k in ("tokens", "analyzed", "ortho", "variant", "propn", "oov",
                        "dropped_docs", "dropped_words")}
    return {
        "totals": totals,
        "per_source": per_source,
        "top_oov": oov_counter.most_common(200),
        "top_variant": variant_counter.most_common(200),
    }


def _coverage(d: dict) -> float:
    return 100 * (d["analyzed"] + d["ortho"]) / d["tokens"] if d["tokens"] else 0.0


def main() -> None:
    from pyfoma import FST
    main_fst = FST.load(str(ROOT / "build/analyser.fst"))
    lenient_fst = FST.load(str(ROOT / "build/lenient.fst"))
    result = run(main_fst, lenient_fst, progress=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    t = result["totals"]
    print(f"Korpus gesamt: {t['tokens']} Token, Coverage {_coverage(t):.1f}%")
    for s in result["per_source"]:
        extra = (f"  (verworfen: {s['dropped_docs']} Docs / {s['dropped_words']} Wörter)"
                 if s["dropped_docs"] else "")
        print(f"  {s['name']:20s} {s['tokens']:7d} Token  "
              f"{_coverage(s):5.1f}%{extra}")
    print(f"→ {OUT}")

    for label, key in [("OOV (unbekannte Lemmata)", "top_oov"),
                       ("Flexionslücken (variant)", "top_variant")]:
        entries = result.get(key, [])[:30]
        print(f"\n  {label} — Top {len(entries)}:")
        print(f"  {'Freq':>5}  Wort")
        for w, n in entries:
            print(f"  {n:5d}  {w}")


if __name__ == "__main__":
    main()
