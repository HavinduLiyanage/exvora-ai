"""
Contextual reranker that uses tag affinities to reorder candidates.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from .affinity import compute_affinity_by_tag, get_strongest_affinity_tag, format_affinity_reason

# Configuration constants
RERANK_LAMBDA = 0.25  # Weight for affinity bonus in reranking
RERANK_REASON_THRESHOLD = 0.30  # Minimum affinity for reason generation


def candidate_tag_affinity(candidate: Dict[str, Any], aff_by_tag: Dict[str, float]) -> float:
    """
    Calculate average tag affinity for a candidate POI.
    
    Args:
        candidate: POI candidate data
        aff_by_tag: Dictionary mapping tags to affinity scores
    
    Returns:
        Average affinity score for the candidate's tags
    """
    candidate_tags = set(candidate.get("tags", []))
    
    if not candidate_tags or not aff_by_tag:
        return 0.0
    
    # Calculate average affinity for candidate's tags
    tag_affinities = [aff_by_tag.get(tag, 0.0) for tag in candidate_tags if tag in aff_by_tag]
    
    if not tag_affinities:
        return 0.0
    
    return sum(tag_affinities) / len(tag_affinities)


def affinity_bonus_for_poi(poi: Dict[str, Any], affinities: Dict[str, float]) -> float:
    """
    Calculate affinity bonus for a POI (used in ranking).
    
    Args:
        poi: POI data
        affinities: Tag affinities
    
    Returns:
        Affinity bonus score
    """
    return RERANK_LAMBDA * candidate_tag_affinity(poi, affinities)


def rerank_candidates(candidates: List[Dict[str, Any]], audit_log: Dict[str, Any], 
                     base_key: str = "score") -> List[Dict[str, Any]]:
    """
    Rerank candidates based on tag affinities from audit log.
    
    Args:
        candidates: List of candidate POIs with scores
        audit_log: Audit log containing feedback_events
        base_key: Key to use for base score (default: "score")
    
    Returns:
        List of reranked candidates with updated scores and reasons
    """
    if not candidates or not audit_log:
        return candidates
    
    feedback_events = audit_log.get("feedback_events", [])
    if not feedback_events:
        return candidates
    
    # Compute tag affinities from feedback
    aff_by_tag = compute_affinity_by_tag(feedback_events)
    
    if not aff_by_tag:
        return candidates
    
    # Rerank candidates
    reranked = []
    
    for candidate in candidates:
        # Calculate new score
        base_score = candidate.get(base_key, 0.0)
        tag_affinity = candidate_tag_affinity(candidate, aff_by_tag)
        new_score = base_score + RERANK_LAMBDA * tag_affinity
        
        # Create reranked candidate
        reranked_candidate = dict(candidate)
        reranked_candidate["score"] = new_score
        
        # Add reason if affinity is strong enough
        strongest_tag_info = get_strongest_affinity_tag(aff_by_tag, RERANK_REASON_THRESHOLD)
        if strongest_tag_info:
            tag, affinity = strongest_tag_info
            candidate_tags = set(candidate.get("tags", []))
            if tag in candidate_tags:
                reranked_candidate["reason"] = format_affinity_reason(tag, affinity)
        
        reranked.append(reranked_candidate)
    
    # Sort by new score (descending), then by poi_id for determinism
    reranked.sort(key=lambda x: (-x["score"], x.get("poi_id", ""), x.get("title", "")))
    
    return reranked


def rerank_candidates_with_metadata(candidates: List[Dict[str, Any]], audit_log: Dict[str, Any], 
                                   base_key: str = "score") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rerank candidates and return metadata about the reranking process.
    
    Args:
        candidates: List of candidate POIs with scores
        audit_log: Audit log containing feedback_events
        base_key: Key to use for base score (default: "score")
    
    Returns:
        Tuple of (reranked_candidates, metadata)
    """
    if not candidates or not audit_log:
        return candidates, {"rerank_applied": False, "reason": "No candidates or audit log"}
    
    feedback_events = audit_log.get("feedback_events", [])
    if not feedback_events:
        return candidates, {"rerank_applied": False, "reason": "No feedback events"}
    
    # Compute tag affinities
    aff_by_tag = compute_affinity_by_tag(feedback_events)
    
    if not aff_by_tag:
        return candidates, {"rerank_applied": False, "reason": "No tag affinities computed"}
    
    # Count candidates with reasons
    candidates_with_reasons = 0
    reranked = []
    
    for candidate in candidates:
        base_score = candidate.get(base_key, 0.0)
        tag_affinity = candidate_tag_affinity(candidate, aff_by_tag)
        new_score = base_score + RERANK_LAMBDA * tag_affinity
        
        reranked_candidate = dict(candidate)
        reranked_candidate["score"] = new_score
        
        # Add reason if affinity is strong enough
        strongest_tag_info = get_strongest_affinity_tag(aff_by_tag, RERANK_REASON_THRESHOLD)
        if strongest_tag_info:
            tag, affinity = strongest_tag_info
            candidate_tags = set(candidate.get("tags", []))
            if tag in candidate_tags:
                reranked_candidate["reason"] = format_affinity_reason(tag, affinity)
                candidates_with_reasons += 1
        
        reranked.append(reranked_candidate)
    
    # Sort by new score (descending), then by poi_id for determinism
    reranked.sort(key=lambda x: (-x["score"], x.get("poi_id", ""), x.get("title", "")))
    
    metadata = {
        "rerank_applied": True,
        "n_feedback_events": len(feedback_events),
        "n_affinity_tags": len(aff_by_tag),
        "n_candidates_with_reasons": candidates_with_reasons,
        "lambda": RERANK_LAMBDA,
        "reason_threshold": RERANK_REASON_THRESHOLD
    }
    
    return reranked, metadata


