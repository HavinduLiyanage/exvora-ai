"""
Tests for fixture dataset to ensure it has the right diversity and demo data.
"""

from app.dataset.fixtures import load_fixture_pois


def test_fixture_has_minimum_diversity():
    """Test that fixture has minimum diversity for demos."""
    pois = load_fixture_pois()
    assert len(pois) >= 12
    
    all_tags = {t for p in pois for t in p.get("tags", [])}
    # Ensure tags that matter for demos are present
    for needed in ["hiking", "quiet", "street_food", "nightlife", "crowded", "history", "wildlife"]:
        assert needed in all_tags, f"Missing required tag: {needed}"


def test_fixture_has_known_demo_ids():
    """Test that fixture contains the specific POIs needed for demos."""
    pois = load_fixture_pois()
    ids = {p["poi_id"] for p in pois}
    required_ids = {"ella_rock_hike", "pettah_market_colombo", "nightlife_district_colombo"}
    assert required_ids <= ids, f"Missing required POI IDs: {required_ids - ids}"


def test_fixture_pois_have_required_fields():
    """Test that all POIs have the required fields for reranking."""
    pois = load_fixture_pois()
    
    required_fields = ["poi_id", "tags", "name", "price_band", "estimated_cost", "duration_minutes"]
    
    for poi in pois:
        for field in required_fields:
            assert field in poi, f"POI {poi.get('poi_id', 'unknown')} missing field: {field}"
        
        # Check that tags is a list
        assert isinstance(poi["tags"], list), f"POI {poi['poi_id']} tags should be a list"
        
        # Check that estimated_cost is numeric
        assert isinstance(poi["estimated_cost"], (int, float)), f"POI {poi['poi_id']} estimated_cost should be numeric"
        
        # Check that duration_minutes is numeric
        assert isinstance(poi["duration_minutes"], (int, float)), f"POI {poi['poi_id']} duration_minutes should be numeric"


def test_fixture_has_demo_scenarios():
    """Test that fixture has the right combinations for demo scenarios."""
    pois = load_fixture_pois()
    
    # Find POIs for hiking/quiet demo
    hiking_quiet_pois = [p for p in pois if "hiking" in p["tags"] and "quiet" in p["tags"]]
    assert len(hiking_quiet_pois) >= 1, "Need at least one hiking/quiet POI for demo"
    
    # Find POIs for nightlife/crowded demo
    nightlife_crowded_pois = [p for p in pois if "nightlife" in p["tags"] and "crowded" in p["tags"]]
    assert len(nightlife_crowded_pois) >= 1, "Need at least one nightlife/crowded POI for demo"
    
    # Find POIs for street_food demo
    street_food_pois = [p for p in pois if "street_food" in p["tags"]]
    assert len(street_food_pois) >= 1, "Need at least one street_food POI for demo"


def test_fixture_has_price_diversity():
    """Test that fixture has diverse price bands for budget testing."""
    pois = load_fixture_pois()
    
    price_bands = {p["price_band"] for p in pois}
    expected_bands = {"free", "low", "medium", "high"}
    
    # Should have at least 3 different price bands
    assert len(price_bands) >= 3, f"Need more price diversity, only found: {price_bands}"
    
    # Should have free and low cost options
    assert "free" in price_bands, "Need free POIs for budget testing"
    assert "low" in price_bands, "Need low-cost POIs for budget testing"


def test_fixture_has_duration_diversity():
    """Test that fixture has diverse durations for scheduling testing."""
    pois = load_fixture_pois()
    
    durations = [p["duration_minutes"] for p in pois]
    
    # Should have short, medium, and long activities
    short_activities = [d for d in durations if d <= 60]
    medium_activities = [d for d in durations if 60 < d <= 180]
    long_activities = [d for d in durations if d > 180]
    
    assert len(short_activities) >= 2, "Need more short activities (≤60 min)"
    assert len(medium_activities) >= 2, "Need more medium activities (60-180 min)"
    assert len(long_activities) >= 1, "Need at least one long activity (>180 min)"
