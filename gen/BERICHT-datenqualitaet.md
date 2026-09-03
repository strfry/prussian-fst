# Datenqualitäts-Bericht — Twanksta-Nomenflexion

**An:** Autor/Pflege von `twanksta_entries.json`
**Von:** generativer FST-Prototyp (`fst/gen/`), Stand 2026-09-03
**Grundlage:** nicht-zirkulärer Abgleich der Flexionstabellen gegen einen
handgeschriebenen generativen FST (Stamm + Paradigmenendung + eine
Akzent-Morphophonologiestufe).

## Methode

Für jedes Nomen wird der oblique Stamm mechanisch aus dem Gen.Sg. abgeleitet
(Gen.Sg. minus Klassenendung) und über handformulierte Endungssätze +
Akzentregel wieder zu allen acht Kasusformen expandiert. Die Endungen/Regeln
stammen **nicht** aus den Daten, sondern aus einer linguistischen Hypothese pro
Twanksta-Paradigmennummer — der Abgleich ist damit ein echter Deckungstest, keine
Selbstkonsistenz. Reproduzierbar mit `uv run python gen/data_report.py`.

Modelliert sind die fünf großen Stammfamilien (Nomen); es fehlen nur wenige kleine
irreguläre Paradigmen (39, 51) und die Konsonant-/n-Stämme 61/63/68/69:

| Familie | Paradigmen | Formen | Deckung |
|---|---|---|---|
| i-Stämme | 52/53/54/56/57/58/60 | 8432 | 99.4 % |
| a-Stämme | 32/35/36 | 16984 | 99.7 % |
| u-Stämme | 42/43/44 | 480 | 97.9 % |
| jo-Stämme | 40/41/37/38 | 5672 | 99.7 % |
| ā/jā/ī-Stämme (fem) | 45/46/50 | 11856 | 99.8 % |
| **gesamt** | | **43424** | **99.64 %** |

Die 156 Abweichungen zerfallen in **echte Datenfehler** (unten, Teil A) und
**systematische Morphophonologie**, die der Prototyp noch nicht abbildet (Teil B,
keine Fehler — nur zur Kenntnis bzw. als Konsistenzfrage).

---

## A. Konkrete Datenfehler (Korrektur empfohlen)

### A1. Voll-invariante Flexionstabellen (36 Einträge)

Alle acht Kasus == Lemma — die Deklinationstabelle wurde offenbar nie gefüllt
(sie wiederholt nur das Stichwort). Ein deklinierendes Nomen kann das nicht sein.
Nach Paradigma:

- **p52** (7): `Dānija` `animācija` `federācija` `galiōnan` `stabenīkista` `ēdawa` `wakcinacīja`
- **p49** (6): `lāukiskan` `priwātiskan` `pusiwadūniskan` `trinewīngiskan` `wargaprātiskan` `āustewingiskan`
- **p40** (4): `geōgrafs` `māgiks` `slidenīks` `šlūzims`
- **p45** (4): `plastilīns` `wītwagā` `zentlawingiskan` `zēisnā`
- **p35** (3): `Sēināi` `saldiskāi` `sinōnimas`
- **p44** (2): `Marokko` `sekkan` · **p32** (2): `Nōrwegija` `kukurūza` · **p46** (2): `gazzasgara` `prasijjā`
- je 1: `brūnagalwa`[48] `izmāitint`[69] `knāistis`[68] `kāuplis`[53] `nunni`[42] `swasri`[51]

Manche Fremdwörter (`Marokko`, `Dānija`) sind evtl. bewusst indeklinabel — dann
wäre aber die Paradigmenzuweisung irreführend. Die nativ geformten Fälle
(`geōgrafs`, `māgiks`, `slidenīks`, `sinōnimas`, `kāuplis`) sind sehr
wahrscheinlich schlicht unbefüllt.

### A2. Wortart-/Genus-Fehlklassifikation

- **`izmāitint`** [p69] — Gloss *„lost"*, Genus leer, endet auf `-int`: das ist ein
  **Verb/Partizip**, kein Nomen. Voll-invariante Tabelle (siehe A1).
- **`plastilīns`** [p45, **fem**] — maskulin geformt (`-īns`); p45 ist die fem.
  ā-Familie. Genus/Paradigma passen nicht zur Form.

### A3. Encoding-Schaden

- **`māršs`** [p32] — die obliquen Zellen enthalten ein **U+FFFD REPLACEMENT
  CHARACTER**: `Gen.Sg. 'marš<FFFD>as'`, `Nom.Pl. 'marš<FFFD>ai'` … Der Nom.Sg.
  `māršs` ist intakt. Erwartet wäre `māršas / māršai / …`. (Einziger solcher Fall
  im Nomen-Bestand.)

