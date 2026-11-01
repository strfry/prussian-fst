# Prussian FST

Morphological analyzer and generator for New Prussian (HFST, Giella tags).

Open-class morphology (nouns, adjectives, verbs, numerals) is **generative**: the
paradigm table `gen/paradigms.json` derives every form from the lemma, the Twanksta
paradigm number and a few **principal forms**:

| pos | principal forms (besides the lemma) |
|---|---|
| noun | sg.gen, pl.dat |
| adj | comp.msc.sg.nom, msc.sg.gen |
| verb | prs.sp3, prt.sp3, subj.sp3, part.prs.act.msc.sg.nom, part.prf.act.msc.sg.nom, part.prf.pss.msc.sg.nom |

Every other cell comes from one of them by a suffix rule (optionally with the
stressless stem: macrons shortened, geminates simplified). A verb cell always comes
from the principal form of its group (prs/imprt ← prs.sp3, prt ← prt.sp3,
subj/opt ← subj.sp3, each participle ← its msc.sg.nom), so a corrected principal form
carries over; for nouns and adjectives the table learns the source per paradigm. The lexemes come from the
**lean NVH**, the word list that keeps only what the rules do not produce: wrong
principal forms and override cells, both as plain `inflectedForm`. Closed classes
(function words, pronouns) are hand-written lexc.

## Data

