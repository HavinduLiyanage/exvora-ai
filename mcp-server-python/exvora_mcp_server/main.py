#!/usr/bin/env python3

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl

from .poi_manager import POIManager
from .itinerary_analyzer import ItineraryAnalyzer
from .travel_insights import TravelInsights
from .data_validator import DataValidator
from .tripadvisor_client import TripAdvisorClient
from .google_places_client import GooglePlacesClient


class ExvoraTravelMCPServer:
    def __init__(self):
        self.server = Server("exvora-travel-mcp-server")
        
        # Initialize components - use existing Exvora app structure
        self.data_path = Path(__file__).parent.parent.parent / "app" / "dataset"
        self.poi_manager = POIManager(self.data_path)
        self.itinerary_analyzer = ItineraryAnalyzer(self.poi_manager)
        self.travel_insights = TravelInsights(self.poi_manager)
        self.data_validator = DataValidator(self.poi_manager)
        
        # External API integrations (require API keys from environment)
        import os
        self.tripadvisor_api_key = os.getenv('TRIPADVISOR_API_KEY')
        self.tripadvisor_client = None
        
        self.google_places_api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        self.google_places_client = None
        
        self.setup_handlers()

    def setup_handlers(self):
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name="search_pois",
                    description="Search Points of Interest in the Sri Lanka dataset by themes, tags, location, or price range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "themes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by themes (Cultural, Nature, Adventure, Food, etc.)"
                            },
                            "tags": {
                                "type": "array", 
                                "items": {"type": "string"},
                                "description": "Filter by activity tags"
                            },
                            "price_band": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "description": "Filter by price range"
                            },
                            "region": {
                                "type": "string",
                                "description": "Filter by region/area"
                            },
                            "max_cost": {
                                "type": "number",
                                "description": "Maximum estimated cost"
                            },
                            "limit": {
                                "type": "number",
                                "default": 10,
                                "description": "Maximum number of results to return"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="get_poi_details",
                    description="Get detailed information about a specific POI by ID or place_id",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "poi_id": {
                                "type": "string",
                                "description": "The POI ID to lookup"
                            },
                            "place_id": {
                                "type": "string", 
                                "description": "The Google Place ID to lookup"
                            }
                        },
                        "required": ["poi_id"]
                    }
                ),
                types.Tool(
                    name="add_poi",
                    description="Add a new Point of Interest to the dataset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "poi_id": {"type": "string", "description": "Unique POI identifier"},
                            "place_id": {"type": "string", "description": "Google Place ID"},
                            "name": {"type": "string", "description": "POI name"},
                            "coords": {
                                "type": "object",
                                "properties": {
                                    "lat": {"type": "number"},
                                    "lng": {"type": "number"}
                                },
                                "required": ["lat", "lng"]
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Activity tags"
                            },
                            "themes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Thematic categories"
                            },
                            "price_band": {
                                "type": "string",
                                "enum": ["low", "medium", "high"]
                            },
                            "estimated_cost": {"type": "number"},
                            "duration_minutes": {"type": "number"},
                            "region": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["poi_id", "name", "coords", "tags", "themes", "price_band"]
                    }
                ),
                types.Tool(
                    name="analyze_itinerary",
                    description="Analyze an itinerary for insights like cost breakdown, time distribution, theme balance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "itinerary": {
                                "type": "object",
                                "description": "Itinerary response object from Exvora API"
                            }
                        },
                        "required": ["itinerary"]
                    }
                ),
                types.Tool(
                    name="get_travel_insights",
                    description="Get travel insights and recommendations for Sri Lanka",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "region": {"type": "string", "description": "Specific region to focus on"},
                            "season": {"type": "string", "description": "Travel season (wet/dry/peak)"},
                            "budget_range": {"type": "string", "enum": ["budget", "mid-range", "luxury"]},
                            "interests": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Traveler interests"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="validate_dataset",
                    description="Validate the POI dataset for completeness and consistency",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "fix_issues": {
                                "type": "boolean",
                                "default": False,
                                "description": "Attempt to automatically fix validation issues"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="export_poi_data",
                    description="Export POI data in various formats (JSON, CSV, GeoJSON)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "format": {
                                "type": "string",
                                "enum": ["json", "csv", "geojson"],
                                "default": "json"
                            },
                            "filter": {
                                "type": "object",
                                "description": "Optional filters to apply before export"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="run_candidate_analysis",
                    description="Run the Exvora candidate generation engine on POI dataset",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "preferences": {
                                "type": "object",
                                "description": "User preferences for filtering"
                            },
                            "date": {"type": "string", "description": "Date for analysis (YYYY-MM-DD)"},
                            "base_place_id": {"type": "string", "description": "Starting location"},
                            "pace": {"type": "string", "enum": ["light", "moderate", "intense"]},
                            "radius_km": {"type": "number", "description": "Search radius in km"}
                        },
                        "required": ["date", "base_place_id", "pace"]
                    }
                ),
                types.Tool(
                    name="enrich_poi_tripadvisor",
                    description="Enrich a POI with TripAdvisor data (ratings, reviews, photos)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "poi_id": {"type": "string", "description": "POI ID to enrich"},
                            "include_reviews": {"type": "boolean", "default": True, "description": "Include review summary"},
                            "review_limit": {"type": "number", "default": 5, "description": "Number of reviews to include"}
                        },
                        "required": ["poi_id"]
                    }
                ),
                types.Tool(
                    name="search_tripadvisor",
                    description="Search TripAdvisor for locations near coordinates or by name",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_query": {"type": "string", "description": "Search term (attraction name, etc.)"},
                            "lat": {"type": "number", "description": "Latitude for location-based search"},
                            "lng": {"type": "number", "description": "Longitude for location-based search"},
                            "radius": {"type": "number", "default": 10000, "description": "Search radius in meters"},
                            "limit": {"type": "number", "default": 10, "description": "Maximum results"}
                        },
                        "required": ["search_query"]
                    }
                ),
                types.Tool(
                    name="bulk_enrich_dataset",
                    description="Enrich entire POI dataset with TripAdvisor data",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "save_results": {"type": "boolean", "default": False, "description": "Save enriched data back to dataset"},
                            "max_pois": {"type": "number", "default": 10, "description": "Maximum POIs to process (rate limiting)"},
                            "include_reviews": {"type": "boolean", "default": False, "description": "Include review summaries"}
                        }
                    }
                ),
                types.Tool(
                    name="get_tripadvisor_reviews",
                    description="Get detailed TripAdvisor reviews for a POI",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "poi_id": {"type": "string", "description": "POI ID to get reviews for"},
                            "limit": {"type": "number", "default": 10, "description": "Number of reviews to retrieve"},
                            "sort_order": {"type": "string", "enum": ["most_recent", "highest_rated", "lowest_rated"], "default": "most_recent"}
                        },
                        "required": ["poi_id"]
                    }
                ),
                types.Tool(
                    name="enrich_poi_google_places",
                    description="Enrich a POI with Google Places data (FREE - ratings, reviews, photos)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "poi_id": {"type": "string", "description": "POI ID to enrich"},
                            "include_reviews": {"type": "boolean", "default": True, "description": "Include review summary"},
                            "review_limit": {"type": "number", "default": 5, "description": "Number of reviews to include"}
                        },
                        "required": ["poi_id"]
                    }
                ),
                types.Tool(
                    name="search_google_places",
                    description="Search Google Places for locations (FREE tier available)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_query": {"type": "string", "description": "Search term (attraction name, etc.)"},
                            "lat": {"type": "number", "description": "Latitude for location-based search"},
                            "lng": {"type": "number", "description": "Longitude for location-based search"},
                            "radius": {"type": "number", "default": 10000, "description": "Search radius in meters"},
                            "limit": {"type": "number", "default": 10, "description": "Maximum results"}
                        },
                        "required": ["search_query"]
                    }
                ),
                types.Tool(
                    name="bulk_enrich_google_places",
                    description="Enrich entire POI dataset with Google Places data (FREE tier optimized)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "save_results": {"type": "boolean", "default": False, "description": "Save enriched data back to dataset"},
                            "max_pois": {"type": "number", "default": 10, "description": "Maximum POIs to process (free tier limit)"},
                            "include_reviews": {"type": "boolean", "default": False, "description": "Include review summaries"}
                        }
                    }
                ),
                types.Tool(
                    name="get_google_places_reviews",
                    description="Get detailed Google Places reviews for a POI (FREE)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "poi_id": {"type": "string", "description": "POI ID to get reviews for"},
                            "limit": {"type": "number", "default": 5, "description": "Number of reviews to retrieve"}
                        },
                        "required": ["poi_id"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            try:
                if name == "search_pois":
                    result = await self.poi_manager.search_pois(**arguments)
                elif name == "get_poi_details":
                    result = await self.poi_manager.get_poi_details(**arguments)
                elif name == "add_poi":
                    result = await self.poi_manager.add_poi(**arguments)
                elif name == "analyze_itinerary":
                    result = await self.itinerary_analyzer.analyze(**arguments)
                elif name == "get_travel_insights":
                    result = await self.travel_insights.get_insights(**arguments)
                elif name == "validate_dataset":
                    result = await self.data_validator.validate(**arguments)
                elif name == "export_poi_data":
                    result = await self.poi_manager.export_data(**arguments)
                elif name == "run_candidate_analysis":
                    result = await self.run_candidate_analysis(**arguments)
                elif name == "enrich_poi_tripadvisor":
                    result = await self.enrich_poi_tripadvisor(**arguments)
                elif name == "search_tripadvisor":
                    result = await self.search_tripadvisor(**arguments)
                elif name == "bulk_enrich_dataset":
                    result = await self.bulk_enrich_dataset(**arguments)
                elif name == "get_tripadvisor_reviews":
                    result = await self.get_tripadvisor_reviews(**arguments)
                elif name == "enrich_poi_google_places":
                    result = await self.enrich_poi_google_places(**arguments)
                elif name == "search_google_places":
                    result = await self.search_google_places(**arguments)
                elif name == "bulk_enrich_google_places":
                    result = await self.bulk_enrich_google_places(**arguments)
                elif name == "get_google_places_reviews":
                    result = await self.get_google_places_reviews(**arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [types.TextContent(type="text", text=result)]
                
            except Exception as e:
                error_msg = f"Error executing {name}: {str(e)}"
                return [types.TextContent(type="text", text=error_msg)]

    async def run_candidate_analysis(self, **kwargs) -> str:
        """Run Exvora's candidate generation engine directly from MCP"""
        try:
            # Import Exvora's engine modules
            import sys
            exvora_path = self.data_path.parent
            if str(exvora_path) not in sys.path:
                sys.path.insert(0, str(exvora_path))
            
            from app.engine.candidates import basic_candidates
            from app.dataset.loader import load_pois
            
            # Load POIs using Exvora's loader
            pois = load_pois()
            
            # Extract parameters
            preferences = kwargs.get('preferences', {})
            date = kwargs['date']
            base_place_id = kwargs['base_place_id']
            pace = kwargs['pace']
            radius_km = kwargs.get('radius_km')
            
            # Create day window (simplified for analysis)
            day_window = {"start": "08:00", "end": "20:00"}
            
            # Run candidate generation
            candidates, reasons = basic_candidates(
                pois=pois,
                prefs=preferences,
                date_str=date,
                day_window=day_window,
                base_place_id=base_place_id,
                pace=pace,
                radius_km=radius_km
            )
            
            # Format results
            result = f"# 🎯 Candidate Analysis Results\n\n"
            result += f"**Date:** {date}\n"
            result += f"**Base Location:** {base_place_id}\n"
            result += f"**Pace:** {pace}\n"
            result += f"**Candidates Found:** {len(candidates)}\n\n"
            
            if reasons:
                result += "## Filtering Reasons\n"
                for reason, count in reasons.items():
                    result += f"- **{reason}:** {count} POIs filtered\n"
                result += "\n"
            
            result += "## Top Candidates\n"
            for i, candidate in enumerate(candidates[:10], 1):
                result += f"{i}. **{candidate.get('name', 'Unknown')}** "
                result += f"({candidate.get('poi_id', 'No ID')})\n"
                result += f"   - Themes: {', '.join(candidate.get('themes', []))}\n"
                result += f"   - Cost: {candidate.get('estimated_cost', 0)} LKR\n"
                result += f"   - Duration: {candidate.get('duration_minutes', 'N/A')} min\n\n"
            
            return result
            
        except Exception as e:
            return f"Error running candidate analysis: {str(e)}"

    async def _ensure_tripadvisor_client(self):
        """Ensure TripAdvisor client is initialized"""
        if not self.tripadvisor_api_key:
            raise ValueError("TripAdvisor API key not found. Set TRIPADVISOR_API_KEY environment variable.")
        
        if not self.tripadvisor_client:
            self.tripadvisor_client = TripAdvisorClient(self.tripadvisor_api_key)

    async def enrich_poi_tripadvisor(self, poi_id: str, include_reviews: bool = True, review_limit: int = 5) -> str:
        """Enrich a single POI with TripAdvisor data"""
        await self._ensure_tripadvisor_client()
        
        # Get POI from dataset
        pois = await self.poi_manager.load_pois()
        poi = None
        for p in pois:
            if p.get('poi_id') == poi_id:
                poi = p
                break
        
        if not poi:
            return f"POI with ID '{poi_id}' not found in dataset."
        
        async with self.tripadvisor_client:
            # Enrich POI
            enriched_poi = await self.tripadvisor_client.enrich_poi_with_tripadvisor(poi)
            
            # Format response
            result = f"# 🌟 TripAdvisor Enrichment for {poi.get('name', 'Unknown POI')}\n\n"
            
            ta_data = enriched_poi.get('tripadvisor', {})
            if ta_data:
                result += f"## Enrichment Successful\n"
                result += f"- **TripAdvisor ID:** {ta_data.get('location_id', 'N/A')}\n"
                result += f"- **Rating:** {ta_data.get('rating', 'N/A')}/5\n"
                result += f"- **Reviews:** {ta_data.get('num_reviews', 0)}\n"
                result += f"- **Ranking:** {ta_data.get('ranking', 'N/A')}\n"
                result += f"- **Price Level:** {ta_data.get('price_level', 'N/A')}\n"
                
                if ta_data.get('description'):
                    result += f"\n**Description:** {ta_data['description'][:300]}{'...' if len(ta_data.get('description', '')) > 300 else ''}\n"
                
                if ta_data.get('amenities'):
                    result += f"\n**Amenities:** {', '.join(ta_data['amenities'][:5])}\n"
                
                if ta_data.get('photo_url'):
                    result += f"\n**Photo:** {ta_data['photo_url']}\n"
                
                # Include review summary if requested
                if include_reviews and ta_data.get('location_id'):
                    review_summary = await self.tripadvisor_client.get_poi_reviews_summary(poi, review_limit)
                    result += f"\n{review_summary}\n"
                
                result += f"\n## Enhanced POI Data\n```json\n{json.dumps(enriched_poi, indent=2, ensure_ascii=False)}\n```"
            else:
                result += f"## No TripAdvisor Data Found\n"
                result += f"Could not find matching location on TripAdvisor for '{poi.get('name', 'Unknown')}'.\n"
                result += f"This could be due to:\n"
                result += f"- Name variations between datasets\n"
                result += f"- Location not listed on TripAdvisor\n"
                result += f"- Coordinate mismatch\n"
            
            return result

    async def search_tripadvisor(
        self, 
        search_query: str, 
        lat: Optional[float] = None, 
        lng: Optional[float] = None,
        radius: int = 10000,
        limit: int = 10
    ) -> str:
        """Search TripAdvisor for locations"""
        await self._ensure_tripadvisor_client()
        
        async with self.tripadvisor_client:
            locations = await self.tripadvisor_client.search_locations(
                search_query=search_query,
                lat=lat,
                lng=lng,
                radius=radius,
                limit=limit
            )
            
            result = f"# 🔍 TripAdvisor Search Results\n\n"
            result += f"**Query:** {search_query}\n"
            if lat is not None and lng is not None:
                result += f"**Location:** {lat}, {lng} (radius: {radius}m)\n"
            result += f"**Results:** {len(locations)}\n\n"
            
            if not locations:
                result += "No locations found matching your search criteria.\n"
                return result
            
            for i, location in enumerate(locations, 1):
                result += f"## {i}. {location.name}\n"
                result += f"- **TripAdvisor ID:** {location.location_id}\n"
                result += f"- **Rating:** {location.rating or 'N/A'}/5 ({location.num_reviews} reviews)\n"
                result += f"- **Address:** {location.address}\n"
                
                if location.ranking:
                    result += f"- **Ranking:** {location.ranking}\n"
                
                if location.price_level:
                    result += f"- **Price Level:** {location.price_level}\n"
                
                if location.description:
                    desc = location.description[:200]
                    if len(location.description) > 200:
                        desc += "..."
                    result += f"- **Description:** {desc}\n"
                
                if location.amenities:
                    result += f"- **Amenities:** {', '.join(location.amenities[:3])}\n"
                
                if location.photo_url:
                    result += f"- **Photo:** {location.photo_url}\n"
                
                result += "\n"
            
            return result

    async def bulk_enrich_dataset(
        self, 
        save_results: bool = False, 
        max_pois: int = 10, 
        include_reviews: bool = False
    ) -> str:
        """Enrich multiple POIs with TripAdvisor data"""
        await self._ensure_tripadvisor_client()
        
        pois = await self.poi_manager.load_pois()
        
        # Limit processing for rate limiting
        process_pois = pois[:max_pois]
        
        result = f"# 🚀 Bulk TripAdvisor Enrichment\n\n"
        result += f"**Total POIs in dataset:** {len(pois)}\n"
        result += f"**Processing:** {len(process_pois)} POIs\n"
        result += f"**Save results:** {'Yes' if save_results else 'No'}\n\n"
        
        enriched_pois = []
        success_count = 0
        error_count = 0
        
        async with self.tripadvisor_client:
            for i, poi in enumerate(process_pois, 1):
                poi_name = poi.get('name', f'POI #{i}')
                result += f"**{i}/{len(process_pois)}** Processing: {poi_name}... "
                
                try:
                    enriched_poi = await self.tripadvisor_client.enrich_poi_with_tripadvisor(poi)
                    
                    if enriched_poi.get('tripadvisor'):
                        ta_data = enriched_poi['tripadvisor']
                        result += f"✅ Found! Rating: {ta_data.get('rating', 'N/A')}/5, Reviews: {ta_data.get('num_reviews', 0)}\n"
                        success_count += 1
                    else:
                        result += f"❌ Not found on TripAdvisor\n"
                        error_count += 1
                    
                    enriched_pois.append(enriched_poi)
                    
                    # Rate limiting delay
                    if i < len(process_pois):
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    result += f"❌ Error: {str(e)}\n"
                    enriched_pois.append(poi)  # Keep original POI
                    error_count += 1
        
        # Save results if requested
        if save_results and success_count > 0:
            try:
                # Update the processed POIs in the original dataset
                for i, enriched_poi in enumerate(enriched_pois):
                    pois[i] = enriched_poi
                
                await self.poi_manager.save_pois(pois)
                result += f"\n✅ **Saved {success_count} enriched POIs to dataset**\n"
            except Exception as e:
                result += f"\n❌ **Error saving to dataset:** {str(e)}\n"
        
        # Summary
        result += f"\n## Summary\n"
        result += f"- **Successful:** {success_count}/{len(process_pois)}\n"
        result += f"- **Failed:** {error_count}/{len(process_pois)}\n"
        result += f"- **Success Rate:** {(success_count/len(process_pois)*100):.1f}%\n"
        
        if success_count > 0:
            result += f"\n## Enhanced POIs\n"
            for poi in enriched_pois:
                if poi.get('tripadvisor'):
                    ta_data = poi['tripadvisor']
                    result += f"- **{poi.get('name')}:** {ta_data.get('rating', 'N/A')}/5 ({ta_data.get('num_reviews', 0)} reviews)\n"
        
        return result

    async def get_tripadvisor_reviews(
        self, 
        poi_id: str, 
        limit: int = 10, 
        sort_order: str = "most_recent"
    ) -> str:
        """Get detailed TripAdvisor reviews for a POI"""
        await self._ensure_tripadvisor_client()
        
        # Get POI from dataset
        pois = await self.poi_manager.load_pois()
        poi = None
        for p in pois:
            if p.get('poi_id') == poi_id:
                poi = p
                break
        
        if not poi:
            return f"POI with ID '{poi_id}' not found in dataset."
        
        async with self.tripadvisor_client:
            return await self.tripadvisor_client.get_poi_reviews_summary(poi, limit)

    async def _ensure_google_places_client(self):
        """Ensure Google Places client is initialized"""
        if not self.google_places_api_key:
            raise ValueError("Google Places API key not found. Set GOOGLE_PLACES_API_KEY environment variable.")
        
        if not self.google_places_client:
            self.google_places_client = GooglePlacesClient(self.google_places_api_key)

    async def enrich_poi_google_places(self, poi_id: str, include_reviews: bool = True, review_limit: int = 5) -> str:
        """Enrich a single POI with Google Places data"""
        await self._ensure_google_places_client()
        
        # Get POI from dataset
        pois = await self.poi_manager.load_pois()
        poi = None
        for p in pois:
            if p.get('poi_id') == poi_id:
                poi = p
                break
        
        if not poi:
            return f"POI with ID '{poi_id}' not found in dataset."
        
        async with self.google_places_client:
            # Enrich POI
            enriched_poi = await self.google_places_client.enrich_poi_with_google_places(poi)
            
            # Format response
            result = f"# ⭐ Google Places Enrichment for {poi.get('name', 'Unknown POI')}\n\n"
            
            google_data = enriched_poi.get('google_places', {})
            if google_data:
                result += f"## Enrichment Successful ✅ (FREE)\n"
                result += f"- **Google Place ID:** {google_data.get('place_id', 'N/A')}\n"
                result += f"- **Rating:** {google_data.get('rating', 'N/A')}/5\n"
                result += f"- **Reviews:** {google_data.get('user_ratings_total', 0)}\n"
                result += f"- **Price Level:** {google_data.get('price_level', 'N/A')}/4\n"
                result += f"- **Address:** {google_data.get('formatted_address', 'N/A')}\n"
                
                if google_data.get('phone'):
                    result += f"- **Phone:** {google_data['phone']}\n"
                
                if google_data.get('website'):
                    result += f"- **Website:** {google_data['website']}\n"
                
                if google_data.get('types'):
                    result += f"- **Categories:** {', '.join(google_data['types'][:3])}\n"
                
                if google_data.get('photos'):
                    result += f"\n**Photos ({len(google_data['photos'])}):**\n"
                    for i, photo_url in enumerate(google_data['photos'][:3], 1):
                        result += f"{i}. {photo_url}\n"
                
                # Include review summary if requested
                if include_reviews and google_data.get('reviews'):
                    result += f"\n## Recent Reviews\n"
                    for i, review in enumerate(google_data['reviews'][:review_limit], 1):
                        result += f"\n### Review {i}\n"
                        result += f"- **Rating:** {review['rating']}/5\n"
                        result += f"- **Author:** {review['author_name']}\n"
                        if review['text']:
                            text = review['text'][:200] + ('...' if len(review['text']) > 200 else '')
                            result += f"- **Review:** {text}\n"
                        if review['relative_time_description']:
                            result += f"- **Posted:** {review['relative_time_description']}\n"
                
                result += f"\n## Enhanced POI Data\n```json\n{json.dumps(enriched_poi, indent=2, ensure_ascii=False)[:1000]}...\n```"
            else:
                result += f"## No Google Places Data Found\n"
                result += f"Could not find matching location on Google Places for '{poi.get('name', 'Unknown')}'.\n"
                result += f"This could be due to:\n"
                result += f"- Name variations between datasets\n"
                result += f"- Location not verified on Google\n"
                result += f"- Coordinate mismatch\n"
            
            return result

    async def search_google_places(
        self, 
        search_query: str, 
        lat: Optional[float] = None, 
        lng: Optional[float] = None,
        radius: int = 10000,
        limit: int = 10
    ) -> str:
        """Search Google Places for locations"""
        await self._ensure_google_places_client()
        
        async with self.google_places_client:
            places = await self.google_places_client.search_places(
                query=search_query,
                lat=lat,
                lng=lng,
                radius=radius,
                limit=limit
            )
            
            result = f"# 🔍 Google Places Search Results (FREE)\n\n"
            result += f"**Query:** {search_query}\n"
            if lat is not None and lng is not None:
                result += f"**Location:** {lat}, {lng} (radius: {radius}m)\n"
            result += f"**Results:** {len(places)}\n\n"
            
            if not places:
                result += "No locations found matching your search criteria.\n"
                return result
            
            for i, place in enumerate(places, 1):
                result += f"## {i}. {place.name}\n"
                result += f"- **Google Place ID:** {place.place_id}\n"
                result += f"- **Rating:** {place.rating or 'N/A'}/5 ({place.user_ratings_total} reviews)\n"
                result += f"- **Address:** {place.formatted_address}\n"
                
                if place.price_level is not None:
                    result += f"- **Price Level:** {place.price_level}/4\n"
                
                if place.types:
                    result += f"- **Categories:** {', '.join(place.types[:3])}\n"
                
                if place.photos:
                    result += f"- **Photos:** {len(place.photos)} available\n"
                    result += f"- **Sample Photo:** {place.photos[0]}\n"
                
                result += "\n"
            
            return result

    async def bulk_enrich_google_places(
        self, 
        save_results: bool = False, 
        max_pois: int = 10, 
        include_reviews: bool = False
    ) -> str:
        """Enrich multiple POIs with Google Places data (FREE tier optimized)"""
        await self._ensure_google_places_client()
        
        pois = await self.poi_manager.load_pois()
        
        # Limit processing for free tier optimization
        process_pois = pois[:max_pois]
        
        result = f"# 🚀 Bulk Google Places Enrichment (FREE)\n\n"
        result += f"**Total POIs in dataset:** {len(pois)}\n"
        result += f"**Processing:** {len(process_pois)} POIs\n"
        result += f"**Save results:** {'Yes' if save_results else 'No'}\n"
        result += f"**Free tier optimized:** ✅\n\n"
        
        enriched_pois = []
        success_count = 0
        error_count = 0
        
        async with self.google_places_client:
            for i, poi in enumerate(process_pois, 1):
                poi_name = poi.get('name', f'POI #{i}')
                result += f"**{i}/{len(process_pois)}** Processing: {poi_name}... "
                
                try:
                    enriched_poi = await self.google_places_client.enrich_poi_with_google_places(poi)
                    
                    if enriched_poi.get('google_places'):
                        google_data = enriched_poi['google_places']
                        result += f"✅ Found! Rating: {google_data.get('rating', 'N/A')}/5, Reviews: {google_data.get('user_ratings_total', 0)}\n"
                        success_count += 1
                    else:
                        result += f"❌ Not found on Google Places\n"
                        error_count += 1
                    
                    enriched_pois.append(enriched_poi)
                    
                    # Small delay to be respectful to free tier
                    if i < len(process_pois):
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    result += f"❌ Error: {str(e)}\n"
                    enriched_pois.append(poi)  # Keep original POI
                    error_count += 1
        
        # Save results if requested
        if save_results and success_count > 0:
            try:
                # Update the processed POIs in the original dataset
                for i, enriched_poi in enumerate(enriched_pois):
                    pois[i] = enriched_poi
                
                await self.poi_manager.save_pois(pois)
                result += f"\n✅ **Saved {success_count} enriched POIs to dataset**\n"
            except Exception as e:
                result += f"\n❌ **Error saving to dataset:** {str(e)}\n"
        
        # Summary
        result += f"\n## Summary\n"
        result += f"- **Successful:** {success_count}/{len(process_pois)}\n"
        result += f"- **Failed:** {error_count}/{len(process_pois)}\n"
        result += f"- **Success Rate:** {(success_count/len(process_pois)*100):.1f}%\n"
        result += f"- **API Cost:** FREE (within Google's $200/month credit)\n"
        
        if success_count > 0:
            result += f"\n## Enhanced POIs\n"
            for poi in enriched_pois:
                if poi.get('google_places'):
                    google_data = poi['google_places']
                    result += f"- **{poi.get('name')}:** {google_data.get('rating', 'N/A')}/5 ({google_data.get('user_ratings_total', 0)} reviews)\n"
        
        return result

    async def get_google_places_reviews(self, poi_id: str, limit: int = 5) -> str:
        """Get detailed Google Places reviews for a POI"""
        await self._ensure_google_places_client()
        
        # Get POI from dataset
        pois = await self.poi_manager.load_pois()
        poi = None
        for p in pois:
            if p.get('poi_id') == poi_id:
                poi = p
                break
        
        if not poi:
            return f"POI with ID '{poi_id}' not found in dataset."
        
        async with self.google_places_client:
            return await self.google_places_client.get_poi_reviews_summary(poi, limit)

    async def run(self):
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                NotificationOptions()
            )


def main():
    """Entry point for the MCP server"""
    asyncio.run(ExvoraTravelMCPServer().run())


if __name__ == "__main__":
    main()