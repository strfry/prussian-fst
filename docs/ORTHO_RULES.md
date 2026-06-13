# Orthographische Regeln für den prūsischen FST-Analysator

Stand: 2026-06-13. Basierend auf 78 Paradigmen Partizip-Daten + existierendem FST.

> **Implementierungsstand (2026-06-13):** Die lebende Implementierung ist
> `src/prussian/fst/rules.py` (pyfoma-Rewrite-Regeln) komponiert mit der
> Morphotaktik aus `src/prussian/fst/lexd_gen.py`; das Akzentmodell
> dahinter ist in [AKZENT.md](AKZENT.md) hergeleitet (die `%^VowS`-Marker
> von §1.2 sind durch die Akzentmarker M/S ersetzt). Die twolc-Notation
> in §1/§4 beschreibt die Regeln äquivalent für einen späteren HFST-Port —
> sie wird nicht kompiliert. §2 (Partizipien, Modi) ist die Spezifikation
> für den nächsten Ausbauschritt.

---

## 1. Existierende Regeln (Implementierung: `src/prussian/fst/rules.py`)

### 1.1 Archiphonem-Auflösung (`@DEFAULT_LONG@`)

```
{A}:ā  {E}:ē  {I}:ī  {O}:ō  {U}:ū
```

Archiphoneme `{A}{E}{I}{O}{U}` repräsentieren Vokale, die zwischen lang/kurz alternieren.
Default = Langform. Kurzform wird durch `%^VowS`-Marker erzwungen.

### 1.2 Vokalkürzung (`@VOW_SHORTEN@`)

```
{A}:a <=> _  ? - %^VowS * %^VowS:
```

Wenn ein Suffix den Marker `%^VowS` trägt, wird der vorangehende Archiphonem-Vokal gekürzt:
`{A}→a`, `{E}→e`, `{I}→i`, `{O}→o`, `{U}→u`. Der Marker selbst wird getilgt (`%^VowS:0`).

**Anwendungsfälle:**
- Nominal: Pl.Nom (mīst-an → mistāi — `{I}:i` vor `%^VowS`)
- Verbal: 1Pl/2Pl Präsens (imm- → immimai, immitei — kein Archiphonem hier, aber Marker schützt die Endung)

### 1.3 J-Palatalisierung (`@JPAL@`, `@JPAL_PRE@`)

```
g:ģ  k:ķ  n:ņ  s:š  t:ţ  z:ž  <=> _ %^JPal:
```

Wenn ein Suffix den Marker `%^JPal` trägt (beginnt mit `j`), wird der stammauslautende Konsonant palatalisiert. Der Marker wird getilgt.

**@JPAL_PRE@**: Palatalisierung, wenn `%^JPal` VOR dem Konsonanten steht (Präfix-Kontext).

**Anwendungsfälle:**
- Nominal: Gen.Sg von -is-Stämmen (kūg-es → kūģas — `g→ģ` vor `%^JPal`)
- Nominal: Dat.Sg (kūg-u → kūģu)
- Verbal: -ja-Klasse Präsens (glab-ja → glabja — `b` wird nicht palatalisiert, weil `b` nicht in der Palatalisierungsliste ist)

### 1.4 Orthographie-Normalisierer (`build/lenient.fst`)

Früher ein separater, aufzählender `ortho.fst`; jetzt entstehen die
Twanksta-j-Varianten **pro Endung** in der Morphotaktik
(`lexd_gen.jan_variant`, V-Marker) — `lenient.fst` akzeptiert sie und
liefert direkt die Standardanalyse. Die Variantenregeln:

| Twanksta | Standard | Kontext |
|----------|----------|---------|
| `-jas` | `-es` | Gen.Sg nach weichem Stamm |
| `-ja` | `-e` | weiche Endung |
| `-ju` | `-u` | Dat.Sg nach weichem Stamm |
| `-jan` | `-en` | Akk nach weichem Stamm |

Dies sind **Mažiulis §§21–25** Palatalisierungsregeln: Twanksta schreibt explizites `j`, Prusaspira/Standard schreibt palatalisierten Konsonanten + weichen Vokal.

---

## 2. Neue Regeln — Verbalmorphologie jenseits Präs/Prät

