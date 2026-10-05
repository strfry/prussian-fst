"""Build-Zeit-Backen der datenfreien Atom-FSTs (gen/*.lexc → build/gen-*.hfstol).

Je (pos, Twanksta-Paradigma, Rolle) entsteht genau ein Atom:

    gen/<family>.lexc
        --(nur LEXICON Root ersetzt: <Infl-Lexikone> ;)-->  build/gen-atom-<name>.lexc
        --hfst.compile_lexc_file-->                          tag ↦ Endung+Marker
    hfst.regex("[<STEM_ALPHABET>]*")                        Stamm-Kopierer
        --concatenate (PRODUKT: Stamm bleibt auf beiden Bändern)-->
    full = Kopierer ++ Atom .o. gen-accent.hfst --minimize--> --convert(OL)-->
        build/gen-<family>-<paradigm>[-<role>].hfstol

Also ``Stamm + Tag → Oberfläche``, z. B. ``dumsl+Sg+Gen → dumslis``:
``concatenate`` ist das Band-Produkt (der Stamm fließt durch), ``compose`` die
anschließende Regelkomposition (Akzent/Makron/Gemination). Ein Komponieren statt
Produktieren liefert nichts — die Komposition verlangt Gleichheit der ganzen
Zwischenstrings, ein reiner Stamm-Kopierer kann sie nicht herstellen.

Genau ein lexc-Compile pro Prozess: ``hfst.compile_lexc_file`` liefert ab dem
zweiten Aufruf im selben Prozess ein leeres Transducer. Deshalb ein Prozess je
Atom; ``--all`` startet sie als Subprozesse.

Der Build ist die einzige Stelle, die die Grammatik anfasst — ``gen/*.lexc`` und
``gen/accent.regex`` bleiben die einzige Quelle, ``gen/generator.py`` liest zur
Laufzeit nur die fertigen Atome.

    uv run python gen/atom_fst.py --list
    uv run python gen/atom_fst.py noun 53
    uv run python gen/atom_fst.py verb 85 partpres
    uv run python gen/atom_fst.py --all -j8
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generator import (  # noqa: E402
    ATOM_DIR, ROOT as GEN_ROOT, STEM_ALPHABET, atom_path, atom_targets,
    paradigm_spec, resolve_paradigm, slot_tag,
)

import hfst  # noqa: E402

OL = hfst.ImplementationType.HFST_OL_TYPE
ACCENT = ROOT / "build" / "gen-accent.hfst"

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


def build_atom(pos: str, paradigm: str, role: str, verbose: bool = True,
               lemma: str = "") -> Path:
    """Ein Atom backen. Genau ein lexc-Compile — danach ist der Prozess verbraucht.

    ``lemma`` wird nur zur Variantenauflösung gebraucht (Verb 87a/87b); ohne
    Lemma muss die konkrete Paradigmennummer genannt werden.
    """
    par = paradigm_spec(pos, paradigm, lemma)
    spec = par.roles[role]
    name = atom_path(pos, paradigm, role, lemma).name
    ATOM_DIR.mkdir(parents=True, exist_ok=True)

    source = GEN_ROOT / spec.lexc
    lexc_path = ATOM_DIR / f"gen-atom-{Path(name).stem}.lexc"
    lexc_path.write_text(rewrite_root(source.read_text(), spec.atoms))

    atom = hfst.compile_lexc_file(str(lexc_path))
    if atom is None or atom.number_of_states() == 0:
        raise SystemExit(f"{name}: lexc-Compile leer ({lexc_path})")

    full = hfst.HfstTransducer(hfst.regex(copier_regex()))
    full.concatenate(atom)
    if not ACCENT.exists():
        raise SystemExit(f"{ACCENT} fehlt — bauen mit: make gen-accent.hfst")
    full.compose(hfst.HfstInputStream(str(ACCENT)).read())
    full.minimize()
    _check_alphabet(atom, name)

    probe = "Teststam"
    empty = [slot for slot in spec.slots if not full.lookup(probe + slot_tag(slot))]
    if empty:
        raise SystemExit(
            f"{name}: {len(empty)} Slots ohne Pfad (Atom {spec.atoms} in "
            f"{spec.lexc}): {', '.join(empty[:6])}{' …' if len(empty) > 6 else ''}")

    full.convert(OL)                 # Zyklus (Kopierer-Stern) stört OL nicht
    out = atom_path(pos, paradigm, role, lemma)
    stream = hfst.HfstOutputStream(filename=str(out), type=OL)
    stream.write(full)
    stream.flush()
    stream.close()
    if verbose:
        print(f"{out.name:44} {len(spec.slots):2} Slots  {spec.atoms}"
              f"  <- {spec.lexc}")
    return out


def _one(args: tuple[str, str, str]) -> str:
    """Ein Atom im EIGENEN Prozess backen (ein lexc-Compile pro Prozess!)."""
    pos, paradigm, role = args
    done = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), pos, paradigm, role],
        capture_output=True, text=True)
    if done.returncode:
        detail = (done.stderr or done.stdout).strip().splitlines()
        return f"FEHLER {pos}/{paradigm}/{role}: " + (detail[-1] if detail else "?")
    sys.stdout.write(done.stdout)
    return ""


def build_all(jobs: int) -> int:
    targets = [(pos, paradigm, role)
               for pos, paradigm, role, _path in atom_targets()]
    targets.sort(key=lambda t: (t[0], len(t[1]), t[1], t[2]))
    errors = 0
    with ThreadPoolExecutor(max_workers=max(jobs, 1)) as pool:
        for error in pool.map(_one, targets):
            if error:
                errors += 1
                print(error, file=sys.stderr)
    print(f"{len(targets) - errors}/{len(targets)} Atome gebaut in {ATOM_DIR}")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pos", nargs="?", choices=["noun", "adj", "verb"])
    parser.add_argument("paradigm", nargs="?")
    parser.add_argument("role", nargs="?")
    parser.add_argument("--lemma", default="",
                        help="Lemma zur Variantenauflösung (Verb 87a/87b)")
    parser.add_argument("--list", action="store_true",
                        help="alle zu bauenden Atome auflisten")
    parser.add_argument("--all", action="store_true", help="alle Atome backen")
    parser.add_argument("-j", "--jobs", type=int, default=max(os.cpu_count() or 1, 1))
    parser.add_argument("--print-regex", action="store_true",
                        help="Kopierer-Ausdruck ausgeben")
    args = parser.parse_args(argv)

    if args.print_regex:
        print(copier_regex())
        return 0
    if args.all:
        return build_all(args.jobs)
    if args.list:
        for pos, paradigm, role, path in atom_targets():
            print(f"{pos:5} {paradigm:5} {role:9} {path.name}")
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
    build_atom(args.pos, args.paradigm, role, lemma=args.lemma)
    return 0


if __name__ == "__main__":
    sys.exit(main())
