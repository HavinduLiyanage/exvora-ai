"""
Hardened rules layer for candidate filtering with explainable drop reasons.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple, Iterable, Optional
import datetime
from math import radians, sin, cos, asin, sqrt


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Calculate distance between two points using Haversine formula."""
    lat1, lng1 = a
    lat2, lng2 = b
    
    # Convert to radians
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * asin(sqrt(a))
    
    # Earth radius in kilometers
    r = 6371
    return c * r


def theme_overlap(poi: Dict[str, Any], prefs: Dict[str, Any]) -> int:
    """Count overlap between poi.tags/themes and preferences.themes/activity_tags."""
    themes = set(prefs.get("themes", []))
    activity_tags = set(prefs.get("activity_tags", []))
    
    poi_themes = set(poi.get("themes", []))
    poi_tags = set(poi.get("tags", []))
    
    theme_matches = len(themes & poi_themes)
    tag_matches = len(activity_tags & poi_tags)
    
    return theme_matches + tag_matches


def violates_avoid_tags(poi: Dict[str, Any], avoid: Iterable[str]) -> str | None:
    """Return offending tag or None."""
    avoid_set = set(avoid)
    poi_tags = set(poi.get("tags", []))
    
    # Check for exact matches
    for tag in avoid_set:
        if tag in poi_tags:
            return tag
    
    # Check for partial matches (case-insensitive)
    for avoid_tag in avoid_set:
        for poi_tag in poi_tags:
            if avoid_tag.lower() in poi_tag.lower() or poi_tag.lower() in avoid_tag.lower():
                return avoid_tag
    
    return None


def in_season(poi: Dict[str, Any], date_range: Dict[str, str]) -> bool:
    """Month-based seasonality check; true if any month in range is in poi.seasonality (or no seasonality)."""
    seasonality = poi.get("seasonality", [])
    if not seasonality:
        return True  # No seasonality restrictions

    # Special case: "All" means available year-round
    if "All" in seasonality or "all" in seasonality:
        return True

    # Extract months from date range
    start_date = date_range.get("start", "")
    end_date = date_range.get("end", "")

    try:
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")

        # Check if any month in the range is in seasonality
        current = start_dt
        while current <= end_dt:
            month_name = current.strftime("%b")
            if month_name in seasonality:
                return True
            current = current.replace(day=1) + datetime.timedelta(days=32)
            current = current.replace(day=1)

        return False
    except ValueError:
        return True  # Invalid date format, be lenient


def is_open_for_day(poi: Dict[str, Any], day_slot: Dict[str, str]) -> bool:
    """True if any period overlaps day window; if opening_hours missing → be lenient (True)."""
    opening_hours = poi.get("opening_hours", {})
    if not opening_hours:
        return True  # No opening hours data, be lenient
    
    day_start = day_slot.get("start", "08:00")
    day_end = day_slot.get("end", "20:00")
    
    # Convert time strings to minutes since midnight
    def time_to_minutes(time_str: str) -> int:
        try:
            hour, minute = map(int, time_str.split(":"))
            return hour * 60 + minute
        except:
            return 0
    
    day_start_min = time_to_minutes(day_start)
    day_end_min = time_to_minutes(day_end)
    
    # Check each day of the week for overlap
    for day_name in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
        day_hours = opening_hours.get(day_name, [])
        if not day_hours:
            continue
        
        for period in day_hours:
            open_time = period.get("open", "00:00")
            close_time = period.get("close", "23:59")
            
            open_min = time_to_minutes(open_time)
            close_min = time_to_minutes(close_time)
            
            # Check for overlap
            if open_min < day_end_min and close_min > day_start_min:
                return True
    
    return False


