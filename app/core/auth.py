import secrets

from fastapi import HTTPException, Request

from app.core.config import get_settings

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def review_auth(request: Request) -> None:
    if not get_settings().AUTH_ENABLED:
        return
    """Review API: open for local dev, bearer token required whenever CONTROL_API_TOKEN is set (any deployment)."""
    token = get_settings().CONTROL_API_TOKEN
    if token and not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
        raise HTTPException(401, "Missing or invalid bearer token")


def control_auth(request: Request) -> None:
    if not get_settings().AUTH_ENABLED:
        return
    token = get_settings().CONTROL_API_TOKEN
    if token:
        header = request.headers.get("authorization", "")
        if not secrets.compare_digest(header, f"Bearer {token}"):
            raise HTTPException(401, "Missing or invalid bearer token")
    elif (request.client.host if request.client else "") not in LOCAL_HOSTS:
        raise HTTPException(403, "Control API accepts only 127.0.0.1 unless CONTROL_API_TOKEN is set")
