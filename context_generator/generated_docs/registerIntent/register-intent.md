# registerIntent API Integration Guide

## Overview

Source endpoint: `POST /merchants/transactions/registerIntent`

`registerIntent` registers a UPI intent transaction with Juspay before the customer completes payment. On success, the API returns the identifiers and payee details required to continue the UPI journey, including `gatewayTransactionId`, `orderId`, `payeeName`, and `payeeVpa`.

## Business Use Case

Use `registerIntent` when your server needs to register a UPI payment intent ahead of the customer paying through a UPI app. The API supports:

- Standard transaction intents and mandate intents (`flow`: `TRANSACTION` or `MANDATE`).
- Dynamic payee VPA assignment (`payeeVpa`) when dynamic VPA validation is enabled for your merchant account.
- Third-party validation configuration (`tpvType`, `payerAccountHashes`).
- Split details, split settlement configuration, sub-merchant details, mutual fund details, and tips.

## Integration Flow

1. Generate a unique `merchantRequestId` for the intent registration.
2. Send a `POST` request to the `registerIntent` endpoint with the request body.
3. On success, read `payload.gatewayTransactionId`, `payload.orderId`, and the payee details, and use them to continue the UPI payment journey.
4. If the response is a failure, or the outcome is unknown (timeout, network error), check the transaction status before creating a new registration request.

## Endpoint

```
POST {{host}}/api/{{uri}}/merchants/transactions/registerIntent
```

- Content type: `application/json`
- The endpoint is authenticated; send the merchant credentials configured for your server-to-server integration.

## Request

### Required Minimum

```json
{
  "merchantRequestId": "REQ-2024-000123"
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
| `intentRequestExpiryMinutes` | String | No | Digits only; value must be greater than 0 and less than or equal to 64800 |
| `intentRequestExpirySeconds` | String | No | Digits only; value must be greater than 0 and less than or equal to 3888000 |
| `flow` | String | No | Allowed values: `TRANSACTION`, `MANDATE` |
| `splitDetails` | Array | No | Array of split detail objects; see Nested Request Objects |
| `enableTips` | Boolean | No | — |
| `mutualFundDetails` | Array | No | Array of mutual fund detail objects; see Nested Request Objects |
| `payerAccountHashes` | Array | No | When provided, the list must be non-empty |
| `iat` | String | No | — |
| `udfParameters` | String | No | Must be a JSON object serialized as text; must not contain the characters `/ $ - * ! % ~ `` ` |
| `splitSettlementDetails` | Object | No | See Nested Request Objects |
| `firstExecutionAmount` | String | No | — |
| `applyRefundOnSuccess` | String | No | Must be `true` or `false` (case-insensitive) |
| `subMerchantDetails` | Object | No | See Nested Request Objects |
| `payeeVpa` | String | Conditional | Required when dynamic VPA validation is enabled for the merchant; 3–255 characters; must match the configured VPA format |
| `tpvType` | String | No | Allowed values: `FULL`, `PARTIAL` |

### Defaults and Omitted Field Behavior

- `merchantRequestId` is the only mandatory field. All other fields are optional.
- Optional fields that are omitted are not validated and take no default value in the request.
- `payeeVpa` is optional in the general case but becomes required when dynamic VPA validation is enabled for your merchant account.

### Nested Request Objects

**`splitDetails`** — array of objects:

| Field | Type | Required |
|---|---|---|
| `name` | String | Yes |
| `value` | String | Yes |

**`mutualFundDetails`** — array of objects:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `memberId` | String | Yes | — |
| `userId` | String | Yes | — |
| `mfPartner` | String | Yes | Allowed values: `NSE`, `BSE`, `KFIN`, `CAMS` |
| `investmentType` | String | Yes | Allowed values: `LUMPSUM`, `SIP` |
| `orderNumber` | String | Yes | — |
| `amount` | String | Yes | — |
| `amcCode` | String | No | — |
| `folioNumber` | String | No | — |
| `ihNumber` | String | No | — |
| `schemeCode` | String | No | — |
| `panNumber` | String | No | — |
| `applicationNumber` | String | No | Partner reference number (ITRN) |

**`splitSettlementDetails`** — object:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `splitType` | String | Yes | Allowed values: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER` |
| `merchantSplit` | String | No | — |
| `partnersSplit` | Array | No | Array of objects with `partnerId` (String, required) and `value` (String, required) |