Der existierende FST generiert nur Präsens, Präteritum, Infinitiv. Die folgenden Regeln beschreiben, was für Optativ, Konjunktiv, Imperativ und Partizipien hinzukommen muss.

### 2.1 Optativ (3. Person Imperativ)

**Stamm:** Infinitivstamm (Lemma minus `-tun/-twei/-stwei`)

**Suffix:** `-sei`

**Regel:** Direkte Konkatenation. Keine phonologischen Marker nötig.

| Lemma | Inf-Stamm | Optativ |
|-------|-----------|---------|
| īmtun | īm- | īmsei |
| segītun | segī- | segīsei |
| dīnkautwei | dīnkau- | dīnkausei |

**Ausnahme:** būtwei → seīsei (suppletiv, lexikalisch)

### 2.2 Konjunktiv

**Stamm:** Normalerweise **Infinitivstamm**. Aber bei **s-Infinitiven** (wo `s+t→st`/`d+t→st` den Stamm phonologisch verschleiert): **Präteritumstamm**.

**Suffixe:** `-lai` (1/2/3sg, 3pl), `-limai` (1pl), `-litei` (2pl)

| Lemma | Inf-Stamm | Prät-Stamm | Konjunktiv | Welcher Stamm? |
|-------|-----------|------------|------------|----------------|
| īmtun | īm- | imm- | īmlai | **Inf** (īm+lai) |
| segītun | segī- | segēi- | segīlai | Inf |
| lānktun | lānk- | lānk- | lānklai | Inf |
| sīstwei | sī- | sīd- | **sīd**lai | **Prät** |
| īstun | īs- | īd- | **īd**lai | **Prät** |
| kwistun | kwis- | kwitt- | **kwit**lai | **Prät** |
| waīstun | waīs- | waīda- | **waīd**lai | **Prät** |
| ristun | ris- | rissa- | rislai | **ambig** (ris+lai ≙ riss→ris+lai) |
| jāstun | jās- | jāsa- | jāslai | **ambig** |

**Regel:** `stem + lai` / `stem + limai` / `stem + litei`. Stammtyp = `Inf` (default) oder `Prät` (lexikalisch markiert für Paradigmen, deren Infinitivstamm durch s+t→st/d+t→st phonologisch verändert ist: 100, 117, 122, 128). Bei degeminierten Prät-Stämmen (kwitt- → kwit-, riss- → ris-) ist die Gemination vor dem Konsonantanschluss reduziert.

### 2.3 Imperativ 2sg/2pl

**Stamm:** 3sg-Präsensstamm

**Suffixe** (paradigmenabhängig, vgl. gramm.htm):

| Paradigmenbereich | 2sg-Endung | 2pl-Endung | Beispiele |
|-------------------|-----------|------------|-----------|
| 70–114, 122, 128, 136, 141–142, 144 | `-ais/-eis/-is` (+ 3sg-Vokal) → `-aiti/-eiti/-iti` | `-aiti` | trepp-ais → treppaiti |
| 131–135, 137–138 | `-s` (Infinitivstamm + s) | `-ti` | segī-s → segīti |
| 115–121, 123–127 | `-s/-eis/-ais` (athematisch) | `-ti/-eiti` | dīnkau-s, sei-s |
| 137a, 139–140 | `-īs` (Inf-Stamm + īs) | `-īti` | krikstī-s → krikstīti |

**FST-Ansatz:** Imperativ-Endungen werden pro Paradigma im Lexikon gelistet (wie Präs/Prät-Endungen). Keine neuen phonologischen Regeln nötig — die Endungsvarianten sind paradigmenfest.

### 2.4 Präsenspartizip Aktiv (`+Ptc+Prs`)

**Stamm:** 3sg-Präsensstamm (Default). **Ausnahmen** mit separatem lexikalischem Stamm: P117 (īst→īdants, Prät-Stamm), P118–121 (dātun→dānts, Wurzel-Stamm), P137 (turri→turīnts, Inf-Stamm).

**Suffix:** `+nts` (mask.nom.sg, Paradigma 29). Trägt Marker `%^NtLong` oder `%^NtDiph` für die phonologische Allomorphie.

#### Allomorphie-Regeln

**R1 — `%^NtLong`: Kurzvokal → Langvokal vor -nt**

