"""
Day scheduler for packing activities with transfer placeholders.
"""

from __future__ import annotations
from typing import List, Dict, Any
from datetime import datetime, timedelta


def pack_day(candidates_for_day: List[Dict[str, Any]], day_template: Dict[str, str], locks: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    """
    Greedy packing:
      - Respect day_template start/end and activity duration_minutes
      - Keep locks at fixed times; fill remaining slots around them
      - Insert transfer placeholders between consecutive activities:
        { "type":"transfer","from_place_id":A,"to_place_id":B,"mode":"DRIVE","duration_minutes":None,"distance_km":None,"source":"heuristic" }
    Return list of items (activity/transfer alternation).
    """
    if locks is None:
        locks = []
    
    items = []
    day_start = day_template.get("start", "08:00")
    day_end = day_template.get("end", "20:00")
    pace = day_template.get("pace", "moderate")
    
    # Convert time strings to minutes since midnight
    def time_to_minutes(time_str: str) -> int:
        try:
            hour, minute = map(int, time_str.split(":"))
            return hour * 60 + minute
        except:
            return 0
    
    def minutes_to_time(minutes: int) -> str:
        hour = minutes // 60
        minute = minutes % 60
        return f"{hour:02d}:{minute:02d}"
    
    day_start_min = time_to_minutes(day_start)
    day_end_min = time_to_minutes(day_end)
    
    # Sort locks by start time
    sorted_locks = sorted(locks, key=lambda x: time_to_minutes(x.get("start", "08:00")))
    
    # Create a list of available time slots
    available_slots = []
    current_time = day_start_min
    
    for lock in sorted_locks:
        lock_start = time_to_minutes(lock.get("start", "08:00"))
        lock_end = time_to_minutes(lock.get("end", "08:00"))
        
        # Add slot before lock if there's time
        if lock_start > current_time:
            available_slots.append((current_time, lock_start))
        
        # Add the locked slot
        available_slots.append((lock_start, lock_end))
        current_time = lock_end
    
    # Add remaining time after last lock
    if current_time < day_end_min:
        available_slots.append((current_time, day_end_min))
    
    # Pack activities into available slots
    current_poi = None
    used_pois = set()
    
    # Pre-mark locked POIs as used
    for lock in locks:
        used_pois.add(lock.get("poi_id"))
    
    for slot_start, slot_end in available_slots:
        slot_duration = slot_end - slot_start
        current_slot_time = slot_start
        
        # Check if this is a locked slot
        is_locked_slot = False
        locked_activity = None
        for lock in locks:
            lock_start = time_to_minutes(lock.get("start", "08:00"))
            if slot_start == lock_start:
                is_locked_slot = True
                # Find the locked activity in candidates
                for candidate in candidates_for_day:
                    if candidate.get("poi_id") == lock.get("poi_id"):
                        locked_activity = candidate
                        break
                # Mark this POI as used so it won't be scheduled again
                if locked_activity:
                    used_pois.add(locked_activity.get("poi_id"))
                break
        
        if is_locked_slot and locked_activity:
            # Add transfer if we're moving to a new POI
            if current_poi and current_poi.get("poi_id") != locked_activity.get("poi_id"):
                transfer = {
                    "type": "transfer",
                    "from_place_id": current_poi.get("place_id"),
                    "to_place_id": locked_activity.get("place_id"),
                    "mode": "DRIVE",
                    "duration_minutes": None,
                    "distance_km": None,
                    "source": "heuristic"
                }
                items.append(transfer)
            
            # Add the locked activity
            activity_start = minutes_to_time(slot_start)
            activity_end = minutes_to_time(slot_end)
            
            activity_item = {
                "type": "activity",
                "poi_id": locked_activity.get("poi_id"),
                "place_id": locked_activity.get("place_id"),
                "title": locked_activity.get("title", locked_activity.get("name", "")),
                "start": activity_start,
                "end": activity_end,
                "duration_minutes": slot_end - slot_start,
                "estimated_cost": locked_activity.get("estimated_cost", 0),
                "tags": locked_activity.get("tags", []),
                "price_band": locked_activity.get("price_band", "low"),
                "opening_hours": locked_activity.get("opening_hours", {}),
                "locked": True
            }
            items.append(activity_item)
            current_poi = locked_activity
            used_pois.add(locked_activity.get("poi_id"))
        else:
            # Pack multiple activities in this slot if they fit
            while current_slot_time < slot_end:
                # Find best activity for remaining time in slot
                best_activity = None
                best_score = -1
                
                for candidate in candidates_for_day:
                    duration = candidate.get("duration_minutes", 60)
                    
                    # Skip if activity doesn't fit in remaining time
                    if duration > (slot_end - current_slot_time):
                        continue
                    
                    # Skip if we've already used this POI
                    if candidate.get("poi_id") in used_pois:
                        continue
                    
                    # Score based on opening alignment and theme overlap
                    score = candidate.get("opening_align", 0.0)
                    if score > best_score:
                        best_score = score
                        best_activity = candidate
                
                if best_activity:
                    # Add transfer if we're moving to a new POI
                    if current_poi and current_poi.get("poi_id") != best_activity.get("poi_id"):
                        transfer = {
                            "type": "transfer",
                            "from_place_id": current_poi.get("place_id"),
                            "to_place_id": best_activity.get("place_id"),
                            "mode": "DRIVE",
                            "duration_minutes": None,
                            "distance_km": None,
                            "source": "heuristic"
                        }
                        items.append(transfer)
                    
                    # Add the activity
                    activity_start = minutes_to_time(current_slot_time)
                    activity_end = minutes_to_time(current_slot_time + best_activity.get("duration_minutes", 60))
                    
                    activity_item = {
                        "type": "activity",
                        "poi_id": best_activity.get("poi_id"),
                        "place_id": best_activity.get("place_id"),
                        "title": best_activity.get("title", best_activity.get("name", "")),
                        "start": activity_start,
                        "end": activity_end,
                        "duration_minutes": best_activity.get("duration_minutes", 60),
                        "estimated_cost": best_activity.get("estimated_cost", 0),
                        "tags": best_activity.get("tags", []),
                        "price_band": best_activity.get("price_band", "low"),
                        "opening_hours": best_activity.get("opening_hours", {}),
                        "locked": False
                    }
                    items.append(activity_item)
                    current_poi = best_activity
                    used_pois.add(best_activity.get("poi_id"))
                    
                    # Move to next time slot
                    current_slot_time += best_activity.get("duration_minutes", 60)
                else:
                    # No more activities fit, break out of slot
                    break
    
    # Add breaks if needed based on pace
    if pace == "slow" and len(items) > 2:
        # Add a break after every 2 activities
        break_items = []
        for i, item in enumerate(items):
            if item.get("type") == "activity" and i > 0 and (i + 1) % 3 == 0:
                # Add break after this activity
                break_start = time_to_minutes(item.get("end", "12:00"))
                break_end = break_start + 30  # 30 minute break
                
                if break_end <= day_end_min:
                    break_item = {
                        "type": "break",
                        "start": minutes_to_time(break_start),
                        "end": minutes_to_time(break_end),
                        "title": "Break",
                        "duration_minutes": 30
                    }
                    break_items.append((i + 1, break_item))
        
        # Insert breaks in reverse order to maintain indices
        for i, break_item in reversed(break_items):
            items.insert(i, break_item)
    
    return items