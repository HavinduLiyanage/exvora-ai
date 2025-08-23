from typing import List, Dict, Any


def _score(poi: Dict[str, Any], daily_cap: float | None) -> float:
    """Calculate score for a POI based on budget fit and time fit."""
    cost = float(poi.get("estimated_cost") or 0)
    dur = int(poi.get("duration_minutes") or 60)
    
    # Budget fit: prefer POIs that don't consume too much of daily budget
    if daily_cap is None:
        budget_fit = 1.0
    else:
        # Give bonus to cheaper items, penalty for items over 25% of budget
        budget_fit = max(0.0, 1.0 - max(0, cost - 0.25 * daily_cap) / max(daily_cap, 1))
    
    # Time fit: prefer activities that are 60-150 minutes
    time_fit = 1.0 if 60 <= dur <= 150 else 0.6
    
    # Weighted combination
    return 0.6 * budget_fit + 0.4 * time_fit


def rank(cands: List[Dict[str, Any]], daily_cap: float | None) -> List[Dict[str, Any]]:
    """Rank candidates by score in descending order."""
    return sorted(cands, key=lambda c: _score(c, daily_cap), reverse=True)
