# Pipeline & Modul-Landkarte

Wozu dient welcher Code, und in welcher Reihenfolge entsteht der FST? Diese
Übersicht trennt **Laufzeit** (was den fertigen Analysator nutzt) von der
**Daten-Pipeline** (was die Gold-Daten und den FST erzeugt) und den **Dev-Tools**
(manuell, nicht Teil des automatischen Builds).

## Laufzeit (nutzt nur die fertigen Artefakte)

Der ausgelieferte Analysator besteht aus den kompilierten FSTs in `build/` plus
dem Tag-System. Zum Analysieren wird **nicht** der Generator-Code gebraucht:

- `fst/analyze.py` — CLI: Wörter/Sätze gegen `build/analyser.fst` / `lenient.fst`
- `fst/tags.py` — morphologisches Tag-System (Genus, Kasus, Tempus, Modus)
- `build/analyser.fst`, `build/lenient.fst` — kompilierte Transduktoren

## Daten-Pipeline (erzeugt Gold-Daten → FST)

Reihenfolge der Erzeugung. Schneller Build via PyPy (s. Memory): `PYTHONPATH=src
pypy3 -m <modul>`.

```
                data/external/tabula.html   (aus prussian-corpus)
                            │
   ┌────────────────────────┼─────────────────────────┐
   ▼                        ▼                          ▼
gold/goldstandard.py   gold/goldstandard_verbs.py   (Partizip-Extraktion)
   │  → goldstandard.json   │  → goldstandard_verben.json (kuratierte Quelle)
   │                        │  → goldstandard_verben_fst.json (FST-Form, abgeleitet)
   ▼
gold/adj_comparison.py  (hängt comp/sup-Einträge an goldstandard.json an)
   │
   ▼
gold/accent.py  → accent_model.json   (Akzentklassen, Rinkevičius)
   │
   ▼
fst/build.py    goldstandard.json + goldstandard_verben_fst.json + twanksta_entries.json
                 + data/closed/*.json
                → build/morphotactics.lexd → (pyfoma) → build/analyser.fst, lenient.fst
```

`fst/build.py` (Einziger registrierter Entry-Point `prussian-fst-build`) komponiert
laut eigenem Kopfkommentar: `morphotactics.lexd ∘ Regelschicht`. Die SPEC-Tabellen,
die `adj_comparison.py`, `verbs.py` und `nominals.py` dabei verwenden, liegen
ausgelagert in [`data/spec/`](../data/spec/) (s. [README.md](README.md)).

### Quelle vs. abgeleitet bei den Verb-Gold-Dateien

Kein Duplikat, sondern zwei Stufen:

- `data/gold/goldstandard_verben.json` — **kuratierte Quelle** (aus tabula via
  `goldstandard_verbs.py`); menschenlesbar.
- `data/gold/goldstandard_verben_fst.json` — **abgeleitet** daraus (FST-Form,
  Stamm+Suffixe je Paradigma/Tempus); Eingang für `fst/build.py`.

## Dev-Tools (manuell, nicht im automatischen Build)

Diese Module haben `if __name__ == "__main__"` und werden bei Bedarf direkt
aufgerufen; sie sind **nicht** in den Build importiert.

> Das frühere `fetch/`-Paket (Crawlen von prusaspira.org / Twanksta) wurde
> entfernt; Quellbeschaffung **und Parsing** liegen jetzt in
> [prussian-corpus](https://github.com/strfry/prussian-corpus). Die Artefakte
> kommen über `data/external/`.

| Modul(e) | Zweck |
|---|---|
| `compare/compare_sources.py`, `compare_verbs.py`, `compare_paradigms.py` | Quellen-Vergleich → `data/derived/vergleich*.json/html` (Validierung, **kein** Build-Input) |
| `compare/extract_paradigms.py`, `extract_participles.py`, `parse_verbs.py` | Extraktion/Parsing aus Quellen-HTML (Analyse-Werkzeuge) |
| `report/dashboard.py`, `corpus_coverage.py`, `dict_coverage.py`, … | Metriken/Reports → `data/derived/` und Dashboard |

## Tests

`pytest` (über `.venv`, mit `PYTHONPATH=src`). Lädt die fertigen FSTs aus `build/`
und die Gold-Daten aus `data/gold/`; baut für die Report-Guardrails einmalig das
Dashboard. Roundtrip-, Coverage-, Ortho- und Accent-Tests prüfen das
Analyse-/Generierungsverhalten.
