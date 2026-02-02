"""Pydantic schemas for the relay API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CaptureIn(BaseModel):
    """Incoming capture request."""

    content: str = ""
    url: Optional[str] = None
    source_url: Optional[str] = None
    title: Optional[str] = Field(None, max_length=500)
    image_data: Optional[str] = None  # base64, max ~10MB

    @field_validator("content")
    @classmethod
    def content_max_size(cls, v: str) -> str:
        if len(v) > 512_000:  # 500KB
            raise ValueError("content exceeds 500KB limit")
        return v

    @field_validator("url", "source_url")
    @classmethod
    def url_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) > 2048:
            raise ValueError("URL exceeds 2048 character limit")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("image_data")
    @classmethod
    def image_max_size(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 10_485_760:  # ~10MB base64
            raise ValueError("image_data exceeds 10MB limit")
        return v

    def model_post_init(self, __context) -> None:
        if not self.content and not self.url:
            raise ValueError("Either content or url must be provided")


class CaptureOut(BaseModel):
    """Response after creating a capture."""

    id: int
    status: str
    created_at: datetime


class PendingCapture(BaseModel):
    """Full capture data returned to pull client."""

    id: int
    content: str
    url: Optional[str]
    source_url: Optional[str]
    title: Optional[str]
    image_data: Optional[str]
    created_at: datetime
