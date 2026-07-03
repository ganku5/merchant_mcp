# Update Dispute API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/disputes/update`

## Overview

Update Dispute is a merchant server-to-server API used to submit the merchant's response to an existing UPI dispute.

Merchants call this API after they have received or fetched a dispute identified by `adjUid`. The merchant can accept the dispute, reject it, or partially accept it. For rejection and partial acceptance flows, the merchant can also upload proof, such as fulfilment evidence or transaction-supporting documents.

Newton validates the merchant, request signature/encryption, dispute ownership, dispute state, TAT, response amount, and reason code. On success, Newton updates the dispute record to `SUBMITTED` and returns the updated dispute details.

Success from this API means Newton has accepted and stored the merchant response. It does not mean the overall dispute lifecycle is closed. Use dispute fetch/list responses or dispute callbacks to track final closure or reopening.

## Business Use Case

Use this API when the merchant backend needs to respond to a dispute before the dispute TAT expires.

Common cases:

- Accept a dispute and agree to the full requested adjustment amount.
- Reject a dispute and submit a valid rejection reason.
- Reject a dispute with supporting proof.
- Partially accept a dispute with a smaller response amount and supporting reason/proof.
- Submit a response after receiving a dispute callback or after discovering the dispute through the list/fetch APIs.

Do not use this API to create a new dispute, fetch proof data, or poll dispute status. Those are separate dispute flows.

## Integration Flow

1. Merchant receives a dispute notification or calls the dispute list/fetch API.
2. Merchant stores the dispute identifiers, especially `adjUid`, `type`, `reqAdjAmount`, `disputeReasonCode`, and `tat`.
3. Merchant decides the `merchantAction`, response `amount`, and `actionReasonCode`.
4. Merchant attaches `proof` and `proofName` when required for the selected action/dispute type.
5. Merchant sends the encrypted/signed S2S request to Newton before `tat`.
6. Newton decrypts/verifies the request, checks merchant API access, validates the dispute, optionally uploads proof, and updates the dispute to `SUBMITTED`.
7. Merchant stores the response payload for reconciliation and uses follow-up fetch/list/callbacks to track final status.

Important identifiers:

- `adjUid`: Newton dispute adjustment id. This is the primary identifier for this update API.
- `upiRequestId`: UPI transaction id associated with the disputed transaction.
- `merchantRequestId`: Merchant transaction/order reference associated with the dispute.
- `reqAdjAmount`: Adjustment amount requested by the dispute.
- `adjAmount`: Merchant response amount submitted through this API.

## Endpoint

```http
POST /api/{apiVersion}/merchants/disputes/update
```

Payloads use the standard Newton server-to-server request and response envelope configured during onboarding. The JSON examples in this guide show the decrypted business payload for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Conditional | Required only when the integration is configured to act as a sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required only when using sub-merchant headers. |
| `x-timestamp` | Yes | Current 13-digit epoch timestamp in milliseconds. Newton rejects stale timestamps outside the configured validity window. |
| `x-merchant-signature` | Conditional | Required for plain unsigned payload mode. In JWS/JWE mode, payload signature/encryption is carried in the envelope configured during onboarding. |
| `x-request-id` | No | Optional request id for tracing. Newton generates one if omitted. |
| `x-session-id` | No | Optional session id for tracing. Defaults to `x-request-id` if omitted. |
| `x-api-version` | No | If your onboarding profile uses this header, keep it aligned with the path version. No update-specific branching is visible in this code path. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version route segment, for example `4` when configured for your integration. |

### Authentication and Encryption

The route accepts the Newton S2S envelope type:

- JWE encrypted payload.
- JWS signed payload.
- Plain payload, when enabled for the merchant, protected by `x-merchant-signature`.

For this S2S path, a JWE payload is expected to decrypt to a signed payload so Newton can validate the source of the request.

For signed or encrypted requests, include `iat` inside the decrypted business payload. It must be a current 13-digit epoch timestamp in milliseconds. For plain unsigned payload mode, `iat` is not validated by the `validateIAT` branch, but sending it is harmless and keeps payloads consistent across modes.

