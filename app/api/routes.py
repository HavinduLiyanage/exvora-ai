from fastapi import APIRouter, HTTPException
from app.schemas.models import (ItineraryRequest, ItineraryResponse, FeedbackRequest, DayPlan)
from app.dataset.loader import load_pois, pois
from app.engine.candidates import basic_candidates
from app.engine.rules import apply_hard_rules
from app.engine.rank import rank
from app.engine.schedule import schedule_day

router = APIRouter()


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
def build_itinerary(req: ItineraryRequest):
    if len(pois())==0: load_pois()
    if _locks_conflict(req.locks):
        raise HTTPException(status_code=409, detail="Lock time windows overlap")
    date0 = req.trip_context.date_range.start
    day_start = req.trip_context.day_template.start
    day_end = req.trip_context.day_template.end
    prefs = req.preferences.model_dump()
    cands = basic_candidates(
        pois(), prefs, date_str=date0, day_window=(day_start, day_end)
    )
    cands = apply_hard_rules(cands, req.constraints.model_dump() if req.constraints else {}, req.locks)
    ranked = rank(cands, (req.constraints.daily_budget_cap if req.constraints else None))
    plan = schedule_day(
        date0, ranked, (req.constraints.daily_budget_cap if req.constraints else None),
        day_start=day_start, day_end=day_end, locks=req.locks
    )
    resp = {"currency":"LKR","days":[DayPlan(**plan)],"totals":{"trip_cost_est":plan["summary"]["est_cost"],"trip_transfer_minutes":sum(i.get("duration_minutes",0) for i in plan["items"] if i.get("type")=="transfer")}}
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
def feedback_repack(req: FeedbackRequest):
    if len(pois())==0: load_pois()
    if _locks_conflict(req.locks):
        raise HTTPException(status_code=409, detail="Lock time windows overlap")
    remove_ids = {a.place_id for a in req.actions if a.type=="remove_item" and a.place_id}
    prefs = req.preferences.model_dump() if req.preferences else {}
    prefs = _apply_feedback_bias(prefs, req.actions)
    day_start, day_end = req.day_template.start, req.day_template.end
    cands = basic_candidates(pois(), prefs, date_str=req.date, day_window=(day_start, day_end))
    cands = [c for c in cands if c.get("place_id") not in remove_ids]
    ranked = rank(cands, (req.constraints.daily_budget_cap if req.constraints else None))
    plan = schedule_day(req.date, ranked, (req.constraints.daily_budget_cap if req.constraints else None),
                        day_start=day_start, day_end=day_end, locks=req.locks)
    return DayPlan(**plan)
