# Prussian Foma

Vergleich der altpreußischen Paradigmendaten aus drei Quellen mit
Finite-State-Transducer-Analyse (experimentell, PyFoma).

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
Wörterbuch- und Flexionsdaten aus `prussian_dictionary.json`
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
       compare_sources.py
                │
        ┌───────┴────────┐
        ▼                ▼
  vergleich.html    vergleich.json   (roh, ohne Matching-Annotation)
                         │
                         ▼
                  goldstandard.py
                         │
                 ┌───────┴────────┐
                 ▼                ▼
           GOLDSTANDARD.md   goldstandard.json
           (Review/Tabelle)  (FST-Eingabe: Stamm + Suffixe)
                                 │
                                 ▼
                         fst/build_fst.py
                                 │
                     ┌───────────┼───────────┐
                     ▼           ▼           ▼
              Giella-Dateien  nominals.lexd  nominals.fst
              (fst/morphology/ (PyFoma lexd) (kompilierter
               root.lexc,                    FST)
               stems/nouns.lexc,
               affixes/nouns.lexc,           │
               phonology.twolc)              ▼
                                        fst/gen_check.py
                                        (919/919 Zellen ✓)
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

## Skripte

| Skript | Aufgabe |
|--------|---------|
| `fetch_prusaspira.py` | Lädt Flexionstabellen von prusaspira.org |
| `lookup_prusaspira.py` | Schlägt Lemmata in `prussian_dictionary.json` nach |
| `lookup_prusaspira_fuzzy.py` | Zweiter Durchlauf mit Fuzzy- und manuellem Matching |
| `twanksta_api_check.py` | Validierung der twanksta-Treffer per API |
| `compare_paradigms.py` | Vergleich tabula vs. prusaspira (ABGLEICH.md) |
| `compare_sources.py` | 3-Wege-Vergleich → `vergleich.html` + `vergleich.json` |
| `goldstandard.py` | Auswertung/Formauswahl aus `vergleich.json` → `GOLDSTANDARD.md` + `goldstandard.json` |
| `extract_paradigms.py` | Extrahiert Paradigmen aus `tabula.html` |
| `fst/build_fst.py` | Erzeugt Giella-`.lexc`-Dateien + `phonology.twolc` + `nominals.lexd`, kompiliert FST |
| `fst/gen_check.py` | Validiert FST-Generierung gegen alle 919 Gold-Zellen + 18 Parallelformen (100 % Match, `+Tag`-Format) |

## FST-Modell

`fst/build_fst.py` erzeugt einen bidirektionalen FST fuer die Nominalparadigmen
(Substantive, Paradigmen 9–70). Die Ausgabe folgt **Giella-Konventionen**
(vgl. `lang-lav/src/fst/morphology/`) fuer einen spaeteren hfst-lexc/twolc-Port —
die Verzeichnisstruktur unter `fst/` spiegelt diese bewusst.

**Zwei-Ausgabe-Strategie:**

1. **Kanonische Giella-Dateien** (fuer hfst-Port, unter `fst/morphology/`):
   - `root.lexc` — `Multichar_Symbols`, `LEXICON Root` → Nouns
   - `stems/nouns.lexc` — Lemma+Paradigma mit Archiphonem-Notation `{A}`
   - `affixes/nouns.lexc` — Flexionsendungen mit `%^JPal` / `%^VowS`-Markern
   - `phonology.twolc` — 4 twolc-Regelgruppen (Default-Laengung, Kuerzung vor
     `%^VowS`, Palatalisierung vor `%^JPal`, Marker-Tilgung)

2. **PyFoma-kompilierter FST** (prae-aufgeloeste Phonologie, unter `fst/`):
   - `nominals.lexd` — Lexd-Grammatik mit aufgeloesten Vokalen/Palatalen
   - `nominals.fst` — Bidirektionaler FST (849 Zustaende)

**Tagset (Giella flat-plus Format):**
```
+N +Msc +Fem +Neut  +Sg +Pl  +Nom +Gen +Dat +Acc
```
Beispiel: `wāiks+N+Msc+Sg+Nom` → `wāiks`

**Marker (Giella-konform):**
| Marker | Bedeutung | Regel |
|--------|-----------|-------|
| `%^JPal` | J-Palatalisierung | `g:ģ <=> _ %^JPal: ;` |
| `%^VowS` | Vokalkuerzung | `{A}:a <=> _ ?* %^VowS: ;` |

