"""Tests für den Kompressor (§3): fette NVH → lean NVH, verlustfrei.

Die erwarteten Oberflächen sind **attestierte twanksta-Zellen** (aus
``twanksta_dmlex.full.nvh``), nicht Generator-Ausgaben — sonst wäre der
Verlustfreiheits-Test zirkulär. Pro POS ein reguläres, ein stamm-pflichtiges und
ein override-pflichtiges Lexem:

    noun  Adwēnts P56   Stufe 0 deckt alles
    noun  Patals  P32   obliquer Stamm mit -ll-: gelieferter Stamm obl=Patall
    noun  aūgmens P61   Pl.Nom. -jai statt -es: Override (zwei Varianten am Slot)
    adj   amērikanisks P25  Stufe 0 deckt das ganze Raster
    adj   auktums P25   obliquer Stamm mit -mm-: Stamm pos=auktumm + ein Override
    adj   wilnis  P27   jo-Stamm im Paradigma 27: 3 Overrides
    verb  mitātun  P132 finite Tafel und Partizipien vollständig aus dem Lemma
    verb  rusītwei P134 Präsens-Makron ē: gelieferter Stamm pres=rusē
    verb  kalbītwei P136 Prät.-Stamm pret=kalbē, Partizippräsens partpres=kalbant,
                        ein Override für den Optativ (DEVIATIONS B)

Die Tests laufen ohne Korpusdatei; die beiden corpus_tests am Ende prüfen dieselben
Eigenschaften an einer Stichprobe der echten fette NVH und überspringen sie, wenn
die Datei fehlt. Atome baut der Test bei Bedarf selbst (``make atoms`` baut alle).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "gen"))

import compress_forms as cf  # noqa: E402
import generator as gen  # noqa: E402

# ── Atome ───────────────────────────────────────────────────────────────────

NOUN_ROLES = ("obl",)
ADJ_ROLES = ("pos", "adv", "cmp", "sup")
VERB_ROLES = ("pres", "nonfin", "partPresAct", "partPerfAct", "partPerfPass")
WANTED = (
    [("noun", paradigm, role, "") for paradigm in ("32", "56", "61") for role in NOUN_ROLES]
    + [("adj", paradigm, role, "") for paradigm in ("25", "27") for role in ADJ_ROLES]
    + [("verb", paradigm, role, "") for paradigm in ("132", "134") for role in VERB_ROLES]
    + [("verb", "136", role, "") for role in VERB_ROLES]
    + [("verb", "136", "pret", "")]
    + [("verb", "87", role, "kandautwei") for role in VERB_ROLES]
)


@pytest.fixture(scope="session")
def atoms():
    """Fehlende Atome bauen (Session-Fixture: je Atom ein Subprozess)."""
    pytest.importorskip("hfst", reason="hfst-Paket fehlt (make atoms braucht es)")
    if not (REPO / "build/gen-accent.hfst").exists():
        pytest.skip("build/gen-accent.hfst fehlt — make gen-accent.hfst")
    for pos, paradigm, role, lemma in WANTED:
        if gen.atom_path(pos, paradigm, role, lemma).exists():
            continue
        done = subprocess.run(
            [sys.executable, str(REPO / "gen/atom_fst.py"), pos, paradigm, role]
            + (["--lemma", lemma] if lemma else []),
            capture_output=True, text=True, cwd=REPO)
        if done.returncode:
            pytest.fail(f"Atom {pos}/{paradigm}/{role} nicht baubar:\n"
                        f"{(done.stderr or done.stdout)[-2000:]}")


# ── NVH-Leser ───────────────────────────────────────────────────────────────

# Wörtlich aus ../corpus/parsed/twanksta_dmlex.full.nvh (Auszug, ein Eintrag).
FAT_SNIPPET = """entry: Adwēnts
  id: Adwēnts|56|[Advent MK]
  pos: noun
  gender: masc
  paradigm: 56
  label: MK
  sense:
    en: Advent
    de: Advent
    lt: adventas
    lv: Advents
    pl: adwent
    ru: адвент
  inflectedForm: Adwēnts
    tag: sg.nom
  inflectedForm: Adwēntis
    tag: sg.gen
  inflectedForm: Adwēntjai
    tag: pl.nom
  legacy:
    desc: [Advent MK]
