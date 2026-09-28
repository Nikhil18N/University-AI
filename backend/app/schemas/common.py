"""Common response schemas."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    services: dict[str, str]
