#!/usr/bin/env python3
"""Fast dictionary coverage for the HFST (lexd) pipeline via hfst-lookup batch."""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DICT = ROOT / "data/external/twanksta_entries.json"
GOLD = ROOT / "data/gold/goldstandard.json"
ANALYSER = ROOT / "build/hfst/analyser.hfst"
LENIENT = ROOT / "build/hfst/lenient.hfst"
CLOSED_FW = ROOT / "data/closed/function_words.json"

CASE_MAP = {
    "Nominative": "Nom",
    "Genitive": "Gen",
    "Dative": "Dat",
    "Accusative": "Acc",
}
NUM_MAP = {"singular": "sg", "plural": "pl"}
GENDER_MAP = {"masc": "m", "fem": "f", "neut": "n"}

# <Tag> → +Tag conversion for output
_RE_TAG = re.compile(r"<([A-Za-z0-9]+)>")


def _to_plus(tags: str) -> str:
    return _RE_TAG.sub(r"+\1", tags)


def _batch_lookup(fst_path: str, forms: list[str]) -> set[str]:
    """Pipe all forms through hfst-lookup, return set of analyzed (form, tags)."""
    if not forms:
        return set()
    input_text = "\n".join(forms) + "\n"
    result = subprocess.run(
        ["hfst-lookup", fst_path],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=300,
    )
    # Parse: "form\ttag1,tag2\tweight"
    found = set()
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1] and "+?" not in parts[1]:
            form = parts[0].strip()
            tags = _to_plus(parts[1].strip())
            found.add((form, tags))
    return found


def _collect_forms(words: list[dict]) -> dict[str, dict]:
    """Collect all nominal + verbal forms from wordlist, return {form: info}."""
    forms: dict[str, dict] = {}
    for w in words:
        par = w.get("paradigm", "")
        lemma = w.get("word", "")
        f = w.get("forms")
        if not isinstance(f, dict):
            continue
        decl = f.get("declension")
        if isinstance(decl, list):
            for block in decl:
                for case_info in block.get("cases", []):
                    if case_info.get("case", "") not in CASE_MAP:
                        continue
                    for num_name in NUM_MAP:
                        form = case_info.get(num_name, "").strip()
                        if form and form != "—":
                            forms.setdefault(form, {"lemma": lemma, "par": par})
        indicative = f.get("indicative")
        if isinstance(indicative, list):
            for block in indicative:
                for slot in block.get("forms", []):
                    form = slot.get("form", "").strip()
                    if form and form != "—" and " " not in form:
                        forms.setdefault(form, {"lemma": lemma, "par": par})
    return forms


def _par_int(p: str) -> int:
    m = re.match(r"(\d+)", p)
    return int(m.group(1)) if m else 999


def main():
    words = json.loads(DICT.read_text(encoding="utf-8"))
    print(f"Wörterbuch-Einträge: {len(words)}")

    forms = _collect_forms(words)
    all_forms = list(forms.keys())
    print(f"Unique Formen: {len(all_forms)}")

    # Batch lookup through analyser
    print("··· hfst-lookup analyser …", end=" ", flush=True)
    analysed = _batch_lookup(str(ANALYSER), all_forms)
    analysed_forms = {f for f, _ in analysed}
    print(f"{len(analysed_forms)} gefunden")

    # Missing forms → lenient
    missing = [f for f in all_forms if f not in analysed_forms]
    ortho = set()
    if missing:
        print(
            f"··· hfst-lookup lenient ({len(missing)} fehlende) …", end=" ", flush=True
        )
        ortho_raw = _batch_lookup(str(LENIENT), missing)
        ortho = {f for f, _ in ortho_raw}
        print(f"{len(ortho)} gefunden")

    no_match = set(all_forms) - analysed_forms - ortho
    total = len(all_forms)
    direct_pct = 100 * len(analysed_forms) / total
    ortho_pct = 100 * len(ortho) / total
    no_pct = 100 * len(no_match) / total

    print(f"\n=== HFST (lexd) Dictionary Coverage ===")
    print(f"  Direct (analyser):  {len(analysed_forms):>6}/{total} ({direct_pct:.1f}%)")
    print(f"  Ortho (lenient):    {len(ortho):>6}/{total} ({ortho_pct:.1f}%)")
    print(f"  Not recognized:     {len(no_match):>6}/{total} ({no_pct:.1f}%)")
    print(
        f"  Total coverage:     {len(analysed_forms | ortho):>6}/{total} ({direct_pct + ortho_pct:.1f}%)"
    )

    # By POS (nominal vs verbal)
    nom_forms = {f for f, _ in analysed if "+N" in _ or "+A" in _ or "+Pron" in _}
    verb_forms = {f for f, _ in analysed if "+V" in _}
    other_forms = analysed_forms - nom_forms - verb_forms
    other_pos = Counter()
    for f, tags in analysed:
        if f in other_forms:
            for pos in ["+Num", "+Adv", "+Pr", "+Cjn", "+Pcl", "+Refl"]:
                if pos in tags:
                    other_pos[pos] += 1
    print(f"\n  Nominal (+N/+A/+Pron): {len(nom_forms)}")
    print(f"  Verbal (+V):           {len(verb_forms)}")
    print(f"  Other:                 {len(other_forms)}")
    if other_pos:
        print(f"    breakdown: {dict(other_pos.most_common())}")

    # Sample unrecognized
    if no_match:
        print(f"\n  Unrecognized samples (top 15):")
        for i, f in enumerate(sorted(no_match)[:15]):
            info = forms.get(f, {})
            print(f"    {f}  ({info.get('lemma', '?')}, P{info.get('par', '?')})")

    # Transducer sizes
    import hfst

    for name, path, label in [
        ("analyser", ANALYSER, "Analyser"),
        ("generator", ROOT / "build/hfst/generator.hfst", "Generator"),
        ("lenient", LENIENT, "Lenient"),
    ]:
        fst = hfst.HfstInputStream(str(path)).read()
        print(
            f"\n  {label}: {fst.number_of_states()} states ({fst.number_of_arcs()} arcs)"
        )

    # Compare with pyfoma dashboard
    try:
        dash = json.loads(
            (ROOT / "data/derived/dashboard.json").read_text(encoding="utf-8")
        )
        pyfoma = dash["kpis"]["form_coverage"]
        print(f"\n=== Comparison: pyfoma dashboard ===")
        print(f"  pyfoma: {pyfoma['pct']}% ({pyfoma['num']}/{pyfoma['den']})")
        print(f"  hfst:   {direct_pct:.1f}% ({len(analysed_forms)}/{total})")
    except Exception:
        pass


if __name__ == "__main__":
    main()
