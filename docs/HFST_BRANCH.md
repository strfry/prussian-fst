# HFST-nativer Analysatorzweig

> **Status:** ✅ umgesetzt (paralleler Zweig zu pyfoma). Ziel: dieselbe
> Sprachbeschreibung **durchgängig in HFST** komponieren — echte Komposition
> statt aufgezählter Varianten — und später quantitativ mit dem pyfoma-Zweig
> vergleichen.

Code: `src/prussian/fst/hfst/`. Bau & Prüfung: `scripts/build_hfst.sh`.

## Motivation

Der pyfoma-Zweig (`src/prussian/fst/{build,phonology}.py`) erzeugt den
nachsichtigen Analysator `lenient.fst`, indem er die Quellschreibungen
(Twanksta-`j`, `elaktr-`, …) als **V-Zeilen pro Stamm/Endung** in die
Morphotaktik *aufzählt* — pyfoma kann die zugehörigen Wildcard-Regeln nicht
komponieren (docs/HFST_SPIKE.md). HFST kann es. Dieser Zweig formuliert die
Varianten daher als **generalisierende Regeln** und komponiert die gesamte
Pipeline nativ in HFST:

```
data/gold + Wortliste                       (dieselbe Quelle wie pyfoma)
   │  hfst/lexc_gen.py   (markierte Unterseite: A E I O U, M/S/J, Grenzmarker ·)
   ▼
build/hfst/morphotactics.lexc
   │  hfst.compile_lexc_file
   ▼
Lexikon  ∘  rules.PHONOLOGY            = generator.hfst  (Analyse → Oberfläche)
            (SHORTEN ∘ LENGTHEN ∘ JPAL ∘ CLEANUP)        invertiert: analyser.hfst
   │
   │  ∘ rules.SPELLRELAX_MARKED  (Grenz-j vor CLEANUP)
   │  ∘ rules.SPELLRELAX_SURFACE (TWANKSTA_J, ELAKTR, -as/-us; nach CLEANUP)
   ▼
lenient.hfst  (Oberfläche + Quellvarianten → Analyse)
```

Anders als die V-Zeilen sind das **echte Regeln**: sie greifen auch auf
Wortlisten-/Korpusvokabular, nicht nur auf belegte Lexeme.

## Zwei Lexikon-Backends: lexc (inline) und lexd (handgeschrieben + generiert)

Die Morphotaktik gibt es in zwei Varianten, beide mit identischer markierter
Unterseite und identischer Regelschicht:

- **lexc** (`hfst/lexc_gen.py` + `hfst/build.py`): alles inline aus den
  Eintragsdaten generiert, kompiliert mit `hfst.compile_lexc_file` (reines
  python-hfst, keine externen CLIs). Schnellster Selbsttest.
- **lexd** (`hfst/lexd_gen.py` + `hfst/lexd_build.py`): Apertium-`lexd`-Format,
  kompiliert über die CLIs `lexd` → `.att` → `hfst-txt2fst`. Hier ist die
  **Arbeitsteilung** umgesetzt, die der pyfoma-Zweig nicht hat:

  | Teil | Quelle |
  |------|--------|
  | Paradigmentabellen (PATTERNS + Infl) | **handgeschrieben** in `data/lexd/*.lexd` |
  | geschlossene Klassen — Pronomen, Suppletive, Numeralia, Funktionswörter, Adverbien | **handgeschrieben** in `data/lexd/{30-pronouns,35-suppletives,70-numerals,50-function-words,60-adverbs}.lexd` (literale Vollformen) |
  | große Wortliste (Lemma → Stamm + Paradigma) | **automatisch generiert** (`lexd_gen.build_lexd(stems_close_only=True)`) |

  Die geschlossenen Klassen sind hochgradig suppletiv/irregulär (z. B.
  `as→men→mans`, `tāns→ten-`, `debīks→māises-`); sie werden daher — wie die
  Numeralia — als **literale Vollformen** geschrieben statt über
  Stamm+Endung+Regeln. `lexd_build._handwritten_closed()` filtert die
  entsprechenden Paradigmen aus den generierten Stämmen, damit sie nicht
  doppelt erscheinen. Bootstrap der Literalformen aus dem Goldstandard über
  `report.cases.nominal_cases`; danach in `data/lexd/*` von Hand gepflegt.

  **Toolchain (lexd-Build):** zusätzlich zu `python-hfst` die System-CLIs
  `lexd` und `hfst-txt2fst` (Debian/Ubuntu: `apt-get install lexd hfst`).

