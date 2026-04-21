"""Building phase tools."""

import json
import random
import string
from typing import Any

from ..utils.db import db
from ..utils.llm import llm_client


CODE_TEMPLATES = {
    "python": '''import requests
import hmac
import hashlib

# {endpoint_id}
url = "https://api.juspay.in{path}"
payload = {payload_json}
headers = {{
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_API_KEY"
}}

response = requests.{method}(url, json=payload, headers=headers)
data = response.json()

if response.status_code == 200:
    print("Success:", data)
else:
    print("Error:", data)
''',
    "nodejs": '''const axios = require('axios');

// {endpoint_id}
const url = 'https://api.juspay.in{path}';
const payload = {payload_json};
const headers = {{
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_API_KEY'
}};

axios.{method}(url, payload, {{ headers }})
    .then(response => console.log('Success:', response.data))
    .catch(error => console.error('Error:', error.response?.data));
''',
    "java": '''import java.net.http.*;
import java.net.URI;

// {endpoint_id}
public class PaymentClient {{
    public static void main(String[] args) throws Exception {{
        HttpClient client = HttpClient.newHttpClient();
        
        String jsonBody = "{payload_compact}";
        
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("https://api.juspay.in{path}"))
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer YOUR_API_KEY")
            .method("{method_upper}", HttpRequest.BodyPublishers.ofString(jsonBody))
            .build();
        
        HttpResponse<String> response = client.send(request, 
            HttpResponse.BodyHandlers.ofString());
        
        System.out.println("Status: " + response.statusCode());
        System.out.println("Body: " + response.body());
    }}
}}
''',
    "go": '''package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

func main() {{
    // {endpoint_id}
    url := "https://api.juspay.in{path}"
    payload := {payload_go_struct}
    
    jsonData, _ := json.Marshal(payload)
    req, _ := http.NewRequest("{method_upper}", url, bytes.NewBuffer(jsonData))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", "Bearer YOUR_API_KEY")
    
    client := &http.Client{{}}
    resp, err := client.Do(req)
    if err != nil {{
        fmt.Println("Error:", err)
        return
    }}
    defer resp.Body.Close()
    
    fmt.Println("Status:", resp.Status)
}}
''',
    "php": '''<?php
// {endpoint_id}
$url = 'https://api.juspay.in{path}';
$payload = {payload_php_array};

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, '{method_upper}');
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Authorization: Bearer YOUR_API_KEY'
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($httpCode == 200) {{
    echo "Success: " . $response;
}} else {{
    echo "Error: " . $response;
}}
?>
'''
}


WEBHOOK_TEMPLATES = {
    "python": '''import hmac
import hashlib
import json
from flask import Flask, request, abort

app = Flask(__name__)
WEBHOOK_SECRET = "YOUR_WEBHOOK_SECRET"

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Get signature from header
    signature = request.headers.get('X-Juspay-Signature')
    if not signature:
        abort(400, 'Missing signature')
    
    # Verify signature
    payload = request.get_data()
    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
        abort(401, 'Invalid signature')
    
    # Parse event
    event = request.json
    event_type = event.get('event')
    
    # Handle {event_type}
    if event_type == '{event_type}':
        # Process the event
        order_id = event.get('order_id')
        status = event.get('status')
        print(f"Order {{order_id}} status: {{status}}")
        
        # Idempotent processing - check if already processed
        # ...
    
    return '', 200

if __name__ == '__main__':
    app.run(port=5000)
''',
    "nodejs": '''const express = require('express');
const crypto = require('crypto');

const app = express();
app.use(express.raw({{ type: 'application/json' }}));

const WEBHOOK_SECRET = 'YOUR_WEBHOOK_SECRET';

app.post('/webhook', (req, res) => {{
    const signature = req.headers['x-juspay-signature'];
    if (!signature) {{
        return res.status(400).send('Missing signature');
    }}
    
    // Verify signature
    const expectedSig = crypto
        .createHmac('sha256', WEBHOOK_SECRET)
        .update(req.body)
        .digest('hex');
    
    if (!crypto.timingSafeEqual(
        Buffer.from(signature), 
        Buffer.from(expectedSig)
    )) {{
        return res.status(401).send('Invalid signature');
    }}
    
    // Parse and handle event
    const event = JSON.parse(req.body);
    
    if (event.event === '{event_type}') {{
        console.log('Order:', event.order_id, 'Status:', event.status);
        // Process event...
    }}
    
    res.sendStatus(200);
}});

app.listen(5000);
'''
}


