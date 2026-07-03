# Refund360 API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/refund360`

## Overview

Refund360 is a server-to-server API used to initiate or re-check refunds against a successful or deemed-successful merchant transaction.

This API supports three refund modes through one request shape:

- `ONLINE`: initiates an online UPI refund through the configured refund rail.
- `OFFLINE`: creates or returns an offline refund record for refunds handled outside the online refund rail.
- `UDIR`: initiates a UDIR refund/complaint refund flow.

Newton validates the request envelope, merchant, API access, original transaction, refund feature enablement, refund amount, refund window, split settlement rules, and duplicate refund request id before creating a new refund. If the same `refundRequestId` already exists, behavior depends on the existing refund type, as described below.

Payloads use the standard Newton S2S signed/encrypted request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Use Refund360 when the merchant backend needs a single refund integration that can:

- Refund a completed UPI transaction through online refund rails.
- Record offline refunds for reconciliation and cumulative-refund tracking.
- Initiate UDIR complaint refund flows where enabled.
- Use either the original merchant order id or the original UPI transaction id to find the transaction.
- Supply a merchant-generated refund idempotency key.
- Enforce that cumulative refunds do not exceed the original transaction amount.
- Carry split settlement details for partial refunds of split-settled original transactions.
- Re-check an existing online or UDIR refund when a previous attempt is still pending or deemed.

Important identifiers:

- `refundRequestId`: Merchant-generated refund id and idempotency key. Stored as the refund record's merchant request/reference id.
- `originalMerchantRequestId`: Merchant's original order or transaction reference. Newton uses this to find the original merchant order and linked transaction.
- `originalUpiRequestId`: Newton/UPI id of the original transaction. Use this when the merchant order id is not available.
- `refundUpiRequestId`: Optional merchant-supplied UPI id for the refund transaction. If omitted for online flows, Newton generates/stores the refund transaction id internally.
- `gatewayTransactionId`: Original Newton/UPI transaction id returned in the response.
- `gatewayRefundTransactionId`: Refund UPI transaction id returned in the response when available.
- `gatewayRefundReferenceId`: Gateway reference/RRN for the refund or original transaction, depending on refund type.

## Integration Flow

