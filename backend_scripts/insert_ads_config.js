require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY);

async function main() {
  const adsConfig = [
    { config_key: 'admob_banner_ad_id', config_value: 'ca-app-pub-4064462736581300/8496961361' },
    { config_key: 'admob_interstitial_ad_id', config_value: 'ca-app-pub-4064462736581300/1666313762' },
    { config_key: 'admob_rewarded_ad_id', config_value: 'ca-app-pub-4064462736581300/7273863668' }
  ];

  for (const item of adsConfig) {
    const { data, error } = await supabase
      .from('secure_remote_config')
      .upsert(item, { onConflict: 'config_key' });
    
    if (error) {
      console.error('Error inserting', item.config_key, error.message);
    } else {
      console.log('Inserted', item.config_key);
    }
  }
}

main();
