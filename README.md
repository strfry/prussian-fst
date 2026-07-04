# Prussian Foma FST

Vollform-Lookup-FST fürs Neupreußische, generiert aus
`twanksta_entries.json`.  Jede flektierte Form ist ein eigener
lexc-Eintrag (Lookup-Tabelle, keine Stamm-Endung-Zerlegung).

## Daten

`twanksta_entries.json` aus dem
[`strfry/prussian-corpus`](https://github.com/strfry/prussian-corpus)-Release:

```bash
RELEASE="https://github.com/strfry/prussian-corpus/releases/download/v2026-06-21"
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
└── build/
    └── base.fst              # kompilierter FST
```

Alle Einträge sind Vollformen (`lemma+POS+Tag:form # ;`), nach
Wortart in separate Dateien gruppiert (Klassifikation anhand
`desc`-Feld und Paradigmen-Nummer im Dictionary).
