# Validate URL API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/validateURL`

## Overview

Validate URL is a server-to-server API used when a merchant needs Newton to verify the signature attached to a UPI intent or QR URL.

The merchant sends the complete URL, including its `sign` query parameter. Newton authenticates the merchant, validates the request body, decides whether the URL should be verified with a PSP public key or a verified-merchant public key, and returns `payload.valid` as `true` or `false`.

Use this API when the merchant backend has received, generated, scanned, or persisted a signed UPI URL and needs a server-side signature check before trusting or forwarding that URL.

## Business Use Case

Validate URL helps merchants:

- Verify that a signed UPI intent or QR URL has not been modified after signing.
- Validate PSP-signed URLs by using the PSP public key mapped to the URL's `orgid`.
- Validate verified-merchant signed URLs by using the public key configured on the verified VPA record.
- Separate URL signature validity from transaction creation, collection, status, or reconciliation flows.
- Avoid exposing PSP or merchant public-key lookup details to client applications.

This API does not create or update a transaction, register an intent, call transaction status, or store an idempotency record. It only validates the URL signature and returns a boolean result.

## Integration Flow

1. Merchant obtains or builds the complete signed UPI URL.
2. Merchant ensures the URL contains all query parameters exactly as signed, including the literal `&sign=` segment.
3. Merchant calls `validateURL` with the URL in the Newton S2S request envelope.
4. Newton authenticates the merchant and checks merchant API, timestamp, signature, and IP configuration.
5. Newton validates the decrypted request body.
6. Newton parses query parameters from `url` and selects the verification key from PSP keys or verified VPA configuration.
7. Newton verifies the signature against the exact URL text before `&sign=`.
8. Merchant decrypts/verifies the response and reads `payload.valid`.

Important values:

- `url`: The exact UPI URL string to verify.
- `sign`: Query parameter inside `url`. The implementation expects it as a literal `&sign=` delimiter.
- `orgid`: Query parameter inside `url`. A non-zero numeric value can route verification to PSP key lookup.
- `mc`: Query parameter inside `url`. A non-zero numeric value can route verification to verified-merchant key lookup.
- `pa`: Query parameter inside `url`. Required for merchant-key verification because Newton uses it to find the verified VPA record.
- `valid`: Boolean signature result. `false` means the URL was parsed and a key was found, but ECDSA verification failed.

## Endpoint

```http
POST /api/{apiVersion}/merchants/validateURL
```

Payloads use the standard Newton server-to-server request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. Required for merchant resolution. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. Required for merchant resolution. |
| `x-timestamp` | Request timestamp in epoch milliseconds. Required by the signature middleware and must be within the accepted freshness window. |
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

The route accepts `EncRequest ValidateUrlRequest`, so the outer request can be one of the standard S2S envelope forms:

| Envelope mode | JSON shape | Verification behavior |
| --- | --- | --- |
| JWE encrypted payload | `{"protected":"...","encryptedKey":"...","iv":"...","cipherText":"...","tag":"..."}` | Newton decrypts the JWE, expects a signed body inside, verifies the JWS, and extracts the business payload. The decrypted business payload must contain `iat`. |
| JWS signed payload | `{"payload":"...","signature":"...","protected":"..."}` | Newton verifies the JWS and extracts the business payload. The decoded business payload must contain `iat`. |
| Plain JSON payload | Business JSON directly in the request body | Newton verifies `x-merchant-signature` against the raw body and `x-timestamp`. `iat` is optional in this mode. Plain mode availability depends on onboarding and environment configuration. |

Responses use `RespHeaders (EncResponse ValidateUrlResponse)`. Depending on merchant configuration, Newton returns:

- A JWS response envelope.
- A JWE response envelope containing a signed response.
- A plain business response with `X-Response-Signature`.

In all cases, after decrypting/verifying the response, the business JSON shape is the same as the success and failure examples in this guide.

## Request

### Decrypted Minimum Request

```json
{
  "url": "upi://pay?pa=merchant@upi&pn=Example%20Merchant&am=100.00&cu=INR&orgid=189211&sign=MEUCIQD2b7xR9QzYxQ1H4nL2p8r6s0u3v5w7y9zA1B2C3D4E5F6G7AIgG8H9J0K1L2M3N4P5Q6R7S8T9U0V1W2X3Y4Z5a6b7c8="
}
```

### Decrypted Request With `iat` and UDF Metadata

Use this form for JWS/JWE envelope modes and whenever request signing uses an issued-at timestamp inside the business payload.

