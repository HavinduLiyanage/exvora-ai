#!/usr/bin/env python3

"""HTTP wrapper for Exvora Travel MCP Server"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .main import ExvoraTravelMCPServer


class ExvoraTravelHTTPServer:
    def __init__(self):
        self.app = FastAPI(
            title="Exvora Travel MCP Server",
            description="HTTP API wrapper for Exvora Travel MCP tools",
            version="1.0.0"
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
        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/")
        async def root():
            return {
                "name": "Exvora Travel MCP Server", 
                "version": "1.0.0",
                "tools": await self.list_tools()
            }

        @self.app.get("/tools")
        async def list_tools():
            return await self.list_tools()

        @self.app.post("/tools/{tool_name}")
        async def call_tool(tool_name: str, arguments: Dict[str, Any]):
            try:
                # Call the MCP server method directly
                if tool_name == "search_pois":
                    result = await self.mcp_server.poi_manager.search_pois(**arguments)
                elif tool_name == "get_poi_details":
                    result = await self.mcp_server.poi_manager.get_poi_details(**arguments)
                elif tool_name == "validate_dataset":
                    result = await self.mcp_server.data_validator.validate(**arguments)
                elif tool_name == "analyze_itinerary":
                    result = await self.mcp_server.itinerary_analyzer.analyze(**arguments)
                elif tool_name == "get_travel_insights":
                    result = await self.mcp_server.travel_insights.get_insights(**arguments)
                elif tool_name == "enrich_poi_google_places":
                    result = await self.mcp_server.enrich_poi_google_places(**arguments)
                elif tool_name == "search_google_places":
                    result = await self.mcp_server.search_google_places(**arguments)
                elif tool_name == "bulk_enrich_google_places":
                    result = await self.mcp_server.bulk_enrich_google_places(**arguments)
                elif tool_name == "run_candidate_analysis":
                    result = await self.mcp_server.run_candidate_analysis(**arguments)
                else:
                    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
                
                return {"result": result, "success": True}
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # Validation endpoint
        @self.app.post("/validate")
        async def validate_dataset(fix_issues: bool = False):
            try:
                result = await self.mcp_server.data_validator.validate(fix_issues=fix_issues)
                return {"result": result, "success": True}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # POI search endpoint  
        @self.app.get("/pois/search")
        async def search_pois(
            themes: str = None,
            tags: str = None, 
            price_band: str = None,
            region: str = None,
            limit: int = 10
        ):
            try:
                args = {"limit": limit}
                if themes:
                    args["themes"] = themes.split(",")
                if tags:
                    args["tags"] = tags.split(",") 
                if price_band:
                    args["price_band"] = price_band
                if region:
                    args["region"] = region
                    
                result = await self.mcp_server.poi_manager.search_pois(**args)
                return {"result": result, "success": True}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    async def list_tools(self):
        return [
            "search_pois",
            "get_poi_details", 
            "validate_dataset",
            "analyze_itinerary",
            "get_travel_insights",
            "enrich_poi_google_places",
            "search_google_places",
            "bulk_enrich_google_places",
            "run_candidate_analysis"
        ]

def start_http_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the HTTP server"""
    server = ExvoraTravelHTTPServer()
    uvicorn.run(server.app, host=host, port=port)

if __name__ == "__main__":
    start_http_server()