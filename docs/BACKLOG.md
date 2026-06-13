# Backlog

## Datenmodell

- [ ] **Großbuchstaben ↔ Archiphonem-Kollision** Eigennamen wie
      `Ewangēlijan` liefern Stämme mit initialem Großbuchstaben
      (`EwangElij`), der von der Archiphonem-Notation (Großbuchstabe =
      alternierender Vokal) nicht unterscheidbar ist — das Initial wird
      mitgedehnt/gekürzt. Schon im alten `resolve_stem` so (Bug-Parität).
      Fix: Stämme casefolden + Großschreibung als Lemma-Eigenschaft
      separat führen, oder Archiphoneme auf eigene Symbole umstellen.

## Orthographische Normalisierung

- [x] **elektr-/elaktr-** Twanksta `elektrō-` vs Prusaspira `elaktrō-`
      → erledigt 2026-06-13: V-Stammvariante in `lexd_gen.py`,
      akzeptiert von `build/lenient.fst` (Test: `tests/test_ortho.py`)

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
