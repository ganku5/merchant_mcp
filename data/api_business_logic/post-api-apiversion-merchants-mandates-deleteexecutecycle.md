# Delete Execute Cycle API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/deleteExecuteCycle`

## Overview

Delete Execute Cycle is a server-to-server UPI mandate API used to cancel one or more merchant-created mandate execution notifications before they are processed further.

The merchant identifies the original mandate using the mandate creation `merchantRequestId`, then sends the execution notification `merchantRequestId` values that should be skipped. Newton marks each matching PAYEE-side notification as `SKIPPED` and returns the skipped notification details.

Use this API when an upcoming mandate debit should no longer be executed, for example when the customer cancels the order, the merchant voids an installment, or an execution notification was created for the wrong business cycle.

## Business Use Case

Delete Execute Cycle helps merchants:

- Cancel pending mandate execution notifications without revoking the mandate itself.
- Skip one or more scheduled debit cycles for an active mandate.
- Make repeated delete calls safely after a timeout, because already `SKIPPED` notifications are accepted.
- Reconcile which notification rows were skipped by merchant request id, amount, sequence number, and execution status.

This API does not revoke, pause, or update the mandate. It only changes matching mandate notification statuses to `SKIPPED`.

## Integration Flow

1. Merchant creates a UPI mandate through the mandate creation flow and stores the mandate creation `merchantRequestId`.
2. Merchant creates or receives one or more mandate execution notifications, each with its own notification `merchantRequestId`.
3. Merchant decides that those notified execution cycles should not proceed.
4. Merchant calls `deleteExecuteCycle` with:
   - `originalMerchantRequestId`: the mandate creation `merchantRequestId`.
   - `merchantRequestIds`: the notification `merchantRequestId` values to skip.
5. Newton authenticates and decrypts the S2S request, validates the decrypted payload, and loads the merchant from the request context.
6. Newton looks up the mandate for the merchant and `originalMerchantRequestId`.
7. Newton updates each matching PAYEE notification whose current status is `PENDING`, `FAILURE_RETRY`, `SUCCESS`, or `SKIPPED` to `SKIPPED`.
8. Newton returns the updated notification records in `notificationDetials`.

Important identifiers:

| Identifier | Meaning |
| --- | --- |
| `originalMerchantRequestId` | Merchant request id used when the original mandate was created. This identifies the mandate. |
| `merchantRequestIds[]` | Merchant request ids of the mandate execution notifications to skip. These are not the mandate creation id. |
| `seqNumber` | Mandate execution sequence number returned for each skipped notification. |

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/deleteExecuteCycle
```

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope. The JSON examples below show the decrypted business payload for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant, for example `v1` or the value shared during onboarding. The route captures it but this handler does not branch on it. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-merchant-id` | Yes | Merchant id used to resolve the authenticated merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id used with `x-merchant-id`. |
| `x-sub-merchant-id` | Conditional | Required only for enabled sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Conditional | Required only for enabled sub-merchant integrations. |
| `x-timestamp` | Yes | Request timestamp used for freshness checks. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain S2S payloads. For signed or encrypted payloads, JWS/JWE validation is used instead. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured; the first IP in the header must be allow-listed. |
| `x-request-id` | No | Optional client request id for tracing. Newton generates one when omitted. |
| `x-session-id` | No | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

### Authentication, Encryption, and Signing

Newton accepts the standard `EncRequest` transport shapes:

- `JWE`: encrypted request body with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- `JWS`: signed request body with `payload`, `signature`, and `protected`.
- Plain JSON payload in non-production or specially configured flows.

For encrypted requests, Newton decrypts the JWE with the PSP private key, expects the decrypted content to be a JWS body, verifies the JWS using the merchant key, and then parses the business payload. Responses are returned using the configured encrypted or signed response envelope for the merchant. After decryption, the success and error examples below are the underlying JSON shapes.

