# List NPCI Keys API Integration Guide

Source endpoint: `GET /api/{apiVersion}/merchants/npci/keys`

## Overview

List NPCI Keys is a server-to-server API used by a merchant backend to fetch the NPCI `RespListKeys` data that client UPI workflows need before invoking the NPCI common library.

The response contains the merchant identifiers and a single `npciKey` string. Depending on Newton configuration and API version, `npciKey` can be a configured static key payload or a base64-encoded NPCI `RespListKeys` XML response. The merchant backend should pass the value to the client component that needs NPCI list-key material for registration, UPI Lite, biometric authentication, or other supported common-library journeys.

This guide covers the GET variant only. The route has a POST sibling for `clVersion`, but this file documents `GET /api/{apiVersion}/merchants/npci/keys`.

## Business Use Case

Use this API when:

- The merchant backend needs current NPCI key material before starting a UPI customer journey.
- A client flow needs the NPCI common-library list-key payload but the merchant wants key retrieval to happen through its backend integration with Newton.
- The merchant wants Newton to choose the correct key variant based on server configuration and `x-api-version`.
- The integration wants Newton to use cache/static-key behavior where configured, avoiding a synchronous NPCI call when possible.

Do not use this API to create a transaction, register a customer, fetch account data, or validate a VPA. It only returns list-key material.

## Integration Flow

1. Merchant backend receives or prepares to start a client UPI journey that needs NPCI list keys.
2. Merchant backend calls `GET /api/{apiVersion}/merchants/npci/keys` with merchant headers.
3. Newton resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
4. Newton reads `x-api-version` from headers. If it is absent or not an integer, Newton uses version `0`.
5. Newton builds an internal list-key request from server configuration:
   - `useStaticRespListKeys`
   - `respListKeysApiVersionForLiteKeys`
   - `respListKeysApiVersionForBioAuthKeys`
6. Newton looks for a cached key in Redis.
7. On cache miss, Newton either returns configured static key material or calls NPCI `ReqListKeys`, then caches the resulting key list.
8. Newton returns the first key entry's data as `payload.npciKey`.
9. Merchant backend decrypts/verifies the response if configured, then forwards the `npciKey` value only to the trusted client component that needs it.

## Endpoint

```http
GET /api/{apiVersion}/merchants/npci/keys
```

### Path Parameters

| Name | Type | Required | Validation / behavior | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | string | Yes | Captured by the route. The traced product logic does not parse this path value for this endpoint. | Version segment in the URL, for example `/api/v1/merchants/npci/keys` or the value shared during onboarding. |

### Query Parameters

This GET endpoint does not define query parameters.

Unknown query parameters are not used by the traced handler. Do not send query parameters for key selection.

### Headers

| Header | Required | Validation / behavior | Description |
| --- | --- | --- | --- |
| `x-merchant-id` | Yes | Must identify an enabled merchant row with the supplied channel id. Missing or unknown values fail before product logic. | Merchant identifier shared during onboarding. |
| `x-merchant-channel-id` | Yes | Must match the merchant channel id for `x-merchant-id`. Missing or unknown values fail before product logic. | Merchant channel identifier shared during onboarding. |
| `x-api-version` | Recommended | Parsed as an integer. If absent or invalid, Newton uses `0`. This value controls whether Newton requests Lite or biometric-auth key variants. | API behavior version. Use the version shared during onboarding. |
| `x-request-id` | Recommended | If omitted, Newton generates one. Returned as response header `x-requestid`. | Merchant request correlation id. |
| `x-session-id` | Optional | If omitted, Newton uses the request id. Returned as response header `x-sessionid`. | Session/correlation id for logs. |
| Response encryption/signing strategy headers | Conditional | Used by shared response wrapping to choose plain signed response, JWS, or JWS+JWE response, depending on merchant configuration and headers. | Use the response security headers and key ids shared during onboarding. |
| `Content-Type` | No | No request body is expected. | `application/json` is harmless but not required for this GET call. |

### Authentication, Encryption, and Signing

This GET route is unusual among Newton S2S APIs because it does not accept an encrypted request body. The traced handler does not call `getReqBody` and does not run `merchantSignatureVerificationV2`; it sets an empty plaintext body and resolves the merchant only from headers.

Request expectations:

