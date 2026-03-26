"""
server.py — Flask webhook server for handling Stripe events.
This will be integrated into main.py as a daemon thread.
"""

import os
import logging
import stripe
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
from supabase import create_client
from src.billing import mark_subscribed, cancel_subscription, get_subscription_by_customer
from src.arb_tracker import get_stats, get_recent_arbs, record_feedback, search_arbs

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Initialize Supabase
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))

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


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """JSON API endpoint for stats - for external integrations."""
    days = request.args.get("days", default=30, type=int)
    stats = get_stats(days=days)
    return jsonify(stats), 200


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """Record user feedback on an arb alert."""
    data = request.get_json()
    alert_id = data.get("alert_id")
    user_id = data.get("user_id")
    is_positive = data.get("is_positive", True)

    if not alert_id or not user_id:
        return jsonify({"error": "Missing alert_id or user_id"}), 400

    success = record_feedback(alert_id, user_id, is_positive)

    if success:
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "already_submitted"}), 200


@app.route("/stats", methods=["GET"])
def stats_dashboard():
    """Public stats dashboard with live metrics."""
    days = request.args.get("days", default=30, type=int)
    stats = get_stats(days=days)
    recent_arbs = get_recent_arbs(limit=10)

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Arbitrage Stats Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 40px 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                color: white;
                margin-bottom: 40px;
            }
            .header h1 {
                font-size: 48px;
                margin-bottom: 10px;
            }
            .header p {
                font-size: 18px;
                opacity: 0.9;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }
            .stat-card {
                background: white;
                border-radius: 16px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .stat-card .label {
                font-size: 14px;
                color: #718096;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 10px;
            }
            .stat-card .value {
                font-size: 42px;
                font-weight: bold;
                color: #2d3748;
            }
            .stat-card .unit {
                font-size: 24px;
                color: #718096;
                margin-left: 5px;
            }
            .section {
                background: white;
                border-radius: 16px;
                padding: 30px;
                margin-bottom: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .section h2 {
                font-size: 24px;
                color: #2d3748;
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 2px solid #e2e8f0;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th {
                text-align: left;
                padding: 12px;
                background: #f7fafc;
                color: #4a5568;
                font-weight: 600;
                font-size: 14px;
                text-transform: uppercase;
            }
            td {
                padding: 12px;
                border-bottom: 1px solid #e2e8f0;
                color: #2d3748;
            }
            .badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }
            .badge-success { background: #c6f6d5; color: #22543d; }
            .badge-warning { background: #fef3c7; color: #78350f; }
            .badge-error { background: #fed7d7; color: #742a2a; }
            .badge-active { background: #dbeafe; color: #1e3a8a; }
            .no-data {
                text-align: center;
                padding: 40px;
                color: #718096;
                font-size: 16px;
            }
            .footer {
                text-align: center;
                color: white;
                margin-top: 40px;
                opacity: 0.8;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Arbitrage Stats</h1>
                <p>Last {{ stats.days }} days • Updated in real-time</p>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="label">Total Arbs Found</div>
                    <div class="value">{{ stats.total_arbs }}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Average Margin</div>
                    <div class="value">{{ stats.avg_margin }}<span class="unit">%</span></div>
                </div>
                <div class="stat-card">
                    <div class="label">Success Rate</div>
                    <div class="value">{{ stats.success_rate }}<span class="unit">%</span></div>
                </div>
                <div class="stat-card">
                    <div class="label">User Feedback</div>
                    <div class="value">{{ stats.total_feedback }}</div>
                </div>
            </div>

            {% if stats.top_books %}
            <div class="section">
                <h2>🏆 Top Book Combinations</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Book Combination</th>
                            <th>Count</th>
                            <th>Avg Margin</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for book in stats.top_books %}
                        <tr>
                            <td><strong>{{ book.combo }}</strong></td>
                            <td>{{ book.count }}</td>
                            <td>{{ "%.2f"|format(book.avg_margin) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}

            {% if stats.top_sports %}
            <div class="section">
                <h2>🏀 Top Sports</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Sport</th>
                            <th>Arbs Found</th>
                            <th>Avg Margin</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for sport in stats.top_sports %}
                        <tr>
                            <td><strong>{{ sport.sport }}</strong></td>
                            <td>{{ sport.count }}</td>
                            <td>{{ "%.2f"|format(sport.avg_margin) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}

            {% if recent_arbs %}
            <div class="section">
                <h2>⚡ Recent Alerts</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Game</th>
                            <th>Sport</th>
                            <th>Margin</th>
                            <th>Books</th>
                            <th>Status</th>
                            <th>Feedback</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for arb in recent_arbs %}
                        <tr>
                            <td><strong>{{ arb.game }}</strong></td>
                            <td>{{ arb.sport }}</td>
                            <td>{{ "%.2f"|format(arb.margin_pct) }}%</td>
                            <td>{{ arb.books|join(', ') }}</td>
                            <td>
                                {% if arb.status == 'verified' %}
                                <span class="badge badge-success">Verified</span>
                                {% elif arb.status == 'failed' %}
                                <span class="badge badge-error">Failed</span>
                                {% else %}
                                <span class="badge badge-active">Active</span>
                                {% endif %}
                            </td>
                            <td>
                                👍 {{ arb.feedback_positive }} / 👎 {{ arb.feedback_negative }}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <div class="section">
                <div class="no-data">
                    No recent arbitrage opportunities yet.<br>
                    Check back soon!
                </div>
            </div>
            {% endif %}

            <div class="footer">
                <p>Sports Arbitrage Alert System • Premium Quality Alerts</p>
            </div>
        </div>
    </body>
    </html>
    """, stats=stats, recent_arbs=recent_arbs), 200


@app.route("/history", methods=["GET"])
def history_search():
    """Historical arb database with search filters."""
    # Get query parameters
    sport = request.args.get("sport")
    book_combo = request.args.get("books")
    min_margin = request.args.get("min_margin", type=float)
    max_margin = request.args.get("max_margin", type=float)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Search arbs
    results = search_arbs(
        sport=sport,
        book_combo=book_combo,
        min_margin=min_margin,
        max_margin=max_margin,
        start_date=start_date,
        end_date=end_date,
        limit=100
    )

    # Get unique sports for filter dropdown (simple version)
    try:
        all_sports_result = supabase.table("arb_alerts").select("sport,sport_key").execute()
        unique_sports = list(set((a["sport"], a["sport_key"]) for a in all_sports_result.data))
    except:
        unique_sports = []

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Arb History</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
            h1 { color: #2d3748; margin-bottom: 20px; }
            .filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #4a5568; }
            select, input { width: 100%; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; }
            .buttons { display: flex; gap: 10px; margin-top: 15px; }
            button { background: #667eea; color: white; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            button:hover { background: #5568d3; }
            .btn-clear { background: #718096; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 25px 0; }
            .stat-box { background: #f7fafc; padding: 20px; border-radius: 8px; text-align: center; }
            .stat-value { font-size: 28px; font-weight: bold; color: #667eea; margin-bottom: 5px; }
            .stat-label { color: #718096; font-size: 14px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }
            th { background: #f7fafc; font-weight: bold; color: #4a5568; }
            .no-results { text-align: center; padding: 40px; color: #718096; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Arbitrage History Search</h1>
            <form method="get">
                <div class="filters">
                    <div>
                        <label>Sport:</label>
                        <select name="sport">
                            <option value="">All Sports</option>
                            {% for sport_name, sport_key in unique_sports %}
                            <option value="{{ sport_key }}" {{ 'selected' if sport == sport_key else '' }}>{{ sport_name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label>Min Margin %:</label>
                        <input type="number" step="0.1" name="min_margin" value="{{ min_margin or '' }}" placeholder="e.g., 1.5">
                    </div>
                    <div>
                        <label>Max Margin %:</label>
                        <input type="number" step="0.1" name="max_margin" value="{{ max_margin or '' }}" placeholder="e.g., 3.0">
                    </div>
                    <div>
                        <label>Start Date:</label>
                        <input type="date" name="start_date" value="{{ start_date or '' }}">
                    </div>
                    <div>
                        <label>End Date:</label>
                        <input type="date" name="end_date" value="{{ end_date or '' }}">
                    </div>
                </div>
                <div class="buttons">
                    <button type="submit">🔍 Search</button>
                    <button type="button" class="btn-clear" onclick="window.location.href='/history'">Clear Filters</button>
                </div>
            </form>

            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value">{{ results.stats.count }}</div>
                    <div class="stat-label">Results Found</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{{ "%.2f"|format(results.stats.avg_margin) }}%</div>
                    <div class="stat-label">Avg Margin</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{{ "%.1f"|format(results.stats.success_rate) }}%</div>
                    <div class="stat-label">Success Rate</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{{ results.stats.total_feedback }}</div>
                    <div class="stat-label">User Feedback</div>
                </div>
            </div>

            {% if results.arbs %}
            <table>
                <thead>
                    <tr>
                        <th>Date/Time</th>
                        <th>Game</th>
                        <th>Sport</th>
                        <th>Margin</th>
                        <th>Books</th>
                        <th>Feedback</th>
                    </tr>
                </thead>
                <tbody>
                    {% for arb in results.arbs %}
                    <tr>
                        <td>{{ arb.sent_at[:16].replace('T', ' ') }}</td>
                        <td><strong>{{ arb.game }}</strong></td>
                        <td>{{ arb.sport }}</td>
                        <td>{{ "%.2f"|format(arb.margin_pct) }}%</td>
                        <td>{{ arb.books|join(', ') }}</td>
                        <td>👍 {{ arb.feedback_positive }} / 👎 {{ arb.feedback_negative }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="no-results">
                <p>No results found. Try adjusting your filters or check back later!</p>
            </div>
            {% endif %}
        </div>
    </body>
    </html>
    """, results=results, unique_sports=unique_sports, sport=sport, min_margin=min_margin, max_margin=max_margin, start_date=start_date, end_date=end_date), 200


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
    from src.discord_alerter import grant_premium_access, discord_slash_bot

    try:
        # Schedule the coroutine on the Discord bot's event loop
        # The bot is running in a separate thread, so we use run_coroutine_threadsafe
        loop = discord_slash_bot.loop
        future = asyncio.run_coroutine_threadsafe(grant_premium_access(user_id), loop)
        # Wait for it to complete (with timeout)
        future.result(timeout=10)
        logger.info(f"✅ Discord access granted to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to grant Discord access: {e}")


def revoke_discord_access(user_id: str):
    """
    Revoke premium role from Discord user.
    Calls Discord API via discord_alerter module.
    """
    import asyncio
    from src.discord_alerter import revoke_premium_access, discord_slash_bot

    try:
        # Schedule the coroutine on the Discord bot's event loop
        loop = discord_slash_bot.loop
        future = asyncio.run_coroutine_threadsafe(revoke_premium_access(user_id), loop)
        # Wait for it to complete (with timeout)
        future.result(timeout=10)
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
