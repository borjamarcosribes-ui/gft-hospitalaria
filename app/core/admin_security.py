import hmac

from fastapi import Header, HTTPException

from app.core import config


def require_admin_api_key(
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> None:
    if config.ADMIN_API_KEY is None:
        raise HTTPException(status_code=503, detail="Admin API key is not configured")

    if x_admin_api_key is None:
        raise HTTPException(status_code=401, detail="Missing admin API key")

    if not hmac.compare_digest(str(x_admin_api_key), str(config.ADMIN_API_KEY)):
        raise HTTPException(status_code=403, detail="Invalid admin API key")

    return None