1. Merchant completes an original payment transaction.
2. Merchant decides the refund type: `ONLINE`, `OFFLINE`, or `UDIR`.
3. Merchant creates a unique `refundRequestId`.
4. Merchant calls `POST /api/{apiVersion}/merchants/transactions/refund360` with either `originalMerchantRequestId` or `originalUpiRequestId`.
5. Newton verifies the request envelope, merchant headers, signature, API access, timestamp, and IP allowlist where configured.
6. Newton validates the decrypted request body.
7. Newton finds the original merchant order and successful/deemed transaction.
8. Newton checks refund enablement, refund TAT, amount limits, duplicate behavior, split settlement rules, and refund VPA rules.
9. Newton creates or updates the refund record, calls the configured downstream refund rail when required, and returns the current refund status.
10. Merchant stores `refundRequestId`, `gatewayTransactionId`, `gatewayRefundTransactionId`, `gatewayResponseStatus`, `gatewayResponseCode`, and `gatewayResponseMessage` for reconciliation.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/refund360
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment under `/api`. The transformer also reads `x-api-version` for response-version behavior. Use the version shared during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-merchant-id` | Yes, unless using an enabled sub-merchant flow | Merchant id assigned by Newton. |
| `x-merchant-channel-id` | Yes, unless using an enabled sub-merchant flow | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required only for sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Conditional | Required only for sub-merchant integrations. |
| `x-timestamp` | Yes | Request timestamp in epoch milliseconds. Newton validates that it is a 13-digit timestamp within 30 minutes of server time, except in configured non-production checksum bypass flows. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payloads. Signature is computed from merchant/sub-merchant ids, timestamp, and raw body using the configured merchant API key and signature strategy. |
| `x-api-version` | Recommended | Controls versioned response behavior. Use `3` or higher for the current Refund360 response payload. |
| `x-request-id` | No | Request correlation id. Newton generates one if omitted and returns it as `x-requestid`. |
| `x-session-id` | No | Session/correlation id. Defaults to `x-request-id` when omitted and is returned as `x-sessionid`. |
| `x-forwarded-for` | Conditional | Required when the merchant has configured `whitelistedIps`; the first IP in this header must be allowlisted. |

### Authentication, Signing, and Encryption

The route accepts Newton's standard S2S envelope:

- Plain JSON business payload.
- JWS signed payload.
- JWE encrypted payload containing a signed payload.

For client integrations, use the signed or encrypted envelope configured during onboarding. The decrypted business payload is the JSON shown in this guide.

JWE request body shape:

```json
{
  "protected": "<jwe protected header>",
  "encryptedKey": "<encrypted key>",
  "iv": "<initialization vector>",
  "cipherText": "<encrypted payload>",
  "tag": "<authentication tag>"
}
```

JWS request body shape:

```json
{
  "payload": "<base64url encoded business payload>",
  "signature": "<jws signature>",
  "protected": "<base64url encoded jws protected header>"
}
```

For unsigned/plain payloads, Newton validates `x-merchant-signature` against:

```text
x-merchant-id + x-merchant-channel-id + x-sub-merchant-id + x-sub-merchant-channel-id + x-timestamp + raw request body
```

Signed/encrypted payloads are still checked for merchant identity, API access, request `iat`, timestamp freshness, and IP restriction where configured.

Responses are returned using the merchant's configured response strategy:

- JWS response when response strategy is `JWS`.
- JWE response when response strategy is `JWS_AND_JWE`.
- Plain business response with `X-Response-Signature` otherwise.

## Request

### Required Minimum: Online Refund

For `ONLINE`, send `merchantRefundVpa` unless the authenticated context is a sub-merchant flow where Newton can resolve the refund merchant without the request VPA.

```json
{
  "originalMerchantRequestId": "ORDER12345",
  "refundRequestId": "REFUND12345",
  "refundAmount": "100.00",
  "refundType": "ONLINE",
  "merchantRefundVpa": "refunds@merchantbank",
  "remarks": "Customer refund"
}
```

### Required Minimum: Offline Refund

```json
{
  "originalMerchantRequestId": "ORDER12345",
  "refundRequestId": "REFUND12346",
  "refundAmount": "100.00",
  "refundType": "OFFLINE",
  "remarks": "Offline refund processed"
}
```

### Required Minimum: UDIR Refund

```json
{
  "originalUpiRequestId": "TXN1234567890",
  "refundRequestId": "REFUND12347",
  "refundAmount": "100.00",
  "refundType": "UDIR",
  "remarks": "UDIR refund",
  "adjCode": "102"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `originalMerchantRequestId` | string | Conditional | No default. | Merchant's original order/transaction reference. Use this or `originalUpiRequestId` to identify the original transaction. If both are supplied, Newton uses `originalMerchantRequestId` first. Length must be 1 to 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore. |
| `originalUpiRequestId` | string | Conditional | No default. | Original Newton/UPI transaction id. Required when `originalMerchantRequestId` is not supplied. Length must be 1 to 35 characters and alphanumeric only. |
| `originalTransactionTimestamp` | string | No | No default. | Original transaction timestamp used to narrow partitioned transaction/order lookup and for refund-window validation when supplied. Must parse as a valid Newton timestamp. |
| `refundRequestId` | string | Yes | No default. | Unique merchant-generated refund id and idempotency key. Length must be 1 to 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore. |
| `refundUpiRequestId` | string | No | Newton generates/stores the refund transaction id where the refund rail requires one. | Optional refund UPI transaction id. Length must be 1 to 35 characters and alphanumeric only. For API versions `> 1`, or when this field is supplied, `gatewayRefundTransactionId` is returned when available. |
| `refundAmount` | string | Yes | No default. | Refund amount. Must be greater than `0.00` and use exactly two decimal places, for example `100.00`. Cumulative refunds for the original transaction cannot exceed the original transaction amount. |
| `refundType` | string | Yes | No default. | Refund mode. Allowed values: `ONLINE`, `OFFLINE`, `UDIR`. The selected type must be enabled for the merchant through `allowedRefundTypes` when that configuration is present. |
| `merchantRefundVpa` | string | Conditional | No default. | Merchant/refund VPA used for online refund merchant lookup. Required for `ONLINE` when Newton cannot resolve a sub-merchant refund account from context. Must pass VPA validation. |
| `remarks` | string | Yes | No default. | Refund remarks. Length must be 1 to 255 characters. Allowed pattern permits letters, numbers, spaces, and hyphen, and must contain an alphanumeric/hyphen start after optional leading spaces. |
| `iat` | string | Conditional for signed/encrypted envelope | No default. | Issued-at timestamp used in request freshness validation for signed/encrypted payloads. Plain unsigned payloads do not require this body field. |
| `udfParameters` | JSON-object string | No | No default. Echoed as `udfParameters` in the top-level response when supplied. | Merchant-defined metadata as a string containing a JSON object. The string must parse as a JSON object and pass the configured character restrictions. |
| `splitSettlementDetails` | object | Conditional | No default. | Required for partial refunds of split-settled original transactions. Rejected when split settlement is disabled for the merchant or not applicable to the original transaction. |
| `adjCode` | string | Conditional | No default. | UDIR request adjustment code. For `UDIR`, if supplied, it must be one of the configured `udirRefundsReqAdjCodes`. Ignored by non-UDIR refund logic. |
| `useGlobalVpaForRefund` | string | No | Defaults from sub-merchant or merchant configuration `useGlobalVpaForRefund`; if no config exists, behavior defaults to `false`. | String boolean, accepted values are `true` or `false` case-insensitively. Used by online refund processing to decide whether to use a global refund VPA. |
| `purpose` | string | No | No default. | Optional UPI purpose code passed to the online refund rail. Must be exactly two uppercase alphanumeric characters. |

### Defaults and Omitted Field Behavior

This API does not generate a `refundRequestId`, `refundAmount`, `refundType`, or `remarks`; those fields are mandatory.

When optional fields are omitted:

- `originalMerchantRequestId`/`originalUpiRequestId`: at least one must be present. If both are omitted, Newton rejects the request.
- `refundUpiRequestId`: Newton may generate/store a refund transaction id for online flows.
- `merchantRefundVpa`: allowed to be omitted except for `ONLINE` without a resolved sub-merchant refund context.
- `originalTransactionTimestamp`: no lookup partition hint is applied.
- `splitSettlementDetails`: no split override is applied. For a partial refund of a split-settled original transaction, omission is rejected.
- `useGlobalVpaForRefund`: falls back to sub-merchant configuration, then parent merchant configuration, then `false`.
- `udfParameters`: omitted from the top-level response.

Internally, new refunds are initialized differently by type:

- `ONLINE`: creates a refund transaction and a pending refund record, then calls the configured online refund rail. Existing pending/deemed online refunds may be status-checked and updated.
- `OFFLINE`: creates an offline refund record. Repeating the same `refundRequestId` returns the existing offline refund.
- `UDIR`: creates/updates the UDIR refund/complaint flow and may trigger status checking for an existing UDIR refund.

### Nested Request Objects

#### `splitSettlementDetails`

Use `splitSettlementDetails` only when split settlement is enabled for the merchant and the original transaction used split settlement.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `splitType` | string | Yes | Settlement split mode. Allowed values: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. For refund partial splits, `AMOUNT` is required. |
| `merchantSplit` | string | Conditional | Merchant's own refund share. Required for `AMOUNT` and `PERCENTAGE` unless using a mode where no explicit split is expected. Must use two decimal places. |
| `partnersSplit` | array of objects | Conditional | Partner refund shares. Required when partners receive a portion of the refund split. |

Validation rules:

- Split settlement must be enabled for the merchant.
- For `AMOUNT`, `merchantSplit` plus all `partnersSplit[].value` values must equal `refundAmount`.
- For `PERCENTAGE`, `merchantSplit` plus all `partnersSplit[].value` values must equal `100.00`.
- For `DEFAULT` and `LATER`, do not send explicit split values unless configured behavior requires them.
- Partner ids may be validated against the merchant's configured vendor/partner list.
- If the original transaction was not split-settled, sending split details is rejected with `SplitSettlement not Allowed`.
- If the original transaction was split-settled and this is a full refund, sending split details is rejected with `SplitSettlementDetails not Required`.
- If the original transaction was split-settled and this is a partial refund, `splitType` must be `AMOUNT`, details must be supplied, and cumulative partner-level refund splits cannot exceed the original partner-level transaction split.

#### `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `partnerId` | string | Yes | Partner/vendor identifier configured for the merchant. Must be non-empty. |
| `value` | string | Yes | Partner's refund share. Must use exactly two decimal places. |

## Request Examples

### Online Refund By Original Merchant Request Id

```json
{
  "originalMerchantRequestId": "ORDER12345",
  "refundRequestId": "REFUND12345",
  "refundAmount": "100.00",
  "refundType": "ONLINE",
  "refundUpiRequestId": "RFNUPI123456",
  "merchantRefundVpa": "refunds@merchantbank",
  "remarks": "Customer refund",
  "useGlobalVpaForRefund": "false",
  "purpose": "00",
  "udfParameters": "{\"ticketId\":\"TICKET123\"}"
}
```

### Offline Refund By Original UPI Request Id

```json
{
  "originalUpiRequestId": "TXN1234567890",
  "refundRequestId": "REFUND12346",
  "refundAmount": "50.00",
  "refundType": "OFFLINE",
  "remarks": "Refund completed offline"
}
```

### Partial Refund With Split Settlement

```json
{
  "originalMerchantRequestId": "ORDER12345",
  "refundRequestId": "REFUND12348",
  "refundAmount": "40.00",
  "refundType": "OFFLINE",
  "remarks": "Partial refund",
  "splitSettlementDetails": {
    "splitType": "AMOUNT",
    "merchantSplit": "30.00",
    "partnersSplit": [
      {
        "partnerId": "PARTNER01",
        "value": "10.00"
      }
    ]
  }
}
```

### UDIR Refund With Adjustment Code

```json
{
  "originalMerchantRequestId": "ORDER12345",
  "refundRequestId": "REFUND12349",
  "refundAmount": "100.00",
  "refundType": "UDIR",
  "remarks": "UDIR refund",
  "adjCode": "102",
  "purpose": "00"
}
```

## Validation and Processing Rules

### Request Body Validation

Newton validates the decrypted business payload before product processing:

- `originalMerchantRequestId`, when present, must be 1 to 35 characters and match the allowed merchant request id format.
- `originalUpiRequestId`, when present, must be 1 to 35 characters and alphanumeric.
- `refundUpiRequestId`, when present, must be 1 to 35 characters and alphanumeric.
- `originalTransactionTimestamp`, when present, must parse as a valid timestamp.
- `refundRequestId` is mandatory, 1 to 35 characters, and must match the allowed merchant request id format.
- `refundAmount` is mandatory, must match `^[0-9]+\\.[0-9][0-9]$`, and must be greater than zero.
- `refundType` must parse to one of `ONLINE`, `OFFLINE`, or `UDIR`.
- `merchantRefundVpa`, when present, must pass VPA validation.
- `remarks` is mandatory, 1 to 255 characters, and must pass remarks validation.
- `udfParameters`, when present, must be a stringified JSON object and pass configured character restrictions.
- `splitSettlementDetails`, when present, must pass split settlement validation against `refundAmount`.
- `useGlobalVpaForRefund`, when present, must be `true` or `false`.
- `purpose`, when present, must be exactly two uppercase alphanumeric characters.

For signed or encrypted envelopes, `iat` must be present and fresh enough to pass timestamp validation.

### Merchant and API Access Validation

Before refund logic runs, Newton:

- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- Resolves and validates sub-merchant context when sub-merchant headers are supplied.
- Checks whether `refund360` is blocked for the merchant.
- Checks allowed API names when the merchant or sub-merchant is configured with explicit API allowlisting.
- Checks IP allowlisting when `whitelistedIps` is configured.
- Checks `allowedRefundTypes`, if configured at merchant, parent merchant, or global level. The requested `refundType` must be present.

The `allowedRefundTypes` check is skipped only when Newton has already found an existing refund for the same `refundRequestId`.

### Original Transaction Lookup

Newton must find the original merchant transaction and merchant order before creating a new refund.

Lookup behavior:

- If `originalMerchantRequestId` is present, Newton first finds the merchant order for the authenticated merchant/sub-merchant, then finds the linked valid merchant transaction.
- If `originalMerchantRequestId` is omitted and `originalUpiRequestId` is present, Newton finds valid transactions by original UPI request id, filters to the authenticated merchant or sub-merchant customer id, then finds the merchant order from the transaction's stored `merchantRequestId`.
- If both identifiers are supplied, `originalMerchantRequestId` takes precedence.
- If neither identifier is supplied, the request fails with `INVALID_DATA`.

The original transaction must be in a success/deemed state accepted by refund processing. If the merchant order has no linked transaction, the request fails with `UNINITIATED_REQUEST`.

### Refund Window

For new `ONLINE` and `UDIR` refunds, Newton uses the online refund TAT from the sub-merchant or merchant store key `transactionExpiryForOnlineRefund`, defaulting to `180` when not configured.

For new `OFFLINE` refunds through Refund360, Newton uses environment configuration `transactionExpiryForRefund`.

If `originalTransactionTimestamp` is supplied, Newton may validate that timestamp against the configured refund window before lookup processing. A transaction outside the refund window is rejected with the configured refund TAT failure.

### Duplicate and Idempotency Behavior

`refundRequestId` is the idempotency key.

If no existing refund is found for the authenticated merchant/sub-merchant, Newton validates feature enablement and creates a new refund.

If an existing refund is found:

- `OFFLINE`: if the existing refund is also `OFFLINE`, Newton returns the existing refund details. If the existing refund is not `OFFLINE`, Newton rejects with `INVALID_DATA` and message `Offline Refund Not Found`.
- `ONLINE`: Newton checks that the existing refund belongs to the same original transaction. If not, it rejects with `INVALID_DATA` and message `Refund Transaction Id mismatch`. If it matches, Newton re-checks/updates the existing online refund when it is still pending or deemed.
- `UDIR`: Newton continues through the UDIR existing-refund path and may perform a status check/update for the existing UDIR refund.

For new refunds, Newton uses a short-lived per-original-transaction lock before validating cumulative refund amount. If parallel refund requests for the same original transaction cannot acquire the lock, Newton rejects the request with `BAD_REQUEST` and message `Multiple Parallel Refund Request Raised`.

### Amount Limits

Newton rejects the request when:

- `refundAmount` is not greater than zero.
- `refundAmount` plus previously recorded refunds for the original transaction exceeds the original transaction amount.
- Split settlement details do not add up to `refundAmount` or exceed partner-level original split limits.

### Online Refund Behavior

For `ONLINE`:

- `merchantRefundVpa` is required unless the authenticated sub-merchant context lets Newton resolve the refund merchant.
- Newton finds the refund merchant record from the request VPA or sub-merchant/parent merchant configuration.
- Newton validates the original merchant order is initiated and linked to a transaction.
- Newton creates a refund transaction and refund record.
- Depending on configuration, Newton initiates the refund through NPCI/Galileo or Olive/mprepay.
- If the refund is pending/deemed, a repeat request with the same `refundRequestId` can re-check status when rate-limit/backoff rules permit.
- For on-us NPCI refunds, Newton validates that the refund payee VPA is active unless `useGlobalVpaForRefund` is true.

### Offline Refund Behavior

For `OFFLINE`:

- Newton records the refund and returns the stored refund result.
- Refund360 allows repeated calls with the same offline `refundRequestId` and returns the existing offline refund.
- Offline refund processing does not require `merchantRefundVpa`.

### UDIR Refund Behavior

For `UDIR`:

- Newton uses the UDIR refund route and creates or updates the complaint/refund flow.
- `adjCode`, when supplied, must be configured as an allowed UDIR refund request adjustment code.
- The response may include UDIR-specific fields such as `crn`, `reqAdjCode`, `reqAdjFlag`, `adjFlag`, and `adjCode`.
- UDIR deemed responses may be exposed as `SUCCESS` instead of `DEEMED` when merchant/config flag `markUdirDeemedAsSuccess` is enabled.

## Response

### Success Response Example: `x-api-version > 2`

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "originalMerchantRequestId": "ORDER12345",
    "refundRequestId": "REFUND12345",
    "refundAmount": "100.00",
    "refundType": "ONLINE",
    "refundTimestamp": "2026-07-02T10:15:30+05:30",
    "remarks": "Customer refund",
    "merchantRefundVpa": "payer@bank",
    "gatewayTransactionId": "TXN1234567890",
    "gatewayRefundReferenceId": "123456789012",
    "gatewayResponseStatus": "PENDING",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Refund is in pending state",
    "gatewayRefundTransactionId": "RFNUPI123456"
  },
  "udfParameters": "{\"ticketId\":\"TICKET123\"}"
}
```

### Success Response Example: Offline Refund

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "originalMerchantRequestId": "ORDER12345",
    "refundRequestId": "REFUND12346",
    "refundAmount": "50.00",
    "refundType": "OFFLINE",
    "refundTimestamp": "2026-07-02T10:16:00+05:30",
    "remarks": "Offline refund processed",
    "gatewayTransactionId": "TXN1234567890",
    "gatewayRefundReferenceId": "123456789012",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayRefundTransactionId": "TXN1234567890"
  }
}
```

