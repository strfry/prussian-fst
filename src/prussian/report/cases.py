"""Generierungs-Orakel: (POS, Paradigma, Lemma, Tag, erwartete Form, Doublette).

Einzige Quelle für die Gold-Zellen-Generierung — genutzt von
``report.generation`` (Dashboard-Integrität) UND ``tests/test_roundtrip.py``
(Generierungs-/Analyse-Symmetrie). ``expected`` kommt aus ``resolve_stem``
(dem Bake-Orakel), nicht aus dem FST — der FST muss es reproduzieren.
"""

from dataclasses import dataclass

from prussian.fst.oracle import resolve_stem
from prussian.fst.tags import (
    _paradigm_kind, _pos, ADV_POS_TAG, cell_tag, ptcp_cell_tag, split_reflexive,
    split_suffix, tag_prefix, verb_cell_tag,
)
from prussian.fst.morphology.verbs import _PTCP_DECL


@dataclass(frozen=True)
class Case:
    pos: str          # +N / +A / +Pron / +Num / +Adv / +V
    paradigm: str
    lemma: str
    tag: str          # vollständiger Generierungs-Tag (lemma + Tagfolge)
    expected: str     # erwartete Oberfläche (Standardform)
    variant: str | None  # Doubletten-Vollform oder None


def nominal_pos(paradigm: str) -> str:
    """POS fürs Dashboard — Adverbien (deadjektivisch) als eigene Klasse."""
    return ADV_POS_TAG if _paradigm_kind(paradigm) == "adv" else _pos(paradigm)


def nominal_cases(entries: list[dict]):
    for e in entries:
        pos = nominal_pos(e["paradigm"])
        prefix = tag_prefix(e["paradigm"], e["gender"])
        for cell, v in e["suffixe"].items():
            std, variant = split_suffix(v["suffix"])
            expected = resolve_stem(
                e["stamm"], v["betont"], v.get("palatize", False)) + std
            yield Case(pos, e["paradigm"], e["lemma"],
                       f"{e['lemma']}{prefix}{cell_tag(cell)}", expected, variant)


def verbal_cases(entries: list[dict]):
    for e in entries:
        is_ptcp = bool(e.get("gender")) and e["tense"] in _PTCP_DECL
        for cell, v in e["suffixe"].items():
            if is_ptcp:
                tcell = ptcp_cell_tag(e["tense"], e["gender"], cell)
                std, variant = split_suffix(v["suffix"])
            else:
                bare, refl = split_reflexive(v["suffix"])
                tcell = verb_cell_tag(e["tense"], cell, refl)
                std, variant = split_suffix(bare)
            expected = resolve_stem(
                e["stamm"], v["betont"], v.get("palatize", False)) + std
            yield Case("+V", e["paradigm"], e["lemma"],
                       f"{e['lemma']}+V{tcell}", expected, variant)
