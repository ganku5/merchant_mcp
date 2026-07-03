# List Sub Merchants API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/sub/list`

## Overview

List Sub Merchants is a merchant server-to-server API used by an aggregator or parent merchant to fetch the sub-merchants onboarded under it.

The API returns a paginated list of sub-merchant identifiers and the total number of matching sub-merchants. It is read-only: it does not create, update, enable, disable, or migrate any sub-merchant.

Payloads use Newton's standard server-to-server request and response envelope. The examples below show decrypted business JSON for readability.

## Business Use Case

Use this API when the parent merchant backend needs to:

- Display sub-merchants onboarded under the aggregator.
- Page through a large sub-merchant base for an operations console or reconciliation job.
- Filter the list by enabled/disabled status before calling sub-merchant info, update, or migration APIs.
- Reconcile Newton's sub-merchant records with the merchant's own onboarding system.

## Integration Flow

1. Parent merchant backend chooses the page size, offset, and optional enabled-state filter.
2. Merchant wraps the business payload using the S2S transport mode configured during onboarding: plain JSON with merchant signature, JWS, or JWE containing a signed payload.
3. Merchant calls `POST /api/{apiVersion}/merchants/sub/list` with merchant headers and timestamp.
4. Newton verifies the envelope, merchant identity, request signature, API access configuration, timestamp, and IP allow-list when configured.
5. Newton confirms that the authenticated merchant is an aggregator.
6. Newton queries sub-merchants by parent merchant id, applies `limit`, `offset`, and optional `enabled`, then counts all matching sub-merchants.
7. Merchant decrypts/verifies the response and reads `payload.subMerchants` and `payload.subMerchantsCount`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/sub/list
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment assigned during onboarding, for example `v1`. This endpoint's business logic does not branch on the path version. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON before any configured JWS/JWE wrapping. |
| `x-merchant-id` | Yes | Parent merchant id configured in Newton. |
| `x-merchant-channel-id` | Yes | Parent merchant channel id configured in Newton. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness for normal environments. |
| `x-merchant-signature` | Conditional | Required when sending a plain unsigned business payload. The signature is calculated over merchant id, merchant channel id, optional sub-merchant headers, timestamp, and the exact raw request body. |
| `x-sub-merchant-id` | Conditional | Only for integrations explicitly configured to authenticate through sub-merchant headers. For this API, the useful result set is still the parent aggregator's sub-merchant list. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` when sub-merchant header routing is enabled. |
| `x-forwarded-for` | Conditional | Required when Newton has `whitelistedIps` configured for the merchant. The first IP in the header must be allow-listed. |
| `x-request-id` | No | Optional tracing id. Newton generates one when omitted. |
| `x-session-id` | No | Optional tracing/session id. If omitted, Newton uses `x-request-id` or a generated id. |

### Authentication and Envelope

The route accepts Newton's common `EncRequest` transport:

| Transport mode | On-wire JSON shape | Requirements |
| --- | --- | --- |
| Plain JSON | The decrypted business payload directly. | Requires `x-merchant-signature`, `x-timestamp`, and the exact raw body used for signing. Payload `iat` is not required for this mode. |
| JWS | `payload`, `signature`, `protected`. | Newton verifies the key id and JWS signature. The decrypted business payload must include `iat`. |
| JWE | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`. | Newton decrypts the JWE using PSP key material and expects the decrypted content to be a signed payload. The decrypted business payload must include `iat`. |

For signed or encrypted request bodies, send `iat` as a fresh 13-digit epoch-millisecond timestamp within the freshness window shared during onboarding. Response wrapping follows the merchant's configured response strategy; examples in this guide show the decrypted response body.

## Request Body

### Default Page

Send an empty business payload to fetch the first page of all sub-merchants.

```json
{}
```

With no pagination fields, Newton uses `limit = 20` and `offset = 0`.

### Paginated Request

```json
{
  "limit": 50,
  "offset": 0
}
```

### Filter by Enabled State

```json
{
  "limit": 25,
  "offset": 50,
  "enabled": "true"
}
```

### Signed or Encrypted Request

When using JWS or JWE, include `iat` inside the decrypted business payload.

```json
{
  "limit": 25,
  "offset": 0,
  "enabled": "false",
  "iat": "1764660330000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `limit` | integer | No | Defaults to `20` in product logic. | Must be zero or a positive integer when supplied. `0` is accepted and returns no rows while still returning the matching count. | Maximum number of sub-merchants to return in this page. |
| `offset` | integer | No | Defaults to `0` in product logic. | Must be zero or a positive integer when supplied. | Number of matching rows to skip before returning the page. Use with `limit` for pagination. |
| `enabled` | string | No | If omitted, Newton returns both enabled and disabled sub-merchants. | Must be `"true"` or `"false"`; validation is case-insensitive. | Filters sub-merchants by enabled status. |
| `iat` | string | Conditional | No business default. Ignored by product logic. | Required for JWS/JWE request envelopes and validated as a timestamp before product logic. Not required for plain signed payload mode. | Issued-at timestamp for signed/encrypted S2S request validation. |

There are no nested request objects for this API.

## Validation Rules

- The authenticated merchant must resolve from the supplied merchant headers, or from explicitly configured sub-merchant header routing.
- The effective merchant used by product logic must be an aggregator. Non-aggregator merchants are rejected.
- `limit`, when present, must be `>= 0`.
- `offset`, when present, must be `>= 0`.
- `enabled`, when present, must be a boolean string: `"true"` or `"false"` in any letter case.
- For JWS/JWE requests, `iat` is mandatory and must pass timestamp validation.
- For plain JSON requests, `x-merchant-signature`, `x-timestamp`, and the exact signed raw body must be valid.
- If the merchant has API access restrictions, `listSubMerchant` must not be blocked and must be present in the allowed API set when an allow-list is configured.
- If `whitelistedIps` is configured, the first IP in `x-forwarded-for` must be allow-listed.

## Response

### Success Example

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "subMerchants": [
      {
        "subMerchantId": "SUBMERCHANT001",
        "subMerchantChannelId": "SUBMERCHANTAPP"
      },
      {
        "subMerchantId": "SUBMERCHANT002",
        "subMerchantChannelId": "SUBMERCHANTAPP"
      }
    ],
    "subMerchantsCount": 128
  }
}
```

### Empty Page Example

If no rows match the filter or the requested offset is beyond the result set, Newton returns an empty list and the count for the filter.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "subMerchants": [],
    "subMerchantsCount": 0
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `"SUCCESS"` for a successful list operation. |
| `responseCode` | string | `"SUCCESS"` for a successful list operation. |
| `responseMessage` | string | `"SUCCESS"` for a successful list operation. |
| `payload` | object | Business payload. Present on success. |
| `payload.subMerchants` | array of objects | Page of sub-merchants after applying `enabled`, `limit`, and `offset`. |
| `payload.subMerchants[].subMerchantId` | string | Sub-merchant id configured/onboarded under the parent merchant. |
| `payload.subMerchants[].subMerchantChannelId` | string | Sub-merchant channel id. |
| `payload.subMerchantsCount` | integer | Total count of sub-merchants matching the `enabled` filter, independent of `limit` and `offset`. Use this to decide whether another page exists. |

This API does not return detailed sub-merchant profile fields such as VPA, account, MCC, callback URLs, or configurations. Use the sub-merchant info API for one sub-merchant's detailed record.

## Failure Scenarios

Failure responses may be returned inside the configured encrypted/signed response envelope or directly by an authentication/parsing layer. The examples below show decrypted response bodies where the code constructs a JSON error body.

### Request Validation Failure

Invalid `enabled`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "BoolStringValidation \"Parameter is not true or false\""
}
```

