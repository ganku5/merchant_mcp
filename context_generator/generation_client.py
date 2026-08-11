import json
import os
import urllib.request
import urllib.error
from typing import List, Dict, Any


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def request_documentation(
    messages: List[Dict[str, str]],
    engine: str = "",
    temperature: float = 0.1,
) -> str:
    base_url = _env("GENERATION_API_BASE").rstrip("/")
    api_key = _env("GENERATION_API_KEY")
    engine = engine or _env("GENERATION_ENGINE")

    if not base_url:
        raise RuntimeError("Missing GENERATION_API_BASE.")

    if not api_key:
        raise RuntimeError("Missing GENERATION_API_KEY.")

    if not engine:
        raise RuntimeError("Missing GENERATION_ENGINE.")

    url = f"{base_url}/chat/completions"

    payload: Dict[str, Any] = {
        "model": engine,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": int(_env("GENERATION_MAX_TOKENS", "6000")),
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    timeout_seconds = int(_env("GENERATION_TIMEOUT_SECONDS", "420"))

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Documentation service HTTP error {e.code}: {err_body}") from e

    try:
        content = body["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected documentation service response: {json.dumps(body)[:1000]}") from e

    if not content:
        raise RuntimeError(f"Documentation service returned empty content: {json.dumps(body)[:1000]}")

    return content
