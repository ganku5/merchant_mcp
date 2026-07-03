# NPCI Keys API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/npci/keys`

## Overview

The NPCI Keys API lets a merchant backend fetch the NPCI `RespListKeys` material required by UPI client workflows, such as credential capture, token flows, UPI Lite setup, and CL-version-specific key rotation.

Use this API when your backend needs to provide the latest key payload to a client application before it starts an NPCI-dependent UPI flow. Newton returns one `npciKey` string in the response payload. For versioned requests, this is the base64-encoded raw `RespListKeys` XML returned by NPCI. For non-versioned POST requests, this is the merchant/environment configured static NPCI key.

Payloads use the standard Newton server-to-server request and response envelope. Examples in this guide show the decrypted business JSON for readability.

## Business Use Case

NPCI keys are needed by merchant-owned client journeys that rely on NPCI/UPI cryptographic material. The merchant backend should call this API, decrypt the response, and pass the returned `npciKey` only to the approved client component or SDK that needs it.

Common uses:

- Fetch the current configured NPCI key for standard UPI client flows.
- Fetch a CL-version-specific `RespListKeys` payload by sending `clVersion`.
- Cache the returned key on the merchant side for a short duration if allowed by onboarding guidance.
- Refresh keys after client upgrade, CL version upgrade, key expiry, or a downstream key-fetch failure.

## Integration Flow

1. Merchant backend determines whether it needs the default key or a CL-version-specific key.
2. Merchant backend builds the decrypted request payload.
3. Merchant wraps the payload using the configured Newton S2S transport mode: plain JSON with merchant signature, JWS, or JWS inside JWE.
4. Merchant calls `POST /api/{apiVersion}/merchants/npci/keys` with merchant headers and timestamp.
5. Newton verifies the payload/envelope, merchant configuration, API access, timestamp, and IP allowlist when configured.
6. Newton checks Redis for the matching key:
   - `respListKeys-{clVersion}` when `clVersion` is supplied.
   - `npciKey` for non-versioned POST requests.
7. On a cache miss:
   - With `clVersion`, Newton calls NPCI `ReqListKeys` with `Txn.type = ListKeys` and `Txn.clVersion = clVersion`, then stores the base64-encoded raw `RespListKeys`.
   - Without `clVersion`, Newton returns the configured `staticNpciKey`.
8. Merchant decrypts/verifies the response envelope and reads `payload.npciKey`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/npci/keys
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment from onboarding, for example `v1`. The POST business logic does not branch on this value; `clVersion` controls versioned NPCI key fetches. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON before any JWS/JWE transport wrapping. |
| `x-merchant-id` | Yes | Merchant identifier configured in Newton. Used to load merchant and configuration. |
| `x-merchant-channel-id` | Yes | Merchant channel identifier configured in Newton. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness for normal environments. |
| `x-merchant-signature` | Conditional | Required for plain unsigned JSON transport. Signature is verified over merchant ids, optional sub-merchant ids, timestamp, and raw request body. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant routing. Included in signature material when present. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant routing. Included in signature material when present. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP must be allowlisted. |
| `x-request-id` | No | Optional id for tracing. Newton returns it in response headers. |
| `x-session-id` | No | Optional session id for tracing. If omitted, Newton uses `x-request-id` or generates one. |

### Request Envelope

Newton accepts the standard `EncRequest` forms:

