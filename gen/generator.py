"""Datenfreier Stufe-0/1/2-Generator für preußische Wortformen.

Eingabe ist der NVH-Eintragsschema-Ausschnitt:

    entry:    <lemma>                      Nom.Sg. / Infinitiv / Masc.Nom.Sg.
    pos:      noun | adj | verb           Genus steht NICHT im pos
    gender:   masc | fem | neut           nur Nomen, optional (fehlt = unbekannt)
    paradigm: <Twanksta-Paradigmennummer>  zusammen mit pos → Stammfamilie

``legacy.*`` (desc/article/veraltetes paradigm) wird nicht gelesen.

Ausgabe ist ``{NVH-Slot-Key: (Form, …)}`` im dotted ``tag:``-Format (``sg.nom``,
``pl.acc``, ``comp.msc.sg.nom``, ``superl.neu.sg.nom``,
``part.prs.act.msc.sg.nom``, ``prs.sg1``, ``prt.sp3``, ``subj.sp3``, ``opt``,
``imprt.sg2``/``imprt.pl2``). Die gender-Komponente ist reines Durchreich-Tag:
getrieben wird sie nicht — das Atom liefert alle Genusblöcke, die das Paradigma hat.
Für Nomen ohne bekanntes Genus wird nichts erfunden (Nomen emittieren kein Genus —
es ist ein Entry-Fakt, kein Slot).

KEINE KORPUSQUELLE. Die einzige Datenquelle sind die zur Build-Zeit kompilierten,
datenfreien Atom-FSTs ``build/gen-<family>-<paradigm>[-<role>].hfstol``, die aus den
handgeschriebenen Grammatiken ``gen/*.lexc`` + ``gen/accent.regex`` stammen
(siehe ``gen/atom_fst.py``). Zur Laufzeit genügt ein pyhfst-Lookup pro Slot:
``Stamm + Tag → Oberfläche``.

Stufen:

  0   Regel: Stamm je Rolle aus Lemma + Paradigma (``RoleSpec.rules``)
  1   gelieferter Stamm: je Rolle, überschreibt die Regel (``generate(stems=…)``)
  2   Override: fertige Form für Zellen, die Stamm + Paradigma nicht hergeben
      (im NVH-Kompressor, gen/compress_forms.py)

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
_GENDERS = ("msc", "fem", "neu")
_NUMBERS = ("sg", "pl")
_CASES = ("nom", "gen", "dat", "acc")

# Genus im NVH-Slot-Key und im FST-Tag
_GENDER = {"msc": "Msc", "fem": "Fem", "neu": "Neu"}
# Genus als ENTRY-Feld (nur Nomen, nicht im Slot) — unabhängig von der Slot-Schreibweise
_ENTRY_GENDERS = frozenset({"masc", "fem", "neut"})
_NUMBER = {"sg": "Sg", "pl": "Pl"}
_CASE = {"nom": "Nom", "gen": "Gen", "dat": "Dat", "acc": "Acc"}
_DEGREE = {"comp": "Comp", "superl": "Superl"}
# Partizip: tense.voice → Prc-Typ + Voice
_PART_TENSE = {"prs": "Prs", "prf": "Prf"}
_PART_VOICE = {"act": "Act", "pss": "Pss"}
# Indikativ-Tempus (im NVH-Key implizit, im FST-Tag explizit)
_FINITE_TENSE = {"prs": "Prs", "prt": "Prt"}
# Fusion Person/Num: sg1/sp3/pl2 …
_PERSNUM = {"sg1": "Sg1", "sg2": "Sg2", "sp3": "SP3", "pl1": "Pl1", "pl2": "Pl2"}


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
ADJ_CMP_SLOTS = tuple(f"comp.{s}" for s in _GENDERED)
ADJ_SUP_SLOTS = tuple(f"superl.{s}" for s in _GENDERED)
ADJ_SLOTS = (ADJ_POS_SLOTS + ADJ_CMP_SLOTS + ADJ_SUP_SLOTS
             + ("adv", "adv.comp", "adv.superl"))
ADVERB_SLOTS = ("adv", "adv.comp", "adv.superl")
IMP_SLOTS = ("imprt.sg2", "imprt.pl2")
VERB_PRES_SLOTS = ("prs.sg1", "prs.sg2", "prs.sp3", "prs.pl1", "prs.pl2")
VERB_PAST_SLOTS = ("prt.sg1", "prt.sg2", "prt.sp3", "prt.pl1", "prt.pl2")
VERB_SUBJ_SLOTS = ("subj.sg1", "subj.sg2", "subj.sp3", "subj.pl1", "subj.pl2")
VERB_OPT_SLOTS = ("opt",)
VERB_SLOTS = (VERB_PRES_SLOTS + VERB_PAST_SLOTS + VERB_SUBJ_SLOTS
             + VERB_OPT_SLOTS + IMP_SLOTS)
PART_PRES_SLOTS = tuple(f"part.prs.act.{s}" for s in _GENDERED)
PART_PAST_SLOTS = tuple(f"part.prf.act.{s}" for s in _GENDERED)
PART_PASS_SLOTS = tuple(f"part.prf.pss.{s}" for s in _GENDERED)


def slot_tag(slot: str) -> str:
    """NVH-Slot-Key → lexc-Abfragetag (``sg.nom`` → ``+N+Sg+Nom``).

    Eine Funktion für alle Wortarten: die Slot-Keys sind disjoint, die Heads
    (``sg``/``pl`` Nomen, ``comp``/``superl`` Grad, ``adv``, ``part``, ``prs``/
    ``prt``/``subj``, ``opt``, ``imprt``) sind disambiguiiert.

    Der POS-Marker steht im FST-Tag vorn (``+N``/``+V``/``+A``/``+Adv``). Genus
    steht beim Nomen nicht im Slot (Entry-Fakt) und wird dort auch nicht emittiert.
    """
    parts = slot.split(".")
    head = parts[0]
    if head in _NUMBER:                                        # Nomen
        _expect(slot, parts, ("number", "case"))
        return f"+N+{_val(_NUMBER, head, slot)}+{_val(_CASE, parts[1], slot)}"
    if head in _DEGREE:                                        # Adj. comp/superl
        _expect(slot, parts, ("degree", "gender", "number", "case"))
        return (f"+A+{_val(_DEGREE, head, slot)}+{_val(_GENDER, parts[1], slot)}"
                f"+{_val(_NUMBER, parts[2], slot)}+{_val(_CASE, parts[3], slot)}")
    if head in _GENDERS:                                       # Adj. Positiv
        # Positiv ohne Grad-Präfix (NVH: msc.sg.nom, nicht pos.msc.sg.nom).
        _expect(slot, parts, ("gender", "number", "case"))
        return (f"+A+{_val(_GENDER, head, slot)}+{_val(_NUMBER, parts[1], slot)}"
                f"+{_val(_CASE, parts[2], slot)}")
    if head == "adv":                                          # Adverb
        if len(parts) == 1:
            return "+Adv"
        _expect(slot, parts, ("adverb", "degree"))
        return f"+Adv+{_val(_DEGREE, parts[1], slot)}"
    if head == "part":                                         # Partizip
        _expect(slot, parts, ("participle", "tense", "voice", "gender", "number", "case"))
        return (f"+V+{_val(_PART_TENSE, parts[1], slot)}Prc"
                f"+{_val(_PART_VOICE, parts[2], slot)}"
                f"+{_val(_GENDER, parts[3], slot)}+{_val(_NUMBER, parts[4], slot)}"
                f"+{_val(_CASE, parts[5], slot)}")
    if head in ("prs", "prt"):                                 # Verb finit, Ind.
        _expect(slot, parts, ("tense", "person.number"))
        return (f"+V+Ind+{_val(_FINITE_TENSE, head, slot)}"
                f"+{_val(_PERSNUM, parts[1], slot)}")
    if head == "subj":
        _expect(slot, parts, ("mood", "person.number"))
        return f"+V+Subj+{_val(_PERSNUM, parts[1], slot)}"
    if head == "opt":
        _expect(slot, parts, ("optative",))
        return "+V+Opt+SP3"
    if head == "imprt":
        _expect(slot, parts, ("imperative", "person.number"))
        return f"+V+Imprt+{_val(_PERSNUM, parts[1], slot)}"
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
    """Stufe-0-Regel einer Rolle: ``stem = prefix + (Basisstamm − strip) + glide + suffix``.

    ``strip`` ist eine Kandidatenliste (erster Treffer gewinnt). Eine Regel greift,
    wenn eine ihrer Endungen passt; eine leere Liste passt immer. Die erste passende
    Regel in ``RoleSpec.rules`` gewinnt, die letzte ist der Fallback.

    ``after`` schränkt die Regel zusätzlich auf Basisstämme ein, die mit einer der
    aufgeführten Endungen enden — der Kontext wird dabei **nicht** abgezogen (anders
    als ``strip``). ``glide`` ist ein Übergangslaut zwischen Stamm und ``suffix``
    (der Gleitlaut -w- vor dem -uns-Partizip).
    """

    strip: tuple[str, ...] = ()
    prefix: str = ""
    suffix: str = ""
    after: tuple[str, ...] = ()
    glide: str = ""

    def matches(self, base: str) -> bool:
        if self.after and not base.endswith(self.after):
            return False
        return not any(self.strip) or any(base.endswith(e) for e in self.strip if e)

    def apply(self, base: str) -> str:
        return self.prefix + _drop(base, self.strip) + self.glide + self.suffix


def _apply(base: str, rules: tuple[StemRule, ...]) -> str:
    if not rules:
        return base                     # Rolle ohne Stufe-0-Regel (z. B. Nomen)
    for rule in rules:
        if rule.matches(base):
            return rule.apply(base)
    # Letzte Regel = Fallback (z. B. der Themenvokal der Klasse -taw- fällt weg).
    return rules[-1].apply(base)


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

    Stufe 1 ist ein **gelieferter Stamm** je Rolle (``generate(stems=…)``): er ist
    bereits der Rollen-Stamm und wird nicht aus einer Form zurückgewonnen. Wer einen
    Stamm aus einer belegten Form braucht, benutzt ``stem_from_form``.
    """

    lexc: str
    atoms: tuple[str, ...]
    slots: tuple[str, ...]
    rules: tuple[StemRule, ...] = ()

    def stem_from(self, base: str) -> str:
        return _apply(base, self.rules)


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
# family → {Twanksta-Paradigma: Nom.Sg.-Endungen}
# Die Nom.Sg.-Endungen sind der Stufe-0-Abzug vom Lemma (die Basisform). Sie
# sind eine Liste, weil das Zitationslemma je nach Genus eine andere Endung trägt
# (a-Stamm: Neut. -an / Masc. -as; ī-Stamm: -i / -s) — Reihenfolge = Häufigkeit,
# erster Treffer gewinnt. Die Listen sind an den twanksta-Lemmata selbst abgeglichen
# (Lemma:Stem-Paare je Paradigma/Genus, z. B. P32 's': 1318).
# "0" (blanker Stamm, P45/P63) wird als "" geführt.
# Die Gen.Sg.-Endungen der Klassen stehen NICHT mehr hier: ein aus einer belegten
# Form gewonnener Stamm liest seine Endung aus der Grammatik (stem_from_form).
_NOUNS: dict[str, dict[str, tuple[str, ...]]] = {
    "istem": {"52": ("i", "s"), "53": ("ē",), "54": ("i", "s"),
              "56": ("s", "is"), "57": ("s", "is"),
              "58": ("s", "is", "īs"), "60": ("s", "is")},
    "astem": {"32": ("s", "as"), "35": ("an", "as"),
              "36": ("s", "as")},
    "ustem": {"42": ("us",), "43": ("s", "us"), "44": ("u",)},
    "jostem": {"37": ("jan",), "38": ("s",),
               "39": ("īs",),
               "40": ("is",), "41": ("is",)},
    "aastem": {"45": ("",), "46": ("ā", "as"),
               "50": ("i", "ī"), "51": ("ī",)},
    "nstem": {"61": ("s",), "63": ("",)},
}

