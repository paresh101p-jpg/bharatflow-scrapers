require('dotenv').config();
const { createClient } = require('@supabase/supabase-js');
const admin = require('firebase-admin');
const fs = require('fs');
const path = require('path');
const { translate } = require('@vitalets/google-translate-api');
const { updateCurrencyRates } = require('./update_currency');

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
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

// --- Caching Mechanism ---
const CACHE_FILE = path.join(__dirname, 'sent_alerts_cache.json');
let alertCache = { date: '', alerts: {} };

function loadCache() {
  const today = new Date().toISOString().split('T')[0];
  try {
    if (fs.existsSync(CACHE_FILE)) {
      const data = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
      if (data.date === today) {
        alertCache = data;
        return;
      }
    }
  } catch (e) {
    console.error("Cache read error:", e);
  }
  // If different day or error, reset cache
  alertCache = { date: today, alerts: {} };
  saveCache();
}

function saveCache() {
  try {
    fs.writeFileSync(CACHE_FILE, JSON.stringify(alertCache, null, 2));
  } catch (e) {
    console.error("Cache write error:", e);
  }
}

function hasSentToday(key) {
  return !!alertCache.alerts[key];
}

function markAsSentToday(key) {
  alertCache.alerts[key] = true;
  saveCache();
}

const SUPPORTED_LANGS = ['hi', 'gu', 'pa', 'mr', 'bn', 'te', 'ta', 'kn', 'ml', 'en'];

async function sendTranslatedAlert(title, body, topicBase, dataPayload) {
  const promises = SUPPORTED_LANGS.map(async (lang) => {
    let transTitle = title;
    let transBody = body;
    
    // We assume default text is mostly Hindi/English. Translate to other languages.
    if (lang !== 'hi') { 
      try {
        const resTitle = await translate(title, { to: lang });
        const resBody = await translate(body, { to: lang });
        transTitle = resTitle.text;
        transBody = resBody.text;
      } catch (e) {
        console.error(`Translation error for ${lang}:`, e.message);
      }
    }
    
    const topic = `${topicBase}_${lang}`;
    return admin.messaging().send({
      notification: { title: transTitle, body: transBody },
      data: dataPayload,
      topic: topic
    }).catch(e => console.error(`Error sending to topic ${topic}:`, e.message));
  });

  await Promise.allSettled(promises);
}