| Transport mode | On-wire JSON shape | Important behavior |
| --- | --- | --- |
| Plain JSON | The decrypted business payload directly. | Requires `x-merchant-signature`. `iat` is not required by this route for plain JSON. |
| JWS | `payload`, `signature`, `protected`. | Newton verifies the JWS key id and signature. `iat` is required in the decrypted payload and must be a valid timestamp. |
| JWE | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`. | Newton decrypts the JWE using PSP key material and expects the decrypted content to be a signed payload. `iat` is required in the decrypted business payload and must be a valid timestamp. |

Response wrapping is configured per merchant. After successful processing, Newton may return the decrypted business response as plain JSON with a response signature header, as JWS, or as JWS+JWE. The examples below show the decrypted business body.

## Request Body

### Default Static Key

Send an empty business payload when you need the default configured NPCI key.

```json
{}
```

### CL-Version-Specific NPCI Key

Send `clVersion` when the client needs a key payload for a specific NPCI CL version.

```json
{
  "clVersion": "2.0"
}
```

### Signed or Encrypted Request

When using JWS or JWE, include `iat` in the decrypted business payload.

```json
{
  "clVersion": "2.0",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Echo Merchant Metadata

`udfParameters` is echoed in the success response when supplied on the POST route.

```json
{
  "clVersion": "2.0",
  "iat": "2026-07-02T10:15:30+05:30",
  "udfParameters": "{\"clientBuild\":\"android-1452\",\"flow\":\"lite-onboarding\"}"
}
```

## Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `clVersion` | string | No | If omitted, POST uses the non-versioned `npciKey` cache key and falls back to configured `staticNpciKey` on cache miss. | The validation instance rejects an empty string, but this POST transformer does not explicitly call the generic request validator. Send a non-empty CL version when supplied. | NPCI CL version to include in downstream `ReqListKeys`. Drives versioned Redis key `respListKeys-{clVersion}`. |
| `iat` | string | Conditional | Not required for plain unsigned JSON. Required for JWS/JWE payloads. | Must be a valid timestamp when present for signed/encrypted payloads. Invalid or missing `iat` in JWS/JWE fails before business logic. | Issued-at timestamp used by Newton's signed/encrypted request validation. |
| `udfParameters` | string | No | Omitted from the response when not supplied. Echoed in the success response when supplied. | The validation instance expects a JSON-object string and rejects `$`, `-`, `*`, `!`, `%`, `~`, and backtick, but this POST transformer does not explicitly call the generic request validator. Keep it a compact JSON-object string. | Merchant metadata for tracing/correlation. Newton does not use it for key selection. |

There are no nested business request objects for this API.

## Success Response

### Decrypted Body

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "npciKey": "PFJlc3BMaXN0S2V5cyB4bWxucz0iLi4uIj4uLi48L1Jlc3BMaXN0S2V5cz4="
  },
  "udfParameters": "{\"clientBuild\":\"android-1452\",\"flow\":\"lite-onboarding\"}"
}
```

When `udfParameters` is omitted in the request, it is omitted from the response.

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful key fetch. |
| `responseCode` | string | `SUCCESS` on success. |
| `responseMessage` | string | `SUCCESS` on success. |
| `payload` | object | Business response payload. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id resolved from `x-merchant-id` and `x-merchant-channel-id`. |
| `merchantChannelId` | string | Merchant channel id resolved from request headers. |
| `npciKey` | string | Key data returned to the client. With `clVersion`, this is base64-encoded raw NPCI `RespListKeys` XML. Without `clVersion`, POST returns the configured static NPCI key. |

## Failure Scenarios

Failure bodies can be returned as plain JSON, JWS, or JWE according to merchant response configuration. The examples show the underlying decrypted JSON shape. HTTP status can be `200`, `400`, `401`, or `500` depending on the layer that fails; clients should primarily branch on decrypted `status` and `responseCode`.

### Invalid JSON or Malformed JWS Payload

Occurs when the request cannot be parsed as the expected JSON payload, or a JWS payload cannot be base64-decoded and parsed.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in parsing signedPayload"
}
```

Client handling: fix serialization/signing. Do not retry the same payload unchanged.

### Missing or Invalid `iat` for JWS/JWE

Signed and encrypted payloads must include a valid decrypted `iat`.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

If the timestamp format is invalid or outside the allowed freshness window, the message may be:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid timestamp format"
}
```

Client handling: regenerate the payload with a current timestamp and resign/re-encrypt.

### Missing Merchant Headers or Unknown Merchant

Missing `x-merchant-id`, missing `x-merchant-channel-id`, or an unknown merchant/channel fails authentication.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: verify onboarding credentials, environment, merchant id, and channel id. Do not retry until configuration is corrected.

### Signature, JWS, or JWE Verification Failure

Occurs when `x-merchant-signature` is absent or invalid for plain JSON, when the JWS signature/key id is invalid, or when JWE decryption/source validation fails.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: recompute the signature over the exact raw request body and timestamp, or use the correct JWS/JWE keys and `kid`. Do not change whitespace after signing a plain JSON body.

### API Disabled or Not Allowed for Merchant

If the merchant configuration blocks this API or restricts allowed APIs and does not include `listNpciKeysPostS2S`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: contact Newton onboarding/support to enable this API for the merchant/channel. Retrying will not help until the merchant configuration changes.

### IP Allowlist Failure

If merchant configuration contains `whitelistedIps`, the first IP in `x-forwarded-for` must match. Missing or non-allowlisted IP returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: call from an allowlisted egress IP or update the merchant allowlist. Do not retry from the same blocked IP.

### Static Key Not Configured

For non-versioned POST requests, Newton falls back to `staticNpciKey`. If that configuration is absent, the helper raises invalid data.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid fetchNpciKeys - staticNpciKey"
}
```

