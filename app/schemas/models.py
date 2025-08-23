from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field


# Trip Context Models
class TripDateRange(BaseModel):
    start: str  # "YYYY-MM-DD"
    end: str


class DayTemplate(BaseModel):
    start: str  # "HH:MM"
    end: str    # "HH:MM"
    pace: Literal["light", "moderate", "intense"]


class TripContext(BaseModel):
    base_place_id: str
    date_range: TripDateRange
    day_template: DayTemplate
    modes: List[str]


class TripContext(BaseModel):
    base_place_id: str
    date_range: TripDateRange
    day_template: DayTemplate
    modes: List[str]


# Preferences and Constraints
class Preferences(BaseModel):
    themes: List[str] = []
    activity_tags: List[str] = []
    avoid_tags: List[str] = []


class Constraints(BaseModel):
    daily_budget_cap: Optional[float] = None
    max_transfer_minutes: Optional[int] = None


# Lock Model
class Lock(BaseModel):
    place_id: str
    start: Optional[str] = None  # "HH:MM" (optional)
    end: Optional[str] = None    # "HH:MM" (optional)
    title: Optional[str] = None


# Request Models
class ItineraryRequest(BaseModel):
    trip_context: TripContext
    preferences: Preferences
    constraints: Optional[Constraints] = None
    locks: List[Lock] = []


# Response Models
class Activity(BaseModel):
    start: str
    end: str
    place_id: str
    title: Optional[str] = None
    estimated_cost: Optional[float] = 0


class Transfer(BaseModel):
    type: Literal["transfer"]
    from_place_id: str
    to_place_id: str
    mode: str
    duration_minutes: int
    distance_km: float
    source: Literal["heuristic","google_routes_live"]


class Summary(BaseModel):
    title: Optional[str] = None
    est_cost: Optional[float] = None
    walking_km: Optional[float] = None
    health_load: Optional[str] = None


class DayPlan(BaseModel):
    date: str
    summary: dict
    items: List[dict]  # Activity | Transfer


class Totals(BaseModel):
    total_cost: Optional[float] = None
    total_walking_km: Optional[float] = None
    total_duration_hours: Optional[float] = None


class ItineraryResponse(BaseModel):
    currency: Literal["LKR"] = "LKR"
    days: List[DayPlan]
    totals: Optional[Totals] = None


# Feedback Models
class FeedbackAction(BaseModel):
    type: Literal["rate_item", "remove_item", "request_alternative", "edit_time", "daily_signal"]
    place_id: Optional[str] = None
    rating: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    near_place_id: Optional[str] = None
    max_transfer_minutes: Optional[int] = None


class FeedbackRequest(BaseModel):
    date: str
    base_place_id: str
    day_template: DayTemplate
    modes: List[str]
    preferences: Optional[Preferences] = None
    constraints: Optional[Constraints] = None
    locks: List[Lock] = []
    current_day_plan: DayPlan
    actions: List[FeedbackAction]
