"""Code template and test scenario models."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class CodeTemplate(BaseModel):
    """Per-language code example template."""
    template_id: str = Field(..., description="Unique template identifier")
    language: Literal["python", "nodejs", "java", "go", "php"]
    endpoint_id: str = Field(..., description="Related endpoint")
    code_text: str = Field(..., description="Complete working code example")
    sdk_variant: Literal["sdk", "raw_http"] = "sdk"
    includes_error_handling: bool = True
    includes_comments: bool = True
    dependencies: list[str] = Field(default_factory=list)


class TestAssertion(BaseModel):
    """Test scenario assertion."""
    field_path: str = Field(..., description="Field to check")
    operator: Literal["equals", "contains", "exists", "type_check"]
    expected_value: Optional[Any] = None
    description: str


class TestScenario(BaseModel):
    """Sandbox test scenario."""
    scenario_id: str = Field(..., description="Unique scenario identifier")
    flow_type: Literal["payment", "collect", "mandate", "refund", "subscription"]
    name: str = Field(..., description="Scenario name")
    description: str = Field(..., description="What this scenario tests")
    input_data: dict = Field(default_factory=dict)
    expected_http_status: int
    expected_response_pattern: Optional[str] = None
    assertions: list[TestAssertion] = Field(default_factory=list)
    sandbox_notes: Optional[str] = None
    priority: Literal["essential", "comprehensive"] = "essential"
