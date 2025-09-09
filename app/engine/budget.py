from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Set
import math

PRICE_ORDER = {"free": 0, "low": 1, "medium": 2, "high": 3}

@dataclass
class SwapSuggestion:
    remove_idx: int
    add_candidate: Dict[str, Any]
    saved_amount: float
    reason: str

class BudgetOptimizer:
    """
    Post-pack optimizer that:
      1) Computes day cost and trip totals
      2) If a day exceeds cap, tries in-day substitutions with cheaper 'similar' candidates
      3) Optional cross-day rebalance (feature flag) – keep off by default for MVP
    Deterministic: sorts by stable keys, never uses random.
    """

    def __init__(self, enable_cross_day_rebalance: bool = False):
        self.enable_cross_day_rebalance = enable_cross_day_rebalance

    # ---------- Public API ----------
    def optimize_trip(self, *, days: List[Dict[str, Any]], trip_context: Dict[str, Any], preferences: Dict[str, Any], constraints: Dict[str, Any], candidates_by_date: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        cap = (constraints or {}).get("daily_budget_cap")
        if cap is None:
            # No-op if no cap; still compute summary
            totals = self._compute_trip_totals(days)
            return {"days": days, "totals": totals}

        avoid_tags: Set[str] = set((preferences or {}).get("avoid_tags") or [])
        max_transfer_minutes = (constraints or {}).get("max_transfer_minutes", 10**6)
        pace = ((trip_context or {}).get("day_template") or {}).get("pace", "moderate")

        for day in days:
            self._ensure_notes(day)
            day_cost = self._estimate_day_cost(day)
            if day_cost <= cap:
                continue

            # Try in-day substitution(s)
            swaps_applied = self._apply_in_day_swaps(
                day=day,
                cap=cap,
                avoid_tags=avoid_tags,
                day_candidates=candidates_by_date.get(day["date"], []),
                max_transfer_minutes=max_transfer_minutes,
                pace=pace,
            )

            # Recompute after swaps
            day["summary"]["est_cost"] = round(self._estimate_day_cost(day), 2)
            if not swaps_applied and day["summary"]["est_cost"] > cap:
                self._add_note(day, f"Budget warning: day cost {day['summary']['est_cost']} exceeds cap {cap}; no feasible cheaper substitutes found.")

        # Optional cross-day rebalance (off by default – safer MVP)
        if self.enable_cross_day_rebalance:
            self._rebalance_across_days(days, cap)

        totals = self._compute_trip_totals(days)
        return {"days": days, "totals": totals}

    # ---------- Cost & notes ----------
    def _estimate_day_cost(self, day: Dict[str, Any]) -> float:
        cost = 0.0
        for it in day.get("items", []):
            if it.get("type") == "transfer":
                continue
            cost += float(it.get("estimated_cost") or 0.0)
        return cost

    def _ensure_notes(self, day: Dict[str, Any]) -> None:
        day.setdefault("notes", [])
        day.setdefault("summary", {}).setdefault("est_cost", round(self._estimate_day_cost(day), 2))

    def _add_note(self, day: Dict[str, Any], msg: str) -> None:
        notes = day.setdefault("notes", [])
        if msg not in notes:
            notes.append(msg)

    # ---------- In-day substitutions ----------
    def _apply_in_day_swaps(self, *, day: Dict[str, Any], cap: float, avoid_tags: Set[str], day_candidates: List[Dict[str, Any]], max_transfer_minutes: int, pace: str) -> bool:
        """
        Greedy: replace highest-cost, non-locked activities first with cheaper 'similar' candidates
        that (a) respect avoid_tags, (b) fit opening hours & duration window, (c) won't explode transfers.
        Deterministic ordering.
        """
        items = day.get("items", [])
        # Indices of place items eligible for replacement
        replace_idxs = [
            i for i, it in enumerate(items)
            if it.get("type") != "transfer" and not it.get("locked", False)
        ]
        # Sort expensive-first; tie-break by title/place_id for determinism
        replace_idxs.sort(key=lambda i: (-float(items[i].get("estimated_cost") or 0.0), items[i].get("title", ""), items[i].get("place_id", "")))

        # Pre-sort candidates: cheapest-first, then by price_band level, then title
        cands = [c for c in day_candidates if self._candidate_allowed(c, avoid_tags)]
        cands.sort(key=lambda c: (float(c.get("estimated_cost") or 0.0), PRICE_ORDER.get(c.get("price_band", "medium"), 2), c.get("title", ""), c.get("place_id", "")))

        swaps_done = False
        visited_pairs: Set[Tuple[str, str]] = set()  # (removed_place_id, added_place_id) to avoid ping-pong

        for idx in replace_idxs:
            if self._estimate_day_cost(day) <= cap:
                break
            original = items[idx]
            orig_cost = float(original.get("estimated_cost") or 0.0)
            if orig_cost <= 0:
                continue

            # Find first viable cheaper candidate
            for cand in cands:
                if cand.get("place_id") == original.get("place_id"):
                    continue
                if (original.get("place_id"), cand.get("place_id")) in visited_pairs:
                    continue
                if not self._is_similar_enough(original, cand):
                    continue
                if not self._fits_schedule(day, idx, cand, max_transfer_minutes, pace):
                    continue
                cand_cost = float(cand.get("estimated_cost") or 0.0)
                if cand_cost >= orig_cost:
                    continue

                # Apply swap
                saved = orig_cost - cand_cost
                replacement = self._project_candidate_to_item(original, cand)
                items[idx] = replacement
                swaps_done = True
                visited_pairs.add((original.get("place_id"), cand.get("place_id")))
                self._add_note(day, f"Budget optimizer: swapped '{original.get('title')}' ({orig_cost}) → '{cand.get('title')}' ({cand_cost}) saving {round(saved,2)}.")
                # Re-verify transfers for adjacent hops is handled later by routes step; mark as heuristic for now
                self._mark_adjacent_transfers_for_reverify(day, idx)
                if self._estimate_day_cost(day) <= cap:
                    break

        return swaps_done

    def _candidate_allowed(self, c: Dict[str, Any], avoid_tags: Set[str]) -> bool:
        tags = set(c.get("tags") or [])
        return avoid_tags.isdisjoint(tags)

    def _is_similar_enough(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        # Simple Jaccard on tags; require minimal overlap to keep trip theme coherent
        ta, tb = set(a.get("tags") or []), set(b.get("tags") or [])
        if not ta or not tb:
            return True
        inter = len(ta & tb)
        denom = len(ta | tb)
        jacc = inter / denom if denom else 0.0
        return jacc >= 0.2  # tunable

    def _fits_schedule(self, day: Dict[str, Any], idx: int, cand: Dict[str, Any], max_transfer_minutes: int, pace: str) -> bool:
        """
        Heuristic time/transfer check:
        - keep existing start/end for the slot
        - require cand.duration_minutes within ±30% of original duration
        - ensure no adjacent single-hop transfer exceeds max_transfer_minutes
        - do not check opening hours here deeply (assume upstream scheduler pre-filtered day_candidates); MVP
        """
        items = day.get("items", [])
        original = items[idx]
        orig_dur = int(original.get("duration_minutes") or 60)
        cand_dur = int(cand.get("duration_minutes") or orig_dur)
        if not (0.7 * orig_dur <= cand_dur <= 1.3 * orig_dur):
            return False

        # Adjacent transfer durations if present
        left = items[idx - 1] if idx - 1 >= 0 else None
        right = items[idx + 1] if idx + 1 < len(items) else None
        for hop in (left, right):
            if hop and hop.get("type") == "transfer":
                if int(hop.get("duration_minutes") or 0) > max_transfer_minutes:
                    return False
        return True

    def _project_candidate_to_item(self, original: Dict[str, Any], cand: Dict[str, Any]) -> Dict[str, Any]:
        # Keep the original time slot; replace place metadata & cost
        out = dict(original)
        out.update({
            "place_id": cand.get("place_id"),
            "title": cand.get("title", cand.get("name", "Place")),
            "estimated_cost": cand.get("estimated_cost", original.get("estimated_cost")),
            "tags": cand.get("tags", original.get("tags")),
            "price_band": cand.get("price_band", original.get("price_band")),
            "duration_minutes": cand.get("duration_minutes", original.get("duration_minutes")),
            "opening_hours": cand.get("opening_hours", original.get("opening_hours")),
        })
        return out

    def _mark_adjacent_transfers_for_reverify(self, day: Dict[str, Any], idx: int) -> None:
        items = day.get("items", [])
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(items) and items[j].get("type") == "transfer":
                # mark source heuristic so the routes verifier re-checks
                items[j]["source"] = "heuristic"

    # ---------- Totals ----------
    def _compute_trip_totals(self, days: List[Dict[str, Any]]) -> Dict[str, Any]:
        trip_cost = 0.0
        transfer_minutes = 0
        daily = []
        for d in days:
            dc = self._estimate_day_cost(d)
            for it in d.get("items", []):
                if it.get("type") == "transfer":
                    transfer_minutes += int(it.get("duration_minutes") or 0)
            d.setdefault("summary", {})["est_cost"] = round(dc, 2)
            daily.append({"date": d.get("date"), "est_cost": round(dc, 2)})
            trip_cost += dc
        return {"trip_cost_est": round(trip_cost, 2), "trip_transfer_minutes": transfer_minutes, "daily": daily}

    # ---------- Optional cross-day (disabled) ----------
    def _rebalance_across_days(self, days: List[Dict[str, Any]], cap: float) -> None:
        # Placeholder: future enhancement (move flexible items from over-cap days to under-cap days respecting openings)
        return


# Legacy function for backward compatibility
def optimize_day_budget(
    day_plan: Dict[str, Any], 
    ranked_pool: List[Dict[str, Any]], 
    cap: Optional[float]
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Legacy function for backward compatibility.
    Creates a BudgetOptimizer instance and applies optimization to a single day.
    """
    if cap is None:
        return day_plan, []
    
    # Convert single day to days list format
    days = [day_plan]
    
    # Create candidates_by_date dict
    candidates_by_date = {day_plan.get("date", "unknown"): ranked_pool}
    
    # Create optimizer and run
    optimizer = BudgetOptimizer()
    result = optimizer.optimize_trip(
        days=days,
        trip_context={"day_template": {"pace": "moderate"}},
        preferences={"avoid_tags": []},
        constraints={"daily_budget_cap": cap},
        candidates_by_date=candidates_by_date
    )
    
    # Extract notes from the optimized day
    optimized_day = result["days"][0]
    notes = optimized_day.get("notes", [])
    
    return optimized_day, notes