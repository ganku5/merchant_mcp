# Outage Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/outage`

## Overview

Outage Status is a merchant server-to-server API for checking the current health of UPI rails that can affect payment success: remitter or beneficiary banks, PSP handles, and NPCI.

Use this API from a merchant backend when routing, checkout, support, or operations systems need a near-real-time view of UPI rail health. Newton calculates statuses from recent transaction metrics stored in Redis and from NPCI health checks. Missing or insufficient metric data does not fail the API; it is returned as `STATUS_NOT_AVAILABLE`.

Payloads use the standard Newton S2S request and response envelope shared during onboarding. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

Outage Status helps merchants:

- Show payment-risk indicators before a customer starts a UPI journey.
- Decide whether to nudge customers away from degraded banks or PSP apps.
- Power support and operations dashboards for UPI success-rate drops.
- Poll only the banks or PSPs relevant to an order, or use Newton-configured default top banks and PSPs.
- Track financial and non-financial rail health separately when using `x-api-version: 3` or later.

## Integration Flow

1. Merchant backend decides which rails to inspect.
2. Merchant sends `banks`, `psps`, both, or neither. If neither list is sent, Newton uses configured top banks and top PSP handles.
3. Merchant signs and/or encrypts the request using the S2S mechanism configured during onboarding.
4. Newton authenticates merchant headers, validates timestamp/signature/envelope, checks API access and IP allowlist, and decrypts the business payload.
5. Newton validates list shape and bank/PSP filter formats.
6. Newton reads outage metrics for enabled rail categories in the merchant configuration.
7. Merchant decrypts the response and uses returned statuses for routing, UI messaging, support, or monitoring.

Important behavior:

- Bank, PSP, and NPCI sections are returned only when enabled for the merchant through configuration.
- Request lists are capped by server configuration. Extra entries beyond the cap are ignored, not rejected.
- `successRate` is omitted when a status is `STATUS_NOT_AVAILABLE`.
- The response shape depends on `x-api-version`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/outage
```

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Use `application/json`. |
| `x-api-version` | Recommended | Use `3` or higher for separate financial and non-financial status blocks. If absent or non-numeric, Newton treats it as version `0`. |
| `x-merchant-id` | Yes | Merchant identifier configured with Newton. |
| `x-merchant-channel-id` | Yes | Merchant channel identifier configured with Newton. |
| `x-merchant-signature` | Conditional | Required for plain S2S payloads. The signature is computed over merchant ids, timestamp, optional sub-merchant ids, and raw request body as configured during onboarding. |
| `x-timestamp` | Yes | 13-digit Unix epoch timestamp in milliseconds. Must be within 30 minutes of server time. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. Newton checks the first IP in this header. |
| `x-request-id` | No | Optional request id for tracing. Newton generates one if omitted. |
| `x-session-id` | No | Optional session id for tracing. Newton uses `x-request-id` when omitted. |

Path parameter:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Route prefix version, for example `v1`. Response versioning for this endpoint is controlled by the `x-api-version` header. |

## Authentication, Encryption, and Signing

The route accepts Newton's standard `EncRequest` envelope:

| Envelope | JSON shape | Notes |
| --- | --- | --- |
| JWE encrypted payload | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag` | Newton decrypts the JWE, expects the decrypted content to be a signed payload, and then parses the business body. |
| JWS signed payload | `payload`, `signature`, `protected` | Newton verifies the JWS using the configured merchant key. |
| Plain payload | Business JSON directly | Used only when explicitly configured. Newton verifies `x-merchant-signature` over the raw request body. |

For encrypted or signed payloads, include `iat` in the decrypted business body. For plain payloads, `iat` is not required by the envelope validator, but `x-timestamp` is still required for S2S signature validation.

Authentication failures can happen before the business payload is processed. Treat these as integration or credential issues, not rail-health results.

## Request

### Minimum Request

Use this when you want Newton's configured default top banks and PSPs:

```json
{
  "iat": "1719835200000"
}
```

### Bank Filter

