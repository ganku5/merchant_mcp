#!/usr/bin/env python3
"""
Manually create IBMB API specs from the extracted text.
Based on the [Axis] IBMB Bank Server API Specifications.pdf
"""

import json
import os

OUTPUT_DIR = "/home/ganesh/merchant_mcp/api_specs/ibmb"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Error codes loaded from CSV
IBMB_ERROR_CODES = [
    {"error_code": "IBMB001", "description": "Request json object is not in standard format"},
    {"error_code": "IBMB002", "description": "Request is invalid"},
    {"error_code": "IBMB003", "description": "Reference ID is not sent"},
    {"error_code": "IBMB004", "description": "Request is not found"},
    {"error_code": "IBMB005", "description": "Request is failed in Validation"},
    {"error_code": "IBMB006", "description": "Exception found"},
    {"error_code": "IBMB007", "description": "Response object is null and it must be present"},
    {"error_code": "IBMB008", "description": "Requested HEAD timestamp is not within accepted tolerance"},
    {"error_code": "IBMB009", "description": "RequestBody is null or Empty"},
    {"error_code": "IBMB010", "description": "Duplicate request found"},
    {"error_code": "IBMB011", "description": "ReferenceID sent mismatch with the txn refID"},
    {"error_code": "IBMB012", "description": "No transaction found for particular refID/mode mismatch"},
    {"error_code": "IBMB013", "description": "Reference ID mismatch in the request and urn"},
    {"error_code": "IBMB014", "description": "Duplicates found for same refID in keyDB/cache for RequestType FETCH"},
    {"error_code": "IBMB015", "description": "Unexpected error thrown"},
    {"error_code": "IBMB016", "description": "Head Ts is a future date, invalid"},
    {"error_code": "IBMB017", "description": "Reference ID mismatch in the response and request"},
    {"error_code": "IBMB018", "description": "Reference ID mismatch in the request refID was not part of reqTxnInit"},
    {"error_code": "IBMB019", "description": "Duplicate TxnId found"},
    {"error_code": "IBMB020", "description": "Requested Transaction is not found and might be under processing"},
    {"error_code": "IBMB021", "description": "Duplicate Request since RefID is already exist"},
    {"error_code": "IBMB022", "description": "TxnID is not unique"},
    {"error_code": "IBMB023", "description": "RefID is not unique"},
    {"error_code": "IBMB024", "description": "A success response has already been found for the given referenceID"},
    {"error_code": "IBMB025", "description": "Cannot process request - already successful txn with the same RefID"},
    {"error_code": "IBMB026", "description": "Cannot process request - already successful txn with the same txnID"},
    {"error_code": "IBMB027", "description": "Cannot process request - already failed txn with the same txnID"},
    {"error_code": "IBMB028", "description": "Cannot process request - already failed txn with the same refID"},
    {"error_code": "IBMB029", "description": "Suspected fraud, decline / transactions declined based on risk score"},
    {"error_code": "IBMB030", "description": "Blacklisted Merchant"},
    {"error_code": "IBMB031", "description": "Blacklisted MCC"},
    {"error_code": "IBMB032", "description": "Blacklisted entity"},
    {"error_code": "IBMB033", "description": "Txn Ts is a future date, invalid"},
    {"error_code": "IBMB034", "description": "Exception occurred while processing request"},
    {"error_code": "IBMB035", "description": "Invalid timeStamp format"},
    {"error_code": "IBMB036", "description": "ReqPay Failure Response send to Bank"},
    {"error_code": "IBMB037", "description": "No Transaction details found. Please wait till timeout period"},
    {"error_code": "IBMB038", "description": "Transaction Timed-out"}
]

# Common headers for all IBMB APIs
COMMON_HEADERS = {
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
            "description": "A unique UUID for the session, helpful for tracing and debugging",
            "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        },
        {
            "name": "x-request-id",
            "required": True,
            "description": "A unique UUID for the request, helpful for tracing and debugging",
            "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        },
        {
            "name": "x-timestamp",
            "required": True,
            "description": "Epoch unix timestamp in milliseconds string for request initiation",
            "example_value": "1496918882000",
            "pattern": "^\\d{13}$"
        }
    ],
    "response": [
        {
            "name": "Content-Type",
            "required": True,
            "description": "Will be application/json",
            "example_value": "application/json"
        }
    ]
}

