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

# Import tier configuration
from src.tier_config import get_current_tier, format_tier_log

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

# Track last poll time for dynamic tier checking
last_poll_time = None

# Premium channel IDs
DISCORD_CHANNEL = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
TELEGRAM_CHANNEL = os.getenv("TELEGRAM_CHANNEL_ID")

# Line movement tracking - stores arbs from recent polls
arb_history = {}  # {arb_key: {"first_seen": timestamp, "poll_count": N, "arb": ArbOpportunity}}
REQUIRED_CONFIRMATIONS = 2  # Must appear in 2+ consecutive polls before alerting


def generate_arb_key(arb) -> str:
    """
    Generate unique key for arb to track across polls.
    Format: "{game}|{market}|{books_sorted}"
    """
    books = "|".join(sorted([leg["book"] for leg in arb.legs]))
    return f"{arb.game}|{arb.market}|{books}"


def assign_urgency_level(arb, poll_count: int) -> str:
    """
    Assign urgency level based on stability and margin.

    Returns:
    - "🔴 HIGH" - Stable (3+ polls), good margin
    - "🟡 MEDIUM" - Confirmed (2 polls) or lower margin
    - "⚪ WATCH" - New detection (1 poll)
    """
    if poll_count >= 3 and arb.margin_pct >= 2.0:
        return "🔴 HIGH"
    elif poll_count >= REQUIRED_CONFIRMATIONS or arb.margin_pct >= 2.0:
        return "🟡 MEDIUM"
    else:
        return "⚪ WATCH"


def poll_and_alert():
    """
    Poll The Odds API and send arbitrage alerts using tier-based configuration.

    Three tiers optimize API usage based on game schedules:
    - SLEEP (1 AM - 11 AM ET): Minimal polling, overnight sports only
    - MID (11 AM - 5 PM ET): Moderate polling, daytime games
    - PRIME (5 PM - 1 AM ET): Aggressive polling, prime time games
    """
    global last_poll_time, arb_history

    if not ENABLE_POLLING:
        logger.info("Polling is disabled (ENABLE_POLLING=false)")
        return

    # Get current tier configuration
    tier = get_current_tier()
    required_interval_minutes = tier["interval_minutes"]

    # Get current time in Eastern timezone
    eastern = pytz.timezone('US/Eastern')
    current_time_et = datetime.now(eastern)

    # Check if enough time has passed since last poll
    if last_poll_time is not None:
        minutes_since_last_poll = (current_time_et - last_poll_time).total_seconds() / 60
        if minutes_since_last_poll < required_interval_minutes:
            logger.debug(
                f"Skipping poll - only {minutes_since_last_poll:.1f} min since last poll "
                f"(need {required_interval_minutes} min for {tier['name']} tier)"
            )
            return

    last_poll_time = current_time_et

    # Log tier info
    logger.info("🔄 " + tier["reason"])
    logger.info(format_tier_log(tier))

    logger.info("=" * 60)
    logger.info("POLL STARTED")

    # 1. Fetch odds using tier-specific sports and markets
    try:
        events, usage = fetch_all_odds(
            target_sports=tier["sports"],
            markets=tier["markets"]
        )
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
        # Clean up stale arbs from history
        arb_history.clear()
        return

    logger.info(f"{len(arbs)} raw arb(s) detected")

    # 3. Line movement tracking & multi-poll confirmation
    current_poll_keys = set()
    confirmed_arbs = []

    for arb in arbs:
        arb_key = generate_arb_key(arb)
        current_poll_keys.add(arb_key)

        if arb_key in arb_history:
            # Arb seen before - increment poll count
            arb_history[arb_key]["poll_count"] += 1
            arb_history[arb_key]["arb"] = arb  # Update with latest data
        else:
            # New arb - add to history
            arb_history[arb_key] = {
                "first_seen": datetime.now(),
                "poll_count": 1,
                "arb": arb,
                "alerted": False  # Track if we've already sent alert
            }

        poll_count = arb_history[arb_key]["poll_count"]
        already_alerted = arb_history[arb_key]["alerted"]

        # Add tracking metadata to arb
        arb.poll_count = poll_count
        arb.urgency = assign_urgency_level(arb, poll_count)
        arb.first_seen = arb_history[arb_key]["first_seen"]

        # Only send if confirmed (seen in 2+ consecutive polls) AND not already alerted
        if poll_count >= REQUIRED_CONFIRMATIONS and not already_alerted:
            confirmed_arbs.append(arb)
            arb_history[arb_key]["alerted"] = True  # Mark as alerted to prevent duplicates
        else:
            logger.info(
                f"PENDING confirmation ({poll_count}/{REQUIRED_CONFIRMATIONS}): "
                f"{arb.game} | {arb.market} | {arb.margin_pct:.2f}%"
            )

    # Clean up arbs that didn't appear in this poll (stale)
    stale_keys = set(arb_history.keys()) - current_poll_keys
    for key in stale_keys:
        del arb_history[key]

    if not confirmed_arbs:
        logger.info(f"No confirmed arbs (all pending confirmation)")
        logger.info("=" * 60)
        return

    logger.info(f"{len(confirmed_arbs)} confirmed arb(s) — sending to premium channels...")

    # 4. Store arbs in database for tracking and analytics
    for arb in confirmed_arbs:
        try:
            alert_id = store_arb_alert(arb)
            if alert_id:
                # Add alert_id to arb object for feedback tracking
                arb.alert_id = alert_id
        except Exception as e:
            logger.error(f"Failed to store arb: {e}")

    # 5. Send confirmed arbs to channels (premium-only service)
    logger.info(f"Sending {len(confirmed_arbs)} alert(s) to channels")

    try:
        send_discord_alerts(confirmed_arbs, channel_id=DISCORD_CHANNEL)
    except Exception as e:
        logger.error(f"Discord alerts failed: {e}")

    try:
        send_telegram_alerts(confirmed_arbs, channel_id=TELEGRAM_CHANNEL)
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
    logger.info("Mode: TIER-BASED (SLEEP/MID/PRIME)")
    logger.info("  SLEEP (1AM-11AM): 20min | MID (11AM-5PM): 7min | PRIME (5PM-1AM): 2.5min")
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
    logger.info("All systems ready. Starting tier-based polling loop...")
    logger.info("=" * 60)

    # Main thread: Run polling scheduler with tier-based intervals
    try:
        # Run immediately on startup
        poll_and_alert()

        # Check every minute if it's time to poll (poll_and_alert handles tier logic)
        schedule.every(1).minutes.do(poll_and_alert)

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