Newton also verifies merchant configuration for this API. A merchant or sub-merchant allow-list/block-list can reject the call before product logic runs.

## Request

Route request type: `API.EncRequest TfS2S.UpdateDisputeS2SRequest`

Decrypted business payload type: `TfS2S.UpdateDisputeS2SRequest`

### Required Minimum

For full acceptance:

```json
{
  "adjUid": "ADJ202607020001",
  "amount": "100.00",
  "merchantAction": "ACCEPTED",
  "actionReasonCode": "106",
  "iat": "1783008000000"
}
```

For rejection with proof:

```json
{
  "adjUid": "ADJ202607020002",
  "amount": "100.00",
  "merchantAction": "REJECTED",
  "actionReasonCode": "105",
  "proofName": "fulfilment-note.txt",
  "proof": "data:text/plain;base64,T3JkZXIgZGVsaXZlcmVkIG9uIDIwMjYtMDYtMzA=",
  "iat": "1783008000000"
}
```

For partial acceptance:

```json
{
  "adjUid": "ADJ202607020003",
  "amount": "40.00",
  "merchantAction": "PARTIALLY_ACCEPTED",
  "actionReasonCode": "105",
  "proofName": "partial-acceptance-note.txt",
  "proof": "data:text/plain;base64,UGFydGlhbCBmdWxmaWxtZW50IGNvbmZpcm1lZA==",
  "iat": "1783008000000"
}
```

Replace `iat` with the current epoch timestamp in milliseconds when using signed/encrypted payload mode.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `adjUid` | string | Yes | No default. | Newton dispute adjustment id. Must be non-empty. The dispute must belong to the authenticated merchant context. |
| `amount` | string | Yes | No default. | Merchant response amount in strict two-decimal format, for example `100.00`. It must be greater than zero at request validation. Business validation depends on `merchantAction`: for `ACCEPTED` and `REJECTED`, it must equal `reqAdjAmount`; for `PARTIALLY_ACCEPTED`, it must be greater than `0.00` and less than `reqAdjAmount`. |
| `merchantAction` | string enum | Yes | No default. | Merchant response action. Client-supported values are `ACCEPTED`, `REJECTED`, and `PARTIALLY_ACCEPTED`. The enum parser also recognizes `NOT_ACTIONED`, but product validation rejects it with `Invalid merchant action`. |
| `actionReasonCode` | string | Yes | No default. | Reason code for the merchant action. It must be valid for the dispute `type` and selected action. For `PARTIALLY_ACCEPTED`, Newton validates against the same reason-code set as `REJECTED`. |
| `proof` | string | Conditional | If omitted, no proof file is uploaded. | Base64-encoded proof content. Send as a data URL, for example `data:application/pdf;base64,JVBERi0xLjQ...`. For non-accepted actions, Newton decodes and uploads it only when `proofName` is also supplied. For `ACCEPTED`, proof is ignored by storage behavior. |
| `proofName` | string | Conditional | If omitted, no proof name is stored. | File name for `proof`. The extension must be configured as an allowed dispute proof extension. The default configured list includes `doc`, `docx`, `pdf`, `jpg`, `jpeg`, `xls`, `xlsx`, `xps`, `png`, `zip`, `txt`, `rtf`, `bmp`, `rar`, and `tif`, but this may differ by environment. |
| `iat` | string | Conditional | Not validated for plain unsigned payload mode. | Issued-at timestamp used by signed/encrypted request validation. Must be a current 13-digit epoch timestamp in milliseconds when the request is JWS/JWE. |

### Nested Request Objects

This request has no nested objects. `proof` is an encoded file string, and `proofName` is the corresponding file name.

### Action and Amount Rules

