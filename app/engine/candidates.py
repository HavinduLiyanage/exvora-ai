from typing import List, Dict, Any
from datetime import datetime


def _time_to_min(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h*60 + m


def _is_open(poi: Dict[str,Any], date_str: str, day_start: str, day_end: str) -> bool:
    # expect poi["opening_hours"][dow] = [{"open":"HH:MM","close":"HH:MM"}, ...]
    hours = poi.get("opening_hours") or {}
    d = datetime.fromisoformat(date_str)
    dow = ["mon","tue","wed","thu","fri","sat","sun"][d.weekday()]
    spans = hours.get(dow, [])
    if not spans:
        return False
    ds, de = _time_to_min(day_start), _time_to_min(day_end)
    for span in spans:
        os, oe = _time_to_min(span["open"]), _time_to_min(span["close"])
        if os < de and oe > ds:  # overlap
            return True
    return False


def _in_season(poi: Dict[str,Any], date_str: str) -> bool:
    season = poi.get("seasonality") or ["All"]
    if "All" in season:
        return True
    month = datetime.fromisoformat(date_str).strftime("%b")  # "Jan".."Dec"
    return month in season


def basic_candidates(pois: List[Dict[str, Any]], prefs: Dict[str, Any], *,
                     date_str: str, day_window: tuple[str,str]) -> List[Dict[str, Any]]:
    """Filter POIs based on preferences, availability, and seasonality."""
    themes = set(map(str.lower, prefs.get("themes", [])))
    avoid = set(map(str.lower, prefs.get("avoid_tags", [])))
    day_start, day_end = day_window

    out = []
    for poi in pois:
        ptags = set(map(str.lower, poi.get("tags", [])))
        pthemes = set(map(str.lower, poi.get("themes", [])))

        # avoid list
        if avoid & ptags:
            continue
        # theme overlap (if themes given)
        if themes and themes.isdisjoint(pthemes):
            continue
        # availability
        if not _in_season(poi, date_str):
            continue
        if not _is_open(poi, date_str, day_start, day_end):
            continue

        out.append(poi)
    return out
