"""Configuration settings for the Exvora API."""

import os

# Feature flags
USE_GOOGLE_ROUTES = os.getenv("USE_GOOGLE_ROUTES", "false").lower() == "true"

# Ranking weights
RANK_WEIGHTS = {
    "budget_fit": 0.6,
    "time_fit": 0.4,
    "theme_bonus": 0.1
}

# Scheduling constraints
MAX_ITEMS_PER_DAY = int(os.getenv("MAX_ITEMS_PER_DAY", "4"))

# API settings
API_TITLE = "Exvora Stateless Itinerary API"
API_VERSION = "0.1.0"