for _family, _table in _NOUNS.items():
    _lexc = f"gen/{_family}.lexc"
    for _paradigm, _nom in _table.items():
        PARADIGMS[("noun", _paradigm)] = Paradigm(
            family=_family, lexc=_lexc, pos="noun",
            strip=tuple(n for n in _nom if n),
            roles={"obl": RoleSpec(
                lexc=_lexc, atoms=(f"P{_paradigm}",), slots=NOUN_SLOTS)},
        )

# ── Adjektive + Adverbien ───────────────────────────────────────────────────
# Ein Paradigma, Rollen je Wortart/Grad:
#   pos   Adj*Infl → 24 Genusblöcke
#   adv   Adv{A,I,U} → der Adverb-Positiv (Endung steckt im Lexikon)
#   cmp   AdjCmpInfl → comp.* (24) + adv.comp
#   sup   AdjSupInfl → superl.* (24) + adv.superl, Stamm = "uka" + Komparativstamm
# Der Komparativ-/Superlativstamm ist regelhaft: Positivstamm + Grad-Suffix
# (a-Stamm -ais, i-/jo-Stamm -jais, u-Stamm -uis).
_ADJ: dict[str, tuple[str | None, str, str, str]] = {
    # paradigm: (pos-Atom, Adv-Atom, Nom.Sg.-Abzug, cmp-Suffix)
    "25": ("AdjFixedInfl", "AdvA", "s", "ais"),
    "26": ("AdjMobileInfl", "AdvA", "s", "ais"),
    "27": ("AdjIInfl", "AdvI", "is", "jais"),
    "29": ("AdjIMobInfl", "AdvI", "s", "jais"),
    # Par.30 = reines u-Adverb (keine Deklination; Stamm wie Par.31 aus dem
    # Nom.Sg. minus -us, Adverb -u, Grad -uis).
    "30": (None, "AdvU", "us", "uis"),
    "31": ("AdjUMobInfl", "AdvU", "us", "uis"),
}

