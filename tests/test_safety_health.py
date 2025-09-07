"""
Tests for safety and health features.
"""
import pytest
from app.engine.rank import _calculate_safety_penalty, _calculate_health_fit, collect_safety_warnings
from app.engine.rules import _should_filter_safety


def test_safety_penalty_crowded():
    """Test safety penalty for crowded POIs when avoiding crowded places."""
    poi = {
        "name": "Crowded Market",
        "safety_flags": ["crowded_peak_hours"]
    }
    prefs = {
        "avoid_tags": ["crowded"]
    }
    
    penalty = _calculate_safety_penalty(poi, prefs)
    assert penalty == 0.2


def test_safety_penalty_night():
    """Test safety penalty for night safety flags."""
    poi = {
        "name": "Night Club",
        "safety_flags": ["unsafe_night"]
    }
    prefs = {
        "avoid_tags": []
    }
    
    penalty = _calculate_safety_penalty(poi, prefs)
    assert penalty == 0.1


def test_safety_penalty_combined():
    """Test safety penalty for multiple safety flags."""
    poi = {
        "name": "Crowded Night Spot",
        "safety_flags": ["crowded_peak_hours", "unsafe_night"]
    }
    prefs = {
        "avoid_tags": ["crowded"]
    }
    
    penalty = _calculate_safety_penalty(poi, prefs)
    assert penalty == 0.25  # Capped at 0.25


def test_safety_penalty_no_flags():
    """Test safety penalty for POI with no safety flags."""
    poi = {
        "name": "Safe Place",
        "safety_flags": []
    }
    prefs = {
        "avoid_tags": ["crowded"]
    }
    
    penalty = _calculate_safety_penalty(poi, prefs)
    assert penalty == 0.0


def test_health_fit_light_pace():
    """Test health fit for light pace preference."""
    # Strenuous activity should be penalized
    poi = {
        "tags": ["Hiking", "Trekking"],
        "duration_minutes": 120
    }
    
    health_fit = _calculate_health_fit(poi, "light")
    assert health_fit == 0.3  # Penalized for strenuous activity
    
    # Short activity should be preferred
    poi_short = {
        "tags": ["Museum"],
        "duration_minutes": 60
    }
    
    health_fit_short = _calculate_health_fit(poi_short, "light")
    assert health_fit_short == 1.0  # Preferred for light pace


def test_health_fit_intense_pace():
    """Test health fit for intense pace preference."""
    # Short activities should be boosted
    poi = {
        "tags": ["Museum"],
        "duration_minutes": 45
    }
    
    health_fit = _calculate_health_fit(poi, "intense")
    assert health_fit == 1.0  # Boosted for short duration


def test_health_fit_moderate_pace():
    """Test health fit for moderate pace preference."""
    # Balanced activities should be preferred
    poi = {
        "tags": ["Museum"],
        "duration_minutes": 90
    }
    
    health_fit = _calculate_health_fit(poi, "moderate")
    assert health_fit == 1.0  # Good fit for moderate pace


def test_safety_filtering():
    """Test safety filtering in rules."""
    # Should filter out crowded POI when avoiding crowded
    poi = {
        "name": "Crowded Market",
        "safety_flags": ["crowded_peak_hours"]
    }
    constraints = {
        "avoid_tags": ["crowded"]
    }
    
    should_filter = _should_filter_safety(poi, constraints)
    assert should_filter is True
    
    # Should not filter when not avoiding crowded
    constraints_no_avoid = {
        "avoid_tags": []
    }
    
    should_filter_no_avoid = _should_filter_safety(poi, constraints_no_avoid)
    assert should_filter_no_avoid is False


def test_collect_safety_warnings():
    """Test collecting safety warnings for scheduled items."""
    day_items = [
        {
            "type": "activity",
            "title": "Crowded Market",
            "safety_flags": ["crowded_peak_hours"]
        },
        {
            "type": "transfer",
            "from_place_id": "A",
            "to_place_id": "B"
        },
        {
            "type": "activity",
            "title": "Night Club",
            "safety_flags": ["unsafe_night"]
        },
        {
            "type": "activity",
            "title": "Safe Museum",
            "safety_flags": []
        }
    ]
    
    warnings = collect_safety_warnings(day_items)
    
    assert len(warnings) == 2
    assert "Crowded Market" in warnings[0]
    assert "crowded at peak hours" in warnings[0]
    assert "Night Club" in warnings[1]
    assert "unsafe at night" in warnings[1]


def test_collect_safety_warnings_no_flags():
    """Test collecting safety warnings when no safety flags exist."""
    day_items = [
        {
            "type": "activity",
            "title": "Safe Museum",
            "safety_flags": []
        },
        {
            "type": "transfer",
            "from_place_id": "A",
            "to_place_id": "B"
        }
    ]
    
    warnings = collect_safety_warnings(day_items)
    assert len(warnings) == 0