```json
{
  "url": "upi://pay?pa=merchant@upi&pn=Example%20Merchant&am=100.00&cu=INR&orgid=189211&sign=MEUCIQD2b7xR9QzYxQ1H4nL2p8r6s0u3v5w7y9zA1B2C3D4E5F6G7AIgG8H9J0K1L2M3N4P5Q6R7S8T9U0V1W2X3Y4Z5a6b7c8=",
  "iat": "1782976800000",
  "udfParameters": "{\"orderId\":\"ORD12345\",\"source\":\"checkout\"}"
}
```

### Merchant-Key Verification Request

When `orgid` is absent, zero, or non-numeric and `mc` is a non-zero number, Newton verifies with the public key on the verified VPA record for `pa`.

```json
{
  "url": "upi://pay?pa=store@upi&pn=Example%20Store&am=100.00&cu=INR&mc=5411&sign=MEUCIQD2b7xR9QzYxQ1H4nL2p8r6s0u3v5w7y9zA1B2C3D4E5F6G7AIgG8H9J0K1L2M3N4P5Q6R7S8T9U0V1W2X3Y4Z5a6b7c8=",
  "iat": "1782976800000"
}
```

### Request Variants

There is only one business request type for this endpoint. The meaningful variants are:

- Plain business payload with only `url`.
- Business payload with `url` and `iat` for signed/encrypted envelope modes.
- Optional `udfParameters`, which is validated and echoed in successful responses.
- PSP-key verification, selected by a non-zero numeric `orgid` with `mc` absent, zero, or non-numeric.
- Merchant-key verification, selected by a non-zero numeric `mc` with `orgid` absent, zero, or non-numeric.
- Mixed `orgid` and `mc`, where Newton uses the verified VPA merchant key when `pa` is found, otherwise the PSP key for `orgid`.

## Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `url` | string | Yes | No default. | Must be non-empty. Newton parses query parameters by splitting after the first `?`, then on `&`, then on the first `=`. Parameter names are case-sensitive and are not URL-decoded before lookup. The signature verifier expects a literal `&sign=` delimiter. | Exact signed UPI URL string to validate. |
| `iat` | string | Conditional | No default. | Required when the outer request is JWS or JWE because the middleware validates `iat` for non-plain payloads. Optional for plain JSON payload mode. Must be a 13-digit epoch-milliseconds timestamp within Newton's freshness window when present. | Issued-at timestamp for signed/encrypted request freshness checks. |
| `udfParameters` | string | No | Omitted from response when not supplied. | Must be a string containing a JSON object. The text must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. | Merchant-defined metadata. Echoed unchanged in successful decrypted responses. |

There are no nested request objects for this API.

## URL Query Parameter Rules

| Query parameter in `url` | Required | Rule | Effect |
| --- | --- | --- | --- |
| `sign` | Yes for a usable validation result | The implementation splits the original URL on literal `&sign=` and verifies the part before it against the Base64 DER ECDSA signature after it. Keep `sign` as the final query parameter. | Missing `&sign=` can fail before a boolean result. Invalid signature bytes return `valid: false`. |
| `orgid` | Conditional | Parsed as an integer. Missing, zero, or non-numeric values are treated as `0` for routing. | Non-zero numeric `orgid` enables PSP-key verification. |
| `mc` | Conditional | Parsed as an integer from the `mc` query parameter. Missing, zero, or non-numeric values are treated as `0` for routing. | Non-zero numeric `mc` enables merchant-key verification when `orgid` is not usable, or verified-VPA preference when both are present. |
| `pa` | Conditional | Looked up exactly as query parameter `pa`, then lowercased inside verified VPA lookup. | Required when Newton must use a verified-merchant public key. |

Key selection behavior:

| Parsed URL state | Key used | Failure if key cannot be selected |
| --- | --- | --- |
| `orgid` non-zero and `mc` zero | PSP public key for `orgid`. | `PSP key not found` or `PSP key not found with NPCI`. |
| `orgid` zero and `mc` non-zero | Verified VPA public key for `pa`. | `verifiedVpa not found` or `Merchant key not found`. |
| `orgid` non-zero and `mc` non-zero, `pa` found in verified VPA table | Verified VPA public key for `pa`. | `Merchant key not found`. |
| `orgid` non-zero and `mc` non-zero, `pa` not found in verified VPA table | PSP public key for `orgid`. | `PSP key not found` or `PSP key not found with NPCI`. |
| `orgid` zero and `mc` zero | No key selected. | `Invalid case orgId and mcc are zero`. |

No amount, currency, VPA format, QR expiry, merchant order, or transaction-state validation is performed by this endpoint. Validate those business rules in your own system or through the relevant Newton transaction APIs.

## Defaults and Omitted Field Behavior

Fields not listed here have no default and are not accepted by the business request type.

