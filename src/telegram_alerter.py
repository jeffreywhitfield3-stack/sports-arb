"""
telegram_alerter.py — Sends arb alerts to a Telegram channel.
"""

import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
from src.arb_calculator import ArbOpportunity
import stripe

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
PREMIUM_CHANNEL_ID = os.getenv("TELEGRAM_PREMIUM_CHANNEL_ID")
PREMIUM_INVITE_LINK = os.getenv("TELEGRAM_PREMIUM_INVITE_LINK")

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://example.com/success")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://example.com/cancel")

logger = logging.getLogger(__name__)

MARKET_LABELS = {
    "h2h": "Moneyline",
    "spreads": "Spreads",
    "totals": "Totals",
}


def build_message(arb: ArbOpportunity) -> str:
    market_label = MARKET_LABELS.get(arb.market, arb.market.upper())
    lines = [
        f"{arb.emoji} *ARB ALERT — {arb.margin_pct:.2f}% Margin*",
        f"🏟 *{escape(arb.game)}*",
        f"📋 {escape(arb.sport)} · {escape(market_label)}",
        "",
    ]

    for i, leg in enumerate(arb.legs, 1):
        odds_str = f"+{leg['odds']}" if leg['odds'] > 0 else str(leg['odds'])
        lines += [
            f"*Leg {i} — {escape(leg['outcome'])}*",
            f"  📚 Book: `{escape(leg['book'])}`",
            f"  💰 Odds: `{odds_str}`",
            f"  📉 Implied: `{leg['implied_pct']}%`",
            f"  💵 Stake \\($100 base\\): `${leg['stake']:.2f}`",
            "",
        ]

    total_implied = sum(l["implied_pct"] for l in arb.legs)
    lines += [
        f"📊 *Total implied:* `{total_implied:.2f}%`",
        f"✅ *Profit on $100:* `${arb.margin_pct:.2f}`",
        f"🕐 Game time: `{arb.commence_time[:16].replace('T', ' ')} UTC`",
    ]

    return "\n".join(lines)


def escape(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    specials = r"\_*[]()~`>#+-=|{}.!"
    for ch in specials:
        text = text.replace(ch, f"\\{ch}")
    return text


async def _send_message(arb: ArbOpportunity, channel_id: str = None):
    """Send arb alert message to specified Telegram channel."""
    if channel_id is None:
        channel_id = CHANNEL_ID

    bot = Bot(token=BOT_TOKEN)
    text = build_message(arb)
    await bot.send_message(
        chat_id=channel_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info(f"Telegram alert sent to channel {channel_id}: {arb.game} | {arb.margin_pct:.2f}%")


def send_telegram_alert(arb: ArbOpportunity, channel_id: str = None):
    """Synchronous wrapper."""
    try:
        asyncio.run(_send_message(arb, channel_id))
    except Exception as e:
        logger.error(f"Telegram alerter failed: {e}")


def send_telegram_alerts(arbs: list[ArbOpportunity], channel_id: str = None):
    """Send multiple arb alerts to the specified Telegram channel."""
    for arb in arbs:
        send_telegram_alert(arb, channel_id)


# ============================================================================
# Telegram Bot with Command Handlers
# ============================================================================

async def telegram_bot_main():
    """
    Run Telegram bot with command handlers for subscription.
    This runs in a separate thread with its own asyncio event loop.
    """
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - welcome message."""
        await update.message.reply_text(
            "👋 *Welcome to Sports Arbitrage Alerts\\!*\n\n"
            "🆓 *Free users* get moneyline \\(h2h\\) alerts\n"
            "💎 *Premium subscribers* get spreads and totals too\n\n"
            "Use /subscribe to upgrade\\!",
            parse_mode=ParseMode.MARKDOWN_V2
        )

    async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe command - create Stripe checkout session."""
        user_id = update.effective_user.id

        try:
            # Create Stripe checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': STRIPE_PRICE_ID,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=STRIPE_SUCCESS_URL,
                cancel_url=STRIPE_CANCEL_URL,
                metadata={
                    'user_id': str(user_id),
                    'platform': 'telegram',
                }
            )

            await update.message.reply_text(
                f"🔗 *Subscribe here:* {session.url}\n\n"
                f"✨ *Premium includes:*\n"
                f"• All h2h \\(moneyline\\) alerts\n"
                f"• Spreads alerts\n"
                f"• Totals alerts\n\n"
                f"You'll receive an invite link after payment\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )

            logger.info(f"Stripe checkout created for Telegram user {user_id}")

        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            await update.message.reply_text(
                "❌ Sorry, something went wrong\\. Please try again later\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )

    # Build application
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))

    # Initialize and start
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("Telegram bot started (command handlers active)")

    # Keep running until stopped
    stop_event = asyncio.Event()
    await stop_event.wait()


def send_premium_invite(user_id: str):
    """
    Send premium channel invite to Telegram user.
    Called from webhook after successful subscription.
    """
    async def _send():
        bot = Bot(token=BOT_TOKEN)
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 *Welcome to Premium\\!*\n\n"
                    f"Join the premium channel for spreads and totals alerts:\n"
                    f"{PREMIUM_INVITE_LINK}"
                ),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            logger.info(f"✅ Sent premium invite to Telegram user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send premium invite to user {user_id}: {e}")

    try:
        asyncio.run(_send())
    except Exception as e:
        logger.error(f"Error in send_premium_invite: {e}")


def revoke_premium_access(user_id: str):
    """
    Remove user from Telegram premium channel.
    Called from webhook after subscription cancellation.
    """
    async def _revoke():
        bot = Bot(token=BOT_TOKEN)
        try:
            # Kick user from premium channel
            await bot.ban_chat_member(
                chat_id=PREMIUM_CHANNEL_ID,
                user_id=int(user_id)
            )

            # Unban immediately so they can rejoin if they resubscribe
            await bot.unban_chat_member(
                chat_id=PREMIUM_CHANNEL_ID,
                user_id=int(user_id)
            )

            logger.info(f"✅ Removed user {user_id} from Telegram premium channel")

        except Exception as e:
            logger.error(f"Failed to revoke Telegram access from user {user_id}: {e}")

    try:
        asyncio.run(_revoke())
    except Exception as e:
        logger.error(f"Error in revoke_premium_access: {e}")
