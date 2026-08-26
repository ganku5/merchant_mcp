# registerIntent API Integration Guide

## Overview

`registerIntent` registers a UPI intent transaction for a merchant. On success, the API returns the identifiers and payment details (such as `gatewayTransactionId`, `orderId`, and payee details) required to continue the UPI journey.

- Source endpoint: `POST /merchants/transactions/registerIntent`
- Request body: JSON
- Response body: JSON
- Authentication: This endpoint requires merchant authentication (vault-based credentials).

## Business Use Case

Use `registerIntent` to create a UPI intent payment request that the customer completes in a UPI app. The API supports:

- Transaction and mandate flows (`flow`: `TRANSACTION` or `MANDATE`)
- Third-party validation configuration (`tpvType`: `FULL` or `PARTIAL`)
- Dynamic payee VPA (`payeeVpa`, required when dynamic VPA validation is enabled)
- Intent expiry control in minutes or seconds
- Split details, split settlement details, mutual fund details, tips, sub-merchant details, and merchant-defined UDF parameters

## Integration Flow

1. Build the request with a unique `merchantRequestId` and any optional business fields (amount, remarks, expiry, flow, TPV, splits, and so on).
2. Send the authenticated `POST` request with a JSON body.
3. The request is validated (field length, format, and allowed-value checks). Validation failures return a `FAILURE` status with an error `responseCode`.
4. On success, read `payload.gatewayTransactionId` and `payload.orderId` and store them for the subsequent UPI journey and status tracking.
5. If the outcome is unknown (timeout or no response), check the transaction status before submitting a new request.

## Endpoint

| Property | Value |
|---|---|
| Method | `POST` |
| URL | `{{host}}/api/{{uri}}/merchants/transactions/registerIntent` |
| Content-Type | `application/json` |
| Authentication | Merchant vault credentials |

## Request

### Required Minimum

```json
{
  "merchantRequestId": "REQ-2024-000123"
}
```

`payeeVpa` is additionally required when dynamic VPA validation is enabled for the merchant.

### Sample Request

```json
{
  "merchantRequestId": "REQ-2024-000123",
  "merchantCustomerId": "CUST98765",
  "upiRequestId": "UPIREQ12345",
  "amount": "199.00",
  "remarks": "Order payment",
  "refUrl": "https://merchant.example.com/order/ORDER123456789",
  "refCategory": "00",
  "intentRequestExpiryMinutes": "30",
  "flow": "TRANSACTION",
  "enableTips": false,
  "payeeVpa": "acme@upi",
  "tpvType": "FULL",
  "udfParameters": "{\"udf1\":\"value1\"}"
}
```

### Field Reference

| Field | Type | Required | Constraints |
|---|---|---|---|
| `merchantRequestId` | String | Yes | 1–35 characters; must match `^[-._]*([a-zA-Z0-9][-._]*)+$`; unique per request; a duplicate value returns `DUPLICATE_REQUEST` |
| `merchantCustomerId` | String | No | 1–256 characters; must match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$` |
| `upiRequestId` | String | No | 1–35 characters; alphanumeric only (`^[a-zA-Z0-9]+$`) |
| `amount` | String | No | Must match `^[0-9]+\.[0-9][0-9]$` (two decimal places); value must be greater than 0 |
| `remarks` | String | No | 1–255 characters; must match `^[ ]*[a-zA-Z0-9-][a-zA-Z0-9 _.,-]*$` |
| `refUrl` | String | No | — |
| `refCategory` | String | No | — |
| `intentRequestExpiryMinutes` | String | No | Digits only; value greater than 0 and up to 64800 |
| `intentRequestExpirySeconds` | String | No | Digits only; value greater than 0 and up to 3888000 |
| `flow` | String | No | Allowed values: `TRANSACTION`, `MANDATE` |
| `splitDetails` | Array | No | — |
| `enableTips` | Boolean | No | — |
| `mutualFundDetails` | Array | No | — |
| `payerAccountHashes` | Array | No | Must be non-empty when provided |
| `iat` | String | No | — |
| `udfParameters` | String | No | Must be a valid JSON object string; must not contain the characters `/ $ - * ! % ~ `` ` |
| `splitSettlementDetails` | Object | No | — |
| `firstExecutionAmount` | String | No | — |
| `applyRefundOnSuccess` | String | No | Must be `true` or `false` (case-insensitive) |
| `subMerchantDetails` | Object | No | — |
| `payeeVpa` | String | Conditional | Required when dynamic VPA validation is enabled; 3–255 characters; must match the configured VPA format |
| `tpvType` | String | No | Allowed values: `FULL`, `PARTIAL` |

### Defaults and Omitted Field Behavior

- Only `merchantRequestId` is mandatory. All other fields are optional and may be omitted.
- Field validations run only when a field is present; omitted optional fields are not validated.
- `payeeVpa` is conditionally required: it must be sent when dynamic VPA validation is enabled for the merchant.
- `merchantRequestId` acts as the merchant reference and idempotency identifier for the request.

## Response

### Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "Intent registered successfully",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL01",
    "merchantCustomerId": "CUST98765",
    "merchantRequestId": "REQ-2024-000123",
    "gatewayTransactionId": "GTWTXN9F8E7D6C5B",
    "orderId": "ORDER123456789",
    "payeeName": "Acme Stores",
    "payeeVpa": "acme@upi",
    "payeeMcc": "5411",
    "amount": "199.00",
    "currency": "INR",
    "remarks": "Order payment",
    "refUrl": "https://merchant.example.com/order/ORDER123456789",
    "refCategory": "00",
    "flow": "TRANSACTION",
    "enableTips": false,
    "tpvType": "FULL"
  },
  "udfParameters": "{\"udf1\":\"value1\"}"
}
```

