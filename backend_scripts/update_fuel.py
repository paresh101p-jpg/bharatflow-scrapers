import os
import requests
import re
from datetime import datetime
from supabase import create_client, Client

SUPABASE_URL = "https://wkhelvyqudzyzbrayyqo.supabase.co"
from dotenv import load_dotenv
load_dotenv()
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_KEY:
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraGVsdnlxdWR6eXpicmF5eXFvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NzY2ODE5NCwiZXhwIjoyMDkzMjQ0MTk0fQ.4wM9t8CBYkpP8fkGxT0yyljQMOpn9o5RbC5_foEq-K0"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

cities = [
    "surat", "ahmedabad", "delhi", "mumbai", "pune", "chennai", "kolkata", "jaipur", "lucknow", "bangalore", "hyderabad", "patna"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}

def get_float(text):
    if not text: return None
    try:
        return float(text.replace(',', ''))
    except:
        return None

for city in cities:
    print(f"Fetching {city}...")
    try:
        p_res = requests.get(f"https://www.goodreturns.in/petrol-price-in-{city}.html", headers=headers, timeout=10)
        d_res = requests.get(f"https://www.goodreturns.in/diesel-price-in-{city}.html", headers=headers, timeout=10)
        l_res = requests.get(f"https://www.goodreturns.in/lpg-price-in-{city}.html", headers=headers, timeout=10)
        c_res = requests.get(f"https://www.goodreturns.in/cng-price-in-{city}.html", headers=headers, timeout=10)
        png_res = requests.get(f"https://www.goodreturns.in/png-price-in-{city}.html", headers=headers, timeout=10)
        
        rx_petrol = re.compile(r'petrol price in [a-zA-Z\s]+ is (?:at )?(?:<b>)?(?:&#x20b9;|&#8377;|\u20B9|₹|Rs\.?)\s*(?:<b>)?(\d+(?:,\d+)*\.\d+)', re.IGNORECASE)
        rx_diesel = re.compile(r'diesel price in [a-zA-Z\s]+ is (?:at )?(?:<b>)?(?:&#x20b9;|&#8377;|\u20B9|₹|Rs\.?)\s*(?:<b>)?(\d+(?:,\d+)*\.\d+)', re.IGNORECASE)
        rx_cng = re.compile(r'CNG price in [a-zA-Z\s]+ (?:is|stands) (?:at )?(?:<b>)?(?:&#x20b9;|&#8377;|\u20B9|₹|Rs\.?)\s*(?:<b>)?(\d+(?:,\d+)*\.\d+)', re.IGNORECASE)
        rx_png = re.compile(r'PNG price in [a-zA-Z\s]+ (?:is|stands) (?:at )?(?:<b>)?(?:&#x20b9;|&#8377;|\u20B9|₹|Rs\.?)\s*(?:<b>)?(\d+(?:,\d+)*\.\d+)', re.IGNORECASE)
        
        p_match = rx_petrol.search(p_res.text)
        d_match = rx_diesel.search(d_res.text)
        c_match = rx_cng.search(c_res.text)
        png_match = rx_png.search(png_res.text)
        
        l_html = l_res.text
        d_lpg_match = re.search(r'Domestic LPG .*? (?:is|stands) (?:at )?(?:<b>)?(?:&#x20b9;|&#8377;|\u20B9|₹|Rs\.?)\s*(?:<b>)?(\d+(?:,\d+)*\.\d+)', l_html, re.IGNORECASE)
        if not d_lpg_match:
            d_lpg_match = re.search(r'(?:&#x20b9;|&#8377;|\u20B9|₹|Rs\.?)\s*(?:<b>)?(\d+(?:,\d+)*\.\d+)(?:<\/b>)?', l_html, re.IGNORECASE)
            
        c_lpg_match = re.search(r'Commercial LPG .*? (?:is|stands) (?:at )?(?:<b>)?(?:&#x20b9;|&#8377;|\u20B9|₹|Rs\.?)\s*(?:<b>)?(\d+(?:,\d+)*\.\d+)', l_html, re.IGNORECASE)
        
        petrol = get_float(p_match.group(1)) if p_match else None
        diesel = get_float(d_match.group(1)) if d_match else None
        cng = get_float(c_match.group(1)) if c_match else 82.16
        png = get_float(png_match.group(1)) if png_match else 49.60
        domestic_lpg = get_float(d_lpg_match.group(1)) if d_lpg_match else 918.50
        commercial_lpg = get_float(c_lpg_match.group(1)) if c_lpg_match else 3024.50
        
        if domestic_lpg > commercial_lpg and commercial_lpg > 0:
            domestic_lpg, commercial_lpg = commercial_lpg, domestic_lpg
            
        if not petrol or not diesel:
            print(f"Failed to parse fuel for {city}")
            continue
            
        record = {
            "city": city.capitalize(),
            "state": "Gujarat" if city in ["surat", "ahmedabad"] else "Unknown",
            "petrol": petrol,
            "diesel": diesel,
            "cng": cng,
            "png": png,
            "lpg": domestic_lpg,
            "commercial_lpg": commercial_lpg,
            "updated_at": datetime.utcnow().isoformat()
        }
        print(f"Data for {city}: {record}")
        
        supabase.table("fuel_prices").upsert(record, on_conflict="city,state").execute()
        
        # update history
        history_record = record.copy()
        del history_record["updated_at"]
        history_record["recorded_at"] = datetime.utcnow().isoformat()
        supabase.table("fuel_price_history").insert(history_record).execute()
        
    except Exception as e:
        print(f"Error for {city}: {e}")

print("Done")
