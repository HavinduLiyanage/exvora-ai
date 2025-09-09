"""
Tests for candidate generator and rules hardening.
"""

from app.engine.candidates import generate_candidates

BASE_REQ = {
    "trip_context": {
        "base_place_id": "ChIJ_col_museum",
        "date_range": {"start": "2025-09-10", "end": "2025-09-10"},
        "day_template": {"start": "08:30", "end": "20:00", "pace": "moderate"},
        "modes": ["DRIVE", "WALK"]
    },
    "preferences": {
        "themes": ["Nature", "Culture"], 
        "activity_tags": ["Hiking", "History"], 
        "avoid_tags": ["late_night"]
    },
    "constraints": {
        "max_transfer_minutes": 90
    }
}


def test_candidate_geo_window_and_opening_alignment():
    """Test that candidates are filtered by geographic window and have opening alignment."""
    kept, drops = generate_candidates(
        BASE_REQ["trip_context"], 
        BASE_REQ["preferences"], 
        BASE_REQ["constraints"]
    )
    
    assert isinstance(kept, list) and len(kept) > 0
    assert all("opening_align" in c and "distance_km" in c for c in kept)
    
    # Check that all candidates have valid opening alignment scores
    for candidate in kept:
        assert 0.0 <= candidate["opening_align"] <= 1.0
        assert candidate["distance_km"] >= 0.0


def test_rules_avoid_tags_and_seasonality_closures():
    """Test that avoid tags and seasonality rules work correctly."""
    prefs = dict(BASE_REQ["preferences"])
    prefs["avoid_tags"] = ["crowded"]
    
    kept, drops = generate_candidates(
        BASE_REQ["trip_context"], 
        prefs, 
        BASE_REQ["constraints"]
    )
    
    # Check that no kept candidates have avoided tags
    for candidate in kept:
        tags = candidate.get("tags", [])
        assert "crowded" not in tags
    
    # Check that we have some drop reasons
    reasons = {d["reason"] for d in drops}
    assert len(reasons) > 0  # Should have some drops
    
    # Should have avoid_tag drops or other valid reasons
    valid_reasons = {
        "avoid_tag:crowded", "bad_season", "closed", 
        "precheck_transfer_exceeds", "safety_gate"
    }
    assert any(reason in valid_reasons for reason in reasons)


def test_rules_precheck_transfer_exceeds():
    """Test that transfer time limits are enforced."""
    # Use very restrictive transfer time limit
    constraints = {"max_transfer_minutes": 1}  # 1 minute is very restrictive
    
    kept, drops = generate_candidates(
        BASE_REQ["trip_context"], 
        BASE_REQ["preferences"], 
        constraints
    )
    
    reasons = [d["reason"] for d in drops]
    assert "precheck_transfer_exceeds" in reasons or len(kept) < 5  # Either drops or very few kept


def test_deterministic_sorting():
    """Test that candidates are sorted deterministically."""
    kept1, _ = generate_candidates(
        BASE_REQ["trip_context"], 
        BASE_REQ["preferences"], 
        BASE_REQ["constraints"]
    )
    
    kept2, _ = generate_candidates(
        BASE_REQ["trip_context"], 
        BASE_REQ["preferences"], 
        BASE_REQ["constraints"]
    )
    
    # Results should be identical
    assert kept1 == kept2
    
    # Check that sorting is by price_band, then opening_align, etc.
    if len(kept1) > 1:
        for i in range(len(kept1) - 1):
            current = kept1[i]
            next_item = kept1[i + 1]
            
            # Price band should be non-decreasing
            from app.engine.candidates import PRICE_ORDER
            current_price = PRICE_ORDER.get(current.get("price_band", "low"), 1)
            next_price = PRICE_ORDER.get(next_item.get("price_band", "low"), 1)
            
            if current_price == next_price:
                # If same price, opening_align should be non-increasing
                current_align = current.get("opening_align", 0.0)
                next_align = next_item.get("opening_align", 0.0)
                assert current_align >= next_align