## Module

| Modul | Aufgabe |
|-------|---------|
| `hfst/lexc_gen.py` | Eintragsdaten → `morphotactics.lexc` (markiert, V-frei). Wiederverwendet die pyfoma-freie Morphotaktik-Logik aus `morphology.lexd`. |
| `hfst/rules.py` | Regelschicht als HFST-Regex-Strings: Phonologie/Akzent + spellrelax. Keine hfst-Importe beim Laden. |
| `hfst/build.py` | Komposition: lexc ∘ Regeln → `generator/analyser/lenient.hfst`. |
| `hfst/check.py` | Validierung gegen Goldstandard (= `gen_check` für den HFST-Zweig), spiegelt `report.generation.run` über Lookup-Adapter. |

## Markierte Unterseite

Identisch zum pyfoma-Zweig (docs/AKZENT.md, docs/ORTHO_RULES.md §4), plus
ein Grenzmarker:

| Marker | Bedeutung |
|--------|-----------|
| `A E I O U` | Archiphonem (lang/kurz alternierend) |
| `M` | Mobile-Lexem (Akzentklasse), vor dem Stamm |
| `S` | starke Endung (zieht den Akzent) |
| `J` | palatalisierende Endung (`g→ģ` …) |
| `·` | **neu:** Stamm\|Endungs-Grenze, nur auf j-relaxbaren, nicht-palatalen Endungen. Trägt die generalisierenden Grenz-j-Regeln; wird von `CLEANUP` getilgt. |

Der Grenzmarker macht die Twanksta-`j`-Variante regelhaft: statt 166+
aufgezählter Endungsvarianten platziert `lexc_gen` den Marker (das
`jan_variant`-Prädikat liefert nur die *Endungsklasse*), und
`rules.HARD_J`/`SOFT_J` berechnen die Form (`in→jan`, `us→jus`, `ēi→jai`, …).

## Bauen & Prüfen

```bash
scripts/build_hfst.sh --gold-only   # nur Goldstandard (kein Wortlisten-Download nötig)
scripts/build_hfst.sh               # voll (braucht data/external/twanksta_entries.json)
```

Das Skript legt beim ersten Lauf ein Python-3.12-venv (`.venv-hfst`) an und
installiert `python-hfst` (kein cp313-Wheel verfügbar, daher separat vom
pyfoma-venv). Build ~8 s für den vollen Datensatz (≈35 k Lexeme).

## Paritätsergebnis (gegen pyfoma-Zweig)

| Maß | HFST | pyfoma |
|-----|------|--------|
| Nominale Gold-Zellen | **1471/1471 exakt** | 1471/1471 |
| Doublettenformen | **18/18** | 18/18 |
| Verbale Gold-Zellen | 904/952 (48 no_gen) | 904/952 (48 no_gen) |
| `test_ortho`-Varianten | 8/9 | 8/9 |

Die 48 verbalen `no_gen` sind die noch nicht modellierte Partizip-
Deklination (PrsPrc/PstPrc Fem/Neut) — in **beiden** Zweigen identisch.
Das 9. `test_ortho`-Paar (`māldaisjan↔māldaisin`, Komparativ-Formant) ist
ebenfalls in beiden Zweigen offen (der Grenzmarker sitzt vor dem ganzen
`ais`-Formanten statt vor der Kasusendung).

## Offene Punkte / Nächstes

- Komparativ-Grenzmarker zwischen Formant und Kasusendung setzen
  (`māld·ais·in`), damit das 9. Paar fällt — wäre der erste Punkt, an dem
  der HFST-Zweig den pyfoma-Zweig **übertrifft**.
- Quantitativer Coverage-Vergleich (Wortliste/Korpus) HFST vs. pyfoma als
  eigener Report.
- `-as/-us`-Generalisierung (`rules.AS_US_S`) gegen die BACKLOG-Lücke messen.
