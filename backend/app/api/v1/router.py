from fastapi import APIRouter

from app.api.v1 import auth, catalog, customers, inventory, reports, sales, settings, users

api_router = APIRouter(prefix="/api/v1")
for module in (auth, users, catalog, inventory, customers, sales, reports, settings):
    api_router.include_router(module.router)
