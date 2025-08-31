# Exvora AI - Stateless Itinerary API

An AI-powered travel companion for Sri Lanka that generates day-by-day itineraries with activities, transfers, and cost estimates.

## Features

- **Stateless API** for itinerary generation
- **Budget-aware planning** with daily spending constraints
- **Feedback loop** to repack days based on user actions
- **Sri Lankan POI dataset** with 45+ attractions
- **OpenAPI documentation** with Swagger UI
- **Production-ready** with Docker support

## Tech Stack

- **FastAPI** - Modern, fast web framework
- **Python 3.11+** - Latest Python features
- **Pydantic** - Data validation and serialization
- **Uvicorn** - ASGI server
- **Pytest** - Testing framework
- **Ruff & Black** - Code formatting and linting
- **Docker** - Containerization

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd exvora-ai
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   
   # On Windows
   .venv\Scripts\activate
   
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at:
- **API**: http://127.0.0.1:8000
- **Swagger Documentation**: http://127.0.0.1:8000/docs
- **ReDoc Documentation**: http://127.0.0.1:8000/redoc

## API Endpoints

### Health Check
```bash
GET /v1/healthz
```

### Generate Itinerary
```bash
POST /v1/itinerary
```

**Sample Request:**
```bash
curl -X POST http://127.0.0.1:8000/v1/itinerary \
  -H "Content-Type: application/json" \
  -d '{
    "trip_context": {
      "base_place_id": "ChIJbase...",
      "date_range": {
        "start": "2025-09-10",
        "end": "2025-09-14"
      },
      "day_template": {
        "start": "08:30",
        "end": "20:00",
        "pace": "moderate"
      },
      "modes": ["DRIVE", "WALK"]
    },
    "preferences": {
      "themes": ["Nature", "Food", "History"],
      "activity_tags": ["Hiking", "Local Cuisine"],
      "avoid_tags": ["nightlife"]
    },
    "constraints": {
      "daily_budget_cap": 120,
      "max_transfer_minutes": 90
    },
    "locks": []
  }'
```

### Feedback and Repack
```bash
POST /v1/itinerary/feedback
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_itinerary_api.py

# Run with coverage
pytest --cov=app tests/
```

## Development

### Code Quality

Format code:
```bash
black .
```

Lint code:
```bash
ruff check .
```

### Project Structure

```
exvora-ai/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration settings
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API endpoints
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── models.py        # Pydantic models
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── candidates.py    # POI filtering
│   │   ├── rules.py         # Hard constraints
│   │   ├── rank.py          # POI ranking
│   │   ├── schedule.py      # Day scheduling
│   │   └── transfers.py     # Transfer estimation
│   └── dataset/
│       ├── __init__.py
│       ├── loader.py        # Data loading utilities
│       └── pois.sample.json # Sri Lankan POI dataset
├── tests/
│   ├── __init__.py
│   ├── test_engine_core.py  # Engine unit tests
│   └── test_itinerary_api.py # API integration tests
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI/CD
├── Dockerfile               # Docker container definition
├── pyproject.toml          # Project metadata and tool config
├── requirements.txt        # Python dependencies
└── README.md
```

## Docker

### Build the image:
```bash
docker build -t exvora-ai .
```

### Run the container:
```bash
docker run -p 8080:8080 exvora-ai
```

The API will be available at http://localhost:8080

## API Response Examples

### Successful Itinerary Response:
```json
{
  "currency": "LKR",
  "days": [
    {
      "date": "2025-09-10",
      "summary": {
        "title": "Day Plan",
        "est_cost": 85.0,
        "health_load": "moderate"
      },
      "items": [
        {
          "start": "09:00",
          "end": "10:30",
          "place_id": "gangaramaya_temple",
          "title": "Gangaramaya Temple",
          "estimated_cost": 5.0
        },
        {
          "type": "transfer",
          "from_place_id": "gangaramaya_temple",
          "to_place_id": "temple_of_tooth",
          "mode": "DRIVE",
          "duration_minutes": 15,
          "distance_km": 3.0,
          "source": "heuristic"
        },
        {
          "start": "10:45",
          "end": "12:45",
          "place_id": "temple_of_tooth",
          "title": "Temple of the Sacred Tooth Relic",
          "estimated_cost": 10.0
        }
      ]
    }
  ]
}
```

## Configuration

Environment variables can be used to configure the application:

### Google Routes Integration

Set `USE_GOOGLE_ROUTES=true` and `GOOGLE_MAPS_API_KEY` to enable live ETAs via Google Distance Matrix.

**Environment Variables:**
- `USE_GOOGLE_ROUTES`: Enable Google Routes API (default: false)
- `GOOGLE_MAPS_API_KEY`: Your Google Maps API key (required when USE_GOOGLE_ROUTES=true)
- `TRANSFER_CACHE_TTL_SECONDS`: Cache TTL for transfer data (default: 600 seconds)
- `TRANSFER_MAX_CALLS_PER_REQUEST`: Max Google API calls per request (default: 30)

**Response Fields:**
Transfer responses remain the same but now include realistic data:
```json
{
  "type": "transfer",
  "duration_minutes": 25,
  "distance_km": 8.5,
  "source": "google_routes_live"
}
```

**Error Handling:**
- With Google enabled: Returns HTTP 424 on transfer verification failures
- With Google disabled: Always falls back to heuristic estimates
- Automatic fallback when API key is missing or invalid

**Caching & Limits:**
- Per-process cache keyed by (from, to, mode, 15-min bucket)
- Max Google calls per request controlled by `TRANSFER_MAX_CALLS_PER_REQUEST`
- Cache reduces repeat calls during itinerary generation

### General Settings
- `MAX_ITEMS_PER_DAY`: Maximum activities per day (default: 4)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

