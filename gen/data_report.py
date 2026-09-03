"""Datenqualitäts-Report über die generativ modellierten Nomen-Familien.

Nutzt den handgeschriebenen Generator (gen/{i,a,u}stem.lexc + gen/accent.regex,
über gen/coverage_gen.py) als Referenz für das REGULÄRE Verhalten. Jede Form, die
der Generator aus Stamm (Gen.Sg. minus Klassenendung) + Paradigmenendung + Akzent-
regel NICHT trifft, ist ein Kandidat und wird nach Art der Abweichung sortiert:

  - lexikalische Nom.Sg.-Wahl (-s vs -is/-us)      → Sprachfakt, kein Fehler
  - Makron-/Geminaten-Varianz in mobilen Slots     → Morphophonologie, teils Rest
  - Obliquus-Synkope / Gerüstunterschied           → unmodellierte Morphophonologie
  - invariante Tabelle (alle Kasus = Lemma)        → Datenfehler
  - Rest                                           → prüfen

Zusätzlich ein rein daten-interner Check auf invariante Einträge (unabhängig vom
Generator, deckt alle Paradigmen ab).

    uv run python gen/data_report.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "gen"))

import json  # noqa: E402

import coverage_gen as cov  # noqa: E402
from prussian_fst.fst_lookup import glookup_batch  # noqa: E402

MAC = "āēīōū"
def deac(s: str) -> str: return s.translate(str.maketrans(MAC, "aeiou"))
def degem(s: str) -> str: return re.sub(r"(.)\1", r"\1", s)
def skel(s: str) -> str: return degem(deac(s))
def nvow(s: str) -> int: return len(re.findall(r"[aeiou]", deac(s)))


def classify(slot: str, want: str, got: str) -> str:
    if not got:
        return "keine Form generiert"
    if skel(want) == skel(got):
        # gleiches Konsonanten+Kurzvokal-Gerüst → nur Länge/Gemination weicht ab
        return "Makron/Geminaten-Varianz (mobil)"
    if slot == "Sg+Nom":
        # Endungswahl -s vs -is/-us/-as+Vokal
        if want[:-1] and (want.endswith(("is", "us")) or nvow(want) > nvow(got)):
            return "Nom.Sg. -s/-is/-us (lexikalisch)"
    if nvow(want) != nvow(got):
        return "Synkope/Vokal-Unterschied"
    return "Rest (Gerüst verschieden)"


def report_family(fam: str) -> tuple[int, int, Counter, dict]:
    cov.FAMILY = fam
    cov.LEXC, cov.TARGETS = cov.FAMILIES[fam]
    targets = cov.load_targets()
    hfstol = cov.build(cov.write_lexc(targets))
    queries = [f"{t['lemma']}+N+{t['gender']}+{n}+{c}"
               for t in targets for n in ("Sg", "Pl") for c in cov.CASES]
    gen = glookup_batch(queries, str(hfstol))

    total = hit = 0
    buckets: Counter = Counter()
    examples: dict = defaultdict(list)
    for t in targets:
        allslots = {f"{n}+{c}": t["forms"].get(f"{n}+{c}")
                    for n in ("Sg", "Pl") for c in cov.CASES}
        invariant = (sum(1 for v in allslots.values()
                         if v == t["lemma"]) >= 7)
        for slot, want in allslots.items():
            if not want:
                continue
            total += 1
            a = f"{t['lemma']}+N+{t['gender']}+{slot}"
            got = (gen.get(a) or [""])[0]
            if want in gen.get(a, []):
                hit += 1
                continue
            cat = "invariante Tabelle (alle Kasus = Lemma)" if invariant \
                else classify(slot, want, got)
            buckets[cat] += 1
            if len(examples[cat]) < 6:
                examples[cat].append(
                    f"{t['lemma']}[{t['para']}] {slot}: {want!r} ≠ {got or '∅'!r}")
    return total, hit, buckets, examples


def invariant_scan() -> tuple[list, list]:
    """Datenintern, alle Nomen-Paradigmen: Tabelle == Lemma in >=7/8 Kasus."""
    CA = cov.CA
    tw = json.loads((ROOT.parent / "corpus" / "parsed"
                     / "twanksta_entries.json").read_text())
    decl_shaped, vowel_final = [], []
    for e in tw:
        p = e.get("paradigm")
        if not (p and p.isdigit() and 32 <= int(p) <= 70):
            continue
        decl = e.get("forms", {}).get("declension")
        if not decl:
            continue
        b = decl[0]
        lemma = e.get("word", "")
        if " " in lemma or "/" in lemma:
            continue
        vals = []
        for c in b.get("cases", []):
            ca = CA.get(c.get("case", ""))
            if not ca:
                continue
            vals.append(cov.primary(c.get("singular")))
            vals.append(cov.primary(c.get("plural")))
        vals = [v for v in vals if v]
        if len(vals) >= 8 and vals.count(lemma) >= 7:
            (decl_shaped if re.search(r"[bcdfgklmnprstvwzž]s$", lemma)
             else vowel_final).append(f"{lemma}[{p}]")
    return decl_shaped, vowel_final


def main() -> None:
    print("=" * 72)
    print("DATENQUALITÄTS-REPORT — generativ modellierte Nomen-Familien")
    print("=" * 72)
    grand_t = grand_h = 0
    all_buckets: Counter = Counter()
    all_ex: dict = defaultdict(list)
    for fam in ("istem", "astem", "ustem", "jostem", "aastem"):
        t, h, buckets, ex = report_family(fam)
        grand_t += t
        grand_h += h
        print(f"\n### {fam}: {h}/{t} ({100*h/t:.1f}%) — {t-h} Abweichungen")
        for cat, n in buckets.most_common():
            print(f"    {n:4}  {cat}")
        all_buckets.update(buckets)
        for cat, lst in ex.items():
            all_ex[cat].extend(lst)

    print("\n" + "=" * 72)
    print(f"GESAMT: {grand_h}/{grand_t} ({100*grand_h/grand_t:.2f}%)  "
          f"— {grand_t-grand_h} Abweichungen nach Art:")
    for cat, n in all_buckets.most_common():
        print(f"\n  [{n}] {cat}")
        for x in all_ex[cat][:6]:
            print(f"        {x}")

    ds, vf = invariant_scan()
    print("\n" + "=" * 72)
    print("INVARIANTE EINTRÄGE (datenintern, alle Nomen-Paradigmen 32–70):")
    print(f"\n  Deklinierbar geformt (Nom.Sg. -Cs → SOLLTE deklinieren) [{len(ds)}]:")
    print("     ", " ".join(ds))
    print(f"\n  Vokal-/fremdendig (evtl. wirklich indeklinabel) [{len(vf)}]:")
    print("     ", " ".join(vf))


if __name__ == "__main__":
    main()
