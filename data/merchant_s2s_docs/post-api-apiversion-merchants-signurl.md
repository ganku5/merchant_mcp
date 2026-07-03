# Sign URL API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/signURL`

## Overview

Sign URL is a server-to-server API used when a merchant needs Newton to produce the PSP signature for a UPI intent or QR URL that the merchant has already built.

The merchant sends the complete URL to Newton. Newton validates that the URL is eligible for PSP signing, signs the exact `url` string with the configured PSP ECDSA private key, and returns the detached signature with the merchant identifiers from the authenticated merchant context.

Use this API when the UPI URL must carry a PSP-generated signature before it is shown to the customer, embedded in a QR code, or passed to a UPI app.

## Business Use Case

Sign URL helps merchants:

- Sign a UPI intent or QR URL from the merchant backend without exposing PSP signing keys.
- Ensure the URL belongs to Newton's configured PSP `orgid`.
- Prevent PSP signing for a VPA that is present in Newton's verified VPA directory.
- Receive a signature that can be attached to or distributed with the same URL string that was submitted for signing.

This API does not create or update a transaction, register an intent, call NPCI, or store an idempotency record. It only validates and signs the supplied URL.

## Integration Flow

1. Merchant builds the final UPI URL, including all UPI query parameters that need to be signed.
2. Merchant ensures the URL contains `orgid` equal to Newton's PSP org id shared during onboarding.
3. Merchant calls `signURL` with the URL in the encrypted or signed Newton S2S envelope.
4. Newton authenticates the merchant, checks merchant API/IP configuration, validates the decrypted request body, parses URL query parameters, and rejects URLs that cannot be PSP-signed.
5. Newton signs the exact `url` text supplied in the request.
6. Merchant decrypts/verifies the response and uses `payload.signature` with the same URL string. Do not change, reorder, encode, or append URL parameters after signing unless the signing format you use explicitly includes those changes in a new signature request.

Important values:

