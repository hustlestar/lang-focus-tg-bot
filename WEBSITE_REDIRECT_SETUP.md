# Website Redirect Setup for Product Links

## Overview
Create clean redirect URLs that track analytics before sending users to Chrome Web Store or Telegram.

## URLs to Create

1. **Exchange Rates Pro**: `https://overx.ai/go/exchange-rates`
   - Redirects to: Chrome Web Store listing for Exchange Rates Pro

2. **Site Blocker**: `https://overx.ai/go/site-blocker`
   - Redirects to: Chrome Web Store listing for Block Website

3. **Law Bot**: `https://overx.ai/go/law-bot`
   - Redirects to: `https://t.me/belarus_law_support_bot`

## Implementation Options

### Option 1: Server-Side (Node.js/Express)

```javascript
// routes/redirects.js
const express = require('express');
const router = express.Router();
const { GA4 } = require('google-analytics-data');

// Initialize GA4
const analytics = new GA4({
  propertyId: 'YOUR-GA4-PROPERTY-ID',
  credentials: require('./ga4-credentials.json')
});

const redirects = {
  'exchange-rates': {
    url: 'https://chrome.google.com/webstore/detail/YOUR-EXCHANGE-RATES-ID',
    name: 'Exchange Rates Pro'
  },
  'site-blocker': {
    url: 'https://chrome.google.com/webstore/detail/YOUR-SITE-BLOCKER-ID',
    name: 'Block Website'
  },
  'law-bot': {
    url: 'https://t.me/belarus_law_support_bot',
    name: 'Belarus Law Support Bot'
  }
};

router.get('/go/:product', async (req, res) => {
  const product = req.params.product;
  const destination = redirects[product];

  if (!destination) {
    return res.status(404).send('Product not found');
  }

  // Track event in GA4
  try {
    await analytics.runReport({
      dimensions: [{ name: 'eventName' }],
      metrics: [{ name: 'eventCount' }],
      dateRanges: [{ startDate: 'today', endDate: 'today' }],
      dimensionFilter: {
        filter: {
          fieldName: 'eventName',
          stringFilter: {
            value: 'bot_product_redirect'
          }
        }
      },
      customEvents: [{
        name: 'bot_product_redirect',
        parameters: {
          product_id: product,
          product_name: destination.name,
          source: 'lang_focus_bot',
          medium: 'telegram',
          timestamp: new Date().toISOString()
        }
      }]
    });
  } catch (error) {
    console.error('GA4 tracking error:', error);
  }

  // Redirect user
  res.redirect(301, destination.url);
});

module.exports = router;
```

### Option 2: Client-Side HTML/JavaScript

Create files in `/go/` directory:

```html
<!-- /go/exchange-rates/index.html -->
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Перенаправление на Exchange Rates Pro</title>

  <!-- Google Analytics 4 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-YOUR-ID"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-YOUR-ID');
  </script>

  <script>
    // Track the event
    gtag('event', 'bot_product_click', {
      'event_category': 'telegram_bot',
      'event_label': 'exchange_rates',
      'product_name': 'Exchange Rates Pro',
      'traffic_source': 'lang_focus_bot',
      'traffic_medium': 'telegram'
    });

    // Redirect after a brief delay to ensure tracking
    setTimeout(() => {
      window.location.href = 'https://chrome.google.com/webstore/detail/YOUR-EXTENSION-ID';
    }, 200);
  </script>

  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
    }
    .container {
      text-align: center;
    }
    .spinner {
      border: 3px solid rgba(255,255,255,0.3);
      border-radius: 50%;
      border-top: 3px solid white;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div class="container">
    <h2>Перенаправление на Exchange Rates Pro</h2>
    <div class="spinner"></div>
    <p>Переходим в Chrome Web Store...</p>
  </div>
</body>
</html>
```

### Option 3: Using Cloudflare Workers (Edge)

```javascript
// cloudflare-worker.js
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

const redirects = {
  '/go/exchange-rates': 'https://chrome.google.com/webstore/detail/YOUR-ID',
  '/go/site-blocker': 'https://chrome.google.com/webstore/detail/YOUR-ID',
  '/go/law-bot': 'https://t.me/belarus_law_support_bot'
};

async function handleRequest(request) {
  const url = new URL(request.url);
  const path = url.pathname;

  if (redirects[path]) {
    // Log to GA4 using Measurement Protocol
    await logToGA4(path, request);

    // Return redirect
    return Response.redirect(redirects[path], 301);
  }

  return new Response('Not Found', { status: 404 });
}

async function logToGA4(path, request) {
  const GA4_MEASUREMENT_ID = 'G-YOUR-ID';
  const GA4_API_SECRET = 'YOUR-API-SECRET';

  const payload = {
    client_id: crypto.randomUUID(),
    events: [{
      name: 'bot_redirect',
      params: {
        page_path: path,
        page_referrer: request.headers.get('Referer') || 'telegram',
        product: path.split('/').pop()
      }
    }]
  };

  await fetch(`https://www.google-analytics.com/mp/collect?measurement_id=${GA4_MEASUREMENT_ID}&api_secret=${GA4_API_SECRET}`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}
```

## Google Analytics 4 Setup

### 1. Enable Measurement Protocol
1. Go to GA4 Admin → Data Streams → Your Web Stream
2. Click "Measurement Protocol API secrets"
3. Create a new secret

### 2. Create Custom Events
In GA4, create custom dimensions for better tracking:
- `product_name` - The product being redirected to
- `traffic_source` - Source of traffic (lang_focus_bot)
- `traffic_medium` - Medium (telegram)

### 3. Create Reports
Set up custom reports to track:
- Total clicks per product
- Conversion funnel (bot → redirect → install)
- Time-based trends
- User segments

## Benefits

1. **Clean URLs**: No visible UTM parameters
2. **Better Analytics**: Track exactly which products get clicked
3. **Flexibility**: Can update destination URLs without updating bot
4. **A/B Testing**: Can test different landing pages
5. **Fallback**: Can show a landing page if Chrome Store is down

## Testing

1. Create the redirect endpoints
2. Test each URL manually
3. Check GA4 Real-time reports
4. Verify events are being logged correctly

## Monitoring

Monitor in GA4:
- **Real-time**: See immediate clicks
- **Events**: Track bot_redirect events
- **Conversions**: Set up conversion goals
- **User Flow**: See the complete journey