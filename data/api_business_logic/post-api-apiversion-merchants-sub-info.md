# Sub-Merchant Info API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/sub/info`

## Overview

Sub-Merchant Info is a server-to-server lookup API for aggregator or parent merchants. Use it to fetch the current Newton record for one onboarded sub-merchant, including its VPA, primary account summary, MCC, enabled flag, callbacks, agent phone numbers, and selected sub-merchant configuration values.

The API does not create or mutate data. It reads the sub-merchant that belongs to the authenticated parent merchant and returns the latest stored values that Newton will use for sub-merchant UPI processing.

Payloads use the standard Newton S2S encrypted/signed request and response envelope. Examples below show the decrypted business payload for readability.

## Business Use Case

Use this API when the parent merchant backend needs to:

- Confirm that a sub-merchant has been onboarded under the parent merchant.
- Retrieve the sub-merchant VPA and primary settlement account summary after add/update flows.
- Check whether the sub-merchant is currently enabled.
- Reconcile callback URL and MCC configuration stored in Newton.
- Fetch response-visible configuration flags before enabling payment, refund, transaction status, mandate, or direct-pay journeys for the sub-merchant.

## Integration Flow

1. Parent merchant identifies the sub-merchant using the merchant-scoped `subMerchantId` and `subMerchantChannelId`.
2. Parent merchant sends a Newton S2S request envelope with merchant headers and request signature/encryption as configured during onboarding.
3. Newton decrypts/verifies the request, sets the parent merchant context, validates the timestamp/signature/IP/API permissions, and validates the business payload.
4. Newton checks that the authenticated merchant is an aggregator parent.
5. Newton looks up the sub-merchant under that parent, fetches merchant info, the primary merchant account, callbacks, and supported configuration fields.
6. Newton returns the response using the merchant's configured response transport: unsigned JSON with `X-Response-Signature`, JWS, or JWS-and-JWE.

## Endpoint