### Top-Level Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API result. Success response uses `SUCCESS`. |
| `responseCode` | string | Top-level API response code. Success response uses `SUCCESS`. |
| `responseMessage` | string | Top-level response message. Success response uses `SUCCESS`. |
| `payload` | object | Refund response payload. Present on success. |
| `udfParameters` | string | Echoes request `udfParameters` when supplied. |

### Payload Field Reference: Current Response (`x-api-version > 2`)

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id assigned by Newton. |
| `merchantChannelId` | string | Merchant channel id assigned by Newton. |
| `subMerchantId` | string | Sub-merchant id when the request is processed in sub-merchant context. Omitted otherwise. |
| `subMerchantChannelId` | string | Sub-merchant channel id when applicable. Omitted otherwise. |
| `originalMerchantRequestId` | string | Original merchant order/transaction reference resolved from the original merchant order. |
| `refundRequestId` | string | Merchant refund id/idempotency key. |
| `refundAmount` | string | Refund amount with two decimal places. |
| `refundType` | string | Refund mode: `ONLINE`, `OFFLINE`, or `UDIR`. |
| `refundTimestamp` | string | Refund record creation timestamp. |
| `remarks` | string | Remarks from the request. |
| `merchantRefundVpa` | string | Decrypted payer/refund VPA from the online refund transaction when available. Despite the field name, this is populated from the refund transaction's payer VPA in current product response construction. |
| `riskScore` | string | Risk score when configured to be exposed as a response parameter and available on the refund transaction. |
| `gatewayTransactionId` | string | Original transaction UPI request id. |
| `gatewayRefundReferenceId` | string | Refund gateway reference id/RRN. For offline refunds, this is derived from the original transaction response id. |
| `gatewayResponseStatus` | string | Normalized refund status. Possible values include `SUCCESS`, `PENDING`, `DEEMED`, and `FAILURE`. |
| `gatewayResponseCode` | string | Gateway/refund response code from the refund or refund transaction response. |
| `gatewayResponseMessage` | string | Gateway/refund response message from the refund or refund transaction response. |
| `gatewayRefundTransactionId` | string | Refund UPI transaction id when available. |
| `splitSettlementDetails` | object | Split settlement details stored for the refund, when available. |
| `crn` | string | UDIR complaint reference number when available. |
| `reqAdjCode` | string | UDIR requested adjustment code when available. |
| `reqAdjFlag` | string | UDIR requested adjustment flag when available. |
| `adjFlag` | string | UDIR adjustment flag from the complaint/refund flow when available. |
| `adjCode` | string | UDIR adjustment code from the complaint/refund flow when available. |

