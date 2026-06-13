#!/usr/bin/env python3
"""Analyse Prussian verb paradigms for participle derivations."""

import json
import re
from collections import defaultdict
from pathlib import Path

VERB_PARADIGMS = Path(__file__).parent / "verb_paradigms.json"


def load_paradigms(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["paradigms"]


def infinitive_stem(inf: dict) -> str | None:
    """Extract infinitive stem by removing -tun, -twei, or -stwei."""
    tun = inf.get("tun")
    twei = inf.get("twei")
    form = tun or twei
    if not form:
        return None
    for suffix in ("stwei", "twei", "tun"):
        if form.endswith(suffix):
            return form[: -len(suffix)]
    return form


def is_transitive(inf: dict) -> bool:
    """Whether the paradigm has a transitive (-tun) infinitive form."""
    return inf.get("tun") is not None


def preterite_first(form: str) -> str:
    """Take the first variant if preterite has multiple forms like 'immi/immē'."""
    return form.split("/")[0]


def present_ending(form: str) -> tuple[str, str]:
    """Classify the present 3sg ending into a (category, subpattern) tuple."""
    if form is None:
        return ("??", "")
    # Order matters – longer specific patterns first
    patterns = [
        ("ijja", "ijja"),
        ("ūja", "ūja"),
        ("aui", "aui"),
        ("āi", "āi"),
        ("ēi", "ēi"),
        ("ei", "ei"),
        ("ai", "ai"),
        ("ja", "ja"),
        ("ne", "ne"),
        ("sta", "a"),   # sta-stem — subtype of a-stem
        ("da", "a"),    # d-infix a-stem
        ("na", "a"),    # n-infix a-stem
        ("a", "a"),
        ("e", "e"),
        ("i", "i"),
        ("t", "t"),
    ]
    for ending_pat, category in patterns:
        if form.endswith(ending_pat):
            return (category, ending_pat)
    return (form[-2:] if len(form) >= 2 else form, "")


def present_participle_ending(present_3sg: str) -> str:
    """Derive expected present active participle ending from present 3sg form."""
    cat, sub = present_ending(present_3sg)
    mapping = {
        "a": "-ants",
        "e": "-ints",
        "i": "-ints",
        "ai": "-ānts",
        "āi": "-ānts",
        "ei": "-īnts",
        "ēi": "-īnts",
        "aui": "-auints",
        "ūja": "-ūjants",
        "ja": "-jants",
        "ijja": "-ijjants",
        "ne": "-nints",
        "t": "-nts",
    }
    base = mapping.get(cat, f"-?nts ({cat})")
    # Add note for infixed subtypes
    if sub in ("sta", "da", "na"):
        base = f"{base} ({sub}-infix)"
    return base


def compute_active_past(inf_stem: str | None, pret_3sg: str, pard_num: str) -> tuple[str | None, list[str]]:
    """Compute expected active past participle. Returns (form, warnings)."""
    warnings = []
    if inf_stem is None:
        return None, ["no infinitive stem"]

    pret = preterite_first(pret_3sg)

    # Paradigms 106-108 special: -juns
    if any(pard_num.startswith(prefix) for prefix in ("106", "107", "108")):
        # Strip preterite ending -a/ā for these j-stems
        pret_stem = re.sub(r"[āa]$", "", pret)
        return f"{pret_stem}uns", warnings

    # If infinitive stem ends in vowel → stem + -wuns
    if inf_stem and re.search(r"[aeiouūāēīō]$", inf_stem, re.IGNORECASE):
        return f"{inf_stem}wuns", warnings

    # Consonant stem: use preterite stem → preterite stem + -uns
    # Strip preterite 3sg ending: -i, -ē, -e, -a, -ā, -ai, -ei, -ū
    pret_stem = re.sub(r"(?:[āaeēi]|ai|ei)$", "", pret)
    if pret_stem:
        return f"{pret_stem}uns", warnings
    else:
        warnings.append("could not extract preterite stem")
        return f"{inf_stem}uns", warnings


def compute_passive(inf_stem: str | None, inf: dict) -> tuple[str | None, list[str]]:
    """Compute expected passive (perfect) participle: infinitive stem + -ts.
    Only for transitive (-tun) verbs."""
    warnings = []
    if not is_transitive(inf):
        return None, ["intransitive – no passive participle"]
    if inf_stem is None:
        return None, ["no infinitive stem"]
    return f"{inf_stem}ts", warnings


def flag_problems(pard_num: str, inf: dict, pret_3sg: str, inf_stem: str | None,
                  pres_3sg: str) -> list[str]:
    """Collect warnings/flags for non-straightforward paradigms."""
    flags = []

    if inf.get("tun") is None and inf.get("twei") is None:
        flags.append("no infinitive form at all")

    if "/" in pret_3sg:
        flags.append("preterite has variants")

    if inf_stem is None:
        flags.append("cannot determine infinitive stem")

    # Check for suppletive / irregular paradigms
    irregular_paradigms = {
        "115": "suppletive: ast/bēi",
        "116": "gūbi irregular preterite",
        "121": "dest/dīja irregular present/preterite",
        "117": "īst/īda irregular",
        "123": "skreīt/skrijja irregular present/preterite",
        "84": "jāute/jutta irregular",
        "112": "strāuja/struwwa irregular",
    }
    if pard_num in irregular_paradigms:
        flags.append(f"irregular: {irregular_paradigms[pard_num]}")

    # Check tempusgleich (preterite == present)
    return flags


def main():
    paradigms = load_paradigms(VERB_PARADIGMS)

    rows = []
    for pard_key in sorted(paradigms.keys(), key=lambda k: (k.rstrip("abcdfgs"), k)):
        p = paradigms[pard_key]
        inf = p.get("inf", {})
        pres = p.get("present", {})
        pret = p.get("preterite", {})
        tempusgleich = p.get("tempusgleich", False)

        pres_3sg = pres.get("3sg")
        pret_3sg = pret.get("3sg", "")

        inf_stem = infinitive_stem(inf)
        ending_cat, ending_sub = present_ending(pres_3sg)

        pret_first = preterite_first(pret_3sg) if pret_3sg else ""
        pret_eq_pres = tempusgleich or (pret_first == pres_3sg)

        pres_part_end = present_participle_ending(pres_3sg)

        act_past, act_warn = compute_active_past(inf_stem, pret_3sg, pard_key)
        pas_part, pas_warn = compute_passive(inf_stem, inf)

        problems = flag_problems(pard_key, inf, pret_3sg, inf_stem, pres_3sg)
        problems.extend(act_warn)
        problems.extend(pas_warn)
        if pret_eq_pres and not tempusgleich:
            problems.append("preterite equals present (de facto tempusgleich)")
        if tempusgleich:
            problems.append("tempusgleich – preterite=present")

        rows.append({
            "num": pard_key,
            "lemma": p.get("lemma", ""),
            "inf_stem": inf_stem or "?",
            "inf_form": inf.get("tun") or inf.get("twei") or "?",
            "pres_3sg": pres_3sg or "?",
            "pres_ending": ending_sub,
            "pres_cat": ending_cat,
            "pret_3sg": pret_first,
            "pret_eq_pres": pret_eq_pres,
            "pres_part": pres_part_end,
            "act_past_part": act_past or "?",
            "pas_part": pas_part or "—",
            "problems": problems,
        })

    # ── Summary by present 3sg ending pattern ──
    groups = defaultdict(list)
    for r in rows:
        groups[r["pres_cat"]].append(r["num"])

    print("=" * 92)
    print("PRUSSIAN VERB PARTICIPLE ANALYSIS")
    print("=" * 92)

    # Summary table
    print(f"\n{'Present 3sg ending':<16} {'Pres. Part.':<22} {'Count':>6}   Paradigms")
    print("-" * 92)
    for ending in sorted(groups.keys()):
        nums = groups[ending]
        # get a representative present participle ending
        rep = next(r["pres_part"] for r in rows if r["pres_cat"] == ending)
        print(f"{ending:<16} {rep:<22} {len(nums):>6}   {', '.join(nums)}")

    # ── Detailed table ──
    print("\n" + "=" * 140)
    print("DETAILED PARADIGM TABLE")
    print("=" * 140)
    header = (f"{'Par#':<6} {'Lemma':<20} {'Inf.Stem':<12} {'Pres.3sg':<12} "
              f"{'End':<6} {'Pret.3sg':<12} {'T=Pr':<4} {'Pres.Part':<20} "
              f"{'Act.Past.Part':<18} {'Pass.Part':<14} {'Flags'}")
    print(header)
    print("-" * 140)
    for r in rows:
        t_flag = "✓" if r["pret_eq_pres"] else ""
        flags = "; ".join(r["problems"]) if r["problems"] else ""
        print(f"{r['num']:<6} {r['lemma']:<20} {r['inf_stem']:<12} {r['pres_3sg']:<12} "
              f"{r['pres_ending']:<6} {r['pret_3sg']:<12} {t_flag:<4} {r['pres_part']:<20} "
              f"{r['act_past_part']:<18} {r['pas_part']:<14} {flags}")

    print("\n" + "=" * 140)
    print("KEY — Present participle endings (derived from present 3sg ending pattern):")
    print("  -ants   = a-stems")
    print("  -ints   = e-stems, i-stems")
    print("  -ānts   = ā-stems (present in -ai/-āi)")
    print("  -īnts   = ī-stems (present in -ei/-ēi)")
    print("  -jants  = ja-stems")
    print("  -ijjants= ijja-stems")
    print("  -ūjants = ūja-stems")
    print("  -auints = au-stems (present in -aui)")
    print("  -nints  = ne-stems")
    print("  -nts    = athematic (present in -t)")
    print()
    print("Active past participle (active preterite participle):")
    print("  vowel stem infinitive → stem + -wuns")
    print("  consonant stem infinitive → preterite stem + -uns")
    print("  paradigms 106-108 → -juns (j-stem preterites)")
    print()
    print("Passive (perfect) participle:")
    print("  transitive (-tun) only → infinitive stem + -ts")
    print("  intransitive (-twei) → no passive participle")


if __name__ == "__main__":
    main()