Send bank IFSC prefixes or full IFSCs. Four-character values represent bank-level IFSC prefixes; 11-character values represent full IFSCs.

```json
{
  "banks": [
    "HDFC",
    "ICIC0000001"
  ],
  "iat": "1719835200000",
  "udfParameters": "{\"dashboard\":\"checkout-risk\"}"
}
```

### PSP Filter

Send PSP handles without `@`.

```json
{
  "psps": [
    "ybl",
    "okhdfcbank",
    "paytm"
  ],
  "iat": "1719835200000"
}
```

### Bank and PSP Filter

```json
{
  "banks": [
    "SBIN",
    "UTIB0000001"
  ],
  "psps": [
    "apl",
    "waicici"
  ],
  "iat": "1719835200000"
}
```

### Invalid Empty List

Do not send empty arrays. Omit the field instead.

```json
{
  "banks": [],
  "iat": "1719835200000"
}
```

This fails validation because a present list must contain at least one value.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `banks` | array of strings | No | If omitted, Newton uses configured `topBanks`, then caps processing at `maximumAllowedBanksForOutageStatus`. | If present, the array must be non-empty. Each value must be either 4 alphabetic characters or 11 alphanumeric characters. Values are uppercased internally for metric lookup. | Bank filters. Send 4-character IFSC prefixes for bank-level checks or full 11-character IFSCs for exact-bank checks. |
| `psps` | array of strings | No | If omitted, Newton uses configured `topPsps`, then caps processing at `maximumAllowedPSPHandlesForOutageStatus`. | If present, the array must be non-empty. Each value must match `^[a-zA-Z0-9]+$`. Values are uppercased internally for metric lookup; display names use known lowercase handles where available. | PSP handle filters, such as `ybl`, `okaxis`, `paytm`, `apl`. |
| `udfParameters` | string | No | Omitted from response when not supplied. | Must be a JSON-object string and must not contain restricted characters matched by Newton's UDF validator. | Merchant-defined metadata. Echoed back in the S2S response. |
| `iat` | string | Conditional | No default. | Required for JWE/JWS envelopes. Must be a 13-digit epoch-millisecond timestamp within 30 minutes of server time. | Issued-at timestamp used in envelope/signature validation. |

### Defaults and Limits

The endpoint has no merchant-supplied pagination. Server configuration controls:

| Setting | Default in code | Behavior |
| --- | --- | --- |
| `windowSizeForOutageStatus` | `5` minutes | Metrics are read for the current window; if the current window has insufficient volume, Newton also reads the previous window. |
| `maximumAllowedBanksForOutageStatus` | `10` unless overridden | Newton takes only the first configured/requested bank filters up to this limit. |
| `maximumAllowedPSPHandlesForOutageStatus` | Uses the same environment default as bank limit unless overridden | Newton takes only the first configured/requested PSP handles up to this limit. |
| `topBanks` | Environment/configured list | Used only when `banks` is omitted. |
| `topPsps` | Environment/configured list | Used only when `psps` is omitted. |

## Success Response

The response uses the standard Newton S2S response envelope. After decrypting the response, the business body has this shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "bankList": [],
    "npciSuccessRate": {},
    "pspList": []
  },
  "udfParameters": "{\"dashboard\":\"checkout-risk\"}"
}
```

Fields whose values are `null` are omitted from JSON.

### Version 3+ Response Example

Use `x-api-version: 3` or later for this shape.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "bankList": [
      {
        "ifsc": "HDFC",
        "name": "HDFC Bank",
        "bankCode": "400240",
        "fin": {
          "status": "UP",
          "successRate": "99.2"
        },
        "nonFin": {
          "status": "STATUS_NOT_AVAILABLE"
        }
      }
    ],
    "npciSuccessRate": {
      "fin": {
        "status": "MEDIUM_SUCCESS_RATE",
        "successRate": "87.5"
      },
      "nonFin": {
        "status": "UP",
        "successRate": "98.7"
      }
    },
    "pspList": [
      {
        "handle": "YBL",
        "name": "PhonePe",
        "status": "LOW_SUCCESS_RATE"
      },
      {
        "handle": "PAYTM",
        "name": "Paytm Payments Bank App",
        "status": "UP",
        "successRate": "96.4"
      }
    ]
  },
  "udfParameters": "{\"dashboard\":\"checkout-risk\"}"
}
```

