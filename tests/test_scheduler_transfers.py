"""
Tests for scheduler and transfers functionality.
"""

from app.engine.schedule import pack_day
from app.engine.transfers import routes_verify
from unittest.mock import patch


def _demo_candidates():
    """Create demo candidates for testing."""
    return [
        {
            "poi_id": "colombo_national_museum",
            "place_id": "ChIJ_col_museum",
            "title": "Museum",
            "duration_minutes": 90,
            "tags": ["history", "museum"],
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        },
        {
            "poi_id": "dutch_hospital_shopping",
            "place_id": "ChIJ_dutch_hospital",
            "title": "Dutch Hospital",
            "duration_minutes": 90,
            "tags": ["shopping", "food"],
            "estimated_cost": 15,
            "price_band": "medium",
            "opening_align": 0.7
        },
        {
            "poi_id": "gangaramaya_temple",
            "place_id": "ChIJ_gangaramaya",
            "title": "Temple",
            "duration_minutes": 60,
            "tags": ["culture", "temple"],
            "estimated_cost": 5,
            "price_band": "low",
            "opening_align": 0.9
        }
    ]


def test_pack_day_inserts_transfer_placeholders():
    """Test that pack_day inserts transfer placeholders between activities."""
    items = pack_day(_demo_candidates(), {"start": "09:00", "end": "17:00", "pace": "moderate"}, locks=[])
    
    # Should have activities and transfers
    types = [("transfer" if it.get("type") == "transfer" else "activity") for it in items]
    assert types.count("transfer") == 2  # 2 transfers for 3 activities
    
    # Check transfer structure
    for it in items:
        if it.get("type") == "transfer":
            assert it.get("source") == "heuristic"
            assert it.get("duration_minutes") is None  # Not yet verified
            assert "from_place_id" in it
            assert "to_place_id" in it
            assert it.get("mode") == "DRIVE"


def test_pack_day_respects_time_constraints():
    """Test that pack_day respects day start/end times."""
    items = pack_day(_demo_candidates(), {"start": "10:00", "end": "16:00", "pace": "moderate"}, locks=[])
    
    # All activities should be within the time window
    for item in items:
        if item.get("type") == "activity":
            start_time = item.get("start", "00:00")
            end_time = item.get("end", "00:00")
            
            # Convert to minutes for comparison
            def time_to_minutes(time_str):
                hour, minute = map(int, time_str.split(":"))
                return hour * 60 + minute
            
            start_min = time_to_minutes(start_time)
            end_min = time_to_minutes(end_time)
            
            assert start_min >= 10 * 60  # After 10:00
            assert end_min <= 16 * 60   # Before 16:00


def test_pack_day_handles_locks():
    """Test that pack_day respects locked time slots."""
    locks = [{"poi_id": "locked_poi", "start": "12:00", "end": "13:00"}]
    
    # Add a locked candidate
    candidates = _demo_candidates() + [{
        "poi_id": "locked_poi",
        "place_id": "ChIJ_locked",
        "title": "Locked Activity",
        "duration_minutes": 60,
        "tags": ["locked"],
        "estimated_cost": 20,
        "price_band": "high",
        "opening_align": 1.0
    }]
    
    items = pack_day(candidates, {"start": "09:00", "end": "17:00", "pace": "moderate"}, locks=locks)
    
    # Should have the locked activity at the specified time
    locked_found = False
    for item in items:
        if item.get("poi_id") == "locked_poi":
            assert item.get("start") == "12:00"
            assert item.get("end") == "13:00"
            locked_found = True
            break
    
    assert locked_found, "Locked activity should be scheduled at specified time"


@patch("app.engine.transfers._call_google_routes")
def test_routes_verify_sets_durations_and_source(mock_google):
    """Test that routes_verify sets durations and source when Google API works."""
    mock_google.return_value = [{"minutes": 14, "km": 4.2}, {"minutes": 11, "km": 3.5}]
    
    items = pack_day(_demo_candidates(), {"start": "09:00", "end": "17:00", "pace": "moderate"}, locks=[])
    transfers = routes_verify(items, mode="DRIVE")
    
    for t in transfers:
        assert t.get("duration_minutes") is not None
        assert t.get("distance_km") is not None
        assert t.get("source") == "google_routes_live"


