"""
telegram_alerter.py — Sends arb alerts to Telegram with feedback buttons.
"""

import os
import logging
import asyncio
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
from src.arb_calculator import ArbOpportunity
import stripe
import requests

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
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

# Global application instance for alert sending
telegram_app = None


def build_message(arb: ArbOpportunity) -> str:
    """Build Telegram message with MarkdownV2 formatting."""
    market_label = MARKET_LABELS.get(arb.market, arb.market.upper())

    # Add urgency and stability indicators
    urgency = getattr(arb, 'urgency', '🟡 MEDIUM')
    poll_count = getattr(arb, 'poll_count', 1)

    if poll_count >= 3:
        stability = "🟢 STABLE"
    elif poll_count == 2:
        stability = "✅ CONFIRMED"
    else:
        stability = "⚡ NEW"

    lines = [
        f"{urgency} \\| {arb.emoji} *ARB ALERT — {escape(f'{arb.margin_pct:.2f}')}% Margin*",
        f"{escape(stability)} \\(seen {poll_count}x\\)",
        f"🏟 *{escape(arb.game)}*",
        f"📋 {escape(arb.sport)} · {escape(market_label)}",
        "",
    ]

    for i, leg in enumerate(arb.legs, 1):
        odds_str = f"+{leg['odds']}" if leg['odds'] > 0 else str(leg['odds'])
        implied_pct_str = escape(f"{leg['implied_pct']}")
        stake_str = escape(f"${leg['stake']:.2f}")
        lines += [
            f"*Leg {i} — {escape(leg['outcome'])}*",
            f"  📚 Book: `{escape(leg['book'])}`",
            f"  💰 Odds: `{escape(odds_str)}`",
            f"  📉 Implied: `{implied_pct_str}%`",
            f"  💵 Stake \\($100 base\\): `{stake_str}`",
            "",
        ]

    total_implied = sum(l["implied_pct"] for l in arb.legs)
    total_implied_str = escape(f"{total_implied:.2f}")
    profit_str = escape(f"${arb.margin_pct:.2f}")
    game_time_str = escape(arb.commence_time[:16].replace('T', ' '))

    lines += [
        f"📊 *Total implied:* `{total_implied_str}%`",
        f"✅ *Profit on $100:* `{profit_str}`",
        f"🕐 Game time: `{game_time_str} UTC`",
    ]

    return "\n".join(lines)


def build_feedback_keyboard(alert_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard with feedback buttons."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Worked", callback_data=f"feedback_yes:{alert_id}"),
            InlineKeyboardButton("❌ Failed", callback_data=f"feedback_no:{alert_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def escape(text: str) -> str:
    """Escape special MarkdownV2 characters."""
    specials = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    result = text
    for ch in specials:
        result = result.replace(ch, f"\\{ch}")
    return result


async def send_alert_with_feedback(arb: ArbOpportunity, channel_id: str = None):
    """Send alert with feedback buttons using persistent application."""
    global telegram_app

    if telegram_app is None:
        logger.error("Telegram app not initialized")
        return

    if channel_id is None:
        channel_id = CHANNEL_ID

    try:
        text = build_message(arb)
        keyboard = build_feedback_keyboard(arb.alert_id) if hasattr(arb, 'alert_id') else None

        await telegram_app.bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=keyboard
        )

        logger.info(f"Telegram alert sent to channel {channel_id}: {arb.game} | {arb.margin_pct:.2f}%")
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")


def send_telegram_alert(arb: ArbOpportunity, channel_id: str = None):
    """Synchronous wrapper for sending alert."""
    # Alerts will be queued and sent by the persistent application
    pass