# Common field definitions
DEVICE_FIELDS = [
    {
        "parent_path": "device",
        "field_name": "geocode",
        "field_type": "string",
        "requirement": "optional",
        "description": "User location latitude & longitude"
    },
    {
        "parent_path": "device",
        "field_name": "ip",
        "field_type": "string",
        "requirement": "optional",
        "description": "Device IP address",
        "constraints": {"pattern": "^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"}
    },
    {
        "parent_path": "device",
        "field_name": "deviceId",
        "field_type": "string",
        "requirement": "optional",
        "description": "Device fingerprint",
        "constraints": {"maxLength": 35}
    },
    {
        "parent_path": "device",
        "field_name": "os",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "OS of the user device",
        "constraints": {"maxLength": 20}
    },
    {
        "parent_path": "device",
        "field_name": "appId",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "AppId for the bank mobile banking app",
        "constraints": {"maxLength": 20}
    },
    {
        "parent_path": "device",
        "field_name": "location",
        "field_type": "string",
        "requirement": "optional",
        "description": "Location of the device",
        "constraints": {"maxLength": 40}
    },
    {
        "parent_path": "device",
        "field_name": "browser",
        "field_type": "string",
        "requirement": "optional",
        "description": "Browser used on user device",
        "constraints": {"maxLength": 20}
    }
]

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

KEY_LIST_FIELDS = [
    {
        "parent_path": "keyList[*]",
        "field_name": "keyId",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Key identifier"
    },
    {
        "parent_path": "keyList[*]",
        "field_name": "keyValue",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Key value (Base64 encoded)"
    },
    {
        "parent_path": "keyList[*]",
        "field_name": "keyType",
        "field_type": "string",
        "requirement": "mandatory",
        "description": "Key type"
    }
]


