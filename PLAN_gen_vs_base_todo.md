# TODO: Abweichungen gen/ ↔ base.fst (Twanksta)

Werkzeug: `uv run python gen/deviation_report.py` (Referenz = `build/base.gen.hfstol`,
der Generierungs-Zweig der Vollform-LUT `build/base.fst`). Jede Zeile unten ist an
echten Slots verifiziert; Zahlen = betroffene Slots bzw. Lemmata.

Grundraster des Reports: pro Analyse-String vergleicht er die gen-Oberflächenmenge mit
der base-Menge → **AGREE / VARIANT** (Mengen überlappen) **/ KONFLIKT** (disjunkt, echter
Formfehler) **/ GEN_GAP / EXTRA** (base hat keinen Pfad für die Analyse). Gesamt ~189k
Slots, ~166,6k AGREE. Die echten Fehler stecken in KONFLIKT; VARIANT + EXTRA sind
großteils Konventions-/Anreicherungsfragen (siehe unten).

---

## A. Adverb-Nachtrag prüfen — Verdacht: fehlerhaft implementiert
- Ganze Adverb-Kategorie (3042 Slots) fällt unter „EXTRA": gen lemmatisiert das Adverb
  unter dem **Adjektiv**-Lemma (`begalbis+Adv → begalbjai`), base unter dem **Adverb**-
  Lemma (`begalbjai+Adv`). Gleiche Oberfläche, andere Analyse → Konvention klären.
- **3 echte Formfehler:** `etkūmps / sklāits / spārts +Adv` — gen hängt `-ai` an
  (`etkūmpai`), base hat das bare Adverb `etkūmps`. → als Ausnahme (bare `-s`-Adverbien)
  in `LEXICON AdvExcept` (gen/adj.lexc) aufnehmen oder Regel korrigieren.
- Herkunft: Adverb-Block kam mit `8370cff` (Phase 1+2). Vor Fix klären, ob die
  Lemma-Konvention (Adj- vs. Adv-Lemma) überhaupt so gewollt ist.

## B. `/`-Varianten: gen erzeugt nur EINE von zwei attestierten Formen
base bietet je eine `-j-`-Nebenform, gen nicht (VARIANT, ~10,3k Slots — überwiegend Partizip):
- **Partizip-Präs** (9864): kurz `-ints/-tas/-tan…` + lang `-ānts…`; gen nur lang
  (`ainapreslinānts` statt `ainapreslints/ainapreslinānts`). Betrifft praktisch alle Verben.
- **Nomen istem/nstem Pl.Nom** (48): `-jai`-Nebenform fehlt (`lukkes` statt `lukkes/lukkjai`,
  `aūgmenes` statt `aūgmenes/aūgmenjai`).
- **Adj Neut Sg Nom/Acc** (382): `-jan`-Nebenform fehlt (`instrawingi` statt
  `instrawingi/instrawingjan`).
- → Entscheidung: soll gen die zweite (palatalisierte) Variante mitgenerieren? Wenn ja,
  Endungslexika um die `-j-`-Alternative erweitern.

## C. Nomen Nom.Sg. lexikalisch falsch reduziert (KONFLIKT)
- **astem** (43 Lemmata): gen über-reduziert, wo die reale Form voll bleibt —
  `bliccis→blics`, `deggals→degls`, `Mikēlis→Mikēls`, `diwūlis→diwūls`
  (Degemination/Synkope/`-is→-s`). Nom.Sg.-Endungswahl ist lexikalisch.
- **ustem** (9): gen über-generiert `-us`+Gemination, wo real bare `-s`:
  `aps→appus`, `keps→keppus`, `sals→sallus`, `pōrts→pōrttus`. (Umgekehrt `kōmbus→kōmbs`.)
- **aastem** (15): `-snas`-Nomina — gen dropt Nom.Sg. `-s` und setzt `-ā`
  (`graudīnsnas→graudīnsna`, `glabāsnas→glabāsna`, `bēgas→begā`).
- **jostem** (4): `aulemli→aulemlis`, `mēslasgrambali→…lis` — gen hängt `-s` an, real bare `-i`.

