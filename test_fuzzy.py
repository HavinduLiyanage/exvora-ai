"""Test fuzzy matching in prefilter"""
from app.engine.candidates import prefilter_by_themes_tags

# Mock POIs with "Nature" theme
pois = [
    {"name": "POI 1", "themes": ["Nature"], "tags": ["Wildlife"]},
    {"name": "POI 2", "themes": ["Cultural"], "tags": ["Temple"]},
    {"name": "POI 3", "themes": ["Nature"], "tags": []},
]

# Request with different theme names
preferences = {
    "themes": ["Nature & Wildlife", "National Parks & Safaris"],
    "activity_tags": ["Temple Visits"]
}

filtered = prefilter_by_themes_tags(pois, preferences)

print(f"Original POIs: {len(pois)}")
print(f"Filtered POIs: {len(filtered)}")
print("\nFiltered results:")
for poi in filtered:
    print(f"  - {poi['name']}: themes={poi['themes']}, tags={poi['tags']}")

# Test with no match at all
preferences_no_match = {
    "themes": ["Beach", "Mountains"],
    "activity_tags": ["Scuba Diving"]
}

filtered_no_match = prefilter_by_themes_tags(pois, preferences_no_match)
print(f"\nNo match test: {len(filtered_no_match)} POIs (should be {len(pois)} - fallback)")
