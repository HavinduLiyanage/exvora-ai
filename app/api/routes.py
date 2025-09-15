from fastapi import APIRouter, HTTPException, Request, Depends
from app.schemas.models import (
    ItineraryRequest, ItineraryResponse, FeedbackRequest, DayPlan,
    NLPPlanRequest, NLPPlanResponse, ShareRequest, ShareResponse, ShareGetResponse
)
from app.dataset.loader import load_pois, pois
# from app.engine.candidates import basic_candidates  # Replaced with generate_candidates
# from app.engine.rules import apply_hard_rules  # Now integrated in generate_candidates
from app.engine.rank import rank, collect_safety_warnings
# from app.engine.schedule import schedule_days  # Replaced with pack_day + routes_verify
from app.config import get_settings
from app.api.errors import raise_http_error
from app.logs import log_json, log_summary
from app.common.logging import timed
from app.engine.feedback import repack_day_from_actions
from app.engine import BudgetOptimizer
from app.engine.reranker import rerank_candidates_with_metadata
from app.nlp.parse import parse_prompt_to_plan
from app.share.store import create_share_token, get_share_data
from app.utils.currency import get_currency_from_request, convert_currency
from datetime import datetime, timedelta
import time
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

# Simple in-memory rate limiting
_rate_limit_store = {}  # ip -> [timestamps]

router = APIRouter()


