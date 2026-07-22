"""FST-Build über das python-``hfst``-Modul statt der hfst-CLI-Tools.

Ersetzt die früher im Makefile aufgerufenen Kommandozeilen-Werkzeuge
(hfst-lexc, hfst-xfst, hfst-compose, hfst-minimize, hfst-invert,
hfst-fst2fst) durch die entsprechenden Aufrufe der python-Bindings.  So
hängt der Build nur noch am pip-Paket ``hfst`` (bereits Projekt-Abhängigkeit)
und nicht mehr an einer separat installierten hfst-Toolchain.

Nicht zu verwechseln mit ``pyhfst`` (fst_lookup.py): pyhfst ist die reine
Lookup-Runtime, ``hfst`` das volle Build-Toolkit.

Subkommandos (1:1 zu den bisherigen Makefile-Rezepten):

  lexc    IN OUT              — hfst-lexc:   .lexc  → .fst
  xfst    SCRIPT              — hfst-xfst -F: xfst-Skript ausführen
                                (das Skript schreibt seinen Stack selbst)
  compose OUT IN...           — hfst-compose | hfst-minimize:
                                IN[0] .o. IN[1] .o. … , minimiert → OUT
  hfstol  IN OUT              — hfst-invert | hfst-fst2fst:
                                invertiert (surface→analysis) und in das
                                optimized-lookup-Format (unweighted) → OUT
"""

from __future__ import annotations

import argparse
from pathlib import Path

import hfst

# optimized-lookup, unweighted — dasselbe Format wie
# `hfst-fst2fst -f optimized-lookup-unweighted`, das pyhfst zur Laufzeit liest.
OL_TYPE = hfst.ImplementationType.HFST_OL_TYPE


def _write(tr: hfst.HfstTransducer, path: str, type=None) -> None:
    out = hfst.HfstOutputStream(filename=path,
                                type=type if type is not None else tr.get_type())
    out.write(tr)
    out.flush()
    out.close()


def _read(path: str) -> hfst.HfstTransducer:
    return hfst.HfstInputStream(path).read()


def cmd_lexc(args: argparse.Namespace) -> None:
    """hfst-lexc: lexc-Quelle zu einem Transducer kompilieren."""
    tr = hfst.compile_lexc_file(args.input)
    _write(tr, args.output)


def cmd_xfst(args: argparse.Namespace) -> None:
    """hfst-xfst -F: xfst-Skript ausführen (schreibt seinen Stack per `save`)."""
    hfst.compile_xfst_file(args.script)


def cmd_compose(args: argparse.Namespace) -> None:
    """hfst-compose | hfst-minimize: Kaskade komponieren und minimieren."""
    result = _read(args.inputs[0])
    for path in args.inputs[1:]:
        result.compose(_read(path))
    result.minimize()
    _write(result, args.output)


def cmd_hfstol(args: argparse.Namespace) -> None:
    """hfst-invert | hfst-fst2fst: invertieren und als optimized-lookup schreiben.

    build/*.fst bildet analysis → surface ab; für den Lookup brauchen wir
    surface → analysis, daher vor der Format-Konvertierung invertieren.
    """
    tr = _read(args.input)
    tr.invert()
    tr.convert(OL_TYPE)
    _write(tr, args.output, type=OL_TYPE)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("lexc", help="lexc-Quelle → .fst")
    p.add_argument("input")
    p.add_argument("output")
    p.set_defaults(func=cmd_lexc)

    p = sub.add_parser("xfst", help="xfst-Skript ausführen")
    p.add_argument("script")
    p.set_defaults(func=cmd_xfst)

    p = sub.add_parser("compose", help="Transducer komponieren + minimieren")
    p.add_argument("output")
    p.add_argument("inputs", nargs="+")
    p.set_defaults(func=cmd_compose)

    p = sub.add_parser("hfstol", help="invertieren → optimized-lookup")
    p.add_argument("input")
    p.add_argument("output")
    p.set_defaults(func=cmd_hfstol)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
