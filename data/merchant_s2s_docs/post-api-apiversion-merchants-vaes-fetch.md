# Fetch VAEs API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vaes/fetch`

## Overview

Fetch VAEs is a read-only server-to-server API used to fetch Newton's locally stored VAE/verified VPA directory for merchant-side sync workflows.

The merchant calls this API with pagination controls and, optionally, a `lastUpdatedTimestamp` cursor. Newton verifies the S2S envelope and merchant access, validates the request, reads active `VerifiedVpas` rows modified at or after the cursor, decrypts stored VPA addresses where required, and returns the requested page.

Use this API when the merchant backend needs to keep a local cache of verified VPA metadata such as VPA address, display name, logo URL, website URL, key code, key index, and public key. This API does not call NPCI directly in the request path; it reads the VAE records that Newton has already synced into storage.

Payloads use the standard Newton server-to-server encrypted request and response envelope. Examples below show decrypted business payloads for readability.

## Business Use Case

Fetch VAEs helps merchants:

- Sync the verified VPA/VAE directory from Newton in pages.
- Perform an initial full sync by omitting `lastUpdatedTimestamp`.
- Perform incremental syncs by sending the last processed modification timestamp.
- Cache VAE display metadata for customer-facing or risk/reconciliation workflows.
- Update or upsert local records using `id`, `addr`, `modifiedAt`, and `active`.
- Retry page fetches safely because the API is read-only.

This API does not create, update, remove, or validate a VAE. VAE creation/update/removal is handled by Newton's upstream VAE sync flows.

## Integration Flow

1. Merchant backend chooses a page size `limit` up to the configured maximum.
2. For the first full sync, merchant sends `offset: 0` and omits `lastUpdatedTimestamp`.
3. Newton uses the configured default cursor `1990-12-31T12:00:00Z`, counts matching active VAE rows, and returns page `0`.
4. Merchant processes `payload.vaeList` and requests the next page with the same `lastUpdatedTimestamp` and `offset + 1` while `offset + 1 < totalPages`.
5. After all pages for a cursor are processed, merchant stores the highest `modifiedAt` observed as the next incremental cursor.
6. For later incremental syncs, merchant sends that stored cursor in `lastUpdatedTimestamp`.
7. Merchant upserts returned rows locally and tolerates duplicate boundary rows because Newton filters with `modifiedAt >= lastUpdatedTimestamp`.

Important behavior:

- `offset` is a zero-based page number, not a raw row offset. Newton calculates the datastore offset as `offset * limit`.
- `limit` is required and must be greater than `0`.
- `totalPages` is calculated from the total matching row count and the requested `limit`.
- Rows are ordered by `modifiedAt` ascending.
- Only rows where `active` is `true` or not set are returned. Rows with `active: false` are excluded.
- `addr` is decrypted before it is returned when Passetto encryption is enabled.
- The count for a given `lastUpdatedTimestamp` can be served through Redis cache; clients should still treat each page response as current Newton state, not as a long-lived snapshot.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vaes/fetch
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. No endpoint-specific response shaping by `x-api-version` was found for this API. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds used for merchant signature freshness. Required by merchant signature verification. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding. Required for unsigned/plain business payload transport. |
| `x-forwarded-for` | Required only when IP allowlisting is configured for the merchant. |
| `x-request-id` | Optional request id for tracing. Newton generates one when omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |
| `x-sub-merchant-id` | Optional. Required only for configured sub-merchant routing. |
| `x-sub-merchant-channel-id` | Optional. Required only for configured sub-merchant routing. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. Depending on the configured transport, the request body can be a JWE envelope, a JWS body, or a plain business payload with merchant signature verification. Plain decrypted JSON payloads are accepted only in environments/configurations where that mode is explicitly enabled.

For encrypted or signed request bodies, include `iat` in the decrypted business payload. Newton validates `iat` as a 13-digit epoch-millisecond timestamp within its freshness window before running product logic. `iat` is separate from `lastUpdatedTimestamp`.

### Path and Version Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route version segment. Use the value shared during onboarding. |
| `x-api-version` | header | integer string | Recommended | Standard Newton S2S version header. This route does not use it for endpoint-specific response shaping in the reviewed code. |

## Request

### Required Minimum

Initial full sync, first page:

```json
{
  "offset": 0,
  "limit": 100
}
```

Incremental sync, first page:

```json
{
  "offset": 0,
  "limit": 100,
  "lastUpdatedTimestamp": "2026-07-02T10:30:00+05:30"
}
```

Encrypted or signed transport business body:

