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


@app.route("/", methods=["GET"])
def index():
    """Root endpoint - simple status page."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sports Arb Alert System</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                padding: 50px 40px;
                max-width: 500px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            .icon { font-size: 80px; margin-bottom: 20px; }
            h1 { color: #2d3748; font-size: 32px; margin-bottom: 15px; }
            p { color: #718096; font-size: 18px; line-height: 1.6; margin-bottom: 15px; }
            .status {
                display: inline-block;
                background: #48bb78;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: bold;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">⚡</div>
            <h1>Sports Arb Alert System</h1>
            <div class="status">✓ Service Running</div>
            <p>The arbitrage alert system is running successfully.</p>
            <p style="margin-top: 25px; font-size: 14px; color: #a0aec0;">
                Webhook endpoint: /webhook<br>
                Health check: /health
            </p>
        </div>
    </body>
    </html>
    """, 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "healthy"}), 200


@app.route("/success", methods=["GET"])
def success():
    """Success page after Stripe checkout completion."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome to Premium - Sports Arb Alerts</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                padding: 50px 40px;
                max-width: 500px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            .icon { font-size: 80px; margin-bottom: 20px; }
            h1 { color: #2d3748; font-size: 32px; margin-bottom: 15px; }
            p { color: #718096; font-size: 18px; line-height: 1.6; margin-bottom: 15px; }
            .highlight {
                background: #f7fafc;
                border-left: 4px solid #48bb78;
                padding: 20px;
                margin: 25px 0;
                border-radius: 8px;
                text-align: left;
            }
            .highlight h3 { color: #2d3748; font-size: 16px; margin-bottom: 10px; }
            .highlight ul { list-style: none; padding-left: 0; }
            .highlight li { color: #4a5568; margin: 8px 0; padding-left: 25px; position: relative; }
            .highlight li:before { content: "✓"; position: absolute; left: 0; color: #48bb78; font-weight: bold; }
            .footer { margin-top: 30px; color: #a0aec0; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">🎉</div>
            <h1>Welcome to Premium!</h1>
            <p>Your subscription is now active. You'll receive premium access shortly.</p>

            <div class="highlight">
                <h3>What's Next?</h3>
                <ul>
                    <li>Check your Discord DMs for the premium role</li>
                    <li>Check your Telegram for the premium channel invite</li>
                    <li>You'll now receive spreads and totals alerts</li>
                    <li>All moneyline (h2h) alerts included</li>
                </ul>
            </div>

            <p style="margin-top: 25px;">Premium alerts are sent every 10 minutes when opportunities are found.</p>

            <div class="footer">
                Questions? Contact us in Discord or Telegram
            </div>
        </div>
    </body>
    </html>
    """, 200


@app.route("/cancel", methods=["GET"])
def cancel():
    """Cancel page when user cancels Stripe checkout."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Checkout Canceled - Sports Arb Alerts</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                padding: 50px 40px;
                max-width: 500px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            .icon { font-size: 80px; margin-bottom: 20px; }
            h1 { color: #2d3748; font-size: 32px; margin-bottom: 15px; }
            p { color: #718096; font-size: 18px; line-height: 1.6; margin-bottom: 15px; }
            .box {
                background: #f7fafc;
                border-radius: 12px;
                padding: 25px;
                margin: 25px 0;
            }
            .box h3 { color: #2d3748; font-size: 18px; margin-bottom: 15px; }
            .box p { color: #4a5568; font-size: 16px; }
            code {
                background: #edf2f7;
                padding: 3px 8px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                color: #e53e3e;
            }
            .footer { margin-top: 30px; color: #a0aec0; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">💭</div>
            <h1>Checkout Canceled</h1>
            <p>No worries! You can subscribe anytime.</p>

            <div class="box">
                <h3>How to Subscribe</h3>
                <p>Use the <code>/subscribe</code> command in Discord or Telegram whenever you're ready.</p>
            </div>

            <p style="margin-top: 25px;">You'll continue to receive free moneyline (h2h) alerts in the free channel.</p>

            <div class="footer">
                Questions? Ask in Discord or Telegram
            </div>
        </div>
    </body>
    </html>
    """, 200


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


def run_server():
    """
    Start Flask server on configured host/port.
    Reads PORT from environment (Railway sets this dynamically).
    Can be called from threading or run directly.
    """
    host = "0.0.0.0"
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting Flask webhook server on {host}:{port}...")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    from src.logger_setup import setup_logging
    from src.billing import init_db

    setup_logging()
    init_db()
    run_server()
