require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');
const axios = require('axios');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

async function main() {
  console.log(`[${new Date().toISOString()}] Starting Currency Fetcher...`);
  try {
    // 1. Fetch live rates — try multiple sources for best accuracy
    let rates = null;
    let source = '';

    // Primary: exchangerate-api (updates more frequently)
    try {
      const response = await axios.get('https://open.er-api.com/v6/latest/USD');
      if (response.data.result === 'success' && response.data.rates) {
        rates = response.data.rates;
        source = 'open.er-api.com';
      }
    } catch (e) {
      console.warn('Primary API (open.er-api) failed:', e.message);
    }

    // Fallback: frankfurter.app (ECB data, very accurate)
    if (!rates) {
      try {
        const response = await axios.get('https://api.frankfurter.app/latest?from=USD');
        if (response.data && response.data.rates) {
          rates = response.data.rates;
          rates['USD'] = 1; // frankfurter doesn't include base currency
          source = 'frankfurter.app';
        }
      } catch (e) {
        console.warn('Fallback API (frankfurter) failed:', e.message);
      }
    }

    if (!rates) {
      console.error("All exchange rate APIs failed!");
      return;
    }

    console.log(`Using rates from: ${source}`);
    const inrRate = rates['INR'];
    
    if (!inrRate) {
      console.error("INR rate not found in API response");
      return;
    }

    // 2. Fetch supported currency codes from our database
    const { data: dbCurrencies, error } = await supabase
      .from('currencies')
      .select('currency_code');
      
    if (error || !dbCurrencies) {
      console.error("Error fetching currencies from DB:", error);
      return;
    }

    const todayStr = new Date().toISOString().split('T')[0];
    const upsertPayload = [];

    // 3. Calculate INR equivalent and prepare payload
    for (const c of dbCurrencies) {
      const code = c.currency_code;
      if (rates[code]) {
        // formula: 1 Unit of Foreign Currency = (INR per USD) / (Foreign Currency per USD)
        const rateToInr = inrRate / rates[code];
        
        upsertPayload.push({
          currency_code: code,
          recorded_date: todayStr,
          rate_to_inr: parseFloat(rateToInr.toFixed(6))
        });
      } else {
        console.warn(`Rate not found for ${code} in the open API.`);
      }
    }

    // 4. Delete today's existing records to prevent duplicates
    console.log(`Deleting any existing records for ${todayStr}...`);
    await supabase.from('currency_history').delete().eq('recorded_date', todayStr);

    // 5. Insert new records
    console.log(`Inserting ${upsertPayload.length} new records for ${todayStr}...`);
    const { error: insertError } = await supabase.from('currency_history').insert(upsertPayload);
    
    if (insertError) {
      console.error("Error inserting currency history:", insertError);
    } else {
      console.log(`[${new Date().toISOString()}] Successfully updated currency rates.`);
    }

  } catch (error) {
    console.error("Error in update_currency script:", error.message);
  }
}

module.exports = { updateCurrencyRates: main };

// Allow standalone execution: node update_currency.js
if (require.main === module) {
  main();
}
