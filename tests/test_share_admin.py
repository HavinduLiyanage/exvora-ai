"""
Tests for share tokens and admin endpoints.
"""
import pytest
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.share.store import create_share_token, get_share_data, get_store_stats

client = TestClient(app)


class TestShareTokens:
    """Test share token functionality."""
    
    def test_create_share_token(self):
        """Test creating a share token."""
        request_data = {"test": "request"}
        response_data = {"test": "response"}
        
        token = create_share_token(request_data, response_data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify data can be retrieved
        retrieved_data = get_share_data(token)
        assert retrieved_data is not None
        assert retrieved_data["request"] == request_data
        assert retrieved_data["response"] == response_data
    
    def test_get_share_data_nonexistent(self):
        """Test retrieving data for non-existent token."""
        data = get_share_data("nonexistent_token")
        assert data is None
    
    def test_share_token_expiry(self):
        """Test share token expiry."""
        # Create a token with normal TTL
        request_data = {"test": "request"}
        response_data = {"test": "response"}
        
        token = create_share_token(request_data, response_data)
        
        # Manually expire the token by modifying its creation time
        from app.share.store import _share_store
        if token in _share_store:
            # Set creation time to 2 days ago (well beyond 24 hour TTL)
            _share_store[token]["created_at"] = time.time() - (2 * 24 * 60 * 60)
        
        # Should be expired now (cleanup happens in get_share_data)
        data = get_share_data(token)
        assert data is None
    
    def test_get_store_stats(self):
        """Test getting store statistics."""
        # Clear store first
        from app.share.store import _share_store
        _share_store.clear()
        
        # Create some tokens
        create_share_token({"test1": "data"}, {"test1": "response"})
        create_share_token({"test2": "data"}, {"test2": "response"})
        
        stats = get_store_stats()
        assert stats["active_tokens"] == 2
        assert stats["ttl_minutes"] > 0


class TestAdminEndpoints:
    """Test admin POI endpoints."""
    
    def test_admin_endpoints_require_key(self):
        """Test that admin endpoints require admin key."""
        # Test without key
        response = client.get("/admin/pois")
        assert response.status_code == 403  # Admin disabled by default
        
        response = client.post("/admin/pois", json={"poi_id": "test"})
        assert response.status_code == 403  # Admin disabled by default
    
    def test_admin_endpoints_disabled(self):
        """Test admin endpoints when disabled."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = None
            
            response = client.get("/admin/pois", headers={"x-admin-key": "any-key"})
            assert response.status_code == 403
    
    def test_list_pois(self):
        """Test listing POIs."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            response = client.get("/admin/pois", headers={"x-admin-key": "test-admin-key"})
            assert response.status_code == 200
            
            data = response.json()
            assert "pois" in data
            assert "pagination" in data
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["limit"] == 50
    
    def test_create_poi(self):
        """Test creating a POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            poi_data = {
                "poi_id": "test_poi_1",
                "place_id": "ChIJtest",
                "name": "Test POI",
                "coords": {"lat": 7.2906, "lng": 80.6337},
                "tags": ["test"],
                "themes": ["Test"],
                "duration_minutes": 60,
                "opening_hours": [],
                "price_band": "free",
                "estimated_cost": 0,
                "safety_flags": [],
                "region": "test_region"
            }
            
            response = client.post("/admin/pois", json=poi_data, headers={"x-admin-key": "test-admin-key"})
            assert response.status_code == 200
            
            data = response.json()
            assert data["message"] == "POI created successfully"
            assert data["poi"]["poi_id"] == "test_poi_1"
    
    def test_create_poi_duplicate(self):
        """Test creating a duplicate POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            poi_data = {
                "poi_id": "duplicate_poi",
                "place_id": "ChIJduplicate",
                "name": "Duplicate POI",
                "coords": {"lat": 7.2906, "lng": 80.6337},
                "tags": [],
                "themes": [],
                "duration_minutes": 60,
                "opening_hours": [],
                "price_band": "free",
                "estimated_cost": 0,
                "safety_flags": [],
                "region": "test_region"
            }
            
            # Create first POI
            response1 = client.post("/admin/pois", json=poi_data, headers={"x-admin-key": "test-admin-key"})
            assert response1.status_code == 200
            
            # Try to create duplicate
            response2 = client.post("/admin/pois", json=poi_data, headers={"x-admin-key": "test-admin-key"})
            assert response2.status_code == 409
    
    def test_update_poi(self):
        """Test updating a POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            # First create a POI
            poi_data = {
                "poi_id": "update_poi",
                "place_id": "ChIJupdate",
                "name": "Original Name",
                "coords": {"lat": 7.2906, "lng": 80.6337},
                "tags": [],
                "themes": [],
                "duration_minutes": 60,
                "opening_hours": [],
                "price_band": "free",
                "estimated_cost": 0,
                "safety_flags": [],
                "region": "test_region"
            }
            
            create_response = client.post("/admin/pois", json=poi_data, headers={"x-admin-key": "test-admin-key"})
            assert create_response.status_code == 200
            
            # Update the POI
            update_data = {
                "name": "Updated Name",
                "estimated_cost": 50
            }
            
            update_response = client.patch("/admin/pois/update_poi", json=update_data, headers={"x-admin-key": "test-admin-key"})
            assert update_response.status_code == 200
            
            data = update_response.json()
            assert data["message"] == "POI updated successfully"
            assert data["poi"]["name"] == "Updated Name"
            assert data["poi"]["estimated_cost"] == 50
    
    def test_update_poi_not_found(self):
        """Test updating a non-existent POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            update_data = {"name": "Updated Name"}
            
            response = client.patch("/admin/pois/nonexistent", json=update_data, headers={"x-admin-key": "test-admin-key"})
            assert response.status_code == 404
    
    def test_delete_poi(self):
        """Test deleting a POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            # First create a POI
            poi_data = {
                "poi_id": "delete_poi",
                "place_id": "ChIJdelete",
                "name": "To Delete",
                "coords": {"lat": 7.2906, "lng": 80.6337},
                "tags": [],
                "themes": [],
                "duration_minutes": 60,
                "opening_hours": [],
                "price_band": "free",
                "estimated_cost": 0,
                "safety_flags": [],
                "region": "test_region"
            }
            
            create_response = client.post("/admin/pois", json=poi_data, headers={"x-admin-key": "test-admin-key"})
            assert create_response.status_code == 200
            
            # Delete the POI
            delete_response = client.delete("/admin/pois/delete_poi", headers={"x-admin-key": "test-admin-key"})
            assert delete_response.status_code == 200
            
            data = delete_response.json()
            assert data["message"] == "POI deleted successfully"
            assert data["deleted_poi"]["poi_id"] == "delete_poi"
    
    def test_delete_poi_not_found(self):
        """Test deleting a non-existent POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            response = client.delete("/admin/pois/nonexistent", headers={"x-admin-key": "test-admin-key"})
            assert response.status_code == 404
    
    def test_get_poi(self):
        """Test getting a specific POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            # First create a POI
            poi_data = {
                "poi_id": "get_poi",
                "place_id": "ChIJget",
                "name": "Get POI",
                "coords": {"lat": 7.2906, "lng": 80.6337},
                "tags": [],
                "themes": [],
                "duration_minutes": 60,
                "opening_hours": [],
                "price_band": "free",
                "estimated_cost": 0,
                "safety_flags": [],
                "region": "test_region"
            }
            
            create_response = client.post("/admin/pois", json=poi_data, headers={"x-admin-key": "test-admin-key"})
            assert create_response.status_code == 200
            
            # Get the POI
            get_response = client.get("/admin/pois/get_poi", headers={"x-admin-key": "test-admin-key"})
            assert get_response.status_code == 200
            
            data = get_response.json()
            assert data["poi"]["poi_id"] == "get_poi"
            assert data["poi"]["name"] == "Get POI"
    
    def test_get_poi_not_found(self):
        """Test getting a non-existent POI."""
        with patch('app.config.get_settings') as mock_settings:
            mock_settings.return_value.ADMIN_API_KEY = "test-admin-key"
            
            response = client.get("/admin/pois/nonexistent", headers={"x-admin-key": "test-admin-key"})
            assert response.status_code == 404