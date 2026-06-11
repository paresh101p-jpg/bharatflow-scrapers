require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');
const axios = require('axios');

// Environment Variables
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
const GOVT_API_KEY = process.env.GOVT_API_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY || !GOVT_API_KEY) {
  console.error("Missing Environment Variables! Please check your .env file.");
  process.exit(1);
}

// Initialize Supabase Client
const WebSocket = require('ws');
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
  auth: {
    persistSession: false,
  },
  realtime: {
    transport: WebSocket,
  },
});

const MAX_RECORDS = 5000;
const BATCH_SIZE = 1000;

async function fetchAndUpsert(url) {
  try {
    const response = await axios.get(url, { timeout: 20000 });
    const records = response.data.records || [];
    if (records.length === 0) return 0;

    const mappedList = records.map(r => {
      const rawDate = r.Arrival_Date || r.arrival_date || '';
      let isoDate = rawDate;
      try {
        const parts = rawDate.split('/');
        if (parts.length === 3) {
          isoDate = `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
        }
      } catch (e) {}

      return {
        mandi_name: r.Market || r.market || 'Unknown',
        commodity_name: r.Commodity || r.commodity || 'Other',
        state: r.State || r.state || 'India',
        district: r.District || r.district || '',
        arrival_date: isoDate,
        modal_price: parseFloat(r.Modal_Price || r.modal_price || 0) || 0,
        min_price: parseFloat(r.Min_Price || r.min_price || 0) || 0,
        max_price: parseFloat(r.Max_Price || r.max_price || 0) || 0,
        variety: r.Variety || r.variety || 'General',
      };
    });

    const { error } = await supabase.from('mandi_prices').insert(mappedList);
    if (error) {
      console.error("Supabase Insert Error:", error);
      return 0;
    }
    
    return mappedList.length;
  } catch (error) {
    console.error("Fetch Error:", error.message);
    return 0;
  }
}

async function syncNationalData() {
  console.log(`[${new Date().toISOString()}] Starting Mandi Data Sync...`);
  
  // Date logic for last 3 days
  const dateFilters = [];
  const now = new Date();
  for (let i = 0; i < 3; i++) {
    const d = new Date(now);
    d.setDate(now.getDate() - i);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    dateFilters.push(`${day}/${month}/${year}`);
  }

  for (const dateFilter of dateFilters) {
    console.log(`Syncing data for date: ${dateFilter}`);
    let offset = 0;
    while (offset < MAX_RECORDS) {
      const url = `https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24?api-key=${GOVT_API_KEY}&format=json&limit=${BATCH_SIZE}&offset=${offset}&filters[Arrival_Date]=${dateFilter}`;
      
      const count = await fetchAndUpsert(url);
      console.log(`  Fetched and saved ${count} records (Offset: ${offset})`);
      
      if (count < BATCH_SIZE) break; // Reached the end of data for this date
      offset += BATCH_SIZE;
      
      // Sleep for 1 second to avoid overwhelming the Govt API
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  
  console.log(`[${new Date().toISOString()}] Sync Completed Successfully!`);
}

// Run the sync function immediately when the script starts
syncNationalData();