- Do not send a JSON request body.
- Do not send `merchantPayload`, JWE, or JWS request envelope fields for this GET endpoint.
- `iat`, `x-timestamp`, and request-body signature validation are not used by the traced GET handler.
- `x-merchant-id` and `x-merchant-channel-id` are still mandatory because Newton needs the merchant for response wrapping and payload fields.

Response expectations:

- The business response is produced as `ListNpciKeysResponse`.
- Shared S2S response wrapping can return:
  - an unsigned JSON business response with `X-Response-Signature`, or
  - a JWS response, or
  - a JWS encrypted inside JWE.
- The selected response shape depends on merchant response security configuration and request headers.
- Early failures that occur before a merchant is available can be returned as the raw Newton error JSON shape rather than an encrypted merchant-specific response.

## Request

### Empty GET Request

```http
GET /api/v1/merchants/npci/keys HTTP/1.1
Host: newton.example
x-merchant-id: MERCHANT123
x-merchant-channel-id: APP
x-api-version: 2
x-request-id: req-20260702-001
```

### cURL Example

```bash
curl --request GET 'https://newton.example/api/v1/merchants/npci/keys' \
  --header 'x-merchant-id: MERCHANT123' \
  --header 'x-merchant-channel-id: APP' \
  --header 'x-api-version: 2' \
  --header 'x-request-id: req-20260702-001'
```

### Body

This endpoint has no request body.

Do not send:

```json
{}
```

Do not send an encrypted S2S request envelope:

```json
{
  "protected": "eyJhbGciOiJSU0EtT0FFUC0yNTYiLCJlbmMiOiJBMjU2R0NNIiwia2lkIjoibWVyLWp3ZS1rZXktMSJ9",
  "encrypted_key": "dGVzdC1lbmNyeXB0ZWQta2V5",
  "iv": "dGVzdC1pdi0xMjM0",
  "ciphertext": "dGVzdC1jaXBoZXJ0ZXh0",
  "tag": "dGVzdC10YWc"
}
```

### Meaningful Request Variants

The client-controlled variants are header-only:

| Variant | How to call | Effect |
| --- | --- | --- |
| Base/default key request | Omit `x-api-version` or send a version below the configured Lite and biometric thresholds. | Newton uses internal `sendLiteKeys = false` and `sendBioAuthKeys = false`; cache key suffix is `npciKey`. |
| Lite key request | Send `x-api-version` greater than or equal to configured `respListKeysApiVersionForLiteKeys`. Default server config threshold is `1`. | Newton uses `sendLiteKeys = true`; if biometric threshold is not reached, cache key suffix is `npciKeyV1`. |
| Biometric-auth key request | Send `x-api-version` greater than or equal to configured `respListKeysApiVersionForBioAuthKeys`. Default server config threshold is `2`. | Newton uses `sendBioAuthKeys = true`; cache key suffix is `npciKeyBioAuth`. |
| Invalid or missing `x-api-version` | Omit the header or send a non-integer value such as `latest`. | Newton falls back to version `0`; no validation error is returned for the version header. |

## Field Reference

### Client-Supplied Fields

There are no body or query fields for this GET endpoint.

| Field | Location | Required | Validation / behavior |
| --- | --- | --- | --- |
| Request body | Body | No | No `ReqBody` is defined on the GET route. Body content is not part of the business request. |
| Query parameters | Query | No | No query parameters are defined or used by the traced handler. |

### Internal Request Fields

Newton builds these fields internally after reading headers and configuration. They are not sent by the merchant.

| Internal field | Type | Source | Default / behavior | Description |
| --- | --- | --- | --- | --- |
| `useStaticRespListKeys` | boolean | Runtime config `USE_STATIC_RESPLISTKEYS` | Defaults to `true` when env config is absent. | Controls whether Newton can return configured static keys instead of calling NPCI. |
| `sendLiteKeys` | boolean | `x-api-version >= respListKeysApiVersionForLiteKeys` | Default threshold is `1`. If `x-api-version` is absent/invalid, version `0` is used. | Selects the Lite key variant for GET requests. |
| `sendBioAuthKeys` | boolean | `x-api-version >= respListKeysApiVersionForBioAuthKeys` | Default threshold is `2`. If true, biometric key selection takes precedence over Lite cache suffix selection. | Selects the biometric-auth key variant for GET requests. |
| `clVersion` | optional string | Not available on GET | Always `null` for this GET route. | Common-library version is supported by the POST sibling, not this GET endpoint. |

