"""§3 Kompressor: fette NVH → lean NVH (Wortliste + nur das Irreduzible).

Die fette NVH (``twanksta_dmlex.full.nvh``: alle POS, Giella-Tags, top-level
``paradigm``, eigenes ``gender``-Feld) listet **jede** attestierte Zelle als
``inflectedForm`` + ``tag``. Der Kompressor verdichtet sie **pro Eintrag** mit dem
listenlosen Generator (``gen/generator.py``) auf das, was die Grammatik nicht
selbst erzeugt:

    Stufe 0   Lemma → Stamm je Rolle regelhaft   → wird **nicht** gespeichert
    Stufe 1   gelieferter Stamm je Rolle          → ``stemOverrides: ROLLE=STAMM``
    Stufe 2   Override: fertige Form je Zelle     → ``inflectedForm`` + ``tag``

Ein **gelieferter Stamm** ist der Rollen-Stamm selbst (``obl``, ``pres``, ``pret``,
``nonfin``, ``partpres`` …), nicht eine Belegform. Er wird **aus einer belegten
Form gewonnen** (``generator.stem_from_form``): die Grammatik misst die Endung des
Slots, der Rest ist der Stamm. Ein **Override** ist jede attestierte Oberfläche,
die ``generate(stems)`` nicht liefert. Das Paar ist verlustfrei:

    generate(lemma, stems) ∪ overrides == attested          (zellweise)

Drei Zusicherungen, im Code erzwungen statt behauptet:

* **Minimalität** — ein Stamm wird nur geliefert, wenn er attestierte Zellen *neu*
  deckt (Greedy über die Rollen eines Paradigmas, Gleichstand → erste der
  alphabetisch sortierten Kandidaten). Slots zweier Rollen sind disjunkt
  (``ROLES_ARE_DISJOINT``, eigener Test), die Rollenentscheidungen stören sich
  also nicht gegenseitig. Stufe 0 identische Stämme werden nie geliefert (Lint).
* **Fixpunkt/Idempotenz** — ein gelieferter Stamm ist **Eingang**, nicht Ergebnis:
  die lean NVH trägt ihn als ``stemOverrides`` und der zweite Lauf übernimmt ihn
  unverändert. Er läuft nicht ins Leere, weil die fette NVH ihn nicht enthält.
* **Verlustfreiheit** — jede Runde wird gegen das **ursprüngliche** ``attested``
  geprüft; eine Ableitung, die Zellen verlöre, wird verworfen und gemeldet.

Was der Generator nicht abdecken kann, bleibt als Override stehen, damit die lean
NVH dieselben Zellen ausweist wie die fette — verlustfrei by construction:

* unbekanntes Paradigma (kein ``PARADIGMS``-Key) → alle Zellen Override,
* Stamm außerhalb des Kopierer-Alphabets (Leerzeichen in Mehrwort-Lemmata wie
  ``mitātun si``, ``Centralafrikas Republīki``) → die Rolle entfällt, ihre Zellen
  werden Override,
* Restzellen, die der Stamm nicht deckt (z. B. Neut.Pl.Nom. -ai ohne
  Makronshortening-Rückweg) → Override je Zelle.

CLI::

    uv run python gen/compress_forms.py --stats
    uv run python gen/compress_forms.py --lemma-only --dry-run
    uv run python gen/compress_forms.py --verify-idempotent

Kern ist reines, importierbares Python (``parse_nvh``, ``derive_minimal``,
``compress``); die CLI ist ein dünner Entrypoint. Quellen sind die fette NVH und
die gebackenen Atome — keine Wortliste, kein ``twanksta_entries.json``.
"""

from __future__ import annotations

import argparse
import collections
import sys
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generator as gen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT.parent / "corpus" / "parsed"
FULL_NVH = PARSED / "twanksta_dmlex.full.nvh"
LEAN_NVH = PARSED / "twanksta_dmlex.nvh"

GENDERS = ("masc", "fem", "neut")

# Die Zeile, die einen gelieferten Stamm je Rolle trägt (Stufe 1 im NVH).
STEM_OVERRIDES = "stemOverrides"

# Eine NVH-Zelle = (Slot, Oberfläche). Mehrere Oberflächen je Slot sind Varianten
# und zählen einzeln (so liefert die Roh-HTML-Quelle sie, §0.1/0.2 des Plans).


def slot_class(pos: str, slot: str) -> str:
    """Zellenklasse eines Slots — die Verben werden in finite/Partizip getrennt.

    Die Verben tragen 18 finite Zellen (prs/prt/subj/opt/imprt) und 72 Partizip-
    Zellen je Eintrag. Ohne diese Trennung verwässert das Partizip-Grid (80 % der
    Verbzellen) die Deckungszahl, die ``gen/DEVIATIONS.md`` für die finite Tafel
    gibt.
    """
    return "partizip" if pos == "verb" and slot.startswith("part.") else pos


def _roles_are_disjoint() -> bool:
    for par in gen.PARADIGMS.values():
        seen: set[str] = set()
        for spec in par.roles.values():
            if seen & set(spec.slots):
                return False
            seen |= set(spec.slots)
    return True


ROLES_ARE_DISJOINT = _roles_are_disjoint()


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