def send_telegram_alerts(arbs: list[ArbOpportunity], channel_id: str = None):
    """Send multiple alerts (queued for persistent app)."""
    global telegram_app
    if telegram_app:
        for arb in arbs:
            # Queue for sending
            asyncio.create_task(send_alert_with_feedback(arb, channel_id))


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback button clicks."""
    query = update.callback_query
    await query.answer()

    # Parse callback data
    data = query.data
    if not data.startswith("feedback_"):
        return

    try:
        action, alert_id = data.split(":", 1)
        is_positive = action == "feedback_yes"

        # Call feedback API
        response = requests.post(
            f"{os.getenv('RAILWAY_URL', 'http://localhost:5000')}/api/feedback",
            json={
                "alert_id": alert_id,
                "user_id": str(query.from_user.id),
                "is_positive": is_positive
            }
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                message = "✅ Thanks! Feedback recorded." if is_positive else "❌ Thanks for the feedback. We'll improve!"
                await query.edit_message_reply_markup(reply_markup=None)  # Remove buttons
                await query.message.reply_text(message)
            else:
                await query.message.reply_text("You've already given feedback on this arb!")
        else:
            await query.message.reply_text("❌ Failed to record feedback. Try again later.")

    except Exception as e:
        logger.error(f"Feedback handler error: {e}")
        await query.message.reply_text("❌ Error processing feedback.")


async def telegram_bot_main():
    """Run Telegram bot with command handlers and feedback."""
    global telegram_app

    async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe command."""
        user_id = update.effective_user.id

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
                mode='subscription',
                success_url=STRIPE_SUCCESS_URL,
                cancel_url=STRIPE_CANCEL_URL,
                metadata={
                    'user_id': str(user_id),
                    'platform': 'telegram',
                }
            )

            await update.message.reply_text(
                f"🔗 **Subscribe to Premium**\n\n"
                f"Click here: {session.url}\n\n"
                f"✨ Premium Benefits:\n"
                f"• All markets (h2h, spreads, totals)\n"
                f"• High-quality filtered alerts\n"
                f"• Verified book combinations\n"
                f"• Real-time notifications",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"Stripe checkout created for Telegram user {user_id}")
        except Exception as e:
            logger.error(f"Stripe checkout error: {e}")
            await update.message.reply_text("❌ Failed to create checkout. Try again later.")

    async def manage_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /manage command - opens Stripe Customer Portal."""
        user_id = update.effective_user.id

        try:
            from src.billing import supabase

            # Get user's subscription from database
            result = supabase.table("subscriptions").select("stripe_customer_id").eq(
                "user_id", str(user_id)
            ).eq("platform", "telegram").execute()

            if not result.data or not result.data[0].get("stripe_customer_id"):
                await update.message.reply_text(
                    "❌ **No Active Subscription**\n\n"
                    "You don't have an active subscription\\.\n"
                    "Use /subscribe to get started\\!",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                return

            customer_id = result.data[0]["stripe_customer_id"]

            # Create Customer Portal session
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=STRIPE_SUCCESS_URL,
            )

            await update.message.reply_text(
                f"🔗 **Manage Your Subscription**\n\n"
                f"Click here: {portal_session.url}\n\n"
                f"You can:\n"
                f"• Cancel your subscription\n"
                f"• Update payment method\n"
                f"• View billing history\n"
                f"• Download invoices",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"Customer portal created for Telegram user {user_id}")

        except Exception as e:
            logger.error(f"Customer portal error: {e}")
            await update.message.reply_text("❌ Failed to create portal session\\. Try again later\\.", parse_mode=ParseMode.MARKDOWN_V2)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "👋 **Welcome to Sports Arbitrage Alerts!**\n\n"
            "💎 Premium arbitrage opportunities delivered in real-time.\n\n"
            "**Features:**\n"
            "• All markets: moneyline, spreads, totals\n"
            "• Quality filters (1.5-3% margins)\n"
            "• Trusted books only\n"
            "• User feedback & success tracking\n\n"
            "Use /subscribe to get started!",
            parse_mode=ParseMode.MARKDOWN
        )

    # Build application
    telegram_app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("subscribe", subscribe))
    telegram_app.add_handler(CommandHandler("manage", manage_subscription))
    telegram_app.add_handler(CallbackQueryHandler(handle_feedback))

    # Initialize and start
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()

    logger.info("Telegram bot started (command handlers active)")

    # Keep running
    await asyncio.Event().wait()


def send_premium_invite(user_id: str):
    """Send premium channel invite to Telegram user (called from webhook)."""
    bot = Bot(token=BOT_TOKEN)
    asyncio.run(bot.send_message(
        chat_id=user_id,
        text=f"🎉 **Welcome to Premium!**\n\nJoin the channel: {PREMIUM_INVITE_LINK}",
        parse_mode=ParseMode.MARKDOWN
    ))
    logger.info(f"Sent premium invite to Telegram user {user_id}")


def revoke_premium_access(user_id: str):
    """Kick user from premium channel (called from webhook)."""
    bot = Bot(token=BOT_TOKEN)
    asyncio.run(bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=int(user_id)))
    asyncio.run(bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=int(user_id)))
    logger.info(f"Removed user {user_id} from Telegram channel")