### A4. Einzelzellen-Fehler

- **`kōmbus`** [p43, u-Stamm] — Gen.Pl. steht als `kōmbus`, müsste `kōmbun` sein
  (offenbar aus dem Nom.Sg. kopiert). Übrige Zellen korrekt.
- **`fōrum`** [p35, neut] — lateinisches Lehnwort: Nom.Sg. `-um` statt `-an`, und
  Gen.Pl. steht als `fōrum` (= Nom.Sg.) statt `fōran`. Gemischtes Paradigma
  (Nom.Sg. lateinisch, Obliquus nativ a-Stamm).

---

## B. Systematische Morphophonologie (keine Fehler)

Diese Fälle sind sprachlich regulär; der Prototyp bildet sie noch nicht (voll) ab.
Für die Datenpflege v. a. als **Konsistenzfrage** interessant.

### B1. Nom.Sg. `-s` vs `-is`/`-us` (52 Fälle) — lexikalisch

Bei den „schweren" Nom.Sg.-Klassen (i-/u-Stämme) erscheint mal die synkopierte
Form `-s`, mal der erhaltene Themavokal `-is`/`-us`. Der Split ist **nicht** aus
dem Stamm ableitbar: mehrsilbige Stämme nehmen fast durchweg `-s`, aber unter den
einsilbigen treten beide auf, teils bei gleichem Auslaut (`grūsts` vs `glāstis`,
beide `-st`). Erhalten wird `-is` u. a. bei echten i-Stämmen (`anglis`, `saknis`,
`lūsis`) und Lehnwörtern (`Antarktis`, `Arktis`); synkopiert bei `nakts`, `dānts`,
`ants`. → sinnvoll als lexikalisches Merkmal, nicht als Regel. **Kein Fehler**,
aber prüfenswert, ob die Zuordnung `-s`/`-is` überall gewollt ist.

### B2. Umfang der Betonungs-Reduktion in mobilen Slots — inkonsistent

In den akzentverschobenen Slots (Nom.Pl./Dat.Pl.) verliert der Stamm sein
schweres Merkmal. Die Daten sind aber uneinheitlich, **wie viel** reduziert:

- Mehrsilbige Komposita reduzieren regelmäßig **alle** Makrone:
  `stāminadeīkt-` → `staminadeiktāi`, `drāugiprōfesinisk-` → `draugiprofesiniskāi`.
- Einige Eigennamen/Zahlwörter behalten die **prätonische** Länge:
  `Instrāpil-` → `Instrāpilimmans` (das prätonische `ā` bleibt), ebenso
  `Mētapils`, `Rāistanpils`, `astōnadesīmt-`.

Das ist derselbe morphologische Slot mit gegensätzlichem Verhalten. Entweder ist
die prätonische Länge in den `-pils`-Namen eine bewusste (Eigennamen-)Ausnahme —
oder eine Inkonsistenz in der Betonungsmarkierung. **Bitte prüfen**, welches das
gewünschte Muster ist.

### B3. Erhalt einzelner Geminaten in mobilen Slots

`aupallē` behält `ll` im schweren Slot (`aupallīmans`), wo strukturgleiche Stämme
reduzieren (`nagg-` → `nagīmans`). Ebenso die Zahl-Komposita `trillunks`,
`ketturjalunks` (prätonische Geminate bleibt). Wie B2 betonungsabhängig.

### B4. Gravis-Akzent wird in mobilen Slots getilgt

`ètwartan` → `etwartāi`, `èstiskan` → `estiskāi`, `ensàkninsnā` → `ensakninsnā`,
`izpiĺninsnā` → `izpilninsnā`: der Gravis (`à`/`è`) bzw. das Akut-`ĺ` markiert die
Stammbetonung und verschwindet im akzentverschobenen Slot — regulär, vom Prototyp
noch nicht behandelt (accent.regex kürzt bisher nur Makron/Geminate).

---

## Zusammenfassung

Rund **99,6 %** der Formen (43424) in den fünf großen Stammfamilien sind generativ
aus Stamm + Paradigma + einer Akzentregel exakt reproduzierbar. Die verbleibenden
Abweichungen sind größtenteils reguläre Lexik/Morphophonologie (Teil B). An
**echten Fehlern** fallen v. a. an: ~36 unbefüllte Flexionstabellen (A1), eine
Wortart-Fehlklassifikation (`izmāitint`, A2), ein Encoding-Schaden (`māršs`, A3)
und einzelne Zellfehler (`kōmbus`, `fōrum`, A4).
