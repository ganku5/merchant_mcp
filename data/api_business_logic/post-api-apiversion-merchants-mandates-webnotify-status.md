# Web Notify Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/webNotify/status`

## Overview

Web Notify Status is a server-to-server API used to read the stored status of a mandate notification created through `webNotify` or related mandate notification flows.

Use this API after calling Web Notify when the merchant backend needs to reconcile whether Newton has accepted, sent, retried, failed, or completed the notification for a mandate execution cycle. The API is read-only: it does not create a notification, does not retry notification delivery, and does not call NPCI or a PSP for a fresh status check. It returns Newton's stored notification row, plus optional attempt-level details when `upiRequestId` is supplied.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

Web Notify Status helps merchants:

- Reconcile notification state after a `webNotify` call.
- Recover from missed or delayed callbacks by polling Newton's stored notification status.
- Decide whether a mandate execution cycle is ready, still pending, failed, already executed, or not yet initiated.
- Fetch notification identifiers such as `orgMandateId`, notification `merchantRequestId`, notification attempt `gatewayTransactionId`, `seqNumber`, `amount`, and `nextExecution`.
- Distinguish transport/API success from the business status of the mandate notification.

Important distinction: a successful API response means Newton found and returned the notification status. The notification itself can still be `PENDING` or `FAILURE`, represented inside `payload.gatewayResponseStatus`.

## Integration Flow

1. Merchant creates or already has an approved UPI mandate.
2. Merchant calls `webNotify` for an execution cycle and stores the notification `merchantRequestId`.
3. Merchant optionally stores the attempt `upiRequestId` returned by the notification flow.
4. Merchant calls Web Notify Status with the notification `merchantRequestId`.
5. Newton authenticates the merchant, checks merchant API configuration and IP restrictions, validates the payload, and looks up the notification for that merchant.
6. If `upiRequestId` is supplied, Newton also looks up the PAYEE notification attempt for that UPI request id and the resolved mandate id.
7. Merchant decrypts/verifies the response and uses `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` for reconciliation and retry decisions.

Identifier usage:

| Identifier | Meaning |
| --- | --- |
| `merchantRequestId` | Required. Merchant request id used when creating the mandate notification. This is the primary lookup key for this API. |
| `originalMerchantRequestId` | Optional request field. Typically the merchant request id used for original mandate creation. The route validates it when present, but notification lookup is still by `merchantRequestId`. |
| `upiRequestId` | Optional attempt UPI request id. When present, Newton uses it only to fetch the notification attempt; it is returned as `payload.gatewayTransactionId` if found. |
| `orgMandateId` | Newton mandate UPI request id. Not accepted in this request, but returned from the stored notification or mandate. |
| `umn` | UPI mandate number. Not accepted in this request, but returned when the stored notification is linked to a mandate row containing UMN. |

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/webNotify/status
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version segment in the route. Use the version assigned during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | Numeric API version used by response transformation. When `x-api-version > 0`, `payload.originalMerchantRequestId` can be returned. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. Used to resolve and authorize the merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain business payloads. Newton verifies the signature over merchant ids, timestamp, and raw body using the merchant API key and configured signature strategy. |
| `x-timestamp` | Yes | Request timestamp used by middleware freshness validation. |
| `x-sub-merchant-id` | Conditional | Required only when acting as a configured sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required only when acting as a configured sub-merchant. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. Newton checks the first IP in the comma-separated value. |
| `Authorization` | Conditional | Read by authentication middleware for integrations configured to use it. Use only when shared during onboarding. |

### Encryption, Signing, and Envelope

The route accepts `EncRequest MandateNotificationStatusRequest` and returns `EncResponse MandateNotificationStatusResponse`.

The wire request can be one of these envelope forms:

```json
{
  "protected": "base64url-protected-header",
  "encryptedKey": "base64url-encrypted-key",
  "iv": "base64url-iv",
  "cipherText": "base64url-cipher-text",
  "tag": "base64url-auth-tag"
}
```

