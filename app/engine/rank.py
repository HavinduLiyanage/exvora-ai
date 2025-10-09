from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import logging
from app.config import get_settings
from app.engine.reranker import affinity_bonus_for_poi
from app.engine.ml_pref import get_preference_scorer

logger = logging.getLogger(__name__)
settings = get_settings()


def _calculate_pref_fit(poi: Dict[str, Any], prefs: Dict[str, Any], context: Dict[str, Any] = None) -> float:
    """Calculate preference fit score using ML model or fallback heuristic."""
    if context is None:
        context = {}
    
    # Use the global preference scorer
    scorer = get_preference_scorer()
    return scorer.predict_pref_fit(poi, context, prefs)


def _calculate_time_fit(poi: Dict[str, Any], day_start: str, day_end: str) -> float:
    """Calculate time fit score based on duration and open windows."""
    duration = int(poi.get("duration_minutes") or 60)
    
    # Convert day window to minutes
    start_min = int(day_start.split(":")[0]) * 60 + int(day_start.split(":")[1])
    end_min = int(day_end.split(":")[0]) * 60 + int(day_end.split(":")[1])
    day_length = end_min - start_min
    
    # Prefer activities that fit well within the day
    if duration > day_length:
        return 0.0  # Can't fit in day
    
    # Prefer activities that are 60-180 minutes (good for scheduling)
    if 60 <= duration <= 180:
        time_fit = 1.0
    elif duration < 60:
        time_fit = 0.7  # Too short
    else:
        time_fit = 0.8  # A bit long but acceptable
    
    return time_fit


def _calculate_budget_fit(poi: Dict[str, Any], daily_cap: float | None) -> float:
    """Calculate budget fit score."""
    if daily_cap is None:
        return 0.5  # Neutral if no budget constraint
    
    cost = float(poi.get("estimated_cost") or 0)
    
    if cost > daily_cap:
        return 0.0  # Can't afford
    
    # Prefer items that use 20-80% of budget (good value)
    budget_ratio = cost / daily_cap
    
    if 0.2 <= budget_ratio <= 0.8:
        return 1.0  # Optimal range
    elif budget_ratio < 0.2:
        return 0.8  # Good value
    else:
        return 0.6  # Uses most of budget


def _calculate_diversity(poi: Dict[str, Any], scheduled_items: List[Dict[str, Any]]) -> float:
    """Calculate diversity score to avoid repetition."""
    if not scheduled_items:
        return 1.0  # First item gets full diversity score
    
    poi_themes = set(map(str.lower, poi.get("themes", [])))
    poi_region = poi.get("region")
    
    # Check for theme repetition
    theme_penalty = 0.0
    for item in scheduled_items[-3:]:  # Check last 3 items
        item_themes = set(map(str.lower, item.get("themes", [])))
        if poi_themes & item_themes:
            theme_penalty += 0.3
    
    # Check for region repetition
    region_penalty = 0.0
    for item in scheduled_items[-2:]:  # Check last 2 items
        if item.get("region") == poi_region:
            region_penalty += 0.2
    
    diversity_score = max(0.0, 1.0 - theme_penalty - region_penalty)
    return diversity_score


def _calculate_health_fit(poi: Dict[str, Any], pace: str) -> float:
    """Calculate health fit score based on pace preference and activity intensity."""
    duration = int(poi.get("duration_minutes") or 60)
    tags = [t.lower() for t in (poi.get("tags", []) + poi.get("themes", []))]
    
    # Pace-based duration preferences
    if pace == "light":
        # Penalize strenuous activities
        if any(strenuous in tags for strenuous in ["hiking", "trekking", "climbing", "long walk"]):
            return 0.3
        # Prefer shorter activities for light pace
        if duration <= 90:
            return 1.0
        elif duration <= 120:
            return 0.8
        else:
            return 0.6
    elif pace == "intense":
        # Boost shorter, faster attractions
        if duration < 60:
            return 1.0
        elif duration < 90:
            return 0.8
        else:
            return 0.6
    elif pace == "moderate":
        # Balanced preference for moderate pace
        if 60 <= duration <= 150:
            return 1.0
        elif duration <= 180:
            return 0.8
        else:
            return 0.6
    else:
        return 0.8  # Default moderate preference


def _calculate_safety_penalty(poi: Dict[str, Any], prefs: Dict[str, Any]) -> float:
    """Calculate safety penalty based on safety flags and preferences."""
    safety_flags = poi.get("safety_flags", [])
    avoid_tags = [t.lower() for t in prefs.get("avoid_tags", [])]
    
    penalty = 0.0
    
    # Check for crowded penalty
    if "crowded" in avoid_tags and any("crowded" in flag.lower() for flag in safety_flags):
        penalty += 0.2
    
    # Check for night safety
    if any("unsafe_night" in flag.lower() for flag in safety_flags):
        penalty += 0.1
    
    return min(penalty, 0.25)  # Cap at 0.25


