# Offene Forschungsfragen — FST-Umbau (Monolith auf Per-Paradigma)

Begleitend zum Integrationsplan (`~/.claude/plans/harmonic-kindling-cocoa.md`).
Nur die **ungeklärten** Punkte — mechanische Schritte stehen im Plan. Jede Frage
nennt: Kontext, die eigentliche Unbekannte, was zu untersuchen ist, und was sie blockiert.

**Stand 2026-10-08:** Q1–Q4, Q6 per Subagent untersucht; Befunde + TODO je Frage unter
„Befund“. Hilfsskripte liegen nur im Session-Scratchpad (nicht persistent).

---

## Q1 — Numeral-Flexionsklassen (größtes Risiko, blockiert WS2)

**Kontext:** `gen/*.lexc` hat Grammatiken nur für aastem/astem/istem/jostem/nstem/ustem/adj/verb.
Numeralia (Twanksta-Paradigmen **21–24**) haben **kein** Atom. Entscheidung: Numeralia sollen
durch die Atome generiert werden (nicht eingefroren).

**Unbekannte:** Lassen sich P21–24 auf vorhandene nominale/adjektivische Stammklassen
abbilden, oder braucht es eine eigene `gen/numeral.lexc`?

### Befund — keine `numeral.lexc`; Numeralia = adj-Familie + `numtype`-Merkmal

- P21–24 sind winzig: **6 Lexeme, 108 Zellen** — P21 aīns/eraīns/niaīns (3G×Sg/Pl×4K),
  P22 abbai, P23 dwāi, P24 trīs (je nur Pl, 3G). Keine Suppletion; P22–24 Pl-defektiv.
- Die meisten Numeralia liegen ohnehin in **Adjektiv-Paradigmen** (25/26/27/69/70: Ordinalia
  `pirms`, P27-Kardinalia `pēnkjai`…): 41 Lexeme, bestehende adj-Atome treffen **95,2 %**
  (845/888 Zellen). Rest ist adj-generisch (P27 Neu.Pl `-jin`-Schwankung, `tīrts` pronominal).
- P21 über AdjMobile: je 18/24 — fehlt genau die **pronominale Sg-Flexion**
  (Gen `-asse/-asses`, Dat `-asmu/-assei`), die auch Pronomina P11/12/17/18 und P70 teilen.
- P22–24: 3 Lexeme, 23 Restzellen (abbai `-ejan/-eimas`, dwāi, trīs `trijjan/trimmans`).
- P21-Neutrum (`aīnase`/`aīnasmu`, Sg-Formen in Neu.Pl-Zellen) sieht nach Twanksta-Datenfehler aus.
- `corpus/REPORT_A/B/C.md` existieren nicht — kein Abhängigkeitsproblem.
- **Blocker im Datenpfad:** `twanksta_to_dmlex.decl_cells` liest `decl`-Tabellen mit drei
  Genusblöcken als `pos: noun` ohne Genus-Tags (3× `sg.nom`). Betrifft P21–24 **und 150
  Einträge in Adj-Paradigmen** (P25–29, 68–70, alle Ordinalia). → Q6 #5 ist dieselbe Ursache.
- Heute-Tags: `gen_lexc.numeral_subtype` liest nur erstes desc-Token → `dwāi/trīs/abbai/…`
  nur `+Num` ohne `+Card`; `astōnjai`, `asms` landen als `+A`, `dessimts` als `+N`.

**TODO**
1. ~~Konverter: `decl` mit m/f/n-Blöcken → `pos: adj` + Genus-Tags~~ **erledigt 2026-10-08** (`_is_gendered_adj_decl`, P≥21; 156 Einträge noun→adj; Pronomina P9–20 bewusst unberührt → Q4).
2. Konverter: `numtype: card|ord`, wenn crd/ord **irgendwo** im desc steht.
3. `gen/adj.lexc`: `LEXICON AdjPronMobInfl` (AdjMobile + pronominaler Sg.Gen/Dat) → P21 ≥21/24.
4. `gen/generator.py`: `_ADJ`-Schleife für Paradigmen ohne adv/cmp/sup öffnen; `("adj","21")`;
   `ADJ_POS_PL_SLOTS` für P22–24 (AdjFixed, Pl-only, Rest Stufe-2-Override).
