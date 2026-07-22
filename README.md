# Prussian Foma FST

Vollform-Lookup-FST fürs Neupreußische, generiert aus
`twanksta_entries.json`.  Jede flektierte Form ist ein eigener
lexc-Eintrag (Lookup-Tabelle, keine Stamm-Endung-Zerlegung).

## Daten

`twanksta_entries.json` aus dem
[`strfry/prussian-corpus`](https://github.com/strfry/prussian-corpus)-Release:

```bash
RELEASE="https://github.com/strfry/prussian-corpus/releases/download/v2026-07-04"
curl -fsSL "$RELEASE/twanksta_entries.json" -o data/external/twanksta_entries.json
```

## Bauen

Der FST-Build läuft über das python-`hfst`-Modul (Projekt-Abhängigkeit,
`pip install hfst`), nicht über eine separat installierte hfst-Toolchain;
Lookup zur Laufzeit über `pyhfst`.

```bash
make gen   # .lexc-Dateien aus JSON generieren
make       # python-hfst: lexc → build/base.fst → *.hfstol
```

## Struktur

```
.
├── Makefile                  # gen → python-hfst-Build
├── src/prussian_fst/
│   ├── __init__.py
│   ├── gen_lexc.py           # Konsolidierter Generator aus twanksta_entries.json
│   ├── build_fst.py          # FST-Build über python-hfst (ersetzt hfst-CLI)
│   ├── export_valence.py     # Rektion/Valenz-Export (desc-Feld) → build/valence.json
│   ├── linker.py             # desc-Ref-Resolver → build/links.json
│   ├── cg3_pipeline.py       # CG3-Disambiguator-Pipeline
│   ├── export_conllu.py      # CoNLL-U-Export
│   └── delta_review.py       # Korpus-Dict-Abgleich (Handoff für Glabbis)
├── lexc/
│   ├── symbols.lexc          # handgepflegt
│   ├── root.lexc             # handgepflegt
│   ├── function_words.lexc   # handgepflegt
│   ├── pronouns.lexc         # handgepflegt
│   ├── proper_nouns.lexc     # handgepflegt
│   ├── nouns.lexc            # generiert
│   ├── adjectives.lexc       # generiert
│   ├── numerals.lexc         # generiert
│   ├── verbs.lexc            # generiert
│   ├── adverbs.lexc          # generiert
│   ├── prepositions.lexc     # generiert
│   ├── conjunctions.lexc     # generiert
│   ├── particles.lexc        # generiert
│   ├── interjections.lexc    # generiert
│   └── proper_nouns_auto.lexc # generiert
├── cg3/
│   ├── disambiguator.cg3     # Hauptgrammatik
│   ├── dependency.cg3        # Dependenz-Schicht
│   ├── validator.cg3         # Validierungs-Regeln
│   └── generated-sets.cg3    # CG3-Sets (generiert aus valence.json)
├── norm/                     # Normalisierungs-Stufen (pro Phänomen)
│   ├── macron.regex          # Makron-Verlust (ā ē ī ō ū → a e i o u)
│   ├── degem.regex           # Degemination (nn → n …)
│   └── ortho.regex           # w-Prothese, i-Synkope, twei↔tun …
└── build/                    # Kompilierte Artefakte
    ├── base.hfstol           # Lookup-FST (surface → analysis), strikt
    ├── macron.hfstol         # + Makron-Normalisierung
    ├── lenient.hfstol        # + Degemination/Ortho (Gesamt-Fallback)
    ├── valence.json          # Rektion/Valenz-Export (generiert)
    └── cg3/
        ├── disambiguator.bin
        ├── dependency.bin
        └── validator.bin
```

Alle Einträge sind Vollformen (`lemma+POS+Tag:form # ;`), nach
Wortart in separate Dateien gruppiert (Klassifikation anhand
`desc`-Feld und Paradigmen-Nummer im Dictionary).

## Tags

Neben POS/Kasus/Numerus/Genus/Tempus/Person:

- `+Ind` — Indikativ, explizit an allen finiten Präsens-/Präteritumformen
  (`+Opt`/`+Imp`/`+Subj` wie gehabt)
- `+Cmp` / `+Sup` — Komparativ/Superlativ; volle Adjektivparadigmen aus
  `forms.comparative`/`forms.superlative`, Steigerung abgeleiteter
  Adverbien aus `forms.adverb` (Lemma = Positiv-Adverb, z.B.
  `labbai+Adv+Cmp:walnai`)
- `+GovAkk` / `+GovDat` — Kasusrektion der Präpositionen aus dem
  Twanksta-`desc`-Feld (`prp acc` / `prp dat`); Doppelrektion ergibt
  zwei Einträge (`ēn`, `ezze`, `pa`, `pō`)

`build/valence.json` (aus `src/prussian_fst/export_valence.py`) enthält die
Präpositionsrektion als JSON sowie Best-Effort-Verbvalenz
(nur die ~140 im Wörterbuch annotierten Verben; unpersönliche
Verben sind in Twanksta nicht kodiert).

## FSG/CG-Check (CoNLL-U mit Regel-Provenienz)

Der Einzeltext-Modus der Pipeline liefert das Antwortformat für das
`validate_prussian`-MCP-Tool (`prussian-mcp`): dreiwertige Prüfung
(--validate), optional CoNLL-U (ein Block pro Satz).

```bash
echo "Labban dēinan!" | python3 src/prussian_fst/cg3_pipeline.py --text - --conllu --trace
```

Mit `--trace` wandert Regel-Provenienz nach MISC:

- `Rule=<name,…>` — benannte Grammatikregeln (`KEYWORD:name` in
  `disambiguator.cg3`), die den Cohort laut `vislcg3 --trace` berührt
  haben (auch auf entfernten Lesarten). Eine Regel sichtbar machen =
  ihr in der Grammatik einen `:namen` geben — kein Zwillingsregel-Patch
  nötig. Benannt sind bisher u. a. `agr-head`, `ka-complementizer`,
  `gen-negationis`, `steisan-periphrase`, `r6-di-impersonal`,
  `r7-pred-participle`, `r8-greeting-adj`.
- `AgrParent=<id>` — echtes Kongruenz-Ziel der `agr-head`-Regeln
  (`SETPARENT … BARRIER AgrBarrier`), ermittelt über einen Zweitlauf,
  der vor der Baumschicht (`SECTION dep-tree`) abbricht — bevor
  SECTION 8 den Parent ggf. überschreibt (Koordination).
