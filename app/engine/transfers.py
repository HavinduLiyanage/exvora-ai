def verify(from_place_id: str, to_place_id: str, mode: str, depart_time: str):
    """Generate heuristic transfer data between two places."""
    # For now, return constant heuristic values
    # Later this can be replaced with Google Routes API
    return {
        "duration_minutes": 15,
        "distance_km": 3.0,
        "source": "heuristic"
    }
