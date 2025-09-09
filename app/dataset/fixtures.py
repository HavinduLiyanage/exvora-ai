"""
Fixture dataset loader for development and testing.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any

FIXTURE_PATH = Path("data/fixtures/pois_sl_min.json")

def load_fixture_pois(path: str | None = None) -> List[Dict[str, Any]]:
    """
    Load POI fixture data from JSON file.
    
    Args:
        path: Optional path to fixture file. Defaults to FIXTURE_PATH.
    
    Returns:
        List of POI dictionaries
    """
    p = Path(path) if path else FIXTURE_PATH
    return json.loads(p.read_text(encoding="utf-8"))
