from __future__ import annotations

from typing import List, Tuple, Dict, Any, Optional
from datetime import time

from app.schemas.models import DayPlan, Activity, Transfer


def optimize_day_budget(
    day_plan: Dict[str, Any], 
    ranked_pool: List[Dict[str, Any]], 
    cap: Optional[float]
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Optimize day budget by swapping expensive activities with cheaper alternatives.
    
    If cap is None or current cost <= cap, return unchanged.
    Otherwise, try to swap the highest-cost scheduled activity with a cheaper candidate.
    At most one swap per day.
    """
    notes = []
    
    if cap is None:
        return day_plan, notes
    
    # Calculate current cost
    current_cost = sum(
        item.get("estimated_cost", 0) or 0
        for item in day_plan["items"] 
        if item.get("type") != "transfer"
    )
    
    if current_cost <= cap:
        return day_plan, notes
    
    # Find the most expensive activity
    activities = [item for item in day_plan["items"] if item.get("type") != "transfer"]
    if not activities:
        return day_plan, notes
    
    most_expensive = max(activities, key=lambda x: x.get("estimated_cost", 0) or 0)
    expensive_cost = most_expensive.get("estimated_cost", 0) or 0
    
    # Find cheaper alternatives from ranked pool
    # Filter by same day availability (opening hours and duration)
    cheaper_alternatives = []
    for poi in ranked_pool:
        poi_cost = poi.get("estimated_cost", 0) or 0
        if (poi_cost < expensive_cost and 
            poi_cost > 0 and
            poi.get("place_id") != most_expensive.get("place_id")):
            # Check if POI fits in the same day (simple duration check)
            poi_duration = poi.get("duration_minutes", 60)
            if poi_duration <= 180:  # Reasonable duration for day planning
                cheaper_alternatives.append(poi)
    
    if not cheaper_alternatives:
        return day_plan, notes
    
    # Sort by cost (cheapest first) and take the best one
    best_alternative = min(cheaper_alternatives, key=lambda x: x.get("estimated_cost", 0))
    
    # Create new activity item
    new_activity = {
        "start": most_expensive.get("start", "09:00"),
        "end": most_expensive.get("end", "10:00"),
        "place_id": best_alternative.get("place_id", ""),
        "title": best_alternative.get("name", "Alternative Activity"),
        "estimated_cost": best_alternative.get("estimated_cost", 0)
    }
    
    # Replace in day plan
    new_items = []
    for item in day_plan["items"]:
        if item.get("place_id") == most_expensive.get("place_id"):
            new_items.append(new_activity)
        else:
            new_items.append(item)
    
    # Update day plan
    updated_plan = {
        "date": day_plan["date"],
        "summary": day_plan["summary"],
        "items": new_items,
        "notes": day_plan.get("notes", [])
    }
    
    # Add note about the swap
    notes.append(
        f"Swapped {most_expensive.get('title', 'expensive activity')} → "
        f"{best_alternative.get('name', 'alternative')} to meet budget cap"
    )
    
    return updated_plan, notes
