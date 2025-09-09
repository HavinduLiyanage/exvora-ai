"""
Tests for ML preference scoring functionality.
"""

import pytest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from app.engine.ml_pref import PreferenceScorer, get_preference_scorer
from app.engine.features import vectorize_candidate, get_user_preference_features


def test_fallback_returns_valid_range():
    """Test that fallback mode returns scores in [0,1] range."""
    scorer = PreferenceScorer()
    
    # Test with various candidates
    candidates = [
        {"tags": ["culture", "history"], "price_band": "low", "estimated_cost": 10},
        {"tags": ["nature", "quiet"], "price_band": "free", "estimated_cost": 0},
        {"tags": ["food", "local"], "price_band": "medium", "estimated_cost": 25},
        {"tags": [], "price_band": "high", "estimated_cost": 100},
    ]
    
    context = {"day_template": {"pace": "moderate"}}
    preferences = {"themes": ["culture"], "activity_tags": ["history"], "avoid_tags": []}
    
    for candidate in candidates:
        score = scorer.predict_pref_fit(candidate, context, preferences)
        assert 0.0 <= score <= 1.0, f"Score {score} not in [0,1] range for candidate {candidate}"


def test_fallback_prefers_matching_tags():
    """Test that fallback mode prefers candidates with matching tags."""
    scorer = PreferenceScorer()
    
    context = {"day_template": {"pace": "moderate"}}
    preferences = {"themes": ["culture"], "activity_tags": ["history"], "avoid_tags": []}
    
    # Candidate with matching tags should score higher
    matching_candidate = {"tags": ["culture", "history"], "price_band": "low", "estimated_cost": 10}
    non_matching_candidate = {"tags": ["nature", "sports"], "price_band": "low", "estimated_cost": 10}
    
    matching_score = scorer.predict_pref_fit(matching_candidate, context, preferences)
    non_matching_score = scorer.predict_pref_fit(non_matching_candidate, context, preferences)
    
    assert matching_score > non_matching_score, "Matching candidate should score higher"


def test_fallback_penalizes_avoid_tags():
    """Test that fallback mode penalizes candidates with avoid tags."""
    scorer = PreferenceScorer()
    
    context = {"day_template": {"pace": "moderate"}}
    preferences = {"themes": ["culture"], "activity_tags": ["history"], "avoid_tags": ["crowded"]}
    
    # Candidate with avoid tags should score lower
    avoid_candidate = {"tags": ["culture", "crowded"], "price_band": "low", "estimated_cost": 10}
    normal_candidate = {"tags": ["culture", "history"], "price_band": "low", "estimated_cost": 10}
    
    avoid_score = scorer.predict_pref_fit(avoid_candidate, context, preferences)
    normal_score = scorer.predict_pref_fit(normal_candidate, context, preferences)
    
    # In fallback mode, avoid tags should score 0; in model mode, they might score lower
    if scorer.fallback_mode:
        assert avoid_score == 0.0, "Candidate with avoid tags should score 0 in fallback mode"
    else:
        assert avoid_score < normal_score, "Candidate with avoid tags should score lower than normal candidate"
    
    assert normal_score > 0.0, "Normal candidate should score > 0"


def test_fallback_with_no_preferences():
    """Test that fallback mode handles empty preferences gracefully."""
    scorer = PreferenceScorer()
    
    context = {"day_template": {"pace": "moderate"}}
    preferences = {"themes": [], "activity_tags": [], "avoid_tags": []}
    
    candidate = {"tags": ["culture", "history"], "price_band": "low", "estimated_cost": 10}
    score = scorer.predict_pref_fit(candidate, context, preferences)
    
    assert 0.0 <= score <= 1.0, "Should return valid score even with no preferences"


def test_version_returns_model_version():
    """Test that version returns model version when model is loaded."""
    scorer = PreferenceScorer()
    version = scorer.version()
    
    # Should return either model version or fallback version
    assert version in ["pref_lr_v1", "fallback_rule_v0"], f"Unexpected version: {version}"


def test_get_preference_scorer_singleton():
    """Test that get_preference_scorer returns singleton instance."""
    scorer1 = get_preference_scorer()
    scorer2 = get_preference_scorer()
    
    assert scorer1 is scorer2, "Should return same instance"


