"""Roundtrip: jede Goldstandard-Form wird generiert UND analysiert.

Orakel ist resolve_stem (die frühere Bake-Logik) — der FST muss über
lexd + Regelschicht dieselben Oberflächen liefern.
"""

from prussian.report.cases import nominal_cases, verbal_cases


def _check(analyser, cases):
    gen_fail, ana_fail, var_fail = [], [], []
    n = 0
    for c in cases:
        n += 1
        results = list(analyser.generate(c.tag))
        if c.expected not in results:
            gen_fail.append((c.tag, c.expected, results))
        elif c.tag not in analyser.analyze(c.expected):
            ana_fail.append((c.expected, c.tag))
        if c.variant is not None and c.variant not in results:
            var_fail.append((c.tag, c.variant, results))
    assert not gen_fail, f"{len(gen_fail)}/{n} Generierungsfehler: {gen_fail[:5]}"
    assert not ana_fail, f"{len(ana_fail)}/{n} Analysefehler: {ana_fail[:5]}"
    assert not var_fail, f"{len(var_fail)} Doubletten fehlen: {var_fail[:5]}"


def test_nominal_roundtrip(analyser, gold_nominal):
    _check(analyser, nominal_cases(gold_nominal))


def test_verbal_roundtrip(analyser, gold_verbal):
    _check(analyser, verbal_cases(gold_verbal))


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
