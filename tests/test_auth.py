import pytest
from httpx import AsyncClient
from hackucdbackend.models.user import User


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    payload = {
        "email": "new_student@school.edu",
        "password": "secretpassword123",
        "full_name": "Alex Student",
        "role": "student",
        "age": 19,
        "sex": "male",
        "activity_level": "moderate",
        "dietary_flags": ["halal"],
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "new_student@school.edu"
    assert data["user"]["role"] == "student"
    assert data["user"]["dietary_flags"] == ["halal"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, registered_user: User):
    login_payload = {
        "email": registered_user.email,
        "password": "securepassword123",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == registered_user.email
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, registered_user: User):
    login_payload = {
        "email": registered_user.email,
        "password": "wrongpassword",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient):
    login_payload = {
        "email": "nobody@example.com",
        "password": "somepassword",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, registered_user: User):
    payload = {
        "email": registered_user.email,
        "password": "anotherpassword",
        "full_name": "Duplicate Sarah",
        "role": "student",
        "age": 20,
        "sex": "female",
        "activity_level": "moderate",
        "dietary_flags": [],
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_role(client: AsyncClient):
    payload = {
        "email": "invalid_role@example.com",
        "full_name": "Invalid",
        "role": "admin",  # Invalid role
        "age": 30,
        "sex": "male",
        "activity_level": "moderate",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_me_with_bearer_token(client: AsyncClient, registered_user: User, auth_headers: dict):
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == registered_user.email
    assert data["full_name"] == registered_user.full_name
    assert data["profile"]["role"] == "student"
    assert data["profile"]["age"] == 20


@pytest.mark.asyncio
async def test_get_me_with_x_user_id(client: AsyncClient, registered_user: User):
    headers = {"X-User-Id": str(registered_user.id)}
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == registered_user.email


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
