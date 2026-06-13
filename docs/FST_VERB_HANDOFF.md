# Handoff: Verb-FST (Package 5)

## Datenbasis

`goldstandard_verben.json` enthält **60 Paradigmen** (P71–144, exkl. 18 ohne Wortlisten-Treffer) mit je 5 Personen × 2 Tempora = **10 Formen pro Lemma**:

```json
{
  "paradigm": "71",
  "lemma": "īmtun",
  "tenses": {
    "present": { "1sg":"imma", "2sg":"imma", "3sg":"imma", "1pl":"immimai", "2pl":"immitei" },
    "preterite": { "1sg":"immi", "2sg":"immi", "3sg":"immi", "1pl":"immimai", "2pl":"immitei" }
  }
}
```

### Personen
`1sg`, `2sg`, `3sg`, `1pl`, `2pl` (kein 3pl — nur Tabula-Ebene)

### Tempora
`present`, `preterite` (kein perfekt/futur/optativ/imperativ)

## Voting-Ergebnis (800 Formen)

| Status | Anzahl | Bedeutung |
|--------|--------|-----------|
| EINSTIMMIG | 390 | alle 3 Quellen (T/Ps/Tw) einig |
| VOTUM(T+Ps) | 240 | Tabula + Prusaspira → Prusaspira-Block |
| VOTUM(T+Tw) | 75 | Tabula + Twanksta → Twanksta-Block |
| VOTUM(Ps+Tw) | 25 | Prusaspira + Twanksta (Tabula fehlt) |
| EINZEL | 62 | nur eine Quelle vorhanden |
| LÜCKE | 8 | P74 lastun (nur Tabula 3sg, keine Online-Quelle) |

## Normalisierungsregeln (für Stem-Suffix-Zerlegung)

Die finale Form in GS wurde mit folgenden Regeln ausgewählt:
1. **Makron-Stripping** (`āēīōū` → `aeiou`) — nur für Vergleich, GS-Formen haben Makrons
2. **Palatal-j-Tilgung** (`nojot`: `rja` → `ra`) — Twanksta `tirrja` ≙ Prusaspira `tirre`
3. **Degemination** (`glabbja` ≙ `glabja`, `wella` ≙ `wela`)
4. **Endungsvokal** (`amai` → `imai`, `atei` → `itei`) — Twanksta schreibt oft heller
5. **Prefix-Stripping** (`auwerrja` → `werrja`, `palīkei` → `līkei`)

## Konjugationsklassen (zu analysieren)

Die 60 Paradigmen lassen sich in ca. 6–8 Klassen gruppieren:

| Typ | Present-Endung | Preterite-Endung | Beispiele |
|-----|---------------|-----------------|-----------|
| P71–73 | `a` (alle Pers.) | `i` (alle Pers.) | īmtun, mestun, liktun |
| P74–78 | `a` / `e` | `i` / `ē` | lastun, gnestun, līztun |
| P79–82 | `a` / `ja` / `e` | `i` / `ē` | ōstun, wertun, tirtun |
| P83–90 | `a` / `ai` | `i` / `ē` | dātun, būtwei, kaktwei |
| P91–104 | Endung | `ja` / `a` | — |
| P105–114 | `ja` / `a` | `i` / `e` | wiptwei, smeītwei |
| P115–144 | Gemischt | (oft tempusgleich) | preistātun, līkitun |

## Stem-Suffix-Struktur (Vorschlag)

Die FST-Stems sollten analog zu den Nomina (in `fst/morphology/`) aufgebaut werden:

```
LEXICON Verbs
īmtun+V+Pres+1sg:imm V-P71-PRES ;
īmtun+V+Pres+2sg:imm V-P71-PRES ;
...
```

Oder effizienter: **Stamm + Endungs-Lexikon**

Stamm-Zeilen (z.B. `imm` für īmtun, `met` für mestun) → Present-Endungen: `a`, `imai`, `itei`. Preterite: `i`, `imai`, `itei`.

Die Nominal-FST-Struktur (`build_fst.py`) generiert `.lexc` und `.lexd` pro Paradigma–Genus. Für Verben müsste ein ähnlicher Generator (`build_verb_fst.py`) pro Konjugationsklasse bauen.

## Ausstehende manuelle Klärung

Keine — alle 800 Formen sind automatisch aufgelöst.

## Offene Fragen für den FST-Ansatz

