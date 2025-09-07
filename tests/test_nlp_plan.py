"""
Tests for NLP planner module.
"""
import pytest
from app.nlp.parse import parse_prompt_to_plan


def test_parse_basic_prompt():
    """Test parsing a basic prompt with duration, place, and preferences."""
    prompt = "3 days in Kandy, love temples and hikes, avoid crowded places, tight budget"
    
    trip_context, preferences, constraints, locks = parse_prompt_to_plan(prompt)
    
    # Check trip context
    assert trip_context.base_place_id == "ChIJkandy"
    assert trip_context.date_range.start is not None
    assert trip_context.date_range.end is not None
    assert trip_context.day_template.pace == "moderate"  # Default pace
    assert trip_context.modes == ["DRIVE", "WALK"]
    
    # Check preferences
    assert "Culture" in preferences.themes
    assert "Hiking" in preferences.activity_tags
    assert "crowded" in preferences.avoid_tags
    
    # Check constraints
    assert constraints.daily_budget_cap == 80  # tight budget
    assert constraints.max_transfer_minutes == 90
    
    # Check locks
    assert locks == []


def test_parse_duration_variations():
    """Test parsing different duration formats."""
    # Test "5 days"
    _, _, _, _ = parse_prompt_to_plan("5 days in Colombo")
    
    # Test "weekend"
    _, _, _, _ = parse_prompt_to_plan("weekend in Galle")
    
    # Test "week"
    _, _, _, _ = parse_prompt_to_plan("week in Ella")


def test_parse_place_keywords():
    """Test parsing different place keywords."""
    test_cases = [
        ("kandy", "ChIJkandy"),
        ("colombo", "ChIJcolombo"),
        ("galle", "ChIJgalle"),
        ("unknown place", "ChIJbase")  # Default
    ]
    
    for place_keyword, expected_place_id in test_cases:
        prompt = f"3 days in {place_keyword}"
        trip_context, _, _, _ = parse_prompt_to_plan(prompt)
        assert trip_context.base_place_id == expected_place_id


def test_parse_budget_levels():
    """Test parsing different budget levels."""
    test_cases = [
        ("tight budget", 80),
        ("cheap", 80),
        ("low budget", 80),
        ("medium budget", 120),
        ("high budget", 200),
        ("luxury", 200),
        ("no budget mentioned", 120)  # Default
    ]
    
    for budget_keyword, expected_budget in test_cases:
        prompt = f"3 days in Kandy, {budget_keyword}"
        _, _, constraints, _ = parse_prompt_to_plan(prompt)
        assert constraints.daily_budget_cap == expected_budget


def test_parse_pace_preferences():
    """Test parsing different pace preferences."""
    test_cases = [
        ("chill", "light"),
        ("easy", "light"),
        ("relaxed", "light"),
        ("packed", "intense"),
        ("full schedule", "intense"),
        ("busy", "intense"),
        ("no pace mentioned", "moderate")  # Default
    ]
    
    for pace_keyword, expected_pace in test_cases:
        prompt = f"3 days in Kandy, {pace_keyword}"
        trip_context, _, _, _ = parse_prompt_to_plan(prompt)
        assert trip_context.day_template.pace == expected_pace


def test_parse_preferences():
    """Test parsing themes, activity tags, and avoid tags."""
    prompt = "3 days in Kandy, love temples and culture, hiking and photography, avoid nightlife and crowded places"
    
    _, preferences, _, _ = parse_prompt_to_plan(prompt)
    
    # Check themes
    assert "Culture" in preferences.themes
    
    # Check activity tags
    assert "Hiking" in preferences.activity_tags
    assert "Photography" in preferences.activity_tags
    
    # Check avoid tags
    assert "nightlife" in preferences.avoid_tags
    assert "crowded" in preferences.avoid_tags


def test_parse_complex_prompt():
    """Test parsing a complex prompt with multiple elements."""
    prompt = "5 days in Colombo, love food and beaches, hiking and swimming, avoid expensive and touristy places, medium budget, chill pace"
    
    trip_context, preferences, constraints, locks = parse_prompt_to_plan(prompt)
    
    # Check all components
    assert trip_context.base_place_id == "ChIJcolombo"
    assert trip_context.day_template.pace == "light"
    
    assert "Food" in preferences.themes
    assert "Beach" in preferences.themes
    assert "Hiking" in preferences.activity_tags
    assert "Swimming" in preferences.activity_tags
    assert "expensive" in preferences.avoid_tags
    assert "touristy" in preferences.avoid_tags
    
    assert constraints.daily_budget_cap == 120
    assert constraints.max_transfer_minutes == 90
    
    assert locks == []