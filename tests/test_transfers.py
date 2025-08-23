import os
import pytest
from app.engine.transfers import verify, reset_transfer_call_counter
from app.config import get_settings


def test_heuristic_transfer_default(monkeypatch):
    """Test that heuristic transfers work by default."""
    # default flag is false
    reset_transfer_call_counter()
    res = verify("from", "to", "DRIVE", "09:00")
    assert res["duration_minutes"] > 0
    assert res["distance_km"] > 0
    assert res["source"] == "heuristic"


def test_heuristic_transfer_walking():
    """Test walking mode heuristic transfers."""
    reset_transfer_call_counter()
    res = verify("from", "to", "WALK", "09:00")
    assert res["duration_minutes"] > 0
    assert res["distance_km"] > 0
    assert res["source"] == "heuristic"
    # Walking should generally be slower than driving
    assert res["duration_minutes"] >= 8


def test_transfer_caching():
    """Test that transfers are cached and reused."""
    reset_transfer_call_counter()
    
    # First call
    res1 = verify("place1", "place2", "DRIVE", "09:00")
    
    # Second call with same parameters
    res2 = verify("place1", "place2", "DRIVE", "09:00")
    
    # Should be identical (cached)
    assert res1["duration_minutes"] == res2["duration_minutes"]
    assert res1["distance_km"] == res2["distance_km"]
    assert res1["source"] == res2["source"]


def test_transfer_time_bucketing():
    """Test that time is bucketed into 15-minute intervals."""
    reset_transfer_call_counter()
    
    # Different times in same 15-min bucket should return same result
    res1 = verify("place1", "place2", "DRIVE", "09:05")
    res2 = verify("place1", "place2", "DRIVE", "09:10")
    
    assert res1["duration_minutes"] == res2["duration_minutes"]
    assert res1["distance_km"] == res2["distance_km"]


def test_transfer_call_counter_reset():
    """Test that transfer call counter resets properly."""
    reset_transfer_call_counter()
    
    # Make several calls
    for i in range(5):
        verify(f"place{i}", f"place{i+1}", "DRIVE", "09:00")
    
    # Reset counter
    reset_transfer_call_counter()
    
    # Should be able to make calls again
    res = verify("place1", "place2", "DRIVE", "09:00")
    assert res["source"] == "heuristic"


@pytest.mark.skip(reason="Needs GOOGLE_MAPS_API_KEY set and network access")
def test_google_transfer_live(monkeypatch):
    """Test live Google API integration (requires API key)."""
    monkeypatch.setenv("USE_GOOGLE_ROUTES", "true")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "YOUR_KEY")
    
    # Clear the cached settings
    get_settings.cache_clear()
    
    reset_transfer_call_counter()
    
    # These must be real Google place_ids to pass live
    res = verify("ChIJy...", "ChIJz...", "DRIVE", "09:00")
    assert res["source"] == "google_routes_live"


def test_google_transfer_no_api_key(monkeypatch):
    """Test that Google transfers fail gracefully without API key."""
    monkeypatch.setenv("USE_GOOGLE_ROUTES", "true")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "")
    
    # Clear the cached settings
    get_settings.cache_clear()
    
    reset_transfer_call_counter()
    
    # Should fall back to heuristic when no API key
    res = verify("place1", "place2", "DRIVE", "09:00")
    assert res["source"] == "heuristic"


def test_transfer_mode_normalization():
    """Test that transfer modes are properly normalized."""
    reset_transfer_call_counter()
    
    # Test various mode formats
    modes = ["DRIVE", "drive", "Driving", "WALK", "walk", "Walking"]
    
    for mode in modes:
        res = verify("place1", "place2", mode, "09:00")
        assert res["duration_minutes"] > 0
        assert res["distance_km"] > 0
        assert res["source"] == "heuristic"


def test_transfer_fallback_behavior():
    """Test that transfers fall back to heuristic when needed."""
    reset_transfer_call_counter()
    
    # Test with invalid place IDs (should still work with heuristic)
    res = verify("", "", "DRIVE", "09:00")
    assert res["duration_minutes"] > 0
    assert res["distance_km"] > 0
    assert res["source"] == "heuristic"
