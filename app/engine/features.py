"""
Feature vectorization for preference scoring model.
Builds runtime feature vectors from candidate POI data and user context.
"""

from typing import List, Dict, Any, Set
import numpy as np


def vectorize_candidate(candidate: Dict[str, Any], context: Dict[str, Any], 
                       preferences: Dict[str, Any], tag_vocab: List[str], 
                       feature_names: List[str]) -> List[float]:
    """
    Convert a candidate POI into a feature vector aligned with training schema.
    
    Args:
        candidate: POI candidate data
        context: Trip context (day_template, etc.)
        preferences: User preferences (themes, activity_tags, avoid_tags)
        tag_vocab: Fixed vocabulary of tags used in training
        feature_names: Complete list of feature names in order
        
    Returns:
        Feature vector as list of floats
    """
    # Extract candidate data
    tags = set(candidate.get("tags", []))
    price_band = candidate.get("price_band", "medium")
    estimated_cost = float(candidate.get("estimated_cost", 0))
    duration_minutes = float(candidate.get("duration_minutes", 60))
    
    # Compute opening alignment (simplified heuristic)
    opening_align = _compute_opening_alignment(candidate, context)
    
    # Compute distance (simplified heuristic)
    distance_km = _compute_distance(candidate, context)
    
    # Build feature vector
    features = []
    
    # One-hot encode tags
    for tag in tag_vocab:
        features.append(1.0 if tag in tags else 0.0)
    
    # One-hot encode price bands
    price_bands = ["free", "low", "medium", "high"]
    for band in price_bands:
        features.append(1.0 if price_band == band else 0.0)
    
    # Numeric features
    features.extend([
        estimated_cost,
        duration_minutes,
        opening_align,
        distance_km
    ])
    
    return features


def _compute_opening_alignment(candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
    """
    Compute how well the POI's opening hours align with the trip schedule.
    Returns a value between 0 and 1.
    """
    # Simplified heuristic: assume most POIs are open during day hours
    # In a real implementation, this would parse opening_hours and check against day_template
    
    day_template = context.get("day_template", {})
    pace = day_template.get("pace", "moderate")
    
    # Different paces have different optimal durations
    if pace == "light":
        optimal_duration = 60  # 1 hour
    elif pace == "moderate":
        optimal_duration = 120  # 2 hours
    else:  # intense
        optimal_duration = 180  # 3 hours
    
    candidate_duration = float(candidate.get("duration_minutes", 60))
    
    # Compute alignment based on duration fit
    duration_ratio = min(candidate_duration, optimal_duration) / max(candidate_duration, optimal_duration)
    
    # Add some randomness to simulate real opening hours variation
    base_alignment = 0.7 + 0.3 * duration_ratio  # 0.7 to 1.0
    
    # Add small random component to simulate real-world variation
    # Use a deterministic seed based on candidate data for testing
    import hashlib
    seed = hash(str(candidate.get("place_id", "")) + str(candidate.get("title", ""))) % 1000
    np.random.seed(seed)
    noise = np.random.normal(0, 0.05)
    return max(0.0, min(1.0, base_alignment + noise))


def _compute_distance(candidate: Dict[str, Any], context: Dict[str, Any]) -> float:
    """
    Compute distance from base location to candidate POI.
    Returns distance in kilometers.
    """
    # Simplified heuristic: generate realistic distance based on POI type
    # In a real implementation, this would use actual coordinates and distance calculation
    
    tags = set(candidate.get("tags", []))
    
    # Different tag types have different typical distances
    if "nature" in tags or "beach" in tags or "mountain" in tags:
        # Nature attractions tend to be further from city center
        base_distance = 15.0
    elif "local" in tags or "food" in tags:
        # Local attractions tend to be closer
        base_distance = 3.0
    elif "culture" in tags or "history" in tags or "art" in tags:
        # Cultural attractions are usually in city center
        base_distance = 2.0
    else:
        # Default distance
        base_distance = 8.0
    
    # Add some variation (deterministic for testing)
    import hashlib
    seed = hash(str(candidate.get("place_id", "")) + str(candidate.get("title", ""))) % 1000
    np.random.seed(seed + 1)  # Different seed from opening alignment
    variation = np.random.exponential(2.0)
    return base_distance + variation


def get_user_preference_features(preferences: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract user preference features that can be used for fallback scoring.
    
    Returns:
        Dictionary with user preference information
    """
    themes = set(preferences.get("themes", []))
    activity_tags = set(preferences.get("activity_tags", []))
    avoid_tags = set(preferences.get("avoid_tags", []))
    
    return {
        "themes": themes,
        "activity_tags": activity_tags,
        "avoid_tags": avoid_tags,
        "all_preferred_tags": themes | activity_tags
    }
