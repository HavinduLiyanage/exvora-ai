from typing import List, Dict, Any
from app.schemas.models import Lock


def apply_hard_rules(cands: List[Dict[str, Any]], constraints: Dict[str, Any], locks: List[Lock]) -> List[Dict[str, Any]]:
    """Apply hard constraints to filter candidates."""
    daily_cap = constraints.get("daily_budget_cap")
    
    out = []
    for candidate in cands:
        # Filter out POIs that would exceed daily budget on their own
        if daily_cap is not None and (candidate.get("estimated_cost") or 0) > daily_cap:
            continue
            
        out.append(candidate)
    
    return out
