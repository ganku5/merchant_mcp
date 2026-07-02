# Fetch Dispute API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/disputes/fetch`

## Overview

Fetch Dispute is a server-to-server API used to retrieve the latest Newton record for a single merchant dispute.

The merchant calls this API with the dispute adjustment id, `adjUid`, that was previously received from the dispute list API, a dispute notification callback, or another merchant dispute workflow. Newton validates the encrypted or signed S2S request, resolves the merchant context from headers, looks up the dispute record, enriches it with the original transaction when available, and returns dispute details, action status, TAT, reason information, and any stored merchant proof file.

Use this API when the merchant backend needs to inspect one known dispute in detail before deciding whether to respond, while reconciling dispute state, or while displaying dispute evidence to an operations user.

This API is read-only. It does not create, update, submit, or close a dispute, and it does not make a live downstream enquiry to NPCI.

## Business Use Case

Fetch Dispute helps merchants:

- Retrieve the current lifecycle state for one dispute identified by `adjUid`.
- Confirm the disputed amount, original transaction identifiers, dispute type, reason code, and TAT before responding through the Update Dispute API.
- See whether a merchant action has already been submitted.
- Download the stored proof/evidence file when one exists for the dispute.
- Reconcile a dispute callback or list result against the merchant's internal case management system.

Typical call points:

- After `POST /api/{apiVersion}/merchants/disputes/list` returns an `adjUid`.
- After receiving a dispute notification callback containing an `adjUid`.
- Before calling `POST /api/{apiVersion}/merchants/disputes/update`, to check current `status`, `merchantAction`, `reqAdjAmount`, `adjAmount`, and `tat`.
- During back-office reconciliation, where the merchant wants the full detail for one dispute instead of a paginated list.

## Integration Flow

1. Merchant obtains `adjUid` from a Newton dispute list response or dispute callback.
2. Merchant backend creates the decrypted business payload containing `adjUid`.
3. Merchant signs and/or encrypts the request using the Newton S2S integration method configured during onboarding.
4. Merchant calls the fetch endpoint with merchant headers and the configured API version.
5. Newton validates the S2S envelope, merchant signature/timestamp, merchant API access, and request body.
6. Newton looks up the dispute in the authenticated merchant context.
7. Newton fetches optional proof content from configured object storage when a proof name is stored on the dispute.
8. Merchant decrypts the response and uses `payload.status` to decide the next client action.

Important identifiers:

- `adjUid`: Newton dispute adjustment id. This is the only business identifier accepted by this API.
- `upiRequestId`: UPI transaction id associated with the disputed transaction.
- `merchantRequestId`: Merchant order/reference id associated with the disputed transaction.
- `merchantId`: Merchant id returned in the response for the authenticated merchant context.
- `subMerchantId`: Returned only when the request was made with a valid sub-merchant context.

## Endpoint

