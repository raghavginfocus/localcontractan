from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from config import get_settings

settings = get_settings()

# This creates the OpenAPI security scheme
api_key_header = APIKeyHeader(
    name=settings.api_token_header,
    auto_error=False,
)


async def verify_api_token(
    api_key: str = Security(api_key_header),
):
    # Optional bypass for local development
    if not settings.api_auth_enabled:
        return True

    if not settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API token not configured",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API token",
        )

    if api_key != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )

    return True