"""Compressor: fat NVH -> lean NVH (word list + only what the rules do not give).

The fat NVH (``twanksta.nvh``) lists every Twanksta cell as ``inflectedForm`` +
``tag``. Per entry the compressor keeps exactly the cells the generator
(``gen/generator.py``) does not reproduce from the lemma:

1. principal forms (sg.gen, prs.sp3, ...) that the lemma rule gets wrong; stored,
   they become the source of their dependent cells,
2. every other slot the generator then still gets wrong, as an override.

Both are plain ``inflectedForm`` cells; the lean NVH has no other lexical field. An
override replaces its slot, so a wrong rule form never survives next to the listed
one. The pair is exact by construction and checked by ``verify``:

    generate(lemma, cells=overrides) ⊕ overrides == fat cells     (⊕ = replace slot)

Entries without a known paradigm keep all their cells.

    uv run python gen/compress_forms.py --dry-run          # statistics only
    uv run python gen/compress_forms.py --out build/lean.nvh --verify-roundtrip
"""

from __future__ import annotations

import argparse
import collections
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generator as gen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT.parent / "corpus" / "parsed"
FULL_NVH = PARSED / "twanksta.nvh"
LEAN_NVH = PARSED / "twanksta_dmlex.nvh"
GENDERS = ("masc", "fem", "neut")

# Retired lean-NVH field (stems per role); dropped when read.
_RETIRED_FIELDS = ("stemOverrides",)

# Known Twanksta dumper error: some cells carry the paradigm number glued to the
# form (federācija52, ukaizpilninamins27). No Prussian word form contains a digit,
# so removing the digits restores the cell; the repaired cells go to a review list.
REVIEW_ARTIFACTS = ROOT / "build" / "review_dumper_artifacts.tsv"


@dataclass(frozen=True)
class Entry:
    """One NVH entry: header facts + cells.

    ``attested`` maps slot -> surfaces (several surfaces are variants of one slot).
    ``head``/``tail`` are the raw lines around the ``inflectedForm`` blocks, so the
    writer keeps ``id``, ``label``, ``sense``, ``legacy`` and ``relation`` byte-equal.
    """

    lemma: str
    pos: str = ""
    paradigm: str = ""
    gender: str = ""
    numtype: str = ""
    attested: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    head: tuple[str, ...] = ()
    tail: tuple[str, ...] = ()

    @property
    def cells(self) -> int:
        return sum(len(v) for v in self.attested.values())


# ── NVH reader/writer ────────────────────────────────────────────────────────


def _split_pos(value: str) -> tuple[str, str]:
    """``noun-masc`` (legacy spelling) -> ``("noun", "masc")``."""
    pos, _, gender = value.partition("-")
    return pos, gender if gender in GENDERS else ""


def parse_nvh(text: str) -> list[Entry]:
    """NVH text -> entries. Surfaces are NFC-normalised."""
    entries: list[Entry] = []
    lemma: str | None = None
    pos = paradigm = gender = numtype = ""
    forms: dict[str, set[str]] = {}
    head: list[str] = []
    tail: list[str] = []
    saw_form = False
    form: str | None = None

    def flush() -> None:
        if lemma is None:
            return
        entries.append(Entry(
            lemma=lemma, pos=pos, paradigm=paradigm, gender=gender, numtype=numtype,
            attested={slot: tuple(sorted(s)) for slot, s in sorted(forms.items())},
            head=tuple(head), tail=tuple(tail)))

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
            pos = paradigm = gender = numtype = ""
            forms, head, tail = {}, [], []
            saw_form, form = False, None
            continue
        if indent == 2:
            if key == "inflectedForm":
                form, saw_form = value, True
                continue
            if key in _RETIRED_FIELDS:
                continue
            if key == "pos":
                pos, gender = _split_pos(value)
            elif key == "gender":
                gender = value
            elif key == "paradigm":
                paradigm = value
            elif key == "numtype":
                numtype = value
            (tail if saw_form else head).append(line)
            continue
        if form is not None and key == "tag":
            forms.setdefault(value, set()).add(gen.nfc(form))
            form = None
            continue
        (tail if saw_form else head).append(line)
    flush()
    return entries


