"""Tests für die gold-freie Paradigmen-Ableitung (prussian.gold.derive).

Braucht data/external/prusaspira_entries.json; überspringt sonst.
"""

import json

import pytest

from prussian.gold.derive import (
    PR_PATH, char_fold, declension_cells, derive_suffix_tables,
    derive_twanksta_j_pairs, stem_boundary,
)

ROOT = PR_PATH.parent.parent.parent
TW_PATH = PR_PATH.parent / "twanksta_entries.json"


def test_char_fold_macron_palatal():
    assert char_fold("kūģu") == "kugu"          # Makron + Palatal
    assert char_fold("ābalniš") == "abalnis"    # Makron + Caron


def test_stem_boundary_palatal_insensitive():
    # kūgis-Typ: Dat sg palatalisiert (kūģu) — Stamm bleibt kūg (3)
    assert stem_boundary(["kūgis", "kūģu", "kūgin"]) == 3


@pytest.fixture(scope="module")
def tables():
    if not PR_PATH.exists():
        pytest.skip("prusaspira_entries.json fehlt — s. README data/external")
    pr = json.loads(PR_PATH.read_text(encoding="utf-8"))
    return derive_suffix_tables(pr)


# Saubere (regelmäßige) Paradigmen müssen exakt die bekannten Standardendungen
# liefern — Evidenz, dass die Ableitung die Gold-Tabelle reproduziert.
EXPECTED = {
    "32": {"Nom sg": "s", "Gen sg": "as", "Dat sg": "u", "Akk sg": "an",
           "Nom pl": "ai", "Gen pl": "an", "Dat pl": "amans", "Akk pl": "ans"},
    "52": {"Nom sg": "i", "Gen sg": "is", "Dat sg": "ei", "Akk sg": "in",
           "Nom pl": "is", "Gen pl": "in", "Dat pl": "imans", "Akk pl": "ins"},
    "35": {"Nom sg": "an", "Gen sg": "as", "Dat sg": "u", "Akk sg": "an",
           "Nom pl": "āi", "Gen pl": "an", "Dat pl": "ammans", "Akk pl": "ans"},
}


@pytest.mark.parametrize("par,exp", EXPECTED.items())
def test_derived_table_matches_standard(tables, par, exp):
    got = tables.get(par, {})
    for cell, suffix in exp.items():
        assert got.get(cell) == suffix, (
            f"P{par} {cell}: abgeleitet {got.get(cell)!r} ≠ Standard {suffix!r}")


def test_twanksta_j_pairs_derived():
    """Die weichvokalischen Twanksta-j-Endungen (-jas~-es …) werden aus dem
    Wörterbuchvergleich abgeleitet (datengetrieben, kein Regel-Listing)."""
    if not (PR_PATH.exists() and TW_PATH.exists()):
        pytest.skip("externe Dicts fehlen — s. README data/external")
    pr = json.loads(PR_PATH.read_text(encoding="utf-8"))
    tw = json.loads(TW_PATH.read_text(encoding="utf-8"))
    pairs = derive_twanksta_j_pairs(pr, tw)
    assert "jas" in pairs and "es" in pairs["jas"]   # Gen sg -jas~-es
    assert "jan" in pairs and "in" in pairs["jan"]   # Akk sg -jan~-in
    assert all("j" in tw_ for tw_ in pairs)          # nur echte j-Varianten
