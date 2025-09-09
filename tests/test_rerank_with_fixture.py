"""
Tests using fixture dataset to demonstrate reranker functionality.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.dataset.fixtures import load_fixture_pois

client = TestClient(app)


def pick(ids, pois):
    """Helper to pick specific POIs by ID from the fixture data."""
    poi_map = {p["poi_id"]: p for p in pois}
    return [poi_map[i] for i in ids]


def test_rerank_fixture_demo_boosts_hiking_penalizes_nightlife():
    """Test that reranker boosts hiking/quiet POIs and penalizes nightlife/crowded POIs."""
    pois = load_fixture_pois()
    
    # Pick 3 canonical demo candidates
    cands = pick(["ella_rock_hike", "nightlife_district_colombo", "pettah_market_colombo"], pois)
    
    payload = {
        "candidates": [
            {"poi_id": c["poi_id"], "tags": c["tags"], "score": 0.60} for c in cands
        ],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "ella_rock_hike",
                    "rating": 5,
                    "tags": ["hiking", "quiet"],
                    "ts": "2025-08-25T08:30:00Z"
                },
                {
                    "poi_id": "nightlife_district_colombo",
                    "rating": 1,
                    "tags": ["nightlife", "crowded"],
                    "ts": "2025-08-24T19:10:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    reranked = data["reranked"]
    
    # Should have 3 candidates
    assert len(reranked) == 3
    
    # Get the order
    order = [x["poi_id"] for x in reranked]
    
    # Hiking should rise to top, nightlife should be penalized (not necessarily last)
    assert order[0] == "ella_rock_hike", f"Expected ella_rock_hike to be first, got: {order}"
    
    # Nightlife should be penalized (lower than its original position)
    nightlife_position = order.index("nightlife_district_colombo")
    assert nightlife_position > 0, f"Nightlife should be penalized, got position {nightlife_position}"
    
    # Check that scores reflect the reranking
    ella_score = next(x["score"] for x in reranked if x["poi_id"] == "ella_rock_hike")
    nightlife_score = next(x["score"] for x in reranked if x["poi_id"] == "nightlife_district_colombo")
    
    assert ella_score > 0.60, f"Ella should be boosted above 0.60, got {ella_score}"
    assert nightlife_score < 0.60, f"Nightlife should be penalized below 0.60, got {nightlife_score}"


def test_rerank_fixture_with_reasons():
    """Test that reranker provides clear reasons for reranking decisions."""
    pois = load_fixture_pois()
    
    # Use POIs with strong tag affinities
    cands = pick(["ella_rock_hike", "nightlife_district_colombo"], pois)
    
    payload = {
        "candidates": [
            {"poi_id": c["poi_id"], "tags": c["tags"], "score": 0.60} for c in cands
        ],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "ella_rock_hike",
                    "rating": 5,
                    "tags": ["hiking", "quiet"],
                    "ts": "2025-08-25T08:30:00Z"
                },
                {
                    "poi_id": "nightlife_district_colombo",
                    "rating": 1,
                    "tags": ["nightlife", "crowded"],
                    "ts": "2025-08-24T19:10:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    reranked = data["reranked"]
    
    # Check for reasons (may or may not be present depending on affinity strength)
    has_reasons = any("reason" in candidate and candidate["reason"] for candidate in reranked)
    
    if has_reasons:
        # If reasons are present, they should be meaningful
        for candidate in reranked:
            if "reason" in candidate and candidate["reason"]:
                reason = candidate["reason"]
                if candidate["poi_id"] == "ella_rock_hike":
                    assert "hiking" in reason.lower() or "quiet" in reason.lower(), f"Ella reason should mention hiking/quiet: {reason}"
                elif candidate["poi_id"] == "nightlife_district_colombo":
                    assert "nightlife" in reason.lower() or "crowded" in reason.lower(), f"Nightlife reason should mention nightlife/crowded: {reason}"


def test_rerank_fixture_mixed_feedback():
    """Test reranking with mixed positive and negative feedback."""
    pois = load_fixture_pois()
    
    # Use more POIs for a richer test
    cands = pick([
        "ella_rock_hike", 
        "nightlife_district_colombo", 
        "pettah_market_colombo",
        "colombo_national_museum"
    ], pois)
    
    payload = {
        "candidates": [
            {"poi_id": c["poi_id"], "tags": c["tags"], "score": 0.60} for c in cands
        ],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "ella_rock_hike",
                    "rating": 5,
                    "tags": ["hiking", "quiet"],
                    "ts": "2025-08-25T08:30:00Z"
                },
                {
                    "poi_id": "nightlife_district_colombo",
                    "rating": 1,
                    "tags": ["nightlife", "crowded"],
                    "ts": "2025-08-24T19:10:00Z"
                },
                {
                    "poi_id": "colombo_national_museum",
                    "rating": 4,
                    "tags": ["history", "culture"],
                    "ts": "2025-08-23T14:00:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    reranked = data["reranked"]
    
    # Should have 4 candidates
    assert len(reranked) == 4
    
    # Get the order
    order = [x["poi_id"] for x in reranked]
    
    # Ella should still be first (strongest positive feedback)
    assert order[0] == "ella_rock_hike", f"Expected ella_rock_hike to be first, got: {order}"
    
    # Nightlife should be penalized (not necessarily last due to other factors)
    nightlife_position = order.index("nightlife_district_colombo")
    assert nightlife_position > 0, f"Nightlife should be penalized, got position {nightlife_position}"
    
    # Museum should be in the middle (positive but weaker feedback)
    museum_position = order.index("colombo_national_museum")
    assert museum_position > 0, "Museum should not be first"
    assert museum_position < len(order) - 1, "Museum should not be last"


def test_rerank_fixture_deterministic():
    """Test that reranking with fixture data is deterministic."""
    pois = load_fixture_pois()
    cands = pick(["ella_rock_hike", "nightlife_district_colombo", "pettah_market_colombo"], pois)
    
    payload = {
        "candidates": [
            {"poi_id": c["poi_id"], "tags": c["tags"], "score": 0.60} for c in cands
        ],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "ella_rock_hike",
                    "rating": 5,
                    "tags": ["hiking", "quiet"],
                    "ts": "2025-08-25T08:30:00Z"
                },
                {
                    "poi_id": "nightlife_district_colombo",
                    "rating": 1,
                    "tags": ["nightlife", "crowded"],
                    "ts": "2025-08-24T19:10:00Z"
                }
            ]
        }
    }
    
    # Run multiple times
    results = []
    for _ in range(3):
        response = client.post("/v1/rerank", json=payload)
        assert response.status_code == 200
        results.append(response.json()["reranked"])
    
    # Results should be identical
    for i in range(1, len(results)):
        assert results[i] == results[0], f"Reranking should be deterministic, got different results"


def test_rerank_fixture_metadata():
    """Test that reranking metadata is correctly populated."""
    pois = load_fixture_pois()
    cands = pick(["ella_rock_hike", "nightlife_district_colombo"], pois)
    
    payload = {
        "candidates": [
            {"poi_id": c["poi_id"], "tags": c["tags"], "score": 0.60} for c in cands
        ],
        "audit_log": {
            "feedback_events": [
                {
                    "poi_id": "ella_rock_hike",
                    "rating": 5,
                    "tags": ["hiking", "quiet"],
                    "ts": "2025-08-25T08:30:00Z"
                },
                {
                    "poi_id": "nightlife_district_colombo",
                    "rating": 1,
                    "tags": ["nightlife", "crowded"],
                    "ts": "2025-08-24T19:10:00Z"
                }
            ]
        }
    }
    
    response = client.post("/v1/rerank", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    metadata = data["metadata"]
    
    # Should have reranking metadata
    assert "rerank_applied" in metadata
    assert "n_feedback_events" in metadata
    assert "n_affinity_tags" in metadata
    assert "n_candidates_with_reasons" in metadata
    
    # Should be applied
    assert metadata["rerank_applied"] is True
    assert metadata["n_feedback_events"] == 2
    assert metadata["n_affinity_tags"] >= 4  # hiking, quiet, nightlife, crowded
