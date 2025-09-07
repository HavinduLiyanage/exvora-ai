"""
Ephemeral share token storage with TTL support.
"""
import time
import secrets
from typing import Dict, Any, Optional
from app.config import get_settings

settings = get_settings()

# In-memory storage: token -> { created_at, request_json, response_json }
_share_store: Dict[str, Dict[str, Any]] = {}


def create_share_token(request_data: Dict[str, Any], response_data: Dict[str, Any]) -> str:
    """
    Create a share token for request/response data.
    
    Args:
        request_data: The request data to store
        response_data: The response data to store
        
    Returns:
        A unique token string
    """
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    
    # Store with current timestamp
    _share_store[token] = {
        "created_at": time.time(),
        "request": request_data,
        "response": response_data
    }
    
    # Cleanup expired tokens
    _cleanup_expired_tokens()
    
    return token


def get_share_data(token: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve shared data by token.
    
    Args:
        token: The share token
        
    Returns:
        Dict with 'request' and 'response' keys, or None if not found/expired
    """
    # Cleanup expired tokens first
    _cleanup_expired_tokens()
    
    if token not in _share_store:
        return None
    
    data = _share_store[token]
    
    # Check if expired (double check after cleanup)
    ttl_minutes = settings.SHARE_TTL_MIN
    if time.time() - data["created_at"] > (ttl_minutes * 60):
        del _share_store[token]
        return None
    
    return {
        "request": data["request"],
        "response": data["response"]
    }


def _cleanup_expired_tokens() -> None:
    """Remove expired tokens from storage."""
    current_time = time.time()
    ttl_seconds = settings.SHARE_TTL_MIN * 60
    
    expired_tokens = [
        token for token, data in _share_store.items()
        if current_time - data["created_at"] > ttl_seconds
    ]
    
    for token in expired_tokens:
        del _share_store[token]


def get_store_stats() -> Dict[str, int]:
    """Get statistics about the share store."""
    _cleanup_expired_tokens()
    return {
        "active_tokens": len(_share_store),
        "ttl_minutes": settings.SHARE_TTL_MIN
    }