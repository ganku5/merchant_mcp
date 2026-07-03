# List PSP API Integration Guide

Source endpoint: `GET /api/{apiVersion}/npci/listPsp`

## Overview

List PSP is a read-only server-to-server API used to fetch the PSP list that Newton currently has for NPCI UPI PSP/provider metadata.

The merchant backend calls this API when it needs a current PSP catalogue for client-side UPI workflows, internal PSP-code mapping, or backend cache warm-up. Newton returns PSP display names, PSP code values, the active flag returned by NPCI, and version metadata when available.

This endpoint does not fetch banks, customer accounts, NPCI keys, NPCI tokens, UPI Lite parameters, or transaction status. It only returns the PSP list.

## Business Use Case

List PSP helps merchants:

- Build or refresh a PSP/provider catalogue used by UPI registration or app-selection workflows.
- Map PSP names to the PSP code values returned by NPCI.
- Read the PSP `active` marker without hard-coding the list in the merchant backend.
- Read `versionSupported` when the merchant app needs to reason about PSP-supported UPI versions.
- Recover from stale local PSP metadata without shipping an app/backend configuration change.

Use this API during backend startup, scheduled cache refresh, or before a UPI customer journey when the merchant-side PSP cache is missing or stale. Do not call it for every screen render; cache the response on the merchant side and refresh periodically.

## Integration Flow

1. Merchant backend calls `GET /api/{apiVersion}/npci/listPsp`.
2. Newton checks its Redis PSP-list cache at the deployment-specific key prefix plus `psps`.
3. If Redis has a non-empty PSP list, Newton returns that cached list.
4. If Redis is empty or missing, Newton creates an internal NPCI `ReqListPsp` request.
5. Newton sends `ReqListPsp` to NPCI using NPCI API version `2.0`.
6. If NPCI returns `Resp.result = "SUCCESS"` and `PspList.Psp` is present, Newton writes the list back to Redis using the configured TTL and returns it.
7. Merchant backend stores the returned list and uses it in downstream customer or operational workflows.

Important fields:

- `name`: PSP display name from NPCI/Redis.
- `codes`: PSP code values associated with the PSP.
- `active`: Active marker returned as text by NPCI/Redis. Treat it as a string, not a boolean.
- `versionSupported`: Optional NPCI version-supported metadata.

## Endpoint

```http
GET /api/{apiVersion}/npci/listPsp
```

### Path Parameters

| Name | Type | Required | Validation / behavior | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | string | Yes | Captured by the Newton route. The traced handler does not parse this value for List PSP product behavior. | Version segment in the URL, for example `/api/v1/npci/listPsp` or the value shared during onboarding. |

### Query Parameters

This endpoint does not define query parameters.

Unknown query parameters are not used by the traced handler. Do not send query parameters for PSP filtering, pagination, or version selection.

### Headers

| Header | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- |
| `Accept` | Recommended | If omitted, the service still produces JSON for this route. | Send `application/json`. |
| `Content-Type` | No | No request body is expected. | Not required for this GET endpoint. |
| `x-request-id` | No | Newton generates a UUID if omitted. Returned as response header `x-requestid`. | Merchant/request correlation id. |
| `x-session-id` | No | Defaults to the request id. Returned as response header `x-sessionid`. | Session correlation id for logs. |
| `x-api-version` | No | Not read by the traced List PSP product path. Sending or omitting it does not change response fields. | Some gateway/onboarding setups may still ask merchants to send a standard API-version header. |
| `x-merchant-id` | Conditional | Not validated by the traced List PSP route handler itself. | Send if required by your Newton gateway, network allowlist, or onboarding contract. |
| `x-merchant-channel-id` | Conditional | Not validated by the traced List PSP route handler itself. | Send with `x-merchant-id` when your environment requires merchant headers. |
| Response security headers | Conditional | The default traced GET wrapper returns the plain business JSON as an unsigned `EncResponse` variant. | Use only the signing/encryption mode explicitly enabled for this GET endpoint. Do not set SDK-style JWE response encryption headers unless Newton has enabled the required context for this route. |

### Authentication, Envelope, and Signing

This route is a GET endpoint and does not accept an encrypted request body. In the current handler, Newton does not call `getReqBody`, request payload verification, or `merchantSignatureVerificationV2` for this endpoint.

Request expectations:

