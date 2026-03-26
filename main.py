"""
main.py — Sports Arbitrage Alert System
Entry point with multi-threaded architecture:
- Main thread: Polling scheduler
- Thread 1: Flask webhook server
- Thread 2: Telegram bot with command handlers
- Thread 3: Discord bot with slash commands
"""

import logging
import schedule
import time
import threading
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
import pytz

# Import logging setup first
from src.logger_setup import setup_logging

# Import polling and arb detection
from src.odds_fetcher import fetch_all_odds
from src.arb_calculator import find_arbs

# Import alerters with new channel_id parameters
from src.discord_alerter import send_discord_alerts, discord_slash_bot
from src.telegram_alerter import send_telegram_alerts, telegram_bot_main

# Import Flask webhook server
from server import run_server

# Import billing for database initialization
from src.billing import init_db

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

POLL_INTERVAL_MINUTES = 10
ENABLE_POLLING = os.getenv("ENABLE_POLLING", "true").lower() == "true"

# Channel IDs for tiered alerts
FREE_DISCORD_CHANNEL = int(os.getenv("DISCORD_FREE_CHANNEL_ID", os.getenv("DISCORD_CHANNEL_ID", "0")))
PREMIUM_DISCORD_CHANNEL = int(os.getenv("DISCORD_PREMIUM_CHANNEL_ID", "0"))
FREE_TELEGRAM_CHANNEL = os.getenv("TELEGRAM_FREE_CHANNEL_ID", os.getenv("TELEGRAM_CHANNEL_ID"))
PREMIUM_TELEGRAM_CHANNEL = os.getenv("TELEGRAM_PREMIUM_CHANNEL_ID")


def poll_and_alert():
    """
    Poll The Odds API, detect arbitrage opportunities, and send tiered alerts.
    Free users get h2h only, premium users get all markets.
    Only runs between 9 AM and 1 AM Eastern time.
    """
    if not ENABLE_POLLING:
        logger.info("Polling is disabled (ENABLE_POLLING=false)")
        return

    # Time gate: Only run between 9 AM and 1 AM Eastern
    eastern = pytz.timezone('US/Eastern')
    current_time_et = datetime.now(eastern)
    current_hour = current_time_et.hour

    # Active hours: 9 AM (9) to 1 AM (1)
    # This means: hour >= 9 OR hour < 1
    if not (current_hour >= 9 or current_hour < 1):
        logger.info(
            f"Outside active hours (9 AM - 1 AM ET), skipping poll. "
            f"Current time: {current_time_et.strftime('%I:%M %p %Z')}"
        )
        return

    logger.info("=" * 60)
    logger.info("POLL STARTED")

    # 1. Fetch odds
    try:
        events, usage = fetch_all_odds()
        logger.info(
            f"Odds fetch complete. Events: {len(events)} | "
            f"API remaining: {usage.get('requests_remaining', 'N/A')}"
        )
    except Exception as e:
        logger.error(f"Failed to fetch odds: {e}")
        return

    # 2. Detect arbs
    try:
        arbs = find_arbs(events)
    except Exception as e:
        logger.error(f"Arb calculation failed: {e}")
        return

    if not arbs:
        logger.info("No arb opportunities found this poll.")
        logger.info("=" * 60)
        return

    logger.info(f"{len(arbs)} arb(s) found — routing to tiered channels...")

    # 3. Split arbs by market type
    h2h_arbs = [arb for arb in arbs if arb.market == 'h2h']
    premium_arbs = [arb for arb in arbs if arb.market in ['spreads', 'totals']]

    # 4. Send h2h alerts to free channels
    if h2h_arbs:
        logger.info(f"Sending {len(h2h_arbs)} h2h alert(s) to free channels")
        try:
            send_discord_alerts(h2h_arbs, channel_id=FREE_DISCORD_CHANNEL)
        except Exception as e:
            logger.error(f"Discord free alerts failed: {e}")

        try:
            send_telegram_alerts(h2h_arbs, channel_id=FREE_TELEGRAM_CHANNEL)
        except Exception as e:
            logger.error(f"Telegram free alerts failed: {e}")

    # 5. Send premium alerts to premium channels
    if premium_arbs:
        logger.info(f"Sending {len(premium_arbs)} premium alert(s) to premium channels")
        try:
            send_discord_alerts(premium_arbs, channel_id=PREMIUM_DISCORD_CHANNEL)
        except Exception as e:
            logger.error(f"Discord premium alerts failed: {e}")

        try:
            send_telegram_alerts(premium_arbs, channel_id=PREMIUM_TELEGRAM_CHANNEL)
        except Exception as e:
            logger.error(f"Telegram premium alerts failed: {e}")

    logger.info("Alerts sent.")
    logger.info("=" * 60)


# ============================================================================
# Thread Functions
# ============================================================================

def run_flask_server():
    """Thread 1: Flask webhook server for Stripe events."""
    try:
        run_server()
    except Exception as e:
        logger.error(f"Flask server error: {e}")


def run_telegram_bot():
    """Thread 2: Telegram bot with command handlers (separate asyncio loop)."""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        logger.info("Starting Telegram bot...")
        loop.run_until_complete(telegram_bot_main())
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")


def run_discord_bot():
    """Thread 3: Discord bot with slash commands."""
    try:
        logger.info("Starting Discord bot...")
        discord_slash_bot.run(os.getenv("DISCORD_BOT_TOKEN"))
    except Exception as e:
        logger.error(f"Discord bot error: {e}")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """
    Main entry point - orchestrates all components in a single process.
    """
    logger.info("=" * 60)
    logger.info("Sports Arbitrage Alert System starting up...")
    logger.info(f"Polling: {'ENABLED' if ENABLE_POLLING else 'DISABLED'} (every {POLL_INTERVAL_MINUTES} minutes)")
    logger.info("=" * 60)

    # Initialize database
    init_db()

    # Start Flask server in daemon thread
    flask_thread = threading.Thread(target=run_flask_server, daemon=True, name="FlaskServer")
    flask_thread.start()
    logger.info("✓ Flask webhook server thread started")

    # Start Telegram bot in daemon thread
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True, name="TelegramBot")
    telegram_thread.start()
    logger.info("✓ Telegram bot thread started")

    # Start Discord bot in daemon thread
    discord_thread = threading.Thread(target=run_discord_bot, daemon=True, name="DiscordBot")
    discord_thread.start()
    logger.info("✓ Discord bot thread started")

    # Give threads time to initialize
    time.sleep(3)

    logger.info("=" * 60)
    logger.info("All systems ready. Starting polling loop...")
    logger.info("=" * 60)

    # Main thread: Run polling scheduler
    try:
        # Run immediately on startup
        poll_and_alert()

        # Schedule recurring polls
        schedule.every(POLL_INTERVAL_MINUTES).minutes.do(poll_and_alert)

        # Main loop
        while True:
            schedule.run_pending()
            time.sleep(30)

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Shutting down gracefully...")
        logger.info("All daemon threads will terminate")
        logger.info("Goodbye!")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
