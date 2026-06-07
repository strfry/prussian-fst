#!/usr/bin/env python3
"""Extract all paradigms from repaired tabula.html using regex (more robust)."""

import re
import json

print("Parsing tabula.html with regex...")
with open('tabula.html', encoding='utf-8') as f:
    html = f.read()

paradigms_by_num = {}

# Find all <p>...</p> tags
p_pattern = r'<p[^>]*>(.*?)</p>'
for p_match in re.finditer(p_pattern, html, re.DOTALL):
    p_content = p_match.group(1)

    # Remove HTML tags but keep text intact
    # This is key: remove span tags but don't add spaces
    text = re.sub(r'<[^>]*>', '', p_content)

    # Clean entities
    text = text.replace('&nbsp;', ' ').replace('&ndash;', '-').replace('–', '-')

    # Normalize multiple spaces to single space
    text = ' '.join(text.split())

    if not text or len(text) < 3:
        continue

    # Skip headers
    if any(x in text for x in ['TABLE', 'TABVLA', 'Abbreviationes', 'abbreviationes']):
        continue

    # Extract paradigm number
    match = re.match(r'^(\d+[a-z]?)\s+([mfn/]+)?\s*:?\s*(.*)', text)
    if not match:
        continue

    num_str = match.group(1)
    try:
        num = int(num_str.rstrip('a'))
        if not (1 <= num <= 144):
            continue
    except:
        continue

    if num_str not in paradigms_by_num:
        paradigms_by_num[num_str] = []
    paradigms_by_num[num_str].append(text)

sorted_nums = sorted(paradigms_by_num.keys(), key=lambda x: (int(re.match(r'\d+', x).group()), x))

# Classify
substantive = [n for n in sorted_nums if 32 <= int(re.match(r'\d+', n).group()) <= 67]
adjektive = [n for n in sorted_nums if 8 <= int(re.match(r'\d+', n).group()) <= 31]
partizip = [n for n in sorted_nums if 68 <= int(re.match(r'\d+', n).group()) <= 70]
pronomen = [n for n in sorted_nums if 1 <= int(re.match(r'\d+', n).group()) <= 7]
verben = [n for n in sorted_nums if int(re.match(r'\d+', n).group()) > 70]

print(f"\n✓ Extracted paradigms by type:")
print(f"  Substantiv: {len(substantive)}")
print(f"  Adjektiv/Demonstrativ: {len(adjektive)}")
print(f"  Partizip: {len(partizip)}")
print(f"  Pronomen: {len(pronomen)}")
print(f"  Verb: {len(verben)}")
print(f"  Total: {len(sorted_nums)}")

# Coverage
with open('wordlist.json') as f:
    wordlist = json.load(f)

wl_paradigms = set()
for entry in wordlist:
    if isinstance(entry, dict) and 'paradigm' in entry:
        p = str(entry['paradigm']).strip()
        if p and p != 'None':
            wl_paradigms.add(p)

extracted_set = set(sorted_nums)
missing = sorted(wl_paradigms - extracted_set)

print(f"\nCoverage: {len(extracted_set)}/{len(wl_paradigms)}")
if missing:
    print(f"Missing ({len(missing)}): {missing[:15]}...")

# Key samples
print(f"\nKey samples:")
for num in ['1', '32', '35a', '75', '107', '144']:
    if num in paradigms_by_num:
        text = paradigms_by_num[num][0]
        print(f"  {num}: {text[:100]}")

print(f"\n✓ Ready to generate CSVs")
