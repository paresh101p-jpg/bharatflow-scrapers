require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

async function alterTable() {
  // Using RPC to execute raw SQL (if rpc 'exec_sql' exists, or similar)
  // Wait, Supabase JS client doesn't support raw SQL like ALTER TABLE.
  // We need to use the REST API or write a quick SQL script and run it through the Supabase Dashboard.
  console.log("Please run the following SQL manually in Supabase SQL Editor:");
  console.log("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS fcm_token text;");
  console.log("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS notifications_on boolean DEFAULT true;");
}

alterTable();
