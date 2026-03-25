"""
discord_alerter.py — Sends arb alerts to a Discord channel as rich embeds.
"""

import os
import logging
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from src.arb_calculator import ArbOpportunity
import stripe

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


def build_embed(arb: ArbOpportunity) -> discord.Embed:
    market_label = MARKET_LABELS.get(arb.market, arb.market.upper())
    color = COLOR_MAP.get(arb.emoji, 0xAAAAAA)

    embed = discord.Embed(
        title=f"{arb.emoji} Arb Alert — {arb.margin_pct:.2f}% Margin",
        description=f"**{arb.game}**\n{arb.sport} · {market_label}",
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


async def _send_embed(arb: ArbOpportunity, channel_id: int = None):
    """Send arb alert embed to specified Discord channel."""
    if channel_id is None:
        channel_id = CHANNEL_ID

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(channel_id)
            if channel is None:
                channel = await client.fetch_channel(channel_id)
            embed = build_embed(arb)
            await channel.send(embed=embed)
            logger.info(f"Discord alert sent to channel {channel_id}: {arb.game} | {arb.margin_pct:.2f}%")
        except Exception as e:
            logger.error(f"Discord send error: {e}")
        finally:
            await client.close()

    await client.start(BOT_TOKEN)


def send_discord_alert(arb: ArbOpportunity, channel_id: int = None):
    """Synchronous wrapper — runs the async Discord send in a fresh event loop."""
    try:
        asyncio.run(_send_embed(arb, channel_id))
    except Exception as e:
        logger.error(f"Discord alerter failed: {e}")


def send_discord_alerts(arbs: list[ArbOpportunity], channel_id: int = None):
    """Send multiple arb alerts to the specified Discord channel."""
    for arb in arbs:
        send_discord_alert(arb, channel_id)


# ============================================================================
# Discord Bot with Slash Commands
# ============================================================================

def setup_discord_bot():
    """
    Create persistent Discord bot with slash commands for subscription.
    This bot runs in a separate thread from the alert sending client.
    """
    intents = discord.Intents.default()
    intents.members = True  # Required for role assignment
    intents.guilds = True

    bot = commands.Bot(command_prefix="/", intents=intents)

    @bot.event
    async def on_ready():
        try:
            await bot.tree.sync()
            logger.info(f"Discord bot ready: {bot.user} (slash commands synced)")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

    @bot.tree.command(
        name="subscribe",
        description="Subscribe to premium arbitrage alerts (spreads & totals)"
    )
    async def subscribe(interaction: discord.Interaction):
        """Handle /subscribe slash command - create Stripe checkout session."""
        try:
            # Create Stripe checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': STRIPE_PRICE_ID,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=STRIPE_SUCCESS_URL,
                cancel_url=STRIPE_CANCEL_URL,
                metadata={
                    'user_id': str(interaction.user.id),
                    'platform': 'discord',
                }
            )

            await interaction.response.send_message(
                f"🔗 **Subscribe here:** {session.url}\n\n"
                f"✨ Premium includes:\n"
                f"• All h2h (moneyline) alerts\n"
                f"• Spreads alerts\n"
                f"• Totals alerts\n\n"
                f"You'll get access to the premium channel after payment!",
                ephemeral=True  # Only visible to the user
            )

            logger.info(f"Stripe checkout created for Discord user {interaction.user.id}")

        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            await interaction.response.send_message(
                "❌ Sorry, something went wrong. Please try again later.",
                ephemeral=True
            )

    return bot


async def grant_premium_access(user_id: str):
    """
    Grant premium role to Discord user.
    Called from webhook after successful subscription.
    """
    try:
        # Get the bot instance (will be set in main.py)
        if not hasattr(discord_slash_bot, 'guilds') or not discord_slash_bot.guilds:
            logger.warning(f"Bot not ready, cannot grant access to user {user_id}")
            return

        guild = discord_slash_bot.get_guild(GUILD_ID)
        if guild is None:
            guild = await discord_slash_bot.fetch_guild(GUILD_ID)

        member = await guild.fetch_member(int(user_id))
        role = guild.get_role(PREMIUM_ROLE_ID)

        if role is None:
            logger.error(f"Premium role {PREMIUM_ROLE_ID} not found")
            return

        await member.add_roles(role, reason="Premium subscription activated")
        logger.info(f"✅ Granted premium role to Discord user {user_id}")

    except discord.NotFound:
        logger.error(f"Discord user {user_id} not found in guild {GUILD_ID}")
    except discord.Forbidden:
        logger.error(f"Bot lacks permission to assign roles in guild {GUILD_ID}")
    except Exception as e:
        logger.error(f"Failed to grant Discord access to user {user_id}: {e}")


async def revoke_premium_access(user_id: str):
    """
    Revoke premium role from Discord user.
    Called from webhook after subscription cancellation.
    """
    try:
        # Get the bot instance (will be set in main.py)
        if not hasattr(discord_slash_bot, 'guilds') or not discord_slash_bot.guilds:
            logger.warning(f"Bot not ready, cannot revoke access from user {user_id}")
            return

        guild = discord_slash_bot.get_guild(GUILD_ID)
        if guild is None:
            guild = await discord_slash_bot.fetch_guild(GUILD_ID)

        member = await guild.fetch_member(int(user_id))
        role = guild.get_role(PREMIUM_ROLE_ID)

        if role is None:
            logger.error(f"Premium role {PREMIUM_ROLE_ID} not found")
            return

        await member.remove_roles(role, reason="Premium subscription canceled")
        logger.info(f"✅ Revoked premium role from Discord user {user_id}")

    except discord.NotFound:
        logger.error(f"Discord user {user_id} not found in guild {GUILD_ID}")
    except discord.Forbidden:
        logger.error(f"Bot lacks permission to remove roles in guild {GUILD_ID}")
    except Exception as e:
        logger.error(f"Failed to revoke Discord access from user {user_id}: {e}")


# Create bot instance (will be used by main.py)
discord_slash_bot = setup_discord_bot()