def update_affinities_from_actions(actions: List[Any]) -> Dict[str, float]:
    """
    Update affinities from feedback actions (for backward compatibility).
    This is a simplified version that doesn't use timestamps.
    """
    feedback_events = []
    for action in actions:
        if hasattr(action, 'type') and action.type == "rate_item" and hasattr(action, 'rating') and action.rating:
            feedback_events.append({
                "poi_id": getattr(action, 'place_id', None),
                "rating": action.rating,
                "tags": getattr(action, 'tags', []),
                "ts": datetime.now().isoformat()
            })
    
    return compute_affinity_by_tag(feedback_events)


def test_reranker():
    """Test function for reranker functionality."""
    # Test data
    candidates = [
        {
            "poi_id": "ella_hike",
            "title": "Ella Rock Hike",
            "tags": ["hiking", "quiet", "nature"],
            "score": 0.62
        },
        {
            "poi_id": "nightlife_district",
            "title": "Nightlife District",
            "tags": ["nightlife", "crowded"],
            "score": 0.58
        },
        {
            "poi_id": "pettah_market",
            "title": "Pettah Market",
            "tags": ["street_food", "local"],
            "score": 0.55
        }
    ]
    
    audit_log = {
        "feedback_events": [
            {
                "poi_id": "ella_hike",
                "rating": 5,
                "tags": ["hiking", "quiet"],
                "ts": "2025-08-25T08:30:00Z"
            },
            {
                "poi_id": "nightlife_district",
                "rating": 1,
                "tags": ["nightlife", "crowded"],
                "ts": "2025-08-24T19:10:00Z"
            }
        ]
    }
    
    # Test reranking
    reranked, metadata = rerank_candidates_with_metadata(candidates, audit_log)
    
    print("Reranker test results:")
    print(f"Metadata: {metadata}")
    print("\nReranked candidates:")
    for i, candidate in enumerate(reranked):
        print(f"{i+1}. {candidate['title']} (score: {candidate['score']:.3f})")
        if 'reason' in candidate:
            print(f"   Reason: {candidate['reason']}")
    
    # Verify that hiking candidate is boosted
    hiking_candidate = next((c for c in reranked if c['poi_id'] == 'ella_hike'), None)
    nightlife_candidate = next((c for c in reranked if c['poi_id'] == 'nightlife_district'), None)
    
    if hiking_candidate and nightlife_candidate:
        assert hiking_candidate['score'] > 0.62, "Hiking candidate should be boosted"
        assert nightlife_candidate['score'] < 0.58, "Nightlife candidate should be penalized"
        print("\n✓ Reranker test passed!")


if __name__ == "__main__":
    test_reranker()