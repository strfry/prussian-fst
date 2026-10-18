"""Tests für den Eintrags-Leser der lean NVH (prussian_fst.nvh)."""

from pathlib import Path

import pytest

from prussian_fst.nvh import DEFAULT_LEAN_NVH, plain_desc, read_entries

SAMPLE = """\
entry: be
  id: be-1
  homograph: 1
  pos: prep
  sense:
    en: without
    de: ohne
  legacy:
    desc: prp acc [bhe 49(17)]
entry: be
  id: be-2
  homograph: 2
  pos: cconj
  sense:
    en: and
    de: und
  legacy:
    desc: [bhe 17(13)]
entry: galbimai
  id: galbimai
  label: variantSkeleton
  relation: variantOf
    member: galbimai role: variant
    member: galbtwei role: lemma
  inflectedForm: galbimai
    tag: sg.nom
  legacy:
    desc: ↑ <a href="#galbtwei">Galbtwei</a> ps 1 sg m [galbimai 31]
entry: ast
  id: ast
  sense:
    en: is
    en: (as if) is
"""


@pytest.fixture
def entries(tmp_path: Path) -> list[dict]:
    path = tmp_path / "sample.nvh"
    path.write_text(SAMPLE, encoding="utf-8")
    return read_entries(path)


def test_homographs_are_separate_entries(entries):
    be1, be2 = entries[0], entries[1]
    assert (be1["id"], be1["homograph"], be1["pos"]) == ("be-1", 1, "prep")
    assert (be2["id"], be2["homograph"], be2["pos"]) == ("be-2", 2, "cconj")
    assert be1["translations"] == {"en": ["without"], "de": ["ohne"]}
    assert be2["translations"] == {"en": ["and"], "de": ["und"]}


def test_desc_is_plain_text(entries):
    assert entries[0]["desc"] == "prp acc [bhe 49(17)]"
    assert entries[2]["desc"] == "↑ Galbtwei ps 1 sg m [galbimai 31]"


def test_forms_and_relations_ignored(entries):
    galbimai = entries[2]
    assert galbimai["label"] == "variantSkeleton"
    assert galbimai["translations"] == {}
    assert "forms" not in galbimai


def test_repeated_language_lines_collected(entries):
    assert entries[3]["translations"] == {"en": ["is", "(as if) is"]}


def test_plain_desc_decodes_and_unescapes():
    assert plain_desc(r"a\nb &amp; <i>c</i>") == "a b & c"


@pytest.mark.skipif(not DEFAULT_LEAN_NVH.exists(), reason="corpus-Checkout fehlt")
def test_lean_nvh_ids_unique():
    ids = [e["id"] for e in read_entries()]
    assert len(ids) == len(set(ids))