- `url`: required. Missing or non-string values fail JSON/body parsing before product logic.
- `iat`: no default. Required for JWS/JWE envelope modes and optional for plain JSON payload mode.
- `udfParameters`: no default. If omitted, Newton omits it from the successful decrypted response.
- Query parameters inside `url`: no default at the request type level. During URL classification, missing or non-numeric `orgid` and `mc` are treated as zero.
- `sign`: no default. The current verifier expects `&sign=` in the original URL text.

## Processing Behavior

1. `getReqBody` resolves the merchant from headers and extracts the business payload from plain, JWS, or JWE request form.
2. `merchantSignatureVerificationV2` validates `iat` for JWS/JWE, verifies the merchant signature for plain JSON payloads, checks API allow/block configuration, validates IP allowlisting, and validates `x-timestamp`.
3. `validateUrlRoute` calls request-body validation for `url` and `udfParameters`.
4. Newton parses query parameters from `url` with simple string splitting.
5. Newton selects a PSP or verified VPA public key using `orgid`, `mc`, and `pa`.
6. Newton splits the original URL on `&sign=`.
7. Newton verifies ECDSA over the text before `&sign=` using SHA-256 and the supplied Base64 DER signature.
8. Newton returns `SUCCESS` with `payload.valid = true` when verification succeeds.
9. Newton returns `SUCCESS` with `payload.valid = false` when a key is selected but signature verification returns false or the signature cannot be decoded.

## Success Response

### Valid Signature

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "udfParameters": "{\"orderId\":\"ORD12345\",\"source\":\"checkout\"}",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "WEB",
    "valid": true
  }
}
```

### Invalid Signature

Invalid signature data is not treated as a business exception when a verification key was found. Newton returns success with `valid: false`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "WEB",
    "valid": false
  }
}
```

If `udfParameters` was omitted from the request, it is omitted from the decrypted response, as shown above.

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when request processing completed and a boolean validation result is available. |
| `responseCode` | string | `SUCCESS` for completed validation. |
| `responseMessage` | string | `SUCCESS` for completed validation. |
| `udfParameters` | string | Present only when supplied in the request. Echoed unchanged. |
| `payload` | object | Business payload containing merchant identifiers and URL signature validity. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record, not from the request body. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `valid` | boolean | `true` when ECDSA verification succeeds; `false` when verification runs but the signature is invalid. |

### Response Headers

| Header | Description |
| --- | --- |
| `x-requestid` | Request id from `x-request-id`, or Newton-generated id if omitted. |
| `x-sessionid` | Session id from `x-session-id`, or the request id if omitted. |
| `X-Response-Signature` | Present in plain response mode. In JWS/JWE response modes, the response body itself is signed/encrypted instead. |

## Error Handling

Failure responses can be returned as plain error JSON, signed response, or encrypted response depending on where the failure occurs and the merchant envelope configuration. After decrypting/verifying when applicable, failures use Newton's standard error fields.

HTTP status can vary by layer. Several business-rule failures are intentionally thrown with HTTP 200 and `status: "FAILURE"` in the decrypted JSON. Always handle the decrypted `status`, `responseCode`, `responseMessage`, and, on success, `payload.valid`; do not rely only on HTTP status.

### Request Validation Failures

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

Missing required `url` or malformed JSON fails during request parsing. The exact parser text can vary by payload mode; a typical normalized body is:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"url\" not found"
}
```

Client handling:

- Do not retry unchanged validation failures.
- Send `url` as a non-empty string.
- Send `udfParameters` only as a JSON-object string, for example `"{\"orderId\":\"ORD12345\"}"`.

### URL Classification and Key Selection Failures

Both `orgid` and `mc` are missing, zero, or non-numeric:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid case orgId and mcc are zero"
}
```

Merchant-key verification requested but `pa` is missing or no active verified VPA record is found:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "verifiedVpa not found"
}
```

Verified VPA record exists but has no public key:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Merchant key not found"
}
```

PSP public key is not available in Redis:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "PSP key not found"
}
```

PSP public key remains unavailable after Newton attempts NPCI key refresh:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "PSP key not found with NPCI"
}
```

Client handling:

- Keep query parameter names lowercase: `pa`, `orgid`, `mc`, and `sign`.
- Include a non-zero numeric `orgid` for PSP-key validation.
- Include a non-zero numeric `mc` and a verified `pa` for merchant-key validation.
- Escalate to Newton if the URL is correct but PSP or merchant keys are not found.

### Signature Format and Public Key Failures