```http
POST /api/{apiVersion}/merchants/sub/info
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment mounted under `/api/{apiVersion}`. The route also reads `x-api-version` for version-gated response fields. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON, usually as the Newton S2S envelope. |
| `x-merchant-id` | Yes | Parent merchant id used to resolve the authenticated merchant. |
| `x-merchant-channel-id` | Yes | Parent merchant channel id used with `x-merchant-id`. |
| `x-timestamp` | Yes | Request timestamp used by merchant signature validation. Send a 13-digit Unix epoch timestamp in milliseconds; Newton accepts values within 30 minutes of server time. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payload requests outside allowed development bypasses. Signature input is `x-merchant-id + x-merchant-channel-id + x-sub-merchant-id + x-sub-merchant-channel-id + x-timestamp + rawBody`. For this endpoint, sub-merchant header values are usually absent, so they contribute empty strings. |
| `x-forwarded-for` | Conditional | Required when merchant configuration contains `whitelistedIps`; the first IP in the header must be in that configured list. |
| `x-api-version` | Recommended | Controls version-gated response mapping. Send the version assigned during onboarding. `configurations` is omitted for version `0` and included above version `0` when present. |
| `x-request-id` | Optional | Request id for tracing. If omitted, Newton generates one and returns it. |
| `x-session-id` | Optional | Session id for tracing. If omitted, Newton uses `x-request-id`. |

### Auth, Encryption, And Signing

The route accepts the standard `API.EncRequest` forms:

- JWE encrypted request containing a JWS signed payload.
- JWS signed request.
- Plain JSON payload only where the integration is configured to allow it.

For encrypted or signed requests, the decrypted business payload must include `iat`; Newton validates it as a 13-digit Unix epoch timestamp in milliseconds before processing. For plain unsigned payloads, `iat` is not required by the signature middleware, but new integrations should still include it when their onboarding spec requires it.

On success, Newton returns `API.EncResponse`. Depending on the merchant response strategy, the transport body can be:

- `UnSignedResponse` plus `X-Response-Signature`.
- `SignedResponse` as JWS.
- `EncryptedResponse` as JWE containing a signed response.

The success and failure JSON examples below show the decrypted underlying business body.

## Request

### Decrypted Request Body

```json
{
  "subMerchantId": "SUBMERCHANT001",
  "subMerchantChannelId": "APP",
  "iat": "1782987330000",
  "udfParameters": "{\"traceId\":\"lookup-123\"}"
}
```

### Minimum Request

```json
{
  "subMerchantId": "SUBMERCHANT001",
  "subMerchantChannelId": "APP"
}
```

There is only one meaningful request variant for this endpoint: lookup by `subMerchantId` and `subMerchantChannelId` within the authenticated parent merchant.

### Field Reference

| Field | Type | Required | Validation | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- | --- |
| `subMerchantId` | string | Yes | 1 to 256 characters; allowed characters are letters, numbers, space, underscore, plus, dot, and hyphen. | No default. | Merchant-scoped sub-merchant id supplied during sub-merchant onboarding. |
| `subMerchantChannelId` | string | Yes | Same validation as `subMerchantId`. | No default. | Merchant-scoped channel id for the sub-merchant. |
| `iat` | string | Conditional | For JWS/JWE requests, must be present, formatted as a 13-digit Unix epoch timestamp in milliseconds, and within 30 minutes of Newton server time. | Not used by validation for plain unsigned payloads. | Issued-at timestamp for signed/encrypted request freshness. |
| `udfParameters` | string | No | Must be a JSON object encoded as a string and must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick characters. | Omitted from response if not supplied. | Merchant metadata echoed in the success response. |

### Conditional Rules

- The authenticated caller must be the parent merchant. The sub-merchant is searched by parent merchant database id, `subMerchantId`, and `subMerchantChannelId`.
- The parent merchant must be configured as an aggregator. Non-aggregator merchants receive `INVALID_MERCHANT`.
- The lookup does not require the sub-merchant to be enabled; the code uses a lookup without enabled-status filtering and returns the current `enabled` flag.
- No request fields are defaulted by product logic for this endpoint.

## Response

### Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "PARENT001",
    "merchantChannelId": "WEB",
    "subMerchantId": "SUBMERCHANT001",
    "subMerchantChannelId": "APP",
    "vpa": "submerchant001@bank",
    "maskedAccountNumber": "XXXXXX1234",
    "ifsc": "HDFC0001234",
    "mcc": "5411",
    "enabled": "true",
    "callbackUrls": "{\"TRANSACTION\":\"https://merchant.example/callbacks/transactions\"}",
    "agentPhoneNumbers": [
      "9876543210"
    ],
    "configurations": [
      {
        "config": "BLOCK_DIRECT_PAY",
        "value": "false"
      },
      {
        "config": "ENABLE_SMS_NOTIFICATION",
        "value": "true"
      },
      {
        "config": "PAYER_ACC_TYPES_ALLOWED",
        "value": [
          {
            "accType": "SAVINGS",
            "limit": 50000,
            "limitType": "SMALL",
            "vpaHandles": [
              "okhdfcbank"
            ]
          }
        ]
      }
    ]
  },
  "udfParameters": "{\"traceId\":\"lookup-123\"}"
}
```

### Response Envelope Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful lookup. |
| `responseCode` | string | `SUCCESS` for successful lookup. |
| `responseMessage` | string | `SUCCESS` for successful lookup. |
| `payload` | object | Sub-merchant information. |
| `udfParameters` | string | Echoed only when supplied in the request. |

### Payload Fields