```json
{
  "payload": "base64url-payload",
  "signature": "base64url-signature",
  "protected": "base64url-protected-header"
}
```

Plain decrypted business JSON is accepted only for integrations explicitly configured for unsigned payloads. For encrypted or signed requests, include `iat` in the decrypted business payload; middleware rejects missing or stale `iat` before product logic runs.

Error responses use the same response envelope mode where possible. The examples below show the underlying decrypted JSON body.

## Request

### Minimum Notification Status Request

Use this for the latest stored status of the notification request.

```json
{
  "merchantRequestId": "NOTIFY202407010001",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Notification Status With Original Mandate Reference

Use `originalMerchantRequestId` as merchant-side context. The current product route does not use it as a lookup key.

```json
{
  "merchantRequestId": "NOTIFY202407010001",
  "originalMerchantRequestId": "MANDATECREATE202407010001",
  "iat": "2026-07-02T10:15:30+05:30",
  "udfParameters": "{\"source\":\"reconciliation\"}"
}
```

### Notification Attempt Status By UPI Request Id

Use this when you also want the attempt UPI request id and sequence number in the response. If no PAYEE attempt is found for this `upiRequestId`, the API still returns the notification status, but `gatewayTransactionId` and `seqNumber` are omitted.

```json
{
  "merchantRequestId": "NOTIFY202407010001",
  "upiRequestId": "UPINOTIFY202407010001",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Must be present and non-empty. | Merchant request id of the Web Notify operation. Newton looks up a PAYEE notification status row by this id and the authenticated merchant. |
| `originalMerchantRequestId` | string | No | No default. | If supplied, must be non-empty. | Merchant request id of the original mandate creation, used as merchant-side context only in this route. It is not used for lookup. |
| `upiRequestId` | string | No | No default. | No request-type validation beyond JSON parsing. The attempt lookup is exact-match and PAYEE-role scoped. | Notification attempt UPI request id. If it matches an attempt for the resolved mandate, the response includes it as `payload.gatewayTransactionId` and includes `payload.seqNumber`. |
| `iat` | string | Conditional | No default. | Required for encrypted or signed envelopes. Middleware validates timestamp freshness. | Issued-at timestamp used by request authentication. |
| `udfParameters` | string | No | No default. Echoed back in the response if supplied. | No explicit validation is applied by this request type. For compatibility with other S2S APIs, send a JSON-object string. | Merchant-defined metadata for correlation. |

### Defaults and Conditional Rules

- There are no product-level default values for request fields.
- `merchantRequestId` is always the notification lookup key.
- `originalMerchantRequestId` is validated when present but is not used to resolve a notification.
- `upiRequestId` does not change the notification lookup. It only attempts to enrich the response with attempt-level fields.
- The API returns only PAYEE notification status rows for the authenticated merchant.
- If the authenticated call is for a valid sub-merchant, Newton validates that the sub-merchant belongs to the parent merchant and returns the sub-merchant ids in the response.

## Response

### Success Response: Notification Pending

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "MERCHANTAPP",
    "merchantRequestId": "NOTIFY202407010001",
    "originalMerchantRequestId": "MANDATECREATE202407010001",
    "umn": "9f6d6a4c5b2e4a8d9c0f1a2b3c4d5e6f@upi",
    "orgMandateId": "MND202407010001",
    "amount": "100.00",
    "nextExecution": "2024-07-05 10:00:00",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your notification is in pending state",
    "gatewayResponseStatus": "PENDING"
  },
  "udfParameters": "{\"source\":\"reconciliation\"}"
}
```

### Success Response: Notification Successful With Attempt

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "MERCHANTAPP",
    "subMerchantId": "SUBMERCHANT001",
    "subMerchantChannelId": "SUBAPP",
    "merchantRequestId": "NOTIFY202407010001",
    "originalMerchantRequestId": "MANDATECREATE202407010001",
    "umn": "9f6d6a4c5b2e4a8d9c0f1a2b3c4d5e6f@upi",
    "gatewayTransactionId": "UPINOTIFY202407010001",
    "orgMandateId": "MND202407010001",
    "amount": "100.00",
    "nextExecution": "2024-07-05 10:00:00",
    "gatewayReferenceId": "401234567890",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your notification is successful",
    "gatewayResponseStatus": "SUCCESS",
    "seqNumber": "2"
  }
}
```

