"""
BharatFlow - Monthly Subsidy Sync
myscheme.gov.in se subsidies fetch karta hai
- Nayi subsidy aaye     → INSERT
- Purani band ho jaaye  → is_active = FALSE
"""

import os
import json
import time
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

MYSCHEME_API = "https://api.myscheme.gov.in/search/v4/schemes"
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "origin": "https://www.myscheme.gov.in",
    "referer": "https://www.myscheme.gov.in/",
    "user-agent": "Mozilla/5.0 (compatible; BharatFlow/1.0)",
}

def fetch_schemes(page=1, limit=50):
    params = {"keyword": "", "sortBy": "closingDate", "sortOrder": "asc", "lang": "en", "page": page, "limit": limit}
    try:
        resp = requests.get(MYSCHEME_API, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"API error: {e}")
        return {}

def fetch_detail(scheme_id):
    url = f"https://api.myscheme.gov.in/search/v4/schemes/{scheme_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", {}) or {}
    except:
        return {}

def parse_amount(val):
    if not val:
        return None
    try:
        return float(str(val).replace(",", "").replace("₹", "").strip())
    except:
        return None

def map_row(scheme, detail):
    title_en = (scheme.get("schemeName") or scheme.get("title") or "").strip()
    state = scheme.get("state") or "All India"
    if not state or state.lower() in ("", "all", "central"):
        state = "All India"
    eligibility = detail.get("eligibilityCriteria") or {}
    if isinstance(eligibility, str):
        eligibility = {"criteria": eligibility}
    benefit = detail.get("benefits") or {}
    if isinstance(benefit, str):
        benefit = {"details": benefit}
    docs = detail.get("documents") or []
    if isinstance(docs, str):
        docs = [docs]
    apply_url = (detail.get("applicationProcess", {}).get("onlineApplicationUrl") or scheme.get("schemeUrl") or "https://www.myscheme.gov.in/")
    return {
        "subsidy_id": scheme.get("schemeId") or scheme.get("id") or "",
        "category_name": scheme.get("schemeCategory") or "Other",
        "state_name": state,
        "title_en": title_en,
        "title_hi": detail.get("schemeNameHi") or title_en,
        "title_gu": detail.get("schemeNameGu") or title_en,
        "description_en": (detail.get("briefDescription") or "").strip(),
        "start_date": scheme.get("launchDate") or None,
        "end_date": scheme.get("closingDate") or None,
        "is_active": True,
        "min_project_cost": parse_amount(detail.get("minProjectCost")),
        "max_project_cost": parse_amount(detail.get("maxProjectCost")),
        "subsidy_percentage": parse_amount(detail.get("subsidyPercentage")),
        "max_subsidy_amount": parse_amount(detail.get("maxSubsidyAmount")),
        "eligibility_criteria": eligibility or None,
        "benefit_details_json": benefit or None,
        "required_documents": docs or None,
        "apply_url_online": apply_url,
        "apply_node_offline": None,
        "search_keywords": scheme.get("tags") or None,
    }

def get_existing_ids():
    existing = set()
    resp = supabase.table("subsidies").select("subsidy_id").execute()
    for r in resp.data or []:
        if r.get("subsidy_id"):
            existing.add(r["subsidy_id"])
    return existing

def get_active_ids():
    active = set()
    resp = supabase.table("subsidies").select("subsidy_id").eq("is_active", True).execute()
    for r in resp.data or []:
        if r.get("subsidy_id"):
            active.add(r["subsidy_id"])
    return active

def sync():
    print("=" * 50)
    print("BharatFlow - Monthly Subsidy Sync")
    print("=" * 50)

    # Step 1: myscheme se data fetch karo
    print("\nData fetch ho raha hai...")
    all_schemes = []
    page = 1
    while True:
        print(f"  Page {page}...", end=" ")
        data = fetch_schemes(page=page, limit=50)
        schemes = data.get("data", {}).get("schemes") or data.get("schemes") or []
        if not schemes:
            print("khatam!")
            break
        all_schemes.extend(schemes)
        print(f"{len(schemes)} schemes")
        total = data.get("data", {}).get("total") or 0
        if len(all_schemes) >= total or len(schemes) < 50:
            break
        page += 1
        time.sleep(1)

    print(f"\nTotal {len(all_schemes)} schemes mili")

    # Step 2: Supabase se existing data lo
    existing_ids = get_existing_ids()
    active_ids = get_active_ids()
    live_ids = set()
    print(f"Supabase mein: {len(existing_ids)} subsidies")

    # Step 3: Insert / Reactivate
    inserted = reactivated = skipped = 0
    for scheme in all_schemes:
        sid = scheme.get("schemeId") or scheme.get("id") or ""
        if not sid:
            continue
        live_ids.add(sid)
        if sid in existing_ids:
            if sid not in active_ids:
                supabase.table("subsidies").update({"is_active": True}).eq("subsidy_id", sid).execute()
                reactivated += 1
                print(f"  Reactivated: {sid}")
            else:
                skipped += 1
        else:
            detail = fetch_detail(sid)
            row = map_row(scheme, detail)
            if row["title_en"]:
                supabase.table("subsidies").insert(row).execute()
                inserted += 1
                print(f"  Inserted: {sid} - {row['title_en'][:40]}")
            time.sleep(0.5)

    # Step 4: Deactivate jo live nahi hain
    deactivated = 0
    for sid in (active_ids - live_ids):
        supabase.table("subsidies").update({"is_active": False}).eq("subsidy_id", sid).execute()
        deactivated += 1
        print(f"  Deactivated: {sid}")

    print("\n" + "=" * 50)
    print(f"Nayi insert:    {inserted}")
    print(f"Reactivated:    {reactivated}")
    print(f"Deactivated:    {deactivated}")
    print(f"Same rahi:      {skipped}")
    print("SYNC COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    sync()
