# Plan: listenloser Generator + optionale Stammformen (alle POS)

## Kontext

Ziel ist **ein genereller Generierungs-Mechanismus für alle Wortarten** (Nomen,
Adjektive, Adverbien, Verben, Partizipien): aus **Lemma + Paradigma + optionalen
Stammformen** werden alle Flexionsformen erzeugt. Die Grammatik (Endungen/Deklination
je Paradigma) ist datenfrei; lexem-spezifisch sind nur die Stämme.

Die **Verben waren der Forschungsfall**: dort hat die Voruntersuchung gezeigt, dass die
Ableitung aus dem Lemma allein nicht reicht und **optionale Stammformen** (bis zu drei
Prinzipalstämme: Präsens, Präteritum, nonfin) nötig sind — mit Ablaut/Nasal-Infix/
Suppletion. Der Mechanismus (optionale Stämme in den Daten, vom Generator konsumiert)
ist aber **POS-übergreifend uniform**; Nomen brauchen meist 0–1 (den obliquen Stamm),
Verben bis zu 3. Dieser Plan beschreibt den gemeinsamen Mechanismus und die
FST-Integration; Verben sind das durchgearbeitete Beispiel.

Frühere Fassung dieses Plans war verb-zentriert — das war ein Missverständnis des
Scopes und ist hiermit korrigiert.

## 0. Grundentscheidungen (POS-übergreifend, abgestimmt)

0.1 **Quelle & Gold = Roh-HTML.** Alle Formen über `corpus/scripts/twanksta_parse.py:
parse_forms` aus `corpus/raw/twanksta/forms/{paradigm}_{word}.html` — nicht
`twanksta_entries.json`. Regressions-/Abnahme-Gold ist dasselbe `raw/` (zellweise,
Varianten als Menge). **Nicht** `cache_live/` (Blackbox-Experiment, nicht für reale
Lemmata).

0.2 **Darstellung = ein Vokabular: DMLex `inflectedForm` + `inflectedTag`.** Jede
Generator-Zelle ist ein `inflectedForm` (Wert = Oberfläche) mit `tag` = kanonischer Slot.
Kein `stem:`-Block, kein `override:/slot:`-Knoten, kein `label`, kein `example`. Ein
**Stamm** ist der `inflectedForm` am **Seed-Slot**; ein **Override** der an einem
Nicht-Seed-Slot. Seed/Override ist eine Eigenschaft des **Paradigmas** (welche Slots
Seeds sind), nicht des Eintrags → kein Rollen-Marker in den Daten. Reflexiv/Varianten:
Wert ohne `" si"`; Varianten = mehrere `inflectedForm` mit gleichem `tag`.

0.3 **Kanonisches Slot-Vokabular = `corpus/MAPPING.md` §4.2 (`inflectedFormTags`),
POS-übergreifend.** Auszug:
- Nomen: `sg.nom … pl.acc`.
- Adjektiv: `msc.sg.nom … neu.pl.acc`, `comp.<g>.<n>.<c>`, `superl.<g>.<n>.<c>`; Adverb
  `adv`, `adv.comp`, `adv.superl`.
- Verb: `prs.<pn>` `prt.<pn>` `subj.<pn>` (pn ∈ `sg1,sg2,sp3,pl1,pl2`; SP3 = numerus-
  fusionierte 3. Person), `opt`, `imprt.sg2`, `imprt.pl2`.
- Partizip: `part.prs.act.<g>.<n>.<c>`, `part.prf.act.<g>.<n>.<c>`, `part.prf.pss.<g>.<n>.<c>`
  (Genus-Komponente <g> ∈ `msc/fem/neu`; Passiv = PrcTyp `prf` + Voice `pss`).

Die Slot-Keys sind **Giella-FST-Komponenten**: Person/Num ist fusioniert und in
Giella-Reihenfolge (`sg1 sg2 sp3 pl1 pl2`), POS-Marker steht nicht im Key. Genus ist beim
Nomen ein **Entry-Fakt** (`gender: masc|fem|neut`, voll ausgeschrieben) und steht dort
deshalb nicht im Slot — nur die Slot-Key-Komponente heißt `msc/neu`.