All dictionary data lives in the sibling
[`strfry/prussian-corpus`](https://github.com/strfry/prussian-corpus) checkout; the
fst repo has no copy:

| file (`../corpus/parsed/`) | role |
|---|---|
| `twanksta_dmlex.nvh` | **lean NVH**: build input (lexemes, kept cells, invariables) |
| `twanksta.nvh` | fat NVH: every Twanksta cell |
| `twanksta_entries.json` | raw export; still read by `export_valence.py` |

The compressor (`gen/compress_forms.py`) turns a full NVH into a lean one, exactly:

    generate(lemma, cells) ⊕ cells == full cells     (⊕ = a cell replaces its slot)

## Build

The build uses the python `hfst` module (a project dependency), no hfst CLI;
runtime lookup uses `pyhfst`.

```bash
uv sync
make         # lean NVH + paradigm table + lexc/ -> build/analyzer.lexc -> base.fst -> *.hfstol
```

More targets:

```bash
make paradigms         # re-derive gen/paradigms.json from the lean NVH
make analyzer-parity   # surface coverage against the frozen Twanksta gold
make cg3-check         # generate CG3 sets + compile the grammars
make disambiguate      # full-corpus run with ambiguity statistics
make conllu            # CoNLL-U silver export -> data/prussian_silver.conllu
make links             # ↑ reference resolver (form -> base form) -> build/links.json
make validate-corpus   # validator over the corpora (false-alarm regression)
uv run pytest
```

Generator and compressor:

```bash
uv run python gen/generator.py generate noun 53 zemē
uv run python gen/generator.py generate verb 136 kalbītwei --cell prt.sp3=kalbēja
uv run python gen/generator.py show verb 136          # rules of one paradigm
uv run python gen/compress_forms.py --dry-run
uv run python gen/compress_forms.py --out build/lean.nvh --verify-roundtrip
```

## Lookup

With the (optional) hfst CLI:

```bash
echo "dumslis" | hfst-lookup build/base.hfstol                    # analysis
echo "dumslē+N+Fem+Sg+Gen" | hfst-lookup build/base.gen.hfstol    # generation
```

In Python: `prussian_fst.fst_lookup.flookup_batch` / `glookup_batch`, or the
high-level API `prussian_fst.api` (`analyze`, `validate`, `conllu`).
`PRUSSIAN_FST=<path>` selects another analyzer for the CG3 pipeline.

## Layout

```
.
├── Makefile
├── gen/                      # generative core
│   ├── paradigms.json        # paradigm table: slot -> source principal form + rules
│   ├── generator.py          # lemma + paradigm (+ principal forms) -> slots
│   ├── derive_paradigms.py   # lean (or full) NVH -> paradigms.json
│   ├── compress_forms.py     # compressor: full NVH -> lean NVH
│   └── build_analyzer.py     # lean NVH + generator + lexc/ -> build/analyzer.lexc
├── lexc/                     # hand-written
│   ├── root.lexc, symbols.lexc          # Root + multichar tag inventory
│   ├── function_words.lexc
│   └── pronouns.lexc
├── src/prussian_fst/
│   ├── build_fst.py          # FST build via python-hfst (replaces the hfst CLI)
│   ├── fst_lookup.py         # pyhfst lookup (analysis/generation)
│   ├── api.py                # in-process API for prussian-mcp
│   ├── cg3_pipeline.py       # CG3 disambiguator/validator pipeline
│   ├── export_conllu.py      # CoNLL-U export
│   ├── export_valence.py     # government/valency -> build/valence.json
│   ├── gen_cg3_sets.py       # valence.json -> cg3/generated-sets.cg3
│   └── linker.py             # ↑ reference resolver (form -> base form) -> build/links.json
├── cg3/
│   ├── disambiguator.cg3     # main grammar
│   ├── dependency.cg3        # dependency layer
│   ├── validator.cg3         # validation rules
│   └── generated-sets.cg3    # generated
├── norm/                     # normalisation stages (one per phenomenon)
│   ├── macron.regex          # macron loss (ā ē ī ō ū -> a e i o u)
│   ├── degem.regex           # degemination (nn -> n …)
│   └── ortho.regex           # w-prothesis, i-syncope, twei↔tun …
├── tests/                    # pytest; gold/ = frozen Twanksta surfaces
└── build/
    ├── analyzer.lexc         # baked merged lexc (source of base.fst)
    ├── base.hfstol           # analyzer (surface -> analysis), strict
    ├── base.gen.hfstol       # generator (analysis -> surface)
    ├── macron.hfstol         # + macron normalisation
    ├── lenient.hfstol        # + degemination/ortho (overall fallback)
    └── cg3/*.bin
```

## Tags

Giella inventory (`lexc/symbols.lexc`), order `lemma+POS[+Sub]+…`, e.g.:

```
dumslē+N+Fem+Sg+Gen:dumslis
Adwēnts+N+Prop+Msc+Sg+Nom:Adwēnts
begalbis+A+Comp+Msc+Sg+Nom:begalbjaisis
begalbis+Adv+Comp:begalbjais
perwaidīntun+V+Ind+Prs+Sg1+Refl:perwaidinnas
```

- POS: `+N` (`+Prop` = capitalised noun), `+A`, `+Adv`, `+V`, `+Num`
  (`+Card`/`+Ord`), `+Pron`, `+Pr`, `+Po`, `+CC`/`+CS`, `+Pcle`, `+Interj`
- nouns carry their gender (`+Msc`/`+Fem`/`+Neu`) as an entry fact
- verbs: `+Ind`/`+Subj`/`+Opt`/`+Imprt`, `+Prs`/`+Prt`, persons
  `+Sg1 +Sg2 +SP3 +Pl1 +Pl2`; participles `+PrsPrc`/`+PrfPrc` × `+Act`/`+Pss`
- comparison `+Comp`/`+Superl`, also on derived adverbs

Preposition government is not in the FST but a lemma list in the CG layer
(`build/valence.json` -> `cg3/generated-sets.cg3`). `valence.json` also holds
best-effort verb valency (only the verbs annotated in the dictionary).

## FSG/CG check (CoNLL-U with rule provenance)

The single-text mode of the pipeline produces the answer format of the
`validate_prussian` MCP tool (`prussian-mcp`): three-valued check (--validate),
optionally CoNLL-U (one block per sentence).

```bash
echo "Labban dēinan!" | python3 src/prussian_fst/cg3_pipeline.py --text - --conllu --trace
```

With `--trace`, rule provenance goes to MISC:

- `Rule=<name,…>`: named grammar rules (`KEYWORD:name` in `disambiguator.cg3`) that
  touched the cohort according to `vislcg3 --trace` (also on removed readings). To
  make a rule visible, give it a `:name` in the grammar; no twin-rule patch needed.
  Named so far, among others: `agr-head`, `ka-complementizer`, `gen-negationis`,
  `steisan-periphrase`, `r6-di-impersonal`, `r7-pred-participle`, `r8-greeting-adj`.
- `AgrParent=<id>`: the real agreement target of the `agr-head` rules
  (`SETPARENT … BARRIER AgrBarrier`), found by a second run that stops before the
  tree layer (`SECTION dep-tree`), before SECTION 8 may overwrite the parent
  (coordination).