1. **Tag-Schema**: `+V+Pres+1sg` (Giella flat-plus) oder anders?
2. **Archiphoneme**: bei Verben kaum relevant (keine Vokalwechsel im Stamm)
3. **Infinitive**: sollen die mit ins FST? (`tun`/`twei`-Endungen)
4. **Integration**: separater Verb-FST (`verbals.fst`) oder kombinierter Lexikon-FST?
5. **pyfoma/hfst**: build_fst.py setzt pyfoma voraus (nicht installiert) — Giella-lexc-Output würde auch reichen

---

## Antwort (Linguistik-Lehrer): Drei-Stamm-Modell

> Korrigiert Frage 2 ("Archiphoneme kaum relevant") und Frage 3 (Infinitive).

Die `ī/i`-Alternation (P71 `īmtun`) ist **keine Lautregel**, sondern die Grenze
zwischen **gespeicherten Stämmen** — das baltische **Drei-Stamm-Modell**
(lit. `im̃ti / ìma / ė̃mė` = Infinitiv / Präsens / Präteritum). `īmtun→imma` ist
Ablaut (ī~i) **plus** die Jotierung, die den Präsensstamm baute — beides
lexikalisch, **nicht** aus dem Infinitiv ableitbar. Dieselbe Lehre wie beim
nominalen Unterstamm ([`HANDOFF_allomorphie.md`](HANDOFF_allomorphie.md)):
**Prinzipalformen speichern, nicht generieren.**

**Regelhaft** (für ganz Klasse 71 gleich) ist die **Kategorie → Stamm**-Zuordnung:

| Stamm | Form | Realisierung | Kategorien |
|-------|------|--------------|------------|
| **Infinitivstamm** `īm-` (lang) | — | — | Infinitiv `-tun/-twei`, Optativ `-sei`, Konjunktiv `-lai/-limai/-litei`, Passivpartizip `-ts` |
| **Präsens-/Prät.-Stamm** `imm-` (kurz, jotiert) | — | — | Präsens `-a/-imai/-itei`, Präteritum `-i/-imai/-itei`, Imperativ `-is/-iti`, akt. Prät.-Partizip `-uns` (+ Perfekt/Futur-Umschreibung) |
| **Präsenspartizip** | `imānts` | kurzer Stamm, vor schwerem `-ānts` **entgeminiert** (imm→im) | Präsenspartizip `-ānts` |

**Korrektur der früheren Intuition:** Konjunktiv/Optativ/Passivpartizip behalten
die Langwurzel; **Imperativ und aktive Partizipien sitzen auf dem kurzen
Präsensstamm**, nicht auf `īm-`. „Wurzel bleibt" gilt also nur für die
infinitivbasierten Formen, nicht pauschal für „alles außer Präs/Prät".

**Regelmäßigkeit:** Gegeben die Stämme sind alle Formen vollständig regelhaft
(Endungen + Kategorie→Stamm-Zuordnung). Unregelmäßig (= nicht herleitbar) ist
**nur die Stammform selbst**.

**Konsequenz fürs FST — dieselbe Architektur wie die Nomina:**
1. Pro Verb die Stämme als **Prinzipalformen** speichern (Infinitiv-, Präsens-,
   ggf. eigener Präteritalstamm). Inf-Stamm aus dem Lemma (`īmtun→īm-`),
   Präs/Prät-Stamm aus 3sg (`imma→imm-`) — `wordlist_to_verb_entries` gewinnt 2
   davon bereits; der **Infinitivstamm fehlt** (wird derzeit fälschlich vom
   Präsensstamm abgeleitet → `*immun` statt `īmtun`).
2. Deterministische **Kategorie→Stamm-Tabelle** als lexd-Pattern (wählt pro
   Tempus/Modus den richtigen Stamm) + reguläres Endungsset je Kategorie.
3. **Keine neue Lautregel:** Jotierung + Schwer-Endungs-Schwächung sind die
   nominalen Regeln. `īmts→imtāi/imtammans` = nominale **R2**;
   `imma→imānts` = R2 + Jotierungsumkehr (`phonology.py`,
   [`ORTHO_RULES.md`](ORTHO_RULES.md)).

Verbspezifisch ist also **nur** die Stammliste + Kategorie→Stamm-Zuordnung; die
Phonologie wird mit der Nominalflexion geteilt.
