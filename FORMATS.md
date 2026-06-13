# HTML formats of verb data sources

## Prusaspira

URL: `http://prusaspira.org/wirdeins?wirds={STEM}&akc=Iz&bila=1`

### Structure

Each result block contains one verb table with all conjugated forms, wrapped in:
```html
<table width="100%"><tr><td width="10%"></td><td width="90%">
  <table CLASS="boldtable"> … </table>
</td></tr></table>
```

### boldtable layout

The table has **one header row** followed by **six data rows** (As, Tū, 3sg, Mes, Jūs, 3pl).
Each row has **8 columns**:

| Col | Heading     | Content                                        |
|-----|-------------|------------------------------------------------|
| 0   | (person)    | `<b>As:</b>`, `<b>Tū:</b>`, `<b>3sg:</b>`, …   |
| 1   | tēntisku    | Present tense form                             |
| 2   | pragūbingisku | Preterite form                               |
| 3   | perfektan   | Perfect (auxiliary + participle)               |
| 4   | perejīngisku | Future (auxiliary + participle)               |
| 5   | imperatīws  | Imperative form (2sg!, 2pl!, 3sg!, 1pl!)       |
| 6   | kōnjunktiws  | Subjunctive forms                             |
| 7   | particīpai  | Participle labels / forms                      |

### Participle column (col 7)

The participle column alternates between headers and links:

| Row  | Content in col 7                                   |
|------|-----------------------------------------------------|
| 1    | `<b>tēntiskas aktīws:</b>` (header)                 |
| 2    | `<a onclick="ens_str('FORM,PARADIGM,TYPE,LEMMA')">TEXT</a>` — present active participle |
| 3    | `<b>pragūbiniskas aktīws:</b>` (header)             |
| 4    | `<a onclick="ens_str('FORM,PARADIGM,TYPE,LEMMA')">TEXT</a>` — past active participle    |
| 5    | `<b>pasīws:</b>` (header) OR `<i>nitranzitīws</i>` for intransitives |
| 6    | `<a …>TEXT</a>` — passive participle OR empty for intransitives |

**onclick format**: `ens_str('FORM,29,pcps,LEMMA')`

- `FORM` = the base form (e.g. `imānts`, `immuns`, `īmts`)
- `29` or `68` or `69` — paradigm number for the participle
- `pcps` / `pcptac` / `pcptpa` — participle type (present/past/passive)
- `LEMMA` — the verb lemma

### Imperative column (col 5)

- Row 1: **3sg optative** — ends with `!` (e.g. `īmsei!`)
- Row 2: **2sg imperative** — e.g. `immais!`
- Row 3: **3sg optative** — same as row 1
- Row 4: **1pl imperative** — same as 1pl present
- Row 5: **2pl imperative** — e.g. `immaiti!`
- Row 6: **3sg optative** — same as row 1

### Conjunctive column (col 6)

- Row 1-3: **1/2/3sg** form — all identical (e.g. `īmlai`)
- Row 4: **1pl** — e.g. `īmlimai`
- Row 5: **2pl** — e.g. `īmlitei`
- Row 6: **3pl** — same as 1/2/3sg

### Parsing notes

The boldtable HTML is **malformed** — rows are separated by `</tr>` but only the
first row has a `<tr>`.  lxml and BeautifulSoup merge everything into one row.
**Workaround**: split the raw table content on `</tr>` and extract `<td>` contents
from each chunk.

---

## Twanksta

URL: `POST https://wirdeins.twanksta.org/more/`

Headers:
- `Content-Type: application/x-www-form-urlencoded`
- `X-Requested-With: XMLHttpRequest`

Body: `word={LEMMA}&numb={PARADIGM}&desc={DESCRIPTION}&dia=semba`

### Structure

The response is well-formed HTML with two main regions:

```
<div class="left-verbs">                        ← Indicative
  <h3>Indicative mood</h3>
  <table class="response">
    <span class="head">Present</span>
    <span class="pronoun">as</span><span class="verb">FORM</span>
    …
    <span class="head">Past</span>
    …
    <span class="head">Perfect</span>
    …
    <span class="head">Future</span>
    …
  </table>
</div>

<div class="right-verbs">                       ← Non-indicative
  <h3>Optative</h3>
  <span class="verb">FORM</span>

  <h3>Imperative</h3>
  <span class="pronoun">(tū)</span><span class="verb">FORM</span>
  <span class="pronoun">(jūs)</span><span class="verb">FORM</span>

  <h3>Participle</h3>                           ← Participles
  <span class="head">Present</span>
  <span class="spoiler-title2">
    <span class="arrow">▶ </span>
    <span>FORM</span>                            ← participle nominative
  </span>
  <div class="spoiler-body2">                   ← full declension (hidden by default)
    <table id="subst"> … </table>               ← masc
    <table id="subst"> … </table>               ← fem
    <table id="subst"> … </table>               ← neut
  </div>

  <span class="head">Past</span>
  <span class="spoiler-title2 closed">
    <span>FORM</span>
  </span>
  <div class="spoiler-body2"><table id="subst">…</table></div>

  <span class="head">Passive</span>              (only for transitive verbs)
  <span class="spoiler-title2 closed">
    <span>FORM</span>
  </span>
  <div class="spoiler-body2"><table id="subst">…</table></div>

  <h3>Subjunctive</h3>
  <span class="pronoun">as</span><span class="verb">FORM</span>   ← 1/2/3sg, 3pl
  <span class="pronoun">mes</span><span class="verb">FORM</span>   ← 1pl
  <span class="pronoun">jūs</span><span class="verb">FORM</span>   ← 2pl
</div>
```

### Participle spoiler structure

```html
<td valign="top" align="center">
  <span class="head">Present</span>              ← participle type
  <span class="spoiler-title2">
    <span class="arrow">▶ </span>
    <span>imānts</span>                          ← nominative form (no class!)
  </span>
  <div class="spoiler-body2">                   ← declension (hidden)
    <table id="subst">
      <tbody><tr><th class="null">masc</th>…</tr>
        <tr><th class="hea">Nominative</th>
          <td><span class="verb">imānts</span></td>    ← masc nom sg
          <td><span class="verb">imāntjai</span></td>  ← masc nom pl
        </tr>
        <tr><th class="hea">Genitive</th>…</tr>
        <tr><th class="hea">Dative</th>…</tr>
        <tr><th class="hea">Accusative</th>…</tr>
      </tbody>
    </table>
    <!-- same for fem, neut -->
  </div>
</td>
```

The **second `<span>`** inside `.spoiler-title2` (the one without a class)
holds the nominal singular masculine form.  This is the canonical participle
lemma.

The `.spoiler-body2` contains full `<table id="subst">` blocks — one per gender
(masc, fem, neut) — with 4 cases × 2 numbers each.

### Parsing notes

Twanksta HTML is well-formed.  Use `BeautifulSoup` with `html.parser`.

- Extract the `.right-verbs` div
- Find all `.spoiler-title2` elements; the participle form is the second `<span>`
  inside each.
- The `.head` immediately preceding each `.spoiler-title2` tells whether it is
  Present, Past, or Passive.
- The `.spoiler-body2` following each title holds gender-pivoted declension tables
  (`<table id="subst">` with `<th class="null">` gender label).