async def generate_payload(endpoint_id: str, params: dict = None, include_optional: bool = False) -> dict:
    """Generate a valid JSON payload for an endpoint."""
    spec = await db.get_endpoint_spec(endpoint_id)
    
    if not spec:
        return {
            "content": [{
                "type": "text",
                "text": f"Endpoint '{endpoint_id}' not found."
            }],
            "isError": True
        }
    
    params = params or {}
    request_schema = spec.get('request_schema', {})
    fields = request_schema.get('fields', [])
    
    payload = {}
    
    for field in fields:
        field_name = field.get('field_name')
        is_required = field.get('required', False)
        field_type = field.get('field_type', 'string')
        example = field.get('example')
        default = field.get('default')
        
        # Skip optional fields if not requested
        if not is_required and not include_optional and field_name not in params:
            continue
        
        # Use provided param, example, default, or generate based on type
        if field_name in params:
            payload[field_name] = params[field_name]
        elif example is not None:
            payload[field_name] = example
        elif default is not None:
            payload[field_name] = default
        else:
            payload[field_name] = _generate_default_value(field_type, field)
    
    payload_json = json.dumps(payload, indent=2)
    
    return {
        "content": [{
            "type": "text",
            "text": f"## Generated Payload for {endpoint_id}\n\n```json\n{payload_json}\n```"
        }]
    }


def _generate_default_value(field_type: str, field: dict) -> Any:
    """Generate a default value based on field type."""
    if field_type == "string":
        if field.get('format') == 'uuid':
            import uuid
            return str(uuid.uuid4())
        elif field.get('format') == 'date-time':
            from datetime import datetime
            return datetime.now().isoformat()
        return ''.join(random.choices(string.ascii_lowercase, k=10))
    elif field_type == "integer":
        return random.randint(1000, 9999)
    elif field_type == "number":
        return round(random.uniform(10, 1000), 2)
    elif field_type == "boolean":
        return True
    elif field_type == "array":
        return []
    elif field_type == "object":
        return {}
    return None


async def get_code_example(endpoint_id: str, language: str) -> dict:
    """Get working code example for an endpoint."""
    spec = await db.get_endpoint_spec(endpoint_id)
    
    # Generate payload first
    payload_result = await generate_payload(endpoint_id)
    payload_json = "{}"
    
    # Extract payload from result
    if not payload_result.get('isError'):
        text = payload_result['content'][0]['text']
        if '```json' in text:
            payload_json = text.split('```json')[1].split('```')[0].strip()
    
    # Get template
    template = CODE_TEMPLATES.get(language)
    if not template:
        return {
            "content": [{
                "type": "text",
                "text": f"Language '{language}' not supported. Available: python, nodejs, java, go, php"
            }],
            "isError": True
        }
    
    # Format template
    path = '/v1/orders/create'  # Default path
    method = 'post'
    method_upper = 'POST'
    
    if spec:
        path = spec.get('path', path)
        method = spec.get('method', 'post').lower()
        method_upper = method.upper()
    
    code = template.format(
        endpoint_id=endpoint_id,
        path=path,
        method=method,
        method_upper=method_upper,
        payload_json=payload_json,
        payload_compact=json.dumps(json.loads(payload_json) if payload_json else {}).replace('"', '\\"'),
        payload_go_struct=_dict_to_go_struct(json.loads(payload_json) if payload_json else {}),
        payload_php_array=_dict_to_php_array(json.loads(payload_json) if payload_json else {})
    )
    
    return {
        "content": [{
            "type": "text",
            "text": f"## Code Example: {endpoint_id} ({language})\n\n```{language}\n{code}\n```"
        }]
    }


def _dict_to_go_struct(d: dict) -> str:
    """Convert dict to Go struct literal."""
    parts = []
    for k, v in d.items():
        if isinstance(v, str):
            parts.append(f'{k.capitalize()} string `json:"{k}"`')
        elif isinstance(v, (int, float)):
            parts.append(f'{k.capitalize()} float64 `json:"{k}"`')
    return "\n    ".join(parts) if parts else "// Add fields here"


