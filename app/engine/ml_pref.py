"""
ML-based preference scoring with graceful fallback.
Loads trained model artifacts and provides preference fit scores.
"""

import os
import json
import joblib
import numpy as np
from typing import Dict, Any, List, Optional
from .features import vectorize_candidate, get_user_preference_features


class PreferenceScorer:
    """
    Preference scorer that uses ML model when available, falls back to heuristic rules.
    """
    
    def __init__(self):
        self.model = None
        self.metadata = None
        self.tag_vocab = None
        self.feature_names = None
        self.fallback_mode = True
        
        self._load_artifacts()
    
    def _load_artifacts(self):
        """Load model artifacts if available."""
        model_path = "app/models/pref_lr_v1.joblib"
        metadata_path = "app/models/pref_lr_v1.metadata.json"
        
        try:
            if os.path.exists(model_path) and os.path.exists(metadata_path):
                self.model = joblib.load(model_path)
                
                with open(metadata_path, "r") as f:
                    self.metadata = json.load(f)
                
                self.tag_vocab = self.metadata.get("tag_vocab", [])
                self.feature_names = self.metadata.get("feature_names", [])
                self.fallback_mode = False
                
                print(f"Loaded preference model: {self.metadata.get('version', 'unknown')}")
            else:
                print("Preference model artifacts not found, using fallback mode")
                
        except Exception as e:
            print(f"Error loading preference model: {e}, using fallback mode")
            self.fallback_mode = True
    
    def predict_pref_fit(self, candidate: Dict[str, Any], context: Dict[str, Any], 
                        preferences: Dict[str, Any]) -> float:
        """
        Predict preference fit score for a candidate POI.
        
        Args:
            candidate: POI candidate data
            context: Trip context (day_template, etc.)
            preferences: User preferences (themes, activity_tags, avoid_tags)
            
        Returns:
            Preference fit score between 0 and 1
        """
        if not self.fallback_mode and self.model is not None:
            return self._predict_with_model(candidate, context, preferences)
        else:
            return self._predict_with_fallback(candidate, context, preferences)
    
    def _predict_with_model(self, candidate: Dict[str, Any], context: Dict[str, Any], 
                           preferences: Dict[str, Any]) -> float:
        """Predict using the trained ML model."""
        try:
            # Build feature vector
            features = vectorize_candidate(
                candidate, context, preferences, 
                self.tag_vocab, self.feature_names
            )
            
            # Predict probability
            features_array = np.array(features).reshape(1, -1)
            proba = self.model.predict_proba(features_array)[0, 1]  # Probability of class 1
            
            # Clamp to [0, 1] range
            return max(0.0, min(1.0, proba))
            
        except Exception as e:
            print(f"Error in ML prediction: {e}, falling back to heuristic")
            return self._predict_with_fallback(candidate, context, preferences)
    
    def _predict_with_fallback(self, candidate: Dict[str, Any], context: Dict[str, Any], 
                              preferences: Dict[str, Any]) -> float:
        """
        Fallback heuristic based on tag similarity.
        Uses Jaccard similarity between candidate tags and user preferences.
        """
        # Get user preference features
        pref_features = get_user_preference_features(preferences)
        user_tags = pref_features["all_preferred_tags"]
        avoid_tags = pref_features["avoid_tags"]
        
        # Get candidate tags
        candidate_tags = set(candidate.get("tags", []))
        
        # Check for avoid tags (immediate disqualification)
        if avoid_tags and candidate_tags & avoid_tags:
            return 0.0
        
        # If no user preferences, return neutral score
        if not user_tags:
            return 0.5
        
        # Compute Jaccard similarity
        if not candidate_tags:
            return 0.3  # Slight penalty for POIs with no tags
        
        intersection = len(user_tags & candidate_tags)
        union = len(user_tags | candidate_tags)
        
        if union == 0:
            return 0.5
        
        jaccard_similarity = intersection / union
        
        # Apply some additional heuristics
        score = jaccard_similarity
        
        # Boost for certain tag combinations
        if "local" in candidate_tags and "food" in candidate_tags:
            score += 0.1
        if "culture" in candidate_tags and "history" in candidate_tags:
            score += 0.1
        if "nature" in candidate_tags and "quiet" in candidate_tags:
            score += 0.1
        
        # Penalty for certain combinations
        if "crowded" in candidate_tags and "quiet" in user_tags:
            score -= 0.2
        if "luxury" in candidate_tags and "budget" in user_tags:
            score -= 0.2
        
        # Clamp to [0, 1] range
        return max(0.0, min(1.0, score))
    
    def version(self) -> str:
        """Return model version or fallback version."""
        if self.metadata:
            return self.metadata.get("version", "unknown")
        else:
            return "fallback_rule_v0"
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return model metadata."""
        return self.metadata or {}


# Global instance for reuse
_preference_scorer = None

def get_preference_scorer() -> PreferenceScorer:
    """Get the global preference scorer instance."""
    global _preference_scorer
    if _preference_scorer is None:
        _preference_scorer = PreferenceScorer()
    return _preference_scorer
