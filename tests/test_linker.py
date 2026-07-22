"""Tests für den desc-Ref-Resolver (linker.py).

parse_desc und Kaskadenlogik laufen ohne FST (monkeypatched lookup);
der Smoke-Test braucht die gebauten .hfstol-Artefakte.
"""

from pathlib import Path

import pytest

from prussian_fst import linker
from prussian_fst.linker import (
    BracketItem,
    parse_desc,
    resolve_corpus,
    resolve_form,
)

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


def test_parse_desc_language_prefix_dropped():
    # Sprachkürzel ("lat.") verwerfen, echten Beleg behalten.
    assert parse_desc("[lat. portus MK]") == [BracketItem("portus")]
    assert parse_desc("[lit. viešėti]") == [BracketItem("viešėti")]
    # Bleibt nichts übrig, entsteht auch kein Eintrag.
    assert parse_desc("[gr. MK]") == []


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
    assert res["lemmas"] == ["dēinā"]
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


def test_cascade_cluster(patched):
    # Mehrere Lemmata sind kein Fehler, sondern ein resolved-Cluster.
    patched({"base": {"labban": [("labban", ["N", "Sg", "Akk"]),
                                 ("labs", ["Aj", "Sg", "Akk"])]}})
    res = resolve_form("labban", FSTS)
    assert res["status"] == "resolved"
    assert res["lemmas"] == ["labban", "labs"]
    assert res["method"] == "exact"


def test_cascade_gap(patched):
    patched({})
    assert resolve_form("vieseti", FSTS)["status"] == "gap"


def test_alphabet_guard_skips_lookup(patched):
    # ļ/ķ liegen außerhalb des FST-Alphabets: gar kein Lookup, direkt gap,
    # auch wenn ein Präfix-Müll-Match in der Tabelle stünde.
    patched({"base": {"kaļķis": [("ka", ["N"]), ("kas", ["Pron"])]}})
    res = resolve_form("kaļķis", FSTS)
    assert res["status"] == "gap"
    assert "lemmas" not in res


def test_alphabet_guard_allows_macron_and_space(patched):
    patched({"base": {"dāst dais": [("dātun", ["V"])]}})
    res = resolve_form("dāst dais", FSTS)
    assert res["status"] == "resolved"


# ── resolve_corpus ──

def test_resolve_corpus_cluster_and_skips(patched):
    patched({"base": {"labban": [("labban", ["N"]), ("labs", ["Aj"])]}})
    entries = [
        {"word": "labs", "desc": "[labban MK]"},   # Cluster-Treffer
        {"word": "Werk", "desc": "[Advent MK]"},   # Großschreibung → skip
        {"word": "x", "desc": "[kaļķis MK]"},      # Nicht-FST-Zeichen → gap
    ]
    links, unresolved = resolve_corpus(entries, FSTS)
    assert len(links) == 1
    assert links[0]["ref"] == "labban"
    assert links[0]["lemmas"] == ["labban", "labs"]
    assert "lemma" not in links[0]
    # Advent wird übersprungen (kein Link, kein unresolved-Eintrag);
    # kaļķis bleibt als gap offen.
    assert [u["ref"] for u in unresolved] == ["kaļķis"]
    assert unresolved[0]["status"] == "gap"


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
