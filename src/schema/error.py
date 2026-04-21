"""Error code models."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ErrorCategory(str):
    """Error category types."""
    RETRYABLE = "retryable"
    TERMINAL = "terminal"
    MERCHANT_ACTION = "merchant_action"
    SYSTEM_ERROR = "system_error"


class RetryConfig(BaseModel):
    """Retry configuration for an error."""
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_strategy: Literal["exponential", "linear", "fixed"] = "exponential"
    initial_delay_seconds: float = Field(default=1.0, gt=0)
    max_delay_seconds: float = Field(default=60.0, gt=0)
    cooldown_period_seconds: Optional[int] = None


class ErrorCode(BaseModel):
    """Structured error definition."""
    error_code: str = Field(..., description="Error code string")
    http_status: int = Field(..., description="HTTP status code")
    category: Literal["retryable", "terminal", "merchant_action", "system_error"]
    message: str = Field(..., description="Human-readable error message template")
    description: str = Field(..., description="Condensed explanation for LLM")
    retry_guidance: Optional[RetryConfig] = None
    common_causes: list[str] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    bank_specific: Optional[dict[str, str]] = None
    related_errors: list[str] = Field(default_factory=list)
