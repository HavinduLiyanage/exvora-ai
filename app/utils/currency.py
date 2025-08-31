"""Currency conversion utilities for Exvora AI."""

from typing import Dict, Optional
from app.config import get_settings

settings = get_settings()

# Stub exchange rates (in production, these would come from a real API)
_EXCHANGE_RATES = {
    "USD": {
        "LKR": 320.0,  # 1 USD = 320 LKR
        "EUR": 0.85,   # 1 USD = 0.85 EUR
        "GBP": 0.75,   # 1 USD = 0.75 GBP
    },
    "LKR": {
        "USD": 1/320.0,
        "EUR": 1/320.0 * 0.85,
        "GBP": 1/320.0 * 0.75,
    },
    "EUR": {
        "USD": 1/0.85,
        "LKR": 1/0.85 * 320.0,
        "GBP": 0.75/0.85,
    },
    "GBP": {
        "USD": 1/0.75,
        "LKR": 1/0.75 * 320.0,
        "EUR": 0.85/0.75,
    }
}

def convert_currency(amount: float, from_currency: str, to_currency: str) -> Optional[float]:
    """Convert amount from one currency to another."""
    if from_currency == to_currency:
        return amount
    
    if from_currency not in _EXCHANGE_RATES or to_currency not in _EXCHANGE_RATES[from_currency]:
        return None
    
    rate = _EXCHANGE_RATES[from_currency][to_currency]
    return amount * rate

def get_currency_from_request(preferences: Optional[Dict] = None, constraints: Optional[Dict] = None) -> str:
    """Extract currency preference from request, fallback to default."""
    # Check preferences first
    if preferences and "currency" in preferences:
        return preferences["currency"]
    
    # Check constraints
    if constraints and "currency" in constraints:
        return constraints["currency"]
    
    # Fallback to default
    return settings.DEFAULT_CURRENCY
