import requests
import json

# SUPABASE CONFIG
SUPABASE_URL = "https://wkhelvyqudzyzbrayyqo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraGVsdnlxdWR6eXpicmF5eXFvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc2NjgxOTQsImV4cCI6MjA5MzI0NDE5NH0.DyqHPzEpwo-ToLg8uH4ZYBZBrgl1V4KzZ5iE0QiYVyY"

def upload_batch_2():
    print("Uploading Official Batch 2 (Punjab, Bihar, Haryana, Rajasthan, MP)...")
    
    warehouses = [
        # PUNJAB
        {"name": "FREINDS ASSOCIATES", "address": "VILL BEHAK GUJRAN, Ferozepur, Punjab", "district": "Ferozepur", "capacity": "46760 MT", "latitude": 30.9200, "longitude": 74.6000, "type": "Private", "monthly_rent": 13.0},
        {"name": "ANGOORI DEVI", "address": "OPP GATE ARMY CANTT, FAZILKA ROAD, Ferozepur, Punjab", "district": "Ferozepur", "capacity": "5049 MT", "latitude": 30.9300, "longitude": 74.6100, "type": "Private", "monthly_rent": 12.5},
        {"name": "GARG GODOWNS & WAREHOUSE", "address": "Village Toorbanjara, Dirba, Mansa, Punjab", "district": "Mansa", "capacity": "104000 MT", "latitude": 30.0000, "longitude": 75.4000, "type": "Private", "monthly_rent": 11.0},
        
        # BIHAR
        {"name": "BSWC CHAPRA", "address": "BSWC Compound, Chapra, Bihar", "district": "Saran", "capacity": "10000 MT", "latitude": 25.7800, "longitude": 84.7300, "type": "Government", "monthly_rent": 14.0},
        {"name": "BSWC Gulabbagh", "address": "Purnia Division, Gulabbagh, Bihar", "district": "Purnia", "capacity": "8925 MT", "latitude": 25.7800, "longitude": 87.5000, "type": "Government", "monthly_rent": 13.5},
        
        # HARYANA
        {"name": "HAFED COMPLEX DEEPALPUR", "address": "Village Deepalpur, Sonipat, Haryana", "district": "Sonipat", "capacity": "8550 MT", "latitude": 28.9800, "longitude": 77.0200, "type": "Government", "monthly_rent": 12.0},
        
        # RAJASTHAN
        {"name": "Central Warehouse, Hanumangarh", "address": "Near Railway Station, Hanumangarh, Rajasthan", "district": "Hanumangarh", "capacity": "23150 MT", "latitude": 29.5800, "longitude": 74.3200, "type": "Government", "monthly_rent": 11.0},
        
        # MADHYA PRADESH
        {"name": "CHUNCHUN WAREHOUSE", "address": "VILLAGE RALA, TEHSIL NASRULLAGANJ, Sehore, MP", "district": "Sehore", "capacity": "5000 MT", "latitude": 22.8500, "longitude": 77.0800, "type": "Private", "monthly_rent": 15.0},
        {"name": "ABHILASHI WAREHOUSE", "address": "VILLGE BARKHEDA BARAMAD, TEHSIL BERASIA, Bhopal, MP", "district": "Bhopal", "capacity": "5610 MT", "latitude": 23.6300, "longitude": 77.4300, "type": "Private", "monthly_rent": 14.5},
        {"name": "VEDANTAM WAREHOUSE", "address": "Soyat Road Machalur, Rajgarh, MP", "district": "Rajgarh", "capacity": "3273 MT", "latitude": 23.6800, "longitude": 76.7300, "type": "Private", "monthly_rent": 16.0}
    ]

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    url = f"{SUPABASE_URL}/rest/v1/warehouses"
    
    # Append to existing real data
    print(f"Uploading {len(warehouses)} more real records...")
    response = requests.post(url, headers=headers, data=json.dumps(warehouses))
    
    if response.status_code in [200, 201]:
        print("Success! Batch 2 uploaded.")
    else:
        print(f"Failed! Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    upload_batch_2()
