"""Integration flow models."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class FlowStep(BaseModel):
    """Single step in an integration flow."""
    step_number: int = Field(..., ge=1)
    name: str = Field(..., description="Step name")
    description: str = Field(..., description="What this step does")
    endpoint_id: Optional[str] = None
    required_parameters: list[str] = Field(default_factory=list)
    expected_response: Optional[str] = None
    error_handling: Optional[str] = None
    decision_point: Optional[str] = None
    next_steps: list[str] = Field(default_factory=list)


class IntegrationFlow(BaseModel):
    """Complete integration flow."""
    flow_id: str = Field(..., description="Unique flow identifier")
    name: str = Field(..., description="Flow name")
    description: str = Field(..., description="Flow description")
    use_case: Literal["payment", "collect", "mandate", "refund", "subscription"]
    steps: list[FlowStep]
    version: str = Field(default="v1")
    prerequisites: list[str] = Field(default_factory=list)
    estimated_duration_minutes: Optional[int] = None
