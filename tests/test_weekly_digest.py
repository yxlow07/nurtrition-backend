import io
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from hackucdbackend.schemas.meal import AIMealAnalysis


def mock_vision(name: str, colors: list) -> AIMealAnalysis:
    return AIMealAnalysis(
        meal_name=name,
        detected_ingredients=["greens", "beans", "grains"],
        plant_colors=colors,
        upf_tier="unprocessed",
        plant_points=30,
        whole_food_points=25,
        protein_points=20,
        upf_penalty=0,
        confidence=0.95,
        reassurance_note="Great nutritious meal.",
    )


@pytest.mark.asyncio
async def test_get_weekly_digest_with_meals(client: AsyncClient, auth_headers: dict):
    # 1. Create family
    fam_res = await client.post("/api/v1/families/create", json={"name": "Healthy Squad"}, headers=auth_headers)
    fam_id = fam_res.json()["id"]

    # 2. Upload two meals for the family
    with patch("hackucdbackend.routers.meals.run_vision_analysis", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = mock_vision("Salad Bowl", ["green", "red"])
        await client.post(
            "/api/v1/meals/upload",
            files={"image": ("m1.jpg", io.BytesIO(b"img1"), "image/jpeg")},
            data={"family_id": fam_id},
            headers=auth_headers,
        )

        mock_ai.return_value = mock_vision("Carrot Soup", ["orange", "yellow_white"])
        await client.post(
            "/api/v1/meals/upload",
            files={"image": ("m2.jpg", io.BytesIO(b"img2"), "image/jpeg")},
            data={"family_id": fam_id},
            headers=auth_headers,
        )

    # 3. Call GET /api/v1/families/{id}/weekly
    with patch(
        "hackucdbackend.routers.families.generate_family_narrative_and_swap",
        new_callable=AsyncMock,
        return_value={
            "ai_family_narrative": "The Healthy Squad achieved 4 colorful botanical hits this week!",
            "recommended_grocery_swap": "Swap white bread for whole grain sourdough.",
        },
    ):
        digest_res = await client.get(f"/api/v1/families/{fam_id}/weekly", headers=auth_headers)
        assert digest_res.status_code == 200
        data = digest_res.json()
        assert data["family_id"] == fam_id
        assert data["collective_plant_count"] == 4
        assert "4 colorful botanical hits" in data["ai_family_narrative"]
        assert "whole grain sourdough" in data["recommended_grocery_swap"]
        assert "rankings" in data["leaderboard_payload"]
        assert len(data["leaderboard_payload"]["rankings"]) >= 1


@pytest.mark.asyncio
async def test_get_weekly_digest_nonexistent_family(client: AsyncClient, auth_headers: dict):
    random_id = uuid.uuid4()
    res = await client.get(f"/api/v1/families/{random_id}/weekly", headers=auth_headers)
    assert res.status_code == 404
