#!/usr/bin/env python3
"""Parse verb paradigms (P71–144) from tabula.html into structured JSON.

Each verb entry contains:
  - paradigm: number (e.g. "71")
  - lemma: infinitive form (e.g. "īmtun")
  - inf: infinitive variants {"tun": "...", "twei": "..."}
  - present: {person: form} (persons: 1sg, 2sg, 3sg, 1pl, 2pl)
  - preterite: {person: form}
  - tempusgleich: bool (ps = pt, forms identical)
One entry per verb paradigm. Participle sections (pc) and abstract
sub-paradigms (leading dash) are skipped.
"""
import json
import re
from pathlib import Path

TABULA = Path("tabula.html")
OUT = Path("verb_paradigms.json")

# Person number → label map
# In the tabula: unmarked = 3sg, "1." = 1sg, "2." = 2sg, "6." = 1pl, "7." = 2pl
PERSON_LABEL = {"": "3sg", "1": "1sg", "2": "2sg", "6": "1pl", "7": "2pl"}
PERSON_ORDER = ["3sg", "2sg", "1sg", "1pl", "2pl"]


def load_tabula_verb_texts():
    """Extract raw text of each verb paradigm (71–144) from tabula.html.

    Skips participle continuations (pc) and abstract sub-paradigms
    (lemma starts with dash or uppercase K).
    Returns dict {num: text}.
    """
    html = TABULA.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.DOTALL):
        text = re.sub(r"<[^>]*>", "", m.group(1))
        text = text.replace("&nbsp;", " ").replace("&ndash;", "-")
        text = text.replace("\u2013", "-")
        text = " ".join(text.split())
        if len(text) < 3:
            continue
        mm = re.match(r"^(\d+[a-z]?)\s*(?:[mfn/]+)?\s*:?\s*(.*)", text)
        if not mm:
            continue
        num = mm.group(1)
        base_num = int(re.match(r"\d+", num).group())
        if not (71 <= base_num <= 144):
            continue
        rest = mm.group(2).strip()
        if not rest:
            continue
        # Verb entries must start with an infinitive form (ending in tun/twei)
        first_tok = rest.split()[0] if rest else ""
        if not first_tok.endswith("tun") and not first_tok.endswith("twei"):
            continue
        # Skip abstract templates (lemma starts with dash or uppercase K)
        if first_tok.startswith("-") or first_tok.startswith("K"):
            continue
        out[num] = rest
    return out


def parse_infinitive(text):
    """Parse infinitive from the beginning of a verb paradigm text.

    The infinitive is the first token(s) before 'ps' or 'pt' or 'ip'.
    Handles variant suffixes like /-twei, /-stwei, /twei (with or without dash).

    Examples:
      "īmtun/-twei ps ..."     → {"tun": "īmtun", "twei": "īmtwei"}
      "mestun/-stwei ps ..."   → {"tun": "mestun", "twei": "mestwei"}
      "madlītun/twei ps ..."   → {"tun": "madlītun", "twei": "madlītwei"}
      "klantītun/-ītwei ps ..."→ {"tun": "klantītun", "twei": "klantītwei"}
      "kaktwei ps ..."         → {"tun": None, "twei": "kaktwei"}

    Returns dict {"tun": str|None, "twei": str|None}.
    """
    m = re.search(r"\s+(?:(?:ps|pt|ip)(?:\s*/\s*(?:ps|pt))?)\s", text)
    end = m.start() if m else len(text)
    raw = text[:end].strip()

    parts = [p.strip() for p in raw.split("/")]
    main = parts[0]

    result = {}
    if main.endswith("tun"):
        result["tun"] = main
    elif main.endswith("twei"):
        result["twei"] = main

    for p in parts[1:]:
        bare_body = p.lstrip("-")
        if main.endswith("tun") and bare_body.endswith("twei"):
            result["twei"] = main[:-3] + "twei"
        elif main.endswith("twei") and bare_body.endswith("tun"):
            result["tun"] = main[:-4] + "tun"

    return {"tun": result.get("tun"), "twei": result.get("twei")}