The configured public key cannot be parsed as an ECDSA public key:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid Public Key"
}
```

The URL is missing the literal `&sign=` delimiter, or the signature parameter is named or positioned in a way the current implementation cannot split. This can fail before `valid: false` is produced; the normalized response commonly has this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Signature bytes that can be parsed far enough for verification but do not match the URL return `SUCCESS` with `payload.valid = false`, not a failure response.

Client handling:

- Place `sign` after at least one prior query parameter so the URL contains literal `&sign=`.
- Keep `sign` as the final query parameter because the verifier uses everything after `&sign=` as the signature text.
- Do not change, reorder, encode, or append URL parameters after the signature was produced.
- Treat `valid: false` as a definitive signature-validation failure for that exact URL string.

### Authentication, Signature, Timestamp, and Encryption Failures

Missing merchant headers, missing timestamp/raw body, missing or invalid `x-merchant-signature`, invalid JWS, failed JWE decryption, invalid key id, or failed signature verification can return an authorization failure such as:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Malformed encrypted or signed payloads can also return invalid-data parse errors. Exact parser text varies by bad input; one concrete example is:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

JWS/JWE payload without `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

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

Client handling:

- Verify `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, and `x-merchant-signature` are generated for the exact raw request body sent on the wire.
- For JWS/JWE, include `iat` in the decrypted business payload as a 13-digit epoch-milliseconds timestamp.
- Use the correct merchant keys and `kid` values configured for the selected envelope mode.
- Retry only after correcting credentials, key ids, timestamp skew, or envelope construction.

### Merchant Configuration, API Disabled, and IP Restriction Failures

If `validateUrl` is blocked or not allowed for the merchant configuration, Newton returns:

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

- Confirm the merchant is enabled for `validateUrl`.
- Confirm the request is sent from an allowlisted IP and that proxies preserve `x-forwarded-for`.
- Do not retry rapidly; this is configuration or routing, not a transient business failure.

### Merchant Lookup, NPCI, and Unexpected Failures

Merchant or key lookup failures can happen before URL validation. The exact message can vary by deployment and helper, but decrypted bodies typically use one of these shapes:

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

When PSP keys are absent from Redis, Newton can call NPCI to refresh ListPSP keys. NPCI timeout or service failures can surface through standard downstream error codes, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "GATEWAY_TIMEOUT",
  "responseMessage": "Timed out from NPCI"
}
```

Unexpected internal errors use the standard internal-error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Retry with backoff for timeouts, `GATEWAY_TIMEOUT`, `SERVICE_UNAVAILABLE`, `INTERNAL_SERVER_ERROR`, or no response received.
- Keep the same `url` when retrying if the intended validation target has not changed.
- Escalate with `x-request-id`, timestamp, merchant id, and the decrypted failure body if errors persist.

## Retry and Idempotency Guidance

Validate URL has no transaction side effect and does not store an idempotency key. A retry of the exact same request is safe when the previous attempt did not produce a usable decrypted response.

- Safe to retry: network timeout, HTTP 5xx, `GATEWAY_TIMEOUT`, `SERVICE_UNAVAILABLE`, `INTERNAL_SERVER_ERROR`, or no response received.
- Retry with backoff and jitter. Keep retry windows short when the URL itself contains time-sensitive QR or intent parameters.
- Do not retry unchanged: empty `url`, invalid `udfParameters`, missing `&sign=`, missing `orgid`/`mc` classification data, auth failures, API disabled, or IP restriction failures.
- Treat `payload.valid = false` as a completed validation result, not as a transport failure.
- If you rebuild or re-sign the URL, call Validate URL again with the newly signed exact URL.

## Source References

- API route prefix and `{apiVersion}` capture: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- Validate URL route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:427)
- Route handler, request extraction, signature middleware, and product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2492)
- Request and response types plus field validation: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:1555)
- Product logic for URL parsing, key selection, key lookup, signature verification, and response mapping call: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:949)
- Response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1754)
- URL query parser: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:3899)
- ECDSA verification and public-key parser: [src/Newton/Utils/Crypto.hs](../../src/Newton/Utils/Crypto.hs:64), [src/Newton/Utils/Crypto.hs](../../src/Newton/Utils/Crypto.hs:373)
- Verified VPA lookup: [src/Newton/Storage/QueriesMiddleware/VerifiedVpa.hs](../../src/Newton/Storage/QueriesMiddleware/VerifiedVpa.hs:33)
- PSP key Redis lookup and Redis existence check: [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs:731)
- NPCI key refresh path: [src/Newton/External/NPCI/NpciV2.hs](../../src/Newton/External/NPCI/NpciV2.hs:129)
- Request body validation helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- `url` and `udfParameters` validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275)
- S2S request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:72)
- Merchant signature verification, API enablement, timestamp, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response envelope and headers: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:28), [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:73)
- Standard success and error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:169), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
