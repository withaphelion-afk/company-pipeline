import secrets

from fastapi import HTTPException, Request

from app.core.config import get_settings

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def control_auth(request: Request) -> None:
    token = get_settings().CONTROL_API_TOKEN
    if token:
        header = request.headers.get("authorization", "")
        if not secrets.compare_digest(header, f"Bearer {token}"):
            raise HTTPException(401, "Missing or invalid bearer token")
    elif (request.client.host if request.client else "") not in LOCAL_HOSTS:
        raise HTTPException(403, "Control API accepts only 127.0.0.1 unless CONTROL_API_TOKEN is set")
