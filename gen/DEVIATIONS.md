# Verb-Generator: Abweichungen vom twanksta-Bestand

Stand automatisch prüfbar über `uv run python gen/coverage_verb.py --show 300`
(nicht-zirkulär: generiert aus Prinzipalform-Stämmen, vergleicht gegen die vollen
twanksta-Formen). Dieses Dokument ist das **Ledger**: jede Stelle, an der der
Generator NICHT die twanksta-Form liefert. Nichts davon ist heimlich handgelistet;
alles ist als Regel-Deckung offen ausgewiesen und später per Override ausbügelbar.

**Regel-Deckung: 27050 / 27180 Slots (99.5 %).** 136 Slots weichen ab, verteilt
auf ~60 Lexeme (~96 % der 1510 Ziel-Lexeme sind vollständig korrekt).

Urteil-Legende: **Regel** = echte Morphophonologie, sauber nachziehbar ·
**Daten** = twanksta-Inkonsistenz-Verdacht, erst prüfen · **Override** = Einzelfall,
gezielt überschreiben.

---

## A. Optativ-Konsonantenschwund vor -sei — *Regel*

Der Optativ `-sei` reduziert den Stammauslaut (st-/d-/l-Cluster fällt), der
Subjunktiv `-lai` behält ihn. EIN Nonfin-Stamm kann beide nicht liefern.

| Par. | ×  | erwartet ≠ erzeugt | Auslaut |
|------|----|--------------------|---------|
| 87a  | 7  | `aukansei` ≠ `aukandsei` | -nd → -n |
| 87b  | 18 | `auskrāisei` ≠ `auskrāidsei`, `basei` ≠ `badsei` | -d/-dd → ∅ |
| 97   | 3  | `spīsei` ≠ `spīlsei` | -l → ∅ |
| 88   | 1  | `kāisei` ≠ `kāissei` | -ss → -s |

→ Regel im accent.regex (Cluster-Reduktion vor `-sei`) ODER eigenes Opt-Atom mit
reduziertem Stamm. **25+1 Slots.** Betrifft den Optativ von Par.87 systematisch.

## B. Par.136 Optativ-Makron — *Daten*

19× `kalbisei` (kurz i) statt generiert `kalbīsei` (lang ī). Subjunktiv ist
durchweg lang (`kalbīlai`), Schwesterklassen 134/139 ebenfalls lang. Der kurze
Opt-Vokal ist mit hoher Wahrscheinlichkeit eine twanksta-Inkonsistenz.
→ Gegen Quellen prüfen; wenn Artefakt, Override; nicht modellieren. **19 Slots.**

## C. Par.81 interner Präterital-Vokalwechsel (ē/ī) — *Daten → Override*

Das Präteritum ist regulär `ē`, in twanksta aber pro Verb in GENAU EINER Zelle `ī`
— und die abweichende Zelle wandert nach Wurzeltyp (`-er-/-eg-` → 1pl, `-em-/-el-`
→ 3sg). Kein sauberes Muster → höchstwahrscheinlich Generierungs-Artefakt in
twanksta.

| Zelle | × | Beispiel |
|-------|---|----------|
| Prät P1/P2 Pl | 15 | `augīrimai` (erz. `augērimai`) |
| Prät P1/P2 Sg | 14 | `aulīmi` (erz. `aulēmi`), `drībi` (erz. `drēbi`) |

→ 21 Lemmata × je 1 Zelle. **Override-Liste** (gezielte Mini-LUT), NACHDEM gegen
Prussian-Quellen geklärt ist, ob das `ī` real sporadisch ist. **36 Slots.**

## D. Par.81 -st-Verben (dwestwei-Typ): Gemination/Cluster — *Override*

`dwestwei/nadwestwei/etdwestun`: Präsens-Gemination im Imperativ (`dwessjais` vs.
erz. `dwesjais`) und Opt-Cluster (`dwessei` vs. erz. `dwetsei`). Der -st-Wechsel
sitzt quer zu den drei Stämmen. **~11 Slots**, 3 Lexeme → Override.

## E. Falsche Subklasse (kleine, echte Untergruppen) — *Regel (klein)*

