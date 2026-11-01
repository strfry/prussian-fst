"""Tests for the paradigm generator (gen/generator.py + gen/paradigms.json).

Expected forms are Twanksta cells, not generator output, so the tests are not
circular. They need only the committed table, no corpus file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "gen"))

import generator as gen  # noqa: E402

# ── Slot vocabulary ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("slot, tag", [
    ("sg.nom", "+N+Sg+Nom"), ("pl.dat", "+N+Pl+Dat"),
    ("msc.sg.nom", "+A+Msc+Sg+Nom"), ("neu.pl.acc", "+A+Neu+Pl+Acc"),
    ("comp.msc.sg.nom", "+A+Comp+Msc+Sg+Nom"), ("superl.neu.sg.dat", "+A+Superl+Neu+Sg+Dat"),
    ("adv", "+Adv"), ("adv.comp", "+Adv+Comp"), ("adv.superl", "+Adv+Superl"),
    ("prs.sg1", "+V+Ind+Prs+Sg1"), ("prs.sp3", "+V+Ind+Prs+SP3"),
    ("prt.pl2", "+V+Ind+Prt+Pl2"), ("subj.sg1", "+V+Subj+Sg1"),
    ("subj.sp3", "+V+Subj+SP3"), ("opt", "+V+Opt+SP3"),
    ("imprt.sg2", "+V+Imprt+Sg2"), ("imprt.pl2", "+V+Imprt+Pl2"),
    ("part.prs.act.msc.sg.nom", "+V+PrsPrc+Act+Msc+Sg+Nom"),
    ("part.prf.act.msc.sg.nom", "+V+PrfPrc+Act+Msc+Sg+Nom"),
    ("part.prf.pss.neu.pl.gen", "+V+PrfPrc+Pss+Neu+Pl+Gen"),
])
def test_slot_tag(slot, tag):
    assert gen.slot_tag(slot) == tag


@pytest.mark.parametrize("bad", [
    "sg", "sg.loc", "comp.msc.nom", "prs.p4", "prs.sp3.pl", "nonsense", "sg.nom.x",
])
def test_slot_tag_rejects_unknown(bad):
    with pytest.raises(ValueError):
        gen.slot_tag(bad)


def test_slot_tags_are_distinct():
    slots = [s for pos_slots in gen.SLOTS.values() for s in pos_slots]
    tags = [gen.slot_tag(s) for s in slots]
    assert len(set(tags)) == len(tags)


# ── Rules ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("text, rule", [
    ("ē>is", ("", "ē", "is", False)),
    ("~ē>īmans", ("", "ē", "īmans", True)),
    ("uka+is>", ("uka", "is", "", False)),
    ("~uka+s>is", ("uka", "s", "is", True)),
    (">", ("", "", "", False)),
])
def test_rule_notation_roundtrips(text, rule):
    assert gen.parse_rule(text) == rule
    assert gen.format_rule(rule) == text


def test_rule_without_arrow_is_rejected():
    with pytest.raises(ValueError):
        gen.parse_rule("ēis")


@pytest.mark.parametrize("stem, light", [
    ("zemm", "zem"), ("akkint", "akint"), ("Mettelā", "Metela"), ("bīl", "bil"),
])
def test_destress_shortens_macrons_and_simplifies_geminates(stem, light):
    assert gen.destress(stem) == light


def test_first_matching_rule_wins_and_needs_a_stem():
    rules = [gen.parse_rule(r) for r in ("arē>arris", "ē>is")]
    assert gen.apply_rules(rules, "zemē") == "zemis"
    assert gen.apply_rules(rules, "garē") == "garris"
    assert gen.apply_rules([gen.parse_rule("ē>is")], "ē") is None   # nothing left


def test_table_is_well_formed():
    """Every rule parses; every source is the lemma or a principal form of its pos;
    a principal form is always derived from the lemma."""
    for fam, pars in gen._table().items():
        principal = gen.PRINCIPAL[fam]
        for par, spec in pars.items():
            for slot, (source, rules) in spec.items():
                assert slot in gen.SLOTS[fam], (fam, par, slot)
                assert rules, (fam, par, slot)
                assert source == gen.LEMMA or source in principal, (fam, par, slot, source)
                if slot in principal:
                    assert source == gen.LEMMA, (fam, par, slot)
                if fam == "verb":
                    assert source == gen.verb_source(slot), (par, slot, source)


# ── Forms (expected = Twanksta cells) ────────────────────────────────────────


@pytest.mark.parametrize("pos, paradigm, lemma, forms", [
    ("noun", "53", "zemē", {"sg.gen": "zemmis", "sg.dat": "zemmei", "pl.dat": "zemīmans"}),
    ("noun", "56", "Adwēnts", {"sg.gen": "Adwēntis", "sg.dat": "Adwēnti",
                               "pl.nom": "Adwēntjai"}),
    ("adj", "27", "wilnis", {"fem.sg.nom": "wilni", "comp.msc.sg.nom": "wilnjaisis",
                             "superl.msc.sg.nom": "ukawilnjaisis", "adv": "wilnjai"}),
    ("verb", "132", "mitātun", {"prs.sp3": "mitāi", "prs.pl1": "mitāimai",
                                "part.prf.act.msc.sg.nom": "mitāwuns",
                                "part.prf.pss.msc.sg.nom": "mitāts"}),
    ("verb", "136", "kalbītwei", {"prs.sp3": "kalba", "prt.sp3": "kalbēi",
                                  "prt.pl1": "kalbēimai", "imprt.sg2": "kalbais"}),
    ("verb", "85", "treptun", {"prs.sp3": "treppa", "prs.pl1": "treppimai",
                               "opt": "trepsei", "part.prf.pss.msc.sg.nom": "trepts"}),
])
def test_forms(pos, paradigm, lemma, forms):
    out = gen.generate(pos, paradigm, lemma)
    for slot, form in forms.items():
        assert out[slot] == (form,), slot


def test_u_stem_adverb_follows_the_errata():
    """Twanksta's -u is a data error (corpus/TWANKSTA_ERRATA.md): the adverb is -jai."""
    assert gen.generate("adj", "31", "gillus")["adv"] == ("gilljai",)


