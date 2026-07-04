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

```bash
cd fst && make gen   # .lexc-Dateien aus JSON generieren
cd fst && make       # hfst-lexc → build/base.fst
```

## Struktur

```
fst/
├── Makefile                  # gen → hfst-lexc
├── scripts/
│   ├── gen_lexc.py           # Konsolidierter Generator aus twanksta_entries.json
│   ├── export_valence.py     # Rektion/Valenz-Export (desc-Feld) → valence.json
│   └── delta_review.py       # Korpus-Dict-Abgleich (Handoff für Glabbis)
├── symbols.lexc
├── root.lexc
├── nouns.lexc                # generiert
├── adjectives.lexc           # generiert
├── pronouns.lexc             # generiert
├── numerals.lexc             # generiert
├── verbs.lexc                # generiert (+ Partizip-Routing)
├── verb_participles.lexc     # handgeschriebene Partizip-Paradigmen
├── adverbs.lexc              # generiert
├── prepositions.lexc         # generiert
├── conjunctions.lexc         # generiert
├── particles.lexc            # generiert
├── interjections.lexc        # generiert
├── norm.regex                # Normalisierung (lenient)
├── valence.json              # Rektion/Valenz-Export (generiert)
└── build/
    └── base.fst              # kompilierter FST
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

`valence.json` (aus `scripts/export_valence.py`) enthält die
Präpositionsrektion als JSON sowie Best-Effort-Verbvalenz
(nur die ~140 im Wörterbuch annotierten Verben; unpersönliche
Verben sind in Twanksta nicht kodiert).