### Success Response: Notification Failed

Gateway or NPCI business failure is returned as a successful API read with failure details inside the payload.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "MERCHANTAPP",
    "merchantRequestId": "NOTIFY202407010001",
    "originalMerchantRequestId": "MANDATECREATE202407010001",
    "orgMandateId": "MND202407010001",
    "amount": "100.00",
    "nextExecution": "2024-07-05 10:00:00",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "FAILURE",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

If Newton has an NPCI `errCode` in the stored notification response, `gatewayResponseCode` is that error code and `gatewayResponseMessage` is mapped from Newton's gateway error-code details. If no error code is stored, Newton falls back to `JPNL` and `FAILURE`.

### Response Field Reference

| Field | Type | Presence | Description |
| --- | --- | --- | --- |
| `status` | string | Always | API transport/business-read status. For found notification rows this is `SUCCESS`, even when the notification itself failed. |
| `responseCode` | string | Always | Top-level API code. Success value is `SUCCESS`. |
| `responseMessage` | string | Always | Top-level API message. Success value is `SUCCESS`. |
| `payload` | object | Success only | Notification status payload. |
| `udfParameters` | string | Optional | Echo of request `udfParameters`, if supplied. |

### Payload Field Reference

| Field | Type | Presence | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Always | Merchant id from the authenticated parent merchant. |
| `merchantChannelId` | string | Always | Merchant channel id from the authenticated parent merchant. |
| `subMerchantId` | string | Conditional | Returned when the request is authenticated for a valid sub-merchant. |
| `subMerchantChannelId` | string | Conditional | Returned when the request is authenticated for a valid sub-merchant. |
| `merchantRequestId` | string | Always | The request `merchantRequestId` used to fetch the notification. |
| `originalMerchantRequestId` | string | Conditional | Original mandate merchant request id from the stored mandate or notification store. Returned only when `x-api-version > 0` and the value is available. |
| `umn` | string | Conditional | UPI mandate number. Returned only when the notification is linked to a mandate row that has UMN. Old or migrated records may omit it. |
| `gatewayTransactionId` | string | Conditional | Notification attempt UPI request id. Returned only when request `upiRequestId` matches a PAYEE notification attempt for this mandate. |
| `orgMandateId` | string | Always on success | Newton mandate UPI request id. Comes from the linked mandate row or from the notification status record. |
| `amount` | string | Always | Notification amount formatted with two decimal places. |
| `nextExecution` | string | Always | Execution timestamp stored on the notification status record, formatted as text. |
| `gatewayReferenceId` | string | Conditional | NPCI/customer reference id extracted from stored `txnInfo.custRef`, when available. |
| `gatewayResponseCode` | string | Always | Derived from stored notification status and stored NPCI response. `00` for `SUCCESS` or `EXECUTED`, `01` for pending-like statuses, otherwise stored `errCode` or `JPNL`. |
| `gatewayResponseMessage` | string | Always | Derived message. Pending-like statuses return `Your notification is in pending state`; successful statuses return `Your notification is successful`; failed statuses use mapped error text or `FAILURE`. |
| `gatewayResponseStatus` | string | Always | Notification business status. Possible returned values include `PENDING`, `SUCCESS`, `EXECUTED`, and `FAILURE`. |
| `seqNumber` | string | Conditional | Notification cycle sequence number. Returned only when request `upiRequestId` is present and a matching attempt is found. |

### Stored Status Mapping

