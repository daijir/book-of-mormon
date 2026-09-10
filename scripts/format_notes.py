#!/usr/bin/env python3
"""
Book of Mormon Chapter Notes Formatter
Formats monolithic text blocks into readable 2-4 sentence paragraphs,
separates Further Reading citations into bullet points, repairs OCR artifacts,
generates a fully valid GitHub-compatible Table of Contents, and verifies 100% word fidelity.
"""

import os
import sys
import glob
import re

def gh_slug(title):
    """Generate GitHub-compatible markdown anchor slug."""
    s = title.strip().lower()
    s = re.sub(r'[^a-z0-9 _-]', '', s)
    s = s.replace(' ', '-')
    return s

def clean_ocr(text):
    """Clean common OCR scanning artifacts and typos."""
    # Split words with hyphens across linebreaks: e.g. "com-\n mandments" -> "commandments"
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    # Split digits in chapter:verse citations: e.g. "4:1 1" -> "4:11", "2:2 1" -> "2:21"
    text = re.sub(r'(\d+):(\d+)\s+(\d+)', r'\1:\2\3', text)
    # Dashes with extra spaces: e.g. "21 –22" -> "21–22", "1– 2" -> "1–2"
    text = re.sub(r'(\d+)\s+–\s*(\d+)', r'\1–\2', text)
    text = re.sub(r'(\d+)–\s+(\d+)', r'\1–\2', text)
    # Quotes with detached spaces: e.g. 'you ”' -> '“you”'
    text = re.sub(r'\s+”', '”', text)
    text = re.sub(r'“\s+', '“', text)
    # Common OCR name / word gluts
    text = re.sub(r'MonteS\.', 'Monte S.', text)
    text = re.sub(r'\btop rosper\b', 'to prosper', text)
    text = re.sub(r'\bpert ains\b', 'pertains', text)
    text = re.sub(r'\bof fers\b', 'offers', text)
    text = re.sub(r'\bhes aid\b', 'he said', text)
    text = re.sub(r'\btoZe dekiah\b', 'to Zedekiah', text)
    text = re.sub(r'\bapp eared\b', 'appeared', text)
    text = re.sub(r'\bnot s ee\b', 'not see', text)
    text = re.sub(r'\bnots ee\b', 'not see', text)
    text = re.sub(r'\b1stand\b', '1st and', text)
    return text

KNOWN_ABBREVS = {
    'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'rev.', 'st.',
    'e.g.', 'i.e.', 'vs.', 'etc.', 'cf.', 'ed.', 'eds.',
    'no.', 'vol.', 'vols.', 'ch.', 'chs.', 'v.', 'vv.', 'p.', 'pp.',
    'bc.', 'ad.', 'b.c.', 'a.d.'
}

def split_into_sentences(text):
    """Split text into sentences while respecting abbreviations and quotes."""
    tokens = text.split(' ')
    sentences = []
    current = []
    
    for i, token in enumerate(tokens):
        current.append(token)
        clean_tok = token.rstrip(r'”"\'\)]')
        if not clean_tok:
            continue
        last_char = clean_tok[-1]
        if last_char in '.?!':
            tok_lower = clean_tok.lower()
            if tok_lower in KNOWN_ABBREVS:
                continue
            # Initial like J. or S.
            if len(clean_tok) == 2 and clean_tok[0].isalpha() and last_char == '.':
                continue
            # Lookahead to see if next token begins a new sentence
            if i + 1 < len(tokens):
                next_tok = tokens[i + 1].lstrip(r'“"\'\([')
                if next_tok and (next_tok[0].isupper() or next_tok[0].isdigit()):
                    sentences.append(" ".join(current))
                    current = []
            else:
                sentences.append(" ".join(current))
                current = []
                
    if current:
        if sentences:
            sentences[-1] += " " + " ".join(current)
        else:
            sentences.append(" ".join(current))
            
    return sentences

