from fastapi import APIRouter, Depends

from app.core.admin_security import require_admin_api_key

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def admin_health(_: None = Depends(require_admin_api_key)):
    return {"status": "ok"}
