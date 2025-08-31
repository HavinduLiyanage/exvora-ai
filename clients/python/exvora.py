"""Python client for Exvora AI API."""

import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ExvoraClient:
    """Client for Exvora AI API."""
    base_url: str = "http://localhost:8000"
    
    def build_itinerary(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build an itinerary using the API."""
        response = requests.post(
            f"{self.base_url}/v1/itinerary",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
    
    def feedback(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send feedback to repack a day."""
        response = requests.post(
            f"{self.base_url}/v1/itinerary/feedback",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()

# Convenience functions
def build_itinerary(request_data: Dict[str, Any], base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Build an itinerary using the API."""
    client = ExvoraClient(base_url)
    return client.build_itinerary(request_data)

def feedback(request_data: Dict[str, Any], base_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """Send feedback to repack a day."""
    client = ExvoraClient(base_url)
    return client.feedback(request_data)