### Legacy Response Behavior

For `x-api-version <= 2`, Refund360 returns the legacy payload shape:

- `transactionAmount` is included.
- `merchantRequestId` is included for versions above `0`; it contains the original merchant order/reference id.
- `originalMerchantRequestId`, `remarks`, `merchantRefundVpa`, `subMerchantId`, `subMerchantChannelId`, UDIR adjustment fields, and `crn` are not part of the legacy payload shape.
- `gatewayRefundTransactionId` is included when `x-api-version > 1` or when the request supplied `refundUpiRequestId`; otherwise it may be omitted.

Use `x-api-version: 3` or higher for new integrations so the response clearly distinguishes `refundRequestId` from `originalMerchantRequestId`.

### Gateway Status Mapping

Newton normalizes gateway codes into `gatewayResponseStatus` as follows:

| Gateway code | `gatewayResponseStatus` |
| --- | --- |
| `00` | `SUCCESS` |
| `01`, `91`, `09`, `060`, `070`, `080` | `PENDING` |
| `RB`, `96` | `DEEMED` |
| `JPREFD` | `DEEMED`, or `SUCCESS` for UDIR when `markUdirDeemedAsSuccess` is enabled |
| Any other code | `FAILURE` |

## Error Handling

Failure responses use the same response transport strategy as success responses. After decryption, failures generally follow this body shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Both upiRequestId and merchantTransactionId cannot be Nothing"
}
```

HTTP status can vary by validation layer. Clients should always read decrypted `status`, `responseCode`, and `responseMessage`.

### Validation Error Examples

Missing both original transaction identifiers:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Both upiRequestId and merchantTransactionId cannot be Nothing"
}
```

