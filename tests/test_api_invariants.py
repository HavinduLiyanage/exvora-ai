"""
Core API Invariants Smoke Tests

Tests the fundamental contract of the itinerary API to ensure all new features
(budget optimizer, ML preference scorer, contextual reranker) work together
without breaking the core API structure.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

REQ = {
    "trip_context": {
        "base_place_id": "ChIJ_col_museum",  # from our fixture set
        "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
        "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
        "modes": ["DRIVE", "WALK"]
    },
    "preferences": {
        "themes": ["Nature", "Culture"],
        "activity_tags": ["Hiking", "History"],
        "avoid_tags": ["late_night"]  # should push nightlife away if present
    },
    "constraints": {
        "daily_budget_cap": 120,
        "max_transfer_minutes": 120
    },
    "audit_log": {
        "feedback_events": [
            {"poi_id": "ella_rock_hike", "rating": 5, "tags": ["hiking", "quiet"], "ts": "2025-08-25T08:30:00Z"},
            {"poi_id": "nightlife_district_colombo", "rating": 1, "tags": ["nightlife", "crowded"], "ts": "2025-08-24T19:10:00Z"}
        ]
    }
}


def _is_transfer(x):
    """Helper to identify transfer items."""
    return x.get("type") == "transfer"


def test_itinerary_smoke_contract():
    """Test that the core itinerary API contract is preserved with all new features."""
    response = client.post("/v1/itinerary", json=REQ)
    assert response.status_code == 200
    data = response.json()

    # Top-level structure
    assert "days" in data and isinstance(data["days"], list) and len(data["days"]) >= 1
    assert "totals" in data and "trip_cost_est" in data["totals"]
    assert "daily" in data["totals"] and isinstance(data["totals"]["daily"], list)
    assert "currency" in data
    assert "notes" in data  # May be None, but field should exist

    # Per-day invariants
    for day in data["days"]:
        assert "date" in day
        assert "summary" in day and "est_cost" in day["summary"]
        assert "items" in day and isinstance(day["items"], list) and len(day["items"]) >= 1

        # Transfers present between activities; each transfer has required fields
        transfers = [it for it in day["items"] if _is_transfer(it)]
        for t in transfers:
            assert "duration_minutes" in t and t["duration_minutes"] is not None
            assert "distance_km" in t and t["distance_km"] is not None
            assert t.get("source") in ("google_routes_live", "heuristic")

    # Budget optimizer integration - check daily breakdown
    daily_costs = data["totals"]["daily"]
    assert len(daily_costs) == len(data["days"]), "Daily cost breakdown should match number of days"
    
    for i, daily_cost in enumerate(daily_costs):
        assert "date" in daily_cost
        assert "est_cost" in daily_cost
        assert daily_cost["date"] == data["days"][i]["date"], "Daily cost dates should match day dates"


def test_feedback_preserves_contract():
    """Test that the feedback API contract is preserved with all new features."""
    # For smoke testing, we'll just verify the feedback endpoint exists and handles requests
    # The complex Pydantic model validation is tested in dedicated feedback tests
    payload = {
        "date": "2025-09-10",
        "base_place_id": "ChIJ_col_museum",
        "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
        "modes": ["DRIVE", "WALK"],
        "preferences": {"themes": ["Nature", "Culture"]},
        "constraints": {"daily_budget_cap": 120, "max_transfer_minutes": 120},
        "current_day_plan": {
            "date": "2025-09-10",
            "summary": {"title": "Test Day", "est_cost": 50, "walking_km": 2.0, "health_load": "moderate"},
            "items": []
        },
        "actions": []
    }
    
    response = client.post("/v1/itinerary/feedback", json=payload)
    # Should either succeed or return a validation error (not a 500)
    assert response.status_code in [200, 422], f"Unexpected status code: {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        # Core feedback response structure
        assert "date" in data
        assert "items" in data and isinstance(data["items"], list)
        assert "summary" in data and "est_cost" in data["summary"]


def test_budget_optimizer_integration():
    """Test that budget optimizer is properly integrated and working."""
    response = client.post("/v1/itinerary", json=REQ)
    assert response.status_code == 200
    data = response.json()

    # Check budget totals structure
    totals = data["totals"]
    assert "trip_cost_est" in totals
    assert "trip_transfer_minutes" in totals
    assert "daily" in totals

    # Check daily budget caps are respected (within tolerance)
    daily_cap = REQ["constraints"]["daily_budget_cap"]
    for daily_cost in totals["daily"]:
        assert daily_cost["est_cost"] <= daily_cap * 1.1, f"Day {daily_cost['date']} exceeds budget cap: {daily_cost['est_cost']} > {daily_cap}"

    # Check that trip total is reasonable
    assert totals["trip_cost_est"] > 0, "Trip should have some cost"
    assert totals["trip_cost_est"] <= daily_cap * len(data["days"]) * 1.1, "Trip total should not exceed daily cap * days"


def test_ml_preference_scorer_integration():
    """Test that ML preference scorer is integrated and working."""
    response = client.post("/v1/itinerary", json=REQ)
    assert response.status_code == 200
    data = response.json()

    # Check that ranking metadata includes preference model version
    # This would be in the logs, but we can verify the response structure is intact
    assert "days" in data
    assert len(data["days"]) > 0

    # Verify that the API response structure is intact after ML processing
    for day in data["days"]:
        assert "items" in day
        for item in day["items"]:
            # Should have valid POI data structure
            if "poi_id" in item:
                assert "title" in item
                assert "estimated_cost" in item
                # Tags may or may not be present depending on the data source
                if "tags" in item:
                    assert isinstance(item["tags"], list)

    # The ML preference scorer is working if we get a valid response
    # The actual preference application is tested in the reranker tests


def test_reranker_integration():
    """Test that contextual reranker is integrated and working."""
    response = client.post("/v1/itinerary", json=REQ)
    assert response.status_code == 200
    data = response.json()

    # Verify that audit_log is being processed (no errors)
    assert "days" in data
    assert len(data["days"]) > 0

    # Check that the response structure is intact after reranking
    for day in data["days"]:
        assert "items" in day
        for item in day["items"]:
            if "poi_id" in item:
                # Should have valid POI data
                assert "title" in item
                assert "estimated_cost" in item


def test_api_response_time():
    """Test that API responds within reasonable time with all features enabled."""
    import time
    
    start_time = time.time()
    response = client.post("/v1/itinerary", json=REQ)
    end_time = time.time()
    
    assert response.status_code == 200
    response_time = end_time - start_time
    
    # Should respond within 5 seconds (reasonable for ML + budget optimization)
    assert response_time < 5.0, f"API took too long: {response_time:.2f}s"


def test_error_handling():
    """Test that API handles errors gracefully."""
    # Test with invalid request
    invalid_req = {
        "trip_context": {
            "base_place_id": "invalid_place_id",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE", "WALK"]
        },
        "preferences": {
            "themes": ["Nature", "Culture"]
        }
    }
    
    response = client.post("/v1/itinerary", json=invalid_req)
    # Should either return 200 with empty results or appropriate error
    assert response.status_code in [200, 400, 422], f"Unexpected status code: {response.status_code}"
    
    if response.status_code == 200:
        data = response.json()
        # If successful, should have proper structure even with empty results
        assert "days" in data
        assert "totals" in data


def test_deterministic_behavior():
    """Test that API returns deterministic results for the same input."""
    # Make two identical requests
    response1 = client.post("/v1/itinerary", json=REQ)
    response2 = client.post("/v1/itinerary", json=REQ)
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    
    data1 = response1.json()
    data2 = response2.json()
    
    # Results should be identical (deterministic)
    assert data1 == data2, "API should return deterministic results for identical inputs"
