"""Building phase MCP tools."""

import json
import random
import string
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from ..utils.database import database
from ..utils.llm import llm_client


CODE_TEMPLATES = {
    "python": '''import requests
import hmac
import hashlib
from datetime import datetime

# Configuration
API_KEY = "YOUR_API_KEY"
BASE_URL = "https://api.juspay.in"

# {endpoint_id}
def {function_name}():
    url = f"{{BASE_URL}}{path}"
    
    payload = {payload_json}
    
    headers = {{
        "Content-Type": "application/json",
        "Authorization": f"Bearer {{API_KEY}}"
    }}
    
    try:
        response = requests.{method}(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        print(f"✓ Success: {{data}}")
        return data
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP Error: {{e.response.status_code}} - {{e.response.text}}")
        raise
    except Exception as e:
        print(f"✗ Error: {{e}}")
        raise

if __name__ == "__main__":
    result = {function_name}()
''',
    "nodejs": '''const axios = require('axios');

// Configuration
const API_KEY = 'YOUR_API_KEY';
const BASE_URL = 'https://api.juspay.in';

// {endpoint_id}
async function {function_name}() {{
    const url = `${{BASE_URL}}{path}`;
    
    const payload = {payload_json};
    
    const headers = {{
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${{API_KEY}}`
    }};
    
    try {{
        const response = await axios.{method}(url, payload, {{ headers }});
        console.log('✓ Success:', response.data);
        return response.data;
    }} catch (error) {{
        if (error.response) {{
            console.error('✗ HTTP Error:', error.response.status, error.response.data);
        }} else {{
            console.error('✗ Error:', error.message);
        }}
        throw error;
    }}
}}

{function_name}().catch(console.error);
''',
    "java": '''import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import com.fasterxml.jackson.databind.ObjectMapper;

public class {class_name} {{
    private static final String API_KEY = "YOUR_API_KEY";
    private static final String BASE_URL = "https://api.juspay.in";
    
    // {endpoint_id}
    public static void main(String[] args) throws Exception {{
        HttpClient client = HttpClient.newHttpClient();
        ObjectMapper mapper = new ObjectMapper();
        
        String url = BASE_URL + "{path}";
        
        // Build request body
        var payload = {payload_java};
        String jsonBody = mapper.writeValueAsString(payload);
        
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer " + API_KEY)
            .{method_lower}(HttpRequest.BodyPublishers.ofString(jsonBody))
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
    "time"
)

const (
    APIKey  = "YOUR_API_KEY"
    BaseURL = "https://api.juspay.in"
)

// {endpoint_id}
func main() {{
    url := BaseURL + "{path}"
    
    payload := {payload_go}
    
    jsonData, err := json.Marshal(payload)
    if err != nil {{
        panic(err)
    }}
    
    req, err := http.NewRequest(http.Method{method_cap}, url, bytes.NewBuffer(jsonData))
    if err != nil {{
        panic(err)
    }}
    
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Authorization", "Bearer "+APIKey)
    
    client := &http.Client{{Timeout: 30 * time.Second}}
    resp, err := client.Do(req)
    if err != nil {{
        panic(err)
    }}
    defer resp.Body.Close()
    
    fmt.Println("Status:", resp.Status)
}}
''',
    "php": '''<?php
// {endpoint_id}

$apiKey = 'YOUR_API_KEY';
$baseUrl = 'https://api.juspay.in';
$url = $baseUrl . '{path}';

$payload = {payload_php};

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, '{method_upper}');
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Authorization: Bearer ' . $apiKey
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

if (curl_errno($ch)) {{
    echo 'Error: ' . curl_error($ch);
}} else {{
    echo "HTTP Code: $httpCode\\n";
    echo "Response: $response\\n";
}}

curl_close($ch);
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
    """Handle {event_type} webhook."""
    # Get signature from header
    signature = request.headers.get('X-Juspay-Signature')
    if not signature:
        abort(400, 'Missing signature')
    
    # Get raw body
    payload = request.get_data()
    
    # Verify signature
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
    
    print(f"Received event: {{event_type}}")
    
    # Handle {event_type}
    if event_type == '{event_type}':
        order_id = event.get('order_id')
        status = event.get('status')
        
        # Idempotency check - ensure you haven't processed this before
        # using order_id as idempotency key
        
        print(f"Processing {{order_id}} - Status: {{status}}")
        
        # Your business logic here
        # fulfill_order(order_id)
    
    return '', 200

if __name__ == '__main__':
    app.run(port=5000, debug=True)
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
    
    // Verify signature using raw body
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
    console.log(`Received event: ${{event.event}}`);
    
    if (event.event === '{event_type}') {{
        const {{ order_id, status }} = event;
        
        // Idempotency check using order_id
        
        console.log(`Processing ${{order_id}} - Status: ${{status}}`);
        // Your business logic here
    }}
    
    res.sendStatus(200);
}});

app.listen(5000, () => console.log('Webhook server on port 5000'));
''',
    "go": '''package main

import (
    "crypto/hmac"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

const webhookSecret = "YOUR_WEBHOOK_SECRET"

func verifySignature(payload []byte, signature string) bool {
    mac := hmac.New(sha256.New, []byte(webhookSecret))
    mac.Write(payload)
    expected := hex.EncodeToString(mac.Sum(nil))
    return hmac.Equal([]byte(signature), []byte(expected))
}

func webhookHandler(w http.ResponseWriter, r *http.Request) {
    signature := r.Header.Get("X-Juspay-Signature")
    if signature == "" {
        http.Error(w, "Missing signature", http.StatusBadRequest)
        return
    }
    
    body, _ := io.ReadAll(r.Body)
    
    if !verifySignature(body, signature) {
        http.Error(w, "Invalid signature", http.StatusUnauthorized)
        return
    }
    
    var event map[string]interface{}
    json.Unmarshal(body, &event)
    
    fmt.Printf("Received event: %s\\n", event["event"])
    
    if event["event"] == "{event_type}" {{
        orderId := event["order_id"]
        status := event["status"]
        fmt.Printf("Processing %s - Status: %s\\n", orderId, status)
        // Process event
    }}
    
    w.WriteHeader(http.StatusOK)
}}

func main() {
    http.HandleFunc("/webhook", webhookHandler)
    http.ListenAndServe(":5000", nil)
}
'''
}