**`subMerchantDetails`** — object:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `name` | String | Yes | — |
| `accountNumber` | String | No | — |
| `ifsc` | String | No | — |
| `bankName` | String | No | — |
| `accountType` | String | No | — |
| `bankIIN` | String | No | — |
| `mcc` | String | Yes | — |
| `brandName` | String | Yes | — |
| `legalName` | String | Yes | — |
| `franchise` | String | Yes | — |
| `merchantType` | String | Yes | `SMALL` or `LARGE` |
| `ownershipType` | String | Yes | — |
| `genre` | String | Yes | `OFFLINE` or `ONLINE` |
| `onboardingType` | String | Yes | `BANK`, `AGGREGATOR`, `NETWORK`, or `TPAP` |
| `gstin` | String | No | — |
| `mid` | String | No | — |
| `sid` | String | No | — |
| `tid` | String | No | — |

## Request Examples

Minimum request:

```json
{
  "merchantRequestId": "REQ-2024-000123"
}
```

Request with amount, expiry, and dynamic payee VPA:

```json
{
  "merchantRequestId": "REQ-2024-000124",
  "merchantCustomerId": "CUST-8899",
  "amount": "100.00",
  "remarks": "Order payment",
  "intentRequestExpiryMinutes": "30",
  "payeeVpa": "acme@upi",
  "tpvType": "FULL",
  "payerAccountHashes": ["a1b2c3d4e5"],
  "udfParameters": "{\"udf1\":\"order-7788\"}"
}
```

## Response

### Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-8899",
    "merchantRequestId": "REQ-2024-000124",
    "gatewayTransactionId": "GTXN987654321",
    "orderId": "ORDER987654",
    "payeeName": "Acme Stores",
    "payeeVpa": "acme@upi",
    "payeeMcc": "5411",
    "amount": "100.00",
    "currency": "INR",
    "remarks": "Order payment",
    "refUrl": "https://merchant.example.com/order/7788",
    "refCategory": "RETAIL",
    "flow": "TRANSACTION",
    "tpvType": "FULL",
    "payerAccountHashes": ["a1b2c3d4e5"],
    "firstExecutionAmount": "100.00",
    "applyRefundOnSuccess": "true"
  },
  "udfParameters": "{\"udf1\":\"order-7788\"}"
}
```

### Field Reference

Response envelope:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `status` | String | Yes | Request outcome status |
| `responseCode` | String | Yes | Machine-readable result code |
| `responseMessage` | String | Yes | Human-readable result message |
| `payload` | Object | No | Present on success; contains the registered intent details |
| `udfParameters` | String | No | Echoes the UDF parameters sent in the request |

Response payload:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `merchantId` | String | Yes | — |
| `merchantChannelId` | String | Yes | — |
| `subMerchantId` | String | No | Returned from payload version V3 onward |
| `subMerchantChannelId` | String | No | Returned from payload version V3 onward |
| `merchantCustomerId` | String | No | — |
| `merchantRequestId` | String | Yes | Echoes the request identifier |
| `gatewayTransactionId` | String | Yes | Gateway identifier for the transaction |
| `orderId` | String | Yes | Order identifier for the registered intent |
| `payeeName` | String | Yes | — |
| `payeeVpa` | String | Conditional | Returned when dynamic VPA validation is enabled |
| `payeeMcc` | String | No | — |
| `amount` | String | No | — |
| `splitDetails` | Array | No | Returned from payload version V3 onward |
| `enableTips` | Boolean | No | Returned from payload version V3 onward |
| `currency` | String | No | — |
| `remarks` | String | No | — |
| `refUrl` | String | No | — |
| `refCategory` | String | No | — |
| `flow` | String | No | Returned from payload version V2 onward |
| `tpvType` | String | No | Returned from payload version V4 onward |
| `mutualFundDetails` | Array | No | — |
| `payerAccountHashes` | Array | No | — |
| `splitSettlementDetails` | Object | No | Returned from payload version V3 onward |
| `firstExecutionAmount` | String | No | — |
| `applyRefundOnSuccess` | String | No | — |

## Response Versioning

The response payload is versioned. Newer versions add fields on top of the base payload:

- **V1 (base):** `merchantId`, `merchantChannelId`, `merchantCustomerId`, `merchantRequestId`, `gatewayTransactionId`, `orderId`, `payeeName`, `payeeVpa`, `payeeMcc`, `amount`, `currency`, `remarks`, `refUrl`, `refCategory`, `mutualFundDetails`, `payerAccountHashes`, `firstExecutionAmount`, `applyRefundOnSuccess`.
- **V2:** adds `flow`.
- **V3:** adds `subMerchantId`, `subMerchantChannelId`, `splitDetails`, `enableTips`, and `splitSettlementDetails`.
- **V4:** adds `tpvType`.

## Idempotency

`merchantRequestId` is the merchant reference and idempotency identifier for the request. It must be unique per request. Submitting a request with a `merchantRequestId` that was already used returns a failure response with `responseCode` `DUPLICATE_REQUEST` and a null payload.

## Expiry

You can control how long the registered intent remains payable using either expiry field:

- `intentRequestExpiryMinutes`: numeric string, greater than 0 and up to 64800.
- `intentRequestExpirySeconds`: numeric string, greater than 0 and up to 3888000.

Values outside these ranges, or non-numeric values, fail validation.

## Validation During Payment

- `payeeVpa` must be supplied when dynamic VPA validation is enabled for your merchant account; it must be 3–255 characters and match the configured VPA format.
- `tpvType` (`FULL` or `PARTIAL`) configures third-party validation behavior for the payment.
- `payerAccountHashes`, when provided, must be a non-empty list.

## Feature-Specific Notes

- `flow` accepts only `TRANSACTION` or `MANDATE`; any other value fails validation.
- `applyRefundOnSuccess` is a boolean string and accepts only `true` or `false` (case-insensitive).
- `udfParameters` must be a JSON object serialized as text and must not contain the characters `/ $ - * ! % ~ `` `; the same value is echoed back in the response envelope.
- `mutualFundDetails[].mfPartner` accepts `NSE`, `BSE`, `KFIN`, or `CAMS`; `mutualFundDetails[].investmentType` accepts `LUMPSUM` or `SIP`.
- `splitSettlementDetails.splitType` accepts `AMOUNT`, `PERCENTAGE`, `DEFAULT`, or `LATER`.

## Error Handling

Failures return `status` `FAILURE` with a `responseCode` and `responseMessage` describing the failure, and a null payload.

| Condition | Response |
|---|---|
| `merchantRequestId` already used | `responseCode`: `DUPLICATE_REQUEST`, `responseMessage`: `DUPLICATE_REQUEST`, `payload`: null |
| `merchantRequestId` fails length or format rules | Validation failure (length must be 1–35; format `^[-._]*([a-zA-Z0-9][-._]*)+$`) |
| `merchantCustomerId` fails length or format rules | Validation failure (length 1–256; allowed character set) |
| `upiRequestId` fails length or format rules | Validation failure (length 1–35; alphanumeric only) |
| `amount` format invalid or not greater than 0 | Validation failure |
| `remarks` fails length or format rules | Validation failure (length 1–255) |
| Expiry value non-numeric or out of range | Validation failure |
| `flow` not in `TRANSACTION`, `MANDATE` | Validation failure |
| `tpvType` not in `FULL`, `PARTIAL` | Validation failure |
| `payerAccountHashes` provided as an empty list | Validation failure |
| `udfParameters` not parseable as a JSON object or contains disallowed characters | Validation failure |
| `applyRefundOnSuccess` not `true`/`false` | Validation failure |
| `payeeVpa` fails length or format rules | Validation failure (length 3–255) |

Example duplicate-request failure:

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST",
  "payload": null
}
```

## Retry / Status Guidance

- If the request fails validation, correct the field values and resend.
- If the outcome of a request is unknown (timeout, network failure, or no response), check the transaction status using the transaction status API before creating a new `registerIntent` request. Do not blindly retry.
- Do not resend the same `merchantRequestId` after receiving `DUPLICATE_REQUEST`; confirm the status of the original request first.
- Use a new unique `merchantRequestId` only when you are intentionally creating a new intent registration.