#!/usr/bin/env python3

"""MCP-over-HTTP server for Exvora Travel MCP Server"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .main import ExvoraTravelMCPServer


class ExvoraMCPHttpServer:
    def __init__(self):
        self.app = FastAPI(
            title="Exvora Travel MCP Server",
            description="MCP-over-HTTP server for Exvora Travel tools",
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
        self.setup_mcp_routes()

    def setup_mcp_routes(self):
        @self.app.post("/")
        async def handle_mcp_request(request: Request):
            """Handle MCP JSON-RPC requests"""
            try:
                body = await request.json()
                
                if body.get("method") == "tools/list":
                    return await self.list_tools(body)
                elif body.get("method") == "tools/call":
                    return await self.call_tool(body)
                elif body.get("method") == "initialize":
                    return await self.initialize(body)
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {body.get('method')}"
                        }
                    }
                    
            except Exception as e:
                return {
                    "jsonrpc": "2.0", 
                    "id": body.get("id") if "body" in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }

        @self.app.get("/")
        async def root():
            return {
                "name": "Exvora Travel MCP Server",
                "version": "1.0.0",
                "protocol": "mcp-over-http",
                "description": "Travel POI management and analysis tools"
            }

    async def initialize(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "exvora-travel-mcp-server",
                    "version": "1.0.0"
                }
            }
        }

    async def list_tools(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tools/list request"""
        tools = [
            {
                "name": "search_pois",
                "description": "Search Points of Interest in the Sri Lanka dataset by themes, tags, location, or price range",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "themes": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "price_band": {"type": "string", "enum": ["low", "medium", "high"]},
                        "region": {"type": "string"},
                        "limit": {"type": "number", "default": 10}
                    }
                }
            },
            {
                "name": "validate_dataset",
                "description": "Validate the POI dataset for completeness and consistency",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "fix_issues": {"type": "boolean", "default": False}
                    }
                }
            },
            {
                "name": "get_poi_details",
                "description": "Get detailed information about a specific POI by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "poi_id": {"type": "string"}
                    },
                    "required": ["poi_id"]
                }
            },
            {
                "name": "analyze_itinerary",
                "description": "Analyze an itinerary for insights like cost breakdown, time distribution, theme balance",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "itinerary": {"type": "object"}
                    },
                    "required": ["itinerary"]
                }
            },
            {
                "name": "get_travel_insights",
                "description": "Get travel insights and recommendations for Sri Lanka",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "region": {"type": "string"},
                        "season": {"type": "string"},
                        "budget_range": {"type": "string", "enum": ["budget", "mid-range", "luxury"]},
                        "interests": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            {
                "name": "enrich_poi_google_places",
                "description": "Enrich a POI with Google Places data (FREE - ratings, reviews, photos)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "poi_id": {"type": "string"},
                        "include_reviews": {"type": "boolean", "default": True}
                    },
                    "required": ["poi_id"]
                }
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": tools
            }
        }

    async def call_tool(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tools/call request"""
        try:
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            # Call the appropriate tool
            if tool_name == "search_pois":
                result = await self.mcp_server.poi_manager.search_pois(**arguments)
            elif tool_name == "validate_dataset":
                result = await self.mcp_server.data_validator.validate(**arguments)
            elif tool_name == "get_poi_details":
                result = await self.mcp_server.poi_manager.get_poi_details(**arguments)
            elif tool_name == "analyze_itinerary":
                result = await self.mcp_server.itinerary_analyzer.analyze(**arguments)
            elif tool_name == "get_travel_insights":
                result = await self.mcp_server.travel_insights.get_insights(**arguments)
            elif tool_name == "enrich_poi_google_places":
                result = await self.mcp_server.enrich_poi_google_places(**arguments)
            elif tool_name == "run_candidate_analysis":
                result = await self.mcp_server.run_candidate_analysis(**arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }
            
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }

def start_mcp_http_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the MCP-over-HTTP server"""
    server = ExvoraMCPHttpServer()
    print(f"🚀 Starting Exvora Travel MCP-over-HTTP Server on {host}:{port}")
    print(f"📋 Available tools: search_pois, validate_dataset, get_poi_details, analyze_itinerary, get_travel_insights, enrich_poi_google_places")
    uvicorn.run(server.app, host=host, port=port)

if __name__ == "__main__":
    start_mcp_http_server()