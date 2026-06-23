"""Akzentmodell (docs/AKZENT.md): Ableitung muss konfliktfrei bleiben.

Schutz gegen Regressionen, wenn goldstandard.json neu generiert wird:
das Rinkevičius-Modell (globale Endungsstärke + Lexemklassen) muss die
betont-Flags weiterhin vollständig erklären.
"""

from prussian.gold.accent import derive_nominal_model, derive_verb_classes


def test_volle_abdeckung_ohne_exceptions(gold_nominal):
    _classes, _strength, _pairs, exceptions, (correct, total) = \
        derive_nominal_model(gold_nominal)
    assert total > 0
    assert correct == total, f"Abdeckung {correct}/{total}"
    assert exceptions == []


def test_dreiteilung_exakt(gold_nominal):
    """Grunddeklination: bar ⟺ Archiphonem+alle betont; na ⟺ kein Archiphonem
    (AKZENT.md §3.1). Produktive Steigerung trägt den Akzent auf dem Suffix
    und steht außerhalb der Dreiteilung (§3.6): alle Zellen betont."""
    classes, *_ = derive_nominal_model(gold_nominal)
    for e in gold_nominal:
        cls = classes[(e["paradigm"], e["gender"])]["class"]
        if cls == "steig":
            assert all(v["betont"] for v in e["suffixe"].values()), \
                f"P{e['paradigm']} {e['lemma']}: steig, aber nicht alle betont"
            continue
        has_arch = any(c.isupper() for c in e["stamm"])
        assert (cls == "na") == (not has_arch), \
            f"P{e['paradigm']} {e['lemma']}: class={cls}, arch={has_arch}"


def test_verben_nur_infinitiv_ablaut(gold_verbal):
    """Finite Verbmuster: Mischung betrifft nur den Infinitiv = Ablaut
    (AKZENT.md §3.5). Partizipien dekliniert nominal und dürfen mobil sein
    (§3.6)."""
    for rec in derive_verb_classes(gold_verbal):
        if rec["tense"].endswith("ptcp"):
            assert rec["class"] in ("bar", "na", "mob"), rec
            continue
        assert rec["class"] in ("bar", "na", "ablaut"), rec
        if rec["class"] == "ablaut":
            assert rec["unbetonte_zellen"] == ["Inf"], rec
