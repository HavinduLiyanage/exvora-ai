from typing import List, Optional, Union, Literal, Annotated, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, date, time


# Basic Models
class Coords(BaseModel):
    lat: float
    lng: float


# Trip Context Models
class TripDateRange(BaseModel):
    start: str  # "YYYY-MM-DD"
    end: str  # "YYYY-MM-DD"
    
    @field_validator('end')
    @classmethod
    def validate_date_range(cls, v, info):
        start = info.data.get('start')
        if start:
            start_date = datetime.fromisoformat(start)
            end_date = datetime.fromisoformat(v)
            days_diff = (end_date - start_date).days + 1
            if days_diff > 14:
                raise ValueError(f"Trip duration {days_diff} days exceeds maximum of 14 days")
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "start": "2025-09-10",
            "end": "2025-09-14"
        }
    })


class DayTemplate(BaseModel):
    start: str  # "HH:MM"
    end: str    # "HH:MM"
    pace: Literal["light", "moderate", "intense"]
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "start": "08:30",
            "end": "20:00",
            "pace": "moderate"
        }
    })


class TripContext(BaseModel):
    base_place_id: str
    date_range: TripDateRange
    day_template: DayTemplate
    modes: List[str]
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-14"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE", "WALK"]
        }
    })


# Preferences and Constraints
class Preferences(BaseModel):
    themes: List[str] = []
    activity_tags: List[str] = []
    avoid_tags: List[str] = []
    currency: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "themes": ["Nature", "Food", "History"],
            "activity_tags": ["Hiking", "Local Cuisine"],
            "avoid_tags": ["nightlife"]
        }
    })


class Constraints(BaseModel):
    daily_budget_cap: Optional[float] = None
    max_transfer_minutes: Optional[int] = None
    currency: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "daily_budget_cap": 120,
            "max_transfer_minutes": 90
        }
    })


# Lock Model
class Lock(BaseModel):
    place_id: str
    start: Optional[str] = None  # "HH:MM" (optional)
    end: Optional[str] = None    # "HH:MM" (optional)
    title: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "place_id": "ChIJlocked",
            "start": "14:00",
            "end": "15:00",
            "title": "Reserved Lunch"
        }
    })


# Audit Log Models
class FeedbackEvent(BaseModel):
    poi_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    tags: List[str] = Field(default_factory=list)
    comment: Optional[str] = None
    ts: Optional[str] = None

class AuditLog(BaseModel):
    feedback_events: List[FeedbackEvent] = Field(default_factory=list)

# Request Models
class ItineraryRequest(BaseModel):
    trip_context: TripContext
    preferences: Preferences
    constraints: Optional[Constraints] = None
    locks: List[Lock] = []
    audit_log: Optional[AuditLog] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "trip_context": {
                "base_place_id": "ChIJbase",
                "date_range": {"start": "2025-09-10", "end": "2025-09-14"},
                "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
                "modes": ["DRIVE", "WALK"]
            },
            "preferences": {"themes": ["Culture"], "avoid_tags": ["nightlife"]},
            "constraints": {"daily_budget_cap": 120},
            "locks": []
        }
    })


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
    duration_minutes: Optional[int] = None
    distance_km: Optional[float] = None
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
    notes: Optional[List[str]] = None


class Totals(BaseModel):
    trip_cost_est: Optional[float] = None
    trip_transfer_minutes: Optional[int] = None
    daily: Optional[List[Dict[str, Any]]] = None


class ItineraryResponse(BaseModel):
    currency: str = "LKR"  # Allow dynamic currencies
    days: List[DayPlan]
    totals: Optional[Totals] = None
    notes: Optional[List[str]] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "currency": "LKR",
            "days": [
                {
                    "date": "2025-09-10",
                    "summary": {
                        "title": "Day Plan",
                        "est_cost": 85.0,
                        "health_load": "moderate"
                    },
                    "items": [
                        {
                            "start": "09:00",
                            "end": "10:30",
                            "place_id": "gangaramaya_temple",
                            "title": "Gangaramaya Temple",
                            "estimated_cost": 5.0
                        },
                        {
                            "type": "transfer",
                            "from_place_id": "gangaramaya_temple",
                            "to_place_id": "temple_of_tooth",
                            "mode": "DRIVE",
                            "duration_minutes": 15,
                            "distance_km": 3.0,
                            "source": "heuristic"
                        }
                    ]
                }
            ],
            "totals": {
                "trip_cost_est": 85.0,
                "trip_transfer_minutes": 15,
                "daily": [
                    {"date": "2025-09-10", "est_cost": 85.0}
                ]
            }
        }
    })


# Feedback Models
class FeedbackAction(BaseModel):
    type: Literal["rate_item", "remove_item", "request_alternative", "edit_time", "daily_signal"]
    place_id: Optional[str] = None
    rating: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    near_place_id: Optional[str] = None
    max_transfer_minutes: Optional[int] = None


class CurrentDayPlan(BaseModel):
    items: List[Union[Activity, Transfer]]


class FeedbackRequest(BaseModel):
    date: str
    base_place_id: str
    day_template: DayTemplate
    modes: List[str]
    preferences: Optional[Preferences] = None
    constraints: Optional[Constraints] = None
    locks: List[Lock] = []
    current_day_plan: CurrentDayPlan
    actions: List[FeedbackAction]
    audit_log: Optional[AuditLog] = None


class FeedbackResponse(BaseModel):
    date: date
    summary: Summary
    items: List[Union[Activity, Transfer]]
    notes: List[str] = []


# NLP Planner models
class NLPPlanRequest(BaseModel):
    prompt: str


class NLPPlanResponse(BaseModel):
    trip_context: TripContext
    preferences: Preferences
    constraints: Constraints
    locks: List[Lock] = []


# Share token models
class ShareRequest(BaseModel):
    request: dict
    response: dict


class ShareResponse(BaseModel):
    token: str


class ShareGetResponse(BaseModel):
    request: dict
    response: dict


# Admin POI models
class POICreateRequest(BaseModel):
    poi_id: str
    place_id: str
    name: str
    coords: Coords
    tags: List[str] = []
    themes: List[str] = []
    duration_minutes: int = 60
    opening_hours: List[dict] = []
    price_band: Optional[str] = None
    estimated_cost: Optional[float] = None
    safety_flags: List[str] = []
    region: Optional[str] = None


class POIUpdateRequest(BaseModel):
    name: Optional[str] = None
    coords: Optional[Coords] = None
    tags: Optional[List[str]] = None
    themes: Optional[List[str]] = None
    duration_minutes: Optional[int] = None
    opening_hours: Optional[List[dict]] = None
    price_band: Optional[str] = None
    estimated_cost: Optional[float] = None
    safety_flags: Optional[List[str]] = None
    region: Optional[str] = None