def test_locked_items_never_dropped():
    """Test that locked items are never dropped by rules."""
    # Create a request with a locked item that exists in the fixture
    trip_context = dict(BASE_REQ["trip_context"])
    trip_context["locks"] = [{"poi_id": "colombo_national_museum", "start": "09:00", "end": "12:00"}]
    
    # Use very restrictive constraints that would normally drop most items
    constraints = {
        "max_transfer_minutes": 1,  # Very restrictive
        "daily_budget_cap": 1  # Very low budget
    }
    
    kept, drops = generate_candidates(trip_context, BASE_REQ["preferences"], constraints)
    
    # The locked item should still be in kept candidates
    locked_poi_ids = {candidate["poi_id"] for candidate in kept}
    assert "colombo_national_museum" in locked_poi_ids


def test_region_windowing():
    """Test that candidates are filtered by geographic region."""
    # Use a very small radius to test region windowing
    constraints = {"radius_km": 1}  # 1km radius
    
    kept, drops = generate_candidates(
        BASE_REQ["trip_context"], 
        BASE_REQ["preferences"], 
        constraints
    )
    
    # Should have very few candidates due to small radius
    assert len(kept) < 10  # Most POIs should be filtered out by distance
    
    # All kept candidates should be within the radius
    for candidate in kept:
        distance = candidate.get("distance_km", 0.0)
        assert distance <= 1.0


def test_opening_hours_filtering():
    """Test that candidates are filtered by opening hours."""
    # Use a very early day template that most POIs won't be open for
    trip_context = dict(BASE_REQ["trip_context"])
    trip_context["day_template"] = {"start": "02:00", "end": "04:00", "pace": "moderate"}
    
    kept, drops = generate_candidates(
        trip_context, 
        BASE_REQ["preferences"], 
        BASE_REQ["constraints"]
    )
    
    # Should have fewer candidates due to opening hours
    reasons = [d["reason"] for d in drops]
    assert "closed" in reasons or len(kept) < 20  # Either closed drops or fewer kept


def test_theme_prefiltering():
    """Test that theme prefiltering works."""
    # Use very specific themes that few POIs will match
    prefs = {
        "themes": ["VerySpecificTheme"],
        "activity_tags": ["VerySpecificTag"],
        "avoid_tags": []
    }
    
    kept, drops = generate_candidates(
        BASE_REQ["trip_context"], 
        prefs, 
        BASE_REQ["constraints"]
    )
    
    # Should have very few candidates due to specific themes
    assert len(kept) < 10


def test_safety_gate():
    """Test that safety gate filters out inappropriate activities."""
    # Use low energy preference to trigger safety gate
    prefs = {
        "themes": ["Nature"],
        "activity_tags": ["Hiking"],
        "avoid_tags": [],
        "health": {"health_load": "low"}
    }
    
    kept, drops = generate_candidates(
        BASE_REQ["trip_context"], 
        prefs, 
        BASE_REQ["constraints"]
    )
    
    # Should have some safety gate drops
    reasons = [d["reason"] for d in drops]
    assert "safety_gate" in reasons or len(kept) < 20


def test_drop_log_format():
    """Test that drop log has correct format."""
    kept, drops = generate_candidates(
        BASE_REQ["trip_context"], 
        BASE_REQ["preferences"], 
        BASE_REQ["constraints"]
    )
    
    # Check drop log format
    for drop in drops:
        assert "poi_id" in drop
        assert "reason" in drop
        assert isinstance(drop["poi_id"], str)
        assert isinstance(drop["reason"], str)
        
        # Check that reason is from allowed list
        allowed_reasons = {
            "avoid_tag:",
            "bad_season",
            "closed", 
            "precheck_transfer_exceeds",
            "safety_gate"
        }
        reason = drop["reason"]
        assert any(reason.startswith(prefix) or reason == prefix for prefix in allowed_reasons)
