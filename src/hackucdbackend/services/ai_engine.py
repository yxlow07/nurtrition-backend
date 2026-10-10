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
            "meal_name": {"type": "string", "description": "Concise name or description of the dish"},
            "detected_ingredients": {"type": "array", "items": {"type": "string"}, "description": "Identifiable ingredients on plate"},
            "plant_colors": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["green", "red", "orange", "yellow_white", "purple"],
                },
                "description": "Distinct botanical plant colors present on the plate",
            },
            "upf_tier": {
                "type": "string",
                "enum": ["unprocessed", "minimally_processed", "processed", "ultra_processed"],
                "description": "NOVA processing classification level",
            },
            "plant_points": {
                "type": "integer",
                "description": "Additive plant diversity points between 0 and 50 (~10 points per unique plant color category present)",
            },
            "whole_food_points": {
                "type": "integer",
                "description": "Points based on whole ingredient density between 0 and 30 (0 = highly refined, 15 = balanced, 30 = fresh whole foods)",
            },
            "protein_points": {
                "type": "integer",
                "description": "Points for presence of quality protein between 0 and 20 (0 = negligible, 10 = moderate, 20 = prominent quality protein)",
            },
            "upf_penalty": {
                "type": "integer",
                "description": "Deduction if ultra-processed foods dominate, between 0 and 20 (0 = unprocessed, 5 = processed, 15-20 = heavily ultra-processed)",
            },
            "confidence": {"type": "number", "description": "Vision detection confidence between 0.0 and 1.0"},
            "reassurance_note": {"type": "string", "description": "A warm, single-sentence note framed for parents or students"},
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
    system_prompt = (
        "You are an expert nutritional assessment engine for family care. "
        "Evaluate plates using an ADDITIVE scoring model on a 0-100 total scale:\n"
        "- plant_points (0 to 50): Award ~10 points per distinct botanical color category detected "
        "(green, red, orange, yellow_white, purple). E.g., 1 color = 10, 2 colors = 20, 3 colors = 30, 4 colors = 40, 5 colors = 50.\n"
        "- whole_food_points (0 to 30): Award points for density of whole, unprocessed or minimally processed ingredients. "
        "0 = none/refined, 15 = moderate, 30 = predominantly fresh whole foods.\n"
        "- protein_points (0 to 20): Award points for presence of quality protein (eggs, poultry, fish, tofu, beans, lean meats, Greek yogurt). "
        "0 = negligible, 10 = moderate, 20 = strong portion of quality protein.\n"
        "- upf_penalty (0 to 20): Deduct points ONLY if ultra-processed foods dominate the plate. "
        "0 = none/unprocessed, 5 = minor processed items, 15-20 = heavily ultra-processed foods (deep-fried, soda, candy).\n"
        "IMPORTANT: Do NOT use small 1-5 scales! Output full scale integer points (e.g. plant_points: 30, whole_food_points: 22, protein_points: 18, upf_penalty: 5).\n"
        "Do NOT estimate hidden calories or exact grams. Cooking context provided by user: '" + prep_context + "'."
    )
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
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


def _sanitize_analysis(analysis: AIMealAnalysis) -> AIMealAnalysis:
    """Safeguard: Detect if an AI model returned 1-5 star ratings instead of 0-100 rubric points, and auto-scale."""
    if (
        analysis.confidence >= 0.3
        and analysis.whole_food_points <= 5
        and analysis.protein_points <= 5
        and analysis.plant_points <= 5
        and (analysis.whole_food_points > 0 or analysis.protein_points > 0 or analysis.plant_points > 0)
    ):
        logger.warning("Detected 1-5 star scale from AI model; normalizing to 0-100 rubric.")
        scaled_plant = min(50, len(analysis.plant_colors) * 10) if analysis.plant_colors else analysis.plant_points * 10
        scaled_whole = int((analysis.whole_food_points / 5.0) * 30)
        scaled_protein = int((analysis.protein_points / 5.0) * 20)
        scaled_penalty = int((analysis.upf_penalty / 5.0) * 20)

        analysis.plant_points = max(0, min(50, scaled_plant))
        analysis.whole_food_points = max(0, min(30, scaled_whole))
        analysis.protein_points = max(0, min(20, scaled_protein))
        analysis.upf_penalty = max(0, min(20, scaled_penalty))

    return analysis


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
                    analysis = AIMealAnalysis.model_validate_json(content)
                    return _sanitize_analysis(analysis)

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