5. `build_analyzer`: P21–24 → `adj`; `analysis_tags` ersetzt `+A` durch `+Num+Card|+Num+Ord` bei `numtype`.
6. Kompressor-Lauf + Parität gegen eingefrorenes `lexc/numerals.lexc` (61 Lemmata).
7. Twanksta-Datenfrage: P21-Neutrum Absicht oder Fehler?
8. Später: `AdjPronMobInfl` für `tīrts` und Pronomina P11/12/17/18 prüfen.

---

## Q2 — Redesign des `id:`-Feldes

**Kontext:** Die Entry-ID ist aktuell `word|paradigm|encode(desc)` + `#n` bei echter
Kollision (`twanksta_to_dmlex.py:425`). Das war die schnelle Migrationslösung (Natur-Schlüssel,
weil twanksta keine Quell-IDs hat — siehe [[twanksta-dmlex-migration]]). Pipe-getrennt, mit
voll eingebettetem Legacy-`desc`, jetzt als hässlich empfunden.

**Unbekannte:** Soll die ID neu entworfen werden, und wenn ja wie — ohne die
Entry-Identität/Stabilität zu brechen?

### Befund — jetzt umstellen; persistente lesbare Surrogat-ID

- **Nichts Gespeichertes hängt daran:** lokale Lexonomy-DB hat 0 Edits (nur Import-`create`),
  `linkables`/`crossref` leer; Lexonomy identifiziert über Integer-`entries.id`. Overrides
  (flexsrv/exportov) laufen über den Analyse-String, nicht die ID. `corpus/parsed/` ist gitignored.
- Einziger echter Konsument: `relation/member` (985 Relationen, 1970 Member), vom Konverter
  selbst geschrieben; plus Test `test_twanksta_to_dmlex.py:145` (`endswith("#1")`).
- **0 von 10769 IDs sind gültige NCNames** (Leerzeichen, `[`, `|`, 5× `: ` → macht
  `member: <id> role:` mehrdeutig). Median 30, max 169 Zeichen; 1565 mit leerem Paradigma.
- Natur-Schlüssel ist **nicht stabil**: `desc_text` ist Output der Parser-Heuristik
  `extract_desc_refs`, `#n` hängt an `<li>`-Reihenfolge; Headword/Paradigma-Edits machen ihn falsch.
- `(word, paradigm)` kollidiert noch in 204 Gruppen → `word-paradigm`-Slug reicht nicht.
  290 Headwords mit >1 Eintrag (max 4). ASCII-Faltung erhöht Kollisionen → Diakritika behalten.
- DMLex: `id` optional; Identität = Headword + `homograph`; XML-portabel nur NCName.

**Empfehlung:** ID = Headword-Slug (NCName, Leerzeichen→`_`), bei Homographen `-n` +
Feld `homograph: n`; **einmal vergeben, in committeter Mapping-Datei eingefroren**, nie neu
berechnet. Einmal-Rewrite, kein Übergangs-Alias (kein Leser dafür).

**TODO**
1. `corpus/ids/twanksta_ids.tsv` (word, paradigm, desc_text, idx → id) einmalig erzeugen, committen.
   Offen: `-1` für ersten Homographen oder erst ab dem zweiten?
2. Konverter (`:425-440`): Dedup auf `key_of`-Tupel; ID aus Mapping; neue Schlüssel anhängen,
   verschwundene **laut melden** (macht Parser-Drift sichtbar).
3. NVH: `homograph:` emittieren; `member: <id>` mit `role:` als Kindknoten; `parse_nvh` +
   Lexonomy-`nvhSchema` nachziehen.
