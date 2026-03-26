"""
state_books.py — Mapping of US states to legal sportsbooks.
"""

# State → Legal Sportsbooks Mapping
# Based on current legal sports betting states (2026)
STATE_BOOKS = {
    "AZ": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers", "ESPN BET"],
    "AR": ["BetlyAR"],  # Limited market
    "CO": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "PointsBet", "BetRivers"],
    "CT": ["DraftKings", "FanDuel"],
    "DE": ["DraftKings"],  # Limited online options
    "FL": ["Hard Rock Bet"],  # Tribal-only
    "IL": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers", "PointsBet"],
    "IN": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers"],
    "IA": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook"],
    "KS": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook"],
    "KY": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "ESPN BET"],
    "LA": ["DraftKings", "Caesars Sportsbook", "BetRivers"],
    "ME": ["DraftKings", "FanDuel", "Caesars Sportsbook"],
    "MD": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers"],
    "MA": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "WynnBET"],
    "MI": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "PointsBet", "BetRivers"],
    "MS": [],  # Retail only
    "NV": ["DraftKings", "BetMGM", "Caesars Sportsbook", "WynnBET"],
    "NH": ["DraftKings"],
    "NJ": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers", "PointsBet", "Unibet"],
    "NM": [],  # Tribal retail only
    "NY": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers", "PointsBet", "WynnBET"],
    "NC": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "ESPN BET", "Fanatics Sportsbook"],
    "OH": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers"],
    "OR": [],  # State lottery only
    "PA": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers", "ESPN BET"],
    "RI": ["DraftKings"],  # State lottery partnership
    "TN": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "ESPN BET"],
    "VA": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook", "BetRivers", "ESPN BET"],
    "VT": ["DraftKings", "FanDuel"],
    "WV": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook"],
    "WY": ["DraftKings"],
    "DC": ["DraftKings", "FanDuel", "BetMGM", "Caesars Sportsbook"],
}

# States where online sports betting is legal
LEGAL_STATES = set(STATE_BOOKS.keys())


def get_books_for_state(state: str) -> list[str]:
    """Get list of legal books for a state."""
    return STATE_BOOKS.get(state.upper(), [])


def is_arb_valid_for_state(arb_books: list[str], state: str) -> bool:
    """Check if an arb's books are all legal in a given state."""
    if not state:
        return True  # No state restriction

    legal_books = get_books_for_state(state)
    if not legal_books:
        return False  # No legal books in this state

    # All arb books must be legal in the state
    return all(book in legal_books for book in arb_books)


def filter_arbs_by_state(arbs: list, state: str) -> list:
    """
    Filter a list of arbs to only those valid in a given state.

    Args:
        arbs: List of ArbOpportunity objects
        state: US state code (e.g., "NY", "NJ")

    Returns:
        Filtered list of arbs valid for the state
    """
    if not state:
        return arbs

    legal_books = get_books_for_state(state)
    if not legal_books:
        return []

    return [
        arb for arb in arbs
        if all(leg["book"] in legal_books for leg in arb.legs)
    ]


def get_states_for_book(book: str) -> list[str]:
    """Get list of states where a book is legal."""
    return [state for state, books in STATE_BOOKS.items() if book in books]
