from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router

app = FastAPI(title="gft-hospitalaria")
app.include_router(health_router)
app.include_router(imports_router)
