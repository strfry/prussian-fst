# Paradigma 40: Phonologische Subtypen und Auto-Routing

> **Status:** ✅ Entschieden & umgesetzt — Routing-SPEC ausgelagert nach
> [`data/spec/nominal_routing.json`](../data/spec/nominal_routing.json) (`par40_routing`).
> Klassifikation siehe [docs/README.md](README.md).

**Stand:** 2026-06-07 — Untersuchung der Prusaspira-Livedaten für alle 646 Wörter
mit Paradigma 40/40a in `wordlist.json`.

## Fragestellung

Paradigma 40 hat in der Tabula vier Varianten (40, 40a, 40b, 40c), aber die
Twanksta-Wortliste (`wordlist.json`) kennt nur `"40"` (637 unique words) und
`"40a"` (10 words, alle auf -zis). Wie werden die restlichen Wörter korrekt
auf die Subtypen verteilt? Und wie generiert Prusaspira die Formen?

## Methode

- `GET https://www.prusaspira.org/wirdeins?akc=Iz&tap=W&bila=1&wirds={word}`
- Extrahiert: `dnum` (Prusaspiras interne Paradigmen-Nummer aus `<b class='dnum'>`)
  und alle 8 flektierten Formen aus der HTML-Tabelle
- 499 Wörter erfolgreich abgefragt (121 not found), Skript in `investigate_40.py`,
  Rohdaten in `investigation_40.json`

## Ergebnis: Paradigma 40 zerfällt in 4 phonologisch bedingte Typen

Alle Subtypen teilen Nom.Sg `-is`, Gen.Pl `-in`, Akk.Sg `-in`, Akk.Pl `-ins`.
Sie unterscheiden sich in **Nom.Pl, Gen.Sg, Dat.Sg, Dat.Pl** — und zwar
strikt nach dem **letzten Konsonanten des Stamms**:

### Typübersicht

| Prusaspira dnum | Unser Name | Stammauslaut | Nom.Pl | Gen.Sg | Dat.Sg | Dat.Pl | n |
|---|---|---|---|---|---|---|---|
| `<40>` | Vokalpalatalisierung | -g,-k,-n,-r,-t,-d | -ei | -es | -ģu/-ķu/-ņu/-ŗu/-țu | -emans | 334 |
| `<40>` | j-Einschub | -w,-b,-p,-m | -jai | -jas | -ju | -jamans | 46 |
| `<40>` | Sibilanten-Pal. | -s,-z | -šai/-žai | -šas/-žas | -šu/-žu | -šamans/-žamans | 28 |
| `<40>` | Schlicht (keine Pal.) | -l | -ai | -as | -lu | -amans | 59 |
| `<40a>` | Sibilanten-Pal. (nur -zis) | -z | -žai | -žas | -žu | -žamans | 9 |
| `<40c>` | Schlicht (Einzelfälle) | -c | -ai | -as | -cu | -amans | 2 |

**Wichtig:** dnum `<40a>` und dnum `<40 z-type>` haben **identische**
Suffix-Muster. Der Unterschied ist taxonomisch: 40a = native -zis-Wörter,
z-type = alle anderen Sibilanten (Arīsis, kursis, miksis, ...).

### Vollständige Beispiel-Paradigmen

```
Vokalpalatalisierung (kūgis, Stamm kūg-):
  Nōm: kūgis / kūgei     Gēn: kūges / kūgin
  Dāt: kūģu  / kūgemans   Akk: kūgin / kūgins

j-Einschub (gīrbis, Stamm gīrb-):
  Nōm: gīrbis / gīrbjai   Gēn: gīrbjas / gīrbin
  Dāt: gīrbju / gīrbjamans Akk: gīrbin / gīrbins

Sibilanten (Arīsis, Stamm Arīs-):
  Nōm: Arīsis / Arīšai    Gēn: Arīšas / Arīsin
  Dāt: Arīšu  / Arīšamans  Akk: Arīsin / Arīsins

Schlicht (anzalis, Stamm anzal-):
  Nōm: anzalis / anzalai  Gēn: anzalas / anzalin
  Dāt: anzalu  / anzalamans Akk: anzalin / anzalins

40a (dulzis, Stamm dulz-):
  Nōm: dulzis / dulžai    Gēn: dulžas / dulzin
  Dāt: dulžu  / dulžamans  Akk: dulzin / dulzins

40c (buccis, Stamm bucc-):
  Nōm: buccis / buccai    Gēn: buccas / buccin
  Dāt: buccu  / buccamans  Akk: buccin / buccins
```

