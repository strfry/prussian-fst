"""Datenfreier Stufe-0/1/2-Generator für preußische Wortformen.

Eingabe ist der NVH-Eintragsschema-Ausschnitt:

    entry:    <lemma>                      Nom.Sg. / Infinitiv / Masc.Nom.Sg.
    pos:      noun | adj | verb           Genus steht NICHT im pos
    gender:   masc | fem | neut           nur Nomen, optional (fehlt = unbekannt)
    paradigm: <Twanksta-Paradigmennummer>  zusammen mit pos → Stammfamilie

``legacy.*`` (desc/article/veraltetes paradigm) wird nicht gelesen.

Ausgabe ist ``{NVH-Slot-Key: (Form, …)}`` im dotted ``tag:``-Format (``sg.nom``,
``pl.acc``, ``cmp.masc.sg.nom``, ``sup.masc.sg.nom``, ``part.pres.masc.sg.nom``,
``pres.p1.sg``, ``p3`` ohne Numerus, ``opt``, ``imp.sg``/``imp.pl``). Die
gender-Komponente ist reines Durchreich-Tag: getrieben wird sie nicht — das Atom
liefert alle Genusblöcke, die das Paradigma hat. Für Nomen ohne bekanntes Genus wird
nichts erfunden.

KEINE KORPUSQUELLE. Die einzige Datenquelle sind die zur Build-Zeit kompilierten,
datenfreien Atom-FSTs ``build/gen-<family>-<paradigm>[-<role>].hfstol``, die aus den
handgeschriebenen Grammatiken ``gen/*.lexc`` + ``gen/accent.regex`` stammen
(siehe ``gen/atom_fst.py``). Zur Laufzeit genügt ein pyhfst-Lookup pro Slot:
``Stamm + Tag → Oberfläche``.

Stufen:

  0   Lemma → Basisstamm (Paradigma-Abzug) → alle Rollen regelhaft
  1   Prinzipalform(en) → Stamm (Seed-Abzug je Rolle)
  2   explizite Rollen-Stämme (Override)
  3   Slot-Overrides — nicht in diesem Paket (PLAN_generation.md)

Beispiel::

    generate("noun", "53", lemma="dumslē")     # → 8 oblique Formen
    generate("verb", "85", lemma="ainagimmatun")
    generate("adj", "27", lemma="wilnis")      # pos + cmp + sup + adv

Der Kern liest weder twanksta_entries.json noch eine NVH-Datei: die einzige
Lese-Abhängigkeit zur Laufzeit sind die gebauten Atom-FSTs.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
ATOM_DIR = ROOT / "build"

# ── Kopierer-/Stamm-Alphabet ───────────────────────────────────────────────
# Alle Zeichen, die real in Stämmen vorkommen, je in Groß- und Kleinschreibung.
# Feste Konstante, NICHT aus dem Korpus gescannt (ein Scan zöge sense:-Fremdsprachen
# und Satzzeichen mit rein). Eingaben vorher NFC-normalisieren, damit die
# Combining-Marks U+0300/U+0304 nicht als eigene Zeichen auftreten.
# Zusätzlich die drei morphologischen Marker, die in Stämmen stehen dürfen:
#   ^  Akzentgrenze (der Endungen bzw. mobilen Stufen-1-Stämmen)
#   ~  Schutzmarker „lexikalische Gemination"
#   >  Geminations-Marker (verdoppelt den Stammauslaut)
STEM_ALPHABET = (
    "aeiou" "AEIOU"
    "āēīōū" "ĀĒĪŌŪ"
    "áàèìùú" "ÁÀÈÌÙÚ"
    "bcdfghjklmnprstvwyz" "BCDFGHJKLMNPRSTVWYZ"
    "čšžźĺľŕńḿ" "ČŠŽŹĹĽŔŃḾ"
    "^~>"
)
STEM_ALPHABET_SET = frozenset(STEM_ALPHABET)

# ── Slot-Vokabular (NVH tag:, dotted) ───────────────────────────────────────
_GENDERS = ("masc", "fem", "neut")
_NUMBERS = ("sg", "pl")
_CASES = ("nom", "gen", "dat", "acc")

_GENDER = {"masc": "Masc", "fem": "Fem", "neut": "Neut"}
_NUMBER = {"sg": "Sg", "pl": "Pl"}
_CASE = {"nom": "Nom", "gen": "Gen", "dat": "Dat", "acc": "Acc"}
_DEGREE = {"cmp": "Cmp", "sup": "Sup"}
_PART = {"pres": "Pres", "past": "Past", "pass": "Pass"}
_FINITE = {"pres": "Pres", "past": "Pret", "subj": "Subj"}
_PERSON = {"p1": "P1", "p2": "P2", "p3": "P3"}


def _declined(genders: Iterable[str] = ()) -> tuple[str, ...]:
    """(gender.)number.case in kanonischer Reihenfolge.

    Ohne gender-Liste (Nomen: Genus ist ein Entry-Fakt, keine Slot-Dimension)
    kommt der einzelne Block ohne Präfix.
    """
    out: list[str] = []
    for gender in tuple(genders) or ("",):
        for number in _NUMBERS:
            for case in _CASES:
                out.append(f"{gender}.{number}.{case}" if gender else f"{number}.{case}")
    return tuple(out)


NOUN_SLOTS = _declined()
_GENDERED = _declined(_GENDERS)
ADJ_POS_SLOTS = _GENDERED
ADJ_CMP_SLOTS = tuple(f"cmp.{s}" for s in _GENDERED)
ADJ_SUP_SLOTS = tuple(f"sup.{s}" for s in _GENDERED)
ADJ_SLOTS = ADJ_POS_SLOTS + ADJ_CMP_SLOTS + ADJ_SUP_SLOTS + ("adv", "adv.cmp", "adv.sup")
ADVERB_SLOTS = ("adv", "adv.cmp", "adv.sup")
IMP_SLOTS = ("imp.sg", "imp.pl")
VERB_PRES_SLOTS = ("pres.p1.sg", "pres.p2.sg", "pres.p3", "pres.p1.pl", "pres.p2.pl")
VERB_PAST_SLOTS = ("past.p1.sg", "past.p2.sg", "past.p3", "past.p1.pl", "past.p2.pl")
VERB_SUBJ_SLOTS = ("subj.p1.sg", "subj.p2.sg", "subj.p3", "subj.p1.pl", "subj.p2.pl")
VERB_OPT_SLOTS = ("opt",)
VERB_SLOTS = VERB_PRES_SLOTS + VERB_PAST_SLOTS + VERB_SUBJ_SLOTS + VERB_OPT_SLOTS + IMP_SLOTS
PART_PRES_SLOTS = tuple(f"part.pres.{s}" for s in _GENDERED)
PART_PAST_SLOTS = tuple(f"part.past.{s}" for s in _GENDERED)
PART_PASS_SLOTS = tuple(f"part.pass.{s}" for s in _GENDERED)


def slot_tag(slot: str, v_prefix: bool = True) -> str:
    """NVH-Slot-Key → lexc-Abfragetag (``sg.nom`` → ``+Sg+Nom``).

    Eine Funktion für alle Wortarten: die Slot-Keys sind disjoint, die Heads
    (``sg``/``pl`` Nomen, ``cmp``/``sup`` Grad, ``adv``, ``part``, ``pres``/
    ``past``/``subj``, ``opt``, ``imp``) sind disambiguiiert.

    ``v_prefix=False`` unterdrückt das ``+V`` der Partizip-Tags. Die Grammatik
    ist hier uneinheitlich und der Generator folgt ihr: ``PartPresInfl`` in
    ``gen/adj.lexc`` taggt ``+V+Part+Pres+…``, ``PartActInfl``/``PartPassInfl``
    dagegen ``+Part+Past+…``/``+Part+Pass+…`` (so fragt auch gen/coverage_adj.py
    ab). Die Rolle entscheidet also, nicht der Slot-Key allein — siehe
    ``RoleSpec.v_prefix``.
    """
    parts = slot.split(".")
    head = parts[0]
    if head in _NUMBER:
        _expect(slot, parts, ("number", "case"))
        return f"+{_val(_NUMBER, head, slot)}+{_val(_CASE, parts[1], slot)}"
    if head in _DEGREE:
        _expect(slot, parts, ("degree", "gender", "number", "case"))
        return (f"+Adj+{_val(_DEGREE, head, slot)}+{_val(_GENDER, parts[1], slot)}"
                f"+{_val(_NUMBER, parts[2], slot)}+{_val(_CASE, parts[3], slot)}")
    if head in _GENDER:
        # Positiv ohne Grad-Präfix (NVH: masc.sg.nom, nicht pos.masc.sg.nom).
        _expect(slot, parts, ("gender", "number", "case"))
        return (f"+Adj+{_val(_GENDER, head, slot)}+{_val(_NUMBER, parts[1], slot)}"
                f"+{_val(_CASE, parts[2], slot)}")
    if head == "adv":
        if len(parts) == 1:
            return "+Adv"
        _expect(slot, parts, ("adverb", "degree"))
        return f"+Adv+{_val(_DEGREE, parts[1], slot)}"
    if head == "part":
        _expect(slot, parts, ("participle", "tense", "gender", "number", "case"))
        return (("+V" if v_prefix else "") + f"+Part+{_val(_PART, parts[1], slot)}"
                f"+{_val(_GENDER, parts[2], slot)}+{_val(_NUMBER, parts[3], slot)}"
                f"+{_val(_CASE, parts[4], slot)}")
    if head in _FINITE:
        # p3 trägt keinen Numerus (3. Person unterscheidet ihn nie) — p1/p2
        # umgekehrt immer: die Grammatik kennt kein +Ind+Pres+P1 ohne Numerus.
        person = _val(_PERSON, parts[1] if len(parts) > 1 else "", slot)
        if person == "P3":
            _expect(slot, parts, ("tense", "p3"))
        else:
            _expect(slot, parts, ("tense", person.lower(), "number"))
        mood = "+Subj" if head == "subj" else f"+Ind+{_FINITE[head]}"
        tag = f"{mood}+{person}"
        return tag if person == "P3" else tag + f"+{_val(_NUMBER, parts[2], slot)}"
    if head == "opt":
        _expect(slot, parts, ("optative",))
        return "+Opt+P3"
    if head == "imp":
        _expect(slot, parts, ("imperative", "number"))
        return f"+Imp+P2+{_val(_NUMBER, parts[1], slot)}"
    raise ValueError(f"unbekannter Slot-Key: {slot!r}")


def _expect(slot: str, parts: list[str], shape: tuple[str, ...]) -> None:
    if len(parts) != len(shape):
        raise ValueError(f"Slot-Key {slot!r}: erwartet {'.'.join(shape)}")


def _val(mapping: Mapping[str, str], key: str, slot: str) -> str:
    """Tabellenwert mit sprechendem Fehler statt stillem KeyError."""
    try:
        return mapping[key]
    except KeyError:
        raise ValueError(f"Slot-Key {slot!r}: {key!r} ist unbekannt") from None


# ── Paradigmen-/Rollen-Metadaten ────────────────────────────────────────────


@dataclass(frozen=True)
class StemRule:
    """Stufe-0-Regel einer Rolle: ``stem = prefix + (Basisstamm − strip) + suffix``.

    ``strip`` ist eine Kandidatenliste (erster Treffer gewinnt). Eine Regel greift,
    wenn eine ihrer Endungen passt; eine leere Liste passt immer. Die erste passende
    Regel in ``RoleSpec.rules`` gewinnt, die letzte ist der Fallback.
    """

    strip: tuple[str, ...] = ()
    prefix: str = ""
    suffix: str = ""

    def matches(self, base: str) -> bool:
        return not any(self.strip) or any(base.endswith(e) for e in self.strip if e)


def _apply(base: str, rules: tuple[StemRule, ...]) -> str:
    if not rules:
        return base                     # Rolle ohne Stufe-0-Regel (z. B. Nomen)
    for rule in rules:
        if rule.matches(base):
            return rule.prefix + _drop(base, rule.strip) + rule.suffix
    # Letzte Regel = Fallback (z. B. der Themenvokal der Klasse -taw- fällt weg).
    fallback = rules[-1]
    return fallback.prefix + _drop(base, fallback.strip) + fallback.suffix


@dataclass(frozen=True)
class RoleSpec:
    """Eine Rolle = ein Atom-FST + seine Slots + seine Stammregel.

    ``atoms`` sind die datenfreien Infl-Lexikone, die der Build in den
    synthetischen ``LEXICON Root`` des Atoms schreibt (alles andere in der
    Grammatik bleibt unangetastet). ``lexc`` nennt die Quelldatei, damit eine
    Rolle ihre Endungen aus der richtigen Grammatik holt (Partizipien stehen in
    ``gen/adj.lexc``, die finiten Verbformen in ``gen/verb.lexc``).

    Stufe 0: ``rules`` ist eine geordnete Regeliste (siehe ``StemRule``), angewandt
    auf den Basisstamm aus ``Paradigm.strip`` (Lemma bzw. Infinitiv).

    Stufe 1: ``seed_slot`` ist die Prinzipalform (attestierte Oberfläche),
    ``seed_strip`` wird davon abgezogen. Der Seed-Pfad wendet keine Stufe-0-Regel an —
    die Prinzipalform ist bereits der Rollen-Stamm.
    """

    lexc: str
    atoms: tuple[str, ...]
    slots: tuple[str, ...]
    rules: tuple[StemRule, ...] = ()
    seed_slot: str | None = None
    seed_strip: tuple[str, ...] = ()
    v_prefix: bool = True

    def stem_from(self, base: str) -> str:
        return _apply(base, self.rules)

    def stem_from_seed(self, form: str) -> str:
        return _drop(form, self.seed_strip)


@dataclass(frozen=True)
class Paradigm:
    """(pos, Twanksta-Paradigma) → Stammfamilie, Grammatik und Rollen."""

    family: str
    lexc: str
    roles: dict[str, RoleSpec]
    strip: tuple[str, ...] = ()          # Stufe 0: vom Lemma abziehen
    pos: str = ""


def _drop(text: str, endings: Iterable[str]) -> str:
    """Erste passende Endung abschneiden (leeres tuple/'' = nichts abziehen)."""
    for ending in endings:
        if ending and text.endswith(ending):
            return text[: -len(ending)]
    return text


def _norm(lemma: str) -> str:
    return unicodedata.normalize("NFC", lemma).strip()


PARADIGMS: dict[tuple[str, str], Paradigm] = {}


# ── Nomen ───────────────────────────────────────────────────────────────────
# family → {Twanksta-Paradigma: (Nom.Sg.-Endungen, Gen.Sg.-Klassenendung)}
# Die Nom.Sg.-Endungen sind der Stufe-0-Abzug vom Lemma (die Basisform), die
# Gen.Sg.-Klassenendung der Stufe-1-Abzug von der Prinzipalform sg.gen. Die
# Nom-Kandidaten sind eine Liste, weil das Zitationslemma je nach Genus eine
# andere Endung trägt (a-Stamm: Neut. -an / Masc. -as; ī-Stamm: -i / -s) — Reihenfolge
# = Häufigkeit, erster Treffer gewinnt. Belegt an den twanksta-Lemmata selbst:
# `gen/coverage_gen.py --family <fam> --emit-stems build/gen-<fam>-stems.lexc` liefert
# Lemma:Stem-Paare, daraus je Paradigma/Genus die Abzugsliste (z. B. P32 's':1318).
# "0" (blanker Stamm, P45/P63) wird als "" geführt.
_NOUNS: dict[str, dict[str, tuple[tuple[str, ...], str]]] = {
    "istem": {"52": (("i", "s"), "is"), "53": (("ē",), "is"), "54": (("i", "s"), "is"),
              "56": (("s", "is"), "is"), "57": (("s", "is"), "is"),
              "58": (("s", "is", "īs"), "is"), "60": (("s", "is"), "is")},
    "astem": {"32": (("s", "as"), "as"), "35": (("an", "as"), "as"),
              "36": (("s", "as"), "as")},
    "ustem": {"42": (("us",), "us"), "43": (("s", "us"), "us"), "44": (("u",), "us")},
    "jostem": {"37": (("jan",), "jas"), "38": (("s",), "jas"),
               "39": (("īs",), "ijjas"),
               "40": (("is",), "jas"), "41": (("is",), "jas")},
    "aastem": {"45": (("",), "s"), "46": (("ā", "as"), "as"),
               "50": (("i", "ī"), "jas"), "51": (("ī",), "jas")},
    "nstem": {"61": (("s",), "es"), "63": (("",), "es")},
}

for _family, _table in _NOUNS.items():
    _lexc = f"gen/{_family}.lexc"
    for _paradigm, (_nom, _gen) in _table.items():
        PARADIGMS[("noun", _paradigm)] = Paradigm(
            family=_family, lexc=_lexc, pos="noun",
            strip=tuple(n for n in _nom if n),
            roles={"obl": RoleSpec(
                lexc=_lexc, atoms=(f"P{_paradigm}",), slots=NOUN_SLOTS,
                seed_slot="sg.gen", seed_strip=(_gen,) if _gen else ())},
        )

# ── Adjektive + Adverbien ───────────────────────────────────────────────────
# Ein Paradigma, Rollen je Wortart/Grad:
#   pos   Adj*Infl → 24 Genusblöcke
#   adv   Adv{A,I,U} → der Adverb-Positiv (Endung steckt im Lexikon)
#   cmp   AdjCmpInfl → cmp.* (24) + adv.cmp
#   sup   AdjSupInfl → sup.* (24) + adv.sup, Stamm = "uka" + Komparativstamm
# Der Komparativ-/Superlativstamm ist regelhaft: Positivstamm + Grad-Suffix
# (a-Stamm -ais, i-/jo-Stamm -jais, u-Stamm -uis).
_ADJ: dict[str, tuple[str | None, str, str, str, str]] = {
    # paradigm: (pos-Atom, Adv-Atom, Nom.Sg.-Abzug, cmp-Suffix, Gen.Sg.-Seed-Abzug)
    "25": ("AdjFixedInfl", "AdvA", "s", "ais", "as"),
    "26": ("AdjMobileInfl", "AdvA", "s", "ais", "as"),
    "27": ("AdjIInfl", "AdvI", "is", "jais", "jas"),
    "29": ("AdjIMobInfl", "AdvI", "s", "jais", "is"),
    # Par.30 = reines u-Adverb (keine Deklination in gen/coverage_adj.py; Stamm wie
    # Par.31 aus dem Nom.Sg. minus -us, Adverb -u, Grad -uis).
    "30": (None, "AdvU", "us", "uis", "was"),
    "31": ("AdjUMobInfl", "AdvU", "us", "uis", "was"),
}

for _paradigm, (_pos_atom, _adv_atom, _nom, _cmp_suffix, _seed) in _ADJ.items():
    _lexc = "gen/adj.lexc"
    _roles: dict[str, RoleSpec] = {}
    if _pos_atom:                                    # Par.30 hat keine Deklension
        _roles["pos"] = RoleSpec(
            lexc=_lexc, atoms=(_pos_atom,), slots=ADJ_POS_SLOTS,
            seed_slot="masc.sg.gen", seed_strip=(_seed,))
    _roles["adv"] = RoleSpec(lexc=_lexc, atoms=(_adv_atom,), slots=("adv",))
    _roles["cmp"] = RoleSpec(
        lexc=_lexc, atoms=("AdjCmpInfl",), slots=ADJ_CMP_SLOTS + ("adv.cmp",),
        rules=(StemRule(suffix=_cmp_suffix),))
    _roles["sup"] = RoleSpec(
        lexc=_lexc, atoms=("AdjSupInfl",), slots=ADJ_SUP_SLOTS + ("adv.sup",),
        rules=(StemRule(prefix="uka", suffix=_cmp_suffix),))
    PARADIGMS[("adj", _paradigm)] = Paradigm(
        family="adj", lexc=_lexc, pos="adj",
        strip=(_nom,) if _nom else (), roles=_roles)

# ── Verben (finite) ─────────────────────────────────────────────────────────
# role → (Infl-Lexikone, Seed-Abzug von pres.p3/past.p3/subj.p3)
# Der Präteritumstamm kommt NIE aus dem Präsens: er ist eine eigene Rolle
# (seed_slot past.p3) dort, wo die Grammatik ihn aus einem -pret-Stamm speist.
# Wo die Grammatik das Präteritum aus dem Präsens- bzw. Nonfin-Stamm speist
# (Pret_Ai / Pret_0), trägt die jeweilige Rolle das Atomsymbol mit.
_FINITE_ROLES: dict[str, tuple[tuple[str, ...], str]] = {
    "pres": (("Pres_A", "Pres_I", "Pres_Aa", "Pres_Ja", "Pres_Jja", "Pres_Ui"),
             "a"),
    "pret": (("Pret_A", "Pret_Ai", "Pret_I", "Pret_0"), "a"),
    "nonfin": (("SubjOpt",), "lai"),
}
_IMPERATIVE_ATOMS = ("Imp_Ais", "Imp_Is", "Imp_S", "Imp_Siti", "Imp_Jais")

def _atom_slots(atom: str) -> tuple[str, ...]:
    """Slots, die ein Infl-Lexikon des jeweiligen Paradigmas versorgt."""
    if atom.startswith("Pres_"):
        return VERB_PRES_SLOTS
    if atom.startswith("Pret_"):
        return VERB_PAST_SLOTS
    if atom == "SubjOpt":
        return VERB_SUBJ_SLOTS + VERB_OPT_SLOTS
    if atom in _IMPERATIVE_ATOMS:
        return IMP_SLOTS
    raise KeyError(f"unbekanntes Infl-Lexikon: {atom!r}")


# Ein Bucket = ein Stamm + die Infl-Lexikone, die ihn speisen — dieselbe
# Einteilung wie in gen/coverage_verb.py (P85PresStems / P85NonfinStems /
# VerbStrongStems).  Wert: (Infl-Lexikone, Seed-Abzug, Stufe-0-Abzug vom
# Basisstamm = Infinitiv − tun/twei).
#
# Stufe 0 ist ehrlich bescheiden: der NONFIN-Bucket ist der Infinitivstamm
# selbst (deckt 132/138/139/136/142 zu 100 %), der PRES-Bucket zieht den
# Themenvokal der Klasse ab (138 -i, 143 -u, 85 -a/-ā …).  Was eine reine
# Suffix-Regel nicht leistet — Gemination (-ipp-, -ijj-, -āss-), n-Insertion
# (-ūn- im Präs. v. 111), j-Insertion (Präs. v. 144) und vor allem der
# ABLAUT-Präteritumstamm —, läuft über Stufe 1 (attestierte Prinzipalform) oder
# Stufe 2 (Stamm-Override); ein Default, der danebenliegt, ist kein Fehler,
# sondern die Aufforderung, einen Seed zu setzen.
_VERBS: dict[str, dict[str, tuple[tuple[str, ...], str, tuple[str, ...]]]] = {
    "85": {"pres": (("Pres_A", "Pret_Ai", "Imp_Ais"), "a", ("a", "ā")),
           "nonfin": (("SubjOpt",), "lai", ())},
    "132": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), "i", ()),
            "nonfin": (("SubjOpt",), "lai", ())},
    "138": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), "i", ("i",)),
            "nonfin": (("SubjOpt",), "lai", ())},
    "134": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), "i", ()),
            "nonfin": (("SubjOpt",), "lai", ())},
    "139": {"pres": (("Pres_A", "Pret_Ai"), "a", ()),
            "nonfin": (("SubjOpt", "Imp_S"), "lai", ())},
    "143": {"pres": (("Pres_Ui",), "ui", ("u",)),
            "nonfin": (("Pret_0", "SubjOpt", "Imp_Siti"), "lai", ())},
    "144": {"pres": (("Pres_A", "Imp_Ais"), "a", ()),
            "pret": (("Pret_A",), "a", ()),
            "nonfin": (("SubjOpt",), "lai", ())},
    "142": {"pres": (("Pres_A", "Imp_Ais"), "a", ("ā", "a")),
            "nonfin": (("Pret_I", "SubjOpt"), "lai", ())},
    "136": {"pres": (("Pres_A", "Imp_Ais"), "a", ("ī",)),
            "pret": (("Pret_I",), "i", ()),
            "nonfin": (("SubjOpt",), "lai", ())},
    "111": {"pres": (("Pres_Ja", "Imp_Jais"), "ja", ()),
            "pret": (("Pret_A",), "a", ()),
            "nonfin": (("SubjOpt",), "lai", ())},
    "71": {"pres": (("Pres_Aa", "Pret_I", "Imp_Ais"), "a", ()),
           "nonfin": (("SubjOpt",), "lai", ())},
    "75": {"pres": (("Pres_Jja", "Pret_I"), "ja", ()),
           "nonfin": (("SubjOpt", "Imp_Jais"), "lai", ())},
    "81": {"pres": (("Pres_Jja", "Imp_Jais"), "ja", ()),
           "pret": (("Pret_I",), "i", ()),
           "nonfin": (("SubjOpt",), "lai", ())},
    "87a": {"pres": (("Pres_A", "Pret_A", "Imp_Ais"), "a", ("a", "ā")),
            "nonfin": (("SubjOpt",), "lai", ())},
    "87b": {"pres": (("Pres_A", "Pret_Ai", "Imp_Ais"), "a", ("a", "ā")),
            "nonfin": (("SubjOpt",), "lai", ())},
    "131": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), "i", ()),
            "nonfin": (("SubjOpt",), "lai", ())},
}
# Starke Verben: identische Endungen, eigenes Präteritum-Lexikon (Ablaut).
for _paradigm in ("88", "89", "90", "91", "92", "93", "94", "96", "97", "99", "100",
                  "102", "106", "107", "108", "109", "113", "122", "141"):
    _VERBS[_paradigm] = {"pres": (("Pres_A", "Imp_Ais"), "a", ("a", "ā")),
                          "pret": (("Pret_A",), "a", ()),
                          "nonfin": (("SubjOpt",), "lai", ())}

# ── Verben (Partizipien) ────────────────────────────────────────────────────
# Regel-Default, nicht Seed (der attestierte Masc.Gen.Sg.-Seed des
# Wegschmeißen-Codes ist KEIN Grundmechanismus). Drei Regeln auf dem Verb-Infinitiv:
#   partpres  -(Basisstamm − t) + nt        (-nts-Partizip, -tun-Klassen)
#   partact   Basisstamm − at               (-uns-Partizip)
#   partpass  Basisstamm − at               (-ts-Partizip)
# Der Rest (Klasse-2 -int, die twei-Klasse mit i/a-Wechsel) läuft über
# Stamm-Overrides (Stufe 2) bzw. Slot-Overrides (Stufe 3).
_PARTICIPLE_ROLES: dict[str, RoleSpec] = {
    "partpres": RoleSpec(
        lexc="gen/adj.lexc", atoms=("PartPresInfl",), slots=PART_PRES_SLOTS,
        rules=(StemRule(strip=("u",), suffix="wint"),    # Klasse -taw-: au → awint
               StemRule(suffix="nt"))),
    "partact": RoleSpec(
        lexc="gen/adj.lexc", atoms=("PartActInfl",), slots=PART_PAST_SLOTS,
        rules=(StemRule(strip=("a",)),), v_prefix=False),  # Basisstamm − athema
    "partpass": RoleSpec(
        lexc="gen/adj.lexc", atoms=("PartPassInfl",), slots=PART_PASS_SLOTS,
        rules=(StemRule(strip=("a",)),), v_prefix=False),
}

_VERB_LEXC = "gen/verb.lexc"
_SEED_SLOT = {"pres": "pres.p3", "pret": "past.p3", "nonfin": "subj.p3"}
for _paradigm, _role_table in _VERBS.items():
    _roles: dict[str, RoleSpec] = {}
    for _role, (_atoms, _seed_strip, _strip) in _role_table.items():
        _slots: list[str] = []
        for _atom in _atoms:
            for _slot in _atom_slots(_atom):
                if _slot not in _slots:
                    _slots.append(_slot)
        _roles[_role] = RoleSpec(
            lexc=_VERB_LEXC, atoms=tuple(_atoms), slots=tuple(_slots),
            rules=(StemRule(strip=_strip),),
            seed_slot=_SEED_SLOT[_role], seed_strip=(_seed_strip,))
    _roles.update(_PARTICIPLE_ROLES)
    PARADIGMS[("verb", _paradigm)] = Paradigm(
        family="verb", lexc=_VERB_LEXC, pos="verb",
        strip=("tun", "twei"), roles=_roles)

# Par.87: Prät.Pl. -amai nach Nasal+d (kand-, brend-, skēnd-), sonst -imai.
# Phonologisch bedingt, keine Einzelfälle: -87a/87b wird aus dem Infinitiv
# aufgelöst (Themenvokal weg, dann auf "nd" prüfen).
_VERB_VARIANTS = {"87"}


def _resolve_87(lemma: str) -> str:
    """Par.87: Prät.Pl. -amai bei Stamm auf Nasal+d (kand-, brend-, skēnd-)."""
    base = _drop(lemma, ("twei", "tun"))
    return "87a" if re.search(r"nd[aāuīīou]*$", base) else "87b"


_VARIANT_RESOLVERS: dict[tuple[str, str], Callable[[str], str]] = {
    ("verb", "87"): _resolve_87,
}


def family_of(pos: str, paradigm: str | int) -> str:
    """(pos, Twanksta-Paradigma) → Stammfamilie (Teil des Atom-Namens)."""
    return _paradigm(pos, paradigm, lemma="").family


def paradigm_spec(pos: str, paradigm: str | int, lemma: str = "") -> Paradigm:
    """Paradigm-Datensatz (family/lexc/roles) — auch für den Build."""
    return _paradigm(pos, paradigm, lemma)


def _paradigm(pos: str, paradigm: str | int, lemma: str = "") -> Paradigm:
    pos = pos.lower()
    key = (pos, str(paradigm))
    resolver = _VARIANT_RESOLVERS.get(key)
    if resolver is not None:
        key = (pos, resolver(_norm(lemma)))
    try:
        return PARADIGMS[key]
    except KeyError:
        raise KeyError(
            f"unbekanntes Paradigma {paradigm!r} für pos={pos!r} "
            f"(bekannt: {sorted(p for q, p in PARADIGMS if q == pos)})") from None


def resolve_paradigm(pos: str, paradigm: str | int, lemma: str = "") -> str:
    """Twanksta-Paradigma → Atompfad-Paradigma (87 → 87a/87b)."""
    return _paradigm_key(pos, paradigm, lemma)


def _paradigm_key(pos: str, paradigm: str | int, lemma: str = "") -> str:
    key = (pos.lower(), str(paradigm))
    resolver = _VARIANT_RESOLVERS.get(key)
    return resolver(_norm(lemma)) if resolver is not None else str(paradigm)


# ── Atom-FSTs ───────────────────────────────────────────────────────────────


def atom_name(pos: str, paradigm: str | int, role: str, lemma: str = "") -> str:
    """Atom-Dateiname (ohne Pfad): ``gen-<family>-<paradigm>[-<role>]``.

    ``lemma`` löst Varianten auf (Verb 87a/87b); ohne Lemma muss die konkrete
    Nummer stehen, sonst greift die Default-Auflösung der Variante.
    """
    par = _paradigm(pos, paradigm, lemma)
    if role not in par.roles:
        raise KeyError(f"unbekannte Rolle {role!r} für {pos}/{paradigm} "
                       f"(bekannt: {sorted(par.roles)})")
    key = _paradigm_key(pos, paradigm, lemma)
    if len(par.roles) == 1:
        return f"gen-{par.family}-{key}"
    return f"gen-{par.family}-{key}-{role}"


def atom_path(pos: str, paradigm: str | int, role: str, lemma: str = "") -> Path:
    return ATOM_DIR / f"{atom_name(pos, paradigm, role, lemma)}.hfstol"


def atom_targets() -> list[tuple[str, str, str, Path]]:
    """Alle zu bauenden Atome: (pos, paradigm, role, Pfad)."""
    out = []
    for (pos, paradigm), par in sorted(PARADIGMS.items()):
        for role in sorted(par.roles):
            out.append((pos, paradigm, role, atom_path(pos, paradigm, role)))
    return out


@lru_cache(maxsize=None)
def _atom(pos: str, paradigm: str, role: str):
    """Atom-FST laden (pyhfst, lazy import — der Build braucht kein pyhfst)."""
    import pyhfst

    path = atom_path(pos, paradigm, role)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} fehlt — bauen mit: make atoms (gen/atom_fst.py)")
    return pyhfst.HfstInputStream(str(path)).read()


# ── Stufen 0/1/2 ────────────────────────────────────────────────────────────


def default_stems(pos: str, paradigm: str | int, lemma: str | None = None,
                  seeds: Mapping[str, str] | None = None) -> dict[str, str]:
    """Stamm je Rolle: Stufe 0 (Lemma) und Stufe 1 (Prinzipalformen).

    ``seeds`` bildet Slot-Key → attestierte Oberfläche ab (``{"sg.gen": "dumslis"}``
    für Nomen, ``{"pres.p3": "ainagimmat", "subj.p3": "ainagimmatlai"}`` für Verben).
    Ein Seed gilt für die Rolle, deren ``seed_slot`` er ist; Rollen ohne Seed
    fallen auf den Lemma-Stamm zurück. Priorität: Seed > Lemma.
    """
    par = _paradigm(pos, paradigm, lemma or "")
    base = _drop(_norm(lemma), par.strip) if lemma else ""
    seeds = seeds or {}
    out: dict[str, str] = {}
    for role, spec in par.roles.items():
        form = seeds.get(spec.seed_slot) if spec.seed_slot else None
        if form:
            out[role] = spec.stem_from_seed(_norm(form))
        elif base:
            out[role] = spec.stem_from(base)
    return out


def check_stem(stem: str, role: str = "") -> str:
    """Stamm gegen STEM_ALPHABET prüfen (Kopierer-Verlust wäre sonst stumm)."""
    bad = [c for c in stem if c not in STEM_ALPHABET_SET]
    if bad:
        where = f" für Rolle {role!r}" if role else ""
        raise ValueError(
            f"Stamm {stem!r}{where} enthält {len(bad)} Zeichen außerhalb von "
            f"STEM_ALPHABET: {''.join(sorted(set(bad)))!r} "
            f"(NFC-normalisieren oder STEM_ALPHABET erweitern)")
    return stem


def generate(pos: str, paradigm: str | int, lemma: str | None = None,
             stems: Mapping[str, str] | None = None,
             seeds: Mapping[str, str] | None = None,
             gender: str | None = None) -> dict[str, tuple[str, ...]]:
    """Wortformen erzeugen: ``(pos, Twanksta-Paradigma, Lemma)`` → Slot → Formen.

    ``pos`` ist ``noun``/``adj``/``verb``, ``paradigm`` die Twanksta-Nummer,
    ``lemma`` die Basisform (Nom.Sg. / Infinitiv / Masc.Nom.Sg.). ``stems``
    (Stufe 2) überschreibt einzelne Rollen-Stämme, ``seeds`` (Stufe 1) liefert
    attestierte Prinzipalformen je Slot. ``gender`` wird nicht gebraucht — die
    Genus-Dimension ist reines Durchreich-Tag in den Slot-Keys; bei Nomen ohne
    bekanntes Genus wird nichts erfunden.

    Ein Slot mit leerem Tupel heißt: das Paradigma hat diese Form nicht (z. B.
    Part.Pl.Dat. ohne Geminate) — kein Fehler, aber auch keine Form.
    """
    par = _paradigm(pos, paradigm, lemma or "")
    resolved = default_stems(pos, paradigm, lemma=lemma, seeds=seeds)
    for role, stem in (stems or {}).items():
        if role not in par.roles:
            raise KeyError(f"unbekannte Rolle {role!r} für {pos}/{paradigm} "
                           f"(bekannt: {sorted(par.roles)})")
        resolved[role] = stem
    if gender is not None and gender not in _GENDER:
        raise ValueError(f"unbekanntes gender {gender!r} (masc|fem|neut)")
    key_paradigm = _paradigm_key(pos, paradigm, lemma or "")
    out: dict[str, tuple[str, ...]] = {}
    for role in par.roles:
        stem = resolved.get(role)
        if stem is None:
            continue                      # weder Lemma noch Seed → nichts zu tun
        check_stem(_norm(stem), role)
        spec = par.roles[role]
        tr = _atom(pos, key_paradigm, role)
        for slot in spec.slots:
            out[slot] = tuple(sorted({surface for surface, _w in tr.lookup(
                _norm(stem) + slot_tag(slot, spec.v_prefix))}))
    return out


def _main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show", help="Paradigmen-/Atom-Tabelle")
    show.add_argument("pos", nargs="?", choices=["noun", "adj", "verb"])
    gen = sub.add_parser("generate", help="Formen für ein Lexem")
    gen.add_argument("pos", choices=["noun", "adj", "verb"])
    gen.add_argument("paradigm")
    gen.add_argument("lemma")
    gen.add_argument("--stem", action="append", default=[],
                     metavar="ROLE=STEM", help="Stufe-2-Stamm-Override")
    gen.add_argument("--seed", action="append", default=[],
                     metavar="SLOT=FORM", help="Stufe-1-Prinzipalform")
    gen.add_argument("--gender", choices=["masc", "fem", "neut"])
    args = parser.parse_args(argv)

    if args.cmd == "show":
        for pos, paradigm, role, path in atom_targets():
            if args.pos and pos != args.pos:
                continue
            print(f"{pos:5} {paradigm:5} {role:9} {path.name}")
        return 0
    seeds = dict(kv.split("=", 1) for kv in args.seed)
    stems = dict(kv.split("=", 1) for kv in args.stem)
    result = generate(args.pos, args.paradigm, lemma=args.lemma, stems=stems,
                      seeds=seeds, gender=args.gender)
    for slot, forms in result.items():
        print(f"{slot:28} {' | '.join(forms)}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
