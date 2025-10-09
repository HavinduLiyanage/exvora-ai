"""
Transfer verification with Google Routes API and heuristic fallback.
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import os
from math import radians, sin, cos, asin, sqrt


def _env_int(name: str, default: int) -> int:
    """Get environment variable as integer with default."""
    try:
        return int(os.getenv(name, default))
    except:
        return default


MAX_EDGES = _env_int("TRANSFER_VERIFY_MAX_EDGES", 30)


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


def estimate_heuristic(a_lat: float, a_lng: float, b_lat: float, b_lng: float, mode: str) -> Tuple[int, float]:
    """
    Return (duration_minutes, distance_km) using haversine and mode speed:
    DRIVE ~ 40 km/h, WALK ~ 4.5 km/h. Clamp min 3 minutes.
    """
    distance_km = haversine_km((a_lat, a_lng), (b_lat, b_lng))
    
    # Speed estimates (km/h)
    speeds = {
        "DRIVE": 40.0,
        "WALK": 4.5,
        "BIKE": 15.0,
        "TRANSIT": 25.0
    }
    
    speed = speeds.get(mode.upper(), 20.0)  # Default speed
    duration_hours = distance_km / speed
    duration_minutes = max(3, int(duration_hours * 60))  # Minimum 3 minutes
    
    return duration_minutes, distance_km


def _extract_edges(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return list of {'idx': i, 'from_place_id', 'to_place_id', 'mode'} for transfer items in items order."""
    edges = []
    
    for i, item in enumerate(items):
        if item.get("type") == "transfer":
            edge = {
                "idx": i,
                "from_place_id": item.get("from_place_id"),
                "to_place_id": item.get("to_place_id"),
                "mode": item.get("mode", "DRIVE")
            }
            edges.append(edge)
    
    return edges


def _call_google_routes(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Use Google Directions API to get routing information for transfers.
    Return [{'minutes': int, 'km': float, 'polyline': str, 'steps': list}] aligned with edges.
    Raise on HTTP/timeouts so caller can fallback.
    """
    import googlemaps

    api_key = "AIzaSyBguUvWS6pEhSADJjAhOAIFf9m4YcIUWmc"

    client = googlemaps.Client(key=api_key)

    # Map transfer modes to Google Directions API modes
    mode_mapping = {
        "DRIVE": "driving",
        "WALK": "walking",
        "BIKE": "bicycling",
        "TRANSIT": "transit"
    }

    results = []

    try:
        # Process each edge individually with Directions API
        for i, edge in enumerate(edges):
            from_place = edge["from_place_id"]
            to_place = edge["to_place_id"]
            mode = mode_mapping.get(edge.get("mode", "DRIVE").upper(), "driving")

            # Call Directions API
            directions = client.directions(
                origin=f"place_id:{from_place}",
                destination=f"place_id:{to_place}",
                mode=mode,
                units="metric",
                alternatives=False  # Get single best route
            )

            if not directions or len(directions) == 0:
                raise ValueError(f"No directions found for edge {i}")

            # Extract route information
            route = directions[0]
            leg = route["legs"][0]

            duration_seconds = leg["duration"]["value"]
            distance_meters = leg["distance"]["value"]

            duration_minutes = max(3, int(duration_seconds / 60))  # Minimum 3 minutes
            distance_km = distance_meters / 1000.0

            # Extract polyline for route visualization
            polyline = route["overview_polyline"]["points"]

            # Extract steps for detailed instructions (optional)
            steps = []
            for step in leg.get("steps", []):
                steps.append({
                    "instruction": step.get("html_instructions", ""),
                    "distance": step["distance"]["value"],
                    "duration": step["duration"]["value"],
                    "mode": step.get("travel_mode", mode)
                })

            results.append({
                "minutes": duration_minutes,
                "km": distance_km,
                "polyline": polyline,
                "steps": steps
            })

        return results

    except Exception as e:
        # Any error should trigger fallback
        raise RuntimeError(f"Google Directions API error: {str(e)}")


def routes_verify(items: List[Dict[str, Any]], mode: str = "DRIVE") -> List[Dict[str, Any]]:
    """
    Verify at most MAX_EDGES edges. For each edge:
      - Try Google; set source 'google_routes_live' on success
      - On any failure, set heuristic values and source 'heuristic'
    Update items in place; return list of transfer items updated.
    """
    edges = _extract_edges(items)[:MAX_EDGES]
    if not edges:
        return []
    
    try:
        results = _call_google_routes(edges)
        for e, r in zip(edges, results):
            t = items[e["idx"]]
            t["duration_minutes"] = int(r["minutes"])
            t["distance_km"] = float(r["km"])
            t["polyline"] = r.get("polyline", "")
            t["steps"] = r.get("steps", [])
            t["source"] = "google_directions_api"
    except Exception:
        # Fill all target edges heuristically
        for e in edges:
            t = items[e["idx"]]
            # Use safe defaults when coordinates aren't available
            t["duration_minutes"] = 12  # 12 minutes default
            t["distance_km"] = 3.5  # 3.5 km default
            t["source"] = "heuristic"

    return [it for it in items if it.get("type") == "transfer"]