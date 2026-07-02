# Complaint Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/complaints/status`

## Overview

Complaint Status is a server-to-server API used to fetch the latest known status of a complaint raised for a UPI transaction.

The merchant calls this API after a complaint is raised, or when a pending complaint needs to be reconciled against the latest status available to Newton. Newton first validates the merchant, customer, transaction, and complaint linkage. When the complaint is eligible for a fresh downstream status check, Newton may poll NPCI using the complaint and transaction details, update Newton's stored records, and return the updated complaint state. When polling is not eligible, Newton returns the latest stored complaint status.

Use this API for complaint reconciliation, merchant support dashboards, back-office follow-up, and client-side customer support workflows that need the latest complaint outcome.

## Business Use Case

Complaint Status helps merchants:

- Check whether a raised complaint is still pending, resolved, or failed.
- Reconcile a support ticket against Newton's stored complaint state.
- Fetch the complaint adjustment fields returned by NPCI when a complaint is resolved.
- Poll safely without creating a new complaint or duplicate request.
- Resolve a specific complaint by complaint id when more than one complaint can exist for the original transaction.
- Check UDIR refund complaints by using the `REFUND` status type.

This API is a status lookup. It does not raise or resolve a complaint by itself. However, when Newton is allowed to query NPCI for a fresh status, the lookup can update Newton's stored complaint and transaction records before returning the response.

## Integration Flow

1. Merchant raises a complaint through the complaint raise flow and stores the returned `gatewayComplaintId`.
2. Merchant calls Complaint Status with the original transaction UPI request id and, when checking a specific complaint, the complaint's `gatewayComplaintId`.
3. Newton decrypts and verifies the request using the standard S2S integration process.
4. Newton validates the request body and merchant/customer configuration.
5. Newton finds the original transaction and complaint.
6. Newton returns the stored complaint status, or polls NPCI first when the complaint is eligible for a fresh status check.
7. Merchant interprets `payload.gatewayResponseStatus` as the complaint outcome and stores the response for reconciliation.

Important identifiers:

- `originalTransactionUpiRequestId`: The UPI request id of the original transaction for which the complaint was raised.
- `originalUpiRequestId`: The complaint UPI request id. This is the `gatewayComplaintId` returned by complaint raise. Omit it only when you want Newton to find the default self-initiated complaint for the transaction.
- `merchantCustomerId`: Merchant's customer identifier. Required unless the merchant is configured to allow this API without it.

## Endpoint

```http
POST /api/{apiVersion}/merchants/complaints/status
```

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the API version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Current 13-digit millisecond timestamp, used for signature freshness validation. |
| `x-merchant-signature` | Required for unsigned/plain payload mode. Compute using the onboarding signature process. |
| `x-sub-merchant-id` | Conditional. Send only when your integration uses sub-merchant credentials. |
| `x-sub-merchant-channel-id` | Conditional. Send only when your integration uses sub-merchant credentials. |

Authentication, signing, encryption, key ids, and response decryption follow the standard Newton S2S process shared during onboarding. For encrypted or signed request envelopes, include `iat` in the decrypted business payload because the signature middleware validates it. Both `x-timestamp` and `iat` are validated as 13-digit millisecond timestamps within the configured freshness window. Requests can also be rejected by merchant API allowlisting/blocklisting and IP allowlist checks.

## Request

### Required Minimum

For a normal complaint status check where the complaint should be resolved from the original transaction:

```json
{
  "merchantCustomerId": "CUST10001",
  "originalTransactionUpiRequestId": "TXN202607020001",
  "type": "DISPUTE",
  "iat": "1782967530000"
}
```

For a specific complaint, send the complaint id returned earlier as `gatewayComplaintId`:

```json
{
  "merchantCustomerId": "CUST10001",
  "originalTransactionUpiRequestId": "TXN202607020001",
  "originalUpiRequestId": "CMP202607020001",
  "type": "DISPUTE",
  "iat": "1782967560000",
  "udfParameters": "{\"supportTicketId\":\"SUP-908172\"}"
}
```

For a UDIR refund complaint:

```json
{
  "merchantCustomerId": "CUST10001",
  "originalTransactionUpiRequestId": "TXN202607020001",
  "originalUpiRequestId": "CMP202607020045",
  "type": "REFUND",
  "iat": "1782967680000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Conditional | If omitted, Newton accepts the request only when merchant configuration `allowWithoutMerchantCustomerId` is enabled. When allowed, Newton derives the merchant-customer context from the original transaction. Otherwise the request fails with `BAD_REQUEST`. | Merchant's customer identifier for the customer linked to the original transaction. If supplied, it must match the transaction's merchant-customer relationship. |
| `originalTransactionUpiRequestId` | string | Yes | No default. | UPI request id of the original transaction. This is not the merchant order id. Newton uses it to find the transaction across recent transaction partitions. |
| `originalUpiRequestId` | string | No | If omitted, Newton looks for the self-initiated complaint linked to the original transaction. | Complaint UPI request id, returned as `gatewayComplaintId` in complaint raise/status responses. Send it when checking a specific complaint. |
| `type` | string | Yes | No default. | Complaint status check subtype. Allowed values: `DISPUTE`, `DISPUTEHIST`, `TXNDISPUTE`, `REFUND`. Use `REFUND` for UDIR refund complaints; refund complaints checked with any other type are rejected. |
| `iat` | string | Conditional | No default. Required for encrypted/signed request envelopes. | Issued-at timestamp used by the S2S signature/encryption validation layer. Send a 13-digit millisecond timestamp within the freshness window shared during onboarding. |
| `udfParameters` | string | No | Omitted from the response when not supplied. | Stringified JSON object for merchant-defined metadata. Newton validates it as JSON-object text and echoes it in the response. |

### Defaults and Omitted Field Behavior

Fields not listed above have no default.

- `originalUpiRequestId`: omit only when a transaction has one self-initiated complaint and you want Newton to find it by transaction id. If multiple complaints can exist, store and send the `gatewayComplaintId` from complaint raise.
- `merchantCustomerId`: omit only if Newton has enabled `allowWithoutMerchantCustomerId` for the merchant.
- `udfParameters`: no processing default; if omitted, `udfParameters` is omitted from the success response.
- Request has no nested business objects.

### Validation Notes

- `originalTransactionUpiRequestId` must be non-empty.
- `originalUpiRequestId`, when supplied, must be 1 to 35 alphanumeric characters.
- `merchantCustomerId`, when supplied, must be 1 to 256 characters and match the allowed merchant customer id character set.
- `udfParameters`, when supplied, must be a JSON object encoded as a string and must pass the configured character checks.
- Invalid enum values for `type` fail request parsing/validation before business lookup.
- If the complaint stored in Newton is a refund complaint, `type` must be `REFUND`.

## Processing Behavior

Complaint Status performs these checks in order:

1. Decrypts/verifies the S2S envelope and merchant signature.
2. Validates the decrypted request body.
3. Finds the merchant and validates that the API is enabled for that merchant/sub-merchant.
4. Finds the original payer transaction using `originalTransactionUpiRequestId`.
5. Resolves the merchant customer and verifies it belongs to the requesting merchant.
6. Finds the complaint either by `originalUpiRequestId` or by the original transaction's self-initiated complaint.
7. Decides whether to poll NPCI or return the stored complaint state.

Newton may skip the downstream NPCI poll and return the stored status when:

- The complaint status is already terminal: `CLOSED` or `FAILURE`.
- The complaint is on-us for the configured on-us payee IFSC.
- The complaint is outside the configured status-check time window.
- Status-check rate limiting or cooldown prevents another downstream poll.
- The UDIR polling limit for the original transaction has been reached.

This means a successful API response can be either a freshly updated status or the latest status already stored in Newton.

## Response

### Response Envelope

On a successfully served status lookup, Newton returns:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. For a successful lookup this is `SUCCESS`, even if the complaint itself is pending or failed. |
| `responseCode` | string | Top-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level response message. Success value is `SUCCESS`. |
| `payload` | object | Complaint status details. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id for the owning merchant. |
| `merchantChannelId` | string | Merchant channel id for the owning merchant. |
| `merchantRequestId` | string | Merchant request id stored in the complaint metadata when the complaint was raised. |
| `merchantCustomerId` | string | Merchant customer id linked to the complaint/transaction. |
| `customerMobileNumber` | string | Customer mobile number, trimmed by Newton before returning. |
| `transactionAmount` | string | Original transaction amount formatted with two decimal places. |
| `payerVpa` | string | Payer VPA from the original transaction. |
| `payeeVpa` | string | Payee VPA from the original transaction. |
| `reqAdjFlag` | string | Requested adjustment flag stored with the complaint. |
| `reqAdjCode` | string | Requested adjustment code stored with the complaint. |
| `reqAdjAmount` | string | Requested adjustment amount formatted with two decimal places. |
| `adjAmount` | string | Actual adjusted amount returned by NPCI when available. Omitted when not available. |
| `adjFlag` | string | Actual adjustment flag returned by NPCI when available. Omitted when not available. |
| `adjCode` | string | Actual adjustment code returned by NPCI when available. Omitted when not available. |
| `crn` | string | Complaint reference number when available. Omitted when not available. |
| `gatewayComplaintId` | string | Complaint UPI request id. Store this and send it as `originalUpiRequestId` for specific follow-up checks. |
| `gatewayReferenceId` | string | Complaint UPI response/reference id stored by Newton. |
| `gatewayResponseCode` | string | Complaint response code stored in the complaint NPCI response. `00` is treated as resolved successfully; `01` is treated as pending. Other values are mapped through Newton/NPCI error-code messages where available. |
| `gatewayResponseMessage` | string | Human-readable message for `gatewayResponseCode`. |
| `gatewayResponseStatus` | string | Current complaint status: `OPEN`, `COMPLAINT_RECEIVED`, `PENDING`, `CLOSED`, or `FAILURE`. Use this field for business interpretation. |

### Status Interpretation

Use `payload.gatewayResponseStatus` as the complaint outcome:

| `gatewayResponseStatus` | Client handling |
| --- | --- |
| `OPEN` | Complaint exists but has not reached a final downstream outcome. Poll later using backoff or wait for callback where configured. |
| `COMPLAINT_RECEIVED` | Complaint was received/registered. Treat as non-terminal and poll later. |
| `PENDING` | Complaint is still pending. Do not create a new complaint for the same issue. Poll later or wait for callback. |
| `CLOSED` | Complaint is resolved. Read `adjAmount`, `adjFlag`, `adjCode`, and `crn` when present. Stop polling. |
| `FAILURE` | Complaint ended in a failed/rejected state. Stop automated polling and surface the failure according to your support workflow. |

For refund complaints, Newton maps downstream code `00` to `CLOSED`; `01`, `JPREFD`, and timeout-like `UTO*` codes to `PENDING`; `NAC*` and most other codes to `FAILURE`.

For non-refund complaints, Newton maps `01`, `RB`, `JPRTO`, `JPBTO`, `JPBUU`, `JPPUU`, `JPPTO`, and `UTO*` to `PENDING`; `U48` and `NAC*` to `FAILURE`; and other resolved codes to `CLOSED`.

## Success Response Examples

### Pending Complaint

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER10001",
    "merchantCustomerId": "CUST10001",
    "customerMobileNumber": "9876543210",
    "transactionAmount": "250.00",
    "payerVpa": "customer@upi",
    "payeeVpa": "merchant@upi",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U008",
    "reqAdjAmount": "250.00",
    "gatewayComplaintId": "CMP202607020001",
    "gatewayReferenceId": "608184991234",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Complaint is in pending state",
    "gatewayResponseStatus": "PENDING"
  },
  "udfParameters": "{\"supportTicketId\":\"SUP-908172\"}"
}
```

