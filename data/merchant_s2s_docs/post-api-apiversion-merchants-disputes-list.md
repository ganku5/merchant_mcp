# List Disputes API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/disputes/list`

## Overview

List Disputes is a Newton merchant server-to-server API used to fetch dispute records for a merchant or authenticated sub-merchant for one dispute date and dispute type.

Merchants use this API to discover dispute cases that need operational review, proof upload, acceptance, rejection, refund reconciliation, or follow-up through the Fetch Dispute and Update Dispute APIs. Newton returns a paginated list of matching disputes with transaction identifiers, adjustment amounts, dispute lifecycle status, TAT, proof name, refund totals, and reason-code details.

Payloads use the standard Newton S2S request and response protection configured during onboarding. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

Call this API when the merchant backend needs to:

- Pull the daily dispute queue for a specific dispute type.
- Build a merchant operations dashboard for pending, submitted, closed, or reopened disputes.
- Identify disputes that require proof or merchant action before TAT expiry.
- Reconcile dispute amounts with completed or pending refunds.
- Get `adjUid` values to call Fetch Dispute for proof data or Update Dispute for merchant action.

This API is read-only. It does not create, update, accept, reject, or submit dispute records.

## Integration Flow

1. Merchant chooses the dispute date, dispute type, and optional page controls.
2. Merchant signs or encrypts the request using the onboarded Newton S2S strategy.
3. Merchant calls `POST /api/{apiVersion}/merchants/disputes/list`.
4. Newton verifies the merchant headers, payload signature/encryption, timestamp, IP allowlist where configured, and API enablement.
5. Newton validates the decrypted payload and resolves the authenticated merchant or sub-merchant context.
6. Newton fetches matching disputes ordered by most recently created first.
7. Merchant stores `adjUid`, `upiRequestId`, `merchantRequestId`, status, amount, and TAT for reconciliation or follow-up calls.

## Endpoint

