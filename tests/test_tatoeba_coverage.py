"""Tatoeba-Satz-Coverage: analysiert alle prg-Sätze gegen den FST.

Jeder Satz wird tokenisiert, und pro Wort wird geprüft, ob der
Analysator mindestens eine Analyse liefert.
"""

import csv
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ANALYSER = ROOT / "build/analyser.fst"
CORPUS = ROOT / "corpus/prg_sentences_detailed.tsv"

# Punktuation, die wir am Wortende abschneiden
PUNCT = re.compile(r"[.!?;,:\"„“”'‘’()\[\]{}…—–\-]+$")
# Satzzeichen, die als eigenes Token gelten — wir entfernen sie ganz
PUNCT_ANY = re.compile(r"^[.!?;,:\"„“”'‘’()\[\]{}…—–\-]+$")


def _tokenize(text: str) -> list[str]:
    """Einfache Tokenisierung: whitespace-split, Punktuation abgeschnitten."""
    tokens = []
    for raw in text.split():
        t = raw.strip()
        # Komplett aus Punktuation → überspringen
        if PUNCT_ANY.match(t):
            continue
        # Führende Punktuation entfernen
        t = re.sub(r"^[„“”'‘’(\[{]+", "", t)
        # Nachfolgende Punktuation entfernen
        t = PUNCT.sub("", t)
        if t:
            tokens.append(t.lower())
    return tokens


def _load_fst(path: Path):
    from pyfoma import FST
    if not path.exists():
        pytest.skip(f"{path} fehlt — erst `uv run python -m prussian.fst.build`")
    return FST.load(str(path))


@pytest.fixture(scope="session")
def analyser():
    return _load_fst(ANALYSER)


@pytest.fixture(scope="session")
def sentences():
    """Alle prg-Sätze aus der Tatoeba-Datei."""
    if not CORPUS.exists():
        pytest.skip(f"{CORPUS} fehlt — Korpus beziehen (s. data/corpus/manifest.json)")
    rows = []
    with open(CORPUS, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            rows.append(row)
    return rows


def test_tatoeba_coverage(analyser, sentences):
    total_tokens = 0
    total_recognized = 0
    total_sentences = 0
    sentence_results: list[tuple[str, int, int, float]] = []  # (satz, tokens, erkannt, quote)

    for row in sentences:
        if len(row) < 3 or row[1] != "prg":
            continue
        text = row[2]
        tokens = _tokenize(text)
        if not tokens:
            continue

        recognized = sum(1 for t in tokens if bool(list(analyser.analyze(t))))
        total_tokens += len(tokens)
        total_recognized += recognized
        total_sentences += 1

        if recognized < len(tokens):
            sentence_results.append(
                (text, len(tokens), recognized, 100 * recognized / len(tokens))
            )

    # ── Report ──
    overall_pct = 100 * total_recognized / total_tokens if total_tokens else 0
    lines = [
        f"\n{'='*70}",
        f"Tatoeba-Satz-Coverage ({total_sentences} Sätze, {total_tokens} Tokens)",
        f"{'='*70}",
        f"  Erkannte Tokens:     {total_recognized:5d}  ({overall_pct:5.1f}%)",
        f"  Unerkannte Tokens:   {total_tokens - total_recognized:5d}  "
        f"({100 - overall_pct:5.1f}%)",
        "",
    ]

    # Bottom-N: die 20 Sätze mit der niedrigsten Coverage
    sentence_results.sort(key=lambda x: x[3])
    lines.append("  Sätze mit niedrigster Coverage (Bottom 20):")
    lines.append(f"  {'Coverage':>8s}  {'Tokens':>6s}  {'Satz'}")
    lines.append(f"  {'─'*8}  {'─'*6}  {'─'*50}")
    for text, n_tok, n_rec, pct in sentence_results[:20]:
        preview = text if len(text) < 55 else text[:52] + "..."
        lines.append(f"  {pct:7.1f}%  {n_tok:5d}/{n_rec:<2d}  {preview}")

    # Unerkannte Tokens sammeln
    unknown: dict[str, int] = {}
    for row in sentences:
        if len(row) < 3 or row[1] != "prg":
            continue
        for t in _tokenize(row[2]):
            if not list(analyser.analyze(t)):
                unknown[t] = unknown.get(t, 0) + 1

    lines.append("")
    lines.append(f"  Unerkannte Types: {len(unknown)}")
    lines.append("  Top-30 unbekannte Wörter (nach Häufigkeit):")
    lines.append(f"  {'Freq':>5s}  {'Wort'}")
    lines.append(f"  {'─'*5}  {'─'*30}")
    for w, cnt in sorted(unknown.items(), key=lambda x: -x[1])[:30]:
        lines.append(f"  {cnt:5d}  {w}")

    report = "\n".join(lines)
    print(report)

    assert overall_pct > 30, (
        f"Token-Coverage ({overall_pct:.1f}%) liegt unter 30%"
    )
