"""
Tests for tag affinity computation.
"""

import pytest
from datetime import datetime, timedelta
from app.engine.affinity import (
    rating_weight, compute_affinity_by_tag, get_strongest_affinity_tag, 
    format_affinity_reason
)


def test_rating_weight():
    """Test rating weight conversion."""
    # Test valid ratings
    assert rating_weight(1) == -1.0
    assert rating_weight(2) == -0.5
    assert rating_weight(3) == 0.0
    assert rating_weight(4) == 0.5
    assert rating_weight(5) == 1.0
    
    # Test invalid ratings
    with pytest.raises(ValueError):
        rating_weight(0)
    
    with pytest.raises(ValueError):
        rating_weight(6)
    
    with pytest.raises(ValueError):
        rating_weight(-1)


def test_compute_affinity_by_tag():
    """Test affinity computation from feedback events."""
    now = datetime.now()
    
    # Test with positive feedback
    feedback_events = [
        {
            "poi_id": "hiking_trail",
            "rating": 5,
            "tags": ["hiking", "nature", "quiet"],
            "ts": now.isoformat()
        }
    ]
    
    affinities = compute_affinity_by_tag(feedback_events, now)
    
    # Should have positive affinity for all tags
    assert affinities["hiking"] > 0
    assert affinities["nature"] > 0
    assert affinities["quiet"] > 0
    
    # All affinities should be equal (same rating, same time)
    assert abs(affinities["hiking"] - affinities["nature"]) < 0.001
    assert abs(affinities["nature"] - affinities["quiet"]) < 0.001


def test_compute_affinity_negative_rating():
    """Test affinity computation with negative feedback."""
    now = datetime.now()
    
    feedback_events = [
        {
            "poi_id": "nightclub",
            "rating": 1,
            "tags": ["nightlife", "crowded"],
            "ts": now.isoformat()
        }
    ]
    
    affinities = compute_affinity_by_tag(feedback_events, now)
    
    # Should have negative affinity for all tags
    assert affinities["nightlife"] < 0
    assert affinities["crowded"] < 0


def test_compute_affinity_mixed_ratings():
    """Test affinity computation with mixed positive and negative feedback."""
    now = datetime.now()
    
    feedback_events = [
        {
            "poi_id": "hiking_trail",
            "rating": 5,
            "tags": ["hiking", "nature"],
            "ts": (now - timedelta(hours=1)).isoformat()
        },
        {
            "poi_id": "nightclub",
            "rating": 1,
            "tags": ["nightlife", "crowded"],
            "ts": now.isoformat()
        }
    ]
    
    affinities = compute_affinity_by_tag(feedback_events, now)
    
    # Should have positive affinity for hiking/nature
    assert affinities["hiking"] > 0
    assert affinities["nature"] > 0
    
    # Should have negative affinity for nightlife/crowded
    assert affinities["nightlife"] < 0
    assert affinities["crowded"] < 0


def test_compute_affinity_decay():
    """Test that affinities decay over time."""
    now = datetime.now()
    old_time = now - timedelta(days=10)  # 10 days ago
    
    feedback_events = [
        {
            "poi_id": "hiking_trail",
            "rating": 5,
            "tags": ["hiking"],
            "ts": old_time.isoformat()
        }
    ]
    
    affinities = compute_affinity_by_tag(feedback_events, now)
    
    # Affinity should be decayed (less than original 1.0)
    assert 0 < affinities["hiking"] < 1.0


def test_compute_affinity_ema():
    """Test that multiple ratings for same tag use EMA."""
    now = datetime.now()
    
    feedback_events = [
        {
            "poi_id": "hiking_trail1",
            "rating": 3,  # Neutral
            "tags": ["hiking"],
            "ts": (now - timedelta(hours=2)).isoformat()
        },
        {
            "poi_id": "hiking_trail2",
            "rating": 5,  # Positive
            "tags": ["hiking"],
            "ts": now.isoformat()
        }
    ]
    
    affinities = compute_affinity_by_tag(feedback_events, now)
    
    # Should have positive affinity (EMA of neutral + positive)
    assert affinities["hiking"] > 0
    assert affinities["hiking"] < 1.0  # But less than pure positive


def test_get_strongest_affinity_tag():
    """Test getting strongest affinity tag."""
    affinities = {
        "hiking": 0.8,
        "nature": 0.6,
        "crowded": -0.9,
        "nightlife": -0.3
    }
    
    # Should return the tag with strongest absolute affinity
    strongest = get_strongest_affinity_tag(affinities, threshold=0.5)
    assert strongest is not None
    assert strongest[0] == "crowded"  # -0.9 is strongest absolute
    assert strongest[1] == -0.9
    
    # Test with threshold
    strongest_high_threshold = get_strongest_affinity_tag(affinities, threshold=0.95)
    assert strongest_high_threshold is None  # No tag meets 0.95 threshold
    
    # Test with empty affinities
    assert get_strongest_affinity_tag({}) is None


def test_format_affinity_reason():
    """Test affinity reason formatting."""
    # Positive affinity
    reason = format_affinity_reason("hiking", 0.8)
    assert "Boosted" in reason
    assert "hiking" in reason
    assert "0.8" in reason
    
    # Negative affinity
    reason = format_affinity_reason("crowded", -0.6)
    assert "Penalized" in reason
    assert "crowded" in reason
    assert "0.6" in reason  # Should show absolute value


def test_compute_affinity_empty_events():
    """Test affinity computation with empty events."""
    affinities = compute_affinity_by_tag([], datetime.now())
    assert affinities == {}


def test_compute_affinity_no_tags():
    """Test affinity computation with events that have no tags."""
    now = datetime.now()
    
    feedback_events = [
        {
            "poi_id": "test_poi",
            "rating": 5,
            "tags": [],
            "ts": now.isoformat()
        }
    ]
    
    affinities = compute_affinity_by_tag(feedback_events, now)
    assert affinities == {}


def test_compute_affinity_invalid_timestamp():
    """Test affinity computation with invalid timestamp."""
    now = datetime.now()
    
    feedback_events = [
        {
            "poi_id": "test_poi",
            "rating": 5,
            "tags": ["hiking"],
            "ts": "invalid_timestamp"
        }
    ]
    
    # Should handle invalid timestamp gracefully
    affinities = compute_affinity_by_tag(feedback_events, now)
    assert "hiking" in affinities
    assert affinities["hiking"] > 0
