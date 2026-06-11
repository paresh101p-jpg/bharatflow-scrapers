import sys
import json
import time
import random
import re
import urllib.request
import urllib.parse
import os
from bs4 import BeautifulSoup
from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://wkhelvyqudzyzbrayyqo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraGVsdnlxdWR6eXpicmF5eXFvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NzY2ODE5NCwiZXhwIjoyMDkzMjQ0MTk0fQ.4wM9t8CBYkpP8fkGxT0yyljQMOpn9o5RbC5_foEq-K0')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def format_amount(rupee_str):
    """Convert raw rupee amount to display string like '17 Crore+' """
    try:
        amt = int(re.sub(r'[^\d]', '', rupee_str))
        if amt >= 10_000_000:
            return f"{amt // 10_000_000} Crore+"
        elif amt >= 100_000:
            return f"{amt // 100_000} Lakh+"
        elif amt > 0:
            return f"{amt:,}"
    except:
        pass
    return None

def search_myneta(name, retries=2):
    for attempt in range(retries):
        try:
            url = f"https://myneta.info/search_myneta.php?q={urllib.parse.quote(name)}"
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode('utf-8', errors='replace')
                soup = BeautifulSoup(html, 'html.parser')
                links = soup.find_all('a', href=re.compile(r'candidate_id=\d+'))
                if links:
                    href = links[0]['href']
                    if not href.startswith('http'):
                        href = 'https://myneta.info' + href
                    return href
            return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (attempt + 1) * 60
                print(f"  MyNeta rate limited! Waiting {wait}s...")
                time.sleep(wait)
            else:
                break
        except Exception:
            time.sleep(3)
    return None

def fetch_candidate_details(url, retries=2):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode('utf-8', errors='replace')
                soup = BeautifulSoup(html, 'html.parser')
                text = soup.get_text(' ', strip=True)

                result = {}

                # Criminal Cases
                m = re.search(r'Number of Criminal Cases\s*[:\-]\s*(\d+)', text)
                if m:
                    result['criminal_cases'] = int(m.group(1))

                # Education
                edu_section = re.search(r'Educational Details(.{10,300}?)(?:Details of Criminal|Assets)', text, re.DOTALL)
                if edu_section:
                    edu_text = edu_section.group(1).strip()
                    edu_lines = [l.strip() for l in edu_text.split('\n') if l.strip() and len(l.strip()) > 4]
                    if edu_lines:
                        result['education'] = edu_lines[0][:200]

                # Total Assets - look for the summary line
                assets_m = re.search(r'Assets\s*[:\-]?\s*Rs\s*[.\s]*([\d,]+)\s*~?\s*([\d]+\s*(?:Crore|Lacs?|Thou)\+?)', text)
                if assets_m:
                    display = assets_m.group(2).strip()
                    result['assets'] = {'total': display, 'details': ''}
                else:
                    # Try raw number
                    assets_m2 = re.search(r'Total Assets.*?Rs\s*([\d,]+)', text)
                    if assets_m2:
                        formatted = format_amount(assets_m2.group(1))
                        if formatted:
                            result['assets'] = {'total': formatted, 'details': ''}

                # Liabilities
                liab_m = re.search(r'Liabilities\s*[:\-]?\s*Rs\s*[.\s]*([\d,]+)\s*~?\s*([\d]+\s*(?:Crore|Lacs?|Thou)\+?)', text)
                if liab_m:
                    display = liab_m.group(2).strip()
                    result['liabilities'] = {'total': display, 'details': ''}

                # Birthdate from Age (approximate)
                dob_m = re.search(r'Date of Birth\s*[:\-]\s*(\d{2}[-/]\d{2}[-/]\d{4})', text)
                if dob_m:
                    raw = dob_m.group(1)
                    parts = re.split(r'[-/]', raw)
                    if len(parts) == 3:
                        result['birthdate'] = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

                return result if result else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (attempt + 1) * 60
                print(f"  Rate limited! Waiting {wait}s...")
                time.sleep(wait)
        except Exception:
            time.sleep(3)
    return None

def main():
    # Load all leaders missing assets data
    all_leaders = []
    offset = 0
    print("Loading leaders needing data...")
    while True:
        res = (supabase.table('leaders_master')
               .select('id, name, constituency, party')
               .is_('assets', 'null')
               .range(offset, offset + 999)
               .execute())
        if not res.data:
            break
        all_leaders.extend(res.data)
        offset += 1000
        if len(res.data) < 1000:
            break

    total = len(all_leaders)
    print(f"Total leaders needing data: {total}")
    updated = 0
    skipped = 0

    for i, leader in enumerate(all_leaders):
        name = leader['name']

        # Search on myneta.info
        candidate_url = search_myneta(name)
        if candidate_url:
            data = fetch_candidate_details(candidate_url)
            if data:
                supabase.table('leaders_master').update(data).eq('id', leader['id']).execute()
                updated += 1
                parts = []
                if 'assets' in data: parts.append(f"assets={data['assets']['total']}")
                if 'education' in data: parts.append(f"edu={data['education'][:20]}")
                if 'criminal_cases' in data: parts.append(f"cases={data['criminal_cases']}")
                print(f"OK [{updated}] {name}: {', '.join(parts)}")
            else:
                skipped += 1
        else:
            skipped += 1

        if (i + 1) % 50 == 0:
            print(f"--- Progress: {i+1}/{total} | Updated: {updated} | Skipped: {skipped} ---")

        # Random delay to avoid blocks - 1 to 2 seconds
        time.sleep(random.uniform(1.0, 2.0))

    print(f"\n=== DATA FETCH DONE ===")
    print(f"Updated: {updated} | Skipped: {skipped} | Total: {total}")

if __name__ == '__main__':
    main()