| Stored notification status | Response code | Response message | Response status | Client interpretation |
| --- | --- | --- | --- | --- |
| `PENDING` | `01` | `Your notification is in pending state` | `PENDING` | Notification is not final. Poll later with backoff. |
| `FAILURE_RETRY` | `01` | `Your notification is in pending state` | `PENDING` | Newton considers it retryable or retry-in-progress. Poll later; do not create duplicate notifications unless advised. |
| `UNINITIATED` | `01` | `Your notification is in pending state` | `PENDING` | Notification has not reached a final state. Poll later or inspect the original Web Notify flow. |
| `SUCCESS` | `00` | `Your notification is successful` | `SUCCESS` | Notification completed successfully. Merchant may proceed according to mandate execution rules. |
| `EXECUTED` | `00` | `Your notification is successful` | `EXECUTED` | Notification is associated with an executed cycle. Treat as terminal success for notification reconciliation. |
| `FAILURE` | Stored `errCode`, or `JPNL` | Mapped error text, or `FAILURE` | `FAILURE` | Terminal or operational failure. Inspect the error code and decide whether a fresh Web Notify call is allowed for the cycle. |
| `SKIPPED` | Stored `errCode`, or `JPNL` | Mapped error text, or `FAILURE` | `FAILURE` | Notification was skipped in storage but maps to failure in this endpoint's response helper. |

## Error Handling

Failure responses can be encrypted/signed in the same transport format as success responses. After decryption, common failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId field is empty\""
}
```

Some shared error helpers include `"payload": null`; clients should tolerate either omitted or null payload in errors.

### Validation Failures

Missing or empty `merchantRequestId` fails request validation before lookup.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId field is empty\""
}
```

Empty `originalMerchantRequestId`, when present, fails similarly.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"originalMerchantRequestId field is empty\""
}
```

Client handling: fix the payload and retry with the same intended notification `merchantRequestId`. Do not create a new Web Notify request to fix a status-query validation error.

### Authentication, Signature, Encryption, and Timestamp Failures

Missing merchant headers, invalid merchant credentials, invalid signature/checksum, encrypted payload decode failure, missing `iat` for encrypted/signed payloads, stale timestamps, or failed response encryption can return unauthorized or bad-request style bodies from shared middleware.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

For missing `iat` in encrypted or signed requests, the underlying decrypted error is a bad request from timestamp validation.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "IAT is empty"
}
```

Client handling: check merchant id/channel id, sub-merchant headers, clock sync, `x-timestamp`, `iat`, key id, signing key, and encryption format. Retry only after correcting credentials or the envelope.

### Merchant Configuration, API Disabled, and IP Restriction

If the API is blocked for the merchant, not in the allowed API list for a disabled merchant/sub-merchant mode, or the request IP is not whitelisted, middleware rejects the request before product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

For IP restriction failures, the response uses the shared unauthorized body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: verify onboarding configuration, enabled API names, sub-merchant relationship, and `x-forwarded-for` source IP. Do not retry aggressively; this is configuration-driven.

### Notification Lookup Failure

If Newton cannot find a PAYEE notification status row for the authenticated merchant and `merchantRequestId`, it returns request-not-found.

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

Client handling: confirm that the `merchantRequestId` belongs to the Web Notify operation, not the original mandate creation or execution request. Also confirm that the same merchant/sub-merchant identity is used as in the original Web Notify call.

### Linked Mandate Lookup Failure

When the notification row references a mandate id but the mandate row cannot be found, Newton returns an invalid-notification bad request.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid notification"
}
```

Client handling: treat this as a data inconsistency and contact Newton support with `merchantRequestId`, merchant id, and request timestamp.

### Notification Attempt Not Found

If `upiRequestId` is supplied but no PAYEE attempt is found for that UPI request id and mandate id, the API does not fail. It returns the notification status without these optional fields:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "MERCHANTAPP",
    "merchantRequestId": "NOTIFY202407010001",
    "orgMandateId": "MND202407010001",
    "amount": "100.00",
    "nextExecution": "2024-07-05 10:00:00",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your notification is in pending state",
    "gatewayResponseStatus": "PENDING"
  }
}
```

