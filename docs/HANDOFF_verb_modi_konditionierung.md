# Handoff: Konditionierung der Präsens-Stamm-Modi (Verb-Rollout Stufe 2)

## Kontext

Der FST modelliert Verben nach dem baltischen **Drei-Stamm-Modell** (Inf-/Präs-/
entgeminierter Stamm), die Modus-Suffixe sind **universell** (ein Set über alle
Paradigmen), Oberflächen-Unterschiede sind phonologisch.

**Stufe 1 ist erledigt** — die drei *Inf-Stamm*-Kategorien generieren für alle
attestierten Verben (76 % Trefferquote, P71 unverändert):

| Kategorie | Suffix | Stamm | Beispiel |
|---|---|---|---|
| Optativ | `-sei` | Inf | `īmsei`, `lānksei`, `bresei` |
| Konjunktiv | `-lai/-limai/-litei` | Inf | `īmlai`, `lānklai`, `bredlai` |
| Passivpartizip | `-ts` | Inf | `īmts`, `lānkts`, `brests` |

Trick: der lemma-spezifische Stamm wird je Kategorie durch **Abstreifen des
universellen Suffixes von der attestierten Form** gewonnen → `stem+suffix==Form`
per Konstruktion, Grenz-Sandhi (`-st`-Wurzeln) absorbiert sich.

**Stufe 2 offen:** Imperativ + Aktiv-Partizip (Prät.) + Präsens-Partizip. Hier
funktioniert der Stufe-1-Trick *nicht* sauber, weil die Oberfläche vom **Präsens-
Themavokal** (a/ja/i/ā/…) abhängt — Suffix universell, aber Themavokal +
Hiatusbruch variieren. Naive Trefferquote nur 16–48 %.

## Befund (datengetrieben, attestierte Twanksta-Formen)

Repräsentative Verben, gruppiert nach Präsens-3sg-Auslaut:

| Lemma | Präs 3sg | Imp 2sg | Akt-Ptz | Präs-Ptz |
|---|---|---|---|---|
| pabelztwei | pabelz**a** | pabelz**ais** | pabelz**uns** | pabelz**ants** |
| ebglābtun | ebglāb**a** | ebglāb**ais** | ebglāb**uns** | ebglāb**ants** |
| abōnitun | abōn**i** | abōn**is** | abōni**wuns** | abōn**ints** |
| anzitun | anz**i** | anz**is** | anzi**wuns** | anz**ints** |
| augrābtun | augrāb**ja** | augrāb**jais** | augrāb**uns** | augrāb**ints** |
| gabātun | gabā**i** | gabā**is** | gabā**wuns** | gabā**nts** |
| āustabautwei | āustabau**i** | āustabau**s** | āustaba**wuns** | āustaba**wints** |
| paāntrintun | paāntrin**a** | paāntrin**ais** | paāntrin**uns** | paāntrin**ants** |
| liptwei | līmp**a** | līmp**ais** | **lipp**uns | līmp**ants** |
| brestwei | bredd**a** | bredd**ais** | bredd**uns** | bred**ānts** |

Muster (vorläufig): **a-Klasse** → Imp `-ais`, Akt `-uns`, Präs `-ants`;
**i-Klasse** → Imp `-is`, Akt `-iwuns` (w-Hiatus), Präs `-ints`; **ja-Klasse** →
Imp `-jais`, Präs `-ints`. Die Palatalisierung (`augrābja`→`augrābjais`) steckt
bereits im Präsensstamm (aus 3sg ableitbar).

## Fragen

1. **Präsens-Klassen-Inventar:** Welche Präsens-/Themaklassen gibt es (a, ja, i,
   ā, na, sta, athematisch …), und **woran erkennt man die Klasse eines Verbs** —
   eindeutig am Präsens-3sg-Auslaut, oder braucht es eine weitere Prinzipalform?
2. **Endungstabelle je Klasse:** Bitte die exakten Oberflächen-Endungen pro Klasse
   für **Imperativ 2sg/2pl**, **Aktiv-Partizip** (`-uns`) und **Präsens-Partizip**
   (`-nts`) — inkl. des Themavokals (z. B. i-Klasse Präs-Ptz `-ints`, a-Klasse
   `-ants`).
3. **Stamm je Kategorie:** Sitzt das **Aktiv-Partizip** auf dem Präsensstamm oder
   dem (langen) Infinitivstamm? Beispiele deuten auf Ablaut hin: `līmpa` (Präs)
   vs. `lippuns` (Akt-Ptz), `preikālsa` vs. `preikalsīwuns`. Muss ein eigener
   Aktiv-/Prät.-Stamm gespeichert werden, oder ist er aus Inf+Präs ableitbar?
4. **Hiatusbruch:** Wann wird `w` (bzw. `j`) eingeschoben? Offenbar `i/ī/au` + `uns`
   → `-iwuns`/`-wuns`, `i` + `nts` → `-ints`/`-wints`. Ist das eine generelle
   Hiatusregel (Vokal+Vokal) oder klassenspezifisch?
5. **Imperativ-Bildung:** Ist der Imperativ = Präsensstamm (inkl.
   Palatalisierung/Themavokal aus 3sg) + `-is`/`-ais`, sodass er sich direkt aus
   der attestierten Präsens-3sg ableiten lässt?

## Was der FST schon kann / Format der Antwort

Ideal als **Klassentabelle**: pro Präsens-Klasse (a) ein Erkennungsmerkmal
(z. B. „3sg endet auf -a, nicht -ja/-i"), (b) die Endungen Imp/Akt-Ptz/Präs-Ptz
mit Themavokal, (c) der jeweils tragende Stamm. Suppletive/Ablaut-Verben mit
eigenem Aktiv-Stamm bitte als Ausnahmeliste. Damit kann Stufe 2 — wie Stufe 1 —
rein datengetrieben + geteilte Regelschicht umgesetzt werden (keine Pro-Lemma-
Kuratierung). Quelle bleibt Twanksta → Ergebnis `provisional`.
