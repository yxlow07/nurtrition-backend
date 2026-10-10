import base64
import logging
from typing import Optional
import httpx
from fastapi import HTTPException

from hackucdbackend.core.config import settings
from hackucdbackend.schemas.meal import AIMealAnalysis

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

NUTRITION_JSON_SCHEMA = {
    "name": "meal_nutrition_evaluation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "meal_name": {"type": "string"},
            "detected_ingredients": {"type": "array", "items": {"type": "string"}},
            "plant_colors": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["green", "red", "orange", "yellow_white", "purple"],
                },
            },
            "upf_tier": {
                "type": "string",
                "enum": ["unprocessed", "minimally_processed", "processed", "ultra_processed"],
            },
            "plant_points": {"type": "integer"},
            "whole_food_points": {"type": "integer"},
            "protein_points": {"type": "integer"},
            "upf_penalty": {"type": "integer"},
            "confidence": {"type": "number"},
            "reassurance_note": {"type": "string"},
        },
        "required": [
            "meal_name",
            "detected_ingredients",
            "plant_colors",
            "upf_tier",
            "plant_points",
            "whole_food_points",
            "protein_points",
            "upf_penalty",
            "confidence",
            "reassurance_note",
        ],
        "additionalProperties": False,
    },
}


def _build_openrouter_payload(b64_image: str, prep_context: str, model: str) -> dict:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a nutritional assessment engine for family care. "
                    "Evaluate plates using ADDITIVE nutrition: reward botanical colors, "
                    "unprocessed ingredients, and balanced protein. "
                    "Do NOT estimate hidden calories or exact grams. "
                    f"Cooking context provided by user: '{prep_context}'."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this meal photo:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                ],
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": NUTRITION_JSON_SCHEMA,
        },
    }


async def run_vision_analysis(
    image_bytes: bytes,
    prep_context: str = "home_cooked",
    override_model: Optional[str] = None,
) -> AIMealAnalysis:
    """Dispatches meal image to OpenRouter multimodal model with strict JSON schema enforcement.
    Cascades to fallback model on upstream failure or model unavailability.
    """
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": settings.APP_URL,
        "X-Title": "FamilyCareEats",
        "Content-Type": "application/json",
    }

    models_to_try = [
        override_model or settings.OPENROUTER_PRIMARY_MODEL,
        settings.OPENROUTER_FALLBACK_MODEL,
    ]

    last_error: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        for model in models_to_try:
            if not model:
                continue
            payload = _build_openrouter_payload(b64_image, prep_context, model)
            try:
                resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return AIMealAnalysis.model_validate_json(content)

                logger.warning(
                    f"OpenRouter model {model} returned status {resp.status_code}: {resp.text}"
                )
                last_error = HTTPException(
                    status_code=502,
                    detail=f"OpenRouter upstream error ({resp.status_code}): {resp.text}",
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning(f"OpenRouter connection error with model {model}: {exc}")
                last_error = HTTPException(
                    status_code=504,
                    detail=f"OpenRouter request timed out or network error: {str(exc)}",
                )
            except Exception as exc:
                logger.exception(f"Unexpected error calling OpenRouter with model {model}: {exc}")
                last_error = HTTPException(
                    status_code=500,
                    detail=f"AI pipeline failure: {str(exc)}",
                )

    if last_error:
        raise last_error

    raise HTTPException(status_code=500, detail="AI multimodal analysis failed on all models.")
