"""
Shared API response models used across multiple routers.
"""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Standard error envelope returned by all 4xx/5xx responses."""

    detail: str
