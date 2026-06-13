# Handoff: Stamm-Allomorphie in der altpreußischen Nominalflexion

**Kontext für dich (Linguistik-Experte):** Wir bauen einen computerlinguistischen Morphologie-Analysator/-Generator für das (neu-rekonstruierte) Altpreußisch — ein endlicher Transduktor (FST) mit der Bibliothek PyFoma. Datengrundlage sind die Flexionsparadigmen aus der **„TABVLA NOVA MMVII"** (`tabula.fixed.htm`). Jedes Substantiv-Paradigma (Nr. 32–67) liefert 8 Formen: Sg und Pl je **Nom · Gen · Dat · Acc**.

Ich (der Programmierer) habe nur flüchtige Linguistik-Kenntnisse und brauche von dir die **sprachwissenschaftlich korrekte Modellierung**, damit das Programm sie richtig umsetzt. Es geht **nur** um die unten beschriebene Kernfrage.

---

## Das Ziel

Wir wollen jedes Lemma der Wortliste (gegeben ist die **Nominativ-Singular-Zitierform** + die Paradigmennummer) automatisch in alle 8 Formen flektieren. Dafür muss das Programm jede Form in **Stamm + Endung** zerlegen und wissen, *wie* sich der Stamm über die Zellen verändert.

## Das Problem: der Stamm ist nicht konstant

In vielen Paradigmen alterniert der Stamm je nach Kasus/Numerus. Beispiele aus den Daten (Reihenfolge: `Sg: Nom Gen Dat Acc | Pl: Nom Gen Dat Acc`):

**Gemination (Einfach-/Doppelkonsonant):**
- **42** `tal-`: tal**s** · ta**ll**us · ta**ll**u · ta**ll**un | ta**ll**us … → einfaches `l` nur im Nom Sg
- **60** `ak-`: a**k**s · a**kk**is · a**kk**ei · a**kk**in | a**kk**is … → einfaches `k` nur im Nom Sg
- **37** `pan-`: pa**nn**in · pa**nn**es · pa**ņņ**u · pa**nn**in | pa**n**ēi · pa**nn**in · pa**n**emmans · pa**nn**ins → `nn`, aber `n` im **Pl Nom** und **Pl Dat**, und `ņņ` im Dat Sg

**Palatalisierung:**
- **40** `kūg-`: kū**g**is · kū**g**es · kū**ģ**u · kū**g**in | … → palatales `ģ` nur im Dat Sg
- **37a/40a** (z/ž), **50a/51a** (s/š): der alternierende Konsonant ist in der Quelle **rot** markiert. Bsp. 50a `ķāsi`: ķā**s**i · ķā**š**as · ķā**š**ai · ķā**s**in | ķā**š**as · ķā**s**in · ķā**š**amans · ķā**s**ins → `š` in Gen/Dat, `s` in Nom/Acc

**Ablaut (Vokallänge):**
- **35** `mīst-`: m**ī**stan · m**ī**stas · m**ī**stu · m**ī**stan | m**i**stāi · m**ī**stan … → kurzes `i` nur im **Pl Nom**
- **46**: sp**i**gsnā · sp**ī**gsnas · sp**ī**gsnai · sp**ī**gsnan | sp**ī**gsnas · sp**ī**gsnan · sp**i**gsnāmans · sp**ī**gsnans → kurzes `i` im **Nom Sg** und **Pl Dat**

**Konsonantstamm-Erweiterung:**
- **62** `em-`: e**mm**ens · e**mn**es · e**mn**i · e**mn**in | e**mn**ei … → `mm` nur Nom Sg, sonst `mn`
- **66** `mūt-`: mūti · mūtis · mū**ter**ei · mūtin | mūtis · mūtin · mū**ter**imans · mūtins → Erweiterung `-ter-` im Dat Sg und Pl Dat
- **63** `sīmen-`: s**ī**men · sīmenes · sīmeni · sīmen | s**i**menēi · sīmenin · s**i**menimmans · sīmenins → kurzes `i` im Pl Nom/Dat

**Auffälliges Muster:** Die „schwachen" Allomorphe (Einfachkonsonant / Kurzvokal) tauchen oft genau im **Pl Nom** und **Pl Dat** auf (mistāi, panēi, simenēi, spigsnāmans, simenimmans, panemmans). → Ist das eine echte, regelhafte morphophonologische Verteilung?

Wichtig: Diese Alternationen sind **morphologisch konditioniert** (an bestimmte Zellen gebunden), nicht durchgängig phonologisch — eine globale „ersetze überall `nn`→`n`"-Regel würde falsch über-applizieren.

---

## Unsere drei Modellierungs-Optionen

1. **Nur regelmäßige zuerst:** Paradigmen ohne Alternation (32, 45, 49, 50, 52, 58, 47, 54 …) sofort als Stamm+Endung bauen; alternierende später.
2. **Allomorph je Zelle listen:** Pro Paradigma für jede der 8 Zellen den Stamm-Allomorph (z.B. `pann`/`pan`/`paņņ`) + die Endung explizit hinterlegen. Robust, aber: Wie überträgt man das auf ein **neues** Lemma, von dem nur der Nom Sg bekannt ist?
3. **Ein Unterstamm + Alternationsregeln:** Ein „Unterstamm" (z.B. `pan`, `kūg`) plus kontextuelle Regeln pro Paradigma, die die Allomorphe erzeugen (klassisches Zwei-Ebenen-Modell).

---

## Konkrete Fragen an dich

1. **Folgt diese Tabelle einer etablierten Analyse** (Mažiulis / Palmaitis–Klusis „Prūsiskan")? Gibt es dort bereits einen kanonischen **Unterstamm** + **Alternationsregeln**, die wir übernehmen können?
2. Sind die Alternationen **vorhersagbar** aus der Lautumgebung (stammauslautender Konsonant + folgender Vokal), oder pro Lexem **idiosynkratisch**? — Das entscheidet, ob Option 3 (Regeln) überhaupt für neue Lemmata trägt.
3. Wo liegt konventionell die **Stamm/Endung-Grenze**? (Ist z.B. das Nom-Sg `-s` / `-is` / `-an` eine Endung auf `wīr-` / `kūg-` / `mīst-`?)
4. Ist die **Pl-Nom/Pl-Dat-Schwächung** (s.o.) eine eigenständige Regel, die man einmal formulieren kann?
5. Welche der drei Optionen ist sprachwissenschaftlich am ehrlichsten und zugleich auf neue Lemmata anwendbar?

**Was wir am Ende brauchen:** eine Vorschrift, die — gegeben Nom Sg + Paradigmennummer — die übrigen 7 Formen korrekt erzeugt (inkl. der Allomorphie). Je nach deiner Antwort wählen wir Option 1/2/3.
