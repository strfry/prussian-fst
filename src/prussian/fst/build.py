#!/usr/bin/env python3
"""Baut Analysatoren: morphotactics.lexd ∘ Regelschicht → analyser/lenient.

Pipeline (vgl. docs/AKZENT.md §4, docs/ORTHO_RULES.md):
  1. entries.py:   goldstandard.json + wordlist.json → Einträge
  2. lexd_gen.py:  Einträge → build/morphotactics.lexd (markierte Unterseite,
                   inkl. V-Zeilen für Twanksta-j-Varianten)
  3. rules.py:     Akzent- und Palatalisierungsregeln
  4. Komposition:
       analyser.fst  = lexd ohne V-Zeilen ∘ rule_chain     (Standard)
       lenient.fst   = lexd mit V-Zeilen  ∘ rule_chain     (akzeptiert
                       Quellvarianten; ersetzt den alten ortho.fst)

Aufruf:  python -m prussian.fst.build [--gold-only]
"""

import argparse
import json
from pathlib import Path

from pyfoma import lexd

from prussian.fst.entries import combine_entries, wordlist_to_entries
from prussian.fst.lexd_gen import build_lexd
from prussian.fst.rules import rule_chain

ROOT = Path(__file__).resolve().parent.parent.parent.parent
GOLD = ROOT / "data/gold/goldstandard.json"
VERB_GOLD = ROOT / "data/gold/goldstandard_verben_fst.json"
WORDLIST = ROOT / "data/external/wordlist.json"
BUILD_DIR = ROOT / "build"
LEXD_OUT = BUILD_DIR / "morphotactics.lexd"
FST_OUT = BUILD_DIR / "analyser.fst"
ATT_OUT = BUILD_DIR / "analyser.att"
LENIENT_OUT = BUILD_DIR / "lenient.fst"


def strip_variant_lines(lexd_text: str) -> str:
    """V-Zeilen (Twanksta-Varianten) für den Standard-Build entfernen."""
    return "\n".join(
        line for line in lexd_text.splitlines()
        if not (":" in line and line.split(":", 1)[1].startswith("V"))
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-only", action="store_true",
                    help="nur Goldstandard-Lexeme (schneller Testbau)")
    args = ap.parse_args()

    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))
    verb_data = json.loads(VERB_GOLD.read_text(encoding="utf-8"))
    print(f"Goldstandard: {len(gs_data)} nominal, {len(verb_data)} verbal")

    if args.gold_only:
        combined = gs_data
    else:
        wl_data = json.loads(WORDLIST.read_text(encoding="utf-8"))
        wl_entries = wordlist_to_entries(wl_data, gs_data)
        print(f"Wortliste: {len(wl_entries)} Einträge (P9–P67)")
        combined = combine_entries(gs_data, wl_entries)
    print(f"Kombiniert: {len(combined)} Einträge")

    lexd_text = build_lexd(combined, verb_data)
    BUILD_DIR.mkdir(exist_ok=True)
    LEXD_OUT.write_text(lexd_text, encoding="utf-8")
    print(f"lexd → {LEXD_OUT} ({len(lexd_text.splitlines())} Zeilen)")

    morph = lexd.compile(strip_variant_lines(lexd_text))
    print(f"Morphotaktik (Standard): {len(morph.states)} Zustände")
    analyser = morph.compose(rule_chain()).minimize()
    print(f"analyser.fst (∘ Regeln, minimiert): {len(analyser.states)} Zustände")
    analyser.save(str(FST_OUT))
    analyser.save_att(str(ATT_OUT))

    morph_len = lexd.compile(lexd_text)
    print(f"Morphotaktik (mit Varianten): {len(morph_len.states)} Zustände")
    lenient = morph_len.compose(rule_chain()).minimize()
    print(f"lenient.fst (∘ Regeln, minimiert): {len(lenient.states)} Zustände")
    lenient.save(str(LENIENT_OUT))

    print(f"Gespeichert: {FST_OUT}, {ATT_OUT}, {LENIENT_OUT}")


if __name__ == "__main__":
    main()