```http
POST /api/{apiVersion}/merchants/disputes/list
```

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-api-version` | Recommended | Use the API version shared during onboarding. |
| `x-merchant-id` | Yes, unless only sub-merchant headers are used by your onboarded flow | Parent merchant identifier. |
| `x-merchant-channel-id` | Yes, unless only sub-merchant headers are used by your onboarded flow | Parent merchant channel identifier. |
| `x-sub-merchant-id` | Conditional | Sub-merchant identifier. Use with `x-sub-merchant-channel-id` to list disputes for that sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Sub-merchant channel identifier. Required when `x-sub-merchant-id` is sent. |
| `x-timestamp` | Yes | 13-digit epoch-millisecond timestamp. Newton validates freshness, currently within 30 minutes. |
| `x-merchant-signature` | Conditional | Required for plain JSON/header-signature mode. JWS/JWE requests are verified through the protected payload. |
| `x-request-id` | No | Merchant request correlation id. Newton generates one if omitted. |
| `x-session-id` | No | Merchant session/correlation id. Defaults to `x-request-id` when omitted. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant. |

## Authentication And Encryption

Newton accepts the standard S2S envelope configured for the merchant:

- JWS: signed request payload and signed response.
- JWS and JWE: signed payload encrypted in JWE, with encrypted response.
- Plain JSON with header signature, only when explicitly enabled for the merchant.

For JWS or JWE requests, include `iat` in the decrypted business payload. Newton validates `iat` as a 13-digit epoch-millisecond timestamp. For plain JSON/header-signature mode, Newton validates `x-merchant-signature` over merchant headers, `x-timestamp`, and raw body.

If response encryption is enabled for the merchant, error responses are protected the same way as success responses. The examples below show decrypted bodies.

## Request

Route request type: `API.EncRequest TfS2S.ListDisputeS2SRequest`

Decrypted business payload type: `TfS2S.ListDisputeS2SRequest`

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `date` | string | Yes | No default. | Dispute adjustment date filter. Current code applies two date checks with different expected shapes: the generic S2S validator accepts a date-only value, while the dispute parser expects `YYYY-MM-DDTHH:MM:SS` and then normalizes to start of day. Confirm the accepted production format during onboarding for this endpoint. |
| `type` | string | Yes | No default. | Dispute type filter. Must be one of the supported dispute type enum values listed below. |
| `subMerchantId` | string | No | No query default. | Validated for merchant-id format when supplied, but the current transformer does not pass this field into product lookup. Use `x-sub-merchant-id` and `x-sub-merchant-channel-id` headers to scope the query to a sub-merchant. |
| `limit` | integer | No | DB lookup defaults to `51` records when omitted. Values greater than the configured `QUERY_MAX_LIMIT` are rejected before lookup. | Maximum number of disputes to return for this page. Must be non-negative. |
| `offset` | integer | No | Defaults to `0` when omitted. | Zero-based offset for pagination. Must be non-negative. |
| `iat` | string | Conditional | Required for JWS/JWE request strategies. Not used for plain JSON/header-signature mode. | 13-digit epoch-millisecond issued-at timestamp validated during merchant signature verification. |

### Supported Dispute Types

Send the enum value exactly as shown:

| Value | Meaning |
| --- | --- |
| `COMPLAINT_RAISE` | Complaint raised. |
| `CHARGEBACK_RAISE` | Chargeback raised. |
| `FRAUD_CHARGEBACK_RAISE` | Fraud chargeback raised. |
| `DIFFERED_CHARGEBACK_RAISE` | Differed chargeback raised. |
| `PREARBITRATION_RAISE` | Pre-arbitration raised. |
| `DIFFERED_PREARBITRATION_RAISE` | Differed pre-arbitration raised. |
| `ARBITRATION_RAISE` | Arbitration raised. |
| `DIFFERED_ARBITRATION_RAISE` | Differed arbitration raised. |
| `REMITTER_NEGATIVE_GOOD_FAITH_CHARGEBACK` | Remitter negative good-faith chargeback. |

### Validation Notes

- `date` is required and currently has the implementation caveat described in the field table.
- `type` must parse as a known `DisputeType`.
- `subMerchantId`, when sent, must be 1 to 256 characters and match `^[a-zA-Z0-9 _+.-]+$`.
- `limit` must be `0` or greater and must not exceed the configured `QUERY_MAX_LIMIT`; the default config value is `100`.
- `offset` must be `0` or greater.
- For JWS/JWE, `iat` must be present and pass timestamp freshness validation.

There are no nested request objects for this API.

Implementation caveat: as currently wired, a date-only value can pass the generic S2S date validator but fail the dispute parser, while a `YYYY-MM-DDTHH:MM:SS` value can fail the generic validator before the dispute parser runs. Treat the examples below as the intended dispute lookup payload shape and confirm the accepted date format for your environment before production use.

## Request Examples

The `iat` values below are illustrative. Generate a fresh 13-digit epoch-millisecond value at send time.

### List Chargebacks For A Date

```json
{
  "date": "2026-06-30T00:00:00",
  "type": "CHARGEBACK_RAISE",
  "limit": 25,
  "offset": 0,
  "iat": "1782806400000"
}
```

### List Pending Operational Page For A Different Dispute Type

```json
{
  "date": "2026-06-30T00:00:00",
  "type": "PREARBITRATION_RAISE",
  "limit": 10,
  "offset": 10,
  "iat": "1782806400000"
}
```

### Sub-Merchant Scoped Listing

Use sub-merchant headers for scoping. The body field is shown only because the request type accepts it; the current lookup uses the authenticated sub-merchant context from headers.

```http
x-merchant-id: AGGREGATOR001
x-merchant-channel-id: WEB
x-sub-merchant-id: STORE0001
x-sub-merchant-channel-id: WEB
```

```json
{
  "date": "2026-06-30T00:00:00",
  "type": "COMPLAINT_RAISE",
  "subMerchantId": "STORE0001",
  "limit": 25,
  "offset": 0,
  "iat": "1782806400000"
}
```

## Response

Route response type: `RespHeaders (API.EncResponse TfS2S.ListDisputeS2SResponse)`

Decrypted business response type: `TfS2S.ListDisputeS2SResponse`

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API execution status. Success is `SUCCESS`. |
| `responseCode` | string | Machine-readable response code. Success is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success is `SUCCESS`. |
| `payload` | object | Present on success. Omitted in most failure bodies. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `summary` | object | Pagination summary for the matching query. |
| `data` | array | Dispute rows returned for the current page. Empty when no disputes match. |

### `payload.summary`

| Field | Type | Description |
| --- | --- | --- |
| `totalCount` | integer | Total disputes matching merchant context, date, and type, before page limit and offset are applied. |
| `count` | integer | Number of dispute rows returned in this response. |

### `payload.data[]`

| Field | Type | Description |
| --- | --- | --- |
| `adjUid` | string | Unique dispute adjustment id. Use this for Fetch Dispute and Update Dispute. |
| `type` | string | Dispute type. |
| `adjDate` | string | Adjustment date/time as stored by Newton, serialized with `+05:30`. |
| `upiRequestId` | string | Newton UPI request id associated with the original transaction. |
| `merchantRequestId` | string | Merchant order/reference id associated with the original transaction or dispute. |
| `reqAdjAmount` | string | Requested adjustment amount in two-decimal format. |
| `originatingChannel` | string | Source channel for the dispute, for example `UDIR` or `UMOB`. |
| `status` | string | Dispute lifecycle status exposed to the merchant. `UNRESPONDED`, `SAVED`, and `PROOF_REQUIRED` are returned as `PENDING`; other values are `SUBMITTED`, `CLOSED`, or `REOPENED`. |
| `merchantAction` | string | Merchant action already recorded, such as `ACCEPTED`, `REJECTED`, or `PARTIALLY_ACCEPTED`. Omitted when no action has been taken. |
| `txnTimestamp` | string | Original transaction timestamp, if the transaction can be found. |
| `txnAmount` | string | Original transaction amount in two-decimal format, if the transaction can be found. |
| `adjAmount` | string | Merchant response/adjustment amount, if available. |
| `upiResponseId` | string | UPI response id for the original transaction, if available. |
| `actionReasonCode` | string | Reason code recorded with the merchant action, if available. |
| `actionReason` | string | Human-readable reason for `actionReasonCode`, if available. |
| `proofName` | string | First proof file name stored against the dispute, if any. The list API does not return proof bytes; use Fetch Dispute for proof data. |
| `tat` | string | Turnaround-time deadline for merchant action, serialized with `+05:30`. |
| `pendingRefunds` | string | Sum of `PENDING` and `DEEMED` refunds for this merchant request id. Omitted when the sum is `0.00`. |
| `completedRefunds` | string | Sum of `SUCCESS` refunds for this merchant request id. Omitted when the sum is `0.00`. |
| `lastModified` | string | Last dispute update timestamp, serialized with `+05:30`. |
| `disputeReason` | string | Human-readable reason derived from `disputeReasonCode`. |
| `disputeReasonCode` | string | Original requested adjustment reason code. |
| `subMerchantId` | string | Sub-merchant id from authenticated sub-merchant context. Omitted for parent-merchant scoped calls. |
| `merchantId` | string | Parent merchant id from authenticated merchant context. |

Nullable response fields are omitted from JSON when they are not available.

## Success Response Examples

### Page With One Dispute

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "summary": {
      "totalCount": 12,
      "count": 1
    },
    "data": [
      {
        "adjUid": "ADJ202606300001",
        "type": "CHARGEBACK_RAISE",
        "adjDate": "2026-06-30T00:00:00+05:30",
        "upiRequestId": "GTXN1234567890",
        "merchantRequestId": "ORDER12345",
        "reqAdjAmount": "100.00",
        "originatingChannel": "UDIR",
        "status": "PENDING",
        "txnTimestamp": "2026-06-29T15:12:30+05:30",
        "txnAmount": "100.00",
        "upiResponseId": "123456789012",
        "tat": "2026-07-03T00:00:00+05:30",
        "pendingRefunds": "25.00",
        "lastModified": "2026-06-30T09:30:00+05:30",
        "disputeReason": "Merchant was unable to provide the service",
        "disputeReasonCode": "1095",
        "merchantId": "MERCHANT001"
      }
    ]
  }
}
```

