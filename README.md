# Prussian Foma

Vergleich der altpreußischen Paradigmendaten aus drei Quellen mit
Finite-State-Transducer-Analyse (experimentell, PyFoma).

> **Umfang:** Dieses Projekt reproduziert die **normalisierte Oberfläche der
> TABVLA NOVA** (rekonstruiertes/wiederbelebtes „Neupreußisch", Palmaitis/Klusis)
> und drei darauf aufbauende moderne Lexika. Es modelliert **nicht** das
> historisch belegte altpreußische Korpus. Geeignet für
> Sprachwiederbelebung/Lehre, **nicht** für diachrone bzw. attestations­kritische
> Korpusanalyse. Begründung: [docs/AKZENT.md](docs/AKZENT.md) §1.

> **Herkunft & Vertrauenskette der Daten:** [docs/PROVENANCE.md](docs/PROVENANCE.md)

## Datenquellen

### 1. Tabula Nova (tabula.html)

**URL:** [http://donelaitis.vdu.lt/prussian/tabula.htm](http://donelaitis.vdu.lt/prussian/tabula.htm)
(Spiegel von `prusaspira.org/tabula.html`, derzeit erreichbar).

Eine manuell gepflegte HTML-Referenztabelle aller altpreußischen
Flexionsparadigmen (Nr. 1–144). Jedes `<p>`-Element enthält Nummer,
Genusangabe (m/f/n, m/f, m/f/n) und die vier Kasus in Singular und Plural
in der Reihenfolge Nom–Gen–Dat–Akk.

Mehrere `<p>`-Elemente pro Nummer kodieren mehrere Genera oder
Pronominalformen (`pnl`). Die `load_tabula()`-Funktion in
`compare_sources.py` parsiert diese und expandiert
Schrägstrich-Genusangaben (z.B. `m/f` → `m` + `f`).

### 2. Prusaspira (prusaspira.org)

**URL:** `https://www.prusaspira.org/wirdeins?akc=Iz&tap=W&bila=1&wirds=<lemma>`

Ein Online-Wörterbuch, das zu jedem Lemma eine vollständige
Flexionstabelle anzeigt. Die Daten werden von `fetch_prusaspira.py`
abgerufen (1 req/s, `bila=1` für englische Oberfläche) und als
`prusaspira/{num}_{lemma}.html` (rohes HTML) sowie
`prusaspira/{num}_{lemma}.txt` (Nur-Text-Extrakt) gespeichert.

Das `.txt`-Format hat eine `prūsiskai:`-Zeile mit Lemma,
Bedeutung, Wortart, Referenzbeleg und einer darauffolgenden
Gender-Spezifikation (z.B. `m sg m pl f sg f pl n sg n pl`). Es folgen
die vier Kasuszeilen (Nōm, Gēn, Dāt, Akk), wobei die n-Formen
(neutral) auf einer Fortsetzungszeile stehen.

### 3. Twanksta (wirdeins.twanksta.org)

**URL:** `https://wirdeins.twanksta.org/search/?dia=semba&s=<lemma>&language=engl`

Ein API-gestütztes Wörterbuch, das zu jedem Lemma die
Wörterbuch- und Flexionsdaten aus `twanksta_entries.json`
referenziert. Die Daten werden über `twanksta_api_check.py` validiert
und in `twanksta/{num}_{lemma}/lemma.json` abgelegt.

Das `lemma.json`-Format enthält entweder direkt ein Array von
Einträgen (bei exakten Treffern) oder ein Objekt mit `query/match/score/`
und `entries` (bei Fuzzy-/API-/manuellen Treffern).

**Beleglage:** von den 69 Lemmata haben 54 einen exakten
Dictionary-Treffer, 4 wurden per API ergänzt, 1 per Fuzzy-Suche,
5 manuell gemappt, 5 haben keinen Eintrag.

## Datenfluss

```
tabula.html               prusaspira.org            wirdeins.twanksta.org
    │                           │                           │
    │                           ▼                           ▼
    │                   fetch_prusaspira.py         twanksta_api_check.py
    │                           │                   lookup_prusaspira.py
    │                           │                   lookup_prusaspira_fuzzy.py
    │                           ▼                           │
    │                   prusaspira/{n}_{l}.txt      twanksta/{n}_{l}/lemma.json
    │                           │                           │
    └───────────┬───────────────┴───────────────────────────┘
                │
                ▼
   src/prussian/compare/compare_sources.py
                │
        ┌───────┴────────┐
        ▼                ▼
  data/derived/     data/derived/
  vergleich.html    vergleich.json   (roh, ohne Matching-Annotation)
                         │
                         ▼
           src/prussian/gold/goldstandard.py
                         │
                 ┌───────┴────────┐
                 ▼                ▼
        data/gold/          data/gold/
        GOLDSTANDARD.md     goldstandard.json
        (Review/Tabelle)    (FST-Eingabe: Stamm + Suffixe + betont-Flags)
                                 │
                ┌────────────────┤
                ▼                ▼
  src/prussian/gold/accent.py   src/prussian/fst/build.py
  (Akzentmodell, docs/AKZENT.md) (= entries + lexd_gen ∘ rules)
                │                        │
                ▼                ┌───────┴────────────┐
  data/gold/accent_model.json    ▼                    ▼
                        build/morphotactics.lexd  build/analyser.fst
                        (Stämme 1×, Marker M/S/J/V) build/lenient.fst
                                                       │
                                                       ▼
                                          src/prussian/fst/gen_check.py
                                          (967/967 Zellen + 18 Doubletten ✓)
```

## Entscheidungen für die Vergleichstabelle

### Normalisierung

- **Genus:** twanksta `"masc"/"fem"/"neut"` → `"m"/"f"/"n"`; tabula
  `"m/f"` → `"m"`, `"m/f/n"` → `"m"` (expandiert zu getrennten
  Zeilen).
- **Kasus:** tabula-Reihenfolge Nom–Gen–Dat–Akk; zweite Hälfte nach
  `pl`-Marker ist Plural.
- **Diakritika:** Für den Variantenvergleich werden alle Formen
  normalisiert (NFKD, diakritische Zeichen entfernt, ŕ→r, ķ→k, ļ→l,
  ņ→n).

### Geschlechteraufschlüsselung

- Jedes Genus bekommt eine eigene Tabellenzeile.
- Tabula-Einträge mit Schrägstrich-Genus (z.B. `m/f`) werden in
  Einzelgenus-Zeilen expandiert — die Formen werden dabei für beide
  Genera gleich gesetzt.
- Prusaspira-Header (`m sg m pl f sg f pl n sg n pl`) werden von
  `detect_prusaspira_genders()` analysiert. Die Spezifikation steht
  entweder als eigenständige Zeile(n) oder am Ende der
  `prūsiskai:`-Lemma-Zeile **nach** der letzten `]` (Referenzklammer),
  um Verwechslungen mit grammatischen Annotationen wie `1 SG NOM sg m`
  zu vermeiden.
- Kurzschreibweisen (`f sg pl` → `f sg f pl`) werden expandiert.
- Pronominal- (`Prōnominālas`), Komparativ-, Superlativ-,
  Adjektiv- und Adverbialabschnitte in Prusaspira-Dateien werden
  übersprungen.

### Mehrfach-Lemmata (Multi-Paradigma)

Manche Prusaspira-Dateien enthalten mehrere `prūsiskai:`-Lemmata
(z.B. `32_wīrs.txt` hat `wīrs` und `wīrsawiskas`).
`parse_prusaspira_multi()` probiert alle aus und wählt nach
Punktzahl:
- **100** = exakter Treffer (normalisierter Lemma-Name identisch)
- **80** = Präfix-Treffer (erwartetes Lemma ist Präfix des gefundenen,
  Differenz ≤ 6 Zeichen)
- **0** = kein Treffer

Bei Gleichstand gewinnt die reichhaltigere Tabelle (mehr gefüllte Zellen).

### Genus-Erkennung

- Steht das Gender-Schema in den Header-Zeilen
  (`m sg m pl f sg f pl n sg n pl` → ng=6 für 3 Genera × 2 Numeri),
  wird es direkt übernommen.
- `ng=4`: zwei Genera (m/f) mit sg+pl.
- `ng=3`: drei Genera (m/f/n) nur ein Numerus (pl).
- Sonst: Einzelgenus aus der `prūsiskai:`-Zeile extrahiert
  (Regex `\b([mfn])\s+sg\s+pl`).

### Duplikat-Behandlung bei Prusaspira

Wenn ein `Akk:`-Wert auf der gleichen Zeile wie ein
`prūsiskai:`-Marker eines zweiten Lemmas erscheint (z.B.
`Akk: mūsan mūsans … prūsiskai: mūsa …`), werden die Akkusativ-Daten
bis zum `prūsiskai:` abgeschnitten und dem ersten Lemma zugeordnet.
Erscheint derselbe Kasus später mit mehr Werten, wird er ersetzt.

### Hervorhebung (Diff-Markierung)

- **Rot (`diff`):** Keine Variante dieser Zelle kommt in einer
  zweiten Quelle vor (weicht von der 2-von-3-Mehrheit ab).
- **Gelb (`partial`):** Enthält die Mehrheitsform, aber hat
  zusätzliche Schreibvarianten.
- Die Mehrheit wird pro Zelle aus den normalisierten Varianten aller
  Quellen mit `/`-Split gebildet. Eine Variante gilt als Mehrheit,
  wenn sie in ≥ 2 Quellen vorkommt.

### Genus-lose Twanksta-Daten

Wenn twanksta keine Genus-Differenzierung hat (Gender `""`) aber
Formen liefert, werden diese in alle vorhandenen Genus-Zeilen
kopiert, die keine eigenen twanksta-Daten haben.

### Pl-Only-Erkennung

Wenn prusaspira und/oder twanksta nur Pluralformen haben, wird die
tabula-Singular-Spalte unterdrückt, selbst wenn tabula dort Werte
hat.

## Goldstandard-Auswahl

`compare_sources.py` schreibt neben `vergleich.html` einen rohen, source-major Dump
`vergleich.json` (geparste Formen pro Quelle, ohne Farb-/Matching-Annotation).
`goldstandard.py` liest diese JSON und wählt je Inflektionszelle eine kanonische Form
(`GOLDSTANDARD.md`). Die Abweichungen werden in drei Kategorien geführt:

- **Gender-Mismatch:** Quellen weisen demselben Lemma verschiedene Genera zu (jede Quelle
  genau ein Genus). Vorschlag = Mehrheits-Genus.
- **Variation:** echte Formdivergenz, die **nach** der orthographischen Regelschicht
  fortbesteht. Goldstandard = Mehrheitsvotum (2/3); **kein** MCP-Check (der Prussian MCP
  *ist* die Twanksta-Quelle).
- **Orthographie:** nach Anwendung der Regelschicht identisch (gleiches Morphem).

Zusätzlich schreibt `goldstandard.py` die **vollständige** FST-Eingabe `goldstandard.json` —
eine Liste mit einem Eintrag pro (Paradigma, Genus): Felder `paradigm`, `lemma`, `gender`,
`stamm`, `suffixe`. Der **Stamm** ist der makron- **und palatalisierungs**-insensitive
gemeinsame Präfix **aller** Goldformen des Paradigmas (über alle Genera hinweg gleich), sodass
weder Vokallänge (ī/i) noch Palatalisierung (ŗ/r, š/s) den Stamm bricht; die Schreibung inkl.
Makron stammt vom maskulinen Nom sg (= Lemma-Zitierform). Je Zelle steht das **Suffix**
(Goldform minus Stamm) mit zwei Flags: **`macron_shift`** (Stamm-Region in längen-verschobenem
Grad → Längen-Allomorphie) und optional **`palatize`** (Stamm-Region palatalisiert, z. B.
`kūg-` → `kūģu`). Der exakte Grad bzw. die Palatalisierung bleibt einer späteren
(morphophonologischen) Schicht überlassen; die exakten Oberflächenformen stehen in
`GOLDSTANDARD.md` / `vergleich.json`.

### Orthographische Regelschicht (vor dem Votum)

Das Mehrheitsvotum läuft erst **nach** Normalisierung der quellenspezifischen
Schreibkonventionen (Mažiulis, *Historical Grammar* §§21–25, §122). Zwei Richtungen:

- **A – Palatal-j:** Twanksta schreibt Palatalisierung als explizites `j`
  (`sj`=š, `gj`=ģ, `kj`=ķ …; §21 „*j is not marked after the letter i"). Gemination `jj`
  bleibt erhalten (echte Variation).
- **B – weiche Endung:** `-an/-in/-en` werden als Allomorphe derselben weichen Endung
  neutralisiert (§122 Fn54).

**Nicht** normalisiert (= echte Variation): Vokalgrad (ī/ē, ū/ā), Gemination (ss/s, jj/j),
Stamm- und Konsonantstamm-Unterschiede.

### Editorische Einzelentscheidungen (manuelle Goldwahl)

Bei echten 3-Wege-Konflikten, die das Votum nicht auflöst, werden Entscheidungen in
`MANUAL_GOLD` (in `goldstandard.py`) festgehalten und in der Tabelle als `MANUELL` markiert:

| Par | Lemma | Entscheidung | Begründung |
|-----|-------|--------------|------------|
| 29 | sēnts | **swints** (Prusaspira, swint-Stamm) für alle m/f/n-Zellen | swint- ist im Korpus am weitesten verbreitet; Tabula `sēnt-` und Twanksta `swent-` verworfen. |
| 54 | pekūri | **maskulines Prusaspira-Paradigma** (`pekūr-`) | Mažiulis widerlegt die Tabula-Formen: die weiche Endung `-jas` (Twanksta) entspricht regelhaft `-es` (Prusaspira), nicht Tabulas `-is`. Daher Prusaspira-Maskulinum (ū-Stamm; Twanksta-`pekār-` mit ā verworfen). Nur maskulin — die femininen Formen in Prusaspira/Twanksta sind Parsing-Zufallsfunde, die nicht zu Klasse 54 gehören, und werden verworfen. Dat sg = `pekūrei` (zellenspezifisch; `-ei` wie bei allen anderen Lemmata der Klasse 54, statt Prusaspiras `pekūŗu`). |

## Module (`src/prussian/`)

| Modul | Aufgabe |
|--------|---------|
| `fetch/fetch_prusaspira.py` | Lädt Flexionstabellen von prusaspira.org |
| `fetch/fetch_verb_data.py` | Lädt Verbformen (beide Quellen) |
| `fetch/lookup_prusaspira*.py` | Lemma-Lookup in `twanksta_entries.json` (+ Fuzzy) |
| `compare/compare_paradigms.py` | Vergleich tabula vs. prusaspira |
| `compare/compare_sources.py` | 3-Wege-Vergleich → `data/derived/vergleich.{html,json}` |
| `compare/compare_verbs.py` | dito für Verben |
| `compare/extract_paradigms.py` | Extrahiert Paradigmen aus `tabula.html` |
| `compare/extract_participles.py` | Extrahiert Partizipien/Modi aus den Rohabzügen |
| `gold/goldstandard.py` | Formauswahl aus `vergleich.json` → `data/gold/` |
| `gold/goldstandard_verbs.py` | dito für Verben |
| `gold/accent.py` | Leitet das Akzentmodell ab → `accent_model.json` (s. `docs/AKZENT.md`) |
| `gold/{analyze,validate}_participles.py` | Partizip-Auswertung (Vorarbeit nächster Schritt) |
| `fst/entries.py` | Goldstandard + Wortliste → FST-Einträge (Routing, Archiphonem-Detektion) |
| `fst/lexd_gen.py` | Einträge → `build/morphotactics.lexd` (Marker M/S/J/V) |
| `fst/rules.py` | Akzent-/Palatalisierungs-/Varianten-Regeln (pyfoma-Rewrite) |
| `fst/build.py` | Komposition → `build/analyser.fst` + `build/lenient.fst` |
| `fst/gen_check.py` | Validiert Generierung gegen alle 967 Gold-Zellen + 18 Parallelformen |
| `fst/match_forms.py` | Korpus-Coverage gegen `twanksta_entries.json` |
| `fst/analyze.py` | CLI: Wörter analysieren (Standard + nachsichtig) |

## FST-Modell

`python -m prussian.fst.build` erzeugt bidirektionale FSTs für Nominal-
(P9–P70) und Verbalparadigmen (P71–P144, Präs/Prät/Inf). Architektur:

```
build/morphotactics.lexd   Morphotaktik (lexd): Stämme genau 1×, Endungen 1×
        ∘  rules.py        Akzent- + Palatalisierungsregeln (pyfoma-Rewrite)
        =  analyser.fst    Standard-Orthographie ↔ +Tags
        ∘  V-Zeilen+Regeln Twanksta-j-Schreibung, elektr-/elaktr-
        =  lenient.fst     akzeptiert Quellvarianten → Standardanalyse
```

Die Morphotaktik trägt auf der Unterseite **Marker**, die die Regelschicht
auflöst und tilgt:

| Marker | Position | Bedeutung |
|--------|----------|-----------|
| `M` | vor dem Stamm | Lexem ist Mobile (Akzentklasse) |
| `S` | vor der Endung | Endung ist stark (zieht den Akzent) |
| `J` | vor der Endung | Endung palatalisiert den Stammauslaut (`g→ģ` …) |
| `V` | vor der Endung | Twanksta-Orthographievariante (nur in `lenient.fst`) |
| `A E I O U` | im Stamm | Archiphonem: Vokal alterniert lang/kurz |

**Akzentmodell (Rinkevičius 2009, hergeleitet in `docs/AKZENT.md`):**
Akzent = erstes starkes Morphem. Barytona (starker Stamm) tragen das
Makron in allen Zellen; Mobilia (`M`) kürzen das Stamm-Archiphonem vor
starken Endungen (`S`): `MmIstan → mīstan`, aber `MmIstSāi → mistāi`.
Das Modell deckt 100 % der 967 Goldstandard-Zellen ab
(`data/gold/accent_model.json`, 0 Exceptions).

**Tagset (Giella flat-plus Format):**
```
+N +A +Pron +Num +V  +Msc +Fem +Neut  +Sg +Pl  +Nom +Gen +Dat +Acc
+Inf +Prs +Prt +1Sg +2Sg +3 +1Pl +2Pl  +Def +Superl +Adv +Comp +Pos
```
Beispiel: `wāiks+N+Msc+Sg+Nom` → `wāiks`; `analyse("kūgjan")` über
`lenient.fst` → `kūgis+N+Msc+Sg+Acc`.

**HFST-nativer Paralleler Zweig:** Dieselbe Sprachbeschreibung wird zusätzlich
durchgängig in HFST komponiert (lexc-Lexikon ∘ Phonologie-/spellrelax-Regeln),
mit generalisierenden Regeln statt aufgezählter V-Zeilen. Volle Parität mit
dem pyfoma-Zweig (1471/1471 nominale Gold-Zellen). Bau: `scripts/build_hfst.sh`,
Details in [`docs/HFST_BRANCH.md`](docs/HFST_BRANCH.md). lexd ist Apertium-
kompatibel, die twolc-Äquivalente der Regeln stehen in `docs/ORTHO_RULES.md` §4.

**Doublettenformen / Parallelformen (Pronomina):**
Einige pronominale Neutrum-Zellen (P11 stas, P16 subs, P18 kits, P21 aīns —
18 Zellen insgesamt) haben im Goldstandard zwei gleichwertige Formen, im
Twanksta-`/`-Format notiert (z. B. `a/stan`). **Konvention: erster Teil =
Standardfall (echtes Suffix), zweiter Teil = literale Vollform-Variante.**

Der FST erzeugt beide als **Parallelformen** (bidirektional):
```
generate(stas+N+Neut+Sg+Nom) → ['sta', 'stan']
analyze('sta')  → … stas+N+Neut+Sg+Nom
analyze('stan') → … stas+N+Neut+Sg+Nom
```
Umsetzung in `src/prussian/fst/lexd_gen.py`: `split_suffix()` trennt die
Zelle; der Standard laeuft durch die normale Stamm+Suffix-Mechanik, die
Variante wird als literale `upper:lower`-Vollform in ein eigenes
`LEXICON Variants` emittiert. Ein Guard
(`variant.startswith(resolve_stem(stamm, …))`) verhindert, dass die
lemma-spezifische Variante faelschlich auf Geschwister-Lemmata derselben Klasse
(z. B. eraīns, jūss) vererbt wird. Das Goldformat behaelt `/` als Quellnotation.

**Validierung:** `src/prussian/fst/gen_check.py` generiert alle 967 Zellen aus
dem FST und vergleicht sie mit den erwarteten Formen aus `goldstandard.json`.
Ergebnis: **967/967 Standard-Zellen exakt** (100 %) **+ 18/18 Parallelformen**;
dazu 872/872 Verbzellen (`tests/`).

> **Hinweis zur Aussagekraft:** `gen_check` misst die **interne Konsistenz** —
> der FST wird gegen denselben Goldstandard geprüft, aus dem er gebaut wurde;
> 100 % bedeutet hier *implementatorische Korrektheit*, **keine** unabhängige
> linguistische Validierung. Die externen Maße sind die Wortlisten- und
> Korpus-Coverage (`report/dict_coverage.py`, `report/corpus_coverage.py`,
> Tests `test_wordlist_coverage.py` / `test_tatoeba_coverage.py`).

## Setup / externe Daten

Aus Platzgruenden **nicht** im Repo (per `.gitignore`); separat beziehen und
unter `data/external/` ablegen:

| Datei | Quelle / Zweck |
|-------|----------------|
| `data/external/twanksta_entries.json` (24 MB) | Twanksta-Einträge mit Stichwortliste, Übersetzungen (6 Sprachen), Deklinationstabellen. |
| `data/external/prusaspira_entries.json` (17 MB) | Prusaspira-Einträge mit Stichwortliste, Übersetzungen, Deklinationstabellen. |

Ebenfalls ignoriert (regenerierbar bzw. read-only Referenz):
- `prusaspira/`, `twanksta/`, `corpus/` — gefetchte Korpora (1 req/s, via
  `prussian.fetch` neu erzeugbar).
- `build/` — vollstaendig aus `data/gold/` + `data/external/` generiert.
- `lang-lit/`, `lang-lav/`, `lang-fao/` — optionale Giella-Referenzklone.

Aufbau (nach `uv sync`):
```
uv run python -m prussian.fst.build              # → build/analyser.fst, build/lenient.fst
uv run python -m prussian.fst.build --gold-only  # schneller Testbau ohne Wortliste
uv run python src/prussian/fst/gen_check.py      # validiert: 967/967 Zellen
uv run python src/prussian/gold/accent.py        # Akzentmodell neu ableiten
```

## Struktur

```
data/sources/      tabula.html, gramm.htm           Rohquellen (committed)
data/external/     twanksta_entries.json, prusaspira_entries.json   [ignoriert]
data/derived/      vergleich*.{json,html}           3-Wege-Vergleich
data/gold/         goldstandard*.json, GOLDSTANDARD*.md, accent_model.json
src/prussian/      fetch/ compare/ gold/ fst/       Pipeline-Module (s. o.)
docs/              AKZENT.md, ORTHO_RULES.md, PROVENANCE.md, references.md, …
build/             morphotactics.lexd, analyser.fst, lenient.fst   [generiert]
tests/             pytest-Suite
```
