#!/usr/bin/env python3

"""Simple HTTP webhook server for Exvora Travel MCP Server"""

import asyncio
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from exvora_mcp_server.main import ExvoraTravelMCPServer


class ExvoraWebhookHandler(BaseHTTPRequestHandler):
    
    def __init__(self, *args, **kwargs):
        self.mcp_server = ExvoraTravelMCPServer()
        super().__init__(*args, **kwargs)
    
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _send_json(self, data, status=200):
        self._set_headers(status)
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))
    
    def _send_error(self, message, status=500):
        self._send_json({"error": message, "success": False}, status)
    
    def do_OPTIONS(self):
        self._set_headers()
    
    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query_params = parse_qs(parsed_path.query)
            
            # Convert query params (lists) to single values
            params = {}
            for key, values in query_params.items():
                params[key] = values[0] if values else None
            
            if path == "/":
                self._send_json({
                    "name": "Exvora Travel API",
                    "version": "1.0.0",
                    "description": "Travel POI management and analysis webhook",
                    "endpoints": {
                        "validate": "GET /validate?fix_issues=true",
                        "search": "GET /search?themes=Cultural&price_band=low",
                        "poi": "GET /poi?poi_id=temple_id",
                        "insights": "GET /insights?region=Kandy&season=dry",
                        "health": "GET /health"
                    }
                })
            
            elif path == "/health":
                self._send_json({
                    "status": "healthy",
                    "service": "Exvora Travel API"
                })
            
            elif path == "/validate":
                fix_issues = params.get('fix_issues', 'false').lower() == 'true'
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.mcp_server.data_validator.validate(fix_issues=fix_issues)
                )
                loop.close()
                self._send_json({
                    "success": True,
                    "report": result
                })
            
            elif path == "/search":
                # Parse search parameters
                args = {"limit": int(params.get('limit', 10))}
                if params.get('themes'):
                    args['themes'] = params['themes'].split(',')
                if params.get('tags'):
                    args['tags'] = params['tags'].split(',')
                if params.get('price_band'):
                    args['price_band'] = params['price_band']
                if params.get('region'):
                    args['region'] = params['region']
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.mcp_server.poi_manager.search_pois(**args)
                )
                loop.close()
                self._send_json({
                    "success": True,
                    "data": result,
                    "query": args
                })
            
            elif path == "/poi":
                poi_id = params.get('poi_id')
                if not poi_id:
                    self._send_error("Missing poi_id parameter", 400)
                    return
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.mcp_server.poi_manager.get_poi_details(poi_id=poi_id)
                )
                loop.close()
                self._send_json({
                    "success": True,
                    "poi_id": poi_id,
                    "data": result
                })
            
            elif path == "/insights":
                args = {}
                if params.get('region'):
                    args['region'] = params['region']
                if params.get('season'):
                    args['season'] = params['season']
                if params.get('budget_range'):
                    args['budget_range'] = params['budget_range']
                if params.get('interests'):
                    args['interests'] = params['interests'].split(',')
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.mcp_server.travel_insights.get_insights(**args)
                )
                loop.close()
                self._send_json({
                    "success": True,
                    "insights": result
                })
            
            else:
                self._send_error("Endpoint not found", 404)
        
        except Exception as e:
            self._send_error(str(e))
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
            except json.JSONDecodeError:
                data = {}
            
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            
            if path == "/analyze":
                itinerary = data.get('itinerary')
                if not itinerary:
                    self._send_error("Missing 'itinerary' in request body", 400)
                    return
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.mcp_server.itinerary_analyzer.analyze(itinerary=itinerary)
                )
                loop.close()
                self._send_json({
                    "success": True,
                    "analysis": result
                })
            
            else:
                self._send_error("POST endpoint not found", 404)
        
        except Exception as e:
            self._send_error(str(e))
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass


def run_webhook_server(port=8080):
    server_address = ('', port)
    
    # Create a custom handler class that shares the MCP server instance
    class SharedMCPHandler(ExvoraWebhookHandler):
        _mcp_server = None
        
        def __init__(self, *args, **kwargs):
            if SharedMCPHandler._mcp_server is None:
                SharedMCPHandler._mcp_server = ExvoraTravelMCPServer()
            self.mcp_server = SharedMCPHandler._mcp_server
            BaseHTTPRequestHandler.__init__(self, *args, **kwargs)
    
    httpd = HTTPServer(server_address, SharedMCPHandler)
    print(f"🌐 Exvora Travel Webhook Server running on http://localhost:{port}")
    print(f"🔍 Test: http://localhost:{port}/search?themes=Cultural")
    print(f"✅ Validate: http://localhost:{port}/validate?fix_issues=true")
    print(f"📊 Health: http://localhost:{port}/health")
    print("🛑 Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.server_close()


if __name__ == "__main__":
    run_webhook_server()