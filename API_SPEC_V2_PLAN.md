# API Specification V2 - Implementation Plan

## Goal
Extend the MCP system to support comprehensive API specs including headers, conditional fields, nested structures, and complete request/response samples.

## 1. Enhanced Database Schema

### New Tables

#### `api_specs_v2` - Main API Specifications
```sql
CREATE TABLE api_specs_v2 (
    spec_id SERIAL PRIMARY KEY,
    endpoint_id TEXT UNIQUE NOT NULL,
    
    -- Basic info
    method VARCHAR(10) NOT NULL,
    path TEXT NOT NULL,
    api_version TEXT DEFAULT 'v1',
    description TEXT,
    
    -- Documentation
    summary TEXT,
    documentation_url TEXT,
    changelog JSONB DEFAULT '[]',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(method, path, api_version)
);
```

#### `api_headers` - Request/Response Headers
```sql
CREATE TABLE api_headers (
    header_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id),
    header_type VARCHAR(10) NOT NULL CHECK (header_type IN ('request', 'response')),
    
    -- Header info
    name TEXT NOT NULL,
    value_template TEXT,
    required BOOLEAN DEFAULT TRUE,
    description TEXT,
    
    -- Conditional logic
    conditional_when TEXT,
    conditional_expression TEXT,
    
    -- Constraints
    pattern TEXT,
    enum_values JSONB,
    min_length INTEGER,
    max_length INTEGER,
    
    -- Example
    example_value TEXT,
    default_value TEXT,
    
    UNIQUE(spec_id, header_type, name)
);
```

#### `api_fields` - Request/Response Fields (Flattened)
```sql
CREATE TABLE api_fields (
    field_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id),
    context VARCHAR(20) NOT NULL CHECK (context IN ('request', 'response')),
    
    -- Field hierarchy (for nested fields)
    parent_path TEXT DEFAULT '',
    field_name TEXT NOT NULL,
    full_path TEXT GENERATED ALWAYS AS (
        CASE 
            WHEN parent_path = '' THEN field_name
            ELSE parent_path || '.' || field_name
        END
    ) STORED,
    
    -- Type info
    field_type VARCHAR(30) NOT NULL,
    subtype VARCHAR(30),
    format VARCHAR(50),
    
    -- Description
    description TEXT,
    placeholder TEXT,
    
    -- Requirement level
    requirement VARCHAR(20) DEFAULT 'optional' 
        CHECK (requirement IN ('mandatory', 'optional', 'conditional')),
    
    -- Conditional logic
    condition_description TEXT,
    condition_expression TEXT,
    condition_dependencies JSONB DEFAULT '[]',
    
    -- Constraints
    constraints JSONB DEFAULT '{}',
    -- e.g., {
    --   "minLength": 10,
    --   "maxLength": 100,
    --   "pattern": "^[a-z]+$",
    --   "minimum": 0,
    --   "maximum": 1000,
    --   "exclusiveMinimum": true,
    --   "multipleOf": 5,
    --   "enum": ["value1", "value2"]
    -- }
    
    -- Array constraints
    array_constraints JSONB DEFAULT '{}',
    -- e.g., {
    --   "minItems": 1,
    --   "maxItems": 10,
    --   "uniqueItems": true
    -- }
    
    -- Object constraints
    object_constraints JSONB DEFAULT '{}',
    -- e.g., {
    --   "additionalProperties": false,
    --   "minProperties": 1,
    --   "maxProperties": 50,
    --   "required": ["field1", "field2"]
    -- }
    
    -- Examples
    example_value JSONB,
    default_value JSONB,
    
    -- Metadata
    is_sensitive BOOLEAN DEFAULT FALSE,
    encoding VARCHAR(20),
    
    -- Ordering
    display_order INTEGER DEFAULT 0,
    
    UNIQUE(spec_id, context, full_path)
);
```

#### `api_samples` - Complete Request/Response Samples
```sql
CREATE TABLE api_samples (
    sample_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id),
    
    -- Sample identification
    sample_name TEXT NOT NULL,
    description TEXT,
    scenario VARCHAR(50), -- e.g., 'happy_path', 'validation_error', 'edge_case'
    
    -- Complete request
    request JSONB NOT NULL DEFAULT '{}',
    -- Structure: {
    --   "headers": { "Content-Type": "application/json", ... },
    --   "query_params": { "page": 1, ... },
    --   "path_params": { "id": "123" },
    --   "body": { ... }
    -- }
    
    -- Expected response
    response JSONB NOT NULL DEFAULT '{}',
    -- Structure: {
    --   "status_code": 200,
    --   "headers": { "Content-Type": "application/json" },
    --   "body": { ... }
    -- }
    
    -- CURL command
    curl_command TEXT,
    
    -- Validation info
    expected_validation_errors JSONB,
    
    UNIQUE(spec_id, sample_name)
);
```

