"""
discord_alerter.py — Sends arb alerts to Discord with feedback buttons.
Uses persistent bot for slash commands and alert sending.
"""

import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from src.arb_calculator import ArbOpportunity
import stripe
import requests

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0"))
PREMIUM_ROLE_ID = int(os.getenv("DISCORD_PREMIUM_ROLE_ID", "0"))

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://example.com/success")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://example.com/cancel")

logger = logging.getLogger(__name__)

MARKET_LABELS = {
    "h2h": "Moneyline",
    "spreads": "Spreads",
    "totals": "Totals",
}

COLOR_MAP = {
    "🟢": 0x2ECC71,  # green
    "🟡": 0xF1C40F,  # yellow
    "⚪": 0xECF0F1,  # light gray
}


class FeedbackView(discord.ui.View):
    """Interactive buttons for user feedback on arb alerts."""

    def __init__(self, alert_id: str):
        super().__init__(timeout=None)  # Buttons never timeout
        self.alert_id = alert_id

    @discord.ui.button(label="✅ Worked", style=discord.ButtonStyle.success, custom_id="feedback_yes")
    async def feedback_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        """User confirms the arb worked."""
        try:
            # Call feedback API
            response = requests.post(
                f"{os.getenv('RAILWAY_URL', 'http://localhost:5000')}/api/feedback",
                json={
                    "alert_id": self.alert_id,
                    "user_id": str(interaction.user.id),
                    "is_positive": True
                }
            )

            if response.status_code == 200:
                await interaction.response.send_message(
                    "✅ Thanks for the feedback! Glad it worked.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "You've already given feedback on this arb!",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Feedback API error: {e}")
            await interaction.response.send_message(
                "❌ Failed to record feedback. Try again later.",
                ephemeral=True
            )

    @discord.ui.button(label="❌ Failed", style=discord.ButtonStyle.danger, custom_id="feedback_no")
    async def feedback_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        """User reports the arb didn't work."""
        try:
            response = requests.post(
                f"{os.getenv('RAILWAY_URL', 'http://localhost:5000')}/api/feedback",
                json={
                    "alert_id": self.alert_id,
                    "user_id": str(interaction.user.id),
                    "is_positive": False
                }
            )

            if response.status_code == 200:
                await interaction.response.send_message(
                    "❌ Thanks for the feedback. We'll improve our filters!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "You've already given feedback on this arb!",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Feedback API error: {e}")
            await interaction.response.send_message(
                "❌ Failed to record feedback. Try again later.",
                ephemeral=True
            )


def build_embed(arb: ArbOpportunity) -> discord.Embed:
    """Build Discord embed for an arb alert."""
    market_label = MARKET_LABELS.get(arb.market, arb.market.upper())
    color = COLOR_MAP.get(arb.emoji, 0xAAAAAA)

    # Add urgency indicator to title
    urgency = getattr(arb, 'urgency', '🟡 MEDIUM')
    poll_count = getattr(arb, 'poll_count', 1)

    # Build stability indicator
    if poll_count >= 3:
        stability = "🟢 STABLE"
    elif poll_count == 2:
        stability = "✅ CONFIRMED"
    else:
        stability = "⚡ NEW"

    embed = discord.Embed(
        title=f"{urgency} | {arb.emoji} Arb Alert — {arb.margin_pct:.2f}% Margin",
        description=f"**{arb.game}**\n{arb.sport} · {market_label}\n{stability} (seen {poll_count}x)",
        color=color,
    )

    for leg in arb.legs:
        odds_str = f"+{leg['odds']}" if leg['odds'] > 0 else str(leg['odds'])
        embed.add_field(
            name=f"📌 {leg['outcome']}",
            value=(
                f"**Book:** {leg['book']}\n"
                f"**Odds:** {odds_str}\n"
                f"**Implied:** {leg['implied_pct']}%\n"
                f"**Stake (${100:.0f} base):** ${leg['stake']:.2f}"
            ),
            inline=True,
        )

    embed.add_field(
        name="📊 Summary",
        value=(
            f"Total implied: {sum(l['implied_pct'] for l in arb.legs):.2f}%\n"
            f"Guaranteed profit on $100: **${arb.margin_pct:.2f}**"
        ),
        inline=False,
    )

    embed.set_footer(text=f"Game time: {arb.commence_time[:16].replace('T', ' ')} UTC")
    return embed


def send_discord_alert(arb: ArbOpportunity, channel_id: int = None):
    """Send alert using the persistent bot (non-blocking)."""
    # This will be called from the persistent bot's send_alert method
    pass  # Placeholder - actual sending happens via bot


def send_discord_alerts(arbs: list[ArbOpportunity], channel_id: int = None):
    """Queue alerts to be sent by the persistent bot."""
    # Store alerts in bot's queue
    for arb in arbs:
        discord_slash_bot.alert_queue.append((arb, channel_id))


# ============================================================================
# Discord Bot with Slash Commands and Alert Sending
# ============================================================================

def setup_discord_bot():
    """
    Create persistent Discord bot with slash commands and alert sending.
    """
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True
    intents.message_content = False  # Don't need message content

    bot = commands.Bot(command_prefix="/", intents=intents)
    bot.alert_queue = []  # Queue for alerts to send

    @bot.event
    async def on_ready():
        try:
            await bot.tree.sync()
            logger.info(f"Discord bot ready: {bot.user} (slash commands synced)")

            # Start background task to process alert queue
            bot.loop.create_task(process_alert_queue())
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    async def process_alert_queue():
        """Background task to send queued alerts."""
        await bot.wait_until_ready()
        while not bot.is_closed():
            try:
                if bot.alert_queue:
                    arb, channel_id = bot.alert_queue.pop(0)

                    # Get channel
                    target_channel_id = channel_id or CHANNEL_ID
                    channel = bot.get_channel(target_channel_id)
                    if channel is None:
                        channel = await bot.fetch_channel(target_channel_id)

                    # Build embed and view
                    embed = build_embed(arb)
                    view = FeedbackView(alert_id=arb.alert_id) if hasattr(arb, 'alert_id') else None

                    # Send message with or without buttons
                    if view:
                        await channel.send(embed=embed, view=view)
                    else:
                        await channel.send(embed=embed)

                    logger.info(f"Discord alert sent to channel {target_channel_id}: {arb.game} | {arb.margin_pct:.2f}%")

                await asyncio.sleep(2)  # Rate limit protection
            except Exception as e:
                logger.error(f"Error processing alert queue: {e}")
                await asyncio.sleep(5)

    @bot.tree.command(name="subscribe", description="Subscribe to premium arbitrage alerts")
    async def subscribe(interaction: discord.Interaction):
        """Handle /subscribe command."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': STRIPE_PRICE_ID, 'quantity': 1}],
                mode='subscription',
                success_url=STRIPE_SUCCESS_URL,
                cancel_url=STRIPE_CANCEL_URL,
                metadata={
                    'user_id': str(interaction.user.id),
                    'platform': 'discord',
                }
            )

            await interaction.response.send_message(
                f"🔗 **Subscribe to Premium**\n\n"
                f"Click here to subscribe: {session.url}\n\n"
                f"✨ **Premium Benefits:**\n"
                f"• All markets (h2h, spreads, totals)\n"
                f"• High-quality filtered alerts\n"
                f"• Verified book combinations\n"
                f"• Real-time notifications\n\n"
                f"Support the service and get the best arb opportunities!",
                ephemeral=True
            )
            logger.info(f"Stripe checkout created for Discord user {interaction.user.id}")
        except Exception as e:
            logger.error(f"Stripe checkout error: {e}")
            await interaction.response.send_message(
                "❌ Failed to create checkout session. Please try again later.",
                ephemeral=True
            )

    @bot.tree.command(name="manage", description="Manage your subscription (cancel, update payment)")
    async def manage_subscription(interaction: discord.Interaction):
        """Handle /manage command - opens Stripe Customer Portal."""
        try:
            from src.billing import supabase

            # Get user's subscription from database
            result = supabase.table("subscriptions").select("stripe_customer_id").eq(
                "user_id", str(interaction.user.id)
            ).eq("platform", "discord").execute()

            if not result.data or not result.data[0].get("stripe_customer_id"):
                await interaction.response.send_message(
                    "❌ **No Active Subscription**\n\n"
                    "You don't have an active subscription.\n"
                    "Use `/subscribe` to get started!",
                    ephemeral=True
                )
                return

            customer_id = result.data[0]["stripe_customer_id"]

            # Create Customer Portal session
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=STRIPE_SUCCESS_URL,
            )

            await interaction.response.send_message(
                f"🔗 **Manage Your Subscription**\n\n"
                f"Click here to manage your subscription: {portal_session.url}\n\n"
                f"You can:\n"
                f"• Cancel your subscription\n"
                f"• Update payment method\n"
                f"• View billing history\n"
                f"• Download invoices",
                ephemeral=True
            )
            logger.info(f"Customer portal created for Discord user {interaction.user.id}")

        except Exception as e:
            logger.error(f"Customer portal error: {e}")
            await interaction.response.send_message(
                "❌ Failed to create portal session. Please try again later.",
                ephemeral=True
            )

    return bot


# Create the persistent bot instance
import asyncio
discord_slash_bot = setup_discord_bot()


# Grant/revoke premium access (called from webhooks)
async def grant_premium_access(user_id: str):
    """Grant premium role to Discord user."""
    try:
        guild = discord_slash_bot.get_guild(GUILD_ID)
        if guild is None:
            guild = await discord_slash_bot.fetch_guild(GUILD_ID)

        member = await guild.fetch_member(int(user_id))
        role = guild.get_role(PREMIUM_ROLE_ID)

        if role:
            await member.add_roles(role)
            logger.info(f"✅ Granted premium access to Discord user {user_id}")
        else:
            logger.error(f"Premium role {PREMIUM_ROLE_ID} not found")
    except Exception as e:
        logger.error(f"Failed to grant Discord premium access: {e}")


async def revoke_premium_access(user_id: str):
    """Revoke premium role from Discord user."""
    try:
        guild = discord_slash_bot.get_guild(GUILD_ID)
        if guild is None:
            guild = await discord_slash_bot.fetch_guild(GUILD_ID)

        member = await guild.fetch_member(int(user_id))
        role = guild.get_role(PREMIUM_ROLE_ID)

        if role:
            await member.remove_roles(role)
            logger.info(f"✅ Revoked premium access from Discord user {user_id}")
        else:
            logger.error(f"Premium role {PREMIUM_ROLE_ID} not found")
    except Exception as e:
        logger.error(f"Failed to revoke Discord premium access: {e}")
