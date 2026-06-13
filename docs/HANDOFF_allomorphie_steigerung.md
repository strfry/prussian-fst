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
