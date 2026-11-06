from fastapi import APIRouter

from app.routers.health import router as health_router
from app.routers.model_info import router as model_info_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/api")
api_router.include_router(model_info_router, prefix="/api")
