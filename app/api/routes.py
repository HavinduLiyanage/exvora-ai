from fastapi import APIRouter, HTTPException, Request
from app.schemas.models import (ItineraryRequest, ItineraryResponse, FeedbackRequest, DayPlan)
from app.dataset.loader import load_pois, pois
from app.engine.candidates import basic_candidates
from app.engine.rules import apply_hard_rules
from app.engine.rank import rank
from app.engine.schedule import schedule_days
from app.config import get_settings
from app.api.errors import raise_http_error
from app.logs import log_json, log_summary
from app.utils.currency import get_currency_from_request, convert_currency
from datetime import datetime, timedelta
import time
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

# Simple in-memory rate limiting
_rate_limit_store = {}  # ip -> [timestamps]

router = APIRouter()


def _check_rate_limit(ip: str) -> bool:
    """Simple rate limiting: max requests per minute per IP"""
    now = time.time()
    minute_ago = now - 60
    
    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []
    
    # Clean old timestamps
    _rate_limit_store[ip] = [ts for ts in _rate_limit_store[ip] if ts > minute_ago]
    
    # Check limit
    max_requests = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 10)
    if len(_rate_limit_store[ip]) >= max_requests:
        return False
    
    # Add current request
    _rate_limit_store[ip].append(now)
    return True


def _overlap(a_start:str,a_end:str,b_start:str,b_end:str)->bool:
    to_m=lambda s:int(s[:2])*60+int(s[3:5])
    return to_m(a_start) < to_m(b_end) and to_m(b_start) < to_m(a_end)


def _locks_conflict(locks):
    spans=[]
    for lk in locks:
        if lk.start and lk.end:
            spans.append((lk.start, lk.end))
    spans.sort(key=lambda x:x[0])
    for i in range(1,len(spans)):
        if _overlap(spans[i-1][0],spans[i-1][1],spans[i][0],spans[i][1]):
            return True
    return False


@router.get("/healthz")
def healthz():
    if len(pois())==0: load_pois()
    return {"status":"ok","pois_loaded":len(pois())}


