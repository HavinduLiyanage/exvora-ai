#!/usr/bin/env python3
"""Export OpenAPI schema from Exvora AI app."""

import json
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app

def main():
    """Export OpenAPI schema to stdout."""
    try:
        openapi_schema = app.openapi()
        json.dump(openapi_schema, sys.stdout, indent=2)
        print(file=sys.stderr)  # Add newline to stderr for clean output
    except Exception as e:
        print(f"Error exporting OpenAPI schema: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
