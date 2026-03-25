# 🏆 Sports Arbitrage Alert System

Polls live odds via [The Odds API](https://the-odds-api.com), detects arbitrage opportunities across bookmakers, and fires real-time alerts to **Discord** and **Telegram** simultaneously.

---

## Features

- ✅ Polls all active US sports every **10 minutes** (free tier safe)
- ✅ Detects arbs across **all bookmakers** for **moneyline & spreads**
- ✅ Only alerts on margins **≥ 1.5%** (skips > 15% as likely data errors)
- ✅ Calculates **optimal stake split** for a $100 base bet
- ✅ Rich **Discord embeds** + clean **Telegram markdown** alerts
- ✅ Emoji indicator: 🟢 3%+ · 🟡 2–3% · ⚪ under 2%
- ✅ Full **timestamped logging** with API usage tracking
- 💎 **Premium subscription system** via Stripe
  - Free users: moneyline (h2h) alerts only
  - Premium users: all markets (h2h, spreads, totals)
  - `/subscribe` commands in Discord & Telegram
  - Automatic premium channel access management

---

## Project Structure

```
sports_arb/
├── main.py                  # Entry point with multi-threaded architecture
├── server.py                # Flask webhook server for Stripe events
├── requirements.txt
├── .env.example             # Copy to .env and fill in keys
├── logs/                    # Auto-created log files
├── data/                    # SQLite database for subscriptions
│   └── subscriptions.db
└── src/
    ├── odds_fetcher.py      # Pulls odds from The Odds API
    ├── arb_calculator.py    # Detects arbs & calculates stakes
    ├── discord_alerter.py   # Discord alerts + slash commands
    ├── telegram_alerter.py  # Telegram alerts + command handlers
    ├── billing.py           # SQLite subscription management
    └── logger_setup.py      # Configures file + console logging
```

---

## Setup

### 1. Clone & install dependencies

```bash
git clone <your-repo-url>
cd sports_arb
pip install -r requirements.txt
```

### 2. Configure your `.env` file

```bash
cp .env.example .env
```

Then open `.env` and fill in all five keys (see below).

### 3. Run

```bash
python main.py
```

---

## Getting API Keys

### 🔑 The Odds API
1. Go to [https://the-odds-api.com](https://the-odds-api.com) and sign up for a free account.
2. You'll receive an API key on your dashboard.
3. Free tier gives **500 requests/month**. Polling every 10 minutes with ~10 sports uses ~4,320 requests/month — consider reducing sports or polling to every 30 min if needed.
4. Add to `.env` as `ODDS_API_KEY`.

### 🤖 Discord Bot
1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**.
2. Go to **Bot** → **Add Bot** → copy the **Token**. Add as `DISCORD_BOT_TOKEN`.
3. Under **Bot** → **Privileged Gateway Intents**, enable:
   - ✅ Server Members Intent (required for role assignment)
4. Under **OAuth2 → URL Generator**, select scopes:
   - `bot`
   - `applications.commands` (for slash commands)
5. Select bot permissions:
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Manage Roles (for premium subscriptions)
6. Use the generated URL to invite the bot to your server.
7. **Get IDs** (enable Developer Mode in Discord User Settings → Advanced):
   - Right-click server → Copy Server ID → Add as `DISCORD_GUILD_ID`
   - Right-click free channel → Copy Channel ID → Add as `DISCORD_FREE_CHANNEL_ID`
   - Create a premium channel and role (see Stripe Setup section below)

### 📲 Telegram Bot
1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, follow the prompts, and copy the **HTTP API token**. Add as `TELEGRAM_BOT_TOKEN`.
3. **Create two channels**: one for free users, one for premium
   - Add the bot as an **Administrator** to both channels
4. To get channel IDs: forward a message from each channel to [@userinfobot](https://t.me/userinfobot). The IDs will be negative numbers like `-1001234567890`. Add as `TELEGRAM_FREE_CHANNEL_ID` and `TELEGRAM_PREMIUM_CHANNEL_ID`.
5. Create an invite link for the premium channel (Channel Settings → Invite Link). Add as `TELEGRAM_PREMIUM_INVITE_LINK`.

---

## Stripe Setup (Premium Subscriptions)

### 1. Create Stripe Product

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/products)
2. Click **"Add product"**
3. Fill in:
   - **Name**: "Sports Arbitrage Premium"
   - **Pricing**: Recurring, monthly (e.g., $19.99/month)
   - **Payment type**: Subscription
4. Click **"Add product"** to create
5. Copy the **Price ID** (starts with `price_`) from the pricing section
6. Add to `.env` as `STRIPE_PRICE_ID`

### 2. Get Stripe API Keys

1. Go to [Developers → API Keys](https://dashboard.stripe.com/apikeys)
2. Copy the **Secret key** (starts with `sk_test_` for test mode or `sk_live_` for production)
3. Add to `.env` as `STRIPE_SECRET_KEY`

**⚠️ Important**: Never commit your secret key to version control!

### 3. Setup Webhook Endpoint

#### Development (Local Testing)

1. Install Stripe CLI:
   ```bash
   brew install stripe/stripe-cli/stripe
   # Or for other OS: https://stripe.com/docs/stripe-cli
   ```

2. Login to Stripe CLI:
   ```bash
   stripe login
   ```

3. Forward webhooks to your local server:
   ```bash
   stripe listen --forward-to localhost:5000/webhook
   ```

4. Copy the **webhook signing secret** (starts with `whsec_`) from the terminal output
5. Add to `.env` as `STRIPE_WEBHOOK_SECRET`

#### Production (Live Server)

1. Go to [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click **"Add endpoint"**
3. Enter your webhook URL: `https://yourdomain.com/webhook`
4. Select events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
5. Click **"Add endpoint"**
6. Copy the **Signing secret** from the webhook details page
7. Add to your production `.env` as `STRIPE_WEBHOOK_SECRET`

### 4. Setup Premium Channels

#### Discord Premium Setup

1. **Create two channels** in your Discord server:
   - `#free-alerts` - for moneyline (h2h) alerts
   - `#premium-alerts` - for all market types

2. **Create a premium role**:
   - Server Settings → Roles → Create Role
   - Name it "Premium Subscriber"
   - Copy the Role ID (right-click role → Copy ID with Developer Mode enabled)
   - Add as `DISCORD_PREMIUM_ROLE_ID`

3. **Configure channel permissions**:
   - Right-click `#premium-alerts` → Edit Channel → Permissions
   - Set `@everyone` to ❌ "View Channel"
   - Add "Premium Subscriber" role with ✅ "View Channel"

4. **Get IDs** (enable Developer Mode in Discord settings):
   - Right-click server → Copy Server ID → Add as `DISCORD_GUILD_ID`
   - Right-click `#free-alerts` → Copy Channel ID → Add as `DISCORD_FREE_CHANNEL_ID`
   - Right-click `#premium-alerts` → Copy Channel ID → Add as `DISCORD_PREMIUM_CHANNEL_ID`

5. **Update bot permissions**:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Your Application → OAuth2 → URL Generator
   - Select scopes: `bot`, `applications.commands`
   - Select permissions: `Manage Roles`, `Send Messages`, `Embed Links`
   - Use the generated URL to re-invite the bot (required for slash commands)

#### Telegram Premium Setup

1. **Create two channels** (not groups):
   - One for free users (moneyline alerts)
   - One for premium users (all markets)

2. **Add bot as admin** to both channels with these permissions:
   - Post messages
   - Edit messages
   - Delete messages
   - Ban users (for revoking premium access)

3. **Get channel IDs**:
   - Forward a message from each channel to [@getidsbot](https://t.me/getidsbot)
   - Copy the channel IDs (negative numbers like `-1001234567890`)
   - Add as `TELEGRAM_FREE_CHANNEL_ID` and `TELEGRAM_PREMIUM_CHANNEL_ID`

4. **Create premium channel invite link**:
   - Open premium channel → Channel Info → Invite Link
   - Create a new invite link (or use existing)
   - Copy the link (looks like `https://t.me/joinchat/ABC123...`)
   - Add as `TELEGRAM_PREMIUM_INVITE_LINK`

### 5. Testing the Subscription Flow

```bash
# Terminal 1: Start the application
python main.py

# Terminal 2: Forward Stripe webhooks (development only)
stripe listen --forward-to localhost:5000/webhook

# Terminal 3: Test a checkout event
stripe trigger checkout.session.completed
```

#### Manual Testing

1. **Discord**:
   - Join your Discord server
   - Type `/subscribe` in any channel
   - Click the Stripe checkout link
   - Complete test payment (use test card: `4242 4242 4242 4242`)
   - Bot should automatically assign premium role
   - Verify you can now see `#premium-alerts`

2. **Telegram**:
   - Start a chat with your bot
   - Send `/subscribe`
   - Click the Stripe checkout link
   - Complete test payment
   - Bot should send you the premium channel invite link
   - Join the premium channel

3. **Webhook verification**:
   ```bash
   curl http://localhost:5000/health
   # Should return: {"status": "healthy"}
   ```

4. **Database verification**:
   ```bash
   sqlite3 data/subscriptions.db "SELECT * FROM subscriptions;"
   # Should show subscription records
   ```

### 6. Stripe Test Cards

For testing in development mode:

| Card Number         | Description                    |
|---------------------|--------------------------------|
| 4242 4242 4242 4242 | Successful payment             |
| 4000 0000 0000 0002 | Card declined                  |
| 4000 0000 0000 9995 | Insufficient funds             |

Use any future expiration date, any 3-digit CVC, and any billing ZIP code.

---

## Example Alert

**Discord embed:**
```
🟢 Arb Alert — 2.34% Margin
Kansas City Chiefs @ Buffalo Bills
NFL · Moneyline

📌 Buffalo Bills           📌 Kansas City Chiefs
Book: DraftKings           Book: FanDuel
Odds: +115                 Odds: -108
Implied: 46.51%            Implied: 51.92%
Stake ($100 base): $47.24  Stake: $52.76

📊 Total implied: 98.43%
✅ Guaranteed profit on $100: $2.34
```

---

## Notes

- The system deduplicates by finding the **best available odds per outcome** across all books, so even if a book offers both sides, it always picks the optimal pairing.
- Logs are written daily to `logs/arb_YYYYMMDD.log`.
- API request usage is logged after every poll so you can monitor your quota.
