# Übersicht der verbleibenden Linker-Ambiguitäten

## Kontext

Nach dem Linker-Volllauf (`uv run python -m prussian_fst.linker --stats`)
bleiben **325 „ambiguous"-Fälle** übrig — Verweise aus den `desc`-Feldern
von `twanksta_entries.json`, für die die Analyzer-Kaskade (base → macron →
lenient) mehr als ein Lemma liefert.

Davon sind **194 großgeschriebene Refs** (Lemma-Zitierformen wie `[Advent]`,
`[Grēnztun]`), die ohnehin ignoriert werden. Es bleiben **97 unique
kleingeschriebene Formen**.

Die naheliegende Frage war: Sind das Flexionsform-Kollisionen, die sich
durch **Ergänzungen in der richtigen Regelstufe** (base/macron/lenient)
auflösen lassen?

**Antwort: Nein, größtenteils nicht.** Ein Per-Stufen-Lookup (jede Stufe
getrennt geprüft) zeigt: **~75 der 97 Formen sind schon in `base` ambig** —
beide Kandidaten erzeugen dieselbe Oberflächenform legitim im
Vollform-Lexikon. Regelstufen können das prinzipiell nicht trennen; nötig
wäre echte Lexem-Verknüpfung bzw. eine Präferenzlogik.

Diese Übersicht klassifiziert die 97 Formen und hält die Entscheidung fest,
wie der Linker damit umgeht.

## Entscheidung: Mehrere Kandidaten sind kein Fehlerfall

Mehrere Lemmata für dieselbe Form sind **kein `ambiguous`-Fehler mehr**,
sondern werden als **Cluster** gelinkt: `status = "resolved"`,
`lemmas: [...]`. Alle beteiligten Einträge erscheinen im Cluster als
zusätzliche Form/Übersetzung; gleiches Lexem = echter Chunk.

Konkret gilt das für die Klassen **A/B/C** (lexikalisierte Ableitungen,
Infinitivpaare, Sg-/Pl-tantum-Paare) und **vorerst auch D**
(Makron-Kollisionen). Nur **E** (echtes Rauschen aus fremden Zeichen) wird
im Linker tatsächlich gefixt — und zwar als `gap`, nicht als Treffer.

> Später optional: redundante Lemmata, die im Stammlexem bereits
> beschrieben sind, aus dem Chunk weglassen. **Jetzt noch nicht.**

---

## A. Lexikalisierte Ableitung vs. flektiertes Grundwort (~45 Formen, base-ambig)

**Muster:** Ein Adverb/Substantiv ist ein eigenes Lemma **und** zugleich
eine Flexionsform des zugehörigen Adjektivs/Verbs. Beide Analysen sind
korrekt.

| Form | Kandidaten |
| --- | --- |
| `arwiskai` | `arwiskai` (Adv), `arwisks` (Aj) |
| `labban` | `labban` (N), `labs` (Aj) |
| `madli` | `madli` (N), `madlītun` (V) |
| `mīlan`, `tusnan`, `perōniskan`, `deiwūtiskan` | Adv/N ↔ Aj-Flexion |
| `sēja`, `ēda`, `winzus`, `plattus` | N ↔ Aj/V-Flexion |

→ **Keine Regelstufe hilft**, beide Analysen sind sprachlich richtig.
Adverb ↔ Adjektiv gehören ohnehin demselben Wortfeld an.