# ── NVH-Leser ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Entry:
    """Ein NVH-Eintrag: Kopfdaten + gelieferte Stämme + attestierte Zellen.

    ``attested`` bildet Slot-Key → **mengenweise** Oberflächen (Varianten eines
    Slots). ``stems`` sind die ``stemOverrides`` der Zeile (Rolle → Stamm); in der
    fette NVH ist die Menge leer, in der lean NVH trägt sie die Stufe 1.
    ``head``/``tail`` sind die Rohzeilen ohne ``stemOverrides``- und
    ``inflectedForm``-Blöcke, damit der Schreiber den Rest byte-gleich hält:
    ``id``, ``label``, ``sense``, ``legacy`` und ``relation`` bleiben unangetastet.
    """

    lemma: str
    pos: str = ""
    paradigm: str = ""
    gender: str = ""
    attested: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    stems: Mapping[str, str] = field(default_factory=dict)
    head: tuple[str, ...] = ()
    tail: tuple[str, ...] = ()

    @property
    def cells(self) -> int:
        """Attestierte Zellen (Oberflächen, nicht Slots)."""
        return sum(len(v) for v in self.attested.values())

    @property
    def generable(self) -> bool:
        """Eintrag hat POS + Paradigma + überhaupt Zellen."""
        return bool(self.pos and self.paradigm and self.attested)


def _split_pos(value: str) -> tuple[str, str]:
    """``noun-masc`` (Legacy-Schreibweise) → ``("noun", "masc")``."""
    pos, _, gender = value.partition("-")
    return pos, gender if gender in GENDERS else ""


def parse_nvh(text: str) -> list[Entry]:
    """NVH-Text → Einträge (eingerücktes ``key: value``).

    Gelesen werden genau die Felder des Auftrags: ``pos``, ``gender``,
    ``paradigm`` (top-level), ``stemOverrides`` (Stufe 1) und ``inflectedForm`` +
    ``tag`` (Stufe 2 bzw. die fette NVH). Alle übrigen Zeilen — inklusive der
    tieferen ``sense``-/``legacy``-/``relation``-Blöcke — wandern unverändert nach
    ``head``/``tail``. Oberflächen werden NFC-normalisiert, weil der Kopierer des
    Generators NFD-Kombining-Marks nicht kennt.
    """
    entries: list[Entry] = []
    lemma: str | None = None
    pos = paradigm = gender = ""
    forms: dict[str, set[str]] = {}
    stems: dict[str, str] = {}
    head: list[str] = []
    tail: list[str] = []
    saw_form = False
    form: str | None = None

    def flush() -> None:
        nonlocal lemma, pos, paradigm, gender, forms, stems, head, tail
        nonlocal saw_form, form
        if lemma is None:
            return
        entries.append(Entry(
            lemma=lemma, pos=pos, paradigm=paradigm, gender=gender,
            attested={slot: tuple(sorted(surfaces))
                      for slot, surfaces in sorted(forms.items())},
            stems=dict(sorted(stems.items())),
            head=tuple(head), tail=tuple(tail)))
        lemma = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, _, value = line.strip().partition(": ")
        value = value.strip()
        if indent == 0:
            flush()
            lemma = value
            pos = paradigm = gender = ""
            forms, stems, head, tail = {}, {}, [], []
            saw_form, form = False, None
            continue
        if indent == 2:
            if key == "inflectedForm":
                form, saw_form = value, True
                continue
            if key == STEM_OVERRIDES:
                for item in value.split():
                    role, _, stem = item.partition("=")
                    if stem:
                        stems[role] = stem
                continue
            if key == "pos":
                pos, gender = _split_pos(value)
            elif key == "gender":
                gender = value
            elif key == "paradigm":
                paradigm = value
            (tail if saw_form else head).append(line)
            continue
        if form is not None and key == "tag":
            forms.setdefault(value, set()).add(_nfc(form))
            form = None
            continue
        (tail if saw_form else head).append(line)
    flush()
    return entries


def read_nvh(path: str | Path) -> list[Entry]:
    return parse_nvh(Path(path).read_text(encoding="utf-8"))


def render_entry(entry: Entry, stems: Mapping[str, str] | None = None,
                 overrides: Mapping[str, Sequence[str]] | None = None
                 ) -> str:
    """Ein leaner Eintrag: Kopfdaten (roh) + gelieferte Stämme + Rest-Overrides.

    Reihenfolge: erst die Kopfdaten, dann ``stemOverrides: ROLLE=STEM`` in der
    Rollenreihenfolge des Paradigmas, dann die Overrides je Slot sortiert. Ein
    Eintrag, den Stufe 0 (bzw. die gelieferten Stämme) vollständig deckt, bekommt
    überhaupt keine Formzeile — genau das ist die Kompression.
    """
    stems = stems or {}
    overrides = overrides or {}
    order = sorted(stems, key=_role_order(entry))
    lines = [f"entry: {entry.lemma}", *entry.head]
    if order:
        lines.append(f"  {STEM_OVERRIDES}: "
                     + " ".join(f"{role}={stems[role]}" for role in order))
    slots = list(entry.attested)
    slots += [slot for slot in overrides if slot not in slots]
    for slot in slots:
        for surface in sorted(overrides.get(slot, ())):
            lines.append(f"  inflectedForm: {surface}")
            lines.append(f"    tag: {slot}")
    lines.extend(entry.tail)
    return "\n".join(lines) + "\n"


