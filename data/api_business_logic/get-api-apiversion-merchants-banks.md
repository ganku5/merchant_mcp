# Banks API Integration Guide

Source endpoint: `GET /api/{apiVersion}/merchants/banks`

## Overview

Banks is a server-to-server API used to fetch the bank/account-provider list that Newton currently knows about for UPI account discovery and downstream customer journeys.

The merchant backend calls this API when it needs to show a selectable bank list, map a customer-selected bank to the Newton `bankCode`, or refresh the merchant's local bank metadata before calling account-discovery APIs such as Fetch Accounts. Newton returns the bank display name, bank IIN/code, Newton reference id, and version or mobile-registration metadata when available.

This endpoint is intentionally read-only. It does not identify a customer, fetch customer accounts, link accounts, generate OTP, or initiate any payment movement.

## Business Use Case

Banks helps merchants:

- Build or refresh the bank-selection screen used before Fetch Accounts.
- Store the `code` value that downstream account APIs expect as `bankCode`.
- Display current bank names as returned by NPCI/Newton's bank cache.
- Read `versionSupported` when the merchant app needs to decide which UPI, account, or credential versions a bank advertises.
- Read `mobRegFormat` where enabled, usually for mobile-registration format handling.
- Recover from stale local bank metadata without shipping an app/backend config change.

Use this API during application startup, merchant backend cache warm-up, or before a bank-selection journey if the local bank cache is missing or stale. Do not call it for every customer screen render; cache the response on the merchant side and refresh periodically or when account discovery starts failing because of a stale bank code.

## Integration Flow

1. Merchant backend calls `GET /api/{apiVersion}/merchants/banks`.
2. Newton checks its Redis bank-list cache.
3. If Redis has a non-empty bank list, Newton uses that cached list.
4. If Redis is empty or missing, Newton calls NPCI `ReqListAccPvd`, syncs the bank table, refreshes the Redis `banks` cache, and returns the refreshed list.
5. Merchant stores the returned `banks[].code` values and uses the selected value as `bankCode` in account-discovery flows.

Important identifiers:

- `code`: Bank IIN/code. Use this as `bankCode` in account APIs such as Fetch Accounts.
- `ifsc`: Bank IFSC/root IFSC. Included only for `x-api-version > 0`.
- `referenceId`: Newton bank row/reference id. Store it only if your integration specifically needs Newton's bank reference id.

## Endpoint

```http
GET /api/{apiVersion}/merchants/banks
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Accept` | `application/json` |
| `x-api-version` | `1` or higher recommended when the client needs `ifsc`. Missing or non-numeric values fall back to `0`. |
| `x-request-id` | Optional merchant/request trace id. Newton generates one if omitted. |
| `x-session-id` | Optional session trace id. Newton uses `x-request-id` as the session id if omitted. |

### Authentication and Encryption

This route is a GET endpoint and does not accept an encrypted request body. In the current handler, Newton does not run the request-body payload verification or `merchantSignatureVerificationV2` middleware used by signed/encrypted POST S2S APIs.

Practical integration expectations:

- Send no request body.
- Do not send JWS/JWE request payload fields; there is no `EncRequest` for this route.
- Follow the network, gateway, allowlist, and credential requirements shared during onboarding for your environment.
- If your onboarding requires response signing or encryption through headers or an upstream gateway, apply that process around the HTTP response as configured. The business payload examples below show decrypted/plain JSON for readability.
- Do not set response-encryption headers that require a customer or merchant-customer context unless Newton has explicitly enabled that mode for this GET endpoint.

### Path, Query, and Header Parameters

| Name | Location | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | No default. | Route version segment. Use the value shared during onboarding. |
| `x-api-version` | header | integer string | No | Missing or non-numeric values are treated as `0`. | Response shaping version. `ifsc` is included only when this value is greater than `0`. |
| `x-request-id` | header | string | No | Newton generates a UUID if omitted. | Correlation id returned in response headers. |
| `x-session-id` | header | string | No | Defaults to the request id. | Session correlation id returned in response headers. |

This endpoint has no query parameters.

### Version Behavior

| `x-api-version` | Response behavior |
| --- | --- |
| Missing, non-numeric, or `0` | Base response. `ifsc` is omitted from every bank object. |
| `1` and above | `ifsc` is included for every bank object returned by Newton. |

`apiVersion` in the path selects the deployed route namespace. `x-api-version` controls the response fields described above.

## Request

### Required Minimum

```http
GET /api/2/merchants/banks
Accept: application/json
x-api-version: 1
x-request-id: BANKLIST20250101001
```

### Field Reference

