"""Tests für den Flexions-Microservice (lexonomy/flexsrv.py).

Geprüft wird die Kante, die der Lexonomy-Editor sieht: die Response-Form
``{slots:[{slot, form, source}]}`` samt ``source = override > rule``. Die
erwarteten Oberflächen sind dieselben handabgelesenen wie in
``tests/test_generator.py`` (Stamm + Endung aus ``gen/*.lexc`` + Akzentregel) —
kein twanksta, kein NVH, kein Server nötig: der Endpoint-Kern
``generate_payload`` ist der ganze Testgegenstand, der HTTP-Handler nur ein
Transportskelett über ihm.

Atome baut die Session-Fixture bei Bedarf selbst (wie test_generator.py).
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lexonomy"))

import flexsrv

WANTED = [
    ("noun", "36", "obl"), ("noun", "53", "obl"),
    ("adj", "27", "pos"), ("adj", "27", "adv"),
    ("adj", "27", "cmp"), ("adj", "27", "sup"),
    ("verb", "132", "pres"), ("verb", "132", "nonfin"),
    ("verb", "85", "pres"), ("verb", "85", "nonfin"),
    ("verb", "85", "partPresAct"), ("verb", "85", "partPerfAct"),
    ("verb", "85", "partPerfPass"),
]


@pytest.fixture(scope="session")
def atoms():
    pytest.importorskip("hfst", reason="hfst-Paket fehlt (Atome brauchen es)")
    if not (REPO / "build/gen-accent.hfst").exists():
        pytest.skip("build/gen-accent.hfst fehlt — make gen-accent.hfst")
    for pos, paradigm, role in WANTED:
        done = subprocess.run(
            [sys.executable, str(REPO / "gen/atom_fst.py"), pos, paradigm, role],
            capture_output=True, text=True, cwd=REPO, check=False)
        if done.returncode:
            pytest.fail(f"Atom {pos}/{paradigm}/{role} nicht baubar:\n"
                        f"{(done.stderr or done.stdout)[-2000:]}")


def forms_by_slot(response) -> dict[str, str | None]:
    return {cell["slot"]: cell["form"] for cell in response["slots"]}


# ── Slot-Beschriftung: total, deutsch, Key-Fallback ──────────────────────────

@pytest.mark.parametrize("slot, label", [
    ("sg.nom", "Nom. Sg."), ("pl.dat", "Dat. Pl."),
    ("msc.sg.nom", "Masc. Nom. Sg."), ("neu.pl.acc", "Neut. Acc. Pl."),
    ("comp.msc.sg.nom", "Comparative Masc. Nom. Sg."),
    ("superl.neu.sg.dat", "Superlative Neut. Dat. Sg."),
    ("adv", "Adverb"), ("adv.comp", "Adverb (Comparative)"),
    ("adv.superl", "Adverb (Superlative)"),
    ("prs.sg1", "Present 1st Sg."), ("prt.sp3", "Past 3rd Sg./Pl."),
    ("subj.pl2", "Subjunctive 2nd Pl."), ("opt", "Optative 3rd Sg."),
    ("imprt.sg2", "Imperative 2nd Sg."),
    ("part.prs.act.msc.sg.nom", "Part. Pres. Active Masc. Nom. Sg."),
    ("part.prf.pss.fem.sg.acc", "Part. Perf. Passive Fem. Acc. Sg."),
])
def test_slot_label(slot, label):
    assert flexsrv.slot_label(slot) == label


def test_slot_label_falls_back_to_the_key():
    assert flexsrv.slot_label("sg.datx") == "sg.datx"
    assert flexsrv.slot_label("quatsch") == "quatsch"


# ── /generate: die Response, die der Editor rendert ──────────────────────────

def test_noun_matches_the_generator(atoms):
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun-masc", "paradigm": "36"})
    assert forms_by_slot(res) == {
        "sg.nom": "Dēiws", "sg.gen": "Dēiwas", "sg.dat": "Dēiwu", "sg.acc": "Dēiwan",
        "pl.nom": "Deiwāi", "pl.gen": "Dēiwan", "pl.dat": "Deiwammans",
        "pl.acc": "Dēiwans"}


def test_pos_carries_the_gender_and_is_split(atoms):
    res = flexsrv.generate_payload(
        {"headword": "dumslē", "pos": "noun-neut", "paradigm": "53"})
    assert (res["pos"], res["gender"]) == ("noun", "neut")
    assert res["family"] == "istem" and res["resolved"] == "53"
    assert res["stems"] == {"obl": "dumsl"}


def test_explicit_gender_wins_over_the_pos(atoms):
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun", "gender": "masc", "paradigm": "36"})
    assert res["gender"] == "masc"


def test_adjective_keeps_all_degrees(atoms):
    res = flexsrv.generate_payload(
        {"headword": "wilnis", "pos": "adj", "paradigm": "27"})
    got = forms_by_slot(res)
    assert got["msc.sg.nom"] == "wilnis"
    assert got["fem.pl.dat"] == "wilnimans"
    assert got["adv"] == "wilnjai"
    assert got["comp.msc.sg.nom"] == "wilnjaisis"
    assert got["superl.msc.sg.nom"] == "ukawilnjaisis"


def test_verb_table_and_participles(atoms):
    res = flexsrv.generate_payload(
        {"headword": "appautwei", "pos": "verb", "paradigm": "85"})
    got = forms_by_slot(res)
    assert got["prs.sp3"] == "appaua"                             # Präsens
    assert got["prt.pl1"] == "appauimai"                          # Präteritum
    assert got["subj.sp3"] == "appaulai"                          # Konjunktiv
    assert got["opt"] == "appausei"                               # Optativ
    assert got["imprt.pl2"] == "appauaiti"                        # Imperativ
    assert got["part.prs.act.msc.sg.nom"] == "appawints"
    assert got["part.prf.act.msc.sg.nom"] == "appawuns"
    assert got["part.prf.pss.msc.sg.nom"] == "appauts"


def test_verb_variant_87_is_resolved_from_the_lemma(atoms):
    res = flexsrv.generate_payload(
        {"headword": "kandtwei", "pos": "verb", "paradigm": "87"})
    assert res["paradigm"] == "87" and res["resolved"] == "87a"


def test_delivered_stem_overrides_the_rule(atoms):
    res = flexsrv.generate_payload(
        {"headword": "Patals", "pos": "noun-masc", "paradigm": "32",
         "stems": {"obl": "Patall"}})
    assert forms_by_slot(res)["sg.gen"] == "Patallas"


def test_role_metadata_reports_default_and_delivered_stem(atoms):
    plain = flexsrv.generate_payload(
        {"headword": "Patals", "pos": "noun-masc", "paradigm": "32"})
    obl = next(r for r in plain["roles"] if r["role"] == "obl")
    assert obl["label"] == "Oblique/nominal stem"
    assert (obl["stem"], obl["default"], obl["source"]) == ("Patal", "Patal", "rule")
    assert plain["delivered"] == {}

    fixed = flexsrv.generate_payload(
        {"headword": "Patals", "pos": "noun-masc", "paradigm": "32",
         "stems": {"obl": "Patall"}})
    obl = next(r for r in fixed["roles"] if r["role"] == "obl")
    assert (obl["stem"], obl["default"], obl["source"]) == (
        "Patall", "Patal", "stem")
    assert fixed["delivered"] == {"obl": "Patall"}


def test_verb_roles_cover_every_atom_with_a_label(atoms):
    res = flexsrv.generate_payload(
        {"headword": "appautwei", "pos": "verb", "paradigm": "85"})
    roles = {r["role"]: r for r in res["roles"]}
    assert set(roles) == {"pres", "nonfin", "partPresAct", "partPerfAct", "partPerfPass"}
    assert all(r["label"] and r["label"] != r["role"] for r in roles.values())


def test_delivered_thematic_vowel_regenerates_the_paradigm(atoms):
    res = flexsrv.generate_payload(
        {"headword": "rusītwei", "pos": "verb", "paradigm": "134",
         "stems": {"pres": "rusē"}})
    assert forms_by_slot(res)["prs.sp3"] == "rusēi"
    assert res["roles"][0]["source"] == "stem"


def test_unknown_role_stem_is_rejected(atoms):
    with pytest.raises(flexsrv.ApiError, match="unknown role"):
        flexsrv.generate_payload(
            {"headword": "Patals", "pos": "noun-masc", "paradigm": "32",
             "stems": {"quatsch": "X"}})


def test_stem_outside_the_alphabet_is_a_client_error(atoms):
    with pytest.raises(flexsrv.ApiError, match="allowed alphabet"):
        flexsrv.generate_payload(
            {"headword": "Patals", "pos": "noun-masc", "paradigm": "32",
             "stems": {"obl": "Pa tall"}})


def test_slots_come_back_in_role_order_with_groups(atoms):
    res = flexsrv.generate_payload(
        {"headword": "appautwei", "pos": "verb", "paradigm": "85"})
    slots = [cell["slot"] for cell in res["slots"]]
    assert slots[0].startswith("prs.") and slots[-1].startswith("part.")
    assert len(set(slots)) == len(slots)          # disjunkte Rollen-Slots
    assert {c["group"] for c in res["slots"]} >= {
        "Present", "Subjunctive", "Participle"}
    assert all(c["role"] for c in res["slots"])    # jede Zelle kennt ihre Rolle


# ── Tabellenlayout (wie wirdeins.twanksta.org) ───────────────────────────────

def test_noun_table_is_one_case_by_number_matrix(atoms):
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun-masc", "paradigm": "36"})
    tables = res["tables"]
    assert len(tables) == 1 and tables[0]["title"] is None
    block = tables[0]["blocks"][0]
    assert tables[0]["blocks"][0]["title"] is None   # Nomen: kein Genus-Block
    assert block["columns"] == ["Singular", "Plural"]
    assert block["rows"] == ["Nominative", "Genitive", "Dative", "Accusative"]
    assert block["cells"][0][0]["slot"] == "sg.nom"
    assert block["cells"][0][0]["form"] == "Dēiws"
    assert block["cells"][3][1]["slot"] == "pl.acc"


def test_adjective_has_three_gender_blocks_plus_degrees_and_adverb(atoms):
    res = flexsrv.generate_payload(
        {"headword": "wilnis", "pos": "adj", "paradigm": "27"})
    tables = res["tables"]
    assert [t["title"] for t in tables] == [
        None, "Comparison", "Comparative", "Superlative", "Adverb"]
    assert [b["title"] for b in tables[0]["blocks"]] == [
        "Masculine", "Feminine", "Neuter"]
    assert tables[1]["blocks"][0]["columns"] == ["Positive", "Comparative", "Superlative"]
    pos, comp, sup = tables[1]["blocks"][0]["cells"][0]
    assert (pos["form"], comp["form"], sup["form"]) == (
        "wilnis", "wilnjaisis", "ukawilnjaisis")
    # Steigerung als vollständige Deklination (3 Genera), wie der Positiv.
    for table, slot_head, msc_form in (
            (tables[2], "comp", "wilnjaisis"),
            (tables[3], "superl", "ukawilnjaisis")):
        assert [b["title"] for b in table["blocks"]] == [
            "Masculine", "Feminine", "Neuter"]
        cell = table["blocks"][0]["cells"][0][0]
        assert cell["slot"] == f"{slot_head}.msc.sg.nom" and cell["form"] == msc_form
    assert tables[4]["blocks"][0]["columns"] == ["Positive", "Comparative", "Superlative"]
    assert [c["form"] for c in tables[4]["blocks"][0]["cells"][0]] == [
        "wilnjai", "wilnjais", "ukawilnjais"]


def test_verb_lays_out_moods_and_participles(atoms):
    res = flexsrv.generate_payload(
        {"headword": "appautwei", "pos": "verb", "paradigm": "85"})
    titles = [t["title"] for t in res["tables"]]
    assert titles[:4] == ["Indicative", "Subjunctive", "Optative", "Imperative"]
    assert titles[4:] == ["Present participle active", "Past participle active",
                          "Past participle passive"]
    indicative = res["tables"][0]["blocks"][0]
    assert indicative["columns"] == ["Present", "Past"]
    assert indicative["rows"][0] == "1st Sg."
    assert indicative["cells"][0][0]["slot"] == "prs.sg1"
    part = res["tables"][4]["blocks"]
    assert [b["title"] for b in part] == ["Masculine", "Feminine", "Neuter"]
    assert part[0]["cells"][0][0]["slot"] == "part.prs.act.msc.sg.nom"


def test_override_shows_up_in_the_table_cell(atoms):
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun-masc", "paradigm": "36",
         "overrides": {"sg.dat": "deiwu"}})
    cell = res["tables"][0]["blocks"][0]["cells"][2][0]
    assert cell["slot"] == "sg.dat"
    assert (cell["form"], cell["source"], cell["ruleForms"]) == (
        "deiwu", "override", ["Dēiwu"])


def test_unknown_paradigm_has_no_tables():
    res = flexsrv.generate_payload(
        {"headword": "quatsch", "pos": "noun", "paradigm": "99"})
    assert res["tables"] == []


def test_empty_cell_stays_in_the_table(atoms, monkeypatch):
    """Eine Lücke der Grammatik ist eine editierbare Zelle, keine fehlende.

    Die gebauten Atome füllen jedes Slot ihres Paradigmas — Lücken wären eine
    Aussage über die Grammatik, nicht über den Dienst. Die Lücke wird deshalb
    hier erzwungen (der Dienst muss sie nur durchreichen).
    """
    real = flexsrv.gen.generate

    def holed(pos, paradigm, **kwargs):
        out = dict(real(pos, paradigm, **kwargs))
        out["pl.acc"] = ()
        return out

    monkeypatch.setattr(flexsrv.gen, "generate", holed)
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun-masc", "paradigm": "36"})
    gaps = [c for c in res["slots"] if c["form"] is None]
    assert [c["slot"] for c in gaps] == ["pl.acc"]
    assert gaps[0]["source"] == "none" and gaps[0]["ruleForms"] == []


# ── Overrides: die Editor-Rückrichtung ───────────────────────────────────────

def test_override_wins_over_the_rule(atoms):
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun-masc", "paradigm": "36",
         "overrides": {"sg.dat": "deiwu"}})
    cell = next(c for c in res["slots"] if c["slot"] == "sg.dat")
    assert cell["source"] == "override" and cell["form"] == "deiwu"
    assert cell["ruleForms"] == ["Dēiwu"]         # die Regel bleibt sichtbar


def test_override_fills_an_empty_cell(atoms):
    res = flexsrv.generate_payload(
        {"headword": "appautwei", "pos": "verb", "paradigm": "85",
         "overrides": {"part.prs.act.fem.sg.acc": "appawintījau"}})
    cell = next(c for c in res["slots"]
                if c["slot"] == "part.prs.act.fem.sg.acc")
    assert cell["source"] == "override"
    assert cell["form"] == "appawintījau"


def test_override_outside_the_vocabulary_is_kept(atoms):
    """Ein Override mit erfundenem Slot darf dem Editor nicht verlorengehen."""
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun-masc", "paradigm": "36",
         "overrides": {"sg.datx": "X"}})
    cell = next(c for c in res["slots"] if c["slot"] == "sg.datx")
    assert cell["source"] == "override" and cell["form"] == "X"
    assert cell["role"] is None


def test_empty_override_values_are_dropped(atoms):
    res = flexsrv.generate_payload(
        {"headword": "Dēiws", "pos": "noun-masc", "paradigm": "36",
         "overrides": {"sg.dat": "  ", "sg.gen": "dēiwas"}})
    cells = {c["slot"]: c["source"] for c in res["slots"]}
    assert cells["sg.dat"] == "rule" and cells["sg.gen"] == "override"


# ── Fehler: die Meldung landet in der UI ─────────────────────────────────────

def test_unknown_paradigm_is_a_note_not_an_error():
    res = flexsrv.generate_payload(
        {"headword": "quatsch", "pos": "noun", "paradigm": "99"})
    assert res["slots"] == [] and res["resolved"] is None
    assert "99" in res["note"]


def test_unknown_paradigm_still_echoes_the_overrides():
    res = flexsrv.generate_payload(
        {"headword": "quatsch", "pos": "noun", "paradigm": "99",
         "overrides": {"sg.nom": "quatsch"}})
    assert [c["source"] for c in res["slots"]] == ["override"]


@pytest.mark.parametrize("request_, needle", [
    ({"pos": "noun", "paradigm": "53"}, "headword"),
    ({"headword": "dumslē", "pos": "noun"}, "paradigm"),
    ({"headword": "dumslē", "pos": "quatsch-masc", "paradigm": "53"}, "POS"),
    ({"headword": "dumslē", "pos": "noun", "paradigm": "53",
      "gender": "quatsch"}, "unknown gender"),
    ({"headword": "dumslē", "pos": "noun", "paradigm": "53",
      "overrides": []}, "overrides"),
    ({"headword": "dumslē", "pos": "noun", "paradigm": "53",
      "stems": {"quatsch": "x"}}, "unknown role"),
])
def test_bad_request_raises_api_error(request_, needle):
    with pytest.raises(flexsrv.ApiError, match=needle):
        flexsrv.generate_payload(request_)


# ── Vokabular-Endpunkte ──────────────────────────────────────────────────────

def test_paradigms_list_matches_the_generator():
    listed = flexsrv.paradigms_payload("noun")
    keys = {(p["pos"], p["paradigm"]) for p in listed}
    assert keys == {k for k in flexsrv.gen.PARADIGMS if k[0] == "noun"}
    assert all(p["atoms"] and p["family"] for p in listed)


def test_paradigms_reject_a_foreign_pos():
    with pytest.raises(flexsrv.ApiError, match="unknown"):
        flexsrv.paradigms_payload("conj")


def test_health_lists_the_missing_atoms(monkeypatch):
    monkeypatch.setattr(flexsrv.gen, "atom_targets",
                        lambda: [(("noun", "36", "obl"),
                                  None, None, Path("/nope/gen-x.hfstol"))])
    health = flexsrv.health_payload()
    assert health["ok"] is False and health["missing"] == ["gen-x.hfstol"]


# ── HTTP-Transportschicht (echter Socket, CORS inklusive) ────────────────────

@pytest.fixture(scope="module")
def server():
    httpd = flexsrv.serve("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        return json.loads(response.read())


def test_health_over_http(server):
    health = _get(f"{server}/health")
    assert set(health) >= {"ok", "atoms", "missing"}


def test_paradigms_over_http(server):
    payload = _get(f"{server}/paradigms?pos=adj")
    assert payload["pos"] == "adj" and payload["paradigms"]


def test_slots_over_http(server):
    payload = _get(f"{server}/slots?pos=noun&paradigm=36&lemma=D%C4%93iws")
    assert payload["resolved"] == "36"
    assert payload["slots"][0]["label"] == "Nom. Sg."


def test_generate_over_http(server):
    body = json.dumps({"headword": "Dēiws", "pos": "noun-masc",
                       "paradigm": "36", "overrides": {"sg.dat": "deiwu"}}
                      ).encode("utf-8")
    request = urllib.request.Request(
        f"{server}/generate", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        payload = json.loads(response.read())
    cell = next(c for c in payload["slots"] if c["slot"] == "sg.dat")
    assert (cell["form"], cell["source"]) == ("deiwu", "override")


def test_preflight_is_answered(server):
    request = urllib.request.Request(f"{server}/generate", method="OPTIONS")
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 204
        assert "POST" in response.headers["Access-Control-Allow-Methods"]


def test_unknown_path_and_broken_json_are_400(server):
    for request in (
        urllib.request.Request(f"{server}/nope"),
        urllib.request.Request(f"{server}/generate", data=b"{not json",
                               method="POST"),
    ):
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        assert caught.value.code == 400
        assert json.loads(caught.value.read())["error"]