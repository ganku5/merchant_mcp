import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "repo_name": "default",
    "source_of_truth": "codebase",
    "documentation_focus": "merchant-facing API documentation",
    "include_globs": ["src/**/*.hs"],
    "exclude_globs": ["context_generator/generated/**", "**/__pycache__/**"],
    "priority_path_keywords": [],
    "contract_keywords": [],
    "forbidden_output_terms": [
        "predicate",
        "transformer",
        "handler",
        "source file",
        ".hs",
        "code path",
        "backend flow",
        "internal implementation",
    ],
    "required_sections": [
        "Overview",
        "When to Use",
        "Endpoint",
        "Authentication",
        "Request Fields",
        "Response Fields",
        "Validations",
        "Error Handling",
        "Retry / Status Guidance",
        "Sample Request",
        "Sample Response",
        "Notes and Assumptions",
    ],
}


def load_config(config_path: str = "") -> Dict[str, Any]:
    if not config_path:
        return DEFAULT_CONFIG

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    user_config = json.loads(path.read_text())
    merged = dict(DEFAULT_CONFIG)
    merged.update(user_config)
    return merged