@lru_cache(maxsize=None)
def _role_sort_key(pos: str, paradigm: str) -> tuple[str, ...]:
    """Rollenreihenfolge eines Paradigmas (stabil, unabhängig vom Lemma)."""
    try:
        return tuple(gen.PARADIGMS[(pos, paradigm)].roles)
    except KeyError:
        return ()


def _role_order(entry: Entry) -> "collections.abc.Callable[[str], tuple[str, ...]]":
    key = _role_sort_key(entry.pos, gen.resolve_paradigm(entry.pos, entry.paradigm)
                         if entry.pos in ("noun", "adj", "verb") else entry.paradigm)
    return lambda role: (key.index(role) if role in key else len(key), role)


def write_nvh(path: str | Path,
              pairs: Iterable[tuple[Entry, Derivation]]) -> None:
    """Lean NVH schreiben. ``pairs`` ist die Ausgabe von ``compress``."""
    Path(path).write_text(
        "".join(render_entry(entry, d.stems, d.overrides) for entry, d in pairs),
        encoding="utf-8")


# ── Generierung (Stufe 0/1) ─────────────────────────────────────────────────


def _usable(stem: str) -> bool:
    """Kann der Stamm in den Kopierer? Leerzeichen/Mehrwort-Lemmata: nein."""
    try:
        gen.check_stem(_nfc(stem))
    except ValueError:
        return False
    return True


def _merged(generated: Mapping[str, Sequence[str]],
            overrides: Mapping[str, Sequence[str]]) -> dict[str, frozenset[str]]:
    """``generate(stems) ∪ overrides`` als Zellmengen."""
    out = {slot: frozenset(forms) for slot, forms in generated.items()}
    for slot, surfaces in overrides.items():
        out[slot] = out.get(slot, frozenset()) | frozenset(surfaces)
    return out


def uncovered(attested: Mapping[str, Sequence[str]],
              produced: Mapping[str, Sequence[str]]) -> dict[str, tuple[str, ...]]:
    """Attestierte Oberflächen, die ``produced`` an diesem Slot nicht liefert."""
    out: dict[str, tuple[str, ...]] = {}
    for slot, surfaces in attested.items():
        have = frozenset(produced.get(slot, ()))
        rest = tuple(s for s in surfaces if s not in have)
        if rest:
            out[slot] = rest
    return out


def covered_cells(attested: Mapping[str, Sequence[str]],
                  produced: Mapping[str, Sequence[str]]) -> int:
    return sum(1 for slot, surfaces in attested.items()
               for s in surfaces if s in frozenset(produced.get(slot, ())))


def usable_stems(pos: str, paradigm: str, lemma: str,
                 stems: Mapping[str, str] | None = None) -> dict[str, str]:
    """Stufe-0-Stämme, überschrieben von den gelieferten — ohne die unbrauchbaren.

    Das Paradigma wird **vor** dem ``generate``-Aufruf aufgelöst (``87`` → ``87a``/
    ``87b``), weil ``generate`` ohne Lemma sonst die Default-Auflösung nähme.
    """
    out = gen.default_stems(pos, paradigm, lemma=lemma)
    for role, stem in (stems or {}).items():
        if role not in out:
            continue                  # unbekannte Rolle → nicht unser Problem
        out[role] = stem
    return {role: stem for role, stem in out.items() if _usable(stem)}


def regenerate(pos: str, paradigm: str, lemma: str,
               stems: Mapping[str, str] | None = None) -> dict[str, tuple[str, ...]]:
    """``generate`` mit den Stufe-0/1-Stämmen (siehe ``usable_stems``)."""
    return gen.generate(pos, gen.resolve_paradigm(pos, paradigm, lemma),
                        stems=usable_stems(pos, paradigm, lemma, stems))


