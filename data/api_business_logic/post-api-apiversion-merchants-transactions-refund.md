# Refund API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/refund`

## Overview

Refund is a server-to-server API used to create an offline refund record against a successful or deemed-successful merchant transaction.

This endpoint is the legacy/offline refund path. It validates the merchant, request signature/envelope, original transaction, refund eligibility, refund amount, refund time window, and duplicate refund request id. When accepted, Newton stores a refund record and returns the original gateway transaction id along with the refund result code. It does not initiate an online refund through refund rails; for online refund initiation use the dedicated `onlineRefund` or `refund360` APIs enabled for that integration.

Payloads use the standard Newton S2S encrypted/signed request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Use this API when the merchant backend needs Newton to record an offline refund against a previous merchant transaction, for example:

- The refund is handled outside the real-time UPI online refund rail.
- The merchant needs Newton to track refunded amount for reconciliation and refund status.
- The merchant wants idempotent refund creation using a merchant-generated refund request id.
- The merchant wants Newton to enforce that cumulative refunds do not exceed the original transaction amount.

Important identifiers:

- `merchantRequestId`: Merchant-generated refund request id. This is the idempotency key for the refund.
- `merchantTransactionId`: Merchant's original transaction/order reference. Newton uses this to find the original merchant order and transaction.
- `gatewayTransactionId`: Newton/UPI id of the original transaction, returned in the response.

## Integration Flow

