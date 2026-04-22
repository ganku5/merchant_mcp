#!/usr/bin/env python3
"""
Create Merchant API specifications for IBMB.
"""

import json
import os

OUTPUT_DIR = "/home/ganesh/merchant_mcp/api_specs/ibmb"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Merchant-specific headers
MERCHANT_HEADERS = {
    "request": [
        {
            "name": "Content-Type",
            "required": True,
            "description": "Must be application/json",
            "example_value": "application/json"
        },
        {
            "name": "Accept",
            "required": True,
            "description": "Must be application/json",
            "example_value": "application/json"
        },
        {
            "name": "x-session-id",
            "required": True,
            "description": "A unique UUID for the session, helpful for tracing and debugging"
        },
        {
            "name": "x-trace-id",
            "required": True,
            "description": "A unique UUID for the request, helpful for tracing and debugging"
        },
        {
            "name": "x-timestamp",
            "required": True,
            "description": "Epoch unix timestamp in milliseconds string for request initiation",
            "example_value": "1496918882000"
        },
        {
            "name": "x-merchant-id",
            "required": True,
            "description": "Merchant identifier"
        },
        {
            "name": "x-merchant-channel-id",
            "required": True,
            "description": "Merchant Channel Identifier"
        }
    ],
    "response": [
        {
            "name": "Content-Type",
            "required": True,
            "description": "Will be application/json"
        }
    ]
}

# Common device details structure
DEVICE_DETAILS_FIELDS = [
    {
        "parent_path": "deviceDetails",
        "field_name": "geocode",
        "field_type": "string",
        "requirement": "optional",
        "description": "User location latitude,longitude",
        "constraints": {"pattern": "^nn\\.nnnn,nn\\.nnnn$"}
    },
    {
        "parent_path": "deviceDetails",
        "field_name": "ip",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Device ip address",
        "constraints": {"maxLength": 20, "pattern": "^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"}
    },
    {
        "parent_path": "deviceDetails",
        "field_name": "browser",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Browser used on user device",
        "constraints": {"maxLength": 20}
    },
    {
        "parent_path": "deviceDetails",
        "field_name": "os",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "OS of the user device",
        "constraints": {"maxLength": 20}
    },
    {
        "parent_path": "deviceDetails",
        "field_name": "deviceId",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Device ID of the user device",
        "constraints": {"maxLength": 35}
    },
    {
        "parent_path": "deviceDetails",
        "field_name": "appId",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "App id",
        "constraints": {"maxLength": 20}
    },
    {
        "parent_path": "deviceDetails",
        "field_name": "location",
        "field_type": "string",
        "requirement": "optional",
        "description": "Location of the user",
        "constraints": {"maxLength": 40}
    }
]

# Common additional info structure
ADDITIONAL_INFO_FIELDS = [
    {
        "parent_path": "additionalInfo[*]",
        "field_name": "name",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Name of the property",
        "constraints": {"maxLength": 255}
    },
    {
        "parent_path": "additionalInfo[*]",
        "field_name": "value",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Value of the property",
        "constraints": {"maxLength": 255}
    },
    {
        "parent_path": "additionalInfo[*]",
        "field_name": "visibility",
        "field_type": "boolean",
        "requirement": "mandatory",
        "description": "Property visible to customer",
        "example_value": True
    }
]

# Amount breakup structure
AMOUNT_BREAKUP_FIELDS = [
    {
        "parent_path": "amountBreakUp[*]",
        "field_name": "name",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Amount breakup name",
        "constraints": {"maxLength": 50}
    },
    {
        "parent_path": "amountBreakUp[*]",
        "field_name": "value",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Amount breakup value",
        "constraints": {"maxLength": 50, "pattern": "^(0|[1-9][0-9]*)\\.[0-9]{2}$"}
    }
]

# TPV details structure
TPV_DETAILS_FIELDS = [
    {
        "parent_path": "tpvDetails",
        "field_name": "custName",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Customer name for TPV",
        "constraints": {"maxLength": 50}
    },
    {
        "parent_path": "tpvDetails",
        "field_name": "accNum",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Customer plain text account number for TPV",
        "constraints": {"maxLength": 30, "pattern": "^\\d{1,30}$"}
    },
    {
        "parent_path": "tpvDetails",
        "field_name": "ifsc",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Customer IFSC for TPV",
        "constraints": {"length": 12}
    }
]

