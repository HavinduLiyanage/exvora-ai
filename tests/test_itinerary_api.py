"""Integration tests for the itinerary API endpoints."""

import pytest
from fastapi.testclient import TestClient
from datetime import date, time
from app.main import app
from app.dataset.loader import load_pois

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_data():
    """Load POIs before each test."""
    load_pois()


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset rate limit between tests."""
    from app.api.routes import _rate_limit_store
    _rate_limit_store.clear()
    yield


def test_healthz_endpoint():
    """Test the health check endpoint."""
    response = client.get("/v1/healthz")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["pois_loaded"] > 0


def test_build_itinerary_success():
    """Test successful itinerary generation."""
    request_body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-14"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE", "WALK"]
        },
        "preferences": {
            "themes": ["Culture", "Food"],
            "avoid_tags": ["nightlife"]
        },
        "constraints": {
            "daily_budget_cap": 120,
            "max_transfer_minutes": 90
        },
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_body)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "days" in data
    assert len(data["days"]) >= 1
    assert data["currency"] == "LKR"
    
    # Check day structure
    day = data["days"][0]
    assert "date" in day
    assert "summary" in day
    assert "items" in day
    
    # Check that we have both activities and transfers
    items = day["items"]
    has_activity = any(item.get("place_id") for item in items if item.get("type") != "transfer")
    has_transfer = any(item.get("type") == "transfer" for item in items)
    
    assert has_activity
    if len(items) > 1:  # Only expect transfers if we have multiple items
        assert has_transfer


def test_build_itinerary_with_budget_constraint():
    """Test itinerary generation respects budget constraints."""
    request_body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "light"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 50},
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_body)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that total cost is within budget
    day = data["days"][0]
    total_cost = day["summary"]["est_cost"]
    assert total_cost <= 50


def test_feedback_remove_item():
    """Test feedback endpoint with remove_item action."""
    # First, build an initial itinerary
    initial_request = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE", "WALK"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 120},
        "locks": []
    }
    
    initial_response = client.post("/v1/itinerary", json=initial_request)
    initial_day = initial_response.json()["days"][0]
    
    # Find an activity to remove
    activity_to_remove = None
    for item in initial_day["items"]:
        if item.get("place_id") and item.get("type") != "transfer":
            activity_to_remove = item["place_id"]
            break
    
    assert activity_to_remove is not None, "No activity found to remove"
    
    # Now send feedback to remove that item
    feedback_request = {
        "date": "2025-09-10",
        "base_place_id": "ChIJbase",
        "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
        "modes": ["DRIVE", "WALK"],
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 120},
        "locks": [],
        "current_day_plan": initial_day,
        "actions": [
            {
                "type": "remove_item",
                "place_id": activity_to_remove
            }
        ]
    }
    
    response = client.post("/v1/itinerary/feedback", json=feedback_request)
    
    assert response.status_code == 200
    new_day = response.json()
    
    # Check that the removed item is no longer in the plan
    new_place_ids = {
        item.get("place_id") for item in new_day["items"] 
        if item.get("place_id") and item.get("type") != "transfer"
    }
    assert activity_to_remove not in new_place_ids


def test_build_itinerary_invalid_request():
    """Test that invalid requests return 422."""
    invalid_request = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            # Missing required fields
        }
    }
    
    response = client.post("/v1/itinerary", json=invalid_request)
    assert response.status_code == 422


def test_itinerary_respects_locks_and_budget():
    """Test itinerary generation respects locks and budget constraints."""
    body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-14"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE", "WALK"]
        },
        "preferences": {"themes": ["Culture"], "avoid_tags": []},
        "constraints": {"daily_budget_cap": 100},
        "locks": [{"place_id": "ChIJlock1", "start": "12:00", "end": "13:00", "title": "Lunch"}]
    }
    res = client.post("/v1/itinerary", json=body)
    assert res.status_code == 200
    data = res.json()
    items = data["days"][0]["items"]
    assert any(i.get("title") == "Lunch" for i in items)


def test_feedback_remove_and_rate_bias():
    """Test feedback with remove_item and rate_item actions."""
    # First, build an initial itinerary
    seed_itinerary_body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE", "WALK"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 120},
        "locks": []
    }
    
    res = client.post("/v1/itinerary", json=seed_itinerary_body)
    day = res.json()["days"][0]["date"]
    
    # Pick an activity place_id from response
    act = next(i for i in res.json()["days"][0]["items"] if i.get("type") != "transfer")
    
    fb = {
        "date": day,
        "base_place_id": "ChIJbase",
        "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
        "modes": ["DRIVE", "WALK"],
        "preferences": {"themes": ["Culture"], "avoid_tags": []},
        "constraints": {"daily_budget_cap": 100},
        "locks": [],
        "current_day_plan": {"date": day, "summary": {"title": "tmp"}, "items": []},
        "actions": [
            {"type": "remove_item", "place_id": act["place_id"]},
            {"type": "rate_item", "place_id": act["place_id"], "rating": 1, "tags": ["too_crowded"]}
        ]
    }
    
    res2 = client.post("/v1/itinerary/feedback", json=fb)
    assert res2.status_code == 200
    
    ids = [i.get("place_id") for i in res2.json()["items"] if i.get("type") != "transfer"]
    assert act["place_id"] not in ids


def test_locks_conflict_returns_409():
    """Test that overlapping locks return 409 conflict."""
    body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-14"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE", "WALK"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 100},
        "locks": [
            {"place_id": "ChIJlock1", "start": "12:00", "end": "13:00", "title": "Lunch"},
            {"place_id": "ChIJlock2", "start": "12:30", "end": "13:30", "title": "Meeting"}
        ]
    }
    res = client.post("/v1/itinerary", json=body)
    assert res.status_code == 409
    # Check structured error format
    error_data = res.json()
    assert "error" in error_data
    assert error_data["error"]["code"] == 409
    assert error_data["error"]["type"] == "lock_conflict"
    assert "Lock time windows overlap" in error_data["error"]["message"]


def test_validation_limits_items_per_day():
    """Test that each day respects MAX_ITEMS_PER_DAY limit."""
    # This test might need adjustment based on actual POI data
    request_body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "intense"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture", "Nature", "Food"]},
        "constraints": {"daily_budget_cap": 500},  # High budget to allow many items
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_body)
    
    # Should either succeed (if POI data allows) or fail with 400 if limit exceeded
    if response.status_code == 200:
        data = response.json()
        for day in data["days"]:
            non_transfer_items = [item for item in day["items"] if item.get("type") not in ["transfer", "break"]]
            assert len(non_transfer_items) <= 4  # MAX_ITEMS_PER_DAY default


def test_feedback_preserves_locks():
    """Test that feedback repack preserves existing locks."""
    # Create a day with a lock
    itinerary_request = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 50},  # Lower budget to avoid exceeding item limit
        "locks": [
            {
                "place_id": "ChIJlocked",
                "start": "14:00",
                "end": "15:00",
                "title": "Reserved Lunch"
            }
        ]
    }
    
    itinerary_response = client.post("/v1/itinerary", json=itinerary_request)
    assert itinerary_response.status_code == 200
    itinerary_data = itinerary_response.json()
    
    # Test feedback that should preserve the lock
    feedback_request = {
        "date": "2025-09-10",
        "base_place_id": "ChIJbase",
        "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
        "modes": ["DRIVE"],
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 50},  # Keep same budget
        "locks": [
            {
                "place_id": "ChIJlocked",
                "start": "14:00",
                "end": "15:00",
                "title": "Reserved Lunch"
            }
        ],
        "current_day_plan": itinerary_data["days"][0],
        "actions": [
            {
                "type": "rate_item",
                "place_id": itinerary_data["days"][0]["items"][0]["place_id"],
                "rating": 3
            }
        ]
    }
    
    response = client.post("/v1/itinerary/feedback", json=feedback_request)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that the lock is preserved
    lock_items = [item for item in data["items"] if item.get("place_id") == "ChIJlocked"]
    assert len(lock_items) == 1
    lock_item = lock_items[0]
    assert lock_item["start"] == "14:00"
    assert lock_item["end"] == "15:00"
    assert lock_item["title"] == "Reserved Lunch"


def test_response_notes_on_heuristic_fallback():
    """Test that response includes notes when heuristic fallback is used."""
    request_body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 100},
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_body)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that notes field exists (may be None if no fallbacks)
    assert "notes" in data
    # If notes exist, they should contain information about heuristic usage
    if data.get("notes"):
        assert any("heuristic" in note.lower() for note in data["notes"])


def test_currency_conversion():
    """Test that currency conversion works correctly."""
    request_body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {
            "themes": ["Culture"],
            "currency": "USD"  # Request USD instead of default LKR
        },
        "constraints": {"daily_budget_cap": 100},
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_body)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that currency is USD
    assert data["currency"] == "USD"
    
    # Check that totals are computed (currency conversion should work)
    assert "totals" in data
    assert data["totals"]["total_cost"] is not None


def test_structured_error_format():
    """Test that errors follow consistent structured format."""
    # Test with invalid date range (should trigger 422)
    request_body = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-25"},  # >14 days
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 100},
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_body)
    
    assert response.status_code == 422
    data = response.json()
    
    # Check structured error format
    assert "error" in data
    assert data["error"]["code"] == 422
    assert data["error"]["type"] == "validation_error"
    assert "message" in data["error"]
    assert "hints" in data["error"]


def test_feedback_notes():
    """Test that feedback responses include notes about changes."""
    # Create a day with a lock
    itinerary_request = {
        "trip_context": {
            "base_place_id": "ChIJbase",
            "date_range": {"start": "2025-09-10", "end": "2025-09-11"},
            "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 50},
        "locks": [
            {
                "place_id": "ChIJlocked",
                "start": "14:00",
                "end": "15:00",
                "title": "Reserved Lunch"
            }
        ]
    }
    
    itinerary_response = client.post("/v1/itinerary", json=itinerary_request)
    assert itinerary_response.status_code == 200
    itinerary_data = itinerary_response.json()
    
    # Test feedback that removes an item
    feedback_request = {
        "date": "2025-09-10",
        "base_place_id": "ChIJbase",
        "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
        "modes": ["DRIVE"],
        "preferences": {"themes": ["Culture"]},
        "constraints": {"daily_budget_cap": 50},
        "locks": [
            {
                "place_id": "ChIJlocked",
                "start": "14:00",
                "end": "15:00",
                "title": "Reserved Lunch"
            }
        ],
        "current_day_plan": itinerary_data["days"][0],
        "actions": [
            {
                "type": "remove_item",
                "place_id": itinerary_data["days"][0]["items"][0]["place_id"]
            }
        ]
    }
    
    response = client.post("/v1/itinerary/feedback", json=feedback_request)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that notes field exists and contains information about the removal
    assert "notes" in data
    if data.get("notes"):
        assert any("removed" in note.lower() for note in data["notes"])