### Key Selection Behavior

| Condition | Source of key material | Cache lookup / write key |
| --- | --- | --- |
| Cached key exists | Redis value is returned; no static config or NPCI call is needed. | `newton-npciKey`, `newton-npciKeyV1`, or `newton-npciKeyBioAuth`, with deployment-specific Redis prefix. |
| `useStaticRespListKeys = true` and `sendBioAuthKeys = true` | Configured `staticBioAuthNpciKey`. | `npciKeyBioAuth` suffix. |
| `useStaticRespListKeys = true`, `sendLiteKeys = true`, `sendBioAuthKeys = false` | Configured `staticLiteNpciKey`. | `npciKeyV1` suffix. |
| `sendLiteKeys = false` and `sendBioAuthKeys = false` | Configured `staticNpciKey`. | `npciKey` suffix. |
| `useStaticRespListKeys = false` and `sendLiteKeys = true` | NPCI `ReqListKeys`, then base64-encoded raw `RespListKeys` XML. | `npciKeyV1` or `npciKeyBioAuth` depending on flags. |

For this GET route, if `useStaticRespListKeys = false` and `sendLiteKeys = false`, the code still uses configured `staticNpciKey`.

## Success Response

### Decrypted Business Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "npciKey": "PFJlc3BMaXN0S2V5cz48SGVhZCB2ZXI9IjIuMCIvPjwvUmVzcExpc3RLZXlzPg=="
  }
}
```

`udfParameters` is always omitted for the GET variant because the GET request has no business payload and the response builder sets it to `null`.

### Response Headers

| Header | Description |
| --- | --- |
| `x-requestid` | Echoes `x-request-id` from the request, or a Newton-generated id if not supplied. |
| `x-sessionid` | Echoes `x-session-id` from the request, or the request id when no session id is supplied. |
| `X-Response-Signature` | Present for response-signature strategies that return an unsigned JSON response with signature header. Not present when the whole response body is returned as JWS or JWE. |

### Response Envelope Notes

The examples in this guide show the decrypted business payload. Depending on onboarding configuration, the actual HTTP body may be one of these shapes:

Plain business JSON with response signature header:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "npciKey": "PFJlc3BMaXN0S2V5cz48SGVhZCB2ZXI9IjIuMCIvPjwvUmVzcExpc3RLZXlzPg=="
  }
}
```

JWS response:

```json
{
  "payload": "eyJzdGF0dXMiOiJTVUNDRVNTIiwicmVzcG9uc2VDb2RlIjoiU1VDQ0VTUyJ9",
  "protected": "eyJhbGciOiJSUzI1NiIsImtpZCI6Im1lci1qd3Mta2V5LTEifQ",
  "signature": "c2FtcGxlLXJzMjU2LXNpZ25hdHVyZQ"
}
```

JWE response:

```json
{
  "protected": "eyJhbGciOiJSU0EtT0FFUC0yNTYiLCJlbmMiOiJBMjU2R0NNIiwia2lkIjoibWVyLWp3ZS1rZXktMSJ9",
  "encrypted_key": "dGVzdC1lbmNyeXB0ZWQta2V5",
  "iv": "dGVzdC1pdi0xMjM0",
  "ciphertext": "dGVzdC1jaXBoZXJ0ZXh0",
  "tag": "dGVzdC10YWc"
}
```

### Response Field Reference

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `status` | string | Yes | `SUCCESS` for successful processing. |
| `responseCode` | string | Yes | `SUCCESS` for successful processing. |
| `responseMessage` | string | Yes | `SUCCESS` for successful processing. |
| `payload` | object | Yes | Business response payload. |
| `payload.merchantId` | string | Yes | Merchant id resolved from `x-merchant-id` and `x-merchant-channel-id`. |
| `payload.merchantChannelId` | string | Yes | Merchant channel id resolved from request headers. |
| `payload.npciKey` | string | Yes | The first returned NPCI key data value. This can be configured static key material or base64-encoded raw `RespListKeys` XML when fetched from NPCI. |
| `udfParameters` | string | No | Not returned by this GET route. |

## Failure Scenarios