**Auflösung:** Als Cluster linken. (Optionale spätere Präferenz-Heuristik:
den Kandidaten bevorzugen, der case-insensitiv dem `orig_lemma` des
Eintrags entspricht — ein Verweis belegt meist das eigene Lemma; sonst als
„verwandt, beide behalten" markieren.)

## B. `tun`/`twei`-Infinitivpaare (~10 Formen, base-ambig)

`dāst` / `dais` / `dāiti` → `[dātun, dātwei]`; ebenso `brewinnimai`,
`lista`, `burtas`, `klantīwuns`, `deggus` … — **dasselbe Lexem mit zwei
Zitierformen** im Wörterbuch (`-tun`- und `-twei`-Infinitiv).

→ Kein Regelstufen-Thema. Als **ein** Treffer werten (kanonisch z. B.
`-tun`) bzw. beide als gleichwertigen Cluster ausgeben.

## C. Sg-/Pl-tantum-Lemmapaare (~10 Formen)

Das Wörterbuch führt Singular- und Plurale-tantum-Variante als getrennte
Lemmata:

| Form | Kandidaten |
| --- | --- |
| `wissan` / `-as` / `-ans` | `wiss`, `wisāi` |
| `deinan(s)` | `dēinā`, `dēināi` |
| `tūlan` | `tūlan`, `tūlāi` |
| `taukai` | `taūks`, `taūkāi` |
| `penningans` | `pennings`, `penningāi` |

→ Wie B: Lemmapaar (gleicher Stamm) zusammenfassen, per Regel nicht
trennbar.

## D. Erst durch die Makron-Stufe kollidierend (~15 Formen, inhärent)

| Form | Kandidaten | Anmerkung |
| --- | --- | --- |
| `wargan` | `wārgan`, `wārgs` | |
| `spartin` | `spārtis`, `spārts` | |
| `laukan` | `laūks`, `lāuks` | |
| `wagā` | `wagā`, `wāgā` | echtes Makron-Minimalpaar! |
| `maldaisin` | `māldaisis`, `mālds` | |
| `senti` / `seisei` | `būtwei` + Rausch (`sētun`) | |

→ Das ist der **Preis der `macron`-Stufe selbst**: Eine „richtige
Regelstufe" existiert nicht, weil die unterscheidende Information (das
Makron) in der Korpusschreibung schlicht fehlt. Nur über die A-Heuristik
(`orig_lemma`) oder Kontext auflösbar. Die `būtwei`-Belegformen (`asmai`,
`assei`, `senti`, `seisei`) sind korrekt via `orig_lemma = būtwei`.

Vorerst ebenfalls als Cluster gelinkt.

## E. Bugs / Noise (~5 Formen) — die einzigen echten Fixes im Linker

Hier lagen tatsächliche Fehlmatches vor:

- `kaļķis` → `[ka, kas]`, `pastāvēt` → `[pastā, pāstun]`, lat. `portus` →
  `[lāt, lātwei]`: `pyhfst` (`fst_lookup.flookup_batch`) verwirft
  FST-fremde Zeichen (`ļ`, `ķ`, `v`, `é`) offenbar still, statt die Form zu
  rejecten → **Präfix-Müll-Matches**.
- lat. `portus`: Der Sprachkürzel-Token `lat.` wurde als Wortform behandelt.

**Fix (umgesetzt):**

1. **Alphabet-Guard in `resolve_form`:** Formen mit Zeichen außerhalb des
   FST-Alphabets (`a–z` + `āēīōū`, case-insensitiv; Leerzeichen/Bindestrich
   erlaubt) werden gar nicht erst nachgeschlagen → `gap` statt Müll-Match.
2. **`parse_desc`:** Tokens mit `.` (Sprachkürzel wie `lat.`, `lit.`)
   werden verworfen.

---

## Umsetzung im Linker (`linker.py`)

1. **Cluster statt ambiguous:** `resolve_form` gibt bei ≥ 1 Lemma
   `status = "resolved"` mit `lemmas: [...]` (sortiert) zurück; `method`
   bleibt der Stufenname. Einzeltreffer sind einfach ein einelementiges
   `lemmas` — einheitliches Schema. Der Status `ambiguous` entfällt.
2. **Großschreibung überspringen:** In `resolve_corpus` werden Refs mit
   großem Anfangsbuchstaben (`ref[:1].isupper()`) übersprungen (weder Link
   noch `unresolved`).
3. **Alphabet-Guard + Punkt-Filter:** siehe E.

## Verifikation

```
uv run pytest tests/test_linker.py
uv run python -m prussian_fst.linker --stats
```

**Erwartung nach dem Umbau:**

- `unresolved` besteht nur noch aus **echten `gap`s** (kein `ambiguous`
  mehr).
- Müll-Matches (`kaļķis → ka`, `lat. portus → lāt`) verschwinden — sie
  werden zu `gap`.
- `resolved` steigt um die ~300 Cluster-Fälle (die vormals `ambiguous`
  waren), davon in der Stats-Zeile „Cluster (mehrere Lemmata)" ausgewiesen.
