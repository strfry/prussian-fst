"""Derive the paradigm table (gen/paradigms.json) from the dictionary.

The input is the lean NVH, expanded with the current table, so the dictionary's
corrections (edited cells, errata) are what the rules learn; ``--full`` reads an
NVH that lists every cell instead (the Twanksta dump, or a migration expansion).

For every part of speech and paradigm number, and every slot the paradigm has (a
slot listed by more than half of its lexemes), this picks the source principal
form and an ordered suffix-rule list (see gen/generator.py for the notation):

* candidates: every rule "prefix + drop x, add y, optionally destress" that maps a
  source form to the cell for at least MIN_SUPPORT lexemes,
* decision list: candidates ordered most specific ending first (or by support,
  whichever scores better); a rule stays only if it makes at least MIN_SUPPORT
  more cells right than the rule that would fire in its place,
* source: the principal form with the best score, cells right minus MIN_SUPPORT
  per rule (lemma on ties), so a long list never beats a short one by a cell.

MIN_SUPPORT >= 2 keeps single lexemes out of the grammar: what only one word does
is an override of that word, not a rule.

    uv run python gen/derive_paradigms.py                    # -> gen/paradigms.json
    uv run python gen/derive_paradigms.py --full build/full_from_lean.nvh
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compress_forms as cf  # noqa: E402
import generator as gen  # noqa: E402

MAX_DROP = 6
MAX_PREFIX = 3


def candidates(source: str, cell: str):
    """Every rule (prefix, drop, add, destress) with ``apply(rule, source) == cell``."""
    for i in range(0, min(MAX_PREFIX, len(cell)) + 1):
        prefix, rest = cell[:i], cell[i:]
        if i and rest[:1] not in (source[:1], source[:1].translate(gen._SHORT)):
            continue
        for n in range(0, min(len(source) - 1, MAX_DROP) + 1):
            stem = source[: len(source) - n]
            drop = source[len(stem):]
            if rest.startswith(stem):
                yield prefix, drop, rest[len(stem):], False
            light = gen.destress(stem)
            if light != stem and rest.startswith(light):
                yield prefix, drop, rest[len(light):], True


def _prune(rules: list[gen.Rule], examples: list[tuple[str, str]], min_support: int
           ) -> tuple[list[gen.Rule], int]:
    """Drop every rule that does not make at least ``min_support`` more cells right
    than the rule that would fire in its place. Returns (rules, cells right)."""
    applicable = []
    for source, cell in examples:
        applicable.append([(i, gen.apply_rules((r,), source) == cell)
                           for i, r in enumerate(rules)
                           if source.endswith(r[1]) and len(source) > len(r[1])])
    alive = [True] * len(rules)
    while True:
        gain = [0] * len(rules)
        right = 0
        for hits in applicable:
            live = [h for h in hits if alive[h[0]]][:2]
            if not live:
                continue
            first, ok = live[0]
            right += ok
            gain[first] += ok - (live[1][1] if len(live) > 1 else False)
        # One rule at a time: rules that duplicate each other all show gain 0, and
        # removing them together would remove the cell's only rule.
        weakest = min(((g, i) for i, g in enumerate(gain) if alive[i]), default=None)
        if weakest is None or weakest[0] >= min_support:
            return [r for r, a in zip(rules, alive) if a], right
        alive[weakest[1]] = False


def learn(examples: list[tuple[str, str]], min_support: int
          ) -> tuple[list[gen.Rule], int]:
    """Decision list for one (paradigm, slot, source); returns (rules, cells right)."""
    support = collections.Counter()
    for source, cell in examples:
        support.update(set(candidates(source, cell)))
    pool = [r for r, n in support.items() if n >= min_support]
    best: tuple[list[gen.Rule], int] = ([], 0)
    for order in (lambda r: (-len(r[1]), -support[r], r[3], r),     # specific first
                  lambda r: (-support[r], -len(r[1]), r[3], r)):    # support first
        rules, right = _prune(sorted(pool, key=order), examples, min_support)
        if score(rules, right, min_support) > score(*best, min_support):
            best = (rules, right)
    return best


def score(rules: list[gen.Rule], right: int, min_support: int) -> int:
    """Cells right minus the price of the rules: a rule must pay for itself."""
    return right - min_support * len(rules)


def lexemes(path: Path, lean: bool) -> dict[tuple[str, str], list[dict[str, str]]]:
    """NVH -> (family, paradigm) -> lexemes as slot -> single form (+ lemma).

    ``lean``: the file is a lean NVH; every entry is expanded with the current table
    first (``cf.expand``), so the dictionary's own corrections are what is learned.
    """
    entries, _review = cf.repair_dumper_artifacts(cf.read_nvh(path))
    out: dict[tuple[str, str], list[dict[str, str]]] = collections.defaultdict(list)
    for e in entries:
        fam = gen.family(e.pos)
        if fam not in gen.SLOTS or not e.paradigm:
            continue
        lemma = gen.split_si(gen.nfc(e.lemma))[0]
        if " " in lemma:
            continue
        attested = cf.expand(e) if lean else e.attested
        if not attested:
            continue
        cells = {gen.LEMMA: lemma}
        for slot, forms in attested.items():
            forms = {gen.nfc(f) for f in forms}
            if len(forms) == 1:
                cells[slot] = forms.pop()
        out[(fam, e.paradigm)].append(cells)
    return out


def _shared(a: str, b: str) -> int:
    """Number of leading slot components ``a`` and ``b`` share (prt.pl1, prt.sp3 -> 1)."""
    n = 0
    for x, y in zip(a.split("."), b.split(".")):
        if x != y:
            break
        n += 1
    return n


def _sources(slot: str, principal: tuple[str, ...], slots: list[str]) -> list[str]:
    """Candidate sources, preferred first: on equal score a cell follows the principal
    form of its own group (prt.* -> prt.sp3), so correcting that form carries over."""
    near = sorted((p for p in principal if p in slots and _shared(slot, p)),
                  key=lambda p: -_shared(slot, p))
    rest = [p for p in principal if p in slots and p not in near]
    return near + [gen.LEMMA] + rest


def _derive_paradigm(args: tuple[str, list[dict[str, str]], int]) -> dict:
    """Rules of one paradigm: slot -> {"from": source, "rules": [...]}."""
    fam, group, min_support = args
    principal = gen.PRINCIPAL[fam]
    counts = collections.Counter(s for cells in group for s in cells)
    slots = [s for s in gen.SLOTS[fam] if counts[s] * 2 > len(group)]
    spec = {}
    for slot in slots:
        sources = [gen.LEMMA] if slot in principal else _sources(slot, principal, slots)
        best = None
        for source in sources:
            examples = [(c[source], c[slot]) for c in group if source in c and slot in c]
            rules, right = learn(examples, min_support)
            value = score(rules, right, min_support)
            if rules and (best is None or value > best[2]):
                best = (source, rules, value)
        if best:
            spec[slot] = {"from": best[0], "rules": [gen.format_rule(r) for r in best[1]]}
    return spec


def derive(path: Path, min_support: int, jobs: int, lean: bool) -> dict:
    groups = sorted(lexemes(path, lean).items())
    table: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        specs = pool.map(_derive_paradigm,
                         [(fam, group, min_support) for (fam, _), group in groups])
        for ((fam, paradigm), _), spec in zip(groups, specs):
            if spec:
                table[fam][paradigm] = spec
    return {"source": path.name, "min_support": min_support,
            "principal": gen.PRINCIPAL, "paradigms": table}


def dumps(table: dict) -> str:
    """JSON with one line per slot, so a diff of the table shows rule changes."""
    def block(obj, depth: int) -> str:
        if depth == 4 or not isinstance(obj, dict):
            return json.dumps(obj, ensure_ascii=False)
        pad = " " * (depth + 1)
        items = [f"{pad}{json.dumps(k, ensure_ascii=False)}: {block(v, depth + 1)}"
                 for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + " " * depth + "}"
    return block(table, 0) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--lean", type=Path, default=cf.LEAN_NVH,
                        help="lean NVH, expanded with the current table (default: %(default)s)")
    source.add_argument("--full", type=Path, help="NVH that lists every cell")
    parser.add_argument("--out", type=Path, default=gen.TABLE_PATH)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    if args.min_support < 2:
        parser.error("--min-support must be >= 2 (one lexeme is an override, not a rule)")
    table = derive(args.full or args.lean, args.min_support, args.jobs, lean=not args.full)
    args.out.write_text(dumps(table), encoding="utf-8")
    n_rules = sum(len(s["rules"]) for pars in table["paradigms"].values()
                  for slots in pars.values() for s in slots.values())
    print(f"{sum(len(p) for p in table['paradigms'].values())} paradigms, "
          f"{n_rules} rules -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