def read_nvh(path: str | Path) -> list[Entry]:
    return parse_nvh(Path(path).read_text(encoding="utf-8"))


def render_entry(entry: Entry, overrides: Mapping[str, Sequence[str]] | None = None) -> str:
    """A lean entry: raw header + the kept cells, in the slot order of the input."""
    overrides = overrides or {}
    lines = [f"entry: {entry.lemma}", *entry.head]
    slots = list(entry.attested) + [s for s in overrides if s not in entry.attested]
    for slot in slots:
        for surface in sorted(overrides.get(slot, ())):
            lines.append(f"  inflectedForm: {surface}")
            lines.append(f"    tag: {slot}")
    lines.extend(entry.tail)
    return "\n".join(lines) + "\n"


def write_nvh(path: str | Path, pairs: Iterable[tuple[Entry, "Derivation"]]) -> None:
    Path(path).write_text("".join(render_entry(e, d.overrides) for e, d in pairs),
                          encoding="utf-8")


# ── Dumper artifacts ─────────────────────────────────────────────────────────


def is_dumper_artifact(lemma: str, paradigm: str, surface: str) -> bool:
    """A digit anywhere in the surface: no real Prussian form contains one."""
    return any(ch.isdigit() for ch in surface)


def repair_surface(surface: str, paradigm: str = "") -> str:
    """Remove a glued paradigm number (``Dānija52`` -> ``Dānija``).

    Lettered paradigms are glued with their letter (``Kirsnagārbija35a``); when the
    entry's paradigm occurs in the surface it is removed whole, otherwise only the
    digits.
    """
    if paradigm and not paradigm.isdigit():
        i = surface.rfind(paradigm)
        if i >= 0 and (i == 0 or not surface[i - 1].isdigit()):
            surface = surface[:i] + surface[i + len(paradigm):]
    return "".join(ch for ch in surface if not ch.isdigit())


def repair_dumper_artifacts(entries: Iterable[Entry]
                            ) -> tuple[list[Entry], list[tuple[str, str, str]]]:
    """Repair glued-paradigm cells; returns (entries, [(lemma, paradigm, slot)])."""
    clean: list[Entry] = []
    review: list[tuple[str, str, str]] = []
    for entry in entries:
        if not entry.attested:
            clean.append(entry)
            continue
        repaired: dict[str, tuple[str, ...]] = {}
        for slot, surfaces in entry.attested.items():
            out: list[str] = []
            for s in surfaces:
                if is_dumper_artifact(entry.lemma, entry.paradigm, s):
                    review.append((entry.lemma, entry.paradigm, slot))
                    s = repair_surface(s, entry.paradigm)
                if s and s not in out:
                    out.append(s)
            if out:
                repaired[slot] = tuple(out)
        clean.append(replace(entry, attested=repaired))
    return clean, review


def write_review(path: Path, review: Iterable[tuple[str, str, str]]) -> int:
    rows = list(review)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("lemma\tparadigm\tslot\n"
                    + "".join(f"{l}\t{p}\t{s}\n" for l, p, s in rows), encoding="utf-8")
    return len(rows)


# ── Cell algebra ─────────────────────────────────────────────────────────────


def merged(generated: Mapping[str, Sequence[str]],
           overrides: Mapping[str, Sequence[str]]) -> dict[str, frozenset[str]]:
    """``generated ⊕ overrides``: an override replaces its slot."""
    out = {slot: frozenset(forms) for slot, forms in generated.items()}
    for slot, surfaces in overrides.items():
        out[slot] = frozenset(surfaces)
    return out


def mismatched(attested: Mapping[str, Sequence[str]],
               produced: Mapping[str, Sequence[str]]) -> dict[str, tuple[str, ...]]:
    """Listed slots ``produced`` does not hit exactly, with their full cell."""
    return {slot: tuple(surfaces) for slot, surfaces in attested.items()
            if frozenset(surfaces) != frozenset(produced.get(slot, ()))}


