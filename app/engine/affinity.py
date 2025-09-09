"""
Tag affinity computation based on user feedback.
Converts 1-5 star ratings into per-tag affinities using EMA and decay.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import math

# Configuration constants
AFFINITY_ALPHA = 0.25  # EMA smoothing factor
AFFINITY_DECAY_PER_DAY = 0.02  # Daily decay rate toward 0


def rating_weight(rating: int) -> float:
    """
    Convert 1-5 star rating to weight in [-1, +1] range.
    3 stars = 0 (neutral), 1-2 stars = negative, 4-5 stars = positive.
    """
    if rating < 1 or rating > 5:
        raise ValueError(f"Rating must be between 1 and 5, got {rating}")
    
    # Linear mapping: 1->-1, 2->-0.5, 3->0, 4->0.5, 5->1
    return (rating - 3) / 2.0


def compute_affinity_by_tag(feedback_events: List[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, float]:
    """
    Compute tag affinities from feedback events using EMA and decay.
    
    Args:
        feedback_events: List of feedback events with 'rating', 'tags', 'ts' fields
        now: Current time for decay calculation (defaults to now)
    
    Returns:
        Dictionary mapping tag names to affinity scores
    """
    if now is None:
        now = datetime.now()
    
    # Sort events by timestamp
    sorted_events = sorted(feedback_events, key=lambda e: e.get('ts', now))
    
    # Initialize affinity tracking
    affinities = {}
    last_update_time = None
    
    for event in sorted_events:
        rating = event.get('rating', 3)
        tags = event.get('tags', [])
        event_time = event.get('ts', now)
        
        # Convert timestamp string to datetime if needed
        if isinstance(event_time, str):
            try:
                event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                # Make timezone-naive for comparison
                if event_time.tzinfo is not None:
                    event_time = event_time.replace(tzinfo=None)
            except ValueError:
                event_time = now
        
        # Apply decay to all existing affinities
        if last_update_time is not None:
            time_diff = (event_time - last_update_time).total_seconds() / 86400  # Convert to days
            decay_factor = math.exp(-AFFINITY_DECAY_PER_DAY * time_diff)
            
            for tag in affinities:
                affinities[tag] *= decay_factor
        
        # Update affinities for this event's tags
        weight = rating_weight(rating)
        
        for tag in tags:
            if tag not in affinities:
                affinities[tag] = 0.0
            
            # EMA update: new_value = alpha * weight + (1 - alpha) * old_value
            affinities[tag] = AFFINITY_ALPHA * weight + (1 - AFFINITY_ALPHA) * affinities[tag]
        
        last_update_time = event_time
    
    # Apply final decay from last event to now
    if last_update_time is not None:
        time_diff = (now - last_update_time).total_seconds() / 86400
        decay_factor = math.exp(-AFFINITY_DECAY_PER_DAY * time_diff)
        
        for tag in affinities:
            affinities[tag] *= decay_factor
    
    return affinities


def get_strongest_affinity_tag(affinities: Dict[str, float], threshold: float = 0.30) -> Optional[tuple]:
    """
    Get the tag with the strongest absolute affinity above threshold.
    
    Args:
        affinities: Dictionary of tag affinities
        threshold: Minimum absolute affinity to consider
    
    Returns:
        Tuple of (tag, affinity) or None if no tag meets threshold
    """
    if not affinities:
        return None
    
    # Find tag with strongest absolute affinity
    strongest_tag = max(affinities.items(), key=lambda x: abs(x[1]))
    
    if abs(strongest_tag[1]) >= threshold:
        return strongest_tag
    
    return None


def format_affinity_reason(tag: str, affinity: float) -> str:
    """
    Format affinity reason string for display.
    
    Args:
        tag: Tag name
        affinity: Affinity value
    
    Returns:
        Formatted reason string
    """
    if affinity > 0:
        return f"Boosted by {affinity:.1f}★ {tag} affinity"
    else:
        return f"Penalized by {abs(affinity):.1f}★ {tag} rating"


def test_affinity_computation():
    """Test function for affinity computation logic."""
    # Test data
    feedback_events = [
        {
            "poi_id": "hiking_trail",
            "rating": 5,
            "tags": ["hiking", "nature", "quiet"],
            "ts": "2025-08-25T08:30:00Z"
        },
        {
            "poi_id": "nightclub",
            "rating": 1,
            "tags": ["nightlife", "crowded"],
            "ts": "2025-08-24T19:10:00Z"
        }
    ]
    
    affinities = compute_affinity_by_tag(feedback_events)
    
    # Should have positive affinity for hiking/nature/quiet
    assert affinities.get("hiking", 0) > 0
    assert affinities.get("nature", 0) > 0
    assert affinities.get("quiet", 0) > 0
    
    # Should have negative affinity for nightlife/crowded
    assert affinities.get("nightlife", 0) < 0
    assert affinities.get("crowded", 0) < 0
    
    print("Affinity computation test passed!")
    print(f"Affinities: {affinities}")


if __name__ == "__main__":
    test_affinity_computation()