## D. Diakritika-/Normalisierungs-Divergenz (mit Punkt H zusammen behandeln)
- gen **bewahrt** lexikalische Grave/Palatal, base **normalisiert weg**:
  `ensàkninsnā`↔`ensakninsnā`, `izpiĺninsnā`↔`izpilninsnā`, `iĺgisnā`↔`ilgisnā`.
- Macron/Diphthong in einzelnen Slots: `Maūraws→Mauraws`, `aītagenīs→aitagenīs`,
  `sarpīs→sarpis`; `-pils`-Namen Pl.Dat `Instrāpilimmans`↔gen `Instrapilimmans`.
- → welche Seite ist kanonisch? Gehört zur Anreicherungs-/Normalisierungs-Recherche (H).

## E. Verb-Endungen (KONFLIKT) — Detail jetzt in gen/DEVIATIONS.md
- **Prät P1/P2 Pl (`baddamai↔baddimai`): ERLEDIGT** — Par.87 per Nasal-Regel
  (Stamm auf Nasal+d → -amai, sonst -imai), `_resolve_p87` in coverage_verb.py.
- **Optativ P3 `-sei`, Cluster-Assimilation:** OFFEN — gen `aukandsei / auskrāidsei`,
  base `aukansei / auskrāisei` (nd/d + sei → n/…). Echte Regel (accent.regex). ~25 Slots.
- **Par.136 Opt-Makron** (`kalbīsei↔kalbisei`, 19) + **Par.81 ē/ī-Zellen** (36):
  Datenverdacht → prüfen/Override. Alles in gen/DEVIATIONS.md gelistet.

## F. Adjektiv Nom.Sg. + Endungen (KONFLIKT, 45 Lemmata)
- `-iskas`-Lehnadjektive behalten voll (`elektrōmagnētiskas`, `chrōniskas`), gen `-sks`.
- Mobile `-ars`-Adjektive über-synkopiert: `astars→astrs`, `anzars→anzrs`, `dabbars→dabrs`.
- Pl.Dat Doppel-`ma`: `auktimmamans`↔base `auktimmans`; Neut.Pl `bass→basāi` (Degem) ↔ `bassāi`.

## G. Partizip-Präs Präsensstamm falsch (KONFLIKT, 3 Lemmata)
- `gestwei`: gen `gesānts`, base Nasal-Infix `gēndants`. Präsensstamm-Quelle stimmt nicht
  (Infix `-nd-` fehlt). Wenige Lemmata — Drei-Prinzipalformen-Stamm prüfen.

## H. RESEARCH: Anreicherungs-Tags (+PropN, +PPpēr …) & Normalisierung
- Der große „EXTRA"-Block ist **kein** echter Deckungsunterschied, sondern
  **Anreicherungstag-Mismatch**: base trägt Zusatz-Tags, die gen nicht emittiert, daher
  matcht der Analyse-String nicht und base.gen liefert ∅. Verifiziert:
  - Proper Nouns: base `Angōla+PropN+Fem+Sg+Nom`, gen `Angōla+N+…` (Nomen-EXTRA ~2700, Adj 1896).
  - Preverb/Partikel: base `laikānts = laikātun+V+Part+Pres+…+PPpēr`, gen ohne `+PPpēr`
    (Partizip-EXTRA 2256). Finite Formen von `laikātun` fehlen in base wirklich (Verb-EXTRA 1584).
- **Vom User angeregt:** recherchieren, wie andere CG3-Pipelines (Apertium, GiellaLT …)
  Eigennamen-Tags und Diakritika-Normalisierung handhaben, bevor eine Konvention für gen/
  festgelegt wird. Danach: soll gen `+PropN`/`+PPpēr` mitführen, oder bleibt das
  analyse-seitig getrennt?
- Bis dahin: EXTRA nicht als Fehler werten (Report weist es separat aus).

---

## Reihenfolge (Vorschlag)
Erst die eindeutigen Formfehler: **A** (Adverb, klein + sichtbar), **E/F** (Verb-/Adj-
Endungen, regelhaft), **C** (Nomen Nom.Sg.), **G** (3 Partizipien). Dann Grundsatz-
entscheidungen: **B** (`/`-Varianten mitgenerieren?), **H** (Anreicherung/Normalisierung,
Research) — **D** hängt an H.