Invalid amount format or non-positive amount:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "amount regex match failed"
}
```

Cumulative refund amount exceeds the original transaction amount:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_REFUND_AMOUNT",
  "responseMessage": "INVALID_REFUND_AMOUNT"
}
```

Online refund without a resolvable refund merchant VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "MerchantRefundVpa and subMerchant both Not Present for Online Refund"
}
```

Invalid UDIR `adjCode`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid adjCode"
}
```

Split settlement supplied when not allowed:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SplitSettlement not Allowed"
}
```

Partial split-settled refund without split details:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SplitSettlementDetails not Found in Request Body"
}
```

Parallel refund attempt for the same original transaction:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Multiple Parallel Refund Request Raised"
}
```

Refund type not enabled for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ONLINE Refund is not Allowed"
}
```

### Original Transaction and Duplicate Error Examples

Original transaction not found by UPI request id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Original record not found"
}
```

Merchant order exists but no initiated transaction is linked:

```json
{
  "status": "FAILURE",
  "responseCode": "UNINITIATED_REQUEST",
  "responseMessage": "UNINITIATED_REQUEST"
}
```

Repeated `refundRequestId` points to a different original transaction for online refund:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Refund Transaction Id mismatch"
}
```

Repeated offline refund id exists as a different refund type:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Offline Refund Not Found"
}
```

### Authentication, Signing, Encryption, and Access Errors

Missing merchant headers, invalid merchant signature, invalid JWS/JWE verification, unsigned payload rejection in encrypted-only flows, missing raw body, or invalid IP allowlist generally return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not allowlisted for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Invalid `x-timestamp` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired `x-timestamp`:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

JWE/JWS parsing or decryption failures may return `INVALID_DATA`, `UNAUTHORIZED`, or `BAD_REQUEST` depending on which envelope step fails.

### Business and Downstream Failures

Refund360 can return a top-level `SUCCESS` while the refund itself is still pending, deemed, or failed. In that case the business outcome is in `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

