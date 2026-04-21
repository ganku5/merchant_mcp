"""Endpoint specification models."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class FieldConstraints(BaseModel):
    """Constraints for a payload field."""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None


class PayloadField(BaseModel):
    """Individual field definition in an API payload."""
    field_name: str = Field(..., description="JSON key name")
    json_path: str = Field(..., description="Full JSONPath expression")
    field_type: Literal["string", "integer", "number", "boolean", "object", "array"]
    required: bool = Field(default=False, description="Whether field is mandatory")
    format: Optional[str] = Field(None, description="JSON Schema format")
    constraints: Optional[FieldConstraints] = None
    valid_values: Optional[list[str]] = Field(None, description="Enum values if constrained")
    default: Optional[Any] = None
    example: Optional[Any] = None
    description: str = Field(..., description="Condensed field description for LLM")
    children: Optional[list["PayloadField"]] = None
    item_schema: Optional["PayloadField"] = Field(None, description="Item schema for arrays")
    sensitive: bool = Field(default=False, description="Contains PII/sensitive data")
    bank_specific_notes: Optional[dict[str, str]] = None


PayloadField.model_rebuild()


class RateLimit(BaseModel):
    """Rate limit configuration."""
    requests_per_minute: int
    burst_allowance: int


class ErrorResponse(BaseModel):
    """Error response definition."""
    error_code: str
    http_status: int
    description: str


class IdempotencyConfig(BaseModel):
    """Idempotency key configuration."""
    required: bool
    header_name: str = "X-Idempotency-Key"
    expiration_seconds: Optional[int] = None
    behavior: str = "Returns existing response for duplicate keys"


class PayloadSchema(BaseModel):
    """Complete request or response payload schema."""
    fields: list[PayloadField]
    description: Optional[str] = None


class EndpointSpec(BaseModel):
    """Complete API endpoint specification."""
    endpoint_id: str = Field(..., description="Unique identifier")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    path: str = Field(..., description="URL path template")
    version: str = Field(default="v1", description="API version")
    description: str = Field(..., description="Condensed purpose description")
    auth_type: Literal["api_key", "bearer", "basic"]
    request_schema: PayloadSchema
    response_schema: PayloadSchema
    error_responses: list[ErrorResponse] = []
    rate_limit: Optional[RateLimit] = None
    idempotency: IdempotencyConfig
    related_webhooks: list[str] = []
    related_flows: list[str] = []
    code_examples: dict[str, str] = Field(default_factory=dict)
    sandbox_notes: Optional[str] = None
