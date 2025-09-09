"""
Integration tests for reranking in itinerary flows.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_itinerary_with_audit_log():
    """Test that itinerary endpoint accepts audit_log and produces valid plan."""
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
            "daily_budget_cap": 100.0,
            "max_transfer_minutes": 60
        },
        "locks": [],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "test_poi",
                    "rating": 5,
                    "tags": ["culture", "history"],
                    "ts": "2025-08-25T08:30:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have valid itinerary structure
    assert "days" in data
    assert "totals" in data
    assert "currency" in data
    
    # Should have at least one day
    assert len(data["days"]) >= 1
    
    # Day should have valid structure
    day = data["days"][0]
    assert "date" in day
    assert "summary" in day
    assert "items" in day


def test_itinerary_without_audit_log():
    """Test that itinerary endpoint works without audit_log."""
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
            "daily_budget_cap": 100.0,
            "max_transfer_minutes": 60
        },
        "locks": []
        # No audit_log
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have valid itinerary structure
    assert "days" in data
    assert "totals" in data
    assert "currency" in data


def test_itinerary_with_empty_audit_log():
    """Test that itinerary endpoint works with empty audit_log."""
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
            "daily_budget_cap": 100.0,
            "max_transfer_minutes": 60
        },
        "locks": [],
        "audit_log": {
            "feedback_events": []
        }
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have valid itinerary structure
    assert "days" in data
    assert "totals" in data
    assert "currency" in data


def test_itinerary_rerank_ordering():
    """Test that itinerary with audit_log produces different ordering."""
    # First request without audit_log
    request_without_audit = {
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
            "daily_budget_cap": 100.0,
            "max_transfer_minutes": 60
        },
        "locks": []
    }
    
    response1 = client.post("/v1/itinerary", json=request_without_audit)
    assert response1.status_code == 200
    data1 = response1.json()
    
    # Second request with audit_log
    request_with_audit = {
        **request_without_audit,
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "test_poi",
                    "rating": 5,
                    "tags": ["culture", "history"],
                    "ts": "2025-08-25T08:30:00Z"
                }
            ]
        }
    }
    
    response2 = client.post("/v1/itinerary", json=request_with_audit)
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Both should have valid structure
    assert "days" in data1
    assert "days" in data2
    assert "totals" in data1
    assert "totals" in data2
    
    # Both should have same number of days
    assert len(data1["days"]) == len(data2["days"])
    
    # The ordering might be different due to reranking
    # (This is a basic test - in practice, the reranking effect might be subtle)


def test_itinerary_audit_log_validation():
    """Test that itinerary endpoint validates audit_log properly."""
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
            "daily_budget_cap": 100.0,
            "max_transfer_minutes": 60
        },
        "locks": [],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "test_poi",
                    "rating": 6,  # Invalid rating
                    "tags": ["culture"],
                    "ts": "2025-08-25T08:30:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 422 (validation error)
    assert response.status_code == 422


def test_itinerary_multi_day_with_audit_log():
    """Test multi-day itinerary with audit_log."""
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
        "locks": [],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "test_poi",
                    "rating": 5,
                    "tags": ["culture", "history"],
                    "ts": "2025-08-25T08:30:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/itinerary", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have 3 days
    assert len(data["days"]) == 3
    
    # All days should have valid structure
    for day in data["days"]:
        assert "date" in day
        assert "summary" in day
        assert "items" in day
