import json
import pathlib
from typing import List, Dict, Any

_DATA: List[Dict[str, Any]] = []


def load_pois(path: str | None = None) -> int:
    """Load POIs from JSON file and validate them."""
    global _DATA
    
    if path is None:
        path = str(pathlib.Path(__file__).with_name("pois.sample.json"))
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Validate data
    ids = set()
    for poi in data:
        # Check for unique poi_id
        if poi["poi_id"] in ids:
            raise ValueError(f"Duplicate poi_id: {poi['poi_id']}")
        ids.add(poi["poi_id"])
        
        # Validate duration_minutes is numeric
        if not isinstance(poi.get("duration_minutes"), (int, float)):
            raise ValueError(f"duration_minutes must be numeric for poi_id: {poi['poi_id']}")
        
        # Check presence of opening_hours when duration > 0
        if poi.get("duration_minutes", 0) > 0 and not poi.get("opening_hours"):
            raise ValueError(f"opening_hours required when duration > 0 for poi_id: {poi['poi_id']}")
    
    _DATA = data
    return len(_DATA)


def pois() -> List[Dict[str, Any]]:
    """Return the in-memory list of POIs."""
    return _DATA
