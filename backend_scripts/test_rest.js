require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

async function main() {
  console.time('Fetch');
  const { data, error } = await supabase.from('mandi_prices')
    .select('commodity_name, arrival_date, modal_price')
    .order('arrival_date', { ascending: false })
    .limit(5000);
  console.timeEnd('Fetch');
  
  if (error) return console.log(error);
  
  const latestMap = {};
  for (const row of data) {
    if (!latestMap[row.commodity_name]) {
      latestMap[row.commodity_name] = { date: row.arrival_date, price: row.modal_price };
    }
  }
  
  console.log(`Found latest dates for ${Object.keys(latestMap).length} commodities.`);
  console.log("Gur(Jaggery):", latestMap['Gur(Jaggery)']);
}
main();