4. Tests: NCName + Eindeutigkeit; zweiter Lauf = kein Mapping-Diff; `:145` anpassen.
5. Doku: `corpus/MAPPING.md:226-248`, `dictionary/web/README.md:103`, `custom_editor.js:20`, `preview.html:74`.
6. Lexonomy neu importieren (gefahrlos); Cutover-Regel festschreiben: danach ist Lexonomy Quelle, Mapping eingefroren.

---

## Q3 — Eigennamen über die Noun-Atome (WS2)

**Kontext:** Pit/Per-Eigennamen stehen schon als `pos: noun, label: Pit|Per, paradigm: 32–70`
in der NVH → über Noun-Atome generierbar (nur `+Prop` fehlt).

**Entschieden:** Die kuratierte `proper_nouns.lexc` ist Scaffolding (unvollständige,
teils klein-geschriebene Handformen) → **kann weg**, keine Migration.

**Unbekannte:** Dekliniert jeder Pit/Per-Name sauber durch die Noun-Atome, oder gibt es
namens-spezifische Irregularitäten (fremde Phonotaktik, unflektierbare/Pluraletantum-Namen)?

### Befund — Namen deklinieren sauber; aber **Pit/Per ist kein Eigennamen-Marker**

- **Prämisse falsch:** `Per` hat **0** Einträge (nur in Regexen `gen_lexc.py:110`,
  `build_analyzer.py:74`). `Pit` (398) markiert inhaltlich **modernen Wortschatz/Neologismen**:
  von 363 Pit-Nomen sind nur 117 großgeschrieben, **246 Gattungswörter** (`bankōmats`, `stress`,
  `diplōmats`). Umgekehrt haben 372 von 489 großgeschriebenen Nomen **kein** Pit (`Afrika`,
  `Berlīns`, `Alnā`). Heutiges Routing gibt also 246 Appellativen `+Prop` und verpasst ~¾ der Namen.
- Abdeckung (alle, keine Stichprobe): Pit-Nomen S0 97,5 % / S1 **99,3 %** der Zellen;
  großgeschriebene Pit-Nomen S1 **100 %**; alle anderen Nomen S1 98,9 %.
  Fremde Phonotaktik, Akzent, Großschreibung: **kein** Fehlschlag.
- Namensspezifisch nur: **Pluralia tantum** (`Komōrai`, `Ālpis`, 28 großgeschr.; S0 hängt
  Endungen ans Pl-Lemma, S1 ok), **Mehrwortnamen** (23 Pit; „nur letztes Token flektiert“ →
  15/23), wenige **Indeklinable** (`Burkīna Fasō`; `Palau`/`Perū`/`Samōa` ohne POS).
- Nicht namensspezifisch: 39 Nomen mit „alle 8 Zellen = Lemma“ (Dumper-Artefakt, z. B.
  `Dānija`), Gemination im Obliquus, **P35a fehlt in `PARADIGMS`** (115 Einträge korpusweit).
- `+Prop`-Position: `+N+Prop+G+Nb+C` (wie `proper_nouns_auto.lexc`, Giella). CG3 nutzt `+Prop`
  nirgends → risikoarm. Großschreibung braucht im FST kein Folding (Pipeline-Fallback existiert).

**TODO**
1. Kriterium in `build_analyzer.is_proper/routed_to_auto_proper` und `gen_lexc.is_proper_noun`:
   `pos == noun and lemma[0].isupper()` statt Pit/Per; `Per` streichen.
2. `analysis_tags` → `+N+Prop+…`; `ProperNouns`/`ProperNounsAuto` aus `root.lexc` entfernen;
   Abnahme: Parität gegen Gold aller großgeschriebenen Nomen.
