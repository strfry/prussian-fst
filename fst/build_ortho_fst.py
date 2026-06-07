#!/usr/bin/env python3
"""Baut einen Orthographie-Normalisierungs-FST aus ALLEN FST-Eintraegen
(goldstandard.json + wordlist.json).

Erzeugt fst/ortho.fst: einen Transducer der Twanksta-Orthographie-Varianten
(mit explizitem Palatalisierungs-j) auf die FST-Standard-Formen abbildet.

Der FST ist obere/untere-Seite: standard:variant.
  .analyze("kūgjan") → ["kūgin"]   (Variant → Standard)
"""

import json
from pathlib import Path

from pyfoma import FST

from fst.ortho_rules import variant_suffix
from fst.build_fst import resolve_stem, wordlist_to_entries

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GOLD = ROOT / "goldstandard.json"
WORDLIST = ROOT / "wordlist.json"
ORTHO_FST = HERE / "ortho.fst"


def build_pairs(entries: list[dict]) -> list[tuple[str, str]]:
    """Generate (standard, variant) form pairs from entries."""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for e in entries:
        stamm = e["stamm"]
        for _cell, v in e["suffixe"].items():
            suffix = v["suffix"]
            betont = v["betont"]
            pal = v.get("palatize", False)

            jvar = variant_suffix(suffix)
            if jvar is None:
                continue

            standard = resolve_stem(stamm, betont, pal) + suffix
            variant = resolve_stem(stamm, betont, False) + jvar

            if standard != variant and (standard, variant) not in seen:
                seen.add((standard, variant))
                pairs.append((standard, variant))

    return pairs


def main() -> None:
    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))
    wl_data = json.loads(WORDLIST.read_text(encoding="utf-8"))
    print(f"Loaded {len(gs_data)} goldstandard + {len(wl_data)} wordlist entries")

    wl_entries = wordlist_to_entries(wl_data, gs_data)
    all_entries = gs_data + wl_entries
    seen_keys: set[tuple[str, str, str]] = set()
    combined: list[dict] = []
    for e in all_entries:
        key = (e["lemma"], e["paradigm"], e["gender"])
        if key not in seen_keys:
            seen_keys.add(key)
            combined.append(e)
    print(f"Combined unique entries: {len(combined)}")

    pairs = build_pairs(combined)
    print(f"Ortho variant pairs: {len(pairs)}")

    fst = FST.from_strings(pairs)
    n_states = len(fst.states)
    print(f"Compiled ortho FST: {n_states} states")

    fst.save(str(ORTHO_FST))
    print(f"Saved {ORTHO_FST}")

    # Quick sanity checks
    tests = [
        ("kūgjan", "kūgin"),
        ("āngjan", "āngin"),
        ("āngjas", "ānges"),
        ("kūgjai", "kūgei"),
        ("māldaisjan", "māldaisin"),
        ("buccjas", "buccas"),
        ("buccjai", "buccai"),
        ("buccjamans", "buccamans"),
        ("dulzjai", "dulžai"),
        ("dulzjas", "dulžas"),
        ("dulzju", "dulžu"),
        ("dulzjamans", "dulžamans"),
        ("garkītjamans", "garkītemans"),
        # Neue Wortlist-Eintraege
        ("sāminjas", "sāmines"),
        ("paāntrinsenjas", "paāntrinsenes"),
        ("līgjas", "līges"),
    ]
    for variant, expected in tests:
        results = list(fst.analyze(variant))
        ok = expected in results
        print(f"  {'OK' if ok else 'FAIL'}  analyze({variant!r}) → {expected!r}  {results}")

    print("Done.")


if __name__ == "__main__":
    main()
