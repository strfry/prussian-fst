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

from prussian_fst.cg3_pipeline import relevant_checks, sentence_status  # noqa: E402


def coverage(word_tokens=4, oov=(), collapsed=(), ambig=(), unlicensed=(),
             checks=("prep-case",)):
    return {
        "word_tokens": word_tokens,
        "oov": list(oov),
        "collapsed": list(collapsed),
        "ambig": list(ambig),
        "unlicensed": list(unlicensed),
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


def test_unlicensed_case_is_out_of_coverage():
    # Kasus ohne lizenzierenden Kontext (fragmentierter Baum) →
    # Abstention, keine Violation
    cov = coverage(unlicensed=[{"index": 3, "form": "stan"}])
    assert sentence_status([], cov) == "out_of_coverage"
    assert "unlicensed_case" in cov["reasons"]


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
    # Realistischer Pipeline-Output: @-Rollentags sind beim Parsen
    # bereits aus den Lesarten gefiltert — der subj-verb-Anker ist
    # das Nom-P1/P2-Pronomen plus finites Verb im Satz.
    cohorts = [
        cohort("As", ("as", "Pron", "P1", "Sg", "Nom"), dep=(1, 2)),
        cohort("pūwa", ("pūtun", "V", "Ind", "Pret", "P1", "Sg"), dep=(2, 2)),
        cohort("sen", ("sēn", "Prp", "GovAkk"), dep=(3, 4)),
        cohort("laīwan", ("laīwan", "N", "Sg", "Akk", "Neut"), dep=(4, 2)),
    ]
    checks = relevant_checks(cohorts, genverbs=set())
    assert "prep-case" in checks
    assert "subj-verb" in checks
    assert "pred-nom" not in checks


def test_relevant_checks_subj_verb_needs_finite_verb():
    # Pronomen ohne finites Verb (verbloser Satz) — kein Anker
    cohorts = [
        cohort("Tū", ("tū", "Pron", "P2", "Sg", "Nom"), dep=(1, 1)),
        cohort("stwi", ("stwi", "Adv"), dep=(2, 1)),
    ]
    assert "subj-verb" not in relevant_checks(cohorts, genverbs=set())


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


# ── Regressionsbatterie: Positiv-/Negativpaare über die echte
#    Pipeline (Arbeitsauftrag 2026-07: 0 false verifies).  Läuft nur
#    mit gebauten Artefakten (cg-proc + base.hfstol), wie test_api.py.

import shutil  # noqa: E402

FST_OL = REPO / "build/base.hfstol"
needs_pipeline = pytest.mark.skipif(
    not (shutil.which("cg-proc") and FST_OL.exists()),
    reason="cg-proc/base.hfstol nicht verfügbar",
)


@needs_pipeline
@pytest.mark.parametrize("text,status,rules_or_reasons", [
    # A1: Prädikatsnomen im Akkusativ
    ("As asma prūsiskan wīran.", "violations_found", {"pred-nom-akk"}),
    # A1: Adj-Kongruenz in der Prädikats-NP (Pl+Fem neben Masc.Sg-Kopf)
    ("As asma prūsiskas wīrs.", "violations_found",
     {"agr-adj-num", "agr-adj-gend"}),
    ("As asma prūsisks wīrs.", "verified_in_coverage", set()),
    # P2: Nominativ in PP feuert lokal trotz OOV (ēimi) im Satz
    ("As ēimi en stas buttas.", "violations_found", {"pp-nom"}),
    # P3: doppeltes Nominativ-Subjekt (turītun-Valenz)
    ("Tū turri stas wīrs.", "violations_found", {"subj-dup"}),
    # P3: Numerusclash Subjekt↔Verb (waida hat P1 nur als Sg)
    ("Mes waida stan wīran.", "violations_found", {"agr-subj-verb-num"}),
    ("Tū turri stan wīran.", "verified_in_coverage", set()),
    # A2: frei schwebendes Nominal → Degradierung, keine Verifikation
    ("As asma stan autōmatikin rekōnstruiwuns be sen grammatikin "
     "perbāndan plattinuns.", "out_of_coverage", {"unlicensed_case"}),
    # Verbloser Einzel-Wurzel-Satz bleibt von unlicensed_case unberührt
    ("Labban dēinan!", "verified_in_coverage", set()),
])
def test_validation_battery(text, status, rules_or_reasons):
    from prussian_fst import api
    r = api.validate(text)[0]
    assert r["status"] == status, r
    if status == "violations_found":
        assert rules_or_reasons <= {v["rule"] for v in r["violations"]}, r
    elif status == "out_of_coverage":
        assert rules_or_reasons <= set(r["coverage"]["reasons"]), r
    else:
        assert not r["violations"], r
