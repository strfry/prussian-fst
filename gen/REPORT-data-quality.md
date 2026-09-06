# Data-quality report — Twanksta noun (and participle) inflection

**To:** maintainer of `twanksta_entries.json`
**From:** generative FST prototype (`fst/gen/`), 2026-09-06
**Basis:** non-circular comparison of the stored inflection tables against a
hand-written generative FST (stem + paradigm ending + one accent/morphophonology
stage).

## Method

For every noun the oblique stem is derived mechanically from the Gen.Sg. (Gen.Sg.
minus the class ending) and expanded back into all eight case forms via
hand-written ending sets + one accent rule. The endings and rules are **not**
learned from the data; they are a linguistic hypothesis per Twanksta paradigm
number. The comparison is therefore a genuine coverage test, not
self-consistency. Reproducible with `uv run python gen/data_report.py` (nouns) and
`uv run python gen/coverage_adj.py` (participles).

Six noun stem-families are modelled, covering **98.6 % of all noun lemmas**
(5911 / 5993 in paradigms 32–70); the remaining ~25 lemmas sit in tiny scattered
paradigms (47, 49, 62, 64, 65, …), 1–6 entries each. Par.68/69 are **not nouns**
but participles (active `-uns`, passive `-ts`) with adjectival declension (Dat.Sg.
`-jasmu` / `-asmu`); they are modelled on the adjective side (`gen/adj.lexc`,
`gen/coverage_adj.py`: 98.8 %, active 100 %) and not counted below.

| Family | Paradigms | Forms | Coverage |
|---|---|---|---|
| i-stems | 52/53/54/56/57/58/60 | 8432 | 99.4 % |
| a-stems | 32/35/36 | 16984 | 99.7 % |
| u-stems | 42/43/44 | 480 | 97.9 % |
| jo-stems | 37/38/39/40/41 | 5760 | 99.7 % |
| ā/jā/ī-stems (fem) | 45/46/50/51 | 11992 | 99.8 % |
| n-stems | 61/63 | 168 | 100 % |
| **total** | | **43816** | **99.64 %** |

The 157 remaining mismatches split into **genuine data errors** (Part A) and
**systematic morphophonology** that the prototype does not (yet) reproduce
(Part B — not errors, listed for awareness / as consistency questions).

---

## A. Concrete data errors (correction recommended)

### A1. Fully invariant inflection tables (36 entries)

All eight cases == headword — the declension table was apparently never filled
(it just repeats the lemma). A noun that declines cannot look like this. By
paradigm:

- **p52** (7): `Dānija` `animācija` `federācija` `galiōnan` `stabenīkista` `ēdawa` `wakcinacīja`
- **p49** (6): `lāukiskan` `priwātiskan` `pusiwadūniskan` `trinewīngiskan` `wargaprātiskan` `āustewingiskan`
- **p40** (4): `geōgrafs` `māgiks` `slidenīks` `šlūzims`
- **p45** (4): `plastilīns` `wītwagā` `zentlawingiskan` `zēisnā`
- **p35** (3): `Sēināi` `saldiskāi` `sinōnimas`
- **p44** (2): `Marokko` `sekkan` · **p32** (2): `Nōrwegija` `kukurūza` · **p46** (2): `gazzasgara` `prasijjā`
- one each: `brūnagalwa`[48] `izmāitint`[69] `knāistis`[68] `kāuplis`[53] `nunni`[42] `swasri`[51]

Some loanwords (`Marokko`, `Dānija`) may be intentionally indeclinable — but then
the paradigm assignment is misleading. The natively-shaped cases (`geōgrafs`,
`māgiks`, `slidenīks`, `sinōnimas`, `kāuplis`) are almost certainly just unfilled.

### A2. Part-of-speech / gender misclassification

- **`izmāitint`** [p69] — gloss *"lost"*, empty gender, ends in `-int`: this is a
  **verb / participle**, not a noun (and has a fully invariant table, see A1).
- **`plastilīns`** [p45, **fem**] — masculine in shape (`-īns`); p45 is the
  feminine ā-family. Gender/paradigm do not match the form.

