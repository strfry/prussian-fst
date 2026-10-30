"""Build-Zeit-Ablesen der Endungen (gen/*.lexc → build/gen-endings.json) und der
Akzentregeln (gen/accent.regex → build/gen-accent.hfstol).

Je (pos, Twanksta-Paradigma, Rolle) gibt es ein Atom, das sind die Infl-Lexika
der Rolle:

    gen/<family>.lexc
        --(nur LEXICON Root ersetzt: <Infl-Lexikone> ;)-->  build/gen-atom-<name>.lexc
        --hfst.compile_lexc_file-->                          Tag ↦ Endung+Marker
        --alle Pfade ablesen-->                              gen-endings.json[<name>][<slot>]

Ein Atom ist eine endliche Tabelle Slot-Tag → Endungen (mit ^ ~ >), z. B.
``+N+Pl+Dat ↦ ^īmans``. Die Endungen hängen von Paradigma und Rolle ab, nicht vom
einzelnen Stamm: die Eingabeseite eines Atoms trägt nur Tags. Das prüft der Build
(``read_endings``); stünden dort Buchstaben oder Flags, wäre das Atom keine Tabelle
mehr und der Build bricht ab.

Die Phonologie an der Grenze Stamm/Endung (Makronkürzung und Degemination vor ^,
Schutz durch ~, Gemination vor >, Koda-Vereinfachung vor -s) steckt allein in
``build/gen-accent.hfstol`` (Kopierer .o. gen-accent.hfst). Der Generator bildet
``Stamm + Endung`` und schickt es durch diese Regeln — dieselbe Relation wie die
frühere Komposition ``Kopierer ++ Atom .o. Akzent`` je Atom-FST.

Genau ein lexc-Compile pro Prozess: ``hfst.compile_lexc_file`` liefert ab dem
zweiten Aufruf im selben Prozess ein leeres Transducer. Deshalb ein Prozess je
Atom; ``--all`` startet sie als Subprozesse und schreibt die Tabelle.

Der Build ist die einzige Stelle, die die Grammatik anfasst — ``gen/*.lexc`` und
``gen/accent.regex`` bleiben die einzige Quelle, ``gen/generator.py`` liest zur
Laufzeit nur die Tabelle und die Akzentregeln.

    uv run python gen/atom_fst.py --list
    uv run python gen/atom_fst.py noun 53                 # Endungen eines Atoms zeigen
    uv run python gen/atom_fst.py verb 85 partPresAct
    uv run python gen/atom_fst.py --all -j8               # Tabelle + Akzentregeln bauen
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generator import (  # noqa: E402
    ACCENT_PATH as ACCENT_OL, ATOM_DIR, ENDINGS_PATH, ROOT as GEN_ROOT, STEM_ALPHABET,
    atom_name, atom_targets, paradigm_spec, resolve_paradigm, slot_tag,
)

import hfst  # noqa: E402

OL = hfst.ImplementationType.HFST_OL_TYPE
ACCENT = ROOT / "build" / "gen-accent.hfst"
EPSILON = "@_EPSILON_SYMBOL_@"

# Im hfst.regex sind + ^ ~ > % { } : | ( ) & - $ Sonderzeichen → "%" davor.
_REGEX_SPECIAL = set("+^~>%{}:|()&-$")


def copier_regex(alphabet: str = STEM_ALPHABET) -> str:
    """Kopierer-Ausdruck: ``[a|b|…]*`` — Union, dann Kleene-Stern.

    Union (nicht Konkatenation): ``[ab]*`` kopiert genau ein Zeichen aus der Menge,
    ``[ab|cd]*`` wäre eine zweizeichige Alternative.
    """
    units = [f"%{c}" if c in _REGEX_SPECIAL else c for c in alphabet]
    return "[" + " | ".join(units) + "]*"


_LEXICON_START = re.compile(r"^LEXICON\s+(\S+)\s*$")
_CALL = re.compile(r"^\s+\S+\s*;\s*(?:!.*)?$")
_BLANK_OR_COMMENT = re.compile(r"^\s*(?:!.*)?$")


def rewrite_root(text: str, atoms: tuple[str, ...]) -> str:
    """``LEXICON Root`` durch die Atom-Aufrufe ersetzen — sonst nichts anfassen.

    Der Root-Rumpf besteht aus Lexikonaufrufen (``  P53 ;``), Leerzeilen und
    Kommentaren; der erste andere Inhalt beendet ihn. Es werden KEINE Endungen,
    Ausnahmelisten oder Stammlexikone angefasst — nur der Einstiegspunkt.
    """
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines)
                  if _LEXICON_START.match(line.rstrip("\n"))
                  and _LEXICON_START.match(line.rstrip("\n")).group(1) == "Root"), None)
    if start is None:
        raise ValueError(f"kein LEXICON Root in der Grammatik ({text[:40]!r}…)")
    end = start + 1
    while end < len(lines) and (_CALL.match(lines[end]) or _BLANK_OR_COMMENT.match(lines[end])):
        end += 1
    if end == start + 1:
        raise ValueError("LEXICON Root ist leer — nichts zu ersetzen")
    new_root = "LEXICON Root\n" + "".join(f"  {atom} ;\n" for atom in atoms)
    return "".join(lines[:start]) + new_root + "".join(lines[end:])


def _check_alphabet(atom, name: str) -> None:
    """Build-Assertion: alle Endungszeichen müssen im Kopierer-Alphabet liegen.

    Ein Endungszeichen außerhalb von STEM_ALPHABET fällt beim Kopieren still weg —
    die Form käme dann verstümmelt heraus. Geprüft wird das Alphabet des Atoms
    (Tags sind mehrzeichige Symbole und werden übersprungen); die Stammseite deckt
    STEM_ALPHABET per Konstruktion ab.
    """
    missing = set()
    for symbol in atom.get_alphabet():
        text = str(symbol)
        if len(text) != 1 or text.startswith("@_") or text == "+":
            continue
        if text in STEM_ALPHABET or text.isdigit():
            continue
        missing.add(text)
    if missing:
        raise SystemExit(
            f"{name}: Endungszeichen {sorted(missing)!r} fehlen in STEM_ALPHABET "
            f"(gen/generator.py) — der Stammkopierer würde sie nicht durchlassen")


def read_endings(pos: str, paradigm: str, role: str,
                 lemma: str = "") -> tuple[str, dict[str, list[str]]]:
    """Ein Atom ablesen: (Name, Slot → Endungen). Genau ein lexc-Compile — danach
    ist der Prozess verbraucht.

    ``lemma`` wird nur zur Variantenauflösung gebraucht (Verb 87a/87b); ohne
    Lemma muss die konkrete Paradigmennummer genannt werden.
    """
    par = paradigm_spec(pos, paradigm, lemma)
    spec = par.roles[role]
    name = atom_name(pos, paradigm, role, lemma)
    ATOM_DIR.mkdir(parents=True, exist_ok=True)

    source = GEN_ROOT / spec.lexc
    lexc_path = ATOM_DIR / f"gen-atom-{name}.lexc"
    lexc_path.write_text(rewrite_root(source.read_text(), spec.atoms))

    atom = hfst.compile_lexc_file(str(lexc_path))
    if atom is None or atom.number_of_states() == 0:
        raise SystemExit(f"{name}: lexc-Compile leer ({lexc_path})")
    _check_alphabet(atom, name)
    if atom.is_cyclic():
        raise SystemExit(f"{name}: Atom ist zyklisch, keine endliche Endungstabelle")

    by_tag: dict[str, set[str]] = collections.defaultdict(set)
    for _weight, pairs in atom.extract_paths(output="raw"):
        stray = sorted({i for i, _o in pairs if i != EPSILON and not i.startswith("+")})
        if stray:
            raise SystemExit(
                f"{name}: Eingabeseite trägt {stray!r} statt nur Tags — die Endung "
                f"hinge dann vom Stamm ab und ist als Tabelle nicht darstellbar")
        tag = "".join(i for i, _o in pairs if i != EPSILON)
        by_tag[tag].add("".join(o for _i, o in pairs if o != EPSILON))

    accent = hfst.HfstInputStream(str(build_accent())).read()
    probe = "Teststam"
    endings: dict[str, list[str]] = {}
    empty = []
    for slot in spec.slots:
        found = sorted(by_tag.get(slot_tag(slot), ()))
        if not found or not all(accent.lookup(probe + e) for e in found):
            empty.append(slot)
        endings[slot] = found
    if empty:
        raise SystemExit(
            f"{name}: {len(empty)} Slots ohne Pfad (Atom {spec.atoms} in "
            f"{spec.lexc}): {', '.join(empty[:6])}{' …' if len(empty) > 6 else ''}")
    return name, endings


def build_accent(force: bool = False) -> Path:
    """``build/gen-accent.hfstol``: die Akzentregeln als Lookup-Transducer.

    Vorgeschaltet ist der Kopierer, damit jedes Zeichen von STEM_ALPHABET explizit
    im Alphabet steht: in der Komposition ``Atom .o. Akzent`` hätte hfst die
    unbekannten Symbole der Regeln (``?``) gegen das Atom-Alphabet aufgelöst, ein
    allein stehender Lookup-Transducer kennt nur, was in ihm steht.
    """
    if ACCENT_OL.exists() and not force and ACCENT_OL.stat().st_mtime >= ACCENT.stat().st_mtime:
        return ACCENT_OL
    if not ACCENT.exists():
        raise SystemExit(f"{ACCENT} fehlt — bauen mit: make gen-accent.hfst")
    rules = hfst.HfstTransducer(hfst.regex(copier_regex()))
    rules.compose(hfst.HfstInputStream(str(ACCENT)).read())
    rules.minimize()
    rules.convert(OL)
    tmp = ACCENT_OL.with_suffix(f".tmp{os.getpid()}")
    stream = hfst.HfstOutputStream(filename=str(tmp), type=OL)
    stream.write(rules)
    stream.flush()
    stream.close()
    tmp.replace(ACCENT_OL)
    return ACCENT_OL


def _one(args: tuple[str, str, str]) -> tuple[str, dict[str, list[str]]] | str:
    """Ein Atom im EIGENEN Prozess ablesen (ein lexc-Compile pro Prozess!)."""
    pos, paradigm, role = args
    done = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), pos, paradigm, role, "--json"],
        capture_output=True, text=True)
    if done.returncode:
        detail = (done.stderr or done.stdout).strip().splitlines()
        return f"FEHLER {pos}/{paradigm}/{role}: " + (detail[-1] if detail else "?")
    name, endings = json.loads(done.stdout)
    return name, endings


def build_all(jobs: int) -> int:
    """Akzentregeln und die ganze Endungstabelle bauen; alte Atom-FSTs entfernen."""
    build_accent(force=True)
    targets = [(pos, paradigm, role) for pos, paradigm, role, _name in atom_targets()]
    table: dict[str, dict[str, list[str]]] = {}
    errors = 0
    with ThreadPoolExecutor(max_workers=max(jobs, 1)) as pool:
        for result in pool.map(_one, targets):
            if isinstance(result, str):
                errors += 1
                print(result, file=sys.stderr)
            else:
                table[result[0]] = result[1]
    if errors:
        print(f"{errors}/{len(targets)} Atome fehlerhaft, {ENDINGS_PATH} nicht geschrieben",
              file=sys.stderr)
        return 1
    tmp = ENDINGS_PATH.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(table, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                   encoding="utf-8")
    tmp.replace(ENDINGS_PATH)
    for stale in ATOM_DIR.glob("gen-*.hfstol"):      # Atom-FSTs der früheren Bauweise
        if stale != ACCENT_OL:
            stale.unlink()
    print(f"{len(table)} Atome, {sum(len(e) for e in table.values())} Slots → {ENDINGS_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pos", nargs="?", choices=["noun", "adj", "verb"])
    parser.add_argument("paradigm", nargs="?")
    parser.add_argument("role", nargs="?")
    parser.add_argument("--lemma", default="",
                        help="Lemma zur Variantenauflösung (Verb 87a/87b)")
    parser.add_argument("--list", action="store_true",
                        help="alle zu bauenden Atome auflisten")
    parser.add_argument("--all", action="store_true",
                        help="Endungstabelle + Akzentregeln bauen")
    parser.add_argument("-j", "--jobs", type=int, default=max(os.cpu_count() or 1, 1))
    parser.add_argument("--print-regex", action="store_true",
                        help="Kopierer-Ausdruck ausgeben")
    parser.add_argument("--json", action="store_true",
                        help="ein Atom als JSON [Name, {Slot: Endungen}] ausgeben (für --all)")
    args = parser.parse_args(argv)

    if args.print_regex:
        print(copier_regex())
        return 0
    if args.all:
        return build_all(args.jobs)
    if args.list:
        for pos, paradigm, role, name in atom_targets():
            print(f"{pos:5} {paradigm:5} {role:9} {name}")
        print(f"{len(atom_targets())} Atome", file=sys.stderr)
        return 0
    if not (args.pos and args.paradigm):
        parser.error("pos und paradigm sind nötig (oder --list/--all)")
    key = resolve_paradigm(args.pos, args.paradigm, args.lemma)
    if key != str(args.paradigm) and not args.lemma:
        parser.error(f"Paradigma {args.paradigm} ist eine Variante (→ {key}) — "
                     f"--lemma angeben oder {key} direkt bauen")
    try:
        par = paradigm_spec(args.pos, args.paradigm, args.lemma)
    except KeyError:
        parser.error(f"unbekanntes Paradigma {args.pos}/{args.paradigm}")
    role = args.role
    if role is None:
        roles = sorted(par.roles)
        if len(roles) != 1:
            parser.error(f"Paradigma {key} hat {len(roles)} Rollen: "
                         f"{', '.join(roles)} — Rolle angeben")
        role = roles[0]
    elif role not in par.roles:
        parser.error(f"unbekannte Rolle {role!r} — {', '.join(sorted(par.roles))}")
    name, endings = read_endings(args.pos, args.paradigm, role, lemma=args.lemma)
    if args.json:
        print(json.dumps([name, endings], ensure_ascii=False))
    else:
        print(f"{name}  ({len(endings)} Slots, {par.roles[role].lexc})")
        for slot, found in endings.items():
            print(f"  {slot:28} {' | '.join(found) or '∅'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
