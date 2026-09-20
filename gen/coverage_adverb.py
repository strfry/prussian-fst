"""Nicht-zirkulärer Deckungstest für die Adverb-Gradtafel (Positiv/Komparativ/Superlativ).

Adverbien werden nicht dekliniert — je EINE Form pro Grad (Twanksta `forms.adverb` =
{positive, comparative, superlative}). Die Grammatik (Endungen) steht datenfrei in
gen/adj.lexc; hier wird nur die STAMM-Inventarisierung skaliert: für jedes reale
Adjektiv-Lexem der Ziel-Paradigmen werden der Adjektiv-Stamm (aus der Deklination)
und der Komparativ-Stamm (aus der Komparativ-Deklination) abgeleitet, an die
Grammatik gehängt, kompiliert, mit gen/accent.regex komponiert und gegen Twanksta
verglichen.

Regeln (an Twanksta verifiziert, n=1019):
  Positiv    = Adjektivstamm + Klassensuffix (-ai a-Stamm, -jai i-/jo-, -u u-Stamm)
  Komparativ = Positiv + -s (u-Stamm stattdessen -uis)
  Superlativ = uka- + Komparativ (100 % regelhaft)

Suppletion/Stamm-Irregularität (labs→walnai, līkuts→mazzan, dabbars→dabbrai, …) ist
per Definition regellos und steht als fertige Form in LEXICON AdvExcept (gen/adj.lexc).
Das Skript liest diese Liste und RECHNET die gelisteten Lemmata aus der Regel-Deckung
heraus — so täuscht die Liste den Nicht-Zirkularitätstest nicht. Die Regel-Deckung
wird getrennt von den gelisteten Ausnahmen ausgewiesen.

    uv run python gen/coverage_adverb.py [--show N]
    uv run python gen/coverage_adverb.py --emit-stems build/gen-adverb-stems.lexc
"""
from __future__ import annotations

import argparse
import re
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

# Paradigma → (Stamm-Lexikon, Infl-Lexikon, Quell-Slot, Basis-Endung,
#              Positiv-Suffix, Komparativ-Suffix).
# Positiv = Stamm + Positiv-Suffix; Komparativ = Stamm + Komparativ-Suffix
# (= Positiv + s, u-Stamm -uis); Superlativ = uka- + Komparativ(-Stamm).
# Par.30 (u-Stamm, fest) nutzt dasselbe Stamm-/Infl-Lexikon wie Par.31 — fürs
# Adverb zählt nur die u-Endung, die verknüpfte Adjektiv-Deklination ist irrelevant.
ADV_TARGETS = {
    "25": ("AdjFixed",  "AdjFixedInfl",  "Genitive",   "as",  "ai",  "ais"),
    "26": ("AdjMobile", "AdjMobileInfl", "Genitive",   "as",  "ai",  "ais"),
    "27": ("AdjI",      "AdjIInfl",      "Genitive",   "jas", "jai", "jais"),
    "30": ("AdjUMob",   "AdjUMobInfl",   "Nominative", "us",  "u",   "uis"),
    "31": ("AdjUMob",   "AdjUMobInfl",   "Nominative", "us",  "u",   "uis"),
}
# Par.27 hat zwei Untertypen: jo-Stamm (Gen.Sg. -jas) und i-Stamm (Gen.Sg. -is);
# beide liefern denselben Adverb-Stamm — beim Abtrennen wird -jas vor -is versucht.
# Alle Stamm-Lexika, auf die LEXICON Root in gen/adj.lexc verweist (ggf. leer).
STEM_LEXICONS = ["AdjFixed", "AdjMobile", "AdjI", "AdjIMob", "AdjUMob",
                 "PartPass", "PartAct", "AdjCmpStems", "AdjSupStems"]
# Die Komparativ-/Superlativ-Deklination ist i-/jo-stämmig, egal welches
# Basis-Paradigma: der Komparativ-Stamm = Komparativ Masc.Gen.Sg. minus -jas.
CMP_INFL = "AdjCmpInfl"
SUP_INFL = "AdjSupInfl"
GEN = {"m": "Masc", "f": "Fem", "n": "Neut"}
CA = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Acc"}


def primary(cell: str) -> str:
    return (cell or "").split(" / ")[0].strip()


def adv_exception_lemmas() -> set[str]:
    """Lemmata mit hand-gepflegter Adverb-Gradtafel aus LEXICON AdvExcept.

    Suppletion/Stamm-Irregularität ist regellos und MUSS gelistet werden; diese
    Lemmata werden deshalb aus der Regel-Deckung herausgerechnet (ihre Formen
    kommen fertig aus LEXICON AdvExcept).
    """
    text = LEXC.read_text()
    m = re.search(r"^LEXICON AdvExcept\b(.*?)(?=^LEXICON |\Z)", text, re.M | re.S)
    if not m:
        return set()
    return set(re.findall(r"^\s*(\S+?)\+Adv", m.group(1), re.M))


