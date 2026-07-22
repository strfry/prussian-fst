"""Ref-Resolver für Twanksta-desc-Verweise.

Die desc-Felder von twanksta_entries.json enthalten in eckigen Klammern
Herleitungs-/Belegverweise, oft auf andere preußische Formen
("[pawargan 63 MK]", "[Grēnztun drv]").  Der Linker löst diese Formen
über eine Analyzer-Kaskade zunehmender Toleranz auf ein Lemma des FST auf:

  1. exact   — base.hfstol, Form wie geschrieben
  2. case    — base.hfstol, lower-/Capitalize-Varianten
  3. macron  — macron.hfstol (Makron-Verlust), Case-Varianten
  4. lenient — lenient.hfstol (Makron + Degemination + Ortho), Case-Varianten

Mindestens 1 Analyse in einer Stufe → Treffer (status "resolved",
method = Stufenname).  Mehrere Lemmata werden NICHT als Fehler behandelt,
sondern als Cluster gelinkt (lemmas: [...]): dieselbe Oberflächenform ist
im Vollform-Lexikon von mehreren Lemmata legitim ableitbar (lexikalisierte
Ableitung vs. flektiertes Grundwort, tun/twei-Infinitivpaare, Sg-/Pl-tantum-
Paare, Makron-Minimalpaare).  Regelstufen können solche Fälle nicht trennen;
Details siehe docs/ambiguities.md.  Keine Analyse → gap (erwartbar für die
vielen deutschen/litauischen Etymologie-Verweise).

Großgeschriebene Refs (Lemma-Zitierformen) und Formen mit Zeichen außerhalb
des FST-Alphabets (Fremd-/Lehnwortschreibungen) werden gar nicht erst
nachgeschlagen — siehe resolve_corpus bzw. den Alphabet-Guard.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:
    from .fst_lookup import flookup_batch
except ImportError:  # Direktaufruf als Skript
    from fst_lookup import flookup_batch

REPO = Path(__file__).resolve().parents[2]
DEFAULT_BASE = REPO / "build/base.hfstol"
DEFAULT_MACRON = REPO / "build/macron.hfstol"
DEFAULT_LENIENT = REPO / "build/lenient.hfstol"
DEFAULT_CORPUS = REPO / "data/external/twanksta_entries.json"

# Annotations-Marker in Verweisen, keine Wortformen (Quellen-Kürzel,
# Herleitungstyp).  Großgeschriebene Werke (E, GrG …) nur als ganzes Token.
MARKERS = {"MK", "Nx", "DIA", "drv", "DRV", "E", "GlN", "GrG", "GrA", "GrF",
           "JB", "APN", "TN", "ON", "AV", "av", "ptv", "mod", "rel", "cp",
           "aci", "Riemann"}

BRACKET_RE = re.compile(r"\[([^\]]*)\]")

# Zeichen, die der FST kennt: Kleinbuchstaben a-z plus Makron-Vokale.
# Formen mit anderen Zeichen (ļ ķ v é …) stammen aus fremdsprachigen
# Etymologie-/Lehnwortschreibungen; sie im FST nachzuschlagen liefert nur
# Präfix-Müll-Matches (kaļķis → ka).  Leerzeichen/Bindestrich sind für
# mehrteilige Verweise erlaubt.
FST_ALPHABET = set("abcdefghijklmnopqrstuvwxyzāēīōū")
_ALLOWED_EXTRA = set(" -")


def _in_alphabet(form: str) -> bool:
    return all(ch.lower() in FST_ALPHABET or ch in _ALLOWED_EXTRA
               for ch in form)


@dataclass
class BracketItem:
    form: str
    source: str | None = None  # Beleg-Nummer, z.B. "63" aus "pawargan 63"


def parse_desc(desc: str) -> list[BracketItem]:
    """Alle [...]-Verweise einer desc extrahieren.

    Kommagetrennte Einträge, Klammern gestrippt ((grīki)si → grīkisi),
    nachgestellte Belegnummern abgetrennt, Marker-Tokens entfernt.
    """
    items: list[BracketItem] = []
    for bracket in BRACKET_RE.findall(desc):
        for chunk in bracket.split(","):
            tokens = chunk.replace("(", "").replace(")", "").split()
            source = None
            words = []
            for tok in tokens:
                if tok.isdigit():
                    source = tok
                elif "." in tok:
                    # Sprachkürzel wie "lat." / "lit." — kein preußischer Beleg.
                    continue
                elif tok not in MARKERS and tok.strip("+"):
                    words.append(tok.strip("+"))
            if words:
                items.append(BracketItem(form=" ".join(words), source=source))
    return items


def _case_variants(form: str) -> list[str]:
    seen: list[str] = []
    for v in (form, form.lower(), form[:1].upper() + form[1:].lower()):
        if v not in seen:
            seen.append(v)
    return seen


def resolve_form(form: str, fsts: dict[str, Path]) -> dict:
    """Kaskade über die Analyzer-Stufen; erste Stufe mit Analysen gewinnt.

    Ein oder mehrere Lemmata werden gleich behandelt: status "resolved" mit
    lemmas als (sortierter) Liste.  Mehrere Lemmata sind kein Fehlerfall,
    sondern ein Cluster gleichwertiger Analysen derselben Oberflächenform
    (siehe Modul-Docstring / docs/ambiguities.md).
    """
    if not _in_alphabet(form):
        # Zeichen außerhalb des FST-Alphabets → Nachschlagen liefert nur
        # Präfix-Müll-Matches; direkt als gap behandeln.
        return {"status": "gap"}
    stages = [
        ("exact", fsts["base"], [form]),
        ("case", fsts["base"], _case_variants(form)[1:]),
        ("macron", fsts["macron"], _case_variants(form)),
        ("lenient", fsts["lenient"], _case_variants(form)),
    ]
    for method, fst_path, variants in stages:
        if not variants or not fst_path.exists():
            continue
        analyses = flookup_batch(variants, fst_path)
        pairs = {(lemma, tuple(tags))
                 for hits in analyses.values() for lemma, tags in hits}
        lemmas = sorted({lemma for lemma, _ in pairs})
        if lemmas:
            tags = sorted({"+".join(t) for _, t in pairs})
            return {"status": "resolved", "lemmas": lemmas,
                    "tags": tags, "method": method}
    return {"status": "gap"}


def resolve_corpus(entries: list[dict], fsts: dict[str, Path]) -> tuple[list, list]:
    links, unresolved = [], []
    cache: dict[str, dict] = {}
    for entry in entries:
        desc = entry.get("desc", "")
        for item in parse_desc(desc):
            # Großgeschriebene Refs sind Lemma-Zitierformen (E, GrG, eigene
            # Lemmata …), keine aufzulösenden Flexionsformen → überspringen.
            if item.form[:1].isupper():
                continue
            if item.form not in cache:
                cache[item.form] = resolve_form(item.form, fsts)
            res = cache[item.form]
            record = {"orig_lemma": entry.get("word"), "ref": item.form,
                      "desc": desc, "source": item.source}
            if res["status"] == "resolved":
                links.append({**record, "lemmas": res["lemmas"],
                              "tags": res["tags"], "method": res["method"]})
            else:
                record["status"] = res["status"]
                unresolved.append(record)
    return links, unresolved


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--out-dir", type=Path, default=REPO / "build")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    entries = json.loads(args.corpus.read_text())
    fsts = {"base": DEFAULT_BASE, "macron": DEFAULT_MACRON,
            "lenient": DEFAULT_LENIENT}
    links, unresolved = resolve_corpus(entries, fsts)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "links.json").write_text(
        json.dumps(links, ensure_ascii=False, indent=1))
    (args.out_dir / "links_unresolved.json").write_text(
        json.dumps(unresolved, ensure_ascii=False, indent=1))

    if args.stats:
        methods = Counter(l["method"] for l in links)
        status = Counter(u["status"] for u in unresolved)
        clusters = sum(1 for l in links if len(l["lemmas"]) > 1)
        total = len(links) + len(unresolved)
        print(f"Verweise gesamt: {total}")
        print(f"aufgelöst: {len(links)} "
              f"({', '.join(f'{m}={n}' for m, n in methods.most_common())})")
        print(f"  davon Cluster (mehrere Lemmata): {clusters}")
        print(f"offen: {len(unresolved)} "
              f"({', '.join(f'{s}={n}' for s, n in status.most_common())})")


if __name__ == "__main__":
    main()