# Merchant structure (for dynamic merchant flow)
MERCHANT_FIELDS = [
    {
        "parent_path": "merchant",
        "field_name": "mcc",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Merchant Category Code",
        "constraints": {"length": 4, "pattern": "^[0-9]{4}$"}
    },
    {
        "parent_path": "merchant",
        "field_name": "mid",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Merchant ID",
        "constraints": {"pattern": "^[A-Z]{3}[0-9]{2}[A-Z0-9]{8}[0-9]{2}$"}
    },
    {
        "parent_path": "merchant",
        "field_name": "merchantLegalName",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Merchant Legal Name",
        "constraints": {"maxLength": 255}
    },
    {
        "parent_path": "merchant",
        "field_name": "beneficiary",
        "field_type": "object",
        "requirement": "mandatory",
        "description": "Merchant (beneficiary) details"
    },
    {
        "parent_path": "merchant.beneficiary",
        "field_name": "id",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Merchant (beneficiary) ID",
        "constraints": {"maxLength": 5}
    },
    {
        "parent_path": "merchant.beneficiary",
        "field_name": "accountNumber",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Merchant's Account Number",
        "constraints": {"maxLength": 30}
    }
]


def create_merchant_transaction_init_api():
    """Merchant Transaction Init API - /api/merchants/v1/tranasction/initiate"""
    return {
        "endpoint_id": "ibmb.merchant.transaction.init",
        "method": "POST",
        "path": "/api/merchants/v1/tranasction/initiate",
        "api_version": "v1",
        "description": "Generate URLs for QR/INTENT/REDIRECTION based transactions. Used by merchant server to initiate payment requests.",
        "summary": "Initiate transaction and generate payment URL",
        "headers": MERCHANT_HEADERS,
        "request_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "A unique id for the request (same as x-trace-id header)",
                "constraints": {"maxLength": 50}
            },
            {
                "parent_path": "",
                "field_name": "requestTs",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Timestamp of the request (same as x-timestamp header)",
                "constraints": {"length": 13}
            },
            {
                "parent_path": "",
                "field_name": "merchantRequestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Reference ID of the merchant transaction (Julian Date: YDDD + random alphanumeric)",
                "constraints": {"length": 20}
            },
            {
                "parent_path": "",
                "field_name": "intentExpiry",
                "field_type": "string",
                "requirement": "optional",
                "description": "Expiry of the intent in seconds",
                "example_value": "300",
                "default_value": "86400"
            },
            {
                "parent_path": "",
                "field_name": "amount",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Amount of the transaction",
                "constraints": {"pattern": "^(0|[1-9][0-9]*)\\.[0-9]{2}$"},
                "example_value": "1000.00"
            },
            {
                "parent_path": "",
                "field_name": "initiationMode",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Mode of the transaction",
                "constraints": {"enum": ["QR", "INTENT", "REDIRECTION"]}
            },
            {
                "parent_path": "",
                "field_name": "currency",
                "field_type": "string",
                "requirement": "optional",
                "description": "Currency to be used for the transaction",
                "default_value": "INR"
            },
            {
                "parent_path": "",
                "field_name": "amountBreakUp",
                "field_type": "array",
                "subtype": "object",
                "requirement": "optional",
                "description": "Amount breakup details"
            },
            *AMOUNT_BREAKUP_FIELDS,
            {
                "parent_path": "",
                "field_name": "tpvDetails",
                "field_type": "object",
                "requirement": "optional",
                "description": "TPV details provided by merchant"
            },
            *TPV_DETAILS_FIELDS,
            {
                "parent_path": "",
                "field_name": "additionalInfo",
                "field_type": "array",
                "subtype": "object",
                "requirement": "optional",
                "description": "Additional info for UDF parameters"
            },
            *ADDITIONAL_INFO_FIELDS,
            {
                "parent_path": "",
                "field_name": "deviceDetails",
                "field_type": "object",
                "requirement": "mandatory",
                "description": "Customer device information"
            },
            *DEVICE_DETAILS_FIELDS,
            {
                "parent_path": "",
                "field_name": "merchant",
                "field_type": "object",
                "requirement": "conditional",
                "condition_description": "Required for Dynamic Merchant Flow",
                "description": "Details of merchant"
            },
            *MERCHANT_FIELDS
        ],
        "response_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Request ID echoed back"
            },
            {
                "parent_path": "",
                "field_name": "result",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "API response status",
                "constraints": {"enum": ["SUCCESS", "FAILURE"]}
            },
            {
                "parent_path": "",
                "field_name": "responseCode",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "API response code"
            },
            {
                "parent_path": "",
                "field_name": "responseMessage",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "API response message"
            },
            {
                "parent_path": "",
                "field_name": "payload",
                "field_type": "object",
                "requirement": "mandatory",
                "description": "Response Payload"
            },
            {
                "parent_path": "payload",
                "field_name": "merchantRequestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Reference ID of the transaction"
            },
            {
                "parent_path": "payload",
                "field_name": "intentExpiry",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Expiry of the intent"
            },
            {
                "parent_path": "payload",
                "field_name": "amount",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Amount of the transaction"
            },
            {
                "parent_path": "payload",
                "field_name": "initiationMode",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Mode of the transaction"
            },
            {
                "parent_path": "payload",
                "field_name": "currency",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Currency code"
            },
            {
                "parent_path": "payload",
                "field_name": "amountBreakUp",
                "field_type": "array",
                "subtype": "object",
                "requirement": "optional",
                "description": "Amount breakup details"
            },
            {
                "parent_path": "payload.amountBreakUp[*]",
                "field_name": "name",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Amount breakup name"
            },
            {
                "parent_path": "payload.amountBreakUp[*]",
                "field_name": "value",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Amount breakup value"
            },
            {
                "parent_path": "payload",
                "field_name": "tpvDetails",
                "field_type": "object",
                "requirement": "optional",
                "description": "TPV details"
            },
            {
                "parent_path": "payload.tpvDetails",
                "field_name": "custName",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload.tpvDetails",
                "field_name": "accNum",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload.tpvDetails",
                "field_name": "ifsc",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload",
                "field_name": "additionalInfo",
                "field_type": "array",
                "subtype": "object",
                "requirement": "optional"
            },
            {
                "parent_path": "payload",
                "field_name": "device",
                "field_type": "object",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload",
                "field_name": "merchant",
                "field_type": "object",
                "requirement": "conditional",
                "condition_description": "Present for dynamic merchant flow"
            },
            {
                "parent_path": "payload",
                "field_name": "url",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Url sent by NBBL (deeplink)"
            }
        ],
        "conditions": [
            {
                "condition_name": "dynamic_merchant_required",
                "description": "Merchant object required for dynamic merchant flow",
                "expression": "merchant.mid IS NOT NULL AND merchant.mid != ''"
            }
        ],
        "samples": [
            {
                "sample_name": "intent_init_success",
                "description": "Initiate INTENT mode transaction",
                "scenario": "happy_path",
                "request": {
                    "headers": {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "x-session-id": "550e8400-e29b-41d4-a716-446655440000",
                        "x-trace-id": "trx-123-456-789",
                        "x-timestamp": "1496918882000",
                        "x-merchant-id": "MERCHANT123",
                        "x-merchant-channel-id": "CHANNEL_WEB"
                    },
                    "body": {
                        "requestId": "trx-123-456-789",
                        "requestTs": "1496918882000",
                        "merchantRequestId": "20240901234ABCDE5678",
                        "intentExpiry": "300",
                        "amount": "1000.00",
                        "initiationMode": "INTENT",
                        "currency": "INR",
                        "deviceDetails": {
                            "ip": "192.168.1.1",
                            "browser": "Chrome",
                            "os": "Windows 11",
                            "deviceId": "device123456",
                            "appId": "merchant.web.app"
                        }
                    }
                },
                "response": {
                    "status_code": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "requestId": "trx-123-456-789",
                        "result": "SUCCESS",
                        "responseCode": "SUCCESS",
                        "responseMessage": "Intent generated successfully",
                        "payload": {
                            "merchantRequestId": "20240901234ABCDE5678",
                            "intentExpiry": "300",
                            "amount": "1000.00",
                            "initiationMode": "INTENT",
                            "currency": "INR",
                            "url": "nb://pay?ver=1.0&mode=INTENT&orgID=MERCHANT123&...",
                            "device": {
                                "ip": "192.168.1.1",
                                "browser": "Chrome"
                            }
                        }
                    }
                },
                "curl_command": "curl -X POST https://api.example.com/api/merchants/v1/tranasction/initiate \\\n  -H 'Content-Type: application/json' \\\n  -H 'x-session-id: 550e8400-e29b-41d4-a716-446655440000' \\\n  -H 'x-trace-id: trx-123-456-789' \\\n  -H 'x-timestamp: 1496918882000' \\\n  -H 'x-merchant-id: MERCHANT123' \\\n  -H 'x-merchant-channel-id: CHANNEL_WEB' \\\n  -d '{\"requestId\":\"trx-123-456-789\",\"requestTs\":\"1496918882000\",\"merchantRequestId\":\"20240901234ABCDE5678\",\"amount\":\"1000.00\",\"initiationMode\":\"INTENT\",\"deviceDetails\":{\"ip\":\"192.168.1.1\",\"browser\":\"Chrome\",\"os\":\"Windows 11\",\"deviceId\":\"device123456\",\"appId\":\"merchant.web.app\"}}'"
            }
        ],
        "rate_limit": {
            "requests_per_minute": 1000,
            "requests_per_second": 50
        },
        "idempotency": {
            "required": True,
            "header_name": "x-trace-id",
            "ttl_seconds": 300
        }
    }


