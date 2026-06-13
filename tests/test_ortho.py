"""Orthographievarianten: lenient.fst akzeptiert Quellschreibungen,
analyser.fst lehnt sie ab (Testfälle des früheren ortho.fst + BACKLOG)."""

import pytest

# (Variante, Standardform) — aus den Sanity-Checks des alten build_ortho_fst.py
VARIANT_PAIRS = [
    ("kūgjan", "kūgin"),
    ("kūgjai", "kūgei"),
    ("kūgju", "kūģu"),
    ("kūgjas", "kūges"),
    ("māldaisjan", "māldaisin"),
    ("dulzjai", "dulžai"),
    ("dulzjas", "dulžas"),
    ("dulzju", "dulžu"),
    ("garkītjamans", "garkītemans"),
]


@pytest.mark.parametrize("variant,standard", VARIANT_PAIRS)
def test_variante_liefert_standardanalyse(lenient, analyser, variant, standard):
    std_analyses = set(analyser.analyze(standard))
    assert std_analyses, f"Standardform {standard!r} nicht analysierbar"
    assert std_analyses <= set(lenient.analyze(variant))


@pytest.mark.parametrize("variant,_", VARIANT_PAIRS)
def test_standard_analysator_lehnt_variante_ab(analyser, variant, _):
    assert not list(analyser.analyze(variant))


def test_standard_generiert_keine_varianten(analyser):
    """generate() liefert nur Standardorthographie (keine V-Pfade)."""
    forms = set(analyser.generate("kūgis+N+Msc+Sg+Dat"))
    assert "kūģu" in forms
    assert "kūgju" not in forms


def test_elaktr_variante(lenient, analyser):
    """elektr- ↔ elaktr- (BACKLOG): nur falls elektr-Lexeme im Build sind."""
    probe = None
    for word in ("elektriskas", "elektrisks"):
        if list(analyser.analyze(word)):
            probe = word
            break
    if probe is None:
        pytest.skip("kein elektr-Lexem im Build (gold-only?)")
    variant = probe.replace("elektr", "elaktr")
    assert set(analyser.analyze(probe)) <= set(lenient.analyze(variant))
