import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

from context_generator.schemas import RepoContext


_FIELD_RE = re.compile(r"_([A-Za-z][A-Za-z0-9_]*)\s*::\s*([^,\n}]+)")
_ASSIGNED_FIELD_RE = re.compile(r"_([A-Za-z][A-Za-z0-9_]*)\s*=")


@dataclass
class ContractField:
    name: str
    type: str = ""
    required: str = ""
    constraints: str = "—"
    validation: str = ""
    validation_source: str = ""


def _clean_type(raw_type: str) -> str:
    raw_type = raw_type.strip()
    if raw_type.startswith("Maybe "):
        raw_type = raw_type.replace("Maybe ", "", 1)
    if raw_type == "Text":
        return "String"
    if raw_type == "Bool":
        return "Boolean"
    if raw_type.startswith("["):
        return "Array"
    return raw_type


def _is_required(raw_type: str) -> str:
    return "No" if raw_type.strip().startswith("Maybe ") else "Yes"


def _dedupe_fields(fields: List[ContractField]) -> List[ContractField]:
    seen = set()
    out = []
    for field in fields:
        if field.name in seen:
            continue
        seen.add(field.name)
        out.append(field)
    return out


def _read_full_repo_source(repo_path: str) -> str:
    if not repo_path:
        return ""

    root = Path(repo_path).expanduser()
    if not root.exists():
        return ""

    parts: List[str] = []
    for path in sorted(root.rglob("*.hs")):
        path_str = str(path)
        if any(skip in path_str for skip in ["/.stack-work/", "/dist-newstyle/", "/node_modules/"]):
            continue
        try:
            content = path.read_text(errors="ignore")
        except Exception:
            continue
        parts.append(f"\n\n-- FILE: {path.relative_to(root)}\n{content}")

    return "\n".join(parts)


def _record_fields_for_type(source_text: str, type_name: str) -> List[ContractField]:
    if not type_name:
        return []

    lines = source_text.splitlines()
    start_idx = None

    for i, line in enumerate(lines):
        # Supports plain source lines and snippet lines like "1218: data RegisterIntentRequest"
        if re.search(rf"\bdata\s+{re.escape(type_name)}\b", line):
            start_idx = i
            break

    if start_idx is None:
        return []

    fields = []
    for line in lines[start_idx : min(len(lines), start_idx + 120)]:
        if fields and re.search(r"\bderiving\b", line):
            break

        m = _FIELD_RE.search(line)
        if not m:
            continue

        name, raw_type = m.group(1), m.group(2)
        fields.append(
            ContractField(
                name=name,
                type=_clean_type(raw_type),
                required=_is_required(raw_type),
                constraints="Required" if not raw_type.strip().startswith("Maybe ") else "—",
            )
        )

    return _dedupe_fields(fields)


def _find_route_types(source_text: str, api: str) -> Dict[str, str]:
    route_window = ""
    api_pos = source_text.find(f'"{api}"')
    if api_pos != -1:
        route_window = source_text[api_pos : api_pos + 700]

    req_match = re.search(r"EncRequest\s+(?:[A-Za-z0-9_]+\.)?([A-Za-z0-9_]+)", route_window)
    resp_match = re.search(r"EncResponse\s+(?:[A-Za-z0-9_]+\.)?([A-Za-z0-9_]+)", route_window)

    return {
        "request_type": req_match.group(1) if req_match else "",
        "response_type": resp_match.group(1) if resp_match else "",
    }


def _find_builder_fields(source_text: str, response_type: str) -> List[str]:
    if not response_type:
        return []

    fields: List[str] = []

    # Look near response constructor usage.
    for match in re.finditer(re.escape(response_type), source_text):
        window = source_text[match.start() : match.start() + 1800]
        for field in _ASSIGNED_FIELD_RE.findall(window):
            if field not in fields:
                fields.append(field)

    return fields


def _infer_constraints(source_text: str, fields: List[ContractField]) -> None:
    lower_source = source_text.lower()

    for field in fields:
        name_lower = field.name.lower()
        constraints = []

        if field.required == "Yes":
            constraints.append("Required")

        if name_lower == "merchantrequestid":
            constraints.append("Unique per request")
            if "duplicate_request" in lower_source:
                constraints.append("Duplicate value can return DUPLICATE_REQUEST")

        if name_lower == "payeevpa" and "dynamicvpa" in lower_source.replace("_", ""):
            field.required = "Conditional"
            constraints.append("Required when dynamic VPA validation is enabled")

        if "expiry" in name_lower:
            constraints.append("Expiry value")

        field.constraints = "; ".join(dict.fromkeys(constraints)) if constraints else "—"



def _api_related_windows(source_text: str, api: str, window_size: int = 12000) -> List[str]:
    windows = []
    patterns = [
        api,
        api[0].upper() + api[1:] if api else api,
        f"mk{api[0].upper() + api[1:]}Response" if api else api,
        f"{api}Route",
    ]

    for pattern in dict.fromkeys(patterns):
        if not pattern:
            continue
        for match in re.finditer(re.escape(pattern), source_text, flags=re.IGNORECASE):
            start = max(0, match.start() - 1200)
            end = min(len(source_text), match.end() + window_size)
            windows.append(source_text[start:end])

    return windows