Client handling: send `clVersion` if you intended to fetch from NPCI, or ask Newton to configure the static NPCI key for this environment.

### NPCI Failure or Empty Key Response

When `clVersion` is supplied and NPCI returns failure, timeout, immediate failure, or no key list, Newton maps the business failure to service unavailable.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Client handling: retry with backoff. If failures persist, surface a temporary service issue and avoid starting the dependent UPI client flow.

### Downstream Decode, Redis, or Unexpected Internal Error

Unexpected downstream decode failures, missing required raw XML from NPCI after a successful response, or missing key data after fetch can surface as an internal server error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry once after a short delay if the request is otherwise valid. Escalate with `x-request-id` if the issue persists.

### Rate Limiting or Downstream Protection

Versioned key fetches call NPCI and pass through the PSP API rate limiter using the `reqListNpciKeys` rate-limit program. The exact response body depends on the shared rate-limiter layer for the deployment.

Typical decrypted shape:

```json
{
  "status": "FAILURE",
  "responseCode": "RATE_LIMIT_EXCEEDED",
  "responseMessage": "Too many requests"
}
```

Client handling: cache successful keys, avoid per-device bursts for the same `clVersion`, and retry after the configured cool-down.

## Retry and Idempotency Guidance

This API does not accept a merchant request id and does not create a business transaction. It is safe to retry from a business-idempotency perspective.

Recommended client behavior:

- Cache successful `npciKey` values on the merchant side only for the duration approved during onboarding. Newton caches keys internally using `npciListKeysCacheTtl`, defaulting to `93600` seconds when not overridden.
- Retry transient `SERVICE_UNAVAILABLE_NPCI_NA`, rate-limit, and internal errors with exponential backoff and jitter.
- Do not retry unchanged requests for `UNAUTHORIZED`, `API NOT ENABLED`, IP allowlist failures, malformed JSON, invalid signatures, or missing configuration.
- For `clVersion` requests, use the exact CL version required by the client. Changing `clVersion` changes the Redis key and downstream NPCI request.
- For plain JSON signatures, regenerate both `x-timestamp` and `x-merchant-signature` on every retry.

## Source References

- Route definition for GET and POST `/merchants/npci/keys`: [Core.hs](../../src/Newton/App/Routes/Core.hs:461)
- POST handler, auth, merchant config setup, and transformer call: [Core.hs](../../src/Newton/App/Routes/Core.hs:2692)
- S2S transformer for POST: [ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:701)
- POST request/response builders and POST defaults: [ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1161)
- Request and response JSON types: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2027)
- Core product logic, Redis lookup, fetch, and response mapping: [ListNpciKeys.hs](../../src/Newton/Product/Merchant/Customer/ListNpciKeys.hs:13)
- Static key, versioned key, Redis cache, and NPCI-error handling: [Customer/Helper.hs](../../src/Newton/Product/Merchant/Customer/Helper.hs:149)
- NPCI `ReqListKeys` payload fields: [NpciV2.hs](../../src/Newton/External/NPCI/NpciV2.hs:186)
- NPCI key fetch, raw XML base64 encoding, and downstream failure mapping: [NpciV2.hs](../../src/Newton/External/NPCI/NpciV2.hs:619)
- Merchant headers, API enablement, signature checks, timestamp, and IP allowlist: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:48)
- JWS/JWE/plain request handling: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Response wrapping strategy: [RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:75)
- Envelope JSON shapes: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Error/success response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
- Config defaults for static keys and cache TTL: [Config/Transformer.hs](../../src/Newton/Types/Config/Transformer.hs:248)
