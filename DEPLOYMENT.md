# Railway Deployment Guide

Complete step-by-step guide to deploy Sports Arbitrage Alert System to Railway.

---

## Prerequisites

- ✅ GitHub account
- ✅ Railway account (sign up at [railway.app](https://railway.app))
- ✅ All environment variables from `.env` file

---

## Step 1: Push to GitHub

### Create a new repository:

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit - Sports Arb Alert System"

# Create a new repository on GitHub (https://github.com/new)
# Then link it:
git remote add origin https://github.com/YOUR_USERNAME/sports-arb.git
git branch -M main
git push -u origin main
```

**Important:** Make sure `.env` is in `.gitignore` (it is!) - never commit secrets.

---

## Step 2: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click **"Login"** → Sign in with GitHub
3. Click **"New Project"**
4. Select **"Deploy from GitHub repo"**
5. Choose your `sports-arb` repository
6. Railway will auto-detect it's a Python project

**Railway will automatically:**
- ✅ Install dependencies from `requirements.txt`
- ✅ Use Python 3.12 (from `.python-version`)
- ✅ Run `python3 main.py` (from `railway.json`)

---

## Step 3: Configure Environment Variables

1. In Railway dashboard → Your project → **Variables** tab
2. Click **"Raw Editor"**
3. Paste all your environment variables:

```bash
# The Odds API
ODDS_API_KEY=your_actual_odds_api_key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_actual_supabase_anon_key

# Discord
DISCORD_BOT_TOKEN=your_actual_discord_bot_token
DISCORD_GUILD_ID=your_actual_guild_id
DISCORD_FREE_CHANNEL_ID=your_actual_free_channel_id
DISCORD_PREMIUM_CHANNEL_ID=your_actual_premium_channel_id
DISCORD_PREMIUM_ROLE_ID=your_actual_premium_role_id

# Telegram
TELEGRAM_BOT_TOKEN=your_actual_telegram_bot_token
TELEGRAM_FREE_CHANNEL_ID=your_actual_free_channel_id
TELEGRAM_PREMIUM_CHANNEL_ID=your_actual_premium_channel_id
TELEGRAM_PREMIUM_INVITE_LINK=https://t.me/joinchat/your_invite_link

# Stripe
STRIPE_SECRET_KEY=sk_live_your_actual_stripe_key
STRIPE_PRICE_ID=price_your_actual_price_id
STRIPE_WEBHOOK_SECRET=whsec_CHANGE_THIS_AFTER_WEBHOOK_SETUP
STRIPE_SUCCESS_URL=https://RAILWAY_DOMAIN_HERE/success
STRIPE_CANCEL_URL=https://RAILWAY_DOMAIN_HERE/cancel
```

4. Click **"Save"**

**Note:** We'll update `STRIPE_WEBHOOK_SECRET` and the URLs in the next steps.

---

## Step 4: Generate Railway Domain

1. In Railway → **Settings** tab
2. Scroll to **"Networking"** section
3. Click **"Generate Domain"**
4. Railway will give you a URL like: `https://sports-arb-production-abc123.up.railway.app`
5. **Copy this URL** - you'll need it for Stripe

---

## Step 5: Update Stripe URLs

1. Go back to **Variables** tab
2. Update these variables with your Railway domain:

```bash
STRIPE_SUCCESS_URL=https://your-app.up.railway.app/success
STRIPE_CANCEL_URL=https://your-app.up.railway.app/cancel
```

3. Click **"Save"**

---

## Step 6: Setup Stripe Webhook

### Create webhook endpoint:

1. Go to [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click **"Add endpoint"**
3. Enter your **Endpoint URL**:
   ```
   https://your-app.up.railway.app/webhook
   ```
4. Click **"Select events"**
5. Choose these 2 events:
   - ✅ `checkout.session.completed`
   - ✅ `customer.subscription.deleted`
6. Click **"Add events"**
7. Click **"Add endpoint"**

### Get webhook signing secret:

1. Click on your newly created webhook endpoint
2. Scroll to **"Signing secret"**
3. Click **"Reveal"** or copy the secret (starts with `whsec_`)
4. Copy this secret

### Update Railway environment variable:

1. Back in Railway → **Variables** tab
2. Update:
   ```bash
   STRIPE_WEBHOOK_SECRET=whsec_your_actual_secret_from_stripe
   ```
3. Click **"Save"**

The app will automatically redeploy with the new variables.

---

## Step 7: Verify Deployment

### Check logs:

1. In Railway → **Deployments** tab
2. Click on the latest deployment
3. Check the logs - you should see:

```
✓ Flask webhook server thread started
✓ Telegram bot thread started
✓ Discord bot thread started
All systems ready. Starting polling loop...
```

### Test endpoints:

```bash
# Health check
curl https://your-app.up.railway.app/health
# Should return: {"status":"healthy"}

# Success page
# Visit in browser: https://your-app.up.railway.app/success

# Cancel page
# Visit in browser: https://your-app.up.railway.app/cancel
```

### Test webhook:

1. In Stripe Dashboard → Webhooks → Your endpoint
2. Click **"Send test webhook"**
3. Choose `checkout.session.completed`
4. Check Railway logs - you should see the event received

---

## Step 8: Test the Full Flow

1. **Test Discord `/subscribe`:**
   - In your Discord server, type `/subscribe`
   - You should get an ephemeral message with a Stripe link
   - Complete checkout with test card: `4242 4242 4242 4242`
   - Should redirect to your success page
   - Check Railway logs for webhook event

2. **Test Telegram `/subscribe`:**
   - In Telegram, send `/subscribe` to your bot
   - Get Stripe link, complete checkout
   - Should redirect to success page

3. **Verify alerts work:**
   - Wait for next polling cycle (10 minutes)
   - Or check logs to see if polling is working
   - Alerts should appear in your Discord/Telegram channels

---

## Troubleshooting

### App won't start:
- Check Railway logs for errors
- Verify all environment variables are set
- Check Python version (should be 3.12)

### Webhook not working:
- Verify webhook URL is correct in Stripe
- Check that `STRIPE_WEBHOOK_SECRET` matches Stripe
- Test webhook signature in Railway logs

### Bots not responding:
- Verify bot tokens are correct
- Check that bots have proper permissions
- Check Discord bot has slash commands enabled
- Check Telegram bot is admin in channels

### API rate limits:
- Check Odds API usage in logs
- Using 8 calls per poll × 6 polls/hour = 48 calls/hour

---

## Monitoring

### View logs:
- Railway dashboard → Click on service → Logs tab
- Filter by error/warning if needed

### Check API usage:
- The Odds API: Check remaining requests in logs
- Supabase: Check dashboard for query usage
- Stripe: Check dashboard for events

### Restart service:
- Railway dashboard → Click on service → Settings
- Scroll to "Danger Zone" → Restart

---

## Updating Your App

### Deploy changes:

```bash
# Make your changes locally
git add .
git commit -m "Description of changes"
git push

# Railway automatically redeploys!
```

Railway will:
1. Pull latest code from GitHub
2. Install dependencies
3. Restart the app
4. Keep environment variables

---

## Free Tier Limits

Railway free tier includes:
- ✅ $5 credit per month
- ✅ 512MB RAM
- ✅ 1GB disk
- ✅ Unlimited builds/deploys

Your app should easily fit within free tier limits!

---

## Next Steps

After deployment:
1. ✅ Set up Supabase `subscriptions` table (see README.md)
2. ✅ Test subscription flow end-to-end
3. ✅ Monitor logs for first few hours
4. ✅ Set up Stripe in production mode (when ready)

---

## Support

- Railway docs: https://docs.railway.app
- Your app: Check logs in Railway dashboard
- Stripe: https://stripe.com/docs/webhooks
