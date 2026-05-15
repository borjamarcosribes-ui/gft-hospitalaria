from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.api.routes.cima import router as cima_router
from app.api.routes.bifimed import router as bifimed_router
from app.api.routes.gft import router as gft_router
from app.api.routes.admin import router as admin_router

app = FastAPI(title="gft-hospitalaria")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.app\.github\.dev",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-API-Key"],
)
app.include_router(health_router)
app.include_router(imports_router)
app.include_router(cima_router)
app.include_router(bifimed_router)
app.include_router(gft_router)
app.include_router(admin_router)