def load_targets(exceptions: set[str]) -> tuple[list[dict], list[dict], int]:
    """Adverb-Lexeme der Ziel-Paradigmen, getrennt in Regel vs. gelistet.

    Gelistete Ausnahmen (LEXICON AdvExcept, = exceptions-Notwendigkeit) brauchen
    KEINEN ableitbaren Stamm — ihre Formen kommen fertig aus AdvExcept. Regel-
    Lexeme müssen Adjektiv- und Komparativ-Stamm ableiten können; wer Mehrwort/
    Slash ist, kein Adverb/m-Block hat oder keine Stamm-Endung ableiten lässt,
    zählt als ausgeschlossen (MWE/Datenrest). Rückgabe: (rule, listed, excluded).
    """
    entries = json.loads(TWANKSTA.read_text())
    rule, listed, seen = [], [], set()
    excluded = 0
    for e in entries:
        para = e.get("paradigm")
        if para not in ADV_TARGETS:
            continue
        adv = e.get("forms", {}).get("adverb")
        lemma = e.get("word", "")
        if not adv:
            excluded += 1
            continue
        if (lemma, para) in seen:
            continue
        seen.add((lemma, para))
        forms = {
            "Pos": primary(adv.get("positive")),
            "Cmp": primary(adv.get("comparative")),
            "Sup": primary(adv.get("superlative")),
        }
        if lemma in exceptions:
            listed.append({"lemma": lemma, "para": para, "forms": forms})
            continue
        decl = e.get("forms", {}).get("declension") or []
        cmp_decl = e.get("forms", {}).get("comparative") or []
        blocks = {b.get("gender"): b for b in decl}
        cmp_blocks = {b.get("gender"): b for b in cmp_decl}
        if (" " in lemma or "/" in lemma
                or "m" not in blocks or "m" not in cmp_blocks):
            excluded += 1
            continue
        stem_lex, infl, src_case, base_end, pos_suf, _ = ADV_TARGETS[para]
        src = ""
        for c in blocks["m"].get("cases", []):
            if c.get("case") == src_case:
                src = primary(c.get("singular"))
        stem = None
        if para == "27":
            for end in ("jas", "is"):
                if src.endswith(end):
                    stem = src[: -len(end)]
                    break
        elif src.endswith(base_end):
            stem = src[: -len(base_end)]
        csrc = ""
        for c in cmp_blocks["m"].get("cases", []):
            if c.get("case") == "Genitive":
                csrc = primary(c.get("singular"))
        if stem is None or not csrc.endswith("jas"):
            excluded += 1
            continue
        cmp_stem = csrc[: -len("jas")]
        sup_stem = "uka" + cmp_stem
        rule.append({
            "lemma": lemma, "para": para,
            "stem_lex": stem_lex, "infl": infl,
            "stem": stem, "cmp_stem": cmp_stem, "sup_stem": sup_stem,
            "pos_suf": pos_suf,
            "forms": forms,
        })
    print(f"Regel-Lexeme: {len(rule)}  Gelistet: {len(listed)}  "
          f"Ausgeschlossen: {excluded}")
    return rule, listed, excluded


def stems_block(targets: list[dict]) -> str:
    """Aus twanksta inventarisierte Stämme als LEXICON-Block.

    Drei Stämme je Lexem: der Adjektiv-Stamm (→ Positiv über Adv{A,I,U}), der
    Komparativ-Stamm (AdjCmpStems → +Adv+Cmp leer) und der Superlativ-Stamm
    (AdjSupStems = uka+Komparativ-Stamm → +Adv+Sup leer). Die uka-Präfix-Mechanik
    lebt hier (einmal erzeugt) und wird vom Adjektiv-Superlativ mit-genutzt.
    """
    stems = {sl: [] for sl in STEM_LEXICONS}
    for t in targets:
        stems[t["stem_lex"]].append(f"  {t['lemma']}:{t['stem']}  {t['infl']} ;")
        stems["AdjCmpStems"].append(f"  {t['lemma']}:{t['cmp_stem']}  {CMP_INFL} ;")
        stems["AdjSupStems"].append(f"  {t['lemma']}:{t['sup_stem']}  {SUP_INFL} ;")
    body = ["! === Aus twanksta generierte Stämme — NICHT von Hand editieren ===",
            "! (erzeugt von gen/coverage_adverb.py --emit-stems; Grammatik: gen/adj.lexc)"]
    for stem_lex in STEM_LEXICONS:
        body.append(f"LEXICON {stem_lex}")
        # lexc erlaubt kein leeres LEXICON → Epsilon-Platzhalter für Klassen ohne
        # Adverb-Lemmata (AdjIMob, PartPass, PartAct); wird nie angefragt.
        body.extend(stems[stem_lex] or ["  0:0  # ;"])
        body.append("")
    return "\n".join(body) + "\n"