@router.post("/itinerary", response_model=ItineraryResponse)
def build_itinerary(req: ItineraryRequest, request: Request):
    # Rate limiting
    client_ip = request.client.host
    if not _check_rate_limit(client_ip):
        log_json(getattr(request.state, 'req_id', 'unknown'), "rate_limit", ip=client_ip)
        raise_http_error(429, "rate_limit_exceeded", "Rate limit exceeded", [f"Max {settings.RATE_LIMIT_PER_MINUTE} requests per minute"])
    
    request_id = getattr(request.state, 'req_id', 'unknown')
    overall_start = time.time()
    
    log_json(request_id, "request_start", 
             start_date=req.trip_context.date_range.start, 
             end_date=req.trip_context.date_range.end)
    
    if len(pois())==0: load_pois()
    if _locks_conflict(req.locks):
        raise_http_error(409, "lock_conflict", "Lock time windows overlap", ["Check lock start/end times"])
    
    # Derive list of dates
    start_date = datetime.fromisoformat(req.trip_context.date_range.start)
    end_date = datetime.fromisoformat(req.trip_context.date_range.end)
    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") 
             for i in range((end_date - start_date).days + 1)]
    
    day_start = req.trip_context.day_template.start
    day_end = req.trip_context.day_template.end
    pace = req.trip_context.day_template.pace
    prefs = req.preferences.model_dump()
    
    # Stage 1: Candidates
    start_time = time.time()
    cands, filter_reasons = basic_candidates(
        pois(), prefs, date_str=dates[0], day_window=(day_start, day_end),
        base_place_id=req.trip_context.base_place_id, pace=pace
    )
    candidates_time = time.time() - start_time
    log_json(request_id, "candidates", 
             ms=round(candidates_time * 1000, 1),
             kept_candidates=len(cands),
             dropped_avoid=filter_reasons.get('dropped_avoid', 0),
             dropped_closed=filter_reasons.get('dropped_closed', 0),
             dropped_radius=filter_reasons.get('dropped_radius', 0))
    
    # Stage 2: Rules
    start_time = time.time()
    cands, rules_filter_reasons = apply_hard_rules(cands, req.constraints.model_dump() if req.constraints else {}, req.locks)
    rules_time = time.time() - start_time
    log_json(request_id, "rules", 
             ms=round(rules_time * 1000, 1),
             kept_candidates=len(cands),
             dropped_budget=rules_filter_reasons.get('dropped_budget', 0),
             dropped_transfer=rules_filter_reasons.get('dropped_transfer', 0),
             dropped_locks=rules_filter_reasons.get('dropped_locks', 0))
    
    # Stage 3: Ranking
    start_time = time.time()
    ranked, ranking_metrics = rank(cands, (req.constraints.daily_budget_cap if req.constraints else None), prefs, day_start, day_end, pace)
    rank_time = time.time() - start_time
    log_json(request_id, "rank", 
             ms=round(rank_time * 1000, 1),
             kept_candidates=len(ranked),
             model_version=ranking_metrics.get('model_version', 'unknown'))
    
    # Stage 4: Scheduling
    start_time = time.time()
    try:
        days = schedule_days(
            dates, ranked, (req.constraints.daily_budget_cap if req.constraints else None),
            day_start=day_start, day_end=day_end, locks=req.locks, pace=pace
        )
    except Exception as e:
        # Only escalate as 424 when Google route verification is explicitly enabled
        if settings.USE_GOOGLE_ROUTES:
            raise HTTPException(status_code=424, detail=f"Transfer verification failed: {e}")
        # otherwise, re-raise (or you could fall back to heuristic globally)
        raise
    
    schedule_time = time.time() - start_time
    total_items = sum(len([item for item in day["items"] if item.get("type") != "transfer"]) for day in days)
    total_transfers = sum(len([item for item in day["items"] if item.get("type") == "transfer"]) for day in days)
    
    # Count verified vs heuristic transfers
    verified_transfers = sum(1 for day in days for item in day["items"] if item.get("type") == "transfer" and item.get("source") == "google_routes_live")
    heuristic_transfers = sum(1 for day in days for item in day["items"] if item.get("type") == "transfer" and item.get("source") == "heuristic")
    failed_verifications = sum(1 for day in days for item in day["items"] if item.get("type") == "transfer" and item.get("verify_failed", 0) == 1)
    
    log_json(request_id, "schedule", 
             ms=round(schedule_time * 1000, 1),
             days_scheduled=len(days),
             verified_edges=verified_transfers,
             heuristic_edges=heuristic_transfers,
             failed_edges=failed_verifications)
    
    # Validate that each day has ≤ MAX_ITEMS_PER_DAY non-transfer items
    max_items = getattr(settings, 'MAX_ITEMS_PER_DAY', 4)
    for day in days:
        non_transfer_items = [item for item in day["items"] if item.get("type") not in ["transfer", "break"]]
        if len(non_transfer_items) > max_items:
            raise_http_error(
                400, 
                "items_per_day_exceeded", 
                f"Day {day['date']} has {len(non_transfer_items)} items, exceeding limit of {max_items} items/day",
                [f"Reduce activities or increase MAX_ITEMS_PER_DAY limit"]
            )
    
    # Calculate totals
    trip_cost_est = sum(day["summary"].get("est_cost", 0) for day in days)
    trip_transfer_minutes = sum(
        item.get("duration_minutes", 0) 
        for day in days 
        for item in day["items"] 
        if item.get("type") == "transfer"
    )
    
    # Currency conversion
    request_currency = get_currency_from_request(prefs, req.constraints.model_dump() if req.constraints else None)
    converted_cost = trip_cost_est  # Default to LKR cost
    if request_currency and request_currency != "LKR":
        converted_cost = convert_currency(trip_cost_est, "LKR", request_currency) or trip_cost_est
    
    # Ensure we always have a valid currency string
    final_currency = request_currency or "LKR"
    
    # Collect notes for heuristic fallbacks and dropped items
    notes = []
    if heuristic_transfers > 0:
        notes.append(f"{heuristic_transfers} transfers used heuristic estimates (Google verification unavailable)")
    if failed_verifications > 0:
        notes.append(f"{failed_verifications} transfers failed verification and fell back to heuristic")
    
    resp = {
        "currency": final_currency,
        "days": [DayPlan(**day) for day in days],
        "totals": {
            "total_cost": converted_cost,
            "total_walking_km": 0.0,  # Placeholder for now
            "total_duration_hours": sum(
                item.get("duration_minutes", 0) 
                for day in days 
                for item in day["items"] 
                if item.get("type") not in ["transfer", "break"]
            ) / 60.0  # Convert minutes to hours
        },
        "notes": notes if notes else None
    }
    
    total_time = time.time() - overall_start
    log_summary(request_id, round(total_time * 1000, 1),
                days=len(days), 
                total_cost=converted_cost, 
                currency=request_currency,
                total_transfer_minutes=trip_transfer_minutes)
    
    return resp


