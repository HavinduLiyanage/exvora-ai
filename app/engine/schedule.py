from typing import List, Dict, Any, Tuple
from app.engine.transfers import verify, reset_transfer_call_counter


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


def schedule_day(date: str, ranked: List[Dict[str, Any]], daily_cap: float | None, *,
                 day_start: str="08:30", day_end: str="20:00", locks: List[Any]=[]):
    """Schedule activities for a day with locks-first and gap-filling approach."""
    reset_transfer_call_counter()
    cost_sum = 0.0
    items: List[Dict[str,Any]] = []

    # 1) place locks first
    lock_items = _locks_to_items(locks)
    items.extend(lock_items)

    # 2) build time gaps
    gaps = _build_gaps(day_start, day_end, lock_items)

    # 3) fill each gap with top ranked that fit time & budget
    for gstart, gend in gaps:
        t = gstart
        last_place_id = None if not items else items[-1].get("place_id")
        for poi in list(ranked):  # iterate a snapshot; we'll remove placed ones
            dur = int(poi.get("duration_minutes") or 60)
            cost = float(poi.get("estimated_cost") or 0)
            if t + dur > gend:
                continue
            if not _fits_budget(cost_sum, cost, daily_cap):
                continue

            # add transfer if previous thing is an activity
            if items and items[-1].get("type") != "transfer" and last_place_id and poi["place_id"] != last_place_id:
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
                "start": _fmt(t), 
                "end": _fmt(t+dur), 
                "place_id": poi["place_id"], 
                "title": poi.get("name"), 
                "estimated_cost": cost
            })
            t += dur
            cost_sum += cost
            last_place_id = poi["place_id"]
            ranked.remove(poi)

    # clean dangling transfer
    if items and items[-1].get("type") == "transfer":
        items.pop()

    return {
        "date": date,
        "summary": {"title":"Day Plan","est_cost": cost_sum,"health_load":"moderate"},
        "items": items
    }
