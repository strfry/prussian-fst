# Plan (fst): kanonische Tag-Reihenfolge herstellen — gender-first

## Ziel
Der Analyzer (und damit `build/base.gen.hfstol`) soll die **nominale Deklination
in derselben Reihenfolge emittieren wie die handgeschriebenen Generatoren
`gen/*.lexc`**: Genus VOR Numerus VOR Kasus. Das ist die GiellaLT-idiomatische
Reihenfolge (Russisch-Präzedenz: Nomen `+N+Msc+…`, Adjektiv `+Msc+Sg+Nom`) und
beseitigt die Analyzer↔Generator-Divergenz.

**Nur die REIHENFOLGE ändern. Tag-NAMEN bleiben unverändert** (`+Akk` bleibt `+Akk`,
`+Pret` bleibt `+Pret` — kein Rename in diesem Schritt).

## Kanonische Reihenfolge (Zielzustand)
| Kategorie | Tag-String |
|---|---|
| Nomen | `+N +{Gender} +{Num} +{Case}` |
| Adjektiv | `+Adj [+Cmp\|+Sup] +{Gender} +{Num} +{Case}` |
| Partizip | `+V +Part +{Pres\|Pret\|Pass} +{Gender} +{Num} +{Case}` |
| Verb finit/Inf/Imp/Opt/Subj | **UNVERÄNDERT** (schon idiomatisch: Mood/Tense/Person/Number) |

## Änderungen: `src/prussian_fst/gen_lexc.py`
Die Emission ist an mehreren Format-Strings verstreut. Aktuell steht Genus HINTER
Num+Kasus (`+{num}+{case}{gender}`); es muss DAVOR (`{gender}+{num}+{case}`).

1. **`nominal_forms`** (~Z. 285): `f"{pos_tag}{subtype_tag}{deg_tag}+{num_tag}+{c_tag}{g_tag}"`
   → `f"{pos_tag}{subtype_tag}{deg_tag}{g_tag}+{num_tag}+{c_tag}"`
   (`g_tag` enthält bereits sein führendes `+`, z.B. `+Masc`; `c_tag` nicht.)
2. **Partizip allgemein** (~Z. 453): `…+V+Part+{tag}+{num_tag}+{c_tag}{g_tag}{refl}…`
   → `…+V+Part+{tag}{g_tag}+{num_tag}+{c_tag}{refl}…`
3. **Partizip-Fallback bare** (~Z. 455): `+Sg+Nom+Masc` → `+Masc+Sg+Nom`
4. **Nominale Zitierform** (~Z. 565): `{tag}{subtype}+Sg+Nom{gender}` → `{tag}{subtype}{gender}+Sg+Nom`
5. **Pret-Nominativ-Pfad** (~Z. 344): `f"Part+Pret+{gend}+{num}+Nom"` ist BEREITS
   gender-first — **nicht ändern**. Nach Fix (2) erzeugen beide Pfade denselben
   String und deduplizieren automatisch (results ist ein dict).

**Absicherung:** Nach den Edits `grep -nE '\+(Sg|Pl)\+(Nom|Gen|Dat|Akk)' src/prussian_fst/gen_lexc.py`
und prüfen, dass an KEINER nominalen Stelle noch Genus hinter Num+Kasus steht.
Verben (finite) dürfen `+{Num}` behalten — die tragen kein Genus.

## Rebuild
```
make gen        # regeneriert lexc/*.lexc aus twanksta
make            # base.fst, base.hfstol, base.gen.hfstol neu
```

## Fixtures / Tests anpassen
- **`tests/fixtures/cg3_golden.tsv`**: erwartete Lesarten kodieren die alte
  Reihenfolge (`labs+Adj+Sg+Akk+Fem`, `dēinā+N+Sg+Akk+Fem`). Reorder der
  Trailing-Dimensionen `+{Num}+{Case}+{Gender}` → `+{Gender}+{Num}+{Case}`
  (skriptbar mit Regex über die Spalte der Lesarten). Partizipien analog.
- **CG3-Regeln** (`cg3/*.cg3`): `(Sg Nom Masc)`-Sets sind ungeordnet → **keine
  Änderung nötig**. Nur verifizieren.

## Verifikation (Gates — alle müssen grün sein)
1. `uv run pytest` — alle Tests grün (v.a. `tests/test_cg3.py`, `test_api.py`,
   `test_conllu.py`, `test_validate.py`, `test_linker.py`).
2. `make cg3-check` — CG3 kompiliert.
3. Round-trip Spot-Check (neue Reihenfolge):
   - Analyse: eine Nomen-/Adj-Oberflächenform ergibt `…+N+{Gender}+{Num}+{Case}`.
   - Generierung gegen `build/base.gen.hfstol`: `dēinā+N+Fem+Sg+Akk` → Form;
     die ALTE Reihenfolge `dēinā+N+Sg+Akk+Fem` darf KEINE Form mehr liefern.
4. `git diff --stat lexc/` zeigt die regenerierten Vollform-Dateien.

## Commit
Auf dem aktuellen Branch committen. Nachricht: „fst: canonical gender-first tag
order for nominal declension (analyzer ↔ generator alignment)".

## WICHTIG für das Nachbarrepo
`build/base.gen.hfstol` ändert danach die erwartete Query-Reihenfolge. Das
`dictionary`-Repo (queries.go) MUSS im Gleichschritt umgestellt werden — siehe
dessen `PLAN_tagorder.md`. Erst fst fertig bauen, dann dictionary.
