from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from hackucdbackend.core.config import settings
from hackucdbackend.core.database import init_db
from hackucdbackend.routers.auth import router as auth_router
from hackucdbackend.routers.meals import router as meals_router
from hackucdbackend.routers.families import router as families_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    await init_db()
    # Ensure uploads directory exists
    Path("uploads").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend orchestration service for mobile clients, Supabase, and OpenRouter AI gateway.",
    lifespan=lifespan,
)

# CORS Policy (PRD Section 7)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local uploads directory for fallback image retrieval
uploads_path = Path("uploads")
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include Routers
app.include_router(auth_router)
app.include_router(meals_router)
app.include_router(families_router)


@app.get("/", tags=["Health & Status"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health & Status"])
async def health_check():
    return {
        "status": "healthy",
        "openrouter_model": settings.OPENROUTER_PRIMARY_MODEL,
        "supabase_connected": bool(settings.SUPABASE_PROJECT_URL),
    }


def main():
    import uvicorn
    uvicorn.run("hackucdbackend.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