- Send no JSON request body.
- Do not send `merchantPayload`, JWS, or JWE request envelope fields.
- `iat`, `x-timestamp`, `x-raw-body`, request-body checksum, and request-body signature validation are not used by the traced List PSP handler.
- Follow the gateway, IP allowlist, and credential requirements shared during onboarding for your environment.

Response expectations:

- The route response type is `DefaultRespHeaders (API.EncResponse TfS2S.ListPspResponse)`.
- By default, the traced GET wrapper serializes `UnSignedResponse`, so the HTTP body is the business JSON shown below.
- The route response headers are `x-requestid` and `x-sessionid`.
- The route type does not include `X-Response-Signature`.
- If an upstream gateway or environment-specific wrapper applies response encryption/signing, decrypt or verify according to the onboarding process. The examples below show the decrypted/plain business payload.

## Request

### Required Minimum

```http
GET /api/v1/npci/listPsp HTTP/1.1
Host: newton.example
Accept: application/json
x-request-id: psp-list-20260702-001
```

### cURL Example

```bash
curl --request GET 'https://newton.example/api/v1/npci/listPsp' \
  --header 'Accept: application/json' \
  --header 'x-request-id: psp-list-20260702-001'
```

If your onboarding requires merchant headers, include them:

```bash
curl --request GET 'https://newton.example/api/v1/npci/listPsp' \
  --header 'Accept: application/json' \
  --header 'x-merchant-id: MERCHANT123' \
  --header 'x-merchant-channel-id: APP' \
  --header 'x-request-id: psp-list-20260702-002'
```

### Body

This endpoint has no request body.

Do not send an empty JSON body:

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

### Client-Supplied Field Reference

There are no body or query fields for this GET endpoint.

| Field | Location | Required | Default / omitted behavior | Validation / behavior |
| --- | --- | --- | --- | --- |
| Request body | Body | No | No body is needed. | No `ReqBody` is defined on the route. Body content is not part of the business request and should not be sent. |
| Query parameters | Query | No | No defaults. | No query parameters are defined or used by the traced handler. |
| `apiVersion` | Path | Yes | No default. | Captured by the route namespace; not parsed by List PSP product logic. |
| `x-request-id` | Header | No | Generated UUID if omitted. | Used for tracing and echoed as `x-requestid`. |
| `x-session-id` | Header | No | Defaults to request id. | Used for tracing and echoed as `x-sessionid`. |
| `x-api-version` | Header | No | No List PSP behavior change when omitted. | Not read by the traced List PSP product path. |

### Internal Request Fields

Newton builds these values internally. Merchants do not send them.

| Internal field | Type | Source | Default / behavior | Description |
| --- | --- | --- | --- | --- |
| `Head.ver` | string | Code constant in helper | Always built as `2.0`. | NPCI request header version for `ReqListPsp`. |
| `Head.orgId` | string | Runtime NPCI config | No client override. | Newton/NPCI organization id. |
| `Txn.id` | string | Generated by Newton | New transaction id for the fallback NPCI call. | Used to correlate `ReqListPsp` and async NPCI response. |
| `Txn.note` | string | Code constant | `List PSP`. | NPCI transaction note. |
| `Txn.refId` | string | Generated UUID | New UUID for each fallback call. | Internal NPCI reference id. |
| `Txn.refUrl` | string | Runtime NPCI config | No client override. | Newton reference URL sent to NPCI. |
| `Txn.type` | string | Code constant | `ListPsp`. | NPCI request type. |
| Redis cache key | string | Runtime Redis prefix plus `psps` | No client override. | Cache lookup/write location for the PSP list. |

## Validation and Processing Behavior

- There are no business-field validators because the endpoint has no request body and no query parameters.
- Missing or invalid `x-api-version` does not fail the request and does not alter the List PSP response.
- The route handler logs `Get PSPs API called.`, sets monitoring options, and invokes the List PSP transformer.
- Newton first tries Redis. A non-empty cached list is returned directly.
- A missing or empty Redis list triggers the NPCI fallback call.
- On NPCI success, Newton requires `PspList.Psp` to be present. A success response without the PSP array is treated as an internal failure, not as an empty list.
- On fallback success, Newton refreshes Redis with the configured TTL and returns the PSP list.
- On NPCI failure, timeout, malformed response, missing list, Redis/cache failure, or unexpected helper failure, the product path does not expose the upstream NPCI code directly to clients. It returns the standard internal-error body.
- The success response does not add top-level `status`, `responseCode`, or `responseMessage`.

