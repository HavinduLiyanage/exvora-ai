"""
Integration tests for rank module with preference scoring.
"""

import pytest
from app.engine.rank import rank, _calculate_pref_fit
from app.engine.ml_pref import get_preference_scorer


def test_rank_includes_pref_model_version():
    """Test that rank function includes pref_model_version in metadata."""
    candidates = [
        {"place_id": "test1", "tags": ["culture"], "price_band": "low", "estimated_cost": 10},
        {"place_id": "test2", "tags": ["nature"], "price_band": "medium", "estimated_cost": 25},
    ]
    
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    context = {"day_template": {"pace": "moderate"}}
    
    ranked, metrics = rank(candidates, None, preferences, context=context)
    
    # Should include pref_model_version in metrics
    assert "pref_model_version" in metrics
    assert metrics["pref_model_version"] is not None
    assert isinstance(metrics["pref_model_version"], str)


def test_rank_returns_valid_scores():
    """Test that rank function returns valid scores."""
    candidates = [
        {"place_id": "test1", "tags": ["culture"], "price_band": "low", "estimated_cost": 10},
        {"place_id": "test2", "tags": ["nature"], "price_band": "medium", "estimated_cost": 25},
    ]
    
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    context = {"day_template": {"pace": "moderate"}}
    
    ranked, metrics = rank(candidates, None, preferences, context=context)
    
    # Should return ranked candidates
    assert len(ranked) == 2
    assert all("place_id" in cand for cand in ranked)
    
    # Should have valid metrics
    assert "avg_pref_fit" in metrics
    assert "avg_time_fit" in metrics
    assert "avg_budget_fit" in metrics
    assert "pref_model_version" in metrics
    
    # All averages should be in [0,1] range
    assert 0.0 <= metrics["avg_pref_fit"] <= 1.0
    assert 0.0 <= metrics["avg_time_fit"] <= 1.0
    assert 0.0 <= metrics["avg_budget_fit"] <= 1.0


def test_calculate_pref_fit_with_context():
    """Test that _calculate_pref_fit works with context parameter."""
    candidate = {"tags": ["culture"], "price_band": "low", "estimated_cost": 10}
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    context = {"day_template": {"pace": "moderate"}}
    
    score = _calculate_pref_fit(candidate, preferences, context)
    
    assert 0.0 <= score <= 1.0
    assert isinstance(score, float)


def test_calculate_pref_fit_without_context():
    """Test that _calculate_pref_fit works without context parameter."""
    candidate = {"tags": ["culture"], "price_band": "low", "estimated_cost": 10}
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    
    score = _calculate_pref_fit(candidate, preferences)
    
    assert 0.0 <= score <= 1.0
    assert isinstance(score, float)


def test_rank_deterministic():
    """Test that rank function produces deterministic results."""
    candidates = [
        {"place_id": "test1", "tags": ["culture"], "price_band": "low", "estimated_cost": 10},
        {"place_id": "test2", "tags": ["nature"], "price_band": "medium", "estimated_cost": 25},
    ]
    
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    context = {"day_template": {"pace": "moderate"}}
    
    # Run ranking multiple times
    results = []
    for _ in range(3):
        ranked, metrics = rank(candidates, None, preferences, context=context)
        results.append((ranked, metrics))
    
    # Results should be identical
    for i in range(1, len(results)):
        assert results[i][0] == results[0][0], "Ranked candidates should be identical"
        assert results[i][1]["pref_model_version"] == results[0][1]["pref_model_version"], "Model version should be identical"


def test_rank_with_different_contexts():
    """Test that rank function responds to different contexts."""
    candidates = [
        {"place_id": "test1", "tags": ["culture"], "price_band": "low", "estimated_cost": 10, "duration_minutes": 60},
        {"place_id": "test2", "tags": ["nature"], "price_band": "medium", "estimated_cost": 25, "duration_minutes": 120},
    ]
    
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    
    # Test with different paces
    light_context = {"day_template": {"pace": "light"}}
    intense_context = {"day_template": {"pace": "intense"}}
    
    ranked_light, metrics_light = rank(candidates, None, preferences, context=light_context)
    ranked_intense, metrics_intense = rank(candidates, None, preferences, context=intense_context)
    
    # Both should return valid results
    assert len(ranked_light) == 2
    assert len(ranked_intense) == 2
    
    # Model versions should be the same
    assert metrics_light["pref_model_version"] == metrics_intense["pref_model_version"]


def test_rank_with_budget_constraint():
    """Test that rank function works with budget constraints."""
    candidates = [
        {"place_id": "test1", "tags": ["culture"], "price_band": "low", "estimated_cost": 10},
        {"place_id": "test2", "tags": ["nature"], "price_band": "high", "estimated_cost": 100},
    ]
    
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    context = {"day_template": {"pace": "moderate"}}
    
    # Test with budget cap
    ranked, metrics = rank(candidates, 50.0, preferences, context=context)
    
    assert len(ranked) == 2
    assert "avg_budget_fit" in metrics
    assert 0.0 <= metrics["avg_budget_fit"] <= 1.0


def test_rank_with_affinities():
    """Test that rank function works with affinities."""
    candidates = [
        {"place_id": "test1", "tags": ["culture"], "price_band": "low", "estimated_cost": 10},
        {"place_id": "test2", "tags": ["nature"], "price_band": "medium", "estimated_cost": 25},
    ]
    
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    context = {"day_template": {"pace": "moderate"}}
    affinities = {"culture": 0.5, "nature": -0.3}
    
    ranked, metrics = rank(candidates, None, preferences, context=context, affinities=affinities)
    
    assert len(ranked) == 2
    assert "pref_model_version" in metrics
