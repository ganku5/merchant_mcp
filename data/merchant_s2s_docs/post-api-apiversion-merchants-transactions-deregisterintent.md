# Deregister Intent API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/deregisterIntent`

## Overview

Deregister Intent is a server-to-server API used to cancel a previously registered UPI payment or mandate intent before the customer completes authorization.

The merchant calls this API with the original `merchantRequestId` used in `registerIntent`. Newton looks up the registered intent for the authenticated merchant or sub-merchant, verifies that the intent can still be cancelled, stores the optional deregistration reason, and marks the intent as expired by writing the current timestamp into the registered intent's validation data.

Use this API when an order is cancelled, the checkout session expires on the merchant side, the customer abandons the flow, or the merchant no longer wants Newton to accept a later UPI authorization for that registered intent.

This API does not call NPCI. It updates Newton's stored intent validation record.

## Business Use Case

Deregister Intent helps merchants:

- Cancel a previously registered UPI intent or mandate intent before authorization.
- Prevent a later UPI app authorization from being matched to an order that the merchant has already cancelled.
- Keep Newton's intent-validation state aligned with merchant checkout expiry or order cancellation.
- Record a client-side cancellation reason for audit and support.
- Scope cancellation to the merchant or sub-merchant that owns the original registered intent.

## Integration Flow

1. Merchant creates an intent by calling `registerIntent`.
2. Merchant presents the UPI intent/QR/mandate authorization journey to the customer.
3. If the merchant order is cancelled or the checkout expires before successful authorization, merchant calls `deregisterIntent` with the same `merchantRequestId`.
4. Newton validates the S2S envelope, merchant signature, API access, source IP where configured, and request body.
5. Newton finds the original intent for the authenticated merchant or sub-merchant.
6. Newton rejects the deregistration if the intent is already expired or if a merchant order already exists in `PENDING` or `SUCCESS`.
7. Newton stores `deregisterReason` when supplied, sets the intent `expiryTimestamp` to the current server time, updates Redis, and returns success.

Important identifiers:

- `merchantRequestId`: The merchant-created id used in the original `registerIntent` request. This is the only business identifier accepted by `deregisterIntent`.
- `merchantId` and `merchantChannelId`: Returned for the authenticated parent merchant.
- `subMerchantId` and `subMerchantChannelId`: Returned only when the request is made in a sub-merchant context.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/deregisterIntent
```

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope. Examples in this guide show decrypted business payloads for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | `application/json` |
| `x-api-version` | Recommended | API version shared during onboarding. The current deregister response shape is not version-dependent. If omitted or invalid, Newton treats it as version `0` internally. |
| `x-merchant-id` | Yes, except for configured sub-merchant-only routing | Parent merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes, except for configured sub-merchant-only routing | Parent merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Conditional | Required when deregistering an intent that belongs to a sub-merchant context. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id`. |
| `x-timestamp` | Yes | Current request timestamp in 13-digit epoch milliseconds. Must be within Newton's freshness window, currently plus/minus 30 minutes. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payload transport. JWS/JWE request modes carry signature verification through the envelope. |
| `x-forwarded-for` | Conditional | Required when the merchant is configured with source-IP allowlisting. The first IP in the header must be whitelisted. |
| `x-request-id` | No | Optional client request id. If omitted, Newton generates one and returns it in `x-requestid`. |
| `x-session-id` | No | Optional client session id. If omitted, Newton uses the request id and returns it in `x-sessionid`. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | URL version segment, for example `v1` or the version shared during onboarding. |

### Authentication and Envelope

Newton accepts the standard `EncRequest` envelope:

- JWE encrypted payload with fields `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed payload with fields `payload`, `signature`, and `protected`.
- Plain JSON business payload only where merchant configuration permits unsigned/plain transport.

For JWE, Newton decrypts the request, expects the decrypted content to be a signed payload, verifies the JWS signature, and then parses the business request. For JWS, Newton verifies the signature and parses the decoded business request. For plain transport, Newton verifies `x-merchant-signature` over merchant ids, timestamp, and the raw request body.

For signed or encrypted requests, send `iat` inside the decrypted business payload. Newton validates `iat` as a 13-digit epoch-milliseconds timestamp within the same freshness window. For plain/unsigned business payloads, `iat` is ignored by the envelope layer.

Responses use the merchant's configured response strategy:

- `JWS`: Newton returns a signed response envelope.
- `JWS_AND_JWE`: Newton returns an encrypted response envelope containing a signed response.
- Other configured/plain strategies: Newton returns the decrypted response JSON with an `X-Response-Signature` response header.

## Request

### Required Minimum

```json
{
  "merchantRequestId": "ORDER12345"
}
```

### With Deregistration Reason and Metadata

```json
{
  "merchantRequestId": "ORDER12345",
  "deregisterReason": "Customer cancelled checkout",
  "iat": "1751457600000",
  "udfParameters": "{\"cartId\":\"CART123\",\"source\":\"web\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | The `merchantRequestId` from the original `registerIntent` call. Must identify an existing registered intent for the authenticated merchant or sub-merchant. |
| `deregisterReason` | string | No | No default. If omitted, no reason is stored. | Optional cancellation reason stored against the original intent record. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp in 13-digit epoch milliseconds. Required by the S2S verification layer for signed/encrypted requests. |
| `udfParameters` | string | No | No default. If omitted, it is omitted from the success response. | JSON-object string for merchant-defined metadata. Echoed in the success response when supplied. |

There are no nested business objects for this API.

## Validation Rules

Newton applies request validation after the S2S envelope is verified and before product logic runs.

| Field | Rule |
| --- | --- |
| `merchantRequestId` | Required. Length must be 1 to 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore. The value must contain at least one letter or number. |
| `deregisterReason` | Optional. When supplied, length must be 1 to 256 characters. |
| `iat` | Nullable in the business type, but required by signed/encrypted S2S verification. When verified, it must be a 13-digit epoch-milliseconds timestamp and within plus/minus 30 minutes of Newton server time. |
| `udfParameters` | Optional. When supplied, it must be a string containing a valid JSON object and must pass Newton's restricted-character validation. Avoid `/`, `$`, `!`, `%`, `~`, backtick, and related punctuation that can be rejected by the validator. |

Business validation:

- The authenticated merchant or sub-merchant must be valid and enabled for this API.
- The source IP must pass the merchant allowlist when `whitelistedIps` is configured.
- The original registered intent must exist for the authenticated merchant/sub-merchant and `merchantRequestId`.
- The original registered intent must not already be expired.
- A merchant order with the same `merchantRequestId` must not already be in `PENDING` or `SUCCESS`.

## Success Response

Successful decrypted business responses use this shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "CHANNEL001",
    "merchantRequestId": "ORDER12345"
  },
  "udfParameters": "{\"cartId\":\"CART123\",\"source\":\"web\"}"
}
```

For a sub-merchant request:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "PARENTMERCHANT001",
    "merchantChannelId": "PARENTCHANNEL001",
    "merchantRequestId": "ORDER12345",
    "subMerchantId": "SUBMERCHANT001",
    "subMerchantChannelId": "SUBCHANNEL001"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when the intent was deregistered. |
| `responseCode` | string | `SUCCESS` for successful deregistration. |
| `responseMessage` | string | `SUCCESS` for successful deregistration. |
| `payload` | object | Business response payload. |
| `udfParameters` | string | Echo of request `udfParameters`, only when supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Parent merchant id from the authenticated request context. |
| `merchantChannelId` | string | Parent merchant channel id from the authenticated request context. |
| `merchantRequestId` | string | Original registered intent id that was deregistered. |
| `subMerchantId` | string | Sub-merchant id, present only when request authentication resolved a sub-merchant. |
| `subMerchantChannelId` | string | Sub-merchant channel id, present only when request authentication resolved a sub-merchant. |

## Failure Responses

Failure responses use the same configured S2S response transport as success responses where possible. After decryption, most failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchant request id regex failed\""
}
```

`payload` is usually omitted because the shared `ErrorResponse` type omits an empty payload. HTTP status varies by layer: validation failures from `validateRequestBody` are commonly returned with HTTP 200 and a failure body; malformed envelope/payload can use HTTP 400; authentication, signature, API access, and IP failures use HTTP 401; product business rejections use HTTP 400; missing stored state or persistence failures can surface as HTTP 500 or as an internal-error body.

### Request Body Validation Failure

Occurs when the decrypted business payload is syntactically valid JSON but fails field validation.

Invalid `merchantRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

Invalid `deregisterReason` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"deregisterReason field length is not between 1 and 256\""
}
```

