#!/usr/bin/env python3
"""
Book of Mormon Notes Quality & Integrity Checker (check_notes.py)

Performs comprehensive linting and consistency validation across all *_notes.md files:
1. TOC vs Body Heading Synchronization (count, title, anchor slugs)
2. Heading Hierarchy & Indentation Alignment (TOC indent level vs H3/H4)
3. Mis-nested Verse Headings (e.g. "1 Nephi 1:20" accidentally marked as H4 instead of H3)
4. Section Divider (---) Placement before H3 headings
5. Monolithic / Unformatted Paragraphs (> 800 chars without line breaks)
6. OCR Artifacts / Typo patterns
"""

import os
import sys
import glob
import re
from collections import defaultdict

def gh_slug(title):
    """Generate GitHub / standard markdown anchor slug."""
    s = title.strip().lower()
    s = re.sub(r'[^a-z0-9 _-]', '', s)
    s = s.replace(' ', '-')
    return s

def check_file(filepath):
    errors = []
    warnings = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- 1. Check Header & TOC Presence ---
    if not content.startswith('# '):
        errors.append("Missing H1 title at line 1")

    toc_match = re.search(r'^## Table of Contents.*$', content, re.MULTILINE)
    if not toc_match:
        errors.append("Missing '## Table of Contents' section")
        return errors, warnings

    toc_start = toc_match.end()
    sep_match = re.search(r'\n---\s*\n', content[toc_start:])
    if not sep_match:
        errors.append("Missing '---' separator after Table of Contents")
        return errors, warnings

    toc_raw = content[toc_start : toc_start + sep_match.start()]
    body_raw = content[toc_start + sep_match.end():]

    # --- 2. Parse TOC Items ---
    toc_items = []
    for line_idx, line in enumerate(toc_raw.splitlines(), start=1):
        if not line.strip():
            continue
        m = re.match(r'^(\s*)[-*+]\s+\[(.*?)\]\(#(.*?)\)', line)
        if m:
            indent_spaces = len(m.group(1))
            title = m.group(2).strip()
            slug = m.group(3).strip()
            # Indent level: 0 = root, 1 = child
            level = 1 if indent_spaces >= 2 else 0
            toc_items.append({
                'title': title,
                'slug': slug,
                'level': level,
                'line': line.strip()
            })
        else:
            warnings.append(f"TOC line not recognized as markdown link: '{line.strip()}'")

    # --- 3. Parse Body Headings ---
    body_sections = []
    body_lines = body_raw.splitlines()
    for idx, line in enumerate(body_lines):
        m = re.match(r'^(#{2,5})\s+(.*)', line)
        if m:
            h_hashes = m.group(1)
            h_title = m.group(2).strip()
            # Clean possible docsify attributes or trailing tags
            h_title_clean = re.sub(r'\s*\{.*?\}\s*$', '', h_title).strip()
            
            if h_title_clean.lower() == 'further reading':
                continue
            
            body_sections.append({
                'level': len(h_hashes), # 3 for H3, 4 for H4
                'title': h_title_clean,
                'slug': gh_slug(h_title_clean),
                'line_num': idx + 1,
                'prev_line': body_lines[idx - 1] if idx > 0 else '',
                'prev_prev_line': body_lines[idx - 2] if idx > 1 else ''
            })

    # --- 4. Cross-check TOC and Body Headings ---
    # A. Count comparison
    if len(toc_items) != len(body_sections):
        errors.append(f"Heading count mismatch: TOC has {len(toc_items)} entries, Body has {len(body_sections)} headings")

    # B. Pairwise comparison
    check_len = min(len(toc_items), len(body_sections))
    for i in range(check_len):
        t = toc_items[i]
        b = body_sections[i]
        
        # Title match
        if t['title'] != b['title']:
            # Check if minor difference (like smart quotes)
            norm_t = re.sub(r'[\u2018\u2019\u201c\u201d\']', '"', t['title'])
            norm_b = re.sub(r'[\u2018\u2019\u201c\u201d\']', '"', b['title'])
            if norm_t != norm_b:
                errors.append(f"Title mismatch at item {i+1}:\n    TOC:  '{t['title']}'\n    Body: '{b['title']}'")

        # Hierarchy level match: TOC level 0 -> H3, TOC level 1 -> H4
        expected_body_level = 3 if t['level'] == 0 else 4
        if b['level'] != expected_body_level:
            errors.append(
                f"Level mismatch for '{t['title'][:35]}': TOC indent={t['level']} (expected H{expected_body_level}) vs Body H{b['level']}"
            )

    # --- 5. Check for Mis-nested Verse Headings in H4 ---
    # Patterns like "1 Nephi 1:20", "2 Nephi 2:5", "Mosiah 3:19"
    verse_ref_pattern = re.compile(r'\b\d?\s*[A-Za-z]+\s+\d+:\d+\b')
    for b in body_sections:
        if b['level'] >= 4 and verse_ref_pattern.search(b['title']):
            warnings.append(
                f"Suspicious nested verse heading (marked as H{b['level']}): '{b['title']}'"
            )

    # --- 6. Check Separator before H3 Headings ---
    # In body_raw, each H3 heading should be preceded by '---'
    for idx, b in enumerate(body_sections):
        if b['level'] == 3 and idx > 0:
            # Check if there is a '---' line within the preceding 3 lines
            prev_lines = [b['prev_line'].strip(), b['prev_prev_line'].strip()]
            if '---' not in prev_lines:
                warnings.append(f"Missing '---' divider before H3 section: '{b['title'][:35]}'")

    # --- 7. Check for Monolithic Paragraphs ---
    paragraphs = [p.strip() for p in body_raw.split('\n\n') if p.strip()]
    for p in paragraphs:
        if p.startswith('#') or p.startswith('- ') or p.startswith('|') or p.startswith('---'):
            continue
        if len(p) > 1200:
            warnings.append(f"Monolithic unformatted paragraph detected ({len(p)} chars): '{p[:60]}...'")

    # --- 8. Check for Common OCR / Scanning Typos ---
    ocr_typos = [
        r'\btop rosper\b', r'\bpert ains\b', r'\bof fers\b', r'\bhes aid\b',
        r'\btoZe dekiah\b', r'\bapp eared\b', r'\bnot s ee\b', r'\bnots ee\b',
        r'\b1stand\b'
    ]
    for typo in ocr_typos:
        m = re.search(typo, body_raw, re.IGNORECASE)
        if m:
            warnings.append(f"Possible OCR artifact: '{m.group(0)}'")

    return errors, warnings

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check quality and integrity of Book of Mormon notes files.")
    parser.add_argument("pattern", nargs="?", default="*/*_notes.md", help="Glob pattern for notes files (default: */*_notes.md)")
    parser.add_argument("--errors-only", action="store_true", help="Only show files with errors (hide warnings)")
    parser.add_argument("--summary-only", action="store_true", help="Only output the summary counts")
    args = parser.parse_args()

    files = sorted(glob.glob(args.pattern))
    if not files:
        print(f"No files matching '{args.pattern}' found.")
        sys.exit(1)

    total_errors = 0
    total_warnings = 0
    files_with_issues = 0
    warning_categories = defaultdict(int)

    results = []

    for f in files:
        errs, warns = check_file(f)
        if errs or warns:
            files_with_issues += 1
            total_errors += len(errs)
            total_warnings += len(warns)
            for w in warns:
                if 'Monolithic unformatted paragraph' in w:
                    cat = 'Monolithic paragraph (> 1200 chars)'
                elif 'Missing \'---\'' in w:
                    cat = 'Missing \'---\' section divider'
                elif 'Suspicious nested verse' in w:
                    cat = 'Suspicious nested verse in H4'
                elif 'Possible OCR artifact' in w:
                    cat = 'Possible OCR artifact'
                else:
                    cat = w.split(':')[0] if ':' in w else w[:30]
                warning_categories[cat] += 1
            results.append((f, errs, warns))

    if not args.summary_only:
        for f, errs, warns in results:
            if args.errors_only and not errs:
                continue
            print(f"File: {f}")
            for e in errs:
                print(f"  [ERROR] {e}")
            if not args.errors_only:
                for w in warns:
                    print(f"  [WARN]  {w}")
            print()

    print("=" * 60)
    print(f"Scan complete: {len(files)} files checked.")
    print(f"Files with issues: {files_with_issues}")
    print(f"Total Errors:      {total_errors}")
    print(f"Total Warnings:    {total_warnings}")
    if warning_categories:
        print("\nWarning Breakdown:")
        for cat, cnt in sorted(warning_categories.items(), key=lambda x: -x[1]):
            print(f"  - {cat}: {cnt}")
    print("=" * 60)

    if total_errors > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
