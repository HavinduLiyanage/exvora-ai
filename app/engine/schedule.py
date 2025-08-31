from typing import List, Dict, Any, Tuple
from app.engine.transfers import verify, verify_sequence, reset_transfer_call_counter
from app.config import get_settings
from datetime import datetime
import logging

settings = get_settings()
logger = logging.getLogger(__name__)


def _min(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h*60 + m


def _fmt(m: int) -> str:
    return f"{m//60:02d}:{m%60:02d}"


def _locks_to_items(locks: List[Any]) -> List[Dict[str,Any]]:
    # turn locks into Activity blocks; if no start/end, treat as 60m placeholder
    items = []
    for lk in locks:
        st = lk.start or "09:00"
        en = lk.end or _fmt(_min(st) + 60)
        items.append({
            "start": st, 
            "end": en, 
            "place_id": lk.place_id, 
            "title": lk.title or "Locked Activity", 
            "estimated_cost": 0
        })
    # sort by start time
    return sorted(items, key=lambda a: _min(a["start"]))


def _build_gaps(day_start: str, day_end: str, lock_items: List[Dict[str,Any]]) -> List[Tuple[int,int]]:
    cur = _min(day_start)
    gaps = []
    for it in lock_items:
        s, e = _min(it["start"]), _min(it["end"])
        if s > cur:
            gaps.append((cur, s))
        cur = max(cur, e)
    if cur < _min(day_end):
        gaps.append((cur, _min(day_end)))
    return gaps


def _fits_budget(cost_sum: float, add: float, cap: float|None) -> bool:
    if cap is None: 
        return True
    return cost_sum + (add or 0) <= cap


def _find_open_window(poi: Dict[str, Any], date_str: str, start_time: int, end_time: int) -> Tuple[int, int]:
    """Find the next feasible open window for a POI within the given time range."""
    hours = poi.get("opening_hours") or {}
    d = datetime.fromisoformat(date_str)
    dow = ["mon","tue","wed","thu","fri","sat","sun"][d.weekday()]
    spans = hours.get(dow, [])
    
    if not spans:
        # If no opening hours specified, use the requested time range
        return start_time, end_time
    
    # Find the first open window that overlaps with our time range
    for span in spans:
        open_min = _min(span["open"])
        close_min = _min(span["close"])
        
        # Check if this window overlaps with our range
        if open_min < end_time and close_min > start_time:
            # Calculate the actual available window
            window_start = max(start_time, open_min)
            window_end = min(end_time, close_min)
            
            if window_end - window_start >= 60:  # At least 1 hour available
                return window_start, window_end
    
    # If no suitable window found, return the requested range
    return start_time, end_time


def _should_insert_break(continuous_minutes: int) -> bool:
    """Determine if a break should be inserted after continuous activity."""
    return continuous_minutes >= settings.BREAK_AFTER_MINUTES


def _insert_break(items: List[Dict[str, Any]], current_time: int) -> int:
    """Insert a break item and return the new current time."""
    break_duration = 30  # 30-minute break
    
    items.append({
        "type": "break",
        "start": _fmt(current_time),
        "end": _fmt(current_time + break_duration),
        "title": "Break",
        "duration_minutes": break_duration
    })
    
    return current_time + break_duration


def schedule_day(date: str, ranked: List[Dict[str, Any]], daily_cap: float | None, *,
                 day_start: str="08:30", day_end: str="20:00", locks: List[Any]=[], pace: str="moderate") -> Dict[str, Any]:
    """Schedule activities for a day with locks-first, opening-hours-aware, and break-inserting approach."""
    start_time = datetime.now()
    
    reset_transfer_call_counter()
    cost_sum = 0.0
    items: List[Dict[str,Any]] = []
    items_added = 0
    max_items = getattr(settings, 'MAX_ITEMS_PER_DAY', 4)
    
    # Track continuous activity time for break insertion
    continuous_minutes = 0
    notes = []

    # 1) place locks first
    lock_items = _locks_to_items(locks)
    items.extend(lock_items)
    
    # Locks count toward the item limit
    items_added = len(lock_items)

    # 2) build time gaps
    gaps = _build_gaps(day_start, day_end, lock_items)

    # 3) fill each gap with top ranked that fit time & budget
    for gstart, gend in gaps:
        if items_added >= max_items:
            break
            
        t = gstart
        last_place_id = None if not items else items[-1].get("place_id")
        
        for poi in list(ranked):  # iterate a snapshot; we'll remove placed ones
            if items_added >= max_items:
                break
                
            dur = int(poi.get("duration_minutes") or 60)
            cost = float(poi.get("estimated_cost") or 0)
            
            # Check if activity fits in gap
            if t + dur > gend:
                continue
                
            if not _fits_budget(cost_sum, cost, daily_cap):
                continue

            # Find feasible open window for this POI within the available gap
            open_start, open_end = _find_open_window(poi, date, t, gend)
            
            # Check if we can fit the activity in the open window
            if open_start + dur > open_end:
                # Activity doesn't fit in open window
                notes.append(f"Could not schedule {poi.get('name', 'POI')} - insufficient open hours")
                continue
            
            # Check if we need to insert a break
            if _should_insert_break(continuous_minutes):
                t = _insert_break(items, t)
                continuous_minutes = 0
            
            # add transfer if previous thing is an activity
            if items and items[-1].get("type") not in ["transfer", "break"] and last_place_id and poi["place_id"] != last_place_id:
                tr = verify(last_place_id, poi["place_id"], "DRIVE", _fmt(t))
                items.append({
                    "type":"transfer",
                    "from_place_id": last_place_id,
                    "to_place_id": poi["place_id"],
                    "mode":"DRIVE", 
                    **tr
                })
                t += tr["duration_minutes"]

            # add activity
            items.append({
                "start": _fmt(open_start), 
                "end": _fmt(open_start + dur), 
                "place_id": poi["place_id"], 
                "title": poi.get("name"), 
                "estimated_cost": cost,
                "duration_minutes": dur
            })
            
            t = open_start + dur
            cost_sum += cost
            last_place_id = poi["place_id"]
            ranked.remove(poi)
            items_added += 1
            
            # Update continuous activity tracking
            continuous_minutes += dur

    # clean dangling transfer
    if items and items[-1].get("type") == "transfer":
        items.pop()

    # 4) Final verification of transfers when Google Routes is enabled
    if settings.USE_GOOGLE_ROUTES:
        try:
            # Extract just the activity items (non-transfer, non-break) for sequence verification
            activity_items = [item for item in items if item.get("type") not in ["transfer", "break"]]
            verified_items = verify_sequence(activity_items, "DRIVE")
            
            # Replace items with verified sequence
            items = verified_items
            
            # Check if any transfers failed verification
            failed_transfers = [item for item in items if item.get("type") == "transfer" and item.get("verify_failed", 0) == 1]
            if failed_transfers and settings.GOOGLE_VERIFY_FAILURE_424:
                notes.append(f"Warning: {len(failed_transfers)} transfers failed Google verification, using heuristic estimates")
                
        except Exception as e:
            logger.warning(f"Google verification failed for day {date}: {e}")
            notes.append("Google verification failed, using heuristic transfer estimates")

    duration = (datetime.now() - start_time).total_seconds()
    logger.debug(f"Day scheduling completed: {len(items)} items scheduled in {duration:.3f}s")

    return {
        "date": date,
        "summary": {"title":"Day Plan","est_cost": cost_sum,"walking_km": 0.0,"health_load": pace},
        "items": items,
        "notes": notes
    }


def schedule_days(dates: List[str], ranked: List[Dict[str, Any]], daily_cap: float | None, *,
                  day_start: str="08:30", day_end: str="20:00", locks: List[Any]=[], pace: str="moderate") -> List[Dict[str, Any]]:
    """Schedule activities for multiple days, building fresh timeline for each day."""
    start_time = datetime.now()
    
    days = []
    
    for date in dates:
        # Create a fresh copy of ranked candidates for each day
        day_candidates = ranked.copy()
        
        # Schedule this day
        day_plan = schedule_day(
            date, day_candidates, daily_cap,
            day_start=day_start, day_end=day_end, locks=locks, pace=pace
        )
        days.append(day_plan)
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.debug(f"Multi-day scheduling completed: {len(days)} days scheduled in {duration:.3f}s")
    
    return days
