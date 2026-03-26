"""
arb_tracker.py — Tracks arbitrage alerts and user feedback for analytics.
"""

import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def generate_alert_id(arb) -> str:
    """
    Generate a unique alert ID based on arb details.
    Format: sport_game_market_timestamp
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    # Create hash from game + market + books for uniqueness
    unique_str = f"{arb.game}_{arb.market}_{'_'.join(sorted([leg['book'] for leg in arb.legs]))}"
    hash_short = hashlib.md5(unique_str.encode()).hexdigest()[:8]
    return f"{arb.sport_key}_{hash_short}_{timestamp}"


def store_arb_alert(arb) -> str:
    """
    Store an arb alert in the database for tracking.
    Returns the alert_id.
    """
    try:
        alert_id = generate_alert_id(arb)
        books = [leg["book"] for leg in arb.legs]

        data = {
            "alert_id": alert_id,
            "sport": arb.sport,
            "sport_key": arb.sport_key,
            "game": arb.game,
            "market": arb.market,
            "margin_pct": float(arb.margin_pct),
            "books": books,
            "legs": arb.legs,
            "status": "active",
        }

        supabase.table("arb_alerts").insert(data).execute()
        logger.info(f"Stored arb alert: {alert_id}")
        return alert_id

    except Exception as e:
        logger.error(f"Failed to store arb alert: {e}")
        return None


def record_feedback(alert_id: str, user_id: str, is_positive: bool) -> bool:
    """
    Record user feedback on an arb alert.
    Returns True if successful.
    """
    try:
        # Get current alert
        result = supabase.table("arb_alerts").select("*").eq("alert_id", alert_id).execute()

        if not result.data:
            logger.warning(f"Alert not found: {alert_id}")
            return False

        alert = result.data[0]
        feedback_users = alert.get("feedback_users", [])

        # Check if user already gave feedback
        if user_id in feedback_users:
            logger.info(f"User {user_id} already gave feedback for {alert_id}")
            return False

        # Update feedback counters
        feedback_users.append(user_id)
        update_data = {"feedback_users": feedback_users}

        if is_positive:
            update_data["feedback_positive"] = alert.get("feedback_positive", 0) + 1
            update_data["status"] = "verified"
        else:
            update_data["feedback_negative"] = alert.get("feedback_negative", 0) + 1
            if alert.get("feedback_negative", 0) + 1 >= 3:  # 3 negative = mark as failed
                update_data["status"] = "failed"

        supabase.table("arb_alerts").update(update_data).eq("alert_id", alert_id).execute()
        logger.info(f"Recorded {'positive' if is_positive else 'negative'} feedback for {alert_id} from user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        return False


def get_stats(days: int = 30) -> dict:
    """
    Get aggregated statistics for the dashboard.
    """
    try:
        # Calculate date range
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Get all arbs in range
        result = supabase.table("arb_alerts").select("*").gte("sent_at", since).execute()
        arbs = result.data

        if not arbs:
            return {
                "total_arbs": 0,
                "avg_margin": 0,
                "success_rate": 0,
                "top_books": [],
                "top_sports": [],
                "total_feedback": 0,
            }

        # Calculate metrics
        total_arbs = len(arbs)
        total_margin = sum(float(a["margin_pct"]) for a in arbs)
        avg_margin = total_margin / total_arbs if total_arbs > 0 else 0

        # Success rate (based on feedback)
        total_positive = sum(a.get("feedback_positive", 0) for a in arbs)
        total_negative = sum(a.get("feedback_negative", 0) for a in arbs)
        total_feedback = total_positive + total_negative
        success_rate = (total_positive / total_feedback * 100) if total_feedback > 0 else 0

        # Top book combinations
        book_combos = {}
        for arb in arbs:
            books_key = " + ".join(sorted(arb["books"]))
            if books_key not in book_combos:
                book_combos[books_key] = {"count": 0, "avg_margin": 0, "total_margin": 0}
            book_combos[books_key]["count"] += 1
            book_combos[books_key]["total_margin"] += float(arb["margin_pct"])

        for combo in book_combos.values():
            combo["avg_margin"] = combo["total_margin"] / combo["count"]

        top_books = sorted(
            [{"combo": k, **v} for k, v in book_combos.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]

        # Top sports
        sport_stats = {}
        for arb in arbs:
            sport = arb["sport"]
            if sport not in sport_stats:
                sport_stats[sport] = {"count": 0, "avg_margin": 0, "total_margin": 0}
            sport_stats[sport]["count"] += 1
            sport_stats[sport]["total_margin"] += float(arb["margin_pct"])

        for stat in sport_stats.values():
            stat["avg_margin"] = stat["total_margin"] / stat["count"]

        top_sports = sorted(
            [{"sport": k, **v} for k, v in sport_stats.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]

        return {
            "total_arbs": total_arbs,
            "avg_margin": round(avg_margin, 2),
            "success_rate": round(success_rate, 1),
            "top_books": top_books,
            "top_sports": top_sports,
            "total_feedback": total_feedback,
            "days": days,
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {
            "total_arbs": 0,
            "avg_margin": 0,
            "success_rate": 0,
            "top_books": [],
            "top_sports": [],
            "total_feedback": 0,
            "error": str(e),
        }


def get_recent_arbs(limit: int = 10) -> list:
    """
    Get recent arb alerts for display.
    """
    try:
        result = (
            supabase.table("arb_alerts")
            .select("alert_id,sport,game,margin_pct,books,sent_at,status,feedback_positive,feedback_negative")
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Failed to get recent arbs: {e}")
        return []


def search_arbs(
    sport: Optional[str] = None,
    book_combo: Optional[str] = None,
    min_margin: Optional[float] = None,
    max_margin: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> dict:
    """
    Search historical arbs with filters.

    Returns:
        dict with 'arbs' list and aggregated 'stats'
    """
    try:
        # Start with base query
        query = supabase.table("arb_alerts").select("*")

        # Apply filters
        if sport:
            query = query.eq("sport_key", sport)

        if min_margin is not None:
            query = query.gte("margin_pct", min_margin)

        if max_margin is not None:
            query = query.lte("margin_pct", max_margin)

        if start_date:
            query = query.gte("sent_at", start_date)

        if end_date:
            query = query.lte("sent_at", end_date)

        # Order and limit
        query = query.order("sent_at", desc=True).limit(limit)

        result = query.execute()
        arbs = result.data

        # Filter by book combo if specified
        if book_combo:
            book_list = sorted(book_combo.split(" + "))
            arbs = [
                arb for arb in arbs
                if sorted(arb["books"]) == book_list
            ]

        # Calculate aggregated stats
        if arbs:
            total_positive = sum(a.get("feedback_positive", 0) for a in arbs)
            total_negative = sum(a.get("feedback_negative", 0) for a in arbs)
            total_feedback = total_positive + total_negative

            stats = {
                "count": len(arbs),
                "avg_margin": sum(float(a["margin_pct"]) for a in arbs) / len(arbs),
                "success_rate": (total_positive / total_feedback * 100) if total_feedback > 0 else 0,
                "total_feedback": total_feedback,
            }
        else:
            stats = {
                "count": 0,
                "avg_margin": 0,
                "success_rate": 0,
                "total_feedback": 0,
            }

        return {"arbs": arbs, "stats": stats}

    except Exception as e:
        logger.error(f"Failed to search arbs: {e}")
        return {"arbs": [], "stats": {"count": 0, "avg_margin": 0, "success_rate": 0, "total_feedback": 0}}
