# Exvora Travel MCP Server (Python)

A Model Context Protocol (MCP) server built in Python that provides advanced tools for managing travel data, POIs, and itinerary analysis for the Exvora AI travel platform.

## Why Python?

This MCP server is implemented in Python to seamlessly integrate with your existing Exvora AI codebase:

- **Direct Integration**: Uses your existing POI dataset at `app/dataset/pois.sample.json`
- **Code Reuse**: Leverages Exvora's engine modules (`app.engine.candidates`, etc.)
- **Consistent Dependencies**: Same libraries as your main app (Pydantic, FastAPI patterns)
- **Easy Extension**: Add new features using familiar Python ecosystem

## Features

### 🗺️ POI Management
- **Search POIs** - Advanced filtering by themes, tags, price, region
- **Get Details** - Comprehensive POI information with opening hours
- **Add POIs** - Expand dataset with validation and consistency checks

### 🌟 TripAdvisor Integration
- **Enrich POIs** - Add ratings, reviews, photos from TripAdvisor
- **Search TripAdvisor** - Find locations by name or coordinates
- **Bulk Enrichment** - Process entire dataset with rate limiting
- **Review Analysis** - Get detailed traveler feedback

### 📊 Analysis & Intelligence
- **Itinerary Analysis** - Deep dive into cost, themes, time distribution
- **Travel Insights** - Contextual recommendations for regions, seasons, budgets
- **Candidate Analysis** - Run Exvora's engine directly from MCP
- **Dataset Validation** - Quality checks with auto-fix capabilities

### 📤 Data Operations
- **Export Data** - JSON, CSV, GeoJSON formats with filtering
- **Bulk Operations** - Efficient dataset management
- **Direct File Access** - Works with your existing data files

## Installation

```bash
cd mcp-server-python
pip install -e .
```

### Dependencies
```bash
pip install mcp pydantic fastapi pandas geopy
```

## Usage

### Standalone
```bash
python -m exvora_mcp_server.main
```

### With Claude Desktop

Add to your Claude Desktop MCP configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "exvora-travel": {
      "command": "python",
      "args": ["-m", "exvora_mcp_server.main"],
      "cwd": "/path/to/exvora-ai/mcp-server-python"
    }
  }
}
```

Or using the installed script:

```json
{
  "mcpServers": {
    "exvora-travel": {
      "command": "exvora-mcp-server"
    }
  }
}
```

## Available Tools

### 🔍 search_pois
Search your POI dataset with advanced filters:
```python
{
  "themes": ["Cultural", "Nature"],
  "tags": ["Temple", "Hiking"], 
  "price_band": "low",
  "region": "Kandy",
  "max_cost": 100,
  "limit": 5
}
```

### 📋 get_poi_details
Get comprehensive information about any POI:
```python
{
  "poi_id": "temple_of_the_sacred_tooth_relic"
}
```

### ➕ add_poi
Add new POIs with full validation:
```python
{
  "poi_id": "new_viewpoint_ella",
  "name": "Little Adam's Peak Viewpoint",
  "coords": {"lat": 6.8665, "lng": 81.0456},
  "themes": ["Nature", "Adventure"],
  "tags": ["Hiking", "Views", "Photography"],
  "price_band": "low",
  "estimated_cost": 0,
  "region": "Ella"
}
```

### 📊 analyze_itinerary
Deep analysis of generated itineraries:
```python
{
  "itinerary": {
    "currency": "LKR",
    "days": [
      {
        "date": "2025-01-15",
        "summary": {"est_cost": 120},
        "items": [...]
      }
    ]
  }
}
```

**Analysis includes:**
- Cost breakdown and daily averages
- Theme distribution and balance
- Regional coverage analysis
- Time distribution patterns
- Activity duration statistics
- Recommendations for improvement

### 🌍 get_travel_insights
Contextual travel recommendations:
```python
{
  "region": "Kandy",
  "season": "dry",
  "budget_range": "mid-range",
  "interests": ["Culture", "Nature", "Food"]
}
```

**Insights include:**
- Regional POI analysis and recommendations
- Seasonal travel tips and best practices
- Budget-specific suggestions and price ranges
- Interest-based POI matching
- Transportation and cultural advice

### ✅ validate_dataset
Comprehensive dataset quality checking:
```python
{
  "fix_issues": true  # Auto-fix common issues
}
```

**Validation covers:**
- Required field presence
- Coordinate accuracy (Sri Lanka bounds)
- Enum value validation
- Data consistency checks
- Duplicate detection
- Cross-reference validation

### 📤 export_poi_data
Export in multiple formats with filtering:
```python
{
  "format": "geojson",
  "filter": {
    "themes": ["Cultural"],
    "price_band": "low"
  }
}
```

### 🎯 run_candidate_analysis
Run Exvora's engine directly from MCP:
```python
{
  "date": "2025-01-15",
  "base_place_id": "ChIJkWKWAR1T4zoRWo0CkE7wyHk",
  "pace": "moderate",
  "preferences": {
    "themes": ["Cultural", "Nature"],
    "avoid_tags": ["nightlife"]
  }
}
```

**Provides:**
- Filtered candidate POIs using Exvora's algorithm
- Filtering reason breakdown
- Candidate ranking and scoring
- Direct integration with your engine

### 🌟 enrich_poi_tripadvisor
Enhance POIs with TripAdvisor data:
```python
{
  "poi_id": "temple_of_the_sacred_tooth_relic",
  "include_reviews": true,
  "review_limit": 5
}
```

**Adds:**
- Ratings and review counts
- Professional photos
- Rich descriptions
- Amenities and features

### 🔍 search_tripadvisor
Search TripAdvisor locations:
```python
{
  "search_query": "Sigiriya Rock Fortress",
  "lat": 7.9570,
  "lng": 80.7603,
  "radius": 5000,
  "limit": 5
}
```

### 🚀 bulk_enrich_dataset
Enhance entire dataset with rate limiting:
```python
{
  "save_results": true,
  "max_pois": 20,
  "include_reviews": false
}
```

### 📝 get_tripadvisor_reviews
Get detailed reviews for analysis:
```python
{
  "poi_id": "temple_of_the_sacred_tooth_relic",
  "limit": 10,
  "sort_order": "most_recent"
}
```

## Integration with Exvora AI

### Direct Dataset Access
- Reads from `app/dataset/pois.sample.json`
- Writes updates back to your dataset
- Maintains data consistency with your app

### Engine Integration
```python
# The MCP server imports and uses your engine modules
from app.engine.candidates import basic_candidates
from app.dataset.loader import load_pois

