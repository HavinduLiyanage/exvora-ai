"""
Tests for transfer edge limits and verification caps.
"""

from app.engine.schedule import pack_day
from app.engine.transfers import routes_verify
from unittest.mock import patch
import os


def test_transfer_edge_limit_cap(monkeypatch):
    """Test that transfer verification respects the MAX_EDGES limit."""
    # Create many candidates to generate many transfers
    cands = [
        {
            "poi_id": f"id{i}",
            "place_id": f"pl{i}",
            "title": f"T{i}",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        }
        for i in range(12)
    ]
    
    items = pack_day(cands, {"start": "08:00", "end": "20:00", "pace": "moderate"}, locks=[])
    
    # Set a very low limit
    monkeypatch.setenv("TRANSFER_VERIFY_MAX_EDGES", "4")
    
    with patch("app.engine.transfers._call_google_routes") as g:
        routes_verify(items, mode="DRIVE")
        # Should only call Google API for the limited number of edges
        assert g.call_count <= 4


def test_transfer_edge_limit_default():
    """Test that the default MAX_EDGES limit is applied."""
    # Create many candidates
    cands = [
        {
            "poi_id": f"id{i}",
            "place_id": f"pl{i}",
            "title": f"T{i}",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        }
        for i in range(50)  # More than default limit
    ]
    
    items = pack_day(cands, {"start": "08:00", "end": "20:00", "pace": "moderate"}, locks=[])
    
    with patch("app.engine.transfers._call_google_routes") as g:
        routes_verify(items, mode="DRIVE")
        # Should respect the default limit of 30
        assert g.call_count <= 30


def test_transfer_edge_limit_zero():
    """Test behavior when MAX_EDGES is set to zero."""
    cands = [
        {
            "poi_id": "id1",
            "place_id": "pl1",
            "title": "T1",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        }
    ]
    
    items = pack_day(cands, {"start": "08:00", "end": "20:00", "pace": "moderate"}, locks=[])
    
    # Set limit to zero
    original_limit = os.getenv("TRANSFER_VERIFY_MAX_EDGES")
    os.environ["TRANSFER_VERIFY_MAX_EDGES"] = "0"
    
    try:
        with patch("app.engine.transfers._call_google_routes") as g:
            routes_verify(items, mode="DRIVE")
            # Should not call Google API at all
            assert g.call_count == 0
    finally:
        # Restore original limit
        if original_limit is not None:
            os.environ["TRANSFER_VERIFY_MAX_EDGES"] = original_limit
        else:
            os.environ.pop("TRANSFER_VERIFY_MAX_EDGES", None)


def test_transfer_edge_limit_negative():
    """Test behavior when MAX_EDGES is set to negative value."""
    cands = [
        {
            "poi_id": "id1",
            "place_id": "pl1",
            "title": "T1",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        }
    ]
    
    items = pack_day(cands, {"start": "08:00", "end": "20:00", "pace": "moderate"}, locks=[])
    
    # Set negative limit
    original_limit = os.getenv("TRANSFER_VERIFY_MAX_EDGES")
    os.environ["TRANSFER_VERIFY_MAX_EDGES"] = "-5"
    
    try:
        with patch("app.engine.transfers._call_google_routes") as g:
            routes_verify(items, mode="DRIVE")
            # Should not call Google API at all (negative limit treated as 0)
            assert g.call_count == 0
    finally:
        # Restore original limit
        if original_limit is not None:
            os.environ["TRANSFER_VERIFY_MAX_EDGES"] = original_limit
        else:
            os.environ.pop("TRANSFER_VERIFY_MAX_EDGES", None)


def test_transfer_edge_limit_invalid():
    """Test behavior when MAX_EDGES is set to invalid value."""
    cands = [
        {
            "poi_id": "id1",
            "place_id": "pl1",
            "title": "T1",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        }
    ]
    
    items = pack_day(cands, {"start": "08:00", "end": "20:00", "pace": "moderate"}, locks=[])
    
    # Set invalid limit
    original_limit = os.getenv("TRANSFER_VERIFY_MAX_EDGES")
    os.environ["TRANSFER_VERIFY_MAX_EDGES"] = "invalid"
    
    try:
        with patch("app.engine.transfers._call_google_routes") as g:
            routes_verify(items, mode="DRIVE")
            # Should use default limit (30) when invalid value provided
            assert g.call_count <= 30
    finally:
        # Restore original limit
        if original_limit is not None:
            os.environ["TRANSFER_VERIFY_MAX_EDGES"] = original_limit
        else:
            os.environ.pop("TRANSFER_VERIFY_MAX_EDGES", None)


def test_transfer_verification_graceful_behavior():
    """Test that transfer verification behaves gracefully when limits are exceeded."""
    # Create many candidates
    cands = [
        {
            "poi_id": f"id{i}",
            "place_id": f"pl{i}",
            "title": f"T{i}",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        }
        for i in range(100)  # Way more than any reasonable limit
    ]
    
    items = pack_day(cands, {"start": "08:00", "end": "20:00", "pace": "moderate"}, locks=[])
    
    # Should not raise an exception even with many transfers
    try:
        transfers = routes_verify(items, mode="DRIVE")
        # Should return some transfers
        assert len(transfers) > 0
        
        # All transfers should have duration and distance set
        for transfer in transfers:
            assert transfer.get("duration_minutes") is not None
            assert transfer.get("distance_km") is not None
            assert transfer.get("source") in ["google_routes_live", "heuristic"]
    except Exception as e:
        pytest.fail(f"Transfer verification should not raise exceptions: {e}")


def test_transfer_verification_with_google_failure():
    """Test that transfer verification handles Google API failures gracefully."""
    cands = [
        {
            "poi_id": "id1",
            "place_id": "pl1",
            "title": "T1",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        },
        {
            "poi_id": "id2",
            "place_id": "pl2",
            "title": "T2",
            "duration_minutes": 30,
            "estimated_cost": 10,
            "price_band": "low",
            "opening_align": 0.8
        }
    ]
    
    items = pack_day(cands, {"start": "08:00", "end": "20:00", "pace": "moderate"}, locks=[])
    
    # Mock Google API to fail
    with patch("app.engine.transfers._call_google_routes", side_effect=Exception("Google API failed")):
        transfers = routes_verify(items, mode="DRIVE")
        
        # Should fall back to heuristic
        for transfer in transfers:
            assert transfer.get("duration_minutes") is not None
            assert transfer.get("distance_km") is not None
            assert transfer.get("source") == "heuristic"