def _apply_feedback_bias(prefs: dict, actions):
    # low ratings push tags into avoid for this rebuild
    avoid = set(map(str.lower, prefs.get("avoid_tags", [])))
    for a in actions:
        if a.type=="rate_item" and (a.rating or 0) <= 2:
            for t in (a.tags or []):
                avoid.add(t.lower())
        # request_alternative can bias later (e.g., same region) – simple tag bias for now
        if a.type=="request_alternative" and a.tags:
            # negative bias to tags if provided as "avoid"
            for t in a.tags:
                avoid.add(t.lower())
    return {**prefs, "avoid_tags": list(avoid)}


@router.post("/itinerary/feedback", response_model=DayPlan)
def feedback_repack(req: FeedbackRequest, request: Request):
    # Rate limiting
    client_ip = request.client.host
    if not _check_rate_limit(client_ip):
        log_json(getattr(request.state, 'req_id', 'unknown'), "rate_limit", ip=client_ip)
        raise_http_error(429, "rate_limit_exceeded", "Rate limit exceeded", [f"Max {settings.RATE_LIMIT_PER_MINUTE} requests per minute"])
    
    request_id = getattr(request.state, 'req_id', 'unknown')
    overall_start = time.time()
    
    log_json(request_id, "feedback_start", date=req.date)
    
    if len(pois())==0: load_pois()
    if _locks_conflict(req.locks):
        raise_http_error(409, "lock_conflict", "Lock time windows overlap", ["Check lock start/end times"])
    
    remove_ids = {a.place_id for a in req.actions if a.type=="remove_item" and a.place_id}
    prefs = req.preferences.model_dump() if req.preferences else {}
    prefs = _apply_feedback_bias(prefs, req.actions)
    
    day_start, day_end = req.day_template.start, req.day_template.end
    pace = req.day_template.pace
    
    # Get candidates excluding removed items
    cands, filter_reasons = basic_candidates(pois(), prefs, date_str=req.date, day_window=(day_start, day_end), base_place_id=req.trip_context.base_place_id if hasattr(req, 'trip_context') else None, pace=pace)
    cands = [c for c in cands if c.get("place_id") not in remove_ids]
    
    # Apply constraints
    constraints = req.constraints.model_dump() if req.constraints else {}
    cands, rules_filter_reasons = apply_hard_rules(cands, constraints, req.locks)
    ranked, ranking_metrics = rank(cands, constraints.get("daily_budget_cap"), prefs, day_start, day_end, pace)
    
    try:
        # Schedule only this one day
        day_plans = schedule_days(
            [req.date], ranked, constraints.get("daily_budget_cap"),
            day_start=day_start, day_end=day_end, locks=req.locks, pace=pace
        )
        
        if not day_plans:
            raise_http_error(409, "no_feasible_plan", "No feasible day plan found with given constraints and locks", ["Relax constraints or adjust locks"])
        
        plan = day_plans[0]
        
        # Validate that locks are preserved
        lock_place_ids = {lk.place_id for lk in req.locks}
        scheduled_place_ids = {item.get("place_id") for item in plan["items"] if item.get("place_id")}
        
        # Check that all locks are present in the scheduled plan
        missing_locks = lock_place_ids - scheduled_place_ids
        if missing_locks:
            raise_http_error(
                409, 
                "locks_not_preserved", 
                f"Cannot preserve locks for places: {missing_locks}",
                ["Adjust constraints or remove conflicting locks"]
            )
        
        # Add notes about the repack
        notes = []
        if remove_ids:
            notes.append(f"Removed {len(remove_ids)} items based on feedback")
        if filter_reasons.get('dropped_avoid', 0) > 0:
            notes.append(f"Dropped {filter_reasons['dropped_avoid']} POIs due to avoid tags")
        if filter_reasons.get('dropped_closed', 0) > 0:
            notes.append(f"Dropped {filter_reasons['dropped_closed']} POIs due to opening hours")
        
        # Add notes to the plan
        if notes:
            plan["notes"] = notes
        
        total_time = time.time() - overall_start
        log_summary(request_id, round(total_time * 1000, 1),
                    feedback_date=req.date,
                    actions_applied=len(req.actions),
                    locks_preserved=len(req.locks))
        
        return DayPlan(**plan)
        
    except Exception as e:
        # Only escalate as 424 when Google route verification is explicitly enabled
        if settings.USE_GOOGLE_ROUTES:
            raise_http_error(424, "transfer_verification_failed", f"Transfer verification failed: {e}", ["Check Google Maps API configuration"])
        # otherwise, re-raise (or you could fall back to heuristic globally)
        raise
