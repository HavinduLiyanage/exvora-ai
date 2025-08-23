from fastapi import APIRouter, HTTPException
from app.schemas.models import (
    ItineraryRequest, ItineraryResponse, FeedbackRequest, DayPlan
)
from app.dataset.loader import load_pois, pois
from app.engine.candidates import basic_candidates
from app.engine.rules import apply_hard_rules
from app.engine.rank import rank
from app.engine.schedule import schedule_day

router = APIRouter()


@router.get("/healthz")
def healthz():
    """Health check endpoint."""
    if len(pois()) == 0:
        load_pois()
    return {"status": "ok", "pois_loaded": len(pois())}


@router.post("/itinerary", response_model=ItineraryResponse)
def build_itinerary(req: ItineraryRequest):
    """Build an itinerary for the given trip context and preferences."""
    # Load POIs if not already loaded
    if len(pois()) == 0:
        load_pois()
    
    # Convert preferences to dict for engine functions
    prefs = req.preferences.model_dump() if req.preferences else {}
    constraints = req.constraints.model_dump() if req.constraints else {}
    
    # Run the itinerary generation pipeline
    candidates = basic_candidates(pois(), prefs)
    filtered_candidates = apply_hard_rules(candidates, constraints, req.locks)
    ranked_candidates = rank(filtered_candidates, constraints.get("daily_budget_cap"))
    
    # For MVP, generate plan for the start date only
    start_date = req.trip_context.date_range.start
    day_plan_data = schedule_day(
        str(start_date), 
        ranked_candidates, 
        constraints.get("daily_budget_cap"), 
        locks=req.locks
    )
    
    # Create DayPlan object
    day_plan = DayPlan(**day_plan_data)
    
    return ItineraryResponse(
        currency="LKR",
        days=[day_plan]
    )


@router.post("/itinerary/feedback", response_model=DayPlan)
def feedback_repack(req: FeedbackRequest):
    """Re-pack a day based on user feedback actions."""
    # Load POIs if not already loaded
    if len(pois()) == 0:
        load_pois()
    
    # Extract place_ids to remove from feedback actions
    remove_ids = {
        action.place_id for action in req.actions 
        if action.type == "remove_item" and action.place_id
    }
    
    # Convert preferences to dict for engine functions
    prefs = req.preferences.model_dump() if req.preferences else {}
    constraints = req.constraints.model_dump() if req.constraints else {}
    
    # Run the pipeline excluding removed items
    candidates = basic_candidates(pois(), prefs)
    # Filter out removed items
    candidates = [c for c in candidates if c.get("place_id") not in remove_ids]
    filtered_candidates = apply_hard_rules(candidates, constraints, req.locks)
    ranked_candidates = rank(filtered_candidates, constraints.get("daily_budget_cap"))
    
    # Generate new day plan
    day_plan_data = schedule_day(
        str(req.date), 
        ranked_candidates, 
        constraints.get("daily_budget_cap"), 
        locks=req.locks
    )
    
    return DayPlan(**day_plan_data)