async function runWeatherAlerts() {
  console.log(`[${new Date().toISOString()}] Starting Weather Alert Engine...`);
  
  const { data: weatherData, error } = await supabase
    .from('india_weather_data')
    .select('location_name, temperature, precipitation_1h, forecast_14d, hourly_data');

  if (error || !weatherData) {
    console.error("Error fetching weather data:", error);
    return;
  }

  const nowUtc = new Date();
  const currentHourIST = new Date(nowUtc.getTime() + (5.5 * 60 * 60 * 1000)).getUTCHours();

  for (const loc of weatherData) {
    const city = loc.location_name;
    const topic = `weather_${city.replace(/[^a-zA-Z0-9]/g, '_')}`;

    // 1. Rain Alerts (10mm, 20mm, 30mm, 40mm, 50mm+)
    const rainNow = loc.precipitation_1h;
    if (rainNow >= 10) {
      let rainLevel = Math.floor(rainNow / 10) * 10;
      const rainKey = `weather_${city}_rain_${rainLevel}`;

      if (!hasSentToday(rainKey)) {
        let title = `🌧️ ${city}: बारिश अपडेट`;
        let body = `आपके क्षेत्र में ${rainLevel}mm से ज्यादा बारिश दर्ज की गई है (${rainNow} mm)।`;

        if (rainLevel >= 50) {
          title = `🚨 ${city}: भारी बारिश अलर्ट`;
          body = `आपके क्षेत्र में भारी बारिश (${rainNow} mm) हो रही है! सावधान रहें।`;
        }

        await sendTranslatedAlert(title, body, topic, { type: 'weather', city: city });
        
        console.log(`Sent Rain Alert (${rainLevel}mm) to ${topic}`);
        markAsSentToday(rainKey);
      }
    }

    // 1.5 Future Extreme Weather Forecast Warning (Morning IST)
    if (currentHourIST >= 6 && currentHourIST < 12 && loc.forecast_14d?.time) {
      for (let i = 0; i < loc.forecast_14d.time.length; i++) {
        const rain = loc.forecast_14d.precipitation_sum?.[i] || 0;
        const wind = loc.forecast_14d.wind_speed_10m_max?.[i] || 0;
        
        if (rain >= 50 || wind >= 60) {
          const targetDate = new Date(loc.forecast_14d.time[i]);
          const todayDate = new Date();
          targetDate.setHours(0,0,0,0);
          todayDate.setHours(0,0,0,0);
          
          const diffDays = Math.round((targetDate - todayDate) / (1000 * 60 * 60 * 24));
          const forecastKey = `weather_${city}_storm_${targetDate.toISOString().split('T')[0]}`;
          
          if (!hasSentToday(forecastKey)) {
            let dayText = diffDays === 0 ? "आज" : (diffDays === 1 ? "कल" : `${diffDays} दिन बाद`);
            const bodyText = `${dayText} भारी बारिश (${rain}mm) या तूफ़ान (${wind}km/h) की सम्भावना है! सतर्क रहें।`;
            
            await sendTranslatedAlert(`⚠️ ${city}: मौसम चेतावनी`, bodyText, topic, { type: 'weather', city: city });
            
            console.log(`Sent Forecast Warning for ${city} (${dayText})`);
            markAsSentToday(forecastKey);
          }
          break; // only send warning for the FIRST upcoming storm day
        }
      }
    }

    // 1.8 Rain Prediction (Next 2 hours)
    if (loc.hourly_data && loc.hourly_data.time) {
      const hTimes = loc.hourly_data.time;
      const hProbs = loc.hourly_data.precipitation_probability;
      
      // Find current hour index based on VPS UTC time
      const nowIso = new Date().toISOString().substring(0, 14) + '00'; // "2026-06-01T11:00"
      let currentIndex = hTimes.findIndex(t => t.startsWith(nowIso));
      if (currentIndex === -1) currentIndex = 0; // fallback
      
      // Check next 2 hours
      let willRain = false;
      for (let i = currentIndex; i <= currentIndex + 2 && i < hProbs.length; i++) {
        if (hProbs[i] > 50) {
          willRain = true;
          break;
        }
      }
      
      const rainPredKey = `weather_${city}_rain_pred_${new Date().toISOString().split('T')[0]}_${currentHourIST}`;
      if (willRain && !hasSentToday(rainPredKey)) {
        await sendTranslatedAlert(
          `🌧️ ${city}: बारिश की चेतावनी!`, 
          `अगले 2 घंटों में बारिश होने की संभावना है। कृपया सुरक्षित रहें!`, 
          topic, 
          { type: 'weather', city: city }
        );
        console.log(`Sent 2h Rain Prediction Alert for ${city}`);
        markAsSentToday(rainPredKey);
      }
    }

    // 2. Daily Updates (8 AM / 8 PM Min-Max & 4 PM Next Day)
    const todayMax = loc.forecast_14d?.temperature_2m_max?.[0] || loc.temperature;
    const todayMin = loc.forecast_14d?.temperature_2m_min?.[0] || loc.temperature;
    
    // 8 AM Update
    const morning8amKey = `weather_${city}_8am`;
    if (!hasSentToday(morning8amKey) && currentHourIST === 8) {
      await sendTranslatedAlert(
        `🌤️ ${city}: आज का मौसम`,
        `आज का अधिकतम तापमान ${todayMax}°C और न्यूनतम तापमान ${todayMin}°C रहेगा।`,
        topic,
        { type: 'weather', city: city }
      );
      console.log(`Sent 8 AM Weather Alert to ${topic}`);
      markAsSentToday(morning8amKey);
    } 

    // 8 PM Update
    const evening8pmKey = `weather_${city}_8pm`;
    if (!hasSentToday(evening8pmKey) && currentHourIST === 20) {
      await sendTranslatedAlert(
        `🌙 ${city}: आज का मौसम`,
        `आज का अधिकतम तापमान ${todayMax}°C और न्यूनतम तापमान ${todayMin}°C दर्ज किया गया।`,
        topic,
        { type: 'weather', city: city }
      );
      console.log(`Sent 8 PM Weather Alert to ${topic}`);
      markAsSentToday(evening8pmKey);
    }
    
    // 4 PM Next Day Update
    const evening4pmKey = `weather_${city}_4pm`;
    if (!hasSentToday(evening4pmKey) && currentHourIST >= 16 && currentHourIST < 20) {
      const tomorrowMax = loc.forecast_14d?.temperature_2m_max?.[1] || loc.temperature;
      const tomorrowMin = loc.forecast_14d?.temperature_2m_min?.[1] || loc.temperature;
      await sendTranslatedAlert(
        `🌅 ${city}: कल का मौसम अपडेट`,
        `कल का अधिकतम तापमान ${tomorrowMax}°C और न्यूनतम तापमान ${tomorrowMin}°C रहने की संभावना है।`,
        topic,
        { type: 'weather', city: city }
      );
      console.log(`Sent 4 PM Next Day Alert to ${topic}`);
      markAsSentToday(evening4pmKey);
    }

    // 9 PM Tomorrow's Rain Schedule Alert
    const night9pmKey = `weather_${city}_9pm_rain_sched`;
    if (!hasSentToday(night9pmKey) && currentHourIST === 21 && loc.hourly_data?.time) {
      const hTimes = loc.hourly_data.time;
      const hProbs = loc.hourly_data.precipitation_probability;
      
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const tomorrowDateStr = tomorrow.toISOString().split('T')[0];
      
      let rainHours = [];
      for (let i = 0; i < hTimes.length; i++) {
        if (hTimes[i].startsWith(tomorrowDateStr) && hProbs[i] > 50) {
           let [hStr] = hTimes[i].split('T')[1].split(':');
           let h = parseInt(hStr);
           let ampm = h >= 12 ? 'PM' : 'AM';
           h = h % 12 || 12;
           rainHours.push(`${h} ${ampm}`);
        }
      }
      
      if (rainHours.length > 0) {
        // Group consecutive hours if too many, but for now just list them
        const formattedHours = rainHours.join(', ');
        await sendTranslatedAlert(
          `🌧️ ${city}: कल की बारिश का अलर्ट`,
          `कल इन समयों पर बारिश हो सकती है: ${formattedHours} बजे।`,
          topic,
          { type: 'weather', city: city }
        );
        console.log(`Sent 9 PM Tomorrow Rain Schedule to ${topic}`);
      }
      // Mark sent even if no rain so it doesn't try again today
      markAsSentToday(night9pmKey);
    }
  }
}

