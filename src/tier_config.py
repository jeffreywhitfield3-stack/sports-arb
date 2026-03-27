"""
tier_config.py — Time-based polling tier configuration.

Three tiers optimize API usage based on game schedules:
- SLEEP (1 AM - 11 AM ET): Minimal polling, overnight sports only
- MID (11 AM - 5 PM ET): Moderate polling, daytime games
- PRIME (5 PM - 1 AM ET): Aggressive polling, prime time games
"""

import os
from datetime import datetime
from typing import Dict, List
import pytz


def get_current_tier() -> Dict:
    """
    Determine current polling tier based on Eastern Time.

    Returns tier config dict with: name, interval, sports, markets, reason
    """
    # Check for manual override
    force_tier = os.getenv("FORCE_TIER", "").lower()
    if force_tier in ["sleep", "mid", "prime"]:
        tier = _get_tier_config(force_tier)
        tier["reason"] = f"Forced via FORCE_TIER={force_tier}"
        return tier

    # Get current time in Eastern timezone
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(eastern)
    current_hour = now_et.hour
    day_of_week = now_et.strftime('%A')  # Monday, Tuesday, etc.

    # Determine tier based on time
    if 1 <= current_hour < 11:
        tier_name = "sleep"
        reason = f"SLEEP tier (1 AM - 11 AM ET) | Current: {now_et.strftime('%I:%M %p %Z')}"
    elif 11 <= current_hour < 17:
        tier_name = "mid"
        reason = f"MID tier (11 AM - 5 PM ET) | Current: {now_et.strftime('%I:%M %p %Z')}"
    else:  # 17-24 (5 PM - midnight) or 0 (midnight - 1 AM)
        tier_name = "prime"
        reason = f"PRIME tier (5 PM - 1 AM ET) | Current: {now_et.strftime('%I:%M %p %Z')}"

    tier = _get_tier_config(tier_name, day_of_week)
    tier["reason"] = reason
    return tier


def _get_tier_config(tier_name: str, day_of_week: str = None) -> Dict:
    """Get configuration for a specific tier."""

    # SLEEP tier (1 AM - 11 AM ET)
    if tier_name == "sleep":
        return {
            "name": "SLEEP",
            "interval_minutes": 20,
            "sports": [
                "boxing_boxing",
                "mma_mixed_martial_arts"
            ],
            "markets": ["h2h"],
        }

    # MID tier (11 AM - 5 PM ET)
    elif tier_name == "mid":
        sports = [
            "baseball_mlb",
            "icehockey_nhl",
            "basketball_nba",
            "boxing_boxing",
            "mma_mixed_martial_arts"
        ]

        # Add UFL on Friday/Saturday/Sunday
        if day_of_week in ["Friday", "Saturday", "Sunday"]:
            sports.append("americanfootball_ufl")

        return {
            "name": "MID",
            "interval_minutes": 7,
            "sports": sports,
            "markets": ["h2h", "totals"],
        }

    # PRIME tier (5 PM - 1 AM ET)
    elif tier_name == "prime":
        sports = [
            "basketball_nba",
            "baseball_mlb",
            "icehockey_nhl",
            "boxing_boxing",
            "mma_mixed_martial_arts",
            "basketball_ncaab",
            "americanfootball_ufl"
        ]

        # Drop NCAAB and UFL on Monday/Tuesday
        if day_of_week in ["Monday", "Tuesday"]:
            sports.remove("basketball_ncaab")
            sports.remove("americanfootball_ufl")

        return {
            "name": "PRIME",
            "interval_minutes": 2.5,
            "sports": sports,
            "markets": ["h2h", "totals"],
        }

    else:
        raise ValueError(f"Invalid tier name: {tier_name}")


def format_tier_log(tier: Dict) -> str:
    """Format tier info for logging."""
    return (
        f"📊 {tier['name']} TIER | "
        f"Interval: {tier['interval_minutes']} min | "
        f"Sports: {len(tier['sports'])} | "
        f"Markets: {', '.join(tier['markets'])}"
    )
