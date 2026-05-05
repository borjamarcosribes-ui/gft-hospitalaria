from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.api.routes.cima import router as cima_router
from app.api.routes.gft import router as gft_router

app = FastAPI(title="gft-hospitalaria")
app.include_router(health_router)
app.include_router(imports_router)
app.include_router(cima_router)
app.include_router(gft_router)