In this response, optional fields such as `adjAmount`, `adjFlag`, `adjCode`, and `crn` are omitted because Newton does not yet have final adjustment data.

### Closed Complaint

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER10001",
    "merchantCustomerId": "CUST10001",
    "customerMobileNumber": "9876543210",
    "transactionAmount": "250.00",
    "payerVpa": "customer@upi",
    "payeeVpa": "merchant@upi",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U008",
    "reqAdjAmount": "250.00",
    "adjAmount": "250.00",
    "adjFlag": "PBRB",
    "adjCode": "U008",
    "crn": "CRN608184991234",
    "gatewayComplaintId": "CMP202607020001",
    "gatewayReferenceId": "608184991234",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your complaint is resolved successfully",
    "gatewayResponseStatus": "CLOSED"
  }
}
```

## Error Handling

Failure responses use the standard S2S response transport where possible. Do not rely only on the HTTP status code. Several validation, lookup, downstream, and unexpected-error paths are returned with a Newton error body and may use HTTP `200` at the transport layer. Clients should inspect `status`, `responseCode`, and `responseMessage` whenever a decrypted body is available.

### Validation Failures

Empty `originalTransactionUpiRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"Field is empty\""
}
```

Invalid `originalUpiRequestId` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\""
}
```

Invalid `udfParameters` JSON-object string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Missing `merchantCustomerId` when the merchant is not configured to allow omission:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantCustomerId is mandatory"
}
```

### Authentication, Signature, And Encryption Failures

Missing or invalid merchant headers, invalid merchant signature, invalid encrypted payload, invalid signed payload, timestamp failures, or IP allowlist failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Malformed decrypted/signed payloads can return an invalid-data body:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"originalTransactionUpiRequestId\" not found"
}
```

### Merchant Configuration Failures

If the merchant or sub-merchant is not enabled for this API, or the API is blocked by merchant configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If `merchantCustomerId` is omitted without the required merchant configuration, Newton returns the `BAD_REQUEST` example shown in validation failures.

### Lookup And Business Failures

Original transaction not found for `originalTransactionUpiRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Original record not found"
}
```