- `url`: The exact UPI URL string that Newton signs.
- `orgid`: Query parameter inside `url`. Must match Newton's configured PSP org id.
- `pa`: Query parameter inside `url`. If this payee VPA is found in Newton's verified VPA table, PSP signing is rejected.
- `signature`: PSP-generated signature for the submitted `url`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/signURL
```

Payloads use the standard Newton server-to-server request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. Required for merchant resolution. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. Required for merchant resolution. |
| `x-timestamp` | Request timestamp used by Newton's S2S freshness check. Required by the signature middleware. |
| `x-merchant-signature` | Required for plain JSON payload mode. Signature over merchant id, channel id, optional sub-merchant headers, timestamp, and raw request body. |
| `x-forwarded-for` | Required only when the merchant has `whitelistedIps` configured. Newton checks the first IP in the comma-separated value. |
| `x-request-id` | Optional. Echoed in the `x-requestid` response header; generated if omitted. |
| `x-session-id` | Optional. Echoed in the `x-sessionid` response header; defaults to the request id if omitted. |

Optional sub-merchant headers are included in signature verification when supplied:

| Header | Value |
| --- | --- |
| `x-sub-merchant-id` | Sub-merchant id. |
| `x-sub-merchant-channel-id` | Sub-merchant channel id. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API namespace version in the route, for example `v1` or the version provided during onboarding. |

## Authentication, Encryption, and Signing

The route accepts `EncRequest SignUrlRequest`, so the outer request can be one of the standard S2S envelope forms:

| Envelope mode | JSON shape | Verification behavior |
| --- | --- | --- |
| JWE encrypted payload | `{"protected":"...","encryptedKey":"...","iv":"...","cipherText":"...","tag":"..."}` | Newton decrypts the JWE, expects a signed body inside, verifies the JWS, and extracts the business payload. The decrypted business payload must contain `iat`. |
| JWS signed payload | `{"payload":"...","signature":"...","protected":"..."}` | Newton verifies the JWS and extracts the business payload. The decoded business payload must contain `iat`. |
| Plain JSON payload | Business JSON directly in the request body | Newton verifies `x-merchant-signature` against the raw body and `x-timestamp`. `iat` is optional in this mode. Plain mode availability depends on onboarding and environment configuration. |

Responses use `RespHeaders (EncResponse SignUrlResponse)`. Depending on merchant configuration, Newton returns:

- A JWS response envelope.
- A JWE response envelope containing a signed response.
- A plain business response with `X-Response-Signature`.

In all cases, after decrypting/verifying the response, the business JSON shape is the same as the success and failure examples in this guide.

## Request

### Decrypted Minimum Request

```json
{
  "url": "upi://pay?pa=merchant@upi&pn=Example%20Merchant&am=100.00&cu=INR&orgid=189211"
}
```

### Decrypted Request With `iat` and UDF Metadata

Use this form for JWS/JWE envelope modes and whenever request signing uses an issued-at timestamp inside the business payload.

```json
{
  "url": "upi://pay?pa=merchant@upi&pn=Example%20Merchant&am=100.00&cu=INR&orgid=189211",
  "iat": "2026-07-02T10:30:00+05:30",
  "udfParameters": "{\"orderId\":\"ORD12345\",\"source\":\"checkout\"}"
}
```

### Request for a URL Without `pa`

The code treats `pa` as optional for the verified VPA rejection check. If `pa` is absent and `orgid` matches Newton's PSP org id, Newton can still sign the exact URL.

```json
{
  "url": "upi://pay?pn=Example%20Merchant&am=100.00&cu=INR&orgid=189211",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

### Request Variants

There is only one business request type for this endpoint. The meaningful variants are:

- Plain business payload with only `url`.
- Business payload with `url` and `iat` for signed/encrypted envelope modes.
- Optional `udfParameters`, which is validated and echoed in successful responses.
- URL with `pa`, where Newton additionally checks whether the payee VPA is a verified VPA.
- URL without `pa`, where only the `orgid` eligibility check applies.

## Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `url` | string | Yes | No default. | Must be non-empty. Newton parses the query string by splitting after `?` and then on `&` and `=`. The `orgid` query parameter must equal Newton's configured PSP org id. If `pa` is present and is found in the verified VPA table, the request is rejected. | Exact UPI URL string to sign. Newton signs this exact text. |
| `iat` | string | Conditional | No default. | Required when the outer request is JWS or JWE because the middleware validates `iat` for non-plain payloads. Optional for plain JSON payload mode. Must pass Newton's timestamp freshness validation when present. | Issued-at timestamp for signed/encrypted request freshness checks. |
| `udfParameters` | string | No | Omitted from response when not supplied. | Must be a string containing a JSON object. The text must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. | Merchant-defined metadata. Echoed unchanged in successful decrypted responses. |

### URL Query Parameter Rules

| Query parameter in `url` | Required | Rule | Failure when invalid |
| --- | --- | --- | --- |
| `orgid` | Yes for a successful PSP signature | Must exactly equal Newton's configured PSP org id. Missing `orgid` is treated as an empty value and fails the same check. | `INVALID_DATA`, `orgId must be same as psp's orgId`. |
| `pa` | No | If present, Newton looks it up in the verified VPA table. If found, PSP signing is rejected. | `INVALID_DATA`, `PSP cannot sign for verified merchant`. |

No amount, currency, VPA format, QR static/dynamic mode, or transaction-state validation is performed by this endpoint. Validate the rest of the UPI URL in your own system or use the separate Validate URL flow where applicable.

## Success Response

### Decrypted Business Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "udfParameters": "{\"orderId\":\"ORD12345\",\"source\":\"checkout\"}",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "WEB",
    "signature": "MEUCIQDxExampleSignatureValueAiEAExampleSignatureValue"
  }
}
```

If `udfParameters` was omitted from the request, it is omitted from the decrypted response:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "WEB",
    "signature": "MEUCIQDxExampleSignatureValueAiEAExampleSignatureValue"
  }
}
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for a successful signing operation. |
| `responseCode` | string | `SUCCESS` for success. |
| `responseMessage` | string | `SUCCESS` for success. |
| `udfParameters` | string | Present only when supplied in the request. Echoed unchanged. |
| `payload` | object | Business payload containing merchant identifiers and signature. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record, not from the request body. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `signature` | string | PSP ECDSA signature generated over the exact `url` string in the request. |

### Response Headers

| Header | Description |
| --- | --- |
| `x-requestid` | Request id from `x-request-id`, or Newton-generated id if omitted. |
| `x-sessionid` | Session id from `x-session-id`, or the request id if omitted. |
| `X-Response-Signature` | Present in plain response mode. In JWS/JWE response modes, the response body itself is signed/encrypted instead. |

## Error Handling

