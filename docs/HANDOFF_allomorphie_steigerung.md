# Handoff: Steigerung & Definitheit in der altpreußischen Adjektivflexion

**Kontext für dich (Linguistik-Experte):** Wir bauen einen computerlinguistischen
Morphologie-Analysator/-Generator für das (neu-rekonstruierte) Altpreußisch — ein
endlicher Transduktor (FST, Bibliothek PyFoma). Die **Grundflexion** der Adjektive
(Positiv, Paradigmen P25–P31 + P30a: je 8 Zellen Nom·Gen·Dat·Akk × Sg/Pl × m/f/n)
läuft bereits über die gemeinsame nominale Maschinerie und deckt ~1.110 Lemmata ab.

Jetzt sollen die **gesteigerten und definiten Formen** dazukommen. Tagset & Code
sind dafür vorbereitet (Tags `+Def`, `+Superl`, `+Adv` mit `+Pos/+Comp/+Superl`);
es fehlt die **sprachwissenschaftlich korrekte Modellierung der Allomorphie**. Ich
(der Programmierer) habe nur flüchtige Linguistik-Kenntnisse — dafür dieser Handoff.

Schwesterdokument: [`HANDOFF_allomorphie.md`](HANDOFF_allomorphie.md) (Stamm-
Allomorphie der **Nominal**flexion).

Datenlage: Steigerungsformen liegen in **Twanksta** (`twanksta/<par>/lemma.json`,
Deklinationsblöcke + `adverb`) und **Prusaspira** (`Kōmparatiwan/Superlatīwan/
Adwerban/Prōnominālas fōrmis`) vor; **Tabula** hat keine. Ein 3-Quellen-Mehrheits-
votum wie beim Positiv ist also nicht möglich — meist nur Twanksta ± Prusaspira.
Forman ohne Quellbeleg werden im Goldstandard als `provisional` markiert.

---

## Das Ziel

Gegeben Nom-Sg-Zitierform + Paradigmennummer eines Adjektivs sollen automatisch
auch erzeugt werden: **Komparativ/Definit-Deklination**, **Superlativ-Deklination**
und das **Adverb** in 3 Steigerungsstufen.

## Befund: die Endungen wirken weitgehend regelmäßig

Aus den 5 **nicht-suppletiven** Referenz-Adjektiven (Stamm jeweils blanker
Konsonant; Formant + Kasusendung danach):

| Par  | Lemma     | Stamm   | Komp./Def. (m Nom Sg) | Superlativ        | Adv Pos | Adv Komp | Adv Superl  |
|------|-----------|---------|-----------------------|-------------------|---------|----------|-------------|
| 28   | māldaisis | māld-   | māld**ais**is         | uka·māld·aisis    | (—)     | (—)      | (—)         |
| 29   | sēnts     | swent-  | swent**ais**is        | uka·swent·aisis   | swentai | swentais | ukaswentais |
| 30a  | stāws     | stāw-   | stāw**ais**is (?)     | uka·stāw·aisis    | stāwai  | stāwais  | ukastāwais  |
| 30   | āngus     | āng-    | āng**uis**is          | uka·āng·uisis     | āngu    | ānguis   | ukaānguis   |
| 31   | līgus     | līg-    | līg**uis**is          | uka·līg·uisis     | līgu    | līguis   | ukalīguis   |

Beobachtungen:
- **Kasusendungen uniform** (`-isis` m, `-isi` f/n im Nom Sg; parallel in den
  übrigen Kasus — *bisher nur Nom Sg vollständig geprüft*).
- **Superlativ = `uka-` + Komparativstamm**, sonst identisch.
- Der **Formantvokal** erscheint als `a` (māld-, swent-, stāw-) oder `u`
  (āng-, līg-). Die `u`-Formen sind genau die **u-Stämme** (Positiv masc auf
  `-us`: āngus, līgus); die `a`-Formen die übrigen.
