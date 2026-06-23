# Backlog

## Datenmodell

- [x] **Archiphoneme auf eigene Symbole** (Notation) — erledigt: Archiphoneme
      sind jetzt die distinkten Symbole `Â Ê Î Ô Û` (oracle.ARCHI) statt nackter
      Großbuchstaben A/E/I/O/U. Damit kollidieren literale Großbuchstaben nicht
      mehr mit der Archiphonem-Notation. Umgesetzt in oracle/nominals/verbs/
      morphology.lexd/phonology/hfst.rules + Gold-Migration (goldstandard.py
      emittiert die neue Notation). Coverage-neutral, Gold-Parität 1471/1471.
- [ ] **Großschreibung als Lemma-Eigenschaft** (Folgeschritt) Eigennamen wie
      `Afrika`/`Ewangēlijan` werden noch casegefaltet (`resolve_stem`/
      `render_stem`), sodass die Oberfläche kleingeschrieben generiert wird und
      großgeschriebene Wörterbuchformen (~2.900, ≈5 pp Coverage) nicht direkt
      analysieren. Naiv-Fix (Case erhalten) regressiert Lexeme mit
      großgeschriebenem Lemma + kleingeschriebenen Formen; sauber wäre
      Casefolding + Großschreibung als separate, am Wortanfang reapplizierte
      Lemma-Eigenschaft (oder case-insensitive Lookup im lenient-Pfad).

## Orthographische Normalisierung

- [x] **elektr-/elaktr-** Twanksta `elektrō-` vs Prusaspira `elaktrō-`
      → erledigt 2026-06-13: V-Stammvariante in `lexd_gen.py`,
      akzeptiert von `build/lenient.fst` (Test: `tests/test_ortho.py`)

- [x] **Steigerungs-Formant `š` ↔ `sj`** Der Komparativ-/Superlativformant
      palatalisiert das Formant-s vor a-anlautender weicher Endung; der
      Goldstandard backt das literal als `š` ein (`aišas`, Template AIS/UIS in
      `data/spec/adj_comparison.json`), Twanksta schreibt dieselbe Zelle als
      `sj` (`spārtaisjas`, `māldaisjas`). → erledigt: `sj_variant` in
      `spellrelax.py` emittiert die V-Variante, nur `lenient.fst` akzeptiert
      sie. Hebt die Adjektiv-Form-Coverage von 43,3 % auf 52,3 % (+9 pp,
      +6.759 Formen, ausschließlich über den nachsichtigen Pfad; der
      Standard-Analysator bleibt unverändert).

- [ ] **Nom sg -as/-us vs -s** Paradigmen P25/P32 haben Nom-sg-Suffix
      wahlweise `-as`/`-us` statt `-s`.  Stamm-Extraktion in
      `wordlist_to_entries` muss das erkennen:
      - `milimētras <32>`: Stamm ist `milimētr`, Nom-sg-Suffix ist `as`
      - `elektrōmagnētiskas <25>`: Stamm ist `elektrōmagnētisk`, nicht
        `elektrōmagnētiska`
      - Die `-s`-Form (z.B. `milimētrs`, `elektrōmagnētisks`) soll als
        zusätzliche Variante generiert werden (transparenterer Stamm).

- [ ] **Ortho-FST auf -as/-us decken**  Die 7 P25-`-as`-Wörter und
      P32-`-as`/`-us`-Wörter müssen vom Ortho-FST auf ihre `-s`-Varianten
      abgebildet werden (z.B. `elektrōmagnētiskas` → `elektrōmagnētisks`).

## Coverage-Lücken

- [ ] **P52** (4.618 unmatched) — feminine ī/ā-Stämme, viele Komposita
- [ ] **P25** (1.549 unmatched) — nach Diakritika-Fix und -as-Fix
- [ ] **P29/P68/P69/P49** — Paradigmen fast ohne Wortlisteneinträge
- [ ] **P32** `abazzai` etc. (1.219 unmatched) — Twanksta-Gemination
- [ ] **P35a** (815 unmatched) — Neutra auf -in/-an
