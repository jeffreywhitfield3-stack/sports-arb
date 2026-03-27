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

# Import arb tracking for analytics
from src.arb_tracker import store_arb_alert

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# Polling configuration
ENABLE_POLLING = os.getenv("ENABLE_POLLING", "true").lower() == "true"
USE_HYBRID_SCHEDULE = os.getenv("USE_HYBRID_SCHEDULE", "false").lower() == "true"

# Simple mode: Fixed interval polling
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "10"))

# Hybrid mode: Time-based dynamic intervals (optimal for 20K API quota)
PEAK_HOURS_START = 17  # 5 PM ET
PEAK_HOURS_END = 1     # 1 AM ET (next day)
PEAK_INTERVAL_MINUTES = 10   # Fast polling during peak hours
OFFPEAK_INTERVAL_MINUTES = 20  # Slower polling during off-peak

# Track last poll time for hybrid mode
last_poll_time = None

# Premium channel IDs
DISCORD_CHANNEL = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL_ID")


def poll_and_alert():
    """
    Poll The Odds API and send arbitrage alerts.

    Two modes:
    1. Simple: Fixed interval (set via POLL_INTERVAL_MINUTES)
    2. Hybrid: Dynamic intervals based on time (USE_HYBRID_SCHEDULE=true)
       - Peak (5 PM-1 AM): 10 min | Off-Peak (9 AM-5 PM): 20 min
       - Budget: 19,440 calls/month
    """
    global last_poll_time

    if not ENABLE_POLLING:
        logger.info("Polling is disabled (ENABLE_POLLING=false)")
        return

    # Get current time in Eastern timezone
    eastern = pytz.timezone('US/Eastern')
    current_time_et = datetime.now(eastern)
    current_hour = current_time_et.hour

    # Check if we're in active hours (9 AM - 1 AM ET)
    if not (current_hour >= 9 or current_hour < 1):
        logger.info(
            f"Outside active hours (9 AM - 1 AM ET), skipping poll. "
            f"Current time: {current_time_et.strftime('%I:%M %p %Z')}"
        )
        return

    # HYBRID MODE: Dynamic intervals based on peak/off-peak hours
    if USE_HYBRID_SCHEDULE:
        is_peak_hours = (current_hour >= PEAK_HOURS_START or current_hour < PEAK_HOURS_END)
        required_interval_minutes = PEAK_INTERVAL_MINUTES if is_peak_hours else OFFPEAK_INTERVAL_MINUTES

        # Check if enough time has passed since last poll
        if last_poll_time is not None:
            minutes_since_last_poll = (current_time_et - last_poll_time).total_seconds() / 60
            if minutes_since_last_poll < required_interval_minutes:
                logger.debug(
                    f"Skipping poll - only {minutes_since_last_poll:.1f} min since last poll "
                    f"(need {required_interval_minutes} min in {'peak' if is_peak_hours else 'off-peak'} hours)"
                )
                return

        last_poll_time = current_time_et
        mode = "PEAK" if is_peak_hours else "OFF-PEAK"
        logger.info(f"🔄 Polling in {mode} mode ({required_interval_minutes}-min interval)")
    # SIMPLE MODE: Fixed interval (schedule handles timing)
    else:
        logger.info(f"🔄 Polling (simple mode, {POLL_INTERVAL_MINUTES}-min interval)")

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

    logger.info(f"{len(arbs)} arb(s) found — sending to premium channels...")

    # 3. Store arbs in database for tracking and analytics
    for arb in arbs:
        try:
            alert_id = store_arb_alert(arb)
            if alert_id:
                # Add alert_id to arb object for feedback tracking
                arb.alert_id = alert_id
        except Exception as e:
            logger.error(f"Failed to store arb: {e}")

    # 4. Send ALL arbs to channels (premium-only service)
    logger.info(f"Sending {len(arbs)} alert(s) to channels")

    try:
        send_discord_alerts(arbs, channel_id=DISCORD_CHANNEL)
    except Exception as e:
        logger.error(f"Discord alerts failed: {e}")

    try:
        send_telegram_alerts(arbs, channel_id=TELEGRAM_CHANNEL)
    except Exception as e:
        logger.error(f"Telegram alerts failed: {e}")

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
    logger.info(f"Polling: {'ENABLED' if ENABLE_POLLING else 'DISABLED'}")

    if USE_HYBRID_SCHEDULE:
        logger.info(f"Mode: HYBRID - Peak (5PM-1AM)={PEAK_INTERVAL_MINUTES}min | Off-Peak (9AM-5PM)={OFFPEAK_INTERVAL_MINUTES}min")
        logger.info(f"Budget: ~19,440 calls/month (97% of 20K quota)")
    else:
        logger.info(f"Mode: SIMPLE - Every {POLL_INTERVAL_MINUTES} minutes")

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

        # Schedule polling based on mode
        if USE_HYBRID_SCHEDULE:
            # Hybrid: Check every 5 min, poll_and_alert() decides if it's time
            schedule.every(5).minutes.do(poll_and_alert)
        else:
            # Simple: Use configured interval
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
