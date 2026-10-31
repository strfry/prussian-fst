"""Principal-form measurement: how many Twanksta cells do principal forms + one
suffix rule per slot explain?

Model: every cell is derived from ONE principal form (the lemma or another cell of
the entry) by a suffix replacement "drop x, append y". Rules are learned per key and
slot as a decision list ordered by support (first matching rule wins). Everything is
cross-validated by lemma (rules learned on 4/5 of the lexemes, tested on the rest),
so the numbers are not a fit to Twanksta.

Keys:
  num    Twanksta paradigm number (as today)
  none   no key: only the shape of the source principal form decides
  shape  endings of all principal forms (a data-driven "stem class")

Cost of a lean NVH under this model = principal forms not predictable from the lemma
(supplied, stage 1) + cells no rule hits (overrides). Compared against today's lean
NVH (stemOverrides + overrides).

    uv run python scratch/kennform/measure.py      # report -> scratch/kennform/REPORT.md
"""

from __future__ import annotations

import collections
import json
import os
import random
import re
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "gen"))
import compress_forms as cf  # noqa: E402

FAT = REPO.parent / "corpus/parsed/twanksta.nvh"
LEAN = REPO.parent / "corpus/parsed/twanksta_dmlex.nvh"
OUT = Path(__file__).resolve().parent
LEMMA = "lemma"
MAXN = 6          # longest replaced suffix
FOLDS = 5
KEYS = ("num", "none", "shape")

CONFIGS = {
    "verb": [
        (LEMMA,),
        (LEMMA, "prs.sp3"),
        (LEMMA, "prs.sp3", "prt.sp3"),
        (LEMMA, "prs.sp3", "prt.sp3", "part.prs.act.msc.sg.nom"),
        (LEMMA, "prs.sp3", "prt.sp3", "part.prs.act.msc.sg.nom", "part.prf.act.msc.sg.nom"),
    ],
    "noun": [
        (LEMMA,),
        (LEMMA, "sg.gen"),
        (LEMMA, "pl.dat"),
        (LEMMA, "sg.gen", "pl.dat"),
    ],
    "adj": [
        (LEMMA,),
        (LEMMA, "comp.msc.sg.nom"),
        (LEMMA, "comp.msc.sg.nom", "msc.pl.dat"),
        (LEMMA, "comp.msc.sg.nom", "msc.sg.gen"),
        (LEMMA, "comp.msc.sg.nom", "fem.sg.nom"),
        (LEMMA, "comp.msc.sg.nom", "msc.pl.nom"),
        (LEMMA, "comp.msc.sg.nom", "neu.sg.nom"),
    ],
}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def strip_si(text: str) -> str:
    return text[:-3] if text.endswith(" si") else text


def load() -> dict[str, list[dict]]:
    """Fat NVH -> per pos a list of {lemma, par, cells: slot -> form | None}.

    A slot with several variants is None: no single rule produces it, so it is an
    override in any model.
    """
    out: dict[str, list[dict]] = collections.defaultdict(list)
    entries, _review = cf.repair_dumper_artifacts(cf.read_nvh(FAT))   # as the compressor
    for e in entries:
        if e.pos not in CONFIGS or not e.paradigm or not e.attested:
            continue
        lemma = strip_si(nfc(e.lemma))
        if " " in lemma:
            continue
        cells = {}
        for slot, forms in e.attested.items():
            forms = {strip_si(nfc(f)) for f in forms}
            cells[slot] = forms.pop() if len(forms) == 1 else None
        cells[LEMMA] = lemma
        out[e.pos].append({"lemma": lemma, "par": e.paradigm, "cells": cells})
    return out


_SHORT = str.maketrans("āēīōū", "aeiou")
_GEMINATE = re.compile(r"([bcdfghjklmnprstvwz])\1")
MAXPRE = 3        # longest prepended string (superlative uka-)


def destress(stem: str) -> str:
    """Accent shift onto the ending: shorten every macron, simplify every geminate.

    The same reduction gen/accent.regex applies before ^ (Shorten + Degem).
    """
    return _GEMINATE.sub(r"\1", stem.translate(_SHORT))


def candidates(k: str, f: str):
    """Every rule (pre, x, y, d) with k = s+x and f = pre + d(s) + y.

    ``d`` is ``destress`` or the identity, |x| <= MAXN, |pre| <= MAXPRE, s non-empty.
    """
    for i in range(0, min(MAXPRE, len(f)) + 1):
        pre, g = f[:i], f[i:]
        if i and not (g[:1] == k[:1] or g[:1] == k[:1].translate(_SHORT)):
            continue
        for n in range(0, min(len(k) - 1, MAXN) + 1):
            stem = k[: len(k) - n]
            light = destress(stem)
            if g.startswith(stem):
                yield pre, k[len(stem):], g[len(stem):], False
            if light != stem and g.startswith(light):
                yield pre, k[len(stem):], g[len(light):], True


