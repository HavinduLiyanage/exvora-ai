from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    PUBLIC_API_KEY: str | None = None
    ADMIN_API_KEY: str | None = None
    USE_GOOGLE_ROUTES: bool = Field(default=False)
    GOOGLE_MAPS_API_KEY: str | None = None
    TRANSFER_CACHE_TTL_SECONDS: int = 600   # 10 min
    TRANSFER_MAX_CALLS_PER_REQUEST: int = 30  # safety limit
    RATE_LIMIT_PER_MINUTE: int = 50  # max requests per minute per IP (increased for testing)
    SHARE_TTL_MIN: int = 1440  # 24 hours
    RERANK_EMA_ALPHA: float = 0.25
    RANK_W_HEALTH: float = 0.1
    SAFETY_CROWD_PENALTY: float = 0.2
    
    # P2: Currency
    DEFAULT_CURRENCY: str = Field(default="USD", description="Default currency for responses")
    
    # P1: Rules and filtering
    RADIUS_KM_LIGHT: float = Field(default=5.0, description="Radius in km for light pace")
    RADIUS_KM_MODERATE: float = Field(default=15.0, description="Radius in km for moderate pace")
    RADIUS_KM_INTENSE: float = Field(default=30.0, description="Radius in km for intense pace")
    
    # P1: Ranking weights
    RANK_W_PREF: float = Field(default=0.35, description="Weight for preference fit")
    RANK_W_TIME: float = Field(default=0.25, description="Weight for time fit")
    RANK_W_BUDGET: float = Field(default=0.20, description="Weight for budget fit")
    RANK_W_DIV: float = Field(default=0.10, description="Weight for diversity")
    RANK_W_HEALTH: float = Field(default=0.10, description="Weight for health fit")
    
    # P1: Scheduling
    BREAK_AFTER_MINUTES: int = Field(default=180, description="Insert break after continuous activity")
    
    # P1: Google verification
    GOOGLE_PER_REQUEST_MAX_CALLS: int = Field(default=30, description="Max Google API calls per request")
    GOOGLE_VERIFY_FAILURE_424: bool = Field(default=False, description="Return 424 on Google verification failure")

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Legacy compatibility (deprecated, use get_settings() instead)
USE_GOOGLE_ROUTES = get_settings().USE_GOOGLE_ROUTES
RANK_WEIGHTS = {
    "budget_fit": 0.6,
    "time_fit": 0.4,
    "theme_bonus": 0.1
}
MAX_ITEMS_PER_DAY = 4
API_TITLE = "Exvora Stateless Itinerary API"
API_VERSION = "0.1.0"