#### `api_conditions` - Shared Conditional Logic
```sql
CREATE TABLE api_conditions (
    condition_id SERIAL PRIMARY KEY,
    spec_id INTEGER REFERENCES api_specs_v2(spec_id),
    
    condition_name TEXT NOT NULL,
    description TEXT,
    expression TEXT NOT NULL, -- e.g., "payment_mode == 'UPI'"
    
    -- What triggers this condition
    trigger_field TEXT,
    trigger_values JSONB,
    
    UNIQUE(spec_id, condition_name)
);
```

## 2. JSON Format for API Spec Import

### Complete Example JSON Structure
```json
{
  "endpoint_id": "ibmb.axis.sdk.pay.v2",
  "method": "POST",
  "path": "/api/sdk/v2/pay",
  "api_version": "v2",
  "description": "Process payment transaction (SDK Flow)",
  "summary": "Initiate payment via SDK",
  
  "headers": {
    "request": [
      {
        "name": "X-Request-ID",
        "required": true,
        "description": "Unique request identifier",
        "pattern": "^[a-zA-Z0-9-]{20,50}$",
        "example_value": "req-abc-123-def-456"
      },
      {
        "name": "X-Gateway-Mode",
        "required": false,
        "description": "Gateway mode for routing",
        "conditional_when": "routing_decision_needed",
        "conditional_expression": "transaction_amount > 100000",
        "enum_values": ["primary", "backup", "failover"],
        "default_value": "primary"
      }
    ],
    "response": [
      {
        "name": "X-Transaction-ID",
        "required": true,
        "description": "Transaction reference"
      }
    ]
  },
  
  "request_fields": [
    {
      "parent_path": "",
      "field_name": "requestId",
      "field_type": "string",
      "requirement": "mandatory",
      "description": "Unique request identifier",
      "constraints": {
        "minLength": 20,
        "maxLength": 50,
        "pattern": "^[a-zA-Z0-9-]+$"
      },
      "example_value": "req-2024-001-abc"
    },
    {
      "parent_path": "",
      "field_name": "payer",
      "field_type": "object",
      "requirement": "mandatory",
      "description": "Payer information",
      "object_constraints": {
        "required": ["vpa", "name"],
        "additionalProperties": false
      }
    },
    {
      "parent_path": "payer",
      "field_name": "vpa",
      "field_type": "string",
      "requirement": "conditional",
      "description": "Virtual Payment Address",
      "condition_description": "Required when payment_mode is 'UPI' or 'UPI_COLLECT'",
      "condition_expression": "payment_mode IN ['UPI', 'UPI_COLLECT']",
      "condition_dependencies": ["payment_mode"],
      "constraints": {
        "pattern": "^[a-zA-Z0-9._-]+@[a-zA-Z]+$",
        "maxLength": 100
      },
      "example_value": "user@axisbank"
    },
    {
      "parent_path": "payer",
      "field_name": "card_details",
      "field_type": "object",
      "requirement": "conditional",
      "condition_description": "Required when payment_mode is 'CARD'",
      "condition_expression": "payment_mode == 'CARD'",
      "condition_dependencies": ["payment_mode"],
      "object_constraints": {
        "required": ["number", "expiry", "cvv"],
        "minProperties": 3
      }
    },
    {
      "parent_path": "payer.card_details",
      "field_name": "number",
      "field_type": "string",
      "requirement": "mandatory",
      "is_sensitive": true,
      "constraints": {
        "pattern": "^[0-9]{16}$"
      },
      "encoding": "encrypted"
    },
    {
      "parent_path": "",
      "field_name": "items",
      "field_type": "array",
      "subtype": "object",
      "requirement": "mandatory",
      "description": "Order items",
      "array_constraints": {
        "minItems": 1,
        "maxItems": 100
      }
    },
    {
      "parent_path": "items[*]",
      "field_name": "amount",
      "field_type": "number",
      "format": "decimal",
      "requirement": "mandatory",
      "constraints": {
        "minimum": 0.01,
        "maximum": 999999999.99,
        "multipleOf": 0.01
      },
      "example_value": 99.99
    },
    {
      "parent_path": "items[*]",
      "field_name": "tax_breakup",
      "field_type": "array",
      "subtype": "object",
      "requirement": "optional",
      "array_constraints": {
        "uniqueItems": true
      }
    },
    {
      "parent_path": "items[*].tax_breakup[*]",
      "field_name": "type",
      "field_type": "string",
      "requirement": "mandatory",
      "enum_values": ["CGST", "SGST", "IGST"],
      "default_value": "CGST"
    }
  ],
  
  "response_fields": [
    {
      "parent_path": "",
      "field_name": "status",
      "field_type": "string",
      "requirement": "mandatory",
      "enum_values": ["SUCCESS", "PENDING", "FAILED"]
    },
    {
      "parent_path": "",
      "field_name": "txn_details",
      "field_type": "object",
      "requirement": "mandatory"
    },
    {
      "parent_path": "txn_details",
      "field_name": "id",
      "field_type": "string",
      "requirement": "mandatory"
    },
    {
      "parent_path": "txn_details",
      "field_name": "rrn",
      "field_type": "string",
      "requirement": "conditional",
      "condition_description": "Present when status is SUCCESS",
      "condition_expression": "status == 'SUCCESS'"
    }
  ],
  
  "conditions": [
    {
      "condition_name": "routing_decision_needed",
      "description": "Routing decision required for high-value transactions",
      "expression": "transaction_amount > 100000"
    }
  ],
  
  "samples": [
    {
      "sample_name": "happy_path_upi",
      "description": "Successful UPI payment",
      "scenario": "happy_path",
      "request": {
        "headers": {
          "Content-Type": "application/json",
          "X-Request-ID": "req-001-abc",
          "Authorization": "Bearer eyJhbG..."
        },
        "body": {
          "requestId": "req-001-abc",
          "payment_mode": "UPI",
          "amount": 1000.50,
          "currency": "INR",
          "payer": {
            "vpa": "customer@upi",
            "name": "John Doe"
          },
          "payee": {
            "vpa": "merchant@upi",
            "name": "Merchant Store"
          }
        }
      },
      "response": {
        "status_code": 200,
        "headers": {
          "Content-Type": "application/json",
          "X-Transaction-ID": "txn-xyz-789"
        },
        "body": {
          "status": "SUCCESS",
          "txn_details": {
            "id": "txn-xyz-789",
            "reference": "REF123456",
            "timestamp": "2024-01-15T10:30:00Z"
          },
          "message": "Payment successful"
        }
      },
      "curl_command": "curl -X POST https://api.example.com/api/sdk/v2/pay \\\n  -H 'Content-Type: application/json' \\\n  -H 'X-Request-ID: req-001-abc' \\\n  -H 'Authorization: Bearer TOKEN' \\\n  -d '{\"requestId\":\"req-001-abc\",\"amount\":1000.50}'"
    },
    {
      "sample_name": "validation_error",
      "description": "Missing mandatory field",
      "scenario": "validation_error",
      "request": {
        "headers": {
          "Content-Type": "application/json"
        },
        "body": {
          "amount": 1000
        }
      },
      "response": {
        "status_code": 400,
        "body": {
          "status": "FAILED",
          "error": {
            "code": "MISSING_FIELD",
            "message": "requestId is mandatory",
            "field": "requestId"
          }
        }
      },
      "expected_validation_errors": [
        {
          "field": "requestId",
          "error": "mandatory_field_missing",
          "message": "requestId is required"
        }
      ]
    }
  ],
  
  "rate_limit": {
    "requests_per_second": 100,
    "requests_per_minute": 1000,
    "burst_allowance": 200
  },
  
  "idempotency": {
    "required": true,
    "header_name": "X-Idempotency-Key",
    "ttl_seconds": 86400,
    "behavior": "Returns cached response for duplicate keys within TTL"
  }
}
```