Malformed `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Client handling: fix the payload, regenerate the S2S signature/envelope and timestamps, then retry.

### Malformed Signed or Encrypted Payload

Occurs when a JWS payload cannot be decoded as the request type, or a JWE decrypts to content Newton cannot parse.

Example decrypted error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantRequestId\" not found"
}
```

Client handling: rebuild the business JSON, then sign/encrypt again. Do not replay the same invalid envelope.

### Timestamp or Freshness Failure

Occurs when `x-timestamp` or signed/encrypted `iat` is missing, malformed, or outside Newton's freshness window.

Invalid timestamp format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Missing `iat` for signed/encrypted requests can surface as invalid data:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Client handling: generate a fresh 13-digit epoch-milliseconds `x-timestamp` and, for JWS/JWE, a fresh `iat`; then regenerate the signature/envelope.

### Authentication, Signature, API Access, or IP Failure

Occurs when merchant headers are missing or invalid, the merchant/sub-merchant cannot be resolved, the JWS signature verification fails, JWE decryption fails, plain-payload `x-merchant-signature` is missing or invalid, the API is blocked/not allowed for the merchant, or source IP allowlisting fails.

Generic unauthorized response:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API not enabled or not allowed:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: fix merchant ids, sub-merchant headers, key id, signing key, encrypted payload, API allowlist, or IP allowlist. Regenerate the full request before retrying.

### Original Registered Intent Not Found

The product logic expects an existing `MerchantValidation` record for the authenticated merchant/sub-merchant and `merchantRequestId`. If no record is found, current code treats this as missing internal state and can surface as an internal-error response.

Example decrypted body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: verify that `merchantRequestId` exactly matches a prior successful `registerIntent` call under the same merchant or sub-merchant. Do not use `gatewayTransactionId`, `orderId`, or transaction ids in this API.

### Intent Already Expired or Already Deregistered

Newton checks the original intent expiry before deregistering. If the intent has already expired, or if a previous `deregisterIntent` call already stamped the expiry timestamp, the API returns:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Intent already expired"
}
```

Client handling: treat this as a terminal state for cancellation. The intent is no longer active from Newton's validation perspective.

### Transaction Already Pending or Successful

Newton checks for a merchant order with the same `merchantRequestId`. If an order exists in `PENDING` or `SUCCESS`, deregistration is rejected:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Transaction is in PENDING/SUCCESS state"
}
```

Client handling: do not retry deregistration. Use normal transaction status/reconciliation flows for that order.

### Persistence or Redis Failure

After business validation passes, Newton updates the stored intent record and writes the updated validation state to Redis. Storage failures, missing required runtime context, key/crypto failures while encrypting the response, or Redis failures can surface as internal errors:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: if the HTTP call failed after Newton may have accepted the request, first check whether a repeat `deregisterIntent` returns `Intent already expired`. That response usually means the original deregistration update succeeded. If the response is still unknown, contact Newton support with `merchantRequestId`, `x-request-id`, merchant id, and timestamp.

## Idempotency and Retry Guidance

`deregisterIntent` is not idempotent in the sense of returning the same success body on repeat calls. The first successful call stamps the original intent as expired. A later call with the same `merchantRequestId` is expected to fail with `BAD_REQUEST` and `Intent already expired`.

Recommended client behavior:

- Send exactly one deregistration request when the merchant decides the intent must no longer be honored.
- On network timeout or unknown response, retry once with a fresh timestamp/signature/envelope.
- If the retry returns `Intent already expired`, treat the cancellation as complete.
- If the retry returns `Transaction is in PENDING/SUCCESS state`, stop cancelling and switch to transaction status handling.
- For validation, auth, timestamp, API access, or IP allowlist failures, fix the integration issue and regenerate the signed/encrypted request before retrying.
- Do not call this API after receiving a successful payment/mandate authorization for the same `merchantRequestId`.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:372)
- Route handler and S2S verification call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2331)
- Request and response types plus validation: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:1387)
- Request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:180), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:292)
- Transformer route and success response construction: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:263), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1309)
- Product/business logic: [src/Newton/Product/Merchant/Transactions/DeregisterIntent.hs](../../src/Newton/Product/Merchant/Transactions/DeregisterIntent.hs:23)
- Expiry and merchant-order checks: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1756), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1770)
- Response payload transformer: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:491)
- Merchant validation storage update: [src/Newton/Storage/QueriesMiddleware/MerchantValidation.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantValidation.hs:127)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Merchant payload verification and JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, timestamp, API allowlist, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Shared error responses: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:169), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:259)
