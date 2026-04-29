# API Cookbook: Common Integration Patterns

This cookbook provides practical examples for common integration scenarios using the Merchant MCP tools.

## Table of Contents

1. [Basic Payment Flow](#basic-payment-flow)
2. [Webhook Handling](#webhook-handling)
3. [Error Handling](#error-handling)
4. [Refund Processing](#refund-processing)
5. [Mandate Setup](#mandate-setup)
6. [Testing Strategies](#testing-strategies)
7. [Production Checklist](#production-checklist)

---

## Basic Payment Flow

### Scenario 1: Simple UPI Payment

```python
# Step 1: Generate payload
"Generate a payload for initiating a UPI collect payment of ₹500"

# The tool will return:
payload = {
    "payeeVpaHandle": "merchant@juspay",
    "payeeName": "My Store",
    "payerVpaHandle": "customer@okaxis",
    "amount": "500.00",
    "merchantRequestId": "ORDER_20240901123456",
    "merchantId": "MYMERCHANT001",
    "upiTxnType": "COLLECT",
    "description": "Payment for Order #12345"
}

# Step 2: Get code example
"Show me Python code to call the transaction init endpoint"

# Step 3: Validate payload
"Validate this payload for transaction.init"

# Step 4: Test in sandbox
"Test this transaction in sandbox mode"
```

### Scenario 2: Handling Payment Response

```python
# After getting response, check status
if response['result'] == 'SUCCESS':
    # Save transaction details
    save_to_db({
        'order_id': order_id,
        'merchant_request_id': payload['merchantRequestId'],
        'status': 'INITIATED',
        'intent_url': response['payload']['url']
    })
    
    # Notify customer
    send_notification(customer, "Please approve payment in your UPI app")
else:
    # Handle error
    error_code = response.get('responseCode')
    explain_error(error_code)  # Use MCP tool to get error details
```

### Scenario 3: Complete Payment Flow with Polling

```python
"Run a complete transaction lifecycle test for merchant TEST123"
# This tool will:
# 1. Initiate transaction
# 2. Poll for status (5 second intervals, 12 attempts)
# 3. Track state transitions
# 4. Provide timing analysis
```

---

## Webhook Handling

### Scenario 1: Basic Webhook Setup

```python
# Step 1: Generate webhook handler
"Generate a Python webhook handler with signature verification"

# Step 2: Validate webhook configuration
"Diagnose my webhook at https://myapp.com/webhook"

# Step 3: Test webhook delivery
"My webhook isn't receiving events. Can you diagnose it?"
# Provide headers and body from recent attempt
```

### Scenario 2: Handling Different Event Types

```python
# Webhook handler structure
def handle_webhook(event):
    event_type = event['event']
    
    handlers = {
        'order.charged': handle_payment_success,
        'order.failed': handle_payment_failure,
        'refund.processed': handle_refund_complete,
        'mandate.activated': handle_mandate_active
    }
    
    handler = handlers.get(event_type)
    if handler:
        return handler(event)
    else:
        logger.warning(f"Unknown event type: {event_type}")
        return {'status': 'ignored'}

def handle_payment_success(event):
    order_id = event['order_id']
    # Fulfill order
    fulfill_order(order_id)
    return {'status': 'fulfilled'}

def handle_payment_failure(event):
    order_id = event['order_id']
    error_code = event.get('error_code')
    # Notify customer
    notify_payment_failed(order_id, error_code)
    return {'status': 'notified'}
```

### Scenario 3: Webhook Security

```python
# Always verify signatures
import hmac
import hashlib
import os

WEBHOOK_SECRET = os.environ['WEBHOOK_SECRET']

def verify_signature(body: bytes, signature: str) -> bool:
    """Verify webhook signature using constant-time comparison."""
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)

# In your webhook handler
@app.route('/webhook', methods=['POST'])
def webhook():
    body = request.get_data()  # Raw bytes, not parsed!
    signature = request.headers.get('X-Juspay-Signature')
    
    if not verify_signature(body, signature):
        abort(401, "Invalid signature")
    
    event = request.get_json()
    return handle_webhook(event)
```

---

## Error Handling

### Scenario 1: Understanding Error Codes

```python
# Get detailed error information
"Explain error code MERCHANT_NOT_FOUND"

# Or use lookup for comprehensive mapping
"Lookup error code INVALID_VPA_FORMAT"

# The tools provide:
# - Error description
# - Common causes
# - Fix suggestions
# - Affected endpoints
# - Retry guidance
```

### Scenario 2: Retry Strategy

```python
import time
import random

class PaymentRetryHandler:
    MAX_RETRIES = 3
    BASE_DELAY = 1  # seconds
    
    RETRYABLE_ERRORS = [
        'TIMEOUT',
        'RATE_LIMITED',
        'GATEWAY_ERROR',
        'SERVICE_UNAVAILABLE'
    ]
    
    TERMINAL_ERRORS = [
        'INVALID_VPA_FORMAT',
        'INSUFFICIENT_FUNDS',
        'MERCHANT_NOT_FOUND'
    ]
    
    def should_retry(self, error_code: str) -> bool:
        return error_code in self.RETRYABLE_ERRORS
    
    def calculate_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay = self.BASE_DELAY * (2 ** attempt)
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter
    
    def execute_with_retry(self, operation, *args, **kwargs):
        for attempt in range(self.MAX_RETRIES):
            try:
                return operation(*args, **kwargs)
            except PaymentError as e:
                if not self.should_retry(e.code):
                    raise  # Terminal error, don't retry
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.calculate_delay(attempt)
                    time.sleep(delay)
                else:
                    raise  # Max retries exceeded
```

### Scenario 3: Error Decision Tree

```python
# Generate visual error handling flow
"Generate error decision tree for payment flow"
# This creates a Mermaid diagram showing:
# - Which errors to retry
# - Which errors are terminal
# - Customer communication strategy
```

---

## Refund Processing

### Scenario 1: Simple Refund

```python
# Step 1: Validate original transaction exists
original_txn = get_transaction(order_id)
assert original_txn['status'] == 'SUCCESS'

# Step 2: Generate refund payload
refund_payload = {
    "order_id": order_id,
    "amount": original_txn['amount'],  # Full refund
    "reason": "Customer request",
    "unique_request_id": f"REFUND_{order_id}_{timestamp}"
}

# Step 3: Process refund
response = api.refund.create(refund_payload)

# Step 4: Handle webhook for completion
# Listen for 'refund.processed' event
```

### Scenario 2: Partial Refund

```python
# Partial refund (e.g., only shipping cost)
partial_refund = {
    "order_id": order_id,
    "amount": "50.00",  # Only ₹50
    "reason": "Discount applied post-purchase",
    "unique_request_id": f"PARTIAL_REFUND_{order_id}"
}
```

---

## Mandate Setup

### Scenario 1: Creating a Recurring Mandate

```python
# Step 1: Get mandate setup guide
"Get interactive guide for mandate setup"

# Step 2: Create mandate payload
mandate_payload = {
    "payerVpaHandle": "customer@okaxis",
    "payeeVpaHandle": "merchant@juspay",
    "amount": "1000.00",
    "frequency": "MONTHLY",
    "startDate": "2024-02-01",
    "endDate": "2024-12-31",
    "purpose": "Subscription",
    "merchantRequestId": "MANDATE_001"
}

# Step 3: Initiate mandate
response = api.mandate.create(mandate_payload)
# Returns authorization URL for customer approval

# Step 4: Handle mandate activation webhook
# Listen for 'mandate.activated' event
```

---

## Testing Strategies

### Scenario 1: Comprehensive Test Suite

```python
# Generate complete test suite
"Generate test suite for ibmb.merchant.transaction.init"

# Export to your preferred format
"Export test suite for ibmb.merchant.transaction.init to Postman"
"Export test suite for ibmb.merchant.transaction.init to pytest"
```

### Scenario 2: Load Testing

```python
# Generate JMeter test plan
"Export test suite for transaction.init to JMeter"

# This creates a JMX file you can open in JMeter
# Configure:
# - Number of threads (virtual users)
# - Ramp-up time
# - Duration
# - Assertions
```

### Scenario 3: Integration Verification

```python
# Run full integration check
"Run integration check for merchant MYMERCHANT001"

# Or specific checks
"Run connectivity check for merchant MYMERCHANT001"
"Run security check for merchant MYMERCHANT001"
```

---

## Production Checklist

### Scenario 1: Pre-Launch Verification

```python
# Complete checklist
requirements = [
    'webhook',
    'retry_logic',
    'idempotency',
    'error_handling',
    'logging',
    'ssl'
]

validate_integration_readiness(
    requirements=requirements,
    merchant_config={
        'webhook_url': 'https://myapp.com/webhook',
        'has_ssl': True,
        'implements_retry': True
    }
)
```

### Scenario 2: Go-Live Steps

```python
"Get onboarding wizard status for merchant MYMERCHANT001"
# Shows:
# - Current progress percentage
# - Remaining steps
# - Time estimates
# - Recommended next actions
```

---

## Multi-Language Examples

### Python (Flask)

```python
from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)
API_KEY = os.environ['IBMB_API_KEY']
BASE_URL = os.environ['IBMB_BASE_URL']

@app.route('/create-order', methods=['POST'])
def create_order():
    order_data = request.get_json()
    
    # Generate transaction payload
    payload = {
        "payeeVpaHandle": "merchant@juspay",
        "payerVpaHandle": order_data['customer_vpa'],
        "amount": str(order_data['amount']),
        "merchantRequestId": order_data['order_id'],
        "merchantId": os.environ['MERCHANT_ID'],
        "upiTxnType": "COLLECT"
    }
    
    # Call IBMB API
    response = requests.post(
        f"{BASE_URL}/api/merchants/v1/transaction/initiate",
        json=payload,
        headers={"X-API-Key": API_KEY}
    )
    
    return jsonify(response.json())
```

### Node.js (Express)

```javascript
const express = require('express');
const axios = require('axios');

const app = express();
app.use(express.json());

const API_KEY = process.env.IBMB_API_KEY;
const BASE_URL = process.env.IBMB_BASE_URL;

app.post('/create-order', async (req, res) => {
    const orderData = req.body;
    
    const payload = {
        payeeVpaHandle: 'merchant@juspay',
        payerVpaHandle: orderData.customerVpa,
        amount: orderData.amount.toString(),
        merchantRequestId: orderData.orderId,
        merchantId: process.env.MERCHANT_ID,
        upiTxnType: 'COLLECT'
    };
    
    try {
        const response = await axios.post(
            `${BASE_URL}/api/merchants/v1/transaction/initiate`,
            payload,
            { headers: { 'X-API-Key': API_KEY } }
        );
        
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});
```

### Java (Spring Boot)

```java
@RestController
@RequestMapping("/api")
public class PaymentController {
    
    @Value("${ibmb.api.key}")
    private String apiKey;
    
    @Value("${ibmb.base.url}")
    private String baseUrl;
    
    @PostMapping("/create-order")
    public ResponseEntity<String> createOrder(@RequestBody OrderRequest request) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-API-Key", apiKey);
        headers.setContentType(MediaType.APPLICATION_JSON);
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("payeeVpaHandle", "merchant@juspay");
        payload.put("payerVpaHandle", request.getCustomerVpa());
        payload.put("amount", request.getAmount().toString());
        payload.put("merchantRequestId", request.getOrderId());
        payload.put("upiTxnType", "COLLECT");
        
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(payload, headers);
        
        RestTemplate restTemplate = new RestTemplate();
        ResponseEntity<String> response = restTemplate.exchange(
            baseUrl + "/api/merchants/v1/transaction/initiate",
            HttpMethod.POST,
            entity,
            String.class
        );
        
        return response;
    }
}
```

---

## Troubleshooting Common Issues

### Issue 1: "Webhook not receiving events"

```python
# Diagnostic steps:
"Run deep webhook diagnostics for https://myapp.com/webhook"

# Check:
# 1. DNS resolution
# 2. SSL certificate validity
# 3. Endpoint accessibility
# 4. Firewall rules
# 5. Response codes
```

### Issue 2: "Signature verification fails"

```python
# Common causes:
# 1. Using parsed JSON instead of raw body
# 2. Wrong webhook secret
# 3. Encoding mismatch

# Solution:
"Diagnose webhook with my headers and body"
# Provide:
# - webhook_url
# - headers dict
# - raw body string
# - webhook_secret
```

### Issue 3: "Transaction stuck in PENDING"

```python
"Analyze issue: Transaction remains pending after 10 minutes"
# Context:
# - endpoint: transaction.init
# - status: PENDING
# - merchant_id: MYMERCHANT001

# AI analysis will provide:
# - Likely causes
# - Investigation steps
# - Prevention strategies
```

---

## Performance Optimization

### Scenario 1: Reducing API Latency

```python
# Use connection pooling
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=10,
    max_retries=Retry(total=3, backoff_factor=0.5)
)
session.mount('https://', adapter)

# Use session for all API calls
response = session.post(url, json=payload, headers=headers)
```

### Scenario 2: Webhook Optimization

```python
# Process webhooks asynchronously
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

@app.route('/webhook', methods=['POST'])
def webhook():
    # Verify synchronously
    if not verify_signature(request):
        abort(401)
    
    # Process asynchronously
    event = request.get_json()
    executor.submit(process_webhook_async, event)
    
    # Return immediately
    return 'OK', 200

def process_webhook_async(event):
    # Heavy processing here
    handle_event(event)
```

---

## Additional Resources

- [Full Tool Reference](./TOOLS.md)
- [API Specification Format](./API_SPECS.md)
- [Migration Guide](./MIGRATION.md)
- [Changelog](./CHANGELOG.md)

---

**Need help?** Use the MCP tools to get assistance:

```python
# Search documentation
"Search docs for transaction initialization"

# Get interactive guide
"Get interactive guide for UPI payment integration"

# Analyze specific issue
"Analyze issue: Getting 401 errors on webhook"
```
