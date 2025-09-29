# 🚀 Exvora Travel MCP Server - Quick Start

## ✅ Installation Complete!

Dependencies have been installed in a virtual environment. You're ready to go!

## 🔑 Step 1: Get FREE API Keys

### Google Places API (Recommended - FREE)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable **Places API**
4. Go to **Credentials** → **Create API Key**
5. Copy your API key

### Optional: OpenWeather API (FREE)
1. Go to [OpenWeatherMap](https://openweathermap.org/api)
2. Sign up for free account
3. Get API key from dashboard

## 🔧 Step 2: Set Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit with your API keys
nano .env
```

**Or set directly:**
```bash
export GOOGLE_PLACES_API_KEY="your_key_here"
export OPENWEATHER_API_KEY="your_key_here"
```

## 🧪 Step 3: Test the Server

```bash
# Activate virtual environment
source venv/bin/activate

# Test server startup
python3 -m exvora_mcp_server.main
```

The server should start without errors and wait for MCP connections.

## 📱 Step 4: Add to Claude Desktop

Add this to your Claude Desktop configuration file:

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "exvora-travel": {
      "command": "python3",
      "args": ["-m", "exvora_mcp_server.main"],
      "cwd": "/Users/cubo2022/Desktop/Github/exvora-ai/mcp-server-python",
      "env": {
        "GOOGLE_PLACES_API_KEY": "your_google_places_api_key_here"
      }
    }
  }
}
```

**Alternative (using virtual environment):**
```json
{
  "mcpServers": {
    "exvora-travel": {
      "command": "/Users/cubo2022/Desktop/Github/exvora-ai/mcp-server-python/venv/bin/python",
      "args": ["-m", "exvora_mcp_server.main"],
      "cwd": "/Users/cubo2022/Desktop/Github/exvora-ai/mcp-server-python",
      "env": {
        "GOOGLE_PLACES_API_KEY": "your_google_places_api_key_here"
      }
    }
  }
}
```

## 🎯 Step 5: Test in Claude Desktop

Restart Claude Desktop and try these commands:

### Test Google Places (FREE)
```
Use the search_google_places tool to search for "Sigiriya Rock Fortress"
```

### Test POI Enrichment (FREE)
```
Use the enrich_poi_google_places tool with poi_id "temple_of_the_sacred_tooth_relic"
```

### Test Dataset Processing (FREE)
```
Use the bulk_enrich_google_places tool to enhance 5 POIs
```

## 🛠️ Available Tools

### 🆓 FREE Tools (Start Here!)
- `search_google_places` - Search locations on Google
- `enrich_poi_google_places` - Add ratings, reviews, photos
- `bulk_enrich_google_places` - Process multiple POIs
- `get_google_places_reviews` - Get detailed reviews

### 🗺️ Core POI Tools
- `search_pois` - Search your dataset
- `get_poi_details` - Get POI information
- `add_poi` - Add new locations
- `validate_dataset` - Check data quality

### 📊 Analysis Tools
- `analyze_itinerary` - Deep itinerary analysis
- `get_travel_insights` - Sri Lanka recommendations
- `run_candidate_analysis` - Test Exvora's engine

### 💰 Premium Tools (Requires API Keys)
- `enrich_poi_tripadvisor` - TripAdvisor integration
- `search_tripadvisor` - TripAdvisor search
- `bulk_enrich_dataset` - TripAdvisor bulk processing

## 💡 Pro Tips

### Free Tier Optimization
- **Google Places**: $200/month free = ~40,000 POI lookups
- **Batch processing**: Use `max_pois=10` to stay within limits
- **Smart caching**: Results cached for 1 hour automatically

### Cost Management
```bash
# Start with free tools only
export GOOGLE_PLACES_API_KEY="your_key"

# Add paid tools only when needed
export TRIPADVISOR_API_KEY="your_key"
```

### Development Workflow
```bash
# 1. Test with small batches
use bulk_enrich_google_places with max_pois=3

# 2. Validate results
use validate_dataset 

# 3. Scale up gradually
use bulk_enrich_google_places with max_pois=10, save_results=true
```

## 🔧 Troubleshooting

### Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Import Errors
```bash
# Make sure you're in the right directory
cd /Users/cubo2022/Desktop/Github/exvora-ai/mcp-server-python

# Activate virtual environment
source venv/bin/activate

# Test imports
python3 -c "import mcp; print('MCP OK')"
python3 -c "import aiohttp; print('aiohttp OK')"
```

### API Key Issues
```bash
# Check environment variables
echo $GOOGLE_PLACES_API_KEY

# Test API key
curl "https://maps.googleapis.com/maps/api/place/textsearch/json?query=temple&key=$GOOGLE_PLACES_API_KEY"
```

### Claude Desktop Connection
1. Check config file path: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Restart Claude Desktop completely
3. Check logs in Claude Desktop for error messages
4. Verify absolute paths in configuration

## 📈 Next Steps

1. **Start FREE**: Use Google Places for immediate data enhancement
2. **Analyze Results**: Use analysis tools to understand your data
3. **Scale Gradually**: Add more POIs as you grow
4. **Consider Premium**: TripAdvisor for specialized travel content
5. **Integrate with Exvora**: Use enhanced data in your main application

## 🎉 Success Metrics

✅ **Day 1**: MCP server running, Google Places working  
✅ **Week 1**: 50+ POIs enriched with ratings and reviews  
✅ **Month 1**: Full dataset enhanced, integrated with Exvora AI  
✅ **Month 2**: Premium APIs added, advanced analytics running

**You're all set!** The Exvora Travel MCP Server gives you powerful POI enrichment capabilities with both free and premium options.