```http
POST /api/{apiVersion}/merchants/disputes/fetch
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads and decrypted business responses for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Optional. Send only for enabled sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Conditional. Required when `x-sub-merchant-id` is sent. |
| `x-timestamp` | 13-digit epoch milliseconds, within 30 minutes of Newton's clock. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Depending on the configured envelope, send the required signature/encryption headers such as `x-merchant-signature`. For unsigned/plain requests in allowed environments, Newton verifies the merchant signature against the raw request body. For JWS/JWE requests, the payload must carry `iat` so Newton can validate request freshness.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Request

### Required Minimum

```json
{
  "adjUid": "ADJ202501150001"
}
```

For signed or encrypted S2S requests, include `iat` in the decrypted business payload:

```json
{
  "adjUid": "ADJ202501150001",
  "iat": "1736942400000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `adjUid` | string | Yes | No default. | Newton dispute adjustment id to fetch. Must be non-empty. Use the value returned by list/callback dispute workflows. |
| `iat` | string | Conditional | No default. Required for JWS/JWE requests. Plain-text test payloads do not require it. | Issued-at timestamp in 13-digit epoch milliseconds. Newton validates it for signed/encrypted S2S requests. |

### Defaults and Omitted Field Behavior

This API has no business defaults. `adjUid` is mandatory and no alternate lookup key is supported. If `iat` is omitted on a signed or encrypted request, request freshness validation fails before dispute lookup.

There are no nested request objects for this API.

### Validation Notes

- `adjUid` must be present and non-empty.
- JSON field names are case-sensitive.
- Unknown fields are ignored by the Haskell JSON parser, but clients should not send unused fields.
- The dispute lookup is scoped by the authenticated merchant context from request headers, not by a merchant id in the request body.
- If sub-merchant headers are used, they must represent a valid sub-merchant relationship for the merchant.

## Request Examples

### Fetch From List Result

Use this after a list response returns the `adjUid`.

```json
{
  "adjUid": "ADJ202501150001",
  "iat": "1736942400000"
}
```

### Fetch After Dispute Callback

Use this when a merchant callback has notified your system of a new or updated dispute.

```json
{
  "adjUid": "CBK202501150045",
  "iat": "1736942460000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. `SUCCESS` means the fetch request completed and `payload` contains the dispute record. |
| `responseCode` | string | Machine-readable response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Present on success. Omitted on failures. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `adjUid` | string | Dispute adjustment id that was fetched. |
| `type` | string | Dispute type. Possible values include `COMPLAINT_RAISE`, `CHARGEBACK_RAISE`, `FRAUD_CHARGEBACK_RAISE`, `DIFFERED_CHARGEBACK_RAISE`, `PREARBITRATION_RAISE`, `DIFFERED_PREARBITRATION_RAISE`, `ARBITRATION_RAISE`, `DIFFERED_ARBITRATION_RAISE`, and `REMITTER_NEGATIVE_GOOD_FAITH_CHARGEBACK`. |
| `adjDate` | string | Adjustment/dispute date stored by Newton. Returned as a Newton local timestamp string. |
| `upiRequestId` | string | UPI transaction id associated with the disputed transaction. |
| `merchantId` | string | Merchant id for the authenticated merchant context. |
| `subMerchantId` | string | Sub-merchant id when the request is made in a sub-merchant context. Omitted otherwise. |
| `merchantRequestId` | string | Merchant order/reference id associated with the disputed transaction. |
| `reqAdjAmount` | string | Requested adjustment/dispute amount, formatted with two decimal places. |
| `originatingChannel` | string | Source channel for the dispute record. Known values are `UDIR` and `UMOB`. |
| `status` | string | Client-facing dispute lifecycle status. See status interpretation below. |
| `merchantAction` | string | Merchant action already recorded for this dispute. Omitted when no action has been taken. Values can include `ACCEPTED`, `REJECTED`, and `PARTIALLY_ACCEPTED`. |
| `txnTimestamp` | string | Original transaction creation timestamp when the transaction record is found. Omitted if transaction enrichment is unavailable. |
| `txnAmount` | string | Original transaction amount, formatted with two decimal places, when available. |
| `adjAmount` | string | Merchant response/adjusted amount when one has been recorded. Omitted before merchant action or when no adjustment amount is stored. |
| `upiResponseId` | string | UPI response id from the original transaction when available. |
| `actionReasonCode` | string | Merchant action reason code when an action has been recorded. |
| `actionReason` | string | Human-readable reason mapped from `type` and `actionReasonCode` when available. |
| `proof` | string | Proof file content as a data URI, for example `data:image/png;base64,...`. Returned only when a proof name exists and the file download succeeds. |
| `proofName` | string | Proof file name stored for the dispute. Omitted when no proof exists. |
| `lastModified` | string | Last update timestamp for the dispute record. |
| `tat` | string | Turnaround/deadline timestamp for merchant action or dispute processing. |
| `disputeReason` | string | Human-readable dispute reason mapped from `type` and `disputeReasonCode` when available. |
| `disputeReasonCode` | string | Original dispute/request adjustment reason code. |

### Status Interpretation

`payload.status` is the dispute lifecycle status clients should use for workflow decisions:

| `payload.status` | Meaning | Suggested client handling |
| --- | --- | --- |
| `PENDING` | Newton internal status is `UNRESPONDED`, `SAVED`, or `PROOF_REQUIRED`. | Merchant action may still be needed. Check `tat`, `merchantAction`, `proofName`, `reqAdjAmount`, and `disputeReasonCode`. |
| `SUBMITTED` | Merchant response has been submitted to Newton. | Treat the merchant response as recorded. Avoid duplicate manual updates unless instructed by operations. |
| `CLOSED` | Dispute is closed. | Treat as terminal for normal merchant action. Reconcile final amounts and reason fields. |
| `REOPENED` | Dispute has been reopened. | Re-check the case and follow the latest operational guidance before updating. |

The top-level `status` only tells you whether this fetch API call succeeded. Always use `payload.status` for dispute workflow state.

### Omitted Fields

Response JSON omits `null` optional fields.

- `merchantAction` is omitted when the stored action is `NOT_ACTIONED`.
- `subMerchantId` is omitted outside a sub-merchant context.
- `txnTimestamp`, `txnAmount`, and `upiResponseId` are omitted when the original transaction record cannot be found during enrichment.
- `adjAmount`, `actionReasonCode`, and `actionReason` are omitted until an action/adjustment has been recorded.
- `proof` and `proofName` are omitted when no proof file is stored.
- If `proofName` exists but object storage cannot return the file, the API can fail instead of returning metadata-only success.

## Success Response Examples

### Pending Dispute Without Merchant Action

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "adjUid": "ADJ202501150001",
    "type": "CHARGEBACK_RAISE",
    "adjDate": "2025-01-15 00:00:00",
    "upiRequestId": "UPI123456789012",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "ORDER12345",
    "reqAdjAmount": "100.00",
    "originatingChannel": "UDIR",
    "status": "PENDING",
    "txnTimestamp": "2025-01-14 18:40:12",
    "txnAmount": "100.00",
    "upiResponseId": "501418401234",
    "lastModified": "2025-01-15 10:12:45",
    "tat": "2025-01-20 23:59:59",
    "disputeReason": "Goods or Services Not Provided / Not Received",
    "disputeReasonCode": "1064"
  }
}
```

### Submitted Dispute With Proof

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "adjUid": "CBK202501150045",
    "type": "CHARGEBACK_RAISE",
    "adjDate": "2025-01-15 00:00:00",
    "upiRequestId": "UPI123456789099",
    "merchantId": "MERCHANT123",
    "subMerchantId": "SUBMERCHANT01",
    "merchantRequestId": "ORDER67890",
    "reqAdjAmount": "250.00",
    "originatingChannel": "UDIR",
    "status": "SUBMITTED",
    "merchantAction": "REJECTED",
    "txnTimestamp": "2025-01-14 12:05:31",
    "txnAmount": "250.00",
    "adjAmount": "0.00",
    "upiResponseId": "501412051111",
    "actionReasonCode": "1096",
    "actionReason": "Services/Goods provided see the supporting document",
    "proof": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
    "proofName": "delivery-proof.png",
    "lastModified": "2025-01-16 09:30:00",
    "tat": "2025-01-20 23:59:59",
    "disputeReason": "Goods or Services Not Provided / Not Received",
    "disputeReasonCode": "1064"
  }
}
```

## Error Handling

Failure responses use the same encrypted/signed response transport as success responses when the request reaches the S2S response layer. After decryption, failures include `status: "FAILURE"` plus a concrete `responseCode` and diagnostic `responseMessage`.

HTTP status can vary by layer. Validation errors from the shared request validator may return an error body with HTTP 200, while malformed encrypted payloads can return HTTP 400 and auth failures can return HTTP 401. Client integrations should always inspect decrypted `status`, `responseCode`, and `responseMessage`.

### Validation Failure

Scenario: `adjUid` is empty.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"adjUid field is empty\""
}
```