def apply(rules: list[tuple[str, str, str, bool]], k: str) -> str | None:
    for pre, x, y, d in rules:
        if k.endswith(x) and len(k) > len(x):
            stem = k[: len(k) - len(x)]
            return pre + (destress(stem) if d else stem) + y
    return None


def shape(entry: dict, kenn: tuple[str, ...]) -> tuple:
    return tuple((entry["cells"].get(k) or "?")[-2:] for k in kenn)


def keyfun(name: str, kenn: tuple[str, ...]):
    if name == "num":
        return lambda e: e["par"]
    if name == "shape":
        return lambda e: shape(e, kenn)
    return lambda e: ""


class Model:
    """Per (key, slot): the best source principal form and its decision list."""

    def __init__(self, train: list[dict], kenn: tuple[str, ...], key):
        self.key = key
        votes = collections.defaultdict(collections.Counter)    # (key, slot, src) -> rule
        global_votes = collections.defaultdict(collections.Counter)
        for e in train:
            kk = key(e)
            for slot, f in e["cells"].items():
                if f is None or slot == LEMMA:
                    continue
                for src in kenn:
                    k = e["cells"].get(src)
                    if src == slot or not k:
                        continue
                    for rule in candidates(k, f):
                        votes[(kk, slot, src)][rule] += 1
                        global_votes[(slot, src)][rule] += 1
        self.rules = {g: [r for r, _ in c.most_common()] for g, c in votes.items()}
        self.grules = {g: [r for r, _ in c.most_common()] for g, c in global_votes.items()}
        # Source per (key, slot): the one with the highest training accuracy.
        hits = collections.defaultdict(collections.Counter)
        for e in train:
            kk = key(e)
            for slot, f in e["cells"].items():
                if f is None or slot == LEMMA:
                    continue
                for src in kenn:
                    k = e["cells"].get(src)
                    if src != slot and k and apply(self.rules.get((kk, slot, src), []), k) == f:
                        hits[(kk, slot)][src] += 1
        self.src = {g: c.most_common(1)[0][0] for g, c in hits.items()}
        slot_hits = collections.defaultdict(collections.Counter)
        for (_kk, slot), c in hits.items():
            slot_hits[slot].update(c)
        self.gsrc = {s: c.most_common(1)[0][0] for s, c in slot_hits.items()}

    def predict(self, e: dict, slot: str, known: dict) -> str | None:
        """``known``: principal form -> form (true value once stored in the lean NVH)."""
        kk = self.key(e)
        src = self.src.get((kk, slot))
        rules = self.rules.get((kk, slot, src)) if src else None
        if src is None or not rules:                     # unseen key: global rules
            src = self.gsrc.get(slot)
            rules = self.grules.get((slot, src), []) if src else []
        k = known.get(src)
        return apply(rules, k) if k else None


def slot_group(slot: str) -> str:
    parts = slot.split(".")
    if parts[0] == "part":
        return ".".join(parts[:3])
    if parts[0] in ("comp", "superl", "adv", "prs", "prt", "subj", "imprt", "opt"):
        return parts[0]
    return "pos"


def evaluate(entries: list[dict], kenn: tuple[str, ...], keyname: str, folds: int = FOLDS):
    """Cross-validated: stored principal forms, cell hits, per group/paradigm, misses."""
    rng = random.Random(0)
    lemmas = sorted({e["lemma"] for e in entries})
    rng.shuffle(lemmas)
    fold_of = {lemma: i % folds for i, lemma in enumerate(lemmas)}
    stats = collections.Counter()
    by_group = collections.defaultdict(collections.Counter)
    by_par = collections.defaultdict(collections.Counter)
    misses = collections.defaultdict(list)
    for fold in range(folds):
        train = [e for e in entries if fold_of[e["lemma"]] != fold]
        test = [e for e in entries if fold_of[e["lemma"]] == fold]
        # Stage 0 for the principal forms: lemma -> principal form, same key type
        # (shape of the lemma alone for "shape").
        lemma_model = Model(train, (LEMMA,), keyfun(keyname, (LEMMA,)))
        model = Model(train, kenn, keyfun(keyname, kenn))
        for e in test:
            cells = e["cells"]
            known = {LEMMA: e["lemma"]}
            for k in kenn[1:]:
                true = cells.get(k)
                if true is None:
                    continue
                if lemma_model.predict(e, k, known) != true:
                    stats["kennform_stored"] += 1
                known[k] = true
            for slot, f in cells.items():
                if slot == LEMMA or slot in kenn:
                    continue
                group = slot_group(slot)
                got = model.predict(e, slot, known) if f is not None else None
                ok = f is not None and got == f
                for c in (stats, by_group[group], by_par[e["par"]]):
                    c["cells"] += 1
                    c["ok"] += ok
                if not ok:
                    misses[e["par"]].append((e["lemma"], slot, f, got))
            stats["entries"] += 1
    return stats, by_group, by_par, misses