### No Matching Disputes

No matching dispute is not an error. Newton returns `SUCCESS` with an empty `data` array.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "summary": {
      "totalCount": 0,
      "count": 0
    },
    "data": []
  }
}
```

## Client Handling

Use the envelope `status`, `responseCode`, and `responseMessage` to decide whether the API call itself succeeded. Use each row's `status` to decide dispute workflow state.

Recommended handling:

- Treat `payload.data[]` as a page of dispute records, not as a complete daily export unless `count` covers `totalCount`.
- Use `limit` and `offset` to page through records; de-duplicate by `adjUid` if disputes can be created while pagination is in progress.
- Call Fetch Dispute with `adjUid` when proof bytes are needed.
- Call Update Dispute with `adjUid` only when the merchant is ready to submit action and proof details.
- Do not retry validation, auth, or merchant configuration failures without changing the request or onboarding configuration.
- Retry transient 5xx, gateway, network, database, or encrypted-response transport failures with the same filters after a backoff.
- Because the API is read-only and has no idempotency key, repeated successful calls are safe, but returned status, refund totals, and counts may change as disputes and refunds are updated.

## Error Handling

Failure responses use the same response protection strategy as success responses. The examples below show decrypted bodies. When `payload` is empty, it is omitted.

Most failure bodies follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"date value not valid\""
}
```

