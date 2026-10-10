# Backend Product Requirements Document (PRD)

---

## 1. System Scope & Core Responsibilities

The backend is an asynchronous Python service built on **FastAPI** that acts as the orchestrator between mobile clients, Supabase (PostgreSQL + Object Storage), and the OpenRouter AI gateway.

Its primary responsibilities are:

1. **Low-Latency Meal Ingestion:** Accept multipart image uploads, persist raw assets to Supabase Storage, and extract metadata in under 300 ms.
2. **OpenRouter Multimodal Pipeline:** Dispatch meal photos to fast vision models with strict JSON schema enforcement.
3. **Deterministic Scoring Engine:** Calculate an additive nutritional score (plant diversity, whole-food index, protein balance) adjusted for individual demographic baselines.
4. **Asymmetric Feed & Digest Aggregation:** Serve filtered family feeds, real-time reactions, and schedule weekly batch synthesis reports using reasoning LLMs.

---

## 2. Database Schema (PostgreSQL / Supabase)

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users & Demographic Profiles
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('student', 'parent', 'member')),
    age INT NOT NULL,
    sex VARCHAR(20) NOT NULL CHECK (sex IN ('male', 'female', 'other')),
    activity_level VARCHAR(30) DEFAULT 'moderate' CHECK (activity_level IN ('sedentary', 'moderate', 'active', 'athlete')),
    dietary_flags TEXT[] DEFAULT '{}', -- e.g. ['halal', 'vegetarian']
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Family Circles
CREATE TABLE family_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    invite_code VARCHAR(8) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE family_members (
    family_id UUID REFERENCES family_groups(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (family_id, user_id)
);

-- 3. Meal Logs & AI Output
CREATE TABLE meals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    family_id UUID REFERENCES family_groups(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    preparation_context VARCHAR(30) DEFAULT 'home_cooked' CHECK (preparation_context IN ('home_cooked', 'takeout', 'dining_hall', 'packaged')),
    meal_name VARCHAR(150),
    detected_ingredients TEXT[] DEFAULT '{}',
    plant_colors TEXT[] DEFAULT '{}', -- ['green', 'red', 'orange', 'purple', 'yellow_white']
    upf_tier VARCHAR(30) CHECK (upf_tier IN ('unprocessed', 'minimally_processed', 'processed', 'ultra_processed')),
    plant_score INT NOT NULL DEFAULT 0,
    whole_food_score INT NOT NULL DEFAULT 0,
    protein_score INT NOT NULL DEFAULT 0,
    penalty_score INT NOT NULL DEFAULT 0,
    raw_score INT NOT NULL DEFAULT 0,
    normalized_score INT NOT NULL DEFAULT 0,
    reassurance_note TEXT,
    ai_confidence NUMERIC(3, 2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Social Reactions
CREATE TABLE meal_reactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meal_id UUID REFERENCES meals(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    emoji VARCHAR(10) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(meal_id, user_id, emoji)
);

-- 5. Weekly Family Digests
CREATE TABLE weekly_digests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    family_id UUID REFERENCES family_groups(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    leaderboard_payload JSONB NOT NULL,
    collective_plant_count INT NOT NULL,
    ai_family_narrative TEXT NOT NULL,
    recommended_grocery_swap TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

```

---

## 3. Pydantic Data Contracts (`schemas.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class DemographicProfile(BaseModel):
    age: int = Field(..., ge=1, le=120)
    sex: str = Field(..., pattern="^(male|female|other)$")
    activity_level: str = Field(default="moderate", pattern="^(sedentary|moderate|active|athlete)$")
    role: str = Field(..., pattern="^(student|parent|member)$")

# Schema enforced strictly via OpenRouter json_schema
class AIMealAnalysis(BaseModel):
    meal_name: str = Field(description="Name or concise description of the plate")
    detected_ingredients: List[str] = Field(description="Identifiable ingredients on plate")
    plant_colors: List[str] = Field(description="Detected plant colors: green, red, orange, yellow_white, purple")
    upf_tier: str = Field(description="One of: unprocessed, minimally_processed, processed, ultra_processed")
    plant_points: int = Field(ge=0, le=50, description="Additive plant diversity points")
    whole_food_points: int = Field(ge=0, le=30, description="Points based on whole ingredient density")
    protein_points: int = Field(ge=0, le=20, description="Points for presence of lean/whole protein")
    upf_penalty: int = Field(ge=0, le=20, description="Deduction if ultra-processed foods dominate")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in food detection")
    reassurance_note: str = Field(description="A warm, single-sentence note framed for parents")

class MealCreateResponse(BaseModel):
    meal_id: UUID
    image_url: str
    meal_name: str
    scores: dict
    normalized_score: int
    reassurance_note: str
    created_at: datetime

class FeedItemResponse(BaseModel):
    meal_id: UUID
    user_name: str
    user_role: str
    image_url: str
    meal_name: str
    normalized_score: int
    plant_colors: List[str]
    reassurance_note: str
    reactions: List[str]
    created_at: datetime

```

---

## 4. REST API Endpoint Specifications

```
Auth / Profiles
├── POST /api/v1/auth/register            -> Create user with demographic profile
└── GET  /api/v1/users/me                 -> Retrieve current user & active family ID

Meals & Ingestion
├── POST /api/v1/meals/upload             -> Upload photo, execute VLM, compute score, save
└── GET  /api/v1/meals/{meal_id}          -> Fetch meal audit breakdown

Family & Feed
├── POST /api/v1/families/create          -> Instantiate family circle & return invite code
├── POST /api/v1/families/join            -> Join via 8-character invite code
├── GET  /api/v1/families/{id}/feed       -> Chronological paginated meal timeline
├── POST /api/v1/meals/{id}/react         -> 1-tap reaction emoji toggle
└── GET  /api/v1/families/{id}/weekly     -> Current week leaderboard & aggregate goals

```

### Detailed Endpoint Contract: `POST /api/v1/meals/upload`

* **Request Format:** `multipart/form-data`
* `image`: Binary file (image/jpeg, image/png, image/webp; max 10MB)
* `preparation_context`: String (`home_cooked`, `takeout`, `dining_hall`, `packaged`)
* `family_id`: UUID


* **Response Status:** `201 Created`
* **Response Body:**

```json
{
  "meal_id": "8d3e2304-4b51-4043-982f-897b5e408ec9",
  "image_url": "https://<supabase-id>.supabase.co/storage/v1/object/public/meals/user_1/meal_9.webp",
  "meal_name": "Stir-fried Tofu with Broccoli and Brown Rice",
  "scores": {
    "plant_points": 30,
    "whole_food_points": 25,
    "protein_points": 20,
    "upf_penalty": 0,
    "raw_total": 75
  },
  "normalized_score": 83,
  "reassurance_note": "Nutrient-dense dinner rich in plant protein, dietary fiber, and dark greens.",
  "created_at": "2026-10-10T12:00:00Z"
}

```

---

## 5. OpenRouter Multimodal Engine & Scoring Pipeline

### 5.1 OpenRouter Client Implementation (`services/ai_engine.py`)

Using OpenRouter's structured output support (`response_format: {"type": "json_schema"}`) guarantees exact, parseable Pydantic validation without post-processing regex failures:

```python
import base64
import httpx
from fastapi import HTTPException
from app.core.config import settings
from app.schemas import AIMealAnalysis

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

async def run_vision_analysis(image_bytes: bytes, prep_context: str) -> AIMealAnalysis:
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": settings.APP_URL,
        "X-Title": "FamilyCareEats",
        "Content-Type": "application/json"
    }

    # Strict JSON Schema definition for OpenRouter
    schema_definition = {
        "name": "meal_nutrition_evaluation",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "meal_name": {"type": "string"},
                "detected_ingredients": {"type": "array", "items": {"type": "string"}},
                "plant_colors": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["green", "red", "orange", "yellow_white", "purple"]}
                },
                "upf_tier": {
                    "type": "string",
                    "enum": ["unprocessed", "minimally_processed", "processed", "ultra_processed"]
                },
                "plant_points": {"type": "integer"},
                "whole_food_points": {"type": "integer"},
                "protein_points": {"type": "integer"},
                "upf_penalty": {"type": "integer"},
                "confidence": {"type": "number"},
                "reassurance_note": {"type": "string"}
            },
            "required": [
                "meal_name", "detected_ingredients", "plant_colors", 
                "upf_tier", "plant_points", "whole_food_points", 
                "protein_points", "upf_penalty", "confidence", "reassurance_note"
            ],
            "additionalProperties": False
        }
    }

    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a nutritional assessment engine for family care. "
                    "Evaluate plates using ADDITIVE nutrition: reward botanical colors, "
                    "unprocessed ingredients, and balanced protein. "
                    "Do NOT estimate hidden calories or exact grams. "
                    f"Cooking context provided by user: '{prep_context}'."
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this meal photo:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": schema_definition
        }
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return AIMealAnalysis.model_validate_json(content)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"OpenRouter upstream error: {exc.response.text}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"AI pipeline failure: {str(exc)}")

