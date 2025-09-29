"""TripAdvisor API client for Exvora MCP Server"""

import asyncio
import json
from typing import Any, Dict, List, Optional
import aiohttp
from dataclasses import dataclass
import time


@dataclass
class TripAdvisorLocation:
    location_id: str
    name: str
    rating: Optional[float]
    num_reviews: int
    ranking: Optional[str]
    price_level: Optional[str]
    address: str
    phone: Optional[str]
    website: Optional[str]
    description: Optional[str]
    photo_url: Optional[str]
    amenities: List[str]


class TripAdvisorClient:
    """TripAdvisor Content API client with rate limiting and caching"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.content.tripadvisor.com/api/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limit_delay = 1.0  # Seconds between requests
        self.last_request_time = 0
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make rate-limited API request with caching"""
        
        # Generate cache key
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data
        
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        
        # Add API key to params
        params['key'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        
        if not self.session:
            raise RuntimeError("TripAdvisor client not initialized. Use 'async with' context.")
        
        try:
            async with self.session.get(url, params=params) as response:
                self.last_request_time = time.time()
                
                if response.status == 200:
                    data = await response.json()
                    # Cache successful response
                    self.cache[cache_key] = (data, time.time())
                    return data
                elif response.status == 429:
                    # Rate limited - wait and retry once
                    await asyncio.sleep(5)
                    async with self.session.get(url, params=params) as retry_response:
                        if retry_response.status == 200:
                            data = await retry_response.json()
                            self.cache[cache_key] = (data, time.time())
                            return data
                        else:
                            raise Exception(f"TripAdvisor API error after retry: {retry_response.status}")
                else:
                    error_text = await response.text()
                    raise Exception(f"TripAdvisor API error {response.status}: {error_text}")
        
        except aiohttp.ClientError as e:
            raise Exception(f"TripAdvisor API connection error: {str(e)}")

    async def search_locations(
        self, 
        search_query: str, 
        lat: Optional[float] = None, 
        lng: Optional[float] = None,
        radius: int = 10000,  # meters
        limit: int = 10
    ) -> List[TripAdvisorLocation]:
        """Search for locations by name and/or coordinates"""
        
        params = {
            'searchQuery': search_query,
            'language': 'en'
        }
        
        # Add location-based search if coordinates provided
        if lat is not None and lng is not None:
            params.update({
                'latLong': f"{lat},{lng}",
                'radius': radius,
                'radiusUnit': 'meters'
            })
        
        try:
            response = await self._make_request('/location/search', params)
            
            locations = []
            for item in response.get('data', [])[:limit]:
                location = self._parse_location(item)
                if location:
                    locations.append(location)
            
            return locations
            
        except Exception as e:
            raise Exception(f"Failed to search TripAdvisor locations: {str(e)}")

    async def get_location_details(self, location_id: str) -> Optional[TripAdvisorLocation]:
        """Get detailed information about a specific location"""
        
        params = {
            'language': 'en'
        }
        
        try:
            response = await self._make_request(f'/location/{location_id}/details', params)
            
            if 'data' in response:
                return self._parse_location(response['data'])
            return None
            
        except Exception as e:
            raise Exception(f"Failed to get TripAdvisor location details: {str(e)}")

    async def get_location_photos(self, location_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """Get photos for a location"""
        
        params = {
            'language': 'en'
        }
        
        try:
            response = await self._make_request(f'/location/{location_id}/photos', params)
            
            photos = []
            for photo in response.get('data', [])[:limit]:
                if 'images' in photo:
                    # Get largest available image
                    image_sizes = photo['images']
                    if 'large' in image_sizes:
                        photo_data = {
                            'url': image_sizes['large']['url'],
                            'width': image_sizes['large']['width'],
                            'height': image_sizes['large']['height'],
                            'caption': photo.get('caption', '')
                        }
                        photos.append(photo_data)
            
            return photos
            
        except Exception as e:
            raise Exception(f"Failed to get TripAdvisor photos: {str(e)}")

    async def get_location_reviews(
        self, 
        location_id: str, 
        limit: int = 5,
        sort_order: str = 'most_recent'
    ) -> List[Dict[str, Any]]:
        """Get reviews for a location"""
        
        params = {
            'language': 'en',
            'sort': sort_order
        }
        
        try:
            response = await self._make_request(f'/location/{location_id}/reviews', params)
            
            reviews = []
            for review in response.get('data', [])[:limit]:
                review_data = {
                    'id': review.get('id'),
                    'rating': review.get('rating'),
                    'title': review.get('title', ''),
                    'text': review.get('text', ''),
                    'published_date': review.get('published_date'),
                    'user': {
                        'username': review.get('user', {}).get('username', 'Anonymous'),
                        'location': review.get('user', {}).get('user_location', {}).get('name', '')
                    },
                    'helpful_votes': review.get('helpful_votes', 0),
                    'language': review.get('language', 'en'),
                    'url': review.get('url', '')
                }
                reviews.append(review_data)
            
            return reviews
            
        except Exception as e:
            raise Exception(f"Failed to get TripAdvisor reviews: {str(e)}")

    def _parse_location(self, item: Dict[str, Any]) -> Optional[TripAdvisorLocation]:
        """Parse TripAdvisor API response into TripAdvisorLocation object"""
        
        try:
            location_id = item.get('location_id')
            if not location_id:
                return None
            
            # Extract address
            address_obj = item.get('address_obj', {})
            address_parts = []
            for field in ['street1', 'street2', 'city', 'state', 'country']:
                if address_obj.get(field):
                    address_parts.append(address_obj[field])
            address = ', '.join(address_parts)
            
            # Extract amenities/features
            amenities = []
            if 'amenities' in item:
                for amenity in item['amenities']:
                    if amenity.get('name'):
                        amenities.append(amenity['name'])
            
            # Extract photo URL
            photo_url = None
            if 'photo' in item and 'images' in item['photo']:
                images = item['photo']['images']
                if 'large' in images:
                    photo_url = images['large']['url']
                elif 'medium' in images:
                    photo_url = images['medium']['url']
                elif 'small' in images:
                    photo_url = images['small']['url']
            
            return TripAdvisorLocation(
                location_id=location_id,
                name=item.get('name', ''),
                rating=item.get('rating'),
                num_reviews=item.get('num_reviews', 0),
                ranking=item.get('ranking', ''),
                price_level=item.get('price_level'),
                address=address,
                phone=item.get('phone'),
                website=item.get('website'),
                description=item.get('description', ''),
                photo_url=photo_url,
                amenities=amenities
            )
            
        except Exception as e:
            print(f"Error parsing TripAdvisor location: {e}")
            return None

    async def enrich_poi_with_tripadvisor(self, poi: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a POI with TripAdvisor data"""
        
        enriched_poi = poi.copy()
        
        try:
            # Search for the POI on TripAdvisor
            search_query = poi.get('name', '')
            coords = poi.get('coords', {})
            lat = coords.get('lat')
            lng = coords.get('lng')
            
            if not search_query:
                return enriched_poi
            
            locations = await self.search_locations(
                search_query=search_query,
                lat=lat,
                lng=lng,
                radius=5000,  # 5km radius
                limit=3
            )
            
            if not locations:
                return enriched_poi
            
            # Use the first (most relevant) result
            ta_location = locations[0]
            
            # Get additional details
            detailed_location = await self.get_location_details(ta_location.location_id)
            if detailed_location:
                ta_location = detailed_location
            
            # Enrich POI data
            enriched_poi['tripadvisor'] = {
                'location_id': ta_location.location_id,
                'rating': ta_location.rating,
                'num_reviews': ta_location.num_reviews,
                'ranking': ta_location.ranking,
                'price_level': ta_location.price_level,
                'description': ta_location.description,
                'photo_url': ta_location.photo_url,
                'amenities': ta_location.amenities,
                'website': ta_location.website,
                'phone': ta_location.phone
            }
            
            # Update POI description if empty
            if not poi.get('description') and ta_location.description:
                enriched_poi['description'] = ta_location.description
            
            # Add TripAdvisor rating to metadata
            if ta_location.rating:
                enriched_poi['tripadvisor_rating'] = ta_location.rating
                enriched_poi['tripadvisor_reviews'] = ta_location.num_reviews
            
            return enriched_poi
            
        except Exception as e:
            # Return original POI if enrichment fails
            print(f"Failed to enrich POI {poi.get('name', 'Unknown')} with TripAdvisor: {e}")
            return enriched_poi

    async def get_poi_reviews_summary(self, poi: Dict[str, Any], review_limit: int = 10) -> str:
        """Get a formatted summary of reviews for a POI"""
        
        try:
            # First enrich to get TripAdvisor location ID
            enriched_poi = await self.enrich_poi_with_tripadvisor(poi)
            ta_data = enriched_poi.get('tripadvisor', {})
            
            if not ta_data.get('location_id'):
                return "No TripAdvisor reviews found for this POI."
            
            # Get reviews
            reviews = await self.get_location_reviews(
                ta_data['location_id'], 
                limit=review_limit
            )
            
            if not reviews:
                return "No reviews available on TripAdvisor."
            
            # Format summary
            summary = f"# 🌟 TripAdvisor Reviews for {poi.get('name', 'POI')}\n\n"
            
            if ta_data.get('rating'):
                summary += f"**Overall Rating:** {ta_data['rating']}/5 ({ta_data.get('num_reviews', 0)} reviews)\n\n"
            
            summary += "## Recent Reviews\n\n"
            
            for i, review in enumerate(reviews, 1):
                summary += f"### Review {i}\n"
                summary += f"**Rating:** {review['rating']}/5\n"
                
                if review['title']:
                    summary += f"**Title:** {review['title']}\n"
                
                if review['text']:
                    # Truncate long reviews
                    text = review['text'][:300]
                    if len(review['text']) > 300:
                        text += "..."
                    summary += f"**Review:** {text}\n"
                
                summary += f"**Author:** {review['user']['username']}"
                if review['user']['location']:
                    summary += f" ({review['user']['location']})"
                summary += "\n"
                
                if review['published_date']:
                    summary += f"**Date:** {review['published_date']}\n"
                
                summary += "\n"
            
            return summary
            
        except Exception as e:
            return f"Error retrieving TripAdvisor reviews: {str(e)}"