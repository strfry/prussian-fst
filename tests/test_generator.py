"""Tests für den datenfreien Generator (gen/generator.py + gen/atom_fst.py).

Kein twanksta, kein NVH, kein Korpus: die erwarteten Oberflächen sind von Hand aus
den handgeschriebenen Grammatiken abgelesen — Stamm (Lemma minus Klassenendung)
plus Endung aus gen/<family>.lexc bzw. gen/verb.lexc, dazu die Akzentregel
gen/accent.regex.  Die Atome baut der Test bei Bedarf selbst; hfst.compile_lexc_file
funktioniert pro Prozess nur einmal, deshalb je Atom ein Subprozess (`make atoms`
baut alle 245 auf einmal).
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "gen"))

import atom_fst  # noqa: E402
import generator as gen  # noqa: E402

# Atome, die die Formen-Fixtures unten brauchen (Rollen, nicht Slugs).
WANTED = [
    ("noun", "53", "obl"),
    ("noun", "61", "obl"),
    ("adj", "27", "pos"), ("adj", "27", "adv"),
    ("adj", "27", "cmp"), ("adj", "27", "sup"),
    ("adj", "31", "pos"), ("adj", "31", "adv"),
    ("adj", "30", "adv"),
    ("verb", "132", "pres"), ("verb", "132", "nonfin"),
    ("verb", "143", "pres"), ("verb", "143", "nonfin"),
    ("verb", "85", "partpres"), ("verb", "85", "partact"),
    ("verb", "85", "partpass"),
]


@pytest.fixture(scope="session")
def atoms():
    """Die benötigten Atome bauen (Session-Fixture: ~15 Subprozesse)."""
    pytest.importorskip("hfst", reason="hfst-Paket fehlt (make atoms braucht es)")
    if not (REPO / "build/gen-accent.hfst").exists():
        pytest.skip("build/gen-accent.hfst fehlt — make gen-accent.hfst")
    for pos, paradigm, role in WANTED:
        done = subprocess.run(
            [sys.executable, str(REPO / "gen/atom_fst.py"), pos, paradigm, role],
            capture_output=True, text=True, cwd=REPO)
        if done.returncode:
            pytest.fail(f"Atom {pos}/{paradigm}/{role} nicht baubar:\n"
                        f"{(done.stderr or done.stdout)[-2000:]}")


# ── reine Tabellen: Slot-Key → lexc-Tag ─────────────────────────────────────

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


# ── Round-Trip: Slot-Key → FST-Tag → Slot-Key (bijektiv je POS) ────────────

def _tag_to_slot(tag: str) -> str:
    """FST-Tag → NVH-Slot-Key (Umkehr von ``generator.slot_tag``)."""
    pos, *rest = tag.lstrip("+").split("+")
    if pos == "N":
        number, case = rest
        return f"{number.lower()}.{case.lower()}"
    if pos == "Adv":
        return "adv" if not rest else f"adv.{rest[0].lower()}"
    if pos == "A":
        degree = rest[0].lower() if rest[0] in ("Comp", "Superl") else ""
        gender, number, case = rest[-3:]
        tail = (degree, gender.lower(), number.lower(), case.lower())
        return ".".join(p for p in tail if p)
    if pos == "V":
        if rest[0] in ("PrsPrc", "PrfPrc"):
            _, voice, gender, number, case = rest
            tense = "prs" if rest[0] == "PrsPrc" else "prf"
            tail = (tense, voice.lower(), gender.lower(), number.lower(), case.lower())
            return "part." + ".".join(tail)
        mood = rest[0]
        if mood == "Opt":
            return "opt"
        if mood == "Subj":
            return f"subj.{rest[1].lower()}"
        if mood == "Imprt":
            return f"imprt.{rest[1].lower()}"
        tense, persnum = rest[1], rest[2]
        return f"{tense.lower()}.{persnum.lower()}"
    raise AssertionError(f"unbekannter POS-Marker {pos!r}")


ROUNDTRIP_SLOTS = [
    # Nomen
    gen.NOUN_SLOTS[0], gen.NOUN_SLOTS[-1],
    # Adjektiv (Positiv / comp / superl / Adverb)
    gen.ADJ_POS_SLOTS[0], gen.ADJ_POS_SLOTS[-1],
    gen.ADJ_CMP_SLOTS[0], gen.ADJ_SUP_SLOTS[-1],
    gen.ADVERB_SLOTS[0], gen.ADVERB_SLOTS[-1],
    # Verb finit (alle Modus-/Tempusklassen)
    gen.VERB_PRES_SLOTS[0], gen.VERB_PRES_SLOTS[2],
    gen.VERB_PAST_SLOTS[0], gen.VERB_SUBJ_SLOTS[-1],
    gen.VERB_OPT_SLOTS[0], gen.IMP_SLOTS[0], gen.IMP_SLOTS[-1],
    # Partizipien (alle Prc-Typ/Voice-Kombinationen)
    gen.PART_PRES_SLOTS[0], gen.PART_PAST_SLOTS[-1], gen.PART_PASS_SLOTS[3],
]


@pytest.mark.parametrize("slot", ROUNDTRIP_SLOTS)
def test_slot_tag_roundtrip(slot):
    """key → slot_tag → key: bijektiv (ein Slot je POS-Vertretung)."""
    assert _tag_to_slot(gen.slot_tag(slot)) == slot


def test_slot_tag_roundtrip_is_injective():
    """Verschiedene Slots dürfen nie denselben Tag ergeben."""
    tags = {slot: gen.slot_tag(slot) for slot in ROUNDTRIP_SLOTS}
    assert len(set(tags.values())) == len(tags), tags


# ── Metadaten: jeder Atom-Name muss in der Grammatik existieren ─────────────

def _lexicons(path: Path) -> set[str]:
    return set(re.findall(r"^LEXICON\s+(\S+)", path.read_text(encoding="utf-8"),
                          re.MULTILINE))


@pytest.mark.parametrize("pos, paradigm", sorted(gen.PARADIGMS))
def test_atoms_exist_in_grammar(pos, paradigm):
    """Jedes im Generator genannte Infl-Lexikon steht auch wirklich im lexc."""
    par = gen.PARADIGMS[(pos, paradigm)]
    for role, spec in par.roles.items():
        defined = _lexicons(REPO / spec.lexc)
        for atom in spec.atoms:
            assert atom in defined, f"{pos}/{paradigm}/{role}: LEXICON {atom} fehlt in {spec.lexc}"
        assert spec.slots, f"{pos}/{paradigm}/{role}: keine Slots"


def test_atom_names_are_unique_and_245():
    targets = gen.atom_targets()
    paths = [path for *_rest, path in targets]
    assert len(targets) == len(set(paths)) == 245
    assert all(p.suffix == ".hfstol" and p.parent == gen.ATOM_DIR for p in paths)
    # Ein-Rollen-Atome ohne Rollen-Suffix, Mehr-Rollen-Atome mit.
    assert gen.atom_path("noun", "53", "obl").name == "gen-istem-53.hfstol"
    assert gen.atom_path("adj", "27", "cmp").name == "gen-adj-27-cmp.hfstol"


# ── Stammregeln Stufe 0 (Lemma → Stamm) ────────────────────────────────────

@pytest.mark.parametrize("pos, paradigm, lemma, stems", [
    ("noun", "53", "dumslē", {"obl": "dumsl"}),
    ("noun", "61", "woks", {"obl": "wok"}),
    ("noun", "35", "gurbas", {"obl": "gurb"}),
    # Beim Adverb steckt das -j im Lexikon (AdvI +jai), der Komparativ-Suffix
    # hängt am Stamm: wiln + jais, danach + uka für den Superlativ.
    ("adj", "27", "wilnis", {"pos": "wiln", "adv": "wiln", "cmp": "wilnjais",
                             "sup": "ukawilnjais"}),
    ("adj", "31", "tangus", {"pos": "tang", "adv": "tang", "cmp": "tanguis",
                             "sup": "ukatanguis"}),
    # Verben führen zusätzlich die Partiziprollen; nonfin = Infinitivstamm, und die
    # Partizipien sind es auch — nur mit eigener Endung (Gleit -w-, -nt, -t).
    ("verb", "132", "auwaitjātun", {"pres": "auwaitjā", "nonfin": "auwaitjā",
                                     "partact": "auwaitjāw", "partpass": "auwaitjāt",
                                     "partpres": "auwaitjānt"}),
    ("verb", "138", "absōrbitun", {"pres": "absōrb", "nonfin": "absōrbi",
                                   "partact": "absōrbiw", "partpass": "absōrbit",
                                   "partpres": "absōrbint"}),
    # Klasse -taw-: au → aw, im Präsens au → a (der Infinitiv behält das -au).
    ("verb", "143", "alkautwei", {"pres": "alka", "nonfin": "alkau",
                                   "partact": "alkaw", "partpass": "alkaut",
                                   "partpres": "alkawint"}),
    ("verb", "85", "appautwei", {"pres": "appau", "nonfin": "appau",
                                 "partpres": "appawint", "partact": "appaw",
                                 "partpass": "appaut"}),
])
def test_default_stems(pos, paradigm, lemma, stems):
    assert gen.default_stems(pos, paradigm, lemma=lemma) == stems


def test_default_stems_without_lemma_is_empty():
    """Ohne Lemma gibt es keinen Stamm zu raten — Stufe 0 liefert dann nichts."""
    assert gen.default_stems("noun", "53") == {}
    assert gen.default_stems("verb", "85") == {}


def test_delivered_stem_overrides_the_rule(atoms):
    """Stufe 1: ein gelieferter Stamm ist der Rollen-Stamm, verbatim."""
    assert gen.generate("noun", "53", lemma="dumslē",
                        stems={"obl": "wok"})["sg.gen"] == ("wokis",)
    assert gen.generate("verb", "85", lemma="ainapreslintun",
                        stems={"partpres": "ainapreslinānt"})[
                            "part.prs.act.msc.sg.nom"] == ("ainapreslinānts",)


# ── Stamm aus einer belegten Form: die Grammatik ist das Messgerät ──────────

@pytest.mark.parametrize("pos, paradigm, role, slot, form, stem", [
    ("noun", "53", "obl", "sg.gen", "dumslis", "dumsl"),
    ("noun", "53", "obl", "pl.acc", "dumslins", "dumsl"),
    ("noun", "32", "obl", "pl.dat", "Patallamans", "Patall"),
    ("adj", "27", "pos", "msc.sg.gen", "wilnjas", "wiln"),
    ("adj", "27", "adv", "adv", "wilnjai", "wiln"),
    ("verb", "136", "pret", "prt.sp3", "kalbēi", "kalbē"),
    ("verb", "132", "partact", "part.prf.act.msc.sg.nom", "mitāwuns", "mitāw"),
    ("verb", "132", "partpres", "part.prs.act.msc.sg.nom", "mitānts", "mitānt"),
    ("verb", "132", "partpass", "part.prf.pss.msc.sg.nom", "mitāts", "mitāt"),
])
def test_stem_from_form(atoms, pos, paradigm, role, slot, form, stem):
    """Endung abziehen heißt: die Grammatik fragen, nicht eine Liste pflegen."""
    assert gen.stem_from_form(pos, paradigm, role, slot, form) == stem


def test_stem_from_form_reproduces_the_form(atoms):
    """Der zurückgewonnene Stamm muss die Belegform wiederherstellen."""
    for pos, paradigm, role, slot, form in (
            ("noun", "53", "obl", "pl.acc", "dumslins"),
            ("verb", "132", "partact", "part.prf.act.msc.sg.nom", "mitāwuns")):
        stem = gen.stem_from_form(pos, paradigm, role, slot, form)
        assert form in gen.generate(pos, paradigm, stems={role: stem})[slot]


def test_stem_from_form_rejects_a_foreign_ending(atoms):
    with pytest.raises(ValueError, match="endet nicht auf die Endung"):
        gen.stem_from_form("noun", "53", "obl", "sg.gen", "dumslē")


def test_stem_from_form_rejects_a_foreign_slot(atoms):
    with pytest.raises(ValueError, match="gehört nicht zur Rolle"):
        gen.stem_from_form("noun", "53", "obl", "prs.sp3", "dumslis")


def test_slot_ending_is_measured_through_the_grammar(atoms):
    """Die Endung kommt aus dem Atom, inklusive Akzentgrenze und Markern."""
    assert gen.slot_ending("noun", "53", "obl", "sg.gen") == "is"
    assert gen.slot_ending("noun", "53", "obl", "pl.dat") == "īmans"
    # Der Gleitlaut steckt im Stamm (mitāw), nicht in der Endung des -uns-Partizips.
    assert gen.slot_ending("verb", "132", "partact",
                           "part.prf.act.msc.sg.nom") == "uns"


def test_sentinel_survives_every_atom(atoms):
    """Das Mess-Sentinel muss durch *jedes* Atom unversehindert laufen.

    Sonst wäre eine gemessene Endung still falsch (Doppelkonsonante, Makrone vor
    der Akzentgrenze, Geminate). Der Test läuft über alle Slots aller Paradigmen,
    die der Generator kennt.
    """
    for (pos, paradigm), par in gen.PARADIGMS.items():
        key = gen.resolve_paradigm(pos, paradigm, "dumslē")
        for role, spec in par.roles.items():
            for slot in spec.slots:
                out = gen.generate(pos, key, stems={role: gen._SENTINEL_STEM})[slot]
                assert len(out) == 1, (pos, paradigm, role, slot, out)
                assert out[0].startswith(gen._SENTINEL_STEM), (pos, paradigm, role,
                                                               slot, out)


def test_verb_variant_87():
    assert gen.resolve_paradigm("verb", "87", "kandautwei") == "87a"
    assert gen.resolve_paradigm("verb", "87", "brendautwei") == "87a"
    assert gen.resolve_paradigm("verb", "87", "trāutautwei") == "87b"
    assert ("verb", "87a") in gen.PARADIGMS and ("verb", "87") not in gen.PARADIGMS


def test_gender_is_pass_through_only():
    plain = gen.generate("noun", "53", lemma="dumslē")
    for entry_gender in ("fem", "masc", "neut"):
        assert gen.generate("noun", "53", lemma="dumslē", gender=entry_gender) == plain
    with pytest.raises(ValueError):
        gen.generate("noun", "53", lemma="dumslē", gender="n")


def test_stem_alphabet_is_enforced():
    gen.check_stem("dumsl" + "a" * 16 + "čšž")
    gen.check_stem("aukst~^>")                       # Geminaten-/Akzentmarker
    with pytest.raises(ValueError, match="STEM_ALPHABET"):
        gen.check_stem("nagg1")                      # Ziffer
    with pytest.raises(ValueError, match="STEM_ALPHABET"):
        gen.check_stem("q")                          # nicht im Kopierer


# ── Formen: Stamm + Endung + Akzent, von Hand aus den Grammatiken gelesen ──

@pytest.mark.parametrize("pos, paradigm, lemma, forms", [
    # gen/istem.lexc P53 (Sg.Nom/Dat.Pl mit Akzentmarker ^, Stamm bleibt leicht)
    ("noun", "53", "dumslē", {
        "sg.nom": "dumslē", "sg.gen": "dumslis", "sg.dat": "dumslei", "sg.acc": "dumslin",
        "pl.nom": "dumslis", "pl.gen": "dumslin", "pl.dat": "dumslīmans",
        "pl.acc": "dumslins"}),
    # gen/nstem.lexc P61
    ("noun", "61", "woks", {
        "sg.nom": "woks", "sg.gen": "wokes", "sg.dat": "woki", "sg.acc": "wokin",
        "pl.nom": "wokes", "pl.gen": "wokin", "pl.dat": "wokimans", "pl.acc": "wokins"}),
    # gen/adj.lexc AdjIInfl + AdvI + AdjCmp/AdjSup, Komparativ -jais, Superlativ uka+
    ("adj", "27", "wilnis", {
        "msc.sg.nom": "wilnis", "msc.sg.gen": "wilnjas", "neu.sg.nom": "wilni",
        "fem.pl.dat": "wilnimans", "adv": "wilnjai", "adv.comp": "wilnjais",
        "comp.msc.sg.nom": "wilnjaisis", "superl.msc.sg.nom": "ukawilnjaisis"}),
    # gen/adj.lexc AdjUMobInfl (w-Gleit: Gen.Sg. -was) + AdvU
    ("adj", "31", "tangus", {
        "msc.sg.nom": "tangus", "msc.sg.gen": "tangwas", "adv": "tangu",
        "adv.comp": "tanguis", "comp.msc.sg.nom": "tanguisis",
        "superl.msc.sg.nom": "ukatanguisis"}),
    # Par.30 = reines u-Adverb (keine Deklination)
    ("adj", "30", "sengus", {
        "adv": "sengu", "adv.comp": "senguis", "adv.superl": "ukasenguis",
        "comp.msc.sg.nom": "senguisis", "superl.msc.sg.nom": "ukasenguisis"}),
    # gen/verb.lexc Par.132: Pres_I/Pret_I/Imp_Is + SubjOpt, Stamm = Infinitivstamm
    ("verb", "132", "auwaitjātun", {
        "prs.sg1": "auwaitjāi", "prs.sp3": "auwaitjāi", "prt.sp3": "auwaitjāi",
        "subj.sp3": "auwaitjālai", "opt": "auwaitjāsei", "imprt.sg2": "auwaitjāis",
        "imprt.pl2": "auwaitjāiti"}),
    # Par.143: Präs. -ui auf Stamm -a (alkaut → alka), Nonfin auf alkau (Pret_0/Imp_Siti)
    ("verb", "143", "alkautwei", {
        "prs.sg1": "alkaui", "prs.sp3": "alkaui", "prt.sp3": "alkau",
        "subj.sp3": "alkaulai", "imprt.sg2": "alkaus"}),
    # Partizipien aus gen/adj.lexc: -wints (Klasse -taw-), -wuns (Gleit -w- vor
    # -uns), -ts (Stamm -t). Der Fem.Sg.Acc. des -uns-Partizips bleibt eine Lücke
    # der Grammatik (-usjan), der Neut.Pl.Nom. des -ts-Partizips ebenso (-ai).
    ("verb", "85", "appautwei", {
        "part.prs.act.msc.sg.nom": "appawints", "part.prs.act.fem.sg.nom": "appawintī",
        "part.prf.act.msc.sg.nom": "appawuns", "part.prf.pss.msc.sg.nom": "appauts"}),
])
def test_forms(atoms, pos, paradigm, lemma, forms):
    out = gen.generate(pos, paradigm, lemma=lemma)
    for slot, want in forms.items():
        assert out[slot] == (want,), f"{pos}/{paradigm} {lemma} {slot}: {out[slot]} ≠ {want}"


def test_participle_roles_all_start_from_the_nonfin_stem(atoms):
    """Der Nonfin-Stamm ist der Ausgangspunkt; nur die Endung unterscheidet sich."""
    out = gen.generate("verb", "132", lemma="auwaitjātun")
    assert out["subj.sp3"] == ("auwaitjālai",)
    assert out["part.prf.act.msc.sg.nom"] == ("auwaitjāwuns",)   # + Gleit -w-
    assert out["part.prf.pss.msc.sg.nom"] == ("auwaitjāts",)     # + -t
    assert out["part.prs.act.msc.sg.nom"] == ("auwaitjānts",)     # + -nt


def test_participle_glide_only_after_a_vowel(atoms):
    """Nach Konsonant kein Gleitlaut (audeguns), nach Vokal einer (mitāwuns)."""
    consonant = gen.generate("verb", "85", lemma="akkinantwei")
    vowel = gen.generate("verb", "132", lemma="auwaitjātun")
    assert consonant["part.prf.act.msc.sg.nom"][0].endswith("uns")
    assert not consonant["part.prf.act.msc.sg.nom"][0].endswith("wuns")
    assert vowel["part.prf.act.msc.sg.nom"] == ("auwaitjāwuns",)


def test_delivered_stem_wins_over_the_participle_rule(atoms):
    """Der thematische -in-Stamm ist lexikalisch: geliefert, nicht geregelt."""
    out = gen.generate("verb", "85", lemma="ainapreslintun")
    assert out["part.prs.act.msc.sg.nom"] == ("ainapreslinnts",)   # Regel-Fehler
    fixed = gen.generate("verb", "85", lemma="ainapreslintun",
                         stems={"partpres": "ainapreslinānt"})
    assert fixed["part.prs.act.msc.sg.nom"] == ("ainapreslinānts",)
    # Die Partiziprollen sind getrennt: partpass behält seinen eigenen Regelstamm.
    assert fixed["part.prf.pss.msc.sg.nom"] == ("ainapreslints",)


def test_stem_override_is_stufe_1(atoms):
    """Ein gelieferter Stamm überschreibt den Rollen-Stamm; die Endungen bleiben."""
    out = gen.generate("noun", "53", lemma="dumslē", stems={"obl": "dumslē"})
    # Der gelieferte Stamm ist wörtlich der Stamm — nur die Endung wird angehängt.
    assert out["sg.gen"] == ("dumslēis",)
    assert out["pl.acc"] == ("dumslēins",)
    # %^ē / %^īmans in sg.nom und pl.dat lassen die Akzentgrenze den Stammvokal
    # reduzieren (ē → e vor der Endung).
    assert out["sg.nom"] == ("dumsleē",)
    assert out["pl.dat"] == ("dumsleīmans",)


def test_missing_lemma_yields_nothing(atoms):
    """Ohne Lemma und ohne gelieferten Stamm gibt es keine Formen."""
    assert gen.generate("noun", "53") == {}
    assert gen.generate("noun", "53", stems={"obl": "dumsl"})["sg.gen"] == ("dumslis",)


def test_long_stem_with_markers(atoms):
    """Der Kopierer ist zyklisch: lange Stämme und Schutzmarker überleben.

    Der Marker ``~`` am Stammende (Konvention der Stammdaten, z. B. ``aupall%~``)
    unterdrückt die Gemination vor der Endung — die Surface-Form enthält weder
    Doppelkonsonant noch Marker.
    """
    stem = "auswajjint" + "aukst" * 2 + "~"
    out = gen.generate("noun", "53", stems={"obl": stem})
    assert out["sg.gen"] == ("auswajjintaukstaukstis",)
    assert out["pl.dat"] == ("auswajjintaukstaukstīmans",)
    assert "~" not in "".join(v[0] for v in out.values())


def test_unknown_role_is_rejected(atoms):
    with pytest.raises(KeyError, match="unbekannte Rolle"):
        gen.generate("noun", "53", lemma="dumslē", stems={"partpres": "dumsl"})


# ── Der Build selbst ────────────────────────────────────────────────────────

def test_copier_regex_is_cyclic_and_literal():
    import hfst
    copier = hfst.regex(atom_fst.copier_regex())
    assert copier is not None
    for stem in ("dumsl", "a" * 21, "aukst~", "rik>", "čŠā"):
        assert copier.lookup(stem)
    assert not copier.lookup("q")            # nicht im STEM_ALPHABET


def test_rewrite_root_only_touches_root():
    text = (REPO / "gen/istem.lexc").read_text(encoding="utf-8")
    out = atom_fst.rewrite_root(text, ("P52", "P52Stems"))
    # Nur der Root-Block (Aufrufe + Leerzeilen + Kommentare) wird ersetzt,
    # der Rest der Grammatik ist zeichengleich.
    start = re.search(r"^LEXICON Root$", text, re.MULTILINE).start()
    end = text.index("\nLEXICON ", start) + 1
    assert out == text[:start] + "LEXICON Root\n  P52 ;\n  P52Stems ;\n" + text[end:]
    assert _lexicons(REPO / "gen/istem.lexc") <= _lexicons_str(out)
    with pytest.raises(ValueError, match="kein LEXICON Root"):
        atom_fst.rewrite_root("LEXICON Andere\n  x ;\n", ("P53",))


def _lexicons_str(text):
    return set(re.findall(r"^LEXICON\s+(\S+)", text, re.MULTILINE))