Banks has no decrypted business request payload. There are no request fields, no nested request objects, and no request-body validators.

### Defaults and Omitted Field Behavior

- `x-api-version`: omitted or invalid values behave as `0`, so `ifsc` is omitted.
- Query parameters: ignored because the route defines none.
- Request body: not defined. Clients should not send one.
- Merchant/customer identifiers: not part of this route's business request.

## Request Examples

### Base Bank List

Use this when the merchant only needs bank names and bank codes.

```http
GET /api/2/merchants/banks
Accept: application/json
```

### Bank List With IFSC

Use this for new integrations that need IFSC/root IFSC metadata along with the bank code.

```http
GET /api/2/merchants/banks
Accept: application/json
x-api-version: 1
x-request-id: BANKLIST20250101002
```

### Cache Warm-Up From Backend

Use this as a scheduled or startup cache refresh from the merchant backend.

```http
GET /api/2/merchants/banks
Accept: application/json
x-api-version: 1
x-request-id: BANKLIST_CACHE_WARMUP_001
x-session-id: BANKLIST_CACHE_WARMUP
```

## Response

When the request completes normally, the response body contains only the `banks` array. This endpoint does not add top-level `status`, `responseCode`, or `responseMessage` fields on success.

### Success Response With `x-api-version: 1`

```json
{
  "banks": [
    {
      "name": "Example Bank",
      "ifsc": "EXAM0000001",
      "code": "123456",
      "upiEnabled": true,
      "referenceId": "BANK_REF_123",
      "mobRegFormat": "FORMAT1",
      "versionSupported": {
        "Version": [
          {
            "description": "UPI 2.0",
            "mandatory": "false",
            "no": "2.0"
          }
        ]
      }
    },
    {
      "name": "Sample Payments Bank",
      "ifsc": "SAMP0000001",
      "code": "654321",
      "upiEnabled": true,
      "referenceId": "BANK_REF_456"
    }
  ]
}
```

### Success Response With Missing or `0` `x-api-version`

`ifsc` is omitted when `x-api-version` is missing, non-numeric, or `0`.

```json
{
  "banks": [
    {
      "name": "Example Bank",
      "code": "123456",
      "upiEnabled": true,
      "referenceId": "BANK_REF_123"
    }
  ]
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `banks` | array of objects | Bank/account-provider records available to Newton. The array can be large; clients should cache it and search/filter locally. |

### `banks[]`

| Field | Type | Always present | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Bank display name from the Newton bank record, refreshed from NPCI when the cache is repopulated. |
| `code` | string | Yes | Bank IIN/code. Use this as `bankCode` in account-discovery APIs. |
| `upiEnabled` | boolean | Yes | Currently returned as `true` by the S2S transformer for every bank in this response. Treat presence in the list as the bank being available for the UPI bank-listing journey. |
| `referenceId` | string | Yes | Newton bank reference id. This is not the same as `code`. |
| `ifsc` | string | No | Bank IFSC/root IFSC. Included only when `x-api-version > 0`. |
| `mobRegFormat` | string | No | Mobile-registration format text. Included only when Newton configuration `addMobRegFormatInListBanksResponse` is enabled and the bank record has a value. |
| `versionSupported` | object | No | Version metadata parsed from the bank record. Omitted when NPCI/storage does not provide it or it cannot be parsed into Newton's supported version type. |

### `versionSupported`

| Field | Type | Description |
| --- | --- | --- |
| `Version` | object or array | NPCI version-supported data. It can be a single version object or an array depending on the stored NPCI payload. |

### `versionSupported.Version`

| Field | Type | Description |
| --- | --- | --- |
| `description` | string | Version description returned by NPCI/storage. |
| `mandatory` | string | Whether the version is marked mandatory, when supplied. |
| `no` | string | Version number. |

### Omitted and Default Response Fields

- `ifsc` is omitted for `x-api-version <= 0`.
- `mobRegFormat` is omitted unless both the Newton environment configuration and the bank record provide it.
- `versionSupported` is omitted if unavailable or unparsable.
- `bankHandle`, bank URL, SPOC fields, and NPCI internal fields are not exposed by this S2S response.
- `upiEnabled` is not copied from the stored text field in the current response transformer; it is always set to boolean `true`.
- A successful empty bank list is not expected from the fallback path. If both Redis and NPCI cannot produce a usable list, the current code returns an error instead.

## Error Handling

Failure responses generated by Newton carry `status`, `responseCode`, and `responseMessage`; concrete examples below show the common values clients should handle.

If `payload` is empty, it is omitted from the JSON response.

The HTTP status can vary by the layer that fails. The bank-list fallback path currently throws some lookup/downstream failures with HTTP `200` and a failure body, while framework, gateway, auth, or request parsing failures can use `400`, `401`, `404`, `405`, or `500`.

### Validation and Request Shape Failures

There are no business-field validation errors for this endpoint because it has no request body and no query parameters. Invalid or missing `x-api-version` does not fail the request; it falls back to version `0`.

Framework-level request-shape failures can still occur before the handler runs. The exact body is deployment dependent; when converted to Newton's standard error shape, it can look like this:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid request"
}
```

