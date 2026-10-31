"""Expand the current (stem-based) lean NVH to full cells with the OLD generator.

Migration helper: the lean NVH is an edited dictionary, not a pure derivation of
the Twanksta dump. It carries entries missing from twanksta.nvh, stem corrections
(kurtun pret=kūr) and errata (u-stem adverbs in -jai). Recompressing from
twanksta.nvh would drop all of that, so the new compressor runs on the expansion of
the existing lean NVH instead.

Each entry is expanded exactly as the old analyzer bake did (generate with the
stems, overrides replace their slot). The result is restricted to the slots the
lexeme has: those Twanksta lists for it, plus the slots of its own overrides.
Entries unknown to Twanksta, or without cells there, keep every generated slot.

    uv run python scratch/kennform/expand_lean.py --old-gen <main worktree>/gen \
        --out build/full_from_lean.nvh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PARSED = REPO.parent / "corpus" / "parsed"


def entry_id(entry) -> str:
    for line in entry.head:
        if line.startswith("  id: "):
            return line[len("  id: "):].strip()
    return entry.lemma


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--old-gen", type=Path, required=True,
                        help="gen/ directory of a checkout with the old generator")
    parser.add_argument("--lean", type=Path, default=PARSED / "twanksta_dmlex.nvh")
    parser.add_argument("--fat", type=Path, default=PARSED / "twanksta.nvh")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(args.old_gen.resolve()))
    import build_analyzer as old_ba
    import compress_forms as old_cf

    fat_slots: dict[str, set[str]] = {}
    for e in old_cf.repair_dumper_artifacts(old_cf.read_nvh(args.fat))[0]:
        fat_slots.setdefault(entry_id(e), set()).update(e.attested)
    out = []
    unknown = 0
    for entry in old_cf.read_nvh(args.lean):
        if entry.pos and entry.paradigm:
            cells = old_ba.entry_forms(entry)
            keep = fat_slots.get(entry_id(entry))
            if not keep:                        # unknown to Twanksta or without cells
                unknown += 1
            else:
                keep = keep | set(entry.attested)
                cells = {s: f for s, f in cells.items() if s in keep}
            cells = {s: tuple(sorted(f)) for s, f in cells.items() if f}
        else:
            cells = dict(entry.attested)
        out.append(old_cf.render_entry(entry, {}, cells))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(out), encoding="utf-8")
    print(f"{len(out)} entries ({unknown} not in Twanksta) -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
