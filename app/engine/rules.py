from typing import List, Dict, Any, Tuple
from app.schemas.models import Lock
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def apply_hard_rules(cands: List[Dict[str, Any]], constraints: Dict[str, Any], locks: List[Lock]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Apply hard constraints to filter candidates."""
    start_time = datetime.now()
    
    daily_cap = constraints.get("daily_budget_cap")
    max_transfer_minutes = constraints.get("max_transfer_minutes")
    
    # Track filtering reasons
    filter_reasons = {
        "dropped_budget": 0,
        "dropped_transfer": 0,
        "dropped_locks": 0
    }
    
    out = []
    for candidate in cands:
        # Filter out POIs that would exceed daily budget on their own
        if daily_cap is not None and (candidate.get("estimated_cost") or 0) > daily_cap:
            filter_reasons["dropped_budget"] += 1
            continue
            
        # Filter out POIs that would exceed max transfer time
        if max_transfer_minutes is not None and (candidate.get("duration_minutes") or 60) > max_transfer_minutes:
            filter_reasons["dropped_transfer"] += 1
            continue
            
        # Filter out POIs that conflict with locks
        if locks:
            candidate_duration = candidate.get("duration_minutes", 60)
            # Simple check: if candidate duration > 120 minutes, it might conflict with locks
            # More sophisticated lock conflict checking could be added here
            if candidate_duration > 120:
                filter_reasons["dropped_locks"] += 1
                continue
            
        out.append(candidate)
    
    duration = (datetime.now() - start_time).total_seconds()
    logger.debug(f"Rules filtering completed: {len(out)}/{len(cands)} candidates passed in {duration:.3f}s")
    logger.debug(f"Filter reasons: {filter_reasons}")
    
    return out, filter_reasons
