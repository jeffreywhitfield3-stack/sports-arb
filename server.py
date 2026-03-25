"""
server.py — Flask webhook server for handling Stripe events.
This will be integrated into main.py as a daemon thread.
"""

import os
import logging
import stripe
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from src.billing import mark_subscribed, cancel_subscription, get_subscription_by_customer

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "healthy"}), 200


@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    """
    Handle Stripe webhook events.
    Verifies signature and processes checkout.session.completed and
    customer.subscription.deleted events.
    """
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        logger.error("Missing Stripe signature header")
        return jsonify({"error": "Missing signature"}), 400

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return jsonify({"error": "Invalid signature"}), 400

    # Handle the event
    event_type = event["type"]
    logger.info(f"Received Stripe event: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            handle_checkout_completed(event["data"]["object"])
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(event["data"]["object"])
        else:
            logger.info(f"Unhandled event type: {event_type}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.error(f"Error handling webhook event: {e}", exc_info=True)
        # Return 500 to trigger Stripe retry
        return jsonify({"error": "Internal server error"}), 500


def handle_checkout_completed(session):
    """
    Handle successful checkout completion.
    Extracts user info from metadata and grants premium access.
    """
    user_id = session.get("metadata", {}).get("user_id")
    platform = session.get("metadata", {}).get("platform")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not all([user_id, platform, customer_id, subscription_id]):
        logger.error(f"Missing required fields in checkout session: {session['id']}")
        return

    # Update database
    mark_subscribed(user_id, platform, customer_id, subscription_id)

    # Grant platform-specific access
    if platform == "discord":
        grant_discord_access(user_id)
    elif platform == "telegram":
        grant_telegram_access(user_id)
    else:
        logger.warning(f"Unknown platform: {platform}")


def handle_subscription_deleted(subscription):
    """
    Handle subscription cancellation or deletion.
    Revokes premium access for the user.
    """
    customer_id = subscription.get("customer")

    if not customer_id:
        logger.error(f"Missing customer_id in subscription event: {subscription['id']}")
        return

    # Get subscription details
    sub_data = get_subscription_by_customer(customer_id)
    if not sub_data:
        logger.warning(f"No subscription found for customer {customer_id}")
        return

    user_id = sub_data["user_id"]
    platform = sub_data["platform"]

    # Update database
    cancel_subscription(customer_id)

    # Revoke platform-specific access
    if platform == "discord":
        revoke_discord_access(user_id)
    elif platform == "telegram":
        revoke_telegram_access(user_id)
    else:
        logger.warning(f"Unknown platform: {platform}")


def grant_discord_access(user_id: str):
    """
    Grant premium role to Discord user.
    Calls Discord API via discord_alerter module.
    """
    import asyncio
    from src.discord_alerter import grant_premium_access

    try:
        # Run the async function in the main event loop
        # Note: This runs in Flask's sync context, so we use asyncio.run
        asyncio.run(grant_premium_access(user_id))
        logger.info(f"✅ Discord access granted to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to grant Discord access: {e}")


def revoke_discord_access(user_id: str):
    """
    Revoke premium role from Discord user.
    Calls Discord API via discord_alerter module.
    """
    import asyncio
    from src.discord_alerter import revoke_premium_access

    try:
        asyncio.run(revoke_premium_access(user_id))
        logger.info(f"✅ Discord access revoked from user {user_id}")
    except Exception as e:
        logger.error(f"Failed to revoke Discord access: {e}")


def grant_telegram_access(user_id: str):
    """
    Send premium channel invite to Telegram user.
    Calls Telegram API via telegram_alerter module.
    """
    from src.telegram_alerter import send_premium_invite

    try:
        send_premium_invite(user_id)
        logger.info(f"✅ Telegram invite sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram invite: {e}")


def revoke_telegram_access(user_id: str):
    """
    Remove user from Telegram premium channel.
    Calls Telegram API via telegram_alerter module.
    """
    from src.telegram_alerter import revoke_premium_access

    try:
        revoke_premium_access(user_id)
        logger.info(f"✅ Telegram access revoked from user {user_id}")
    except Exception as e:
        logger.error(f"Failed to revoke Telegram access: {e}")


if __name__ == "__main__":
    from src.logger_setup import setup_logging
    from src.billing import init_db

    setup_logging()
    init_db()

    logger.info("Starting Flask webhook server on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False)