def create_sdk_fetch_api():
    """SDK Fetch API - /api/sdk/v1/fetch"""
    return {
        "endpoint_id": "ibmb.axis.sdk.fetch",
        "method": "POST",
        "path": "/api/sdk/v1/fetch",
        "api_version": "v1",
        "description": "Fetch decrypted transaction details and verify deeplink URL signature. Used by SDK to verify signature and retrieve transaction details including customer bank account information.",
        "summary": "Fetch transaction details and verify URL",
        "headers": COMMON_HEADERS,
        "request_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "A unique id for the request",
                "constraints": {"maxLength": 40},
                "example_value": "995107da-6a85-4cd1-970a-bc1bcc8b837d"
            },
            {
                "parent_path": "",
                "field_name": "requestTs",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Timestamp of the request (epoch unix timestamp)",
                "constraints": {"length": 13},
                "example_value": "1729847669203"
            },
            {
                "parent_path": "",
                "field_name": "requestSource",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Source used to initiate the request",
                "constraints": {"enum": ["SDK", "WEB"]},
                "example_value": "SDK"
            },
            {
                "parent_path": "",
                "field_name": "loginToken",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Unique token generated by bank app for the customer login",
                "constraints": {"pattern": "^[A-Z]{3}[0-9]{2}[0-9]{4}[A-Z0-9]{11}$"}
            },
            {
                "parent_path": "",
                "field_name": "keyList",
                "field_type": "array",
                "subtype": "object",
                "requirement": "optional",
                "description": "List of keys being shared by device to exchange device keys with server",
                "array_constraints": {"minItems": 1}
            },
            *KEY_LIST_FIELDS,
            {
                "parent_path": "",
                "field_name": "url",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Complete deeplink url as received from the merchant app"
            },
            {
                "parent_path": "",
                "field_name": "device",
                "field_type": "object",
                "requirement": "mandatory",
                "description": "Customer device information",
                "object_constraints": {"required": ["os", "appId"]}
            },
            *DEVICE_FIELDS,
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
                "field_name": "mbSessionId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Session Id passed by Axis Mobile App"
            }
        ],
        "response_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "A unique id for the api"
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
                "field_name": "customerId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Unique customer reference Id generated by bank"
            },
            {
                "parent_path": "",
                "field_name": "keyList",
                "field_type": "array",
                "subtype": "object",
                "requirement": "optional",
                "description": "List of keys returned by server"
            },
            *KEY_LIST_FIELDS,
            {
                "parent_path": "",
                "field_name": "txnDetails",
                "field_type": "object",
                "requirement": "optional",
                "description": "Decrypted transaction details. Returned only if deeplink url is valid"
            },
            {
                "parent_path": "txnDetails",
                "field_name": "refId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Unique referenceId generated by merchant/PA"
            },
            {
                "parent_path": "txnDetails",
                "field_name": "merchant",
                "field_type": "object",
                "requirement": "mandatory",
                "description": "Merchant details for txn"
            },
            {
                "parent_path": "txnDetails.merchant",
                "field_name": "mcc",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Merchant category code"
            },
            {
                "parent_path": "txnDetails.merchant",
                "field_name": "mid",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Merchant id"
            },
            {
                "parent_path": "txnDetails.merchant",
                "field_name": "mName",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Merchant name"
            },
            {
                "parent_path": "txnDetails",
                "field_name": "amount",
                "field_type": "object",
                "requirement": "mandatory",
                "description": "Amount details of txn"
            },
            {
                "parent_path": "txnDetails.amount",
                "field_name": "value",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Amount value"
            },
            {
                "parent_path": "txnDetails.amount",
                "field_name": "curr",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Amount currency code"
            },
            {
                "parent_path": "txnDetails",
                "field_name": "initiationMode",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Initiation mode of txn",
                "constraints": {"enum": ["QR", "INTENT", "REDIRECTION"]}
            },
            {
                "parent_path": "",
                "field_name": "accounts",
                "field_type": "array",
                "subtype": "object",
                "requirement": "optional",
                "description": "Account details of customer. Empty array if no accounts found"
            },
            {
                "parent_path": "accounts[*]",
                "field_name": "accType",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Type of bank account",
                "constraints": {"enum": ["SAVINGS", "CURRENT"]}
            },
            {
                "parent_path": "accounts[*]",
                "field_name": "accRefId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Account reference id"
            },
            {
                "parent_path": "accounts[*]",
                "field_name": "maskedAccNum",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Masked account number"
            },
            {
                "parent_path": "accounts[*]",
                "field_name": "balance",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Account balance"
            },
            {
                "parent_path": "accounts[*]",
                "field_name": "isDefault",
                "field_type": "boolean",
                "requirement": "mandatory",
                "description": "Default account flag"
            },
            {
                "parent_path": "",
                "field_name": "authMethods",
                "field_type": "array",
                "subtype": "object",
                "requirement": "mandatory",
                "description": "List of authorization methods. Empty array if no auth required"
            }
        ],
        "conditions": [],
        "samples": [
            {
                "sample_name": "sdk_fetch_success",
                "description": "Successful SDK fetch with customer accounts",
                "scenario": "happy_path",
                "request": {
                    "headers": {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "x-session-id": "550e8400-e29b-41d4-a716-446655440000",
                        "x-request-id": "995107da-6a85-4cd1-970a-bc1bcc8b837d",
                        "x-timestamp": "1729847669203"
                    },
                    "body": {
                        "requestId": "995107da-6a85-4cd1-970a-bc1bcc8b837d",
                        "requestTs": "1729847669203",
                        "requestSource": "SDK",
                        "loginToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                        "url": "nb://pay?ver=1.0&mode=QR&orgID=PAY123&Tts=2024-10-18T10:30:00+05:30&rid=REF1234567890&expiry=300&tdataEnc=xxx&sign=yyy",
                        "device": {
                            "os": "Android 13",
                            "appId": "axis.mobile.app",
                            "geocode": "12.9716,77.5946"
                        },
                        "mbSessionId": "sess-123-456"
                    }
                },
                "response": {
                    "status_code": 200,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": {
                        "requestId": "995107da-6a85-4cd1-970a-bc1bcc8b837d",
                        "result": "SUCCESS",
                        "responseCode": "SUCCESS",
                        "responseMessage": "Transaction details fetched successfully",
                        "customerId": "CUST1234567890",
                        "txnDetails": {
                            "refId": "REF1234567890",
                            "merchant": {
                                "mcc": "5411",
                                "mid": "AXS12345678901",
                                "mName": "SuperMart"
                            },
                            "amount": {
                                "value": "1000.00",
                                "curr": "INR"
                            },
                            "initiationMode": "QR"
                        },
                        "accounts": [
                            {
                                "accType": "SAVINGS",
                                "accRefId": "AXS12000012345678901",
                                "maskedAccNum": "XXXXXX1234",
                                "balance": "50000.00",
                                "isDefault": True
                            }
                        ],
                        "authMethods": []
                    }
                },
                "curl_command": "curl -X POST https://api.axisbank.com/api/sdk/v1/fetch \\\n  -H 'Content-Type: application/json' \\\n  -H 'Accept: application/json' \\\n  -H 'x-session-id: 550e8400-e29b-41d4-a716-446655440000' \\\n  -H 'x-request-id: 995107da-6a85-4cd1-970a-bc1bcc8b837d' \\\n  -H 'x-timestamp: 1729847669203' \\\n  -d '{\"requestId\":\"995107da-6a85-4cd1-970a-bc1bcc8b837d\",\"requestTs\":\"1729847669203\",\"requestSource\":\"SDK\",\"loginToken\":\"eyJhbGci...\",\"url\":\"nb://pay?...\",\"device\":{\"os\":\"Android 13\",\"appId\":\"axis.mobile.app\"},\"mbSessionId\":\"sess-123-456\"}'"
            }
        ],
        "rate_limit": {
            "requests_per_minute": 100,
            "requests_per_second": 10
        },
        "idempotency": {
            "required": True,
            "header_name": "x-request-id",
            "ttl_seconds": 300
        }
    }


