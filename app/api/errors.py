"""Structured error responses for Exvora AI API."""

from fastapi import HTTPException
from typing import List, Dict, Any

def error_response(code: int, type_: str, message: str, hints: List[str] = None) -> Dict[str, Any]:
    """Create a structured error response."""
    if hints is None:
        hints = []
    
    return {
        "error": {
            "code": code,
            "type": type_,
            "message": message,
            "hints": hints
        }
    }

def raise_http_error(code: int, type_: str, message: str, hints: List[str] = None):
    """Raise an HTTPException with structured error details."""
    detail = error_response(code, type_, message, hints)
    raise HTTPException(status_code=code, detail=detail)