### A3. Encoding damage

- **`māršs`** [p32] — the oblique cells contain a **U+FFFD REPLACEMENT
  CHARACTER**: `Gen.Sg. 'marš<FFFD>as'`, `Nom.Pl. 'marš<FFFD>ai'` … The Nom.Sg.
  `māršs` is intact. Expected `māršas / māršai / …`. (The only such case in the
  noun data.)

### A4. Single-cell errors

- **`kōmbus`** [p43, u-stem] — Gen.Pl. is stored as `kōmbus`, should be `kōmbun`
  (apparently copied from the Nom.Sg.). All other cells correct.
- **`fōrum`** [p35, neut] — Latin loan: Nom.Sg. `-um` instead of `-an`, and Gen.Pl.
  stored as `fōrum` (= Nom.Sg.) instead of `fōran`. Mixed paradigm (Latin Nom.Sg.,
  native a-stem oblique).

---

## B. Systematic morphophonology (not errors)

These cases are linguistically regular; the prototype does not (fully) reproduce
them yet. Mostly relevant as **consistency questions** for data curation.

### B1. Nom.Sg. `-s` vs `-is` / `-us` (~52 cases) — lexical

In the "heavy" Nom.Sg. classes (i-/u-stems) the Nom.Sg. appears either syncopated
(`-s`) or with the retained theme vowel (`-is` / `-us`). The split is **not**
derivable from the stem: polysyllabic stems take `-s` almost throughout, but among
monosyllables both occur, sometimes after the same final cluster (`grūsts` vs
`glāstis`, both `-st`). `-is` is retained in genuine i-stems (`anglis`, `saknis`,
`lūsis`) and in loanwords (`Antarktis`, `Arktis`), syncopated in `nakts`, `dānts`,
`ants`. → best treated as a lexical feature, not a rule. **Not an error**, but
worth checking whether the `-s`/`-is` assignment is intended everywhere.

### B2. Extent of unstressing reduction in mobile slots — inconsistent

In the accent-shifted slots (Nom.Pl. / Dat.Pl.) the stem loses its heavy feature.
The prototype reduces **all** heavy features there (the data-driven majority
choice). But the data are not uniform in **how much** reduces:

- Polysyllabic compounds regularly reduce **all** macrons:
  `stāminadeīkt-` → `staminadeiktāi`, `drāugiprōfesinisk-` → `draugiprofesiniskāi`.
- A minority (proper names, numerals) keep the **pretonic** length:
  `Instrāpil-` → `Instrāpilimmans` (pretonic `ā` stays), likewise `Mētapils`,
  `Rāistanpils`, `astōnadesīmt-`.

Same morphological slot, opposite behaviour. Either the pretonic length in the
`-pils` names is a deliberate (proper-name) exception, or an inconsistency in the
stress marking. **Please check** which is the intended pattern.

### B3. Retention of individual geminates in mobile slots

`aupallē` keeps `ll` in the heavy slot (`aupallīmans`) where structurally identical
stems reduce (`nagg-` → `nagīmans`). Likewise the numeral compounds `trillunks`,
`ketturjalunks` (pretonic geminate stays). Stress-dependent, as in B2.

### B4. Grave / acute accent dropped in mobile slots

`ètwartan` → `etwartāi`, `èstiskan` → `estiskāi`, `ensàkninsnā` → `ensakninsnā`,
`izpiĺninsnā` → `izpilninsnā`: the grave (`à` / `è`) or acute `ĺ` marks the stem
stress and disappears in the accent-shifted slot — regular, but the prototype's
accent rule so far only shortens macrons and simplifies geminates.

---

## Summary

About **99.6 %** of the forms (43816) across the six noun stem-families are exactly
reproducible generatively from stem + paradigm + one accent rule; another 98.8 % on
the participle side. The remaining mismatches are mostly regular
lexicon/morphophonology (Part B). The **genuine errors** are: ~36 unfilled
inflection tables (A1), one part-of-speech misclassification (`izmāitint`, A2), one
encoding fault (`māršs`, A3) and isolated cell errors (`kōmbus`, `fōrum`, A4).