For signed or encrypted payloads, the decrypted request body must include `iat`; Newton validates it as a timestamp before signature verification. For plain payloads, `iat` is not required by the middleware.

Merchant authorization checks include:

- Merchant and optional sub-merchant lookup from headers.
- API blocked/allowed configuration checks.
- Signature or JWS/JWE verification.
- IP allow-list check when configured.
- Timestamp freshness check.

## Request

### Minimum Useful Request

```json
{
  "originalMerchantRequestId": "MANDATECREATE001",
  "merchantRequestIds": [
    "EXECYCLE001"
  ],
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Batch Delete Request

```json
{
  "originalMerchantRequestId": "MANDATECREATE001",
  "merchantRequestIds": [
    "EXECYCLE001",
    "EXECYCLE002",
    "EXECYCLE003"
  ],
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Request With UDF Parameters

`udfParameters` must be a JSON object encoded as a string.

```json
{
  "originalMerchantRequestId": "MANDATECREATE001",
  "merchantRequestIds": [
    "EXECYCLE001"
  ],
  "udfParameters": "{\"cancelReason\":\"ORDER_CANCELLED\",\"ticketId\":\"TKT12345\"}",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Idempotent Retry Request

Use the same payload when retrying after a timeout or network failure. If the notifications were already updated to `SKIPPED`, they still match the allowed status list and the retry can return success.

```json
{
  "originalMerchantRequestId": "MANDATECREATE001",
  "merchantRequestIds": [
    "EXECYCLE001",
    "EXECYCLE002"
  ],
  "iat": "2026-07-02T10:16:30+05:30"
}
```

### Empty List Behavior

The Haskell type and validation currently allow an empty `merchantRequestIds` array. In that case Newton still validates and looks up the original mandate, but updates no notifications and returns `notificationDetials: []`.

Do not use an empty list for a real delete request; send at least one notification merchant request id.

```json
{
  "originalMerchantRequestId": "MANDATECREATE001",
  "merchantRequestIds": [],
  "iat": "2026-07-02T10:15:30+05:30"
}
```

## Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `originalMerchantRequestId` | string | Yes for this endpoint | No default. If omitted, this route cannot identify the mandate and returns a bad request. | 1 to 35 characters. Must match `^[-._]*([a-zA-Z0-9][-._]*)+$`. | Merchant request id from the original mandate creation request. |
| `merchantRequestIds` | array of strings | Yes | No default. Empty array is accepted by code but performs no updates. | Each value must satisfy the same merchant request id validation: 1 to 35 characters and `^[-._]*([a-zA-Z0-9][-._]*)+$`. | Merchant request ids of the execution notifications to mark `SKIPPED`. |
| `udfParameters` | string | No | Omitted from the success response when not supplied. | Must be a string containing a valid JSON object. The string must not contain characters rejected by ``^[^/$-*!%~`]+$``. | Merchant-defined metadata echoed in the success response. |
| `iat` | string | Conditional | No default. Required for signed or encrypted request payloads. | Validated as a timestamp by the signing middleware for JWS/JWE requests. | Issued-at timestamp used for freshness and signature/envelope validation. |

## Notification Eligibility Rules

Every `merchantRequestIds[]` value is processed against the mandate found by `originalMerchantRequestId`.

A notification can be skipped only when all of these are true:

- It belongs to the same mandate.
- It has PAYEE role.
- Its `merchantRequestId` equals one of the requested `merchantRequestIds[]` values.
- Its current status is one of `PENDING`, `FAILURE_RETRY`, `SUCCESS`, or `SKIPPED`.

Statuses defined in storage include `PENDING`, `SUCCESS`, `FAILURE`, `FAILURE_RETRY`, `UNINITIATED`, `EXECUTED`, `EXECUTE_PENDING`, and `SKIPPED`. This API only updates the allowed subset above.

If a requested notification is missing, belongs to another mandate or merchant, has PAYER role, or is in an ineligible status such as `EXECUTED`, `EXECUTE_PENDING`, `FAILURE`, or `UNINITIATED`, the update can fail the request.