The exact `responseCode` and `responseMessage` depend on the validation or business rule that failed. HTTP status can vary by layer. Clients should read the decrypted body fields.

### Concrete Failure Scenarios

| Scenario | Decrypted response body |
| --- | --- |
| `date` fails the generic or dispute-specific date validation | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"date value not valid\""}` |
| `type` is missing, malformed, or cannot be parsed as a dispute enum | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Request"}` |
| `subMerchantId` contains unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"subMerchantId is not alphanumeric\""}` |
| `subMerchantId` is empty or longer than 256 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantId length not between 1 and 256\""}` |
| `limit` is negative, greater than configured `QUERY_MAX_LIMIT`, or `offset` is negative | `{"status":"FAILURE","responseCode":"INVAILD_LIMIT_OFFSET","responseMessage":"Invalid limit/offset param"}` |
| JWS/JWE request omits `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| `iat` or `x-timestamp` is not a 13-digit epoch-millisecond timestamp | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` |
| `iat` or `x-timestamp` is outside the allowed freshness window | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` |
| Missing merchant headers, merchant not found, missing signature, signature mismatch, encrypted payload cannot be authenticated, or IP allowlist check fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| API is blocked or not allowed for the merchant configuration | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| Sub-merchant headers identify a sub-merchant that does not belong to the merchant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Submerchant does not belong to the specified merchant"}` |
| Merchant or parent merchant context cannot be resolved from supplied sub-merchant headers | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Database, Redis, transaction lookup, refund lookup, encryption, or unexpected server failure occurs while building the list | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

No matching dispute records return a successful empty list, not an error.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:778)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:5301)
- Request decoding: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:69)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:868)
- Request type and validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4638)
- Response type and row fields: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4670), [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4711)
- S2S request/response constructors: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1633), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1651)
- Product flow: [src/Newton/Product/Merchant/Disputes/Core.hs](../../src/Newton/Product/Merchant/Disputes/Core.hs:41)
- Product date, pagination, and merchant-context helpers: [src/Newton/Product/Merchant/Disputes/Helper.hs](../../src/Newton/Product/Merchant/Disputes/Helper.hs:231), [src/Newton/Product/Merchant/Disputes/Helper.hs](../../src/Newton/Product/Merchant/Disputes/Helper.hs:261), [src/Newton/Product/Merchant/Disputes/Helper.hs](../../src/Newton/Product/Merchant/Disputes/Helper.hs:273)
- Response row transformer and status mapping: [src/Newton/Product/Merchant/Disputes/Transformer.hs](../../src/Newton/Product/Merchant/Disputes/Transformer.hs:46), [src/Newton/Product/Merchant/Disputes/Transformer.hs](../../src/Newton/Product/Merchant/Disputes/Transformer.hs:107)
- Dispute storage enum values: [src/Newton/Types/Storage/MerchantDispute.hs](../../src/Newton/Types/Storage/MerchantDispute.hs:87), [src/Newton/Types/Storage/MerchantDispute.hs](../../src/Newton/Types/Storage/MerchantDispute.hs:123)
- Dispute lookup queries: [src/Newton/Storage/QueriesMiddleware/MerchantDispute.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantDispute.hs:26), [src/Newton/Storage/Queries/MerchantDispute.hs](../../src/Newton/Storage/Queries/MerchantDispute.hs:62)
- Pagination default cap: [src/Newton/Utils/Extra.hs](../../src/Newton/Utils/Extra.hs:240), [src/Newton/Storage/Queries/MerchantDispute.hs](../../src/Newton/Storage/Queries/MerchantDispute.hs:74)
- Validation helpers and error constants: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:320), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:617), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:629), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:965)
