# Das Akzentmodell (nach Rinkevičius 2009)

Stand: 2026-06-13. Abgeleitet von `src/prussian/gold/accent.py` aus
`data/gold/goldstandard.json`; Ergebnis in `data/gold/accent_model.json`.

## 1. Theorie

**Rinkevičius, Vytautas (2009): „Das altpreußische Akzentsystem"**
(Diss.-Zusammenfassung, Univ. Vilnius) reanalysiert die Stamm-Allomorphie
der TABVLA NOVA als Akzentphänomen:

- Zwei nominale Akzentparadigmen:
  - **Barytona** — Akzent fest auf dem Stamm; der Wurzelvokal trägt in
    *allen* Zellen das Makron (z. B. P32 *wīrs*: wīrs, wīras, wīru, …).
  - **Mobilia** — der Akzent springt auf **starke Endungen**; dort ist der
    Wurzelvokal unbetont und kurz (z. B. P46 *spigsnā*: Nom sg spigsn**ā**,
    aber Gen sg sp**ī**gsnas).
- Generative Grundregel: **Akzent = erstes starkes Morphem; fehlt eines →
  erstes Morphem.** Stämme der Barytona sind lexikalisch stark, die der
  Mobilia schwach; Endungen sind inhärent stark oder schwach.
- Orthographischer Reflex in der TABVLA NOVA: **Makron** = langer betonter
  Vokal; **Doppelkonsonant** = Kürzezeichen des betonten Vorvokals.

**Gegenposition:** Kortlandt (2011, Baltistica XLVI(2), 225–232) deutet die
Doppelkonsonanz als „Vortondoppelung" und hält viele Alternationen für
morphologisch statt phonetisch. Für dieses Projekt ist der Disput **nicht
entscheidungsbedürftig**: Wir reproduzieren die normalisierte Oberfläche der
TABVLA NOVA (Palmaitis/Klusis), die Makra und Doppelkonsonanz bereits nach
fester Norm setzt. Das Modell hier ist eine *Datenbeschreibung* dieser Norm
in Rinkevičius' Begriffen.

## 2. Ableitung aus dem Goldstandard

Der Goldstandard speichert pro Zelle ein `betont`-Flag (Stammvokal lang?).
Daraus wird abgeleitet (Details: Docstring von `accent.py`):

1. **Lexemklasse** pro Paradigma × Genus:
   `bar` (alle Zellen betont) / `mob` (gemischt) / `na` (kein Archiphonem im
   Stamm — Akzent an diesem Lexem nicht beobachtbar).
2. **Endungsstärke**: In Mobilia gilt `betont=false` ⟺ Endung **stark**.
   Aggregation über alle Mobilia pro (Zelle, Endungsoberfläche).
3. **De-Akzentuierungspaare**: starke Endung minus Akzentorthographie
   (Makron-Tilgung + Degemination) ↔ Baryton-Endung derselben Zelle.

## 3. Ergebnisse

### 3.1 Dreiteilung ist exakt (121 Einträge, 118 Paradigma × Genus)

| Klasse | Anzahl | Kriterium | Befund |
|---|---|---|---|
| Barytona | 28 | Archiphonem + alle Zellen betont | deckungsgleich |
| Mobilia | 18 | Archiphonem + gemischt | deckungsgleich |
| unbeobachtbar | 72 | kein Archiphonem im Stamm | deckungsgleich |

Es gibt **keinen** Eintrag mit Archiphonem, der nie lang erscheint, und
keinen ohne Archiphonem mit betont-Variation — die Flags kodieren exakt
das Akzentsystem.

### 3.2 Endungsstärke ist global konsistent — 0 Konflikte, 100 % Abdeckung

Eine **einzige** Tabelle (Zelle + Endungsoberfläche → stark/schwach) sagt
alle 967 Goldstandard-Zellen korrekt vorher (`accent_exceptions.json` ist
leer). Starke Endungen (19):

| Zelle | starke Endungen | schwache Endungen (Auswahl) |
|---|---|---|
| Nom sg | -ā, -ī (Feminina) | -s, -is, -us, -an, -a, -i, -u |
| Gen sg | -asse, -asses (pronominal) | -as, -es, -is, -se, -us, -was |
| Dat sg | -asmu, -assei (pronominal) | -u, -ei, -ai, -i, -smu, -usmu |
| Akk sg | — (immer schwach) | -an, -in, -un, -u |
| Nom pl | -āi, -ēi, -wāi | -ai*, -as, -es, -ei, -us, -is |
| Gen pl | -ēisan, -asse | -an, -in, -un |
| Dat pl | -āmans, -ammans, -emmans, -immans, -ummans, -ēimans, -jāmans, -asmu | -amans, -emans, -imans, … (nur Barytona) |
| Akk pl | — (immer schwach) | -ans, -ins, -uns |

