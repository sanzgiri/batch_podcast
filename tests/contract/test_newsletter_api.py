"""
Contract tests for Newsletter API endpoints.

These tests verify the API contract matches the OpenAPI specification
and ensure proper request/response handling for newsletter operations.
"""

import pytest
from typing import Dict, Any
from httpx import AsyncClient


@pytest.mark.contract
@pytest.mark.asyncio
async def test_submit_newsletter_contract():
    """Test newsletter submission endpoint contract."""
    # This test should FAIL initially (TDD approach)
    
    # Test data matching API contract
    newsletter_data = {
        "title": "Weekly Tech Newsletter",
        "content": "This is a sample newsletter content with at least 100 characters to meet validation requirements. It contains technology news and updates for the week.",
        "url": None
    }
    
    expected_response_fields = {
        "id", "title", "content", "url", "content_hash", 
        "word_count", "status", "submitted_at"
    }
    
    # This will fail until we implement the API
    async with AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/newsletters",
            json=newsletter_data
        )
        
        # Contract assertions
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"
        
        response_data = response.json()
        
        # Verify response structure
        assert isinstance(response_data, dict), "Response should be a dictionary"
        assert expected_response_fields.issubset(response_data.keys()), \
            f"Missing fields in response: {expected_response_fields - set(response_data.keys())}"
        
        # Verify data types
        assert isinstance(response_data["id"], str), "ID should be a string"
        assert isinstance(response_data["title"], str), "Title should be a string"
        assert isinstance(response_data["content"], str), "Content should be a string"
        assert response_data["url"] is None, "URL should be None for text submission"
        assert isinstance(response_data["content_hash"], str), "Content hash should be a string"
        assert isinstance(response_data["word_count"], int), "Word count should be an integer"
        assert response_data["status"] in ["pending", "processing"], "Status should be valid"
        assert isinstance(response_data["submitted_at"], str), "Submitted at should be an ISO string"
        
        # Verify content processing
        assert response_data["word_count"] > 0, "Word count should be positive"
        assert len(response_data["content_hash"]) == 64, "Content hash should be SHA-256 (64 chars)"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_submit_newsletter_with_url_contract():
    """Test newsletter submission with URL endpoint contract."""
    newsletter_data = {
        "title": "Newsletter from URL",
        "url": "https://example.com/newsletter",
        "content": None
    }
    
    async with AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/newsletters",
            json=newsletter_data
        )
        
        assert response.status_code == 201
        response_data = response.json()
        
        assert response_data["url"] == newsletter_data["url"]
        assert response_data["content"] is not None, "Content should be extracted from URL"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_submit_newsletter_validation_errors():
    """Test newsletter submission validation error contract."""
    # Test missing both content and URL
    invalid_data = {
        "title": "Invalid Newsletter"
    }
    
    async with AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/newsletters",
            json=invalid_data
        )
        
        assert response.status_code == 400
        error_data = response.json()
        
        # Verify error response structure
        assert "detail" in error_data or "message" in error_data
        

@pytest.mark.contract
@pytest.mark.asyncio
async def test_get_newsletter_contract():
    """Test get newsletter by ID endpoint contract."""
    # First submit a newsletter
    newsletter_data = {
        "title": "Test Newsletter",
        "content": "This is test content for retrieving newsletter information with sufficient length to pass validation."
    }
    
    async with AsyncClient() as client:
        # Submit newsletter
        submit_response = await client.post(
            "http://localhost:8000/api/v1/newsletters",
            json=newsletter_data
        )
        assert submit_response.status_code == 201
        newsletter_id = submit_response.json()["id"]
        
        # Get newsletter
        get_response = await client.get(
            f"http://localhost:8000/api/v1/newsletters/{newsletter_id}"
        )
        
        assert get_response.status_code == 200
        newsletter = get_response.json()
        
        # Verify response structure matches submission
        assert newsletter["id"] == newsletter_id
        assert newsletter["title"] == newsletter_data["title"]
        assert newsletter["content"] == newsletter_data["content"]


@pytest.mark.contract
@pytest.mark.asyncio
async def test_get_newsletter_not_found_contract():
    """Test get newsletter not found error contract."""
    async with AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/newsletters/00000000-0000-0000-0000-000000000000"
        )
        
        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data or "message" in error_data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_list_newsletters_contract():
    """Test list newsletters endpoint contract."""
    async with AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/v1/newsletters")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination structure
        expected_fields = {"items", "total", "limit", "offset"}
        assert expected_fields.issubset(data.keys()), \
            f"Missing pagination fields: {expected_fields - set(data.keys())}"
        
        assert isinstance(data["items"], list), "Items should be a list"
        assert isinstance(data["total"], int), "Total should be an integer"
        assert isinstance(data["limit"], int), "Limit should be an integer"
        assert isinstance(data["offset"], int), "Offset should be an integer"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_newsletter_status_endpoint_contract():
    """Test newsletter processing status endpoint contract."""
    # Submit a newsletter first
    newsletter_data = {
        "title": "Status Test Newsletter",
        "content": "Content for testing newsletter processing status endpoint with sufficient length for validation."
    }
    
    async with AsyncClient() as client:
        submit_response = await client.post(
            "http://localhost:8000/api/v1/newsletters",
            json=newsletter_data
        )
        newsletter_id = submit_response.json()["id"]
        
        # Get status
        status_response = await client.get(
            f"http://localhost:8000/api/v1/newsletters/{newsletter_id}/status"
        )
        
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        # Verify status response structure
        expected_fields = {"id", "status", "progress", "message"}
        assert expected_fields.issubset(status_data.keys())
        
        assert status_data["status"] in ["pending", "processing", "completed", "failed"]
        assert isinstance(status_data["progress"], (int, float))
        assert 0 <= status_data["progress"] <= 100


@pytest.mark.contract
@pytest.mark.asyncio
async def test_duplicate_content_detection_contract():
    """Test duplicate content detection contract."""
    newsletter_data = {
        "title": "Duplicate Test Newsletter",
        "content": "This is unique content for testing duplicate detection functionality with sufficient length."
    }
    
    async with AsyncClient() as client:
        # Submit first newsletter
        first_response = await client.post(
            "http://localhost:8000/api/v1/newsletters",
            json=newsletter_data
        )
        assert first_response.status_code == 201
        
        # Submit same content again
        duplicate_response = await client.post(
            "http://localhost:8000/api/v1/newsletters",
            json=newsletter_data
        )
        
        # Should return 409 Conflict for duplicate content
        assert duplicate_response.status_code == 409
        error_data = duplicate_response.json()
        
        assert "detail" in error_data or "message" in error_data
        # Should include reference to existing newsletter
        assert "existing_id" in error_data.get("details", {}) or \
               "duplicate" in str(error_data).lower()


# Fixtures for test data
@pytest.fixture
def valid_newsletter_data():
    """Fixture providing valid newsletter data."""
    return {
        "title": "Test Newsletter",
        "content": "This is a valid newsletter content with sufficient length to pass all validation requirements and provide meaningful content for processing."
    }


@pytest.fixture
def valid_newsletter_url_data():
    """Fixture providing valid newsletter URL data."""
    return {
        "title": "URL Newsletter",
        "url": "https://example.com/newsletter-content"
    }