for _paradigm, (_pos_atom, _adv_atom, _nom, _cmp_suffix) in _ADJ.items():
    _lexc = "gen/adj.lexc"
    _roles: dict[str, RoleSpec] = {}
    if _pos_atom:                                    # Par.30 hat keine Deklination
        _roles["pos"] = RoleSpec(lexc=_lexc, atoms=(_pos_atom,), slots=ADJ_POS_SLOTS)

    _roles["adv"] = RoleSpec(lexc=_lexc, atoms=(_adv_atom,), slots=("adv",))
    _roles["cmp"] = RoleSpec(
        lexc=_lexc, atoms=("AdjCmpInfl",), slots=ADJ_CMP_SLOTS + ("adv.comp",),
        rules=(StemRule(suffix=_cmp_suffix),))
    _roles["sup"] = RoleSpec(
        lexc=_lexc, atoms=("AdjSupInfl",), slots=ADJ_SUP_SLOTS + ("adv.superl",),
        rules=(StemRule(prefix="uka", suffix=_cmp_suffix),))
    PARADIGMS[("adj", _paradigm)] = Paradigm(
        family="adj", lexc=_lexc, pos="adj",
        strip=(_nom,) if _nom else (), roles=_roles)

# ── Verben (finite) ─────────────────────────────────────────────────────────
# Der Präteritumstamm kommt NIE aus dem Präsens: er ist eine eigene Rolle
# (``pret``) dort, wo die Grammatik ihn aus einem -prt-Stamm speist. Wo die
# Grammatik das Präteritum aus dem Präsens- bzw. Nonfin-Stamm speist
# (Pret_Ai / Pret_0), trägt die jeweilige Rolle das Atomsymbol mit.
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