async def generate_payload(endpoint_id: str, params: Optional[Dict] = None, 
                           include_optional: bool = False) -> dict:
    """Generate a valid JSON payload for an endpoint.
    
    Args:
        endpoint_id: Target endpoint identifier
        params: Override values for specific fields
        include_optional: Include optional fields in output
    
    Returns:
        Complete JSON payload with examples
    """
    if database._pool is None:
        await database.connect()
    
    params = params or {}
    spec = await database.get_endpoint_spec(endpoint_id)
    
    if not spec:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Endpoint '{endpoint_id}' not found."
            }],
            "isError": True
        }
    
    request_schema = spec.get('request_schema', {})
    fields = request_schema.get('fields', [])
    
    payload = {}
    
    for field in fields:
        field_name = field.get('field_name')
        is_required = field.get('required', False)
        field_type = field.get('field_type', 'string')
        
        # Skip optional fields unless requested
        if not is_required and not include_optional and field_name not in params:
            continue
        
        # Use provided param, example, default, or generate
        if field_name in params:
            payload[field_name] = params[field_name]
        elif field.get('example') is not None:
            payload[field_name] = field['example']
        elif field.get('default') is not None:
            payload[field_name] = field['default']
        else:
            payload[field_name] = _generate_default_value(field_type, field)
    
    payload_json = json.dumps(payload, indent=2, default=str)
    
    sections = [
        f"# Generated Payload for {endpoint_id}",
        f"\n```json\n{payload_json}\n```",
        "\n## Field Sources"
    ]
    
    for field in fields:
        fname = field.get('field_name')
        if fname in payload:
            source = "provided"
            if fname not in params:
                source = field.get('example', 'generated' if not field.get('default') else 'default')
            sections.append(f"- **{fname}**: {source}")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