def lean_cost(pos: str, lemmas: set[str]) -> collections.Counter:
    """Today's lean NVH: supplied stems + override cells of the measured lexemes."""
    c = collections.Counter()
    for e in cf.read_nvh(LEAN):
        if e.pos != pos or strip_si(nfc(e.lemma)) not in lemmas:
            continue
        c["entries"] += 1
        c["stems"] += len(e.stems)
        c["overrides"] += len(e.attested)
    return c


def pct(a: int, b: int) -> str:
    return f"{a / b * 100:.2f} %" if b else "-"


_DATA: dict[str, list[dict]] = {}


def _job(args: tuple[str, tuple[str, ...], str]):
    """One (pos, principal forms, key) evaluation in a worker process."""
    pos, kenn, keyname = args
    if not _DATA:
        _DATA.update(load())
    stats, by_group, by_par, misses = evaluate(_DATA[pos], kenn, keyname)
    return args, stats, dict(by_group), dict(by_par), {p: m[:3] for p, m in misses.items()}


def main() -> int:
    data = load()
    jobs = [(pos, kenn, keyname) for pos, configs in CONFIGS.items()
            for kenn in configs for keyname in KEYS]
    with ProcessPoolExecutor(max_workers=min(len(jobs), max((os.cpu_count() or 2) - 4, 1))) as pool:
        results = {}
        for args, *rest in pool.map(_job, jobs):
            results[args] = rest
            print(*args, pct(rest[0]["ok"], rest[0]["cells"]), file=sys.stderr, flush=True)
    lines = ["# Principal-form measurement", "",
             f"Source: `{FAT.relative_to(REPO.parent)}`, cross-validated ({FOLDS} folds by "
             "lemma). Cells = every slot except the principal forms; slots with variants "
             "count as overrides.", ""]
    summary = {}
    for pos, configs in CONFIGS.items():
        entries = data[pos]
        lean = lean_cost(pos, {e["lemma"] for e in entries})
        lines += [f"## {pos} ({len(entries)} lexemes)", "",
                  f"Today's lean NVH for these lexemes: {lean['stems']} stems + "
                  f"{lean['overrides']} override cells = "
                  f"**{lean['stems'] + lean['overrides']}** ({lean['entries']} entries found).",
                  "",
                  "| principal forms | key | cells right | principal forms stored "
                  "| overrides | cost |", "|---|---|---|---|---|---|"]
        best = None
        for kenn in configs:
            for keyname in KEYS:
                stats, by_group, by_par, misses = results[(pos, kenn, keyname)]
                overrides = stats["cells"] - stats["ok"]
                cost = stats["kennform_stored"] + overrides
                lines.append(f"| {', '.join(kenn)} | {keyname} "
                             f"| {pct(stats['ok'], stats['cells'])} "
                             f"| {stats['kennform_stored']} | {overrides} | {cost} |")
                if best is None or cost < best[0]:
                    best = (cost, kenn, keyname, by_group, by_par, misses)
        cost, kenn, keyname, by_group, by_par, misses = best
        summary[pos] = {"principal_forms": kenn, "key": keyname, "cost": cost,
                        "lean_cost": lean["stems"] + lean["overrides"]}
        lines += ["", f"Best configuration: **{', '.join(kenn)}** with key **{keyname}** "
                  f"(cost {cost}).", "", "| slot group | right | cells |", "|---|---|---|"]
        for g in sorted(by_group):
            lines.append(f"| {g} | {pct(by_group[g]['ok'], by_group[g]['cells'])} "
                         f"| {by_group[g]['cells']} |")
        lines += ["", "Weakest paradigms (absolute overrides):", "",
                  "| par. | right | cells | examples (lemma, slot, Twanksta != rule) |",
                  "|---|---|---|---|"]
        worst = sorted(by_par, key=lambda p: by_par[p]["ok"] - by_par[p]["cells"])[:15]
        for p in worst:
            ex = "; ".join(f"{lemma} {s}: {f} != {g}" for lemma, s, f, g in misses.get(p, [])[:3])
            lines.append(f"| {p} | {pct(by_par[p]['ok'], by_par[p]['cells'])} "
                         f"| {by_par[p]['cells']} | {ex} |")
        lines.append("")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    print(f"-> {OUT / 'REPORT.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