### Version 2 Response Example

Use `x-api-version: 2` if your client expects flat bank status with bank metadata and combined NPCI status.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "bankList": [
      {
        "ifsc": "HDFC",
        "name": "HDFC Bank",
        "bankCode": "400240",
        "status": "UP",
        "successRate": "99.2"
      }
    ],
    "npciSuccessRate": {
      "status": "MEDIUM_SUCCESS_RATE",
      "successRate": "87.5"
    },
    "pspList": [
      {
        "handle": "YBL",
        "name": "PhonePe",
        "status": "LOW_SUCCESS_RATE"
      }
    ]
  }
}
```

### Version 0 or 1 Response Example

When `x-api-version` is absent, invalid, `0`, or `1`, Newton returns the legacy NPCI field and flat bank status. Bank `name` and `bankCode` are included only from version `2` onward, so they are omitted here.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "bankList": [
      {
        "ifsc": "HDFC",
        "status": "UP",
        "successRate": "99.2"
      }
    ],
    "npciStatus": "UP",
    "pspList": [
      {
        "handle": "PAYTM",
        "name": "Paytm Payments Bank App",
        "status": "UP",
        "successRate": "96.4"
      }
    ]
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable result. Success value is `SUCCESS`. |
| `payload` | object | Outage status payload. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. |

### `payload`

| Field | Type | Present when | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Always on success | Merchant id from authenticated merchant configuration. |
| `merchantChannelId` | string | Always on success | Merchant channel id from authenticated merchant configuration. |
| `bankList` | array of `BankStatusDetail` | Merchant configuration has `isBankOutageEnabled = true`. | Status for requested or default bank filters. Omitted when bank outage is disabled for the merchant. |
| `npciStatus` | string | `x-api-version <= 1` and merchant configuration has `isNpciOutageEnabled = true`. | Legacy NPCI status. |
| `npciSuccessRate` | `NPCIStatusDetail` | `x-api-version > 1` and merchant configuration has `isNpciOutageEnabled = true`. | Versioned NPCI status and success-rate details. |
| `pspList` | array of `PspStatusDetail` | Merchant configuration has `isPspOutageEnabled = true`. | Status for requested or default PSP handles. Omitted when PSP outage is disabled for the merchant. |

### `BankStatusDetail`

| Field | Type | Present when | Description |
| --- | --- | --- | --- |
| `ifsc` | string | Always for each bank result | Requested bank filter or fallback bank filter. |
| `name` | string | `x-api-version >= 2` and bank metadata is found | Bank display name from bank metadata lookup. |
| `bankCode` | string | `x-api-version >= 2` and bank metadata is found | Bank IIN/code from bank metadata lookup. |
| `status` | string | `x-api-version < 3` | Legacy financial status for the bank. |
| `successRate` | string | `x-api-version < 3` and status is not `STATUS_NOT_AVAILABLE` | Financial success rate percentage truncated to two decimals. |
| `fin` | `OutageStatusDetail` | `x-api-version >= 3` | Financial transaction rail status. |
| `nonFin` | `OutageStatusDetail` | `x-api-version >= 3` | Non-financial rail status, such as balance/account flows. |

### `PspStatusDetail`

| Field | Type | Description |
| --- | --- | --- |
| `handle` | string | PSP handle used for metric lookup. |
| `name` | string | Known app/display name when Newton maps the handle, otherwise the handle itself. |
| `status` | string | PSP outage status. |
| `successRate` | string | PSP success rate percentage truncated to two decimals. Omitted when status is `STATUS_NOT_AVAILABLE`. |

### `NPCIStatusDetail`

| Field | Type | Present when | Description |
| --- | --- | --- | --- |
| `status` | string | `x-api-version == 2` | Combined NPCI status. |
| `successRate` | string | `x-api-version == 2` and status is not `STATUS_NOT_AVAILABLE` | Combined NPCI success rate percentage. |
| `fin` | `OutageStatusDetail` | `x-api-version >= 3` | Financial NPCI health derived from configured NPCI API metrics and health check. |
| `nonFin` | `OutageStatusDetail` | `x-api-version >= 3` | Non-financial NPCI health derived from configured NPCI API metrics and health check. |

### `OutageStatusDetail`

| Field | Type | Description |
| --- | --- | --- |
| `status` | enum | One of `UP`, `MEDIUM_SUCCESS_RATE`, `LOW_SUCCESS_RATE`, `DOWN`, `STATUS_NOT_AVAILABLE`. |
| `successRate` | string | Percentage truncated to two decimals. Omitted when status is `DOWN` due to NPCI health check or `STATUS_NOT_AVAILABLE`. |

### Status Semantics

| Status | Meaning | Client guidance |
| --- | --- | --- |
| `UP` | Success rate is at or above the configured `upSRThreshold`, or NPCI health check reports up and metrics are healthy. | No special action required. |
| `MEDIUM_SUCCESS_RATE` | Success rate is below the `upSRThreshold` but at or above the configured `mediumSRThreshold`. | Consider showing a soft warning or preferring alternate rails when available. |
| `LOW_SUCCESS_RATE` | Success rate is below the medium threshold, or consecutive failures exceed the configured threshold. | Prefer alternate rails or warn customers before payment. |
| `DOWN` | NPCI health check reports down. | Treat as a hard rail outage for the applicable NPCI section. |
| `STATUS_NOT_AVAILABLE` | Not enough transactions in the current/previous metric windows, inconsistent metric data, missing metric data, or an unrecognized NPCI health result. | Do not treat this as success or failure. Display unknown status or fall back to other signals. |

## Error Handling

Failure responses use the same S2S response transport when the response can be wrapped. If decryption, envelope parsing, or authentication fails early, the HTTP status may be `400` or `401` and the body may be an unencrypted error response depending on deployment and middleware stage. A concrete decrypted validation error looks like:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ifsc length validation failed"
}
```