@patch("app.engine.transfers._call_google_routes", side_effect=RuntimeError("boom"))
def test_routes_verify_falls_back_to_heuristic(mock_google):
    """Test that routes_verify falls back to heuristic when Google API fails."""
    items = pack_day(_demo_candidates(), {"start": "09:00", "end": "17:00", "pace": "moderate"}, locks=[])
    transfers = routes_verify(items, mode="DRIVE")
    
    for t in transfers:
        assert t.get("duration_minutes") is not None
        assert t.get("distance_km") is not None
        assert t.get("source") == "heuristic"


def test_routes_verify_handles_empty_items():
    """Test that routes_verify handles empty items list."""
    transfers = routes_verify([], mode="DRIVE")
    assert transfers == []


def test_routes_verify_handles_no_transfers():
    """Test that routes_verify handles items with no transfers."""
    items = [{"type": "activity", "title": "Test Activity"}]
    transfers = routes_verify(items, mode="DRIVE")
    assert transfers == []


def test_pack_day_alternates_activities_and_transfers():
    """Test that pack_day creates proper activity-transfer alternation."""
    items = pack_day(_demo_candidates(), {"start": "09:00", "end": "17:00", "pace": "moderate"}, locks=[])
    
    # Should alternate between activities and transfers
    for i, item in enumerate(items):
        if i % 2 == 0:  # Even indices should be activities
            assert item.get("type") == "activity"
        else:  # Odd indices should be transfers
            assert item.get("type") == "transfer"


def test_pack_day_handles_short_day():
    """Test that pack_day handles very short day windows."""
    items = pack_day(_demo_candidates(), {"start": "10:00", "end": "11:00", "pace": "moderate"}, locks=[])
    
    # Should only fit one short activity
    activities = [item for item in items if item.get("type") == "activity"]
    assert len(activities) <= 1


def test_pack_day_handles_no_candidates():
    """Test that pack_day handles empty candidates list."""
    items = pack_day([], {"start": "09:00", "end": "17:00", "pace": "moderate"}, locks=[])
    assert items == []


def test_estimate_heuristic():
    """Test the heuristic distance/time estimation."""
    from app.engine.transfers import estimate_heuristic
    
    # Test with known coordinates (Colombo to Kandy)
    colombo_lat, colombo_lng = 6.9271, 79.8612
    kandy_lat, kandy_lng = 7.2936, 80.6413
    
    duration, distance = estimate_heuristic(colombo_lat, colombo_lng, kandy_lat, kandy_lng, "DRIVE")
    
    assert duration > 0
    assert distance > 0
    assert duration >= 3  # Minimum 3 minutes
    assert distance > 50  # Should be reasonable distance between Colombo and Kandy


def test_extract_edges():
    """Test the edge extraction function."""
    from app.engine.transfers import _extract_edges
    
    items = [
        {"type": "activity", "poi_id": "act1"},
        {"type": "transfer", "from_place_id": "A", "to_place_id": "B", "mode": "DRIVE"},
        {"type": "activity", "poi_id": "act2"},
        {"type": "transfer", "from_place_id": "B", "to_place_id": "C", "mode": "WALK"}
    ]
    
    edges = _extract_edges(items)
    
    assert len(edges) == 2
    assert edges[0]["idx"] == 1
    assert edges[0]["from_place_id"] == "A"
    assert edges[0]["to_place_id"] == "B"
    assert edges[0]["mode"] == "DRIVE"
    
    assert edges[1]["idx"] == 3
    assert edges[1]["from_place_id"] == "B"
    assert edges[1]["to_place_id"] == "C"
    assert edges[1]["mode"] == "WALK"
