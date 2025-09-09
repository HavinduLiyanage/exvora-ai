import copy
import pytest
from app.engine.budget import BudgetOptimizer

def make_day(date, items):
    return {"date": date, "summary": {"title": "Test"}, "items": items, "notes": []}

def act_item(title, cost, tags=None, price="medium", dur=60, locked=False):
    return {"start":"09:00","end":"10:00","place_id":title.lower().replace(" ","_"),
            "title": title,"estimated_cost": cost,"tags": tags or [],"price_band": price,
            "duration_minutes": dur,"locked": locked}

def xfer(mins):
    return {"type":"transfer","from_place_id":"a","to_place_id":"b","mode":"DRIVE","duration_minutes":mins,"distance_km":5.0,"source":"google_routes_live"}

def test_in_day_swap_brings_under_cap():
    """Test that budget optimizer can swap expensive items with cheaper alternatives to meet budget cap."""
    day = make_day("2025-09-10", [
        act_item("Museum", 40, ["history"]),
        xfer(20),
        act_item("Fancy Lunch", 55, ["food","fine_dining"]),
        xfer(15),
        act_item("Art Gallery", 35, ["art"]),
    ])
    candidates = {
        "2025-09-10": [
            {"place_id":"cheap_lunch","title":"Cheap Lunch","estimated_cost":12,"tags":["food"],"price_band":"low","duration_minutes":60},
            {"place_id":"street_food","title":"Street Food Court","estimated_cost":8,"tags":["food"],"price_band":"low","duration_minutes":45},
        ]
    }
    days = [copy.deepcopy(day)]
    opt = BudgetOptimizer()
    result = opt.optimize_trip(
        days=days,
        trip_context={"day_template":{"pace":"moderate"}},
        preferences={"avoid_tags":[]},
        constraints={"daily_budget_cap":100,"max_transfer_minutes":90},
        candidates_by_date=candidates
    )
    new_day = result["days"][0]
    assert new_day["summary"]["est_cost"] <= 100
    assert any("swapped" in n for n in new_day["notes"])

def test_respects_avoid_tags_and_locks():
    """Test that budget optimizer respects avoid_tags and locked items."""
    day = make_day("2025-09-11", [
        act_item("Viewpoint", 60, ["nature"]),
        xfer(10),
        act_item("Boat Tour", 70, ["water","crowded"], locked=True),
    ])
    candidates = {
        "2025-09-11": [
            {"place_id":"cheap_crowded","title":"Cheap Crowd Spot","estimated_cost":5,"tags":["crowded"],"price_band":"low","duration_minutes":60},
            {"place_id":"cheap_nature","title":"Free Park","estimated_cost":0,"tags":["nature","quiet"],"price_band":"free","duration_minutes":60},
        ]
    }
    days = [copy.deepcopy(day)]
    opt = BudgetOptimizer()
    res = opt.optimize_trip(
        days=days,
        trip_context={"day_template":{"pace":"light"}},
        preferences={"avoid_tags":["crowded"]},
        constraints={"daily_budget_cap":80,"max_transfer_minutes":60},
        candidates_by_date=candidates
    )
    new_items = res["days"][0]["items"]
    # Locked item is untouched
    assert any(it.get("title") == "Boat Tour" for it in new_items if it.get("type") != "transfer")
    # Avoid 'crowded' candidate; choose 'Free Park' if needed
    titles = [it.get("title") for it in new_items if it.get("type") != "transfer"]
    assert "Cheap Crowd Spot" not in titles

def test_no_feasible_swap_adds_warning():
    """Test that budget optimizer adds warning when no feasible swaps are available."""
    day = make_day("2025-09-12", [
        act_item("Premium Safari", 120, ["wildlife"], dur=180),
        xfer(40),
        act_item("Heli Tour", 200, ["adventure"], dur=90),
    ])
    candidates = {
        "2025-09-12": [
            {"place_id":"not_similar","title":"Pottery Class","estimated_cost":5,"tags":["crafts"],"price_band":"low","duration_minutes":60},
        ]
    }
    opt = BudgetOptimizer()
    out = opt.optimize_trip(
        days=[day],
        trip_context={"day_template":{"pace":"moderate"}},
        preferences={"avoid_tags":[]},
        constraints={"daily_budget_cap":100,"max_transfer_minutes":60},
        candidates_by_date=candidates
    )
    notes = out["days"][0]["notes"]
    assert any("Budget warning" in n for n in notes)

