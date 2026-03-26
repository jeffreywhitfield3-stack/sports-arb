"""
odds_fetcher.py — Fetches live odds from The Odds API.
"""

import os
import logging
import re
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"

logger = logging.getLogger(__name__)


def redact_url(url: str) -> str:
    """
    Replace apiKey query parameter value with [REDACTED] to prevent
    API keys from appearing in logs.

    Example:
        https://api.example.com?apiKey=abc123 -> https://api.example.com?apiKey=[REDACTED]
    """
    return re.sub(r'(apiKey=)[^&\s]+', r'\1[REDACTED]', url)


def get_active_sports() -> list[dict]:
    """Return active sports from a predefined list of 8 major US sports."""
    url = f"{BASE_URL}/sports"
    params = {"apiKey": API_KEY}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    sports = resp.json()

    # Only track these 8 specific sports
    target_sports = {
        "americanfootball_nfl",
        "americanfootball_ufl",
        "basketball_nba",
        "basketball_ncaab",
        "baseball_mlb",
        "icehockey_nhl",
        "mma_mixed_martial_arts",
        "boxing_boxing",
    }

    # Filter to only active sports from our target list
    active_sports = [
        s for s in sports
        if s.get("active") and s.get("key") in target_sports
    ]

    logger.info(f"Found {len(active_sports)} active sports from target list")
    return active_sports


def get_odds_for_sport(sport_key: str) -> tuple[list[dict], dict]:
    """
    Fetch h2h and spreads odds for a given sport key.
    Returns (odds_data, api_usage_info).
    """
    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()

    usage = {
        "requests_remaining": resp.headers.get("x-requests-remaining", "N/A"),
        "requests_used": resp.headers.get("x-requests-used", "N/A"),
    }
    logger.info(
        f"[{sport_key}] API usage — used: {usage.get('requests_used', 'N/A')}, "
        f"remaining: {usage.get('requests_remaining', 'N/A')}"
    )
    return resp.json(), usage


def fetch_all_odds() -> tuple[list[dict], dict]:
    """
    Fetch odds across all active US sports.
    Returns (all_events, last_usage_info).
    """
    sports = get_active_sports()
    all_events = []
    last_usage = {}

    for sport in sports:
        key = sport.get("key")
        try:
            events, usage = get_odds_for_sport(key)
            last_usage = usage
            all_events.extend(events)
            logger.info(f"Fetched {len(events)} events for {key}")
        except requests.HTTPError as e:
            error_msg = redact_url(str(e))
            logger.warning(f"HTTP error fetching {key}: {error_msg}")
        except Exception as e:
            error_msg = redact_url(str(e))
            logger.error(f"Unexpected error fetching {key}: {error_msg}")

    logger.info(f"Total events fetched: {len(all_events)}")
    return all_events, last_usage
