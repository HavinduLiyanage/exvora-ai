#!/usr/bin/env python3
"""
FastAPI MCP Server - HTTP Mode
Provides tools to discover routes, generate test cases, list tests, and run tests for FastAPI applications.
"""

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Initialize MCP server
app = Server("fastapi-mcp-server")


def import_fastapi_app(app_import_path: str) -> Any:
    """
    Import a FastAPI application from a module path.

    Args:
        app_import_path: Path like 'myapp.main:app' where 'myapp.main' is the module
                        and 'app' is the FastAPI instance variable name.

    Returns:
        The imported FastAPI application instance.
    """
    try:
        module_path, app_name = app_import_path.split(":")
        module = importlib.import_module(module_path)
        fastapi_app = getattr(module, app_name)
        return fastapi_app
    except Exception as e:
        raise ValueError(f"Failed to import FastAPI app from '{app_import_path}': {str(e)}")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="discover_routes",
            description="Discover all registered routes in a FastAPI application",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_import_path": {
                        "type": "string",
                        "description": "Import path to FastAPI app (e.g., 'myapp.main:app')"
                    }
                },
                "required": ["app_import_path"]
            }
        ),
        Tool(
            name="generate_test_cases",
            description="Generate pytest test functions for FastAPI routes",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_import_path": {
                        "type": "string",
                        "description": "Import path to FastAPI app (e.g., 'myapp.main:app')"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path where test file should be saved"
                    },
                    "sample_values": {
                        "type": "object",
                        "description": "Optional sample values for POST/PUT request bodies (route_path -> data dict)",
                        "additionalProperties": True
                    }
                },
                "required": ["app_import_path", "output_path"]
            }
        ),
        Tool(
            name="list_tests",
            description="List all discovered pytest tests using --collect-only",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Optional path to test file or directory (defaults to current directory)"
                    }
                }
            }
        ),
        Tool(
            name="run_tests",
            description="Run pytest tests with optional arguments",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_path": {
                        "type": "string",
                        "description": "Optional path to test file or directory"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional additional pytest arguments (e.g., ['-v', '-k', 'test_name'])"
                    }
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool execution requests."""

    if name == "discover_routes":
        return await discover_routes(arguments)
    elif name == "generate_test_cases":
        return await generate_test_cases(arguments)
    elif name == "list_tests":
        return await list_tests_tool(arguments)
    elif name == "run_tests":
        return await run_tests(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def discover_routes(arguments: Dict[str, Any]) -> List[TextContent]:
    """Discover all routes in a FastAPI application."""
    app_import_path = arguments["app_import_path"]

    try:
        fastapi_app = import_fastapi_app(app_import_path)

        routes = []
        for route in fastapi_app.routes:
            # Skip non-API routes (like static file routes)
            if hasattr(route, "methods") and hasattr(route, "path"):
                route_info = {
                    "methods": list(route.methods),
                    "path": route.path,
                    "name": route.name if hasattr(route, "name") else None,
                    "endpoint": route.endpoint.__name__ if hasattr(route, "endpoint") else None
                }
                routes.append(route_info)

        result = {
            "app_import_path": app_import_path,
            "total_routes": len(routes),
            "routes": routes
        }

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error discovering routes: {str(e)}"
        )]


async def generate_test_cases(arguments: Dict[str, Any]) -> List[TextContent]:
    """Generate pytest test functions for FastAPI routes."""
    app_import_path = arguments["app_import_path"]
    output_path = arguments["output_path"]
    sample_values = arguments.get("sample_values", {})

    try:
        fastapi_app = import_fastapi_app(app_import_path)

        # Collect routes
        routes = []
        for route in fastapi_app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                routes.append({
                    "methods": list(route.methods),
                    "path": route.path,
                    "name": route.name if hasattr(route, "name") else "unknown"
                })

        # Generate test file content
        test_content = generate_test_file_content(
            app_import_path=app_import_path,
            routes=routes,
            sample_values=sample_values
        )

        # Write to output file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(test_content)

        return [TextContent(
            type="text",
            text=f"Generated {len(routes)} test cases in {output_path}"
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error generating test cases: {str(e)}"
        )]


def generate_test_file_content(
    app_import_path: str,
    routes: List[Dict[str, Any]],
    sample_values: Dict[str, Any]
) -> str:
    """Generate the content of a pytest test file."""

    lines = [
        '"""',
        'Auto-generated pytest tests for FastAPI application.',
        'Generated by FastAPI MCP Server.',
        '"""',
        '',
        'import pytest',
        'from fastapi.testclient import TestClient',
        f'from {app_import_path.split(":")[0]} import {app_import_path.split(":")[1]}',
        '',
        '',
        '@pytest.fixture',
        'def client():',
        f'    """Create a test client for the FastAPI app."""',
        f'    return TestClient({app_import_path.split(":")[1]})',
        '',
        ''
    ]

    # Generate test functions for each route
    for route in routes:
        methods = [m for m in route["methods"] if m != "HEAD" and m != "OPTIONS"]
        path = route["path"]
        name = route["name"]

        for method in methods:
            # Create a safe function name
            func_name = f"test_{method.lower()}_{name}".replace("-", "_")

            lines.append(f'def {func_name}(client):')
            lines.append(f'    """Test {method} {path}"""')

            # Build the request
            if method in ["POST", "PUT", "PATCH"]:
                # Check if we have sample values for this route
                sample_data = sample_values.get(path, {})
                data_json = json.dumps(sample_data, indent=8)

                lines.append(f'    data = {data_json}')
                lines.append(f'    response = client.{method.lower()}("{path}", json=data)')
            else:
                lines.append(f'    response = client.{method.lower()}("{path}")')

            lines.append(f'    # Basic assertion - adjust as needed')
            lines.append(f'    assert response.status_code in [200, 201, 204, 404], f"Unexpected status: {{response.status_code}}"')
            lines.append('')
            lines.append('')

    return '\n'.join(lines)