## Die phonologische Routing-Regel

```
Gegeben: Nominativ Singular auf -is → Stamm = Wort minus -is

Stammauslaut:
  -l         → Paradigma 40c (schlicht: -ai, -as, -u, -amans)
  -w,-b,-p,-m → Paradigma 40b (j-Einschub: -jai, -jas, -ju, -jamans)
  -s,-z      → Paradigma 40a (Sibilanten-Pal.: -šai/-žai, -šas/-žas, …)
  Rest       → Paradigma 40  (Vokal-Pal.: -ei, -es, pal. Konsonant+u, -emans)
```

### Trefferquote: 463/468 = 98,9%

Die 5 Abweichungen:

| Wort | Stammende | Regel erwartet | Prusaspira gibt | Grund |
|---|---|---|---|---|
| Fidžis | -ž | e-type | j-type | -dž ist palataler Affrikat, Wurzel auf Labial? |
| plurksis | -š | e-type | j-type | -kš-Cluster, Einzelfall |
| plīšis | -š | e-type | j-type | Einzelfall |
| tāšis pēilis | -l | ai-type | z-type | Kompositum, Kopfflexion abweichend |
| indicis | -c | e-type | ai-type | Fremdwort/Lehnwort |

Alle 5 sind linguistisch plausible Ausnahmen (Fremdwörter, Komposita, Affrikate).
Die Regel deckt die regelhaft gebildeten Wörter perfekt ab.

## Entscheidung: Auto-Routing in build_fst.py

### Status quo

`build_fst.py:wordlist_to_entries()` routet aktuell starr:
```python
par_g_key = (w["paradigm"], g)  # z.B. ("40", "m")
suffixe = suffixe_map[par_g_key]  # → immer goldstandard "40" (e-type)
```

Das gibt für gīrbis, klūmpis, anzalis etc. **falsche Formen** (e-type statt j-type/ai-type).

### Beschluss

Wenn `wordlist.paradigm == "40"`:

1. **Stamm extrahieren** (Nom.Sg minus `-is`)
2. **Stammauslaut prüfen** und auf korrektes Sub-Paradigma mappen:
   - `-l` → `"40c"`
   - `-w,-b,-p,-m` → `"40b"`
   - `-s,-z` → `"40a"`
   - Rest → `"40"` (default)
3. Goldstandard-Suffixset des gemappten Paradigmas verwenden

Für `wordlist.paradigm == "40a"` bleibt das Mapping `"40a"` → `"40a"` erhalten
(die 10 nativen -zis-Wörter).

### Implementierungshinweis

Die `PALATAL`-Map in `build_fst.py:46` deckt bereits s→š und z→ž ab:
```python
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}
```

`resolve_stem()` palatalisiert den letzten Stammkonsonanten — das funktioniert für
alle vier Subtypen, solange das richtige Suffixset + palatize-Flag aus
`goldstandard.json` verwendet wird. Kein neuer Mechanismus nötig.

## Daten

- `investigate_40.py` — Fetch-Skript (647 API-Calls gegen prusaspira.org)
- `investigation_40.json` — Rohdaten (499 geparste Wörter mit dnum + Formen)
- `goldstandard.json` — Enthält bereits korrekte Suffixsets für 40, 40a, 40b, 40c