def create_merchant_status_api():
    """Merchant Status Check API - /api/merchants/v1/transaction/status"""
    return {
        "endpoint_id": "ibmb.merchant.transaction.status",
        "method": "POST",
        "path": "/api/merchants/v1/transaction/status",
        "api_version": "v1",
        "description": "Retrieve the most recent status of the transaction. Used in event of timeout during transaction processing.",
        "summary": "Check transaction status",
        "headers": MERCHANT_HEADERS,
        "request_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "A unique id for the request"
            },
            {
                "parent_path": "",
                "field_name": "requestTs",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Timestamp of the request"
            },
            {
                "parent_path": "",
                "field_name": "merchantRequestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Reference ID of the transaction"
            }
        ],
        "response_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "",
                "field_name": "result",
                "field_type": "string",
                "requirement": "mandatory",
                "constraints": {"enum": ["SUCCESS", "FAILURE"]}
            },
            {
                "parent_path": "",
                "field_name": "responseCode",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "",
                "field_name": "responseMessage",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "",
                "field_name": "payload",
                "field_type": "object",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload",
                "field_name": "merchantRequestId",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload",
                "field_name": "txnStatus",
                "field_type": "string",
                "requirement": "mandatory",
                "constraints": {"enum": ["SUCCESS", "FAILURE", "PENDING"]},
                "description": "Status of the transaction"
            },
            {
                "parent_path": "payload",
                "field_name": "txnResponseCode",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction response code"
            },
            {
                "parent_path": "payload",
                "field_name": "txnResponseMessage",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction response message"
            },
            {
                "parent_path": "payload",
                "field_name": "amount",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload",
                "field_name": "initiationMode",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload",
                "field_name": "currency",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "payload",
                "field_name": "transactionId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Issuing transaction Id"
            },
            {
                "parent_path": "payload",
                "field_name": "type",
                "field_type": "string",
                "requirement": "mandatory",
                "constraints": {"enum": ["TXN_STATUS"]},
                "description": "Type of the request"
            },
            {
                "parent_path": "payload",
                "field_name": "riskScore",
                "field_type": "string",
                "requirement": "optional",
                "description": "Risk score"
            }
        ],
        "conditions": [],
        "samples": [
            {
                "sample_name": "status_check_pending",
                "description": "Transaction still pending",
                "scenario": "pending_status",
                "request": {
                    "headers": MERCHANT_HEADERS["request"],
                    "body": {
                        "requestId": "status-req-001",
                        "requestTs": "1496918882000",
                        "merchantRequestId": "20240901234ABCDE5678"
                    }
                },
                "response": {
                    "status_code": 200,
                    "body": {
                        "requestId": "status-req-001",
                        "result": "SUCCESS",
                        "responseCode": "SUCCESS",
                        "responseMessage": "Status retrieved",
                        "payload": {
                            "merchantRequestId": "20240901234ABCDE5678",
                            "txnStatus": "PENDING",
                            "txnResponseCode": "PENDING",
                            "txnResponseMessage": "Transaction is being processed",
                            "amount": "1000.00",
                            "initiationMode": "INTENT",
                            "currency": "INR",
                            "transactionId": "TXNBANK987654321",
                            "type": "TXN_STATUS"
                        }
                    }
                }
            }
        ]
    }