**Akzentmodell (unser, nicht in Giella):**
- Archiphonem `{A}` `{E}` `{I}` `{O}` `{U}` im Stamm
- Default: Langvokal (betont=True, kein `%^VowS`-Marker)
- `%^VowS`-Marker im Affix → Kurzvokal (betont=False)

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
Umsetzung in `fst/build_fst.py`: `split_suffix()` trennt die Zelle; der Standard
laeuft durch die normale Stamm+Suffix-Mechanik, die Variante wird als literale
`upper:lower`-Vollform in ein eigenes `LEXICON Variants` emittiert. Ein Guard
(`variant.startswith(resolve_stem(stamm, …))`) verhindert, dass die
lemma-spezifische Variante faelschlich auf Geschwister-Lemmata derselben Klasse
(z. B. eraīns, jūss) vererbt wird. Das Goldformat behaelt `/` als Quellnotation;
das kanonische `affixes/nouns.lexc` enthaelt nur den Standardteil (die Vollform
ist als reines Affix nicht darstellbar — sie lebt nur im kompilierten FST).

**Validierung:** `fst/gen_check.py` generiert alle 919 Zellen aus dem FST und
vergleicht sie mit den erwarteten Formen aus `goldstandard.json`.
Ergebnis: **919/919 Standard-Zellen exakt** (100 %) **+ 18/18 Parallelformen**.

## Setup / externe Daten

Aus Platzgruenden **nicht** im Repo (per `.gitignore`); separat beziehen und ins
Wurzelverzeichnis legen:

| Datei | Quelle / Zweck |
|-------|----------------|
| `wordlist.json` (2,2 MB) | Twanksta-Wortliste mit Paradigmen-Nummern; **noetig** fuer `fst/build_fst.py` (Stamm-Extraktion P32–67). |
| `prussian_dictionary.json` (35 MB) | Twanksta-Woerterbuch-Export; nur fuer `lookup_prusaspira*.py` / `twanksta_api_check.py`. |

Ebenfalls ignoriert (regenerierbar bzw. read-only Referenz):
- `prusaspira/`, `twanksta/` — gefetchte Korpora (1 req/s, via `fetch_prusaspira.py`
  bzw. `twanksta_api_check.py` neu erzeugbar).
- `fst/nominals.*`, `fst/morphology/` — vollstaendig aus `goldstandard.json` +
  `wordlist.json` generiert (`uv run python fst/build_fst.py`).
- `lang-lit/`, `lang-lav/` — optionale Giella-Referenzklone (eigenes `.git`).

Aufbau (nach `uv sync`):
```
uv run python fst/build_fst.py    # erzeugt fst/morphology/* + fst/nominals.*
uv run python fst/gen_check.py    # validiert: 919/919 Zellen
```

## Struktur

```
vergleich.html                   3-Wege-Vergleichstabelle
vergleich.json                   Rohe geparste Formen pro Quelle (FST-Eingabe)
GOLDSTANDARD.md                  Goldstandard-Auswahl je Inflektionszelle
goldstandard.json                FST-Eingabe: Liste, Eintrag pro (Paradigma, Genus)
fst/build_fst.py                 Generator (Giella-Dateien + lexd + kompilierter FST)
fst/gen_check.py                 Validierung gegen alle 919 Gold-Zellen
fst/morphology/root.lexc         Giella Root-Lexicon (Multichar_Symbols + Root)   [generiert]
fst/morphology/stems/nouns.lexc  Giella Noun-Stem-Lexicon ({A}-Archiphoneme)      [generiert]
fst/morphology/affixes/nouns.lexc Giella Noun-Affix-Lexicon (%^JPal/%^VowS)        [generiert]
fst/morphology/phonology.twolc   Giella Twolc-Phonologie (4 Regelgruppen)         [generiert]
fst/nominals.lexd                PyFoma Lexd-Grammatik (prae-aufgeloest)          [generiert]
fst/nominals.fst                 Kompilierter FST (PyFoma)                        [generiert]
fst/nominals.att                 FST im AT&T-Textformat                           [generiert]
prusaspira/{n}_{lemma}.{txt,html} Gefetchte Prusaspira-Tabellen                   [ignoriert]
twanksta/{n}_{lemma}/lemma.json  Woerterbuch-Treffer                             [ignoriert]
```
