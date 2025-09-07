"""
Admin API endpoints for POI management.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from typing import List, Optional
from app.schemas.models import POICreateRequest, POIUpdateRequest, Coords
from app.dataset.loader import pois, load_pois
from app.config import get_settings
from app.api.errors import raise_http_error
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin_key(request: Request) -> None:
    """Check admin API key via x-admin-key header."""
    admin_key = settings.ADMIN_API_KEY
    if not admin_key:
        raise_http_error(403, "admin_disabled", "Admin API is disabled", ["Set ADMIN_API_KEY environment variable"])
    
    provided = request.headers.get("x-admin-key")
    if provided != admin_key:
        raise_http_error(401, "unauthorized", "Missing or invalid admin key", ["Provide x-admin-key header"])


@router.get("/pois")
def list_pois(
    request: Request,
    _: None = Depends(_check_admin_key),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page")
):
    """List POIs with pagination."""
    if len(pois()) == 0:
        load_pois()
    
    all_pois_list = pois()
    total = len(all_pois_list)
    
    # Calculate pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    
    paginated_pois = all_pois_list[start_idx:end_idx]
    
    return {
        "pois": paginated_pois,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }


@router.post("/pois")
def create_poi(
    poi_data: POICreateRequest,
    request: Request,
    _: None = Depends(_check_admin_key)
):
    """Create a new POI."""
    if len(pois()) == 0:
        load_pois()
    
    # Check if POI ID already exists
    existing_poi = next((p for p in pois() if p.get("poi_id") == poi_data.poi_id), None)
    if existing_poi:
        raise_http_error(409, "poi_exists", f"POI with ID '{poi_data.poi_id}' already exists", ["Use a different POI ID"])
    
    # Convert to dict and add to in-memory store
    new_poi = {
        "poi_id": poi_data.poi_id,
        "place_id": poi_data.place_id,
        "name": poi_data.name,
        "coords": poi_data.coords.model_dump(),
        "tags": poi_data.tags,
        "themes": poi_data.themes,
        "duration_minutes": poi_data.duration_minutes,
        "opening_hours": poi_data.opening_hours,
        "price_band": poi_data.price_band,
        "estimated_cost": poi_data.estimated_cost,
        "safety_flags": poi_data.safety_flags,
        "region": poi_data.region
    }
    
    # Add to in-memory dataset (this is non-persistent)
    pois().append(new_poi)
    
    logger.info(f"Created POI: {poi_data.poi_id} - {poi_data.name}")
    
    return {
        "message": "POI created successfully",
        "poi": new_poi
    }


@router.patch("/pois/{poi_id}")
def update_poi(
    poi_id: str,
    update_data: POIUpdateRequest,
    request: Request,
    _: None = Depends(_check_admin_key)
):
    """Partially update a POI."""
    if len(pois()) == 0:
        load_pois()
    
    # Find existing POI
    poi_index = next((i for i, p in enumerate(pois()) if p.get("poi_id") == poi_id), None)
    if poi_index is None:
        raise_http_error(404, "poi_not_found", f"POI with ID '{poi_id}' not found", ["Check POI ID"])
    
    # Update fields (only non-None values)
    update_dict = update_data.model_dump(exclude_unset=True)
    if "coords" in update_dict and update_dict["coords"]:
        update_dict["coords"] = update_dict["coords"].model_dump()
    
    pois()[poi_index].update(update_dict)
    
    logger.info(f"Updated POI: {poi_id}")
    
    return {
        "message": "POI updated successfully",
        "poi": pois()[poi_index]
    }


@router.delete("/pois/{poi_id}")
def delete_poi(
    poi_id: str,
    request: Request,
    _: None = Depends(_check_admin_key)
):
    """Delete a POI."""
    if len(pois()) == 0:
        load_pois()
    
    # Find and remove POI
    poi_index = next((i for i, p in enumerate(pois()) if p.get("poi_id") == poi_id), None)
    if poi_index is None:
        raise_http_error(404, "poi_not_found", f"POI with ID '{poi_id}' not found", ["Check POI ID"])
    
    deleted_poi = pois().pop(poi_index)
    
    logger.info(f"Deleted POI: {poi_id} - {deleted_poi.get('name', 'Unknown')}")
    
    return {
        "message": "POI deleted successfully",
        "deleted_poi": deleted_poi
    }


@router.get("/pois/{poi_id}")
def get_poi(
    poi_id: str,
    request: Request,
    _: None = Depends(_check_admin_key)
):
    """Get a specific POI by ID."""
    if len(pois()) == 0:
        load_pois()
    
    poi = next((p for p in pois() if p.get("poi_id") == poi_id), None)
    if not poi:
        raise_http_error(404, "poi_not_found", f"POI with ID '{poi_id}' not found", ["Check POI ID"])
    
    return {"poi": poi}