| Field | Type | Presence | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Always | Parent merchant id. |
| `merchantChannelId` | string | Always | Parent merchant channel id. |
| `subMerchantId` | string | Always | Requested sub-merchant id. |
| `subMerchantChannelId` | string | Always | Requested sub-merchant channel id. |
| `vpa` | string | Always | Decrypted primary VPA for the sub-merchant. |
| `maskedAccountNumber` | string | Always | Masked primary account number from the sub-merchant's primary merchant account. |
| `ifsc` | string | Always | IFSC from the sub-merchant's primary merchant account. |
| `mcc` | string | Always | Current MCC stored on the sub-merchant. |
| `enabled` | string | Always | `"true"` or `"false"` string derived from the sub-merchant enabled flag. |
| `callbackUrls` | string | Always | Serialized callback mapping produced from the sub-merchant callback rows. Empty or minimal content depends on stored callbacks. |
| `action` | string | Omitted | The shared response payload type has `action`, but this endpoint sets it to `Nothing`, so it is omitted. |
| `agentPhoneNumbers` | array of strings | Optional | Agent phone numbers from merchant info. Values may be decrypted first when Passetto is enabled. Omitted if missing or unparsable. |
| `configurations` | array of objects | Optional | Included only when `x-api-version` is above version `0` and at least one supported configuration exists. |

### `configurations[]`

Only these configuration entries are returned by this endpoint:

| `config` | `value` type | Description |
| --- | --- | --- |
| `BLOCK_DIRECT_PAY` | string | Lowercase string form of the `blockDirectPay` value in the sub-merchant store, for example `"true"` or `"false"`. |
| `ENABLE_SMS_NOTIFICATION` | string | Value of the sub-merchant merchant-configuration key `enableSmsNotification`. |
| `PAYER_ACC_TYPES_ALLOWED` | array of objects | Parsed value of merchant-configuration key `payerAccTypesAllowed`. |

### `PAYER_ACC_TYPES_ALLOWED.value[]`

| Field | Type | Presence | Description |
| --- | --- | --- | --- |
| `accType` | string | Always when configured | Payer account type name configured for the sub-merchant. |
| `limit` | number | Optional | Amount limit associated with the account type. |
| `limitType` | string | Optional | `SMALL` or `LARGE`. |
| `vpaHandles` | array of strings | Optional | Allowed VPA handles for this account type. |

## Failure Scenarios

Failure transport follows the same envelope strategy as success when the request reaches response wrapping. Some failures are thrown before a merchant response strategy can be selected and may be plain error JSON at the HTTP layer. In all cases, clients should decrypt/verify when an encrypted or signed envelope is returned, then inspect `status`, `responseCode`, and `responseMessage`.

### Request Validation Failure

Causes:

- Missing `subMerchantId` or `subMerchantChannelId`.
- Empty id, id longer than 256 characters, or unsupported characters.
- Invalid `udfParameters` string.

Underlying decrypted body:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantId length not between 1 and 256\""
}
```

Client handling: fix the request before retrying. Do not retry unchanged validation failures.

### Missing Or Invalid `iat`

For JWS/JWE requests, `iat` is required and must pass 13-digit millisecond timestamp validation.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "IAT is empty"
}
```

Client handling: send a fresh issued-at timestamp in the decrypted payload and ensure clock synchronization.

### Authentication, Signature, Or Encryption Failure

Causes:

- Missing merchant headers.
- Unknown merchant id/channel id.
- Invalid JWS signature or JWE decryption failure.
- Missing `x-merchant-signature` for plain unsigned payloads.
- Signature mismatch over the expected header/body string.
- Stale `x-timestamp`.

Underlying body commonly uses:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: do not blindly retry. Rebuild the envelope from the exact raw request body, use the onboarded keys, include all required merchant headers, and regenerate timestamps/signatures.

### API Disabled Or Not Allowed

Causes:

- Parent merchant configuration contains `blockedApiNames` with `listSubMerchantInfo`.
- Parent or sub-merchant allowed API configuration does not include `listSubMerchantInfo` when allowed APIs are enforced.

Underlying body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: contact Newton onboarding/operations to enable this API for the merchant configuration. Retrying unchanged requests will not help.

### IP Restriction Failure

When `whitelistedIps` is configured, Newton checks the first IP in `x-forwarded-for`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: call from an allowlisted egress IP and ensure the gateway forwards `x-forwarded-for` correctly.

### Caller Is Not An Aggregator Parent