Clients should fix the URL, method, or gateway request shape instead of retrying unchanged.

### Auth, Signature, and Encryption Failures

The current `getBanks` handler does not invoke merchant request payload verification or merchant signature verification because it has no request body. If your deployment or gateway enforces S2S authentication for this endpoint, failures use the standard Newton auth bodies.

Missing, invalid, or mismatched credentials/signature:

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

Malformed encrypted/signed payload sent to a route or gateway that expects one:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload"
}
```

For this GET route, the normal client fix is to remove the request body/JWS/JWE payload and send the headers required by onboarding for this endpoint.

### Merchant Configuration Failures

The current route handler does not check merchant API allowlists/blocklists because it does not call `merchantSignatureVerificationV2`. If an upstream layer or future route configuration applies merchant API allowlist checks, the shared middleware returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Do not retry this unchanged. Ask Newton to enable the Banks/List Banks API for the merchant/channel or use the merchant credentials configured for this API.

### Lookup and Business Failures

Redis cache is empty, NPCI does not return a successful account-provider list, or the returned list cannot be used:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Current behavior note: `handleListBankResponse` captures NPCI error codes/messages internally, but `bankListNotFoundInRedis` collapses the client-facing response to `INTERNAL_SERVER_ERROR` when it cannot produce a bank list.

### Downstream, Cache, and Sync Failures

The same internal-server-error body is used when the fallback refresh path fails because of downstream or local infrastructure issues, including:

- NPCI `ReqListAccPvd` timeout or immediate failure.
- NPCI response decode failure.
- Missing `AccPvdList` or missing `AccPvd` in the NPCI response.
- Bank table upsert failure during sync.
- Redis write/delete failure while refreshing the bank cache.
- Passetto/encryption failure while encrypting stored bank SPOC data.

Example:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Unexpected Errors

Unexpected server, configuration, database, encryption, or cache failures also return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Client Handling and Retry Guidance

- Treat any successful body containing `banks` as a complete bank-list snapshot for the selected response version.
- Use `banks[].code` as the `bankCode` in Fetch Accounts and related account APIs.
- Cache the list on the merchant side. Refresh on a schedule, during backend startup, or when downstream account discovery suggests stale bank metadata.
- Use `x-api-version: 1` or higher if your client needs `ifsc`; otherwise the field is intentionally omitted.
- Do not infer bank downtime from this API. It lists available account providers; it is not a live per-bank health check.
- Retry with backoff for transport failures, `5xx`, and `INTERNAL_SERVER_ERROR` from this endpoint, especially when the Redis cache may be cold and Newton is refreshing from NPCI.
- Do not retry unchanged requests for wrong method/path, onboarding/auth failures, or `API NOT ENABLED`. Fix the route, credentials, gateway configuration, or merchant enablement first.
- If the endpoint repeatedly returns `INTERNAL_SERVER_ERROR`, keep using the last known good merchant-side bank cache if it is still within your operational freshness window, and escalate to Newton with `x-request-id` and timestamp.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:163)
- GET route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2158)
- Default GET response wrapper: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4888)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:307)
- Bank-list response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:322)
- Response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2711)
- Product bank-list route: [src/Newton/Product/Merchant/Bank/ListBanks.hs](../../src/Newton/Product/Merchant/Bank/ListBanks.hs:14)
- Redis cache helpers: [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs:579)
- NPCI fallback and bank sync helper: [src/Newton/Product/Merchant/Bank/Helper.hs](../../src/Newton/Product/Merchant/Bank/Helper.hs:23)
- Stored bank upsert mapping: [src/Newton/Storage/QueriesMiddleware/Bank.hs](../../src/Newton/Storage/QueriesMiddleware/Bank.hs:28)
- NPCI account-provider response type: [src/Newton/External/NPCI/Types/Meta.hs](../../src/Newton/External/NPCI/Types/Meta.hs:1216)
- `x-api-version` parsing: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:960)
- S2S envelope request/response types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Shared payload verification middleware used by POST S2S APIs: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Shared merchant signature and API enablement middleware used by POST S2S APIs: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Standard error helpers: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124)