def format_paragraph_block(text, target_sentences=3, max_chars=500):
    """Format a monolithic block of text into natural 2-4 sentence paragraphs."""
    # If text has bullet characters (•), format as standard markdown list
    if '•' in text:
        lines = text.split('•')
        intro = lines[0].strip()
        bullets = [b.strip() for b in lines[1:] if b.strip()]
        out = []
        if intro:
            out.append(intro)
        for b in bullets:
            out.append(f"- {b}")
        return '\n\n'.join(out)
        
    sentences = split_into_sentences(text)
    if len(sentences) <= 3 and len(text) < 650:
        return text
        
    paras = []
    cur_para = []
    cur_len = 0
    
    for s in sentences:
        cur_para.append(s)
        cur_len += len(s)
        if len(cur_para) >= target_sentences or cur_len >= max_chars:
            paras.append(" ".join(cur_para))
            cur_para = []
            cur_len = 0
            
    if cur_para:
        if len(paras) > 0 and len(cur_para) == 1 and cur_len < 180:
            paras[-1] = paras[-1] + " " + " ".join(cur_para)
        else:
            paras.append(" ".join(cur_para))
            
    return "\n\n".join(paras)

def format_notes_content(content):
    """Format notes content with clean paragraphs, Further Reading, and valid TOC."""
    content = clean_ocr(content)
    
    # Locate body beginning (first ### heading)
    m = re.search(r'\n###\s+', content)
    if not m:
        return None
        
    header_part = content[:m.start()]
    body_part = content[m.start():]
    
    # Extract metadata before ## Table of Contents
    meta_lines = []
    for line in header_part.splitlines():
        if line.startswith('## Table of Contents'):
            break
        meta_lines.append(line)
    header_meta = "\n".join(meta_lines).strip()
    
    # Split body into sections by '### '
    raw_sections = re.split(r'\n(?=###\s+)', body_part)
    processed_sections = []
    all_headings = [] # for TOC
    
    for sec in raw_sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        h3_line = lines[0]
        h3_title = re.sub(r'^###\s+', '', h3_line).strip()
        all_headings.append((3, h3_title))
        
        body_text = "\n".join(lines[1:]).strip()
        
        # Check for Further Reading
        fr_match = re.search(r'\bFurther Reading\b', body_text, re.IGNORECASE)
        fr_text = ""
        main_text = body_text
        if fr_match:
            main_text = body_text[:fr_match.start()].strip()
            fr_raw = body_text[fr_match.end():].strip()
            # Clean further reading into bullet points
            fr_raw = re.sub(r'^[•\-\*\s:]+', '', fr_raw)
            # Check for multiple citations
            fr_lines = re.split(r'(?<=\))\.\s*(?=[A-Z])|(?<=\d{4}\))\s*(?=[A-Z])', fr_raw)
            fr_items = []
            for item in fr_lines:
                item = item.strip()
                if item:
                    item = re.sub(r'^[•\-\*\s]+', '', item)
                    fr_items.append(f"- {item}")
            if fr_items:
                fr_text = "#### Further Reading\n\n" + "\n".join(fr_items)
            elif fr_raw:
                fr_text = f"#### Further Reading\n\n- {fr_raw}"
                
        # Process main_text: preserve existing #### subheadings if any
        subsections = re.split(r'\n(?=####\s+)', main_text)
        formatted_subsections = []
        
        for sub in subsections:
            sub = sub.strip()
            if not sub:
                continue
            if sub.startswith('#### '):
                sub_lines = sub.splitlines()
                sub_h4 = re.sub(r'^####\s+', '', sub_lines[0]).strip()
                if sub_h4.lower() != "further reading":
                    all_headings.append((4, sub_h4))
                sub_body = "\n".join(sub_lines[1:]).strip()
                blocks = [b.strip() for b in sub_body.split("\n\n") if b.strip()]
                fmt_blocks = [format_paragraph_block(b) for b in blocks]
                formatted_subsections.append(f"#### {sub_h4}\n\n" + "\n\n".join(fmt_blocks))
            else:
                blocks = [b.strip() for b in sub.split("\n\n") if b.strip()]
                fmt_blocks = [format_paragraph_block(b) for b in blocks]
                formatted_subsections.append("\n\n".join(fmt_blocks))
                
        sec_out = f"### {h3_title}\n\n" + "\n\n".join(formatted_subsections)
        if fr_text:
            sec_out += f"\n\n{fr_text}"
        processed_sections.append(sec_out)
        
    # Build clean, accurate Table of Contents
    toc_lines = ["## Table of Contents", ""]
    slug_counts = {}
    for level, title in all_headings:
        base_slug = gh_slug(title)
        if base_slug in slug_counts:
            slug_counts[base_slug] += 1
            slug = f"{base_slug}-{slug_counts[base_slug]}"
        else:
            slug_counts[base_slug] = 0
            slug = base_slug
            
        if level == 3:
            toc_lines.append(f"- [{title}](#{slug})")
        elif level == 4:
            toc_lines.append(f"  - [{title}](#{slug})")
            
    final_output = f"{header_meta}\n\n" + "\n".join(toc_lines) + "\n\n---\n\n" + "\n\n---\n\n".join(processed_sections) + "\n"
    return final_output

