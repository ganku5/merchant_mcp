"""Webhook event models."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

from .endpoint import PayloadSchema


class RetryPolicy(BaseModel):
    """Webhook retry policy."""
    max_retries: int = Field(default=5, ge=0)
    retry_intervals: list[int] = Field(default_factory=lambda: [5, 10, 30, 60, 300])
    timeout_seconds: int = Field(default=30)


class WebhookEvent(BaseModel):
    """Webhook event definition."""
    event_type: str = Field(..., description="Event name")
    description: str = Field(..., description="What triggers this event")
    payload_schema: PayloadSchema
    signature_algorithm: Literal["hmac_sha256", "hmac_sha512"] = "hmac_sha256"
    retry_policy: RetryPolicy
    idempotency_key_field: str = Field(..., description="Payload field serving as idempotency key")
    ordering_guarantee: str = Field(default="unordered", description="Delivery ordering guarantee")
    sample_payload: dict = Field(default_factory=dict)
