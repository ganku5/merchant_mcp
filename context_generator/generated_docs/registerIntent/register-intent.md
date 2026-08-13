# registerIntent API Integration Guide

## Overview

Source endpoint: `POST {{host}}/api/{{uri}}/merchants/transactions/registerIntent`

The registerIntent API registers a UPI intent transaction for a merchant order. On success, it returns the identifiers required to continue the UPI payment journey. The request supports optional capabilities such as Third-Party Validation (TPV), dynamic payee VPA, split settlement, sub-merchant details, tips, mutual fund details, and a configurable intent request expiry.

## Business Use Case

Use registerIntent when a customer pays through a UPI intent flow and the merchant needs to:

- Initiate an intent transaction for an order.
- Apply TPV or dynamic VPA validation where required.
- Pass split settlement or sub-merchant details along with the transaction.
- Control how long the intent request remains valid.

## Integration Flow

1. Generate a unique `merchantRequestId` for each transaction. `merchantRequestId` is used as the merchant reference/idempotency identifier for the request.
2. Send the registerIntent request with the required field and any optional fields needed for the transaction.
3. On success, store `gatewayTransactionId` and `orderId` from the response to continue the UPI journey.
4. If the outcome of the request is unknown, check the transaction status before creating a new request.

## Endpoint

- **Method:** `POST`
- **URL:** `{{host}}/api/{{uri}}/merchants/transactions/registerIntent`
- **Content-Type:** `application/json`
- The endpoint is authenticated. Request and response bodies are exchanged as encrypted payloads.

## Request

### Required Minimum

```json
{
  "merchantRequestId": "MRN2024010100001"
}
```

### Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `merchantRequestId` | String | Yes | Merchant reference/idempotency identifier for the request. |
| `merchantCustomerId` | String | No | Merchant's identifier for the customer. |
| `upiRequestId` | String | No | UPI request identifier. |
| `amount` | String | No | Transaction amount. |
| `remarks` | String | No | Remarks for the transaction. |
| `refUrl` | String | No | Reference URL for the transaction. |
| `refCategory` | String | No | Reference category for the transaction. |
| `intentRequestExpiryMinutes` | String | No | Validity of the intent request in minutes. |
| `intentRequestExpirySeconds` | String | No | Validity of the intent request in seconds. |
| `flow` | String | No | Flow identifier for the request. |
| `splitDetails` | Array of objects | No | Split details for the transaction. |
| `enableTips` | Boolean | No | Enables tips on the transaction. |
| `mutualFundDetails` | Array of objects | No | Mutual fund details for the transaction. |
| `payerAccountHashes` | Array of strings | No | Hashes of payer accounts. |
| `iat` | String | No | Issued-at timestamp of the request. |
| `udfParameters` | String | No | User-defined parameters. |
| `splitSettlementDetails` | — | No | Split settlement details for the transaction. |
| `subMerchantDetails` | — | No | Sub-merchant details for the transaction. |
| `tpvType` | — | No | Third-Party Validation (TPV) type for the transaction. |
| `payeeVpa` | String | Conditional | Payee VPA. Required when dynamic VPA validation is used for the transaction. |
| `firstExecutionAmount` | String | No | Amount of the first execution, when applicable. |
| `applyRefundOnSuccess` | String | No | Indicates whether a refund is applied on success. |

Sample request:

```json
{
  "merchantRequestId": "MRN2024010100001",
  "merchantCustomerId": "CUST000123",
  "amount": "250.00",
  "remarks": "Payment for order 12345",
  "refUrl": "https://merchant.example.com/orders/12345",
  "refCategory": "ECOM",
  "intentRequestExpiryMinutes": "15",
  "enableTips": false,
  "payeeVpa": "merchantpayee@upi",
  "udfParameters": "key1=value1"
}
```

### Defaults and Omitted Field Behavior

All fields other than `merchantRequestId` are optional. Omitted optional fields are treated as not provided.

## Response

### Success Response

```json
{
  "status": "<status>",
  "responseCode": "<response_code>",
  "responseMessage": "<response_message>",
  "payload": {
    "gatewayTransactionId": "<gateway_transaction_id>",
    "orderId": "<order_id>"
  }
}
```

### Field Reference

| Field | Description |
|---|---|
| `status` | Overall status of the request. |
| `responseCode` | Code describing the outcome of the request. |
| `responseMessage` | Message describing the outcome of the request. |
| `payload.gatewayTransactionId` | Gateway transaction identifier for the registered intent. |
| `payload.orderId` | Order identifier for the transaction. |

## Error Handling

Error responses return `status` as `FAILURE` with a `responseCode` and `responseMessage`; no payload is returned.

| responseCode | Meaning | Recommended action |
|---|---|---|
| `BAD_REQUEST` | The request failed validation. | Correct the request fields and resubmit. |
| `DUPLICATE_REQUEST` | A request with the same `merchantRequestId` already exists. | Do not resubmit; check the transaction status for the original request. |
| `REQUEST_PENDING` | The request is still being processed. | Check the transaction status before taking further action. |
| `REQUEST_EXPIRED` | The intent request has expired. | Create a new request with a new `merchantRequestId` if the payment is still required. |

Example error response:

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST"
}
```

## Retry / Status Guidance

- Use a unique `merchantRequestId` for every new transaction. Reusing an existing `merchantRequestId` returns `DUPLICATE_REQUEST`.
- If the response is not received, the request times out, or the outcome is unknown (including `REQUEST_PENDING`), check the transaction status before creating a new request. Do not retry blindly.
- On `DUPLICATE_REQUEST`, check the transaction status of the original request instead of resubmitting.
- On `REQUEST_EXPIRED`, the intent request is no longer valid. If the payment is still required, create a new registerIntent request with a new `merchantRequestId`.