```

### 5.2 Demographic Normalization Algorithm (`services/scoring.py`)

Raw AI scores range from 0 to 100. The normalization engine adjusts the final score using life-stage multipliers:

```python
from app.schemas import AIMealAnalysis, DemographicProfile

def calculate_normalized_score(analysis: AIMealAnalysis, profile: DemographicProfile) -> int:
    raw = (
        analysis.plant_points +
        analysis.whole_food_points +
        analysis.protein_points -
        analysis.upf_penalty
    )
    raw = max(0, min(100, raw))

    # Weight adjustments based on life-stage demands
    multiplier = 1.0

    if profile.role == "student":
        # Students often suffer plant/micronutrient deficits; give 15% boost for plant diversity
        if len(analysis.plant_colors) >= 2:
            multiplier += 0.15
    elif profile.role == "parent":
        # Aging adults benefit from unprocessed diets; penalize UPF more stringently
        if analysis.upf_tier in ["processed", "ultra_processed"]:
            multiplier -= 0.15
        elif analysis.upf_tier == "unprocessed":
            multiplier += 0.10

    if profile.activity_level in ["active", "athlete"] and analysis.protein_points >= 15:
        multiplier += 0.10

    return int(max(10, min(100, raw * multiplier)))

```

---

## 6. Storage & Background Task Flow

To keep API response times minimal, heavy side-effects run via FastAPI `BackgroundTasks`:

```python
# routers/meals.py snippet
from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from app.services.ai_engine import run_vision_analysis
from app.services.scoring import calculate_normalized_score
from app.services.storage import upload_image_to_supabase