| `merchantAction` | Amount rule | Proof behavior | Status after success |
| --- | --- | --- | --- |
| `ACCEPTED` | `amount` must equal the dispute `reqAdjAmount`. | Proof is not uploaded or stored for accepted actions. Do not send proof fields. | `SUBMITTED` |
| `REJECTED` | `amount` must equal the dispute `reqAdjAmount`. | Proof is optional for most dispute types, but should be sent when evidence is needed. For pre-arbitration/arbitration raise types, Newton rejects the request if both `proof` and `proofName` are omitted. | `SUBMITTED` |
| `PARTIALLY_ACCEPTED` | `amount` must be greater than `0.00` and less than `reqAdjAmount`. | Same proof handling as `REJECTED`. | `SUBMITTED` |
| `NOT_ACTIONED` | Not supported for client updates. | Not applicable. | Rejected with `Invalid merchant action`. |

Dispute types that require proof fields for `REJECTED` or `PARTIALLY_ACCEPTED` when both proof fields are omitted:

- `PREARBITRATION_RAISE`
- `DIFFERED_PREARBITRATION_RAISE`
- `ARBITRATION_RAISE`
- `DIFFERED_ARBITRATION_RAISE`

For robust integrations, send `proof` and `proofName` together whenever proof is required. Sending only one of the two fields can result in proof not being uploaded, or in an internal decode/upload error depending on which field is missing.

### Reason Code Compatibility

`actionReasonCode` must match the existing dispute `type`. For `PARTIALLY_ACCEPTED`, use the `REJECTED / PARTIALLY_ACCEPTED` column.

| Dispute `type` | `ACCEPTED` reason codes | `REJECTED` / `PARTIALLY_ACCEPTED` reason codes |
| --- | --- | --- |
| `COMPLAINT_RAISE` | `106` | `107`, `105`, `103`, `144` |
| `CHARGEBACK_RAISE` | `AC`, `111`, `AT`, `1095` | `1096`, `208`, `209` |
| `FRAUD_CHARGEBACK_RAISE` | `129` | `130`, `131`, `132` |
| `DIFFERED_CHARGEBACK_RAISE` | `AC`, `122`, `AT` | `123` |
| `PREARBITRATION_RAISE` | `AC`, `111`, `1099`, `AT` | `1098`, `112`, `113` |
| `DIFFERED_PREARBITRATION_RAISE` | `AC`, `AT`, `125` | `126` |
| `ARBITRATION_RAISE` | `AC`, `1101`, `AT` | `1102` |
| `DIFFERED_ARBITRATION_RAISE` | `AC`, `AT`, `1101` | `1102` |
| `REMITTER_NEGATIVE_GOOD_FAITH_CHARGEBACK` | `NA2` | `NB2`, `NR2`, `NR3` |

Newton derives the response `actionReason` text from this reason-code mapping.

### Proof File Handling

When `merchantAction` is not `ACCEPTED` and both `proofName` and decodable `proof` are present:

- Newton extracts the base64 content after the comma in `proof`.
- Newton validates the decoded file size against the configured maximum. The default configuration is below `1000 * 1024` bytes, but environments can override it.
- Newton validates the file extension from `proofName` against the configured allowed extension list.
- Newton uploads the decoded file to the configured dispute proof bucket.
- Newton stores the proof name as an array containing the first proof name, for example `["fulfilment-note.txt"]`.

The update API response does not return proof content. Use the fetch-dispute API if your integration is enabled to retrieve stored proof data.

### Defaults and Omitted Field Behavior

This request has no product-level defaults for `adjUid`, `amount`, `merchantAction`, or `actionReasonCode`.

- If `proof` and `proofName` are omitted, no proof is uploaded or stored. For the blocked pre-arbitration/arbitration dispute types listed above, rejection or partial acceptance is rejected when both are omitted.
- If `proofName` is omitted, the response omits `proofName`.
- If `iat` is omitted for signed/encrypted requests, request validation fails. If `iat` is omitted for plain unsigned payload mode, the `iat` validation branch does not run.
- On success, Newton always changes the dispute record to `SUBMITTED`.

## Response

Route response type: `RespHeaders (API.EncResponse TfS2S.UpdateDisputeS2SResponse)`