## Response

When the request completes normally, the response body contains only the `psps` array.

### Success Response

```json
{
  "psps": [
    {
      "name": "Example PSP",
      "codes": [
        "EXAM",
        "EXAM2"
      ],
      "active": "Y",
      "versionSupported": {
        "Version": [
          {
            "description": "UPI 2.0",
            "mandatory": "true",
            "no": "2.0"
          }
        ]
      }
    },
    {
      "name": "Sample PSP",
      "codes": [
        "SAMP"
      ],
      "active": "N"
    }
  ]
}
```

### Success Response Without Version Metadata

`versionSupported` is omitted when NPCI/Redis does not provide it or when Newton cannot parse it into the supported version type.

```json
{
  "psps": [
    {
      "name": "Example PSP",
      "codes": [
        "EXAM"
      ],
      "active": "Y"
    }
  ]
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `psps` | array of objects | PSP records available to Newton. Cache this list on the merchant side and refresh periodically. |

### `psps[]`

| Field | Type | Always present | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | PSP display name from NPCI/Redis. |
| `codes` | array of strings | Yes | PSP code values associated with the PSP. |
| `active` | string | Yes | Active marker copied as text from NPCI/Redis, commonly values such as `Y` or `N`. Do not parse this as a JSON boolean. |
| `versionSupported` | object | No | Version metadata parsed from NPCI/Redis. Omitted when unavailable or unparsable. |

### `versionSupported`

| Field | Type | Description |
| --- | --- | --- |
| `Version` | object or array | NPCI version-supported data. It can be a single version object or an array depending on the payload shape. |

### `versionSupported.Version`

| Field | Type | Description |
| --- | --- | --- |
| `description` | string | Version description returned by NPCI/Redis. |
| `mandatory` | string | Whether the version is marked mandatory, when supplied. |
| `no` | string | Version number. |

### Omitted and Non-Exposed Fields

- `versionSupported` is omitted if unavailable or unparsable.
- PSP URL, SPOC name, SPOC email, SPOC phone, and `lastModifedTs` exist in the NPCI PSP type but are not exposed by this S2S response.
- `status`, `responseCode`, and `responseMessage` are not present on success.
- A successful empty list is not expected from the fallback path. If Redis and NPCI cannot produce a usable PSP list, the current product code returns an error instead.

## Error Handling

Failure responses use Newton's standard error body when generated by Newton error helpers:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

If `payload` is empty, it is omitted from the JSON response.

The HTTP status can vary by failing layer. The List PSP product fallback currently throws several downstream/cache failures with HTTP `200` and the failure body above. Framework, gateway, auth, or routing failures can use `400`, `401`, `404`, `405`, `422`, or `500` depending on where the request fails.

### Validation and Request Shape Failures

There are no business-field validation errors for this endpoint because it has no request body and no query parameters.

Wrong path, unsupported method, or gateway-level request-shape failures happen before product logic. Exact text can vary by deployment. When normalized to Newton's error shape, a concrete example is:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid request method or path"
}
```