3. Pluralia tantum: Eintragsmerkmal (z. B. `number: pl`) → nur Pl-Slots, S0 zieht Nom.Pl-Endung ab.
4. Upstream: 39 „alle Zellen = Lemma“-Einträge neu dumpen; Pl.tant.-Sg-Zellen leeren;
   `MAPPING.md` §10: Pit = moderner Wortschatz dokumentieren.
5. P35a (+ 65, 29, 45a) in `PARADIGMS` aufnehmen (allgemeine Nomen-Lücke).
6. Mehrwortnamen: Regel „letztes Token flektiert“; Rest Override.
7. Indeklinable ohne POS über den Q4-Invariablen-Pfad mit `+N+Prop`.

---

## Q4 — Invariable Funktionswörter in der NVH (WS3)

**Kontext:** Das `pos:`-Feld der NVH trägt heute nur `noun|adj|verb`, und zwar weil
`twanksta_to_dmlex.pos_of` POS **aus der Formtabellen-Shape** ableitet (`_shape_and_cells`:
verb→verb, adj→adj, decl→noun, keine Tabelle→`None`). Invariable (Präp/Konj/Partikel/Interj)
haben **keine** Formtabelle → sie fallen als `None` heraus. Die desc-Tags (prp/cj/pcl/…) waren
der alte `gen_lexc`-Monolith-Pfad, **nicht** der DMLex-Konverter. Sie sollen erstklassige
NVH-Einträge werden.

### Befund A — DMLex-POS-Vokabular

