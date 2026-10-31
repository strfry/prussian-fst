"""Tests for the compressor: fat NVH -> lean NVH, exact and lossless.

The fixtures are Twanksta cells (from ``twanksta.nvh``), not generator output. The
corpus test at the end runs on a sample of the real fat NVH and is skipped when the
file is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "gen"))

import compress_forms as cf  # noqa: E402
import generator as gen  # noqa: E402

FAT_SNIPPET = """\
entry: Adwēnts
  id: Adwēnts|56|[Advent MK]
  pos: noun
  gender: masc
  paradigm: 56
  label: MK
  sense:
    en: Advent
  inflectedForm: Adwēnts
    tag: sg.nom
  inflectedForm: Adwēntis
    tag: sg.gen
  inflectedForm: Adwēntjai
    tag: pl.nom
  legacy:
    desc: [Advent MK]
"""


def nvh_text(pos: str, paradigm: str, lemma: str, attested: dict[str, tuple[str, ...]]) -> str:
    lines = [f"entry: {lemma}", f"  id: {lemma}", f"  pos: {pos}", f"  paradigm: {paradigm}"]
    for slot in sorted(attested):
        for surface in attested[slot]:
            lines += [f"  inflectedForm: {surface}", f"    tag: {slot}"]
    return "".join(line + "\n" for line in lines)


# ── Reader / writer ──────────────────────────────────────────────────────────


def test_parse_reads_the_fields():
    (entry,) = cf.parse_nvh(FAT_SNIPPET)
    assert (entry.lemma, entry.pos, entry.paradigm, entry.gender) == (
        "Adwēnts", "noun", "56", "masc")
    assert entry.attested == {"sg.nom": ("Adwēnts",), "sg.gen": ("Adwēntis",),
                              "pl.nom": ("Adwēntjai",)}
    assert entry.cells == 3


def test_parse_keeps_metadata_out_of_the_forms():
    (entry,) = cf.parse_nvh(FAT_SNIPPET)
    assert entry.head[:4] == ("  id: Adwēnts|56|[Advent MK]", "  pos: noun",
                              "  gender: masc", "  paradigm: 56")
    assert entry.tail == ("  legacy:", "    desc: [Advent MK]")


def test_parse_drops_the_retired_stem_field():
    text = FAT_SNIPPET.replace("  label: MK\n", "  label: MK\n  stemOverrides: obl=Adwēnt\n")
    (entry,) = cf.parse_nvh(text)
    assert not any("stemOverrides" in line for line in entry.head + entry.tail)


def test_parse_keeps_variants_and_normalizes_to_nfc():
    text = FAT_SNIPPET.replace(
        "  inflectedForm: Adwēnts\n    tag: sg.nom\n",
        "  inflectedForm: Adwēnts\n    tag: sg.nom\n"
        "  inflectedForm: Adwent\n    tag: sg.nom\n")
    (entry,) = cf.parse_nvh(text)
    assert entry.attested["sg.nom"] == ("Adwent", "Adwēnts")


def test_legacy_pos_spelling_carries_gender():
    text = FAT_SNIPPET.replace("  pos: noun\n  gender: masc\n", "  pos: noun-masc\n")
    (entry,) = cf.parse_nvh(text)
    assert (entry.pos, entry.gender) == ("noun", "masc")


def test_render_keeps_metadata_and_only_the_given_cells():
    (entry,) = cf.parse_nvh(FAT_SNIPPET)
    text = cf.render_entry(entry, {"pl.nom": ("Adwēntjai",)})
    assert "  inflectedForm: Adwēntjai\n    tag: pl.nom\n" in text
    assert "tag: sg.nom" not in text
    assert "sense:" in text and "desc: [Advent MK]" in text
    (again,) = cf.parse_nvh(cf.render_entry(entry, {}))
    assert (again.head, again.tail) == (entry.head + entry.tail, ())


# ── Dumper artifacts ─────────────────────────────────────────────────────────


def test_repair_dumper_artifacts():
    text = (nvh_text("noun", "52", "federācija", {"sg.nom": ("federācija52", "federācija")})
            + nvh_text("adj", "27", "izpilninamins",
                       {"adv.superl": ("ukaizpilninamins27",),
                        "comp.msc.sg.nom": ("izpilninamins27is",)}))
    clean, review = cf.repair_dumper_artifacts(cf.parse_nvh(text))
    assert clean[0].attested["sg.nom"] == ("federācija",)
    assert clean[1].attested == {"adv.superl": ("ukaizpilninamins",),
                                 "comp.msc.sg.nom": ("izpilninaminsis",)}
    assert len(review) == 3


def test_repair_surface_strips_lettered_paradigm():
    assert cf.repair_surface("Kirsnagārbija35a", "35a") == "Kirsnagārbija"
    assert cf.repair_surface("perleītun106d", "106d") == "perleītun"
    assert cf.repair_surface("izpilninamins27is", "27") == "izpilninaminsis"


# ── Derivation ───────────────────────────────────────────────────────────────

ZEME = {"sg.nom": ("zemē",), "sg.gen": ("zemmis",), "sg.dat": ("zemmei",),
        "sg.acc": ("zemmin",), "pl.nom": ("zemmis",), "pl.gen": ("zemmin",),
        "pl.dat": ("zemīmans",), "pl.acc": ("zemmins",)}


def _entry(pos, paradigm, lemma, attested):
    (entry,) = cf.parse_nvh(nvh_text(pos, paradigm, lemma, attested))
    return entry


def test_regular_entry_keeps_no_cell():
    d = cf.derive_entry(_entry("noun", "53", "zemē", ZEME))
    assert d.overrides == {} and d.principal == ()


def test_wrong_principal_form_is_kept_and_feeds_its_dependents():
    """kalbītwei with a preterite stem kalbēj-: only prt.sp3 is stored."""
    att = {"prt.sp3": ("kalbēja",), "prt.pl1": ("kalbējamai",), "prt.pl2": ("kalbējatei",),
           "prs.sp3": ("kalba",)}
    d = cf.derive_entry(_entry("verb", "136", "kalbītwei", att))
    assert d.principal == ("prt.sp3",)
    assert d.overrides == {"prt.sp3": ("kalbēja",)}
    assert not cf.verify([(_entry("verb", "136", "kalbītwei", att), d)])


def test_override_replaces_a_wrong_rule_form():
    att = dict(ZEME, **{"pl.nom": ("zemmes",)})
    entry = _entry("noun", "53", "zemē", att)
    d = cf.derive_entry(entry)
    assert d.overrides == {"pl.nom": ("zemmes",)}
    assert d.expanded["pl.nom"] == frozenset({"zemmes"})      # zemmis is gone


def test_variant_slot_is_stored_whole():
    att = dict(ZEME, **{"pl.nom": ("zemmes", "zemmis")})
    d = cf.derive_entry(_entry("noun", "53", "zemē", att))
    assert d.overrides == {"pl.nom": ("zemmes", "zemmis")}


def test_unknown_paradigm_keeps_every_cell():
    d = cf.derive_entry(_entry("noun", "999", "zemē", ZEME))
    assert d.status == "unknown-paradigm" and d.overrides == ZEME


def test_lean_entry_expands_to_the_fat_cells():
    att = dict(ZEME, **{"pl.nom": ("zemmes",), "sg.gen": ("zemis",)})
    fat = _entry("noun", "53", "zemē", att)
    d = cf.derive_entry(fat)
    (lean,) = cf.parse_nvh(cf.render_entry(fat, d.overrides))
    assert not cf.inexact(fat.attested, cf.expand(lean))
    # Recompressing the lean entry keeps the same cells (fixpoint).
    assert cf.derive_entry(lean).overrides == d.overrides


# ── Corpus sample ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def corpus_sample():
    if not cf.FULL_NVH.exists():
        pytest.skip(f"{cf.FULL_NVH} missing")
    entries, _ = cf.repair_dumper_artifacts(cf.read_nvh(cf.FULL_NVH))
    by_pos: dict[str, list] = {}
    for e in entries:
        if e.pos in ("noun", "adj", "verb") and e.paradigm and e.attested:
            by_pos.setdefault(e.pos, []).append(e)
    return [e for pos in by_pos.values() for e in pos[::40]]


def test_corpus_sample_is_exact_and_roundtrips(corpus_sample):
    pairs = list(cf.compress(corpus_sample))
    assert not cf.verify(pairs)
    lean = cf.parse_nvh("".join(cf.render_entry(e, d.overrides) for e, d in pairs))
    assert len(lean) == len(pairs)
    for (fat, _), entry in zip(pairs, lean):
        assert not cf.inexact(fat.attested, cf.expand(entry)), fat.lemma


def test_corpus_sample_mostly_needs_no_cell(corpus_sample):
    pairs = list(cf.compress(corpus_sample))
    stored = sum(sum(len(v) for v in d.overrides.values()) for _, d in pairs)
    total = sum(e.cells for e, _ in pairs)
    assert stored < 0.06 * total, (stored, total)