Error HTTP status can vary by layer because the global middleware can normalize statuses to HTTP 200 unless disabled. Always process the decrypted or raw JSON body fields: `status`, `responseCode`, and `responseMessage`.

### Missing Merchant Headers

Occurs when `x-merchant-id` or `x-merchant-channel-id` is absent. The GET handler cannot resolve a merchant and stops before key lookup.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: fix integration headers. Do not retry unchanged.

### Unknown or Disabled Merchant

Occurs when the header pair does not resolve to an enabled merchant.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: verify merchant id/channel id and onboarding status with Newton. Do not retry unchanged.

### Invalid `x-api-version`

The traced code does not fail for an invalid `x-api-version`. It silently uses version `0`.

Example request:

```http
x-api-version: latest
```

Observed behavior:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "npciKey": "PFJlc3BMaXN0S2V5cz48SGVhZCB2ZXI9IjIuMCIvPjwvUmVzcExpc3RLZXlzPg=="
  }
}
```

Client handling: send the numeric version shared during onboarding. If the wrong key variant is returned, check `x-api-version` first.

### Request Body Sent to GET

No request body is defined. The traced handler explicitly sets the plaintext body to an empty string for logging and business processing.

There is no business validation error for a missing body because a body is not expected.

Client handling: remove the body and call the endpoint as a normal GET request.

### Encrypted Request Envelope Sent to GET

The GET route does not decrypt request envelopes. A JWE/JWS body is not part of the route contract.

Possible outcomes vary by gateway/client behavior:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Request is not valid"
}
```

or the body may be ignored by the handler if the HTTP stack accepts a GET body.

Client handling: do not send request encryption for this GET endpoint. Use response decryption/verification only if configured.

### API Disabled or Merchant API Allowlist

The API disabled and allowed-API checks live in `merchantSignatureVerificationV2`. The traced GET handler does not call that middleware, so there is no endpoint-level `blockedApiNames` or allowed-API enforcement in this GET path.

If a deployment enforces the same rule in an upstream layer or the route is changed to call signature verification, the underlying body shape is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: confirm that List NPCI Keys is enabled for the merchant. Do not retry unchanged.

### IP Restriction

IP allowlist validation also lives in `merchantSignatureVerificationV2` and is not called by the traced GET handler. If a deployment enforces IP restrictions upstream, failures use the unauthorized body shape:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: send traffic from onboarded egress IPs and include required proxy headers if your deployment requires them. Do not retry from a non-allowlisted IP.

### State or Business-Rule Failure

This endpoint does not read customer, account, VPA, transaction, mandate, or device state. It also does not create or update business records. The realistic business-rule failures for this GET path are therefore configuration/key-selection failures, such as a missing selected static key, or downstream NPCI list-key failure when Newton is configured to call NPCI.

Client handling: treat state-related failures as not applicable for this endpoint. For key/configuration failures, follow the specific guidance below.

### Static NPCI Key Missing in Configuration

Occurs on cache miss when Newton is configured to use static keys but the selected static key is absent:

- `staticNpciKey` for base/default key.
- `staticLiteNpciKey` for Lite key.
- `staticBioAuthNpciKey` for biometric-auth key.

Underlying response:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid fetchNpciKeys - staticNpciKey"
}
```

The response message includes the missing selected key name, for example `staticLiteNpciKey` or `staticBioAuthNpciKey`.

Client handling: contact Newton support or operations. Retrying will not help until configuration is fixed.

### Redis Cache Miss

A Redis miss is not a client-visible failure. Newton falls back to static key material or NPCI lookup.

Client handling: no special handling needed.

### Redis Read/Write Failure

The traced code depends on Redis for cache lookup and cache write. If the Redis helper throws, the response can be an internal error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with backoff. If repeated, raise an incident with `x-requestid`.

### NPCI Returns Failure for `ReqListKeys`

When Newton calls NPCI and receives a `RespListKeys` response whose result is `FAILURE`, Newton marks the key response as errored. The product helper maps that to a service-unavailable failure.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Client handling: retry with backoff. Do not block the customer indefinitely; ask the client to refresh/restart the UPI flow after a short wait.

### NPCI Immediate Failure

When the NPCI call fails immediately before a valid `RespListKeys` response is available, Newton returns a service-unavailable failure. If no timeout code is present, the code suffix is `NA`.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Client handling: retry with backoff. If repeated, use `x-requestid` for support.

### NPCI Timeout

When the NPCI call times out and a timeout code is available, the code appears in the response code suffix.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U20",
  "responseMessage": "NPCI service is not reachable at the moment (U20)"
}
```

