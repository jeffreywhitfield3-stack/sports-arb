#!/usr/bin/env python3
"""
Test script to send a sample alert to Discord and Telegram.
Verifies channels, permissions, and formatting.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from discord_alerter import send_discord_alerts
from telegram_alerter import send_telegram_alerts

load_dotenv()

# Create a test arb
class TestArb:
    def __init__(self):
        self.sport = "NBA"
        self.sport_key = "basketball_nba"
        self.game = "Test Team A vs Test Team B"
        self.market = "h2h"
        self.margin_pct = 2.5
        self.alert_id = f"TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.legs = [
            {
                "outcome": "Test Team A",
                "book": "DraftKings",
                "price": 150,
                "stake_pct": 45.0,
                "url": "https://sportsbook.draftkings.com"
            },
            {
                "outcome": "Test Team B",
                "book": "FanDuel",
                "price": -130,
                "stake_pct": 55.0,
                "url": "https://sportsbook.fanduel.com"
            }
        ]

def main():
    print("=" * 60)
    print("🧪 SENDING TEST ALERT")
    print("=" * 60)

    # Get channel IDs
    discord_channel = os.getenv("DISCORD_CHANNEL_ID")
    telegram_channel = os.getenv("TELEGRAM_CHANNEL_ID")

    if not discord_channel:
        print("❌ DISCORD_CHANNEL_ID not set in .env")
        return

    if not telegram_channel:
        print("❌ TELEGRAM_CHANNEL_ID not set in .env")
        return

    print(f"\n📍 Target Channels:")
    print(f"   Discord: {discord_channel}")
    print(f"   Telegram: {telegram_channel}")
    print()

    # Create test arb
    test_arb = TestArb()

    # Send to Discord
    print("📤 Sending to Discord...")
    try:
        send_discord_alerts([test_arb], channel_id=int(discord_channel))
        print("✅ Discord alert sent!")
    except Exception as e:
        print(f"❌ Discord failed: {e}")

    print()

    # Send to Telegram
    print("📤 Sending to Telegram...")
    try:
        send_telegram_alerts([test_arb], channel_id=telegram_channel)
        print("✅ Telegram alert sent!")
    except Exception as e:
        print(f"❌ Telegram failed: {e}")

    print()
    print("=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)
    print("\nCheck your channels for the test alert!")
    print("It should have:")
    print("  • Test game (Test Team A vs Test Team B)")
    print("  • 2.5% margin")
    print("  • Feedback buttons (✅ Worked / ❌ Failed)")
    print()

if __name__ == "__main__":
    main()
