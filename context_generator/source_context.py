import re
from pathlib import Path
from typing import Any, Dict, List


def _read_repo(repo_path: str) -> str:
    root = Path(repo_path).expanduser()
    if not root.exists():
        return ""

    parts = []
    for path in sorted(root.rglob("*.hs")):
        s = str(path)
        if any(skip in s for skip in ["/.stack-work/", "/dist-newstyle/", "/node_modules/"]):
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        parts.append(f"\n\n-- FILE: {path.relative_to(root)}\n{text}")
    return "\n".join(parts)


def _window(text: str, pos: int, before: int = 2500, after: int = 6500) -> str:
    return text[max(0, pos - before): min(len(text), pos + after)]


def _record_block(text: str, type_name: str) -> str:
    if not type_name:
        return ""

    short = type_name.split(".")[-1]
    names = []
    for name in [type_name, short]:
        if name and name not in names:
            names.append(name)

    for name in names:
        patterns = [
            rf"(?ms)^data\s+{re.escape(name)}\b.*?(?=^data\s+|^newtype\s+|^type\s+|^instance\s+|\Z)",
            rf"(?ms)^newtype\s+{re.escape(name)}\b.*?(?=^data\s+|^newtype\s+|^type\s+|^instance\s+|\Z)",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(0)[:12000]

    return ""

def _validation_block(text: str, type_name: str) -> str:
    if not type_name:
        return ""

    m = re.search(
        rf"(?ms)^instance\b[^\n]*\bNewtonValidation\b[^\n]*\b{re.escape(type_name)}\b[^\n]*where\b.*?(?=^instance\b|^data\b|^newtype\b|^type\b|\Z)",
        text,
    )
    return m.group(0)[:9000] if m else ""


def _payload_type(contract: Dict[str, Any]) -> str:
    for field in contract.get("response_fields") or []:
        if field.get("name") in {"payload", "data"}:
            typ = field.get("type") or ""
            if typ and typ not in {"String", "Text", "Bool", "Boolean"}:
                return typ
    return ""


def _nested_type_names(contract: Dict[str, Any], source_text: str = "", request_type: str = "", payload_type: str = "") -> List[str]:
    out: List[str] = []
    primitive = {"Text", "String", "Bool", "Boolean", "Maybe", "Int", "Integer", "Double", "Scientific"}

    def add_from_type_expr(type_expr: str) -> None:
        for name in re.findall(r"\b[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)?\b", type_expr or ""):
            short = name.split(".")[-1]
            if short not in primitive and short not in out:
                out.append(short)

    for field in (contract.get("request_fields") or []) + (contract.get("response_payload_fields") or []):
        add_from_type_expr(field.get("type") or "")

    for root_type in [request_type, payload_type]:
        block = _record_block(source_text, root_type)
        for raw_type in re.findall(r"_[A-Za-z][A-Za-z0-9_]*\s*::\s*([^,\n}]+)", block):
            add_from_type_expr(raw_type)

    for nested in list(out):
        block = _record_block(source_text, nested)
        for raw_type in re.findall(r"_[A-Za-z][A-Za-z0-9_]*\s*::\s*([^,\n}]+)", block):
            add_from_type_expr(raw_type)

    return out[:30]

def _keyword_windows(text: str, contract: Dict[str, Any]) -> List[str]:
    fields = {f.get("name", "") for f in contract.get("request_fields") or []}
    dynamic_keywords = []

    for field in fields:
        if field:
            dynamic_keywords.append(field)
        lower = field.lower()
        if "expiry" in lower:
            dynamic_keywords.extend(["expiry", "expire", "ttl"])
        if "split" in lower:
            dynamic_keywords.extend(["split", "settlement", "convenience", "fee"])
        if "tpv" in lower or "payeraccounthash" in lower:
            dynamic_keywords.extend(["tpv", "payerAccountHashes", "account hash"])
        if "vpa" in lower:
            dynamic_keywords.extend(["dynamicVpa", "payeeVpa", "vpa"])
        if "mandate" in lower or field == "flow":
            dynamic_keywords.extend(["MANDATE", "TRANSACTION", "flow"])
        if "refund" in lower:
            dynamic_keywords.append("refund")
        if "mutual" in lower:
            dynamic_keywords.extend(["mutualFund", "clearing"])

    windows = []
    seen = set()
    for keyword in dict.fromkeys(dynamic_keywords):
        for m in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
            w = _window(text, m.start(), 1200, 2500)
            key = w[:200]
            if key not in seen:
                seen.add(key)
                windows.append(w)
            if len(windows) >= 12:
                return windows

    return windows


def build_focused_source_context(ctx: Any, contract: Dict[str, Any], max_chars: int = 45000) -> str:
    text = _read_repo(getattr(ctx, "repo_path", ""))
    if not text:
        return ""

    api = getattr(ctx, "api", "")
    request_type = contract.get("request_type", "")
    response_type = contract.get("response_type", "")
    payload_type = _payload_type(contract)

    parts: List[str] = []

    for label, type_name in [
        ("REQUEST TYPE RECORD", request_type),
        ("RESPONSE TYPE RECORD", response_type),
        ("RESPONSE PAYLOAD RECORD", payload_type),
    ]:
        block = _record_block(text, type_name)
        if block:
            parts.append(f"\n\n## {label}: {type_name}\n```haskell\n{block}\n```")

    vblock = _validation_block(text, request_type)
    if vblock:
        parts.append(f"\n\n## REQUEST VALIDATION BLOCK: {request_type}\n```haskell\n{vblock}\n```")

    for nested in _nested_type_names(contract, text, request_type, payload_type):
        block = _record_block(text, nested)
        if block:
            parts.append(f"\n\n## NESTED TYPE RECORD: {nested}\n```haskell\n{block}\n```")

    for pattern in [f'"{api}"', api, request_type, response_type]:
        if not pattern:
            continue
        pos = text.find(pattern)
        if pos != -1:
            parts.append(f"\n\n## SOURCE WINDOW AROUND: {pattern}\n```haskell\n{_window(text, pos)}\n```")

    for idx, win in enumerate(_keyword_windows(text, contract), start=1):
        parts.append(f"\n\n## FEATURE / BEHAVIOR WINDOW {idx}\n```haskell\n{win}\n```")

    result = "\n".join(parts)
    return result[:max_chars]

def _parse_record_fields(block: str) -> List[Dict[str, str]]:
    fields: List[Dict[str, str]] = []
    for raw_name, raw_type in re.findall(r"_([A-Za-z][A-Za-z0-9_]*)\s*::\s*([^,\n}]+)", block):
        t = raw_type.split("--", 1)[0].strip()
        is_array = "[" in t and "]" in t
        clean = re.sub(r"\bMaybe\b", "", t)
        clean = clean.replace("[", "").replace("]", "").strip()
        short = clean.split(".")[-1]
        fields.append(
            {
                "name": raw_name,
                "type": "Array" if is_array else ("Object" if re.search(r"\b[A-Z][A-Za-z0-9_]*\b", short) and short not in {"Text", "String", "Bool", "Boolean", "Int", "Integer", "Double", "Scientific"} else short),
                "source_type": t,
                "item_or_object_type": short if short else clean,
            }
        )
    return fields


def build_nested_contract_summary(ctx: Any, contract: Dict[str, Any]) -> Dict[str, Any]:
    text = _read_repo(getattr(ctx, "repo_path", ""))
    request_type = contract.get("request_type", "")
    payload_type = _payload_type(contract)

    nested_names = _nested_type_names(contract, text, request_type, payload_type)
    objects: Dict[str, Any] = {}

    for name in nested_names:
        block = _record_block(text, name)
        if not block:
            continue

        fields = _parse_record_fields(block)
        if not fields:
            continue

        objects[name] = {
            "fields": fields,
        }

    request_field_types: Dict[str, Any] = {}
    req_block = _record_block(text, request_type)
    for field in _parse_record_fields(req_block):
        typ = field.get("item_or_object_type", "")
        if typ in objects:
            request_field_types[field["name"]] = {
                "container_type": field["type"],
                "nested_type": typ,
                "fields": objects[typ]["fields"],
            }

    return {
        "request_type": request_type,
        "nested_request_objects": request_field_types,
        "nested_type_definitions": objects,
    }
