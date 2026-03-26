"""
arb_calculator.py — Detects arbitrage opportunities from odds data.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MIN_MARGIN_PCT = 1.5   # Only alert on arbs ≥ 1.5%
MAX_MARGIN_PCT = 8.0   # Skip arbs > 8% as likely data errors
BASE_STAKE = 100.0     # Dollar amount for stake split calculation

# Books with known stale lines - skip if ALL legs come from these
EXCLUDED_BOOKS = {"LowVig.ag", "MyBookie.ag", "BetUS"}


@dataclass
class ArbOpportunity:
    sport: str
    sport_key: str
    game: str
    commence_time: str
    market: str
    margin_pct: float
    legs: list[dict] = field(default_factory=list)   # [{outcome, book, odds, stake}]

    @property
    def emoji(self) -> str:
        if self.margin_pct >= 3.0:
            return "🟢"
        elif self.margin_pct >= 2.0:
            return "🟡"
        else:
            return "⚪"


def american_to_implied(odds: int | float) -> float:
    """Convert American odds to implied probability (0–1)."""
    odds = float(odds)
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return abs(odds) / (abs(odds) + 100.0)


def implied_to_decimal(implied: float) -> float:
    """Convert implied probability to decimal odds."""
    if implied == 0:
        return 0.0
    return 1.0 / implied


def optimal_stakes(implied_probs: list[float], base: float = BASE_STAKE) -> list[float]:
    """
    Given implied probs for each leg, return stakes that guarantee equal profit.
    stake_i = base * implied_i / sum(implied_i)   [Kelly-style proportional split]
    """
    total = sum(implied_probs)
    return [(p / total) * base for p in implied_probs]


def find_arbs(events: list[dict]) -> list[ArbOpportunity]:
    """
    Scan all events and markets for arbitrage opportunities.
    Returns a list of ArbOpportunity objects above the minimum margin threshold.
    """
    opportunities: list[ArbOpportunity] = []

    for event in events:
        sport_key = event.get("sport_key", "")
        sport_title = event.get("sport_title", sport_key)
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        game = f"{away} @ {home}"
        commence = event.get("commence_time", "")
        bookmakers = event.get("bookmakers", [])

        # Collect all markets present in this event
        market_keys: set[str] = set()
        for bm in bookmakers:
            for mkt in bm.get("markets", []):
                market_keys.add(mkt["key"])

        for market_key in market_keys:
            # For each outcome name, track best (lowest implied prob = best odds) per book
            best_by_outcome: dict[str, dict] = {}  # outcome_name -> {book, odds, implied}

            for bm in bookmakers:
                book_name = bm.get("title", "Unknown")
                for mkt in bm.get("markets", []):
                    if mkt["key"] != market_key:
                        continue
                    for outcome in mkt.get("outcomes", []):
                        name = outcome["name"]
                        price = outcome["price"]

                        # For spreads markets, include point value in outcome key
                        # to distinguish e.g. "Pirates +1.5" from "Pirates -1.5"
                        outcome_key = name
                        if market_key == "spreads" and "point" in outcome:
                            point = outcome["point"]
                            outcome_key = f"{name} {point:+.1f}"

                        try:
                            imp = american_to_implied(price)
                        except Exception:
                            continue

                        # We want the LOWEST implied probability = best payout odds
                        if outcome_key not in best_by_outcome or imp < best_by_outcome[outcome_key]["implied"]:
                            best_by_outcome[outcome_key] = {
                                "outcome": outcome_key,
                                "book": book_name,
                                "odds": price,
                                "implied": imp,
                            }

            if len(best_by_outcome) < 2:
                continue

            total_implied = sum(v["implied"] for v in best_by_outcome.values())
            if total_implied >= 1.0:
                continue  # No arb

            margin_pct = round((1.0 - total_implied) * 100, 4)

            if margin_pct < MIN_MARGIN_PCT:
                continue

            # Sanity check: skip suspiciously high margins (likely data errors)
            if margin_pct > MAX_MARGIN_PCT:
                logger.warning(
                    f"SKIPPED (margin too high): {game} | {market_key} | "
                    f"margin={margin_pct:.2f}% (threshold: {MAX_MARGIN_PCT}%)"
                )
                continue

            # Calculate optimal stakes
            outcomes_list = list(best_by_outcome.values())
            implied_list = [o["implied"] for o in outcomes_list]
            stakes = optimal_stakes(implied_list, BASE_STAKE)

            legs = []
            for o, stake in zip(outcomes_list, stakes):
                legs.append({
                    "outcome": o["outcome"],
                    "book": o["book"],
                    "odds": o["odds"],
                    "implied_pct": round(o["implied"] * 100, 2),
                    "stake": round(stake, 2),
                })

            # Filter 1: Skip if ALL books are from excluded list (stale lines)
            books_used = {leg["book"] for leg in legs}
            if books_used.issubset(EXCLUDED_BOOKS):
                logger.warning(
                    f"SKIPPED (all books excluded): {game} | {market_key} | "
                    f"margin={margin_pct:.2f}% | books={list(books_used)}"
                )
                continue

            # Filter 2: For h2h markets, check for impossible two-positive odds
            if market_key == "h2h" and len(legs) == 2:
                odds_leg1 = legs[0]["odds"]
                odds_leg2 = legs[1]["odds"]
                if odds_leg1 > 0 and odds_leg2 > 0:
                    logger.warning(
                        f"SKIPPED (both odds positive): {game} | {market_key} | "
                        f"odds={odds_leg1:+d} vs {odds_leg2:+d} (mathematically impossible)"
                    )
                    continue

            arb = ArbOpportunity(
                sport=sport_title,
                sport_key=sport_key,
                game=game,
                commence_time=commence,
                market=market_key,
                margin_pct=margin_pct,
                legs=legs,
            )
            opportunities.append(arb)
            logger.info(
                f"ARB FOUND: {game} | {market_key} | margin={margin_pct:.2f}% | "
                f"books={[l['book'] for l in legs]}"
            )

    logger.info(f"Total arb opportunities found: {len(opportunities)}")
    return opportunities