@lru_cache(maxsize=1 << 16)
def _role_forms(pos: str, paradigm: str, lemma: str, role: str,
                stem: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Nur eine Rolle erzeugen (Kandidatenprüfung im Greedy), Cache je Stamm."""
    if not _usable(stem):
        return ()
    forms = gen.generate(pos, gen.resolve_paradigm(pos, paradigm, lemma),
                         stems={role: stem})
    return tuple(sorted(forms.items()))


def candidate_stems(pos: str, paradigm: str, lemma: str, role: str,
                    attested: Mapping[str, Sequence[str]]
                    ) -> tuple[tuple[str, str], ...]:
    """(Stamm, Belegform) je Rolle, geordnet — aus **irgendeiner** Zelle der Rolle.

    Der Stamm wird nie geraten, sondern aus einer attestierten Oberfläche
    zurückgewonnen (``generator.stem_from_form``): die Grammatik misst die Endung
    des Slots, der Rest ist der Stamm. Endet eine Belegform nicht auf der gemessenen
    Endung (z. B. weil sie eine Variante ist), ist sie kein Kandidat. Ergebnis ist
    alphabetisch sortiert und doppelfrei — der Greedy bricht beim ersten
    Gleichstand ab, die Reihenfolge entscheidet also mit.
    """
    try:
        spec = gen.paradigm_spec(pos, paradigm, lemma).roles[role]
    except KeyError:
        return ()
    out: dict[str, str] = {}
    for slot in spec.slots:
        for form in attested.get(slot, ()):
            try:
                stem = gen.stem_from_form(pos, paradigm, role, slot, _nfc(form),
                                           lemma=lemma)
            except (ValueError, KeyError):
                continue
            if not _usable(stem):
                continue
            out.setdefault(stem, form)
    return tuple(sorted(out.items()))


def _normalize(attested: Mapping[str, Sequence[str]] | None
               ) -> dict[str, tuple[str, ...]]:
    if not attested:
        return {}
    return {slot: tuple(sorted({_nfc(s) for s in surfaces}))
            for slot, surfaces in attested.items() if surfaces}


# ── Ableitung ───────────────────────────────────────────────────────────────


@dataclass
class Derivation:
    """Ergebnis für **einen** Eintrag."""

    stems: dict[str, str] = field(default_factory=dict)
    overrides: dict[str, tuple[str, ...]] = field(default_factory=dict)
    generated: dict[str, tuple[str, ...]] = field(default_factory=dict)
    generated_s0: dict[str, tuple[str, ...]] = field(default_factory=dict)
    cells: int = 0
    covered_s0: int = 0
    covered_s1: int = 0
    status: str = "ok"                 # ok | unbekanntes-paradigma | kein-stamm
    stem_fields: tuple[str, ...] = ()  # Lint: Stamm == Stufe-0-Stamm (redundant)
    supplied_stems: tuple[str, ...] = ()
    override_variant: int = 0           # Overrides an Slots mit Varianten
    lint_generable_override: int = 0
    unstable: bool = False
    rounds: int = 1
    attested: Mapping[str, tuple[str, ...]] = field(default_factory=dict, repr=False)

    @property
    def expanded(self) -> dict[str, frozenset[str]]:
        """Die Zellen, die der lean Eintrag ausweist: ``generate ∪ overrides``."""
        return _merged(self.generated, self.overrides)

    @property
    def missing(self) -> dict[str, tuple[str, ...]]:
        """Was der lean Eintrag verlöre (leer = verlustfrei)."""
        return uncovered(self.attested, self.expanded)

    @property
    def complete_s0(self) -> bool:
        return self.covered_s0 == self.cells


def _derive_once(pos: str, paradigm: str, lemma: str, gender: str,
                 attested: Mapping[str, tuple[str, ...]],
                 lemma_only: bool,
                 supplied: Mapping[str, str] | None = None,
                 dense: bool = False,
                 original: Mapping[str, tuple[str, ...]] | None = None
                 ) -> Derivation:
    """Ein Durchgang: Stufe 0 → gelieferte Stämme (greedy) → Rest-Overrides.

    ``supplied`` sind die ``stemOverrides`` des Eintrags — Eingang, kein Ergebnis.
    Sie werden übernommen, auch wenn sie derzeit nichts zudecken; der Greedy darf
    nur *addieren*. ``attested`` ist die Menge, aus der die Stämme gewonnen und die
    Overrides gebildet werden. ``original`` ist die Zellenmenge der **fette NVH**,
    gegen die ``cells``/``covered_*``/``missing`` gerechnet werden. Ohne diesen
    Unterschied wäre ``missing`` bei jeder Runde ab Runde 2 leer — die
    Verlustfreiheitszusage wäre dann eine Behauptung.

    ``dense`` heißt: die Eingabe ist selbst eine bereits verdichtete NVH. Dann sind
    die Zellen die **Aussage der Datei** (sie stehen dort als Override) und bleiben
    unangetastet; ein Neuableiten aus ihnen wäre Raten mit weniger Information als
    der erste Lauf — er schlägt die 23 Zellen eines Stufe-0-Partizipstamms für die
    eine abweichende Nischenform und wirft sie weg (mitātun, partpass 'kalbit').
    """
    original = attested if original is None else original
    supplied = dict(supplied or {})
    cells = sum(len(v) for v in original.values())
    try:
        par = gen.paradigm_spec(pos, paradigm, lemma)
    except KeyError:
        return Derivation(overrides=dict(attested), cells=cells,
                          status="unbekanntes-paradigma", attested=original)

    if gender and gender not in GENDERS:
        raise ValueError(f"{lemma}: unbekanntes gender {gender!r} ({'|'.join(GENDERS)})")

    s0 = regenerate(pos, paradigm, lemma)
    default = gen.default_stems(pos, paradigm, lemma=lemma)
    stems: dict[str, str] = {role: stem for role, stem in supplied.items()
                             if role in par.roles and _usable(_nfc(stem))}
    redundant: list[str] = []

    if not lemma_only and not dense:
        # Stufe 0 zuerst: ein gelieferter Stamm, der dem Regelstamm entspricht,
        # deckt nichts neu und ist reiner Ballast (Lint (a)).
        generated = dict(s0)
        for role, stem in stems.items():
            generated = {**generated,
                         **_dict(_role_forms(pos, paradigm, lemma, role, stem))}
            if default.get(role) == stem:
                redundant.append(role)
        for role, spec in par.roles.items():
            if role in stems:
                continue
            # Ein gelieferter Stamm **ersetzt** den Stufe-0-Stamm seiner Rolle, der
            # Gewinn ist also eine Differenz: was der Kandidat neu deckt, minus was
            # der bisherige Stamm deckt und der Kandidat verliert. Sonst gewinnt ein
            # Stamm, der eine einzige Nischenform trifft, während er den Rest der
            # Rolle wegwirft (mitātun: partpass 'mitat' für die -ai-Form gegen
            # Stufe 0 'mitāt' mit 23 Zellen).
            before = _role_covered(original, generated, spec.slots)
            best_stem: str | None = None
            best_gain = 0
            for stem, _form in candidate_stems(pos, paradigm, lemma, role, attested):
                if default.get(role) == stem:
                    continue              # Stufe 0 deckt ihn bereits
                after = _role_covered(
                    original,
                    _dict(_role_forms(pos, paradigm, lemma, role, stem)),
                    spec.slots)
                gain = len(after - before) - len(before - after)
                if gain > best_gain:      # Gleichstand → erster sortierter Kandidat
                    best_stem, best_gain = stem, gain
            if best_stem is None:
                continue
            stems[role] = best_stem
            generated = {**generated,
                         **_dict(_role_forms(pos, paradigm, lemma, role, best_stem))}

    generated = regenerate(pos, paradigm, lemma, stems)
    overrides = dict(attested) if dense else uncovered(attested, generated)
    # Lint (b): ein Override, den die Stämme doch liefern, wäre überflüssig. Die
    # Overrides sind per Konstruktion genau der Rest, also muss die Zahl 0 sein —
    # der Lint prüft die Invariante, statt sie zu behaupten.
    lint = sum(1 for slot, surfaces in overrides.items()
               for s in surfaces if s in generated.get(slot, ()))
    variants = sum(len(surfaces) for slot, surfaces in overrides.items()
                   if len(original.get(slot, ())) > 1)
    return Derivation(
        stems=stems, overrides=overrides, generated=generated,
        generated_s0=s0, cells=cells,
        covered_s0=covered_cells(original, s0), covered_s1=covered_cells(original, generated),
        status="ok" if usable_stems(pos, paradigm, lemma, stems) else "kein-stamm",
        stem_fields=tuple(redundant), supplied_stems=tuple(sorted(supplied)),
        override_variant=variants, lint_generable_override=lint,
        attested=original)


def _dict(pairs: Iterable[tuple[str, Sequence[str]]]
          ) -> dict[str, tuple[str, ...]]:
    return {slot: tuple(forms) for slot, forms in pairs}


def _role_covered(attested: Mapping[str, Sequence[str]],
                  produced: Mapping[str, Sequence[str]],
                  slots: Sequence[str]) -> frozenset[str]:
    """Attestierte Oberflächen, die ``produced`` an den Slots einer Rolle deckt.

    Für den Greedy-Vergleich zählen nur die Slots der Rolle — die Slots zweier
    Rollen sind disjunkt (``ROLES_ARE_DISJOINT``), ein Kandidat kann also nur
    innerhalb seiner eigenen Rolle gewinnen oder verlieren.
    """
    out: set[str] = set()
    for slot in slots:
        have = frozenset(produced.get(slot, ()))
        out.update(surface for surface in attested.get(slot, ()) if surface in have)
    return frozenset(out)


def _lean_attested(derivation: Derivation) -> dict[str, tuple[str, ...]]:
    """Was die lean NVH für diesen Eintrag an Zellen ausweist: nur die Overrides."""
    return {slot: tuple(sorted(v)) for slot, v in derivation.overrides.items()}


def derive_entry(pos: str, paradigm: str, lemma: str, gender: str = "",
                 attested: Mapping[str, Sequence[str]] | None = None, *,
                 supplied: Mapping[str, str] | None = None, dense: bool = False,
                 lemma_only: bool = False, rounds: int = 4) -> Derivation:
    """``(stems, overrides)`` + Kennzahlen, bis zum Fixpunkt iteriert.

    ``lemma_only`` ist der Modus „nur Lemma": Stufe 0 ohne gelieferte Stämme, alles
    Nicht-Regenerierte wird Override. ``dense`` heißt: die Eingabe ist selbst eine
    verdichtete NVH — die Zellen bleiben Override, die gelieferten Stämme bleiben,
    es wird nichts neu abgeleitet (siehe ``_derive_once``). Sonst wird bis zum
    Fixpunkt iteriert: jede weitere Runde leitet aus ``overrides`` ab, misst ihren
    Gewinn und ihre Verlustfreiheit aber weiterhin an den **Zellen der fette NVH** —
    bricht diese Invariante, bleibt die letzte verlustfreie Runde stehen und der
    Eintrag wird als ``unstable`` gemeldet (im Bericht: „nicht konvergiert").
    """
    att = _normalize(attested)
    result = _derive_once(pos, paradigm, lemma, gender, att, lemma_only, supplied, dense)
    if lemma_only or dense or not (result.stems or result.overrides):
        return result
    for round_no in range(2, rounds + 1):
        nxt = _derive_once(pos, paradigm, lemma, gender, _lean_attested(result),
                           lemma_only, supplied=result.stems, original=att)
        if (nxt.stems, nxt.overrides) == (result.stems, result.overrides):
            result.rounds = round_no
            return result
        if nxt.missing:                  # Runde verlöre Zellen → zurück zur letzten
            result.unstable = True
            return result
        result = nxt
        result.rounds = round_no
    result.unstable = True
    return result


def derive_minimal(pos: str, paradigm: str, lemma: str, gender: str = "",
                   attested: Mapping[str, Sequence[str]] | None = None, *,
                   supplied: Mapping[str, str] | None = None, dense: bool = False,
                   lemma_only: bool = False, rounds: int = 4
                   ) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """Minimaler ``(stems, overrides)``-Satz für einen Eintrag.

    Zellenweise verlustfrei: ``generate(pos, paradigm, lemma, stems=stems) ∪
    overrides == attested``. ``stems`` ist leer, wenn Stufe 0 alles deckt; leere
    ``overrides`` heißt, dass die gelieferten Stämme das Lexem vollständig
    regenerieren.
    """
    derivation = derive_entry(pos, paradigm, lemma, gender, attested,
                              supplied=supplied, dense=dense,
                              lemma_only=lemma_only, rounds=rounds)
    return derivation.stems, derivation.overrides


# ── Statistik ────────────────────────────────────────────────────────────────


@dataclass
class Stats:
    """Zähler des Berichts; ``record`` je Eintrag, ``report`` als Text.

    ``cells[(pos, kind)]`` mit ``kind`` in ``total`` (alle Zellen des Eintrags),
    ``status`` (Zellen ungenerierbarer Einträge), ``s0`` (Stufe-0-Deckung) und
    ``s1`` (Deckung mit gelieferten Stämmen). ``skipped[(pos, grund)]`` zählt
    Einträge, die der Generator nicht anfasst (unbekanntes Paradigma, Stamm
    außerhalb des Kopierers) bzw. die keine Wortlisteneinträge sind (fehlende
    Zellen).
    """

    entries: collections.Counter = field(default_factory=collections.Counter)
    s0_complete: collections.Counter = field(default_factory=collections.Counter)
    stem_entries: collections.Counter = field(default_factory=collections.Counter)
    stem_fields: collections.Counter = field(default_factory=collections.Counter)
    status_cells: collections.Counter = field(default_factory=collections.Counter)
    overrides: collections.Counter = field(default_factory=collections.Counter)
    override_variant: collections.Counter = field(default_factory=collections.Counter)
    cells: collections.Counter = field(default_factory=collections.Counter)
    class_cells: collections.Counter = field(default_factory=collections.Counter)
    class_s0: collections.Counter = field(default_factory=collections.Counter)
    class_s1: collections.Counter = field(default_factory=collections.Counter)
    skipped: collections.Counter = field(default_factory=collections.Counter)
    lint_redundant_stem: collections.Counter = field(default_factory=collections.Counter)
    lint_generable_override: collections.Counter = field(default_factory=collections.Counter)
    unstable: collections.Counter = field(default_factory=collections.Counter)
    rounds: collections.Counter = field(default_factory=collections.Counter)

    BLOCKING = ("unbekanntes-paradigma", "kein-stamm")

    def record(self, entry: Entry, derivation: Derivation) -> None:
        key = (entry.pos, entry.paradigm)
        self.entries[key] += 1
        self.cells[(entry.pos, "total")] += derivation.cells
        self.rounds[derivation.rounds] += 1
        self.lint_redundant_stem[key] += len(derivation.stem_fields)
        self.lint_generable_override[key] += derivation.lint_generable_override
        if derivation.unstable:
            self.unstable[key] += 1
        for slot, surfaces in derivation.overrides.items():
            self.overrides[key] += len(surfaces)
            if len(entry.attested.get(slot, ())) > 1:
                self.override_variant[key] += len(surfaces)
        if derivation.status != "ok":
            self.skipped[(entry.pos, derivation.status)] += 1
            self.status_cells[(entry.pos, derivation.status)] += derivation.cells
            self.cells[(entry.pos, "status")] += derivation.cells
            return
        self.cells[(entry.pos, "s0")] += derivation.covered_s0
        self.cells[(entry.pos, "s1")] += derivation.covered_s1
        for slot, surfaces in entry.attested.items():
            cls = (entry.pos, slot_class(entry.pos, slot))
            self.class_cells[cls] += len(surfaces)
            self.class_s1[cls] += sum(1 for s in surfaces
                                      if s in frozenset(derivation.generated.get(slot, ())))
            self.class_s0[cls] += sum(1 for s in surfaces
                                      if s in frozenset(derivation.generated_s0.get(slot, ())))
        if derivation.covered_s0 == derivation.cells:
            self.s0_complete[key] += 1
        if derivation.stems:
            self.stem_entries[key] += 1
            for role in derivation.stems:
                self.stem_fields[(entry.pos, entry.paradigm, role)] += 1

    def entries_of(self, pos: str) -> int:
        """Generierbare Einträge (POS + Paradigma + Zellen vorhanden)."""
        return sum(v for (p, _), v in self.entries.items() if p == pos)

    def blocked(self, pos: str) -> int:
        """Einträge, die der Generator nicht anfasst."""
        return sum(v for (p, reason), v in self.skipped.items()
                   if p == pos and reason in self.BLOCKING)

    def blocked_cells(self, pos: str) -> int:
        return self.cells[(pos, "status")]

    def report(self, *, title: str = "Kennzahlen",
               positions: Sequence[str] = ("noun", "adj", "verb")) -> str:
        out = [f"# {title}", ""]
        out.append("## POS-Deckung — Einträge mit bekanntem Paradigma **und** brauchbarem Stamm")
        out.append(f"{'POS':5} {'Einträge':>8} {'Zellen':>8} {'Stufe 0':>18} "
                   f"{'mit Stämmen':>18} {'Overrides':>9}")
        for pos in positions:
            if not self.entries_of(pos):
                continue
            total = self.cells[(pos, "total")] - self.blocked_cells(pos)
            s0, s1 = self.cells[(pos, "s0")], self.cells[(pos, "s1")]
            out.append(f"{pos:5} {self.entries_of(pos) - self.blocked(pos):>8} {total:>8} "
                       f"{_pct(s0, total):>18} {_pct(s1, total):>18} {total - s1:>9}")
        out.append("")
        out.append("## POS-Deckung — alle Zellen der fette NVH (ungegenerierbare Einträge inkl.)")
        out.append(f"{'POS':5} {'Einträge':>8} {'Zellen':>8} {'Stufe 0':>18} {'mit Stämmen':>18}")
        for pos in positions:
            if not self.entries_of(pos):
                continue
            total = self.cells[(pos, "total")]
            s0, s1 = self.cells[(pos, "s0")], self.cells[(pos, "s1")]
            out.append(f"{pos:5} {self.entries_of(pos):>8} {total:>8} "
                       f"{_pct(s0, total):>18} {_pct(s1, total):>18}")
        out.append("")
        out.append("## POS-Deckung nach Zellenklasse (finite Verben vs. Partizip-Grid)")
        out.append(f"{'POS':5} {'Klasse':10} {'Zellen':>8} {'Stufe 0':>18} {'mit Stämmen':>18} "
                   f"{'Overrides':>9}")
        for (pos, cls), total in sorted(self.class_cells.items()):
            if pos not in positions:
                continue
            s0, s1 = self.class_s0[(pos, cls)], self.class_s1[(pos, cls)]
            out.append(f"{pos:5} {cls:10} {total:>8} {_pct(s0, total):>18} "
                       f"{_pct(s1, total):>18} {total - s1:>9}")
        out.append("")
        out.append("## Paradigmen (Einträge / Stufe-0-vollständig / Stamm-Einträge / "
                   "Stamm-Felder / Rest-Overrides)")
        out.append(f"{'POS':5} {'Par':>6} {'Eintr':>6} {'Stufe0':>7} {'Stamm':>6} "
                   f"{'Stamm-Felder':<26} {'Overr.':>7}")
        for (pos, paradigm), n in sorted(self.entries.items()):
            if pos not in positions:
                continue
            complete = self.s0_complete[(pos, paradigm)]
            stemmed = self.stem_entries[(pos, paradigm)]
            over = self.overrides[(pos, paradigm)]
            if not (complete or stemmed or over):
                continue
            fields = ", ".join(f"{role}={n}" for (p, par, role), n in sorted(
                self.stem_fields.items()) if p == pos and par == paradigm)
            out.append(f"{pos:5} {paradigm:>6} {n:>6} {complete:>7} {stemmed:>6} "
                       f"{fields:<26} {over:>7}")
        out.append("")
        out.append("## Lint / Befunde")
        out.append(f"  redundante Stämme (Stamm == Stufe-0-Stamm):     "
                   f"{sum(self.lint_redundant_stem.values())}")
        out.append(f"  Overrides, die doch generierbar sind:          "
                   f"{sum(self.lint_generable_override.values())}")
        out.append(f"  Overrides an Varianten-Slots:                 "
                   f"{sum(self.override_variant.values())}")
        for (pos, reason), n in sorted(self.skipped.items()):
            cells = self.status_cells[(pos, reason)]
            out.append(f"  übersprungen {pos:5} {reason:24} {n:>7} Einträge"
                       + (f", {cells} Zellen (alle Override)" if cells else ""))
        out.append(f"  Fixpunkt-Runden:                              "
                   f"{dict(sorted(self.rounds.items()))}")
        out.append(f"  nicht konvergiert:                            "
                   f"{sum(self.unstable.values())}")
        return "\n".join(out) + "\n"


def _pct(part: int, total: int) -> str:
    return f"{part / total * 100:.2f} % ({part})" if total else "-"


# ── Verdichtung (Einträge → lean NVH) ──────────────────────────────────────


def compress(entries: Iterable[Entry], *, lemma_only: bool = False, rounds: int = 4,
             dense: bool = False, stats: Stats | None = None
             ) -> Iterator[tuple[Entry, Derivation]]:
    """Jeden Eintrag der fette NVH einmal ableiten — einschließlich derer, die nichts
    zu komprimieren haben.

    ``dense`` sagt, dass die Eingabe selbst eine verdichtete NVH ist (siehe
    ``_derive_once``); der Idempotenz-Lauf benutzt es.

    Die lean NVH enthält **denselben** Einträgebestand wie die fette: ein Eintrag,
    den Stufe 0 (bzw. die gelieferten Stämme) vollständig deckt, wird ohne jede
    Formzeile geschrieben, ein Eintrag ohne ``pos``/``paradigm`` (Varianteneinträge
    der NVH: ``variantSkeleton``/``variantOf``) behält seine Metadaten und — falls er
    je Zellen hätte — alle Zellen als Override. Genau das macht den zweiten Lauf
    idempotent: die lean NVH ist wieder eine vollständige Eingabe.
    """
    stats = stats if stats is not None else Stats()
    for entry in entries:
        if not (entry.pos and entry.paradigm):
            reason = ("kein pos/paradigm" if entry.attested
                      else "Varianteneintrag (keine Zellen)")
            stats.skipped[(entry.pos or "-", reason)] += 1
            yield entry, Derivation(overrides=dict(entry.attested), cells=entry.cells,
                                    status="kein-pos-paradigma", attested=entry.attested)
            continue
        derivation = derive_entry(entry.pos, entry.paradigm, entry.lemma,
                                  entry.gender, entry.attested,
                                  supplied=entry.stems, dense=dense,
                                  lemma_only=lemma_only, rounds=rounds)
        stats.record(entry, derivation)
        yield entry, derivation


def verify(pairs: Sequence[tuple[Entry, Derivation]]) -> list[str]:
    """Verlustfreiheit zellweise prüfen; liefert eine Liste von Fehlern.

    Geprüft wird gegen ``entry.attested`` — die Zellen der **fette NVH** — und
    nicht gegen ``derivation.missing``: die Overrides sind per Konstruktion genau
    der Rest, deshalb wäre die Ableitung als Zeuge ihres eigenen Rechts untauglich.
    """
    out: list[str] = []
    for entry, derivation in pairs:
        missing = uncovered(entry.attested, derivation.expanded)
        if missing:
            out.append(f"{entry.pos} {entry.paradigm} {entry.lemma}: {missing}")
    return out


# ── CLI ─────────────────────────────────────────────────────────────────────


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="compress_forms.py", description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="source", type=Path, default=FULL_NVH,
                        help="fette NVH (default: %(default)s)")
    parser.add_argument("--out", dest="target", type=Path, default=LEAN_NVH,
                        help="lean NVH (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="nicht schreiben, nur Statistik")
    parser.add_argument("--dense-input", action="store_true",
                        help="Eingabe ist selbst eine verdichtete NVH: Zellen bleiben "
                             "Override, Stämme bleiben, nichts wird neu abgeleitet")
    parser.add_argument("--lemma-only", action="store_true",
                        help="Modus „nur Lemma“: Stufe 0, keine gelieferten Stämme")
    parser.add_argument("--rounds", type=int, default=4,
                        help="Fixpunkt-Runden je Eintrag (default: %(default)s)")
    parser.add_argument("--limit", type=int, help="nur die ersten N Einträge")
    parser.add_argument("--report", type=Path, help="Statistik hierhin statt stderr")
    parser.add_argument("--no-stats", action="store_true", help="keine Statistik")
    parser.add_argument("--verify-idempotent", action="store_true",
                        help="lean NVH neu einlesen, erneut verdichten, vergleichen")
    args = parser.parse_args(argv)

    entries = read_nvh(args.source)
    if args.limit:
        entries = entries[:args.limit]
    stats = Stats()
    done = list(compress(entries, lemma_only=args.lemma_only, dense=args.dense_input,
                         rounds=args.rounds, stats=stats))
    problems = verify(done)
    mode = "nur Lemma (Stufe 0)" if args.lemma_only else "mit gelieferten Stämmen"

    if not args.no_stats:
        report = (f"# Kompressor — {args.source.name} → {args.target.name} "
                  f"[{mode}, {len(done)} Einträge]\n"
                  + stats.report(title=f"Kennzahlen ({mode})"))
        if args.report:
            args.report.write_text(report, encoding="utf-8")
        else:
            print(report, file=sys.stderr)
    for problem in problems[:20]:
        print(f"VERLUST: {problem}", file=sys.stderr)

    if args.dry_run:
        return 1 if problems else 0

    args.target.parent.mkdir(parents=True, exist_ok=True)
    write_nvh(args.target, done)

    status = 1 if problems else 0
    if args.verify_idempotent:
        again = read_nvh(args.target)
        done2 = list(compress(again, lemma_only=args.lemma_only, dense=True,
                              rounds=args.rounds, stats=Stats()))
        same = len(done2) == len(done) and all(
            (d1.stems, d1.overrides) == (d2.stems, d2.overrides)
            for (_, d1), (_, d2) in zip(done, done2))
        # Idempotenz allein ist schwach: zwei Läufe können übereinstimmen und beide
        # Zellen der fette NVH verloren haben. Deshalb wird die zweite Runde noch
        # einmal gegen die **Zellen des ersten Laufs** geprüft — die fette NVH liegt
        # hier nicht vor, ihr Zeugnis ist ``entry.attested`` aus ``done``.
        losses = [f"{e1.pos} {e1.paradigm} {e1.lemma}: {m}"
                  for (e1, _), (_, d2) in zip(done, done2)
                  for m in [uncovered(e1.attested, d2.expanded)] if m]
        print(f"IDEMPOTENZ: {'ok' if same else 'FEHLGESCHLAGEN'} "
              f"({len(done2)} Einträge)", file=sys.stderr)
        if losses:
            print(f"VERLUST in Runde 2: {len(losses)} Einträge, "
                  f"z. B. {losses[0]}", file=sys.stderr)
        status = status or (0 if same and not losses else 1)
    return status


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
