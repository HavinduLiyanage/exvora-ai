"""
API tests for rerank endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_rerank_endpoint_success():
    """Test successful rerank endpoint call."""
    request_data = {
        "candidates": [
            {
                "poi_id": "ella_hike",
                "tags": ["hiking", "quiet"],
                "score": 0.62
            },
            {
                "poi_id": "nightlife_district",
                "tags": ["nightlife"],
                "score": 0.58
            },
            {
                "poi_id": "pettah_market",
                "tags": ["street_food"],
                "score": 0.55
            }
        ],
        "preferences": {
            "themes": ["nature"],
            "avoid_tags": ["crowded"]
        },
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "ella_hike",
                    "rating": 5,
                    "tags": ["hiking", "quiet"],
                    "ts": "2025-08-25T08:30:00Z"
                },
                {
                    "poi_id": "nightlife_district",
                    "rating": 1,
                    "tags": ["nightlife", "crowded"],
                    "ts": "2025-08-24T19:10:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=request_data)
    
    # Should return 200
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have reranked candidates
    assert "reranked" in data
    assert "metadata" in data
    
    reranked = data["reranked"]
    assert len(reranked) == 3
    
    # Should have poi_id and score for each
    for candidate in reranked:
        assert "poi_id" in candidate
        assert "score" in candidate
        assert isinstance(candidate["score"], (int, float))
    
    # Should be sorted by score (descending)
    scores = [c["score"] for c in reranked]
    assert scores == sorted(scores, reverse=True)
    
    # Metadata should indicate reranking was applied
    metadata = data["metadata"]
    assert metadata["rerank_applied"] is True
    assert metadata["n_feedback_events"] == 2


def test_rerank_endpoint_expected_ordering():
    """Test that rerank endpoint produces expected ordering."""
    request_data = {
        "candidates": [
            {
                "poi_id": "ella_hike",
                "tags": ["hiking", "quiet"],
                "score": 0.62
            },
            {
                "poi_id": "nightlife_district",
                "tags": ["nightlife"],
                "score": 0.58
            }
        ],
        "preferences": {},
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "ella_hike",
                    "rating": 5,
                    "tags": ["hiking", "quiet"],
                    "ts": "2025-08-25T08:30:00Z"
                },
                {
                    "poi_id": "nightlife_district",
                    "rating": 1,
                    "tags": ["nightlife", "crowded"],
                    "ts": "2025-08-24T19:10:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    
    reranked = data["reranked"]
    
    # Ella hike should be first (boosted by positive rating)
    assert reranked[0]["poi_id"] == "ella_hike"
    assert reranked[0]["score"] > 0.62  # Should be boosted
    
    # Nightlife should be second (penalized by negative rating)
    assert reranked[1]["poi_id"] == "nightlife_district"
    assert reranked[1]["score"] < 0.58  # Should be penalized


def test_rerank_endpoint_with_reasons():
    """Test that rerank endpoint includes reasons when appropriate."""
    request_data = {
        "candidates": [
            {
                "poi_id": "hiking_trail",
                "tags": ["hiking", "nature"],
                "score": 0.6
            }
        ],
        "preferences": {},
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "hiking_trail",
                    "rating": 5,
                    "tags": ["hiking", "nature"],
                    "ts": "2025-08-25T08:30:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    
    reranked = data["reranked"]
    assert len(reranked) == 1
    
    # May or may not have reason depending on threshold
    candidate = reranked[0]
    if "reason" in candidate and candidate["reason"] is not None:
        assert "hiking" in candidate["reason"] or "nature" in candidate["reason"]


def test_rerank_endpoint_no_audit_log():
    """Test rerank endpoint with no audit log."""
    request_data = {
        "candidates": [
            {
                "poi_id": "test_poi",
                "tags": ["test"],
                "score": 0.5
            }
        ],
        "preferences": {},
        "audit_log": {
            "feedback_events": []
        }
    }
    
    response = client.post("/v1/rerank", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should return original candidates unchanged
    reranked = data["reranked"]
    assert len(reranked) == 1
    assert reranked[0]["poi_id"] == "test_poi"
    assert reranked[0]["score"] == 0.5
    
    # Metadata should indicate no reranking
    metadata = data["metadata"]
    assert metadata["rerank_applied"] is False


def test_rerank_endpoint_invalid_rating():
    """Test rerank endpoint with invalid rating."""
    request_data = {
        "candidates": [
            {
                "poi_id": "test_poi",
                "tags": ["test"],
                "score": 0.5
            }
        ],
        "preferences": {},
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "test_poi",
                    "rating": 6,  # Invalid rating
                    "tags": ["test"],
                    "ts": "2025-08-25T08:30:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=request_data)
    
    # Should return 422 (validation error)
    assert response.status_code == 422


def test_rerank_endpoint_missing_required_fields():
    """Test rerank endpoint with missing required fields."""
    request_data = {
        "candidates": [
            {
                "poi_id": "test_poi",
                "score": 0.5
                # Missing tags
            }
        ],
        "preferences": {},
        "audit_log": {
            "feedback_events": []
        }
    }
    
    response = client.post("/v1/rerank", json=request_data)
    
    # Should still work (tags is optional with default)
    assert response.status_code == 200


def test_rerank_health_endpoint():
    """Test rerank health endpoint."""
    response = client.get("/v1/rerank/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ok"
    assert data["endpoint"] == "rerank"
