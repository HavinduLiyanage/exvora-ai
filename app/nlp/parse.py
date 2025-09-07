"""
Natural Language Processing module for parsing user prompts into structured plan components.
"""
from typing import Tuple, List
import re
from datetime import datetime, timedelta
from app.schemas.models import TripContext, TripDateRange, DayTemplate, Preferences, Constraints, Lock


def parse_prompt_to_plan(prompt: str) -> Tuple[TripContext, Preferences, Constraints, List[Lock]]:
    """
    Parse natural language prompt into structured plan components.
    
    Rules (very simple keyword parse):
    - Detect city/region keywords → set base_place_id to a placeholder like "ChIJbase" (leave TODO to resolve real place_id)
    - Detect durations like "3 days" → date_range = [today .. today+2]
    - Detect likes: "hike(s)/hiking" → activity_tags+=["Hiking"]; "temple(s)/culture" → themes+=["Culture"]; "food/street food" → themes+=["Food"]
    - Detect avoid: "avoid crowded/nightlife" → avoid_tags
    - Detect budget: "tight/cheap/low" → constraints.daily_budget_cap ~ 80; "medium" ~ 120; "high" ~ 200
    - Pace: "chill/easy"→"light", "packed/full"→"intense", else "moderate"
    
    Returns minimal, valid objects.
    """
    prompt_lower = prompt.lower()
    
    # 1. Extract duration (e.g., "3 days", "5 days", "week")
    duration_days = _extract_duration(prompt_lower)
    
    # 2. Extract base place (simple keyword matching)
    base_place_id = _extract_base_place(prompt_lower)
    
    # 3. Extract preferences
    themes, activity_tags, avoid_tags = _extract_preferences(prompt_lower)
    
    # 4. Extract budget level
    daily_budget_cap = _extract_budget(prompt_lower)
    
    # 5. Extract pace preference
    pace = _extract_pace(prompt_lower)
    
    # 6. Create date range (today + duration)
    today = datetime.now().date()
    end_date = today + timedelta(days=duration_days - 1)
    
    # 7. Build objects
    trip_context = TripContext(
        base_place_id=base_place_id,
        date_range=TripDateRange(
            start=today.isoformat(),
            end=end_date.isoformat()
        ),
        day_template=DayTemplate(
            start="08:30",
            end="20:00",
            pace=pace
        ),
        modes=["DRIVE", "WALK"]
    )
    
    preferences = Preferences(
        themes=themes,
        activity_tags=activity_tags,
        avoid_tags=avoid_tags
    )
    
    constraints = Constraints(
        daily_budget_cap=daily_budget_cap,
        max_transfer_minutes=90
    )
    
    locks = []  # No locks from prompt parsing
    
    return trip_context, preferences, constraints, locks


def _extract_duration(prompt: str) -> int:
    """Extract trip duration in days from prompt."""
    # Look for patterns like "3 days", "5 days", "week", "weekend"
    day_patterns = [
        (r'(\d+)\s*days?', lambda m: int(m.group(1))),
        (r'weekend', lambda m: 2),
        (r'week', lambda m: 7),
        (r'long weekend', lambda m: 3),
    ]
    
    for pattern, extractor in day_patterns:
        match = re.search(pattern, prompt)
        if match:
            days = extractor(match)
            return max(1, min(days, 14))  # Clamp between 1-14 days
    
    return 3  # Default to 3 days


def _extract_base_place(prompt: str) -> str:
    """Extract base place ID from prompt (placeholder for now)."""
    # Simple keyword matching for common places
    place_keywords = {
        'kandy': 'ChIJkandy',
        'colombo': 'ChIJcolombo', 
        'galle': 'ChIJgalle',
        'anuradhapura': 'ChIJanuradhapura',
        'sigiriya': 'ChIJsigiriya',
        'negombo': 'ChIJnegombo',
        'bentota': 'ChIJbentota',
        'ella': 'ChIJella',
        'nuwara eliya': 'ChIJnuwara',
        'polonnaruwa': 'ChIJpolonnaruwa'
    }
    
    for keyword, place_id in place_keywords.items():
        if keyword in prompt:
            return place_id
    
    return "ChIJbase"  # Default placeholder


def _extract_preferences(prompt: str) -> Tuple[List[str], List[str], List[str]]:
    """Extract themes, activity_tags, and avoid_tags from prompt."""
    themes = []
    activity_tags = []
    avoid_tags = []
    
    # Theme keywords
    theme_keywords = {
        'culture': ['Culture'],
        'temple': ['Culture'],
        'temples': ['Culture'],
        'history': ['History'],
        'historical': ['History'],
        'nature': ['Nature'],
        'food': ['Food'],
        'street food': ['Food'],
        'cuisine': ['Food'],
        'beach': ['Beach'],
        'beaches': ['Beach'],
        'wildlife': ['Wildlife'],
        'adventure': ['Adventure']
    }
    
    # Activity tag keywords
    activity_keywords = {
        'hiking': ['Hiking'],
        'hike': ['Hiking'],
        'trekking': ['Hiking'],
        'walking': ['Walking'],
        'photography': ['Photography'],
        'shopping': ['Shopping'],
        'nightlife': ['Nightlife'],
        'dancing': ['Dancing'],
        'swimming': ['Swimming'],
        'surfing': ['Surfing']
    }
    
    # Avoid tag keywords
    avoid_keywords = {
        'crowded': ['crowded'],
        'busy': ['crowded'],
        'nightlife': ['nightlife'],
        'expensive': ['expensive'],
        'touristy': ['touristy']
    }
    
    # Check for themes
    for keyword, theme_list in theme_keywords.items():
        if keyword in prompt:
            themes.extend(theme_list)
    
    # Check for activity tags
    for keyword, tag_list in activity_keywords.items():
        if keyword in prompt:
            activity_tags.extend(tag_list)
    
    # Check for avoid tags
    for keyword, tag_list in avoid_keywords.items():
        if keyword in prompt:
            avoid_tags.extend(tag_list)
    
    # Remove duplicates
    themes = list(set(themes))
    activity_tags = list(set(activity_tags))
    avoid_tags = list(set(avoid_tags))
    
    return themes, activity_tags, avoid_tags


def _extract_budget(prompt: str) -> float:
    """Extract budget level from prompt."""
    # Check for specific budget phrases first (more specific)
    if any(phrase in prompt for phrase in ['medium budget', 'moderate budget']):
        return 120
    if any(phrase in prompt for phrase in ['high budget', 'luxury budget', 'expensive budget']):
        return 200
    if any(phrase in prompt for phrase in ['tight budget', 'cheap budget', 'low budget']):
        return 80
    
    # Then check for individual keywords
    budget_keywords = {
        'tight': 80,
        'cheap': 80,
        'low': 80,
        'medium': 120,
        'moderate': 120,
        'high': 200,
        'luxury': 200,
        'expensive': 200
    }
    
    for keyword, budget in budget_keywords.items():
        if keyword in prompt:
            return budget
    
    return 120  # Default medium budget


def _extract_pace(prompt: str) -> str:
    """Extract pace preference from prompt."""
    pace_keywords = {
        'chill': 'light',
        'easy': 'light',
        'relaxed': 'light',
        'slow': 'light',
        'packed': 'intense',
        'full': 'intense',
        'busy': 'intense',
        'fast': 'intense'
    }
    
    for keyword, pace in pace_keywords.items():
        if keyword in prompt:
            return pace
    
    return 'moderate'  # Default pace