def create_merchant_callback_spec():
    """Merchant Callback - Webhook from backend to merchant"""
    return {
        "endpoint_id": "ibmb.merchant.callback",
        "method": "POST",
        "path": "{{merchant_callback_url}}",
        "api_version": "v1",
        "description": "Callback initiated by backend to merchant server when there is a status update from the NBBL switch. Requires merchant to provide callback URL.",
        "summary": "Transaction status callback webhook",
        "headers": {
            "request": [
                {
                    "name": "Content-Type",
                    "required": True,
                    "description": "Will be application/json"
                },
                {
                    "name": "X-Callback-Signature",
                    "required": True,
                    "description": "HMAC signature for webhook verification"
                }
            ],
            "response": []
        },
        "request_fields": [
            {
                "parent_path": "",
                "field_name": "merchantRequestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Reference ID of the transaction"
            },
            {
                "parent_path": "",
                "field_name": "status",
                "field_type": "string",
                "requirement": "mandatory",
                "constraints": {"enum": ["SUCCESS", "FAILURE", "PENDING"]},
                "description": "Status of the transaction"
            },
            {
                "parent_path": "",
                "field_name": "responseCode",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction response code"
            },
            {
                "parent_path": "",
                "field_name": "responseMessage",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction response message"
            },
            {
                "parent_path": "",
                "field_name": "amount",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "",
                "field_name": "initiationMode",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "",
                "field_name": "currency",
                "field_type": "string",
                "requirement": "mandatory"
            },
            {
                "parent_path": "",
                "field_name": "transactionId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Issuing transaction Id"
            },
            {
                "parent_path": "",
                "field_name": "type",
                "field_type": "string",
                "requirement": "mandatory",
                "constraints": {"enum": ["TXN_STATUS"]},
                "description": "Type of the callback"
            },
            {
                "parent_path": "",
                "field_name": "riskScore",
                "field_type": "string",
                "requirement": "optional"
            }
        ],
        "response_fields": [
            {
                "parent_path": "",
                "field_name": "acknowledged",
                "field_type": "boolean",
                "requirement": "mandatory",
                "description": "Whether callback was acknowledged"
            }
        ],
        "samples": [
            {
                "sample_name": "callback_success",
                "description": "Transaction completed successfully",
                "scenario": "success_callback",
                "request": {
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Callback-Signature": "sha256=abc123..."
                    },
                    "body": {
                        "merchantRequestId": "20240901234ABCDE5678",
                        "status": "SUCCESS",
                        "responseCode": "TXN_SUCCESS",
                        "responseMessage": "Transaction completed successfully",
                        "amount": "1000.00",
                        "initiationMode": "INTENT",
                        "currency": "INR",
                        "transactionId": "TXNBANK987654321",
                        "type": "TXN_STATUS",
                        "riskScore": "LOW"
                    }
                },
                "response": {
                    "status_code": 200,
                    "body": {
                        "acknowledged": True
                    }
                }
            }
        ]
    }