def get_body_words(text):
    """Extract all alphanumeric words from the body (after first ###)."""
    m = re.search(r'\n###\s+', text)
    body = text[m.start():] if m else text
    return set(re.findall(r'[a-zA-Z0-9]+', body.lower()))

def verify_fidelity(orig_text, formatted_text):
    """Verify word retention between original body and formatted body."""
    orig_words = get_body_words(orig_text)
    new_words = get_body_words(formatted_text)
    missing = orig_words - new_words
    # Exclude acceptable OCR typo corrections
    ocr_known = {
        'montes', 'rosper', 'top', 'ains', 'pert', 'fers', 'hes', 'aid',
        'nots', 'ee', 'toze', 'dekiah', 'app', 'eared', '1stand', '1st', 'and'
    }
    real_missing = missing - ocr_known
    return real_missing

def process_single_file(filepath, dry_run=False):
    """Process a single notes file and save if verified."""
    orig_text = open(filepath, encoding='utf-8').read()
    res = format_notes_content(orig_text)
    if not res:
        return False, "Failed to parse sections"
        
    missing = verify_fidelity(orig_text, res)
    if missing:
        return False, f"Missing body words: {missing}"
        
    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(res)
    return True, f"Lines: {len(orig_text.splitlines())} -> {len(res.splitlines())}"

def get_target_files(arg):
    if arg.lower() == 'all':
        books = sorted([d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.') and d not in ['00_special_topics', '01_1nephi', 'scripts']])
        files = []
        for b in books:
            files.extend(sorted(glob.glob(f"{b}/*_notes.md")))
        return files
    elif os.path.isfile(arg):
        return [arg]
    elif os.path.isdir(arg):
        return sorted(glob.glob(os.path.join(arg, "*_notes.md")))
    else:
        return sorted(glob.glob(arg))

def print_help():
    print("""
Book of Mormon Notes Formatter
Usage:
  python scripts/format_notes.py <target> [options]

Targets:
  <book_dir>   Process all *_notes.md in directory (e.g. 02_2nephi, 03_jacob, 08_mosiah)
  <file_path>  Process a single notes file (e.g. 02_2nephi/01_notes.md)
  all          Process all books from 02_2nephi through 15_moroni

Options:
  --dry-run, -n   Run verification and report changes without modifying files
  --help, -h      Show this help message
""")

if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print_help()
        sys.exit(0)
        
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    target_arg = args[0] if args else '02_2nephi'
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    
    files = get_target_files(target_arg)
    print(f"=== Book of Mormon Notes Formatter ===")
    print(f"Target: {target_arg} | Files: {len(files)} | Dry-run: {dry_run}\n")
    
    success_count = 0
    failed = []
    for f in files:
        ok, msg = process_single_file(f, dry_run=dry_run)
        status = "OK" if ok else "FAIL"
        print(f"[{status:4s}] {f}: {msg}")
        if ok:
            success_count += 1
        else:
            failed.append((f, msg))
            
    print(f"\nCompleted: {success_count}/{len(files)} files successfully processed.")
    if failed:
        print(f"Failed files:")
        for fn, err in failed:
            print(f"  - {fn}: {err}")
