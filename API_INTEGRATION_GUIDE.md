# 🔑 API Integration Guide for Exvora AI

## Overview
This guide outlines the recommended APIs to enhance your Sri Lanka travel itinerary platform, prioritized by impact and implementation complexity.

## Phase 1: Essential APIs (Immediate Implementation)

### 1. Google Maps Platform ⭐⭐⭐⭐⭐
**Status**: ✅ Partially Integrated
```env
GOOGLE_MAPS_API_KEY=your_key_here
```

**Current Usage**: Distance Matrix API for transfers
**Additional APIs to implement**:
- **Places API**: Enhanced POI data, photos, reviews
- **Geocoding API**: Address to coordinates conversion
- **Static Maps API**: Itinerary route visualization

**Implementation Example**:
```python
# app/external/google_places.py
import googlemaps

class GooglePlacesService:
    def __init__(self, api_key):
        self.client = googlemaps.Client(key=api_key)
    
    def enrich_poi(self, place_id):
        result = self.client.place(place_id=place_id, fields=[
            'name', 'formatted_address', 'rating', 'photos',
            'opening_hours', 'price_level', 'reviews'
        ])
        return result['result']
```

### 2. OpenWeather API ⭐⭐⭐⭐
**Cost**: Free (1000 calls/day), $40/month for more
```env
OPENWEATHER_API_KEY=your_key_here
```

**Use Cases**:
- Weather-based activity filtering
- Seasonal recommendations
- Rain alerts for outdoor activities

**Implementation**:
```python
# app/external/weather.py
import requests

class WeatherService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"
    
    def get_weather_for_poi(self, lat, lng, date):
        url = f"{self.base_url}/forecast"
        params = {
            'lat': lat, 'lon': lng,
            'appid': self.api_key,
            'units': 'metric'
        }
        response = requests.get(url, params=params)
        return response.json()
    
    def filter_activities_by_weather(self, activities, weather_data):
        # Filter outdoor activities during rain
        pass
```

### 3. OpenAI API ⭐⭐⭐⭐⭐
**Cost**: $0.03/1K tokens (GPT-4)
```env
OPENAI_API_KEY=your_key_here
```

**Use Cases**:
- Intelligent POI descriptions
- Travel recommendation engine
- Natural language itinerary queries

**Integration Example**:
```python
# app/external/ai_insights.py
import openai

class AIInsightsService:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)
    
    def generate_poi_description(self, poi_data):
        prompt = f"""Generate an engaging travel description for:
        Name: {poi_data['name']}
        Themes: {', '.join(poi_data['themes'])}
        Location: {poi_data['region']}
        
        Make it informative and inspiring for travelers."""
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    
    def optimize_itinerary(self, itinerary, preferences):
        # AI-powered itinerary optimization
        pass
```

## Phase 2: Enhancement APIs

### 4. Amadeus Travel APIs ⭐⭐⭐⭐⭐
**Cost**: Free tier available, pay-per-use
```env
AMADEUS_CLIENT_ID=your_client_id
AMADEUS_CLIENT_SECRET=your_secret
```

**APIs to integrate**:
- **Activities & Experiences**: Bookable tours and activities
- **Hotel Search**: Accommodation recommendations
- **Flight Search**: Travel logistics

### 5. TripAdvisor Content API ⭐⭐⭐⭐
**Cost**: Contact for enterprise pricing
```env
TRIPADVISOR_API_KEY=your_key_here
```

**Benefits**:
- Rich POI reviews and ratings
- Professional photos
- Traveler insights

### 6. Foursquare Places API ⭐⭐⭐⭐
**Cost**: $0.50-2.00/1000 requests
```env
FOURSQUARE_API_KEY=your_key_here
```

**Use Cases**:
- Local business discovery
- Real-time popularity data
- Category-based search

## Phase 3: Advanced Integration

### 7. Unsplash API ⭐⭐⭐⭐
**Cost**: Free (50 requests/hour)
```env
UNSPLASH_ACCESS_KEY=your_key_here
```