async function runMandiAlerts() {
  console.log(`[${new Date().toISOString()}] Starting Mandi Alert Engine...`);
  
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const { data: prices, error } = await supabase
    .from('mandi_prices')
    .select('district, mandi_name, commodity_name, modal_price')
    .eq('arrival_date', todayStr)
    .order('modal_price', { ascending: false })
    .limit(100);

  if (error || !prices || prices.length === 0) return;

  const districtAlerts = {};
  for (const price of prices) {
    const dist = (price.district || 'Unknown').toLowerCase().replace(/\s+/g, '_');
    if (!districtAlerts[dist]) districtAlerts[dist] = [];
    if (districtAlerts[dist].length < 3) districtAlerts[dist].push(price);
  }

  for (const [dist, items] of Object.entries(districtAlerts)) {
    if (dist === 'unknown') continue;
    const mandiKey = `mandi_${dist}`;
    if (hasSentToday(mandiKey)) continue;

    const topic = `mandi_${dist}`;
    const mainItem = items[0];
    
    await sendTranslatedAlert(
      `🌾 ${mainItem.district.toUpperCase()} मंडी भाव अपडेट`,
      `${mainItem.commodity_name} का ताज़ा भाव ₹${mainItem.modal_price}/Quintal (${mainItem.mandi_name} मंडी)।`,
      topic,
      { type: 'mandi', district: mainItem.district }
    );
    
    console.log(`Sent Mandi Alert for ${dist}`);
    markAsSentToday(mandiKey);
  }
}

