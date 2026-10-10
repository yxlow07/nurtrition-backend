import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_billing_config(client: AsyncClient):
    response = await client.get("/api/v1/billing/config")
    assert response.status_code == 200
    data = response.json()
    assert "publishable_key" in data
    assert "plans" in data
    assert "monthly" in data["plans"]
    assert "annual" in data["plans"]


@pytest.mark.asyncio
async def test_billing_status_free(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/billing/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["is_subscriber"] is False
    assert "tier" in data


@pytest.mark.asyncio
async def test_create_checkout_session(client: AsyncClient, auth_headers: dict):
    payload = {"plan_id": "monthly"}
    response = await client.post(
        "/api/v1/billing/create-checkout-session",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "checkout_url" in data
    assert data["plan_id"] == "monthly"


@pytest.mark.asyncio
async def test_confirm_payment_activates_pro(client: AsyncClient, auth_headers: dict):
    confirm_res = await client.post(
        "/api/v1/billing/confirm-payment?session_id=cs_test_sample&plan_id=monthly",
        headers=auth_headers,
    )
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()
    assert confirm_data["ok"] is True
    assert "Nurtrition Circle Pro" in confirm_data["tier"]

    # Verify status now reflects active subscription
    status_res = await client.get("/api/v1/billing/status", headers=auth_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["is_subscriber"] is True
    assert status_data["tier"] == "Nurtrition Circle Pro"
