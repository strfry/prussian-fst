"""Roundtrip: jede Goldstandard-Form wird generiert UND analysiert.

Orakel ist resolve_stem (die frühere Bake-Logik) — der FST muss über
lexd + Regelschicht dieselben Oberflächen liefern.
"""

from prussian.fst.entries import (
    cell_tag, resolve_stem, split_reflexive, split_suffix,
    tag_prefix, verb_cell_tag,
)


def _nominal_cases(entries):
    for e in entries:
        prefix = tag_prefix(e["paradigm"], e["gender"])
        for cell, v in e["suffixe"].items():
            std, variant = split_suffix(v["suffix"])
            expected = resolve_stem(
                e["stamm"], v["betont"], v.get("palatize", False)) + std
            yield f"{e['lemma']}{prefix}{cell_tag(cell)}", expected, variant


def _verbal_cases(entries):
    for e in entries:
        for cell, v in e["suffixe"].items():
            bare, refl = split_reflexive(v["suffix"])
            tcell = verb_cell_tag(e["tense"], cell, refl)
            std, variant = split_suffix(bare)
            expected = resolve_stem(
                e["stamm"], v["betont"], v.get("palatize", False)) + std
            yield f"{e['lemma']}+V{tcell}", expected, variant


def _check(analyser, cases):
    gen_fail, ana_fail, var_fail = [], [], []
    n = 0
    for tag, expected, variant in cases:
        n += 1
        results = list(analyser.generate(tag))
        if expected not in results:
            gen_fail.append((tag, expected, results))
        elif tag not in analyser.analyze(expected):
            ana_fail.append((expected, tag))
        if variant is not None and variant not in results:
            var_fail.append((tag, variant, results))
    assert not gen_fail, f"{len(gen_fail)}/{n} Generierungsfehler: {gen_fail[:5]}"
    assert not ana_fail, f"{len(ana_fail)}/{n} Analysefehler: {ana_fail[:5]}"
    assert not var_fail, f"{len(var_fail)} Doubletten fehlen: {var_fail[:5]}"


def test_nominal_roundtrip(analyser, gold_nominal):
    _check(analyser, _nominal_cases(gold_nominal))


def test_verbal_roundtrip(analyser, gold_verbal):
    _check(analyser, _verbal_cases(gold_verbal))


def test_akzent_alternation(analyser):
    """Kernfälle des Akzentmodells (docs/AKZENT.md §3)."""
    # Mobile: Stamm kurz vor starker Endung, lang vor schwacher
    assert "mīstan+N+Neut+Pl+Nom" in analyser.analyze("mistāi")
    assert "mīstan+N+Neut+Sg+Nom" in analyser.analyze("mīstan")
    assert "mīstan+N+Neut+Pl+Dat" in analyser.analyze("mistammans")
    # Baryton: Stamm überall lang
    assert "wīrs+N+Msc+Sg+Nom" in analyser.analyze("wīrs")
    assert "wīrs+N+Msc+Pl+Nom" in analyser.analyze("wīrai")
    # Falsche Längen werden abgelehnt
    assert not list(analyser.analyze("mīstāi"))
    assert not list(analyser.analyze("mistan"))
    assert not list(analyser.analyze("wirs"))
