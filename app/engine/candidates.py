from typing import List, Dict, Any


def basic_candidates(pois: List[Dict[str, Any]], prefs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter POIs based on preferences."""
    themes = set(map(str.lower, prefs.get("themes", [])))
    avoid = set(map(str.lower, prefs.get("avoid_tags", [])))
    
    out = []
    for poi in pois:
        # Get POI tags and themes in lowercase
        ptags = set(map(str.lower, poi.get("tags", [])))
        pthemes = set(map(str.lower, poi.get("themes", [])))
        
        # Skip if POI has any avoided tags
        if avoid & ptags:
            continue
        
        # If themes are specified, require overlap with POI themes
        if themes and themes.isdisjoint(pthemes):
            continue
            
        out.append(poi)
    
    return out