def collect_safety_warnings(day_items: List[Dict[str, Any]]) -> List[str]:
    """Collect safety warnings for scheduled POIs."""
    warnings = []
    
    for item in day_items:
        if item.get("type") == "transfer":
            continue
            
        safety_flags = item.get("safety_flags", [])
        if safety_flags:
            title = item.get("title", "Activity")
            warning_parts = []
            
            for flag in safety_flags:
                if "crowded" in flag.lower():
                    warning_parts.append("crowded at peak hours")
                elif "unsafe_night" in flag.lower():
                    warning_parts.append("unsafe at night")
                else:
                    warning_parts.append(flag.lower())
            
            if warning_parts:
                warnings.append(f"Heads-up: {title} is {' and '.join(warning_parts)}")
    
    return warnings


def _score(poi: Dict[str, Any], daily_cap: float | None, prefs: Dict[str, Any], 
           day_start: str, day_end: str, pace: str, scheduled_items: List[Dict[str, Any]],
           affinities: Optional[Dict[str, float]] = None, context: Dict[str, Any] = None) -> float:
    """Calculate weighted score for a POI."""
    if context is None:
        context = {}
    
    pref_fit = _calculate_pref_fit(poi, prefs, context)
    time_fit = _calculate_time_fit(poi, day_start, day_end)
    budget_fit = _calculate_budget_fit(poi, daily_cap)
    diversity = _calculate_diversity(poi, scheduled_items)
    health_fit = _calculate_health_fit(poi, pace)
    
    # Apply weights from config
    # Calculate safety penalty
    safety_penalty = _calculate_safety_penalty(poi, prefs)
    
    weighted_score = (
        settings.RANK_W_PREF * pref_fit +
        settings.RANK_W_TIME * time_fit +
        settings.RANK_W_BUDGET * budget_fit +
        settings.RANK_W_DIV * diversity +
        settings.RANK_W_HEALTH * health_fit
    )
    # Apply safety penalty and affinity bonus
    weighted_score -= safety_penalty
    if affinities:
        weighted_score += affinity_bonus_for_poi(poi, affinities)
    return weighted_score


def rank(cands: List[Dict[str, Any]], daily_cap: float | None, prefs: Dict[str, Any] = None,
          day_start: str = "08:30", day_end: str = "20:00", pace: str = "moderate",
          scheduled_items: List[Dict[str, Any]] = None,
          affinities: Optional[Dict[str, float]] = None, context: Dict[str, Any] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Rank candidates by weighted score in descending order."""
    start_time = datetime.now()
    
    if prefs is None:
        prefs = {}
    if scheduled_items is None:
        scheduled_items = []
    if context is None:
        context = {"day_template": {"pace": pace}}
    
    # Get preference scorer for model version
    scorer = get_preference_scorer()
    pref_model_version = scorer.version()
    
    # Calculate scores for all candidates
    scored_cands = []
    for cand in cands:
        score = _score(cand, daily_cap, prefs, day_start, day_end, pace, scheduled_items, affinities, context)
        # Add score to candidate for scheduling
        cand["score"] = score
        scored_cands.append((cand, score))

    # Sort by score descending
    ranked = [cand for cand, score in sorted(scored_cands, key=lambda x: x[1], reverse=True)]
    
    # Calculate average scores for logging
    if scored_cands:
        avg_pref = sum(_calculate_pref_fit(cand, prefs, context) for cand, _ in scored_cands) / len(scored_cands)
        avg_time = sum(_calculate_time_fit(cand, day_start, day_end) for cand, _ in scored_cands) / len(scored_cands)
        avg_budget = sum(_calculate_budget_fit(cand, daily_cap) for cand, _ in scored_cands) / len(scored_cands)
    else:
        avg_pref = avg_time = avg_budget = 0.0
    
    duration = (datetime.now() - start_time).total_seconds()
    
    ranking_metrics = {
        "model_version": "balanced_v0",
        "pref_model_version": pref_model_version,
        "avg_pref_fit": round(avg_pref, 3),
        "avg_time_fit": round(avg_time, 3),
        "avg_budget_fit": round(avg_budget, 3),
        "weights": {
            "pref": settings.RANK_W_PREF,
            "time": settings.RANK_W_TIME,
            "budget": settings.RANK_W_BUDGET,
            "diversity": settings.RANK_W_DIV,
            "health": settings.RANK_W_HEALTH
        }
    }
    
    logger.debug(f"Ranking completed: {len(ranked)} candidates ranked in {duration:.3f}s")
    logger.debug(f"Ranking metrics: {ranking_metrics}")
    
    return ranked, ranking_metrics
