require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);
async function main() {
  const {data, error} = await supabase.from('mandi_prices').select('commodity_name').ilike('commodity_name', '%').limit(5000);
  const names = [...new Set(data.map(d => d.commodity_name))];
  console.log("Total unique:", names.length);
  console.log(names.filter(n => n.includes('-') || n.includes('Raw')));
}
main();
