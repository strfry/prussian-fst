"""FST lookup using pyhfst — no C dependencies needed at lookup time."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pyhfst

_transducers: dict[str, pyhfst.Hfst] = {}


def _load_fst(fst_path: Path) -> pyhfst.Hfst:
    key = str(fst_path)
    if key not in _transducers:
        _transducers[key] = pyhfst.HfstInputStream(str(fst_path)).read()
    return _transducers[key]


def flookup_batch(forms: list[str], fst_path: Path) -> dict[str, list[tuple[str, list[str]]]]:
    """Alle Formen durch pyhfst; form → [(lemma, tags)]."""
    if not forms:
        return {}
    tr = _load_fst(fst_path)
    analyses: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    for form in forms:
        for analysis, _weight in tr.lookup(form):
            if analysis.endswith("+?"):
                continue
            segs = analysis.split("+")
            lemma, tags = segs[0], segs[1:]
            if not tags:
                continue
            analyses[form].append((lemma, tags))
    return dict(analyses)
