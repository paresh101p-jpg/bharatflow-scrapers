import os
import csv
import json
import requests
from pathlib import Path

SUPABASE_URL = "https://wkhelvyqudzyzbrayyqo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraGVsdnlxdWR6eXpicmF5eXFvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc2NjgxOTQsImV4cCI6MjA5MzI0NDE5NH0.DyqHPzEpwo-ToLg8uH4ZYBZBrgl1V4KzZ5iE0QiYVyY"

BATCH_SIZE = 100

def upload_batch(batch):
    if not batch:
        return
    url = f"{SUPABASE_URL}/rest/v1/warehouses"
    headers = {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=minimal",
    }
    response = requests.post(url, headers=headers, data=json.dumps(batch))
    if response.status_code in (200, 201):
        print(f"Uploaded batch of {len(batch)} records.")
    else:
        print(f"Failed batch: {response.text}")

def main():
    warehause_dir = Path(r"e:\BharatFlow\BharatFlow\Warehause")
    csv_files = list(warehause_dir.glob("*.csv"))
    
    print("Clearing old data for smart update...")
    requests.delete(f"{SUPABASE_URL}/rest/v1/warehouses?id=gt.0", headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})

    for csv_path in csv_files:
        print(f"Smart Processing {csv_path.name}...")
        batch = []
        try:
            with csv_path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("WH Name") or row.get("WHM Name") or "Unknown").strip()
                    addr = (row.get("Address") or "").strip()
                    dist = (row.get("District") or "").strip()
                    state = (row.get("State") or "").strip()
                    status_raw = (row.get("Status") or "").upper()
                    remarks_raw = (row.get("Remarks") or "").upper()
                    
                    # SMART CLOSED LOGIC (Official Data is better than Google for legal status)
                    is_live = True
                    if "INACTIVE" in status_raw or "CLOSED" in status_raw or "EXPIRED" in status_raw or "CANCELLED" in status_raw:
                        is_live = False
                    if "PERMANENTLY CLOSED" in remarks_raw or "SURRENDERED" in remarks_raw:
                        is_live = False

                    warehouse = {
                        "name": name,
                        "address": f"{addr}, {dist}, {state}".strip(", "),
                        "district": dist,
                        "capacity": row.get("Capacity(in MT)") or row.get("Capacity") or "0",
                        "type": "Private" if "PRIVATE" in name.upper() or "PVT" in name.upper() else "Government",
                        "monthly_rent": 11.0,
                        "is_live": is_live,
                        "contact_no": (row.get("Contact No.") or "").strip()
                    }
                    batch.append(warehouse)
                    if len(batch) >= BATCH_SIZE:
                        upload_batch(batch)
                        batch.clear()
            upload_batch(batch)
        except Exception as e:
            print(f"Error: {e}")

    print("Smart Import complete.")

if __name__ == "__main__":
    main()
