#!/usr/bin/env python3
"""HFST-nativer Build: lexc-Lexikon ∘ Regeln → analyser/lenient (echte Komposition).

    morphotactics.lexc                      (markierte Unterseite, V-frei)
        ∘  rules.PHONOLOGY   (SHORTEN ∘ LENGTHEN ∘ JPAL ∘ CLEANUP)
        =  generator.hfst    (Analyse → Standardoberfläche)
        ∘  rules.SPELLRELAX  (generalisierende Quellvarianten)
        =  lenient (generator-Seite) ; invertiert = analyser/lenient

Gespeichert werden (alle als HFST-Transducer, FOMA-Backend):
    build/hfst/morphotactics.lexc
    build/hfst/generator.hfst   Analyse → Oberfläche  (Standard)
    build/hfst/analyser.hfst    Oberfläche → Analyse  (Standard)
    build/hfst/lenient.hfst     Oberfläche(+Varianten) → Analyse

Aufruf (im hfst-venv, Python 3.12):
    PYTHONPATH=src python -m prussian.fst.hfst.build [--gold-only | --sample N]
"""

import argparse
import json
import random
from pathlib import Path

import hfst

from prussian.fst.hfst.lexc_gen import build_lexc
from prussian.fst.hfst import rules
from prussian.fst.morphology import adverbs as adv_mod
from prussian.fst.morphology import function_words as fw_mod
from prussian.fst.morphology import verbs as verb_morph
from prussian.fst.morphology.nominals import combine_entries, wordlist_to_entries

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
GOLD = ROOT / "data/gold/goldstandard.json"
VERB_GOLD = ROOT / "data/gold/goldstandard_verben_fst.json"
TWANKSTA = ROOT / "data/external/twanksta_entries.json"
CLOSED_FW = ROOT / "data/closed/function_words.json"
CLOSED_PRONOUNS = ROOT / "data/closed/personal_pronouns.json"
BUILD = ROOT / "build/hfst"
LEXC_OUT = BUILD / "morphotactics.lexc"
GEN_OUT = BUILD / "generator.hfst"
ANA_OUT = BUILD / "analyser.hfst"
LEN_OUT = BUILD / "lenient.hfst"

FOMA = hfst.ImplementationType.FOMA_TYPE


def sample_by_lemma(entries, n, rng):
    lemmas = list(dict.fromkeys(e["lemma"] for e in entries))
    if n >= len(lemmas):
        return entries
    keep = set(rng.sample(lemmas, n))
    return [e for e in entries if e["lemma"] in keep]


def _compose_chain(base, regex_strings):
    """base ∘ regex_strings[0] ∘ … (alle als hfst.regex kompiliert)."""
    result = hfst.HfstTransducer(base)
    for src in regex_strings:
        r = hfst.regex(src)
        r.convert(FOMA)
        result.compose(r)
        result.minimize()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-only", action="store_true")
    ap.add_argument("--sample", type=int, metavar="N")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    hfst.set_default_fst_type(FOMA)

    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))
    verb_data = json.loads(VERB_GOLD.read_text(encoding="utf-8"))
    print(f"Goldstandard: {len(gs_data)} nominal, {len(verb_data)} verbal")

    verb_wl = closed = fw_words = adv_words = None
    if args.gold_only:
        combined = gs_data
        wl_entries = []
    else:
        rng = random.Random(args.seed) if args.sample else None
        wl_data = json.loads(TWANKSTA.read_text(encoding="utf-8"))
        wl_entries = wordlist_to_entries(wl_data, gs_data)
        if rng is not None:
            wl_entries = sample_by_lemma(wl_entries, args.sample, rng)
        combined = combine_entries(gs_data, wl_entries)
        verb_wl = verb_morph.wordlist_to_verb_entries(wl_data, verb_data)
        if rng is not None:
            verb_wl = sample_by_lemma(verb_wl, args.sample, rng)
        closed = json.loads(CLOSED_PRONOUNS.read_text(encoding="utf-8"))
        fw_words = fw_mod.load(CLOSED_FW)
        adv_words = adv_mod.load(TWANKSTA)
        print(f"Wortliste: {len(wl_entries)} nominal, "
              f"{len(verb_wl)} verbal; +{len(closed)} Pronomen, "
              f"{len(fw_words)} FW, {len(adv_words)} Adv")

    lexc_text = build_lexc(
        combined, verb_data, verb_wl, closed_entries=closed,
        function_words=fw_words, adverbs=adv_words,
    )
    BUILD.mkdir(parents=True, exist_ok=True)
    LEXC_OUT.write_text(lexc_text, encoding="utf-8")
    print(f"lexc → {LEXC_OUT} ({len(lexc_text.splitlines())} Zeilen)")

    lexicon = hfst.compile_lexc_file(str(LEXC_OUT), verbosity=0)
    lexicon.convert(FOMA)
    print(f"Lexikon: {lexicon.number_of_states()} Zustände")

    # generator = lexicon ∘ Phonologie  (Analyse → Standardoberfläche)
    generator = _compose_chain(lexicon, rules.PHONOLOGY)
    print(f"generator (∘ Phonologie): {generator.number_of_states()} Zustände")

    analyser = hfst.HfstTransducer(generator)
    analyser.invert()
    analyser.minimize()

    # lenient: die Grenz-j-Regeln (SPELLRELAX_MARKED) brauchen den Marker · und
    # laufen daher VOR CLEANUP auf der markierten Unterseite; die rein
    # orthografischen Regeln (SPELLRELAX_SURFACE) danach auf der Oberfläche.
    lenient_phon = [rules.SHORTEN, rules.LENGTHEN, rules.JPAL,
                    *rules.SPELLRELAX_MARKED, rules.CLEANUP]
    lenient_gen = _compose_chain(lexicon, lenient_phon)
    lenient_gen = _compose_chain(lenient_gen, rules.SPELLRELAX_SURFACE)
    lenient = hfst.HfstTransducer(lenient_gen)
    lenient.invert()
    lenient.minimize()
    print(f"lenient (∘ spellrelax, invertiert): "
          f"{lenient.number_of_states()} Zustände")

    for fst, path in ((generator, GEN_OUT), (analyser, ANA_OUT),
                      (lenient, LEN_OUT)):
        out = hfst.HfstOutputStream(filename=str(path), type=FOMA)
        out.write(fst)
        out.flush()
        out.close()
    print(f"Gespeichert: {GEN_OUT.name}, {ANA_OUT.name}, {LEN_OUT.name}")


if __name__ == "__main__":
    main()