def write_combined(targets: list[dict]) -> Path:
    combined = LEXC.read_text().rstrip() + "\n\n" + stems_block(targets)
    out = BUILD / "gen-adverbcov.lexc"
    out.write_text(combined)
    return out


def build(lexc: Path) -> Path:
    fst = BUILD / "gen-adverbcov.fst"
    composed = BUILD / "gen-adverbcov.composed.fst"
    hfstol = BUILD / "gen-adverbcov.gen.hfstol"
    if not ACCENT.exists():
        subprocess.run(HFST + ["xfst", str(ROOT / "gen" / "accent.regex")], check=True)
    subprocess.run(HFST + ["lexc", str(lexc), str(fst)], check=True)
    subprocess.run(HFST + ["compose", str(composed), str(fst), str(ACCENT)], check=True)
    subprocess.run(HFST + ["hfstol-gen", str(composed), str(hfstol)], check=True)
    return hfstol


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", type=int, default=15)
    ap.add_argument("--emit-stems", metavar="PATH",
                    help="nur den generierten Stamm-Block nach PATH schreiben "
                         "(für den Build) und beenden — kein Deckungstest")
    args = ap.parse_args()

    exceptions = adv_exception_lemmas()
    rule, listed, _ = load_targets(exceptions)

    if args.emit_stems:
        Path(args.emit_stems).write_text(stems_block(rule))
        print(f"Stämme geschrieben: {args.emit_stems} ({len(rule)} Lexeme "
              f"[Regel]; {len(listed)} gelistete Ausnahmen ausgelassen)")
        return

    hfstol = build(write_combined(rule))

    queries = []
    for t in rule + listed:
        for deg in ("Pos", "Cmp", "Sup"):
            queries.append(f"{t['lemma']}+Adv" + ({"Pos": "", "Cmp": "+Cmp",
                                                  "Sup": "+Sup"}[deg]))
    gen = glookup_batch(queries, str(hfstol))

    # --- Regel-Deckung (gelistete Ausnahmen herausgerechnet) ---
    total = hit = 0
    per = Counter()
    misses = []
    for t in rule:
        want = t["forms"]
        for deg in ("Pos", "Cmp", "Sup"):
            tag = {"Pos": "", "Cmp": "+Cmp", "Sup": "+Sup"}[deg]
            want_form = want[deg]
            a = f"{t['lemma']}+Adv{tag}"
            got = gen.get(a, [])
            ok = want_form in got
            total += 1
            per[t["para"]] += 1
            hit += ok
            if not ok:
                misses.append(f"  {t['lemma']}[{t['para']}] +Adv{tag}: "
                              f"{want_form!r} ≠ {(got or ['∅'])[0]!r}")
    print(f"\nRegel-Deckung: {hit}/{total} ({100*hit/total:.1f}%)"
          f"  [aus {len(rule)} Regel-Lexemen × 3 Grade]")
    for para in ADV_TARGETS:
        if per[para]:
            print(f"  Par.{para}: {per[para]//3} Lexeme")
    if misses:
        print(f"\nRegel-Abweichungen (erste {args.show}):")
        print("\n".join(misses[: args.show]))

    # --- Gelistete Ausnahmen (getrennt) ---
    exc_hit = exc_ok = 0
    for t in listed:
        for deg in ("Pos", "Cmp", "Sup"):
            tag = {"Pos": "", "Cmp": "+Cmp", "Sup": "+Sup"}[deg]
            a = f"{t['lemma']}+Adv{tag}"
            ok = t["forms"][deg] in gen.get(a, [])
            exc_ok += 1
            exc_hit += ok
    print(f"\nGelistete Ausnahmen (LEXICON AdvExcept): {len(listed)} Lemmata, "
          f"{exc_hit}/{exc_ok} Grade erzeugt")
    for t in listed:
        print(f"  {t['lemma']}[{t['para']}] → {t['forms']['Pos']} / "
              f"{t['forms']['Cmp']} / {t['forms']['Sup']}")


if __name__ == "__main__":
    main()