def save_api_spec(api_spec, filename):
    """Save API spec to JSON file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(api_spec, f, indent=2)
    print(f"Saved: {filepath}")


def main():
    print("=" * 70)
    print("GENERATING MERCHANT API SPECIFICATIONS")
    print("=" * 70)
    
    # Merchant APIs
    tx_init = create_merchant_transaction_init_api()
    save_api_spec(tx_init, "ibmb_merchant_tx_init.json")
    
    tx_status = create_merchant_status_api()
    save_api_spec(tx_status, "ibmb_merchant_tx_status.json")
    
    callback = create_merchant_callback_spec()
    save_api_spec(callback, "ibmb_merchant_callback.json")
    
    # Save combined file
    merchant_apis = [tx_init, tx_status, callback]
    combined_file = os.path.join(OUTPUT_DIR, "_all_merchant_apis.json")
    with open(combined_file, 'w') as f:
        json.dump(merchant_apis, f, indent=2)
    print(f"Saved: {combined_file}")
    
    # Save all IBMB APIs (SDK + Merchant)
    # First load SDK APIs
    sdk_apis = []
    for filename in ["ibmb_axis_sdk_fetch.json", "ibmb_axis_sdk_auth.json", 
                     "ibmb_axis_sdk_pay.json", "ibmb_axis_sdk_status.json"]:
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath) as f:
                sdk_apis.append(json.load(f))
    
    all_ibmb_apis = sdk_apis + merchant_apis
    all_file = os.path.join(OUTPUT_DIR, "_all_ibmb_apis_complete.json")
    with open(all_file, 'w') as f:
        json.dump(all_ibmb_apis, f, indent=2)
    print(f"Saved: {all_file}")
    
    print("\n" + "=" * 70)
    print("GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nGenerated {len(merchant_apis)} Merchant API specifications:")
    for api in merchant_apis:
        print(f"  - {api['endpoint_id']}: {api['method']} {api['path']}")
    print(f"\nTotal IBMB APIs (SDK + Merchant): {len(all_ibmb_apis)}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
