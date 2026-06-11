import sys
import json
import time
import random
import urllib.request
import urllib.parse
import os
from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://wkhelvyqudzyzbrayyqo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraGVsdnlxdWR6eXpicmF5eXFvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NzY2ODE5NCwiZXhwIjoyMDkzMjQ0MTk0fQ.4wM9t8CBYkpP8fkGxT0yyljQMOpn9o5RbC5_foEq-K0')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

WIKI_HEADERS = {
    'User-Agent': 'BharatFlowBot/1.0 (educational civic app; contact@bharatflow.in)',
    'Accept': 'application/json',
}

def get_wiki_image(name, retries=3):
    for attempt in range(retries):
        try:
            search_url = (
                f"https://en.wikipedia.org/w/api.php"
                f"?action=query"
                f"&titles={urllib.parse.quote(name)}"
                f"&prop=pageimages"
                f"&format=json"
                f"&pithumbsize=400"
            )
            req = urllib.request.Request(search_url, headers=WIKI_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                pages = data['query']['pages']
                for page_id, page_info in pages.items():
                    if page_id != '-1' and 'thumbnail' in page_info:
                        return page_info['thumbnail']['source']
            return None  # Page found but no image
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (attempt + 1) * 30  # 30s, 60s, 90s backoff
                print(f"  Rate limited! Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                break
        except Exception:
            time.sleep(2)
    return None

def main():
    # Load all leaders with fake ui-avatar photos, high likes first
    all_fake = []
    offset = 0
    print("Loading leaders needing photos...")
    while True:
        res = (supabase.table('leaders_master')
               .select('id, name, total_likes')
               .ilike('photo_url', '%ui-avatars%')
               .order('total_likes', desc=True)
               .range(offset, offset + 999)
               .execute())
        if not res.data:
            break
        all_fake.extend(res.data)
        offset += 1000
        if len(res.data) < 1000:
            break

    total = len(all_fake)
    print(f"Total leaders needing real photos: {total}")

    updated = 0
    failed = 0

    for i, leader in enumerate(all_fake):
        name = leader['name']

        # Try full name first
        img = get_wiki_image(name)

        # Try first + last name if multi-word
        if not img and ' ' in name:
            parts = name.split()
            if len(parts) >= 2:
                img = get_wiki_image(f"{parts[0]} {parts[-1]}")

        if img:
            supabase.table('leaders_master').update({'photo_url': img}).eq('id', leader['id']).execute()
            updated += 1
            print(f"OK [{updated}] {name}")
        else:
            failed += 1

        if (i + 1) % 100 == 0:
            print(f"--- Progress: {i+1}/{total} | Updated: {updated} | Skipped: {failed} ---")

        # Random delay 0.5 to 1.5 seconds to avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))

    print(f"\n=== PHOTO FETCH DONE ===")
    print(f"Updated: {updated} | Skipped: {failed} | Total: {total}")

if __name__ == '__main__':
    main()