## 3. Implementation Components

### A. New Tool: `insert_api_spec_v2`
```python
async def insert_api_spec_v2(spec_json: dict) -> dict:
    """Insert complete API spec with nested fields, headers, and samples."""
```

### B. New Tool: `get_api_spec_v2`
```python
async def get_api_spec_v2(endpoint_id: str, include_samples: bool = True) -> dict:
    """Retrieve complete API spec with all fields, headers, conditions, and samples."""
```

### C. New Tool: `validate_api_request`
```python
async def validate_api_request(endpoint_id: str, request_data: dict) -> dict:
    """Validate a request against the API spec including conditional logic."""
```

### D. New Tool: `generate_sample_request`
```python
async def generate_sample_request(endpoint_id: str, scenario: str = "happy_path") -> dict:
    """Generate a complete sample request for the specified scenario."""
```

## 4. Migration Strategy

1. Create new tables alongside existing ones
2. Write migration script to convert existing specs to new format
3. Update MCP tools to use new schema
4. Deprecate old tables after validation

## 5. Indexing Strategy

```sql
CREATE INDEX idx_api_fields_lookup ON api_fields(spec_id, context, full_path);
CREATE INDEX idx_api_fields_parent ON api_fields(spec_id, context, parent_path);
CREATE INDEX idx_api_samples_scenario ON api_samples(spec_id, scenario);
CREATE INDEX idx_api_headers_lookup ON api_headers(spec_id, header_type, name);
```

## 6. Query Patterns

### Get complete spec with nested fields
```sql
WITH RECURSIVE field_tree AS (
    SELECT * FROM api_fields 
    WHERE spec_id = ? AND context = 'request' AND parent_path = ''
    UNION ALL
    SELECT f.* FROM api_fields f
    JOIN field_tree ft ON f.parent_path = ft.full_path
    WHERE f.spec_id = ? AND f.context = 'request'
)
SELECT * FROM field_tree ORDER BY display_order;
```

### Get fields by condition
```sql
SELECT * FROM api_fields 
WHERE spec_id = ? 
  AND requirement = 'conditional'
  AND condition_dependencies @> ?::jsonb;
```

Want me to implement this plan? I can start with:
1. Creating the database migration script
2. Implementing the `insert_api_spec_v2` tool
3. Updating `get_api_spec` to handle the new format