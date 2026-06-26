# Partizip-Deklination im FST

Drei Dateien, klare Arbeitsteilung:

| Datei | Inhalt | Pflege |
|-------|--------|--------|
| [`fst/verb_participles.lexc`](../fst/verb_participles.lexc) | die fünf Endungsparadigmen (Past, Pres·Mob/Bar, Pass·Mob/Bar) | **von Hand** |
| [`fst/stress.twolc`](../fst/stress.twolc) | Akzentshift-Regel (Vokalkürzung) | **von Hand** |
| [`fst/verb_participle_stems.lexc`](../fst/verb_participle_stems.lexc) | ein Zitierstamm je Verb je Partizip + Routing | generiert ([`scripts/gen_participles.py`](../scripts/gen_participles.py)) |

Eingehängt über die `Makefile`-Liste `LEXC_FILES`, erreichbar aus `root.lexc`
via `LEXICON VParticiples`.

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

## Stamm: ein Zitierstamm je Partizip

Der FST konkateniert literal. Jedes der drei Partizipien dekliniert wie ein
Adjektiv aus **einem** Stamm — dem langen (barytonen) Zitierstamm, gewonnen aus
seiner eigenen attestierten Mask-Nom-Sg-Form (Endung abstreifen). Damit ist die
Gemination/Länge der Grundform automatisch korrekt:

| Partizip | Form  | Stamm | Paradigma |
|----------|-------|-------|-----------|
| Präsens  | imānts | `imān`  | `PtcpPres{Mob,Bar}` |
| Prät-Akt | immuns | `imm`   | `PtcpPast` |
| Passiv   | īmts   | `īm`    | `PtcpPass{Mob,Bar}` |

Die finiten Verbstämme (Indikativ `imm`, Infinitiv `īm`) passen **nicht** als
Partizipstamm: das Präsenspartizip braucht den entgeminierten Grad (`imān`, nicht
`imm`), der sich weder aus dem Indikativ- noch aus dem Infinitivstamm ergibt.

## Akzentshift als twolc-Regel (Präsens & Passiv)

Präsens (≈ P29) und Passiv (≈ P69) flektieren mit **zwei betonungsbedingten
Stammgraden** (Rinkevičius 2009, [docs/AKZENT.md](AKZENT.md)):

- **Barytona** (feste Stammbetonung): der Stamm behält in *allen* Zellen seinen
  Akzent; die Endungen sind durchweg schwach → `abōnit-i`, `abōnit-ai`.
- **Mobilia** (mobile Betonung): in den **starken Zellen** zieht die Endung den
  Akzent vom Stamm; der Wurzelvokal entakzentuiert → `aikant-ī`, `aikat-āi`.

Starke Zellen sind **Dat-Pl** und **Fem-Nom-Sg** (Präsens), beim Passiv zusätzlich
**Nom-Pl**. Statt für jedes Lexem einen vorberechneten Kurzstamm abzulegen, tragen
die **starken Endungen der `…Mob`-Paradigmen** ein `DEAC`-Trigger-Symbol an der
Stamm-Endungs-Grenze. `stress.twolc` kürzt davor jeden langen/gravischen
Stammvokal und löscht den Trigger:

```
aikānt DEAC ī   →  aikantī
aikāt  DEAC āi  →  aikatāi      (das ā der Endung bleibt — es steht nach DEAC)
```

Die `…Bar`-Paradigmen nehmen in denselben Zellen die schwache Endung ohne Trigger;
der Stamm bleibt lang. Die **Akzentklasse ist lexikalisch idiosynkratisch** — aus
der Zitierform nicht ableitbar — und wird pro Lemma aus prusaspiras
`full_declension` gelesen (starkes vs schwaches Allomorph in einer starken Zelle:
Präsens Fem-Nom-Sg `ī`/`i`, Passiv Mask-Nom-Pl `āi`/`ai`); twanksta-only-Verben
bekommen den Default `Mob` (die 96-%-Mehrheit). Das **Prät.-Aktiv-Partizip**
(≈ P68) hat einen invarianten Stamm ohne Akzentwechsel.

## Tagschema

```
<lemma>+V+Part+<Pres|Pret|Pass>+<Masc|Fem|Neut>+<Sg|Pl>+<Nom|Gen|Dat|Akk>
```

Reflexiva behalten `% si` im Analyse-Lemma; die Oberfläche lässt das Klitikon weg.

## Abdeckung (gegen `prusaspira full_declension`, 116 520 Zellen)

| Partizip | exakt | Anmerkung |
|----------|-------|-----------|
| Prät-Akt | 99,7 % | invarianter Stamm, vollständig regulär |
| Präsens  | 95,3 % | ≈ 99 % ohne die **korrupte** Quellzelle Fem-Dat-Pl (`ț`) |
| Passiv   | 88,6 % | weicher `-tas`-Passiv + Geminat-Entakzentuierung (s. u.) |
| **gesamt** | **95,0 %** | |

Verbleibende Lücken:
1. **Korrupte Quellzelle**: Präsens Fem-Dat-Pl ist in der Quelle mit `ț`
   (t-Cedille statt `t`) gerendert — unmatchbar, betrifft ~1 760 Zellen.
2. **Weicher `-tas`-Vokalstamm-Passiv** (Standardvariation, eigenes Thema): nur
   als Mask-Nom-Sg-Zitierform abgelegt.
3. **Geminat-Entakzentuierung**: bei ~99 mobilen Verben ist der Akzentexponent ein
   *medialer Geminat* (`audribbint → audribint`), kein Langvokal. Die twolc-Regel
   kürzt nur Vokale; eine stabile Geminat-Tilgungsregel ist in hfst-twolc nicht
   formulierbar (Tilgungsregeln mit Kleene-Stern-Kontext explodieren). Diese
   wenigen starken Passivzellen bleiben langgradig.

Neu generieren:

```sh
python scripts/gen_participles.py
make -C fst                 # baut prusaspira.hfst neu
PYTHONPATH=src python tests/test_participles.py
```