def inexact(attested: Mapping[str, Sequence[str]],
            expanded: Mapping[str, Sequence[str]]) -> dict[str, dict]:
    """``{"missing": …, "extra": …}`` per listed slot; empty when exact."""
    missing, extra = {}, {}
    for slot, surfaces in attested.items():
        have = frozenset(expanded.get(slot, ()))
        if lost := tuple(s for s in surfaces if s not in have):
            missing[slot] = lost
        if more := tuple(sorted(have - frozenset(surfaces))):
            extra[slot] = more
    return {k: v for k, v in (("missing", missing), ("extra", extra)) if v}


def expand(entry: Entry) -> dict[str, frozenset[str]]:
    """Cells of a lean entry: ``generate(cells) ⊕ cells``. Unknown paradigm: the cells."""
    try:
        generated = gen.generate(entry.pos, entry.paradigm, entry.lemma, entry.attested)
    except KeyError:
        generated = {}
    return merged(generated, entry.attested)


# ── Derivation ───────────────────────────────────────────────────────────────


@dataclass
class Derivation:
    """Result for one entry."""

    overrides: dict[str, tuple[str, ...]] = field(default_factory=dict)
    generated: dict[str, tuple[str, ...]] = field(default_factory=dict)
    lemma_only: dict[str, tuple[str, ...]] = field(default_factory=dict)
    principal: tuple[str, ...] = ()          # principal forms kept (wrong from the lemma)
    status: str = "ok"                        # ok | unknown-paradigm | no-pos-paradigm

    @property
    def expanded(self) -> dict[str, frozenset[str]]:
        return merged(self.generated, self.overrides)


def derive_entry(entry: Entry) -> Derivation:
    """Keep wrong principal forms, regenerate from them, keep what is still wrong."""
    attested = entry.attested
    if not (entry.pos and entry.paradigm):
        return Derivation(overrides=dict(attested), status="no-pos-paradigm")
    try:
        lemma_only = gen.generate(entry.pos, entry.paradigm, entry.lemma)
    except KeyError:
        return Derivation(overrides=dict(attested), status="unknown-paradigm")
    principal = {slot: attested[slot] for slot in gen.PRINCIPAL.get(gen.family(entry.pos), ())
                 if slot in attested
                 and frozenset(attested[slot]) != frozenset(lemma_only.get(slot, ()))}
    generated = gen.generate(entry.pos, entry.paradigm, entry.lemma, principal)
    return Derivation(overrides=mismatched(attested, generated), generated=generated,
                      lemma_only=lemma_only, principal=tuple(principal))


def compress(entries: Iterable[Entry], stats: "Stats | None" = None
             ) -> Iterator[tuple[Entry, Derivation]]:
    """Derive every entry, including those with nothing to compress."""
    for entry in entries:
        derivation = derive_entry(entry)
        if stats is not None:
            stats.record(entry, derivation)
        yield entry, derivation


def verify(pairs: Sequence[tuple[Entry, Derivation]]) -> list[str]:
    """Exactness per listed slot against the fat cells (``entry.attested``)."""
    return [f"{e.pos} {e.paradigm} {e.lemma}: {err}"
            for e, d in pairs if (err := inexact(e.attested, d.expanded))]


# ── Statistics ───────────────────────────────────────────────────────────────


def slot_class(pos: str, slot: str) -> str:
    """Verb cells split into finite and participle (80 % of verb cells are participles)."""
    return "participle" if pos == "verb" and slot.startswith("part.") else pos


