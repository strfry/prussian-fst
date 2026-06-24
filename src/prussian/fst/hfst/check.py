#!/usr/bin/env python3
"""Validiert den HFST-Build gegen die Gold-Formen (= gen_check für den HFST-Zweig).

Spiegelt ``report.generation.run`` über einen Lookup-Adapter: der HFST-
``generator`` (Analyse → Oberfläche) wird mit ``.generate(tag)`` angesprochen,
``analyser``/``lenient`` (Oberfläche → Analyse) mit ``.analyze(form)``. So
greift dieselbe Zell-Klassifikation wie im pyfoma-Zweig.

Tag-Notation: die HFST-Transducer (lexd-Build) arbeiten mit ``<Sg><Nom>``-
Multichar-Symbolen; der Adapter bildet im- und exportseitig auf das Giella-
konforme ``+Sg+Nom``-Format ab, das Goldstandard, cases.py und tags.py nutzen.

Aufruf (hfst-venv):  PYTHONPATH=src python -m prussian.fst.hfst.check
"""

import json
import re
from pathlib import Path

import hfst

from prussian.report import generation

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
BUILD = ROOT / "build/hfst"
GOLD = ROOT / "data/gold/goldstandard.json"
VERB_GOLD = ROOT / "data/gold/goldstandard_verben_fst.json"

_EPS = "@_EPSILON_SYMBOL_@"
#: Bekannte verbale Generierungslücke (PrsPrc/PstPrc Fem/Neut), identisch im
#: pyfoma-Zweig — solange nicht modelliert, ist das die zulässige Baseline.
VERBAL_NOGEN_BASELINE = 48

#: regex: +Sg+Nom → <Sg><Nom> (für lookup in HFST-Transducer)
_PLUS_TO_LEXD = re.compile(r"\+([A-Za-z0-9]+)")
#: regex: <Sg><Nom> → +Sg+Nom (für API-Ausgabe)
_LEXD_TO_PLUS = re.compile(r"<([A-Za-z0-9]+)>")


def _to_lexd(s: str) -> str:
    return _PLUS_TO_LEXD.sub(r"<\1>", s)


def _to_plus(s: str) -> str:
    return _LEXD_TO_PLUS.sub(r"+\1", s)


def _clean(out: str) -> str:
    return out.replace(_EPS, "")


def _load(path: Path):
    return hfst.HfstInputStream(str(path)).read()


class Generator:
    """Adapter: hfst-Transducer mit pyfoma-naher ``.generate``/``.analyze``-API.

    Konvertiert Eingabe-Tags von ``+Tag``- (Goldstandard/API) nach ``<Tag>``-
    Format (lexd) beim Lookup; Analyse-Ergebnisse werden zurückkonvertiert,
    sodass Konsumenten durchgängig ``+Tag``-Format sehen.
    """

    def __init__(self, fst):
        self.fst = fst

    def generate(self, tag: str) -> list[str]:
        return sorted({_clean(o) for o, _w in self.fst.lookup(_to_lexd(tag))})

    def analyze(self, form: str) -> list[str]:
        return sorted({_to_plus(_clean(o)) for o, _w in self.fst.lookup(form)})


def _print_slice(name: str, b: dict) -> None:
    print(f"\n=== {name} ===")
    print(
        f"  cells={b['cells']}  exact={b['exact']}  case_only={b['case_only']}"
        f"  no_gen={b['no_gen']}  mismatch={b['true_mismatch']}"
        f"  variants={b['variants_matched']}/{b['variants_total']}"
    )
    for s in b["no_gen_samples"][:12]:
        print(
            f"  NO-GEN  P{s['paradigm']} {s['lemma']}: {s['tag']} exp={s['expected']!r}"
        )
    for s in b["mismatch_samples"][:12]:
        print(
            f"  MISMATCH P{s['paradigm']} {s['lemma']}: exp={s['expected']!r} got={s['got']!r}"
        )


def main() -> None:
    generator = Generator(_load(BUILD / "generator.hfst"))
    analyser = Generator(_load(BUILD / "analyser.hfst"))
    lenient = Generator(_load(BUILD / "lenient.hfst"))

    gold_nom = json.loads(GOLD.read_text(encoding="utf-8"))
    gold_verb = json.loads(VERB_GOLD.read_text(encoding="utf-8"))
    result = generation.run(generator, gold_nom, gold_verb)
    _print_slice("Nominal", result["nominal"])
    _print_slice("Verbal", result["verbal"])

    print("\n--- Analyse-Spot-Checks (analyser) ---")
    for form, expected in [
        ("wāiks", "wāiks+N+Msc+Sg+Nom"),
        ("kūģu", "kūgis+N+Msc+Sg+Dat"),
        ("wīrs", "wīrs+N+Msc+Sg+Nom"),
    ]:
        got = analyser.analyze(form)
        print(f"  {'OK' if expected in got else 'FAIL':6s} {form} → {expected}  {got}")

    # Faltungs-Lenient (hfst.fold ∘ Analysator): orthographische + palatal-
    # konsonantische Twanksta-j-Varianten. Das weichvokalische Twanksta-j
    # (kūgjan~kūgin) ist morphologisch und kommt aus der gold-freien
    # Morphologie, nicht aus der Faltung — daher hier kein Testfall.
    print("\n--- Faltungs-Spot-Checks (lenient) ---")
    for variant, expected in [
        ("kūgju", "kūgis+N+Msc+Sg+Dat"),       # palatales j (gj~ģ)
        ("dulzjas", "dulzis+N+Msc+Sg+Gen"),    # zj~ž
    ]:
        got = lenient.analyze(variant)
        std_ok = analyser.analyze(variant)  # darf der Standard NICHT
        print(
            f"  {'OK' if expected in got else 'FAIL':6s} {variant} → {expected}"
            f"  lenient={got}  (std={std_ok})"
        )

    # Gate (CI): nominal muss vollständig generieren, kein true_mismatch.
    # Die verbalen no_gen sind die bekannte Partizip-Deklinations-Lücke (Fem/
    # Neut von PrsPrc/PstPrc), die der pyfoma-Zweig identisch hat — Baseline 48.
    nom, verb = result["nominal"], result["verbal"]
    mism = nom["true_mismatch"] + verb["true_mismatch"]
    print(
        f"\nnominal no_gen={nom['no_gen']}  mismatch={mism}  "
        f"verbal no_gen={verb['no_gen']} (Baseline {VERBAL_NOGEN_BASELINE})"
    )
    if nom["no_gen"] or mism or verb["no_gen"] > VERBAL_NOGEN_BASELINE:
        raise SystemExit("Regression gegenüber Baseline")


if __name__ == "__main__":
    main()
