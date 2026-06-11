require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');
const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

async function test() {
  const { data: currencies } = await supabase.from('currencies').select('*');
  console.log('Currencies:', currencies);
  const { data: history } = await supabase.from('currency_history').select('*').limit(5);
  console.log('History:', history);
}
test();