1. Merchant completes an original payment transaction.
2. Merchant decides to process an offline refund and creates a unique refund request id.
3. Merchant calls `POST /api/{apiVersion}/merchants/transactions/refund`.
4. Newton verifies the request envelope, merchant headers, signature, API access, timestamp, and IP allowlist where configured.
5. Newton validates the request body and finds the original merchant order by `merchantTransactionId`.
6. Newton finds a valid original transaction linked to that order. The transaction must be in a success/deemed-success state.
7. Newton checks refund feature enablement, refund TAT, per-transaction refund lock, and cumulative refund amount.
8. Newton creates the offline refund record, or returns the already-created offline refund when the same refund request id is repeated.
9. Merchant stores `merchantRequestId`, `gatewayTransactionId`, `gatewayResponseCode`, and `gatewayResponseMessage` for reconciliation.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/refund
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment under `/api`. This endpoint does not apply version-specific response branching in the current implementation. Use the version shared during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-merchant-id` | Yes, unless using only sub-merchant headers for an enabled parent lookup | Merchant id assigned by Newton. |
| `x-merchant-channel-id` | Yes, unless using only sub-merchant headers for an enabled parent lookup | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required only for sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Conditional | Required only for sub-merchant integrations. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness except in configured non-production checksum flows. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payloads. Signature is computed from merchant/sub-merchant ids, timestamp, and raw body using the configured merchant API key and signature strategy. |
| `x-request-id` | No | Request correlation id. Newton generates one if omitted and returns it as `x-requestid`. |
| `x-session-id` | No | Session/correlation id. Defaults to `x-request-id` when omitted and is returned as `x-sessionid`. |
| `x-forwarded-for` | Conditional | Required when the merchant has configured `whitelistedIps`; the first IP in this header must be allowlisted. |
| `x-api-version` | No for this route | Some sibling APIs use this header for response behavior. This refund route does not branch on it. |

### Authentication, Signing, and Encryption

The route accepts Newton's standard S2S envelope:

- Plain JSON business payload.
- JWS signed payload.
- JWE encrypted payload containing a signed payload.

For client integrations, use the signed or encrypted envelope configured during onboarding. The decrypted business payload is the JSON shown in this guide.

Envelope body shapes:

```json
{
  "protected": "<jwe protected header>",
  "encryptedKey": "<encrypted key>",
  "iv": "<initialization vector>",
  "cipherText": "<encrypted payload>",
  "tag": "<authentication tag>"
}
```

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

Signed/encrypted payloads are still checked for merchant identity, API access, request IAT, timestamp freshness, and IP restriction where configured.

Responses are returned using the merchant's configured response strategy:

- JWS response when response strategy is `JWS`.
- JWE response when response strategy is `JWS_AND_JWE`.
- Plain business response with `X-Response-Signature` otherwise.

## Request

### Required Minimum

```json
{
  "merchantRequestId": "REFUND12345",
  "refundAmount": "100.00",
  "merchantTransactionId": "ORDER12345"
}
```

### Request With Optional Metadata

```json
{
  "merchantRequestId": "REFUND12346",
  "refundAmount": "25.50",
  "merchantTransactionId": "ORDER12345",
  "iat": "2026-07-02T10:15:30+05:30",
  "udfParameters": {
    "refundReason": "customer_return",
    "ticketId": "TICKET123"
  }
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Unique merchant-generated refund request id and idempotency key. Length must be 1 to 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore. |
| `refundAmount` | string | Yes | No default. | Refund amount. Must be greater than `0.00` and must use exactly two decimal places, for example `100.00`. |
| `merchantTransactionId` | string | Yes | No default. | Merchant's original transaction/order reference. Newton uses this to find the original merchant order, then the linked merchant transaction. Length must be 1 to 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore. |
| `iat` | string | Conditional for signed/encrypted envelope | No default. | Issued-at timestamp used in request freshness validation for signed/encrypted payloads. Plain unsigned payloads do not require this body field. |
| `udfParameters` | object or JSON-object string | No | No default. Returned in the response when supplied. | Merchant-defined metadata. Must be a JSON object or a string containing a JSON object. The value is rejected if it contains disallowed special characters such as `/`, `#`, `-`, `(`, `)`, `*`, `!`, `%`, `~`, or backtick. |

### Defaults and Omitted Field Behavior

This API does not generate a refund request id, refund amount, or original transaction id. There are no request-level defaults for the business fields.

Internally, the offline refund is created with:

- Refund type: `OFFLINE`.
- Refund VPA: not applicable.
- Refund remarks: `"No remarks"`.
- Split settlement details: not accepted on this legacy endpoint; no split fields exist in the request.
- Refund mode: `ONUS` when Newton can find the customer-side transaction, otherwise `OFFUS`. This mode is stored but not returned by this response.
- Initial refund status: normally success with gateway response code `00`; if the environment is configured to create offline refunds as pending, the record starts pending with gateway response code `01`.

## Validation and Processing Rules

### Request Body Validation

Newton validates the decrypted business payload before product processing:

- `merchantRequestId` is mandatory, 1 to 35 characters, and must match the allowed request-id format.
- `merchantTransactionId` is mandatory, 1 to 35 characters, and must match the allowed request-id format.
- `refundAmount` is mandatory, must match `^[0-9]+\\.[0-9][0-9]$`, and must be greater than zero.
- `udfParameters`, when present, must be an object or a stringified object and must pass the configured character restrictions.
- For signed or encrypted envelopes, `iat` must be present and parse as a valid timestamp.

### Merchant and API Access Validation

Before refund logic runs, Newton:

- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`, or resolves the parent merchant from sub-merchant headers where that flow applies.
- Validates that the sub-merchant belongs to the parent merchant when sub-merchant headers are supplied.
- Checks whether this API is blocked for the merchant.
- Checks allowed API names when the merchant or sub-merchant is configured with explicit API allowlisting.
- Checks `allowedRefundTypes`, if configured at merchant, parent merchant, or global configuration. `OFFLINE` must be allowed for this endpoint.
- Checks IP allowlisting when `whitelistedIps` is configured.

### Original Transaction Lookup

For this endpoint, the original transaction is looked up by `merchantTransactionId`.

Newton first finds a merchant order for the current merchant or sub-merchant where:

- Merchant id matches the authenticated merchant context.
- Merchant order request id equals `merchantTransactionId`.

Newton then finds the linked merchant transaction. The transaction must be in one of the valid success/deemed states used by refund processing:

- `SUCCESS`
- `DEEMED`
- `DEEMED_DEBIT`

If no linked successful/deemed transaction is found, the refund is rejected.

### Refund Window

For a new offline refund, Newton validates refund TAT using the original transaction creation time.

The current implementation uses the environment configuration `transactionExpiryForRefund`. If the original transaction is older than the configured number of days, the request fails with `REFUND_TAT_EXPIRED`.

### Duplicate and Idempotency Behavior

`merchantRequestId` is the refund idempotency key.

If a refund with the same `merchantRequestId` already exists for the authenticated merchant or sub-merchant:

- If the existing refund is an offline refund, Newton returns the existing refund details.
- If the existing refund is not an offline refund, Newton rejects the request with an invalid-data error: `Offline Refund Not Found`.

For a new refund, Newton uses a short-lived per-original-transaction lock before validating cumulative refunded amount. If parallel refund requests for the same original transaction cannot acquire the lock, Newton rejects the request with `Multiple Parallel Refund Request Raised`.

### Amount Limits

Newton sums existing refunds for the original transaction and original merchant order. The new `refundAmount` plus already-refunded amount must not exceed the original transaction amount.

If the cumulative amount would exceed the original amount, Newton rejects the request with `INVALID_REFUND_AMOUNT`.

### Offline Refund Status

This endpoint creates an offline refund record. The response's nested gateway fields represent Newton's refund record state, not an online refund rail response.

By configuration:

- Standard behavior: `gatewayResponseCode` is `00`, `gatewayResponseMessage` is `Refund accepted successfully`.
- Pending-offline behavior: `gatewayResponseCode` is `01`, `gatewayResponseMessage` is `Your Transaction is in pending state`.

In both cases, the top-level API response is a transport/business wrapper and is `SUCCESS` when Newton accepted the request.

## Success Response

### Standard Accepted Offline Refund

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12345",
    "transactionAmount": "500.00",
    "refundAmount": "100.00",
    "gatewayTransactionId": "UPI1234567890",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Refund accepted successfully"
  },
  "udfParameters": {
    "refundReason": "customer_return",
    "ticketId": "TICKET123"
  }
}
```

### Accepted Offline Refund Created As Pending

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12345",
    "transactionAmount": "500.00",
    "refundAmount": "100.00",
    "gatewayTransactionId": "UPI1234567890",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your Transaction is in pending state"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. `SUCCESS` means Newton accepted and processed the request. |
| `responseCode` | string | Top-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level response message. Success value is `SUCCESS`. |
| `payload` | object | Refund details. Present on success. |
| `udfParameters` | object or string | Echo of request `udfParameters` when supplied. Omitted when not supplied. |

### `payload` Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Authenticated parent merchant id. |
| `merchantChannelId` | string | Authenticated parent merchant channel id. |
| `subMerchantId` | string | Sub-merchant id. Omitted by this response transformer because the offline refund response sets it to null and null fields are omitted. |
| `subMerchantChannelId` | string | Sub-merchant channel id. Omitted by this response transformer because the offline refund response sets it to null and null fields are omitted. |
| `merchantRequestId` | string | Original transaction/order reference from the original merchant order. This is the request's `merchantTransactionId`, not the refund request id. |
| `transactionAmount` | string | Original transaction amount, formatted with two decimal places. |
| `refundAmount` | string | Refund amount, formatted with two decimal places. |
| `gatewayTransactionId` | string | Original transaction UPI request id. |
| `gatewayResponseCode` | string | Offline refund record response code. `00` means accepted successfully; `01` means pending when configured. |
| `gatewayResponseMessage` | string | Offline refund record response message. |

Note: the response does not currently return the refund request id as a separate payload field. Persist your request `merchantRequestId` with the response for future reconciliation.

## Failure Handling

Failure responses use the configured response envelope where possible. The examples below show the decrypted body.

HTTP status can vary by layer. Several business validation failures are intentionally returned with HTTP 200 and a failure body; authentication and encryption failures generally use HTTP 401; malformed payloads and some concurrency/amount failures use HTTP 400.

Always use the decrypted `status`, `responseCode`, and `responseMessage` to decide client behavior.

### Validation Failure

Invalid business fields are returned as `BAD_REQUEST`. The current validator includes the validation category in the message.

Example: invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Example: invalid `merchantRequestId` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

Client handling: fix the payload and retry with the same refund id only if the previous request did not create a refund. For deterministic validation errors, do not retry unchanged.

### Missing or Invalid `iat`

Signed and encrypted envelopes require a valid `iat`.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Client handling: generate a fresh request timestamp and sign/encrypt the updated payload.

### Authentication or Signature Failure

Missing merchant headers, unknown merchant id/channel id, invalid sub-merchant mapping, missing raw body for signature verification, invalid signature, invalid timestamp, failed JWS verification, failed JWE decryption, or IP allowlist mismatch can fail with:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API allowlist or blocked API failures use:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: do not retry automatically until credentials, envelope keys, timestamp, headers, API enablement, or source IP configuration are corrected.

### Encryption or Signed Payload Parsing Failure

If Newton decrypts or verifies the envelope but cannot parse the inner payload, it returns invalid data.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantTransactionId\" not found"
}
```

Client handling: rebuild the envelope from valid JSON and retry with the same refund id only if the previous request did not reach product processing.

### Offline Refund Not Enabled

If merchant, parent merchant, or global configuration restricts refund types and `OFFLINE` is not allowed:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "OFFLINE Refund is not Allowed"
}
```

