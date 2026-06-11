require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');
const admin = require('firebase-admin');
const Parser = require('rss-parser');
const axios = require('axios');
const fs = require('fs');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
const GOVT_API_KEY = process.env.GOVT_API_KEY; // GNews API key might be here or we need to add it

const serviceAccount = require('./firebase-admin.json');

// Initialize Firebase Admin
if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
  });
}

const WebSocket = require('ws');
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
  auth: { persistSession: false },
  realtime: { transport: WebSocket },
});

const parser = new Parser();

async function syncNews() {
  console.log(`[${new Date().toISOString()}] Starting News Sync...`);
  let newArticlesCount = 0;
  let latestArticle = null;

  const rssSources = [
    'https://news.google.com/rss/search?q=kisan+kheti+mandi+when:24h&hl=hi&gl=IN&ceid=IN:hi',
    'https://hindi.krishijagran.com/rss/news/',
    'https://www.jagran.com/rss/news/business_agriculture.xml',
    'https://www.gaonconnection.com/feed'
  ];

  for (const url of rssSources) {
    try {
      const feed = await parser.parseURL(url);
      for (let i = 0; i < Math.min(feed.items.length, 10); i++) {
        const item = feed.items[i];
        const title = item.title ? item.title.trim() : '';
        const link = item.link ? item.link.trim() : '';
        const content = item.contentSnippet || item.content || item.description || title;
        
        let summary = content.replace(/<[^>]*>?/gm, '').trim();
        if (summary.length > 300) summary = summary.substring(0, 297) + '...';

        if (title && link) {
          const { data, error } = await supabase.from('app_news').upsert({
            title: title,
            summary: summary || title,
            content: summary,
            source_url: link,
            published_at: item.pubDate ? new Date(item.pubDate).toISOString() : new Date().toISOString(),
          }, { onConflict: 'source_url' }).select();

          if (!error && data && data.length > 0) {
            // Check if it was actually inserted (if we keep track of old vs new, but upsert might return even if updated)
            // For simplicity, we just keep track of the first successful insert.
            if (!latestArticle) {
              latestArticle = data[0];
            }
            newArticlesCount++;
          }
        }
      }
    } catch (e) {
      console.error(`Error fetching RSS from ${url}:`, e.message);
    }
  }

  // Optional: Fetch from GNews if needed, but RSS is free and limitless.
  // We'll stick to RSS to save API keys.

  console.log(`[${new Date().toISOString()}] Synced ${newArticlesCount} articles.`);

  // Send FCM Notification if we have at least one article
  if (latestArticle) {
    try {
      const message = {
        notification: {
          title: "📢 ताज़ा खबर: " + latestArticle.title.substring(0, 50),
          body: latestArticle.summary.substring(0, 100) + "...\n• पूरा पढ़ने के लिए टैप करें।",
        },
        data: {
          type: 'news',
          url: latestArticle.source_url
        },
        topic: 'news_updates' // All Flutter users should subscribe to this topic
      };

      const response = await admin.messaging().send(message);
      console.log('Successfully sent message:', response);
    } catch (error) {
      console.error('Error sending message:', error);
    }
  }
}

syncNews().catch(console.error);