Client handling: fix the request payload. Do not retry the same payload.

### Missing `iat` For Signed/Encrypted Request

Scenario: request is sent as JWS/JWE without `iat` in the decrypted business payload.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Client handling: include a fresh 13-digit epoch-millisecond `iat` value and resend with a newly signed/encrypted request.

### Expired Or Invalid Timestamp

Scenario: `x-timestamp` or `iat` is not a 13-digit timestamp, or it is outside the allowed 30-minute freshness window.

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Client handling: regenerate `x-timestamp`, `iat`, and signature/encryption for the retry. Check clock synchronization.

### Authentication Or Signature Failure

Scenario: merchant headers are missing, the signature does not match, JWS verification fails, JWE decryption fails, or the source of the signed payload cannot be validated.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: verify merchant id/channel id, sub-merchant headers, signing input, key id, key material, and raw-body canonicalization. Do not retry unchanged requests.

### Merchant API Not Enabled

Scenario: merchant configuration blocks this API or the merchant is not allowed to call `fetchDisputeS2S`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: contact Newton onboarding/support to enable the disputes fetch API for the merchant or sub-merchant configuration.

### Dispute Not Found Or Wrong Merchant Scope

Scenario: `adjUid` does not exist for the authenticated merchant context, or the client used the wrong parent/sub-merchant headers.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "MerchantDispute record not found"
}
```

Client handling: confirm the `adjUid` from list/callback data and retry only after correcting merchant or sub-merchant headers. If the dispute was just notified, wait briefly and retry with the same `adjUid`.

### Malformed JWS/JWE Payload

Scenario: decrypted payload cannot be parsed as the expected signed body or business JSON.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"adjUid\" not found"
}
```