| Fall | × | Diagnose |
|------|---|----------|
| Par.87b `pēstun/perpēstun` | 9 | Prät-Sg `-i` (`pēdi`) statt `-a` — eigene i-Prät-Untergruppe |
| Par.142 `tālkātun` | 2 | Ablaut `talkā-/talāi-` im Prät-Plural |
| Par.81 `weltun/enweltun` | 2 (Ableitung) | a-Präsens (`wella`), nicht `-ja` → fällt aus der Stamm-Ableitung |

→ je eigene Mini-Regel oder Override; zu klein für eigene Tafel.

## F. Gemination/Ablaut-Einzelfälle (accent.regex greift nicht) — *Override*

| Par. | Lexem | erwartet ≠ erzeugt |
|------|-------|--------------------|
| 85 | `erpilnintun` | `erpilninna` ≠ `erpilnina` (7 Zellen, Gemination) |
| 97 | `gīmtwei` | `gimma` ≠ `gimna` (Nasal-Assimilation, 5 Zellen) |
| 97 | `wiptwei`, `milztun` | `weppais`/`menzais` ≠ `elpais`/`melzais` (Ablaut) |
| 136 | `takītun` | `takkais` ≠ `tākais` (Gemination) |
| 134 | `lāimitwei` | `lāimēis` ≠ `lāimeis` (Makron) |

→ Einzel-Overrides; kein systematischer Fehler.

## G. Stamm-Ableitung schlägt fehl (aus Zielmenge ausgeschlossen, kein Miss)

`auwippintun[143]`, `preipeisātun[138]`, `gultwei[75]`, `kīrptun[97]`,
`weltun/enweltun[81]` — die Prinzipalform endet nicht auf die erwartete
Klassen-Endung (Stamm nicht mechanisch ableitbar). 6 Lexeme. → Override oder
Reklassifizierung; nicht als Slot-Miss gezählt.

## H. twanksta-Datenfehler (geflaggt, NICHT modelliert)

Verben, deren sämtliche synthetischen Formen = Infinitiv sind (kein echtes
Paradigma) — automatisch erkannt in `scan_data_errors()`, nicht emittiert:
`dirtwei, dirtun, kāistwei, enkāistwei, prakāistwei, klīmptwei, tilptwei,
skrabtwei, rjaūgitwei, preijustwei` (+ `perwīlktun si kāigi`, MWE).
→ Upstream in twanksta melden.

---

## Nächste Schritte (Priorität)

1. **A (Opt-Cluster)** — echte Regel, betrifft ganz Par.87; im accent.regex lösen.
2. **C + B** — gegen Quellen prüfen; wenn Daten-Artefakt, Override-Liste (21 + 19).
3. **D/E/F/G** — Einzel-Overrides, wenn die Formen im Dictionary gebraucht werden.
4. **H** — twanksta-Issue.

---

## Anhang: Numeralia / pronominale Adjektive P21–24 (WS2b) — *Override*

Kein eigenes Lexikon: P21 (`aīns`, `eraīns`, `niaīns`) über AdjMobile, P22–24
(`abbai`, `dwāi`, `trīs`, Pluralia tantum) über AdjFixed auf den Pl-Slots. Was die
Regel nicht exakt trifft, ist Override und **ersetzt** den Slot (WS1b):

- P21 pronominales Sg.Gen/Dat `-asse`/`-asmu`/`-asses`/`-assei` (wie `stas`/`kits`),
  Neu.Sg `aīnase`/`aīnasmu` ohne Akzentverschiebung.
- **Offene Datenfrage:** P21-Neutrum-Plural trägt Doppelformen aus dem Singular
  (`aīnan` in neu.pl.nom/acc, `ainasse` in neu.pl.gen, `ainasmu` in neu.pl.dat) —
  Absicht oder Twanksta-Fehler? Bis zur Klärung als Override übernommen (Lesart
  `ainasse` → auch `+Neu+Pl+Gen`).
- P23/24 `dwāi`/`trīs`: Regel trifft nichts; Stufe-1-Stamm (`dwejj`/`trijj`) +
  Overrides.