def precheck_transfer_exceeds(
    poi: Dict[str, Any],
    base_km: float,
    max_transfer_minutes: Optional[int],
    modes: List[str]
) -> bool:
    """
    Heuristic ETA: DRIVE ~ 35-45km/h, WALK ~ 4-5km/h.
    If the minimum duration across modes exceeds max_transfer_minutes → True.
    If max_transfer_minutes is None → treat as 'no constraint' → False.
    """
    if not modes:
        return False

    # Speed estimates (km/h)
    speeds = {
        "DRIVE": 40.0,
        "WALK": 4.5,
        "BIKE": 15.0,
        "TRANSIT": 25.0,
    }

    min_duration_minutes = float("inf")

    for mode in modes:
        speed = speeds.get(mode.upper(), 20.0)  # default speed
        duration_hours = base_km / speed if speed > 0 else float("inf")
        duration_minutes = duration_hours * 60
        min_duration_minutes = min(min_duration_minutes, duration_minutes)

    if max_transfer_minutes is None:
        # No constraint → cannot exceed
        return False

    return min_duration_minutes > float(max_transfer_minutes)



def safety_gate(poi: Dict[str, Any], health: Dict[str, Any]) -> bool:
    """Gate on 'low' energy vs long hikes or scary safety_flags; return True to drop when inappropriate."""
    safety_flags = poi.get("safety_flags", [])
    duration_minutes = poi.get("duration_minutes", 60)
    health_load = health.get("health_load", "moderate")
    
    # Check for dangerous safety flags
    dangerous_flags = {"wild_animals", "steep_climb", "sea_sickness", "late_night", "pickpockets"}
    if any(flag in safety_flags for flag in dangerous_flags):
        if health_load == "low":
            return True  # Drop dangerous activities for low energy users
    
    # Check for long activities with low energy
    if health_load == "low" and duration_minutes > 180:  # 3+ hours
        return True  # Drop long activities for low energy users
    
    return False


def filter_candidates(pois: List[Dict[str, Any]], trip_context: Dict[str, Any], preferences: Dict[str, Any], constraints: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Apply hard filters; never drop locked items.
    Produce drop_log: [{poi_id, reason}].
    Reasons:
      - avoid_tag:<tag>
      - bad_season
      - closed
      - precheck_transfer_exceeds
      - safety_gate
    """
    kept = []
    drop_log = []
    
    # Get locked POI IDs (if any)
    locks = trip_context.get("locks", [])
    locked_poi_ids = {lock.get("poi_id") for lock in locks if lock.get("poi_id")}
    
    # Get constraints
    avoid_tags = preferences.get("avoid_tags", [])
    date_range = trip_context.get("date_range", {})
    day_template = trip_context.get("day_template", {})
    modes = trip_context.get("modes", ["DRIVE"])
    max_transfer_minutes = constraints.get("max_transfer_minutes", 120)
    health = preferences.get("health", {"health_load": "moderate"})
    
    # Get base coordinates for distance calculations
    base_place_id = trip_context.get("base_place_id")
    if base_place_id:
        from .candidates import resolve_base_coords
        base_coords = resolve_base_coords(base_place_id)
    else:
        base_coords = (6.9271, 79.8612)  # Default to Colombo
    
    for poi in pois:
        poi_id = poi.get("poi_id", "")
        
        # Never drop locked items
        if poi_id in locked_poi_ids:
            kept.append(poi)
            continue
        
        # Check avoid tags
        if avoid_tags:
            offending_tag = violates_avoid_tags(poi, avoid_tags)
            if offending_tag:
                drop_log.append({"poi_id": poi_id, "reason": f"avoid_tag:{offending_tag}"})
                continue
        
        # Check seasonality
        if not in_season(poi, date_range):
            drop_log.append({"poi_id": poi_id, "reason": "bad_season"})
            continue
        
        # Check if open for the day
        if not is_open_for_day(poi, day_template):
            drop_log.append({"poi_id": poi_id, "reason": "closed"})
            continue
        
        # Check transfer time limits
        distance_km = poi.get("distance_km", 0.0)
        if precheck_transfer_exceeds(poi, distance_km, max_transfer_minutes, modes):
            drop_log.append({"poi_id": poi_id, "reason": "precheck_transfer_exceeds"})
            continue
        
        # Check safety gate
        if safety_gate(poi, health):
            drop_log.append({"poi_id": poi_id, "reason": "safety_gate"})
            continue
        
        # If we get here, keep the POI
        kept.append(poi)
    
    return kept, drop_log