Clients should use both HTTP status and body fields:

- Retry only transient server/cache failures or network timeouts.
- Do not retry validation, authentication, signature, IP allowlist, or API-disabled failures without changing the request or configuration.
- Do not treat `STATUS_NOT_AVAILABLE` in a successful response as an API failure.

### Failure Scenarios

| Scenario | HTTP status commonly used | Underlying response body | Client handling |
| --- | --- | --- | --- |
| Empty `banks` or `psps` array | `200` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ListValidation \"Field is empty\""}` | Omit the field when no filter is needed. |
| Bank filter is not 4 or 11 characters | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ifsc length validation failed"}` | Send a 4-character bank IFSC prefix or full 11-character IFSC. |
| Bank filter contains invalid characters | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ifsc regex match failed"}` | Use alphabetic characters for 4-character prefixes and alphanumeric characters for full IFSCs. |
| PSP handle contains invalid characters | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"handle regex match failed"}` | Send only letters and digits, without `@`. |
| `udfParameters` is not a JSON-object string or contains restricted characters | `200` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` | Send a JSON-object string such as `"{\"key\":\"value\"}"`, or omit the field. |
| JWE/JWS payload omits `iat` | `200` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` | Include a 13-digit epoch-millisecond `iat` in the decrypted business body. |
| `iat` or `x-timestamp` is not a 13-digit timestamp | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` | Regenerate the timestamp in milliseconds. |
| Timestamp is older/newer than the allowed 30-minute window | `400` | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` | Synchronize clocks and retry with a fresh timestamp. |
| Missing `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, raw body, or required signature header | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Fix headers and signing middleware. |
| Merchant id/channel id cannot be resolved | `401` or `200` | Usually `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}`. Some lookup layers return `INVALID_DATA` with a concrete merchant lookup message. | Verify onboarding identifiers and environment. |
| JWS verification fails | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Verify key id, public/private key pair, signed payload, and base64url encoding. |
| JWE decryption fails | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Verify key id, encryption key, algorithm, and encrypted body fields. |
| Encrypted payload decrypts but does not contain a signed payload | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Wrap the decrypted JWE body as the configured signed payload. |
| Encrypted or signed payload body cannot be parsed as JSON | `400` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: expected Object, but encountered String"}` is one possible parse error; the message contains the parser failure returned by the JSON decoder. | Fix JSON serialization before signing/encrypting. |
| Merchant signature mismatch for a plain payload | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Recompute the signature over the exact raw body and configured signed fields. |
| API is blocked or not allowed for the merchant | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Ask Newton to enable `outageStatusS2S` for the merchant/channel. |
| Merchant has an IP allowlist and `x-forwarded-for` is missing or not allowed | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Send traffic through an allowlisted egress IP and include the forwarding header expected by onboarding. |
| Bank outage, PSP outage, or NPCI outage is disabled in merchant config | `200` | Success body with that section omitted. | This is not an error. Enable the relevant merchant flag if the section is required. |
| Requested bank metadata is not found | `200` | Success body where the bank item has `ifsc` and status but omits `name`/`bankCode`. | Continue using the status; display the requested IFSC/prefix as the label if needed. |
| Redis has insufficient or missing metric samples | `200` | Success body with `STATUS_NOT_AVAILABLE` and no `successRate` for the affected rail. | Treat rail health as unknown. Use another signal or fallback experience. |
| NPCI health check returns an unrecognized value | `200` | Success body with NPCI `STATUS_NOT_AVAILABLE` or empty NPCI detail, depending on version. | Treat NPCI health as unknown. |
| Redis/cache, bank lookup, configuration, or unexpected server failure | `500` or `200` | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry with backoff if the request is unchanged and timestamps/signatures are regenerated. Escalate if persistent. |