Client handling: contact Newton onboarding/support to enable the correct refund type, or use the refund API type enabled for the merchant.

### Original Order Not Found

If `merchantTransactionId` does not match a merchant order for the authenticated merchant/sub-merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_TRANSACTION_ID",
  "responseMessage": "INVALID_TRANSACTION_ID"
}
```

Client handling: verify that `merchantTransactionId` is the original merchant order/reference id, not the refund id or UPI id.

### Original Transaction Not Found or Not Eligible

If the order is found but Newton cannot find a linked original transaction in a success/deemed-success state:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Transaction not found"
}
```

Client handling: check the original transaction status before retrying. Do not refund failed, expired, declined, reversed, or uninitiated transactions through this endpoint.

### Refund Window Expired

If the original transaction is older than the configured refund TAT:

```json
{
  "status": "FAILURE",
  "responseCode": "REFUND_TAT_EXPIRED",
  "responseMessage": "TAT expired for refund"
}
```

Client handling: do not retry unchanged. Use the merchant's exception process if a refund outside the configured window is required.

### Duplicate Refund Id With Non-Offline Refund

If `merchantRequestId` already exists but belongs to a non-offline refund:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Offline Refund Not Found"
}
```

Client handling: use a new refund request id only if this is genuinely a different refund attempt. Do not reuse ids across refund API types.

### Refund Amount Exceeds Original Transaction Amount

If existing refunds plus the new refund amount exceed the original transaction amount:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_REFUND_AMOUNT",
  "responseMessage": "INVALID_REFUND_AMOUNT"
}
```

