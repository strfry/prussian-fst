"""Eigenständige Orthographie-Normalisierung der Neo-Preußisch-Standards.

ISOLIERT vom Morphotaktik-Build (build.py/lexd): braucht weder Goldstandard
noch Wortlisten-Kompilat, nur pyfoma. Modelliert die systematischen
Schreibweisen-Unterschiede zwischen Twanksta (wirdeins.twanksta.org) und
Prusaspira/Tabula-Standard (prusaspira.org) als Finite-State-Transducer.

Ansatz: ein DETERMINISTISCHER Falt-Transducer, der die zwischen den Standards
frei variierenden bzw. systematisch abweichenden Merkmale auf eine gemeinsame
Skelettform abbildet. Zwei Schreibweisen gelten als dieselbe Form, wenn ihre
gefalteten Skelette übereinstimmen — das matcht ohne Übererzeugung/Explosion
(vgl. den früheren generativen Ansatz mit optionalen Regeln, der an der
Macron-Kombinatorik scheiterte).

Gefaltete Merkmale (evidenzbasiert aus dem Wörterbuchvergleich):
  Macron-Länge        ā→a ē→e ī→i ō→o ū→u   (inkl. Diphthong-Position āi/aī)
  Caron-Sibilanten    š→s ž→z ź→z č→c
  Stress-Akzent       à→a è→e ì→i ò→o ù→u  (+ akut, ǹ→n)
  Rhotik/Lateral      ŕ→r ĺ→l ľ→l
  c↔k (Lehnwörter)    c→k
  themat. Vokal -s    (a|i|u) vor wortfinalem s gelöscht  (-as/-is/-us ~ -s)

Aufruf:
  python -m prussian.fst.ortho            # Recall gegen data/external-Dicts
  python -m prussian.fst.ortho --save     # zusätzlich build/ortho.fst sichern
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pyfoma import FST

ROOT = Path(__file__).resolve().parent.parent.parent.parent
TW_PATH = ROOT / "data/external/twanksta_entries.json"
PR_PATH = ROOT / "data/external/prusaspira_entries.json"
ORTHO_OUT = ROOT / "build/ortho.fst"

#: Deterministische Einzelzeichen-Faltung (Diakritika + c→k), parallel.
_CHAR_FOLD = (
    "ā:a|ē:e|ī:i|ō:o|ū:u|"          # Macron
    "š:s|ž:z|ź:z|č:c|"               # Caron
    "à:a|è:e|ì:i|ò:o|ù:u|"          # Gravis
    "á:a|é:e|í:i|ó:o|ú:u|ǹ:n|"      # Akut + ǹ
    "ŕ:r|ĺ:l|ľ:l|"                   # Rhotik/Lateral
    "c:k"                            # Lehnwort-c
)

#: Thematischer Vokal vor wortfinalem s (Nom.-Endung -as/-is/-us ~ -s).
_THEMATIC_S = "$^rewrite((a|i|u):'' / _ s #)"

#: Adjektiv-/Adverb-Endung -an ~ -u (Twanksta -iskan ~ Prusaspira -isku).
_END_AN_U = "$^rewrite((a n):u / _ #)"


@lru_cache(maxsize=1)
def fold_fst() -> FST:
    """Falt-Transducer (Zeichen-Faltung ∘ Themavokal-Tilgung ∘ -an~-u)."""
    return (FST.re(f"$^rewrite({_CHAR_FOLD})")
            .compose(FST.re(_THEMATIC_S))
            .compose(FST.re(_END_AN_U)))


def fold(word: str) -> str:
    """Skelettform eines Lemmas (deterministisch, eine Ausgabe)."""
    outs = fold_fst().apply(word.lower())
    return next(iter(outs))


# ── isolierte Validierung gegen die Wörterbücher ───────────────────────────
def _evaluate() -> None:
    import json
    from collections import defaultdict

    tw = [e["word"] for e in json.loads(TW_PATH.read_text(encoding="utf-8"))]
    pr = [e["word"] for e in json.loads(PR_PATH.read_text(encoding="utf-8"))]
    tw_set, pr_set = set(tw), set(pr)

    pr_by_skel: dict[str, set[str]] = defaultdict(set)
    for w in pr_set:
        pr_by_skel[fold(w)].add(w)

    exact = tw_set & pr_set
    rest = sorted(tw_set - pr_set)
    paired = {}
    for w in rest:
        hits = pr_by_skel.get(fold(w), set()) - {w}
        if hits:
            paired[w] = sorted(hits)

    uniq = sum(1 for h in paired.values() if len(h) == 1)
    print(f"Twanksta unique : {len(tw_set)}")
    print(f"Prusaspira uniq : {len(pr_set)}")
    print(f"exakt gleich    : {len(exact)}")
    print(f"Rest (nur tw)   : {len(rest)}")
    print(f"  davon gepaart : {len(paired)}  (1:1: {uniq})")
    print("Beispiele:", ", ".join(
        f"{w}↔{paired[w][0]}" for w in list(paired)[:6]))


def main() -> None:
    import sys
    if "--save" in sys.argv:
        ORTHO_OUT.parent.mkdir(exist_ok=True)
        fold_fst().save(str(ORTHO_OUT))
        print(f"gespeichert: {ORTHO_OUT}")
    _evaluate()


if __name__ == "__main__":
    main()
