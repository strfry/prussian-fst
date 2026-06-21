#!/usr/bin/env python3
"""Baut Analysatoren: morphotactics.lexd ∘ Regelschicht → analyser/lenient.

Pipeline (vgl. docs/AKZENT.md §4, docs/ORTHO_RULES.md):
  1. entries.py:   goldstandard.json + twanksta_entries.json → Einträge
  2. lexd_gen.py:  Einträge → build/morphotactics.lexd (markierte Unterseite,
                   inkl. V-Zeilen für Twanksta-j-Varianten)
  3. rules.py:     Akzent- und Palatalisierungsregeln
  4. Komposition:
       analyser.fst  = lexd ohne V-Zeilen ∘ rule_chain     (Standard)
       lenient.fst   = lexd mit V-Zeilen  ∘ rule_chain     (akzeptiert
                       Quellvarianten; ersetzt den alten ortho.fst)

Aufruf:  python -m prussian.fst.build [--gold-only | --sample N [--seed S]]

  --gold-only   nur die ~184 Goldstandard-Lexeme (schnellster Bau, ~30 s)
  --sample N    Goldstandard + N zufällige Wörterbuch-Lexeme je Klasse
                (nominal/verbal); reproduzierbar über --seed. Testläufe auf
                einer Teilmenge, ohne den vollen Wörterbuch-Bau abzuwarten.
"""

import argparse
import json
import random
from pathlib import Path

from pyfoma import lexd

from prussian.fst.morphology import adverbs as adv_mod
from prussian.fst.morphology import function_words as fw_mod
from prussian.fst.morphology import verbs as verb_morph
from prussian.fst.morphology.lexd import build_lexd
from prussian.fst.morphology.nominals import combine_entries, wordlist_to_entries
from prussian.fst.phonology import rule_chain

ROOT = Path(__file__).resolve().parent.parent.parent.parent
GOLD = ROOT / "data/gold/goldstandard.json"
VERB_GOLD = ROOT / "data/gold/goldstandard_verben_fst.json"
TWANKSTA_WORDLIST = ROOT / "data/external/twanksta_entries.json"
TWANKSTA_DICT = ROOT / "data/external/twanksta_entries.json"
CLOSED_FW = ROOT / "data/closed/function_words.json"
CLOSED_PRONOUNS = ROOT / "data/closed/personal_pronouns.json"
BUILD_DIR = ROOT / "build"
LEXD_OUT = BUILD_DIR / "morphotactics.lexd"
FST_OUT = BUILD_DIR / "analyser.fst"
ATT_OUT = BUILD_DIR / "analyser.att"
LENIENT_OUT = BUILD_DIR / "lenient.fst"


def sample_by_lemma(entries: list[dict], n: int, rng: random.Random) -> list[dict]:
    """N zufällige Lexeme behalten – ganze Lemma-Gruppen (alle Formen eines
    Verbs / alle Paradigma-Kandidaten eines Nomens bleiben zusammen)."""
    lemmas = list(dict.fromkeys(e["lemma"] for e in entries))
    if n >= len(lemmas):
        return entries
    keep = set(rng.sample(lemmas, n))
    return [e for e in entries if e["lemma"] in keep]


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
    ap.add_argument("--sample", type=int, metavar="N",
                    help="nur N zufällige Wörterbuch-Lexeme je Klasse "
                         "(nominal/verbal) zusätzlich zum Goldstandard – "
                         "Testbau auf Teilmenge")
    ap.add_argument("--seed", type=int, default=0,
                    help="Seed für --sample (reproduzierbar, Default 0)")
    args = ap.parse_args()

    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))
    verb_data = json.loads(VERB_GOLD.read_text(encoding="utf-8"))
    print(f"Goldstandard: {len(gs_data)} nominal, {len(verb_data)} verbal")

    if args.gold_only:
        combined = gs_data
        verb_wl_entries = None
        wl_entries = []
    else:
        rng = random.Random(args.seed) if args.sample else None

        wl_data = json.loads(TWANKSTA_WORDLIST.read_text(encoding="utf-8"))
        wl_entries = wordlist_to_entries(wl_data, gs_data)
        if rng is not None:
            wl_entries = sample_by_lemma(wl_entries, args.sample, rng)
            print(f"Sample: {args.sample} nominale Lexeme (seed={args.seed})")
        print(f"Wortliste: {len(wl_entries)} Einträge (P9–P67)")
        combined = combine_entries(gs_data, wl_entries)

        # Verb-Einträge aus twanksta_entries.json (inkl. Twanksta-Formen)
        dict_data = json.loads(TWANKSTA_DICT.read_text(encoding="utf-8"))
        verb_wl_entries = verb_morph.wordlist_to_verb_entries(
            dict_data, verb_data
        )
        if rng is not None:
            verb_wl_entries = sample_by_lemma(verb_wl_entries, args.sample, rng)
            print(f"Sample: {args.sample} verbale Lexeme (seed={args.seed})")
        n_verbs = len({e["lemma"] for e in verb_wl_entries})
        print(f"Verb-Wortliste: {len(verb_wl_entries)} Einträge "
              f"({n_verbs} Verben)")

    # Closed-class: Personalpronomen
    closed_entries: list[dict] | None = None
    if not args.gold_only:
        closed_entries = json.loads(CLOSED_PRONOUNS.read_text(encoding="utf-8"))
        print(f"Personalpronomen: {len(closed_entries)} Einträge")

    # Unflektierte Funktionswörter + Adverbien (geschlossene Klassen)
    fw_words = None if args.gold_only else fw_mod.load(CLOSED_FW)
    adv_words = None if args.gold_only else adv_mod.load(TWANKSTA_DICT)

    nominal_total = len(gs_data) + len(wl_entries)
    verb_total = len(verb_data) + (len(verb_wl_entries) if verb_wl_entries else 0)
    print(f"Kombiniert: {nominal_total} nominal, {verb_total} verbal")
    if fw_words:
        print(f"Funktionswörter: {len(fw_words)} Types")
    if adv_words:
        print(f"Adverbien: {len(adv_words)} Types")

    lexd_text = build_lexd(
        combined, verb_data, verb_wl_entries,
        closed_entries=closed_entries, function_words=fw_words,
        adverbs=adv_words,
    )
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
