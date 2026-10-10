import json
import pytest
from unittest.mock import AsyncMock, patch
from httpx import Response
from hackucdbackend.schemas.meal import AIMealAnalysis
from hackucdbackend.services.ai_engine import (
    NUTRITION_JSON_SCHEMA,
    _build_openrouter_payload,
    run_vision_analysis,
)


def test_schema_conformance():
    properties = NUTRITION_JSON_SCHEMA["schema"]["properties"]
    assert "meal_name" in properties
    assert "detected_ingredients" in properties
    assert "plant_colors" in properties
    assert "upf_tier" in properties
    assert "plant_points" in properties
    assert "whole_food_points" in properties
    assert "protein_points" in properties
    assert "upf_penalty" in properties
    assert "confidence" in properties
    assert "reassurance_note" in properties
    assert NUTRITION_JSON_SCHEMA["strict"] is True


def test_payload_builder():
    payload = _build_openrouter_payload("fakeb64data", "takeout", "google/gemini-2.5-flash")
    assert payload["model"] == "google/gemini-2.5-flash"
    assert "takeout" in payload["messages"][0]["content"]
    assert payload["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_run_vision_analysis_success():
    sample_response_data = {
        "id": "gen-test-123",
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "meal_name": "Tofu Stir Fry",
                        "detected_ingredients": ["tofu", "broccoli", "brown rice"],
                        "plant_colors": ["green"],
                        "upf_tier": "unprocessed",
                        "plant_points": 25,
                        "whole_food_points": 20,
                        "protein_points": 18,
                        "upf_penalty": 0,
                        "confidence": 0.94,
                        "reassurance_note": "A wonderfully balanced plant-based meal.",
                    })
                }
            }
        ],
    }

    mock_resp = Response(status_code=200, json=sample_response_data)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await run_vision_analysis(b"sample_image_bytes", prep_context="home_cooked")

        assert isinstance(result, AIMealAnalysis)
        assert result.meal_name == "Tofu Stir Fry"
        assert result.plant_points == 25
        assert result.confidence == 0.94


@pytest.mark.asyncio
async def test_run_vision_analysis_fallback_cascade():
    # First model fails with 502, second model succeeds with 200
    fail_resp = Response(status_code=502, text="Bad Gateway on primary")
    success_resp_data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "meal_name": "Chicken Salad",
                        "detected_ingredients": ["chicken breast", "lettuce", "tomatoes"],
                        "plant_colors": ["green", "red"],
                        "upf_tier": "minimally_processed",
                        "plant_points": 20,
                        "whole_food_points": 25,
                        "protein_points": 20,
                        "upf_penalty": 0,
                        "confidence": 0.88,
                        "reassurance_note": "Nutritious and high in lean protein.",
                    })
                }
            }
        ]
    }
    success_resp = Response(status_code=200, json=success_resp_data)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [fail_resp, success_resp]
        result = await run_vision_analysis(b"sample_bytes", prep_context="takeout")

        assert result.meal_name == "Chicken Salad"
        assert mock_post.call_count == 2
