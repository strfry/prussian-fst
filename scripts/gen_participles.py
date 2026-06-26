#!/usr/bin/env python3
"""Generate fst/verb_participle_stems.lexc — the participle STEM list only.

The paradigm endings are hand-written in fst/verb_participles.lexc; the accent
shift is a rule in fst/stress.twolc. This script writes nothing but one citation
(long / barytone) stem per verb per participle, routed to the paradigm that
matches the lemma's accent class. Run once when the corpus dumps change.

Source: data/external/{twanksta,prusaspira}_entries.json (GitHub release of
strfry/prussian-corpus). Each verb carries up to three participles, listed in a
fixed order: [present-active, past-active, passive].

  īmtun:  present imānts   past immuns   passive īmts

Each participle declines like an adjective. We store its long-grade stem (the
Nom-Sg citation minus its ending) and let the paradigm + stress.twolc handle the
gemination / accent alternation:

  • present-active (≈ P29):  stem = citation[:-1] (drop -s)  → PtcpPres{Mob,Bar}
  • past-active   (≈ P68):  stem = citation[:-3] (drop -uns) → PtcpPast (no shift)
  • passive       (≈ P69):  stem = citation[:-1] (drop -s)   → PtcpPass{Mob,Bar}

ACCENT CLASS (Rinkevičius 2009, docs/AKZENT.md) is lexically idiosyncratic — not
recoverable from the Nom-Sg citation, where both classes show a long stem — so we
read it per lemma from prusaspira's full_declension (strong vs weak allomorph in
a strong cell: present Fem-Nom-Sg ī/i, passive Masc-Nom-Pl āi/ai) and default
twanksta-only verbs to mobile (the 96 % majority). A mobile stem de-accents in
the strong cells via the DEAC trigger on those endings; a barytone stem keeps its
accent. The past-active participle has a single invariant stem.

Run from the repo root:  python scripts/gen_participles.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "data" / "external"
OUT = ROOT / "fst" / "verb_participle_stems.lexc"


def lexc_esc(s: str) -> str:
    return s.replace(" ", "% ")


# ── Participle classification & accent class ─────────────────────────────────
def classify(forms: list[str]):
    """Map a verb's participle forms to {present,past,passive: bare_form}, using
    the fixed source order [present, past, passive]. Past = the -uns slot;
    present/passive fill the remaining -s slots in order. Placeholder slots that
    repeat the infinitive (or carry a space) are dropped."""
    out, rest = {}, []
    for f in forms:
        bare = f[:-3] if f.endswith(" si") else f
        if " " in bare:
            continue
        if bare.endswith("uns"):
            out.setdefault("past", bare)
        else:
            rest.append(bare)
    pp = [b for b in rest if b.endswith("s")]
    if pp:
        out["present"] = pp[0]
    if len(pp) >= 2:
        out["passive"] = pp[1]
    return out


def _cell(part, gen, case, num):
    for g in part.get("full_declension", []):
        if g["gender"] != gen:
            continue
        for cs in g["cases"]:
            if cs["case"] == case:
                v = cs.get(num, "")
                return v if v and " " not in v else None
    return None


def accent_class(part, cat):
    """Read 'Mob'/'Bar' from a prusaspira participle's strong cell, else None.
    Present → Fem-Nom-Sg (ī mobile / i barytone); passive → Masc-Nom-Pl (āi / ai)."""
    if cat == "present":
        v = _cell(part, "f", "Nominative", "singular")
        if v:
            return "Mob" if v.endswith("ī") else "Bar"
    elif cat == "passive":
        v = _cell(part, "m", "Nominative", "plural")
        if v:
            return "Mob" if v.endswith("āi") else ("Bar" if v.endswith("ai") else None)
    return None


def collect():
    """Union verbs keyed by lemma. Returns (forms, accent) where
    forms = {lemma: {cat: bareform}} and accent = {(lemma, cat): 'Mob'/'Bar'}
    (only where prusaspira attests it)."""
    forms: dict[str, dict] = {}
    accent: dict[tuple, str] = {}
    for name in ("twanksta_entries.json", "prusaspira_entries.json"):
        path = EXTERNAL / name
        if not path.exists():
            continue
        is_pr = name.startswith("prus")
        for e in json.loads(path.read_text(encoding="utf-8")):
            parts = e.get("forms", {}).get("participles")
            if not parts:
                continue
            word = e["word"]
            core = word[:-3] if word.endswith(" si") else word
            if " " in core:
                continue
            cats = classify([p["form"] for p in parts])
            if not cats:
                continue
            forms.setdefault(word, {}).update(cats)
            if is_pr:
                for part in parts:
                    cat = {"Present": "present", "Past": "past",
                           "Passive": "passive"}.get(part.get("type"))
                    if cat in ("present", "passive"):
                        cls = accent_class(part, cat)
                        if cls:
                            accent[(word, cat)] = cls
    return forms, accent


# ── Emission ─────────────────────────────────────────────────────────────────
def emit_stems(forms: dict, accent: dict) -> tuple[list[str], dict]:
    L = ["LEXICON PtcpStems"]
    stats = {"present": 0, "past": 0, "passive": 0, "passive_soft": 0,
             "Mob": 0, "Bar": 0, "default_mob": 0}

    def two_grade(cat, tag, name, lemma_esc, long_stem, lemma):
        cls = accent.get((lemma, cat))
        if cls is None:
            cls = "Mob"            # twanksta-only default (96 % majority)
            stats["default_mob"] += 1
        stats[cls] += 1
        up = f"{lemma_esc}+V+Part+{tag}"
        L.append(f"  {up}:{lexc_esc(long_stem)}  Ptcp{name}{cls} ;")

    for lemma in sorted(forms):
        cats = forms[lemma]
        lem = lexc_esc(lemma)

        if "present" in cats:
            two_grade("present", "Pres", "Pres", lem, cats["present"][:-1], lemma)
            stats["present"] += 1

        if "past" in cats:
            stem = cats["past"][:-3]
            L.append(f"  {lem}+V+Part+Pret:{lexc_esc(stem)}  PtcpPast ;")
            stats["past"] += 1

        if "passive" in cats:
            form = cats["passive"]
            if form.endswith("ts"):
                two_grade("passive", "Pass", "Pass", lem, form[:-1], lemma)
                stats["passive"] += 1
            else:
                # soft/vowel-stem passive (-tas, Standardvariation): citation only.
                L.append(f"  {lem}+V+Part+Pass+Masc+Sg+Nom:{lexc_esc(form)}  # ;")
                stats["passive_soft"] += 1
    L.append("")
    return L, stats


def main():
    forms, accent = collect()
    out = ["! Participle stems — generated by scripts/gen_participles.py",
           "! Source: data/external/{twanksta,prusaspira}_entries.json",
           "! One citation stem per verb per participle, routed to a hand-written",
           "! paradigm in verb_participles.lexc. The accent shift is a rule in",
           "! stress.twolc. Mob = mobile (de-accents in strong cells), Bar =",
           "! barytone. See docs/FST_PARTICIPLES.md.",
           ""]
    stem_lines, stats = emit_stems(forms, accent)
    out += stem_lines
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}  ({len(forms)} verbs)")
    print(f"  present={stats['present']} past={stats['past']} "
          f"passive(hard)={stats['passive']} passive(soft)={stats['passive_soft']}")
    print(f"  accent: Mob={stats['Mob']} Bar={stats['Bar']} "
          f"(default-mob for twanksta-only={stats['default_mob']})")


if __name__ == "__main__":
    main()
