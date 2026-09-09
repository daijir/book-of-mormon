import os
import re
import html
import time
import urllib.request
import urllib.error

# Definition of the 15 books in the Book of Mormon
# (folder_name, url_slug, display_name, ja_name, num_chapters)
BOOKS = [
    ("01_1nephi", "1-ne", "1 Nephi", "ニーファイ第一書", 22),
    ("02_2nephi", "2-ne", "2 Nephi", "ニーファイ第二書", 33),
    ("03_jacob", "jacob", "Jacob", "ヤコブ書", 7),
    ("04_enos", "enos", "Enos", "エノス書", 1),
    ("05_jarom", "jarom", "Jarom", "ジェロム書", 1),
    ("06_omni", "omni", "Omni", "オムナイ書", 1),
    ("07_wordsofmormon", "w-of-m", "Words of Mormon", "モルモンの言葉", 1),
    ("08_mosiah", "mosiah", "Mosiah", "モーサヤ書", 29),
    ("09_alma", "alma", "Alma", "アルマ書", 63),
    ("10_helaman", "hel", "Helaman", "ヒラマン書", 16),
    ("11_3nephi", "3-ne", "3 Nephi", "第三ニーファイ", 30),
    ("12_4nephi", "4-ne", "4 Nephi", "第四ニーファイ", 1),
    ("13_mormon", "morm", "Mormon", "モルモン書", 9),
    ("14_ether", "ether", "Ether", "エテル書", 15),
    ("15_moroni", "moro", "Moroni", "モロナイ書", 10),
]