Decrypted business response type: `TfS2S.UpdateDisputeS2SResponse`

### Success Response

On success, the response envelope is:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "adjUid": "ADJ202607020001",
    "type": "COMPLAINT_RAISE",
    "adjDate": "2026-07-01T00:00:00+05:30",
    "upiRequestId": "UPI202607011234567890",
    "merchantRequestId": "ORDER12345",
    "reqAdjAmount": "100.00",
    "originatingChannel": "UDIR",
    "status": "SUBMITTED",
    "merchantAction": "ACCEPTED",
    "txnTimestamp": "2026-06-30T14:20:11+05:30",
    "txnAmount": "100.00",
    "adjAmount": "100.00",
    "upiResponseId": "617382910122",
    "actionReasonCode": "106",
    "actionReason": "Goods/services not provided",
    "tat": "2026-07-05T23:59:59+05:30",
    "disputeReason": "Customer account reversed online",
    "disputeReasonCode": "102",
    "merchantId": "MERCHANT123"
  }
}
```

Rejected response with proof:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "adjUid": "ADJ202607020002",
    "type": "COMPLAINT_RAISE",
    "adjDate": "2026-07-01T00:00:00+05:30",
    "upiRequestId": "UPI202607011234567891",
    "merchantRequestId": "ORDER12346",
    "reqAdjAmount": "100.00",
    "originatingChannel": "UDIR",
    "status": "SUBMITTED",
    "merchantAction": "REJECTED",
    "txnTimestamp": "2026-06-30T14:45:02+05:30",
    "txnAmount": "100.00",
    "adjAmount": "100.00",
    "upiResponseId": "617382910123",
    "actionReasonCode": "105",
    "actionReason": "Goods/services provided",
    "proofName": "fulfilment-note.txt",
    "tat": "2026-07-05T23:59:59+05:30",
    "disputeReason": "Customer account reversed online",
    "disputeReasonCode": "102",
    "merchantId": "MERCHANT123",
    "subMerchantId": "STORE001"
  }
}
```

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Updated dispute payload. Present on success. |

### Payload Fields

Optional `Maybe` fields are omitted from JSON when no value is available.

| Field | Type | Description |
| --- | --- | --- |
| `adjUid` | string | Dispute adjustment id that was updated. |
| `type` | string enum | Dispute type, for example `COMPLAINT_RAISE` or `CHARGEBACK_RAISE`. |
| `adjDate` | string | Dispute adjustment date in IST text format, for example `2026-07-01T00:00:00+05:30`. |
| `upiRequestId` | string | UPI transaction id associated with the dispute. |
| `merchantRequestId` | string | Merchant transaction/order reference associated with the dispute. |
| `reqAdjAmount` | string | Requested dispute adjustment amount, formatted with two decimals. |
| `originatingChannel` | string | Dispute-originating channel stored on the dispute, commonly `UDIR` or `UMOB`. |
| `status` | string | Dispute status after the update. Success from this API returns `SUBMITTED`. Other APIs can later return `PENDING`, `CLOSED`, or `REOPENED` depending on lifecycle. |
| `merchantAction` | string | Merchant action stored on the dispute. Omitted only when stored action is `NOT_ACTIONED`, which should not happen after a successful update request. |
| `txnTimestamp` | string | Original transaction timestamp when the transaction record is found. Omitted when transaction details are unavailable. |
| `txnAmount` | string | Original transaction amount when the transaction record is found. |
| `adjAmount` | string | Merchant response amount submitted through this API. |
| `upiResponseId` | string | UPI response/RRN-like identifier when available on the transaction. |
| `actionReasonCode` | string | Merchant action reason code submitted in the request. |
| `actionReason` | string | Reason description derived from `type` and `actionReasonCode`. |
| `proofName` | string | Proof file name echoed from the request when supplied. Proof content is not returned by this API. |
| `tat` | string | Dispute turn-around-time deadline in IST text format. |
| `disputeReason` | string | Original dispute reason description derived from `type` and `disputeReasonCode`. |
| `disputeReasonCode` | string | Original dispute/request adjustment reason code. |
| `merchantId` | string | External merchant id for the authenticated merchant. |
| `subMerchantId` | string | External sub-merchant id when the request is processed in a sub-merchant context. |