@dataclass
class Stats:
    entries: collections.Counter = field(default_factory=collections.Counter)
    cells: collections.Counter = field(default_factory=collections.Counter)
    lemma_hits: collections.Counter = field(default_factory=collections.Counter)
    hits: collections.Counter = field(default_factory=collections.Counter)
    principal: collections.Counter = field(default_factory=collections.Counter)
    overrides: collections.Counter = field(default_factory=collections.Counter)
    by_paradigm: collections.Counter = field(default_factory=collections.Counter)
    status: collections.Counter = field(default_factory=collections.Counter)

    def record(self, entry: Entry, d: Derivation) -> None:
        self.status[(entry.pos or "-", d.status)] += 1
        n_over = sum(len(v) for v in d.overrides.values())
        if d.status != "ok":
            self.cells[(entry.pos or "-", "blocked")] += entry.cells
            return
        self.entries[entry.pos] += 1
        self.principal[entry.pos] += len(d.principal)
        self.by_paradigm[(entry.pos, entry.paradigm)] += n_over
        for slot, surfaces in entry.attested.items():
            cls = (entry.pos, slot_class(entry.pos, slot))
            self.cells[cls] += len(surfaces)
            self.lemma_hits[cls] += sum(s in d.lemma_only.get(slot, ()) for s in surfaces)
            self.hits[cls] += sum(s in d.generated.get(slot, ()) for s in surfaces)
            if slot in d.overrides:
                self.overrides[cls] += len(surfaces)

    def report(self) -> str:
        out = ["# Compressor statistics", "",
               f"{'class':18} {'cells':>8} {'from lemma':>12} {'with principal':>15} "
               f"{'overrides':>10}"]
        for cls in sorted(k for k in self.cells if k[1] != "blocked"):
            n = self.cells[cls]
            out.append(f"{cls[0] + '/' + cls[1]:18} {n:>8} {_pct(self.lemma_hits[cls], n):>12} "
                       f"{_pct(self.hits[cls], n):>15} {self.overrides[cls]:>10}")
        out += ["", "principal forms kept: "
                + ", ".join(f"{p} {n}" for p, n in sorted(self.principal.items())),
                "entries by status: "
                + ", ".join(f"{p}/{s} {n}" for (p, s), n in sorted(self.status.items())),
                "", "paradigms with the most override cells:"]
        for (pos, par), n in self.by_paradigm.most_common(25):
            out.append(f"  {pos:5} {par:>5} {n:>6}")
        return "\n".join(out) + "\n"


def _pct(part: int, total: int) -> str:
    return f"{part / total * 100:.2f} %" if total else "-"


# ── CLI ──────────────────────────────────────────────────────────────────────


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compress_forms.py",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--in", dest="source", type=Path, default=FULL_NVH)
    parser.add_argument("--out", dest="target", type=Path, default=LEAN_NVH)
    parser.add_argument("--dry-run", action="store_true", help="statistics only")
    parser.add_argument("--limit", type=int, help="first N entries only")
    parser.add_argument("--report", type=Path, help="statistics here instead of stderr")
    parser.add_argument("--keep-artifacts", action="store_true",
                        help="do not repair glued paradigm numbers")
    parser.add_argument("--review-out", type=Path, default=REVIEW_ARTIFACTS)
    parser.add_argument("--verify-roundtrip", action="store_true",
                        help="read the written lean NVH back and expand it against the fat cells")
    args = parser.parse_args(argv)

    entries = read_nvh(args.source)
    if args.limit:
        entries = entries[:args.limit]
    if not args.keep_artifacts:
        entries, review = repair_dumper_artifacts(entries)
        if review:
            n = write_review(args.review_out, review)
            print(f"# dumper artifacts repaired: {n} cells -> {args.review_out}",
                  file=sys.stderr)
    stats = Stats()
    done = list(compress(entries, stats))
    problems = verify(done)
    report = stats.report()
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    else:
        print(report, file=sys.stderr)
    for problem in problems[:20]:
        print(f"NOT EXACT: {problem}", file=sys.stderr)
    if args.dry_run:
        return 1 if problems else 0

    args.target.parent.mkdir(parents=True, exist_ok=True)
    write_nvh(args.target, done)
    status = 1 if problems else 0
    if args.verify_roundtrip:
        lean = read_nvh(args.target)
        losses = [f"{e.lemma}: {err}" for (e, _), l in zip(done, lean)
                  if (err := inexact(e.attested, expand(l)))]
        print(f"ROUNDTRIP: {'ok' if not losses else 'FAILED'} ({len(lean)} entries)"
              + (f", e.g. {losses[0]}" if losses else ""), file=sys.stderr)
        status = status or (1 if losses or len(lean) != len(done) else 0)
    return status


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