# Run your algorithms directly
candidates, reasons = basic_candidates(
    pois=pois,
    prefs=preferences,
    date_str=date,
    day_window=day_window,
    base_place_id=base_place_id,
    pace=pace
)
```

### Schema Compatibility
- Uses same Pydantic patterns as your API
- Compatible with your existing data structures
- Consistent validation rules

## Development

### Project Structure
```
exvora_mcp_server/
├── __init__.py
├── main.py              # MCP server entry point
├── poi_manager.py       # POI CRUD operations
├── itinerary_analyzer.py # Analysis tools
├── travel_insights.py   # Recommendation engine
└── data_validator.py    # Quality assurance
```

### Adding New Tools

1. **Add tool definition** in `main.py`:
```python
types.Tool(
    name="your_new_tool",
    description="What it does",
    inputSchema={...}
)
```

2. **Implement handler**:
```python
elif name == "your_new_tool":
    result = await self.your_new_method(**arguments)
```

3. **Add method** to appropriate class or create new module

### Testing
```bash
# Run with your existing test data
python -m exvora_mcp_server.main

# Test specific functions
python -c "
from exvora_mcp_server.poi_manager import POIManager
import asyncio
poi_mgr = POIManager(Path('app/dataset'))
print(asyncio.run(poi_mgr.search_pois(themes=['Cultural'])))
"
```

## Use Cases

### 1. Content Management
- Add new POIs discovered through research
- Validate and clean existing dataset
- Export subsets for analysis or sharing

### 2. Quality Assurance
- Automated dataset validation
- Consistency checking across POIs
- Missing data identification and fixing

### 3. Analytics & Insights
- Analyze generated itineraries for patterns
- Compare different user preferences
- Regional and seasonal analysis

### 4. Development Support
- Test candidate generation algorithms
- Debug filtering and ranking logic
- Prototype new features with real data

### 5. Business Intelligence
- Travel trends and popular destinations
- Price analysis and recommendations
- User behavior insights from itineraries

## Performance

- **Fast startup**: Direct file access, no external dependencies
- **Memory efficient**: Loads data on-demand
- **Scalable**: Can handle datasets with thousands of POIs
- **Caching**: Reuses loaded data across tool calls

## Security & Best Practices

- **Data validation**: All inputs validated before processing
- **Error handling**: Graceful failure with informative messages
- **File safety**: Atomic writes, backup on modifications
- **Schema compliance**: Maintains Exvora data format standards

## Comparison: Python vs JavaScript

| Aspect | Python (This) | JavaScript (Previous) |
|--------|---------------|----------------------|
| **Integration** | ✅ Direct code reuse | ❌ External API calls |
| **Dependencies** | ✅ Same as main app | ❌ Separate node_modules |
| **Development** | ✅ Familiar ecosystem | ❌ Context switching |
| **Performance** | ✅ Direct file access | ❌ JSON over HTTP |
| **Maintenance** | ✅ Single codebase | ❌ Multiple runtimes |
| **Features** | ✅ Full engine access | ❌ Limited to exposed APIs |

The Python implementation provides much better integration with your existing Exvora AI platform while offering the same MCP functionality.