def test_given_principal_form_feeds_its_group():
    """A listed prt.sp3 is the source of the other preterite cells."""
    out = gen.generate("verb", "136", "kalbītwei", {"prt.sp3": ["kalbēja"]})
    assert out["prt.pl1"] == ("kalbējamai",)
    assert out["prt.sp3"] == ("kalbēi",)     # the principal slot itself stays derived


@pytest.mark.parametrize("slot, source", [
    ("prs.pl1", "prs.sp3"), ("imprt.sg2", "prs.sp3"), ("prt.pl2", "prt.sp3"),
    ("subj.sg1", "subj.sp3"), ("opt", "subj.sp3"), ("subj.sp3", "lemma"),
    ("part.prs.act.fem.sg.gen", "part.prs.act.msc.sg.nom"),
    ("part.prf.act.neu.pl.dat", "part.prf.act.msc.sg.nom"),
    ("part.prf.pss.fem.sg.gen", "part.prf.pss.msc.sg.nom"),
    ("part.prf.pss.msc.sg.nom", "lemma"),
])
def test_verb_source_is_fixed_per_group(slot, source):
    assert gen.verb_source(slot) == source


def test_given_subjunctive_feeds_its_group_and_the_optative():
    """ebēitun (116) has no subjunctive rule of its own; a listed subj.sp3 carries
    subj.* and opt."""
    out = gen.generate("verb", "116", "ebēitun", {"subj.sp3": ["ebēilai"]})
    assert out["subj.pl1"] == ("ebēilimai",)
    assert out["opt"] == ("ebēisei",)


def test_principal_form_with_variants_is_not_a_source():
    out = gen.generate("verb", "136", "kalbītwei", {"prt.sp3": ["kalbēja", "kalbēi"]})
    assert out["prt.pl1"] == ("kalbēimai",)


def test_reflexive_lemma_is_generated_without_the_particle():
    assert gen.generate("verb", "136", "kalbītwei si") == gen.generate("verb", "136", "kalbītwei")


def test_pronoun_and_numeral_inflect_as_adjectives():
    assert gen.paradigm_slots("num", "21") == gen.paradigm_slots("adj", "21")


def test_unknown_paradigm_is_a_key_error():
    with pytest.raises(KeyError, match="unknown paradigm"):
        gen.generate("noun", "999", "zemē")
