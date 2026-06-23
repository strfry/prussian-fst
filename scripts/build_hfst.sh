#!/usr/bin/env bash
# HFST-nativer Analysatorzweig: venv provisionieren, bauen, validieren.
#
# python-hfst hat (Stand 2026-06) kein cp313-Wheel; das Projekt verlangt
# aber Python >=3.13 (pyfoma-Zweig). Daher lebt der HFST-Zweig in einem
# separaten, uv-verwalteten Python-3.12-venv. Dieses Skript legt es an,
# installiert hfst, baut analyser/lenient und prüft sie gegen den Goldstandard.
#
# Voraussetzungen: uv, Internet (PyPI), und die System-CLIs `lexd` +
# `hfst-txt2fst` (Debian/Ubuntu: `apt-get install lexd hfst`). Für den vollen
# Build (mit Wortliste) zusätzlich data/external/twanksta_entries.json
# (s. README »Setup«); ohne diese Datei bitte mit --gold-only aufrufen.
#
# Aufruf:  scripts/build_hfst.sh [--gold-only | --sample N]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${HFST_VENV:-$ROOT/.venv-hfst}"
cd "$ROOT"

for cli in lexd hfst-txt2fst; do
  if ! command -v "$cli" >/dev/null 2>&1; then
    echo "FEHLER: '$cli' nicht gefunden — bitte installieren " \
         "(Debian/Ubuntu: apt-get install lexd hfst)." >&2
    exit 1
  fi
done

if [ ! -x "$VENV/bin/python" ]; then
  echo ">> Lege HFST-venv an (Python 3.12) …"
  uv venv --python 3.12 "$VENV"
  uv pip install --python "$VENV/bin/python" hfst
fi

echo ">> Baue HFST-Analysator …"
PYTHONPATH=src "$VENV/bin/python" -m prussian.fst.hfst.lexd_build "$@"

echo ">> Validiere gegen Goldstandard …"
PYTHONPATH=src "$VENV/bin/python" -m prussian.fst.hfst.check
