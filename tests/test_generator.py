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
    ("sg.nom", "+Sg+Nom"), ("pl.dat", "+Pl+Dat"),
    ("masc.sg.nom", "+Adj+Masc+Sg+Nom"), ("neut.pl.acc", "+Adj+Neut+Pl+Acc"),
    ("cmp.masc.sg.nom", "+Adj+Cmp+Masc+Sg+Nom"), ("sup.neut.sg.dat", "+Adj+Sup+Neut+Sg+Dat"),
    ("adv", "+Adv"), ("adv.cmp", "+Adv+Cmp"), ("adv.sup", "+Adv+Sup"),
    ("pres.p1.sg", "+Ind+Pres+P1+Sg"), ("pres.p3", "+Ind+Pres+P3"),
    ("past.p2.pl", "+Ind+Pret+P2+Pl"), ("subj.p1.sg", "+Subj+P1+Sg"),
    ("subj.p3", "+Subj+P3"), ("opt", "+Opt+P3"),
    ("imp.sg", "+Imp+P2+Sg"), ("imp.pl", "+Imp+P2+Pl"),
    ("part.pres.masc.sg.nom", "+V+Part+Pres+Masc+Sg+Nom"),
    # PartAct/PartPass tragen in gen/adj.lexc kein +V (so fragt coverage_adj.py ab).
    ("part.past.masc.sg.nom", "+Part+Past+Masc+Sg+Nom"),
    ("part.pass.neut.pl.gen", "+Part+Pass+Neut+Pl+Gen"),
])
def test_slot_tag(slot, tag):
    v_prefix = not slot.startswith(("part.past", "part.pass"))
    assert gen.slot_tag(slot, v_prefix) == tag


@pytest.mark.parametrize("bad", [
    "sg", "sg.loc", "cmp.sg.nom", "pres.p4", "pres.p3.pl", "nonsense", "sg.nom.x",
])
def test_slot_tag_rejects_unknown(bad):
    with pytest.raises(ValueError):
        gen.slot_tag(bad)


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
    # Verben führen zusätzlich die Partiziprollen; nonfin = Infinitivstamm.
    ("verb", "132", "auwaitjātun", {"pres": "auwaitjā", "nonfin": "auwaitjā",
                                     "partact": "auwaitjā", "partpass": "auwaitjā",
                                     "partpres": "auwaitjānt"}),
    ("verb", "138", "absōrbitun", {"pres": "absōrb", "nonfin": "absōrbi",
                                   "partact": "absōrbi", "partpass": "absōrbi",
                                   "partpres": "absōrbint"}),
    ("verb", "143", "alkautwei", {"pres": "alka", "nonfin": "alkau",
                                   "partact": "alkau", "partpass": "alkau",
                                   "partpres": "alkawint"}),
    ("verb", "85", "appautwei", {"pres": "appau", "nonfin": "appau",
                                 "partpres": "appawint", "partact": "appau",
                                 "partpass": "appau"}),
])
def test_default_stems(pos, paradigm, lemma, stems):
    assert gen.default_stems(pos, paradigm, lemma=lemma) == stems


def test_seed_wins_over_lemma():
    """Stufe 1: eine attestierte Prinzipalform schlägt den Lemma-Stamm."""
    assert gen.default_stems("noun", "53", lemma="dumslē",
                             seeds={"sg.gen": "dumslis"})["obl"] == "dumsl"
    # -na-Stamm: der Seed trägt die Genus-Endung, nicht der Lemma-Abzug.
    assert gen.default_stems("noun", "61", lemma="woks",
                             seeds={"sg.gen": "wokes"})["obl"] == "wok"


def test_verb_variant_87():
    assert gen.resolve_paradigm("verb", "87", "kandautwei") == "87a"
    assert gen.resolve_paradigm("verb", "87", "brendautwei") == "87a"
    assert gen.resolve_paradigm("verb", "87", "trāutautwei") == "87b"
    assert ("verb", "87a") in gen.PARADIGMS and ("verb", "87") not in gen.PARADIGMS