## Success Response

### Single Notification

```json
{
  "status": "SUCCESS",
  "merchantId": "MERCHANT001",
  "merchantChannelId": "APP",
  "notificationDetials": [
    {
      "merchantRequestId": "EXECYCLE001",
      "amount": 100.5,
      "seqNumber": "4",
      "executeCycleStatus": "SKIPPED"
    }
  ]
}
```

### Batch Notification

```json
{
  "status": "SUCCESS",
  "merchantId": "MERCHANT001",
  "merchantChannelId": "APP",
  "notificationDetials": [
    {
      "merchantRequestId": "EXECYCLE001",
      "amount": 100.5,
      "seqNumber": "4",
      "executeCycleStatus": "SKIPPED"
    },
    {
      "merchantRequestId": "EXECYCLE002",
      "amount": 250,
      "seqNumber": "5",
      "executeCycleStatus": "SKIPPED"
    }
  ],
  "udfParameters": "{\"cancelReason\":\"ORDER_CANCELLED\",\"ticketId\":\"TKT12345\"}"
}
```

### Empty List Response

```json
{
  "status": "SUCCESS",
  "merchantId": "MERCHANT001",
  "merchantChannelId": "APP",
  "notificationDetials": []
}
```

### Response Field Reference

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `status` | string | Yes | Success status. The success response sets this to `SUCCESS`. |
| `merchantId` | string | Yes | Merchant id from Newton's merchant configuration. |
| `merchantChannelId` | string | Yes | Merchant channel id from Newton's merchant configuration. |
| `notificationDetials` | array of objects | Yes | Updated notifications. The field name is spelled `notificationDetials` in the API response. |
| `udfParameters` | string | No | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### `notificationDetials[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | Notification merchant request id that was updated. |
| `amount` | number | Yes | Notification amount stored by Newton. Returned as a JSON number. |
| `seqNumber` | string | Yes | Mandate execution sequence number converted to a string. |
| `executeCycleStatus` | string | Yes | Status after the update. Successful delete calls return `SKIPPED` for updated rows. |

## Error Handling

Failure responses may be returned inside the configured encrypted/signed envelope or directly as an error response depending on the layer that rejects the request. After decryption, Newton error bodies generally use:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "human readable error",
  "payload": null
}
```

`payload` is omitted when it is `null` in many serialized responses.

### Validation Failures

Validation failures in the product route use HTTP 200 with a decrypted failure body whose `responseCode` is `BAD_REQUEST`.

Invalid `originalMerchantRequestId` or `merchantRequestIds[]` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchant request id regex failed\""
}
```

Missing `originalMerchantRequestId` reaches mandate lookup and returns:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "originalMerchantRequestId or upiRequestId or umn is mandatory"
}
```

Invalid `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Client handling:

- Treat `BAD_REQUEST` as non-retryable until the payload is corrected.
- Validate merchant request ids locally before sending.
- Encode `udfParameters` as a JSON object string, not as a nested object.

### Authentication, Signature, and Encryption Failures

Missing merchant headers, invalid merchant credentials, JWS signature mismatch, JWE decryption failure, missing or invalid key id, missing `iat` for signed/encrypted requests, invalid timestamp, and invalid `x-merchant-signature` can return HTTP 400 or 401 depending on the failing layer.

Common decrypted response shapes:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Malformed signed or encrypted payloads can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

Client handling:

- Do not retry unchanged requests indefinitely.
- Verify `x-merchant-id`, `x-merchant-channel-id`, key ids, signing key, encryption key, and timestamp clock sync.
- For JWE, ensure the encrypted content is a JWS body, not the raw business payload.

### Merchant Configuration, API Disabled, and IP Restriction

If the merchant or sub-merchant is not allowed to call this API, or the API is blocked for the merchant, Newton returns HTTP 401 with:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If IP allow-listing is configured and the first IP in `x-forwarded-for` is missing or not allow-listed, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling:

