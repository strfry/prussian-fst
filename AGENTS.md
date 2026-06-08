# Prussian word form lookup

Use these when the user asks to look up Prussian word forms. Both
dictionaries search by STEM prefix (word beginning), not inflected form.
Diacritics are optional in search terms.

**Rate limit:** Maximum **1 request per second** for both APIs. Always delay
at least 1 s between requests to either service.

## Required data files

`wordlist.json` und `prussian_dictionary.json` werden für das FST-Projekt
benötigt und sind in <https://github.com/strfry/prussian-mcp> verfügbar.

## Grammar references

- **Tabula Nova (Paradigmentabelle):** <http://donelaitis.vdu.lt/prussian/tabula.htm>
- **English grammar:** <http://donelaitis.vdu.lt/prussian/gramm.htm>
- **Polish grammar:** <http://prusaspira.org/gram_pol.html>

---

## Prusaspira (prusaspira.org)

**Search:** `GET http://prusaspira.org/wirdeins?wirds={STEM}&akc=Iz&bila=1`

Lemmas and inflection tables are embedded directly in the HTML response.
Each result block looks like:

```
prūsiskai: <b class='wirds'>LEMMA</b> <b style='display:none' class='dnum'>LEMMA <PARADIGM_NR></b>
ēngliskai: <b>TRANSLATION</b><br>
<table CLASS="boldtable"> … </table>
```

The inflection table has 4 cases (Nōm, Gēn, Dāt, Akk) × 6 columns
(m sg, m pl, f sg, f pl, n sg, n pl).  After it, adjectives have a
**comparison table** and a **pronominal forms table** (definite declension).

**Structured output:**

```json
{
  "lemma": "elaktrōmagnētiskas",
  "paradigm": "25",
  "translation": "electromagnetic",
  "declension": {
    "m": { "sg": {"Nom":"…","Gen":"…","Dat":"…","Akk":"…"},
           "pl": {"Nom":"…","Gen":"…","Dat":"…","Akk":"…"} },
    "f": { … },
    "n": { … }
  },
  "comparison": {
    "adj": {"komp":"…", "superl":"…", "uka_superl":"…"},
    "adv": {"pos":"…", "komp":"…", "superl":"…", "uka_superl":"…"}
  },
  "pronominal": { … }
}
```

---

## Twanksta (wirdeins.twanksta.org)

Two-step API.

**1. Search** — `GET https://wirdeins.twanksta.org/search/?dia=semba&s={STEM}&language=engl`

Returns HTML `<li>` entries with:

| Field         | Element                          |
|---------------|----------------------------------|
| word (lemma)  | `<span class='word'>`            |
| paradigm nr.  | `<span class='numb'>`            |
| gender        | `<span class='gend'>`            |
| description   | `<span class='desc'>`            |
| translations  | `<span class='translation-child'>` |

**2. Forms** — `POST https://wirdeins.twanksta.org/more/`
`Content-Type: application/x-www-form-urlencoded`

Body: `word={LEMMA}&numb={PARADIGM}&desc={DESCRIPTION}&dia=semba`

Returns HTML `<table id="subst">` per gender with 4 cases × 2 numbers.

**Structured output:**

```json
{
  "lemma": "tāns",
  "paradigm": "12",
  "gender": "masc",
  "translations": { "engl": ["he"] },
  "declension": {
    "masc": {
      "sg": {"Nom":"tāns","Gen":"tenesse","Dat":"tenesmu","Akk":"tennan"},
      "pl": {"Nom":"tenēi","Gen":"tenēisan","Dat":"tenēimans","Akk":"tennans"}
    }
  }
}
```

---

## Key differences

|                 | Prusaspira                              | Twanksta                               |
|-----------------|-----------------------------------------|----------------------------------------|
| Search          | `GET /wirdeins?wirds=…`                | `GET /search/?s=…`                    |
| Forms           | embedded in search HTML                  | separate `POST /more/`                  |
| Paradigm number | `<25>`-style tag inside text             | `<span class='numb'>`                   |
| Gender          | derived from column layout               | explicit `<span class='gend'>`          |
| Translations    | `ēngliskai:` text line                   | structured `<span class='translation-child'>` |