BASE_URL = "https://www.churchofjesuschrist.org/study/scriptures/bofm/{book_slug}/{chapter}?lang={lang}"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_html_text(text, is_japanese=False):
    if not text:
        return ""
    if is_japanese:
        # Remove ruby annotations <rt> and <rp>
        text = re.sub(r'<rt\b[^>]*>.*?</rt>', '', text, flags=re.DOTALL)
        text = re.sub(r'<rp\b[^>]*>.*?</rp>', '', text, flags=re.DOTALL)
    # Remove footnote markers like <sup class="marker" ...>...</sup>
    text = re.sub(r'<sup\b[^>]*class="[^"]*marker[^"]*"[^>]*>.*?</sup>', '', text, flags=re.DOTALL)
    # Remove any remaining html tags
    text = re.sub(r'<[^>]+>', '', text)
    # Unescape html entities
    text = html.unescape(text)
    # Replace non-breaking spaces and normalize whitespace
    text = text.replace('\xa0', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def parse_chapter_html(raw_html, is_japanese=False):
    # Intro
    intros = re.findall(r'<p\b[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</p>', raw_html, re.DOTALL)
    intro_text = clean_html_text(intros[0], is_japanese=is_japanese) if intros else ""
    
    # Summary
    summaries = re.findall(r'<p\b[^>]*class="[^"]*study-summary[^"]*"[^>]*>(.*?)</p>', raw_html, re.DOTALL)
    summary_text = clean_html_text(summaries[0], is_japanese=is_japanese) if summaries else ""
    
    # Verses
    raw_verses = re.findall(r'<p\b[^>]*class="[^"]*verse[^"]*"[^>]*>(.*?)</p>', raw_html, re.DOTALL)
    verses = {}
    for idx, raw_v in enumerate(raw_verses):
        vm = re.search(r'<span class="verse-number">(\d+)</span>', raw_v)
        v_num = int(vm.group(1)) if vm else idx + 1
        cleaned = clean_html_text(raw_v, is_japanese=is_japanese)
        # Strip leading numbers
        text_only = re.sub(r'^\d+\s*', '', cleaned).strip()
        verses[v_num] = text_only
        
    return {
        "intro": intro_text,
        "summary": summary_text,
        "verses": verses
    }

def parse_existing_en_txt(fpath):
    if not os.path.exists(fpath):
        return None
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    title = lines[0] if lines else ""
    
    intro_m = re.search(r'\[Intro(?:\s*/\s*序文)?\]\n(.*?)(?=\n\n|\n\[|\n\d|\Z)', content, re.DOTALL)
    intro = intro_m.group(1).strip() if intro_m else ""
    if intro.startswith("EN: "):
        intro = intro[4:].strip()
    
    summary_m = re.search(r'\[Summary(?:\s*/\s*要約)?\]\n(.*?)(?=\n\n|\n\[|\n\d|\Z)', content, re.DOTALL)
    summary = summary_m.group(1).strip() if summary_m else ""
    if summary.startswith("EN: "):
        summary = summary[4:].strip()
    
    verses = {}
    for line in lines:
        vm = re.match(r'^(\d+)\s+(.*)$', line.strip())
        if vm:
            v_num = int(vm.group(1))
            v_text = vm.group(2).strip()
            verses[v_num] = v_text
            
    return {
        "title": title,
        "intro": intro,
        "summary": summary,
        "verses": verses
    }

def format_bilingual(en_data, ja_data, display_name, ja_name, chapter_num, total_chapters):
    lines = []
    
    # Title
    if total_chapters == 1:
        header_title = f"{display_name} / {ja_name}"
    else:
        header_title = f"{display_name} {chapter_num} / {ja_name} {chapter_num}"
    lines.append(header_title)
    lines.append("")
    
    # Intro if present
    if en_data["intro"] or ja_data["intro"]:
        lines.append("[Intro / 序文]")
        if en_data["intro"]:
            lines.append(f"EN: {en_data['intro']}")
        if ja_data["intro"]:
            lines.append(f"JA: {ja_data['intro']}")
        lines.append("")
        
    # Summary if present
    if en_data["summary"] or ja_data["summary"]:
        lines.append("[Summary / 要約]")
        if en_data["summary"]:
            lines.append(f"EN: {en_data['summary']}")
        if ja_data["summary"]:
            lines.append(f"JA: {ja_data['summary']}")
        lines.append("")
        
    # Verses
    all_v_nums = sorted(set(en_data["verses"].keys()) | set(ja_data["verses"].keys()))
    for v_num in all_v_nums:
        en_v = en_data["verses"].get(v_num, "")
        ja_v = ja_data["verses"].get(v_num, "")
        lines.append(str(v_num))
        if en_v:
            lines.append(f"EN: {en_v}")
        if ja_v:
            lines.append(f"JA: {ja_v}")
        lines.append("")
        
    return "\n".join(lines).strip() + "\n"

def fetch_with_retry(url, retries=3, delay=2):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                raise e

def main():
    import sys
    test_mode = "--test" in sys.argv
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Target directory: {root_dir}")
    
    books_to_process = [BOOKS[0], BOOKS[3]] if test_mode else BOOKS
    total_chapters_count = sum(num_ch for _, _, _, _, num_ch in books_to_process)
    print(f"Mode: {'TEST' if test_mode else 'FULL'}, Total books: {len(books_to_process)}, Total chapters: {total_chapters_count}")
    
    processed_count = 0
    start_time = time.time()
    
    for folder_name, book_slug, display_name, ja_name, num_chapters in books_to_process:
        book_dir = os.path.join(root_dir, folder_name)
        os.makedirs(book_dir, exist_ok=True)
        print(f"\nProcessing [{display_name} / {ja_name}] ({num_chapters} chapters) -> folder: {folder_name}/")
        
        target_range = range(1, 2) if test_mode else range(1, num_chapters + 1)
        for ch in target_range:
            file_name = f"{ch:02d}.txt"
            file_path = os.path.join(book_dir, file_name)
            
            # Fetch English directly from official site
            en_url = BASE_URL.format(book_slug=book_slug, chapter=ch, lang="eng")
            en_html = fetch_with_retry(en_url)
            en_data = parse_chapter_html(en_html, is_japanese=False)
            en_data["title"] = f"{display_name} {ch}" if num_chapters > 1 else display_name
            
            # Fetch Japanese
            ja_url = BASE_URL.format(book_slug=book_slug, chapter=ch, lang="jpn")
            try:
                ja_html = fetch_with_retry(ja_url)
                ja_data = parse_chapter_html(ja_html, is_japanese=True)
                
                bilingual_text = format_bilingual(en_data, ja_data, display_name, ja_name, ch, num_chapters)
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(bilingual_text)
                
                processed_count += 1
                v_count = max(len(en_data["verses"]), len(ja_data["verses"]))
                print(f"  [{processed_count}/{total_chapters_count}] {folder_name}/{file_name} saved bilingual ({v_count} verses)")
                
                # Polite rate limiting
                time.sleep(0.25)
                
            except Exception as e:
                print(f"  ERROR fetching Japanese {ja_url}: {e}")

    elapsed = time.time() - start_time
    print(f"\nCompleted! Processed {processed_count}/{total_chapters_count} bilingual chapters in {elapsed:.1f}s.")

if __name__ == "__main__":
    main()