def _payload_type_from_response_record(source_text: str, response_type: str) -> str:
    if not response_type:
        return ""

    lines = source_text.splitlines()
    start_idx = None

    for i, line in enumerate(lines):
        if re.search(rf"\bdata\s+{re.escape(response_type)}\b", line):
            start_idx = i
            break

    if start_idx is None:
        return ""

    for line in lines[start_idx : min(len(lines), start_idx + 100)]:
        m = re.search(r"_payload\s*::\s*(?:Maybe\s+)?([A-Z][A-Za-z0-9_]*)", line)
        if m:
            return m.group(1)

        if re.search(r"\bderiving\b", line):
            break

    return ""


def _payload_type_candidates(source_text: str, api: str, response_type: str) -> List[str]:
    # Be strict: only trust payload/data object types explicitly referenced
    # by the response record. Do not guess Response -> Payload because that
    # mixes unrelated/internal payloads for APIs whose response has primitive
    # fields like `data :: String`.
    candidates = []

    payload_from_response = _payload_type_from_response_record(source_text, response_type)
    if payload_from_response:
        candidates.append(payload_from_response)

    return list(dict.fromkeys(candidates))


def _local_payload_fields_from_api_builder(source_text: str, api: str) -> List[ContractField]:
    fields = []
    ignore = {
        "reqBody",
        "coreResp",
        "coreResponse",
        "coreResponsePayload",
        "merchant",
        "subMerchant",
        "merchantM",
        "merchantValidation",
        "allowMultibank",
        "decryptedVpa",
        "registerIntentPayload",
        "service",
        "version",
        "payload",
        "parseJSON",
        "toJSON",
        "smatch",
        "us",
        "defaultFirstExecutionAmount",
    }

    junk_suffixes = ("Err", "Error", "Failed", "Mismatch", "Timeout")
    junk_names = {
        "duplicateRequest",
        "unspamFailed",
        "internalServerErr",
        "gatewayTimeout",
        "invalidMerchantTransactionId",
        "requestExpired",
        "invalidChecksum",
        "uninitiatedRequest",
        "outdatedVersion",
        "unauthorized",
        "deviceFingerprintMismatch",
        "upiNumberDetailsInvalid",
        "upiNumberCheckRequestNotFound",
        "upiNumberAlreadyExists",
        "upiNumberVpaMismatch",
        "upiNumberPrevVpaMismatch",
        "upiNumberPortRequestNotFound",
        "upiNumberMobileNumberMismatch",
        "upiNumberInvalidDetails",
    }

    for window in _api_related_windows(source_text, api, window_size=12000):
        if "Payload" not in window and "payload" not in window:
            continue

        for field in re.findall(
            r"^\s*(?:\d+:\s*)?\s*([a-z][A-Za-z0-9_]*)\s*=",
            window,
            flags=re.MULTILINE,
        ):
            if field in ignore or field in junk_names or field.endswith(junk_suffixes):
                continue
            fields.append(ContractField(name=field, type="", required="", constraints="—"))

    return _dedupe_fields(fields)



def _find_validation_block(source_text: str, type_name: str) -> str:
    if not type_name:
        return ""

    pattern = re.compile(
        rf"(?ms)^instance\b[^\n]*\bNewtonValidation\b[^\n]*\b{re.escape(type_name)}\b[^\n]*where\b.*?(?=^instance\b|^data\b|^newtype\b|^type\b|\Z)"
    )
    m = pattern.search(source_text)
    if m:
        return m.group(0)

    # Fallback: look near type name and validation keywords.
    pos = source_text.find(type_name)
    if pos == -1:
        return ""
    window = source_text[pos:pos + 12000]
    if "Validation" in window or "validate" in window:
        return window
    return ""


def _validator_names(expr: str) -> List[str]:
    names = []

    # Capture lower-case function identifiers, including names like
    # expiryValidationSeconds and validateEnum.
    for raw in re.findall(r"\b(?:[A-Z][A-Za-z0-9_]*\.)?([a-z][A-Za-z0-9_]*)\b", expr):
        if raw in {"traverse", "wrapper"}:
            continue
        if "Validation" in raw or raw == "validateEnum":
            if raw not in names:
                names.append(raw)

    return names


def _function_definition(source_text: str, fn_name: str) -> str:
    if not fn_name:
        return ""

    # Prefer signature + body.
    sig = re.search(rf"(?ms)^{re.escape(fn_name)}\s*::.*?(?=^[a-zA-Z_][A-Za-z0-9_']*\s*::|\Z)", source_text)
    if sig:
        return sig.group(0).strip()[:1600]

    body = re.search(rf"(?ms)^{re.escape(fn_name)}\b.*?(?=^[a-zA-Z_][A-Za-z0-9_']*\s*=|^[a-zA-Z_][A-Za-z0-9_']*\s*::|\Z)", source_text)
    return body.group(0).strip()[:1600] if body else ""


