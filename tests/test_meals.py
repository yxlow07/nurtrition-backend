import io
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from hackucdbackend.models.user import User
from hackucdbackend.schemas.meal import AIMealAnalysis


def sample_vision_analysis(
    confidence: float = 0.92,
    plant_points: int = 30,
    whole_food_points: int = 25,
    protein_points: int = 20,
    upf_penalty: int = 0,
) -> AIMealAnalysis:
    return AIMealAnalysis(
        meal_name="Stir-fried Tofu with Broccoli and Brown Rice",
        detected_ingredients=["tofu", "broccoli", "brown rice", "carrots"],
        plant_colors=["green", "orange"],
        upf_tier="unprocessed",
        plant_points=plant_points,
        whole_food_points=whole_food_points,
        protein_points=protein_points,
        upf_penalty=upf_penalty,
        confidence=confidence,
        reassurance_note="Nutrient-dense dinner rich in plant protein, dietary fiber, and dark greens.",
    )


@pytest.mark.asyncio
async def test_upload_meal_success(client: AsyncClient, auth_headers: dict, registered_user: User):
    # Create family first
    fam_res = await client.post("/api/v1/families/create", json={"name": "Dinner Circle"}, headers=auth_headers)
    family_id = fam_res.json()["id"]

    fake_image_file = ("plate.jpg", io.BytesIO(b"fake_jpeg_image_data_here"), "image/jpeg")

    with patch(
        "hackucdbackend.routers.meals.run_vision_analysis",
        new_callable=AsyncMock,
        return_value=sample_vision_analysis(),
    ):
        response = await client.post(
            "/api/v1/meals/upload",
            files={"image": fake_image_file},
            data={"preparation_context": "home_cooked", "family_id": family_id},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "meal_id" in data
        assert data["meal_name"] == "Stir-fried Tofu with Broccoli and Brown Rice"
        assert data["scores"]["plant_points"] == 30
        assert data["scores"]["whole_food_points"] == 25
        assert data["scores"]["protein_points"] == 20
        assert data["scores"]["upf_penalty"] == 0
        assert data["scores"]["raw_total"] == 75
        # registered_user is student: with 2 plant colors -> 75 * 1.15 = 86
        assert data["normalized_score"] == 86
        assert "storage/v1/object/public/meals" in data["image_url"] or "/static/uploads" in data["image_url"]


@pytest.mark.asyncio
async def test_upload_meal_low_confidence_fallback(client: AsyncClient, auth_headers: dict):
    # When confidence < 0.50, default score is 50 and requires_manual_tags = True
    fake_image_file = ("fuzzy_plate.jpg", io.BytesIO(b"fuzzy_image_data"), "image/jpeg")

    with patch(
        "hackucdbackend.routers.meals.run_vision_analysis",
        new_callable=AsyncMock,
        return_value=sample_vision_analysis(confidence=0.45),
    ):
        response = await client.post(
            "/api/v1/meals/upload",
            files={"image": fake_image_file},
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["normalized_score"] == 50
        meal_id = data["meal_id"]

        # Audit breakdown should indicate requires_manual_tags = True
        audit_res = await client.get(f"/api/v1/meals/{meal_id}", headers=auth_headers)
        assert audit_res.status_code == 200
        audit_data = audit_res.json()
        assert audit_data["requires_manual_tags"] is True
        assert audit_data["normalized_score"] == 50


@pytest.mark.asyncio
async def test_meal_reaction_toggle(client: AsyncClient, auth_headers: dict):
    # 1. Upload a meal
    fake_image_file = ("meal.jpg", io.BytesIO(b"image_bytes"), "image/jpeg")
    with patch(
        "hackucdbackend.routers.meals.run_vision_analysis",
        new_callable=AsyncMock,
        return_value=sample_vision_analysis(),
    ):
        up_res = await client.post("/api/v1/meals/upload", files={"image": fake_image_file}, headers=auth_headers)
        meal_id = up_res.json()["meal_id"]

    # 2. Toggle reaction ON
    rxn1 = await client.post(f"/api/v1/meals/{meal_id}/react", json={"emoji": "❤️"}, headers=auth_headers)
    assert rxn1.status_code == 200
    assert rxn1.json()["action"] == "added"
    assert "❤️" in rxn1.json()["reactions"]

    # 3. Toggle reaction OFF (same emoji by same user)
    rxn2 = await client.post(f"/api/v1/meals/{meal_id}/react", json={"emoji": "❤️"}, headers=auth_headers)
    assert rxn2.status_code == 200
    assert rxn2.json()["action"] == "removed"
    assert "❤️" not in rxn2.json()["reactions"]


@pytest.mark.asyncio
async def test_upload_meal_empty_file(client: AsyncClient, auth_headers: dict):
    fake_empty_file = ("empty.jpg", io.BytesIO(b""), "image/jpeg")
    res = await client.post("/api/v1/meals/upload", files={"image": fake_empty_file}, headers=auth_headers)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_meal_invalid_mime_type(client: AsyncClient, auth_headers: dict):
    fake_doc_file = ("doc.pdf", io.BytesIO(b"fake_pdf_content"), "application/pdf")
    res = await client.post("/api/v1/meals/upload", files={"image": fake_doc_file}, headers=auth_headers)
    assert res.status_code == 400
    assert "valid image" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_meal_audit_not_found(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    res = await client.get(f"/api/v1/meals/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_react_to_nonexistent_meal(client: AsyncClient, auth_headers: dict):
    fake_id = uuid.uuid4()
    res = await client.post(f"/api/v1/meals/{fake_id}/react", json={"emoji": "👍"}, headers=auth_headers)
    assert res.status_code == 404