Client handling: verify the attempt `upiRequestId`. If you only need notification-level status, ignore the missing attempt fields.

### Notification Business Failure

A failed notification is not a failed status API call. It is returned in the payload:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "MERCHANTAPP",
    "merchantRequestId": "NOTIFY202407010001",
    "orgMandateId": "MND202407010001",
    "amount": "100.00",
    "nextExecution": "2024-07-05 10:00:00",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "FAILURE",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

Client handling: branch on `payload.gatewayResponseStatus`, not only top-level `status`.

### Downstream or Gateway Failures

This status API does not call NPCI, PSPs, process tracker, or the mandate notification gateway. Downstream failures from the original Web Notify flow are surfaced from stored `npciResponse` as `payload.gatewayResponseCode`, `payload.gatewayResponseMessage`, and `payload.gatewayResponseStatus`.

Client handling: use this endpoint for observation only. To retry a notification, use the Web Notify flow and mandate execution-cycle rules applicable to your integration.

### Unexpected Errors

Storage, decryption, missing old-record data such as `orgMandateId`, or unexpected runtime errors can produce internal error bodies. The exact envelope and HTTP status can vary by deployment and middleware layer.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with bounded backoff for transient 5xx responses. If the same `merchantRequestId` continues to fail, raise it to Newton support.

## Retry and Idempotency Guidance

- Web Notify Status is read-only and has no idempotency key of its own.
- Repeating the same request with the same `merchantRequestId` is safe.
- For `payload.gatewayResponseStatus = "PENDING"`, poll with exponential backoff. Avoid high-frequency polling; this API reads stored state and will not accelerate downstream processing.
- For `payload.gatewayResponseStatus = "SUCCESS"` or `"EXECUTED"`, treat the notification status as terminal success for reconciliation.
- For `payload.gatewayResponseStatus = "FAILURE"`, do not assume the status API should be retried. Review `gatewayResponseCode` and your mandate cycle rules before creating a new Web Notify request.
- For authentication, configuration, validation, and IP errors, retry only after fixing the request or merchant setup.
- For transient 5xx or transport failures, retry the same status request with bounded exponential backoff and alert if the failure persists.

## Source References

- Route declaration for `POST /merchants/mandates/webNotify/status`: [Core.hs](../../src/Newton/App/Routes/Core.hs:590)
- Route handler, request decoding, signature verification, monitoring key, and product call: [Core.hs](../../src/Newton/App/Routes/Core.hs:3189)
- Request and response API types plus request validation: [Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:329)
- Envelope request/response constructors: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Merchant signature, timestamp, API allowed/blocked, and IP whitelist middleware: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:48)
- Product logic for lookup and response construction: [MerchantMandateV2.hs](../../src/Newton/Product/MerchantMandateV2.hs:361)
- Response mapping for notification status payload: [Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2735)
- Notification lookup by merchant request id: [MandateNotificationStatus.hs](../../src/Newton/Storage/QueriesMiddleware/MandateNotificationStatus.hs:70)
- Attempt lookup by UPI request id and PAYEE role: [MandateNotificationAttempt.hs](../../src/Newton/Storage/QueriesMiddleware/MandateNotificationAttempt.hs:30)
- Stored notification status and enum definitions: [MandateNotificationStatus.hs](../../src/Newton/Types/Storage/MandateNotificationStatus.hs:44)
- Stored attempt type and status enums: [MandateNotificationAttempt.hs](../../src/Newton/Types/Storage/MandateNotificationAttempt.hs:39)
- Shared validation error handling: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Notification gateway response-code mapping: [Utils.hs](../../src/Newton/Utils/Utils.hs:1593)
- Shared success, bad request, and request-not-found response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