Client handling: safe to retry with backoff. Since this endpoint only fetches key material and does not mutate customer or transaction state, retries do not create duplicate business objects.

### NPCI Response Missing Raw XML

When Newton calls NPCI successfully but the `RespListKeys` response has no raw XML to encode, the code throws an internal error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with backoff. If repeated, raise to Newton because the upstream response or parser behavior needs investigation.

### NPCI Key List Missing After Fetch

If Newton receives a key response without `npciKeys`, the helper treats it as an NPCI service-unavailable condition.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Client handling: retry with backoff. If repeated, raise with `x-requestid`.

### Response Signing or Encryption Failure

After successful business processing, response wrapping can fail if merchant response keys or key ids are not configured correctly.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: do not retry aggressively. Verify onboarding key configuration with Newton.

### Unexpected Error

Unexpected exceptions are returned using Newton's internal-server-error shape.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with bounded backoff. If the error persists, raise to Newton with `x-requestid`, merchant id, channel id, timestamp, and environment.

## Retry and Idempotency Guidance

This endpoint is read-oriented from the merchant perspective. It does not create a transaction, customer, mandate, account, or idempotency record.

Retry guidance:

- Safe to retry on network errors, `SERVICE_UNAVAILABLE_*`, and transient `INTERNAL_SERVER_ERROR`.
- Use exponential backoff with jitter, for example 1s, 2s, 4s, then stop or degrade the client flow.
- Do not retry unchanged on `UNAUTHORIZED`, `API NOT ENABLED`, or missing static-key configuration errors.
- Include a stable `x-request-id` for each attempt series if your observability expects correlation, or a fresh id per attempt if your support process tracks individual HTTP attempts.

Idempotency guidance:

- No request idempotency key is required.
- `x-request-id` is for tracing only; it does not deduplicate or pin a key response.
- Returned key material may change after cache expiry, static-key rotation, or NPCI key rotation.

Caching guidance for merchants:

- Treat `npciKey` as sensitive operational key material.
- Cache only for the duration and storage policy approved during onboarding.
- Refresh the key before starting a client flow if a previous key is rejected by the common library.

## Source References

- Route prefix and API version capture: [Core.hs](../../src/Newton/App/Routes/Core.hs:112)
- GET route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:461)
- GET route handler: [Core.hs](../../src/Newton/App/Routes/Core.hs:2676)
- S2S transformer route: [ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:694)
- GET internal request and response builders: [ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1136)
- S2S response types: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2027)
- Core product route: [ListNpciKeys.hs](../../src/Newton/Product/Merchant/Customer/ListNpciKeys.hs:13)
- Core product request/response types: [Customer/Types.hs](../../src/Newton/Product/Merchant/Customer/Types.hs:303)
- Key fetch, Redis cache, and validation helpers: [Customer/Helper.hs](../../src/Newton/Product/Merchant/Customer/Helper.hs:149)
- NPCI `ReqListKeys` call and response mapping: [NpciV2.hs](../../src/Newton/External/NPCI/NpciV2.hs:619)
- NPCI list-key payload construction: [NpciV2.hs](../../src/Newton/External/NPCI/NpciV2.hs:186)
- Galileo key response shape reused by helper code: [Galileo/Types.hs](../../src/Newton/External/Galileo/Types.hs:891)
- Header-based merchant resolution for this GET route: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:48)
- API allowlist/IP/signature checks used by signed S2S routes but not called by this GET handler: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- API disabled and allowed-API errors: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- Merchant lookup behavior: [DB.hs](../../src/Newton/Utils/DB.hs:209)
- Merchant not found error: [Merchant.hs](../../src/Newton/Storage/QueriesMiddleware/Merchant.hs:46)
- Response headers and response wrapping: [RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:28)
- Response encryption/signing helpers: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:427)
- Encoded request/response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:16)
- `x-api-version` fallback behavior: [Utils.hs](../../src/Newton/Utils/Utils.hs:960)
- Relevant config defaults: [Config.hs](../../src/Newton/Config/Config.hs:2402)