async def list_tests_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """List all pytest tests using --collect-only."""
    test_path = arguments.get("test_path", ".")

    try:
        cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", test_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = {
            "command": " ".join(cmd),
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

        return [TextContent(
            type="text",
            text=json.dumps(output, indent=2)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error listing tests: {str(e)}"
        )]


async def run_tests(arguments: Dict[str, Any]) -> List[TextContent]:
    """Run pytest tests with optional arguments."""
    test_path = arguments.get("test_path", ".")
    extra_args = arguments.get("args", [])

    try:
        cmd = [sys.executable, "-m", "pytest", test_path] + extra_args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        output = {
            "command": " ".join(cmd),
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }

        return [TextContent(
            type="text",
            text=json.dumps(output, indent=2)
        )]

    except subprocess.TimeoutExpired:
        return [TextContent(
            type="text",
            text="Error: Test execution timed out after 120 seconds"
        )]
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error running tests: {str(e)}"
        )]


def main():
    """
    Run the MCP server over HTTP on http://127.0.0.1:8001/mcp
    """
    # Note: For HTTP mode, we need to use a different transport
    # The MCP SDK's stdio_server is for stdio transport only
    # For HTTP mode, you'll need to use an HTTP server implementation

    print("FastAPI MCP Server - HTTP Mode")
    print("=" * 50)
    print()
    print("This server uses stdio transport by default.")
    print("For HTTP mode on http://127.0.0.1:8001/mcp, you need to:")
    print("1. Use an MCP HTTP server wrapper (like mcp-server-http)")
    print("2. Or integrate with a web framework that wraps this MCP server")
    print()
    print("Starting stdio mode for testing...")
    print()

    # Run in stdio mode (can be wrapped by HTTP server)
    import asyncio
    asyncio.run(stdio_server(app))


if __name__ == "__main__":
    main()