# Ein Bucket = die Infl-Lexikone, die die Rolle speisen, + ihre Stufe-0-Regel auf
# dem Basisstamm (Infinitiv − tun/twei).
#
# Stufe 0 ist ehrlich besessen: der NONFIN-Bucket ist der Infinitivstamm selbst
# (deckt 132/138/139/136/142 zu 100 %), der PRES-Bucket zieht den Themenvokal der
# Klasse ab (138 -i, 143 -u, 85 -a/-ā …). Was eine reine Suffix-Regel nicht leistet
# — Gemination (-ipp-, -ijj-, -āss-), n-Insertion (-ūn- im Präs. v. 111), j-Insertion
# (Präs. v. 144) und vor allem der ABLAUT-Präteritumstamm —, läuft über einen
# gelieferten Stamm (Stufe 1); ein Default, der danebenliegt, ist kein Fehler,
# sondern die Aufforderung, den Stamm zu liefern.
_VERBS: dict[str, dict[str, tuple[tuple[str, ...], tuple[str, ...]]]] = {
    "85": {"pres": (("Pres_A", "Pret_Ai", "Imp_Ais"), ("a", "ā")),
           "nonfin": (("SubjOpt",), ())},
    "132": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), ()),
            "nonfin": (("SubjOpt",), ())},
    "138": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), ("i",)),
            "nonfin": (("SubjOpt",), ())},
    "134": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), ()),
            "nonfin": (("SubjOpt",), ())},
    "139": {"pres": (("Pres_A", "Pret_Ai"), ()),
            "nonfin": (("SubjOpt", "Imp_S"), ())},
    "143": {"pres": (("Pres_Ui",), ("u",)),
            "nonfin": (("Pret_0", "SubjOpt", "Imp_Siti"), ())},
    "144": {"pres": (("Pres_A", "Imp_Ais"), ()),
            "pret": (("Pret_A",), ()),
            "nonfin": (("SubjOpt",), ())},
    "142": {"pres": (("Pres_A", "Imp_Ais"), ("ā", "a")),
            "nonfin": (("Pret_I", "SubjOpt"), ())},
    "136": {"pres": (("Pres_A", "Imp_Ais"), ("ī",)),
            "pret": (("Pret_I",), ()),
            "nonfin": (("SubjOpt",), ())},
    "111": {"pres": (("Pres_Ja", "Imp_Jais"), ()),
            "pret": (("Pret_A",), ()),
            "nonfin": (("SubjOpt",), ())},
    "71": {"pres": (("Pres_Aa", "Pret_I", "Imp_Ais"), ()),
           "nonfin": (("SubjOpt",), ())},
    "75": {"pres": (("Pres_Jja", "Pret_I"), ()),
           "nonfin": (("SubjOpt", "Imp_Jais"), ())},
    "81": {"pres": (("Pres_Jja", "Imp_Jais"), ()),
           "pret": (("Pret_I",), ()),
           "nonfin": (("SubjOpt",), ())},
    "87a": {"pres": (("Pres_A", "Pret_A", "Imp_Ais"), ("a", "ā")),
            "nonfin": (("SubjOpt",), ())},
    "87b": {"pres": (("Pres_A", "Pret_Ai", "Imp_Ais"), ("a", "ā")),
            "nonfin": (("SubjOpt",), ())},
    "131": {"pres": (("Pres_I", "Pret_I", "Imp_Is"), ()),
            "nonfin": (("SubjOpt",), ())},
}
# Starke Verben: identische Endungen, eigenes Präteritum-Lexikon (Ablaut).
for _paradigm in ("88", "89", "90", "91", "92", "93", "94", "96", "97", "99", "100",
                  "102", "106", "107", "108", "109", "113", "122", "141"):
    _VERBS[_paradigm] = {"pres": (("Pres_A", "Imp_Ais"), ("a", "ā")),
                          "pret": (("Pret_A",), ()),
                          "nonfin": (("SubjOpt",), ())}

