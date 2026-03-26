# ✅ Pre-Launch Checklist

Everything you need to do before selling subscriptions.

---

## 1️⃣ Stripe Setup (Required)

### Create Product & Pricing
- [ ] Go to [Stripe Products](https://dashboard.stripe.com/products)
- [ ] Create product: "Sports Arbitrage Premium"
- [ ] Set price: $____/month (or yearly)
- [ ] Copy **Price ID** (starts with `price_`)

### Get API Keys
- [ ] Go to [Stripe API Keys](https://dashboard.stripe.com/apikeys)
- [ ] Copy **Secret Key** (starts with `sk_test_` or `sk_live_`)
- [ ] Keep this secret - never commit to git!

### Setup Webhook
- [ ] Go to [Stripe Webhooks](https://dashboard.stripe.com/webhooks)
- [ ] Add endpoint: `https://worker-production-14eb.up.railway.app/webhook`
- [ ] Select events:
  - `checkout.session.completed`
  - `customer.subscription.deleted`
- [ ] Copy **Webhook Signing Secret** (starts with `whsec_`)

---

## 2️⃣ Discord Configuration (Required)

### Create Premium Role
- [ ] Server Settings → Roles → Create Role
- [ ] Name: `Premium Subscriber` (or your choice)
- [ ] Enable Developer Mode (User Settings → Advanced)
- [ ] Right-click role → Copy ID

### Lock Premium Channel
- [ ] Go to your alerts channel
- [ ] Click gear icon → Permissions
- [ ] Remove @everyone (or deny "View Channel")
- [ ] Add `Premium Subscriber` role with:
  - ✅ View Channel
  - ✅ Read Message History
  - ✅ Use Application Commands
- [ ] Save changes
- [ ] **TEST**: Verify non-premium users can't see channel

### Get Server ID
- [ ] Right-click server icon → Copy Server ID

### Verify Bot Permissions
- [ ] Bot has "Manage Roles" permission
- [ ] Bot's role is ABOVE premium role in hierarchy

---

## 3️⃣ Telegram Configuration (Required)

### Create Premium Channel
- [ ] Create new channel (private, not group)
- [ ] Name: `Sports Arb Premium` (or your choice)
- [ ] Set to Private
- [ ] Add bot as administrator with:
  - ✅ Post messages
  - ✅ Delete messages
  - ✅ Ban users
  - ✅ Invite users via link

### Get Channel Details
- [ ] Forward message from channel to [@getidsbot](https://t.me/getidsbot)
- [ ] Copy Channel ID (starts with `-100`)
- [ ] Channel Info → Invite Links → Create new link
- [ ] Set: Never expire, Unlimited uses
- [ ] Copy invite link (e.g., `https://t.me/joinchat/ABC123...`)

---

## 4️⃣ Railway Environment Variables (Required)

Add these in Railway dashboard:

```bash
# Stripe (from steps above)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SUCCESS_URL=https://worker-production-14eb.up.railway.app/
STRIPE_CANCEL_URL=https://worker-production-14eb.up.railway.app/

# Discord (from steps above)
DISCORD_GUILD_ID=...
DISCORD_PREMIUM_ROLE_ID=...

# Telegram (from steps above)
TELEGRAM_PREMIUM_INVITE_LINK=https://t.me/joinchat/...

# Verify these already exist:
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=... (your premium channel)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=... (starts with -100)
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
```

---

## 5️⃣ Database Setup (Required)

### Run Supabase SQL
- [ ] Go to [Supabase Dashboard](https://app.supabase.com)
- [ ] SQL Editor → New query
- [ ] Copy/paste from: `supabase_schema_subscriptions.sql`
- [ ] Click "Run"
- [ ] Verify in Table Editor: `subscriptions` table exists

### Verify Other Tables
- [ ] `arb_alerts` table exists (from earlier setup)
- [ ] `user_profiles` table exists (from earlier setup)

---

## 6️⃣ Testing (Critical!)

### Test Discord Flow
- [ ] In Discord, type `/subscribe`
- [ ] Get ephemeral checkout link
- [ ] Complete test payment:
  - Card: `4242 4242 4242 4242`
  - Any future date, any CVC, any ZIP
- [ ] Verify premium role is assigned automatically
- [ ] Verify you can now see the locked channel

### Test Telegram Flow
- [ ] Send `/start` to bot
- [ ] Send `/subscribe`
- [ ] Complete test payment
- [ ] Receive DM with invite link
- [ ] Join premium channel successfully

### Verify Access Control
- [ ] Test with another Discord account - can't see channel ✅
- [ ] Test with another Telegram account - can't find channel ✅

### Test Cancellation
- [ ] Go to Stripe Dashboard → Customers
- [ ] Find your test customer → Cancel subscription
- [ ] Verify role removed (Discord) or kicked (Telegram)

---

## 7️⃣ Go Live (When Ready)

### Switch to Live Mode
- [ ] Stripe Dashboard → Toggle to "Live mode"
- [ ] Create live product (or activate existing)
- [ ] Copy LIVE Price ID
- [ ] Get LIVE Secret Key
- [ ] Create LIVE Webhook (same URL, same events)
- [ ] Copy LIVE Webhook Secret

### Update Railway
- [ ] Replace test keys with live keys:
  - `STRIPE_SECRET_KEY=sk_live_...`
  - `STRIPE_PRICE_ID=price_...` (live)
  - `STRIPE_WEBHOOK_SECRET=whsec_...` (live)

### Final Live Test
- [ ] Make real payment (you can refund later)
- [ ] Verify complete flow works in production

---

## 8️⃣ Marketing Prep (Optional but Recommended)

### Create Landing Page
- [ ] Explain what users get
- [ ] Show success rate from `/stats` page
- [ ] Link to `/subscribe` commands

### Prepare Marketing Copy
- [ ] Highlight verified results
- [ ] Show transparency (public stats dashboard)
- [ ] Emphasize quality over quantity

### Pricing Strategy
- [ ] Monthly: $__ (e.g., $19.99)
- [ ] Yearly: $__ (e.g., $199 = 2 months free)
- [ ] Consider 7-day free trial initially

---

## 9️⃣ Security Verification

Before launch, verify:

- [ ] Premium Discord channel = LOCKED to role only
- [ ] Premium Telegram channel = PRIVATE and invite-only
- [ ] No way to access alerts without payment
- [ ] Stripe secret key NOT in git repository
- [ ] Webhook signature verification enabled (it is)
- [ ] Bot permissions correct (Manage Roles for Discord)
- [ ] Test cancellation flow works

---

## 🔟 Launch Day

### Enable Alerts
- [ ] Set `ENABLE_POLLING=true` in Railway (or delete variable)
- [ ] Monitor Railway logs for arbs being detected
- [ ] Verify alerts post to channels

### Monitor First 24 Hours
- [ ] Check Stripe Dashboard for subscriptions
- [ ] Watch Railway logs for any errors
- [ ] Monitor Discord/Telegram for user feedback
- [ ] Verify webhook events are processing

---

## 📊 Ongoing Maintenance

### Weekly
- [ ] Check `/stats` dashboard for success rates
- [ ] Review user feedback on alerts
- [ ] Monitor subscription churn

### Monthly
- [ ] Review Stripe revenue
- [ ] Analyze which sports/books perform best
- [ ] Consider adjusting filters if needed

---

## 🚀 You're Ready When...

✅ All Stripe keys are configured
✅ Channels are locked/private
✅ Test subscription flow works end-to-end
✅ Cancellation flow works
✅ Database tables are created
✅ Alerts are posting to channels
✅ Non-subscribers cannot access channels

**Once all boxes are checked, you can start marketing!**

Need help? See `STRIPE_SETUP_GUIDE.md` for detailed instructions.