```
{A}:ā <=> _ %^NtLong n t ;
{I}:ī <=> _ %^NtLong n t ;
```

| 3sg-Endung | vor Regel | nach Regel | Ergebnis |
|-----------|----------|-----------|----------|
| -a | imm%^NtLongnts | immānts | **imānts** (s.u. Degemination) |
| -e | lānk%^NtLongnts | lānkīnts | → **lānkints** (s.u. ī→i) |
| -i | turr%^NtLongnts | turrīnts | → **turīnts** (lexikalischer Stamm, Gem.Red.) |

**R1b: ī→i nach nicht-palatalem Konsonant.** `{I}:i` nach `k,g` und vor `nt`. Dies ist eine phonotaktische Regel, die verhindert dass `nkīnts` entsteht.

```
{I}:i <=> [k|g] _ n t ;
```

**R2 — `%^NtDiph`: Diphthong-Monophthongierung vor -nt**

```
{A}i:a <=> _ %^NtDiph n t ;
{E}i:i <=> _ %^NtDiph n t ;
{E}i:{I} <=> _ %^NtDiph n t ;  {A}i:{A} <=> _ %^NtDiph n t ;
```

| 3sg-Endung | vor Regel | nach Regel | Ergebnis |
|-----------|----------|-----------|----------|
| -ai | pūd%^NtDiphnts | pūdants | **pūdants** |
| -āi | bil%^NtDiphnts | bilānts | **bilānts** |
| -ei | kāimaluk%^NtDiphnts | kāimalukints | **kāimalukints** |
| -ēi | seg%^NtDiphnts | segīnts | **segīnts** |
| -aui | dīnk%^NtDiphnts | dīnkawints | **dīnkawints** (s.u.) |

**R2b — -aui → -awi vor -nt**

```
u i:w i <=> a _  %^NtDiph n t ;
```

**R3 — -ne → -ni vor -nt** (Themavokal-Reduktion)

```
e:i <=> n _  %^NtDiph n t ;
```

Oder lexikalisch: P110–111 speichern den Stamm ohne -e (pastān- statt pastāne-).

**R4 — Geminations-Reduktion vor Langvokal**

```
C1:C1 <=> _ C1 %^NtLong
```

De-facto-Regel: Doppelkonsonant → Einfachkonsonant vor dem gedehnten Vokal + nt.
Dies erklärt: imma→imānts (nicht *immānts), metta→metānts, treppa→trepānts.

**FST-Umsetzung:** Die Gemination ist im Stamm kodiert. Vor der `%^NtLong`-Regel wird degeminiert:
```
C₁:0 <=> _ C₁ %^NtLong
```

**R5 — -ja/-ija transparent, -ūja/-aūja → -jants** (Stammvokal-Elision)

| 3sg | → Präs.Part | Regel |
|-----|------------|-------|
| -ja | -jants | j + a erhalten |
| -ijja | -ijjants | erhalten |
| -ūja | -jants | ū→0 vor j+nt |
| -aūja | -jants | aū→0 vor j+nt |

#### Sonderfall athematische Verben (-t Präsens)

Keine phonologische Regel — der Stamm muss **lexikalisch** hinterlegt sein:

| P | Lemma | 3sg | Präs.Part-Stamm | Präs.Part |
|---|-------|-----|-----------------|-----------|
| 114 | wīrstwei | wīrst | wīrst- | wīrstants |
| 115 | būtwei | ast | sē- | s**ēnts** (suppl.) |
| 116 | ēitwei | ēit | ē- | **ēnts** |
| 117 | īstun | īst | īd- (Prät) | īdants |
| 118 | dātun | dāst | dā- (Wurzel) | dānts |
| 119 | jātwei | jāt | jā- | jānts |
| 120 | skītwei | skīt | skī- | skīnts |
| 121 | dītun | dest | dī- (Wurzel) | dīnts |

### 2.5 Perfektpartizip Aktiv (`+Ptc+Prt`)

**Stamm:** Präteritumstamm (Konsonantstämme) oder Infinitivstamm (Vokalstämme).

**Suffixe** (paradigmenfest):

