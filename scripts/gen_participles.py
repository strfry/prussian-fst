#!/usr/bin/env python3
"""Generate fst/verb_participles.lexc from the prussian-corpus entry dumps.

Source: data/external/{twanksta,prusaspira}_entries.json (GitHub release of
strfry/prussian-corpus). Each verb carries up to three participles, listed in a
fixed order: [present-active, past-active, passive].

The three participles decline like adjectives (present ≈ P29, past-active ≈ P68,
passive ≈ P69). The crux is gemination / vowel length: the FST concatenates
literally and has no phonology layer, so each participle needs its OWN correctly
graded stem rather than one stem derived from the verb.

  īmtun:  present imānts (im-)   past immuns (imm-)   passive īmts (īm-)

Two stem grades appear in present & passive declension, conditioned by stress:
  dānts (long, most cells)  vs  dantimmans / dantī (short, dat-pl + fem-nom-sg).
We emit BOTH grades as separate stem entries routed to disjoint cell-lexicons:
the long stem feeds the L-cells, the short stem (long vowel shortened) feeds the
stress-bearing S-cells, where the suffix takes its heavy (geminated) shape.
The past-active participle has a single invariant stem.

Run from the repo root:  python scripts/gen_participles.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTERNAL = ROOT / "data" / "external"
OUT = ROOT / "fst" / "verb_participles.lexc"

SHORTEN = {"ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u"}


def shorten_last_long(stem: str) -> str:
    """Shorten the last long vowel (stress retraction to the ending). Returns the
    stem unchanged if it has no long vowel (then no grade alternation applies)."""
    for i in range(len(stem) - 1, -1, -1):
        if stem[i] in SHORTEN:
            return stem[:i] + SHORTEN[stem[i]] + stem[i + 1:]
    return stem


# ── Declension tables ────────────────────────────────────────────────────────
# Cell order for emission (stable, readable).
CELLS = [
    ("m", "Nom", "Sg"), ("m", "Gen", "Sg"), ("m", "Dat", "Sg"), ("m", "Akk", "Sg"),
    ("m", "Nom", "Pl"), ("m", "Gen", "Pl"), ("m", "Dat", "Pl"), ("m", "Akk", "Pl"),
    ("f", "Nom", "Sg"), ("f", "Gen", "Sg"), ("f", "Dat", "Sg"), ("f", "Akk", "Sg"),
    ("f", "Nom", "Pl"), ("f", "Gen", "Pl"), ("f", "Dat", "Pl"), ("f", "Akk", "Pl"),
    ("n", "Nom", "Sg"), ("n", "Gen", "Sg"), ("n", "Dat", "Sg"), ("n", "Akk", "Sg"),
    ("n", "Nom", "Pl"), ("n", "Gen", "Pl"), ("n", "Dat", "Pl"), ("n", "Akk", "Pl"),
]
GTAG = {"m": "+Masc", "f": "+Fem", "n": "+Neut"}

# Past-active participle (P68): single invariant stem (strip -uns), uniform endings.
PAST = {
    ("m", "Nom", "Sg"): "uns",  ("m", "Gen", "Sg"): "ušas",  ("m", "Dat", "Sg"): "ušasmu", ("m", "Akk", "Sg"): "usin",
    ("m", "Nom", "Pl"): "usis", ("m", "Gen", "Pl"): "usin",  ("m", "Dat", "Pl"): "usimans", ("m", "Akk", "Pl"): "usins",
    ("f", "Nom", "Sg"): "usi",  ("f", "Gen", "Sg"): "ušas",  ("f", "Dat", "Sg"): "ušai",   ("f", "Akk", "Sg"): "usin",
    ("f", "Nom", "Pl"): "ušas", ("f", "Gen", "Pl"): "usin",  ("f", "Dat", "Pl"): "usimans", ("f", "Akk", "Pl"): "usins",
    ("n", "Nom", "Sg"): "us",   ("n", "Gen", "Sg"): "ušas",  ("n", "Dat", "Sg"): "ušasmu", ("n", "Akk", "Sg"): "us",
    ("n", "Nom", "Pl"): "us",   ("n", "Gen", "Pl"): "usin",  ("n", "Dat", "Pl"): "usimans", ("n", "Akk", "Pl"): "usins",
}

# Present participle (P29) and passive (P69, hard t-stem) decline with two
# stress-graded stems. A cell is either:
#   ("L", end)             — accent-invariant: long stem + a fixed ending.
#   ("S", heavy, light)    — accent-conditioned (the ~3 cells per word the data
#                            wavers on): stress may sit on stem or ending. The
#                            mora is conserved, so we emit BOTH realizations —
#                            short stem + heavy/geminated ending, and long stem +
#                            light ending — letting the analyser accept either
#                            (the choice is lexical stress, deferred to
#                            stress.twolc). Generation then yields both variants.
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


def lexc_esc(s: str) -> str:
    """Escape a literal space (reflexive clitic) for lexc."""
    return s.replace(" ", "% ")


def cell_tag(g: str, case: str, num: str) -> str:
    return f"{GTAG[g]}+{num}+{case}"


# ── Participle classification ────────────────────────────────────────────────
def classify(forms: list[str]):
    """Map a verb's participle forms to {present,past,passive: bare_form}.

    Order in the source is [present, past, passive]; the past-active form ends in
    -uns. We assign past = the -uns slot, then fill present/passive from the
    remaining slots in their original order. Placeholder slots that merely repeat
    the infinitive (or carry a space, i.e. multiword) are dropped.
    """
    out = {}
    rest = []
    for f in forms:
        bare = f[:-3] if f.endswith(" si") else f
        if " " in bare:        # multiword participle — not modelled
            continue
        if bare.endswith("uns"):
            out.setdefault("past", bare)
        else:
            rest.append(bare)
    # present then passive, by source order, requiring a final -s
    pp = [b for b in rest if b.endswith("s")]
    if len(pp) >= 1:
        out["present"] = pp[0]
    if len(pp) >= 2:
        out["passive"] = pp[1]
    return out


def collect():
    """Union verbs from both dumps keyed by lemma; return {lemma: {cat: bareform}}."""
    verbs: dict[str, dict] = {}
    for name in ("twanksta_entries.json", "prusaspira_entries.json"):
        path = EXTERNAL / name
        if not path.exists():
            continue
        for e in json.loads(path.read_text(encoding="utf-8")):
            parts = e.get("forms", {}).get("participles")
            if not parts:
                continue
            word = e["word"]
            core = word[:-3] if word.endswith(" si") else word
            if " " in core:      # multiword lemma — skip whole verb
                continue
            cats = classify([p["form"] for p in parts])
            if not cats:
                continue
            verbs.setdefault(word, {}).update(cats)
    return verbs


# ── Emission ─────────────────────────────────────────────────────────────────
def emit_decl_lexicons() -> list[str]:
    """The shared continuation lexicons (cell endings, relative to the stem)."""
    L: list[str] = []

    def block(name, pairs):
        L.append(f"LEXICON {name}")
        for tag, end in pairs:
            L.append(f"  {tag}:{end}  # ;")
        L.append("")

    # Past-active: one lexicon, all 24 cells.
    block("PtcpPast", [(cell_tag(*c), PAST[c]) for c in CELLS])

    # Present / passive: L-cells (accent-invariant, long stem) + the two halves of
    # the accent-conditioned cells: heavy ending (on the short stem) and light
    # ending (on the long stem).
    for name, TAB in (("Pres", PRES), ("Pass", PASS)):
        block(f"Ptcp{name}L",
              [(cell_tag(*c), TAB[c][1]) for c in CELLS if TAB[c][0] == "L"])
        block(f"Ptcp{name}Heavy",
              [(cell_tag(*c), TAB[c][1]) for c in CELLS if TAB[c][0] == "S"])
        block(f"Ptcp{name}Light",
              [(cell_tag(*c), TAB[c][2]) for c in CELLS if TAB[c][0] == "S"])
    return L


def emit_stems(verbs: dict) -> tuple[list[str], dict]:
    L = ["LEXICON PtcpStems"]
    stats = {"present": 0, "past": 0, "passive": 0, "passive_soft": 0}
    for lemma in sorted(verbs):
        cats = verbs[lemma]
        lem = lexc_esc(lemma)

        def two_grade(tag: str, long_stem: str, name: str):
            """Emit the three stem entries for a two-grade (present/passive) ptcp:
            long stem → L-cells and the light half; short stem → heavy half."""
            short_stem = shorten_last_long(long_stem)
            up = f"{lem}+V+Part+{tag}"
            L.append(f"  {up}:{lexc_esc(long_stem)}  Ptcp{name}L ;")
            L.append(f"  {up}:{lexc_esc(long_stem)}  Ptcp{name}Light ;")
            L.append(f"  {up}:{lexc_esc(short_stem)}  Ptcp{name}Heavy ;")

        if "present" in cats:
            two_grade("Pres", cats["present"][:-1], "Pres")   # strip masc-nom-sg -s
            stats["present"] += 1

        if "past" in cats:
            stem = cats["past"][:-3]               # strip -uns (invariant stem)
            L.append(f"  {lem}+V+Part+Pret:{lexc_esc(stem)}  PtcpPast ;")
            stats["past"] += 1

        if "passive" in cats:
            form = cats["passive"]
            if form.endswith("ts"):                # hard t-stem passive
                two_grade("Pass", form[:-1], "Pass")
                stats["passive"] += 1
            else:
                # soft/vowel-stem passive (≈6%, distinct paradigm): citation only.
                L.append(f"  {lem}+V+Part+Pass+Masc+Sg+Nom:{lexc_esc(form)}  # ;")
                stats["passive_soft"] += 1
    L.append("")
    return L, stats


def main():
    verbs = collect()
    out = ["! Participle declension — generated by scripts/gen_participles.py",
           "! Source: data/external/{twanksta,prusaspira}_entries.json",
           "! Present/passive use two stress-graded stems (long + shortened);",
           "! past-active uses a single invariant stem.",
           "",
           "LEXICON VParticiples",
           "  PtcpStems ;",
           ""]
    stem_lines, stats = emit_stems(verbs)
    out += stem_lines
    out += emit_decl_lexicons()
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}  ({len(verbs)} verbs)")
    print(f"  present={stats['present']} past={stats['past']} "
          f"passive(hard)={stats['passive']} passive(soft,citation)={stats['passive_soft']}")


if __name__ == "__main__":
    main()
