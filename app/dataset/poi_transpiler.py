import csv
import json
import requests
import time
import sys


API_KEY = "AIzaSyCFFx6WaPoAS3EO5Auo1D1wY5FcFAhLMms"

def get_coordinates(place_name):
    """Fetch latitude and longitude for a place using Google Maps Geocoding API."""
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": place_name + ", Sri Lanka", "key": API_KEY}
    response = requests.get(base_url, params=params)
    data = response.json()
    if data["status"] == "OK":
        location = data["results"][0]["geometry"]["location"]
        place_id = data["results"][0]["place_id"]
        return location, place_id
    else:
        print(f"\nCould not get coordinates for {place_name}: {data['status']}")
        return None, None

def spinner():
    """Simple loader spinner."""
    while True:
        for cursor in '|/-\\':
            yield cursor

def convert_csv_to_json(csv_file_path, json_file_path):
    """Convert CSV tourist spots to structured JSON with coordinates and show loader."""
    output_data = []
    spin = spinner()
    seen_names = set()  # Track unique names

    with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        total = sum(1 for _ in open(csv_file_path)) - 1  # Total rows minus header
        csvfile.seek(0)
        next(reader)  # Skip header

        for idx, row in enumerate(reader, start=1):
            name = row["Name"].strip()
            category = row["Category"]
            province = row["Province"]

            # Skip duplicate names
            name_key = name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            coords, place_id = get_coordinates(name)
            time.sleep(0.1)
            if coords is None:
                continue

            # Generate poi_id safely
            poi_id = name.lower().replace(" ", "_").replace(",", "").replace("'", "")

            json_entry = {
                "poi_id": poi_id,
                "place_id": place_id,
                "name": name,
                "coords": {"lat": coords["lat"], "lng": coords["lng"]},
                "tags": [category],
                "themes": ["Nature" if category in ["Beach", "Nature & Wildlife", "Hill Country"] else "Cultural"],
                "price_band": "low",
                "estimated_cost": 5,
                "opening_hours": {
                    "mon": [{"open": "06:00", "close": "19:00"}],
                    "tue": [{"open": "06:00", "close": "19:00"}],
                    "wed": [{"open": "06:00", "close": "19:00"}],
                    "thu": [{"open": "06:00", "close": "19:00"}],
                    "fri": [{"open": "06:00", "close": "19:00"}],
                    "sat": [{"open": "06:00", "close": "19:00"}],
                    "sun": [{"open": "06:00", "close": "19:00"}]
                },
                "seasonality": ["All"],
                "duration_minutes": 120,
                "safety_flags": [],
                "region": province
            }

            output_data.append(json_entry)

            # Display loader
            sys.stdout.write(f"\rProcessing {idx}/{total} {next(spin)}")
            sys.stdout.flush()

    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(output_data)} unique tourist spots to {json_file_path}")


# Example usage
convert_csv_to_json(
    "/Users/cubo2022/Desktop/Github/exvora-ai/app/dataset/sri_lanka_tourist_spots.csv",
    "/Users/cubo2022/Desktop/Github/exvora-ai/app/dataset/sri_lanka_tourist_hey_spots.json"
)
