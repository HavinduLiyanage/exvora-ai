"""
Tests for budget optimizer module.
"""
import pytest
from app.engine.budget import optimize_day_budget


def test_optimize_day_budget_no_cap():
    """Test budget optimization when no cap is set."""
    day_plan = {
        "date": "2025-01-01",
        "summary": {"est_cost": 100},
        "items": [
            {"type": "activity", "place_id": "A", "estimated_cost": 50},
            {"type": "transfer", "from_place_id": "A", "to_place_id": "B"},
            {"type": "activity", "place_id": "B", "estimated_cost": 50}
        ]
    }
    
    ranked_pool = []
    cap = None
    
    optimized_plan, notes = optimize_day_budget(day_plan, ranked_pool, cap)
    
    # Should return unchanged
    assert optimized_plan == day_plan
    assert notes == []


def test_optimize_day_budget_under_cap():
    """Test budget optimization when cost is under cap."""
    day_plan = {
        "date": "2025-01-01",
        "summary": {"est_cost": 80},
        "items": [
            {"type": "activity", "place_id": "A", "estimated_cost": 40},
            {"type": "activity", "place_id": "B", "estimated_cost": 40}
        ]
    }
    
    ranked_pool = []
    cap = 100
    
    optimized_plan, notes = optimize_day_budget(day_plan, ranked_pool, cap)
    
    # Should return unchanged
    assert optimized_plan == day_plan
    assert notes == []


def test_optimize_day_budget_over_cap():
    """Test budget optimization when cost exceeds cap."""
    day_plan = {
        "date": "2025-01-01",
        "summary": {"est_cost": 150},
        "items": [
            {"type": "activity", "place_id": "A", "title": "Expensive Activity", "estimated_cost": 100},
            {"type": "activity", "place_id": "B", "estimated_cost": 50}
        ]
    }
    
    ranked_pool = [
        {"place_id": "C", "name": "Cheap Alternative", "estimated_cost": 30, "duration_minutes": 60},
        {"place_id": "D", "name": "Another Alternative", "estimated_cost": 40, "duration_minutes": 90}
    ]
    
    cap = 100
    
    optimized_plan, notes = optimize_day_budget(day_plan, ranked_pool, cap)
    
    # Should have swapped the expensive activity
    assert len(notes) == 1
    assert "Swapped" in notes[0]
    assert "Expensive Activity" in notes[0]
    assert "Cheap Alternative" in notes[0]
    
    # Check that the expensive activity was replaced
    activities = [item for item in optimized_plan["items"] if item.get("type") != "transfer"]
    activity_costs = [item.get("estimated_cost", 0) for item in activities]
    assert max(activity_costs) < 100  # No activity should cost more than 100


def test_optimize_day_budget_no_alternatives():
    """Test budget optimization when no cheaper alternatives exist."""
    day_plan = {
        "date": "2025-01-01",
        "summary": {"est_cost": 150},
        "items": [
            {"type": "activity", "place_id": "A", "estimated_cost": 100},
            {"type": "activity", "place_id": "B", "estimated_cost": 50}
        ]
    }
    
    ranked_pool = [
        {"place_id": "C", "estimated_cost": 120, "duration_minutes": 60},  # More expensive
        {"place_id": "D", "estimated_cost": 0, "duration_minutes": 60}  # No cost
    ]
    
    cap = 100
    
    optimized_plan, notes = optimize_day_budget(day_plan, ranked_pool, cap)
    
    # Should return unchanged
    assert optimized_plan == day_plan
    assert notes == []


def test_optimize_day_budget_duration_filter():
    """Test budget optimization filters by duration."""
    day_plan = {
        "date": "2025-01-01",
        "summary": {"est_cost": 150},
        "items": [
            {"type": "activity", "place_id": "A", "title": "Expensive Activity", "estimated_cost": 100},
            {"type": "activity", "place_id": "B", "estimated_cost": 50}
        ]
    }
    
    ranked_pool = [
        {"place_id": "C", "name": "Cheap but Long", "estimated_cost": 30, "duration_minutes": 300},  # Too long
        {"place_id": "D", "name": "Good Alternative", "estimated_cost": 40, "duration_minutes": 90}  # Good duration
    ]
    
    cap = 100
    
    optimized_plan, notes = optimize_day_budget(day_plan, ranked_pool, cap)
    
    # Should have swapped with the good alternative
    assert len(notes) == 1
    assert "Good Alternative" in notes[0]


def test_optimize_day_budget_same_poi_excluded():
    """Test budget optimization excludes the same POI."""
    day_plan = {
        "date": "2025-01-01",
        "summary": {"est_cost": 150},
        "items": [
            {"type": "activity", "place_id": "A", "title": "Expensive Activity", "estimated_cost": 100},
            {"type": "activity", "place_id": "B", "estimated_cost": 50}
        ]
    }
    
    ranked_pool = [
        {"place_id": "A", "name": "Same Activity", "estimated_cost": 30, "duration_minutes": 60},  # Same place_id
        {"place_id": "C", "name": "Different Activity", "estimated_cost": 40, "duration_minutes": 60}
    ]
    
    cap = 100
    
    optimized_plan, notes = optimize_day_budget(day_plan, ranked_pool, cap)
    
    # Should have swapped with the different activity
    assert len(notes) == 1
    assert "Different Activity" in notes[0]
    assert "Same Activity" not in notes[0]