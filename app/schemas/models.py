from datetime import date as Date, time as Time
from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field


# Trip Context Models
class DateRange(BaseModel):
    start: Date
    end: Date


class DayTemplate(BaseModel):
    start: Time
    end: Time
    pace: Literal["light", "moderate", "intense"]


class TripContext(BaseModel):
    base_place_id: str
    date_range: DateRange
    day_template: DayTemplate
    modes: List[Literal["DRIVE", "WALK"]]


# Preferences and Constraints
class Preferences(BaseModel):
    themes: Optional[List[str]] = None
    activity_tags: Optional[List[str]] = None
    avoid_tags: Optional[List[str]] = None
    budget_range: Optional[float] = None


class Constraints(BaseModel):
    daily_budget_cap: Optional[float] = None
    max_transfer_minutes: Optional[int] = None


# Lock Model
class Lock(BaseModel):
    date: Optional[Date] = None
    place_id: str
    start: Optional[Time] = None
    end: Optional[Time] = None


# Request Models
class ItineraryRequest(BaseModel):
    trip_context: TripContext
    preferences: Preferences
    constraints: Optional[Constraints] = None
    locks: List[Lock] = Field(default_factory=list)


# Response Models
class Activity(BaseModel):
    start: Time
    end: Time
    place_id: str
    title: Optional[str] = None
    estimated_cost: Optional[float] = None


class Transfer(BaseModel):
    type: Literal["transfer"] = "transfer"
    from_place_id: str
    to_place_id: str
    mode: Literal["DRIVE", "WALK"]
    duration_minutes: int
    distance_km: float
    source: Literal["heuristic", "google_routes_live"]


class Summary(BaseModel):
    title: Optional[str] = None
    est_cost: Optional[float] = None
    walking_km: Optional[float] = None
    health_load: Optional[str] = None


class DayPlan(BaseModel):
    date: Date
    summary: Summary
    items: List[Union[Activity, Transfer]]


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
    date: Date
    base_place_id: str
    day_template: DayTemplate
    modes: List[Literal["DRIVE", "WALK"]]
    preferences: Optional[Preferences] = None
    constraints: Optional[Constraints] = None
    locks: List[Lock] = Field(default_factory=list)
    current_day_plan: DayPlan
    actions: List[FeedbackAction]
