import os
import sys
import json
import datetime
import requests
from supabase import create_client, Client

def safe_float(val):
    try:
        if val is None:
            return 0.0
        cleaned = str(val).strip()
        if not cleaned or cleaned.lower() in ("null", "none", "n/a", ""):
            return 0.0
        return float(cleaned)
    except ValueError:
        return 0.0

def main():
    print("[START] Starting BharatFlow Background Mandi Data Sync Scraper...")

    # Load credentials from environment
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    gov_api_key = os.environ.get("GOV_API_KEY")

    if not supabase_url or not supabase_key or not gov_api_key:
        print("[ERROR] Missing environment variables! Please configure SUPABASE_URL, SUPABASE_KEY, and GOV_API_KEY.")
        sys.exit(1)

    # Initialize Supabase client
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"[ERROR] Failed to connect to Supabase: {e}")
        sys.exit(1)

    # Calculate date filters for the last 3 days (DD/MM/YYYY)
    now = datetime.datetime.now()
    date_filters = []
    for i in range(3):
        date = now - datetime.timedelta(days=i)
        date_filters.append(date.strftime("%d/%m/%Y"))

    print(f"[INFO] Target arrival dates for synchronization: {date_filters}")

    resource_id = "35985678-0d79-46b4-9ed6-6f13308a1d24"
    base_url = f"https://api.data.gov.in/resource/{resource_id}"

    total_records_synced = 0

    for date_filter in date_filters:
        print(f"[INFO] Fetching data for Arrival Date: {date_filter}...")
        offset = 0
        limit = 1000

        while True:
            url = f"{base_url}?api-key={gov_api_key}&format=json&limit={limit}&offset={offset}&filters[Arrival_Date]={date_filter}"
            
            try:
                response = requests.get(url, timeout=30)
                if response.status_code != 200:
                    print(f"[WARNING] Government API returned error code {response.status_code} for date {date_filter}")
                    break
                
                data = response.json()
                records = data.get("records", [])
                
                if not records:
                    print(f"[INFO] No more records found for date {date_filter} (offset: {offset})")
                    break

                # Map records to Supabase schema
                mapped_records = []
                sync_time = datetime.datetime.utcnow().isoformat() + "Z"

                for r in records:
                    raw_date = r.get("Arrival_Date") or r.get("arrival_date") or ""
                    iso_date = raw_date
                    if "/" in raw_date:
                        parts = raw_date.split("/")
                        if len(parts) == 3:
                            day = parts[0].zfill(2)
                            month = parts[1].zfill(2)
                            year = parts[2]
                            iso_date = f"{year}-{month}-{day}"

                    mapped_records.append({
                        "mandi_name": r.get("Market") or r.get("market") or "Unknown",
                        "commodity_name": r.get("Commodity") or r.get("commodity") or "Other",
                        "state": r.get("State") or r.get("state") or "India",
                        "district": r.get("District") or r.get("district") or "",
                        "arrival_date": iso_date,
                        "modal_price": safe_float(r.get("Modal_Price") or r.get("modal_price")),
                        "min_price": safe_float(r.get("Min_Price") or r.get("min_price")),
                        "max_price": safe_float(r.get("Max_Price") or r.get("max_price")),
                        "variety": r.get("Variety") or r.get("variety") or "General",
                        "grade": r.get("Grade") or r.get("grade") or "FAQ",
                        "sync_at": sync_time
                    })

                # Upsert into Supabase
                try:
                    res = supabase.table("mandi_prices").upsert(mapped_records, on_conflict="mandi_name,commodity_name,arrival_date,variety").execute()
                    print(f"[SUCCESS] Upserted batch of {len(mapped_records)} records (offset: {offset})")
                    total_records_synced += len(mapped_records)
                except Exception as db_err:
                    print(f"[ERROR] Supabase upsert error: {db_err}")

                if len(records) < limit:
                    # No more records for this date
                    break

                offset += limit

            except Exception as e:
                print(f"[ERROR] Error during fetching/processing: {e}")
                break

    print(f"[SUCCESS] Sync completed! Total records synchronized: {total_records_synced}")

if __name__ == "__main__":
    main()