### Field Reference

Response envelope:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `status` | String | Yes | Overall status of the request |
| `responseCode` | String | Yes | Machine-readable result code |
| `responseMessage` | String | Yes | Result message |
| `payload` | Object | No | Registration details; not present on error responses |
| `udfParameters` | String | No | Merchant-defined UDF parameters |

`payload` fields:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `merchantId` | String | Yes | — |
| `merchantChannelId` | String | Yes | — |
| `merchantCustomerId` | String | No | — |
| `merchantRequestId` | String | Yes | Echo of the request identifier; duplicates return `DUPLICATE_REQUEST` |
| `gatewayTransactionId` | String | Yes | Gateway identifier for the transaction |
| `orderId` | String | Yes | Order identifier for the registered intent |
| `payeeName` | String | Yes | — |
| `payeeVpa` | String | Conditional | Present when dynamic VPA validation is enabled |
| `payeeMcc` | String | No | — |
| `amount` | String | No | — |
| `currency` | String | No | — |
| `remarks` | String | No | — |
| `refUrl` | String | No | — |
| `refCategory` | String | No | — |
| `mutualFundDetails` | Array | No | — |
| `payerAccountHashes` | Array | No | — |
| `firstExecutionAmount` | String | No | — |
| `applyRefundOnSuccess` | String | No | — |
| `flow` | String | No | — |
| `subMerchantId` | String | No | — |
| `subMerchantChannelId` | String | No | — |
| `splitDetails` | Array | No | — |
| `enableTips` | Boolean | No | — |
| `splitSettlementDetails` | Object | No | — |
| `tpvType` | String | No | — |

## Error Handling

Error responses use the same envelope with `status` set to `FAILURE`, an error `responseCode` and `responseMessage`, and no `payload`.

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST"
}
```

| responseCode | Meaning |
|---|---|
| `BAD_REQUEST` | The request failed validation (length, format, or allowed-value checks). Correct the fields and resubmit. |
| `DUPLICATE_REQUEST` | The `merchantRequestId` has already been used. Do not resubmit the same request body with the same identifier. |
| `REQUEST_PENDING` | A previous request is still being processed. |
| `REQUEST_EXPIRED` | The request has expired. |

## Retry / Status Guidance

- Treat `merchantRequestId` as the idempotency identifier. Reusing it returns `DUPLICATE_REQUEST`.
- If the outcome of a request is unknown (timeout, network failure, or no response), check the transaction status first before creating a new request. Do not retry blindly.
- If the status shows the original request was registered, continue the journey with the returned `gatewayTransactionId` and `orderId` instead of registering again.
- On `REQUEST_PENDING`, wait and check the transaction status again.
- On `REQUEST_EXPIRED` or a confirmed failed registration, create a new request with a new unique `merchantRequestId`.