Negative `limit` or `offset`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Expected Positive Integer, found -1\""
}
```

Client handling: fix the request payload. Do not retry the same body.

### Missing or Invalid `iat` for JWS/JWE

Signed or encrypted requests are rejected before product logic if `iat` is omitted or stale.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Client handling: regenerate the signed/encrypted payload with a fresh `iat`.

### Authentication, Signature, Encryption, or IP Failure

Missing merchant headers, unknown merchant credentials, missing `x-timestamp`, missing or mismatched `x-merchant-signature`, failed JWS verification, failed JWE decryption, or IP allow-list failure can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Malformed encrypted content that decrypts but is not a signed payload can return an invalid-data parsing body, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: parsing Newton.Types.API.RequestBody.SignedBody failed"
}
```

Client handling: verify merchant ids, key id, raw-body canonicalization, timestamp freshness, signature/encryption construction, and source IP allow-listing. Do not replay an old signed or encrypted body after the timestamp window.

### API Blocked or Not Allowed

If merchant configuration blocks this API or an allow-list is configured and does not include `listSubMerchant`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: ask Newton to enable `listSubMerchant` for the parent merchant or applicable sub-merchant configuration. Do not retry until configuration is fixed.

### Merchant Is Not an Aggregator

If the authenticated merchant is not marked as an aggregator, the API is rejected:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_MERCHANT",
  "responseMessage": "INVALID_MERCHANT"
}
```

Client handling: call this API only with parent aggregator credentials. A normal merchant or a standalone sub-merchant should not use this endpoint to list peers.

### Merchant or Sub-Merchant Header Resolution Failure

If required merchant headers are absent, the merchant cannot be found, the sub-merchant header pair is incomplete, or the sub-merchant does not belong to the resolved parent merchant, the request is rejected during authentication. The common decrypted body is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: use the parent aggregator's `x-merchant-id` and `x-merchant-channel-id` unless Newton has explicitly onboarded a different header-routing pattern for your integration.

### Database or Internal Error

Internal failures while loading merchant configuration, querying sub-merchants, counting results, or building the response can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with backoff only after confirming the request and auth material are unchanged and valid. Include `x-request-id` when raising the issue to Newton support.

## Idempotency, Retries, and Pagination

This is a read-only API and does not create an idempotency record. Retrying the same valid request is safe, but results can change if sub-merchants are added, updated, enabled, disabled, or migrated between calls.

Recommended client behavior:

- Use a stable `limit` and increment `offset` by the number of rows requested, not by `subMerchantsCount`.
- Stop when `offset + returned subMerchants.length >= subMerchantsCount` or when the returned list is empty.
- For signed/encrypted retries, regenerate `iat`, `x-timestamp`, and the request signature/envelope. Do not replay stale signed material.
- Retry transient `INTERNAL_SERVER_ERROR` responses with exponential backoff.
- Do not retry validation, authentication, API-not-enabled, or non-aggregator failures until the request or configuration is corrected.

## Source References

- Route and middleware sequence: [SubMerchant.hs](../../src/Newton/App/Routes/SubMerchant.hs:37)
- Request, response, payload, and sub-merchant list item types: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3133)
- Request validation call: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:673)
- S2S-to-core request and response mapping: [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1116)
- Aggregator check, defaults, filter, query, and count logic: [SubMerchant.hs](../../src/Newton/Product/Merchant/SubMerchant/SubMerchant.hs:110)
- Aggregator failure and response payload construction helpers: [Helper.hs](../../src/Newton/Product/Merchant/SubMerchant/Helper.hs:58)
- Sub-merchant queries and count: [Merchant.hs](../../src/Newton/Storage/QueriesMiddleware/Merchant.hs:114)
- Common request envelope shapes: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- S2S payload verification, JWS/JWE handling, and merchant context setup: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, timestamp, and IP allow-list checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
