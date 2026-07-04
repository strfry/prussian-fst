# Prussian word form lookup — Twanksta only

Look up Prussian word forms on the Twanksta online dictionary
(https://wirdeins.twanksta.org). Search by STEM prefix (word beginning).

**Rate limit:** Max 1 request/s.

## Data file

Requires `twanksta_entries.json` from the
[`strfry/prussian-corpus`](https://github.com/strfry/prussian-corpus) release:

```bash
RELEASE="https://github.com/strfry/prussian-corpus/releases/download/v2026-07-04"
curl -fsSL "$RELEASE/twanksta_entries.json" -o data/external/twanksta_entries.json
```

Release tags follow `v{YYYY-MM-DD}`.

**Script path:** `TWANKSTA_PATH` → `data/external/twanksta_entries.json`

## Build

```bash
cd fst && make gen   # regenerate .lexc files from JSON
cd fst && make       # compile FST
```

## Twanksta API

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