Client handling: fix the JSON body and envelope construction. Ensure the JWE wraps a valid signed payload when that strategy is configured.

### Proof Storage Download Failure

Scenario: the dispute has a stored `proofName`, but Newton cannot download the proof file from configured storage.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry later with a fresh signature/timestamp. If repeated, contact Newton support with `adjUid`, `x-request-id`, and timestamp. The List Disputes API can still be used to view metadata such as `proofName` without downloading proof content.

### Database Or Unexpected Server Failure

Scenario: dispute or transaction lookup fails because of a storage error, or response signing/encryption fails.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with exponential backoff. If the error persists, raise it with Newton support and include `adjUid`, merchant id, request id, and response code/message.

## Retry And Idempotency Guidance

Fetch Dispute is read-only and does not mutate Newton state, so retrying the same business lookup is safe.

- Retry network timeouts, HTTP 5xx, object-storage download failures, and `INTERNAL_SERVER_ERROR` with exponential backoff.
- Regenerate `x-timestamp`, `iat`, and the request signature/encrypted envelope for each retry.
- Do not retry unchanged requests for `BAD_REQUEST`, `UNAUTHORIZED`, or malformed JWS/JWE responses.
- For `INVALID_DATA` with `MerchantDispute record not found`, retry only if the dispute was just created/notified or if you have corrected merchant/sub-merchant scoping.
- Because the API is read-only, no idempotency key is required beyond using the same `adjUid` for the lookup.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:789)
- Route handler and signature verification: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:5338)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, timestamp, and API-allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Merchant/sub-merchant header resolution: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:218)
- Request validation call: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:882)
- Request validation error helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4827)
- S2S/core response transformer: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1639)
- Product fetch flow: [src/Newton/Product/Merchant/Disputes/Core.hs](../../src/Newton/Product/Merchant/Disputes/Core.hs:61)
- Response field mapping and status normalization: [src/Newton/Product/Merchant/Disputes/Transformer.hs](../../src/Newton/Product/Merchant/Disputes/Transformer.hs:78)
- Proof download helper: [src/Newton/Product/Merchant/Disputes/Helper.hs](../../src/Newton/Product/Merchant/Disputes/Helper.hs:289)
- Merchant dispute lookup error: [src/Newton/Storage/Queries/MerchantDispute.hs](../../src/Newton/Storage/Queries/MerchantDispute.hs:66)
- Dispute enum definitions: [src/Newton/Types/Storage/MerchantDispute.hs](../../src/Newton/Types/Storage/MerchantDispute.hs:87)
