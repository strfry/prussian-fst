#!/usr/bin/env python3
"""Clean nom_paradigms.lexc for Twanksta-only build.

Two-pass per LEXICON block:
  Pass 1: collect all cell tags that have a @P.standard.twanksta@ form
  Pass 2: emit lines; for cells with a Twanksta form, skip the unflagged
           (Prusaspira) variant and keep only the Twanksta one (without flag).
"""

import re

def cell_tag_from_line(line):
    m = re.search(r'((?:\+\w+)+):', line.strip())
    return m.group(1) if m else None

def clean_nom_paradigms():
    path = "nom_paradigms.lexc"
    text = open(path).read()
    lines = text.split("\n")
    out = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("LEXICON "):
            # Collect all lines belonging to this LEXICON block
            block_lines = [line]
            i += 1
            while i < len(lines):
                ls = lines[i].strip()
                if ls.startswith("LEXICON ") or (ls == "" and i+1 < len(lines) and lines[i+1].strip().startswith("LEXICON ")):
                    break
                if ls == "" and i+1 < len(lines) and lines[i+1].strip().startswith("!"):
                    # comment before next lexicon: keep blank
                    block_lines.append(lines[i])
                    i += 1
                    # also include the comment
                    if i < len(lines) and lines[i].strip().startswith("!"):
                        block_lines.append(lines[i])
                        i += 1
                    continue
                if ls == "":
                    block_lines.append(lines[i])
                    i += 1
                    if i >= len(lines) or lines[i].strip().startswith("LEXICON "):
                        break
                    continue
                block_lines.append(lines[i])
                i += 1

            # Pass 1: find cells with Twanksta forms
            twanksta_cells = set()
            for bl in block_lines:
                if "@P.standard.twanksta@" in bl:
                    cleaned = bl.replace("@P.standard.twanksta@", "")
                    tag = cell_tag_from_line(cleaned)
                    if tag:
                        twanksta_cells.add(tag)

            # Pass 2: emit
            for bl in block_lines:
                if bl.strip().startswith("LEXICON ") or bl.strip().startswith("!") or bl.strip() == "":
                    out.append(bl)
                    continue
                if "@P.standard.prusaspira@" in bl:
                    continue  # skip prusaspira-specific
                if "@P.standard.twanksta@" in bl:
                    out.append(bl.replace("@P.standard.twanksta@", ""))
                else:
                    tag = cell_tag_from_line(bl)
                    if tag and tag in twanksta_cells:
                        continue  # skip Prusaspira form, Twanksta taken
                    out.append(bl)
        else:
            out.append(line)
            i += 1

    open(path, "w").write("\n".join(out))
    print(f"Cleaned {path}: {len(lines)} -> {len(out)} lines")

def clean_symbols():
    path = "symbols.lexc"
    text = open(path).read()
    text = text.replace("  @P.standard.prusaspira@\n", "")
    text = text.replace("  @P.standard.twanksta@\n", "")
    open(path, "w").write(text)
    print(f"Cleaned {path}")

if __name__ == "__main__":
    clean_nom_paradigms()
    clean_symbols()