### How to Interpret Success

Treat `status = SUCCESS` and `responseCode = SUCCESS` as confirmation that Newton accepted the API request and persisted the merchant response.

Treat `payload.status = SUBMITTED` as the current dispute workflow state. It means the merchant response has been submitted into Newton's dispute process. It is not a final customer/bank dispute outcome.

After a successful update:

- Do not blindly retry the same update. A second call can fail with `Dispute is already submitted`.
- Store `adjAmount`, `merchantAction`, `actionReasonCode`, and `proofName` from the payload.
- Use dispute fetch/list or dispute callbacks to observe final lifecycle changes such as `CLOSED` or `REOPENED`.

## Error Handling

Failures use the standard Newton error response body with `status: "FAILURE"`, a concrete `responseCode`, and a diagnostic `responseMessage`.

The HTTP status and response wrapping can vary by failure layer. Some product validation failures use a failure body with HTTP 200 or HTTP 500, while authentication and encryption failures generally use HTTP 401/400. Clients should always parse the error body, after decrypting when applicable, and make decisions from `status`, `responseCode`, and `responseMessage`, not HTTP status alone.

### Validation Failures

Invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Empty `adjUid`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"adjUid field is empty\""
}
```

Invalid timestamp format for `x-timestamp` or signed/encrypted `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

### Authentication, Encryption, and Merchant Access Failures

Missing or invalid merchant signature for plain payload mode:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

JWS verification failure or JWE decryption failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not allowed for the merchant/sub-merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Merchant IP whitelist failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Lookup and Business Rule Failures

Dispute not found for the authenticated merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "MerchantDispute record not found"
}
```

Dispute already submitted:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Dispute is already submitted"
}
```

Dispute closed:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Dispute is closed"
}
```

TAT expired:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "TAT is expired"
}
```

Invalid amount for the selected action:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid update amount"
}
```

Invalid reason code for the dispute type/action:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid reason code"
}
```

`NOT_ACTIONED` sent as an update:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid merchant action"
}
```

Rejected or partially accepted pre-arbitration/arbitration dispute without proof fields:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Dispute is not allowed"
}
```

### Proof File Failures

Unsupported proof file extension:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid File Type"
}
```

Proof file exceeds the configured size limit, or base64 decoding fails in the file validation branch:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "FileSize Limit Exceeded"
}
```

`proofName` is present but proof is missing or does not contain extractable base64 content:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Proof bucket is not configured or storage upload returns a non-200 status:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Downstream and Unexpected Failures

This update path does not make a synchronous NPCI dispute submission call in the traced code. Downstream failures in this API are primarily proof-storage upload failures or database failures while finding/updating the dispute.

Unexpected server or database failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling

This API does not accept a separate idempotency key. The effective business key is the existing `adjUid`, and a successful update changes the dispute to `SUBMITTED`.

Recommended client behavior:

- Do not retry after receiving a success response. Store the returned payload and track the dispute through fetch/list/callbacks.
- If the request times out or the connection drops before a response is received, call the fetch-dispute API for the same `adjUid`. If the dispute shows your `merchantAction`, `adjAmount`, `actionReasonCode`, and `status = SUBMITTED`, treat the original update as successful.
- Retry transient `INTERNAL_SERVER_ERROR` only after reconciling current dispute state. A retry after the first attempt actually succeeded can fail with `Dispute is already submitted`.
- Do not retry validation failures without changing the request.
- Do not retry authentication, encryption, timestamp, or merchant access failures until credentials, headers, timestamps, or merchant configuration are fixed.
- For proof upload failures, verify file extension, decoded file size, and data URL formatting before retrying.

## Source References

