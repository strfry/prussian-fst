"""Unit-Tests für die dreiwertige Status-Logik des Validators
(cg3_pipeline.sentence_status / relevant_checks) — reine Python-Logik
mit synthetischen Cohort-Dicts, läuft ohne vislcg3/hfst/base.fst.

Kernprinzip: „kein Fehler-Tag" ist NICHT „korrekt" — OOV, Kollaps,
fehlende anwendbare Prüfregeln oder hohe Restambiguität ergeben
out_of_coverage, nie verified_in_coverage.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "fst/scripts"))

from cg3_pipeline import relevant_checks, sentence_status  # noqa: E402


def coverage(word_tokens=4, oov=(), collapsed=(), ambig=(), checks=("prep-case",)):
    return {
        "word_tokens": word_tokens,
        "oov": list(oov),
        "collapsed": list(collapsed),
        "ambig": list(ambig),
        "checks_relevant": list(checks),
        "reasons": [],
    }


VIOLATION = [{"rule": "prep-akk-dat", "tag": "&prep-akk-dat", "index": 4,
              "form": "laīwu", "reading": "laīwan+N+Sg+Dat+Neut",
              "message": ""}]


def test_violations_win():
    cov = coverage()
    assert sentence_status(VIOLATION, cov) == "violations_found"


def test_violations_win_even_out_of_coverage():
    # Ein gefundener Fehler ist positive Evidenz — auch bei OOV im Satz
    cov = coverage(oov=[{"index": 1, "form": "xyz"}])
    assert sentence_status(VIOLATION, cov) == "violations_found"


def test_verified_needs_clean_coverage():
    assert sentence_status([], coverage()) == "verified_in_coverage"


def test_oov_is_not_correct():
    cov = coverage(oov=[{"index": 1, "form": "xyz"}])
    assert sentence_status([], cov) == "out_of_coverage"
    assert "oov" in cov["reasons"]


def test_collapse_is_out_of_coverage():
    # Kollaps (0 Lesarten) kann auch grammatischer, unmodellierter
    # Input sein → Abstention, keine Violation
    cov = coverage(collapsed=[{"index": 2, "form": "wīrans"}])
    assert sentence_status([], cov) == "out_of_coverage"
    assert "collapsed" in cov["reasons"]


def test_no_applicable_checks_is_not_correct():
    cov = coverage(checks=())
    assert sentence_status([], cov) == "out_of_coverage"
    assert "no_applicable_checks" in cov["reasons"]


def test_residual_ambiguity_threshold():
    ambig = [{"index": i, "form": "x", "n_readings": 2} for i in (1, 2)]
    cov = coverage(word_tokens=4, ambig=ambig)  # 50% > AMBIG_MAX
    assert sentence_status([], cov) == "out_of_coverage"
    assert "residual_ambiguity" in cov["reasons"]

    cov = coverage(word_tokens=8, ambig=ambig[:1])  # 12.5% ≤ AMBIG_MAX
    assert sentence_status([], cov) == "verified_in_coverage"


# ── relevant_checks: Anker-Heuristik ──

def cohort(form, *readings, dep=None):
    return {"form": form, "dep": dep, "errtags": [],
            "readings": [{"lemma": lemma, "tags": list(tags)}
                         for lemma, *tags in readings]}


def test_relevant_checks_anchors():
    cohorts = [
        cohort("As", ("as", "Pron", "P1", "Sg", "Nom", "@SUBJ"), dep=(1, 2)),
        cohort("pūwa", ("pūtun", "V", "Ind", "Pret", "P1", "Sg"), dep=(2, 2)),
        cohort("sen", ("sēn", "Prp", "GovAkk"), dep=(3, 4)),
        cohort("laīwan", ("laīwan", "N", "Sg", "Akk", "Neut"), dep=(4, 2)),
    ]
    checks = relevant_checks(cohorts, genverbs=set())
    assert "prep-case" in checks
    assert "subj-verb" in checks
    assert "pred-nom" not in checks


def test_relevant_checks_adj_needs_nominal_parent():
    # Adjektiv mit N-Parent → adj-agr anwendbar
    cohorts = [
        cohort("Labban", ("labs", "Adj", "Sg", "Akk", "Fem"), dep=(1, 2)),
        cohort("dēinan", ("dēinā", "N", "Sg", "Akk", "Fem"), dep=(2, 2)),
    ]
    assert "adj-agr" in relevant_checks(cohorts, genverbs=set())
    # Adverb-aufgelöstes Adjektiv ohne Nominal-Parent → nicht anwendbar
    cohorts = [
        cohort("Bilāimai", ("bilītun", "V", "Ind", "Pres", "P1", "Pl")),
        cohort("prūsiskai", ("prūsiskai", "Adv")),
    ]
    assert "adj-agr" not in relevant_checks(cohorts, genverbs=set())


def test_relevant_checks_genverb_and_steisan():
    cohorts = [
        cohort("Tāns", ("tāns", "Pron", "P3", "Sg", "Nom", "Masc")),
        cohort("bijja", ("bijātun", "V", "Ind", "Pres", "P3")),
        cohort("stēisan", ("stas", "Pron", "Pl", "Gen", "Masc")),
    ]
    checks = relevant_checks(cohorts, genverbs={"bijātun"})
    assert "genverb" in checks
    assert "steisan" in checks
