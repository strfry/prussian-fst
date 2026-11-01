"""Paradigm generator for Prussian word forms: lemma + paradigm number -> slot forms.

Every cell is derived from ONE principal form by a suffix rule. The principal forms
are the lemma plus a few fixed cells per part of speech (the classic dictionary
forms, after Mažiulis/Palmaitis):

    noun  lemma (nom.sg), sg.gen, pl.dat
    adj   lemma (msc.sg.nom), comp.msc.sg.nom, msc.sg.gen
    verb  lemma (infinitive), prs.sp3, prt.sp3, opt, part.prs.act.msc.sg.nom,
          part.prf.act.msc.sg.nom, part.prf.pss.msc.sg.nom

A principal form not given by the caller is itself derived from the lemma. A given
one (``generate(cells=...)``, in the NVH simply an ``inflectedForm`` of that slot)
replaces the derivation as the source of its dependent cells. That is the whole
lexical input: there are no stems and no stem markers.

The rules live in ``gen/paradigms.json`` (built by ``gen/derive_paradigms.py``): per
part of speech and Twanksta paradigm number, per slot the source principal form and
an ordered rule list; the first rule whose ending matches wins. Verb sources are
fixed by slot group (VERB_SOURCES); noun and adjective sources are learned, since
there a fixed choice costs thousands of overrides. A rule is written

    x>y         drop the ending x, append y           (ē>is)
    ~x>y        same, and destress the remaining stem  (~ē>īmans)
    pre+x>y     additionally prepend pre               (uka+>)

Destressing models the accent shift onto the ending: every macron of the stem is
shortened and every geminate simplified (zemmis -> zem-īmans, akkintwei -> akintā).

    uv run python gen/generator.py generate noun 53 zemē
    uv run python gen/generator.py generate verb 85 ainagimmatun --cell prt.sp3=ainagimmatin
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
TABLE_PATH = Path(__file__).resolve().parent / "paradigms.json"
LEMMA = "lemma"

# NVH part of speech -> inflection family. Pronouns/numerals with a form table
# (P21-24) inflect like adjectives; the +Pron/+Num tag is the analyzer's business.
FAMILY = {"pron": "adj", "num": "adj"}

PRINCIPAL = {
    "noun": ("sg.gen", "pl.dat"),
    "adj": ("comp.msc.sg.nom", "msc.sg.gen"),
    "verb": ("prs.sp3", "prt.sp3", "opt", "part.prs.act.msc.sg.nom",
             "part.prf.act.msc.sg.nom", "part.prf.pss.msc.sg.nom"),
}

# Verb slot group (dotted prefix, longest wins) -> its principal form. A corrected
# principal form thus always carries over to its whole group. Principal forms
# themselves come from the lemma.
VERB_SOURCES = {
    "prs": "prs.sp3", "imprt": "prs.sp3", "prt": "prt.sp3", "subj": "opt",
    "part.prs": "part.prs.act.msc.sg.nom",
    "part.prf.act": "part.prf.act.msc.sg.nom",
    "part.prf.pss": "part.prf.pss.msc.sg.nom",
}


def verb_source(slot: str) -> str:
    """The principal form a verb slot is derived from."""
    if slot in PRINCIPAL["verb"]:
        return LEMMA
    for prefix in sorted(VERB_SOURCES, key=len, reverse=True):
        if slot.startswith(prefix + "."):
            return VERB_SOURCES[prefix]
    return LEMMA

# ── Slot vocabulary (NVH tag:, dotted) ───────────────────────────────────────
_GENDERS = ("msc", "fem", "neu")
_NUMBERS = ("sg", "pl")
_CASES = ("nom", "gen", "dat", "acc")

_GENDER = {"msc": "Msc", "fem": "Fem", "neu": "Neu"}
_NUMBER = {"sg": "Sg", "pl": "Pl"}
_CASE = {"nom": "Nom", "gen": "Gen", "dat": "Dat", "acc": "Acc"}
_DEGREE = {"comp": "Comp", "superl": "Superl"}
_PART_TENSE = {"prs": "Prs", "prf": "Prf"}
_PART_VOICE = {"act": "Act", "pss": "Pss"}
_FINITE_TENSE = {"prs": "Prs", "prt": "Prt"}
_PERSNUM = {"sg1": "Sg1", "sg2": "Sg2", "sp3": "SP3", "pl1": "Pl1", "pl2": "Pl2"}


def _declined(genders: Iterable[str] = ()) -> tuple[str, ...]:
    """(gender.)number.case in canonical order; nouns have no gender block."""
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
ADVERB_SLOTS = ("adv", "adv.comp", "adv.superl")
ADJ_SLOTS = ADJ_POS_SLOTS + ADJ_CMP_SLOTS + ADJ_SUP_SLOTS + ADVERB_SLOTS
VERB_SLOTS = (tuple(f"prs.{p}" for p in _PERSNUM) + tuple(f"prt.{p}" for p in _PERSNUM)
              + tuple(f"subj.{p}" for p in _PERSNUM) + ("opt", "imprt.sg2", "imprt.pl2")
              + tuple(f"part.{t}.{s}" for t in ("prs.act", "prf.act", "prf.pss")
                      for s in _GENDERED))
SLOTS = {"noun": NOUN_SLOTS, "adj": ADJ_SLOTS, "verb": VERB_SLOTS}


def slot_tag(slot: str) -> str:
    """NVH slot key -> analysis tag (``sg.nom`` -> ``+N+Sg+Nom``).

    One function for every part of speech: the slot heads (``sg``/``pl`` noun,
    ``comp``/``superl`` degree, gender = adjective positive, ``adv``, ``part``,
    ``prs``/``prt``/``subj``, ``opt``, ``imprt``) are disjoint. Nouns carry no
    gender in the slot (it is an entry fact).
    """
    parts = slot.split(".")
    head = parts[0]
    if head in _NUMBER:
        _expect(slot, parts, ("number", "case"))
        return f"+N+{_val(_NUMBER, head, slot)}+{_val(_CASE, parts[1], slot)}"
    if head in _DEGREE:
        _expect(slot, parts, ("degree", "gender", "number", "case"))
        return (f"+A+{_val(_DEGREE, head, slot)}+{_val(_GENDER, parts[1], slot)}"
                f"+{_val(_NUMBER, parts[2], slot)}+{_val(_CASE, parts[3], slot)}")
    if head in _GENDERS:
        _expect(slot, parts, ("gender", "number", "case"))
        return (f"+A+{_val(_GENDER, head, slot)}+{_val(_NUMBER, parts[1], slot)}"
                f"+{_val(_CASE, parts[2], slot)}")
    if head == "adv":
        if len(parts) == 1:
            return "+Adv"
        _expect(slot, parts, ("adverb", "degree"))
        return f"+Adv+{_val(_DEGREE, parts[1], slot)}"
    if head == "part":
        _expect(slot, parts, ("participle", "tense", "voice", "gender", "number", "case"))
        return (f"+V+{_val(_PART_TENSE, parts[1], slot)}Prc"
                f"+{_val(_PART_VOICE, parts[2], slot)}"
                f"+{_val(_GENDER, parts[3], slot)}+{_val(_NUMBER, parts[4], slot)}"
                f"+{_val(_CASE, parts[5], slot)}")
    if head in ("prs", "prt"):
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
    raise ValueError(f"unknown slot key: {slot!r}")


def _expect(slot: str, parts: list[str], shape: tuple[str, ...]) -> None:
    if len(parts) != len(shape):
        raise ValueError(f"slot key {slot!r}: expected {'.'.join(shape)}")


def _val(mapping: Mapping[str, str], key: str, slot: str) -> str:
    try:
        return mapping[key]
    except KeyError:
        raise ValueError(f"slot key {slot!r}: unknown component {key!r}") from None


# ── Lemma normalisation ──────────────────────────────────────────────────────


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def split_si(lemma: str) -> tuple[str, bool]:
    """``"perwaidīntun si"`` -> ``("perwaidīntun", True)``.

    Reflexive verbs carry the particle in the headword; the forms do not.
    """
    if lemma.endswith(" si"):
        return lemma[:-3], True
    return lemma, False


def family(pos: str) -> str:
    return FAMILY.get(pos.lower(), pos.lower())


# ── Rules ────────────────────────────────────────────────────────────────────

_SHORT = str.maketrans("āēīōū", "aeiou")
_GEMINATE = re.compile(r"([bcdfghjklmnprstvwz])\1")


def destress(stem: str) -> str:
    """Accent shift onto the ending: shorten every macron, simplify every geminate."""
    return _GEMINATE.sub(r"\1", stem.translate(_SHORT))


Rule = tuple[str, str, str, bool]          # (prefix, drop, add, destress)


def parse_rule(text: str) -> Rule:
    """``"~uka+is>jai"`` -> ``("uka", "is", "jai", True)``."""
    soft = text.startswith("~")
    body = text[1:] if soft else text
    prefix, _, body = body.rpartition("+")
    drop, sep, add = body.partition(">")
    if not sep:
        raise ValueError(f"rule without '>': {text!r}")
    return prefix, drop, add, soft


def format_rule(rule: Rule) -> str:
    prefix, drop, add, soft = rule
    return ("~" if soft else "") + (f"{prefix}+" if prefix else "") + f"{drop}>{add}"


def apply_rules(rules: Iterable[Rule], source: str) -> str | None:
    """First rule whose ending matches ``source`` (and leaves a stem) wins."""
    for prefix, drop, add, soft in rules:
        if source.endswith(drop) and len(source) > len(drop):
            stem = source[: len(source) - len(drop)]
            return prefix + (destress(stem) if soft else stem) + add
    return None


# ── Table ────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=None)
def _table() -> dict:
    if not TABLE_PATH.exists():
        raise FileNotFoundError(f"{TABLE_PATH} is missing — build it with "
                                f"uv run python gen/derive_paradigms.py")
    data = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    return {fam: {par: {slot: (spec["from"], tuple(parse_rule(r) for r in spec["rules"]))
                        for slot, spec in slots.items()}
                  for par, slots in pars.items()}
            for fam, pars in data["paradigms"].items()}


def paradigms(pos: str) -> list[str]:
    """Paradigm numbers the table knows for ``pos``."""
    return sorted(_table().get(family(pos), {}))


def paradigm_slots(pos: str, paradigm: str | int) -> tuple[str, ...]:
    return tuple(_spec(pos, paradigm))


def _spec(pos: str, paradigm: str | int) -> dict[str, tuple[str, tuple[Rule, ...]]]:
    try:
        return _table()[family(pos)][str(paradigm)]
    except KeyError:
        raise KeyError(f"unknown paradigm {paradigm!r} for pos={pos!r} "
                       f"(known: {paradigms(pos)})") from None


def generate(pos: str, paradigm: str | int, lemma: str,
             cells: Mapping[str, Iterable[str]] | None = None
             ) -> dict[str, tuple[str, ...]]:
    """Forms of one lexeme: slot -> (form,).

    ``cells`` are known cells of the lexeme (NVH ``inflectedForm``). A known principal
    form with exactly one surface becomes the source of its dependent cells; every
    other cell is ignored here. The returned value of a principal slot is always the
    *derived* one, so a caller that merges ``cells`` over the result (an override
    replaces its slot) can see whether the cell was needed.

    A slot without an applicable rule is absent: the paradigm gives no form for it.
    """
    spec = _spec(pos, paradigm)
    base = split_si(nfc(lemma))[0]
    given = {}
    for slot in PRINCIPAL.get(family(pos), ()):
        forms = {nfc(f) for f in (cells or {}).get(slot, ())}
        if len(forms) == 1:
            given[slot] = forms.pop()
    known = {LEMMA: base}
    out: dict[str, tuple[str, ...]] = {}
    for source_first in (True, False):           # principal forms before their dependents
        for slot, (source, rules) in spec.items():
            if (source == LEMMA) != source_first or source not in known:
                continue
            form = apply_rules(rules, known[source])
            if form is not None:
                out[slot] = (form,)
            if source == LEMMA and slot in PRINCIPAL.get(family(pos), ()):
                if slot in given or form is not None:
                    known[slot] = given.get(slot, form)
    return out


def _main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show", help="rules of one paradigm")
    show.add_argument("pos", choices=["noun", "adj", "verb"])
    show.add_argument("paradigm")
    gen = sub.add_parser("generate", help="forms of one lexeme")
    gen.add_argument("pos", choices=["noun", "adj", "verb", "pron", "num"])
    gen.add_argument("paradigm")
    gen.add_argument("lemma")
    gen.add_argument("--cell", action="append", default=[], metavar="SLOT=FORM",
                     help="known cell, e.g. a principal form")
    args = parser.parse_args(argv)

    if args.cmd == "show":
        for slot, (source, rules) in _spec(args.pos, args.paradigm).items():
            print(f"{slot:28} {source:26} {'  '.join(format_rule(r) for r in rules)}")
        return 0
    cells = {}
    for item in args.cell:
        slot, _, form = item.partition("=")
        cells.setdefault(slot, []).append(form)
    for slot, forms in generate(args.pos, args.paradigm, args.lemma, cells).items():
        print(f"{slot:28} {' | '.join(forms)}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