# ── Verben (Partizipien) ────────────────────────────────────────────────────
# Alle drei Rollen WIEDERVERWENDEN den Nonfin-Stamm (Infinitiv − tun/twei); nur
# die Endung unterscheidet sich. Der belegte Masc.Sg.Nom. ergibt:
#
#   partpass  mitā   → mitāts        PartPassMasc/Sg/Nom hängt -s an den Stamm
#   partact   mitā   → mitāwuns      PartActMasc/Sg/Nom hängt -uns an → Gleitlaut
#   partpres  mitā   → mitānts       PartPresMasc/Sg/Nom hängt -s an, Stamm -nt
#   partact   audeg  → audeguns      nach Konsonant kein Gleitlaut
#   partact   perbartau → perbartawuns    Klasse -taw-: au → aw  (wie partpres)
#
# Empirisch am belegten Raster (msc.sg.nom, 1421 einwortige Verbeinträge):
# partpass base+t 1419/1446 · partact base+w 503, base 514, u→w 128 · partpres
# base+nt 398 (Paradigmen 131/132/134/138/139 zu 100 %), u→wint 128 (Par.143).
# Der Rest ist lexikalisch (Gemination, j-Insertion, Ablaut, -ānt/-ant/-int) und
# kommt als gelieferter Stamm (Stufe 1) bzw. als Override (Stufe 2).
_VOWELS = tuple("aeiouāēīōū")
_PARTICIPLE_ROLES: dict[str, RoleSpec] = {
    "partpres": RoleSpec(
        lexc="gen/adj.lexc", atoms=("PartPresInfl",), slots=PART_PRES_SLOTS,
        rules=(StemRule(strip=("u",), suffix="wint"),    # Klasse -taw-: au → awint
               StemRule(suffix="nt"))),
    "partact": RoleSpec(
        lexc="gen/adj.lexc", atoms=("PartActInfl",), slots=PART_PAST_SLOTS,
        rules=(StemRule(strip=("u",), suffix="w"),       # Klasse -taw-: au → aw
               StemRule(after=_VOWELS, glide="w"),      # Nonfin-Stamm + Gleit -w-
               StemRule())),                             # sonst: Nonfin-Stamm
    "partpass": RoleSpec(
        lexc="gen/adj.lexc", atoms=("PartPassInfl",), slots=PART_PASS_SLOTS,
        rules=(StemRule(suffix="t"),)),                 # Nonfin-Stamm + -t
}

