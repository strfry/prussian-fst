# Handoff: POS-Bestimmung über Übersetzungs-Tagging (stanza)

## Warum ein Handoff?

Die „Bestimmung" (Wortart-Zuweisung) läuft heute rein regelbasiert in
`classify()` (`src/prussian_fst/gen_lexc.py`) aus `desc` + `paradigm`. Einträge
ohne verwertbares Signal fallen auf `"unknown"` und werden **still aus dem FST
gedroppt** (`gen_lexc.py`, Z. 494–497) — v. a. die `↑…`-Querverweis-Stubs.

Idee: für genau diese Einträge die vorhandenen Glossen (DE/EN/LT/LV/PL/RU) mit
einem Standard-POS-Tagger nachbestimmen. **stanza** deckt alle sechs Sprachen ab
(spaCy fehlt LT + LV). Das Problem: stanza lädt seine UD-Modelle beim ersten Lauf
von externen Servern — in der **Cloud-/Agent-Proxy-Umgebung meist blockiert**.

Deshalb ist der Ablauf zweigeteilt:

| Schritt | Netz nötig? | Wo ausführen |
|---|---|---|
| **A** Tagging + Modell-Download → POS-Map erzeugen | **ja** | **lokal** (dieser Handoff) |
| **B** POS-Map als Fallback in die Pipeline einspeisen | nein | Repo / Cloud |

## Schritt A — lokal ausführen

Voraussetzung: lokaler Checkout dieses Branches **mit** `data/external/`
(die große `prussian_dictionary.json` liegt bereits im Repo).

```bash
# 1. Umgebung (getrennt vom Build; stanza ist bewusst KEINE Projekt-Abhängigkeit)
python3 -m venv .venv-handoff
source .venv-handoff/bin/activate
pip install stanza

# 2. Erst klein testen (lädt die 6 UD-Modelle, prüft den Netzzugang)
python3 tools/pos_from_translations.py --limit 50

# 3. Kompletter Lauf
python3 tools/pos_from_translations.py
```

Ergebnis:

- `data/reports/pos_from_translations.json` — pro Eintrag: `inferred_pos`,
  `confidence` (Anteil der Sprachen für die Mehrheit), `votes` je Sprache,
  verwendete `glosses`.
- `data/reports/pos_from_translations.tsv` — schnelle Sicht-/Review-Tabelle.

Was das Skript tut (`tools/pos_from_translations.py`):

1. lädt das Dictionary und **importiert `classify()` aus dem Repo** (bleibt so
   automatisch synchron mit der echten Bestimmung),
2. filtert auf `classify(e) == "unknown"`,
3. taggt je Sprache die Glosse, nimmt die Wortart des **Kopf-Tokens** (letztes
   Inhaltswort — `day-labourer`→NOUN, `to destine`→VERB),
4. mappt UPOS → interne Klasse und stimmt über die Sprachen **mehrheitlich** ab.

## Schritt B — netzfrei einspeisen (Folge-PR)

Die erzeugte JSON committen und in `classify()` als **letzten Fallback** nutzen —
**nur** im `"unknown"`-Zweig (Z. 247), damit `desc`/`paradigm` immer Vorrang
behalten:

```python
# in gen_lexc.py, unmittelbar vor `return "unknown"`
pos = _TRANSLATION_POS.get(e.get("word"))   # aus data/reports/pos_from_translations.json geladen
if pos:
    return pos
return "unknown"
```

Empfehlung: nur Vorschläge mit `confidence >= 0.6` übernehmen und eine
Review-Runde über die `↑`-Stubs fahren (bei denen ist die Wortart des
**Verweisziels** oft die verlässlichere Quelle als die Glosse).

## Reichweite (gemessen an `prussian_dictionary.json`)

`classify()` liefert **1164** `"unknown"`-Einträge. Davon:

| Gruppe | Anzahl | mit ≥1 Glosse | geeignete Methode |
|---|---:|---:|---|
| `↑`-Querverweis-Stubs | 1026 | **40** | **Verweisziel-Erbung** (Glossen fast immer leer) |
| übrige (desc-los o. ä.) | 138 | **138** | **Übersetzungs-Tagging** (dieser Handoff) |
| **Summe mit Glosse** | | **178** | Reichweite des Taggers |

Kernaussage: Das Tagging erreicht **genau die 178 Einträge mit Glosse** — vor
allem die 138 Nicht-`↑`-Fälle, die es vollständig abdeckt. Die 1026 `↑`-Stubs
sind **kein** Tagger-Problem (keine Glossen) — dort ist die Wortart aus dem
Verweisziel zu übernehmen; das ist ein separater, netzfreier Schritt.

## Methodische Vorbehalte

- Glossen-POS ≠ Lemma-POS des Preußischen (Nominalisierungen, cross-linguale
  Verschiebungen). Deshalb **nur Fallback/Tie-Breaker**, nie Override.
- Isolierte Kurz-Phrasen taggen unschärfer als Fließtext → Mehrheitsvotum über
  sechs Sprachen dämpft Ausreißer.
- Pronomen sind hand-gepflegt (`pronouns.lexc`) und werden ohnehin übersprungen;
  `PRON`/`DET`-Vorschläge dienen nur der Sichtung.

## Rückgabe an mich

Committe `data/reports/pos_from_translations.json` auf diesen Branch (oder häng
sie an) — dann übernehme ich Schritt B (Einbau in `classify()`, Coverage-Report,
Tests) netzfrei in der Cloud.
