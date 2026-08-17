"""Centralized market type detection from ticker symbols."""

import re

_ASTOCK_6DIGIT = re.compile(r"^\d{6}$")
_ASTOCK_SUFFIX = re.compile(r"^\d{6}\.(SS|SZ)$", re.IGNORECASE)
_ASTOCK_PREFIX = re.compile(r"^(sh|sz)\d{6}$", re.IGNORECASE)
_HK_SUFFIX = re.compile(r"\.HK$", re.IGNORECASE)
_CRYPTO_SUFFIX = re.compile(r"-USD$", re.IGNORECASE)
_LETTERS_ONLY = re.compile(r"^[A-Za-z]+$")
_US_DOT = re.compile(r"^[A-Za-z]+\.[A-Za-z]+$")


def detect_market_type(ticker: str) -> str:
    """Detect market type from a ticker symbol.

    Returns one of: "astock", "us", "hk", "crypto".
    Falls back to "us" for ambiguous, empty, or None inputs.
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
