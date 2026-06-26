#!/usr/bin/env python3
"""Generate fst/verb_participles.lexc from the prussian-corpus entry dumps.

Source: data/external/{twanksta,prusaspira}_entries.json (GitHub release of
strfry/prussian-corpus). Each verb carries up to three participles, listed in a
fixed order: [present-active, past-active, passive].

The three participles decline like adjectives (present ≈ P29, past-active ≈ P68,
passive ≈ P69). The crux is gemination / vowel length: the FST concatenates
literally, so each participle needs its OWN correctly graded stem rather than one
derived from the verb.

  īmtun:  present imānts (im-)   past immuns (imm-)   passive īmts (īm-)

ACCENT SHIFT (Rinkevičius 2009, docs/AKZENT.md). Present & passive decline with a
two-grade stem governed by the lexeme's accent class:

  • Barytona (fixed stem stress): the stem keeps its accent (long vowel) in every
    cell; the endings are always weak/deaccented   →  abōnit-ai, abōnit-i.
  • Mobilia (mobile stress): a STRONG ending pulls the accent off the stem; there
    the root vowel is unstressed and shortens, and the ending takes its heavy
    (long/geminated) shape                          →  dat-āi, dant-immans, dant-ī.

The strong cells are Dat-Pl and Fem-Nom-Sg (present) plus Nom-Pl (passive). The
accent class is lexically idiosyncratic — not recoverable from the citation
(Nom-Sg) form, where both classes show a long stem — so we read it per lemma from
prusaspira's full_declension (strong vs weak allomorph in a strong cell) and
default twanksta-only verbs to mobile (the 96 % majority). The past-active
participle has a single invariant stem (no accent alternation).

Run from the repo root:  python scripts/gen_participles.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "data" / "external"
OUT = ROOT / "fst" / "verb_participles.lexc"

# Accent orthography (Rinkevičius 2009): a stressed stem vowel is written either
# long (macron) or as a gravis, and its shortness can be marked by gemination of
# the following consonant. All three are accent exponents.
SHORTEN = {"ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u",
           "à": "a", "è": "e", "ì": "i", "ò": "o", "ù": "u"}
VOWELS = set("aeiouāēīōūàèìòùáéíóú")


def deaccent_stem(stem: str) -> str:
    """De-accent a mobile stem under a strong ending: the whole stem is unstressed,
    so remove every accent exponent — shorten long/gravis vowels and de-geminate
    doubled consonants. A short-rooted mobile has none and stays unchanged (the
    shift then shows only on the ending)."""
    out: list[str] = []
    for i, ch in enumerate(stem):
        if ch in SHORTEN:
            out.append(SHORTEN[ch])
        elif out and ch == stem[i - 1] and ch not in VOWELS:
            continue                      # drop the second half of a geminate
        else:
            out.append(ch)
    return "".join(out)


# ── Declension tables ────────────────────────────────────────────────────────
# A cell is either
#   ("L", end)              accent-invariant: long stem + weak ending (all classes)
#   ("S", strong, weak)     accent-conditioned strong cell: mobile → short stem +
#                           strong ending; barytone → long stem + weak ending.
CELLS = [
    ("m", "Nom", "Sg"), ("m", "Gen", "Sg"), ("m", "Dat", "Sg"), ("m", "Akk", "Sg"),
    ("m", "Nom", "Pl"), ("m", "Gen", "Pl"), ("m", "Dat", "Pl"), ("m", "Akk", "Pl"),
    ("f", "Nom", "Sg"), ("f", "Gen", "Sg"), ("f", "Dat", "Sg"), ("f", "Akk", "Sg"),
    ("f", "Nom", "Pl"), ("f", "Gen", "Pl"), ("f", "Dat", "Pl"), ("f", "Akk", "Pl"),
    ("n", "Nom", "Sg"), ("n", "Gen", "Sg"), ("n", "Dat", "Sg"), ("n", "Akk", "Sg"),
    ("n", "Nom", "Pl"), ("n", "Gen", "Pl"), ("n", "Dat", "Pl"), ("n", "Akk", "Pl"),
]
GTAG = {"m": "+Masc", "f": "+Fem", "n": "+Neut"}

# Past-active (P68): single invariant stem (strip -uns), uniform weak endings.
PAST = {
    ("m", "Nom", "Sg"): "uns",  ("m", "Gen", "Sg"): "ušas",  ("m", "Dat", "Sg"): "ušasmu", ("m", "Akk", "Sg"): "usin",
    ("m", "Nom", "Pl"): "usis", ("m", "Gen", "Pl"): "usin",  ("m", "Dat", "Pl"): "usimans", ("m", "Akk", "Pl"): "usins",
    ("f", "Nom", "Sg"): "usi",  ("f", "Gen", "Sg"): "ušas",  ("f", "Dat", "Sg"): "ušai",   ("f", "Akk", "Sg"): "usin",
    ("f", "Nom", "Pl"): "ušas", ("f", "Gen", "Pl"): "usin",  ("f", "Dat", "Pl"): "usimans", ("f", "Akk", "Pl"): "usins",
    ("n", "Nom", "Sg"): "us",   ("n", "Gen", "Sg"): "ušas",  ("n", "Dat", "Sg"): "ušasmu", ("n", "Akk", "Sg"): "us",
    ("n", "Nom", "Pl"): "us",   ("n", "Gen", "Pl"): "usin",  ("n", "Dat", "Pl"): "usimans", ("n", "Akk", "Pl"): "usins",
}

# Present participle (P29). Strong cells: Dat-Pl (all genera) + Fem-Nom-Sg.
PRES = {
    ("m", "Nom", "Sg"): ("L", "s"),     ("m", "Gen", "Sg"): ("L", "is"),
    ("m", "Dat", "Sg"): ("L", "ismu"),  ("m", "Akk", "Sg"): ("L", "in"),
    ("m", "Nom", "Pl"): ("L", "ei"),    ("m", "Gen", "Pl"): ("L", "in"),
    ("m", "Dat", "Pl"): ("S", "immans", "imans"), ("m", "Akk", "Pl"): ("L", "ins"),
    ("f", "Nom", "Sg"): ("S", "ī", "i"), ("f", "Gen", "Sg"): ("L", "es"),
    ("f", "Dat", "Sg"): ("L", "ei"),    ("f", "Akk", "Sg"): ("L", "in"),
    ("f", "Nom", "Pl"): ("L", "es"),    ("f", "Gen", "Pl"): ("L", "in"),
    ("f", "Dat", "Pl"): ("S", "āmans", "amans"), ("f", "Akk", "Pl"): ("L", "ins"),
    ("n", "Nom", "Sg"): ("L", "i"),     ("n", "Gen", "Sg"): ("L", "is"),
    ("n", "Dat", "Sg"): ("L", "ismu"),  ("n", "Akk", "Sg"): ("L", "i"),
    ("n", "Nom", "Pl"): ("L", "ei"),    ("n", "Gen", "Pl"): ("L", "in"),
    ("n", "Dat", "Pl"): ("S", "immans", "imans"), ("n", "Akk", "Pl"): ("L", "ins"),
}

# Passive participle (P69, hard t-stem). Strong cells: Nom-Pl (m/n) + Dat-Pl + Fem-Nom-Sg.
PASS = {
    ("m", "Nom", "Sg"): ("L", "s"),     ("m", "Gen", "Sg"): ("L", "as"),
    ("m", "Dat", "Sg"): ("L", "asmu"),  ("m", "Akk", "Sg"): ("L", "an"),
    ("m", "Nom", "Pl"): ("S", "āi", "ai"), ("m", "Gen", "Pl"): ("L", "an"),
    ("m", "Dat", "Pl"): ("S", "ammans", "amans"), ("m", "Akk", "Pl"): ("L", "ans"),
    ("f", "Nom", "Sg"): ("S", "ā", "a"), ("f", "Gen", "Sg"): ("L", "as"),
    ("f", "Dat", "Sg"): ("L", "ai"),    ("f", "Akk", "Sg"): ("L", "an"),
    ("f", "Nom", "Pl"): ("L", "as"),    ("f", "Gen", "Pl"): ("L", "an"),
    ("f", "Dat", "Pl"): ("S", "āmans", "amans"), ("f", "Akk", "Pl"): ("L", "ans"),
    ("n", "Nom", "Sg"): ("L", "an"),    ("n", "Gen", "Sg"): ("L", "as"),
    ("n", "Dat", "Sg"): ("L", "asmu"),  ("n", "Akk", "Sg"): ("L", "an"),
    ("n", "Nom", "Pl"): ("S", "āi", "ai"), ("n", "Gen", "Pl"): ("L", "an"),
    ("n", "Dat", "Pl"): ("S", "ammans", "amans"), ("n", "Akk", "Pl"): ("L", "ans"),
}

TABLES = {"Pres": PRES, "Pass": PASS}


def lexc_esc(s: str) -> str:
    return s.replace(" ", "% ")


def cell_tag(g: str, case: str, num: str) -> str:
    return f"{GTAG[g]}+{num}+{case}"


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
    """Read 'mob'/'bar' from a prusaspira participle's strong cell, else None.
    Present → Fem-Nom-Sg (ī mobile / i barytone); passive → Masc-Nom-Pl (āi / ai)."""
    if cat == "present":
        v = _cell(part, "f", "Nominative", "singular")
        if v:
            return "mob" if v.endswith("ī") else "bar"
    elif cat == "passive":
        v = _cell(part, "m", "Nominative", "plural")
        if v:
            return "mob" if v.endswith("āi") else ("bar" if v.endswith("ai") else None)
    return None


def collect():
    """Union verbs keyed by lemma. Returns (forms, accent) where
    forms = {lemma: {cat: bareform}} and accent = {(lemma, cat): 'mob'/'bar'}
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
def emit_decl_lexicons() -> list[str]:
    L: list[str] = []

    def block(name, pairs):
        L.append(f"LEXICON {name}")
        for tag, end in pairs:
            L.append(f"  {tag}:{end}  # ;")
        L.append("")

    block("PtcpPast", [(cell_tag(*c), PAST[c]) for c in CELLS])
    for name, TAB in TABLES.items():
        # L-cells (weak endings, long stem — both classes).
        block(f"Ptcp{name}L",
              [(cell_tag(*c), TAB[c][1]) for c in CELLS if TAB[c][0] == "L"])
        # Strong cells, mobile half: strong endings on the de-accented stem.
        block(f"Ptcp{name}Strong",
              [(cell_tag(*c), TAB[c][1]) for c in CELLS if TAB[c][0] == "S"])
        # Strong cells, barytone half: weak endings on the long stem.
        block(f"Ptcp{name}Weak",
              [(cell_tag(*c), TAB[c][2]) for c in CELLS if TAB[c][0] == "S"])
    return L


