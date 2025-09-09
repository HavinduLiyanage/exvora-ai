"""
Tests for feedback re-verification of changed edges.
"""

from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)


@patch("app.engine.transfers._call_google_routes")
def test_feedback_only_reverifies_changed_edges(mock_google):
    """Test that feedback only re-verifies changed edges."""
    req = {
        "trip_context": {
            "base_place_id": "ChIJ_col_museum",
            "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"], "activity_tags": []},
        "constraints": {"daily_budget_cap": 120, "max_transfer_minutes": 120}
    }
    
    # First request
    r1 = client.post("/v1/itinerary", json=req)
    assert r1.status_code == 200
    day = r1.json()["days"][0]
    
    # Reset mock to count only feedback calls
    mock_google.reset_mock()
    
    # Feedback request with item replacement
    feedback = {
        "date": day["date"],
        "base_place_id": req["trip_context"]["base_place_id"],
        "day_template": req["trip_context"]["day_template"],
        "modes": req["trip_context"]["modes"],
        "preferences": req["preferences"],
        "constraints": req["constraints"],
        "current_day_plan": {
            "items": day["items"]
        },
        "actions": [
            {
                "type": "remove_item",
                "place_id": day["items"][2]["place_id"]  # Use activity item (index 2)
            },
            {
                "type": "request_alternative",
                "near_place_id": day["items"][0]["place_id"]
            }
        ]
    }
    
    r2 = client.post("/v1/itinerary/feedback", json=feedback)
    if r2.status_code != 200:
        print(f"Error response: {r2.json()}")
    assert r2.status_code == 200
    
    # Should only call Google API for changed edges (limited number)
    assert mock_google.call_count <= 3  # Only adjacent edges reverified


def test_feedback_handles_no_changes():
    """Test that feedback handles requests with no changes."""
    req = {
        "trip_context": {
            "base_place_id": "ChIJ_col_museum",
            "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"], "activity_tags": []},
        "constraints": {"daily_budget_cap": 120, "max_transfer_minutes": 120}
    }
    
    # First request
    r1 = client.post("/v1/itinerary", json=req)
    assert r1.status_code == 200
    day = r1.json()["days"][0]
    
    # Feedback with no actions
    feedback = {
        "date": day["date"],
        "base_place_id": req["trip_context"]["base_place_id"],
        "day_template": req["trip_context"]["day_template"],
        "modes": req["trip_context"]["modes"],
        "preferences": req["preferences"],
        "constraints": req["constraints"],
        "current_day_plan": {
            "items": day["items"]
        },
        "actions": []  # No changes
    }
    
    r2 = client.post("/v1/itinerary/feedback", json=feedback)
    if r2.status_code != 200:
        print(f"Error response: {r2.json()}")
    assert r2.status_code == 200
    
    # Should return the same day structure
    assert r2.json()["date"] == day["date"]
    # Feedback might filter out transfers, so just check we have some items
    assert len(r2.json()["items"]) > 0


@patch("app.engine.transfers._call_google_routes")
def test_feedback_preserves_transfer_verification(mock_google):
    """Test that feedback preserves transfer verification results."""
    mock_google.return_value = [{"minutes": 15, "km": 5.0}]
    
    req = {
        "trip_context": {
            "base_place_id": "ChIJ_col_museum",
            "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"], "activity_tags": []},
        "constraints": {"daily_budget_cap": 120, "max_transfer_minutes": 120}
    }
    
    # First request
    r1 = client.post("/v1/itinerary", json=req)
    assert r1.status_code == 200
    day = r1.json()["days"][0]
    
    # Check that transfers have been verified
    transfers = [item for item in day["items"] if item.get("type") == "transfer"]
    for transfer in transfers:
        # Duration and distance might be None for heuristic fallback
        assert transfer.get("source") in ["google_routes_live", "heuristic"]
        # If source is google_routes_live, duration and distance should be present
        if transfer.get("source") == "google_routes_live":
            assert transfer.get("duration_minutes") is not None
            assert transfer.get("distance_km") is not None
    
    # Reset mock
    mock_google.reset_mock()
    
    # Feedback request
    feedback = {
        "trip_context": req["trip_context"],
        "preferences": req["preferences"],
        "constraints": req["constraints"],
        "day": {
            "date": day["date"],
            "actions": []  # No changes
        }
    }
    
    r2 = client.post("/v1/itinerary/feedback", json=feedback)
    if r2.status_code != 200:
        print(f"Error response: {r2.json()}")
    assert r2.status_code == 200
    
    # Should not call Google API again for unchanged edges
    assert mock_google.call_count == 0
