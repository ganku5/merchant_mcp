import json
import re
from pathlib import Path
from typing import Dict, Any


REQUIRED_SECTIONS = [
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
]


def count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def review_doc(markdown_path: str, evidence_path: str, out_dir: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    md_path = Path(markdown_path)
    ev_path = Path(evidence_path)

    markdown = md_path.read_text(errors="ignore")
    evidence = json.loads(ev_path.read_text())

    config = config or {}

    issues = []
    warnings = []

    required_sections = config.get("required_sections", REQUIRED_SECTIONS)
    for section in required_sections:
        if f"## {section}" not in markdown:
            issues.append(f"Missing section: {section}")

    source_files_count = evidence.get("source_files_count", 0)

    if source_files_count == 0:
        issues.append("No source files found in evidence.")

    not_confirmed_count = count_pattern(markdown, r"not confirmed from provided evidence")
    assumption_count = count_pattern(markdown, r"assumption|assumptions")
    unsupported_claim_risk_count = count_pattern(
        markdown,
        r"typically|likely|expected|illustrative|general guidance|Intent registered successfully|responseCode.*00|Not confirmed from provided evidence|not confirmed from the provided evidence|Evidence Used"
    )

    forbidden_terms = config.get("forbidden_output_terms", [
        "predicate",
        "transformer",
        "handler",
        "source file",
        ".hs",
        "code path",
        "backend flow",
        "internal implementation",
    ])

    lower_doc = markdown.lower()
    for term in forbidden_terms:
        if term in lower_doc:
            issues.append(f"Merchant-facing doc contains internal/code term: {term}")

    if "## Evidence Used" in markdown or "Evidence Used" in markdown:
        issues.append("Merchant-facing doc must not include Evidence Used section.")

    bad_table_terms = forbidden_terms

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "---" not in stripped:
            lowered_line = stripped.lower()
            for term in bad_table_terms:
                if term in lowered_line:
                    issues.append(f"Parameter table contains internal/code term: {term}")
                    break

    if '"flow": "COLLECT"' in markdown:
        issues.append('Sample request uses flow=COLLECT; evidence indicates flow should be TRANSACTION if supplied.')

    if "typically `POST`" in markdown or "typically POST" in markdown:
        warnings.append("HTTP method is inferred as POST instead of confirmed from evidence.")

    if not_confirmed_count > 8:
        warnings.append(f"High number of unconfirmed statements: {not_confirmed_count}")

    if unsupported_claim_risk_count > 4:
        warnings.append(f"Potential inferred/general statements count: {unsupported_claim_risk_count}")

    if source_files_count <= 0:
        issues.append("Evidence file has no sources.")

    h2s = re.findall(r"(?m)^##\s+(.+?)\s*$", markdown)
    duplicates = sorted({h for h in h2s if h2s.count(h) > 1})
    for heading in duplicates:
        issues.append(f"Duplicate H2 heading: {heading}")

    if re.search(r"<[a-zA-Z][a-zA-Z0-9_ -]*>", markdown):
        issues.append("Angle-bracket placeholder found in generated markdown.")

    if "sample_value" in markdown:
        issues.append("sample_value placeholder found in generated markdown.")

    unsupported_business_terms = [
        "international merchant",
        "international merchant accounts",
        "cross-border",
        "overseas",
        "foreign merchant",
        "global merchant",
    ]
    for term in unsupported_business_terms:
        if term in markdown.lower():
            issues.append(f"Potential unsupported business/use-case term found: {term}")

    if issues:
        status = "NEEDS_FIX"
        confidence = "low"
    elif warnings:
        status = "PASS_WITH_WARNINGS"
        confidence = "medium"
    else:
        status = "PASS"
        confidence = "high"

    review = {
        "status": status,
        "confidence": confidence,
        "issues": issues,
        "warnings": warnings,
        "source_files_count": source_files_count,
        "not_confirmed_count": not_confirmed_count,
        "assumption_count": assumption_count,
        "unsupported_claim_risk_count": unsupported_claim_risk_count,
    }

    reviews_dir = Path(out_dir) / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    review_path = reviews_dir / (md_path.stem + ".review.json")
    review_path.write_text(json.dumps(review, indent=2))

    review["review_path"] = str(review_path)
    return review
