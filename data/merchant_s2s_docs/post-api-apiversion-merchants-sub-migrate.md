# Migrate Sub-Merchant API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/sub/migrate`

## Overview

Migrate Sub-Merchant is a merchant server-to-server API used to move one existing sub-merchant from its current parent merchant to another parent merchant in Newton.

The caller authenticates as the current parent merchant and identifies the sub-merchant to move through sub-merchant headers. The request body identifies the destination parent merchant. On success, Newton updates the sub-merchant's parent merchant id, stores the previous parent id and migration timestamp in the sub-merchant store, clears the sub-merchant merchant-cache entries, and returns the standard success response.

Payloads use Newton's standard server-to-server request and response envelope. Examples in this guide show decrypted business JSON for readability.

## Business Use Case

Use this API when a merchant backend needs to:

- Transfer a sub-merchant from one parent or aggregator record to another parent merchant.
- Preserve the same sub-merchant, VPA, callbacks, primary merchant account, and customer/account linkage while changing its parent relationship.
- Move sub-merchants during aggregator restructuring, channel migration, or parent merchant consolidation.
- Repair parent/sub-merchant ownership after onboarding data has been moved in the merchant's own system.

Important identity roles:

| Role | Sent in | Description |
| --- | --- | --- |
| Current parent merchant | `x-merchant-id`, `x-merchant-channel-id` headers | The merchant that currently owns the sub-merchant. Newton validates that the sub-merchant headers belong to this merchant before migration. |
| Sub-merchant being migrated | `x-sub-merchant-id`, `x-sub-merchant-channel-id` headers | The existing sub-merchant row whose parent merchant id is updated. |
| Destination parent merchant | `newMerchantId`, `newChannelId` request fields | The merchant to which the sub-merchant is moved. |

## Integration Flow

1. Merchant backend chooses the sub-merchant to migrate and the destination parent merchant.
2. Merchant wraps the business payload using the S2S transport mode configured during onboarding: plain JSON with merchant signature, JWS, or JWE containing a signed payload.
3. Merchant calls `POST /api/{apiVersion}/merchants/sub/migrate` with current-parent merchant headers and sub-merchant headers.
4. Newton decrypts/verifies the request, resolves the current parent merchant, resolves the sub-merchant, and validates that the sub-merchant belongs to the current parent.
5. Newton validates request body fields and request freshness/signature/IP/API access.
6. Newton resolves the destination parent merchant from `newMerchantId` and `newChannelId`.
7. Newton updates the sub-merchant's parent id and store metadata, fetches the sub-merchant's primary merchant account and callbacks, and clears cached merchant data.
8. Merchant decrypts/verifies the response and confirms `status = "SUCCESS"`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/sub/migrate
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment mounted under `/api/{apiVersion}`. The migration business logic does not branch on this path value. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON before any configured JWS/JWE wrapping. |
| `x-merchant-id` | Yes | Current parent merchant id. This is not the destination parent. |
| `x-merchant-channel-id` | Yes | Current parent merchant channel id. |
| `x-sub-merchant-id` | Yes | Existing sub-merchant id to migrate. Required because product logic reads the sub-merchant from request context. |
| `x-sub-merchant-channel-id` | Yes | Existing sub-merchant channel id. Required with `x-sub-merchant-id`. |
| `x-timestamp` | Yes | Request timestamp used by merchant signature validation. Send a 13-digit Unix epoch timestamp in milliseconds within 30 minutes of Newton server time. |
| `x-merchant-signature` | Conditional | Required for plain JSON requests. The signature is calculated over `x-merchant-id + x-merchant-channel-id + x-sub-merchant-id + x-sub-merchant-channel-id + x-timestamp + rawBody`. |
| `x-forwarded-for` | Conditional | Required when Newton has `whitelistedIps` configured for the merchant. The first IP in the header must be allow-listed. |
| `x-api-version` | Recommended | Version header assigned during onboarding. This endpoint does not use it for response branching, but sending it consistently is recommended. |
| `x-request-id` | Optional | Request id for tracing. If omitted, Newton generates one and returns it in response headers. |
| `x-session-id` | Optional | Session id for tracing. If omitted, Newton uses `x-request-id`. |

### Auth, Encryption, And Signing

The route accepts Newton's common `EncRequest` forms:

| Transport mode | On-wire JSON shape | Requirements |
| --- | --- | --- |
| Plain JSON | The decrypted business payload directly. | Requires valid current-parent merchant headers, sub-merchant headers, `x-timestamp`, and `x-merchant-signature`. |
| JWS | `payload`, `signature`, `protected`. | Newton verifies the key id and JWS signature. The decrypted business payload must include `iat`. |
| JWE | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`. | Newton decrypts the JWE using PSP key material and expects the decrypted content to be a signed payload. The decrypted business payload must include `iat`. |

For JWS/JWE requests, `iat` is mandatory in the decrypted business payload and must be a fresh 13-digit epoch-millisecond timestamp. Plain JSON requests do not require `iat`, but still require `x-timestamp`.

On success, Newton returns `EncResponse`. Depending on the merchant response strategy, the transport body can be:

- Plain JSON response with `X-Response-Signature`.
- JWS signed response.
- JWE encrypted response containing a signed response.

Success and failure examples below show the decrypted underlying business body.

## Request

### Minimum Request

```json
{
  "newMerchantId": "DEST_PARENT_001",
  "newChannelId": "APP"
}
```

Use headers to identify the current parent and sub-merchant:

```http
x-merchant-id: CURRENT_PARENT_001
x-merchant-channel-id: APP
x-sub-merchant-id: SUBMERCHANT001
x-sub-merchant-channel-id: APP
```

### Signed Or Encrypted Request

When using JWS or JWE, include `iat` inside the decrypted business payload.

```json
{
  "newMerchantId": "DEST_PARENT_001",
  "newChannelId": "APP",
  "iat": "1782987330000"
}
```

### Request With `subMerchantVpa`

`subMerchantVpa` is accepted and validated when present, but the migration logic does not use it to select, verify, or update the sub-merchant. The sub-merchant selected for migration is the one resolved from `x-sub-merchant-id` and `x-sub-merchant-channel-id`.

```json
{
  "newMerchantId": "DEST_PARENT_001",
  "newChannelId": "APP",
  "subMerchantVpa": "submerchant001@bank",
  "iat": "1782987330000"
}
```

### Field Reference

| Field | Type | Required | Validation | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- | --- |
| `newMerchantId` | string | Yes | 1 to 256 characters. Allowed characters: letters, numbers, space, underscore, plus, dot, and hyphen. | No default. | Destination parent merchant id. Newton resolves this with `newChannelId` before updating the sub-merchant parent. |
| `newChannelId` | string | Yes | Same validation as `newMerchantId`. | No default. | Destination parent merchant channel id. |
| `subMerchantVpa` | string | No | If supplied, 3 to 255 characters and must match `local-part@handle`, where both parts may contain letters, numbers, dot, and hyphen. | No default. Omitted is accepted. | Optional VPA value. The code validates it but does not use it in the migration update. |
| `iat` | string | Conditional | Required for JWS/JWE requests. Must be a 13-digit Unix epoch timestamp in milliseconds and within 30 minutes of Newton server time. | Not used by product logic. Not required for plain JSON request mode. | Issued-at timestamp for signed/encrypted request freshness. |

There are no nested request objects for this API.

## Validation Rules

- `x-merchant-id` and `x-merchant-channel-id` must identify the current parent merchant.
- `x-sub-merchant-id` and `x-sub-merchant-channel-id` must identify an existing sub-merchant.
- The sub-merchant from the headers must currently belong to the merchant from the parent headers. Otherwise Newton rejects the request before migration.
- `newMerchantId` and `newChannelId` are mandatory destination-parent identifiers and must pass merchant id validation.
- `subMerchantVpa`, when present, must pass VPA validation. It is not otherwise used by migration logic.
- For plain JSON requests, the merchant signature must be valid for the exact raw request body and headers.
- For JWS/JWE requests, `iat` must be present and valid.
- `x-timestamp` must be valid and fresh for all modes after signature middleware runs.
- If the merchant has API access restrictions, `migrateSubMerchant` must not be blocked and must be in the allowed API set when an allow-list is configured.
- If `whitelistedIps` is configured, the first IP in `x-forwarded-for` must be allow-listed.

Implementation notes that affect clients:

- The migration route does not call the sub-merchant aggregator check used by some other sub-merchant APIs.
- The destination merchant lookup uses merchant id and channel id and does not require the destination merchant to be enabled in that lookup.
- The database update uses an enabled-row filter and ignores the optional update result. If the identified sub-merchant row is disabled, the endpoint can complete successfully while the update is a no-op. Confirm the destination relationship after migration if this case matters for your operation.

## Response

### Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS"
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when migration processing completes. |
| `responseCode` | string | `SUCCESS` for successful processing. |
| `responseMessage` | string | `SUCCESS` for successful processing. |

The response has no payload and does not echo the destination parent or sub-merchant identifiers.

## Failure Scenarios

Failures use the same response envelope when the request reaches route response handling. Some transport, JSON decode, authentication, and decryption failures can occur before Newton can build the merchant-configured encrypted response; clients should handle both encrypted Newton error bodies and plain HTTP error bodies according to onboarding guidance.

### Request Validation Errors

Invalid destination merchant id or channel id returns `BAD_REQUEST`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantId length not between 1 and 256\""
}
```

