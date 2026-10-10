from hackucdbackend.routers.auth import router as auth_router
from hackucdbackend.routers.meals import router as meals_router
from hackucdbackend.routers.families import router as families_router

__all__ = ["auth_router", "meals_router", "families_router"]
