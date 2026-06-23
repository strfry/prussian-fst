#!/usr/bin/env python3
"""Corpus coverage for the HFST (lexd) pipeline: twanksta_articles tokenized."""

import re
import subprocess
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import unescape  # only for HTML entities

ARTICLES = Path("/tmp/corpus_articles/parsed/twanksta_articles")
ANALYSER = Path("build/hfst/analyser.hfst")
LENIENT = Path("build/hfst/lenient.hfst")

_RE_TAG = re.compile(r"<([A-Za-z0-9]+)>")
_RE_TOKEN = re.compile(
    r"[a-zA-ZāčēģīķļņōŗšūžĀČĒĢĪĶĻŅŌŖŠŪŽ]+(?:'[a-zA-ZāčēģīķļņōŗšūžĀČĒĢĪĶĻŅŌŖŠŪŽ]+)*"
)
# Remove entire markdown image lines, inline image references, bare URLs, markdown links
_RE_IMG_LINE = re.compile(r"^\s*\[!\[.*$", re.MULTILINE)
_RE_INLINE_IMG = re.compile(r"\[!\[.*?\]\(.*?\)\]\(.*?\)")
_RE_URL = re.compile(r"https?://\S+")
_RE_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_RE_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_RE_ITALIC = re.compile(r"\*([^*]+)\*")


def _to_plus(tags: str) -> str:
    return _RE_TAG.sub(r"+\1", tags)


def _clean_md(text: str) -> str:
    text = _RE_IMG_LINE.sub("", text)
    text = _RE_INLINE_IMG.sub("", text)
    text = _RE_URL.sub("", text)
    text = _RE_MD_LINK.sub(r"\1", text)
    text = _RE_BOLD.sub(r"\1", text)
    text = _RE_ITALIC.sub(r"\1", text)
    return text


def _tokenize(text: str) -> list[str]:
    cleaned = _clean_md(text)
    return _RE_TOKEN.findall(cleaned.lower())


def _batch_lookup(fst_path: str, forms: list[str]) -> set[str]:
    if not forms:
        return set()
    input_text = "\n".join(forms) + "\n"
    result = subprocess.run(
        ["hfst-lookup", fst_path],
        input=input_text,
        capture_output=True,
        text=True,
        timeout=120,
    )
    found = set()
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1] and "+?" not in parts[1]:
            found.add(parts[0].strip())
    return found


def main():
    all_tokens: list[str] = []
    uniq_tokens: set[str] = set()

    for md_file in sorted(ARTICLES.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        tokens = _tokenize(text)
        all_tokens.extend(tokens)
        uniq_tokens.update(tokens)

    total = len(all_tokens)
    uniq = list(uniq_tokens)
    print(
        f"Korpus: {len(list(ARTICLES.glob('*.md')))} Artikel, {total} Tokens, {len(uniq)} unique"
    )

    # Batch analyser
    print("··· hfst-lookup analyser …", end=" ", flush=True)
    analysed = _batch_lookup(str(ANALYSER), uniq)
    print(f"{len(analysed)}/{len(uniq)}")

    # Batch lenient for missing
    missing = [t for t in uniq if t not in analysed]
    ortho = set()
    if missing:
        print(
            f"··· hfst-lookup lenient ({len(missing)} missing) …", end=" ", flush=True
        )
        ortho = _batch_lookup(str(LENIENT), missing)
        print(f"{len(ortho)}/{len(missing)}")

    no_match = set(uniq) - analysed - ortho

    # Token-level counts (weighted by frequency)
    token_counts = Counter(all_tokens)
    tok_analysed = sum(c for t, c in token_counts.items() if t in analysed)
    tok_ortho = sum(c for t, c in token_counts.items() if t in ortho)
    tok_no = sum(c for t, c in token_counts.items() if t in no_match)

    print(f"\n=== HFST Corpus Coverage (Twanksta Articles) ===")
    print(f"  Type-level (unique tokens):")
    print(
        f"    Analyser: {len(analysed):>5}/{len(uniq)} ({100 * len(analysed) / len(uniq):.1f}%)"
    )
    print(
        f"    Lenient:  {len(ortho):>5}/{len(uniq)} ({100 * len(ortho) / len(uniq):.1f}%)"
    )
    print(
        f"    Unknown:  {len(no_match):>5}/{len(uniq)} ({100 * len(no_match) / len(uniq):.1f}%)"
    )
    print(
        f"    Total:    {len(analysed | ortho):>5}/{len(uniq)} ({100 * len(analysed | ortho) / len(uniq):.1f}%)"
    )

    tok_total = tok_analysed + tok_ortho + tok_no
    print(f"\n  Token-level (weighted by frequency):")
    print(
        f"    Analyser: {tok_analysed:>6}/{tok_total} ({100 * tok_analysed / tok_total:.1f}%)"
    )
    print(
        f"    Lenient:  {tok_ortho:>6}/{tok_total} ({100 * tok_ortho / tok_total:.1f}%)"
    )
    print(f"    Unknown:  {tok_no:>6}/{tok_total} ({100 * tok_no / tok_total:.1f}%)")
    print(
        f"    Coverage: {tok_analysed + tok_ortho:>6}/{tok_total} ({100 * (tok_analysed + tok_ortho) / tok_total:.1f}%)"
    )

    if no_match:
        print(f"\n  Unknown samples (top 30):")
        for t in sorted(no_match, key=lambda x: -token_counts[x])[:30]:
            print(f"    {t} (×{token_counts[t]})")

    # Compare with pyfoma dashboard
    try:
        dash = json.loads(
            (Path(__file__).resolve().parent / "data/derived/dashboard.json").read_text(
                encoding="utf-8"
            )
        )
        pyfoma = dash["kpis"]["corpus_coverage"]
        print(f"\n=== Comparison: pyfoma dashboard ===")
        print(f"  pyfoma: {pyfoma['pct']}% ({pyfoma['num']}/{pyfoma['den']})")
        print(
            f"  hfst:   {100 * (tok_analysed + tok_ortho) / tok_total:.1f}% ({tok_analysed + tok_ortho}/{tok_total})"
        )
    except Exception as e:
        print(f"  (dashboard comparison unavailable: {e})")


if __name__ == "__main__":
    import json

    main()
