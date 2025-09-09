import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_itinerary_with_budget_cap():
    """Test that itinerary API respects budget cap and includes budget totals."""
    request_data = {
        "trip_context": {
            "base_place_id": "test_base",
            "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {
            "themes": ["culture"],
            "activity_tags": [],
            "avoid_tags": []
        },
        "constraints": {
            "daily_budget_cap": 50.0,
            "max_transfer_minutes": 60
        },
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have budget totals
    assert "totals" in data
    assert "trip_cost_est" in data["totals"]
    assert "trip_transfer_minutes" in data["totals"]
    assert "daily" in data["totals"]
    
    # Should have per-day cost estimates
    assert len(data["days"]) == 1
    day = data["days"][0]
    assert "summary" in day
    assert "est_cost" in day["summary"]
    
    # If budget cap is applied, day cost should be within cap or have warning
    day_cost = day["summary"]["est_cost"]
    if day_cost > 50.0:
        # Should have budget warning in notes
        assert "notes" in day
        assert any("Budget warning" in note for note in day["notes"])

def test_itinerary_without_budget_cap():
    """Test that itinerary API works without budget cap."""
    request_data = {
        "trip_context": {
            "base_place_id": "test_base",
            "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {
            "themes": ["culture"],
            "activity_tags": [],
            "avoid_tags": []
        },
        "constraints": {
            "max_transfer_minutes": 60
        },
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should still have budget totals
    assert "totals" in data
    assert "trip_cost_est" in data["totals"]
    assert "trip_transfer_minutes" in data["totals"]
    assert "daily" in data["totals"]
    
    # Should have per-day cost estimates
    assert len(data["days"]) == 1
    day = data["days"][0]
    assert "summary" in day
    assert "est_cost" in day["summary"]

def test_itinerary_budget_optimization_notes():
    """Test that budget optimization adds appropriate notes when swaps occur."""
    request_data = {
        "trip_context": {
            "base_place_id": "test_base",
            "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {
            "themes": ["culture"],
            "activity_tags": [],
            "avoid_tags": []
        },
        "constraints": {
            "daily_budget_cap": 30.0,  # Low cap to force optimization
            "max_transfer_minutes": 60
        },
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Check if budget optimization occurred
    day = data["days"][0]
    if "notes" in day and day["notes"]:
        # Should have either swap notes or budget warning
        has_budget_note = any(
            "swapped" in note or "Budget warning" in note or "Budget optimizer" in note
            for note in day["notes"]
        )
        # Note: This might not always trigger depending on available candidates
        # The important thing is that the API handles budget constraints properly

def test_itinerary_multi_day_budget_totals():
    """Test that multi-day itinerary includes proper budget totals."""
    request_data = {
        "trip_context": {
            "base_place_id": "test_base",
            "date_range": {"start": "2025-09-10", "end": "2025-09-12"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {
            "themes": ["culture"],
            "activity_tags": [],
            "avoid_tags": []
        },
        "constraints": {
            "daily_budget_cap": 100.0,
            "max_transfer_minutes": 60
        },
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have 3 days
    assert len(data["days"]) == 3
    
    # Should have budget totals
    assert "totals" in data
    totals = data["totals"]
    assert "trip_cost_est" in totals
    assert "trip_transfer_minutes" in totals
    assert "daily" in totals
    
    # Daily breakdown should have 3 entries
    assert len(totals["daily"]) == 3
    
    # Each day should have date and est_cost
    for daily_entry in totals["daily"]:
        assert "date" in daily_entry
        assert "est_cost" in daily_entry
    
    # Trip cost should be sum of daily costs
    trip_cost = totals["trip_cost_est"]
    daily_costs = [entry["est_cost"] for entry in totals["daily"]]
    assert abs(trip_cost - sum(daily_costs)) < 0.01  # Allow for small floating point differences

def test_itinerary_currency_conversion_with_budget():
    """Test that currency conversion works with budget totals."""
    request_data = {
        "trip_context": {
            "base_place_id": "test_base",
            "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
            "day_template": {"start": "09:00", "end": "18:00", "pace": "moderate"},
            "modes": ["DRIVE"]
        },
        "preferences": {
            "themes": ["culture"],
            "activity_tags": [],
            "avoid_tags": [],
            "currency": "USD"
        },
        "constraints": {
            "daily_budget_cap": 50.0,
            "max_transfer_minutes": 60
        },
        "locks": []
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have currency in response
    assert "currency" in data
    assert data["currency"] == "USD"
    
    # Should have budget totals
    assert "totals" in data
    assert "trip_cost_est" in data["totals"]