- Confirm the merchant is enabled for mandate APIs and specifically for `deleteExecuteCycle`.
- Send requests from an allow-listed egress IP when IP restrictions are configured.
- Include sub-merchant headers only for onboarded sub-merchant flows.

### Mandate Lookup Failure

If no mandate exists for the authenticated merchant and `originalMerchantRequestId`, Newton returns HTTP 200 with:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate not found"
}
```

Client handling:

- Check that `originalMerchantRequestId` is the mandate creation request id, not an execution notification id.
- Ensure the request uses the same merchant and channel that created the mandate.
- Do not retry without correcting the identifier.

### Notification Lookup or State Failure

If any requested notification cannot be updated, the storage helper raises an internal error response. Realistic causes include:

- The notification `merchantRequestId` does not exist.
- The notification belongs to a different mandate.
- The notification is not a PAYEE notification.
- The notification is already executed or in a status outside `PENDING`, `FAILURE_RETRY`, `SUCCESS`, or `SKIPPED`.

Typical decrypted shape:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Reconcile the notification through the execute-cycle status or notification-status API before retrying.
- Remove ineligible or unknown notification ids from the batch.
- If a batch partially updated before a later item failed, retrying the same batch is safe for already skipped rows, but the ineligible row will continue to fail.

### Downstream, Database, and Unexpected Failures

This API does not call NPCI or a payment gateway to skip the execution cycle; it updates Newton notification state. Therefore gateway/NPCI timeouts are not expected for the normal delete path.

Database, key-store, encryption, response-signing, Redis/secondary-index, or unexpected application failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Retry with the same `originalMerchantRequestId` and `merchantRequestIds` after a short backoff.
- If the retry returns success, use the returned `notificationDetials` as the source of truth.
- If failures persist, query the notification status and contact Newton support with `x-request-id`, merchant ids, `originalMerchantRequestId`, and the notification ids.

## Retry and Idempotency Guidance

This API is effectively idempotent for successful deletes because `SKIPPED` is included in the allowed source statuses. Repeating the same request after success should return the same notifications with `executeCycleStatus: "SKIPPED"`.

Recommended client behavior:

- Use stable notification `merchantRequestId` values. Do not generate new ids for retries.
- Retry transport timeouts, HTTP 5xx, and `INTERNAL_SERVER_ERROR` with the same payload and a fresh `iat`.
- Do not retry validation, auth, API-disabled, or mandate-not-found failures without correcting the request or configuration.
- For batch calls, remember that updates are performed sequentially. If a later item fails, earlier items may already be `SKIPPED`; retrying the same batch is safe for those earlier items, but the failing item must be investigated.
- Store the successful response, especially `merchantRequestId`, `seqNumber`, `amount`, and `executeCycleStatus`, for reconciliation.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:582)
- Route handler, request decryption, signature verification, and product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3117)
- Request and response API types: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:830)
- Request validation instance: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:851)
- Product logic: [src/Newton/Product/MerchantMandateV2.hs](../../src/Newton/Product/MerchantMandateV2.hs:352)
- Mandate lookup and missing-id behavior: [src/Newton/Storage/QueriesMiddleware/Mandate.hs](../../src/Newton/Storage/QueriesMiddleware/Mandate.hs:198)
- Notification update helper: [src/Newton/Storage/QueriesMiddleware/MandateNotificationStatus.hs](../../src/Newton/Storage/QueriesMiddleware/MandateNotificationStatus.hs:447)
- Notification update predicate and allowed statuses: [src/Newton/Storage/Queries/MandateNotificationStatus.hs](../../src/Newton/Storage/Queries/MandateNotificationStatus.hs:249)
- Notification status enum: [src/Newton/Types/Storage/MandateNotificationStatus.hs](../../src/Newton/Types/Storage/MandateNotificationStatus.hs:86)
- Response mapping: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2057) and [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2628)
- S2S envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API enablement, IP, and timestamp checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:48)
- Common validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275) and [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:292)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