def create_sdk_auth_api():
    """SDK Auth API - /api/sdk/v1/auth"""
    return {
        "endpoint_id": "ibmb.axis.sdk.auth",
        "method": "POST",
        "path": "/api/sdk/v1/auth",
        "api_version": "v1",
        "description": "Authenticate and authorize transaction after customer selects account. Validates additional authentication methods (2FA, MPIN) and processes the payment authorization.",
        "summary": "Authenticate and authorize transaction",
        "headers": COMMON_HEADERS,
        "request_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "A unique id for the request",
                "constraints": {"maxLength": 40}
            },
            {
                "parent_path": "",
                "field_name": "requestTs",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Timestamp of the request (epoch unix timestamp)"
            },
            {
                "parent_path": "",
                "field_name": "refId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Reference ID from deeplink/fetch response",
                "constraints": {"length": 20}
            },
            {
                "parent_path": "",
                "field_name": "accRefId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Selected account reference ID",
                "constraints": {"length": 20}
            },
            {
                "parent_path": "",
                "field_name": "authMethod",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Authentication method used",
                "constraints": {"enum": ["MPIN", "OTP", "BIOMETRIC"]}
            },
            {
                "parent_path": "",
                "field_name": "authValue",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Authentication value (encrypted)",
                "is_sensitive": True
            },
            {
                "parent_path": "",
                "field_name": "credBlock",
                "field_type": "object",
                "requirement": "mandatory",
                "description": "Encrypted credential block"
            }
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
                "constraints": {"enum": ["SUCCESS", "FAILURE", "PENDING"]}
            },
            {
                "parent_path": "",
                "field_name": "responseCode",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Response code"
            },
            {
                "parent_path": "",
                "field_name": "txnId",
                "field_type": "string",
                "requirement": "conditional",
                "condition_description": "Present if result is SUCCESS",
                "description": "Transaction ID generated by bank"
            },
            {
                "parent_path": "",
                "field_name": "status",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction status"
            }
        ],
        "conditions": [],
        "samples": [
            {
                "sample_name": "auth_success",
                "description": "Successful authentication",
                "scenario": "happy_path",
                "request": {
                    "headers": COMMON_HEADERS["request"],
                    "body": {
                        "requestId": "auth-123-456",
                        "requestTs": "1729847669203",
                        "refId": "REF1234567890",
                        "accRefId": "AXS12000012345678901",
                        "authMethod": "MPIN",
                        "authValue": "encrypted_mpin_value",
                        "credBlock": {"encryptedData": "xxx"}
                    }
                },
                "response": {
                    "status_code": 200,
                    "body": {
                        "requestId": "auth-123-456",
                        "result": "SUCCESS",
                        "responseCode": "AUTH_SUCCESS",
                        "txnId": "TXN9876543210",
                        "status": "DEBITED"
                    }
                }
            }
        ]
    }