```json
{
  "offset": 0,
  "limit": 100,
  "lastUpdatedTimestamp": "2026-07-02T10:30:00+05:30",
  "iat": "1782968400000"
}
```

The `iat` value above is a concrete example for `2026-07-02T10:30:00+05:30`. In production, generate `iat` at request time so it is within Newton's accepted timestamp window.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `offset` | integer | Yes | No default. | Zero-based page number. Send `0` for the first page, `1` for the second page, and so on. Must be greater than or equal to `0`. Newton multiplies it by `limit` before querying storage. |
| `limit` | integer | Yes | No default. | Page size. Must be greater than `0` and less than or equal to the configured `FETCH_VAE_RESPONSE_MAX_PAGE_SIZE`. Current default maximum is `100` unless configured differently for the environment. |
| `lastUpdatedTimestamp` | string | No | Defaults to `1990-12-31T12:00:00Z`, which effectively requests all stored active VAE rows. | Incremental cursor. Newton returns rows where `modifiedAt >= lastUpdatedTimestamp`. For supplied values, use an ISO-style timestamp with offset such as `2026-07-02T10:30:00+05:30`. |
| `iat` | string | Conditional | No business default. Ignored by product validation for unsigned/plain payloads. | Issued-at timestamp for encrypted/signed request freshness validation. Required for JWE/JWS transport. Must be 13-digit epoch milliseconds and within Newton's timestamp window. |
| `udfParameters` | string | No | No default. Validated when supplied, but this API's response type does not echo it. | Merchant-defined metadata as a JSON-object string, for example `"{\"syncJobId\":\"VAE-20260702-01\"}"`. |

### Defaults and Omitted Field Behavior

There are no defaults for `offset` or `limit`; both must be sent.

Optional fields behave as follows:

- `lastUpdatedTimestamp`: omitted becomes `1990-12-31T12:00:00Z` in product logic, so the API fetches all active rows from the beginning of Newton's stored VAE data.
- `iat`: required only for encrypted/signed envelopes. It is not stored and is not returned.
- `udfParameters`: validated when supplied. It is not stored by this read-only API and is not present in the success response because `FetchVaeResponse` has no `udfParameters` field.

There are no nested business request objects for this API. The only nested objects are the standard S2S JWE/JWS envelope objects used for transport.

### Validation and Processing Behavior

- `offset` must be `0` or greater.
- `limit` must be greater than `0`.
- `limit` must not exceed `FETCH_VAE_RESPONSE_MAX_PAGE_SIZE`; the current default maximum is `100`.
- `lastUpdatedTimestamp`, when supplied, must parse as Newton's IST timestamp format, for example `2026-07-02T10:30:00+05:30`.
- `udfParameters`, when supplied, must be a JSON-object string and must pass Newton's UDF character validation.
- For encrypted/signed envelopes, `iat` must be a 13-digit epoch-millisecond timestamp and must be within the accepted freshness window.
- Newton calculates `pageOffset = offset * limit`.
- Newton counts matching VAE rows for the cursor, calculates `totalPages = ceiling(count / limit)`, and reads one page.
- Newton filters rows by `modifiedAt >= lastUpdatedTimestamp` and `active = true OR active IS NULL`.
- Newton returns rows ordered by `modifiedAt` ascending.
- Newton decrypts stored VPA addresses before building the response.

## Request Examples

### Initial Full Sync

Use this when the merchant does not yet have a local VAE cache.

```json
{
  "offset": 0,
  "limit": 100
}
```

### Next Page of the Same Sync

Use the same cursor and increment only `offset`.

```json
{
  "offset": 1,
  "limit": 100
}
```

Newton reads rows `100` through `199` for this request because `offset` is multiplied by `limit`.

### Incremental Sync

Use this after storing the highest `modifiedAt` from a completed previous sync.

```json
{
  "offset": 0,
  "limit": 50,
  "lastUpdatedTimestamp": "2026-07-02T10:30:00+05:30"
}
```

Because the comparison is inclusive, records with `modifiedAt` exactly equal to `2026-07-02T10:30:00+05:30` can be returned again. Upsert locally by stable identifiers such as `id` or `addr`.

### Sync With Merchant Metadata

Use `udfParameters` only if the merchant wants Newton request logs to carry a merchant-side sync reference. It is validated but not echoed in this API's response.

```json
{
  "offset": 0,
  "limit": 100,
  "lastUpdatedTimestamp": "2026-07-02T10:30:00+05:30",
  "udfParameters": "{\"syncJobId\":\"VAE-20260702-01\"}"
}
```