**Implementation**:
```python
# app/external/photos.py
import requests

class PhotoService:
    def get_poi_photos(self, poi_name, location):
        query = f"{poi_name} {location} Sri Lanka"
        # Fetch high-quality photos for POIs
        pass
```

### 8. Grab/Uber APIs ⭐⭐⭐⭐
**Regional Focus**: Southeast Asia (Grab for Sri Lanka)
```env
GRAB_API_KEY=your_key_here
```

### 9. Currency Layer API ⭐⭐⭐
**Cost**: Free tier, $10+/month
```env
CURRENCY_API_KEY=your_key_here
```

**Replace current stub**:
```python
# Enhanced app/utils/currency.py
import requests

class CurrencyService:
    def get_live_rates(self, base_currency='LKR'):
        # Real-time currency conversion
        pass
```

## Implementation Strategy

### Week 1: Core Infrastructure
1. Set up API client classes in `app/external/`
2. Implement Google Places enhancement
3. Add weather-based filtering

### Week 2: AI Integration
1. Integrate OpenAI for POI descriptions
2. Add intelligent recommendations
3. Implement natural language queries

### Week 3: Data Enhancement
1. Add Amadeus activity data
2. Integrate photo services
3. Enhanced currency conversion

### Week 4: Advanced Features
1. Real-time transport options
2. Social proof (reviews/ratings)
3. Booking integrations

## Configuration Management

Create `app/config/api_config.py`:
```python
from pydantic import BaseSettings

class APISettings(BaseSettings):
    # Google
    google_maps_api_key: str = ""
    
    # Weather
    openweather_api_key: str = ""
    
    # AI
    openai_api_key: str = ""
    
    # Travel
    amadeus_client_id: str = ""
    amadeus_client_secret: str = ""
    
    # Media
    unsplash_access_key: str = ""
    
    class Config:
        env_file = ".env"

api_settings = APISettings()
```

## Rate Limiting & Caching

Implement robust caching for API calls:
```python
# app/external/cache.py
import redis
from functools import wraps
import json

class APICache:
    def __init__(self):
        self.redis_client = redis.Redis()
    
    def cache_api_call(self, ttl_seconds=3600):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
                cached = self.redis_client.get(cache_key)
                
                if cached:
                    return json.loads(cached)
                
                result = func(*args, **kwargs)
                self.redis_client.setex(
                    cache_key, ttl_seconds, json.dumps(result)
                )
                return result
            return wrapper
        return decorator
```

## Monitoring & Analytics

Track API usage and costs:
```python
# app/external/monitoring.py
class APIMonitor:
    def track_api_call(self, service, endpoint, cost=0):
        # Log API usage for billing and optimization
        pass
    
    def get_usage_report(self):
        # Generate API usage reports
        pass
```

## Security Best Practices

1. **API Key Management**: Use environment variables
2. **Rate Limiting**: Implement per-service limits
3. **Error Handling**: Graceful degradation
4. **Monitoring**: Track usage and costs
5. **Caching**: Reduce API calls and costs

## Expected Impact

### Performance Improvements
- **Better POI Data**: Rich descriptions, photos, reviews
- **Weather Intelligence**: Smart activity filtering
- **AI Recommendations**: Personalized suggestions

### User Experience
- **Visual Itineraries**: Maps and photos
- **Real-time Data**: Weather, transport, pricing
- **Social Proof**: Reviews and ratings

### Business Value
- **Reduced Costs**: Smart caching and rate limiting
- **Increased Engagement**: Rich, personalized content
- **Scalability**: Robust API infrastructure

## Getting Started

1. **Sign up for API keys** from priority providers
2. **Update environment variables** in `.env`
3. **Install additional dependencies**:
   ```bash
   pip install googlemaps openai amadeus redis
   ```
4. **Implement Phase 1 APIs** following the examples above
5. **Test with MCP server** to validate integration

## Cost Estimation

**Monthly costs for moderate usage (10,000 itineraries)**:
- Google Maps: $50-100
- OpenWeather: $40
- OpenAI: $100-200
- Amadeus: $50-100
- **Total**: $240-440/month

**ROI**: Enhanced user experience, better conversion rates, premium feature differentiation.