from __future__ import annotations

from typing import Dict, List, Tuple, Union, Optional
from datetime import date

from app.schemas.models import (
    Preferences,
    TripContext,
    Constraints,
    Lock,
    FeedbackAction,
    Activity,
    Transfer,
    CurrentDayPlan,
    DayTemplate,
)
from app.engine.reranker import update_affinities_from_actions
from app.engine import candidates as cand
from app.engine import rules
from app.engine import rank
from app.engine import schedule
from app.engine import transfers


def apply_actions_to_prefs(prefs: Preferences, actions: List[FeedbackAction]) -> Preferences:
    """Return a new Preferences with avoid_tags extended based on actions."""
    avoid = set([t.lower() for t in (prefs.avoid_tags or [])])
    for a in actions:
        if getattr(a, "type", None) == "request_alternative":
            for t in getattr(a, "avoid_tags", []) or []:
                avoid.add(str(t).lower())
    new_prefs = Preferences(
        themes=prefs.themes,
        activity_tags=prefs.activity_tags,
        avoid_tags=list(sorted(avoid)),
        currency=getattr(prefs, "currency", None),
    )
    return new_prefs


def drop_removed_items(plan_items: List[Union[Activity, Transfer]], actions: List[FeedbackAction]) -> List[Activity]:
    """Strip transfers and remove any activities targeted by remove_item actions."""
    remove_ids = {getattr(a, "place_id") for a in actions if getattr(a, "type", None) == "remove_item"}
    activities: List[Activity] = [i for i in plan_items if (i.get("type") != "transfer")]
    kept = [i for i in activities if i.get("place_id") not in remove_ids]
    # ensure chronological order by start time
    kept.sort(key=lambda x: x.get("start"))
    return kept


def find_alternates(near_place_id: str, all_candidates, prefs: Preferences, constraints: Constraints):
    """Simple heuristic: prefer POIs sharing at least one theme/tag with the 'near' POI."""
    near = next((p for p in all_candidates if p.get("place_id") == near_place_id), None)
    if not near:
        return []
    n_themes = set([t.lower() for t in (near.get("themes") or [])])
    n_tags = set([t.lower() for t in (near.get("tags") or [])])
    def _score(po):
        t_themes = set([t.lower() for t in (po.get("themes") or [])])
        t_tags = set([t.lower() for t in (po.get("tags") or [])])
        return len(n_themes & t_themes) + len(n_tags & t_tags)
    ranked = sorted(all_candidates, key=_score, reverse=True)
    return ranked[:10]


def repack_day_from_actions(
    trip_day: date,
    preferences: Optional[Preferences],
    constraints: Optional[Constraints],
    locks: List[Lock],
    current_plan: CurrentDayPlan,
    actions: List[FeedbackAction],
    pois: List[dict],
    day_template: DayTemplate,
    base_place_id: str,
) -> Tuple[List[Union[Activity, Transfer]], List[str]]:
    """
    Build affinities from actions, update prefs, generate+filter candidates, rank with affinities.
    Start fresh (locks preserved), keep still-valid activities, then pack with schedule.pack_day.
    Insert transfers only where legs changed.
    """
    notes: List[str] = []
    # 1) affinities
    affinities = update_affinities_from_actions(actions)

    # 2) prefs update
    prefs2 = apply_actions_to_prefs(preferences or Preferences(themes=[], activity_tags=[], avoid_tags=[]), actions)
    
    # Handle daily_signal energy="low" by treating pace as "light"
    pace = day_template.pace  # Start with template pace
    for a in actions:
        if getattr(a, "type", None) == "daily_signal" and getattr(a, "energy", None) == "low":
            pace = "light"
            break

    # 3) generate candidates
    day_start = day_template.start
    day_end = day_template.end
    
    candidates, _reasons = cand.basic_candidates(pois, prefs2.model_dump(), date_str=trip_day.isoformat(), day_window=(day_start, day_end), base_place_id=base_place_id, pace=pace)
    filtered, _ = rules.apply_hard_rules(candidates, constraints.model_dump() if constraints else {}, locks)
    ranked, metrics = rank.rank(filtered, (constraints.daily_budget_cap if constraints else None), prefs2.model_dump(), day_start, day_end, pace, affinities=affinities)

    # 4) keep still-valid activities from current plan (after removals)
    kept = drop_removed_items(current_plan.items, actions)

    # 5) pack a new day (locks first)
    day_plan = schedule.schedule_day(trip_day.isoformat(), ranked, constraints.daily_budget_cap if constraints else None, day_start=day_start, day_end=day_end, locks=locks, pace=pace)
    new_activities = [i for i in day_plan["items"] if i.get("type") != "transfer"]

    # 6) reinsert transfers only for changed legs
    merged = transfers.reinsert_changed_transfers(current_plan.items, new_activities, "DRIVE")

    # 7) notes
    for a in actions:
        if getattr(a, "type", None) == "remove_item":
            notes.append(f"Removed item {getattr(a, 'place_id')}")
        if getattr(a, "type", None) == "rate_item":
            notes.append(f"Rated {getattr(a, 'place_id')} {getattr(a, 'rating')}★")
        if getattr(a, "type", None) == "request_alternative":
            notes.append(f"Requested alternative near {getattr(a, 'near_place_id')}")

    return merged, notes