- **Adverb**: Positiv `-ai`/`-u`, Komparativ `-ais`/`-uis`, Superlativ `uka-`+Komp.

---

## Getroffene Modellierungs-Entscheidung

**`ais`/`uis` werden als phonologische Schreibvariante EINES Formant-Morphems
behandelt — nicht als zwei morphologische Klassen.** (Entscheidung des Projekts.)

Konkret: im FST steht **ein** Formant mit Archiphonem-Vokal; eine Regel in der
Lautschicht (`phonology.py`, analog zu unseren bestehenden Archiphonem-Regeln
`A/E/I/O/U` lang/kurz) löst ihn je u-Stamm zu `a`/`u` auf. Folgen:

- **Ein** Endungs-Template für alle Adjektivparadigmen (deckt auch P27 ab).
- Die `a`/`u`-Alternation taucht **nicht** im Gold-Votum auf (kein „Quellkonflikt")
  und wird **nicht** im Tagset gespiegelt (keine Klassen-Tags).
- Der **nachsichtige** Analysator akzeptiert zusätzlich die jeweils andere
  Schreibung, sodass Korpusformen mit „falschem" Vokal analysierbar bleiben.

Damit trägt das Modell automatisch auf alle ~1.110 Wortlisten-Adjektive — **sofern
die Konditionierung wirklich vollständig vorhersagbar ist** (s. Frage 1).

---

## Konkrete Fragen an dich

1. **Konditionierung `a`/`u` (Bestätigung):** Wir nehmen an, der Formantvokal ist
   lautlich vorhersagbar: **u-Stamm → `u`, sonst `a`**. Stimmt das durchgängig, oder
   spielt etwas anderes hinein (vorausgehender Vokal, Palatalisierung, Akzentklasse)?
   Gibt es eine **dritte** Realisierung? — Falls die Verteilung nicht rein
   lautlich/vorhersagbar ist, kippt unsere „eine Regel"-Annahme.
2. **P30a `stāws`:** Die Quellen widersprechen sich (`stāwaisis` vs `stāwuisis`).
   Ist `stāws` ein u-Stamm? Welcher Formant ist korrekt?
3. **Komparativ vs. Definit:** Prusaspira führt getrennt `Kōmparatiwan`
   (Komparativ) **und** `Prōnominālas fōrmis` (pronominale/definite Langform, mit
   vorangestelltem Artikel `stāi/stan/stesmu …`). Unser Code fasst die
   Twanksta-Deklinationsblöcke [3–5] derzeit unter einem Tag `+Def` zusammen.
   - Was repräsentieren die Blöcke [3–5] linguistisch — den **Komparativ** oder die
     **definite Langform**?
   - Sind Komparativ-Deklination und definite Langform **dieselbe** oder **zwei
     verschiedene** Paradigmen? Sollten wir `+Comp` und `+Def` trennen?
   - Ist die definite Langform (mit fusioniertem Pronominal-Artikel) überhaupt im
     Skopus, oder ein eigenes späteres Thema?
4. **Doppelformen:** Prusaspira listet „Adjaktīwan: `līgus` / `līguisis`" und
   Superlativ „`ukalīguisis` / `ukalīgus`". Sind das **kurze (indefinite)** vs.
   **lange (definite)** Steigerungsformen? Welche ist die kanonische Zitierform?
5. **Suppletion:** Bestätigt sich `debīks→māises-`, `labs→walns-`? Hat `līkuts`
   überhaupt belegte Steigerungsformen (in keiner Quelle gefunden)? Wo verläuft die
   Grenze zwischen echter Suppletion und einer regelhaften Bildung, die wir nur
   übersehen?
6. **`uka-`-Präfix:** Ist `uka-` der **invariante** Superlativpräfix für alle
   Adjektive? Assimiliert es vor vokalanlautenden Stämmen (`ukaāngu-` vs `ukāngu-`;
   die Quelle schreibt `ukaāngu-`)? Beeinflusst `uka-` die **Akzentklasse**
   (Baryton/Mobile) der Form?
7. **Adverb:** Ist die Positiv-Adverbendung `-ai`/`-u` **identisch** konditioniert
   wie der Komparativ-Formant, oder unabhängig? Bildet **jedes** Adjektiv regelhaft
   ein Adverb?
8. **Stamm/Formant-Grenze:** Hängt der Formant durchgängig am **blanken
   Konsonantenstamm** (= unsere Positiv-Stammgrenze), oder gibt es Stämme, bei
   denen die Grenze abweicht (z. B. Palatalisierungs-Interaktionen)?
9. **P27 `weselīngis`:** In Twanksta fehlen die Deklinationsblöcke; nur ein Adverb
   ist belegt. Bildet `weselīngis` Steigerung **regelhaft**, oder ist es defektiv
   bzw. anders gebaut?
10. **Akzent/Vokallänge:** Folgen Komparativ/Superlativ derselben Akzentklasse wie
    der Positiv, oder verschiebt sich der Akzent? (Entscheidet, wie wir die langen
    Vokale im Formant/in den Endungen als Archiphoneme markieren.)

**Was wir am Ende brauchen:** (a) Bestätigung der `a`/`u`-Konditionierung aus
Frage 1, (b) den **vollständigen** Kasus-Endungssatz der Komparativ/Definit- und
Superlativ-Deklination (alle 8 Zellen × 3 Genera), (c) Klärung Komparativ vs.
Definit (Tag `+Comp`/`+Def`) und (d) die Liste echter Suppletiva. Daraus erzeugen
wir je Adjektiv automatisch die gesteigerten/definiten Formen.

---

## Antwort (Linguistik-Lehrer, 2026-06-14)

**Die Architektur (ein Formant-Morphem + eine Lautregel) ist richtig.** Zwei
Korrekturen, dann zwei konkrete Code-Pflichten.

**Q1 — Formant binär, aber Palatalisierung an der Grenze.** Es gibt **keinen
dritten Formantvokal**. Das scheinbare `-eis-` ist `-ais-` **mit Palatalisierung**,
in Palmaitis-Orthografie gerendert (§2 `ge/re/ke/de/te` = Cʲa). Beweis, derselbe
i-Stamm zweimal geschrieben:

| Quelle | Form | = |
|--------|------|---|
| Palmaitis | aīning**eis**is | /aīningʲ + ais + is/ |
| Twanksta (MCP) | aīning**jais**is | /aīningʲ + ais + is/ |

→ Der Formant-Archiphonem **bleibt binär** (u-Stamm → `u`, sonst `a`). Aber an der
Stamm+Formant-Grenze muss die **bestehende Palatalisierung** feuern: für palatale
Stämme (i-/jo-/weiche) wird `-ais-` zu `-eis-` (nach Velar/Dental/r), `-jais-`
(nach Labial: `arwjaisis`, `wūrmjaisis`), Sibilant → `š/ž`. **Kein** neues Morphem,
**keine** neue Regel — dieselbe Jotierung wie nominal (`kūges/kūgjas`). Der
nachsichtige Analysator akzeptiert `-ais-/-eis-/-jais-`.

**Q9/Q8 — P27 hängt genau daran:** `weselīngis` ist regelhaft, nicht defektiv (die
fehlenden Twanksta-Blöcke sind eine Datenlücke — als Adverb katalogisiert). Mit
einem Template korrekt **nur wenn** die Palatalisierung greift:
`weselīngʲ+ais+is` → `weselīngeisis` (Palm.) / `weselīngjaisis` (Twa.). Feuert sie
nicht → `*weselīngaisis`. Die Stamm/Formant-Grenze ist durchgängig der **blanke
Positivstamm** (wie im Positiv); die Palatalisierung dort ist der **Normalfall**
für palatale Stämme, kein Sonderfall.

**Q3 — `+Comp` ≠ `+Def`.** Die Blöcke [3–5] (`stāwaisis`-Typ, synthetisch) sind der
**Komparativ**, nicht das Definitum. Unser `+Def` darauf ist ein Fehletikett
(„mehr X", nicht „das X"). → `+Comp` und `+Def` **trennen**. Das echte (Artikel-)
Definitum ist die pronominale Positivform mit teils analytischem Artikel `stas`
(`debīkasis · stesmu debīkan …`) — ein anderes, komplexeres Paradigma,
sinnvollerweise **eigenes späteres Thema**. In-Scope ist der synthetische
Komparativ/Superlativ.

**(b) Vollständiger Endungssatz P28** (Komparativ; Superlativ = `uka-` + identisch).
`š` = palatalisierter `s` vor a-anlautender Endung (= Sibilantenregel; Twa. `-sj-`):

| Kasus | m Sg | m Pl | f Sg | f Pl | n Sg | n Pl |
|-------|------|------|------|------|------|------|
| Nom | -aisis | -aišai | -aisi | -aisis | -aisi | -aišai |
| Gen | -aišas | -aisin | -aišas | -aisin/-aišan | -aišas | -aisin |
| Dat | -aišasmu | -aisimans | -aišai | -aisimans | -aišasmu | -aisimans |
| Akk | -aisin | -aisins | -aisin | -aisins | -aisi | -aisins |

(weiche `-s`-Stamm-Adjektivdeklination — Maschinerie ist vorhanden.)

**Übrige Punkte:**
- **Q2 `stāws`:** o-Stamm (keine Palatalisierung) → `-ais-` → `stāwaisis`;
  `stāwuisis` ist Fehllesung (MCP-bestätigt).
- **Q4 Doppelformen:** lange `-sis`-Form (`līguisis`, `ukalīguisis`) = kanonische
  adjektivische Zitierform; kurze (`ukalīgus` = `uka-`+Positiv) = prädikativ/
  adverbial → über `+Adv`, **keine** dritte Deklination.
- **Q5 Suppletion** (MCP-bestätigt): `labs→waln-`, `debīks→māises-`, `līkuts→maz-`
  (nicht defektiv, nur suppletiv → übersehen), dazu `tūls / mūises-` („viel/mehr").
  Wichtig: Suppletiv-Komparative **deklinieren wie normale Positiv-Adjektive**
  (`māisess/māisesas…` = **P26**, nicht P28) → gelisteter Adjektivstamm +
  Normaldeklination + Tag; `uka-` davor für den Superlativ.
- **Q6 `uka-`:** invariantes Präfix, **keine** Kontraktion vor Vokal (Hiat bleibt:
  `ukaaīningjaisis`, `ukamāisess`); hängt am Komparativstamm, ändert dessen Akzent
  nicht.
- **Q7 Adverb:** regulär/produktiv. Positiv-Adverb `-ai/-i/-u` (eigenes kleines
  Set, gleiche o/i/u-Konditionierung); Komp-/Superl-Adverb = der **kurze**
  Komparativ (Formant ohne pronominales `-is`): `wūrais`, `ukawūrais`
  (`wūraisis` Adj. vs. `wūrais` Adv. nur durchs `-is`).
- **Q10 Akzent/Länge:** Positivstamm behält seine Stufe (`stāwaisis` hält `ā`,
  `līguisis` hält `ī` — keine Schwer-Endungs-Schwächung); Formant `-ais-/-uis-` =
  fester Block, `uka-` unbetont. Keine neue Akzentklasse.

### Daraus für die Umsetzung (gegenüber dem ursprünglichen Plan)
1. **Palatalisierung an der Stamm+Formant-Grenze** sicherstellen (bestehende
   `R_JPAL`/J-Marker; sonst brechen i-/jo-/weiche Stämme inkl. P27). ← kritisch.
2. **`+Def` → `+Comp`** umetikettieren (Tagset); echtes Artikel-Definitum bleibt
   out of scope.
3. Suppletive als **P26-deklinierende** gelistete Stämme modellieren (nicht P28).
4. Komp-/Superl-**Adverb** = kurzer Komparativ; `a`/`u`/Palatalisierung wie oben.

Offen vom Lehrer angeboten: ein **PyFoma-Fragment** der Palatalisierungsregel
exakt für diese Grenze.

---

## Antwort 2 — Rollout-Klassifikation (Linguistik-Lehrer)

Zentrale Erkenntnis: **außer P27 ist keines dieser Paradigmen an der Grenze
palatal.** Was in Genitiven wie Palatalisierung aussieht (`swentaisjas`,
`stāwaisjas`, `māldaisjas`), ist die **Formant-s→š/sj-Regel vor a-Endung** (R3) —
sie läuft bei *jedem* Komparativ, palataler Stamm oder nicht, und ist ins
Endungstemplate eingebacken (`aišas`). Die **Grenz-Palatalisierung** (R1/R2, das
`-eis-`/`-jais-`) feuert nur bei lexikalisch palatalen i-/jo-/weichen Stämmen.

### 1. Klassifikation je Paradigma

| Par | Lemma | Klasse | Formant | Grenz-Palatal? | Nachweis |
|-----|-------|--------|---------|----------------|----------|
| 25 | debīks | o-Stamm, suppletiv | — | — | Komp = `māises-`, kein Formant |
| 26 | labs | o-Stamm, suppletiv | — | — | Komp = `waln-`, kein Formant |
| 28 | māldaisis | = Komparativ von `mālds` (P26) | — | — | ist bereits Komparativ |
| 29 | sēnts/swents | o-Stamm (hart) | `-ais-` | nein | `swentaisis` |
| 30a | stāws | o-Stamm (hart) | `-ais-` | nein | `stāwaisis` |

Bestätigt: P27 `-ais-` palatal **ja** (`weselīnģaisis`), P30/P31 `-uis-` (hart,
palatal nein). Also: **palatal = ja nur bei P27**; alle o- und u-Stämme hier
nicht-palatal.

Drei Rollout-relevante Punkte:
- **P25/P26 nehmen keinen Formant** (suppletiv → gelisteter Stamm `māises-`/`waln-`
  in P26-Deklination).
- **P28 `māldaisis` ist der Komparativ von `mālds`** ('jung'→'jünger'), kein
  Positiv. P28 ist die Komparativ-Deklinationsklasse selbst → KEINE
  Komparativbildung darauf anwenden; nur Deklination + Superlativ (`ukamāldaisis`).
  Zugehöriger Positiv = `mālds` (P26, `-ais-`, hart).
- **P29 `swents`** ist trotz t-Auslaut ein **harter o-Stamm** (Positiv `swentas`,
  Gen `-as`), kein palataler Stamm → `swentaisis`, nicht `*swenteisis`. Das `t`
  ist zwar in der Palatalisierungsmenge, aber die Grenz-Palatalisierung feuert nur
  mit lexikalischem j-Marker, den `swents` nicht trägt.

### 2. „Blanker" Komparativstamm — klassenabhängig

Nicht durchgängig „Nom-Sg minus `-s`". Der Formant hängt am Positiv-Konsonanten-
stamm = Nom-Sg minus der vollen Nominativendung:
- **o-Stamm:** minus `-s` → `stāws`→`stāw-`, `wūrs`→`wūr-`, `mālds`→`māld-`
- **u-Stamm:** minus `-us` → `āngus`→`āng-`, `līgus`→`līg-` (nicht minus `-s`!)
- **i-Stamm:** minus `-is` → `weselīngis`→`weselīng-`

= genau der Stamm, den die Positivflexion schon isoliert → wiederverwenden.

**`stāws`-Fehlsegmentierung:** Das Positiv-Gold segmentiert `st-` + `-āws` (das `ā`
liegt fälschlich in der Endung). Korrekt ist Stamm `stāw-`, Endung `-s` (MCP-Positiv
`stāwas/stāwan`). Mit `st-` erzeugt der Komparativ `*staisis`. → `stāws` (und etwaige
andere `-āws/-āus`-Fälle) im Positiv-Gold auf Stamm `stāw-` korrigieren.

### 3. Adverb (produktiv-regelhaft)

- **Positiv-Adverb nach Klasse:** o-Stamm `-ai` (`wūrai`, `swentai`, `stāwai`,
  `māldai`, `wārgai`; teils Variante `-an`), i-Stamm `-i` (Palmaitis `aīningi`;
  Twanksta `-jai`), u-Stamm `-u` (`āngu`, `līgu`).
- **Komp/Superl-Adverb = kurzer Komparativ** (Formant ohne pronominales `-is`):
  `-ais/-eis/-uis`, Superlativ mit `uka-`: `wūrais`/`ukawūrais`, `ānguis`/`ukaānguis`,
  `aīningeis`/`ukaaīningeis`.
- Das Positiv-Adverb `-ai` ist **nicht** der Formant `-ais` (Unterschied: das `-s`)
  — gleiche o/i/u-Konditionierung, aber eigenes Endungsset.
- Suppletive haben **eigene, gelistete Adverbien** (`labs→walnai`, `līkuts→mazzais`,
  viel→`tūls`) — pro Lemma listen.

### 4. Suppletive

Alle vier per MCP bestätigt, deklinieren wie **P26-Positiv**, Superlativ mit `uka-`:

| Positiv | Komp.-Stamm | Superlativ | Adverb (Pos/Komp/Superl) |
|---------|-------------|------------|--------------------------|
| labs | `waln-` | `ukawalns` | `labbai` / `walnai` / `ukawalnai` |
| debīks | `māises-` | `ukamāisess` | — / `tūls` / `ukatūls` |
| līkuts | `maz-` | `ukamazs` | — / `mazzais` / `ukamazzais` |
| viel/sehr | `tūls`, `mūises-` | `ukatūls` | `mūisesan` / — / — |

Gegenprobe `wārgs` ('schlecht', in anderen Sprachen oft suppletiv): **regulär**
(`wārgaisis`), nicht suppletiv → die vier sind vermutlich vollständig. Sicher nur
datengetrieben: **Mismatch-Detektor** über das Wörterbuch — jedes Adjektiv flaggen,
dessen Komparativ-Stamm ≠ Positiv-Stamm + `ais/uis` ist. Fängt Suppletiva (und
Tippfehler) automatisch ab.

### 5. māldaisis-Homonymie (Komparativ UND Substantiv)

`māldaisis` ist zugleich der Komparativ 'jünger' von `mālds` **und** ein
substantiviertes Nomen 'Jünger/Schüler' mit eigenem Lemma (schon als P40-Nomen in
der Wortliste). Etymologisch sauber, parallel zu deutsch „jung → (der) Jünger".

Der Analyzer gibt **beide** Lesarten aus (Auswahl eine Ebene höher, Syntax/LLM):

```
māldaisis →  mālds      +A +Comp +Msc +Nom +Sg     (regulär aus mālds erzeugt)
             māldaisis  +N        +Msc +Nom +Sg     (gelistetes Substantiv 'Jünger')
```

Die Homonymie ist **total über das ganze P28-Paradigma** (das Nomen dekliniert als
P28), kein Nom-Sg-Sonderfall: `māldaišas` = 'des Jüngeren' und 'des Jüngers' usw.
→ als **Lemma-Level-Homonymie** modellieren (zwei Lemmata, ein Oberflächen-
paradigma, beide Lesarten markiert ausgeben). Systematischer Typ: substantivierte
Komparative sind produktiv; die lexikalisierten mit eigener Bedeutung als N-Lemma
listen, die `+A+Comp`-Lesart kommt gratis aus dem Positiv. Der Mismatch-Detektor
(Punkt 4) lässt sich erweitern: zusätzlich flaggen, wo eine Komparativ-Oberfläche
zugleich ein eigenes N-Lemma ist — fängt die `māldaisis`-Klasse automatisch ein.
