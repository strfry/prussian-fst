# HFST-nativer Analysator

> **Status:** ✅ umgesetzt. Die Sprachbeschreibung wird **durchgängig in HFST**
> komponiert — echte Komposition statt aufgezählter Varianten. Dies ist der
> einzige Analysatorzweig (der frühere pyfoma- und der lexc-Inline-Zweig
> wurden entfernt).

Code: `src/prussian/fst/hfst/`. Bau & Prüfung: `scripts/build_hfst.sh`.

## Motivation

Quellschreibungen (Twanksta-`j`, `elaktr-`, …) werden **nicht** als Varianten-
Zeilen pro Stamm/Endung in die Morphotaktik aufgezählt, sondern als
**generalisierende Faltungsregeln** auf der Oberfläche komponiert. Die gesamte
Pipeline läuft nativ in HFST:

```
data/gold + Wortliste
   │  hfst/lexd_gen.py   (markierte Unterseite: Â Ê Î Ô Û, M/S/J)
   ▼
build/hfst/morphotactics.lexd
   │  lexd CLI → .att → hfst-txt2fst
   ▼
Lexikon  ∘  rules.PHONOLOGY            = generator.hfst  (Analyse → Oberfläche)
            (SHORTEN ∘ LENGTHEN ∘ JPAL ∘ CLEANUP)        invertiert: analyser.hfst
   │
   │  ∘ fold.FOLD_SURFACE  (Diakritika, palatales Twanksta-j, elaktr)
   │  ∘ Twanksta-j-Endungen (datengetrieben aus beiden Wörterbüchern)
   ▼
lenient.hfst  (Oberfläche + Quellvarianten → Analyse)
```

Anders als Varianten-Zeilen sind das **echte Regeln**: sie greifen auch auf
Wortlisten-/Korpusvokabular, nicht nur auf belegte Lexeme.

## Zwei Lexikon-Backends: lexc (inline) und lexd (handgeschrieben + generiert)

Die Morphotaktik liegt im **lexd**-Format (`hfst/lexd_gen.py` +
`hfst/lexd_build.py`, Apertium-`lexd`), kompiliert über die CLIs
`lexd` → `.att` → `hfst-txt2fst`. Die **Arbeitsteilung**:

  | Teil | Quelle |
  |------|--------|
  | geschlossene Klassen — Pronomen, Suppletive, Numeralia, Funktionswörter, Adverbien | **handgeschrieben** in `data/lexd/{30-pronouns,35-suppletives,70-numerals,50-function-words,60-adverbs}.lexd` (literale Vollformen) |
  | kuratierte Paradigmentabellen (PATTERNS + Infl) | **handgeschrieben** in `data/lexd/{10-nouns,15-nouns-minor,20-adjectives,22-adjectives-minor,40-verbs,41-participles}.lexd` |
  | übrige Paradigmentabellen (PATTERNS + Infl) | **lean generiert** (gender-gemergt) für alle Paradigmen, die *nicht* handgeschrieben sind |
  | große Wortliste (Lemma → Stamm + Paradigma) | **automatisch generiert** (Stem-Lexika) |

  Die geschlossenen Klassen sind hochgradig suppletiv/irregulär (z. B.
  `as→men→mans`, `tāns→ten-`, `debīks→māises-`); sie werden daher — wie die
  Numeralia — als **literale Vollformen** geschrieben statt über
  Stamm+Endung+Regeln. `lexd_build._handwritten_closed()` filtert die
  entsprechenden Paradigmen aus den generierten Stämmen.

  Die Paradigmentabellen folgen dem **Override-Prinzip**: `lexd_build` scannt
  `data/lexd/*.lexd` nach handgeschriebenen `LEXICON Infl…` und übergibt die
  Namen als `skip_infl` an `build_lexd`. Für diese Paradigmen wird nur das
  Stem-Lexikon generiert (PATTERN + Infl kommen handgeschrieben); alle übrigen
  offenen Paradigmen erhalten PATTERN + Infl **lean generiert** (gender-gemergt).
  Eine handgeschriebene Tabelle ersetzt also einfach das Generat — die
  Migration kann Paradigma für
  Paradigma kuratieren, ohne Abdeckung zu verlieren. Bootstrap der Literal-/
  Tabellenformen aus dem Goldstandard über `report.cases`; danach von Hand
  gepflegt.

  **Vollbau-Parität:** der Vollbau erreicht damit dieselben **1471/1471**
  nominalen Gold-Zellen wie der gold-only-Selbsttest und deckt die gesamte
  Wortliste ab (≈15 k Lexikon-Zustände).

  **Toolchain (lexd-Build):** zusätzlich zu `python-hfst` die System-CLIs
  `lexd` und `hfst-txt2fst` (Debian/Ubuntu: `apt-get install lexd hfst`).

