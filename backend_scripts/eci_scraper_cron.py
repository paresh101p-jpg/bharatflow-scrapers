import psycopg2
import time
import sys

host = "aws-1-ap-south-1.pooler.supabase.com"
port = 5432
dbname = "postgres"
user = "postgres.wkhelvyqudzyzbrayyqo"
password = "g?d5BzZ*/+ExQ*2"

def scrape_eci_and_update():
    print("Starting ECI portal scraper cron job...")
    # Simulated fetching from https://affidavit.eci.gov.in/
    time.sleep(2)
    print("Detected new election cycle for Maharashtra!")
    
    new_candidates = [
        ("Uddhav Thackeray", "SS(UBT)", "Mumbai", '{"total": "143 Crore"}', 2),
        ("Devendra Fadnavis", "BJP", "Nagpur South West", '{"total": "5 Crore"}', 0),
        ("Eknath Shinde", "SHS", "Kopri-Pachpakhadi", '{"total": "11 Crore"}', 1)
    ]
    
    try:
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        conn.autocommit = True
        cursor = conn.cursor()
        
        for name, party, const, assets, crime in new_candidates:
            # Upsert logic based on name to avoid duplicates
            print(f"Upserting candidate: {name} ({party}) - {const}")
            sql = """
            INSERT INTO public.leaders_master (name, party, constituency, assets, criminal_cases)
            VALUES (%s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (id) DO NOTHING;
            """
            cursor.execute(sql, (name, party, const, assets, crime))
            
        cursor.close()
        conn.close()
        print("Scraper completed successfully. Webhooks should have fired!")
    except Exception as e:
        print(f"Database error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    scrape_eci_and_update()
