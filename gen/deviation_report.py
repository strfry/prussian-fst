"""Abweichungs-Report: handgeschriebener gen/-Generator  ↔  base.fst.

Die Twanksta-Einträge sind kanonisch als Vollform-LUT `build/base.fst` gebaut
(lexc/ ← gen_lexc.py ← twanksta_entries.json). Der GENERIERUNGS-Zweig davon,
`build/base.gen.hfstol` (analysis→surface), ist damit die autoritative
Repräsentation der Twanksta-Formen. Dieser Report vergleicht ihn Slot für Slot
mit dem regelbasierten gen/-Generator (gen/*.lexc + gen/accent.regex) über ALLE
modellierten Kategorien:

    Nomen (i/a/u/jo/aa/n-Stämme), Adjektiv (Positiv + Komparativ/Superlativ),
    Adverb (Grad), Präsens-Partizip, finite Verben.

Methode (nicht-zirkulär, immer synchron mit der echten Grammatik):
  * Jedes coverage_*.main() konstruiert authentisch seine Analyse-String-Queries
    und baut den cov-FST mit dem vollen Twanksta-Stamm-Inventar. Wir hängen uns
    per Monkeypatch an glookup_batch und fangen  query → gen-Oberfläche  ab.
  * Dieselben Queries laufen gegen base.gen.hfstol  →  query → base-Oberfläche.
  * Diff je Query (als Mengen, Varianten toleriert):
        AGREE      gen-Menge == base-Menge
        GEN_GAP    gen leer,     base nichtleer   (gen erzeugt nichts)
        GEN_EXTRA  gen nichtleer, base leer        (base kennt den Slot nicht)
        DIFFER     beide nichtleer, aber verschieden

Abweichungen (nicht AGREE) werden nach Familie/Slot aggregiert und morpho-
phonologisch grob klassifiziert (Makron/Gemination vs. Synkope vs. Gerüst).

    uv run python gen/deviation_report.py                 # voller Report
    uv run python gen/deviation_report.py --show 8        # mehr Beispiele/Kat.
    uv run python gen/deviation_report.py --out gen/REPORT-gen-vs-base.md
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "gen"))

from prussian_fst.fst_lookup import glookup_batch  # noqa: E402

BASE_GEN = ROOT / "build" / "base.gen.hfstol"

MAC = "āēīōū"
def deac(s: str) -> str: return s.translate(str.maketrans(MAC, "aeiou"))
def degem(s: str) -> str: return re.sub(r"(.)\1", r"\1", s)
def skel(s: str) -> str: return degem(deac(s))
def nvow(s: str) -> int: return len(re.findall(r"[aeiou]", deac(s)))


def classify(gens: list[str], bases: list[str]) -> str:
    """Grobe morphophonologische Einordnung einer DIFFER-Abweichung."""
    g, b = gens[0], bases[0]
    if skel(g) == skel(b):
        return "Makron/Geminaten-Varianz"
    if nvow(g) != nvow(b):
        return "Synkope/Vokal-Zahl"
    if deac(g) == deac(b):
        return "nur Makron"
    return "Gerüst verschieden"


# ── Query-Erfassung: jede coverage_*.main() liefert authentische Queries + gen-FST ──

def capture(module, argv: list[str]) -> dict[str, list[str]]:
    """coverage-Modul-main() unter Monkeypatch laufen lassen; query→gen-Surface.

    Wir ersetzen die im Modul gebundene glookup_batch durch einen Recorder, der
    das echte Ergebnis durchreicht UND (query→surfaces) sammelt. main() baut dabei
    den cov-FST (voller Twanksta-Stamm) und stellt genau die Queries, die die echte
    Grammatik abdeckt. Modul-stdout (der normale Coverage-Print) wird geschluckt.
    """
    records: dict[str, list[str]] = {}
    real = module.glookup_batch

    def recorder(queries, path):
        res = real(queries, path)
        for q in queries:
            records[q] = res.get(q, [])
        return res

    module.glookup_batch = recorder
    old_argv = sys.argv
    sys.argv = argv
    try:
        with redirect_stdout(io.StringIO()):
            module.main()
    finally:
        sys.argv = old_argv
        module.glookup_batch = real
    return records


def collect() -> dict[str, dict[str, list[str]]]:
    """Alle Kategorien → {Kategorie-Label: {query: gen-Surfaces}}."""
    import coverage_gen, coverage_adj, coverage_adverb, coverage_partpres, coverage_verb

    out: dict[str, dict[str, list[str]]] = {}
    # Nomen: eine main() pro Stammfamilie.
    for fam in sorted(coverage_gen.FAMILIES):
        print(f"  … Nomen/{fam}", file=sys.stderr)
        out[f"Nomen/{fam}"] = capture(coverage_gen, ["x", "--family", fam])
    for label, mod in (("Adjektiv+Grad", coverage_adj),
                       ("Adverb", coverage_adverb),
                       ("Partizip-Präs", coverage_partpres),
                       ("Verb-finit", coverage_verb)):
        print(f"  … {label}", file=sys.stderr)
        out[label] = capture(mod, ["x"])
    return out


# ── Diff & Report ──

def diff_category(gen_map: dict[str, list[str]],
                  base_map: dict[str, list[str]]) -> dict:
    counts = Counter()
    examples: dict[str, list] = defaultdict(list)
    slot_dev = Counter()
    subcat = Counter()
    for q, gens in gen_map.items():
        bases = base_map.get(q, [])
        gset, bset = set(gens), set(bases)
        if gset == bset:
            counts["AGREE"] += 1
            continue
        if not gens and bases:
            kind = "GEN_GAP"
        elif gens and not bases:
            kind = "GEN_EXTRA"
        else:
            kind = "DIFFER"
            subcat[classify(gens, bases)] += 1
        counts[kind] += 1
        slot = re.sub(r"^[^+]+", "", q)          # Tag-Kette ohne Lemma
        slot_dev[(kind, slot)] += 1
        examples[kind].append((q, gens, bases))
    return {"counts": counts, "examples": examples,
            "slot_dev": slot_dev, "subcat": subcat}


def fmt(surfaces: list[str]) -> str:
    return "/".join(surfaces) if surfaces else "∅"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", type=int, default=6,
                    help="max. Beispiel-Abweichungen je Kategorie/Art")
    ap.add_argument("--out", metavar="PATH",
                    help="Report zusätzlich als Markdown hierher schreiben")
    args = ap.parse_args()

    if not BASE_GEN.exists():
        sys.exit(f"Fehlt: {BASE_GEN} — erst `make build/base.gen.hfstol` bauen.")

    print("Sammle gen-Queries + Oberflächen (baut cov-FSTs) …", file=sys.stderr)
    cats = collect()

    all_queries = sorted({q for m in cats.values() for q in m})
    print(f"base.gen-Lookup: {len(all_queries)} Queries …", file=sys.stderr)
    base_map = glookup_batch(all_queries, str(BASE_GEN))

    buf = io.StringIO()
    def p(*a): print(*a, file=buf)

    p("# Abweichungs-Report — gen/ Generator ↔ base.fst (Twanksta)")
    p()
    p("Referenz = `build/base.gen.hfstol` (Generierungs-Zweig von `build/base.fst`, "
      "der Vollform-LUT aus twanksta_entries.json). Verglichen wird der regelbasierte "
      "`gen/`-Generator Slot für Slot gegen diese Referenz.")
    p()
    p("Legende: **GEN_GAP** = gen erzeugt nichts, base schon · "
      "**GEN_EXTRA** = gen erzeugt, base kennt den Slot nicht · "
      "**DIFFER** = beide erzeugen, aber verschieden.")
    p()

    grand = Counter()
    cat_results = {}
    for label, gen_map in cats.items():
        r = diff_category(gen_map, base_map)
        cat_results[label] = r
        grand.update(r["counts"])

    # ── Übersichtstabelle ──
    p("## Übersicht je Kategorie")
    p()
    p("| Kategorie | Slots | AGREE | GEN_GAP | GEN_EXTRA | DIFFER | Abw.-Quote |")
    p("|---|--:|--:|--:|--:|--:|--:|")
    for label, r in cat_results.items():
        c = r["counts"]
        tot = sum(c.values())
        dev = tot - c["AGREE"]
        p(f"| {label} | {tot} | {c['AGREE']} | {c['GEN_GAP']} | "
          f"{c['GEN_EXTRA']} | {c['DIFFER']} | {100*dev/tot:.1f}% |")
    tot = sum(grand.values())
    dev = tot - grand["AGREE"]
    p(f"| **GESAMT** | **{tot}** | **{grand['AGREE']}** | **{grand['GEN_GAP']}** "
      f"| **{grand['GEN_EXTRA']}** | **{grand['DIFFER']}** | **{100*dev/tot:.1f}%** |")
    p()

    # ── Detail je Kategorie ──
    for label, r in cat_results.items():
        c = r["counts"]
        if sum(c.values()) - c["AGREE"] == 0:
            p(f"## {label} — ✅ keine Abweichungen")
            p()
            continue
        p(f"## {label}")
        p()
        # Slot-Hotspots
        top = r["slot_dev"].most_common(8)
        if top:
            p("Abweichungs-Hotspots (Art, Slot → Anzahl): "
              + ", ".join(f"`{kind}{slot}`→{n}" for (kind, slot), n in top))
            p()
        if r["subcat"]:
            p("DIFFER-Art: "
              + ", ".join(f"{k}={n}" for k, n in r["subcat"].most_common()))
            p()
        for kind in ("GEN_GAP", "DIFFER", "GEN_EXTRA"):
            ex = r["examples"].get(kind, [])
            if not ex:
                continue
            p(f"**{kind}** ({len(ex)}), Beispiele:")
            p()
            for q, gens, bases in ex[: args.show]:
                p(f"- `{q}` — gen `{fmt(gens)}` ≠ base `{fmt(bases)}`")
            p()

    out = buf.getvalue()
    print(out)
    if args.out:
        Path(args.out).write_text(out)
        print(f"[geschrieben: {args.out}]", file=sys.stderr)


if __name__ == "__main__":
    main()
