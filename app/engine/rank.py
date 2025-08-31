from typing import List, Dict, Any, Tuple
from datetime import datetime
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _calculate_pref_fit(poi: Dict[str, Any], prefs: Dict[str, Any]) -> float:
    """Calculate preference fit score based on theme/tag overlap."""
    themes = set(map(str.lower, prefs.get("themes", [])))
    avoid_tags = set(map(str.lower, prefs.get("avoid_tags", [])))
    
    if not themes:
        return 0.5  # Neutral score if no themes specified
    
    poi_themes = set(map(str.lower, poi.get("themes", [])))
    poi_tags = set(map(str.lower, poi.get("tags", [])))
    
    # Check for avoid tags
    if avoid_tags & poi_tags:
        return 0.0
    
    # Calculate theme overlap
    if not poi_themes:
        return 0.3  # Low score for POIs without themes
    
    overlap = len(themes & poi_themes)
    total = len(themes)
    
    if total == 0:
        return 0.5
    
    return overlap / total


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
    """Calculate health fit score based on pace preference."""
    duration = int(poi.get("duration_minutes") or 60)
    
    # Pace-based duration preferences
    if pace == "light":
        # Prefer shorter activities for light pace
        if duration <= 90:
            return 1.0
        elif duration <= 120:
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
    elif pace == "intense":
        # Can handle longer activities for intense pace
        if duration >= 120:
            return 1.0
        elif duration >= 90:
            return 0.9
        else:
            return 0.7
    else:
        return 0.8  # Default moderate preference


def _score(poi: Dict[str, Any], daily_cap: float | None, prefs: Dict[str, Any], 
           day_start: str, day_end: str, pace: str, scheduled_items: List[Dict[str, Any]]) -> float:
    """Calculate weighted score for a POI."""
    pref_fit = _calculate_pref_fit(poi, prefs)
    time_fit = _calculate_time_fit(poi, day_start, day_end)
    budget_fit = _calculate_budget_fit(poi, daily_cap)
    diversity = _calculate_diversity(poi, scheduled_items)
    health_fit = _calculate_health_fit(poi, pace)
    
    # Apply weights from config
    weighted_score = (
        settings.RANK_W_PREF * pref_fit +
        settings.RANK_W_TIME * time_fit +
        settings.RANK_W_BUDGET * budget_fit +
        settings.RANK_W_DIV * diversity +
        settings.RANK_W_HEALTH * health_fit
    )
    
    return weighted_score


def rank(cands: List[Dict[str, Any]], daily_cap: float | None, prefs: Dict[str, Any] = None,
          day_start: str = "08:30", day_end: str = "20:00", pace: str = "moderate",
          scheduled_items: List[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Rank candidates by weighted score in descending order."""
    start_time = datetime.now()
    
    if prefs is None:
        prefs = {}
    if scheduled_items is None:
        scheduled_items = []
    
    # Calculate scores for all candidates
    scored_cands = []
    for cand in cands:
        score = _score(cand, daily_cap, prefs, day_start, day_end, pace, scheduled_items)
        scored_cands.append((cand, score))
    
    # Sort by score descending
    ranked = [cand for cand, score in sorted(scored_cands, key=lambda x: x[1], reverse=True)]
    
    # Calculate average scores for logging
    if scored_cands:
        avg_pref = sum(_calculate_pref_fit(cand, prefs) for cand, _ in scored_cands) / len(scored_cands)
        avg_time = sum(_calculate_time_fit(cand, day_start, day_end) for cand, _ in scored_cands) / len(scored_cands)
        avg_budget = sum(_calculate_budget_fit(cand, daily_cap) for cand, _ in scored_cands) / len(scored_cands)
    else:
        avg_pref = avg_time = avg_budget = 0.0
    
    duration = (datetime.now() - start_time).total_seconds()
    
    ranking_metrics = {
        "model_version": "balanced_v0",
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
