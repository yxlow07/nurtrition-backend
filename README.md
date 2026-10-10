# FamilyCareEats Backend

Asynchronous Python orchestration service built on **FastAPI** connecting mobile clients, **Supabase** (PostgreSQL + Object Storage), and the **OpenRouter** AI gateway (Gemini 3.8 Flash multimodal & GPT 6 Luna reasoning LLMs).

---

## Features

- **Low-Latency Meal Ingestion:** Multipart meal photo uploads with fast vision evaluation and async object storage.
- **OpenRouter Multimodal Vision Pipeline:** Structured JSON Schema evaluation extracting ingredients, botanical plant colors, UPF tier, and nutritional points with automatic model fallback routing.
- **Deterministic Demographic Scoring Engine:** Additive nutritional scoring adjusted with demographic life-stage multipliers (students, parents, active/athletes).
- **Family Circles & Social Reactions:** Group circles with 8-character invite codes, chronological family feed timelines, and 1-tap reaction emoji toggles.
- **Weekly Batch Digests:** Member leaderboard calculation and empathetic AI family narrative with evidence-based grocery swap recommendations.

---

## Project Structure

```text
src/hackucdbackend/
├── main.py                     # FastAPI application setup, CORS, lifespan, routes
├── core/
│   ├── config.py               # Pydantic Settings and environment configuration
│   ├── database.py             # Async SQLAlchemy engine and session dependency
│   └── security.py             # JWT bearer auth, X-User-Id support, get_current_user
├── models/
│   ├── base.py                 # Declarative Base, cross-dialect GUID, StringList, and JSON types
│   ├── user.py                 # User model with demographic profile attributes
│   ├── family.py               # FamilyGroup and FamilyMember models
│   ├── meal.py                 # Meal and MealReaction models
│   └── digest.py               # WeeklyDigest model
├── schemas/
│   ├── user.py                 # DemographicProfile, UserRegister, UserMe schemas
│   ├── meal.py                 # AIMealAnalysis, MealCreate, MealAudit, FeedItem schemas
│   └── family.py               # FamilyCreate, FamilyJoin, WeeklyDigest schemas
├── services/
│   ├── ai_engine.py            # OpenRouter multimodal vision analysis (strict JSON schema)
│   ├── scoring.py              # Additive scoring engine & demographic normalization
│   ├── storage.py              # Supabase Object Storage upload with local disk fallback
│   └── digest_engine.py        # Weekly family digest reasoning synthesis
└── routers/
    ├── auth.py                 # POST /api/v1/auth/register, GET /api/v1/users/me
    ├── meals.py                # POST /api/v1/meals/upload, GET /api/v1/meals/{id}, POST react
    └── families.py             # POST create/join family, GET feed, GET weekly digest
tests/
├── conftest.py                 # Async test client & in-memory test database fixture
├── test_ai_engine.py           # Unit tests for vision pipeline & schema validation
├── test_auth.py                # Unit tests for registration and profile auth
├── test_families.py            # Unit tests for family circle creation, join, and feeds
├── test_main.py                # Unit tests for health checks and CORS policies
├── test_meals.py               # Unit tests for meal upload, low-confidence tags, reactions
├── test_scoring.py             # Unit tests for scoring calculations & life-stage bonuses
└── test_weekly_digest.py       # Unit tests for weekly leaderboard & AI digest synthesis
```

---

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Register user with demographic profile & return access token |
| `GET` | `/api/v1/users/me` | Fetch authenticated user profile & active family ID |
| `POST` | `/api/v1/meals/upload` | Multipart photo upload, VLM evaluation, demographic score, background persist |
| `GET` | `/api/v1/meals/{meal_id}` | Retrieve complete meal audit breakdown and reactions |
| `POST` | `/api/v1/meals/{id}/react` | 1-tap reaction emoji toggle (added / removed) |
| `POST` | `/api/v1/families/create` | Instantiate family circle & generate 8-character invite code |
| `POST` | `/api/v1/families/join` | Join family circle via invite code |
| `GET` | `/api/v1/families/{id}/feed` | Chronological paginated meal timeline with reactions |
| `GET` | `/api/v1/families/{id}/weekly` | Current week member leaderboard & synthesized AI narrative |
| `GET` | `/health` | Service health status |
| `GET` | `/docs` | Interactive Swagger API documentation |

---

## Running Locally

### 1. Environment Configuration

Ensure `.env` contains:
```env
SUPABASE_PROJECT_URL=https://<your-project>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<your-key>
SUPABASE_DIRECT_CONNECTION=postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres
DATABASE_URL=sqlite+aiosqlite:///./hackucd.db
OPENROUTER_API_KEY=sk-or-v1-...
APP_URL=http://localhost:8000
JWT_SECRET=supersecret-key
```

### 2. Start the Server

```cmd
cmd.exe /c "set PYTHONPATH=src && uv run uvicorn hackucdbackend.main:app --reload --host 0.0.0.0 --port 8000"
```

Access Swagger UI at `http://localhost:8000/docs`.

### 3. Run the Test Suite

```cmd
cmd.exe /c "set PYTHONPATH=src && uv run python -m pytest tests"
```