\* kurzes -ai erscheint nur in Barytona (s. 3.3) und „na"-Paradigmen.

### 3.3 Die Endung alterniert spiegelbildlich zum Stamm

Starke Endungen tragen den Akzent selbst — als Makron **oder** als
Doppelkonsonant nach Kurzvokal. In Barytona erscheint dieselbe Endung
unbetont, d. h. ohne Makron und ohne Gemination:

| Zelle | Mobile (Endung betont) | Baryton (Endung unbetont) |
|---|---|---|
| Nom pl | -āi, -ēi, -wāi | -ai, -ei, -wai |
| Dat pl | -ammans, -immans, -ummans, -emmans | -amans, -imans, -umans, -emans |
| Dat pl | -āmans, -jāmans | -amans, -jamans |
| Nom sg | -ā, -ī | -a, -i |

12 von 19 starken Endungen haben ihr de-akzentuiertes Gegenstück belegt in
einem Baryton-Paradigma; die übrigen 7 sind Pronominal- (-asse, -asses,
-assei: P21 *aīns*) und Ordinal-Endungen (-ēisan, -ēimans: P70 *tīrts*),
für die der Goldstandard kein Baryton-Gegenstück enthält.

**Konsequenz:** Länge *und* Gemination in der Endung sind reiner
Akzentreflex. Im FST können daher auch die Endungen archiphonemisch
notiert werden (z. B. Dat pl `-{A}m_ans`), die Oberfläche folgt aus der
Akzentregel.

### 3.4 Abgleich mit Rinkevičius' Vorhersagen

| Rinkevičius 2009 | Befund TABVLA-Goldstandard |
|---|---|
| stark: Nom sg -ā/-ū (ā-St.), -ē (ē-St.) | ✓ bestätigt als -ā, -ī |
| stark: Nom pl -ai (a-St.) | ✓ bestätigt (-āi, auch -ēi, -wāi) |
| stark: Dat sg -asmu (Pron./Adj.) | ✓ bestätigt (auch -assei f.) |
| stark: Dat pl -āmans/-amans | ✓ bestätigt, für **alle** Stammklassen (-V́m(m)ans) |
| „evtl. stark": Gen sg -es (C-St.) | ✗ in der TABVLA-Norm **schwach** |
| schwach: Akk sg aller Stämme | ✓ bestätigt (Akk pl ebenso) |
| schwach: Nom sg -s | ✓ bestätigt |
| schwach: Nom pl der ā/ē/i/u-St. | ✓ bestätigt (-as, -es, -us schwach) |
| — | **neu:** Gen pl -ēisan, -asse stark |

### 3.5 Verben: „Mischung" = Ablaut, nicht Akzent

160 Verbeinträge (Paradigma × Tempus): 64 bar, 85 na, **11 „gemischt" —
alle elf betreffen ausschließlich den Infinitiv** (justwei↔jāut-,
kwistun↔kweit-, milītun↔mīl-). Das ist Stammstufen-Ablaut und wird im
Modell als Klasse `ablaut` getrennt geführt; im FST wird er als
lexikalischer Infinitivstamm behandelt (vgl. docs/ORTHO_RULES.md §2),
nicht über die Akzentregel.

## 4. Konsequenz für die FST-Architektur (Schritt 2)

- Stamm **einmal** im Lexikon, archiphonemisch (`m{I}st`), mit
  Klassenmerkmal `bar`/`mob` (bei `na` entfällt das Merkmal).
- Endung **einmal** pro Paradigma, mit Stärkemarker `^S`/`^W` aus
  `accent_model.json`.
- Eine Rewrite-Regel realisiert „Akzent = erstes starkes Morphem":
  - `bar`-Stamm → Archiphonem lang, Endung de-akzentuiert;
  - `mob`-Stamm vor `^S`-Endung → Archiphonem kurz, Endung akzentuiert;
  - `mob`-Stamm vor `^W`-Endung → Archiphonem lang, Endung de-akzentuiert.

## 5. Literatur

- Rinkevičius, V. (2009): *Prūsų kalbos kirčiavimo sistema / Das
  altpreußische Akzentsystem.* Diss.-Zusammenfassung, Universität Vilnius.
- Kortlandt, F. (2011): „On the orthography of the Old Prussian texts."
  *Baltistica* XLVI(2), 225–232.
- Mažiulis, V.: *Historische Grammatik des Altpreußischen* (§§21–25
  Palatalisierung; §§86–138 Quellendivergenzen).
- Palmaitis, M. L. / Klusis, M.: TABVLA NOVA (normalisierte Paradigmen,
  `data/sources/tabula.html`).
