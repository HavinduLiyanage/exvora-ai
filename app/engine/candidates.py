from typing import List, Dict, Any, Tuple
from datetime import datetime
import logging
import math
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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


def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula (km)."""
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def _within_radius(poi: Dict[str, Any], base_place_id: str, pois: List[Dict[str, Any]], pace: str) -> bool:
    """Check if POI is within radius based on pace."""
    # Find base place coordinates
    base_place = next((p for p in pois if p.get("place_id") == base_place_id), None)
    if not base_place or "coords" not in base_place:
        return True  # If no base place or coords, allow all
    
    base_lat, base_lon = base_place["coords"]["lat"], base_place["coords"]["lon"]
    
    if "coords" not in poi:
        return True  # If POI has no coords, allow it
    
    poi_lat, poi_lon = poi["coords"]["lat"], poi["coords"]["lon"]
    distance = _calculate_distance(base_lat, base_lon, poi_lat, poi_lon)
    
    # Get radius based on pace
    if pace == "light":
        max_radius = settings.RADIUS_KM_LIGHT
    elif pace == "moderate":
        max_radius = settings.RADIUS_KM_MODERATE
    elif pace == "intense":
        max_radius = settings.RADIUS_KM_INTENSE
    else:
        max_radius = settings.RADIUS_KM_MODERATE  # Default
    
    return distance <= max_radius


def basic_candidates(pois: List[Dict[str, Any]], prefs: Dict[str, Any], *,
                     date_str: str, day_window: tuple[str,str], base_place_id: str = None, 
                     pace: str = "moderate") -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Filter POIs based on preferences, availability, seasonality, and radius."""
    start_time = datetime.now()
    
    themes = set(map(str.lower, prefs.get("themes", [])))
    avoid = set(map(str.lower, prefs.get("avoid_tags", [])))
    day_start, day_end = day_window
    
    # Track filtering reasons
    filter_reasons = {
        "dropped_avoid": 0,
        "dropped_closed": 0,
        "dropped_radius": 0,
        "dropped_season": 0,
        "dropped_theme": 0
    }

    out = []
    for poi in pois:
        ptags = set(map(str.lower, poi.get("tags", [])))
        pthemes = set(map(str.lower, poi.get("themes", [])))

        # avoid list
        if avoid & ptags:
            filter_reasons["dropped_avoid"] += 1
            continue
            
        # theme overlap (if themes given)
        if themes and themes.isdisjoint(pthemes):
            filter_reasons["dropped_theme"] += 1
            continue
            
        # availability
        if not _in_season(poi, date_str):
            filter_reasons["dropped_season"] += 1
            continue
            
        if not _is_open(poi, date_str, day_start, day_end):
            filter_reasons["dropped_closed"] += 1
            continue
            
        # radius check
        if base_place_id and not _within_radius(poi, base_place_id, pois, pace):
            filter_reasons["dropped_radius"] += 1
            continue

        out.append(poi)
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.debug(f"Candidates filtering completed: {len(out)}/{len(pois)} POIs selected in {duration:.3f}s")
    logger.debug(f"Filter reasons: {filter_reasons}")
    
    return out, filter_reasons