def _generate_default_value(field_type: str, field: Dict) -> Any:
    """Generate a default value based on field type."""
    if field_type == "string":
        fmt = field.get('format', '')
        if fmt == 'uuid':
            return str(uuid.uuid4())
        elif fmt == 'date-time':
            return datetime.now().isoformat()
        elif fmt == 'email':
            return "customer@example.com"
        elif fmt == 'uri':
            return "https://example.com/callback"
        elif field.get('field_name', '').endswith('_id'):
            return f"test_{field['field_name']}_{random.randint(1000, 9999)}"
        return ''.join(random.choices(string.ascii_lowercase, k=10))
    
    elif field_type == "integer":
        return random.randint(10000, 99999)
    
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
    """Get working code example for an endpoint.
    
    Args:
        endpoint_id: Target endpoint identifier
        language: Programming language (python, nodejs, java, go, php)
    
    Returns:
        Complete working code example with error handling
    """
    if database._pool is None:
        await database.connect()
    
    spec = await database.get_endpoint_spec(endpoint_id)
    
    if not spec:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Endpoint '{endpoint_id}' not found."
            }],
            "isError": True
        }
    
    # Check if language is supported
    if language not in CODE_TEMPLATES:
        supported = ', '.join(CODE_TEMPLATES.keys())
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Language '{language}' not supported. Available: {supported}"
            }],
            "isError": True
        }
    
    # Generate payload for the example
    payload_result = await generate_payload(endpoint_id)
    payload_text = "{}"
    
    if not payload_result.get('isError'):
        text = payload_result['content'][0]['text']
        if '```json' in text:
            payload_text = text.split('```json')[1].split('```')[0].strip()
    
    try:
        payload_obj = json.loads(payload_text)
    except:
        payload_obj = {}
    
    # Get endpoint details
    path = spec.get('path', '/v1/orders')
    method = spec.get('method', 'POST').lower()
    function_name = endpoint_id.replace('.', '_')
    class_name = ''.join(word.capitalize() for word in endpoint_id.split('.'))
    
    # Format template
    template = CODE_TEMPLATES[language]
    
    if language == 'python':
        code = template.format(
            endpoint_id=endpoint_id,
            path=path,
            method=method,
            function_name=function_name,
            payload_json=payload_text
        )
    elif language == 'nodejs':
        code = template.format(
            endpoint_id=endpoint_id,
            path=path,
            method=method,
            function_name=function_name,
            payload_json=payload_text
        )
    elif language == 'java':
        code = template.format(
            endpoint_id=endpoint_id,
            path=path,
            method_lower=method,
            class_name=class_name,
            payload_java=_dict_to_java_map(payload_obj)
        )
    elif language == 'go':
        code = template.format(
            endpoint_id=endpoint_id,
            path=path,
            method_cap=method.capitalize(),
            payload_go=_dict_to_go_map(payload_obj)
        )
    elif language == 'php':
        code = template.format(
            endpoint_id=endpoint_id,
            path=path,
            method_upper=method.upper(),
            payload_php=_dict_to_php_array(payload_obj)
        )
    else:
        code = "# Code generation not implemented for this language"
    
    return {
        "content": [{
            "type": "text",
            "text": f"# Code Example: {endpoint_id} ({language})\n\n```{language}\n{code}\n```\n\n**Note:** Replace `YOUR_API_KEY` with your actual API key from the Juspay dashboard."
        }]
    }


def _dict_to_java_map(d: Dict) -> str:
    """Convert dict to Java Map.of syntax."""
    if not d:
        return "Map.of()"
    items = []
    for k, v in d.items():
        if isinstance(v, str):
            items.append(f'"{k}", "{v}"')
        elif isinstance(v, bool):
            items.append(f'"{k}", {str(v).lower()}')
        else:
            items.append(f'"{k}", {v}')
    return "Map.of(\n        " + ",\n        ".join(items) + "\n    )"


def _dict_to_go_map(d: Dict) -> str:
    """Convert dict to Go map syntax."""
    if not d:
        return "map[string]interface{}{}"
    items = []
    for k, v in d.items():
        if isinstance(v, str):
            items.append(f'"{k}": "{v}"')
        else:
            items.append(f'"{k}": {v}')
    return "map[string]interface{}{\n        " + ",\n        ".join(items) + "\n    }"


def _dict_to_php_array(d: Dict) -> str:
    """Convert dict to PHP array syntax."""
    if not d:
        return "[]"
    items = []
    for k, v in d.items():
        if isinstance(v, str):
            items.push(f"'{k}' => '{v}'")
        elif isinstance(v, bool):
            items.append(f"'{k}' => {str(v).lower()}")
        else:
            items.append(f"'{k}' => {v}")
    return "[\n    " + ",\n    ".join(items) + "\n]"


