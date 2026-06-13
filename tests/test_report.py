"""Schwellwert-Guardrails über dieselbe Pipeline, die das Dashboard speist —
eine Quelle der Wahrheit. Bei fehlendem Build überspringen die conftest-
Fixtures (analyser/lenient) automatisch.

Die volle Pipeline ist teuer (Dict-Coverage + Korpus-Scan), darum **einmal**
pro Session über die ``report``-Fixture und Asserts auf das Ergebnis-dict.
"""

import json

import pytest

from prussian.report import dashboard


@pytest.fixture(scope="session")
def report(analyser, lenient):
    return dashboard.build(analyser, lenient)


def test_generation_integrity(report):
    """Jede Gold-Zelle generiert die erwartete Form (nominal + verbal)."""
    gen = report["health"]["generation"]
    for slice_ in ("nominal", "verbal"):
        b = gen[slice_]
        assert b["no_gen"] == 0, f"{slice_}: {b['no_gen']} Zellen ohne Generierung"
        assert b["mismatch"] == 0, f"{slice_}: {b['mismatch']} echte Mismatches"
    assert gen["nominal"]["variants_matched"] == gen["nominal"]["variants_total"]


def test_nominal_dict_coverage(report):
    # Regressions-Guardrail unter dem Ist-Stand (heute ~51 %; Adjektiv-Formen
    # im Wörterbuch sind die Hauptlücke). Soll Einbrüche fangen, nicht Ziel sein.
    fc = report["kpis"]["form_coverage"]
    assert fc["pct"] > 45.0, f"Dict-Coverage nur {fc['pct']}%"


def test_function_words_recognized(report):
    cc = report["closed_class"]
    assert cc["recognized"] == cc["total"], cc["per_pos"]


def test_tatoeba_corpus_coverage(report):
    """Headline-Korpus (sauberes Tatoeba) muss > 60 % Coverage haben."""
    tatoeba = next(s for s in report["corpus"]["sources"] if s["id"] == "tatoeba")
    assert tatoeba["coverage_pct"] > 60.0, f"Tatoeba nur {tatoeba['coverage_pct']}%"


def test_spam_filter_active(report):
    """Der Wiki-Korpus muss Spam-Docs verwerfen (1xbet & Co.)."""
    wiki = next(s for s in report["corpus"]["sources"] if s["id"] == "prusaspira_wiki")
    assert wiki["dropped_docs"] > 0


def test_dashboard_strict_json(report):
    """Vollständiges, serialisierbares JSON nach Schema 2.0."""
    again = json.loads(json.dumps(report, ensure_ascii=False))
    assert again["meta"]["schema_version"] == dashboard.SCHEMA_VERSION
    assert {"kpis", "health", "pos", "paradigms",
            "corpus", "closed_class"} <= again.keys()