- OASIS DMLex v1.0 (https://docs.oasis-open.org/lexidma/dmlex/v1.0/dmlex-v1.0.html):
  **kein kontrolliertes Vokabular**. `partOfSpeech.tag` ist freier String (§3.5);
  standardkonform über `partOfSpeechTag` mit `description`/`for`/`sameAs` (§4.2.6, §4.2.9).
- Empfehlung: projekteigene Kurz-Tags mit `sameAs` auf LexInfo 3.0 + UD, 1:1 auf FST:

  | NVH `pos` | LexInfo | UD | FST |
  |---|---|---|---|
  | `adv` | adverb | ADV | `+Adv` |
  | `prep` | preposition | ADP | `+Pr` |
  | `postp` | postposition | ADP | `+Po` |
  | `cconj` | coordinatingConjunction | CCONJ | `+CC` |
  | `sconj` | subordinatingConjunction | SCONJ | `+CS` |
  | `part` | particle | PART | `+Pcle` |
  | `intj` | interjection | INTJ | `+Interj` |
  | `num` | numeral | NUM | `+Num` |
  | `pron` | pronoun | PRON | `+Pron` |

- **Enklitikon ist keine Wortart** (LexInfo: Eigenschaft `cliticness`) → Merkmal von Pronomenformen (`+Pron+Encl`).
- Lexonomy: Template kennt `posTag`; Live-Schema `pos: ? string` (frei, max. 1);
  **Editor-Dropdown hart `noun|verb|adj`** (`dictionary/web/editor/custom_editor.js:582`).

### Befund B — Klassifikationsquelle: desc-Tags + kleine Hand-Tabelle

- 1565 Einträge ohne `pos`; davon 1003 ohne `sense` (Belege/Verweis-Skelette, kein POS nötig).
  **562 echte Kandidaten.**
- **361** mit POS-tragendem desc-Tag (av 264, prp 28, ij 22, crd 19, pc/aj 12, cj 3, pcl 3, psp 2, …);
  echt mehrdeutig nur `ēnilgan` (av/psp), `kīrsa` (prp/av). Muster `aj n (av)` → `n` = Neutrum → adv.
- **201** ohne Tag: 53 Mehrwort-Phrasen, 45 Flexionsform-Belege, 11 Namen/Fehlklass., 92 Einwort —
  davon **70 schon in `function_words.lexc`**, Rest 22 meist indeklinable Lehnnomen (`taksi`, `kilō`).
- **Vermutung bestätigt:** desc deckt Adv/Präp/Interj, aber **Konjunktionen und Partikeln fehlen
  fast immer** (`be`, `adder`, `kāi`, `ikkai`, `ni`, `jā`…); `cj` unterscheidet nicht koord./subord.
  → Hand-Kuration nötig, aber klein (~40 neue Entscheidungen).
- **Fehler im heutigen Gold:** `mi`/`ti` als `+Pcle` (sind enklitische Pronomenformen → `+Pron+Encl`);
  `ikkai` „wenn“, `anga` „ob“ (evtl. `nikāi`, `kāigi`) als `+CC` statt `+CS`; `stā`/`stu`/`pēr` eher Adv.

**TODO**
1. Konverter `pos_of`: desc-Fallback über **alle** Tokens (av→adv, prp→prep, psp→postp, ij→intj,
   crd/ord→num, pcl→part; `aj|pc … n (av)`→adv; `encl` setzt kein POS).
2. Hand-Tabelle `invariable_pos.tsv` (Schlüssel: Q2-ID) aus FW + Korrekturen (CC/CS, Adv, 22 Lehnnomen → noun `indecl`).
3. Doppel-POS `ēnilgan`/`kīrsa`: Schema `pos: *` + `listingOrder`, oder zwei Einträge.
4. `partOfSpeechTag`-Deklarationen mit `sameAs` in NVH + Lexonomy-`nvhSchema`.
5. Editor-Dropdown aus posTag-Liste; Paradigmen-Box bei Invariablen ausblenden.
6. FST: `mi`/`ti` → `+Pron+Encl`; Postpositionen einheitlich (`+Adp+Po` vs. `+Po`).
7. `function_words.lexc` **aufteilen**: lexikalische Invariable → NVH (`ne`, `te`, `ei`, `ka`,
   `nikaddan`, `nitāli`, `nimazīngi` neu anlegen); Formen (`astits`, `sin`/`sebbei`, …) → Overrides
   am Elterneintrag. Bis dahin FW als Regressionstest „NVH-Invariable ⊇ FW-Tags“.
8. 45 Flexionsform-Belege per Relation an Elterneintrag; 53 Phrasen ohne POS oder Label `phrase`.

---

## Q5 — Coverage gold (ENTSCHIEDEN)

**Entschieden:** Der alte FST ist zu 100 % aus `corpus/parsed/twanksta_entries.json` abgeleitet
→ das non-circular coverage gold ist **direkt `twanksta_entries.json`** (bzw. die daraus mit
der `gen_lexc`-Extraktionslogik erzeugten Oberflächen). Kein `base.merged`-Snapshot nötig,
keine Zirkularität (Gold stammt nicht aus der NVH, gegen die generiert wird — vgl.
[[nvh-overrides-to-fst]], [[twanksta-dmlex-migration]]).

**Konsequenz für WS0:** Die Oberflächen-Extraktion aus `twanksta_entries.json` muss erhalten
bleiben (als Gold-Generator), auch wenn der `gen_lexc`-Open-Class-**FST-Pfad** entfällt — d. h.
entweder die Extraktionsfunktion aus `gen_lexc` in den Paritätstest ziehen oder die Gold-Datei
einmal einfrieren, bevor `gen_lexc` abgebaut wird.

---

## Q6 — Tag-Inventar-Parität (Verifikation, kein echter Fork)

**Kontext:** Der vereinte FST mischt gebackene Open-Class (`slot_tag`/`analysis_tags`) mit
handgeschriebenen geschlossenen lexc (`symbols.lexc`). Downstream (CG3, conllu, MCP) parst
die Analyse-Strings.

**Unbekannte:** Stimmt `generator.slot_tag()`-Ausgabe über **alle** POS exakt mit
`symbols.lexc` überein (Genus `+Msc/+Fem/+Neu`, `+SP3`, Partizip `+PrsPrc/+PrfPrc+Act/+Pss`,
Grad `+Comp/+Superl`, `+Refl`-Position, Numeral-Tags aus Q1)?

### Befund — Namen paritätisch, Reihenfolge nicht; ein echter Bug (+P1/2/3)

- Generator über alle 10769 Einträge: 199 Tag-Strings, **alle Tokens ⊆ `symbols.lexc`**.
  Echte FSTs (`base`, `base.gen`, `analyzer`): Multichars = exakt die 46 `+Tags`. Nur **ein**
  `symbols.lexc`; `gen/*.lexc`-Multichars sind Teilmenge (zweite Pflegestelle, kein Konflikt).
  Downstream (cg3, `export_conllu`, `cg3_pipeline`): keine veralteten Tag-Namen.
- `uv run pytest`: 444 passed (gegen `base`); gegen frisch gebackenen Analyzer 437/7 failed
  (Abdeckung/Disambiguierung: `gūbuns`, `dēināi+N` verdrängt `labs+A+Fem`).

| # | Abweichung | Fundstelle | Wirkung |
|---|---|---|---|
| 1 | **`+P1/+P2/+P3` nicht deklariert** (c93a558 entfernt, Nutzer nicht umgestellt) | `lexc/pronouns.lexc` (164×), `cg3/*.cg3`, `export_conllu.py:60`, `cg3_pipeline.py:507` | zerfällt in `+`,`P`,`1`; **Generierung von Personalpronomen liefert `[]`** (auch MCP `get_word_forms`) |
| 2 | `+Refl` im Analyzer nur bei `+V+Inf` | `gen/build_analyzer.py:173-190` | 3950 Refl-Lesarten in base vs. 172 im Analyzer; CG3 `NonReflV`/`ReflMarker` |
| 3 | Pronomen genus-hinten (`+Pron+Nb+C+G`) | `lexc/pronouns.lexc`, `function_words.lexc:29`, `cg3_golden.tsv` | `stas+Pron+Msc+Sg+Gen` → `[]` |
| 4 | Eigennamen in zwei Reihenfolgen | `lexc/proper_nouns.lexc` vs. `_auto` | erledigt sich mit Q3 (Datei fällt weg) |
| 5 | `pos: noun` + P25–31 → als adj klassifiziert, aber mit noun regeneriert → `+N` ohne Genus | `gen/build_analyzer.py:87-137` | 1258 Lesarten/84 Lemmata falsch (Ordinalia `+N` statt `+Num+Ord`) — **Ursache = Konverter-Bug aus Q1** |
| 6 | 161 `+A` ohne Genus in base | `lexc/adjectives.lexc` | bekannte -uns/-ts-Lücke (Phase 6) |
| 7 | `DEAC`, 6 `@P.…@`-Flags deklariert, unbenutzt | `lexc/symbols.lexc:56-64` | tot |
| 8 | veraltete Kommentare | `disambiguator.cg3:19`, `validator.cg3:147`, `export_conllu.py:7-8` | kosmetisch |

**TODO**
1. ~~`+P1 +P2 +P3` in `symbols.lexc`~~ **erledigt 2026-10-08** (+ `tests/test_api.py::test_generate_person_pronouns`).
2. `bake_open`: `+Refl` an alle Slot-Tags reflexiver Lemmata.
3. `pronouns.lexc`, `function_words.lexc:29` auf gender-first; `cg3_golden.tsv` + dictionary `queries.go` mitziehen.
4. Fällt mit Q1-TODO 1 (Konverter-Genusblöcke); bis dahin `analysis_tags` mit klassifizierter POS aufrufen.
5. Paritätstest: `analysis_tags`-Tokens ⊆ `symbols.lexc` ⊆ `export_conllu`-Mappings + Shape-Check gegen kanonische Reihenfolge.
6. `DEAC`/`@P.…@` entfernen oder dokumentieren; Kommentare bereinigen.
7. Optional: `gen/*.lexc`-Multichars aus `symbols.lexc` ableiten bzw. Teilmengen-Test.