"""


def test_parse_reads_the_four_fields():
    (entry,) = cf.parse_nvh(FAT_SNIPPET)
    assert (entry.lemma, entry.pos, entry.paradigm, entry.gender) == (
        "Adwēnts", "noun", "56", "masc")
    assert entry.attested == {"sg.nom": ("Adwēnts",), "sg.gen": ("Adwēntis",),
                              "pl.nom": ("Adwēntjai",)}
    assert entry.cells == 3


def test_parse_keeps_metadata_out_of_the_forms():
    """``id``/``label``/``sense``/``legacy`` wandern unverändert nach head/tail."""
    (entry,) = cf.parse_nvh(FAT_SNIPPET)
    assert entry.head[:4] == ("  id: Adwēnts|56|[Advent MK]", "  pos: noun",
                              "  gender: masc", "  paradigm: 56")
    assert "  sense:" in entry.head and "    en: Advent" in entry.head
    assert entry.tail == ("  legacy:", "    desc: [Advent MK]")
    assert not any("inflectedForm" in line or "tag:" in line
                   for line in entry.head + entry.tail)


def test_render_preserves_metadata_and_drops_stufe0_forms():
    entry, = cf.parse_nvh(FAT_SNIPPET)
    text = cf.render_entry(entry, {}, {})
    without_forms = "".join(line + "\n" for line in FAT_SNIPPET.splitlines()
                            if "inflectedForm" not in line and "tag:" not in line)
    assert text == without_forms          # Stufe 0 deckt alles: keine Formzeile
    assert "sense:" in text and "desc: [Advent MK]" in text
    (again,) = cf.parse_nvh(text)
    # Ohne Formzeilen wandert der ganze Rest nach ``head`` — die Reihenfolge
    # (``id``/``pos``/``gender``/``paradigm``/``label``/``sense``/``legacy``)
    # bleibt byte-gleich.
    assert (again.head, again.tail) == (entry.head + entry.tail, ())


def test_render_emits_stems_and_overrides_at_their_tag():
    entry, = cf.parse_nvh(FAT_SNIPPET)
    text = cf.render_entry(entry, {"obl": "Adwēnt"}, {"pl.nom": ("Adwēntjai",)})
    assert "  stemOverrides: obl=Adwēnt\n" in text
    assert "  inflectedForm: Adwēntjai\n    tag: pl.nom\n" in text
    assert "tag: sg.nom" not in text               # Stufe 0, nicht gespeichert
    assert "sense:" in text and "desc: [Advent MK]" in text


def test_render_writes_one_stem_overrides_line_and_roundtrips():
    """Rolle=Stamm auf einer Zeile, Parser und Schreiber sind invers zueinander."""
    entry, = cf.parse_nvh(FAT_SNIPPET)
    stems = {"obl": "Adwēnt", "nonfin": "Adwēnt"}
    text = cf.render_entry(entry, stems, {})
    assert text.count(f"  {cf.STEM_OVERRIDES}: ") == 1
    (again,) = cf.parse_nvh(text)
    assert again.stems == stems


def test_parse_accepts_several_stem_overrides_lines():
    text = FAT_SNIPPET.replace(
        "  legacy:",
        f"  {cf.STEM_OVERRIDES}: obl=Adwēnt\n"
        f"  {cf.STEM_OVERRIDES}: nonfin=Adwēnt\n"
        "  legacy:")
    (entry,) = cf.parse_nvh(text)
    assert entry.stems == {"obl": "Adwēnt", "nonfin": "Adwēnt"}


def test_parse_keeps_variants_of_one_slot_as_a_set():
    text = FAT_SNIPPET.replace(
        "  inflectedForm: Adwēnts\n    tag: sg.nom\n",
        "  inflectedForm: Adwēnts\n    tag: sg.nom\n"
        "  inflectedForm: Adwent\n    tag: sg.nom\n")
    (entry,) = cf.parse_nvh(text)
    assert entry.attested["sg.nom"] == ("Adwent", "Adwēnts")   # NFC + sortiert


def test_parse_normalizes_combining_marks():
    """NFD-Eingabe wird NFC — der Kopierer des Generators kennt keine Marks."""
    nfd = "Adwe\u0304nts"
    text = FAT_SNIPPET.replace("Adwēts\n    tag: sg.nom", nfd + "\n    tag: sg.nom")
    (entry,) = cf.parse_nvh(text)
    assert entry.attested["sg.nom"] == ("Adwēnts",)   # NFD → NFC
    assert "\u0304" not in entry.attested["sg.nom"][0]


def test_legacy_pos_spelling_carries_gender():
    text = FAT_SNIPPET.replace("  pos: noun\n  gender: masc\n", "  pos: noun-masc\n")
    (entry,) = cf.parse_nvh(text)
    assert (entry.pos, entry.gender) == ("noun", "masc")


def nvh_text(pos: str, paradigm: str, lemma: str, gender: str,
             attested: dict[str, tuple[str, ...]]) -> str:
    """Fette-NVH-Text für einen Wortlisteneintrag (wie ``twanksta_dmlex.full.nvh``)."""
    lines = [f"entry: {lemma}", f"  id: {lemma}|{paradigm}|[test]"]
    lines += [f"  pos: {pos}"] if pos else []
    lines += [f"  gender: {gender}"] if gender else []
    lines += [f"  paradigm: {paradigm}"] if paradigm else []
    for slot in sorted(attested):
        for surface in attested[slot]:
            lines += [f"  inflectedForm: {surface}", f"    tag: {slot}"]
    return "".join(line + "\n" for line in lines)


def test_parse_reads_several_entries_and_empty_blocks():
    (a, b) = cf.parse_nvh(FAT_SNIPPET + FAT_SNIPPET.replace("Adwēnts", "Adwēntis"))
    assert (a.lemma, b.lemma) == ("Adwēnts", "Adwēntis")
    empty = cf.Entry(lemma="galbimai")
    assert not empty.generable and not empty.cells


# ── Generator-Anbindung ─────────────────────────────────────────────────────

def test_roles_of_a_paradigm_are_slot_disjoint():
    """Greedy je Rolle ist nur zulässig, wenn sich Rollen nicht überlappen."""
    assert cf.ROLES_ARE_DISJOINT


@pytest.mark.parametrize("pos, paradigm, lemma, stems", [
    ("noun", "56", "Adwēnts", {}),
    ("noun", "32", "Patals", {"obl": "Patall"}),
    ("adj", "25", "auktums", {"pos": "auktumm"}),
    ("verb", "134", "rusītwei", {"pres": "rusē"}),
    ("verb", "87", "kandautwei", {}),
])
def test_regenerate_equals_the_plain_generator_call(atoms, pos, paradigm, lemma, stems):
    """Die Stamm-Filterung in ``regenerate`` ändert nichts am Ergebnis.

    ``regenerate`` mischt Stufe 0 und die gelieferten Stämme und lässt die Rollen
    weg, deren Stamm nicht in den Kopierer passt; das ist exakt der Aufruf
    ``generate(stems=usable_stems(...))``.
    """
    usable = cf.usable_stems(pos, paradigm, lemma, stems)
    assert cf.regenerate(pos, paradigm, lemma, stems) == gen.generate(
        pos, gen.resolve_paradigm(pos, paradigm, lemma), stems=usable, gender=None)


def test_supplied_stem_replaces_the_default_stem_of_its_role(atoms):
    """Stufe 1 schlägt Stufe 0 — für genau **eine** Rolle, die übrigen bleiben."""
    assert cf.usable_stems("noun", "32", "Patals", {"obl": "Patall"}) == {
        "obl": "Patall"}
    assert cf.regenerate("noun", "32", "Patals", {"obl": "Patall"})["sg.gen"] == (
        "Patallas",)


def test_unusable_stem_drops_only_that_role(atoms):
    """Mehrwort-Lemma: der Regelstamm mit Leerzeichen fällt raus, der Rest bleibt."""
    usable = cf.usable_stems("verb", "132", "guds si", {"pres": "gudse"})
    assert "nonfin" not in usable and usable["pres"] == "gudse"
    out = cf.regenerate("verb", "132", "guds si", {"pres": "gudse"})
    assert out["prs.sp3"] == ("gudsei",)
    assert cf.uncovered({"prs.sp3": ["gudsei"]}, out) == {}


def test_unknown_paradigm_yields_all_cells_as_overrides():
    stems, overrides = cf.derive_minimal("noun", "46,00", "Afrika", "fem",
                                        {"sg.nom": ("Afrika",), "pl.gen": ("Afrikas",)})
    assert stems == {}
    assert overrides == {"sg.nom": ("Afrika",), "pl.gen": ("Afrikas",)}


def test_unusable_stem_keeps_every_cell(atoms):
    """Leerzeichen im Lemma → alle Zellen bleiben als Override stehen."""
    attested = {"sg.nom": ("Atlāntis Ōkeans",), "pl.gen": ("Atlāntis Ōkeanņan",)}
    derivation = cf.derive_entry("noun", "32", "Atlāntis Ōkeans", "masc", attested)
    assert derivation.status == "kein-stamm"
    assert derivation.stems == {} and derivation.missing == {}


def test_bad_gender_is_rejected():
    with pytest.raises(ValueError, match="unbekanntes gender"):
        cf.derive_minimal("noun", "56", "Adwēnts", "männlich", {"sg.nom": ("Adwēnts",)})


# ── Dumper-Artefakte (Lemma+Paradigmennummer geklebt) ───────────────────────

DUMPER_NVH = (
    "entry: federācija\n"
    "  pos: noun\n"
    "  paradigm: 52\n"
    "  inflectedForm: federācija52\n"
    "    tag: sg.nom\n"
    "  inflectedForm: federācija\n"
    "    tag: sg.nom\n"
    "entry: izpilninamins\n"
    "  pos: adj\n"
    "  paradigm: 27\n"
    "  inflectedForm: ukaizpilninamins27\n"
    "    tag: adv.superl\n"
    "  inflectedForm: izpilninamins27is\n"
    "    tag: comp.msc.sg.nom\n"
    "  inflectedForm: wilnis\n"
    "    tag: msc.sg.nom\n"
)


def test_dumper_artifact_is_detected():
    assert cf.is_dumper_artifact("federācija", "52", "federācija52")
    assert cf.is_dumper_artifact("izpilninamins", "27", "ukaizpilninamins27")
    assert cf.is_dumper_artifact("izpilninamins", "27", "izpilninamins27is")
    assert not cf.is_dumper_artifact("federācija", "52", "federācija")
    assert not cf.is_dumper_artifact("wilnis", "27", "wilnis")


def test_drop_dumper_artifacts_removes_cells_and_reviews_them():
    entries = cf.parse_nvh(DUMPER_NVH)
    clean, review = cf.drop_dumper_artifacts(entries)
    assert clean[0].attested["sg.nom"] == ("federācija",)
    assert clean[1].attested == {"msc.sg.nom": ("wilnis",)}
    assert ("federācija", "52", "sg.nom") in review
    assert ("izpilninamins", "27", "adv.superl") in review
    assert ("izpilninamins", "27", "comp.msc.sg.nom") in review
    assert len(review) == 3


# ── Die neun Fixture-Lexeme ─────────────────────────────────────────────────

# (pos, paradigm, lemma, gender, attestierte Zellen, erwartete Stämme,
#  erwartete Overrides)
FIXTURES = [
    # Nomen — regulär: der Stufe-0-Abzug (Nom.Sg. − -s) trägt alle acht Zellen.
    ("noun", "56", "Adwēnts", "masc",
     {"sg.nom": ("Adwēnts",), "sg.gen": ("Adwēntis",), "sg.dat": ("Adwēnti",),
      "sg.acc": ("Adwēntin",), "pl.nom": ("Adwēntjai",), "pl.gen": ("Adwēntin",),
      "pl.dat": ("Adwēntimans",), "pl.acc": ("Adwēntins",)},
     {}, {}),
    # Nomen — stamm-pflichtig: obliquer Stamm mit -ll-, vom Lemma nicht ableitbar.
    ("noun", "32", "Patals", "masc",
     {"sg.nom": ("Patals",), "sg.gen": ("Patallas",), "sg.dat": ("Patallu",),
      "sg.acc": ("Patallan",), "pl.nom": ("Patallai",), "pl.gen": ("Patallan",),
      "pl.dat": ("Patallamans",), "pl.acc": ("Patallans",)},
     {"obl": "Patall"}, {}),
    # Nomen — Override-pflichtig: Pl.Nom. -jai neben -es; der Slot trägt zwei
    # Varianten, nur die -es-Form generiert der Stamm.
    ("noun", "61", "aūgmens", "masc",
     {"sg.nom": ("aūgmens",), "sg.gen": ("aūgmenes",), "sg.dat": ("aūgmeni",),
      "sg.acc": ("aūgmenin",), "pl.nom": ("aūgmenes", "aūgmenjai"), "pl.gen": ("aūgmenin",),
      "pl.dat": ("aūgmenimans",), "pl.acc": ("aūgmenins",)},
     {}, {"pl.nom": ("aūgmenjai",)}),
    # Adjektiv — regulär: Stufe 0 deckt Positiv, Komparativ, Superlativ, Adverb.
    ("adj", "25", "amērikanisks", "",
     {"msc.sg.nom": ("amērikanisks",), "msc.sg.gen": ("amērikaniskas",),
      "fem.sg.dat": ("amērikaniskai",), "fem.pl.dat": ("amērikaniskamans",),
      "neu.sg.acc": ("amērikaniskan",), "comp.msc.sg.nom": ("amērikaniskaisis",),
      "superl.fem.sg.nom": ("ukaamērikaniskaisi",), "adv": ("amērikaniskai",),
      "adv.comp": ("amērikaniskais",), "adv.superl": ("ukaamērikaniskais",)},
     {}, {}),
    # Adjektiv — Stamm + Override: obliquer Stamm -umm- (geliefert), aber Pl.Dat.
    # -ans verträgt die Geminate nicht (Override).
    ("adj", "25", "auktums", "",
     {"msc.sg.nom": ("auktums",), "msc.sg.gen": ("auktummas",),
      "msc.pl.nom": ("auktummai",), "msc.pl.dat": ("auktummans",), "adv": ("auktumai",)},
     {"pos": "auktumm"}, {"msc.pl.dat": ("auktummans",)}),
    # Adjektiv — Override-pflichtig: jo-Stamm im Paradigma 27 (die -i-Tafel des
    # Atoms liefert fem. -in-, attestiert ist -j-).
    ("adj", "27", "wilnis", "",
     {"msc.sg.nom": ("wilnis",), "fem.sg.gen": ("wilnjas",), "fem.sg.dat": ("wilnjai",),
      "fem.pl.nom": ("wilnjas",), "adv": ("wilnjai",)},
     {}, {"fem.sg.gen": ("wilnjas",), "fem.sg.dat": ("wilnjai",),
          "fem.pl.nom": ("wilnjas",)}),
    # Verb — regulär: finite Tafel **und** Partizipien aus dem Lemma.
    ("verb", "132", "mitātun", "",
     {"prs.sg1": ("mitāi",), "prs.sg2": ("mitāi",), "prs.sp3": ("mitāi",),
      "prs.pl1": ("mitāimai",), "prs.pl2": ("mitāitei",), "prt.sg1": ("mitāi",),
      "prt.sg2": ("mitāi",), "prt.sp3": ("mitāi",), "prt.pl1": ("mitāimai",),
      "prt.pl2": ("mitāitei",), "subj.sg1": ("mitālai",), "subj.sg2": ("mitālai",),
      "subj.sp3": ("mitālai",), "subj.pl1": ("mitālimai",), "subj.pl2": ("mitālitei",),
      "opt": ("mitāsei",), "imprt.sg2": ("mitāis",), "imprt.pl2": ("mitāiti",)},
     {}, {}),
    # Verb — stamm-pflichtig: Präsens ē statt ī (pres=rusē), finite Tafel danach voll.
    ("verb", "134", "rusītwei", "",
     {"prs.sg1": ("rusēi",), "prs.sg2": ("rusēi",), "prs.sp3": ("rusēi",),
      "prs.pl1": ("rusēimai",), "prs.pl2": ("rusēitei",), "prt.sg1": ("rusēi",),
      "prt.sg2": ("rusēi",), "prt.sp3": ("rusēi",), "prt.pl1": ("rusēimai",),
      "prt.pl2": ("rusēitei",), "subj.sg1": ("rusīlai",), "subj.sg2": ("rusīlai",),
      "subj.sp3": ("rusīlai",), "subj.pl1": ("rusīlimai",), "subj.pl2": ("rusīlitei",),
      "opt": ("rusīsei",), "imprt.sg2": ("rusēis",), "imprt.pl2": ("rusēiti",)},
     {"pres": "rusē"}, {}),
    # Verb — Stamm + Override: Präteritum-Ablaut (pret=kalbē) und der u→n-Wechsel
    # im Partizippräsens (partpres=kalbant). Die -wuns-/-ts-Partizipien liefert die
    # Regel selbst (kalbīw/kalbīt); übrig bleibt nur der Optativ mit kurzem i
    # (DEVIATIONS B).
    ("verb", "136", "kalbītwei", "",
     {"prs.sg1": ("kalba",), "prs.sp3": ("kalba",), "prt.sg1": ("kalbēi",),
      "prt.sp3": ("kalbēi",), "subj.sg1": ("kalbīlai",), "subj.sp3": ("kalbīlai",),
      "opt": ("kalbisei",), "imprt.sg2": ("kalbais",), "imprt.pl2": ("kalbaiti",),
      "part.prs.act.msc.sg.nom": ("kalbants",), "part.prf.act.msc.sg.nom": ("kalbīwuns",),
      "part.prf.pss.msc.sg.nom": ("kalbīts",)},
     {"pret": "kalbē", "partPresAct": "kalbant"},
     {"opt": ("kalbisei",)}),
]

IDS = [f"{pos}/{paradigm}/{lemma}" for pos, paradigm, lemma, *_ in FIXTURES]


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
def test_fixture_derivation(atoms, fixture):
    pos, paradigm, lemma, gender, attested, stems, overrides = fixture
    got_stems, got_overrides = cf.derive_minimal(pos, paradigm, lemma, gender, attested)
    assert got_stems == stems
    assert got_overrides == overrides


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
def test_fixture_is_lossless(atoms, fixture):
    """``generate(stems) ∪ overrides == attested`` — zellweise, alle POS."""
    pos, paradigm, lemma, gender, attested, *_ = fixture
    derivation = cf.derive_entry(pos, paradigm, lemma, gender, attested)
    assert derivation.missing == {}
    for slot, surfaces in attested.items():
        assert set(surfaces) <= derivation.expanded[slot], slot


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
def test_fixture_overrides_are_not_generable(atoms, fixture):
    pos, paradigm, lemma, gender, attested, stems, overrides = fixture
    generated = cf.regenerate(pos, paradigm, lemma, stems)
    for slot, surfaces in overrides.items():
        assert not set(surfaces) & set(generated.get(slot, ())), slot


@pytest.mark.parametrize("fixture", [f for f in FIXTURES if f[5]],
                         ids=[i for i, f in zip(IDS, FIXTURES) if f[5]])
def test_every_stem_is_necessary(atoms, fixture):
    """Greedy-minimal: ohne einen gelieferten Stamm verliert der Eintrag Zellen."""
    pos, paradigm, lemma, gender, attested, stems, _ = fixture
    full = cf.covered_cells(attested, cf.regenerate(pos, paradigm, lemma, stems))
    for role in stems:
        without = {k: v for k, v in stems.items() if k != role}
        assert cf.covered_cells(attested,
                                cf.regenerate(pos, paradigm, lemma, without)) < full


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
def test_stem_is_measured_from_an_attested_surface(atoms, fixture):
    """Jeder gelieferte Stamm ist aus einer Belegform **seiner** Rolle gemessen.

    Kein Raten: ``stem_from_form`` zieht die Endung ab, die die Grammatik dort
    anhängt — der Stamm ist also immer eine attestierte Oberfläche ohne Endung.
    """
    pos, paradigm, lemma, gender, attested, stems, _ = fixture
    spec = gen.paradigm_spec(pos, paradigm, lemma)
    for role, stem in stems.items():
        measured = set()
        for slot in spec.roles[role].slots:
            for surface in attested.get(slot, ()):
                try:
                    measured.add(gen.stem_from_form(pos, paradigm, role, slot,
                                                    surface, lemma=lemma))
                except ValueError:      # Variante, kein Stamm für diesen Slot
                    continue
        assert stem in measured, (role, stem, sorted(measured))


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
def test_lemma_only_mode_drops_all_stems(atoms, fixture):
    """Modus „nur Lemma“: Stufe 0 ohne gelieferte Stämme — Overrides wachsen."""
    pos, paradigm, lemma, gender, attested, stems, overrides = fixture
    plain = cf.derive_entry(pos, paradigm, lemma, gender, attested, lemma_only=True)
    assert plain.stems == {}
    assert plain.covered_s1 == plain.covered_s0
    assert plain.missing == {}
    assert sum(len(v) for v in plain.overrides.values()) >= sum(
        len(v) for v in overrides.values())


@pytest.mark.parametrize("fixture", FIXTURES, ids=IDS)
def test_recompress_of_the_lean_entry_is_stable(atoms, fixture):
    """Idempotenz je Eintrag: die lean NVH ergibt dieselben Stämme/Overrides.

    Der zweite Lauf liest die lean Datei im ``dense``-Modus: die Stämme stehen in
    ``stemOverrides``, die Zellen der Datei sind die Aussage der Datei. Ohne diesen
    Modus baute der zweite Lauf aus einer Nischenform einen neuen Stamm und verlor
    die Zellen, die der erste Lauf aus der Regel hatte.
    """
    pos, paradigm, lemma, gender, attested, *_ = fixture
    (entry,) = cf.parse_nvh(nvh_text(pos, paradigm, lemma, gender, attested))
    first = cf.derive_entry(pos, paradigm, lemma, gender, attested)
    text = cf.render_entry(entry, first.stems, first.overrides)
    (lean,) = cf.parse_nvh(text)
    assert (lean.pos, lean.paradigm, lean.gender) == (pos, paradigm, gender)
    assert lean.stems == first.stems
    # Die lean NVH weist nur die Rest-Overrides aus; Stämme stehen in der Zeile.
    assert lean.attested == {slot: tuple(sorted(v))
                             for slot, v in first.overrides.items()}
    assert text.count("  inflectedForm:") == sum(
        len(v) for v in first.overrides.values())
    second = cf.derive_entry(lean.pos, lean.paradigm, lean.lemma, lean.gender,
                             lean.attested, supplied=lean.stems, dense=True)
    assert (second.stems, second.overrides) == (first.stems, first.overrides)
    assert second.missing == {}


# ── Varianten, Varianteneinträge, Lint ──────────────────────────────────────

def test_variant_becomes_an_override(atoms):
    """Ein Stamm deckt je Slot **eine** Oberfläche — die Variante bleibt übrig."""
    attested = {"sg.nom": ("Patals",), "sg.gen": ("Patallas", "Patallax"),
                "sg.dat": ("Patallu",), "sg.acc": ("Patallan",), "pl.nom": ("Patallai",),
                "pl.gen": ("Patallan",), "pl.dat": ("Patallamans",), "pl.acc": ("Patallans",)}
    derivation = cf.derive_entry("noun", "32", "Patals", "masc", attested)
    assert derivation.stems == {"obl": "Patall"}
    assert derivation.overrides == {"sg.gen": ("Patallax",)}
    assert derivation.override_variant == 1
    assert derivation.lint_generable_override == 0
    assert derivation.missing == {}


def test_variant_without_extra_surface_needs_no_override(atoms):
    attested = {"sg.nom": ("Patals",), "sg.gen": ("Patallas",), "sg.dat": ("Patallu",),
                "sg.acc": ("Patallan",), "pl.nom": ("Patallai",), "pl.gen": ("Patallan",),
                "pl.dat": ("Patallamans",), "pl.acc": ("Patallans",)}
    derivation = cf.derive_entry("noun", "32", "Patals", "masc", attested)
    assert derivation.override_variant == 0
    assert derivation.stems == {"obl": "Patall"}


def test_redundant_stem_is_never_selected(atoms):
    """Stamm wie der Stufe-0-Stamm: der Greedy verlangt Gewinn, also keiner.

    Genau diese Invariante zählt ``stem_fields`` im Bericht — bei ``Patals`` ist der
    gemessene Stamm ``Patall`` vom Regelstamm ``Patal`` verschieden (Stamm nötig,
    Lint 0), bei ``Adwēnts`` dagegen identisch (brächte nichts, also keiner).
    """
    stem_case = cf.derive_entry("noun", "32", "Patals", "masc",
                                {"sg.gen": ("Patallas",), "pl.dat": ("Patallamans",)})
    assert stem_case.stems == {"obl": "Patall"}
    assert stem_case.stem_fields == ()
    redundant_case = cf.derive_entry(
        "noun", "56", "Adwēnts", "masc",
        {"sg.nom": ("Adwēnts",), "sg.gen": ("Adwēntis",), "sg.dat": ("Adwēnti",),
         "sg.acc": ("Adwēntin",), "pl.nom": ("Adwēntjai",), "pl.gen": ("Adwēntin",),
         "pl.dat": ("Adwēntimans",), "pl.acc": ("Adwēntins",)})
    assert redundant_case.stems == {}                  # Stamm "Adwēnt" == Stufe 0
    assert redundant_case.stem_fields == ()
    assert redundant_case.complete_s0 and redundant_case.missing == {}


def test_compress_keeps_every_entry_and_counts_the_rest(atoms):
    """Die lean NVH behält den Einträgebestand; Varianteneinträge zählen nur."""
    text = FAT_SNIPPET + "entry: galbimai\n  label: variantSkeleton\n" \
                       "  relation: variantOf\n    member: x role: variant\n"
    entries = cf.parse_nvh(text)
    stats = cf.Stats()
    pairs = list(cf.compress(entries, stats=stats))
    assert [e.lemma for e, _ in pairs] == ["Adwēnts", "galbimai"]
    assert pairs[1][1].stems == {} and pairs[1][1].overrides == {}
    assert stats.skipped[("-", "Varianteneintrag (keine Zellen)")] == 1
    assert stats.entries_of("noun") == 1 and stats.cells[("noun", "s1")] == 3


def test_compress_keeps_cells_of_entries_without_paradigm(atoms):
    """Ohne Paradigma wird nicht geraten, sondern alles als Override übernommen."""
    text = ("entry: ohne\n  pos: noun\n  gender: fem\n"
            "  inflectedForm: Ohnai\n    tag: sg.nom\n")
    (entry,) = cf.parse_nvh(text)
    (pair,) = list(cf.compress([entry]))
    assert pair[1].overrides == {"sg.nom": ("Ohnai",)}
    assert pair[1].missing == {}


def test_verify_looks_at_the_fat_cells_not_at_the_derivation(atoms, corpus_sample):
    """Echte Verlustfreiheitsprüfung: ``generate(stems) ∪ overrides ⊇ fette Zellen``.

    ``derivation.missing`` ist per Konstruktion leer (die Overrides *sind* der
    Rest), deshalb rechnet der Test die Expansion selbst nach und lässt
    ``verify`` gegen ``entry.attested`` laufen.
    """
    pairs = list(cf.compress(corpus_sample))
    for entry, derivation in pairs:
        expanded = derivation.expanded
        for slot, surfaces in entry.attested.items():
            assert set(surfaces) <= expanded.get(slot, frozenset()), (entry.lemma, slot)
    assert cf.verify(pairs) == []


def test_verify_reports_a_tampered_derivation():
    """Gegenprobe: ein fehlendes Override muss als Fehler auffallen."""
    entry, = cf.parse_nvh(nvh_text("noun", "32", "Patals", "masc",
                                   {"sg.nom": ("Patals",), "pl.gen": ("Patallan",)}))
    derivation = cf.derive_entry("noun", "32", "Patals", "masc", entry.attested)
    assert cf.verify([(entry, derivation)]) == []
    # Auch ``generated`` wird gekappt — sonst deckt der Generator die Zelle ja.
    broken = cf.Derivation(stems={},
                           overrides={k: v for k, v in derivation.overrides.items()
                                      if k != "pl.gen"},
                           generated={k: v for k, v in derivation.generated.items()
                                      if k != "pl.gen"},
                           attested=entry.attested)
    assert cf.verify([(entry, broken)]) and "pl.gen" in cf.verify([(entry, broken)])[0]


def test_fixpoint_round_is_measured_against_the_fat_cells(atoms):
    """Runde 2 leitet aus ``stems ∪ overrides`` ab, misst aber an den fetten Zellen.

    Sonst wäre jede Runde ab 2 automatisch verlustfrei. Geprüft wird die
    Zellenrechnung der zweiten Runde direkt — ``waidintinnis`` ist der Fall aus
    dem Korpus: kein gelieferter Stamm, der größte Teil der Zellen aus Stufe 0,
    der Rest als Overrides.
    """
    attested = {"msc.sg.nom": ("waidintinnis",), "msc.sg.gen": ("waidintinnis",),
                "msc.sg.dat": ("waidintinnismu",), "msc.sg.acc": ("waidintinnin",),
                "neu.sg.nom": ("waidintinni",), "neu.sg.gen": ("waidintinnis",)}
    round1 = cf._derive_once("adj", "27", "waidintinnis", "", cf._normalize(attested), False)
    lean = cf._lean_attested(round1)
    round2 = cf._derive_once("adj", "27", "waidintinnis", "", lean, False,
                             original=cf._normalize(attested))
    assert round2.cells == len(attested)               # nicht die 15 Runden-2-Zellen
    assert round2.attested == round1.attested
    assert cf.uncovered(cf._normalize(attested), round2.expanded) == {}
    assert round2.covered_s0 == round1.covered_s0


def test_report_contains_the_required_sections():
    stats = cf.Stats()
    stats.entries[("noun", "56")] = 2
    stats.cells[("noun", "total")] = 16
    stats.cells[("noun", "s0")] = 14
    stats.cells[("noun", "s1")] = 15
    text = stats.report()
    assert "POS-Deckung" in text and "Zellenklasse" in text and "Paradigmen" in text
    assert "Lints" not in text and "Lint / Befunde" in text
    assert "redundante Stämme" in text and "Overrides an Varianten-Slots" in text


# ── Stichprobe der echten fette NVH (überspringt ohne Korpusdatei) ───────────

def _sample(pos: str, count: int = 25) -> list:
    entries = cf.read_nvh(cf.FULL_NVH)
    picked = [e for e in entries if e.pos == pos]
    stride = max(1, len(picked) // count)
    return picked[::stride][:count]


@pytest.fixture(scope="module")
def corpus_sample():
    if not cf.FULL_NVH.exists():
        pytest.skip(f"{cf.FULL_NVH} fehlt (fette NVH nicht erzeugt)")
    return [e for pos in ("noun", "adj", "verb") for e in _sample(pos)]


def test_corpus_sample_is_lossless_and_idempotent(atoms, corpus_sample):
    pairs = list(cf.compress(corpus_sample))
    assert cf.verify(pairs) == []
    stats = cf.Stats()
    list(cf.compress(corpus_sample, stats=stats))          # frisch statt gecacht
    # Idempotenz: die gerenderte lean NVH ergibt dieselben Stämme/Overrides. Der
    # zweite Lauf ist ein dense-Lauf — die lean Datei ist selbst die Aussage.
    again = cf.parse_nvh("".join(cf.render_entry(e, d.stems, d.overrides)
                                 for e, d in pairs))
    second = list(cf.compress(again, dense=True))
    assert len(second) == len(pairs)
    for (e1, d1), (e2, d2) in zip(pairs, second):
        assert (d1.stems, d1.overrides) == (d2.stems, d2.overrides), e1.lemma


def test_corpus_sample_has_regular_and_override_lexemes(atoms, corpus_sample):
    """Die Stichprobe muss reguläre und override-pflichtige Lexeme je POS treffen.

    Gezählt wird die **finite** Tafel: bei Verben sind die Partizip-Overrides keine
    Ausnahme, sondern lange der Normalfall — ein Verb gilt hier als regulär, wenn
    es weder gelieferte Stämme noch finite Overrides braucht.
    """
    kinds: dict[str, set[str]] = {}
    for entry, derivation in cf.compress(corpus_sample):
        finite_overrides = sum(
            len(surfaces) for slot, surfaces in derivation.overrides.items()
            if cf.slot_class(entry.pos, slot) != "partizip")
        if not derivation.stems and not finite_overrides:
            kind = "regulär"
        elif derivation.stems and not finite_overrides:
            kind = "stamm"
        else:
            kind = "override"
        kinds.setdefault(entry.pos, set()).add(kind)
    for pos in ("noun", "adj"):
        assert {"regulär", "override"} <= kinds.get(pos, set()), (pos, kinds.get(pos))
    assert {"regulär", "stamm", "override"} <= kinds.get("verb", set()), kinds.get("verb")


def test_corpus_sample_coverage_bounds(atoms, corpus_sample):
    """Regressionsrahmen: finite Verben und Nomen deutlich über der Override-Quote.

    Die Erwartungsrahmen des Plans (Nomen ~99,6 %, Verb ~99,5 % finite) gelten für
    die finite Tafel gegen die ungefilterte Lexemmenge; hier wird bewusst nur
    geprüft, dass die Deckung nicht einbricht.
    """
    stats = cf.Stats()
    list(cf.compress(corpus_sample, stats=stats))
    for pos, floor in (("noun", 0.95), ("adj", 0.90)):
        total = stats.cells[(pos, "total")] - stats.cells[(pos, "status")]
        assert stats.cells[(pos, "s1")] / total >= floor, (pos, stats.cells[(pos, "s1")], total)
    finite_total = stats.class_cells[("verb", "verb")]
    assert stats.class_s1[("verb", "verb")] / finite_total >= 0.95, stats.class_s1
