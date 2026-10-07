"""Scratch-Microservice: Generator-Ausgabe für den Lexonomy-Editor.

Dev-Dienst, kein Produktivdienst. Er legt genau eine Naht: der Editor
(``lexonomy/custom_editor.js``) ruft ``POST /generate`` und bekommt die
Flexionstabelle, die der **echte** Generator liefert — nicht die Mock-Regel
aus dem Editor.

Der Kern kommt unverändert aus ``gen/generator.py``: ``generate(pos, paradigm,
lemma, stems)`` → ``{slot: (form, …)}``, getrieben von den gebauten Atomen in
``build/``. Der Dienst ergänzt nur, was die HTTP-Kante braucht:

* Slot-Reihenfolge nach Rolle (grammatisch, nicht alphabetisch),
* deutsche Slot-/Gruppennamen (der Editor ist eine de-UI),
* das Tabellenraster des Originals (wirdeins.twanksta.org): Kasus × Numerus
  je Genus, Steigerung/Adverb, Verb nach Wijs/Zeit — siehe ``tables``,
* ``source`` je Zelle: ``override`` (aus dem NVH) schlägt ``rule``,
* Zellen **ohne** Form bleiben im Response (Lücken der Grammatik sind
  editierbar — dort greift der Override),
* CORS, weil Lexonomy auf einem anderen Origin läuft.

Keine neuen Abhängigkeiten: ``http.server`` aus der Standardbibliothek,
``pyhfst`` nur indirekt über den Generator.

Endpunkte::

    GET  /health              → {ok, atoms: n, missing: [...]}
    GET  /paradigms?pos=noun  → [{paradigm, family, roles, slots:[…]}]
    GET  /slots?pos=&paradigm=→ {roles, slots:[…]}   (nur Vokabular, kein FST)
    POST /generate            → siehe unten
    OPTIONS *                 → CORS-Preflight

``POST /generate`` Request::

    {"headword": "Dēiws", "pos": "noun-masc", "gender": "masc",
     "paradigm": "36", "overrides": {"sg.dat": "deiwu"},
     "stems": {"obl": "dēiw"}}          # optional, Stufe 1

Response::

    {"lemma": …, "pos": "noun", "gender": "masc", "paradigm": "36",
     "resolved": "36", "family": "astem", "stems": {"obl": "dēiw"},
     "delivered": {"obl": "dēiw"},
     "roles": [{"role": "obl", "label": "Obliquer/Nominalstamm",
                "stem": "dēiw", "default": "dēiw", "source": "stem"}],
     "slots": [{"slot": "sg.nom", "label": "Nom. Sg.", "group": "Deklination",
                "role": "obl", "form": "Dēiws", "ruleForms": ["Dēiws"],
                "source": "rule"}, …],
     "tables": [{"title": …, "blocks": [{"title": …,
                 "columns": ["Singular", "Plural"],
                 "rows": ["Nominativ", …],
                 "cells": [[{…cell…}, …], …]}]}],
     "note": "unknown paradigm '99' for pos='noun'"}

``roles`` ist die Stufe-1-Sicht: je Rolle der wirksame ``stem``, der Regel-
``default`` (ohne gelieferten Stamm) und ``source`` (``stem``/``rule``) — daraus
baut der Editor die Stamm-Textboxen. ``delivered`` sind genau die gelieferten
Stämme (Eingabe), ``stems`` der wirksame Satz.

``slots`` ist die flache Liste (stabil für API-Konsumenten), ``tables`` dieselben
Zellen im Raster des Originals wirdeins.twanksta.org: Nomen/Adjektiv/Partizip =
Kasus × Numerus je Genus, Adjektiv zusätzlich Steigerung/Adverb, Verb = Person ×
Zeit/Wijs. Der Editor rendert ``tables``; ein unbekanntes Paradigma liefert
``tables: []`` und die Overrides weiterhin in ``slots``.

Starten::

    uv run python lexonomy/flexsrv.py            # 127.0.0.1:8080
    uv run python lexonomy/flexsrv.py --port 9000 --host 0.0.0.0

Voraussetzung: ``make atoms`` (der Generator liest ``build/gen-*.hfstol``);
``/health`` sagt, was fehlt.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import unicodedata
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "gen"))

import generator as gen

# pyhfst-Lookup ist nicht als threadsicher dokumentiert (vgl.
# src/prussian_fst/api.py:_PIPELINE_LOCK) — alle Anfragen werden serialisiert.
_LOCK = threading.Lock()

POS_CHOICES = ("noun", "adj", "verb")

# ── Slot-Beschriftung ────────────────────────────────────────────────────────
# Der Generator kennt nur die Key-Vokabulare (_GENDER/_NUMBER/_CASE/…); die
# deutschen Namen der Anzeige stehen hier, damit der Generator datenfrei
# bleibt und der Dienst trotzdem eine fertige Tabelle liefert.

_GENDER_EN = {"msc": "Masc.", "fem": "Fem.", "neu": "Neut."}
_NUMBER_EN = {"sg": "Sg.", "pl": "Pl."}
_CASE_EN = {"nom": "Nom.", "gen": "Gen.", "dat": "Dat.", "acc": "Acc."}
_PERSON_EN = {"sg1": "1st Sg.", "sg2": "2nd Sg.", "sp3": "3rd Sg./Pl.",
              "pl1": "1st Pl.", "pl2": "2nd Pl."}
_DEGREE_EN = {"comp": "Comparative", "superl": "Superlative"}
_PART_TENSE_EN = {"prs": "Pres.", "prf": "Perf."}
_PART_VOICE_EN = {"act": "Active", "pss": "Passive"}
_FINITE_EN = {"prs": "Present", "prt": "Past"}

# Slot prefix → group (group order = table order).
_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("sg", "pl"), "Declension"),
    (("msc", "fem", "neu"), "Positive"),
    (("comp",), "Comparative"),
    (("superl",), "Superlative"),
    (("adv",), "Adverb"),
    (("prs",), "Present"),
    (("prt",), "Past"),
    (("subj",), "Subjunctive"),
    (("opt",), "Optative"),
    (("imprt",), "Imperative"),
    (("part",), "Participle"),
)
_GROUP_OF = {head: name for heads, name in _GROUPS for head in heads}

# Stufe-1 roles → display name. A role is one atom FST (one stem); the names
# say which stem the user is correcting.
_ROLE_LABEL = {
    "obl": "Oblique/nominal stem",
    "pos": "Positive stem",
    "adv": "Adverb stem",
    "cmp": "Comparative stem",
    "sup": "Superlative stem",
    "pres": "Present stem",
    "pret": "Past stem",
    "nonfin": "Infinitive/non-finite stem",
    "partPresAct": "Present participle stem",
    "partPerfAct": "Past active participle stem",
    "partPerfPass": "Past passive participle stem",
}


def role_label(role: str) -> str:
    return _ROLE_LABEL.get(role, role)


def slot_label(slot: str) -> str:
    """``comp.msc.sg.nom`` → ``Comparative Masc. Nom. Sg.`` (unknown → key).

    Total: an override with a made-up slot key must not raise — the key comes
    back unchanged.
    """
    try:
        return _slot_label(slot)
    except KeyError:
        return slot


def _slot_label(slot: str) -> str:
    parts = slot.split(".")
    head = parts[0]
    if head in gen._NUMBER and len(parts) == 2:                 # noun
        return f"{_CASE_EN[parts[1]]} {_NUMBER_EN[head]}"
    if head in _GENDER_EN and len(parts) == 3:                   # adj. positive
        return f"{_GENDER_EN[head]} {_CASE_EN[parts[2]]} {_NUMBER_EN[parts[1]]}"
    if head in _DEGREE_EN and len(parts) == 4:                   # adj. comp/superl
        return (f"{_DEGREE_EN[head]} {_GENDER_EN[parts[1]]} "
                f"{_CASE_EN[parts[3]]} {_NUMBER_EN[parts[2]]}")
    if head == "adv":
        return "Adverb" if len(parts) == 1 else f"Adverb ({_DEGREE_EN[parts[1]]})"
    if head == "part" and len(parts) == 6:
        return (f"Part. {_PART_TENSE_EN[parts[1]]} {_PART_VOICE_EN[parts[2]]} "
                f"{_GENDER_EN[parts[3]]} {_CASE_EN[parts[5]]} {_NUMBER_EN[parts[4]]}")
    if head in gen._FINITE_TENSE and len(parts) == 2:            # finite verb
        return f"{_FINITE_EN[head]} {_PERSON_EN[parts[1]]}"
    if head == "subj" and len(parts) == 2:
        return f"Subjunctive {_PERSON_EN[parts[1]]}"
    if head == "opt":
        return "Optative 3rd Sg."
    if head == "imprt" and len(parts) == 2:
        return f"Imperative {_PERSON_EN[parts[1]]}"
    return slot


def slot_group(slot: str) -> str:
    return _GROUP_OF.get(slot.split(".")[0], "Inflection")


def _slot_meta(pos: str, paradigm: str, lemma: str = "") -> list[dict[str, str]]:
    """Slot-Vokabular des Paradigmas in Rollenreihenfolge, je Slot seine IDs."""
    try:
        par = gen.paradigm_spec(pos, paradigm, lemma)
    except KeyError:
        return []
    meta: dict[str, dict[str, str]] = {}
    for role, spec in par.roles.items():
        for slot in spec.slots:
            meta.setdefault(slot, {"slot": slot, "label": slot_label(slot),
                                   "group": slot_group(slot), "role": role})
    return list(meta.values())


# ── Tabellenlayout (wie wirdeins.twanksta.org) ───────────────────────────────
# Der Generator liefert Zellen flach; das Original ordnet sie zu Matrizen:
# Nomen/Adjektiv/Partizip = Kasus (Zeile) × Numerus (Spalte), ein Block je Genus;
# Adjektiv zusätzlich Steigerung + Adverb; Verb = Person (Zeile) × Zeit/Wijs
# (Spalte). Die Struktur steht hier, damit der Editor nur noch rendert.

_CASE_ROWS = (("nom", "Nominative"), ("gen", "Genitive"),
              ("dat", "Dative"), ("acc", "Accusative"))
_NUM_COLS = (("sg", "Singular"), ("pl", "Plural"))
_GENDER_BLOCKS = (("msc", "Masculine"), ("fem", "Feminine"), ("neu", "Neuter"))
_PERSON_ROWS = (("sg1", "1st Sg."), ("sg2", "2nd Sg."), ("sp3", "3rd Sg./Pl."),
                ("pl1", "1st Pl."), ("pl2", "2nd Pl."))
_DEGREES = (("", "Positive"), ("comp", "Comparative"), ("superl", "Superlative"))
_PARTICIPLES = (("part.prs.act", "Present participle active"),
                ("part.prf.act", "Past participle active"),
                ("part.prf.pss", "Past participle passive"))


def _blank_cell(slot: str) -> dict[str, Any]:
    """Zelle ohne Regelform: im Raster sichtbar und overridbar (Lücke)."""
    return {"slot": slot, "label": slot_label(slot), "group": slot_group(slot),
            "role": None, "form": None, "ruleForms": [], "source": "none"}


def _declension_table(title: str, prefix: str, gendered: bool,
                      cells: Mapping[str, dict], present: set[str],
                      corner: str = "Case") -> dict[str, Any] | None:
    """Kasus × Numerus, ein Block je Genus (bzw. ein Block ohne Genus)."""
    genders = _GENDER_BLOCKS if gendered else ((None, None),)
    blocks: list[dict[str, Any]] = []
    seen = False
    for gender, glabel in genders:
        matrix = []
        for case, _ in _CASE_ROWS:
            row = []
            for number, _ in _NUM_COLS:
                parts = ([prefix] if prefix else []) \
                    + ([gender] if gender else []) + [number, case]
                slot = ".".join(parts)
                seen = seen or slot in present
                row.append(dict(cells.get(slot) or _blank_cell(slot)))
            matrix.append(row)
        blocks.append({"title": glabel, "corner": corner,
                       "columns": [label for _, label in _NUM_COLS],
                       "rows": [label for _, label in _CASE_ROWS],
                       "cells": matrix})
    return {"title": title or None, "blocks": blocks} if seen else None


def _one_row_table(title: str, specs: list[tuple[str, str]],
                   cells: Mapping[str, dict], present: set[str],
                   columns: list[str]) -> dict[str, Any] | None:
    """Eine Zeile mit benannten Spalten (Steigerung, Adverb, Optativ)."""
    row = []
    seen = False
    for slot, _ in specs:
        seen = seen or slot in present
        row.append(dict(cells.get(slot) or _blank_cell(slot)))
    if not seen:
        return None
    return {"title": title or None, "blocks": [{
        "title": None, "corner": "", "columns": columns,
        "rows": [""], "cells": [row]}]}


def _build_tables(pos: str, cells: Mapping[str, dict],
                  present: set[str]) -> list[dict[str, Any]]:
    """Slots → Tabellenblöcke in der Reihenfolge des Originals."""
    tables: list[dict[str, Any]] = []

    if pos == "noun":
        table = _declension_table("", "", gendered=False, cells=cells,
                                  present=present)
        if table:
            tables.append(table)
        return tables

    if pos == "adj":
        pos_table = _declension_table("", "", gendered=True, cells=cells,
                                      present=present)
        if pos_table:
            tables.append(pos_table)
        cmp_table = _one_row_table(
            "Comparison",
            [(f"{degree}.msc.sg.nom", label) for degree, label in _DEGREES[1:]],
            cells, present, ["Positive", "Comparative", "Superlative"])
        if cmp_table:
            # Positiv-Spalte zuerst, dann die beiden Gradformen.
            cmp_table["blocks"][0]["cells"][0].insert(
                0, dict(cells.get("msc.sg.nom") or _blank_cell("msc.sg.nom")))
            tables.append(cmp_table)
        # Steigerung dekliniert wie der Positiv (3 Genera × 4 Kasus × 2 Numeri).
        for prefix, label in (("comp", "Comparative"), ("superl", "Superlative")):
            degree_table = _declension_table(label, prefix, gendered=True,
                                             cells=cells, present=present)
            if degree_table:
                tables.append(degree_table)
        adv_table = _one_row_table(
            "Adverb",
            [("adv", "Adverb"), ("adv.comp", "Komparativ"), ("adv.superl", "Superlativ")],
            cells, present, ["Positive", "Comparative", "Superlative"])
        if adv_table:
            tables.append(adv_table)
        return tables

    # pos == "verb": finit nach Wijs, danach Partizipien als Deklination.
    present_tenses = [t for t in ("prs", "prt") if any(
        f"{t}.{person}" in present for person, _ in _PERSON_ROWS)]
    if present_tenses:
        matrix = []
        for person, _ in _PERSON_ROWS:
            matrix.append([dict(cells.get(f"{tense}.{person}")
                                or _blank_cell(f"{tense}.{person}"))
                           for tense in present_tenses])
        tables.append({"title": "Indicative", "blocks": [{
            "title": None, "corner": "Person",
            "columns": [_FINITE_EN[t].capitalize() for t in present_tenses],
            "rows": [label for _, label in _PERSON_ROWS], "cells": matrix}]})

    if any(f"subj.{person}" in present for person, _ in _PERSON_ROWS):
        matrix = [[dict(cells.get(f"subj.{person}") or _blank_cell(f"subj.{person}"))]
                  for person, _ in _PERSON_ROWS]
        tables.append({"title": "Subjunctive", "blocks": [{
            "title": None, "corner": "Person", "columns": [""],
            "rows": [label for _, label in _PERSON_ROWS], "cells": matrix}]})

    if "opt" in present:
        tables.append(_one_row_table("Optative", [("opt", "3rd Sg.")],
                                     cells, present, ["3. Sg."]))
    if any(f"imprt.{person}" in present for person in ("sg2", "pl2")):
        matrix = [[dict(cells.get(f"imprt.{person}") or _blank_cell(f"imprt.{person}"))]
                  for person in ("sg2", "pl2")]
        tables.append({"title": "Imperative", "blocks": [{
            "title": None, "corner": "Person", "columns": [""],
            "rows": ["2nd Sg.", "2nd Pl."], "cells": matrix}]})

    for prefix, label in _PARTICIPLES:
        table = _declension_table(label, prefix, gendered=True,
                                  cells=cells, present=present)
        if table:
            tables.append(table)

    return [t for t in tables if t]


# ── Anfrage → Response ───────────────────────────────────────────────────────


class ApiError(Exception):
    """Client-Fehler (→ 400) mit deutscher Meldung für die UI."""


def _norm_lemma(text: str) -> str:
    return unicodedata.normalize("NFC", (text or "").strip())


def split_pos(value: str) -> tuple[str, str]:
    """NVH ``noun-masc`` → ``("noun", "masc")`` (POS und Genus sind verschmolzen)."""
    value = (value or "").strip()
    base, _, gender = value.partition("-")
    base = base.lower()
    if base not in POS_CHOICES:
        raise ApiError(f"unknown POS {value!r} (expected: {', '.join(POS_CHOICES)})")
    return base, gender.strip().lower()


def _str_map(raw: Any, field: str) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ApiError(f"{field} must be an object")
    out: dict[str, str] = {}
    for key, value in raw.items():
        if value is None or str(value).strip() == "":
            continue
        out[str(key)] = _norm_lemma(str(value))
    return out


def generate_payload(request: Mapping[str, Any]) -> dict[str, Any]:
    """Der Endpoint-Kern — ohne HTTP, damit Tests ihn direkt aufrufen."""
    headword = _norm_lemma(str(request.get("headword") or ""))
    raw_pos = str(request.get("pos") or "")
    pos, pos_gender = split_pos(raw_pos)
    gender = _norm_lemma(str(request.get("gender") or "")).lower() or pos_gender
    paradigm = str(request.get("paradigm") or "").strip()
    overrides = _str_map(request.get("overrides"), "overrides")
    stems = _str_map(request.get("stems"), "stems")

    if not headword:
        raise ApiError("headword is missing")
    if not paradigm:
        raise ApiError("paradigm is missing (Twanksta paradigm number)")
    if gender and gender not in ("masc", "fem", "neut"):
        raise ApiError(f"unknown gender {gender!r} (masc|fem|neut)")

    with _LOCK:
        try:
            resolved = gen.resolve_paradigm(pos, paradigm, headword)
            par = gen.paradigm_spec(pos, paradigm, headword)
        except KeyError:
            note = f"unknown paradigm {paradigm!r} for pos={pos!r}"
            # Overrides stay visible: an override is never "gone", just unproducible.
            return {
                "lemma": headword, "pos": pos, "gender": gender,
                "paradigm": paradigm, "resolved": None, "family": None,
                "stems": {}, "delivered": {}, "roles": [], "note": note,
                "tables": [],
                "slots": [
                    {"slot": slot, "label": slot_label(slot),
                     "group": slot_group(slot), "role": None,
                     "form": form, "ruleForms": [], "source": "override"}
                    for slot, form in overrides.items()],
            }
        bad_roles = [role for role in stems if role not in par.roles]
        if bad_roles:
            raise ApiError(f"unknown role(s) {', '.join(map(repr, bad_roles))} "
                           f"for {pos}/{paradigm} (known: {', '.join(par.roles)})")
        try:
            forms_by_slot = gen.generate(pos, paradigm, lemma=headword, stems=stems,
                                         gender=gender or None)
        except FileNotFoundError:
            raise ApiError("generator atoms are missing — run `make atoms`") from None
        except ValueError as exc:
            if "STEM_ALPHABET" in str(exc):
                raise ApiError("a delivered stem contains characters outside "
                               "the allowed alphabet") from None
            raise ApiError(str(exc)) from None
        defaults = gen.default_stems(pos, paradigm, lemma=headword)
        used_stems = dict(defaults)
        used_stems.update(stems)

    meta = {entry["slot"]: entry for entry in _slot_meta(pos, resolved, headword)}
    cells: dict[str, dict[str, Any]] = {}
    for entry in meta.values():
        slot = entry["slot"]
        forms = list(forms_by_slot.get(slot, ()))
        if slot in overrides:
            cells[slot] = {**entry, "form": overrides[slot],
                           "ruleForms": forms, "source": "override"}
        else:
            cells[slot] = {**entry, "form": forms[0] if forms else None,
                           "ruleForms": forms, "source": "rule" if forms else "none"}
    cells_list = list(cells.values())
    # Overrides außerhalb des Paradigma-Vokabulars: der Editor darf sie nicht
    # stillschweigend aus dem NVH verlieren.
    extra = []
    for slot, form in overrides.items():
        if slot in meta:
            continue
        extra.append({"slot": slot, "label": slot_label(slot),
                      "group": slot_group(slot), "role": None,
                      "form": form, "ruleForms": [], "source": "override"})
        cells[slot] = extra[-1]

    return {
        "lemma": headword, "pos": pos, "gender": gender,
        "paradigm": paradigm, "resolved": resolved, "family": par.family,
        "stems": used_stems,
        "delivered": dict(stems),
        "roles": [{"role": role, "label": role_label(role),
                   "stem": used_stems.get(role, ""),
                   "default": defaults.get(role, ""),
                   "source": "stem" if role in stems else "rule"}
                  for role in par.roles],
        "slots": cells_list + extra,
        "tables": _build_tables(pos, cells, set(meta)),
        "note": None,
    }


def paradigms_payload(pos: str) -> list[dict[str, Any]]:
    """Paradigmen-Liste für die Auswahl im Editor (Vokabular, kein FST-Zugriff)."""
    if pos not in POS_CHOICES:
        raise ApiError(f"unknown POS {pos!r} (expected: {', '.join(POS_CHOICES)})")
    out = []
    for (entry_pos, paradigm), par in sorted(gen.PARADIGMS.items()):
        if entry_pos != pos:
            continue
        roles = []
        for role, spec in par.roles.items():
            slots = [s for s in spec.slots]
            roles.append({"role": role, "slots": [
                {"slot": s, "label": slot_label(s), "group": slot_group(s)}
                for s in slots]})
        out.append({"pos": pos, "paradigm": paradigm, "family": par.family,
                    "roles": roles,
                    "atoms": [gen.atom_name(pos, paradigm, role)
                              for role in par.roles]})
    return out


def health_payload() -> dict[str, Any]:
    """Ist der Generator lauffähig? (Atome gebaut, Genus-Vokabular vorhanden.)"""
    missing = [path.name for _, _, _, path in gen.atom_targets()
               if not path.exists()]
    return {"ok": not missing, "atoms": len(gen.atom_targets()),
            "missing": missing,
            "accent": (gen.ATOM_DIR / "gen-accent.hfst").exists(),
            "pos": list(POS_CHOICES)}


# ── HTTP ─────────────────────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    server_version = "prussian-flexsrv/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[flexsrv] %s\n" % (fmt % args))

    # CORS: der Editor läuft auf dem Lexonomy-Origin, der Dienst ist dev-local.
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")

    def _send(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                payload = health_payload()
                self._send(200, payload)
                return
            if parsed.path == "/paradigms":
                pos = (query.get("pos") or ["noun"])[0].lower()
                self._send(200, {"pos": pos, "paradigms": paradigms_payload(pos)})
                return
            if parsed.path == "/slots":
                pos = (query.get("pos") or [""])[0].lower()
                paradigm = (query.get("paradigm") or [""])[0]
                lemma = (query.get("lemma") or [""])[0]
                if pos not in POS_CHOICES:
                    raise ApiError("pos is missing (noun|adj|verb)")
                resolved = gen.resolve_paradigm(pos, paradigm, lemma)
                self._send(200, {"pos": pos, "paradigm": paradigm,
                                 "resolved": resolved,
                                 "slots": _slot_meta(pos, resolved, lemma)})
                return
            raise ApiError(f"unknown path {parsed.path}")
        except ApiError as exc:
            self._send(400, {"error": str(exc)})
        except (KeyError, ValueError) as exc:
            self._send(400, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                request = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiError(f"invalid JSON: {exc}") from None
            if not isinstance(request, dict):
                raise ApiError("request body must be a JSON object")
            if parsed.path != "/generate":
                raise ApiError(f"unknown path {parsed.path}")
            self._send(200, generate_payload(request))
        except ApiError as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:       # noqa: BLE001  # pragma: no cover (500)
            self.log_error("intern: %r", exc)
            self._send(500, {"error": f"Generator-Fehler: {exc}"})


def serve(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    health = health_payload()
    if not health["ok"]:
        print(f"WARNING: {len(health['missing'])} of {health['atoms']} atoms "
              f"missing — run `make atoms` (the generator then raises FileNotFoundError).",
              file=sys.stderr)
    print(f"flexsrv auf http://{args.host}:{args.port}  "
          f"(Atome {health['atoms'] - len(health['missing'])}/{health['atoms']})",
          file=sys.stderr)
    serve(args.host, args.port).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())