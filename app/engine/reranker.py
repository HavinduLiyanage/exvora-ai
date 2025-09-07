from __future__ import annotations

from typing import Dict, List, Optional
import os

from app.schemas.models import FeedbackAction

ALPHA: float = float(os.getenv("RERANK_EMA_ALPHA", "0.25"))


def _rating_to_weight(rating: int) -> float:
    """Map 1..5 star rating to [-1.0, +1.0] with 3 -> 0.

    w = (rating - 3) / 2
    """
    return max(-1.0, min(1.0, (rating - 3) / 2))


def update_affinities_from_actions(actions: List[FeedbackAction]) -> Dict[str, float]:
    """Build per-tag affinities using EMA from rate_item actions.

    affinity[tag] = (1-ALPHA)*affinity.get(tag, 0.0) + ALPHA*w
    """
    affinities: Dict[str, float] = {}
    for a in actions:
        if getattr(a, "type", None) == "rate_item":
            w = _rating_to_weight(int(getattr(a, "rating", 0) or 0))
            for tag in getattr(a, "tags", []) or []:
                tag_l = str(tag).lower()
                prev = affinities.get(tag_l, 0.0)
                affinities[tag_l] = (1 - ALPHA) * prev + ALPHA * w
    return affinities


def affinity_bonus_for_poi(poi: dict, affinities: Dict[str, float], max_bonus: float = 0.10) -> float:
    """Average affinity across poi.tags/themes, clamped to [-max_bonus, +max_bonus]."""
    tags = [str(t).lower() for t in (poi.get("tags") or [])] + [
        str(t).lower() for t in (poi.get("themes") or [])
    ]
    if not tags:
        return 0.0
    vals = [affinities.get(t, 0.0) for t in tags]
    if not vals:
        return 0.0
    avg = sum(vals) / len(vals)
    return max(-max_bonus, min(max_bonus, avg * max_bonus))


def explain_affinity(poi: dict, affinities: Dict[str, float]) -> Optional[str]:
    """Return brief reason when any tag has |affinity| >= 0.3."""
    tags = [str(t).lower() for t in (poi.get("tags") or [])] + [
        str(t).lower() for t in (poi.get("themes") or [])
    ]
    threshold = 0.3
    for t in tags:
        a = affinities.get(t, 0.0)
        if abs(a) >= threshold:
            if a > 0:
                # approximate stars back from weight
                return f"boosted by {t}"
            else:
                return f"penalized by {t}"
    return None


