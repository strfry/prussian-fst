"""Tests für den Pfeil-Verweis-Resolver (linker.py).

parse_arrows, Stichwort-Matching und Kaskadenlogik laufen ohne FST
(monkeypatched lookup); der Smoke-Test braucht die gebauten .hfstol-Artefakte.
"""

from pathlib import Path

import pytest

from prussian_fst import linker
from prussian_fst.linker import (
    Headwords,
    parse_arrows,
    resolve_corpus,
    resolve_form,
    resolve_target,
)

REPO = Path(__file__).resolve().parents[1]


# ── parse_arrows ──

def test_parse_arrows_single():
    assert parse_arrows("↑ Wīrs acc sg m [Wīrans 93(12)]") == ["Wīrs acc sg m"]


def test_parse_arrows_two_targets():
    assert parse_arrows("↑ Klantītun, ↑ Klantītwei ps 1 sg m [klantemmai 29]") == [
        "Klantītun", "Klantītwei ps 1 sg m"]


def test_parse_arrows_brackets_ignored():
    # Belegschreibungen in [...] sind keine Verweise.
    assert parse_arrows("n [bērzi 63 MK]") == []
    assert parse_arrows("") == []


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
    patched({"base": {"deinan": [("dēinā", ["N", "Sg", "Acc"])]}})
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
    patched({"macron": {"deinan": [("dēinā", ["N", "Sg", "Acc"])]}})
    res = resolve_form("deinan", FSTS)
    assert res["method"] == "macron"


def test_cascade_cluster(patched):
    # Mehrere Lemmata sind kein Fehler, sondern ein resolved-Cluster.
    patched({"base": {"labban": [("labban", ["N", "Sg", "Acc"]),
                                 ("labs", ["Aj", "Sg", "Acc"])]}})
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


# ── Stichwort-Auflösung ──

def _heads():
    return Headwords([
        {"id": "wīrs", "word": "wīrs"},
        {"id": "grēkitwei", "word": "grēkitwei"},
        {"id": "audātun si", "word": "audātun si"},
        {"id": "madlītun", "word": "madlītun"},
        {"id": "bilītun-1", "word": "bilītun"},
        {"id": "bilītun-2", "word": "bilītun"},
    ])


def test_target_headword_case_insensitive(patched):
    patched({})
    res = resolve_target("Wīrs acc sg m", _heads(), FSTS)
    assert (res["target_ids"], res["ref"], res["method"]) == (
        ["wīrs"], "Wīrs", "headword")


def test_target_multiword_headword(patched):
    patched({})
    res = resolve_target("Audātun si ps 3", _heads(), FSTS)
    assert res["target_ids"] == ["audātun si"]


def test_target_macron_tolerant(patched):
    patched({})
    res = resolve_target("Madlitun ps 1 sg", _heads(), FSTS)
    assert (res["target_ids"], res["method"]) == (["madlītun"], "macron")


def test_target_homographs_all_ids(patched):
    patched({})
    assert resolve_target("Bilītun ps 3", _heads(), FSTS)["target_ids"] == [
        "bilītun-1", "bilītun-2"]


def test_target_fst_fallback(patched):
    # Kein Stichwort: Analyzer-Kaskade, Lemma muss Stichwort sein.
    patched({"base": {"pirmas": [("wīrs", ["N", "Sg", "Nom"])]}})
    res = resolve_target("Pirmas m pnl", _heads(), FSTS)
    assert (res["target_ids"], res["method"]) == (["wīrs"], "case")


def test_target_gap(patched):
    patched({})
    assert resolve_target("Sīran acc sg", _heads(), FSTS)["status"] == "gap"


# ── resolve_corpus ──

def test_resolve_corpus_links_and_form_tags(patched):
    patched({"base": {"wīrans": [("wīrs", ["N", "Msc", "Sg", "Acc"]),
                                 ("wīrins", ["N", "Msc", "Pl", "Acc"])]}})
    entries = [
        {"id": "wīrs", "word": "wīrs", "desc": "n m"},
        {"id": "wīrans", "word": "wīrans", "desc": "↑ Wīrs acc sg m [Wīrans 93]"},
        {"id": "sīru", "word": "sīru", "desc": "↑ Sīran dat sg [siru 115]"},
    ]
    links, unresolved = resolve_corpus(entries, FSTS)
    assert [(l["orig_id"], l["lemmas"], l["target_ids"], l["tags"])
            for l in links] == [("wīrans", ["wīrs"], ["wīrs"], ["N+Msc+Sg+Acc"])]
    assert [(u["orig_id"], u["ref"], u["status"]) for u in unresolved] == [
        ("sīru", "Sīran", "gap")]


def test_resolve_corpus_homographs_filtered_by_pos(patched):
    patched({"base": {"bētas": [("bētan", ["N", "Neu", "Sg", "Gen"])]}})
    entries = [
        {"id": "bētan-1", "word": "bētan", "pos": "noun", "desc": ""},
        {"id": "bētan-2", "word": "bētan", "pos": "adv", "desc": ""},
        {"id": "bilītun-1", "word": "bilītun", "pos": "verb", "desc": ""},
        {"id": "bilītun-2", "word": "bilītun", "pos": "verb", "desc": ""},
        {"id": "bētas", "word": "bētas", "desc": "↑ Bētan gen [bētas 1]"},
        # Ohne FST-Tags kein Filter: alle Homographen bleiben.
        {"id": "bilāi", "word": "bilāi", "desc": "↑ Bilītun"},
    ]
    links, _ = resolve_corpus(entries, FSTS)
    assert [(l["orig_id"], l["target_ids"]) for l in links] == [
        ("bētas", ["bētan-1"]), ("bilāi", ["bilītun-1", "bilītun-2"])]


def test_resolve_corpus_homographs_keep_entry_id(patched):
    # Homographen teilen das Wort, nicht die Eintrags-ID: jeder Link trägt
    # die orig_id seines NVH-Eintrags.
    patched({})
    entries = [
        {"id": "wīrs", "word": "wīrs", "desc": ""},
        {"id": "be-1", "word": "be", "desc": "↑ Wīrs"},
        {"id": "be-2", "word": "be", "desc": "↑ Wīrs acc"},
    ]
    links, _ = resolve_corpus(entries, FSTS)
    assert [(l["orig_lemma"], l["orig_id"]) for l in links] == [
        ("be", "be-1"), ("be", "be-2")]


# ── Smoke-Test gegen gebaute Artefakte ──

from prussian_fst.cg3_pipeline import DEFAULT_FST as BASE  # noqa: E402


@pytest.mark.skipif(not BASE.exists(), reason="make all zuerst")
def test_resolve_smoke():
    fsts = {"base": BASE, "macron": REPO / "build/macron.hfstol",
            "lenient": REPO / "build/lenient.hfstol"}
    res = resolve_form("niainunts", fsts)
    assert res["status"] == "resolved"
    assert res["lemmas"] == ["niaīnunts"]
    assert res["method"] == "macron"
