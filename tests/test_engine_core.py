"""Tests for core engine functionality."""

import pytest
from app.engine.candidates import basic_candidates
from app.engine.rank import rank
from app.engine.schedule import schedule_day


def test_candidate_filtering_avoid_tags():
    """Test that candidates are filtered out when they have avoided tags."""
    pois = [
        {"poi_id": "temple1", "tags": ["Culture", "Temple"], "themes": ["Culture"], 
         "opening_hours": {"mon": [{"open": "08:00", "close": "18:00"}]}, "seasonality": ["All"]},
        {"poi_id": "bar1", "tags": ["Nightlife", "Bar"], "themes": ["Entertainment"],
         "opening_hours": {"mon": [{"open": "08:00", "close": "18:00"}]}, "seasonality": ["All"]},
        {"poi_id": "museum1", "tags": ["Culture", "Museum"], "themes": ["Culture"],
         "opening_hours": {"mon": [{"open": "08:00", "close": "18:00"}]}, "seasonality": ["All"]}
    ]
    prefs = {"avoid_tags": ["nightlife"]}
    
    result = basic_candidates(pois, prefs, date_str="2025-09-08", day_window=("09:00", "17:00"))
    
    assert len(result) == 2
    assert all(poi["poi_id"] != "bar1" for poi in result)


def test_candidate_filtering_theme_overlap():
    """Test that candidates require theme overlap when themes are specified."""
    pois = [
        {"poi_id": "temple1", "tags": ["Culture"], "themes": ["Culture"],
         "opening_hours": {"mon": [{"open": "08:00", "close": "18:00"}]}, "seasonality": ["All"]},
        {"poi_id": "beach1", "tags": ["Beach"], "themes": ["Nature"],
         "opening_hours": {"mon": [{"open": "08:00", "close": "18:00"}]}, "seasonality": ["All"]},
        {"poi_id": "museum1", "tags": ["Museum"], "themes": ["Culture"],
         "opening_hours": {"mon": [{"open": "08:00", "close": "18:00"}]}, "seasonality": ["All"]}
    ]
    prefs = {"themes": ["Culture"]}
    
    result = basic_candidates(pois, prefs, date_str="2025-09-08", day_window=("09:00", "17:00"))
    
    assert len(result) == 2
    assert all(poi["poi_id"] != "beach1" for poi in result)


def test_rank_scoring_deterministic():
    """Test that ranking returns deterministic order."""
    pois = [
        {"poi_id": "expensive", "estimated_cost": 100, "duration_minutes": 120},
        {"poi_id": "cheap", "estimated_cost": 10, "duration_minutes": 90},
        {"poi_id": "medium", "estimated_cost": 50, "duration_minutes": 150}
    ]
    daily_cap = 200
    
    result1 = rank(pois, daily_cap)
    result2 = rank(pois, daily_cap)
    
    # Results should be identical
    assert [p["poi_id"] for p in result1] == [p["poi_id"] for p in result2]
    # Cheaper items should generally rank higher
    assert result1[0]["estimated_cost"] <= result1[-1]["estimated_cost"]


def test_schedule_respects_daily_budget_cap():
    """Test that schedule_day respects daily budget cap."""
    pois = [
        {"poi_id": "expensive1", "name": "Expensive Activity 1", "place_id": "place1", 
         "estimated_cost": 80, "duration_minutes": 120},
        {"poi_id": "expensive2", "name": "Expensive Activity 2", "place_id": "place2", 
         "estimated_cost": 90, "duration_minutes": 120},
        {"poi_id": "cheap1", "name": "Cheap Activity", "place_id": "place3", 
         "estimated_cost": 10, "duration_minutes": 60}
    ]
    daily_cap = 100
    
    result = schedule_day("2025-09-10", pois, daily_cap, day_start="09:00", day_end="18:00")
    
    # Calculate total cost of activities (excluding transfers)
    total_cost = sum(
        item.get("estimated_cost", 0) 
        for item in result["items"] 
        if item.get("type") != "transfer"
    )
    
    assert total_cost <= daily_cap
    assert result["summary"]["est_cost"] <= daily_cap


def test_schedule_includes_transfers():
    """Test that schedule includes transfers between activities."""
    pois = [
        {"poi_id": "poi1", "name": "Activity 1", "place_id": "place1", 
         "estimated_cost": 20, "duration_minutes": 60},
        {"poi_id": "poi2", "name": "Activity 2", "place_id": "place2", 
         "estimated_cost": 30, "duration_minutes": 90}
    ]
    
    result = schedule_day("2025-09-10", pois, None, day_start="09:00", day_end="18:00")
    
    # Should have activities and transfers
    assert len(result["items"]) >= 2
    # Should contain at least one transfer
    has_transfer = any(item.get("type") == "transfer" for item in result["items"])
    assert has_transfer


def test_availability_filters():
    """Test that candidates are filtered by opening hours and seasonality."""
    pois = [
        {"poi_id": "open_one", "tags": ["Culture"], "themes": ["Culture"],
         "opening_hours": {"mon": [{"open": "09:00", "close": "17:00"}]}, "seasonality": ["All"]},
        {"poi_id": "closed_one", "tags": ["Culture"], "themes": ["Culture"],
         "opening_hours": {"mon": [{"open": "20:00", "close": "22:00"}]}, "seasonality": ["All"]},
        {"poi_id": "seasonal_one", "tags": ["Nature"], "themes": ["Nature"],
         "opening_hours": {"mon": [{"open": "09:00", "close": "17:00"}]}, "seasonality": ["Jan", "Feb"]}
    ]
    prefs = {"themes": ["Culture", "Nature"]}
    
    # Test Monday during day (should get open_one and seasonal_one)
    result = basic_candidates(pois, prefs, date_str="2025-01-06", day_window=("09:00", "17:00"))
    ids = {p["poi_id"] for p in result}
    assert "open_one" in ids and "closed_one" not in ids
    assert "seasonal_one" in ids  # January is in season


def test_locks_first_packing():
    """Test that locks are placed first and activities packed around them."""
    # Create a mock lock object
    class MockLock:
        def __init__(self, place_id, start, end, title):
            self.place_id = place_id
            self.start = start
            self.end = end
            self.title = title
    
    sample_ranked = [
        {"poi_id": "poi1", "name": "Activity 1", "place_id": "place1", 
         "estimated_cost": 20, "duration_minutes": 60},
        {"poi_id": "poi2", "name": "Activity 2", "place_id": "place2", 
         "estimated_cost": 30, "duration_minutes": 90}
    ]
    
    plan = schedule_day("2025-09-10", sample_ranked, 120, day_start="09:00", day_end="18:00",
                        locks=[MockLock("L1", "12:00", "13:00", "Lunch")])
    
    # Lock should be present and activities around it
    times = [it.get("start") for it in plan["items"] if it.get("type") != "transfer"]
    assert "12:00" in times  # lock placed