Malformed signed/encrypted data sent to a gateway or route wrapper that tries to parse it can be returned as:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Unable to parse request payload"
}
```

For this GET route, the normal client fix is to remove the request body/JWS/JWE payload and call the exact GET path.

### Auth, Signature, and Gateway Failures

The traced List PSP handler does not run merchant request payload verification or `merchantSignatureVerificationV2`. If your deployment, gateway, or future route configuration enforces merchant authentication, failures use standard Newton auth bodies.

Missing, invalid, or mismatched credentials:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

SDK/profile style auth failure where that wrapper is enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Merchant API allowlist/blocklist failure if shared merchant-signature middleware is applied upstream:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Do not retry these unchanged. Fix credentials, gateway configuration, allowlist/IP configuration, or API enablement first.

### Response Security Configuration Failures

If a client sends response-encryption headers that cause this GET wrapper to choose a response mode that requires context not established by the route, Newton can fail before returning the PSP list.

Concrete failure body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Use only the response security mode enabled for this endpoint during onboarding.

### PSP List Lookup and NPCI Fallback Failures

When Redis is empty/missing and Newton cannot obtain a usable list from NPCI, the current client-facing body is:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

This covers the following discovered product-path cases:

- Redis has no PSP list or an empty PSP list, and NPCI `ReqListPsp` returns a non-`SUCCESS` result.
- NPCI immediate failure or timeout while waiting for `RespListPsp`.
- NPCI response cannot be decoded into `RespListPsp`.
- NPCI returns `SUCCESS` but omits `PspList.Psp`.
- Redis write fails while caching the refreshed PSP list.
- Runtime configuration needed for the fallback call is unavailable.

The helper captures upstream error code/message internally, but `pspListNotFoundInRedis` collapses the client-facing response to `INTERNAL_SERVER_ERROR` when it cannot return a list.

### Low-Level NPCI Request Signing Failure

A low-level XML signing failure in the NPCI request path throws a generic HTTP 200 server error before the List PSP helper converts it to Newton's JSON error body. The concrete body from that helper is:

```text
OK
```

Treat a non-JSON or otherwise unusable response body as a failed call, retry with backoff if appropriate, and escalate with the request id and timestamp if it persists.

### Unexpected Errors

Unexpected server, Redis, configuration, serialization, encryption, or monitoring failures generally use:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Client Handling and Retry Guidance

- Treat any successful body containing `psps` as a complete PSP-list snapshot.
- Cache the list on the merchant side. Refresh on a schedule, during backend startup, or when downstream UPI flows indicate stale PSP metadata.
- Do not infer live PSP outage from this API. It is a catalogue/cache endpoint, not a real-time PSP health check.
- Do not require `versionSupported`; handle it as optional.
- Treat `active` as a string copied from NPCI/Redis.
- Safe to retry with backoff: transport timeout, no response, HTTP `5xx`, `INTERNAL_SERVER_ERROR`, or a non-JSON/unusable response body.
- Safe to retry because this GET has no customer or transaction side effect. The only server-side side effect is cache refresh on a Redis miss.
- Do not retry unchanged: wrong method/path, malformed request envelope, onboarding/auth failures, `API NOT ENABLED`, or response security mode mismatch.
- If the endpoint repeatedly fails, keep using the last known good merchant-side PSP cache if it is still within your operational freshness window, and escalate to Newton with `x-request-id`, response timestamp, merchant/channel identifiers if sent, and the response body.

## Source References

- API route prefix and `{apiVersion}` capture: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- List PSP route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:320)
- GET route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2176)
- Default GET response wrapper and headers: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4888)
- Response envelope type: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:69)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:814)
- Response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1522)
- Response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3586)
- Product cache-first route: [src/Newton/Product/Merchant/Psp/ListPsp.hs](../../src/Newton/Product/Merchant/Psp/ListPsp.hs:15)
- NPCI request builder, response handling, and fallback errors: [src/Newton/Product/Merchant/Psp/Helper.hs](../../src/Newton/Product/Merchant/Psp/Helper.hs:25), [src/Newton/Product/Merchant/Psp/Helper.hs](../../src/Newton/Product/Merchant/Psp/Helper.hs:43), [src/Newton/Product/Merchant/Psp/Helper.hs](../../src/Newton/Product/Merchant/Psp/Helper.hs:75)
- Redis PSP cache helpers and TTL source: [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs:72), [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs:593)
- NPCI `ReqListPsp`, `RespListPsp`, `PspList`, and `Psp` types: [src/Newton/External/NPCI/Types/Meta.hs](../../src/Newton/External/NPCI/Types/Meta.hs:413), [src/Newton/External/NPCI/Types/Meta.hs](../../src/Newton/External/NPCI/Types/Meta.hs:437), [src/Newton/External/NPCI/Types/Meta.hs](../../src/Newton/External/NPCI/Types/Meta.hs:463), [src/Newton/External/NPCI/Types/Meta.hs](../../src/Newton/External/NPCI/Types/Meta.hs:477)
- NPCI List PSP client call: [src/Newton/External/NPCI/Flow.hs](../../src/Newton/External/NPCI/Flow.hs:615), [src/Newton/External/NPCI/Flow.hs](../../src/Newton/External/NPCI/Flow.hs:1252)
- Version metadata conversion: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:2561), [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:469)
- Shared request payload verification used by POST S2S APIs but not invoked by this GET handler: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Shared merchant signature, API enablement, timestamp, and IP allowlist middleware used by POST S2S APIs but not invoked by this GET handler: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Standard internal-error constant and generic HTTP 200 helper: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [src/Newton/Utils/API.hs](../../src/Newton/Utils/API.hs:44)
