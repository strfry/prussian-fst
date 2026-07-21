"""Tests für den desc-Ref-Resolver (linker.py).

parse_desc und Kaskadenlogik laufen ohne FST (monkeypatched lookup);
der Smoke-Test braucht die gebauten .hfstol-Artefakte.
"""

from pathlib import Path

import pytest

from prussian_fst import linker
from prussian_fst.linker import BracketItem, parse_desc, resolve_form

REPO = Path(__file__).resolve().parents[1]


# ── parse_desc ──

def test_parse_desc_simple():
    assert parse_desc("[Advent MK]") == [BracketItem("Advent")]


def test_parse_desc_source_number():
    assert parse_desc("[pawargan 63 MK]") == [BracketItem("pawargan", "63")]


def test_parse_desc_commas_and_markers():
    items = parse_desc("[ankant, ankants, ankanst DIA Riemann MK]")
    assert [i.form for i in items] == ["ankant", "ankants", "ankanst"]


def test_parse_desc_parens_stripped():
    assert parse_desc("[(grīki)si drv]") == [BracketItem("grīkisi")]


def test_parse_desc_outside_brackets_ignored():
    items = parse_desc("(ēn, prēi acc) [Grēnztun drv]")
    assert items == [BracketItem("Grēnztun")]


def test_parse_desc_multiword():
    assert parse_desc("[das Zitat MK]") == [BracketItem("das Zitat")]


def test_parse_desc_empty():
    assert parse_desc("") == []
    assert parse_desc("[MK]") == []


# ── Kaskade (synthetische Lookups) ──

FSTS = {"base": Path("base"), "macron": Path("macron"), "lenient": Path("lenient")}


def fake_lookup(table):
    """table: fst-name → {form: [(lemma, tags)]}"""
    def _lookup(forms, fst_path):
        data = table.get(str(fst_path), {})
        return {f: data[f] for f in forms if f in data}
    return _lookup


@pytest.fixture
def patched(monkeypatch):
    def patch(table):
        monkeypatch.setattr(linker, "flookup_batch", fake_lookup(table))
        monkeypatch.setattr(Path, "exists", lambda self: True)
    return patch


def test_cascade_exact(patched):
    patched({"base": {"deinan": [("dēinā", ["N", "Sg", "Akk"])]}})
    res = resolve_form("deinan", FSTS)
    assert res["status"] == "resolved"
    assert res["lemma"] == "dēinā"
    assert res["method"] == "exact"


def test_cascade_case(patched):
    patched({"base": {"adwēnts": [("Adwēnts", ["N", "Sg", "Nom"])]}})
    res = resolve_form("ADWĒNTS", FSTS)
    assert res["status"] == "resolved"
    assert res["method"] == "case"


def test_cascade_macron(patched):
    patched({"macron": {"deinan": [("dēinā", ["N", "Sg", "Akk"])]}})
    res = resolve_form("deinan", FSTS)
    assert res["method"] == "macron"


def test_cascade_ambiguous(patched):
    patched({"base": {"x": [("a", ["N"]), ("b", ["V"])]}})
    res = resolve_form("x", FSTS)
    assert res["status"] == "ambiguous"
    assert res["candidates"] == ["a", "b"]


def test_cascade_gap(patched):
    patched({})
    assert resolve_form("viešėti", FSTS)["status"] == "gap"


# ── Smoke-Test gegen gebaute Artefakte ──

BASE = REPO / "build/base.hfstol"


@pytest.mark.skipif(not BASE.exists(), reason="make all zuerst")
def test_resolve_smoke():
    fsts = {"base": BASE, "macron": REPO / "build/macron.hfstol",
            "lenient": REPO / "build/lenient.hfstol"}
    res = resolve_form("niainunts", fsts)
    assert res["status"] == "resolved"
    assert res["lemma"] == "niaīnunts"
    assert res["method"] == "macron"
