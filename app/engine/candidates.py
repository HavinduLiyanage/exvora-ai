"""
Deterministic candidate generator with explainable drop reasons.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from math import radians, sin, cos, asin, sqrt
from app.dataset.fixtures import load_fixture_pois

PRICE_ORDER = {"free": 0, "low": 1, "medium": 2, "high": 3}

# Default radius for region windowing (km)
DEFAULT_RADIUS_KM = 50

# Cache for POIs to avoid repeated loading
_POI_CACHE: List[Dict[str, Any]] | None = None


def load_all_pois() -> List[Dict[str, Any]]:
    """
    Return POIs as list[dict] with fields:
    poi_id, place_id, name/title, tags, themes, price_band, estimated_cost,
    opening_hours, seasonality, duration_minutes, safety_flags, coords {lat,lng}, region, last_verified
    Load from fixture dataset with caching.
    """
    global _POI_CACHE

    # Return cached POIs if available
    if _POI_CACHE is not None:
        return _POI_CACHE

    pois = load_fixture_pois()

    # Normalize field names to match expected schema
    normalized_pois = []
    for poi in pois:
        normalized = {
            "poi_id": poi["poi_id"],
            "place_id": poi["place_id"],
            "name": poi.get("name", poi.get("title", "")),
            "title": poi.get("name", poi.get("title", "")),
            "tags": poi.get("tags", []),
            "themes": poi.get("themes", []),
            "price_band": poi.get("price_band", "low"),
            "estimated_cost": poi.get("estimated_cost", 0),
            "opening_hours": poi.get("opening_hours", {}),
            "seasonality": poi.get("seasonality", []),
            "duration_minutes": poi.get("duration_minutes", 60),
            "safety_flags": poi.get("safety_flags", []),
            "coords": poi.get("coords", {"lat": 0.0, "lng": 0.0}),
            "region": poi.get("region", "Unknown"),
            "last_verified": poi.get("last_verified", "2025-01-01T00:00:00Z")
        }
        normalized_pois.append(normalized)

    # Cache the normalized POIs
    _POI_CACHE = normalized_pois

    return normalized_pois


def resolve_base_coords(base_place_id: str, pois: List[Dict[str, Any]] | None = None) -> Tuple[float, float]:
    """Return (lat,lng) for base place_id from dataset."""
    if pois is None:
        pois = load_all_pois()

    for poi in pois:
        if poi["place_id"] == base_place_id:
            coords = poi["coords"]
            return coords["lat"], coords["lng"]

    # Fallback to Colombo coordinates if not found
    return 6.9271, 79.8612


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


def window_by_region(pois: List[Dict[str, Any]], base: Tuple[float, float], radius_km: float) -> List[Dict[str, Any]]:
    """Return POIs within radius_km of base."""
    base_lat, base_lng = base
    filtered = []
    
    for poi in pois:
        coords = poi.get("coords", {})
        poi_lat = coords.get("lat", 0.0)
        poi_lng = coords.get("lng", 0.0)
        
        distance = haversine_km((base_lat, base_lng), (poi_lat, poi_lng))
        if distance <= radius_km:
            filtered.append(poi)
    
    return filtered


def opening_alignment(poi: Dict[str, Any], day_slot: Dict[str, str]) -> float:
    """
    Return alignment score [0..1] of POI opening hours vs day window {start,end} (HH:MM).
    Simple overlap ratio across the day window; 0 if no overlap.
    """
    opening_hours = poi.get("opening_hours", {})
    if not opening_hours:
        return 0.5  # Neutral score if no opening hours data
    
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
    max_overlap = 0.0
    for day_name in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
        day_hours = opening_hours.get(day_name, [])
        if not day_hours:
            continue
        
        for period in day_hours:
            open_time = period.get("open", "00:00")
            close_time = period.get("close", "23:59")
            
            open_min = time_to_minutes(open_time)
            close_min = time_to_minutes(close_time)
            
            # Calculate overlap
            overlap_start = max(day_start_min, open_min)
            overlap_end = min(day_end_min, close_min)
            
            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                day_duration = day_end_min - day_start_min
                overlap_ratio = overlap_duration / day_duration if day_duration > 0 else 0
                max_overlap = max(max_overlap, overlap_ratio)
    
    return max_overlap


def annotate_runtime_fields(pois: List[Dict[str, Any]], base: Tuple[float, float], day_slot: Dict[str, str]) -> None:
    """Annotate each candidate with 'opening_align' (float) and 'distance_km' (float)."""
    base_lat, base_lng = base
    
    for poi in pois:
        # Calculate distance
        coords = poi.get("coords", {})
        poi_lat = coords.get("lat", 0.0)
        poi_lng = coords.get("lng", 0.0)
        distance = haversine_km((base_lat, base_lng), (poi_lat, poi_lng))
        poi["distance_km"] = distance
        
        # Calculate opening alignment
        alignment = opening_alignment(poi, day_slot)
        poi["opening_align"] = alignment


def prefilter_by_themes_tags(pois: List[Dict[str, Any]], preferences: Dict[str, Any], min_required: int = 50) -> List[Dict[str, Any]]:
    """
    Quick keep if overlap with preferences.themes/activity_tags.
    If too few matches (< min_required), return all POIs to ensure variety.
    This prevents overly restrictive filtering for multi-day trips.
    """
    themes = set(preferences.get("themes", []))
    activity_tags = set(preferences.get("activity_tags", []))

    if not themes and not activity_tags:
        return pois  # No preferences, keep all

    filtered = []
    for poi in pois:
        poi_themes = set(poi.get("themes", []))
        poi_tags = set(poi.get("tags", []))

        # Check for exact overlap
        theme_overlap = bool(themes & poi_themes)
        tag_overlap = bool(activity_tags & poi_tags)

        # Also check for partial/fuzzy matches (case-insensitive substring)
        fuzzy_theme_match = False
        fuzzy_tag_match = False

        if themes and not theme_overlap:
            for requested_theme in themes:
                for poi_theme in poi_themes:
                    if requested_theme.lower() in poi_theme.lower() or poi_theme.lower() in requested_theme.lower():
                        fuzzy_theme_match = True
                        break
                if fuzzy_theme_match:
                    break

        if activity_tags and not tag_overlap:
            for requested_tag in activity_tags:
                for poi_tag in poi_tags:
                    if requested_tag.lower() in poi_tag.lower() or poi_tag.lower() in requested_tag.lower():
                        fuzzy_tag_match = True
                        break
                if fuzzy_tag_match:
                    break

        if theme_overlap or tag_overlap or fuzzy_theme_match or fuzzy_tag_match:
            filtered.append(poi)

    # Fallback: if too few matches, return all POIs (let ranking handle preference weighting)
    # This ensures multi-day trips have enough variety
    if len(filtered) < min_required:
        return pois

    return filtered


def generate_candidates(trip_context: Dict[str, Any], preferences: Dict[str, Any], constraints: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Steps:
      1) Load POIs
      2) Region window around base_place_id (default radius 30–60 km; env or constant)
      3) Prefilter by theme/tag overlap
      4) Annotate opening_align + distance_km
      5) Apply rules.filter_candidates(...) (returns kept, drop_log)
      6) Deterministic sort keepers by:
         (PRICE_ORDER[price_band], -opening_align, -theme_overlap, name/title, poi_id)
    """
    from .rules import filter_candidates
    
    # Step 1: Load POIs (once!)
    all_pois = load_all_pois()

    # Step 2: Region window
    base_place_id = trip_context.get("base_place_id")
    base_coords = resolve_base_coords(base_place_id, pois=all_pois)
    radius_km = constraints.get("radius_km", DEFAULT_RADIUS_KM)
    regional_pois = window_by_region(all_pois, base_coords, radius_km)
    
    # Step 3: Prefilter by themes/tags
    day_template = trip_context.get("day_template", {})

    # Calculate minimum POIs needed based on trip duration
    date_range = trip_context.get("date_range", {})
    if date_range.get("start") and date_range.get("end"):
        from datetime import datetime
        start = datetime.fromisoformat(date_range["start"])
        end = datetime.fromisoformat(date_range["end"])
        num_days = (end - start).days + 1
        # Need at least 4 activities per day, so require 4 * num_days POIs minimum
        min_required = num_days * 4
    else:
        min_required = 50  # Default fallback

    themed_pois = prefilter_by_themes_tags(regional_pois, preferences, min_required=min_required)
    
    # Step 4: Annotate runtime fields
    annotate_runtime_fields(themed_pois, base_coords, day_template)
    
    # Step 5: Apply hard filters
    kept, drop_log = filter_candidates(themed_pois, trip_context, preferences, constraints)
    
    # Step 6: Deterministic sort
    def sort_key(poi):
        price_band = poi.get("price_band", "low")
        price_order = PRICE_ORDER.get(price_band, 1)
        opening_align = poi.get("opening_align", 0.0)
        
        # Calculate theme overlap score
        themes = set(preferences.get("themes", []))
        activity_tags = set(preferences.get("activity_tags", []))
        poi_themes = set(poi.get("themes", []))
        poi_tags = set(poi.get("tags", []))
        
        theme_overlap = len(themes & poi_themes) + len(activity_tags & poi_tags)
        
        name = poi.get("name", poi.get("title", ""))
        poi_id = poi.get("poi_id", "")
        
        return (price_order, -opening_align, -theme_overlap, name, poi_id)
    
    kept.sort(key=sort_key)
    
    return kept, drop_log