def test_gender_is_pass_through_only():
    with_g = gen.generate("noun", "53", lemma="dumslē", gender="fem")
    assert with_g == gen.generate("noun", "53", lemma="dumslē")
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
        "masc.sg.nom": "wilnis", "masc.sg.gen": "wilnjas", "neut.sg.nom": "wilni",
        "fem.pl.dat": "wilnimans", "adv": "wilnjai", "adv.cmp": "wilnjais",
        "cmp.masc.sg.nom": "wilnjaisis", "sup.masc.sg.nom": "ukawilnjaisis"}),
    # gen/adj.lexc AdjUMobInfl (w-Gleit: Gen.Sg. -was) + AdvU
    ("adj", "31", "tangus", {
        "masc.sg.nom": "tangus", "masc.sg.gen": "tangwas", "adv": "tangu",
        "adv.cmp": "tanguis", "cmp.masc.sg.nom": "tanguisis",
        "sup.masc.sg.nom": "ukatanguisis"}),
    # Par.30 = reines u-Adverb (keine Deklination)
    ("adj", "30", "sengus", {
        "adv": "sengu", "adv.cmp": "senguis", "adv.sup": "ukasenguis",
        "cmp.masc.sg.nom": "senguisis", "sup.masc.sg.nom": "ukasenguisis"}),
    # gen/verb.lexc Par.132: Pres_I/Pret_I/Imp_Is + SubjOpt, Stamm = Infinitivstamm
    ("verb", "132", "auwaitjātun", {
        "pres.p1.sg": "auwaitjāi", "pres.p3": "auwaitjāi", "past.p3": "auwaitjāi",
        "subj.p3": "auwaitjālai", "opt": "auwaitjāsei", "imp.sg": "auwaitjāis",
        "imp.pl": "auwaitjāiti"}),
    # Par.143: Präs. -ui auf Stamm -a (alkaut → alka), Nonfin auf alkau (Pret_0/Imp_Siti)
    ("verb", "143", "alkautwei", {
        "pres.p1.sg": "alkaui", "pres.p3": "alkaui", "past.p3": "alkau",
        "subj.p3": "alkaulai", "imp.sg": "alkaus"}),
    # Partizipien aus gen/adj.lexc: -wints (Klasse -taw-), -uns, -s
    ("verb", "85", "appautwei", {
        "part.pres.masc.sg.nom": "appawints", "part.pres.fem.sg.nom": "appawintī",
        "part.past.masc.sg.nom": "appauuns", "part.pass.masc.sg.nom": "appaus"}),
])
def test_forms(atoms, pos, paradigm, lemma, forms):
    out = gen.generate(pos, paradigm, lemma=lemma)
    for slot, want in forms.items():
        assert out[slot] == (want,), f"{pos}/{paradigm} {lemma} {slot}: {out[slot]} ≠ {want}"


def test_stem_override_is_stufe_2(atoms):
    """Stufe 2 überschreibt den Rollen-Stamm; die Endungen bleiben dieselben."""
    out = gen.generate("noun", "53", lemma="dumslē", stems={"obl": "dumslē"})
    # Der Override-Stamm ist wörtlich der Stamm — nur die Endung wird angehängt.
    assert out["sg.gen"] == ("dumslēis",)
    assert out["pl.acc"] == ("dumslēins",)
    # %^ē / %^īmans in sg.nom und pl.dat lassen die Akzentgrenze den Stammvokal
    # reduzieren (ē → e vor der Endung).
    assert out["sg.nom"] == ("dumsleē",)
    assert out["pl.dat"] == ("dumsleīmans",)


def test_missing_lemma_yields_nothing(atoms):
    """Ohne Lemma und ohne Seed gibt es keine Formen — kein Rateversuch."""
    assert gen.generate("noun", "53") == {}


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
