from fastapi import Header, HTTPException

import config


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Raise 401 if the x-api-key header is missing or incorrect."""
    if not x_api_key or x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
