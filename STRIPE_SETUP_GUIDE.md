# 🔐 Complete Stripe Setup Guide

## Goal
Ensure NO ONE can access alerts without a paid subscription. This guide covers:
1. Setting up Stripe product and pricing
2. Configuring webhooks for automatic access control
3. Securing Discord and Telegram channels
4. Testing the complete payment flow

---

## Part 1: Stripe Dashboard Setup

### 1. Create Your Product
1. Go to [Stripe Dashboard → Products](https://dashboard.stripe.com/products)
2. Click **"Add product"**
3. Fill in:
   - **Name**: `Sports Arbitrage Premium`
   - **Description**: `Premium arbitrage alerts with verified results`
   - **Pricing model**: `Recurring`
   - **Price**: Your choice (e.g., $19.99/month or $199/year)
   - **Billing period**: `Monthly` or `Yearly`
4. Click **"Save product"**
5. **Copy the Price ID** (starts with `price_`) - you'll need this

### 2. Get Your API Keys
1. Go to [Developers → API Keys](https://dashboard.stripe.com/apikeys)
2. **Copy the Secret key** (starts with `sk_test_` for test mode, `sk_live_` for production)
3. **IMPORTANT**: Never commit this to git or share it publicly

### 3. Setup Webhook Endpoint

**For Production (Railway):**
1. Go to [Developers → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click **"Add endpoint"**
3. Enter endpoint URL: `https://worker-production-14eb.up.railway.app/webhook`
4. Select events to listen to:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
5. Click **"Add endpoint"**
6. **Copy the Signing secret** (starts with `whsec_`)

**For Local Testing:**
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:5000/webhook
# This will output a signing secret - use it for STRIPE_WEBHOOK_SECRET locally
```

---

## Part 2: Discord Server Configuration

### 1. Create Premium Role
1. In Discord, go to **Server Settings → Roles**
2. Click **"Create Role"**
3. Name it: `Premium Subscriber` (or any name you want)
4. **Set permissions**:
   - General Permissions: Set whatever you want
   - **DO NOT** give this role admin permissions
5. Save the role
6. **Copy the Role ID**:
   - Enable Developer Mode: User Settings → Advanced → Developer Mode
   - Right-click the role → Copy ID

### 2. Lock Down Your Alerts Channel
1. Go to your alerts channel (e.g., `#premium-alerts`)
2. Click the gear icon → **Permissions**
3. **Remove @everyone permissions** (or set to deny "View Channel")
4. Click **"Add role or member"**
5. Select your `Premium Subscriber` role
6. **Allow** these permissions:
   - ✅ View Channel
   - ✅ Read Message History
   - ✅ Use Application Commands (for feedback buttons)
7. **Save Changes**

**Test**: Make sure non-premium members CANNOT see the channel at all.

### 3. Get Server (Guild) ID
1. Enable Developer Mode (if not already)
2. Right-click your server icon
3. Click **"Copy Server ID"**

### 4. Add Bot to Server
Your bot should already be in the server. Make sure it has these permissions:
- ✅ Manage Roles (to assign premium role)
- ✅ Send Messages
- ✅ Embed Links
- ✅ Use Slash Commands

**IMPORTANT**: The bot's role must be HIGHER in the role hierarchy than the Premium Subscriber role, or it won't be able to assign it.

---

## Part 3: Telegram Channel Configuration

### 1. Create Your Premium Channel
1. In Telegram, create a **new channel** (not a group)
2. Name it something like `Sports Arb Premium`
3. Set it to **Private**
4. Add your bot as an **administrator** with these permissions:
   - ✅ Post messages
   - ✅ Edit messages
   - ✅ Delete messages
   - ✅ Invite users via link
   - ✅ Ban users

### 2. Get Channel ID
1. Forward any message from your channel to [@getidsbot](https://t.me/getidsbot)
2. The bot will reply with the channel ID (starts with `-100`)
3. **Copy this ID**

### 3. Create Invite Link
1. In your channel, go to **Channel Info → Invite Links**
2. Click **"Create a new link"**
3. Set it to:
   - **Expire**: Never
   - **Usage limit**: Unlimited
4. **Copy the invite link** (looks like `https://t.me/joinchat/ABC123...`)

**How it works**: When users subscribe, the bot will DM them this invite link. Only paying users receive the link.

---

## Part 4: Environment Variables Setup

### In Railway Dashboard:
Add these environment variables:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_51ABC...  # Your secret key
STRIPE_PRICE_ID=price_1ABC...       # Your price ID
STRIPE_WEBHOOK_SECRET=whsec_ABC...  # Your webhook signing secret
STRIPE_SUCCESS_URL=https://worker-production-14eb.up.railway.app/
STRIPE_CANCEL_URL=https://worker-production-14eb.up.railway.app/

# Discord Premium Configuration
DISCORD_GUILD_ID=123456789012345678        # Your server ID
DISCORD_PREMIUM_ROLE_ID=987654321098765432 # Your premium role ID

# Telegram Premium Configuration
TELEGRAM_PREMIUM_INVITE_LINK=https://t.me/joinchat/ABC123...

# Already set (verify these exist)
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...  # Your premium channel ID
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=... # Your premium channel ID (with -100 prefix)
```

**After adding these**: Railway will automatically redeploy.

---

## Part 5: Database Setup

### Run Subscription Schema in Supabase:
1. Go to your [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **SQL Editor**
4. Click **"New query"**
5. Copy and paste the contents of `supabase_schema_subscriptions.sql`
6. Click **"Run"**
7. Verify the table was created: Go to **Table Editor** → should see `subscriptions` table

---

## Part 6: Testing the Complete Flow

### Test 1: Discord Subscription Flow

1. **In Discord**, type `/subscribe` in any channel
2. You should receive an **ephemeral message** (only you see it) with a Stripe checkout link
3. Click the link
4. Complete test payment using Stripe test card:
   - Card number: `4242 4242 4242 4242`
   - Expiry: Any future date
   - CVC: Any 3 digits
   - ZIP: Any ZIP code
5. After successful payment:
   - Check Railway logs for: `✅ Discord access granted to user [YOUR_ID]`
   - In Discord, verify you now have the Premium Subscriber role
   - Verify you can now see the premium alerts channel

### Test 2: Telegram Subscription Flow

1. **In Telegram**, send `/start` to your bot
2. Send `/subscribe`
3. Click the Stripe checkout link
4. Complete test payment (same test card as above)
5. After successful payment:
   - You should receive a DM from the bot with the channel invite link
   - Click the link to join the premium channel
   - Check Railway logs for: `✅ Telegram invite sent to user [YOUR_ID]`

### Test 3: Verify Webhook Works

Check Railway logs for these messages after checkout:
```
Received Stripe event: checkout.session.completed
Marked discord user [USER_ID] as subscribed
✅ Discord access granted to user [USER_ID]
```

### Test 4: Verify Non-Subscribers Cannot Access

1. **Discord**:
   - Log in with a different account (or ask a friend)
   - They should NOT see the premium alerts channel at all

2. **Telegram**:
   - Without the invite link, the channel should be undiscoverable
   - Even if they somehow find it, they can't join (it's private)

---

## Part 7: Going Live (Production Mode)

### Switch to Live Mode:

1. **In Stripe Dashboard**:
   - Toggle from **Test mode** to **Live mode** (top-right corner)
   - Create a new product (or activate your existing one for live mode)
   - Copy the LIVE Price ID (starts with `price_`)

2. **Get Live API Keys**:
   - Go to [Developers → API Keys](https://dashboard.stripe.com/apikeys)
   - Copy the **Live** Secret key (starts with `sk_live_`)

3. **Create Live Webhook**:
   - Go to [Developers → Webhooks](https://dashboard.stripe.com/webhooks)
   - Ensure you're in **Live mode**
   - Add endpoint: `https://worker-production-14eb.up.railway.app/webhook`
   - Select same events: `checkout.session.completed`, `customer.subscription.deleted`
   - Copy the LIVE webhook signing secret

4. **Update Railway Environment Variables**:
   ```bash
   STRIPE_SECRET_KEY=sk_live_...  # Live secret key
   STRIPE_PRICE_ID=price_...      # Live price ID
   STRIPE_WEBHOOK_SECRET=whsec_... # Live webhook secret
   ```

5. **Test with real payment** (use your own card, you can refund it later)

---

## Part 8: Handling Cancellations

When a user cancels their subscription:

1. Stripe sends `customer.subscription.deleted` event to your webhook
2. Your system automatically:
   - **Discord**: Removes the premium role from the user
   - **Telegram**: Kicks the user from the premium channel
   - Updates database to mark subscription as `active: false`

**To test cancellations**:
```bash
# In Stripe Dashboard (test mode)
# Go to Customers → find your test customer → Subscriptions → Cancel subscription

# Or trigger test event:
stripe trigger customer.subscription.deleted
```

---

## Part 9: Security Checklist

Before launching:

- [ ] Discord premium channel is LOCKED (only premium role can view)
- [ ] Telegram premium channel is PRIVATE (unlisted, invite-only)
- [ ] Bot has "Manage Roles" permission in Discord
- [ ] Bot is admin in Telegram channel with ban permissions
- [ ] STRIPE_SECRET_KEY is NOT committed to git
- [ ] Webhook signature verification is enabled (already in code)
- [ ] Test mode works completely
- [ ] All environment variables are set in Railway
- [ ] `subscriptions` table exists in Supabase
- [ ] You've tested the complete flow with test payment

---

## Part 10: Monitoring & Maintenance

### Check Subscription Status:
```sql
-- In Supabase SQL Editor
SELECT
    user_id,
    platform,
    active,
    created_at,
    updated_at
FROM subscriptions
ORDER BY created_at DESC;
```

### Monitor Stripe Events:
- [Stripe Dashboard → Developers → Events](https://dashboard.stripe.com/events)
- Shows all webhook events and delivery status
- If webhook fails, Stripe will retry automatically

### Railway Logs:
- Watch for successful subscription messages
- Watch for failed role assignments (might indicate permissions issue)

---

## Troubleshooting

### "Failed to grant Discord access"
- **Check**: Bot role is higher than premium role in hierarchy
- **Check**: Bot has "Manage Roles" permission
- **Check**: DISCORD_GUILD_ID and DISCORD_PREMIUM_ROLE_ID are correct

### "Failed to send Telegram invite"
- **Check**: Bot token is valid
- **Check**: Bot can send DMs to user (user hasn't blocked bot)
- **Check**: TELEGRAM_PREMIUM_INVITE_LINK is correct

### Webhook says "Invalid signature"
- **Check**: STRIPE_WEBHOOK_SECRET matches the one in Stripe dashboard
- **Check**: You're using the correct secret for test/live mode

### User paid but didn't get access
- **Check Railway logs** for the webhook event
- **Check Stripe Dashboard → Events** to see if webhook was delivered
- **Manually run**: In Supabase, check if subscription was recorded
- **Manual fix**: Assign role manually and investigate logs

---

## Summary

✅ **Your system is now payment-gated!**

**User Flow:**
1. User types `/subscribe` → Gets Stripe checkout link
2. User pays → Stripe sends webhook to your server
3. Server grants access:
   - Discord: Assigns premium role
   - Telegram: Sends invite link via DM
4. User can now see alerts
5. If they cancel → Automatically lose access

**Security:**
- Discord: Channel locked to premium role only
- Telegram: Private channel, invite-only
- No way to access without active subscription
- Automatic access revocation on cancellation

You're ready to sell! 🚀
