"""
Authentication tests.
"""

import pytest
from fastapi import status
from tests.conftest import client
from app.core.security import create_access_token


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "name" in data
    assert "version" in data


# Note: Full authentication tests would require database setup
# In a real project, use pytest fixtures and test database
