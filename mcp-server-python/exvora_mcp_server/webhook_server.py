#!/usr/bin/env python3

"""Webhook server for Exvora Travel MCP Server"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .main import ExvoraTravelMCPServer


class ExvoraWebhookServer:
    def __init__(self):
        self.app = FastAPI(
            title="Exvora Travel API",
            description="Travel POI management and analysis webhook API",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.mcp_server = ExvoraTravelMCPServer()
        self.setup_webhook_routes()

    def setup_webhook_routes(self):
        @self.app.get("/")
        async def root():
            return {
                "name": "Exvora Travel API",
                "version": "1.0.0",
                "description": "Travel POI management and analysis",
                "endpoints": {
                    "validate": "POST /validate - Validate POI dataset",
                    "search": "GET /search - Search POIs",
                    "details": "GET /poi/{poi_id} - Get POI details", 
                    "insights": "GET /insights - Get travel insights",
                    "analyze": "POST /analyze - Analyze itinerary",
                    "enrich": "POST /enrich/{poi_id} - Enrich with Google Places"
                },
                "docs": "Visit /docs for interactive API documentation"
            }

        @self.app.post("/validate")
        async def validate_dataset(fix_issues: bool = Query(False, description="Automatically fix issues")):
            """Validate the POI dataset and return quality report"""
            try:
                result = await self.mcp_server.data_validator.validate(fix_issues=fix_issues)
                return {
                    "success": True,
                    "report": result,
                    "message": "Dataset validation completed"
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/search")
        async def search_pois(
            themes: str = Query(None, description="Comma-separated themes (Cultural,Nature,Adventure)"),
            tags: str = Query(None, description="Comma-separated tags"),
            price_band: str = Query(None, description="Price band: low, medium, high"),
            region: str = Query(None, description="Region name"),
            limit: int = Query(10, description="Maximum results")
        ):
            """Search POIs with filters"""
            try:
                args = {"limit": limit}
                if themes:
                    args["themes"] = [t.strip() for t in themes.split(",")]
                if tags:
                    args["tags"] = [t.strip() for t in tags.split(",")]
                if price_band:
                    args["price_band"] = price_band
                if region:
                    args["region"] = region
                    
                result = await self.mcp_server.poi_manager.search_pois(**args)
                return {
                    "success": True,
                    "data": result,
                    "query": args
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/poi/{poi_id}")
        async def get_poi_details(poi_id: str):
            """Get detailed information about a specific POI"""
            try:
                result = await self.mcp_server.poi_manager.get_poi_details(poi_id=poi_id)
                return {
                    "success": True,
                    "poi_id": poi_id,
                    "data": result
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/insights")
        async def get_travel_insights(
            region: str = Query(None, description="Region to focus on"),
            season: str = Query(None, description="Travel season (wet/dry/peak)"),
            budget_range: str = Query(None, description="Budget range (budget/mid-range/luxury)"),
            interests: str = Query(None, description="Comma-separated interests")
        ):
            """Get travel insights and recommendations"""
            try:
                args = {}
                if region:
                    args["region"] = region
                if season:
                    args["season"] = season
                if budget_range:
                    args["budget_range"] = budget_range
                if interests:
                    args["interests"] = [i.strip() for i in interests.split(",")]
                    
                result = await self.mcp_server.travel_insights.get_insights(**args)
                return {
                    "success": True,
                    "insights": result,
                    "query": args
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/analyze")
        async def analyze_itinerary(request: Request):
            """Analyze an itinerary for insights"""
            try:
                body = await request.json()
                itinerary = body.get("itinerary")
                if not itinerary:
                    raise HTTPException(status_code=400, detail="Missing 'itinerary' in request body")
                
                result = await self.mcp_server.itinerary_analyzer.analyze(itinerary=itinerary)
                return {
                    "success": True,
                    "analysis": result
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/enrich/{poi_id}")
        async def enrich_poi_google_places(
            poi_id: str,
            include_reviews: bool = Query(True, description="Include Google reviews")
        ):
            """Enrich a POI with Google Places data (FREE)"""
            try:
                # Check if Google Places API key is available
                if not self.mcp_server.google_places_api_key:
                    return {
                        "success": False,
                        "message": "Google Places API key not configured. This is a FREE service - get key from console.cloud.google.com",
                        "poi_id": poi_id
                    }
                
                result = await self.mcp_server.enrich_poi_google_places(
                    poi_id=poi_id,
                    include_reviews=include_reviews
                )
                return {
                    "success": True,
                    "poi_id": poi_id,
                    "enrichment": result
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/enrich/bulk")
        async def bulk_enrich_google_places(
            max_pois: int = Query(10, description="Maximum POIs to process"),
            save_results: bool = Query(False, description="Save enriched data back to dataset")
        ):
            """Bulk enrich POIs with Google Places data (FREE tier optimized)"""
            try:
                if not self.mcp_server.google_places_api_key:
                    return {
                        "success": False,
                        "message": "Google Places API key not configured. Get FREE key from console.cloud.google.com"
                    }
                
                result = await self.mcp_server.bulk_enrich_google_places(
                    max_pois=max_pois,
                    save_results=save_results
                )
                return {
                    "success": True,
                    "bulk_enrichment": result
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/candidates")
        async def run_candidate_analysis(
            date: str = Query(..., description="Date for analysis (YYYY-MM-DD)"),
            base_place_id: str = Query(..., description="Starting location place ID"),
            pace: str = Query(..., description="Pace: light, moderate, intense"),
            radius_km: float = Query(None, description="Search radius in km")
        ):
            """Run Exvora's candidate generation engine"""
            try:
                args = {
                    "date": date,
                    "base_place_id": base_place_id,
                    "pace": pace
                }
                if radius_km:
                    args["radius_km"] = radius_km
                    
                result = await self.mcp_server.run_candidate_analysis(**args)
                return {
                    "success": True,
                    "candidates": result,
                    "query": args
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "service": "Exvora Travel API",
                "version": "1.0.0"
            }

def start_webhook_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the webhook server"""
    server = ExvoraWebhookServer()
    print(f"🌐 Starting Exvora Travel Webhook Server")
    print(f"📡 Server URL: http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"🔍 Quick test: http://{host}:{port}/search?themes=Cultural")
    uvicorn.run(server.app, host=host, port=port)

if __name__ == "__main__":
    start_webhook_server()