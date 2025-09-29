"""Google Places API client for Exvora MCP Server"""

import asyncio
import aiohttp
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import time


@dataclass
class GooglePlace:
    place_id: str
    name: str
    rating: Optional[float]
    user_ratings_total: int
    price_level: Optional[int]
    formatted_address: str
    phone: Optional[str]
    website: Optional[str]
    opening_hours: Optional[Dict[str, Any]]
    photos: List[str]
    reviews: List[Dict[str, Any]]
    types: List[str]


class GooglePlacesClient:
    """Google Places API client with free tier optimization"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request with caching"""
        
        # Generate cache key
        cache_key = f"{endpoint}:{str(sorted(params.items()))}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data
        
        # Add API key to params
        params['key'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        
        if not self.session:
            raise RuntimeError("Google Places client not initialized. Use 'async with' context.")
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Cache successful response
                    self.cache[cache_key] = (data, time.time())
                    return data
                else:
                    error_text = await response.text()
                    raise Exception(f"Google Places API error {response.status}: {error_text}")
        
        except aiohttp.ClientError as e:
            raise Exception(f"Google Places API connection error: {str(e)}")

    async def search_places(
        self, 
        query: str, 
        lat: Optional[float] = None, 
        lng: Optional[float] = None,
        radius: int = 10000,  # meters
        limit: int = 10
    ) -> List[GooglePlace]:
        """Search for places by text query and/or location"""
        
        if lat is not None and lng is not None:
            # Use Nearby Search for location-based queries
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'keyword': query,
                'type': 'tourist_attraction|point_of_interest'
            }
            endpoint = '/place/nearbysearch/json'
        else:
            # Use Text Search for name-based queries
            params = {
                'query': query,
                'type': 'tourist_attraction|point_of_interest'
            }
            endpoint = '/place/textsearch/json'
        
        try:
            response = await self._make_request(endpoint, params)
            
            places = []
            results = response.get('results', [])[:limit]
            
            for result in results:
                place = await self._parse_place_basic(result)
                if place:
                    places.append(place)
            
            return places
            
        except Exception as e:
            raise Exception(f"Failed to search Google Places: {str(e)}")

    async def get_place_details(self, place_id: str, include_reviews: bool = True) -> Optional[GooglePlace]:
        """Get detailed information about a specific place"""
        
        fields = [
            'place_id', 'name', 'rating', 'user_ratings_total', 
            'price_level', 'formatted_address', 'formatted_phone_number',
            'website', 'opening_hours', 'photos', 'types'
        ]
        
        if include_reviews:
            fields.append('reviews')
        
        params = {
            'place_id': place_id,
            'fields': ','.join(fields)
        }
        
        try:
            response = await self._make_request('/place/details/json', params)
            
            if 'result' in response:
                return await self._parse_place_detailed(response['result'])
            return None
            
        except Exception as e:
            raise Exception(f"Failed to get Google Places details: {str(e)}")

    async def get_place_photos(self, photo_references: List[str], max_width: int = 800) -> List[str]:
        """Get photo URLs from photo references"""
        
        photo_urls = []
        
        for photo_ref in photo_references[:5]:  # Limit to 5 photos for free tier
            try:
                params = {
                    'photo_reference': photo_ref,
                    'maxwidth': max_width
                }
                
                url = f"{self.base_url}/place/photo"
                # Photo API returns the image directly, we want the URL
                photo_url = f"{url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}&key={self.api_key}"
                photo_urls.append(photo_url)
                
            except Exception as e:
                print(f"Error getting photo URL: {e}")
                continue
        
        return photo_urls

    async def _parse_place_basic(self, result: Dict[str, Any]) -> Optional[GooglePlace]:
        """Parse basic place data from search results"""
        
        try:
            place_id = result.get('place_id')
            if not place_id:
                return None
            
            # Get photo URLs
            photos = []
            if 'photos' in result:
                photo_refs = [p['photo_reference'] for p in result['photos'][:3]]
                photos = await self.get_place_photos(photo_refs)
            
            return GooglePlace(
                place_id=place_id,
                name=result.get('name', ''),
                rating=result.get('rating'),
                user_ratings_total=result.get('user_ratings_total', 0),
                price_level=result.get('price_level'),
                formatted_address=result.get('formatted_address', ''),
                phone=None,  # Not available in search results
                website=None,  # Not available in search results
                opening_hours=result.get('opening_hours'),
                photos=photos,
                reviews=[],  # Not available in search results
                types=result.get('types', [])
            )
            
        except Exception as e:
            print(f"Error parsing basic place data: {e}")
            return None

    async def _parse_place_detailed(self, result: Dict[str, Any]) -> Optional[GooglePlace]:
        """Parse detailed place data from place details"""
        
        try:
            place_id = result.get('place_id')
            if not place_id:
                return None
            
            # Get photo URLs
            photos = []
            if 'photos' in result:
                photo_refs = [p['photo_reference'] for p in result['photos'][:5]]
                photos = await self.get_place_photos(photo_refs)
            
            # Parse reviews
            reviews = []
            for review in result.get('reviews', [])[:5]:  # Limit to 5 reviews
                review_data = {
                    'author_name': review.get('author_name', 'Anonymous'),
                    'rating': review.get('rating'),
                    'text': review.get('text', ''),
                    'time': review.get('time'),
                    'relative_time_description': review.get('relative_time_description', ''),
                    'author_url': review.get('author_url', '')
                }
                reviews.append(review_data)
            
            return GooglePlace(
                place_id=place_id,
                name=result.get('name', ''),
                rating=result.get('rating'),
                user_ratings_total=result.get('user_ratings_total', 0),
                price_level=result.get('price_level'),
                formatted_address=result.get('formatted_address', ''),
                phone=result.get('formatted_phone_number'),
                website=result.get('website'),
                opening_hours=result.get('opening_hours'),
                photos=photos,
                reviews=reviews,
                types=result.get('types', [])
            )
            
        except Exception as e:
            print(f"Error parsing detailed place data: {e}")
            return None

    async def enrich_poi_with_google_places(self, poi: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a POI with Google Places data"""
        
        enriched_poi = poi.copy()
        
        try:
            # Search for the POI on Google Places
            search_query = poi.get('name', '')
            coords = poi.get('coords', {})
            lat = coords.get('lat')
            lng = coords.get('lng')
            
            if not search_query:
                return enriched_poi
            
            places = await self.search_places(
                query=search_query,
                lat=lat,
                lng=lng,
                radius=2000,  # 2km radius
                limit=3
            )
            
            if not places:
                return enriched_poi
            
            # Use the first (most relevant) result
            google_place = places[0]
            
            # Get additional details
            detailed_place = await self.get_place_details(google_place.place_id, include_reviews=True)
            if detailed_place:
                google_place = detailed_place
            
            # Enrich POI data
            enriched_poi['google_places'] = {
                'place_id': google_place.place_id,
                'rating': google_place.rating,
                'user_ratings_total': google_place.user_ratings_total,
                'price_level': google_place.price_level,
                'formatted_address': google_place.formatted_address,
                'phone': google_place.phone,
                'website': google_place.website,
                'opening_hours': google_place.opening_hours,
                'photos': google_place.photos,
                'reviews': google_place.reviews,
                'types': google_place.types
            }
            
            # Update POI description if empty and we have reviews
            if not poi.get('description') and google_place.reviews:
                # Use the most helpful review as description
                best_review = max(google_place.reviews, key=lambda r: r.get('rating', 0))
                if best_review.get('text'):
                    enriched_poi['description'] = best_review['text'][:300] + ('...' if len(best_review['text']) > 300 else '')
            
            # Add Google rating to metadata
            if google_place.rating:
                enriched_poi['google_rating'] = google_place.rating
                enriched_poi['google_reviews'] = google_place.user_ratings_total
            
            # Update price band based on Google price level
            if google_place.price_level is not None and not poi.get('price_band'):
                price_map = {0: 'low', 1: 'low', 2: 'medium', 3: 'medium', 4: 'high'}
                enriched_poi['price_band'] = price_map.get(google_place.price_level, 'medium')
            
            return enriched_poi
            
        except Exception as e:
            # Return original POI if enrichment fails
            print(f"Failed to enrich POI {poi.get('name', 'Unknown')} with Google Places: {e}")
            return enriched_poi

    async def get_poi_reviews_summary(self, poi: Dict[str, Any], review_limit: int = 10) -> str:
        """Get a formatted summary of Google reviews for a POI"""
        
        try:
            # First enrich to get Google Places data
            enriched_poi = await self.enrich_poi_with_google_places(poi)
            google_data = enriched_poi.get('google_places', {})
            
            if not google_data.get('place_id'):
                return "No Google Places reviews found for this POI."
            
            # Get detailed reviews
            detailed_place = await self.get_place_details(google_data['place_id'], include_reviews=True)
            
            if not detailed_place or not detailed_place.reviews:
                return "No reviews available on Google Places."
            
            # Format summary
            summary = f"# ⭐ Google Places Reviews for {poi.get('name', 'POI')}\n\n"
            
            if google_data.get('rating'):
                summary += f"**Overall Rating:** {google_data['rating']}/5 ({google_data.get('user_ratings_total', 0)} reviews)\n\n"
            
            summary += "## Recent Reviews\n\n"
            
            for i, review in enumerate(detailed_place.reviews[:review_limit], 1):
                summary += f"### Review {i}\n"
                summary += f"**Rating:** {review['rating']}/5\n"
                summary += f"**Author:** {review['author_name']}\n"
                
                if review['text']:
                    # Truncate long reviews
                    text = review['text'][:300]
                    if len(review['text']) > 300:
                        text += "..."
                    summary += f"**Review:** {text}\n"
                
                if review['relative_time_description']:
                    summary += f"**Posted:** {review['relative_time_description']}\n"
                
                summary += "\n"
            
            return summary
            
        except Exception as e:
            return f"Error retrieving Google Places reviews: {str(e)}"