def test_trip_totals_present_and_stable():
    """Test that trip totals are computed correctly and consistently."""
    day = make_day("2025-09-13", [
        act_item("Temple", 10, ["culture"]),
        xfer(10),
        act_item("Market", 15, ["food"]),
    ])
    opt = BudgetOptimizer()
    out = opt.optimize_trip(
        days=[day],
        trip_context={"day_template":{"pace":"moderate"}},
        preferences={},
        constraints={},  # no cap
        candidates_by_date={"2025-09-13":[]}
    )
    assert "trip_cost_est" in out["totals"]
    assert "trip_transfer_minutes" in out["totals"]
    assert "daily" in out["totals"]
    assert out["totals"]["trip_cost_est"] == 25.0
    assert out["totals"]["trip_transfer_minutes"] == 10

def test_no_cap_skips_optimization():
    """Test that when no daily_budget_cap is provided, optimization is skipped but totals are still computed."""
    day = make_day("2025-09-14", [
        act_item("Expensive Activity", 200, ["luxury"]),
    ])
    opt = BudgetOptimizer()
    out = opt.optimize_trip(
        days=[day],
        trip_context={"day_template":{"pace":"moderate"}},
        preferences={},
        constraints={},  # no cap
        candidates_by_date={"2025-09-14":[]}
    )
    # Should not modify the day
    assert out["days"][0]["items"][0]["title"] == "Expensive Activity"
    # But should still compute totals
    assert out["totals"]["trip_cost_est"] == 200.0

def test_deterministic_ordering():
    """Test that the optimizer produces deterministic results with the same input."""
    day = make_day("2025-09-15", [
        act_item("Activity A", 50, ["test"]),
        act_item("Activity B", 50, ["test"]),
    ])
    candidates = {
        "2025-09-15": [
            {"place_id":"cheap1","title":"Cheap 1","estimated_cost":10,"tags":["test"],"price_band":"low","duration_minutes":60},
            {"place_id":"cheap2","title":"Cheap 2","estimated_cost":10,"tags":["test"],"price_band":"low","duration_minutes":60},
        ]
    }
    opt = BudgetOptimizer()
    
    # Run optimization multiple times
    results = []
    for _ in range(3):
        day_copy = copy.deepcopy(day)
        result = opt.optimize_trip(
            days=[day_copy],
            trip_context={"day_template":{"pace":"moderate"}},
            preferences={},
            constraints={"daily_budget_cap":80},
            candidates_by_date=candidates
        )
        results.append(result)
    
    # Results should be identical
    for i in range(1, len(results)):
        assert results[i]["days"][0]["summary"]["est_cost"] == results[0]["days"][0]["summary"]["est_cost"]

def test_similarity_filtering():
    """Test that only similar activities are considered for swapping."""
    day = make_day("2025-09-16", [
        act_item("Museum", 50, ["culture", "history"]),
    ])
    candidates = {
        "2025-09-16": [
            {"place_id":"similar","title":"Art Gallery","estimated_cost":10,"tags":["culture", "art"],"price_band":"low","duration_minutes":60},
            {"place_id":"different","title":"Gym","estimated_cost":5,"tags":["fitness"],"price_band":"low","duration_minutes":60},
        ]
    }
    opt = BudgetOptimizer()
    out = opt.optimize_trip(
        days=[day],
        trip_context={"day_template":{"pace":"moderate"}},
        preferences={},
        constraints={"daily_budget_cap":30},
        candidates_by_date=candidates
    )
    
    # Should swap with similar activity (art gallery) not different one (gym)
    new_items = out["days"][0]["items"]
    activity_titles = [it.get("title") for it in new_items if it.get("type") != "transfer"]
    assert "Art Gallery" in activity_titles
    assert "Gym" not in activity_titles

def test_legacy_function_compatibility():
    """Test that the legacy optimize_day_budget function still works."""
    from app.engine.budget import optimize_day_budget
    
    day = make_day("2025-09-21", [act_item("Expensive", 100, ["test"])])
    candidates = [{"place_id":"cheap","title":"Cheap Alternative","estimated_cost":30,"tags":["test"],"price_band":"low","duration_minutes":60}]
    
    optimized_day, notes = optimize_day_budget(day, candidates, 50)
    
    assert optimized_day["summary"]["est_cost"] <= 50
    assert len(notes) > 0
    assert any("swapped" in note for note in notes)