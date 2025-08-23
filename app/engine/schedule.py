from typing import List, Dict, Any
from datetime import datetime, time
from app.engine.transfers import verify


def schedule_day(date: str, ranked: List[Dict[str, Any]], daily_cap: float | None, locks: List[Any] = None) -> Dict[str, Any]:
    """Schedule activities for a day based on ranked POIs."""
    if locks is None:
        locks = []
    
    items = []
    cost_sum = 0.0
    
    # Start at 9:00 AM (540 minutes from midnight)
    current_time_minutes = 9 * 60
    
    def format_time(minutes: int) -> str:
        """Convert minutes from midnight to HH:MM format."""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"
    
    # TODO: Insert locks first in future iteration
    # For MVP, just place top N ranked POIs under budget
    
    for poi in ranked[:4]:  # Limit to top 4 activities
        cost = float(poi.get("estimated_cost") or 0)
        duration = int(poi.get("duration_minutes") or 60)
        
        # Check budget constraint
        if daily_cap and cost_sum + cost > daily_cap:
            continue
        
        # Add transfer from previous location if needed
        if items:
            last_item = items[-1]
            # Only add transfer if last item was an activity, not a transfer
            if last_item.get("type") != "transfer":
                transfer_info = verify(
                    last_item["place_id"], 
                    poi["place_id"], 
                    "DRIVE", 
                    format_time(current_time_minutes)
                )
                
                transfer = {
                    "type": "transfer",
                    "from_place_id": last_item["place_id"],
                    "to_place_id": poi["place_id"],
                    "mode": "DRIVE",
                    **transfer_info
                }
                items.append(transfer)
                current_time_minutes += transfer_info["duration_minutes"]
        
        # Add the activity
        activity = {
            "start": format_time(current_time_minutes),
            "end": format_time(current_time_minutes + duration),
            "place_id": poi["place_id"],
            "title": poi["name"],
            "estimated_cost": cost
        }
        items.append(activity)
        
        current_time_minutes += duration
        cost_sum += cost
    
    # Remove any dangling transfer at the end
    if items and items[-1].get("type") == "transfer":
        items.pop()
    
    # Create summary
    summary = {
        "title": "Day Plan",
        "est_cost": cost_sum,
        "health_load": "moderate"
    }
    
    return {
        "date": date,
        "summary": summary,
        "items": items
    }