def _check_api_key(request: Request) -> None:
    """Optional API key check via x-api-key header."""
    api_key = settings.PUBLIC_API_KEY
    if not api_key:
        return
    provided = request.headers.get("x-api-key")
    if provided != api_key:
        raise_http_error(401, "unauthorized", "Missing or invalid API key", ["Provide x-api-key header"]) 


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
def build_itinerary(req: ItineraryRequest, request: Request, _: None = Depends(_check_api_key)):
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
    
    # Stage 1: Candidates + Rules (integrated)
    with timed("candidates"):
        from app.engine.candidates import generate_candidates
        cands, drop_log = generate_candidates(
            req.trip_context.model_dump(), 
            prefs, 
            req.constraints.model_dump() if req.constraints else {}
        )
    candidates_time = 0
    # Fallback mechanism: if no candidates, relax filters and retry
    fallback_note = None
    if not cands:
        relaxed_prefs = {**prefs}
        # Drop avoid_tags first to not over-prune
        relaxed_prefs["avoid_tags"] = []
        base_constraints = req.constraints.model_dump() if req.constraints else {}
        relaxed_constraints = {**base_constraints, "max_transfer_minutes": max(180, int(base_constraints.get("max_transfer_minutes" ) or 0)), "radius_km": max(200, int(base_constraints.get("radius_km") or 0))}
        relaxed_context = req.trip_context.model_dump()
        try:
            cands, drop_log = generate_candidates(relaxed_context, relaxed_prefs, relaxed_constraints)
            if cands:
                fallback_note = "Fallback applied: relaxed avoid_tags, widened radius and transfer time to find options."
        except Exception:
            cands = []
        # Last resort: broaden themes too
        if not cands:
            very_relaxed_prefs = {**relaxed_prefs, "themes": []}
            very_relaxed_constraints = {**relaxed_constraints, "radius_km": max(300, int(relaxed_constraints.get("radius_km") or 0)), "max_transfer_minutes": max(300, int(relaxed_constraints.get("max_transfer_minutes") or 0))}
            try:
                cands, drop_log = generate_candidates(relaxed_context, very_relaxed_prefs, very_relaxed_constraints)
                if cands:
                    fallback_note = "Fallback applied: cleared avoid_tags and themes, increased radius and transfer time."
            except Exception:
                cands = []
    
    # Count drop reasons for logging
    drop_reasons = {}
    for drop in drop_log:
        reason = drop["reason"]
        if reason.startswith("avoid_tag:"):
            drop_reasons["dropped_avoid"] = drop_reasons.get("dropped_avoid", 0) + 1
        elif reason == "closed":
            drop_reasons["dropped_closed"] = drop_reasons.get("dropped_closed", 0) + 1
        elif reason == "bad_season":
            drop_reasons["dropped_season"] = drop_reasons.get("dropped_season", 0) + 1
        elif reason == "precheck_transfer_exceeds":
            drop_reasons["dropped_transfer"] = drop_reasons.get("dropped_transfer", 0) + 1
        elif reason == "safety_gate":
            drop_reasons["dropped_safety"] = drop_reasons.get("dropped_safety", 0) + 1
    
    log_json(request_id, "candidates", 
             ms=round(candidates_time * 1000, 1),
             kept_candidates=len(cands),
             dropped_avoid=drop_reasons.get('dropped_avoid', 0),
             dropped_closed=drop_reasons.get('dropped_closed', 0),
             dropped_season=drop_reasons.get('dropped_season', 0),
             dropped_transfer=drop_reasons.get('dropped_transfer', 0),
             dropped_safety=drop_reasons.get('dropped_safety', 0))
    
    # Stage 3: Ranking
    with timed("rank"):
        ranked, ranking_metrics = rank(cands, (req.constraints.daily_budget_cap if req.constraints else None), prefs, day_start, day_end, pace, context=req.trip_context.model_dump())
    rank_time = 0
    log_json(request_id, "rank", 
             ms=round(rank_time * 1000, 1),
             kept_candidates=len(ranked),
             model_version=ranking_metrics.get('model_version', 'unknown'))
    
    # Stage 3.5: Reranking (if audit_log provided)
    if req.audit_log and req.audit_log.feedback_events:
        with timed("rerank"):
            # Add scores to candidates for reranking
            candidates_with_scores = []
            for i, candidate in enumerate(ranked):
                candidate_with_score = dict(candidate)
                candidate_with_score["score"] = 1.0 - (i / max(len(ranked) - 1, 1))  # Simple score based on rank
                candidates_with_scores.append(candidate_with_score)
            
            # Apply reranking
            reranked_candidates, rerank_metadata = rerank_candidates_with_metadata(
                candidates_with_scores, req.audit_log.model_dump()
            )
            
            # Extract reranked candidates (without scores for scheduling)
            ranked = [c for c in reranked_candidates if "score" in c]
            
            log_json(request_id, "rerank",
                     ms=0,  # Placeholder timing
                     rerank_applied=rerank_metadata.get("rerank_applied", False),
                     n_candidates_with_reasons=rerank_metadata.get("n_candidates_with_reasons", 0))
    else:
        rerank_metadata = {"rerank_applied": False}
    
    # Stage 4: Scheduling
    start_time = time.time()
    try:
        with timed("schedule"):
            from app.engine.schedule import pack_day
            from app.engine.transfers import routes_verify
            
            days = []
            for date in dates:
                # Pack the day with activities and transfer placeholders
                day_template = {
                    "start": day_start,
                    "end": day_end,
                    "pace": pace
                }
                items = pack_day(ranked, day_template, locks=req.locks)
                
                # Verify transfer times with Google Routes (or heuristic fallback)
                routes_verify(items, mode="DRIVE")
                
                # Calculate day summary
                total_cost = sum(item.get("estimated_cost", 0) for item in items if item.get("type") == "activity")
                total_walking = sum(item.get("distance_km", 0) or 0 for item in items if item.get("type") == "transfer")
                
                day_plan = {
                    "date": date,
                    "summary": {
                        "title": f"Day {len(days) + 1}",
                        "est_cost": total_cost,
                        "walking_km": total_walking,
                        "health_load": pace
                    },
                    "items": items,
                    "notes": []
                }
                days.append(day_plan)
            
            # Stage 5: Budget optimization
            with timed("budget_optimize"):
                # Create candidates_by_date dict for budget optimizer
                candidates_by_date = {date: ranked for date in dates}
                
                # Apply comprehensive budget optimization
                optimizer = BudgetOptimizer(enable_cross_day_rebalance=False)
                budget_result = optimizer.optimize_trip(
                    days=days,
                    trip_context=req.trip_context.model_dump(),
                    preferences=req.preferences.model_dump(),
                    constraints=req.constraints.model_dump() if req.constraints else {},
                    candidates_by_date=candidates_by_date
                )
                days = budget_result["days"]
                budget_totals = budget_result["totals"]
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
    
    # Calculate totals using budget optimizer results
    if 'budget_totals' in locals():
        trip_cost_est = budget_totals["trip_cost_est"]
        trip_transfer_minutes = budget_totals["trip_transfer_minutes"]
    else:
        # Fallback calculation if budget optimizer wasn't used
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
    
    # Collect notes for heuristic fallbacks, dropped items, and safety warnings
    notes = []
    if heuristic_transfers > 0:
        notes.append(f"{heuristic_transfers} transfers used heuristic estimates (Google verification unavailable)")
    if failed_verifications > 0:
        notes.append(f"{failed_verifications} transfers failed verification and fell back to heuristic")
    
    # Add safety warnings for each day
    for day in days:
        day_warnings = collect_safety_warnings(day["items"])
        if day_warnings:
            if "notes" not in day:
                day["notes"] = []
            day["notes"].extend(day_warnings)
    
    # Prepare totals with budget optimizer format
    if 'budget_totals' in locals():
        totals = {
            "trip_cost_est": converted_cost,
            "trip_transfer_minutes": trip_transfer_minutes,
            "daily": budget_totals["daily"]
        }
    else:
        totals = {
            "trip_cost_est": converted_cost,
            "trip_transfer_minutes": trip_transfer_minutes,
            "daily": [{"date": day["date"], "est_cost": day["summary"].get("est_cost", 0)} for day in days]
        }
    # Attach fallback note if applied
    if fallback_note:
        for day in days:
            if "notes" not in day:
                day["notes"] = []
            if fallback_note not in day["notes"]:
                day["notes"].append(fallback_note)
        if notes is None:
            notes = []
        if fallback_note not in notes:
            notes.append(fallback_note)
    
    resp = {
        "currency": final_currency,
        "days": [DayPlan(**day).model_dump() for day in days],
        "totals": totals,
        "notes": notes if notes else None
    }
    
    total_time = time.time() - overall_start
    log_summary(request_id, round(total_time * 1000, 1),
                days=len(days), 
                total_cost=converted_cost, 
                currency=request_currency,
                total_transfer_minutes=trip_transfer_minutes)
    
    # Rate limit headers
    max_requests = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 10)
    remaining = max(0, max_requests - len(_rate_limit_store.get(client_ip, [])))
    from fastapi.responses import JSONResponse
    response = JSONResponse(content=resp)
    response.headers["X-RateLimit-Limit"] = str(max_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


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
def feedback_repack(req: FeedbackRequest, request: Request, _: None = Depends(_check_api_key)):
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
    
    try:
        with timed("feedback_repack"):
            merged_items, notes = repack_day_from_actions(
                datetime.fromisoformat(req.date).date(),
                req.preferences,  # Pass preferences directly
                req.constraints if req.constraints else None,  # type: ignore
                req.locks,
                req.current_day_plan,
                req.actions,
                pois(),
                req.day_template,  # Pass day template
                req.base_place_id,  # Pass base place ID
            )
        # Build DayPlan response
        plan = {
            "date": req.date,
            "summary": {"title": "Day Plan", "est_cost": sum(i.get("estimated_cost", 0) for i in merged_items if i.get("type") != "transfer"), "walking_km": 0.0, "health_load": pace},
            "items": merged_items,
            "notes": notes,
        }
        total_time = time.time() - overall_start
        log_summary(request_id, round(total_time * 1000, 1), feedback_date=req.date, actions_applied=len(req.actions), locks_preserved=len(req.locks))
        from fastapi.responses import JSONResponse
        response = JSONResponse(content=DayPlan(**plan).model_dump())
        max_requests = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 10)
        remaining = max(0, max_requests - len(_rate_limit_store.get(client_ip, [])))
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
    except Exception as e:
        # Only escalate as 424 when Google route verification is explicitly enabled
        if settings.USE_GOOGLE_ROUTES:
            raise_http_error(424, "transfer_verification_failed", f"Transfer verification failed: {e}", ["Check Google Maps API configuration"])
        # otherwise, re-raise (or you could fall back to heuristic globally)
        raise


