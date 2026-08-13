"""
Integration tests for the gateway API endpoints.
Requires a running MongoDB instance (uses test database).
"""

from __future__ import annotations

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def app():
    """Create the FastAPI application for testing."""
    import os
    os.environ["APP_ENV"] = "test"
    os.environ["MONGO_URI"] = "mongodb://localhost:27017/jobplatform_test"
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-integration-tests"

    from services.gateway.main import app as _app
    return _app


@pytest.fixture(scope="session")
async def client(app):
    """Create an async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
async def auth_headers(client):
    """Register a test user and get auth headers."""
    reg_resp = await client.post("/api/v1/auth/register", json={
        "email": "test@talentlens.io",
        "password": "testpassword123",
        "full_name": "Test User",
    })
    if reg_resp.status_code not in (201, 409):
        pytest.skip(f"Failed to register test user: {reg_resp.status_code}")

    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "test@talentlens.io",
        "password": "testpassword123",
    })
    if login_resp.status_code != 200:
        pytest.skip("Failed to login test user")

    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ─── Health Check ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client):
    """API health endpoint should return 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")


# ─── Auth Endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_user(client):
    """User registration should return 201 with tokens."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "newuser@test.io",
        "password": "password123",
        "full_name": "New User",
    })
    assert resp.status_code in (201, 409)  # 409 if already exists from prior run
    if resp.status_code == 201:
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    """Login with wrong password should return 401."""
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@talentlens.io",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client, auth_headers):
    """Authenticated /auth/me should return user info."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert data["email"] == "test@talentlens.io"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    """Unauthenticated /auth/me should return 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ─── Jobs Endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_jobs(client):
    """Jobs listing endpoint should return paginated results."""
    resp = await client.get("/api/v1/jobs?page=1&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data
    assert "page" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_search_jobs(client):
    """Search endpoint should return results matching query."""
    resp = await client.get("/api/v1/search?q=python&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data


@pytest.mark.asyncio
async def test_jobs_filter_by_remote(client):
    """Filter by remote type should work."""
    resp = await client.get("/api/v1/jobs?remote=remote&page_size=5")
    assert resp.status_code == 200


# ─── Analytics Endpoints ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analytics_overview(client):
    """Analytics overview should return platform stats."""
    resp = await client.get("/api/v1/analytics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_jobs" in data


@pytest.mark.asyncio
async def test_skill_demand(client):
    """Skill demand endpoint should return skill list."""
    resp = await client.get("/api/v1/analytics/skill-demand?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "top_skills" in data


# ─── Notifications ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_notifications_authenticated(client, auth_headers):
    """Notification listing should work for authenticated users."""
    resp = await client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "notifications" in data
    assert "unread_count" in data


@pytest.mark.asyncio
async def test_list_notifications_unauthenticated(client):
    """Notification listing should fail for unauthenticated requests."""
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 401


# ─── Saved Searches ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_delete_saved_search(client, auth_headers):
    """Create a saved search, then delete it."""
    create_resp = await client.post("/api/v1/users/me/saved-searches", json={
        "name": "Integration Test Search",
        "query": "python developer",
        "filters": {"remote_type": "remote"},
        "alert_enabled": True,
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    search_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/users/me/saved-searches/{search_id}", headers=auth_headers)
    assert delete_resp.status_code == 200
