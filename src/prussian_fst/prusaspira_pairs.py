#!/usr/bin/env python3
"""Zellpaare twanksta ↔ Prusaspira aus den beiden fetten NVHs.

Werkzeug für die Prusaspira-Stufe (norm/palatal.regex, norm/length.regex), NICHT Teil des FST. Gepaart wird
nur über exakt gleiches ``(Lemma, Paradigma)`` und gleichen Slot-Tag; mehrteilige
Formen (Leerzeichen) fallen weg. Kein Abgleich unscharfer Lemmata.

Ausgabe:
  build/ps_pairs.tsv            tw  ps  tag  lemma  split   (split per Lemma-Hash 80/20)
  build/ps_correspondences.tsv  count  tw_ctx  ps_ctx  tagclasses  example
                                (nur nicht-identische Paare; Diff-Opcodes ±1 Zeichen)

  make build/ps_pairs.tsv
"""

from __future__ import annotations

import collections
import difflib
import hashlib
from pathlib import Path

FST = Path(__file__).resolve().parents[2]
PARSED = FST.parent / "corpus" / "parsed"
TW_NVH = PARSED / "twanksta.nvh"
PS_NVH = PARSED / "prusaspira.nvh"
OUT_PAIRS = FST / "build" / "ps_pairs.tsv"
OUT_CORR = FST / "build" / "ps_correspondences.tsv"


def load(path: Path) -> dict:
    """(lemma, paradigm) → tag → {surface}."""
    data: dict = collections.defaultdict(lambda: collections.defaultdict(set))
    key = None
    lemma = par = form = None
    for line in open(path, encoding="utf-8"):
        if line.startswith("entry: "):
            lemma, par, form = line[7:].strip(), "", None
        elif line.startswith("  paradigm: "):
            par = line[12:].strip()
        elif line.startswith("  inflectedForm: "):
            form = line[17:].strip()
        elif line.startswith("    tag: ") and form is not None:
            data[(lemma, par)][line[9:].strip()].add(form)
            form = None
        elif not line.startswith("    "):
            form = None
    return data


def split_of(lemma: str) -> str:
    h = int(hashlib.sha1(lemma.encode("utf-8")).hexdigest(), 16) % 100
    return "test" if h < 20 else "dev"


def tag_class(tag: str) -> str:
    head = tag.split(".")[0]
    if head in ("sg", "pl"):
        return "noun"
    if head in ("prs", "prt", "subj", "imprt", "opt"):
        return "verb"
    if head in ("msc", "fem", "neu", "def"):
        return "adj"
    return head          # comp, superl, part, adv, nom/gen/… (pron)


def main() -> None:
    tw, ps = load(TW_NVH), load(PS_NVH)
    keys = sorted(set(tw) & set(ps))
    pairs = []
    for key in keys:
        for tag, ps_forms in ps[key].items():
            tw_forms = tw[key].get(tag)
            if not tw_forms:
                continue
            for p in sorted(ps_forms):
                if " " in p:
                    continue
                for t in sorted(tw_forms):
                    if " " not in t:
                        pairs.append((t, p, tag, key[0]))
    OUT_PAIRS.parent.mkdir(exist_ok=True)
    with open(OUT_PAIRS, "w", encoding="utf-8") as fh:
        for t, p, tag, lemma in pairs:
            fh.write(f"{t}\t{p}\t{tag}\t{lemma}\t{split_of(lemma)}\n")

    # Korrespondenzen: je ps-Form die nächstliegende tw-Form desselben Slots.
    best: dict = {}
    for t, p, tag, lemma in pairs:
        k = (p, tag, lemma)
        r = difflib.SequenceMatcher(None, t, p, autojunk=False).ratio()
        if k not in best or r > best[k][0]:
            best[k] = (r, t)
    ops: collections.Counter = collections.Counter()
    cls: dict = collections.defaultdict(collections.Counter)
    ex: dict = {}
    same = 0
    for (p, tag, lemma), (_, t) in best.items():
        if t == p:
            same += 1
            continue
        sm = difflib.SequenceMatcher(None, t, p, autojunk=False)
        for op, a, b, c, d in sm.get_opcodes():
            if op == "equal":
                continue
            o = (t[max(0, a - 1):b + 1], p[max(0, c - 1):d + 1])
            ops[o] += 1
            cls[o][tag_class(tag)] += 1
            ex.setdefault(o, f"{t}→{p} ({tag})")
    with open(OUT_CORR, "w", encoding="utf-8") as fh:
        for o, n in ops.most_common():
            classes = ",".join(f"{c}:{m}" for c, m in cls[o].most_common(4))
            fh.write(f"{n}\t{o[0]}\t{o[1]}\t{classes}\t{ex[o]}\n")
    print(f"lemmas {len(keys)}  pairs {len(pairs)}  ps-forms {len(best)}  "
          f"identical {same} ({same / len(best):.1%})")
    print(f"wrote {OUT_PAIRS}\nwrote {OUT_CORR}")


if __name__ == "__main__":
    main()