The product logic requires the authenticated merchant to have aggregator mode enabled.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_MERCHANT",
  "responseMessage": "INVALID_MERCHANT"
}
```

Client handling: use the parent aggregator credentials assigned for sub-merchant APIs. A regular merchant credential cannot call this lookup.

### Sub-Merchant Not Found Under Parent

Newton searches by authenticated parent merchant, `subMerchantId`, and `subMerchantChannelId` without enabled-status filtering. If no row matches, the query throws `INVALID_MERCHANT`.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_MERCHANT",
  "responseMessage": "INVALID_MERCHANT"
}
```

Client handling: verify both identifiers and parent credentials. If the sub-merchant was recently onboarded, confirm the add flow completed before lookup.

### Merchant Info Missing

If the sub-merchant exists but the associated merchant-info row is missing, Newton returns invalid data.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid MerchantInfo details"
}
```

Client handling: treat this as an onboarding/data repair issue and contact Newton support. Retrying unchanged is unlikely to help.

### Primary Account Or Decryption/Internal Mapping Failure

If the primary merchant account is missing, VPA decryption fails, Passetto decrypt fails, or account/config mappings are inconsistent, the endpoint can return an internal error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with backoff only for transient internal errors. If repeated for the same sub-merchant, raise the `x-request-id` to Newton support.

### Malformed Stored Configuration

If `payerAccTypesAllowed` exists but cannot be parsed as JSON or cannot be decoded into the expected account-type structure, the endpoint returns an internal error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: do not change request payloads to work around this. The stored sub-merchant configuration needs correction.

## Retry And Idempotency Guidance

This endpoint is read-only and does not create, update, or reserve resources.

- Safe to retry after network failures, timeouts, and `INTERNAL_SERVER_ERROR`, using exponential backoff and the same `subMerchantId`/`subMerchantChannelId`.
- Regenerate request envelope timestamps and signatures on every retry.
- Preserve `x-request-id` only when you want Newton logs to correlate attempts as the same client operation; otherwise use a new id per attempt.
- Do not retry unchanged requests for validation errors, authentication/signature failures, API-disabled errors, IP restriction failures, non-aggregator credentials, or sub-merchant lookup failures.

## Source References

- API mounted under `/api/{apiVersion}` with `SubMerchantAPIs`: [Core.hs](../../src/Newton/App/Routes/Core.hs:112).
- Sub-merchant `info` route and handler: [SubMerchant.hs](../../src/Newton/App/Routes/SubMerchant.hs:31) and [SubMerchant.hs](../../src/Newton/App/Routes/SubMerchant.hs:101).
- Request decryption and header tracing: [Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40).
- Response signing/encryption strategy: [RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35).
- S2S request/response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48).
- Payload JWS/JWE verification and decryption: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96).
- Merchant signature, API permission, timestamp, and IP checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56).
- S2S transformer route: [ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:680).
- Request and response types/validation: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3084).
- Shared sub-merchant payload fields: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2947).
- Configuration response encoding: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2741).
- S2S response mapping and version gate for `configurations`: [ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1094).
- Product lookup flow: [SubMerchant/SubMerchant.hs](../../src/Newton/Product/Merchant/SubMerchant/SubMerchant.hs:97).
- Aggregator requirement: [SubMerchant/Helper.hs](../../src/Newton/Product/Merchant/SubMerchant/Helper.hs:58).
- Response payload construction: [SubMerchant/Helper.hs](../../src/Newton/Product/Merchant/SubMerchant/Helper.hs:511).
- Supported configuration extraction: [SubMerchant/Helper.hs](../../src/Newton/Product/Merchant/SubMerchant/Helper.hs:614).
- Lookup and data errors: [Merchant.hs](../../src/Newton/Storage/QueriesMiddleware/Merchant.hs:79), [MerchantInfo.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantInfo.hs:83), and [MerchantAccount.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantAccount.hs:32).
- Shared error body constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43) and [Common.hs](../../src/Newton/Types/API/Common.hs:12).