def create_sdk_pay_api():
    """SDK Pay API - /api/sdk/v1/pay"""
    return {
        "endpoint_id": "ibmb.axis.sdk.pay",
        "method": "POST",
        "path": "/api/sdk/v1/pay",
        "api_version": "v1",
        "description": "Process payment transaction (SDK Flow). Completes the payment by debiting selected account and notifying NBBL.",
        "summary": "Process payment transaction",
        "headers": COMMON_HEADERS,
        "request_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Unique request ID"
            },
            {
                "parent_path": "",
                "field_name": "requestTs",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Request timestamp"
            },
            {
                "parent_path": "",
                "field_name": "refId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Reference ID"
            },
            {
                "parent_path": "",
                "field_name": "accRefId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Account reference ID"
            },
            {
                "parent_path": "",
                "field_name": "txnAmt",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction amount"
            },
            {
                "parent_path": "",
                "field_name": "credBlock",
                "field_type": "object",
                "requirement": "mandatory",
                "description": "Credential block"
            }
        ],
        "response_fields": [
            {
                "parent_path": "",
                "field_name": "result",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Result status"
            },
            {
                "parent_path": "",
                "field_name": "txnId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction ID"
            },
            {
                "parent_path": "",
                "field_name": "status",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction status",
                "constraints": {"enum": ["SUCCESS", "PENDING", "FAILED"]}
            },
            {
                "parent_path": "",
                "field_name": "rrn",
                "field_type": "string",
                "requirement": "conditional",
                "condition_description": "Present when status is SUCCESS",
                "description": "Retrieval Reference Number"
            }
        ],
        "samples": []
    }


def create_sdk_status_api():
    """SDK Status API - /api/sdk/v1/status"""
    return {
        "endpoint_id": "ibmb.axis.sdk.status",
        "method": "POST",
        "path": "/api/sdk/v1/status",
        "api_version": "v1",
        "description": "Check transaction status (SDK Flow). Retrieves current status of transaction.",
        "summary": "Check transaction status",
        "headers": COMMON_HEADERS,
        "request_fields": [
            {
                "parent_path": "",
                "field_name": "requestId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Unique request ID"
            },
            {
                "parent_path": "",
                "field_name": "refId",
                "field_type": "string",
                "requirement": "conditional",
                "condition_description": "Required if txnId not provided",
                "description": "Reference ID"
            },
            {
                "parent_path": "",
                "field_name": "txnId",
                "field_type": "string",
                "requirement": "conditional",
                "condition_description": "Required if refId not provided",
                "description": "Transaction ID"
            }
        ],
        "response_fields": [
            {
                "parent_path": "",
                "field_name": "result",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Result status"
            },
            {
                "parent_path": "",
                "field_name": "txnId",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction ID"
            },
            {
                "parent_path": "",
                "field_name": "status",
                "field_type": "string",
                "requirement": "mandatory",
                "description": "Transaction status"
            }
        ],
        "samples": []
    }


def save_api_spec(api_spec, filename):
    """Save API spec to JSON file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(api_spec, f, indent=2)
    print(f"Saved: {filepath}")


def main():
    print("=" * 70)
    print("GENERATING IBMB API SPECIFICATIONS")
    print("=" * 70)
    
    # SDK APIs
    sdk_fetch = create_sdk_fetch_api()
    save_api_spec(sdk_fetch, "ibmb_axis_sdk_fetch.json")
    
    sdk_auth = create_sdk_auth_api()
    save_api_spec(sdk_auth, "ibmb_axis_sdk_auth.json")
    
    sdk_pay = create_sdk_pay_api()
    save_api_spec(sdk_pay, "ibmb_axis_sdk_pay.json")
    
    sdk_status = create_sdk_status_api()
    save_api_spec(sdk_status, "ibmb_axis_sdk_status.json")
    
    # Save error codes
    error_codes_file = os.path.join(OUTPUT_DIR, "ibmb_error_codes.json")
    with open(error_codes_file, 'w') as f:
        json.dump(IBMB_ERROR_CODES, f, indent=2)
    print(f"Saved: {error_codes_file}")
    
    # Save combined file
    all_apis = [sdk_fetch, sdk_auth, sdk_pay, sdk_status]
    combined_file = os.path.join(OUTPUT_DIR, "_all_ibmb_apis.json")
    with open(combined_file, 'w') as f:
        json.dump(all_apis, f, indent=2)
    print(f"Saved: {combined_file}")
    
    print("\n" + "=" * 70)
    print("GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nGenerated {len(all_apis)} API specifications:")
    for api in all_apis:
        print(f"  - {api['endpoint_id']}: {api['method']} {api['path']}")
    print(f"\nOutput directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