## Module

| Modul | Aufgabe |
|-------|---------|
| `hfst/lexd_gen.py` | Eintragsdaten → `morphotactics.lexd` (markiert, V-frei). Nutzt die Morphotaktik-Helfer aus `morphology.lexd`. |
| `hfst/rules.py` | Phonologie-/Akzentregeln als HFST-Regex-Strings. Keine hfst-Importe beim Laden. |
| `hfst/fold.py` | Orthographie-Faltung (Twanksta ↔ Standard) als HFST-Regex. |
| `hfst/lexd_build.py` | Komposition: lexd ∘ Regeln ∘ Faltung → `generator/analyser/lenient.hfst`. |
| `hfst/check.py` | Validierung gegen Goldstandard, spiegelt `report.generation.run` über Lookup-Adapter. |

## Markierte Unterseite

Siehe docs/AKZENT.md, docs/ORTHO_RULES.md §4:

| Marker | Bedeutung |
|--------|-----------|
| `Â Ê Î Ô Û` | Archiphonem (lang/kurz alternierend; distinkte Symbole statt nackter Großbuchstaben — literale Großbuchstaben/Eigennamen kollidieren nicht mehr) |
| `M` | Mobile-Lexem (Akzentklasse), vor dem Stamm |
| `S` | starke Endung (zieht den Akzent) |
| `J` | palatalisierende Endung (`g→ģ` …) |

Die Twanksta-`j`-Variante wird nicht in der Morphotaktik aufgezählt, sondern
auf der Oberfläche durch die Faltung (`hfst.fold`) und die datengetrieben
abgeleiteten Twanksta-j-Endungen behandelt (nur `lenient.hfst`).

## Bauen & Prüfen

```bash
scripts/build_hfst.sh --gold-only   # nur Goldstandard (kein Wortlisten-Download nötig)
scripts/build_hfst.sh               # voll (braucht data/external/twanksta_entries.json)
```

Das Skript legt beim ersten Lauf ein Python-3.12-venv (`.venv-hfst`) an und
installiert `python-hfst` (kein cp313-Wheel verfügbar). Build ~8 s für den
vollen Datensatz (≈35 k Lexeme).

## Ergebnis

| Maß | Wert |
|-----|------|
| Nominale Gold-Zellen | **1471/1471 exakt** |
| Doublettenformen | **18/18** |
| Verbale Gold-Zellen | 904/952 (48 no_gen) |

Die 48 verbalen `no_gen` sind die noch nicht modellierte Partizip-Deklination
(PrsPrc/PstPrc Fem/Neut).

## Offene Punkte / Nächstes

- Partizip-Deklination (PrsPrc/PstPrc Fem/Neut) modellieren (48 verbale `no_gen`).
- Ebene 3 (Phonologie/Faltung) deklarativ als twol/xfst-Dateien (statt
  HFST-Regex-Strings in `rules.py`/`fold.py`).
- Quantitativer Coverage-Report (Wortliste/Korpus).