async function runFestivalAlerts() {
  const festivals = {
    "01-14": { title: "मकर संक्रांति की शुभकामनाएँ! 🪁", body: "भारत के सभी किसानों को मकर संक्रांति, पोंगल और लोहड़ी की हार्दिक शुभकामनाएँ।" },
    "04-13": { title: "बैसाखी की शुभकामनाएँ! 🌾", body: "किसानों का पर्व बैसाखी आपके जीवन में खुशहाली लाये।" },
    "10-31": { title: "दीपावली की हार्दिक शुभकामनाएँ! 🪔", body: "भारत फ्लो की तरफ से शुभ दीपावली! लक्ष्मी माता आपके खेतों को धन-धान्य से भर दें।" },
  };

  const today = new Date();
  const mm_dd = `${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  const festivalKey = `festival_${mm_dd}`;
  
  if (festivals[mm_dd] && today.getHours() === 7) { 
    if (!hasSentToday(festivalKey)) {
      await sendTranslatedAlert(
        festivals[mm_dd].title,
        festivals[mm_dd].body,
        'festivals', // topic base
        { type: 'festival' }
      );
      console.log(`Sent Festival Alert for ${mm_dd}`);
      markAsSentToday(festivalKey);
    }
  }
}

async function runKisanMarketAlerts() {
  console.log(`[${new Date().toISOString()}] Starting Kisan Market Matcher (Queue Based)...`);
  
  const { data: matches, error } = await supabase
    .from('store_matches')
    .select('id, matched_user_id, commodity, district, type, seller_name')
    .eq('is_sent', false)
    .limit(50);

  if (error || !matches || matches.length === 0) return;

  for (const match of matches) {
    const { data: profileData } = await supabase
      .from('profiles')
      .select('fcm_token')
      .eq('id', match.matched_user_id)
      .single();
      
    if (profileData && profileData.fcm_token) {
      const title = match.type === 'SELL' ? '🎉 नया विक्रेता मिला!' : '🎉 नया खरीदार मिला!';
      const body = match.type === 'SELL' 
        ? `${match.district} में ${match.commodity} के लिए नया विक्रेता (${match.seller_name}) उपलब्ध है। अभी संपर्क करें!`
        : `${match.district} में ${match.commodity} के लिए नया खरीदार (${match.seller_name}) उपलब्ध है। अभी संपर्क करें!`;

      await admin.messaging().send({
        notification: { title, body },
        data: { type: 'store_match', commodity: match.commodity },
        token: profileData.fcm_token
      }).catch(e => console.error("FCM Error for Match:", e));
      
      console.log(`Notified user ${match.matched_user_id} about match for ${match.commodity}`);
    }
    
    // Mark as sent
    await supabase.from('store_matches').update({ is_sent: true }).eq('id', match.id);
  }
}

async function runFuelAlerts() {
  console.log(`[${new Date().toISOString()}] Starting Fuel Alert Engine...`);
  
  const today = new Date().toISOString().split('T')[0];
  const { data: currentPrices, error } = await supabase
    .from('fuel_prices')
    .select('*')
    .gte('updated_at', today + 'T00:00:00Z');

  if (error || !currentPrices || currentPrices.length === 0) return;

  for (const priceRow of currentPrices) {
    const city = priceRow.city;
    const safeCity = city.toLowerCase().replace(/[^a-z0-9]/g, '');
    const fuelKey = `fuel_prices_update_${safeCity}_${today}`;
    
    if (hasSentToday(fuelKey)) continue;

    // Check history for the last previous price to see if it actually changed
    const { data: history } = await supabase
      .from('fuel_price_history')
      .select('petrol, diesel')
      .eq('city', city)
      .lt('recorded_at', today + 'T00:00:00Z')
      .order('recorded_at', { ascending: false })
      .limit(1);

    let priceChanged = true; // Default to true for the first time
    if (history && history.length > 0) {
      const prev = history[0];
      if (prev.petrol === priceRow.petrol && prev.diesel === priceRow.diesel) {
         priceChanged = false;
      }
    }

    if (priceChanged) {
      const topic = `fuel_update_${safeCity}`;
      await sendTranslatedAlert(
        `⛽ ${city} में पेट्रोल-डीज़ल के नए दाम`,
        `पेट्रोल: ₹${priceRow.petrol}/Ltr | डीज़ल: ₹${priceRow.diesel}/Ltr। नए दाम अपडेट हो गए हैं!`,
        topic,
        { type: 'fuel', city: city }
      );
      console.log(`Sent Fuel Alert for ${city} to topic ${topic}`);
    }
    
    // Always mark as processed so we don't query history repeatedly today
    markAsSentToday(fuelKey);
  }
}

async function runCurrencyAlerts() {
  console.log(`[${new Date().toISOString()}] Starting Currency Alert Engine...`);
  const today = new Date().toISOString().split('T')[0];
  
  const currencyKey = `currency_alerts_${today}`;
  if (hasSentToday(currencyKey)) return;

  // Fetch the latest 2 records for USD to calculate change
  const { data: rates, error } = await supabase
    .from('currency_history')
    .select('currency_code, rate_to_inr, recorded_date')
    .eq('currency_code', 'USD')
    .order('recorded_date', { ascending: false })
    .limit(2);

  if (error || !rates || rates.length === 0) return;

  const currentUsd = rates[0].rate_to_inr;
  let bodyText = `USD: ₹${currentUsd.toFixed(2)}`;

  if (rates.length > 1) {
    const prevUsd = rates[1].rate_to_inr;
    const diff = currentUsd - prevUsd;
    const pct = (diff / prevUsd) * 100;
    
    // Formatting sign
    const sign = diff > 0 ? '+' : (diff < 0 ? '-' : '');
    const absDiff = Math.abs(diff);
    const absPct = Math.abs(pct);
    bodyText += ` | ${sign}Rs. ${absDiff.toFixed(2)} ${sign}${absPct.toFixed(2)}%`;
  }

  bodyText += ` | डॉलर और अन्य 50+ मुद्राओं के लाइव रेट्स अभी चेक करें।`;

  await sendTranslatedAlert(
    `💱 विदेशी मुद्रा के ताज़ा रेट्स`,
    bodyText,
    'currency_alerts',
    { type: 'currency' }
  );

  console.log(`Sent Currency Alert for ${today}`);
  markAsSentToday(currencyKey);
}

async function runNewsAlerts() {
  console.log(`[${new Date().toISOString()}] Starting News Alert Engine...`);
  const nowUtc = new Date();
  const istTime = new Date(nowUtc.getTime() + (5.5 * 60 * 60 * 1000));
  const currentHourIST = istTime.getUTCHours();
  const currentMinuteIST = istTime.getUTCMinutes();
  
  // Morning News (8:30 AM)
  const morningNewsKey = `news_alert_8_30am`;
  if (currentHourIST === 8 && currentMinuteIST >= 30 && !hasSentToday(morningNewsKey)) {
    const { data: news, error } = await supabase.from('app_news').select('*').order('published_at', { ascending: false }).limit(1);
    if (!error && news && news.length > 0) {
      const title = news[0].title || '';
      const cleanTitle = title.replace(/<[^>]*>/g, '').substring(0, 100);
      await sendTranslatedAlert(
        `📰 ताज़ा ख़बर: ${cleanTitle}`,
        `कृषि जगत की आज की बड़ी खबर! पूरी जानकारी के लिए टैप करें।`,
        'news_alerts',
        { type: 'news', url: news[0].source_url }
      );
      console.log(`Sent Morning News Alert (8:30 AM)`);
      markAsSentToday(morningNewsKey);
    }
  }

  // Evening News (9:00 PM)
  const eveningNewsKey = `news_alert_9pm`;
  if (currentHourIST === 21 && !hasSentToday(eveningNewsKey)) {
    const { data: news, error } = await supabase.from('app_news').select('*').order('published_at', { ascending: false }).limit(2);
    if (!error && news && news.length > 0) {
      const title = news[0].title || '';
      const cleanTitle = title.replace(/<[^>]*>/g, '').substring(0, 100);
      await sendTranslatedAlert(
        `📰 रात की ख़बर: ${cleanTitle}`,
        `मंडी और खेती की नई अपडेट्स। अभी पढ़ें!`,
        'news_alerts',
        { type: 'news', url: news[0].source_url }
      );
      console.log(`Sent Evening News Alert (9:00 PM)`);
      markAsSentToday(eveningNewsKey);
    }
  }
}

async function main() {
  loadCache();
  await runWeatherAlerts();
  await runMandiAlerts();
  await runFuelAlerts();
  // Auto-update currency rates from live API before sending alerts
  await updateCurrencyRates().catch(e => console.error('[CURRENCY UPDATE] Auto-update failed:', e.message));
  await runCurrencyAlerts();
  await runNewsAlerts();
  await runFestivalAlerts();
  await runKisanMarketAlerts();
  console.log(`[${new Date().toISOString()}] All Alert Engines Completed.`);
  process.exit(0);
}

main().catch(console.error);