def _dict_to_php_array(d: dict) -> str:
    """Convert dict to PHP array literal."""
    items = [f"'{k}' => {repr(v)}" for k, v in d.items()]
    return "[" + ", ".join(items) + "]"


async def get_webhook_handler(event_type: str, language: str) -> dict:
    """Get webhook handler code with signature verification."""
    template = WEBHOOK_TEMPLATES.get(language)
    
    if not template:
        return {
            "content": [{
                "type": "text",
                "text": f"Language '{language}' not supported for webhook handlers. Available: python, nodejs"
            }],
            "isError": True
        }
    
    code = template.format(event_type=event_type)
    
    return {
        "content": [{
            "type": "text",
            "text": f"## Webhook Handler: {event_type} ({language})\n\n```{language}\n{code}\n```\n\n**Important:** Replace `YOUR_WEBHOOK_SECRET` with your actual webhook secret from the dashboard."
        }]
    }


async def validate_payload(endpoint_id: str, payload: dict) -> dict:
    """Validate a payload against endpoint schema."""
    spec = await db.get_endpoint_spec(endpoint_id)
    
    if not spec:
        return {
            "content": [{
                "type": "text",
                "text": f"Endpoint '{endpoint_id}' not found."
            }],
            "isError": True
        }
    
    request_schema = spec.get('request_schema', {})
    fields = request_schema.get('fields', [])
    
    errors = []
    warnings = []
    suggestions = []
    
    # Check required fields
    required_fields = {f['field_name'] for f in fields if f.get('required')}
    provided_fields = set(payload.keys())
    
    missing = required_fields - provided_fields
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")
    
    # Check field types and constraints
    for field in fields:
        field_name = field.get('field_name')
        if field_name not in payload:
            continue
        
        value = payload[field_name]
        field_type = field.get('field_type')
        
        # Type checking
        type_valid, type_msg = _check_type(value, field_type)
        if not type_valid:
            errors.append(f"Field '{field_name}': {type_msg}")
        
        # Constraint checking
        constraints = field.get('constraints')
        if constraints:
            if constraints.get('min_length') and isinstance(value, str):
                if len(value) < constraints['min_length']:
                    errors.append(f"Field '{field_name}': minimum length is {constraints['min_length']}")
            
            if constraints.get('max_length') and isinstance(value, str):
                if len(value) > constraints['max_length']:
                    errors.append(f"Field '{field_name}': maximum length is {constraints['max_length']}")
            
            if constraints.get('pattern') and isinstance(value, str):
                import re
                if not re.match(constraints['pattern'], value):
                    warnings.append(f"Field '{field_name}': does not match expected pattern")
        
        # Enum checking
        valid_values = field.get('valid_values')
        if valid_values and value not in valid_values:
            errors.append(f"Field '{field_name}': must be one of {valid_values}")
    
    # Check for extra fields
    known_fields = {f['field_name'] for f in fields}
    extra = provided_fields - known_fields
    if extra:
        suggestions.append(f"Extra fields found (may be ignored by API): {', '.join(extra)}")
    
    # Format result
    result_lines = ["## Payload Validation Result\n"]
    
    if errors:
        result_lines.append("### Errors (Must Fix):\n" + "\n".join(f"- {e}" for e in errors))
    
    if warnings:
        result_lines.append("\n### Warnings (Should Fix):\n" + "\n".join(f"- {w}" for w in warnings))
    
    if suggestions:
        result_lines.append("\n### Suggestions:\n" + "\n".join(f"- {s}" for s in suggestions))
    
    if not errors and not warnings:
        result_lines.append("✅ Payload is valid!")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(result_lines)
        }],
        "isError": len(errors) > 0
    }


def _check_type(value: Any, expected_type: str) -> tuple[bool, str]:
    """Check if value matches expected type."""
    type_checks = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
    }
    
    check = type_checks.get(expected_type)
    if check and not check(value):
        return False, f"expected {expected_type}, got {type(value).__name__}"
    
    return True, ""