## Response

### Response Envelope

Successful decrypted business responses use this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when the fetch operation completed. |
| `responseCode` | string | `SUCCESS` when the fetch operation completed. |
| `responseMessage` | string | `SUCCESS` when the fetch operation completed. |
| `payload` | object | VAE fetch payload. Always present on success. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `totalPages` | integer | Number of pages for the requested cursor and `limit`. `0` means there are no matching VAE rows. |
| `vaeList` | array | VAE rows on the requested page, ordered by `modifiedAt` ascending. Empty when the page has no rows. |

### `vaeList[]`

Rows are serialized directly from Newton's `VerifiedVpas` storage type after decrypting `addr`.

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Newton storage id for the verified VPA row. |
| `addr` | string | VAE/verified VPA address. This is decrypted before being returned when stored encrypted. |
| `addrHash` | string | Hash of the VPA address. Omitted when not present in storage. |
| `logo` | string | Logo URL or logo reference from the VAE record. Omitted when not present. |
| `name` | string | Display name for the VAE/verified VPA. |
| `url` | string | Website or reference URL from the VAE record. Omitted when not present. |
| `code` | string | VAE key code. Omitted when not present. |
| `ki` | string | VAE key index/key identifier. Omitted when not present. |
| `publicKey` | string | Public key value associated with the VAE record. Omitted when not present. |
| `createdAt` | string | Newton local timestamp when the row was created. |
| `updatedAt` | string | Newton local timestamp when the row was last touched. |
| `modifiedAt` | string | Newton local timestamp used by this API's incremental cursor. Omitted only if absent in storage; rows with absent `modifiedAt` do not normally match the cursor filter. |
| `active` | boolean | `true` for active records. Omitted when the stored value is null. Rows with `active: false` are excluded from this API. |

### Success Response With VAEs

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "totalPages": 2,
    "vaeList": [
      {
        "id": "VAE001",
        "addr": "verified-store@upi",
        "addrHash": "8e7f4f8f2f3a9a3d5d6c7b8a9f001122",
        "logo": "https://merchant.example/assets/store-logo.png",
        "name": "Verified Store",
        "url": "https://merchant.example",
        "code": "KEY001",
        "ki": "2026-07",
        "publicKey": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AEXAMPLEKEY",
        "createdAt": "2026-07-01T09:00:00",
        "updatedAt": "2026-07-02T10:15:00",
        "modifiedAt": "2026-07-02T10:15:00",
        "active": true
      },
      {
        "id": "VAE002",
        "addr": "verified-brand@upi",
        "name": "Verified Brand",
        "createdAt": "2026-07-01T09:05:00",
        "updatedAt": "2026-07-02T10:25:00",
        "modifiedAt": "2026-07-02T10:25:00",
        "active": true
      }
    ]
  }
}
```

### Success Response With No Matching VAEs

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "totalPages": 0,
    "vaeList": []
  }
}
```

### Success Response for an Empty Page Beyond the Last Page

If a client asks for an `offset` greater than or equal to `totalPages`, Newton still returns a success response with an empty page.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "totalPages": 2,
    "vaeList": []
  }
}
```

### Interpreting Pagination and Cursors

- Continue requesting pages while `offset + 1 < totalPages`.
- Use the same `lastUpdatedTimestamp` for every page in one sync run.
- Stop when the requested page is the last page or when `vaeList` is empty unexpectedly.
- Store the maximum `modifiedAt` observed only after all pages for the cursor are processed.
- Because the cursor comparison is inclusive, deduplicate or upsert repeated records at the cursor boundary.
- If VAE rows change while a sync is in progress, `totalPages` and page contents can change on later requests. A follow-up incremental sync from the maximum processed `modifiedAt` will reconcile changes.

## Error Handling

Failure responses use the standard Newton S2S error body when an error body is produced by Newton. Depending on where the failure occurs, the HTTP status may be `200`, `400`, `401`, or `500`; clients should inspect the decrypted body whenever one is available.

General failure shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Value is not valid\""
}
```

The exact `responseMessage` for parser and validator errors can vary with the failing field and JSON parser text. The examples below show concrete bodies produced by the reviewed validators and error constants.

### Validation Failures

Validation runs before the VAE lookup.

Negative `offset`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Value is not valid\""
}
```

Zero or negative `limit`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Value is not valid\""
}
```

