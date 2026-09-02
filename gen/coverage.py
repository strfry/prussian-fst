"""Coverage-Report: generativer u-Stamm-FST (gen/nouns.lexc) vs. Twanksta-Vollformen.

Liest die Referenzformen für die im generativen FST gepflegten Lexeme direkt
aus lexc/nouns.lexc (Vollform-Lexikon) und vergleicht sie mit dem, was
build/gen-nouns.gen.hfstol für dieselben Analysen erzeugt.

    uv run python gen/coverage.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from prussian_fst.fst_lookup import glookup_batch  # noqa: E402

CASES = ["Nom", "Gen", "Dat", "Akk"]
NUMBERS = ["Sg", "Pl"]

# Lexeme, die gen/nouns.lexc kennt (muss synchron gehalten werden).
LEXEMES = {
    "bebrus": "Fixed",
    "kāzus": "Fixed",
    "Jēzus": "Fixed",
    "Kūbus": "Fixed",
    "sparrjus": "Fixed",
    "dāngs": "Mobile",
    "krūmsts": "Mobile",
    "kōmbus": "Mobile",
}

ENTRY_RE = re.compile(
    r"^\s*(\S+)\+N\+(Sg|Pl)\+(Nom|Gen|Dat|Akk)\+Masc:(\S+)\s*#\s*;"
)


def load_reference(nouns_lexc: Path) -> dict[str, dict[str, str]]:
    """lemma -> {'Sg+Nom': form, ...} aus lexc/nouns.lexc."""
    ref: dict[str, dict[str, str]] = defaultdict(dict)
    for line in nouns_lexc.read_text().splitlines():
        m = ENTRY_RE.match(line)
        if not m:
            continue
        lemma, number, case, form = m.groups()
        if lemma in LEXEMES:
            ref[lemma][f"{number}+{case}"] = form
    return ref


def main() -> None:
    reference = load_reference(ROOT / "lexc" / "nouns.lexc")

    queries = [
        f"{lemma}+N+UStem+{number}+{case}+Masc"
        for lemma in LEXEMES
        for number in NUMBERS
        for case in CASES
    ]
    generated = glookup_batch(queries, ROOT / "build" / "gen-nouns.gen.hfstol")

    total = matched = 0
    mismatches: list[str] = []
    for lemma, accent_class in LEXEMES.items():
        for number in NUMBERS:
            for case in CASES:
                total += 1
                query = f"{lemma}+N+UStem+{number}+{case}+Masc"
                got = set(generated.get(query, []))
                want = reference.get(lemma, {}).get(f"{number}+{case}")
                if want is None:
                    mismatches.append(f"  {lemma} [{accent_class}] {number}+{case}: "
                                       f"keine Twanksta-Referenzform gefunden")
                    continue
                if want in got:
                    matched += 1
                else:
                    mismatches.append(
                        f"  {lemma} [{accent_class}] {number}+{case}: "
                        f"erwartet {want!r}, generiert {sorted(got) or '(nichts)'}"
                    )

    pct = 100 * matched / total if total else 0.0
    print(f"Coverage: {matched}/{total} ({pct:.1f}%)\n")
    if mismatches:
        print("Abweichungen:")
        print("\n".join(mismatches))


if __name__ == "__main__":
    main()