async def get_webhook_handler(event_type: str, language: str) -> dict:
    """Get webhook handler code with signature verification.
    
    Args:
        event_type: Webhook event type (e.g., 'order.charged')
        language: Programming language
    
    Returns:
        Webhook handler code with HMAC verification
    """
    if database._pool is None:
        await database.connect()
    
    # Verify event type exists
    event = await database.get_webhook_event(event_type)
    if not event:
        events = await database.list_webhook_events()
        available = ", ".join([e['event_type'] for e in events])
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Event type '{event_type}' not found. Available: {available}"
            }],
            "isError": True
        }
    
    # Check language support
    if language not in WEBHOOK_TEMPLATES:
        supported = ', '.join(WEBHOOK_TEMPLATES.keys())
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Language '{language}' not supported for webhooks. Available: {supported}"
            }],
            "isError": True
        }
    
    template = WEBHOOK_TEMPLATES[language]
    code = template.format(event_type=event_type)
    
    sections = [
        f"# Webhook Handler: {event_type} ({language})",
        f"\n**Description:** {event.get('description', 'No description')}",
        f"\n**Signature Algorithm:** {event.get('signature_algorithm', 'hmac_sha256')}",
        f"\n**Idempotency Key Field:** `{event.get('idempotency_key_field', 'order_id')}`",
        f"\n```{language}\n{code}\n```",
        "\n## Important Notes",
        "1. **Never expose your webhook secret** - Keep it in environment variables",
        "2. **Use raw request body** for signature verification, NOT parsed JSON",
        "3. **Implement idempotency checks** to avoid duplicate processing",
        "4. **Return 200 status** quickly to acknowledge receipt",
        "5. **Process asynchronously** for long-running operations"
    ]
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
        }]
    }


async def validate_payload(endpoint_id: str, payload: Dict) -> dict:
    """Validate a payload against endpoint schema.
    
    Args:
        endpoint_id: Target endpoint identifier
        payload: JSON payload to validate
    
    Returns:
        Validation results with errors, warnings, and suggestions
    """
    if database._pool is None:
        await database.connect()
    
    spec = await database.get_endpoint_spec(endpoint_id)
    
    if not spec:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Endpoint '{endpoint_id}' not found."
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
    
    # Check each provided field
    field_map = {f['field_name']: f for f in fields}
    
    for field_name, value in payload.items():
        if field_name not in field_map:
            warnings.append(f"Unknown field '{field_name}' (will be ignored by API)")
            continue
        
        field = field_map[field_name]
        field_type = field.get('field_type')
        
        # Type checking
        type_valid, type_msg = _check_type(value, field_type)
        if not type_valid:
            errors.append(f"Field '{field_name}': {type_msg}")
        
        # Constraint checking
        constraints = field.get('constraints') or {}
        if isinstance(value, str):
            if constraints.get('min_length') and len(value) < constraints['min_length']:
                errors.append(f"Field '{field_name}': minimum length is {constraints['min_length']}")
            if constraints.get('max_length') and len(value) > constraints['max_length']:
                errors.append(f"Field '{field_name}': maximum length is {constraints['max_length']}")
            if constraints.get('pattern'):
                import re
                if not re.match(constraints['pattern'], value):
                    warnings.append(f"Field '{field_name}': does not match expected pattern {constraints['pattern']}")
        
        # Enum checking
        valid_values = field.get('valid_values')
        if valid_values and value not in valid_values:
            errors.append(f"Field '{field_name}': must be one of {valid_values}")
    
    # Build response
    sections = [f"# Payload Validation: {endpoint_id}"]
    
    if errors:
        sections.append("\n## ❌ Errors (Must Fix)")
        for e in errors:
            sections.append(f"- {e}")
    
    if warnings:
        sections.append("\n## ⚠️ Warnings")
        for w in warnings:
            sections.append(f"- {w}")
    
    if suggestions:
        sections.append("\n## 💡 Suggestions")
        for s in suggestions:
            sections.append(f"- {s}")
    
    if not errors and not warnings:
        sections.append("\n✅ Payload is valid!")
    
    # Show type reference
    sections.append("\n## Field Types")
    for f in fields:
        req_mark = "*" if f.get('required') else ""
        sections.append(f"- {f['field_name']}{req_mark}: `{f['field_type']}`")
    
    return {
        "content": [{
            "type": "text",
            "text": "\n".join(sections)
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
        actual = type(value).__name__
        return False, f"expected {expected_type}, got {actual}"
    
    return True, ""
