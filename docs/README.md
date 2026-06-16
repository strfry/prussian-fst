# Dokumentations-Index

Diese Übersicht ordnet jede Doku-Datei nach **Typ** und **Status**, damit auf einen
Blick klar ist, was dauerhafte Referenz, was eine getroffene Entscheidung und was
eine offene Frage ist. Dateien bleiben flach in `docs/` (Pfade sind stabil, weil
Code und `data/spec/` darauf verweisen).

## Status-Legende

| Symbol | Bedeutung |
|---|---|
| 📘 Referenz | Theorie/Spezifikation, dauerhaft gültig |
| ✅ Entschieden | Linguistische Entscheidung getroffen **und** im Code/Daten umgesetzt |
| 🔶 Offen | Frage noch nicht entschieden |
| 🚧 In Arbeit | Migration/Umbau begonnen, noch nicht abgeschlossen |

## Quelle der linguistischen Wahrheit

Die linguistischen SPEC-Tabellen (Endungen, Routing, Suppletiva) liegen **als Daten**
in [`data/spec/`](../data/spec/) — jede Datei trägt im `_meta`-Block Begründung,
Quelle und Status. Der Python-Code enthält nur noch die Mechanik, die diese Daten
liest. Das *Warum* steht in den Entscheidungs-Dokumenten unten, das *Was* in
`data/spec/` — beide sind gegenseitig verlinkt.

| SPEC-Datei | Konsument | Entscheidungs-Doku |
|---|---|---|
| [`data/spec/adj_comparison.json`](../data/spec/adj_comparison.json) | `gold/adj_comparison.py` | [HANDOFF_allomorphie_steigerung.md](HANDOFF_allomorphie_steigerung.md) |
| [`data/spec/verb_inflection.json`](../data/spec/verb_inflection.json) | `fst/morphology/verbs.py` | [HANDOFF_verb_modi_konditionierung.md](HANDOFF_verb_modi_konditionierung.md), [FST_VERB_HANDOFF.md](FST_VERB_HANDOFF.md) |
| [`data/spec/nominal_routing.json`](../data/spec/nominal_routing.json) | `fst/morphology/nominals.py` | [HANDOFF_paradigma40.md](HANDOFF_paradigma40.md) |

## Alle Dokumente

### 📘 Referenz (Theorie / Spezifikation)

| Datei | Inhalt |
|---|---|
| [AKZENT.md](AKZENT.md) | Akzentmodell nach Rinkevičius 2009 (Barytona/Mobilia) — hergeleitet von `gold/accent.py` |
| [ORTHO_RULES.md](ORTHO_RULES.md) | Orthographische Regelschicht (Archiphoneme, J-Palatalisierung, Vokalkürzung) |
| [gramatiki.md](gramatiki.md) | Grammatik-Referenz (Konjugation, Partizipien, Adverbien) |
| [FORMATS.md](FORMATS.md) | Datenformat-Spezifikation (HTML-Parsing der Quellen) |
| [PROVENANCE.md](PROVENANCE.md) | Herkunfts- und Vertrauenskette der Daten (Tabula/Prusaspira/Twanksta) |
| [references.md](references.md) | Literaturliste (Mažiulis, Rinkevičius, Palmaitis/Klusis, Kortlandt) |

### ✅ Entschieden & umgesetzt

| Datei | Entscheidung | SPEC |
|---|---|---|
| [HANDOFF_allomorphie_steigerung.md](HANDOFF_allomorphie_steigerung.md) | Adjektiv-Steigerung: Formant `-ais-`/`-uis-` + weiche Deklination; Suppletiva wie P26 | `data/spec/adj_comparison.json` |
| [HANDOFF_paradigma40.md](HANDOFF_paradigma40.md) | P40-Subtypen 40a/40b/40c nach Stammauslaut (Auto-Routing) | `data/spec/nominal_routing.json` |
| [HANDOFF_verb_modi_konditionierung.md](HANDOFF_verb_modi_konditionierung.md) | Präsens-Stamm-Modi, Partizip-Deklination, Imperativ-Klassen | `data/spec/verb_inflection.json` |
| [FST_VERB_HANDOFF.md](FST_VERB_HANDOFF.md) | Verb-FST: Drei-Stamm-Modell, 60 Paradigmen | `data/gold/goldstandard_verben_fst.json`, `data/spec/verb_inflection.json` |

### 🔶 Offen (zu entscheiden)

| Datei | Offene Frage |
|---|---|
| [HANDOFF_allomorphie.md](HANDOFF_allomorphie.md) | Nominale Stamm-Allomorphie (Gemination/Palatalisierung/Ablaut) — 3 Modellierungs-Optionen, keine Entscheidung |
| [BACKLOG.md](BACKLOG.md) | Sammelliste offener TODOs (u. a. `-as/-us`-Epenthese, Großbuchstaben) |

Weitere offene Punkte ohne eigene Datei (in den jeweiligen Dokumenten notiert):
P28 `māldaisis`-Homonymie (Komparativ vs. Substantiv) und die `tūls/mūises-`-Datenlücke
(beide in [HANDOFF_allomorphie_steigerung.md](HANDOFF_allomorphie_steigerung.md)).

### 🚧 In Arbeit (Migration)

| Datei | Inhalt |
|---|---|
| [HFST_Hybrid_Migration.md](HFST_Hybrid_Migration.md) | Plan: generalisierende Leniency über HFST komponieren statt V-Zeilen aufzählen |
| [HFST_SPIKE.md](HFST_SPIKE.md) | Spike-Bericht (Machbarkeit pyfoma ↔ HFST) — Grundlage der Migration |