_VERB_LEXC = "gen/verb.lexc"
for _paradigm, _role_table in _VERBS.items():
    _roles: dict[str, RoleSpec] = {}
    for _role, (_atoms, _strip) in _role_table.items():
        _slots: list[str] = []
        for _atom in _atoms:
            for _slot in _atom_slots(_atom):
                if _slot not in _slots:
                    _slots.append(_slot)
        _roles[_role] = RoleSpec(
            lexc=_VERB_LEXC, atoms=tuple(_atoms), slots=tuple(_slots),
            rules=(StemRule(strip=_strip),))
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


# ── Stufe 0 (Regel) / Stufe 1 (gelieferter Stamm) ───────────────────────────


def default_stems(pos: str, paradigm: str | int, lemma: str | None = None
                  ) -> dict[str, str]:
    """Stufe-0-Stamm je Rolle: die Regel aus Lemma + Paradigma (``RoleSpec.rules``).

    Ohne Lemma liefert die Funktion nichts — es gibt keinen Stamm zu raten. Will man
    einen Rollen-Stamm überschreiben, ist das ein **gelieferter Stamm**
    (``generate(stems=…)``), keine zweite Stufe im Generator.
    """
    par = _paradigm(pos, paradigm, lemma or "")
    if not lemma:
        return {}
    base = _drop(_norm(lemma), par.strip)
    return {role: spec.stem_from(base) for role, spec in par.roles.items()}


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
             gender: str | None = None) -> dict[str, tuple[str, ...]]:
    """Wortformen erzeugen: ``(pos, Twanksta-Paradigma, Lemma)`` → Slot → Formen.

    ``pos`` ist ``noun``/``adj``/``verb``, ``paradigm`` die Twanksta-Nummer,
    ``lemma`` die Basisform (Nom.Sg. / Infinitiv / Masc.Nom.Sg.). ``stems`` ist
    der **gelieferte Stamm** je Rolle und überschreibt die Stufe-0-Regel
    (``{"obl": "Patall"}``, ``{"partpres": "ainapreslinān"}``). ``gender`` wird nicht
    gebraucht — die Genus-Dimension ist reines Durchreich-Tag in den Slot-Keys; bei
    Nomen ohne bekanntes Genus wird nichts erfunden.

    Ein Slot mit leerem Tupel heißt: das Paradigma hat diese Form nicht (z. B.
    Part.Pl.Dat. ohne Geminate) — kein Fehler, aber auch keine Form.
    """
    par = _paradigm(pos, paradigm, lemma or "")
    resolved = default_stems(pos, paradigm, lemma=lemma)
    for role, stem in (stems or {}).items():
        if role not in par.roles:
            raise KeyError(f"unbekannte Rolle {role!r} für {pos}/{paradigm} "
                           f"(bekannt: {sorted(par.roles)})")
        resolved[role] = stem
    if gender is not None and gender not in _ENTRY_GENDERS:
        raise ValueError(f"unbekanntes gender {gender!r} (masc|fem|neut)")
    key_paradigm = _paradigm_key(pos, paradigm, lemma or "")
    out: dict[str, tuple[str, ...]] = {}
    for role in par.roles:
        stem = resolved.get(role)
        if stem is None:
            continue                      # weder Lemma noch Stamm → nichts zu tun
        check_stem(_norm(stem), role)
        spec = par.roles[role]
        tr = _atom(pos, key_paradigm, role)
        for slot in spec.slots:
            out[slot] = tuple(sorted({surface for surface, _w in tr.lookup(
                _norm(stem) + slot_tag(slot))}))
    return out