| Paradigmen | Suffix | Stammtyp |
|-----------|--------|----------|
| 71–105, 109, 114, 116–117, 124–128 | `+uns` | Präteritumstamm |
| 106–108 | `+uns` (j-Stamm) | Präteritumstamm (j erhalten) |
| 110–113, 115, 118–123, 131–144 | `+%^GlideW uns` | Infinitivstamm |

**Phonologische Regel für `%^GlideW`: w-Glide-Einschub nach Vokal**

```
0:w <=> Vowel _ %^GlideW u n s ;
```

| Inf-Stamm | vor Regel | nach Regel | Ergebnis |
|-----------|----------|-----------|----------|
| segī- | segī%^GlideWuns | segīwuns | **segīwuns** |
| bū- | bū%^GlideWuns | būwuns | **būwuns** |
| dā- | dā%^GlideWuns | dāwuns | **dāwuns** |
| rikaū- | rikaū%^GlideWuns | rikaūwuns | **rikaūwuns** |

**Kein Glide** bei Konsonantstämmen (Paradigmen 71–128): direkter Anschluss.

**j-Stämme** (P106–108): Der Stamm endet auf `j`. Das Suffix ist `-uns` → phonetisch `-jjuns` (grejj-uns, lijj-uns). Der j-Erhalt ist transparent — keine Sonderregel nötig.

### 2.6 Passivpartizip (`+Ptc+Pas`)

**Stamm:** Immer der **Infinitivstamm**.

**Suffix:** `+ts` (Paradigma 69). Marker `%^Ptcs` für Prusaspira a-Epenthese.

**Phonologische Regel (nur Prusaspira-Orthographie):**

```
0:a <=> s _ %^Ptcs t s ;
```

| Inf-Stamm | Prusaspira | Twanksta |
|-----------|-----------|----------|
| mes- | mes**tas** | mests |
| wes- | wes**tas** | wests |
| īs- | īs**tas** | īsts |
| īm- | īmts | īmts |
| segī- | segīts | segīts |

Die a-Epenthese ist **rein orthographisch** (Prusaspira-Konvention). Im Twanksta-FST entfällt sie. Der existierende `ortho.fst` kann `-tas` ↔ `-ts` normalisieren.

---

## 3. Orthographie-Varianten zwischen Quellen

Diese sind **Normalisierungsregeln** für den Analysator (kein Generator, sondern `ortho.fst`-Ebene):

### 3.1 ī ↔ ē (Vokalqualität)

| Prusaspira | Twanksta | Paradigmen |
|-----------|----------|------------|
| sīndants, sīduns | sēndants, sēduns | P128 |
| īdants, īduns | ēdants, ēduns | P117 |
| lītwuns | lētwuns | P107, P106 |
| jāsuns, jāstas | jēsuns, jēsts | P127 |

**Regel im ortho.fst:** `ī:ē` ↔ `ē:ī` — bidirektionale Variantenakzeptanz.

### 3.2 Präsenspartizip jj-Geminierung ↔ ā-Monophthong

| Prusaspira | Twanksta | Paradigmen |
|-----------|----------|------------|
| grejjants, sklajjants | grejānts, sklajānts | P106a, P106c |
| lijjuns, wijjuns | līwuns, wīwuns | P107, P108 |

Twanksta vermeidet die jj-Gemination und schreibt stattdessen Langvokal (ā) oder w-Glide (w).

### 3.3 Passiv -tas ↔ -ts (bereits in §2.6 beschrieben)

### 3.4 Akzent-Shift (ā ↔ a)

| Prusaspira | Twanksta |
|-----------|----------|
| werdānts | werdants |
| pilānts | pilīnts |

Diese können durch die existierende `%^VowS`-Architektur aufgelöst werden — der Unterschied liegt in der Vokallänge, die der FST über Archiphoneme steuert.

---

## 4. Regel-Zusammenfassung für `phonology.twolc`