## Retry and Idempotency

This endpoint is read-only and does not create or mutate merchant business state. There is no idempotency key.

Recommended retry behavior:

- Retry network timeouts, `5xx`, and `INTERNAL_SERVER_ERROR` with exponential backoff and jitter.
- Regenerate `x-timestamp`, `iat`, signatures, and encrypted payloads for every retry.
- Do not retry validation failures until the payload is corrected.
- Do not retry `UNAUTHORIZED`, `AUTH_FAILURE`, `API NOT ENABLED`, or IP allowlist failures until credentials or configuration are fixed.
- Polling dashboards should keep a modest interval, such as one metric window or longer, because the default outage metric window is 5 minutes.
- Cache successful responses briefly on the client side if multiple internal systems read the same rail status.

## Source References

- Route type for S2S outage: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs#L685)
- S2S route handler, request decryption, signature verification, and transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs#L5051)
- Server wiring for `outageStatusS2S`: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs#L323)
- S2S request/response types and validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs#L94)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs#L213)
- S2S request/response mapping and versioned response transforms: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs#L218)
- Core outage product logic and merchant flags: [src/Newton/Product/Outage/OutageStatus.hs](../../src/Newton/Product/Outage/OutageStatus.hs#L14)
- Outage domain types and enums: [src/Newton/Product/Outage/Types.hs](../../src/Newton/Product/Outage/Types.hs#L31)
- Metric calculation, status thresholds, versioned NPCI/bank logic, and PSP display names: [src/Newton/Product/Outage/Helper.hs](../../src/Newton/Product/Outage/Helper.hs#L35)
- IFSC and PSP validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs#L44)
- Generic list and UDF validation: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs#L222)
- Request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs#L48)
- S2S payload verification and JWE/JWS parsing: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs#L69)
- Merchant signature, API access, timestamp, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs#L56)
- Timestamp validation: [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs#L108)
- Outage configuration defaults: [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs#L2486)
- Outage configuration mapping: [src/Newton/Types/Config/Transformer.hs](../../src/Newton/Types/Config/Transformer.hs#L460)
- Redis outage metric keys and map reads: [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs#L925)
- Shared success and error bodies: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs#L43)