router = APIRouter(prefix="/meals", tags=["Meals"])

@router.post("/upload", status_code=201)
async def upload_meal(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    preparation_context: str = Form("home_cooked"),
    current_user = Depends(get_current_user)
):
    image_bytes = await image.read()
    
    # 1. Direct synchronous execution of VLM to return instant feedback
    ai_result = await run_vision_analysis(image_bytes, preparation_context)
    normalized_score = calculate_normalized_score(ai_result, current_user.profile)
    
    # 2. Upload file to Supabase Object Storage & write DB records asynchronously
    background_tasks.add_task(
        persist_meal_and_storage,
        user_id=current_user.id,
        family_id=current_user.family_id,
        image_bytes=image_bytes,
        ai_data=ai_result,
        normalized_score=normalized_score
    )
    
    return {
        "status": "success",
        "meal_name": ai_result.meal_name,
        "normalized_score": normalized_score,
        "reassurance_note": ai_result.reassurance_note,
        "plant_colors": ai_result.plant_colors
    }

```

---

## 7. Non-Functional Requirements & Error Handling

| Metric / Failure Mode | Target SLA / Strategy |
| --- | --- |
| **P95 Ingestion Latency** | **< 2.5 seconds** (Image resizing on mobile client + Gemini 2.0 Flash inference via OpenRouter). |
| **OpenRouter Outage Fallback** | Fallback routing configured in OpenRouter to cascade: `google/gemini-2.0-flash-001` $\rightarrow$ `meta-llama/llama-3.2-11b-vision-instruct`. |
| **Unidentifiable / Low-Confidence Photo** | If `confidence < 0.50`, persist record with default score `50` and append a flag `requires_manual_tags = True`. |
| **Database Connection Pooling** | Managed via async SQLAlchemy pool (`pool_size=10`, `max_overflow=20`) connecting to Supabase Transaction Pooler (port 6543). |
| **CORS Policy** | Whitelist mobile scheme origins and Expo development servers during testing (`localhost:8081`). |