Examples:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "refundRequestId": "REFUND12345",
    "refundType": "ONLINE",
    "gatewayTransactionId": "TXN1234567890",
    "gatewayRefundReferenceId": "123456789012",
    "gatewayResponseStatus": "PENDING",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Refund is in pending state"
  }
}
```

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "refundRequestId": "REFUND12345",
    "refundType": "ONLINE",
    "gatewayTransactionId": "TXN1234567890",
    "gatewayRefundReferenceId": "123456789012",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U30",
    "gatewayResponseMessage": "Debit has failed"
  }
}
```

Internal or unexpected failures generally return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Treat `refundRequestId` as immutable. Do not reuse it for a different original transaction, amount, or refund type.
- If the HTTP request times out or the connection fails before a response is received, retry with the same `refundRequestId` and identical payload.
- If the response top-level `status` is `SUCCESS` and `payload.gatewayResponseStatus` is `PENDING` or `DEEMED`, store the identifiers and poll or retry with the same `refundRequestId` after your configured interval. Repeated online and UDIR calls can trigger status refresh where Newton permits it.
- If `payload.gatewayResponseStatus` is `SUCCESS`, mark the refund successful.
- If `payload.gatewayResponseStatus` is `FAILURE`, treat the refund as failed unless Newton operations/support advises otherwise for a specific gateway code.
- Do not retry validation errors such as invalid amount, missing identifiers, invalid split details, or refund amount exceeded without correcting the request.
- Do not immediately retry `Multiple Parallel Refund Request Raised`; wait briefly and retry with the same `refundRequestId` if this was the intended refund.
- For auth, signature, timestamp, or IP allowlist failures, correct headers/envelope/time synchronization before retrying.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:391)
- Route handler and merchant signature verification: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2384)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1066)
- Refund360 transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:582)
- Core request/response transformer: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:791)
- Refund360 request validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:114)
- Field validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:215)
- Shared refund route and type dispatch: [src/Newton/Product/Merchant/Transactions/Refund.hs](../../src/Newton/Product/Merchant/Transactions/Refund.hs:26)
- Online, offline, UDIR, lookup, lock, amount, and split rules: [src/Newton/Product/Merchant/Transactions/RefundHelper.hs](../../src/Newton/Product/Merchant/Transactions/RefundHelper.hs:77)
- Refund response construction and gateway status mapping: [src/Newton/Product/Merchant/Transactions/Transformer.hs](../../src/Newton/Product/Merchant/Transactions/Transformer.hs:24)
- Refund storage lookup/idempotency key: [src/Newton/Storage/QueriesMiddleware/Refund.hs](../../src/Newton/Storage/QueriesMiddleware/Refund.hs:54)
- Standard envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Merchant signature, API allowlist, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:58)