def emit_stems(forms: dict, accent: dict) -> tuple[list[str], dict]:
    L = ["LEXICON PtcpStems"]
    stats = {"present": 0, "past": 0, "passive": 0, "passive_soft": 0,
             "mob": 0, "bar": 0, "default_mob": 0}

    def two_grade(cat, tag, name, lemma_esc, long_stem, lemma):
        cls = accent.get((lemma, cat))
        if cls is None:
            cls = "mob"            # twanksta-only default (96 % majority)
            stats["default_mob"] += 1
        stats[cls] += 1
        up = f"{lemma_esc}+V+Part+{tag}"
        L.append(f"  {up}:{lexc_esc(long_stem)}  Ptcp{name}L ;")
        if cls == "mob":
            short = deaccent_stem(long_stem)
            L.append(f"  {up}:{lexc_esc(short)}  Ptcp{name}Strong ;")
        else:
            L.append(f"  {up}:{lexc_esc(long_stem)}  Ptcp{name}Weak ;")

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
    out = ["! Participle declension — generated by scripts/gen_participles.py",
           "! Source: data/external/{twanksta,prusaspira}_entries.json",
           "! Accent shift (Rinkevičius 2009): mobile stems de-accent (shorten)",
           "! under a strong ending; barytone stems keep stress and take weak",
           "! endings. Class read per lemma from prusaspira full_declension;",
           "! twanksta-only verbs default to mobile. See docs/FST_PARTICIPLES.md.",
           "",
           "LEXICON VParticiples",
           "  PtcpStems ;",
           ""]
    stem_lines, stats = emit_stems(forms, accent)
    out += stem_lines
    out += emit_decl_lexicons()
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}  ({len(forms)} verbs)")
    print(f"  present={stats['present']} past={stats['past']} "
          f"passive(hard)={stats['passive']} passive(soft)={stats['passive_soft']}")
    print(f"  accent: mob={stats['mob']} bar={stats['bar']} "
          f"(default-mob for twanksta-only={stats['default_mob']})")


if __name__ == "__main__":
    main()
