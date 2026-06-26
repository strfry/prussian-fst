# Partizip-Deklination im FST

Generiert von [`scripts/gen_participles.py`](../scripts/gen_participles.py) nach
[`fst/verb_participles.lexc`](../fst/verb_participles.lexc); im Build über die
`Makefile`-Liste `LEXC_FILES` eingehängt, erreichbar aus `root.lexc` via
`LEXICON VParticiples`.

## Datenquelle

GitHub-Release von **strfry/prussian-corpus**:
`data/external/{twanksta,prusaspira}_entries.json`. Jeder Verbeintrag führt drei
Partizipien in fester Reihenfolge **[Präsens-Aktiv, Prät.-Aktiv, Passiv]**:

```
īmtun:  imānts (Präs)   immuns (Prät-Akt)   īmts (Passiv)
```

`prusaspira_entries.json` enthält zusätzlich die **volle Deklination**
(`full_declension`, Genus × Kasus × Numerus) — sie ist die Validierungsgrundlage
(`tests/test_participles.py`).

## Kernproblem: Gemination / Vokallänge

Der FST konkateniert literal und hat **keine** aktive Phonologie-Ebene
(`stress.twolc` ist noch ein No-op; Gemination/Makron stehen direkt im Lexc).
Jedes der drei Partizipien braucht daher seinen **eigenen, korrekt gradierten
Stamm** — nicht einen aus dem Verbstamm abgeleiteten:

| Partizip | Form  | Stamm | Endung |
|----------|-------|-------|--------|
| Präsens  | imānts | `im`  | `ānts` (keine Gemination!) |
| Prät-Akt | immuns | `imm` | `uns`  (Gemination) |
| Passiv   | īmts   | `īm`  | `ts`   |

Der Stamm wird je Partizip aus seiner **eigenen** attestierten Mask-Nom-Sg-Form
gewonnen (Endung abstreifen). Damit ist die Gemination automatisch korrekt.

## Akzentverschiebung: zwei Stammgrade (Präsens & Passiv)

Präsens (≈ P29) und Passiv (≈ P69, harter t-Stamm) flektieren mit **zwei
betonungsbedingten Stammgraden**, gesteuert von der **Akzentklasse des Lexems**
(Rinkevičius 2009, [docs/AKZENT.md](AKZENT.md)):

- **Barytona** (feste Stammbetonung): der Stamm behält in *allen* Zellen seinen
  Akzent (Makron/Gemination); die Endungen sind durchweg schwach/entakzentuiert
  → `abōnit-ai`, `abōnit-i`.
- **Mobilia** (mobile Betonung): eine **starke Endung** zieht den Akzent vom
  Stamm; dort ist der Wurzelvokal unbetont — er **entakzentuiert** — und die
  Endung erscheint „schwer“ → `dat-āi`, `dant-immans`, `dant-ī`.

Starke Zellen sind **Dat-Pl** und **Fem-Nom-Sg** (Präsens), beim Passiv
zusätzlich **Nom-Pl**. Die Entakzentuierung eines mobilen Stamms entfernt das
Akzentexponent der betonten Silbe — Rinkevičius §1: das ist entweder ein
**Langvokal** (Makron/Gravis) **oder** die **Gemination** des Folgekonsonanten
(Kürzezeichen). `deaccent_stem` kürzt daher Lang-/Gravisvokale **und**
entgeminiert (`adressit → adresit`, `dānt → dant`, `ausàkstint → ausakstint`).

Die Akzentklasse ist **lexikalisch idiosynkratisch** — aus der Zitierform
(Nom-Sg, wo beide Klassen langen Stamm zeigen) **nicht** ableitbar. Sie wird
darum pro Lemma aus prusaspiras `full_declension` gelesen (starkes vs schwaches
Allomorph in einer starken Zelle: `ī`/`i`, `āi`/`ai`) und im FST hinterlegt;
twanksta-only-Verben bekommen den Default `mob` (die 96-%-Mehrheit). Verteilung:
**96 % mobil, 4–5 % baryton**, Präsens/Passiv desselben Verbs zu 99,8 % gleich.

Pro Zelle wird so **genau eine** korrekte Form generiert (keine Überproduktion).

Das **Prät.-Aktiv-Partizip** (≈ P68, `-uns`/`-us-`) hat einen invarianten Stamm
ohne Akzentwechsel und dekliniert vollständig aus einem Stamm + festen Endungen.

## Tagschema

```
<lemma>+V+Part+<Pres|Pret|Pass>+<Masc|Fem|Neut>+<Sg|Pl>+<Nom|Gen|Dat|Akk>
```

Reflexiva behalten `% si` im Analyse-Lemma; die Oberfläche lässt das Klitikon
weg (wie bei den finiten Reflexivverben).

## Abdeckung (gegen `prusaspira full_declension`, 116 520 Zellen)

| Partizip | exakt | Anmerkung |
|----------|-------|-----------|
| Prät-Akt | 99,7 % | invarianter Stamm, vollständig regulär |
| Präsens  | 95,3 % | ≈ 99,4 % ohne die **korrupte** Quellzelle Fem-Dat-Pl (`ț`) |
| Passiv   | 90,5 % | weicher `-tas`-Vokalstamm-Passiv (≈ 6 %) nur als Zitierform |
| **gesamt** | **95,6 %** | **99,6 %** der *bewertbaren* Zellen |

Verbleibende Lücken: (a) der weiche `-tas`-Passiv (eigenes Mini-Paradigma,
Standardvariation zwischen den Quellen — hier nur Mask-Nom-Sg-Zitierform),
(b) eine in der Quelle korrupt gerenderte Zelle (`ț`), (c) ~7 Verben mit
quellenabweichendem Partizipstamm.

Neu generieren:

```sh
python scripts/gen_participles.py
make -C fst                 # baut prusaspira.hfst neu
PYTHONPATH=src python tests/test_participles.py
```
