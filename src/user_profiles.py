"""
user_profiles.py — User profile management for regional optimization.
"""

import os
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_user_profile(user_id: str, platform: str) -> Optional[dict]:
    """
    Get user profile from database.

    Returns:
        dict with user_id, platform, state, created_at, updated_at
        None if not found
    """
    try:
        result = (
            supabase.table("user_profiles")
            .select("*")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .execute()
        )

        if result.data:
            return result.data[0]
        return None

    except Exception as e:
        logger.error(f"Failed to get user profile: {e}")
        return None


def set_user_state(user_id: str, platform: str, state: str) -> bool:
    """
    Set or update user's state.

    Args:
        user_id: User ID (Discord or Telegram)
        platform: 'discord' or 'telegram'
        state: US state code (e.g., "NY", "NJ")

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if profile exists
        existing = get_user_profile(user_id, platform)

        if existing:
            # Update existing profile
            supabase.table("user_profiles").update({
                "state": state.upper()
            }).eq("user_id", user_id).eq("platform", platform).execute()
        else:
            # Insert new profile
            supabase.table("user_profiles").insert({
                "user_id": user_id,
                "platform": platform,
                "state": state.upper()
            }).execute()

        logger.info(f"Set state for {platform} user {user_id}: {state}")
        return True

    except Exception as e:
        logger.error(f"Failed to set user state: {e}")
        return False


def get_user_state(user_id: str, platform: str) -> Optional[str]:
    """
    Get user's state setting.

    Returns:
        State code (e.g., "NY") or None if not set
    """
    profile = get_user_profile(user_id, platform)
    return profile.get("state") if profile else None


def delete_user_profile(user_id: str, platform: str) -> bool:
    """Delete user profile."""
    try:
        supabase.table("user_profiles").delete().eq("user_id", user_id).eq("platform", platform).execute()
        logger.info(f"Deleted profile for {platform} user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete user profile: {e}")
        return False


def get_users_by_state(state: str, platform: Optional[str] = None) -> list[dict]:
    """
    Get all users in a specific state.

    Args:
        state: US state code
        platform: Optional platform filter ('discord' or 'telegram')

    Returns:
        List of user profiles
    """
    try:
        query = supabase.table("user_profiles").select("*").eq("state", state.upper())

        if platform:
            query = query.eq("platform", platform)

        result = query.execute()
        return result.data

    except Exception as e:
        logger.error(f"Failed to get users by state: {e}")
        return []


def get_profile_stats() -> dict:
    """Get statistics about user profiles."""
    try:
        result = supabase.table("user_profiles").select("platform,state").execute()
        profiles = result.data

        stats = {
            "total_users": len(profiles),
            "discord_users": len([p for p in profiles if p["platform"] == "discord"]),
            "telegram_users": len([p for p in profiles if p["platform"] == "telegram"]),
            "users_with_state": len([p for p in profiles if p.get("state")]),
            "states": {}
        }

        # Count by state
        for profile in profiles:
            state = profile.get("state")
            if state:
                stats["states"][state] = stats["states"].get(state, 0) + 1

        return stats

    except Exception as e:
        logger.error(f"Failed to get profile stats: {e}")
        return {
            "total_users": 0,
            "discord_users": 0,
            "telegram_users": 0,
            "users_with_state": 0,
            "states": {}
        }