- API version prefix: [src/Newton/App/Routes/Core.hs:114](../../src/Newton/App/Routes/Core.hs:114)
- Dispute route definition: [src/Newton/App/Routes/Core.hs:783](../../src/Newton/App/Routes/Core.hs:783)
- Update route handler, logging, signature verification, transformer call: [src/Newton/App/Routes/Core.hs:5319](../../src/Newton/App/Routes/Core.hs:5319)
- S2S request extraction and payload verification entry point: [src/Newton/Utils/Routes.hs:40](../../src/Newton/Utils/Routes.hs:40), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- S2S envelope request/response types: [src/Newton/Types/API/RequestBody.hs:15](../../src/Newton/Types/API/RequestBody.hs:15), [src/Newton/Types/API/RequestBody.hs:48](../../src/Newton/Types/API/RequestBody.hs:48), [src/Newton/Types/API/RequestBody.hs:69](../../src/Newton/Types/API/RequestBody.hs:69)
- JWS/JWE/plain payload verification behavior: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature, timestamp, API allow-list/block-list checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:205](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:205)
- Timestamp validation: [src/Newton/Utils/DateTime.hs:108](../../src/Newton/Utils/DateTime.hs:108)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs:875](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:875)
- S2S request/response types and validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs:4746](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4746)
- S2S core request and response transformers: [src/Newton/Services/Transformer/ServerToServer/Helper.hs:1636](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1636), [src/Newton/Services/Transformer/ServerToServer/Helper.hs:1642](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1642)
- Product update flow, proof upload, and business validation: [src/Newton/Product/Merchant/Disputes/Core.hs:70](../../src/Newton/Product/Merchant/Disputes/Core.hs:70), [src/Newton/Product/Merchant/Disputes/Core.hs:98](../../src/Newton/Product/Merchant/Disputes/Core.hs:98), [src/Newton/Product/Merchant/Disputes/Core.hs:138](../../src/Newton/Product/Merchant/Disputes/Core.hs:138)
- Amount and business error rules: [src/Newton/Product/Merchant/Disputes/Core.hs:151](../../src/Newton/Product/Merchant/Disputes/Core.hs:151), [src/Newton/Product/Merchant/Disputes/Core.hs:162](../../src/Newton/Product/Merchant/Disputes/Core.hs:162)
- Reason-code mapping, blocked dispute types, and proof base64 extraction: [src/Newton/Product/Merchant/Disputes/Helper.hs:43](../../src/Newton/Product/Merchant/Disputes/Helper.hs:43), [src/Newton/Product/Merchant/Disputes/Helper.hs:203](../../src/Newton/Product/Merchant/Disputes/Helper.hs:203), [src/Newton/Product/Merchant/Disputes/Helper.hs:206](../../src/Newton/Product/Merchant/Disputes/Helper.hs:206), [src/Newton/Product/Merchant/Disputes/Helper.hs:209](../../src/Newton/Product/Merchant/Disputes/Helper.hs:209)
- Response payload mapping and dispute status transformation: [src/Newton/Product/Merchant/Disputes/Transformer.hs:18](../../src/Newton/Product/Merchant/Disputes/Transformer.hs:18), [src/Newton/Product/Merchant/Disputes/Transformer.hs:107](../../src/Newton/Product/Merchant/Disputes/Transformer.hs:107)
- Dispute lookup/update storage helpers: [src/Newton/Storage/Queries/MerchantDispute.hs:66](../../src/Newton/Storage/Queries/MerchantDispute.hs:66), [src/Newton/Storage/Queries/MerchantDispute.hs:84](../../src/Newton/Storage/Queries/MerchantDispute.hs:84)
- Shared success and error response constants: [src/Newton/Constants/APIErrorCode.hs:44](../../src/Newton/Constants/APIErrorCode.hs:44), [src/Newton/Constants/APIErrorCode.hs:61](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs:125](../../src/Newton/Constants/APIErrorCode.hs:125), [src/Newton/Constants/APIErrorCode.hs:151](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs:250](../../src/Newton/Constants/APIErrorCode.hs:250)
