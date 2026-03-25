"""
billing.py — Supabase-based subscription management for Stripe integration.
"""

import logging
import os
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def init_db():
    """
    Initialize the database schema (for Supabase compatibility).

    Note: With Supabase, the table should be created via the Supabase dashboard:

    CREATE TABLE subscriptions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE(user_id, platform)
    );

    CREATE INDEX idx_customer ON subscriptions(stripe_customer_id);
    CREATE INDEX idx_active ON subscriptions(active, platform);

    This function is kept for API compatibility with the SQLite version.
    """
    try:
        # Test connection by attempting to read from the table
        supabase.table("subscriptions").select("id").limit(1).execute()
        logger.info("Supabase connection successful")
    except Exception as e:
        logger.warning(f"Supabase table not found or connection failed: {e}")
        logger.warning("Please create the 'subscriptions' table in Supabase dashboard")


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
    try:
        # Check if subscription already exists
        existing = supabase.table("subscriptions").select("*").eq(
            "user_id", user_id
        ).eq("platform", platform).execute()

        if existing.data:
            # Update existing subscription
            supabase.table("subscriptions").update({
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "active": True,
                "updated_at": "now()"
            }).eq("user_id", user_id).eq("platform", platform).execute()
        else:
            # Insert new subscription
            supabase.table("subscriptions").insert({
                "user_id": user_id,
                "platform": platform,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "active": True
            }).execute()

        logger.info(f"Marked {platform} user {user_id} as subscribed")
    except Exception as e:
        logger.error(f"Failed to mark subscription: {e}")
        raise


def is_subscribed(user_id: str, platform: str) -> bool:
    """
    Check if a user has an active subscription.

    Args:
        user_id: Discord or Telegram user ID
        platform: 'discord' or 'telegram'

    Returns:
        True if user has active subscription, False otherwise
    """
    try:
        result = supabase.table("subscriptions").select("active").eq(
            "user_id", user_id
        ).eq("platform", platform).execute()

        if not result.data:
            return False

        return result.data[0].get("active", False)
    except Exception as e:
        logger.error(f"Failed to check subscription status: {e}")
        return False  # Fail-safe: treat as unsubscribed on error


def cancel_subscription(customer_id: str) -> None:
    """
    Mark a subscription as canceled when Stripe event fires.

    Args:
        customer_id: Stripe customer ID
    """
    try:
        # Find subscription by customer_id
        result = supabase.table("subscriptions").select(
            "user_id, platform"
        ).eq("stripe_customer_id", customer_id).execute()

        if not result.data:
            logger.warning(f"No subscription found for customer {customer_id}")
            return

        # Update status to inactive
        supabase.table("subscriptions").update({
            "active": False,
            "updated_at": "now()"
        }).eq("stripe_customer_id", customer_id).execute()

        logger.info(f"Canceled subscription for customer {customer_id}")
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise


def get_subscription_by_customer(customer_id: str) -> Optional[dict]:
    """
    Get subscription details by Stripe customer ID.

    Args:
        customer_id: Stripe customer ID

    Returns:
        Dictionary with subscription details or None if not found
    """
    try:
        result = supabase.table("subscriptions").select("*").eq(
            "stripe_customer_id", customer_id
        ).execute()

        if not result.data:
            return None

        return result.data[0]
    except Exception as e:
        logger.error(f"Failed to fetch subscription: {e}")
        return None


# Initialize database connection on module import
init_db()
