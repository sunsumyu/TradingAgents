"""Centralized market type detection from ticker symbols."""

import re

_ASTOCK_6DIGIT = re.compile(r"^\d{6}$")
_ASTOCK_SUFFIX = re.compile(r"^\d{6}\.(SS|SZ)$", re.IGNORECASE)
_ASTOCK_PREFIX = re.compile(r"^(sh|sz)\d{6}$", re.IGNORECASE)
_HK_SUFFIX = re.compile(r"\.HK$", re.IGNORECASE)
_CRYPTO_SUFFIX = re.compile(r"-USD$", re.IGNORECASE)
_LETTERS_ONLY = re.compile(r"^[A-Za-z]+$")
_US_DOT = re.compile(r"^[A-Za-z]+\.[A-Za-z]+$")


def detect_market_type(ticker: str, *, fix_astock: bool = False) -> str:
    """Detect market type from a ticker symbol.

    Returns one of: "astock", "us", "hk", "crypto".
    Falls back to "us" for ambiguous, empty, or None inputs.

    When *fix_astock* is True and the ticker looks like a near-miss A-share
    code (e.g. ``60073X``), the detector returns ``"astock"`` so the caller
    can attempt a corrected lookup.
    """
    t = (ticker or "").strip()

    if _ASTOCK_6DIGIT.match(t):
        return "astock"
    if _ASTOCK_SUFFIX.match(t):
        return "astock"
    if _ASTOCK_PREFIX.match(t):
        return "astock"
    if _HK_SUFFIX.search(t):
        return "hk"
    if _CRYPTO_SUFFIX.search(t):
        return "crypto"
    if _LETTERS_ONLY.match(t):
        return "us"
    if _US_DOT.match(t):
        return "us"

    # Near-miss A-share: 6 chars with 1 letter that looks like a digit
    if fix_astock and _try_fix_astock_ticker(t) is not None:
        return "astock"

    return "us"


def normalize_astock_ticker(ticker: str) -> str:
    """Normalize an A-share ticker to a pure 6-digit code.

    Strips .SS/.SZ suffixes and sh/sz prefixes.
    Returns the input unchanged if it is not an A-share ticker.
    """
    t = ticker.strip()

    m = _ASTOCK_SUFFIX.match(t)
    if m:
        return t[:6]

    m = _ASTOCK_PREFIX.match(t)
    if m:
        return t[2:]

    return t


# Map letters that look like digits on Chinese keyboards / OCR errors
# Includes both visually-similar letters AND adjacent-key typos
_LETTER_TO_DIGIT = {
    # Visually similar
    "O": "0", "o": "0",
    "I": "1", "l": "1",
    "Z": "2", "z": "2",
    "S": "5", "s": "5",
    "G": "6", "g": "6",
    "B": "8", "b": "8",
    # Adjacent keys on QWERTY keyboard
    "X": "3",  # X is next to 3
    "C": "3",  # C is next to 3
    "V": "4",  # V is next to 4
    "D": "3",  # D is next to 3
    "F": "4",  # F is next to 4
}


def _try_fix_astock_ticker(ticker: str) -> str | None:
    """Attempt to fix a near-miss A-share ticker (e.g. '60073X' -> '600733').

    A-share tickers are exactly 6 digits.  If the user typed a 6-char code that
    is *almost* all digits (1-2 letters mixed in), try replacing each letter
    with its visually-similar digit and return the first replacement that is a
    valid 6-digit pure-numeric code.  Returns None when no fix is possible.
    """
    t = ticker.strip().upper()

    # Only attempt on 6-char codes with at least one letter
    if len(t) != 6 or t.isdigit():
        return None

    # Collect positions of non-digit characters
    letter_positions = [i for i, c in enumerate(t) if not c.isdigit()]
    if not letter_positions or len(letter_positions) > 2:
        return None  # too many letters — probably not a typo

    # Try replacing each letter with its likely digit
    for pos in letter_positions:
        letter = t[pos]
        digit = _LETTER_TO_DIGIT.get(letter)
        if digit is None:
            continue
        candidate = t[:pos] + digit + t[pos + 1:]
        if candidate.isdigit() and len(candidate) == 6:
            return candidate

    return None