Failure responses can be returned as plain error JSON, signed response, or encrypted response depending on where the failure occurs and the merchant envelope configuration. After decrypting/verifying when applicable, failures use Newton's standard error fields:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"url field is empty\""
}
```

HTTP status can vary by layer. Several business-rule failures are intentionally thrown with HTTP 200 and `status: "FAILURE"` in the decrypted JSON. Always handle the decrypted `status`, `responseCode`, and `responseMessage`; do not rely only on HTTP status.

### Validation Failures

Empty `url`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"url field is empty\""
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

- Do not retry unchanged validation failures.
- Ensure `url` is a non-empty final URL string.
- Send `udfParameters` only as a JSON-object string, for example `"{\"orderId\":\"ORD12345\"}"`.

### URL Eligibility Failures

Missing or mismatched `orgid`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "orgId must be same as psp's orgId"
}
```

Payee VPA is a verified VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "PSP cannot sign for verified merchant"
}
```

Client handling:

- Rebuild the URL with the PSP org id provided during onboarding.
- Do not call Sign URL for verified merchant VPAs; use the integration path configured for that verified merchant.
- Keep query parameter names exactly `orgid` and `pa` in lowercase because the code looks up those exact names.

### Authentication, Signature, and Encryption Failures

Missing merchant headers, missing timestamp/raw body, missing or invalid `x-merchant-signature`, invalid JWS, failed JWE decryption, invalid key id, or stale timestamps can return an authorization failure such as:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Malformed encrypted or signed payloads can also return invalid-data parse errors, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

Client handling:

- Verify `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, and `x-merchant-signature` are generated for the exact raw request body sent on the wire.
- For JWS/JWE, include `iat` in the decrypted business payload.
- Use the correct merchant keys and `kid` values configured for the selected envelope mode.
- Retry only after correcting credentials, key ids, timestamp skew, or envelope construction.

### Merchant Configuration, API Disabled, and IP Restriction Failures

If `signUrl` is blocked or not allowed for the merchant configuration, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If the merchant has `whitelistedIps` configured and the first IP in `x-forwarded-for` is missing or not in the allowlist, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling:

- Confirm the merchant is enabled for `signUrl`.
- Confirm the request is sent from an allowlisted IP and that proxies preserve `x-forwarded-for`.
- Do not retry rapidly; this is configuration or routing, not a transient business failure.

### Lookup Failures

Merchant or key lookup failures happen before signing. The exact message can vary by deployment and helper, but decrypted bodies typically use one of these shapes:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Merchant details"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling:

- Check merchant id/channel id and key ids against onboarding configuration.
- Escalate to Newton if the values are correct but lookup continues to fail.

### Downstream and Unexpected Failures

This endpoint does not call NPCI or any external downstream service. The main unexpected failure paths are internal key/configuration problems or ECDSA signing failures:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Retry with backoff for internal errors.
- Keep the same `url` when retrying if the intended signed URL has not changed.
- Escalate with `x-request-id`, timestamp, merchant id, and the decrypted failure body if the error persists.

## Retry and Idempotency Guidance

Sign URL is deterministic from the client's perspective only if the exact `url` string and Newton signing key remain the same. The endpoint does not store an idempotency key or create a transaction record.

- Safe to retry: network timeout, HTTP 5xx, `INTERNAL_SERVER_ERROR`, or no response received.
- Retry with backoff and jitter. Keep retry windows short because UPI URLs may include time-sensitive parameters.
- Do not retry unchanged: validation failures, `orgid` mismatch, verified VPA rejection, auth failures, API disabled, or IP restriction failures.
- If you regenerate the URL, call Sign URL again and use only the signature returned for that exact regenerated URL.
- Do not treat repeated successful responses as duplicate business transactions; this API has no transaction side effect.

## Source References

- API route prefix and `{apiVersion}` capture: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- Sign URL route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:421)
- Route handler, request extraction, signature middleware, and product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2456)
- Request and response types plus field validation: [src/Newton/Types/API/ServerToServer/Account.hs](../../src/Newton/Types/API/ServerToServer/Account.hs:649)
- Product logic for URL parsing, verified VPA rejection, org id check, signing, and merchant response mapping call: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:925)
- Response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1795)
- URL query parser: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:3899)
- PSP ECDSA signing helper: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:281)
- Request body validation helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- `url` and `udfParameters` validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275)
- S2S request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:72)
- Merchant signature verification, API enablement, timestamp, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response envelope and headers: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:28), [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:73)
- Standard success and error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
