#!/usr/bin/env python3
"""Bestimmung per Übersetzungs-POS-Tagging (netzabhängiger Handoff-Schritt).

Dieses Skript ist bewusst NICHT Teil des `make`-Builds. Es wird EINMAL LOKAL
ausgeführt (dort, wo ``stanza.download()`` die UD-Modelle laden darf — in der
Cloud-/Proxy-Umgebung ist der Download i. d. R. blockiert). Es erzeugt eine
statische POS-Map-Datei, die anschließend netzfrei im Repo weiterverarbeitet
werden kann (siehe ``docs/handoff-pos-tagging.md``).

Vorgehen
--------
1. Dictionary laden (``twanksta_entries.json`` bzw. ``prussian_dictionary.json``).
2. Nur die Einträge behalten, die die bestehende Bestimmung ``classify()`` auf
   ``"unknown"`` fallen lässt — genau die Population, die heute still aus dem
   FST gedroppt wird (Querverweis-Stubs ``↑…``, desc-lose Einträge).
3. Für jede Zielsprache (DE/EN/LT/LV/PL/RU) die Glossen mit stanza taggen,
   die Wortart des Kopf-Tokens je Glosse bestimmen und über alle Sprachen
   mehrheitlich abstimmen.
4. Ergebnis als JSON + TSV nach ``data/reports/`` schreiben.

Das Skript ÜBERSCHREIBT keine Quelldaten und ändert die Pipeline nicht — es
liefert nur einen Vorschlag pro Eintrag, den ein Mensch bzw. der Folgeschritt
als Fallback in ``classify()`` einspeisen kann.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Alt-preußische Autonyme (dict-Schlüssel) -> stanza/UD-Sprachcode.
LANG_MAP = {
    "miks": "de",   # mikiskai  -> Deutsch
    "engl": "en",   # English
    "leit": "lt",   # Litauisch
    "latt": "lv",   # Lettisch
    "pols": "pl",   # Polnisch
    "mask": "ru",   # maskawiskai -> Russisch
}

# Universal POS (stanza) -> projektinterne Wortklasse (vgl. POS_TAGS in gen_lexc.py).
UPOS_TO_CLASS = {
    "NOUN": "noun",
    "PROPN": "proper_noun",
    "VERB": "verb",
    "ADJ": "adjective",
    "ADV": "adverb",
    "NUM": "numeral",
    "ADP": "preposition",
    "CCONJ": "conjunction",
    "SCONJ": "conjunction",
    "PART": "particle",
    "INTJ": "interjection",
    "PRON": "pronoun",
    "DET": "pronoun",
}
# Inhaltswörter, aus denen wir den "Kopf" einer Mehrwort-Glosse wählen.
CONTENT_UPOS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV", "NUM", "INTJ"}


def load_entries() -> list[dict]:
    for name in ("twanksta_entries.json", "prussian_dictionary.json"):
        p = REPO / "data/external" / name
        if p.exists():
            print(f"[load] {p}")
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else list(data.values())
    sys.exit("Kein Dictionary in data/external/ gefunden.")


def import_classify():
    """Die EINE autoritative Bestimmung aus dem Repo wiederverwenden.

    ``gen_lexc`` wird direkt per Dateipfad geladen, damit nicht der Paket-
    ``__init__`` (der ``pyhfst`` u. a. zieht) mit initialisiert werden muss.
    """
    import importlib.util
    path = REPO / "src/prussian_fst/gen_lexc.py"
    spec = importlib.util.spec_from_file_location("_gen_lexc_standalone", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.classify


def build_pipelines(langs):
    import stanza
    pipes = {}
    for lang in sorted(langs):
        try:
            stanza.download(lang, verbose=False)  # NETZ-SCHRITT (lokal!)
            pipes[lang] = stanza.Pipeline(
                lang, processors="tokenize,pos", verbose=False,
                tokenize_no_ssplit=True,
            )
            print(f"[stanza] Pipeline bereit: {lang}")
        except Exception as exc:  # noqa: BLE001
            print(f"[stanza] WARNUNG: {lang} übersprungen ({exc})")
    return pipes


def gloss_head_pos(pipe, gloss: str) -> str | None:
    """UPOS des Kopf-Tokens einer (evtl. mehrwortigen) Glosse.

    Heuristik: letztes Inhaltswort der Glosse (kopf-finale Komposita wie
    'day-labourer', 'algādzis'; bei 'to destine' -> 'destine'). Fällt auf das
    letzte getaggte Token zurück, wenn kein Inhaltswort erkannt wird.
    """
    gloss = gloss.strip()
    if not gloss:
        return None
    doc = pipe(gloss)
    words = [w for s in doc.sentences for w in s.words]
    if not words:
        return None
    content = [w.upos for w in words if w.upos in CONTENT_UPOS]
    if content:
        return content[-1]
    return words[-1].upos


def infer_entry(entry: dict, pipes) -> dict | None:
    translations = entry.get("translations") or {}
    votes: dict[str, str] = {}
    glosses_used: dict[str, str] = {}
    for key, lang in LANG_MAP.items():
        pipe = pipes.get(lang)
        if pipe is None:
            continue
        glosses = translations.get(key) or []
        gloss = next((g for g in glosses if g and g.strip()), None)
        if not gloss:
            continue
        upos = gloss_head_pos(pipe, gloss)
        cls = UPOS_TO_CLASS.get(upos or "")
        if cls:
            votes[lang] = cls
            glosses_used[lang] = gloss
    if not votes:
        return None
    tally = Counter(votes.values())
    top, top_n = tally.most_common(1)[0]
    return {
        "word": entry.get("word", ""),
        "paradigm": entry.get("paradigm", ""),
        "desc": entry.get("desc", ""),
        "inferred_pos": top,
        "confidence": round(top_n / len(votes), 3),
        "votes": votes,
        "glosses": glosses_used,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0,
                    help="nur die ersten N Kandidaten (0 = alle)")
    ap.add_argument("--out", default=str(REPO / "data/reports/pos_from_translations.json"))
    args = ap.parse_args()

    classify = import_classify()
    entries = load_entries()

    candidates = [
        e for e in entries
        if e.get("word") and "/" not in e["word"] and " " not in (
            e["word"][:-3] if e["word"].endswith(" si") else e["word"])
        and classify(e) == "unknown"
    ]
    if args.limit:
        candidates = candidates[: args.limit]
    print(f"[filter] {len(candidates)} 'unknown'-Kandidaten für Übersetzungs-Tagging")

    pipes = build_pipelines(set(LANG_MAP.values()))
    if not pipes:
        sys.exit("Keine stanza-Pipeline verfügbar — läuft der Download lokal?")

    results, resolved = [], 0
    for i, e in enumerate(candidates, 1):
        rec = infer_entry(e, pipes)
        if rec:
            results.append(rec)
            resolved += 1
        if i % 100 == 0:
            print(f"  … {i}/{len(candidates)} ({resolved} bestimmt)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    tsv = out.with_suffix(".tsv")
    lines = ["word\tinferred_pos\tconfidence\tparadigm\tdesc"]
    for r in results:
        lines.append(f"{r['word']}\t{r['inferred_pos']}\t{r['confidence']}\t{r['paradigm']}\t{r['desc']}")
    tsv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    dist = Counter(r["inferred_pos"] for r in results)
    print(f"\n[fertig] {resolved}/{len(candidates)} Kandidaten bestimmt")
    print(f"         Verteilung: {dict(dist.most_common())}")
    print(f"         JSON: {out}\n         TSV : {tsv}")


if __name__ == "__main__":
    main()
