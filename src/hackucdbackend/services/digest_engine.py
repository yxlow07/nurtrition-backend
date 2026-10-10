import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from hackucdbackend.core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DIGEST_JSON_SCHEMA = {
    "name": "family_weekly_digest",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "ai_family_narrative": {
                "type": "string",
                "description": "A warm, 2-3 sentence narrative celebrating the family's healthy choices, plant diversity, and togetherness."
            },
            "recommended_grocery_swap": {
                "type": "string",
                "description": "One actionable, nutritious, whole-food grocery swap recommendation tailored for this family."
            }
        },
        "required": ["ai_family_narrative", "recommended_grocery_swap"],
        "additionalProperties": False
    }
}


async def generate_family_narrative_and_swap(
    family_name: str,
    member_stats: List[Dict[str, Any]],
    collective_plant_count: int,
    recent_meals: List[str]
) -> Dict[str, str]:
    """Generates an empathetic weekly narrative and grocery swap using reasoning LLM via OpenRouter."""
    if not settings.OPENROUTER_API_KEY:
        return {
            "ai_family_narrative": f"Great teamwork by {family_name}! You logged {collective_plant_count} plant diversity points this week. Keep nourishing each other!",
            "recommended_grocery_swap": "Try swapping regular white rice for quinoa or cauliflower rice for extra micronutrients.",
        }

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": settings.APP_URL,
        "X-Title": "FamilyCareEats",
        "Content-Type": "application/json",
    }

    prompt = (
        f"Family Circle: '{family_name}'\n"
        f"Collective Plant Colors Count: {collective_plant_count}\n"
        f"Member Highlights: {json.dumps(member_stats)}\n"
        f"Sample Meals Eaten: {', '.join(recent_meals[:10]) if recent_meals else 'Varied home cooked meals'}\n\n"
        "Synthesize a supportive, warm weekly narrative praising progress and provide 1 practical grocery swap."
    )

    payload = {
        "model": settings.OPENROUTER_REASONING_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an empathetic, encouraging family nutritionist AI crafting weekly digest summaries."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": DIGEST_JSON_SCHEMA,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()["choices"][0]["message"]["content"]
                parsed = json.loads(data)
                return {
                    "ai_family_narrative": parsed.get("ai_family_narrative", ""),
                    "recommended_grocery_swap": parsed.get("recommended_grocery_swap", ""),
                }
            logger.warning(f"OpenRouter digest failed with status {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.warning(f"Failed to generate AI weekly digest via OpenRouter: {e}")

    # Graceful fallback
    return {
        "ai_family_narrative": (
            f"The {family_name} family had a nourishing week with vibrant meals and {collective_plant_count} colorful plant hits! "
            "Celebrating everyone's consistency and mindful eating habits."
        ),
        "recommended_grocery_swap": (
            "Swap standard snack crackers for crunchy roasted chickpeas or spiced edamame to boost plant protein and fiber."
        ),
    }
