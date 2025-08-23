from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    USE_GOOGLE_ROUTES: bool = Field(default=False)
    GOOGLE_MAPS_API_KEY: str | None = None
    TRANSFER_CACHE_TTL_SECONDS: int = 600   # 10 min
    TRANSFER_MAX_CALLS_PER_REQUEST: int = 30  # safety limit

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