def parse_persons(text):
    """Parse person-number forms from a section text.

    Stops when a new section marker (pt, ip) is encountered.
    Skips repeated ps markers within the section (for P114 style).

    Handles:
      Normal: "imma 2. imma 1. imma 6. immimai 7. immitei"
      Repeated-ps: "wīrst ps 2. wīrst ps 1. wīrst ps 6. wīrstmai ps 7. wīrstei"
      Simple: "kīrta" (all persons same)
      Partial: "līki 6. līkimai 7. līkitei" (only 3sg, 1pl, 2pl)

    Returns dict {"1sg": str, "2sg": str, ...} with only the persons found.
    """
    tokens = text.split()
    if not tokens:
        return {}

    result = {}
    i = 0

    # Collect form(s) before first person marker → 3sg
    first = []
    while i < len(tokens) and not re.match(r"\d+\.", tokens[i]):
        t = tokens[i]
        # Stop on new section marker
        if t in ("pt", "ip"):
            break
        # Skip repeated ps markers (P114)
        if t == "ps":
            i += 1
            continue
        first.append(t)
        i += 1
    if first:
        result["3sg"] = " ".join(first)

    # Process person-tagged forms: "2." "form" "1." "form" "6." "form" "7." "form"
    while i < len(tokens):
        t = tokens[i]
        # Stop on new section marker
        if t in ("pt", "ip"):
            break
        # Skip repeated ps markers (P114)
        if t == "ps":
            i += 1
            continue
        m = re.match(r"(\d+)\.", t)
        if m:
            label = PERSON_LABEL.get(m.group(1))
            i += 1
            if i < len(tokens) and not re.match(r"\d+\.", tokens[i]) and tokens[i] not in ("ps", "pt", "ip"):
                if label:
                    result[label] = tokens[i]
                i += 1
        else:
            i += 1

    # If ALL persons are the same, collapse to one form
    form_set = set(result.values())
    if len(form_set) == 1 and len(result) == 5:
        the_form = next(iter(form_set))
        result = {p: the_form for p in PERSON_ORDER}

    return result


def find_section(text, marker):
    """Find a section marker (ps/pt/ip) and return the text after it.

    Returns str or None if not found.
    Handles 'ps/pt' as a combined marker (= tempusgleich).
    """
    # Look for ps/pt combined marker first
    if marker == "ps" and "ps/pt" in text:
        idx = text.index("ps/pt") + 5
        return text[idx:].strip(), True  # True = tempusgleich
    pat = r"\b" + re.escape(marker) + r"\b(?!\s*/\s*pt)"
    m = re.search(pat, text)
    if m:
        return text[m.end():].strip(), False
    return None, False


def parse_one_verb(text):
    """Parse a single verb paradigm text.

    Returns dict {present, preterite, imperative, inf, tempusgleich} or None.
    """
    result = {}

    # Parse infinitive
    result["inf"] = parse_infinitive(text)

    # Determine lemma (first tun form, or twei form, or first token)
    lemma = result["inf"]["tun"] or result["inf"]["twei"] or text.split()[0]
    result["lemma"] = lemma

    # Find present section
    ps_text, tempusgleich = find_section(text, "ps")
    if ps_text:
        result["present"] = parse_persons(ps_text)
    else:
        result["present"] = {}

    # Find preterite section
    pt_text, _ = find_section(text, "pt")
    if tempusgleich or (pt_text and not ps_text):
        # If ps/pt was combined or pt exists without ps
        if tempusgleich:
            result["tempusgleich"] = True
            result["preterite"] = dict(result.get("present", {}))
        elif pt_text:
            result["preterite"] = parse_persons(pt_text)
    elif pt_text:
        result["preterite"] = parse_persons(pt_text)
    else:
        result["preterite"] = {}

    # Find imperative section
    ip_text, _ = find_section(text, "ip")
    if ip_text:
        result["imperative"] = parse_persons(ip_text)
    else:
        result["imperative"] = {}

    return result


def main():
    texts = load_tabula_verb_texts()
    print(f"Found {len(texts)} verb paradigm entries in tabula.html")

    entries = {}
    for num in sorted(texts, key=lambda n: (int(re.match(r"\d+", n).group()), n)):
        text = texts[num]
        parsed = parse_one_verb(text)
        if parsed:
            parsed["paradigm"] = num
            entries[num] = parsed

    # Write output
    output = {"paradigms": entries}
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written to {OUT} ({len(entries)} verb paradigms)")

    # Summary
    complete = sum(1 for e in entries.values() if len(e.get("present", {})) >= 5)
    simple = sum(1 for e in entries.values() if len(e.get("present", {})) == 1)
    tempusgleich = sum(1 for e in entries.values() if e.get("tempusgleich"))
    print(f"  Full paradigms: {complete}")
    print(f"  Simple (3sg only): {simple}")
    print(f"  Tempusgleich: {tempusgleich}")

    # Print sample
    if entries:
        first = sorted(entries.keys(), key=lambda n: (int(re.match(r"\d+", n).group()), n))[0]
        print(f"\nSample entry (P{first}):")
        print(json.dumps(entries[first], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