Client handling: query or reconcile prior refunds and send an amount that keeps cumulative refunds at or below the original transaction amount.

### Parallel Refund Request

If multiple refund requests for the same original transaction are raised concurrently and Newton cannot acquire the refund lock:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Multiple Parallel Refund Request Raised"
}
```

Client handling: retry after a short delay. Use one in-flight refund request per original transaction where possible.

### Internal Error

Unexpected storage/configuration errors can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry only with backoff and alert on repeated failures. If the client timed out after sending a request, first retry with the same `merchantRequestId` to get the idempotent result before creating any new refund id.

## Retry and Idempotency Guidance

- Use a unique `merchantRequestId` for each refund attempt.
- Retry network timeouts and unknown outcomes with the same `merchantRequestId`.
- If the first request created an offline refund, repeating the same request id returns the existing offline refund details.
- Do not reuse the same `merchantRequestId` for a different original transaction, amount, or refund API type.
- Avoid concurrent refunds for the same original transaction. Newton protects cumulative amount validation with a short-lived lock, but client-side serialization gives cleaner outcomes.
- Do not retry unchanged for deterministic validation failures such as invalid amount format, invalid ids, API not enabled, transaction not found, refund TAT expired, or refund amount exceeding the original amount.
- For pending offline refund responses (`gatewayResponseCode: "01"`), store the response and follow the merchant's reconciliation/status process configured for offline refunds.

## Source References

- API route capture: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- Refund route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:385)
- Refund route handler and signature verification: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2367)
- Request/response types and body validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1191)
- Offline refund transformer: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:598)
- Request-to-core mapping and response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:770)
- Core refund route and refund-type dispatch: [src/Newton/Product/Merchant/Transactions/Refund.hs](../../src/Newton/Product/Merchant/Transactions/Refund.hs:26)
- Offline refund product logic: [src/Newton/Product/Merchant/Transactions/RefundHelper.hs](../../src/Newton/Product/Merchant/Transactions/RefundHelper.hs:98)
- Original transaction lookup and idempotency helpers: [src/Newton/Product/Merchant/Transactions/RefundHelper.hs](../../src/Newton/Product/Merchant/Transactions/RefundHelper.hs:177)
- Refund amount and concurrency validation: [src/Newton/Product/Merchant/Transactions/RefundHelper.hs](../../src/Newton/Product/Merchant/Transactions/RefundHelper.hs:275)
- Offline refund record payload: [src/Newton/Utils/Transformers/Transformer7.hs](../../src/Newton/Utils/Transformers/Transformer7.hs:45)
- Core refund response transformer: [src/Newton/Product/Merchant/Transactions/Transformer.hs](../../src/Newton/Product/Merchant/Transactions/Transformer.hs:24)
- Request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:14)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API/IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response signing/encryption behavior: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:60)
- Shared field validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:256)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