```twolc
Alphabet
 %^VowS:0  %^JPal:0  %^NtLong:0  %^NtDiph:0  %^GlideW:0  %^Ptcs:0
 %>  %<
 ;

!! ===== 1. EXISTIEREND =====

"Default vowel lengthening"                  !! @DEFAULT_LONG@
 {A}:ā ;  {E}:ē ;  {I}:ī ;  {O}:ō ;  {U}:ū ;

"Vowel shortening"                           !! @VOW_SHORTEN@
 {A}:a <=> _ ? - %^VowS * %^VowS: ;
 {E}:e <=> _ ? - %^VowS * %^VowS: ;
 {I}:i <=> _ ? - %^VowS * %^VowS: ;
 {O}:o <=> _ ? - %^VowS * %^VowS: ;
 {U}:u <=> _ ? - %^VowS * %^VowS: ;

"J-Palatalization"                           !! @JPAL@
 g:ģ <=> _ %^JPal: ;  k:ķ <=> _ %^JPal: ;  n:ņ <=> _ %^JPal: ;
 s:š <=> _ %^JPal: ;  t:ţ <=> _ %^JPal: ;  z:ž <=> _ %^JPal: ;

"Pre-J-Palatalization"                       !! @JPAL_PRE@
 g:ģ <=> %^JPal: _ ;  k:ķ <=> %^JPal: _ ;  n:ņ <=> %^JPal: _ ;
 s:š <=> %^JPal: _ ;  t:ţ <=> %^JPal: _ ;  z:ž <=> %^JPal: _ ;

!! ===== 2. NEU: Partizip-Phonologie =====

"NT vowel lengthening (a→ā, i→ī before nt)"  !! @PTC.NT.LONG@
 {A}:ā <=> _ %^NtLong n t ;
 {I}:ī <=> _ %^NtLong n t ;

"NT: ī→i after velar"                         !! @PTC.NT.KI@
 {I}:i <=> [k|g] _ n t ;

"NT diphthong: ai→a, ei→i before nt"         !! @PTC.NT.DIPH@
 {A}i:a <=> _ %^NtDiph n t ;
 {E}i:i <=> _ %^NtDiph n t ;

"NT diphthong: ēi→ī, āi→ā before nt"         !! @PTC.NT.DIPH.LONG@
 {E}i:{I} <=> _ %^NtDiph n t ;
 {A}i:{A} <=> _ %^NtDiph n t ;

"NT: aui→awi glide before nt"                 !! @PTC.NT.AWI@
 u i:w i <=> a _ %^NtDiph n t ;

"Gemination reduction before NT-long"          !! @GEM.RED.NT@
 C1:0 <=> _ C1 %^NtLong ;

"Past ptc: w-glide after vowel"               !! @PTC.W.GLIDE@
 0:w <=> Vowel _ %^GlideW u n s ;

"Passiv ptc: a-epenthesis after s (Prus.)"    !! @PTC.PAS.EPEN@
 0:a <=> s _ %^Ptcs t s ;
```

---

## 5. Was NICHT phonologisch ist (lexikalische Einträge)

Diese Fälle erfordern separate Stamm-Einträge im Lexikon, weil sie nicht durch Regeln vorhersagbar sind:

| Phänomen | Paradigmen | FST-Behandlung |
|----------|-----------|----------------|
| Suppletive Stämme | 115 (būtwei), 116 (ēitwei) | Eigener Stamm-Eintrag |
| Athematischer Stammwechsel | 117 (īd-), 118–121 (dā-, jā-, dī-) | Lexikalischer `+Ptc+PrsStem` |
| Geminations-Präsens → Inf-Stamm | 137 (turī-), 137a (milī-) | Lexikalischer `+Ptc+PrsStem` |
| Konjunktiv Prät-Stamm | 100, 117, 128 (kwit-, īd-, sīd-) | Flag `+Konj+UsePrt` im Lexikon |
| Imperativ-Endungsklasse | alle 60 Paradigmen | Pro Paradigma im Affix-Lexikon |

---

## 6. Integrations-Plan

1. **`phonology.twolc`** um §4-Regeln erweitern (5 neue Marker, 7 neue Regelgruppen)
2. **`affixes/verbs.lexc`** um Optativ, Konjunktiv, Imperativ, Partizip-Reihen erweitern
3. **`stems/verbs.lexc`** um lexikalische Partizip-Stämme für Sonderfälle erweitern
4. **`ortho.fst`** um ē↔ī und -tas↔-ts Normalisierung erweitern
5. **`build_fst.py`** um Partizip-Generierung erweitern (neue `+Ptc`-Tags, Stem-Resolution)