`limit` above the configured page-size maximum. This example assumes the default maximum of `100`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"limit field value is not between 0 and 100\""
}
```

Invalid `lastUpdatedTimestamp`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"timestamp value not valid\""
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

Missing type-level required fields or wrong JSON types can fail during JSON parsing before product validation. In signed payload decoding, a missing required field can surface as an invalid-data body similar to:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"limit\" not found"
}
```

For direct malformed HTTP JSON before the business payload is decoded, the HTTP layer can return a parser error without the normal encrypted business response. Treat parse failures as non-retryable until the payload is corrected.

### `iat` and Timestamp Failures

For encrypted/signed payloads, missing `iat` is rejected before product logic:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Malformed `iat` that is not a 13-digit epoch-millisecond timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired or future-skewed `iat` outside Newton's accepted freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

The `x-timestamp` header is validated separately during merchant signature verification and can return the same malformed or expired timestamp responses.

### Authentication, Encryption, and Signature Failures

Authentication failures occur before product logic runs. Common causes include missing/invalid merchant headers, failed JWE decryption, failed JWS verification, invalid merchant signature, missing raw body in the gateway pipeline, failed timestamp validation, or failed IP allowlist checks.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Merchant Configuration and Access Failures

Newton checks whether this API is blocked or allowed for the merchant before fetching VAEs. If the endpoint is disabled for the merchant or sub-merchant configuration, the response is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Contact Newton onboarding/support to enable the API or correct merchant configuration. Do not retry unchanged requests indefinitely.

### Storage, Cache, and Decryption Failures

This endpoint reads Newton storage, can use Redis for the count cache, and decrypts VPA addresses before returning them. Storage errors, Redis/cache errors that are not recoverable by the helper, or Passetto decryption failures can surface as:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Unexpected Errors

Unexpected failures in request processing, response signing/encryption, datastore access, cursor parsing after validation, or response construction use the standard internal-error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- This is a read-only API, so retrying the same request does not create duplicate server-side records.
- Retry transient `INTERNAL_SERVER_ERROR` failures with exponential backoff and the same `offset`, `limit`, and `lastUpdatedTimestamp`.
- Retry authentication failures only after correcting headers, signatures, encryption, key configuration, timestamp freshness, or IP allowlist configuration.
- Do not retry validation errors or `API NOT ENABLED` unchanged.
- Use the same cursor for all pages in one run. Changing `lastUpdatedTimestamp` mid-run can skip or duplicate rows.
- Upsert local VAE rows by `id` or `addr`, and use `modifiedAt` to decide whether a returned record is newer.
- Store the next cursor only after a sync run completes. If a run fails midway, restart that run from page `0` with the previous committed cursor.
- Because the cursor filter is inclusive, expect occasional duplicate rows at the boundary and handle them idempotently.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:625)
- Route handler and middleware chain: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3299)
- Request payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, timestamp, API access, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:168)
- Request and response types: [src/Newton/Types/API/ServerToServer/Vae.hs](../../src/Newton/Types/API/ServerToServer/Vae.hs:126), [src/Newton/Types/API/ServerToServer/Vae.hs](../../src/Newton/Types/API/ServerToServer/Vae.hs:156)
- Product fetch flow: [src/Newton/Product/FetchVae.hs](../../src/Newton/Product/FetchVae.hs:13)
- VAE query wrapper, cursor filter, and count: [src/Newton/Storage/QueriesMiddleware/VerifiedVpa.hs](../../src/Newton/Storage/QueriesMiddleware/VerifiedVpa.hs:105)
- Storage filter and ordering: [src/Newton/Storage/Queries/VerifiedVpa.hs](../../src/Newton/Storage/Queries/VerifiedVpa.hs:55), [src/Newton/Storage/Queries/VerifiedVpa.hs](../../src/Newton/Storage/Queries/VerifiedVpa.hs:148)
- Response row storage type and JSON omission behavior: [src/Newton/Types/Storage/VerifiedVpa.hs](../../src/Newton/Types/Storage/VerifiedVpa.hs:23), [src/Newton/Types/Storage/VerifiedVpa.hs](../../src/Newton/Types/Storage/VerifiedVpa.hs:52)
- Request validation and page-size validation wrappers: [src/Newton/Types/API/ServerToServer/Vae.hs](../../src/Newton/Types/API/ServerToServer/Vae.hs:145), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4690)
- Timestamp and UDF validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:623), [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:109), [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:400)
- Page-size and default cursor configuration: [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs:2511)
- Count cache and VPA address decryption: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:930), [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs:1173), [src/Newton/Utils/Passetto.hs](../../src/Newton/Utils/Passetto.hs:982)
- Shared success and error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:169), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