Invalid characters in `newMerchantId` return a validation message for `merchantId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantId is not alphanumeric\""
}
```

Invalid characters in `newChannelId` return a validation message for `merchantChannelId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantChannelId is not alphanumeric\""
}
```

Invalid `subMerchantVpa` returns VPA validation failure:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantVpa regex failed\""
}
```

Malformed JSON, missing required JSON fields, or a signed payload that cannot be decoded can fail before business validation. For JWS payload decode errors, Newton returns `INVALID_DATA` with the parser message:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

### Timestamp And Freshness Errors

Invalid timestamp format returns `BAD_REQUEST`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired `x-timestamp` or `iat` returns:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Missing `iat` for JWS/JWE requests is surfaced as invalid data:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

### Authentication, Signature, And Encryption Errors

Missing merchant headers, missing `x-timestamp`, missing raw body context, invalid plain-payload signature, failed JWS verification, failed JWE decryption, or an IP allow-list mismatch can return `UNAUTHORIZED`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If `blockedApiNames` blocks this API, or if an allowed-API list is configured and does not include `migrateSubMerchant`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If encrypted payload parsing fails after decryption, Newton can return `INVALID_DATA` with the parser message:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"subMerchantVpa\" not found"
}
```

### Merchant And Sub-Merchant Identity Errors

If the current parent merchant headers do not resolve, or the sub-merchant headers point to a merchant record that does not exist, Newton returns `UNAUTHORIZED`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the sub-merchant headers identify a sub-merchant that does not belong to the current parent merchant headers, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Submerchant does not belong to the specified merchant"
}
```

If the destination parent merchant identified by `newMerchantId` and `newChannelId` is not found, the lookup path returns `UNAUTHORIZED`:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If sub-merchant headers are omitted, the initial merchant resolution can still succeed, but migration product logic cannot find the sub-merchant context and returns an internal error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Internal Or Data-Consistency Errors

Newton can return `INTERNAL_SERVER_ERROR` if required internal data for the sub-merchant is missing or inconsistent, including:

- Sub-merchant store is missing.
- Sub-merchant store cannot be parsed.
- Primary merchant account for the sub-merchant is missing.
- Merchant account VPA cannot be decrypted.
- Cache, database, or unexpected infrastructure errors occur while completing the migration or cache invalidation.

Example:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Idempotency, Retries, And Client Handling

This API does not take an idempotency key and does not create an idempotency record.

A successful migration changes the sub-merchant's parent relationship. Retrying the exact same request with the old current-parent headers after success can fail with `Submerchant does not belong to the specified merchant`, because the sub-merchant now belongs to the destination parent.

Recommended client handling:

- Treat `SUCCESS` as completion of the migration attempt, then verify with sub-merchant lookup/list APIs under the destination parent when operational certainty is required.
- If the client times out after sending the request, first check whether the sub-merchant is visible under the destination parent before retrying.
- If a retry is needed after confirming the current parent has already changed, send headers for the sub-merchant's current parent rather than the old parent.
- Do not rely on `subMerchantVpa` for idempotency or selection. The selected sub-merchant is determined by sub-merchant headers.
- For disabled sub-merchants, confirm the migration result through a read path or operational tooling because the update predicate only updates enabled rows.

## Source References

- Route and middleware sequence: [SubMerchant.hs](../../src/Newton/App/Routes/SubMerchant.hs:118)
- Sub-merchant route declaration: [SubMerchant.hs](../../src/Newton/App/Routes/SubMerchant.hs:42)
- Request envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request verification and merchant/sub-merchant context setup: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Signature, timestamp, API access, and IP checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request/response types and validation: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3202)
- Transformer route and request mapping: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:688), [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1108)
- Product migration logic: [SubMerchant.hs](../../src/Newton/Product/Merchant/SubMerchant/SubMerchant.hs:124)
- Core migration request type: [Types.hs](../../src/Newton/Product/Merchant/SubMerchant/Types.hs:137)
- Merchant update behavior: [Merchant.hs](../../src/Newton/Storage/QueriesMiddleware/Merchant.hs:273), [Merchant.hs](../../src/Newton/Storage/Queries/Merchant.hs:79)
- Shared field validation: [Common.hs](../../src/Newton/Validation/Common.hs:320), [Common.hs](../../src/Newton/Validation/Common.hs:395)
- Timestamp validation: [DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
