"""Nicht-zirkulärer Deckungstest für die adjektivisch deklinierten Partizipien.

Analog zu gen/coverage_gen.py (Nomen), aber für die DREI-GENUS-Paradigmen der
Partizipien (Twanksta-Par.68 aktiv -uns, Par.69 passiv -ts). Die Endungslexika
(PartPassInfl/PartActInfl + Genusblöcke) stehen von Hand in gen/adj.lexc; hier
wird nur die STAMM-Inventarisierung skaliert: für jedes reale Par.68/69-Lexem
wird der Stamm aus dem Masc-Block abgeleitet, in die handgeschriebenen Endungen
eingespeist und die 24 Formen (3 Genera × 8) exakt gegen Twanksta verglichen.

    uv run python gen/coverage_adj.py [--show N]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from prussian_fst.fst_lookup import glookup_batch  # noqa: E402

TWANKSTA = ROOT.parent / "corpus" / "parsed" / "twanksta_entries.json"
LEXC = ROOT / "gen" / "adj.lexc"
ACCENT = ROOT / "build" / "gen-accent.hfst"
BUILD = ROOT / "build"
HFST = ["uv", "run", "python", str(ROOT / "src" / "prussian_fst" / "build_fst.py")]
ENDINGS_MARKER = "LEXICON PartPassInfl"

# Paradigma → (Tag-Typ, Stamm-Lexikon, Infl-Lexikon, Quell-Slot, Klassenendung).
# Stamm = <Quellform des Masc-Blocks> minus Klassenendung.
TARGETS = {
    "69": ("Pass", "PartPass", "PartPassInfl", "Genitive", "as"),
    "68": ("Act", "PartAct", "PartActInfl", "Nominative", "uns"),
}
GEN = {"m": "Masc", "f": "Fem", "n": "Neut"}
CASES = ["Nom", "Gen", "Dat", "Akk"]
CA = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Akk"}


def primary(cell: str) -> str:
    return (cell or "").split(" / ")[0].strip()


def load_targets() -> list[dict]:
    entries = json.loads(TWANKSTA.read_text())
    out, seen = [], set()
    excluded = 0
    for e in entries:
        para = e.get("paradigm")
        if para not in TARGETS:
            continue
        decl = e.get("forms", {}).get("declension") or []
        blocks = {b.get("gender"): b for b in decl}
        lemma = e.get("word", "")
        _, _, _, src_case, end = TARGETS[para]
        if " " in lemma or "/" in lemma or set("mfn") - set(blocks):
            excluded += 1
            continue
        # Referenzformen je Genus/Slot
        forms = {}
        for g, b in blocks.items():
            for c in b.get("cases", []):
                ca = CA.get(c.get("case", ""))
                if not ca:
                    continue
                forms[(GEN[g], f"Sg+{ca}")] = primary(c.get("singular"))
                forms[(GEN[g], f"Pl+{ca}")] = primary(c.get("plural"))
        # Stamm aus Masc-Quellslot
        src = ""
        for c in blocks["m"].get("cases", []):
            if c.get("case") == src_case:
                src = primary(c.get("singular"))
        if not src.endswith(end) or len(forms) < 24:
            excluded += 1
            continue
        stem = src[: -len(end)]
        if (lemma, para) in seen:
            continue
        seen.add((lemma, para))
        out.append({"lemma": lemma, "para": para, "stem": stem, "forms": forms})
    print(f"Ziel-Lexeme: {len(out)}  (ausgeschlossen: {excluded})")
    return out


def write_lexc(targets: list[dict]) -> Path:
    text = LEXC.read_text()
    preamble_mc = next(l for l in text.splitlines()
                       if l.startswith("Multichar_Symbols"))
    endings = text[text.index(ENDINGS_MARKER):]
    # Stamm-Eintrag trägt KEINE Tags — anders als beim Nomen-Coverage tragen die
    # Partizip-Endungslexika die vollen Tags (+Part+Typ+Genus+…).
    stems = {spec[1]: [] for spec in TARGETS.values()}
    for t in targets:
        _, stem_lex, infl, _, _ = TARGETS[t["para"]]
        stems[stem_lex].append(f"  {t['lemma']}:{t['stem']}  {infl} ;")
    body = [preamble_mc, "", "LEXICON Root"]
    body += [f"  {sl} ;" for sl in stems]
    body.append("")
    for sl, lines in stems.items():
        body.append(f"LEXICON {sl}")
        body.extend(lines)
        body.append("")
    out = BUILD / "gen-adjcov.lexc"
    out.write_text("\n".join(body) + "\n" + endings)
    return out


def build(lexc: Path) -> Path:
    fst = BUILD / "gen-adjcov.fst"
    composed = BUILD / "gen-adjcov.composed.fst"
    hfstol = BUILD / "gen-adjcov.gen.hfstol"
    if not ACCENT.exists():
        subprocess.run(HFST + ["xfst", str(ROOT / "gen" / "accent.regex")], check=True)
    subprocess.run(HFST + ["lexc", str(lexc), str(fst)], check=True)
    subprocess.run(HFST + ["compose", str(composed), str(fst), str(ACCENT)], check=True)
    subprocess.run(HFST + ["hfstol-gen", str(composed), str(hfstol)], check=True)
    return hfstol


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", type=int, default=15)
    args = ap.parse_args()

    targets = load_targets()
    hfstol = build(write_lexc(targets))
    queries = [f"{t['lemma']}+Part+{TARGETS[t['para']][0]}+{g}+{n}+{c}"
               for t in targets for g in ("Masc", "Fem", "Neut")
               for n in ("Sg", "Pl") for c in CASES]
    gen = glookup_batch(queries, str(hfstol))

    total = hit = 0
    per = Counter(); per_hit = Counter(); miss_slot = Counter(); misses = []
    for t in targets:
        typ = TARGETS[t["para"]][0]
        for g in ("Masc", "Fem", "Neut"):
            for n in ("Sg", "Pl"):
                for c in CASES:
                    want = t["forms"].get((g, f"{n}+{c}"))
                    if not want:
                        continue
                    total += 1; per[t["para"]] += 1
                    a = f"{t['lemma']}+Part+{typ}+{g}+{n}+{c}"
                    ok = want in gen.get(a, [])
                    hit += ok; per_hit[t["para"]] += ok
                    if not ok:
                        miss_slot[f"{g} {n}+{c}"] += 1
                        misses.append(f"  {t['lemma']}[{t['para']}] {g} {n}+{c}: "
                                      f"{want!r} ≠ {(gen.get(a) or ['∅'])[0]!r}")
    print(f"\nDeckung gesamt: {hit}/{total} ({100*hit/total:.1f}%)")
    for para in TARGETS:
        if per[para]:
            print(f"  Par.{para}: {per_hit[para]}/{per[para]} "
                  f"({100*per_hit[para]/per[para]:.1f}%)")
    if miss_slot:
        print("\nAbweichungen je Slot:", dict(miss_slot.most_common()))
    if misses:
        print(f"\nBeispiele (erste {args.show}):")
        print("\n".join(misses[: args.show]))


if __name__ == "__main__":
    main()