**Seed-Slots je Familie (= heutige `srcmap`/Stammlogik):**
- Nomen (z. B. i-Stamm): `sg.gen` → obliquer Stamm (Header `istem.lexc`: „obliquer Stamm
  = Gen.Sg. minus -is"); `sg.nom` = Lemma.
- Verb: `prs.sp3`, `prt.sp3`, `subj.sp3`; Partizip-Seeds `part.prs.act.msc.sg.nom`,
  `part.prf.act.msc.sg.nom`, `part.prf.pss.msc.sg.nom`.
- Adjektiv/Adverb analog aus der jeweiligen Familienlogik (Adj-Positiv: `msc.sg.gen` →
  obliquer Stamm).

0.4 **Stufenmodell (Stage 0–2), generalisiert.**
- **Stufe 0** — nur Lemma + Paradigma: Stamm/Stämme per **Default-Regel aus dem Lemma**
  je Paradigma. Deckt die reguläre Mehrheit (Nomen ~99,6 %; Verben ~84 %).
- **Stufe 1** — Seed-`inflectedForm`(s) in der NVH, wo die Default-Regel fehlgeht
  (Verb: `prs.sp3`/`prt.sp3`; Nomen: irregulärer obliquer Stamm).
- **Stufe 2** — seltene Zusatz-/Suppletiv-Stämme (Verb: Partizip-Seeds/Suppletiva).
- **Stufe 3** — Rest-Overrides (Nicht-Seed-Slots): in **diesem** Arbeitspaket nur gezählt;
  FST-Verdrahtung ist separat (§6).

0.5 **Analytische Formen = Konstruktion, kein Eintrags-Datum.** Verb-Perfekt/Futur =
`AUX (asmai/wīrst, invariant) + Partizip Prät. Nom.`; eine globale Konstruktionsregel in
der Engine komponiert sie, pro Eintrag nichts gespeichert. Verlustfreiheits-Check:
Aux-Invarianz + Partizip-Komponente = gedumpte Partizip-Nom-Formen. Habitualis fehlt in
den Daten. (Gilt analog für etwaige periphrastische Konstruktionen anderer POS.)

0.6 **`example:` (Belegfaltung) entfällt vorerst** (überambitionierter Legacy-desc-
Auflöser); Roh-HTML bleibt Quelle, jederzeit regenerierbar.

0.7 **Datenheimat & Pipeline.** Roh-HTML ist eingefroren; Ableitung immutable.
- **Fett (corpus, morphologie-frei):** `twanksta_to_dmlex.py` dumpt jede synthetische
  Einwort-Zelle **aller POS** als `inflectedForm`+`tag` → `twanksta_dmlex.full.nvh`.
  (Verb-Teil erledigt, §„Stand".) Kein fst-Import.
- **Lean (fst, Morphologie):** Kompressor (§3) verdichtet zu `twanksta_dmlex.nvh`
  (Seeds + Rest). Die lean NVH geht in den **NVH-nativen Lexonomy-Dict** (danach Heimat).
- **Kein Go** in keiner Phase; fst liest NVH in Python. Fette NVH transient (nicht
  versioniert; Gold = `raw/` + Sample-Fixture).

## 1. Listenloser Basis-Generator (FST-Integration)

Der **wortlistenfreie Basis-Generator** ist der geteilte Kern. **In scope jetzt**, weil
der **Kompressor** (§3) ihn braucht; **später** bedient er auch das **Preview** (§6,
out of scope). Er nimmt **einen** Eintrag (Familie + Paradigma + Stämme) und liefert
dessen Formen — **kein Lexem-Listing, kein Rebuild pro Eintrag**.

**Beobachtung (verifiziert):** jede Familien-Grammatik (`gen/verb.lexc`, `istem.lexc`,
`astem/ustem/jostem/aastem/nstem.lexc`, `adj.lexc`, Adverb) hat die Form
`Root → StemLex(lemma:stem) → AtomLex(tags:ending) → End`. Die **Atom-/Endungs-Lexika
sind bereits datenfrei**; lexem-spezifisch ist nur `StemLex` (heute aus
`coverage_*.py --emit-stems` gebacken). Listenlos = `StemLex` weglassen und den Stamm zur
**Laufzeit** davorsetzen.

**Realisierung (empfohlen):**
1. Pro Familie die **datenfreien Atom-Transducer** einmal aus `gen/<fam>.lexc`
   kompilieren (Grammatik ohne eingespeiste Stammliste). Plus die geteilte
   `gen/accent.regex` → `build/gen-accent.hfst`.
2. Engine `generate(family, paradigm, stems) -> {slot: {forms}}`:
   - Paradigma → `{role → (seed-slot, atom(s))}` (= heutige `PARADIGMS`/`srcmap`, pro
     Familie als Tabelle).
   - pro Rolle: `acceptor(stems[role]) · Atom-FST · accent` → Slot→Formen.
   - rein in-memory (Atom-/Accent-FSTs geladen), keine `lexc`-Kompilierung pro Aufruf.
3. **Reiner Kern, importierbares Python-Modul** (`gen/generator.py`), kein eigenes IO,
   pro **einzelnem** Eintrag. Default-Stammableitung (Stufe 0) je Paradigma lebt hier;
   gelieferte Seeds (Stufe 1/2) überschreiben sie.

**Abgrenzung:** die **Analyse-Richtung** (surface→analysis) und das **volle, listen-
gebackene** Generator-Artefakt (`build/gen.hfstol` mit Lexem-Liste) sind NICHT Teil des
listenlosen Generators — sie gehören zum downstream-Analyzer bzw. zur Override-Overlay
(§6). Der listenlose Generator ist override-frei.

## 2. Pipeline: dumm dumpen → komprimieren (ein Roh-HTML-Parse)

1. **corpus — fett dumpen (alle POS):** jede synthetische Zelle als `inflectedForm`+`tag`
   (§0.2), `paradigm` top-level, kein `example`. (Verb-Dumper steht; auf Nomen/Adjektiv/
   Adverb ausweiten — eigene Parse-Shapes: `declension`, `comparative/superlative`.)
2. **fst — komprimieren (§3):** fette → lean NVH + Statistik je Paradigma + Lint.
3. Perfekt/Futur ausgelassen (§0.5); Partizip-Grid wird nur verworfen, wo die
   Adjektiv-Grammatik es beweisbar reproduziert; Irreguläres (z. B. `-usjan`) bleibt.

## 3. Kompressor

`gen/compress_forms.py` (neu): liest `twanksta_dmlex.full.nvh` (alle POS), ruft je Eintrag
`derive_minimal(family, paradigm, attested)` auf — nutzt den Basis-Generator (§1), um die
**minimalen Seeds** zu finden, die die attestierten Zellen regenerieren; alles sonst
Nicht-Regenerierbare bleibt als Nicht-Seed-`inflectedForm` (Rest-Override). Schreibt lean
NVH + Statistik (Verben/Einträge, benötigte Seed-Felder, Rest-Overrides je Paradigma) +
Lint (Seed = Default, oder Override = generiert → entfernen). **Verlustfrei by
construction** (Nicht-Regenerierbares bleibt stehen).

## 4. Betroffene Dateien / Umsetzung

- `gen/generator.py` (neu): listenloser Basis-Generator (§1), Default-Regeln je Paradigma,
  Paradigma→Rolle→Atom-Tabellen je Familie, NVH-Lesefunktion.
- `gen/compress_forms.py` (neu): Pipeline-Kompressor (§3).
- `gen/coverage_*.py`: Stammquelle auf den Basis-Generator umstellen; bestehende
  Endungs-/Stammlogik bleibt Referenz. Nicht-Zirkularität: Gold = `raw/`.
- `corpus/scripts/twanksta_to_dmlex.py`: Verb-Dump steht; auf übrige POS ausweiten.
- `Makefile`: Basis-Generator-Targets (datenfreie Atom-FSTs je Familie + accent). Der
  volle `gen.hfstol`-Pfad bleibt für §6.
- `gen/DEVIATIONS.md`: Deckungszahlen Stufe 0/1/2 je POS fortschreiben.

## 5. Tests & Abnahme

- **Verlustfreiheit der Kompression:** `generate(lean) == fette NVH` zellweise, alle POS.
- Deckung je POS ≥ heutige Regel-Deckung, gemessen gegen `raw/` (Nomen ~99,6 %,
  Verb ~99,5 % mit Seeds).
- Testmodus **„nur Lemma"** (Stufe 0, keine Seeds) → Stufe-0-Deckung je POS.
- **Analytik-Verlustfreiheit** (§0.5): Perfekt/Futur aus Aux + Partizip komponierbar.
- Analyse-Seite/Tags unverändert (Regressionstest).

## 6. Separat / später (NICHT Teil des listenlosen Generators)

- **Override-Overlay in FST:** Rest-Overrides (Stufe 3) + Editor-Korrekturen als
  Composite/Overlay (`priority_union`) auf das **volle, listen-gebackene** `gen.hfstol`
  gebacken — die zuvor entfernte `emit_overrides`/`punion`-Mechanik, später als eigener
  downstream-Schritt. **Nichts** mit dem listenlosen Generator oder dem Preview.
- **Volles gebackenes Generator-/Analyzer-Artefakt** (Lexem-Liste) für den dictionary.
- **Preview-Microservice** (out of scope jetzt): HTTP-Wrapper um den Basis-Generator
  (§1) fürs Lexonomy-Frontend — `fetchForms({headword, pos, paradigm, stems}) ->
  [{slot, form, source}]`, `source ∈ {rule, stem}`. Override-frei.
- Umzug der NVH-Quelle `full`→Live-Dict-Dump (nur Pfadwechsel).
- Offene morphologische Einzelpunkte: Partizip Prät. Fem.Akk.Sg. `-usjan` vs. `-usin`;
  Optativ-Clusterreduktion Par.87; Verbnummern ohne Endungstafel; einheitliche
  Lemma-/Tag-Konvention Partizipien; Wiederaufnahme `example:`-Belegfaltung.

## Stand (erledigt)

- Fette Verb-NVH erzeugt & verifiziert (opencode/big-pickle): 1917 Verben × 90 Zellen =
  172.530 `inflectedForm`, 12,8 MB, deterministisch; `paradigm` top-level, kein `example`,
  Perfekt/Futur ausgelassen, Reflexiv ohne `si`, Tests grün. → `twanksta_dmlex.full.nvh`.
- fst von Stufe-3-/Legacy-Cruft befreit (emit_overrides/punion, stale Pläne, gen-vs-base-
  Reports); `coverage_gen.py` (Nomen-Engine) bewahrt; Build auf reine Regel-Union
  vereinfacht.
- §1 listenloser Basis-Generator fertig: `gen/generator.py` (POS-übergreifend, Stufe 0–2,
  `generate(pos, paradigm, lemma, stems=, seeds=, gender=)` → dotted Slot-Keys) und
  `gen/atom_fst.py` (245 datenfreie OL-Atome, `make atoms` / `make atom POS=… PARADIGM=…
  ROLE=…`). Stufe-0-Nomenlisten empirisch aus `coverage_gen.py --emit-stems` belegt.
  `tests/test_generator.py`: 120 handverlesene Tests (Slot-Tags, Grammatik-Atomnamen,
  Stammstufen, Formen, Kopierer, Root-Rewrite, Akzentmarker); Gesamtsuite 314 grün.