def _field_validation_exprs(source_text: str, request_type: str) -> Dict[str, str]:
    block = _find_validation_block(source_text, request_type)
    if not block:
        return {}

    out: Dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or "_" not in line:
            continue

        # Keep only lines that appear to apply validation.
        if "Validation" not in line and "validateEnum" not in line and "listValidation" not in line:
            continue

        for field in re.findall(r"_([A-Za-z][A-Za-z0-9_]*)\b", line):
            out[field] = line

    return out


def _constraints_from_validation_expr(expr: str) -> List[str]:
    constraints: List[str] = []

    enum_match = re.search(r"validateEnum\s+\[([^\]]+)\]", expr)
    if enum_match:
        enum_body = enum_match.group(1)
        vals = re.findall(r'"([^"]+)"', enum_body)
        if not vals:
            vals = re.findall(r"\b[A-Z][A-Za-z0-9_]*\.([A-Z][A-Z0-9_]*)\b", enum_body)
        if vals:
            constraints.append("Allowed values: " + ", ".join(vals))

    if "amountValidation" in expr:
        constraints.append("Amount must pass source amount validation")
    if "expiryValidationSeconds" in expr:
        constraints.append("Expiry seconds must pass source expiry validation")
    elif "expiryValidation" in expr:
        constraints.append("Expiry must pass source expiry validation")
    if "listValidation" in expr:
        constraints.append("List must be non-empty when provided")
    if "udfParametersTextValidation" in expr:
        constraints.append("Must pass source UDF parameter text validation")
    if "boolStringValidation" in expr:
        constraints.append("Boolean string must pass source validation")
    if "vpaValidation" in expr:
        constraints.append("Must pass source VPA validation")
    if "upiRequestIdValidation" in expr:
        constraints.append("Must pass source UPI request id validation")
    if "merchantRequestIdValidation" in expr:
        constraints.append("Must pass source merchant request id validation")

    return constraints


def _attach_validation_evidence(source_text: str, request_type: str, fields: List[ContractField]) -> None:
    validation_exprs = _field_validation_exprs(source_text, request_type)

    for field in fields:
        expr = validation_exprs.get(field.name)
        if not expr:
            continue

        field.validation = expr

        definitions = []
        for name in _validator_names(expr):
            definition = _function_definition(source_text, name)
            if definition:
                definitions.append(definition)

        field.validation_source = "\n\n".join(definitions)[:2500]

        existing = [] if field.constraints == "—" else [x.strip() for x in field.constraints.split(";") if x.strip()]
        inferred = _constraints_from_validation_expr(expr)
        merged = list(dict.fromkeys(existing + inferred))
        field.constraints = "; ".join(merged) if merged else field.constraints


def extract_contract(ctx: RepoContext) -> Dict[str, Any]:
    source_text = _read_full_repo_source(getattr(ctx, "repo_path", ""))

    if not source_text:
        source_parts = []
        for source_file in ctx.files:
            snippets = source_file.get("snippets", []) if isinstance(source_file, dict) else source_file.snippets
            for snippet in snippets:
                if isinstance(snippet, str):
                    source_parts.append(snippet)
                elif isinstance(snippet, dict):
                    source_parts.append(snippet.get("text", str(snippet)))
                else:
                    source_parts.append(getattr(snippet, "text", str(snippet)))

        source_text = "\n\n".join(source_parts)

    route_types = _find_route_types(source_text, ctx.api)
    request_type = route_types.get("request_type", "")
    response_type = route_types.get("response_type", "")

    request_fields = _record_fields_for_type(source_text, request_type)
    response_fields = _record_fields_for_type(source_text, response_type)

    builder_fields = _find_builder_fields(source_text, response_type)

    # If response type only has envelope fields, include builder fields as payload hints.
    envelope_names = {f.name for f in response_fields}
    payload_fields = []

    for payload_type in _payload_type_candidates(source_text, ctx.api, response_type):
        if payload_type.startswith("Core"):
            continue

        found = _record_fields_for_type(source_text, payload_type)
        if found:
            payload_fields.extend(found)
            break

    # Be strict: response payload fields are extracted only from an explicit
    # payload object type referenced by the response record. Do not infer payload
    # fields from local builder variables because that can mix unrelated APIs.
    payload_fields = _dedupe_fields(payload_fields)

    _infer_constraints(source_text, request_fields)
    _attach_validation_evidence(source_text, request_type, request_fields)

    _infer_constraints(source_text, payload_fields)

    return {
        "api": ctx.api,
        "request_type": request_type,
        "response_type": response_type,
        "request_fields": [asdict(f) for f in request_fields],
        "response_fields": [asdict(f) for f in response_fields],
        "response_payload_fields": [asdict(f) for f in _dedupe_fields(payload_fields)],
    }