# ── Stamm aus einer belegten Form (die Grammatik ist das_lineare Messgerät) ──
#
# Die Endung eines Slots steht in der Grammatik (gen/*.lexc), nicht in einer Tabelle
# hier. Deshalb wird sie gemessen: ein Sentinel-Stamm durchläuft dasselbe
# ``generate``-Rollenatom wie ein echter Stamm; was hinter dem Sentinel
# herauskommt, ist die Endung des Slots — inklusive Akzentgrenze ``^``, Schutzmarker
# ``~`` und Geminations-Marker ``>``, weil der Lookup diese Zeichen mitkopiert.
#
# Drei Bedingungen an das Sentinel, jede aus gen/accent.regex begründet:
#   keine Makrone            (Shorten verkürzt sie vor ^)
#   keine Doppelkonsonanten   (Degem vor ^, CodaDegem vor wortfinalem -s)
#   Vokal am Ende            (keine Geminate-Regel, kein ^ unmittelbar davor)
_SENTINEL_STEM = "stuba"


@lru_cache(maxsize=None)
def slot_ending(pos: str, paradigm: str, role: str, slot: str) -> str:
    """Endung, die die Grammatik des Atoms an ``slot`` an einen Stamm hängt."""
    surfaces = generate(pos, paradigm, stems={role: _SENTINEL_STEM}).get(slot, ())
    if len(surfaces) != 1:
        raise ValueError(
            f"Endung {pos}/{paradigm}/{role} an {slot!r} nicht messbar: "
            f"Sentinel {_SENTINEL_STEM!r} ergibt {len(surfaces)} Oberflächen "
            f"{surfaces} (erwartet: genau eine)")
    surface = surfaces[0]
    if not surface.startswith(_SENTINEL_STEM):
        raise ValueError(
            f"Endung {pos}/{paradigm}/{role} an {slot!r} nicht messbar: "
            f"Sentinel {_SENTINEL_STEM!r} kam als {surface!r} zurück — die "
            f"Akzentregel hat das Sentinel verändert")
    return surface[len(_SENTINEL_STEM):]


def stem_from_form(pos: str, paradigm: str | int, role: str, slot: str,
                   form: str, lemma: str | None = None) -> str:
    """Rollen-Stamm aus einer belegten Oberfläche an ``slot`` zurückgewinnen.

    Das Gegenstück zu ``default_stems``: statt das Lemma per Regel umzudeuten wird
    eine **belegte Form** (irgendein Slot der Rolle) genommen und die Endung
    abgezogen, die die Grammatik dort anhängt (``slot_ending``). Ergebnis ist der
    gelieferte Stamm (Stufe 1) — ``generate(stems={role: stem})`` muss die Form
    wiederherstellen; der Aufrufer prüft das.

    ``lemma`` wird nur für die Paradigmen-Auflösung gebraucht (Verb 87 → 87a/87b).
    Eine Form, die nicht mit der gemessenen Endung endet, ist kein Stamm für diesen
    Slot — dann ``ValueError`` (der Aufrufer probiert den nächsten Kandidaten).
    """
    par = _paradigm(pos, paradigm, lemma or "")
    if role not in par.roles:
        raise KeyError(f"unbekannte Rolle {role!r} für {pos}/{paradigm} "
                       f"(bekannt: {sorted(par.roles)})")
    if slot not in par.roles[role].slots:
        raise ValueError(f"Slot {slot!r} gehört nicht zur Rolle {role!r} "
                         f"(Slots: {', '.join(par.roles[role].slots)})")
    ending = slot_ending(pos, _paradigm_key(pos, paradigm, lemma or ""), role, slot)
    form = _norm(form)
    if not form.endswith(ending):
        raise ValueError(
            f"{form!r} endet nicht auf die Endung {ending!r} des Slots {slot!r} "
            f"(Rolle {role!r}, {pos}/{paradigm}) — daraus lässt sich kein Stamm "
            f"gewinnen")
    return form[:-len(ending)] if ending else form


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
                     metavar="ROLE=STEM",
                     help="gelieferter Stamm je Rolle (überschreibt Stufe 0)")
    gen.add_argument("--gender", choices=["masc", "fem", "neut"])
    args = parser.parse_args(argv)

    if args.cmd == "show":
        for pos, paradigm, role, path in atom_targets():
            if args.pos and pos != args.pos:
                continue
            print(f"{pos:5} {paradigm:5} {role:9} {path.name}")
        return 0
    stems = dict(kv.split("=", 1) for kv in args.stem)
    result = generate(args.pos, args.paradigm, lemma=args.lemma, stems=stems,
                      gender=args.gender)
    for slot, forms in result.items():
        print(f"{slot:28} {' | '.join(forms)}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
