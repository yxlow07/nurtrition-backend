import uuid
import pytest
from httpx import AsyncClient
from hackucdbackend.models.user import User


@pytest.mark.asyncio
async def test_create_family(client: AsyncClient, auth_headers: dict, registered_user: User):
    payload = {"name": "The Millers"}
    response = await client.post("/api/v1/families/create", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "The Millers"
    assert len(data["invite_code"]) == 8
    assert len(data["members"]) == 1
    assert data["members"][0]["user_id"] == str(registered_user.id)


@pytest.mark.asyncio
async def test_join_family(client: AsyncClient, auth_headers: dict):
    # 1. Create family with registered_user
    fam_res = await client.post("/api/v1/families/create", json={"name": "The Millers"}, headers=auth_headers)
    invite_code = fam_res.json()["invite_code"]
    fam_id = fam_res.json()["id"]

    # 2. Register a second user (parent)
    reg2 = await client.post("/api/v1/auth/register", json={
        "email": "parent_mark@example.com",
        "password": "parentpassword123",
        "full_name": "Mark Miller",
        "role": "parent",
        "age": 52,
        "sex": "male",
        "activity_level": "moderate",
    })
    token2 = reg2.json()["access_token"]
    user2_id = reg2.json()["user"]["id"]

    # 3. Join family using invite code
    join_res = await client.post(
        "/api/v1/families/join",
        json={"invite_code": invite_code},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert join_res.status_code == 200
    data = join_res.json()
    assert data["id"] == fam_id
    assert len(data["members"]) == 2
    member_ids = [m["user_id"] for m in data["members"]]
    assert user2_id in member_ids


@pytest.mark.asyncio
async def test_join_family_invalid_code(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/families/join",
        json={"invite_code": "NONEXIST"},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert "No family circle found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_family_feed_empty(client: AsyncClient, auth_headers: dict):
    fam_res = await client.post("/api/v1/families/create", json={"name": "Feed Circle"}, headers=auth_headers)
    fam_id = fam_res.json()["id"]

    feed_res = await client.get(f"/api/v1/families/{fam_id}/feed", headers=auth_headers)
    assert feed_res.status_code == 200
    assert feed_res.json() == []