def test_vectorize_candidate():
    """Test feature vectorization for candidates."""
    candidate = {
        "tags": ["culture", "history"],
        "price_band": "low",
        "estimated_cost": 15.0,
        "duration_minutes": 90
    }
    
    context = {"day_template": {"pace": "moderate"}}
    preferences = {"themes": ["culture"], "activity_tags": ["history"], "avoid_tags": []}
    
    tag_vocab = ["culture", "history", "nature", "food"]
    feature_names = tag_vocab + ["price_free", "price_low", "price_medium", "price_high", 
                                 "estimated_cost", "duration_minutes", "opening_align", "distance_km"]
    
    features = vectorize_candidate(candidate, context, preferences, tag_vocab, feature_names)
    
    # Should have correct length
    assert len(features) == len(feature_names), f"Expected {len(feature_names)} features, got {len(features)}"
    
    # Should have correct tag features
    assert features[0] == 1.0  # culture
    assert features[1] == 1.0  # history
    assert features[2] == 0.0  # nature
    assert features[3] == 0.0  # food
    
    # Should have correct price band features
    assert features[4] == 0.0  # price_free
    assert features[5] == 1.0  # price_low
    assert features[6] == 0.0  # price_medium
    assert features[7] == 0.0  # price_high
    
    # Should have correct numeric features
    assert features[8] == 15.0  # estimated_cost
    assert features[9] == 90.0  # duration_minutes
    assert 0.0 <= features[10] <= 1.0  # opening_align
    assert features[11] >= 0.0  # distance_km


def test_get_user_preference_features():
    """Test extraction of user preference features."""
    preferences = {
        "themes": ["culture", "history"],
        "activity_tags": ["art", "music"],
        "avoid_tags": ["crowded", "expensive"]
    }
    
    features = get_user_preference_features(preferences)
    
    assert features["themes"] == {"culture", "history"}
    assert features["activity_tags"] == {"art", "music"}
    assert features["avoid_tags"] == {"crowded", "expensive"}
    assert features["all_preferred_tags"] == {"culture", "history", "art", "music"}


@patch('os.path.exists')
def test_model_loading_with_artifacts(mock_exists):
    """Test model loading when artifacts are present."""
    mock_exists.return_value = True
    
    # Mock the model and metadata
    mock_model = MagicMock()
    mock_model.predict_proba.return_value = [[0.3, 0.7]]  # 70% probability of class 1
    
    mock_metadata = {
        "version": "pref_lr_v1",
        "tag_vocab": ["culture", "history"],
        "feature_names": ["culture", "history", "price_low", "estimated_cost"]
    }
    
    with patch('joblib.load', return_value=mock_model), \
         patch('builtins.open', create=True) as mock_open, \
         patch('json.load', return_value=mock_metadata):
        
        scorer = PreferenceScorer()
        
        # Should not be in fallback mode
        assert not scorer.fallback_mode
        assert scorer.model is not None
        assert scorer.metadata == mock_metadata
        
        # Test prediction
        candidate = {"tags": ["culture"], "price_band": "low", "estimated_cost": 10}
        context = {"day_template": {"pace": "moderate"}}
        preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
        
        score = scorer.predict_pref_fit(candidate, context, preferences)
        assert 0.0 <= score <= 1.0  # Should return valid score
        
        # Test version
        assert scorer.version() == "pref_lr_v1"


def test_model_loading_without_artifacts():
    """Test model loading when artifacts are missing."""
    with patch('os.path.exists', return_value=False):
        scorer = PreferenceScorer()
        
        # Should be in fallback mode
        assert scorer.fallback_mode
        assert scorer.model is None
        assert scorer.metadata is None
        assert scorer.version() == "fallback_rule_v0"


def test_model_prediction_error_fallback():
    """Test that model prediction errors fall back to heuristic."""
    mock_model = MagicMock()
    mock_model.predict_proba.side_effect = Exception("Model error")
    
    scorer = PreferenceScorer()
    scorer.model = mock_model
    scorer.fallback_mode = False
    scorer.tag_vocab = ["culture", "history"]
    scorer.feature_names = ["culture", "history", "price_low", "estimated_cost"]
    
    candidate = {"tags": ["culture"], "price_band": "low", "estimated_cost": 10}
    context = {"day_template": {"pace": "moderate"}}
    preferences = {"themes": ["culture"], "activity_tags": [], "avoid_tags": []}
    
    # Should fall back to heuristic on error
    score = scorer.predict_pref_fit(candidate, context, preferences)
    assert 0.0 <= score <= 1.0