@router.post("/nlp/plan", response_model=NLPPlanResponse)
def nlp_plan(req: NLPPlanRequest, request: Request, _: None = Depends(_check_api_key)):
    """Parse natural language prompt into structured plan components."""
    try:
        trip_context, preferences, constraints, locks = parse_prompt_to_plan(req.prompt)
        return NLPPlanResponse(
            trip_context=trip_context,
            preferences=preferences,
            constraints=constraints,
            locks=locks
        )
    except Exception as e:
        raise_http_error(400, "parse_error", f"Failed to parse prompt: {e}", ["Check prompt format"])


@router.post("/share", response_model=ShareResponse)
def create_share(req: ShareRequest, request: Request, _: None = Depends(_check_api_key)):
    """Create a share token for request/response data."""
    try:
        token = create_share_token(req.request, req.response)
        return ShareResponse(token=token)
    except Exception as e:
        raise_http_error(500, "share_error", f"Failed to create share token: {e}", ["Try again later"])


@router.get("/share/{token}", response_model=ShareGetResponse)
def get_share(token: str, request: Request, _: None = Depends(_check_api_key)):
    """Retrieve shared data by token."""
    data = get_share_data(token)
    if not data:
        raise_http_error(404, "share_not_found", "Share token not found or expired", ["Check token or create new share"])
    
    return ShareGetResponse(request=data["request"], response=data["response"])
