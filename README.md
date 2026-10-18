# Prussian FST

Morphologischer Analyzer und Generator fürs Neupreußische (HFST, Giella-Tags).

Die Open-Class-Morphologie (Nomen, Adjektive, Verben, Numeralia) ist
**generativ**: handgeschriebene Endungstabellen (`gen/*.lexc`) plus
Akzentregel (`gen/accent.regex`) erzeugen aus Lemma + Twanksta-Paradigmennummer
die Formen.  Die Lexeme kommen aus der **lean NVH** — der Wortliste, die nur
noch das enthält, was die Grammatik nicht selbst erzeugt (gelieferte Stämme,
Override-Zellen).  Geschlossene Klassen (Funktionswörter, Pronomen) bleiben
handgepflegte lexc.

## Daten

Alle Dictionary-Daten liegen im
[`strfry/prussian-corpus`](https://github.com/strfry/prussian-corpus)-Checkout
nebenan — keine Kopie im fst-Repo:

| Datei (`../corpus/parsed/`) | Rolle |
|---|---|
| `twanksta_dmlex.nvh` | **lean NVH** — Build-Eingabe (Lexeme, `stemOverrides`, Override-Zellen, Invariable) |
| `twanksta.nvh` | fette NVH — jede Twanksta-Zelle; Eingabe des Kompressors |
| `twanksta_entries.json` | Roh-Export; noch gelesen von `export_valence.py`, `linker.py` |

Die lean NVH entsteht aus der fetten über den Kompressor
(`gen/compress_forms.py`), mit der exakten Zusicherung

    generate(lemma, stems) ⊕ overrides == Twanksta-Zellen   (⊕ = Override ersetzt den Slot)

## Bauen

Build über das python-`hfst`-Modul (Projekt-Abhängigkeit), keine separate
hfst-CLI nötig; Lookup zur Laufzeit über `pyhfst`.

```bash
uv sync
make atoms   # datenfreie Atom-FSTs aus gen/*.lexc → build/gen-*.hfstol
make         # Atome + lean NVH + lexc/ → build/analyzer.lexc → base.fst → *.hfstol
```

Weitere Targets:

```bash
make analyzer-parity   # Oberflächendeckung gegen das eingefrorene Twanksta-Gold
make cg3-check         # CG3-Sets generieren + Grammatiken kompilieren
make disambiguate      # Vollkorpus-Lauf mit Ambiguitätsstatistik
make conllu            # CoNLL-U-Silberexport → data/prussian_silver.conllu
make links             # desc-Ref-Resolver → build/links.json
make validate-corpus   # Validator über die Korpora (Fehlalarm-Regression)
make eval-prusaspira   # lenient vs. prusaspira, Leave-one-out je Regel → build/prusaspira_eval.md
uv run pytest
```

Kompressor (fette → lean NVH):

```bash
uv run python gen/compress_forms.py --stats
uv run python gen/compress_forms.py --verify-idempotent
```

## Lookup

Mit der (optionalen) hfst-CLI:

```bash
echo "dumslis" | hfst-lookup build/base.hfstol     # Analyse
echo "dumslē+N+Fem+Sg+Gen" | hfst-lookup build/base.gen.hfstol   # Generierung
```

In Python: `prussian_fst.fst_lookup.flookup_batch` / `glookup_batch`, bzw. die
High-Level-API `prussian_fst.api` (`analyze`, `validate`, `conllu`).
`PRUSSIAN_FST=<pfad>` setzt einen anderen Analyzer für die CG3-Pipeline.

## Struktur

```
.
├── Makefile
├── gen/                      # generativer Kern
│   ├── {a,aa,i,u,jo,n}stem.lexc, adj.lexc, verb.lexc   # Endungstabellen je Familie
│   ├── accent.regex          # Akzent/Makron/Gemination
│   ├── atom_fst.py           # gen/*.lexc → build/gen-<fam>-<paradigm>[-<role>].hfstol
│   ├── generator.py          # datenfreier Generator: Lemma+Paradigma(+Stämme) → Slots
│   ├── compress_forms.py     # Kompressor: fette NVH → lean NVH
│   ├── build_analyzer.py     # lean NVH + Atome + lexc/ → build/analyzer.lexc
│   └── DEVIATIONS.md         # Ledger der Regel-Abweichungen
├── lexc/                     # handgepflegt
│   ├── root.lexc, symbols.lexc          # Root + Multichar-Tag-Inventar
│   ├── function_words.lexc
│   └── pronouns.lexc
├── src/prussian_fst/
│   ├── build_fst.py          # FST-Build über python-hfst (ersetzt hfst-CLI)
│   ├── fst_lookup.py         # pyhfst-Lookup (Analyse/Generierung)
│   ├── api.py                # In-Process-API für prussian-mcp
│   ├── cg3_pipeline.py       # CG3-Disambiguator-/Validator-Pipeline
│   ├── export_conllu.py      # CoNLL-U-Export
│   ├── export_valence.py     # Rektion/Valenz → build/valence.json
│   ├── gen_cg3_sets.py       # valence.json → cg3/generated-sets.cg3
│   └── linker.py             # desc-Ref-Resolver → build/links.json
├── cg3/
│   ├── disambiguator.cg3     # Hauptgrammatik
│   ├── dependency.cg3        # Dependenz-Schicht
│   ├── validator.cg3         # Validierungs-Regeln
│   └── generated-sets.cg3    # generiert
├── norm/                     # Normalisierungs-Stufen (pro Phänomen)
│   ├── macron.regex          # Makron-Verlust (ā ē ī ō ū → a e i o u)
│   ├── degem.regex           # Degemination (nn → n …)
│   ├── ortho.regex           # w-Prothese, i-Synkope, twei↔tun …
│   ├── palatal.regex         # Prusaspira: Palatalnotation (sj→š, Cja→Ce/Ci …)
│   └── length.regex          # Prusaspira: Gemination nach kurzem Vokal
├── tests/                    # pytest; gold/ = eingefrorene Twanksta-Oberflächen
└── build/
    ├── gen-*.hfstol          # Atome (Stamm+Tag → Oberfläche)
    ├── analyzer.lexc         # gebackene Merged-lexc (Quelle von base.fst)
    ├── base.hfstol           # Analyzer (surface → analysis), strikt
    ├── base.gen.hfstol       # Generator (analysis → surface)
    ├── macron.hfstol         # + Makron-Normalisierung
    ├── lenient.hfstol        # + Degemination/Ortho (Gesamt-Fallback)
    ├── prusaspira.hfstol     # + Prusaspira-Schreibnorm (opt-in, über lenient)
    └── cg3/*.bin
```

## Tags

Giella-Inventar (`lexc/symbols.lexc`), Reihenfolge
`lemma+POS[+Sub]+…`, z. B.:

```
dumslē+N+Fem+Sg+Gen:dumslis
Adwēnts+N+Prop+Msc+Sg+Nom:Adwēnts
begalbis+A+Comp+Msc+Sg+Nom:begalbjaisis
begalbis+Adv+Comp:begalbjais
perwaidīntun+V+Ind+Prs+Sg1+Refl:perwaidinnas
```

- POS: `+N` (`+Prop` = großgeschriebenes Nomen), `+A`, `+Adv`, `+V`, `+Num`
  (`+Card`/`+Ord`), `+Pron`, `+Pr`, `+Po`, `+CC`/`+CS`, `+Pcle`, `+Interj`
- Nomen tragen das Genus (`+Msc`/`+Fem`/`+Neu`) als Eintragsfakt
- Verben: `+Ind`/`+Subj`/`+Opt`/`+Imprt`, `+Prs`/`+Prt`, Personen
  `+Sg1 +Sg2 +SP3 +Pl1 +Pl2`; Partizipien `+PrsPrc`/`+PrfPrc` × `+Act`/`+Pss`
- Steigerung `+Comp`/`+Superl`, auch an abgeleiteten Adverbien

Präpositionsrektion steht nicht im FST, sondern als Lemma-Liste in der
CG-Schicht (`build/valence.json` → `cg3/generated-sets.cg3`).
`valence.json` enthält außerdem Best-Effort-Verbvalenz (nur die im
Wörterbuch annotierten Verben).

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
