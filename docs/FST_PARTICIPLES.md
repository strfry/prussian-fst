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

## Zwei Stammgrade (Präsens & Passiv)

Präsens (≈ P29) und Passiv (≈ P69, harter t-Stamm) flektieren mit **zwei
betonungsbedingten Stammgraden**:

```
dānts (lang, die meisten Zellen)   vs   dantimmans / dantī (kurz, Dat-Pl + Fem-Nom-Sg)
```

In den betonungstragenden Zellen (Dat-Pl aller Genera, Fem-Nom-Sg; Passiv
zusätzlich Nom-Pl) wandert die Betonung auf die Endung; der Stammvokal kürzt,
die Endung wird „schwer“ (geminiert/lang). Die **More bleibt erhalten**:
entweder *langer Stamm + leichte Endung* oder *kurzer Stamm + schwere Endung*.

Welche der beiden Realisierungen attestiert ist, hängt vom **lexikalischen
Akzent** ab (z. B. `abōnitai` vs `artāi`) — der noch nicht in `stress.twolc`
modelliert ist. Daher emittiert der FST für diese akzentbedingten Zellen
**beide** Realisierungen; der Analysator akzeptiert beide, die Generierung gibt
beide aus (Ø 1,13 Oberflächenvarianten je Analyse).

Das **Prät.-Aktiv-Partizip** (≈ P68, `-uns`/`-us-`) hat einen invarianten Stamm
und dekliniert vollständig aus einem Stamm + festen Endungen.

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
| Präsens  | 95,2 % | ≈ 99,4 % ohne die **korrupte** Quellzelle Fem-Dat-Pl (`ț`) |
| Passiv   | 88,3 % | weicher Vokalstamm-Passiv (≈ 6 %) nur als Zitierform |
| **gesamt** | **94,9 %** | |

Verbleibende Lücken: (a) der weiche `-as`-Passiv (eigenes Mini-Paradigma, hier
nur Mask-Nom-Sg-Zitierform), (b) eine in der Quelle korrupt gerenderte Zelle,
(c) die wenigen rein akzentbedingten Restfälle.

Neu generieren:

```sh
python scripts/gen_participles.py
make -C fst                 # baut prusaspira.hfst neu
PYTHONPATH=src python tests/test_participles.py
```
