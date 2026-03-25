"""
billing.py — SQLite-based subscription management for Stripe integration.
"""

import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subscriptions.db")


def _get_connection() -> sqlite3.Connection:
    """Get a thread-safe SQLite connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    return conn


def init_db():
    """Initialize the database schema. Called automatically on module import."""
    conn = _get_connection()
    try:
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL;")

        # Create subscriptions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, platform)
            )
        """)

        # Create indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_customer
            ON subscriptions(stripe_customer_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON subscriptions(status, platform)
        """)

        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        conn.close()


def mark_subscribed(
    user_id: str,
    platform: str,
    customer_id: str,
    subscription_id: str
) -> None:
    """
    Mark a user as subscribed after successful Stripe checkout.

    Args:
        user_id: Discord or Telegram user ID
        platform: 'discord' or 'telegram'
        customer_id: Stripe customer ID
        subscription_id: Stripe subscription ID
    """
    conn = _get_connection()
    try:
        conn.execute("""
            INSERT INTO subscriptions
            (user_id, platform, stripe_customer_id, stripe_subscription_id, status, updated_at)
            VALUES (?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, platform) DO UPDATE SET
                stripe_customer_id=excluded.stripe_customer_id,
                stripe_subscription_id=excluded.stripe_subscription_id,
                status='active',
                updated_at=CURRENT_TIMESTAMP
        """, (user_id, platform, customer_id, subscription_id))

        conn.commit()
        logger.info(f"Marked {platform} user {user_id} as subscribed")
    except Exception as e:
        logger.error(f"Failed to mark subscription: {e}")
        raise
    finally:
        conn.close()


def is_subscribed(user_id: str, platform: str) -> bool:
    """
    Check if a user has an active subscription.

    Args:
        user_id: Discord or Telegram user ID
        platform: 'discord' or 'telegram'

    Returns:
        True if user has active subscription, False otherwise
    """
    conn = _get_connection()
    try:
        cursor = conn.execute("""
            SELECT status FROM subscriptions
            WHERE user_id = ? AND platform = ?
        """, (user_id, platform))

        row = cursor.fetchone()
        if row is None:
            return False

        return row['status'] == 'active'
    except Exception as e:
        logger.error(f"Failed to check subscription status: {e}")
        return False  # Fail-safe: treat as unsubscribed on error
    finally:
        conn.close()


def cancel_subscription(customer_id: str) -> None:
    """
    Mark a subscription as canceled when Stripe event fires.

    Args:
        customer_id: Stripe customer ID
    """
    conn = _get_connection()
    try:
        # Find subscription by customer_id
        cursor = conn.execute("""
            SELECT user_id, platform FROM subscriptions
            WHERE stripe_customer_id = ?
        """, (customer_id,))

        row = cursor.fetchone()
        if row is None:
            logger.warning(f"No subscription found for customer {customer_id}")
            return

        # Update status to canceled/expired
        conn.execute("""
            UPDATE subscriptions
            SET status = 'canceled', updated_at = CURRENT_TIMESTAMP
            WHERE stripe_customer_id = ?
        """, (customer_id,))

        conn.commit()
        logger.info(f"Canceled subscription for customer {customer_id}")
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise
    finally:
        conn.close()


def get_subscription_by_customer(customer_id: str) -> Optional[dict]:
    """
    Get subscription details by Stripe customer ID.

    Args:
        customer_id: Stripe customer ID

    Returns:
        Dictionary with subscription details or None if not found
    """
    conn = _get_connection()
    try:
        cursor = conn.execute("""
            SELECT * FROM subscriptions
            WHERE stripe_customer_id = ?
        """, (customer_id,))

        row = cursor.fetchone()
        if row is None:
            return None

        return dict(row)
    except Exception as e:
        logger.error(f"Failed to fetch subscription: {e}")
        return None
    finally:
        conn.close()


# Initialize database on module import
init_db()