Complaint not found for the transaction or complaint id:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

Transaction or complaint does not belong to the supplied merchant/customer context:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Refund complaint checked with a non-`REFUND` type:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Type should be REFUND for udir refunds"
}
```

### Downstream Failures

NPCI timeout while Newton is attempting a fresh status poll:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U91",
  "responseMessage": "UPI service is not reachable at the moment for transactional apis"
}
```

The suffix after `SERVICE_UNAVAILABLE_NPCI_` is the downstream timeout code when available; otherwise Newton uses `NA`.

NPCI response could not be interpreted:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

Some downstream immediate failures include an error code but still leave Newton with an existing stored complaint state. In those cases Newton can return a top-level `SUCCESS` response with the latest stored `gatewayResponseStatus`. Always use `payload.gatewayResponseStatus` and `payload.gatewayResponseCode` for complaint outcome, not only the top-level API status.

### Unexpected Errors

Unexpected decode failures, missing internal state, or unhandled exceptions can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry, Idempotency, And Client Handling

Complaint Status is safe to call repeatedly with the same identifiers. It does not create a new complaint. It can, however, update Newton's stored complaint/transaction status when a downstream poll succeeds.

Recommended handling:

- Store `gatewayComplaintId` from complaint raise and send it as `originalUpiRequestId` for follow-up checks.
- Treat `CLOSED` and `FAILURE` as terminal for automated polling.
- Treat `OPEN`, `COMPLAINT_RECEIVED`, and `PENDING` as non-terminal. Retry later with backoff or rely on complaint callbacks where configured.
- Avoid tight polling loops. Newton has UDIR polling and status-check rate limits, and may return the stored status instead of polling NPCI again.
- Retry `SERVICE_UNAVAILABLE_NPCI_*`, network timeouts, and transient `INTERNAL_SERVER_ERROR` with exponential backoff.
- Do not retry `BAD_REQUEST`, `INVALID_DATA`, `REQUEST_NOT_FOUND`, `UNAUTHORIZED`, or `API NOT ENABLED` without correcting the request, merchant configuration, credentials, or identifiers.
- Reuse the same `originalTransactionUpiRequestId` and `originalUpiRequestId` for the same complaint; do not raise another complaint just because status remains pending.

## Source References

- Route type: [Core.hs](../../src/Newton/App/Routes/Core.hs:631)
- Route handler and merchant signature verification: [Core.hs](../../src/Newton/App/Routes/Core.hs:4670)
- S2S request/response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- S2S request body extraction: [Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Payload verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, timestamp, API enablement, and IP checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp freshness validator: [DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Request and core response payload types: [Types.hs](../../src/Newton/Product/Merchant/Complaints/Types.hs:106)
- Request validation instance: [Types.hs](../../src/Newton/Product/Merchant/Complaints/Types.hs:131)
- Complaint status API validation: [ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:168)
- Common field validators: [Common.hs](../../src/Newton/Validation/Common.hs:174), [Common.hs](../../src/Newton/Validation/Common.hs:275), [Common.hs](../../src/Newton/Validation/Common.hs:311), [Common.hs](../../src/Newton/Validation/Common.hs:575)
- Request validation error wrapping: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Complaint status business route: [Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:175)
- Complaint polling decision logic: [Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:193)
- Downstream status initiation and response validation: [Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:219)
- Complaint status time-window validation: [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2437)
- UDIR polling limiter: [RateLimiter.hs](../../src/Newton/App/Middlewares/Authentication/RateLimiter.hs:172)
- Status-check rate limiter: [TxnStatus.hs](../../src/Newton/Product/Sherlock/TxnStatus.hs:33)
- Downstream ReqChkTxn construction and handling: [ComplaintV2.hs](../../src/Newton/Product/ComplaintV2.hs:129)
- NPCI complaint status update logic: [Helper.hs](../../src/Newton/Product/NpciSwitch/Meta/Complaints/Helper.hs:261)
- Merchant/customer ownership validation: [Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:351)
- Complaint status response payload construction: [Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:146)
- S2S response type: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:153)
- S2S response builder: [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:179)
- Generic complaint status response payload type: [Types.hs](../../src/Newton/Services/Transformer/Generic/Types.hs:147)
- Complaint status type values: [Common.hs](../../src/Newton/Types/API/Common.hs:113)
- Stored complaint status values: [Complaint.hs](../../src/Newton/Types/Storage/Complaint.hs:63)
- Complaint status code mapping: [Utils.hs](../../src/Newton/Utils/Utils.hs:3213), [Utils.hs](../../src/Newton/Utils/Utils.hs:3253)
- Error response constructors: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:34), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:401), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:419), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:797)
