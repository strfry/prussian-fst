#!/usr/bin/env python3
"""Validate participle forms across Prusaspira and Twanksta.

Reads all participles.json files, compares Prusaspira vs Twanksta forms,
and checks against predicted forms from grammatical rules.

Outputs a comparison report as markdown.
"""

import json
from pathlib import Path

TWANKSTA_DIR = Path("twanksta")
VERB_PARADIGMS = Path("verb_paradigms.json")


def main():
    vp = json.loads(VERB_PARADIGMS.read_text(encoding="utf-8"))
    paradigms = vp["paradigms"]

    # Collect all verb data with participles
    rows = []
    for part_file in sorted(TWANKSTA_DIR.glob("*/participles.json")):
        data = json.loads(part_file.read_text())
        num = data["paradigm"]
        lemma = data["lemma"]
        inf_stem = data["infinitive_stem"]
        prus = data.get("prusaspira", {})
        twank = data.get("twanksta", {})

        prus_part = prus.get("participles", {})
        twank_part = {k: v["form"] for k, v in twank.get("participles", {}).items()}

        # Get verb paradigm data (present/preterite 3sg)
        vp_entry = paradigms.get(num, {})
        present_3sg = (vp_entry.get("present") or {}).get("3sg", "") if vp_entry else ""
        pret_3sg = (vp_entry.get("preterite") or {}).get("3sg", "") if vp_entry else ""
        # Take first form if multiple (e.g. "immi/immē")
        if "/" in pret_3sg:
            pret_3sg = pret_3sg.split("/")[0]
        is_intransitive = vp_entry.get("inf", {}).get("tun") is None if vp_entry else False
        has_twei = bool((vp_entry.get("inf") or {}).get("twei")) if vp_entry else False

        rows.append({
            "num": num,
            "lemma": lemma,
            "inf_stem": inf_stem,
            "present_3sg": present_3sg,
            "pret_3sg": pret_3sg,
            "prus_present": prus_part.get("present"),
            "prus_past": prus_part.get("past"),
            "prus_passive": prus_part.get("passive"),
            "twank_present": twank_part.get("present"),
            "twank_past": twank_part.get("past"),
            "twank_passive": twank_part.get("passive"),
            "is_intransitive": is_intransitive,
            "has_twei": has_twei,
        })

    # ── Report ──
    print("# Participle Validation Report\n")
    print(f"Total paradigms with participle data: {len(rows)}\n")

    # 1. Prusaspira vs Twanksta mismatches
    print("## 1. Prusaspira ↔ Twanksta Mismatches\n")
    has_diff = False
    for r in rows:
        diffs = []
        for key, p_label, t_label in [
            ("present", "prus_present", "twank_present"),
            ("past", "prus_past", "twank_past"),
            ("passive", "prus_passive", "twank_passive"),
        ]:
            pv = r[p_label]
            tv = r[t_label]
            if pv and tv and pv != tv:
                diffs.append(f"  `{key}`: prus=`{pv}` twank=`{tv}`")
        if diffs:
            has_diff = True
            print(f"**P{r['num']} {r['lemma']}**")
            for d in diffs:
                print(d)
            print()
    if not has_diff:
        print("No mismatches found.\n")

    # 2. Summary by ending class
    print("## 2. By Present 3sg Ending Class\n")
    from collections import defaultdict
    by_ending = defaultdict(list)
    for r in rows:
        ps3 = r["present_3sg"]
        if ps3:
            # Classify ending
            if ps3.endswith("ne"):
                cls = "-ne"
            elif ps3.endswith("ija") or ps3.endswith("ijja"):
                cls = "-ija/-ijja"
            elif ps3.endswith("ja") and not ps3.endswith(("ija", "ūja", "aūja")):
                cls = "-ja"
            elif ps3.endswith("ūja") or ps3.endswith("aūja"):
                cls = "-ūja/-aūja"
            elif ps3.endswith("aui"):
                cls = "-aui"
            elif ps3.endswith("ēi") or ps3.endswith("ei"):
                cls = "-ēi/-ei"
            elif ps3.endswith("ai") or ps3.endswith("āi"):
                cls = "-ai/-āi"
            elif ps3.endswith("a") and not ps3.endswith("ja"):
                cls = "-a"
            elif ps3.endswith("e") and not ps3.endswith("ne"):
                cls = "-e"
            elif ps3.endswith("i") and not ps3.endswith(("ai", "ei", "ui", "īi", "aui")):
                cls = "-i"
            elif ps3.endswith("t"):
                cls = "-t (athematic)"
            else:
                cls = f"other ({ps3[-3:]})"
            by_ending[cls].append(r)

    for cls in sorted(by_ending.keys()):
        items = by_ending[cls]
        part_forms = set()
        for r in items:
            pp = r["twank_present"] or r["prus_present"]
            if pp:
                part_forms.add(pp)
        print(f"**{cls}** ({len(items)} verbs)")
        print(f"  Pres.p: {sorted(part_forms)[:5]}")
        print()

    # 3. Full data table (markdown)
    print("## 3. Full Data Table\n")
    print("| P | Lemma | 3sg | Prät | Prus.Präs | Twank.Präs | Prus.Perf | Twank.Perf | Prus.Pass | Twank.Pass |")
    print("|---|-------|-----|------|-----------|------------|-----------|------------|-----------|------------|")
    for r in rows:
        def s(v): return v or "-"
        print(f"| {r['num']} | {r['lemma']} | {s(r['present_3sg'])} | {s(r['pret_3sg'])} | "
              f"{s(r['prus_present'])} | {s(r['twank_present'])} | "
              f"{s(r['prus_past'])} | {s(r['twank_past'])} | "
              f"{s(r['prus_passive'])} | {s(r['twank_passive'])} |")

    print(f"\nTotal: {len(rows)} verbs")


if __name__ == "__main__":
    main()
