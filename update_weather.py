import requests
import time
from supabase import create_client
from datetime import datetime, timedelta

# Supabase Setup
url = "https://wkhelvyqudzyzbrayyqo.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndraGVsdnlxdWR6eXpicmF5eXFvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NzY2ODE5NCwiZXhwIjoyMDkzMjQ0MTk0fQ.4wM9t8CBYkpP8fkGxT0yyljQMOpn9o5RbC5_foEq-K0"
supabase = create_client(url, key)

def get_yearly_records(lat, lon):
    try:
        end_date = datetime.now().date() - timedelta(days=1)
        start_date = end_date - timedelta(days=3650) # 10 years historical data
        archive_url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
                       f"&start_date={start_date}&end_date={end_date}"
                       f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto")
        res = requests.get(archive_url).json()
        daily = res['daily']
        mx_t = max(daily['temperature_2m_max'])
        mx_t_d = daily['time'][daily['temperature_2m_max'].index(mx_t)]
        mn_t = min(daily['temperature_2m_min'])
        mn_t_d = daily['time'][daily['temperature_2m_min'].index(mn_t)]
        mx_r = max(daily['precipitation_sum'])
        mx_r_d = daily['time'][daily['precipitation_sum'].index(mx_r)]
        time.sleep(0.5) # Prevents hitting burst rate limits
        return mx_t, mx_t_d, mn_t, mn_t_d, mx_r, mx_r_d
    except:
        time.sleep(0.5)
        return None, None, None, None, None, None

def update_weather():
    try:
        response = supabase.table("india_weather_data").select("*").execute()
        locations = response.data
        if not locations:
            return

        BATCH_SIZE = 40
        for i in range(0, len(locations), BATCH_SIZE):
            chunk = locations[i:i + BATCH_SIZE]
            
            lats = ",".join([str(loc.get('latitude') or 21.17) for loc in chunk])
            lons = ",".join([str(loc.get('longitude') or 72.83) for loc in chunk])
            
            try:
                # Current Weather API (Batched)
                api_url = (f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
                           f"&current=temperature_2m,precipitation,wind_speed_10m"
                           f"&hourly=temperature_2m,precipitation_probability,weather_code"
                           f"&daily=sunrise,sunset,precipitation_sum,wind_speed_10m_max&forecast_days=14&timezone=auto")
                res = requests.get(api_url).json()
                
                # If only 1 item in chunk, OpenMeteo returns a dict, not a list. Handle this:
                if isinstance(res, dict):
                    if 'error' in res:
                        print(f"â Œ API Error for batch: {res}")
                        time.sleep(2)
                        continue
                    res = [res]

                for idx, loc_res in enumerate(res):
                    loc = chunk[idx]
                    city = loc['location_name']
                    lat = loc.get('latitude', 21.17)
                    lon = loc.get('longitude', 72.83)

                    if 'current' not in loc_res:
                        print(f"â Œ Missing current data for {city}")
                        continue

                    # Add actual_time to daily for Flutter App
                    daily_data = loc_res['daily']
                    daily_data['actual_time'] = loc_res['current']['time']

                    update_data = {
                        "temperature": loc_res['current']['temperature_2m'],
                        "precipitation_1h": loc_res['current']['precipitation'],
                        "wind_speed": loc_res['current']['wind_speed_10m'],
                        "forecast_14d": daily_data,
                        "hourly_data": loc_res['hourly'],
                        "updated_at": "now()"
                    }

                    if not loc.get('yearly_max_temp'):
                        mx_t, mx_t_d, mn_t, mn_t_d, mx_r, mx_r_d = get_yearly_records(lat, lon)
                        if mx_t is not None:
                            update_data.update({
                                "yearly_max_temp": mx_t, "yearly_max_date": mx_t_d,
                                "yearly_min_temp": mn_t, "yearly_min_date": mn_t_d,
                                "yearly_max_rain": mx_r, "yearly_max_rain_date": mx_r_d
                            })

                    supabase.table("india_weather_data").update(update_data).eq("location_name", city).execute()
                    print(f"âœ… Synced: {city}")
                
                time.sleep(1) # Prevent rate limiting between batches
            except Exception as e:
                print(f"â Œ Error updating batch {i}: {e}")
    except Exception as e:
        print(f"â Œ Fatal Error: {e}")

if __name__ == "__main__":
    update_weather()
