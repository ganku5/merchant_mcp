# Resolve Complaint API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/complaints/resolve`

## Overview

Resolve Complaint is a merchant server-to-server API used to resolve an existing UPI complaint recorded in Newton.

The merchant calls this API after a complaint has already been raised or received and the merchant backend has decided the resolution adjustment to send to NPCI. Newton validates the merchant, request signature, original payee transaction, existing complaint, and adjustment fields. If the complaint is still non-terminal, Newton sends a `RespComplaint` to NPCI and updates the stored complaint. If the complaint is already terminal, Newton returns the stored complaint result without making another NPCI call.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Use this API when the merchant needs to:

- Resolve a complaint that already exists in Newton for a UPI transaction where the merchant is the payee.
- Send the final adjustment flag, adjustment code, optional adjustment amount, and remarks for the complaint resolution.
- Close a complaint after accepting or otherwise responding to the complaint according to the UDIR/NPCI adjustment flow agreed during onboarding.
- Reconcile merchant support or operations tickets using Newton's complaint id, original transaction id, CRN, gateway reference id, and returned gateway response status.

Do not use this API to raise a new complaint or only check complaint status. Use Complaint Raise to create a complaint, and Complaint Status or List Complaints to retrieve the latest state without attempting a resolution.

## Integration Flow

1. Merchant identifies the existing complaint to resolve, usually from the earlier `gatewayComplaintId`.
2. Merchant identifies the original transaction UPI request id for the transaction under complaint.
3. Merchant generates a new `merchantRequestId` for this resolve attempt.
4. Merchant prepares the decrypted business payload with `originalUpiRequestId`, `originalTransactionUpiRequestId`, `adjFlag`, `adjCode`, and optional `adjAmount`, `remarks`, and `udfParameters`.
5. Merchant signs/encrypts the request using the Newton S2S integration process.
6. Newton decrypts/verifies the request, validates merchant/API configuration, and validates the business payload.
7. Newton finds the original payee-side transaction using `originalTransactionUpiRequestId`.
8. Newton finds the existing complaint using `originalUpiRequestId` and verifies it is linked to the original transaction.
9. If the complaint is not already `CLOSED` or `FAILURE`, Newton sends the resolution response to NPCI and updates the complaint. If the complaint is already terminal, Newton skips NPCI and returns the stored result.
10. Merchant decrypts the response and interprets `payload.gatewayResponseStatus` and `payload.gatewayResponseCode`.

Important identifiers:

- `originalTransactionUpiRequestId`: UPI request id of the original transaction under complaint. Newton uses this to find the payee transaction.
- `originalUpiRequestId`: Existing complaint UPI request id. This is the `gatewayComplaintId` returned by Complaint Raise/Status/List.
- `merchantRequestId`: Merchant-generated reference for this resolve API call. It is used for tracing and returned in the response, but the resolve flow does not deduplicate by this value.
- `gatewayReferenceId`: Newton/NPCI complaint reference stored with the complaint.
- `crn`: Complaint reference number when available.

## Endpoint

```http
POST /api/{apiVersion}/merchants/complaints/resolve
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. If omitted or invalid, Newton falls back to base version `0`. |
| `x-merchant-id` | Merchant id issued by Newton. |
| `x-merchant-channel-id` | Merchant channel id issued by Newton. |
| `x-sub-merchant-id` | Conditional. Send only when your integration uses sub-merchant credentials. |
| `x-sub-merchant-channel-id` | Conditional. Send only when your integration uses sub-merchant credentials. |
| `x-timestamp` | Current 13-digit millisecond timestamp used for signature freshness validation. |
| `x-raw-body` | Raw HTTP request body used for signature verification. For encrypted/signed envelopes, this is the raw envelope body. |
| `x-merchant-signature` | Required for unsigned/plain payload mode. Not required for JWE/JWS payloads where the envelope supplies cryptographic verification. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. In production, send the encrypted or signed envelope configured for the merchant. The decrypted examples in this guide are not the wire format unless Newton has explicitly enabled that mode for your environment.

For encrypted or signed request envelopes, include `iat` in the decrypted business payload. Newton validates `iat` before business processing. Requests can also be rejected by merchant API allowlisting/blocklisting and IP allowlist checks.

### Path and Query Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route version segment in `/api/{apiVersion}`. |

This endpoint does not accept query parameters.

## Request

### Required Minimum

For a full-amount resolve, omit `adjAmount`. Newton defaults the adjustment amount to the original transaction amount.

```json
{
  "merchantRequestId": "RES202607020001",
  "originalUpiRequestId": "CMP202607010001",
  "originalTransactionUpiRequestId": "TXN202606300001",
  "remarks": "Complaint accepted and resolved",
  "adjFlag": "TCC",
  "adjCode": "102",
  "iat": "1782967530000"
}
```

For an explicit adjustment amount:

```json
{
  "merchantRequestId": "RES202607020002",
  "originalUpiRequestId": "CMP202607010002",
  "originalTransactionUpiRequestId": "TXN202606300002",
  "remarks": "Partial adjustment approved",
  "adjAmount": "75.00",
  "adjFlag": "TCC",
  "adjCode": "103",
  "iat": "1782967560000",
  "udfParameters": "{\"supportTicketId\":\"SUP-908172\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Merchant-generated reference for this resolve attempt. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `originalUpiRequestId` | string | Yes | No default. | Existing complaint UPI request id, returned as `gatewayComplaintId` by complaint APIs. Must be 1 to 35 alphanumeric characters. |
| `originalTransactionUpiRequestId` | string | Yes | No default. | UPI request id of the original transaction under complaint. Newton looks up a payee-side transaction using this value. Must be 1 to 35 alphanumeric characters. |
| `remarks` | string | No | If omitted, Newton sends `Complaint resolve` in the downstream NPCI response payload and stores `Complaint Resolved` when the resolve is accepted. | Resolve note/remarks. Must be 1 to 255 characters when supplied. |
| `adjAmount` | string | No | Defaults to the original transaction amount. | Adjustment amount for the resolution in two-decimal format, for example `100.00`. Must be greater than zero when supplied. |
| `adjFlag` | string | Yes | No default. | Resolve adjustment flag agreed for the complaint use case. The S2S validator only checks that it is non-empty; invalid business values can still fail downstream or produce a non-success gateway status. |
| `adjCode` | string | Yes | No default. | Resolve adjustment code agreed for the complaint use case. The S2S validator only checks that it is non-empty; invalid business values can still fail downstream or produce a non-success gateway status. |
| `iat` | string | Conditional | No business default. Required for encrypted/signed request envelopes. | Issued-at timestamp used by the S2S signature/encryption validation layer. Send a 13-digit millisecond timestamp within the freshness window shared during onboarding. |
| `udfParameters` | string | No | Omitted from the response when not supplied. | Stringified JSON object for merchant-defined metadata. Newton validates it as JSON-object text and echoes it in the response. |

### Defaults and Omitted Field Behavior

- `adjAmount` omitted means Newton uses the original transaction amount for the resolution adjustment.
- `remarks` omitted uses `Complaint resolve` in the outbound NPCI `RespComplaint` and `Complaint Resolved` in the stored complaint if the resolve succeeds.
- `udfParameters` omitted means the success response omits `udfParameters`.
- Optional fields with `null` values are treated the same as omitted by the Haskell `Maybe` request type. Prefer omitting unused fields.
- `merchantRequestId` is not an idempotency lookup key in this flow. Reusing it does not by itself prevent another non-terminal resolve attempt.

### Nested Request Objects

This API has no nested request objects. The decrypted business payload is a flat JSON object. `udfParameters`, if used, is a JSON-object string rather than a nested JSON object.

### Validation Notes

- `merchantRequestId` must be 1 to 35 characters and match the merchant request id character set.
- `originalUpiRequestId` and `originalTransactionUpiRequestId` must be 1 to 35 alphanumeric characters.
- `remarks`, when supplied, must be 1 to 255 characters and pass the configured remarks character validation.
- `adjAmount`, when supplied, must match `^[0-9]+\\.[0-9][0-9]$` and be greater than `0.0`.
- `adjFlag` and `adjCode` must be non-empty. Business-valid values should be taken from the UDIR/NPCI adjustment mapping agreed during onboarding.
- `udfParameters`, when supplied, must be a JSON object encoded as a string and must pass the configured character checks.
- Missing required fields can fail JSON parsing before business validation.

## Request Examples

### Resolve for Full Original Amount

`adjAmount` is omitted, so Newton uses the original transaction amount.

```json
{
  "merchantRequestId": "RES202607020001",
  "originalUpiRequestId": "CMP202607010001",
  "originalTransactionUpiRequestId": "TXN202606300001",
  "remarks": "Customer complaint accepted",
  "adjFlag": "TCC",
  "adjCode": "102",
  "iat": "1782967530000",
  "udfParameters": "{\"supportTicketId\":\"SUP-908171\"}"
}
```

### Resolve With Explicit Adjustment Amount

```json
{
  "merchantRequestId": "RES202607020002",
  "originalUpiRequestId": "CMP202607010002",
  "originalTransactionUpiRequestId": "TXN202606300002",
  "remarks": "Partial adjustment approved by operations",
  "adjAmount": "75.00",
  "adjFlag": "TCC",
  "adjCode": "103",
  "iat": "1782967560000"
}
```

### Resolve With Default Remarks

Use this only when the default remarks are acceptable for your operations and downstream reporting.

```json
{
  "merchantRequestId": "RES202607020003",
  "originalUpiRequestId": "CMP202607010003",
  "originalTransactionUpiRequestId": "TXN202606300003",
  "adjAmount": "120.00",
  "adjFlag": "TCC",
  "adjCode": "102",
  "iat": "1782967590000"
}
```

## Processing Behavior

Resolve Complaint performs these checks in order:

1. Decrypts/verifies the S2S request envelope and identifies the merchant from request headers.
2. Verifies the merchant signature or encrypted/signed envelope, `iat` where applicable, `x-timestamp`, merchant API configuration, and optional IP allowlist.
3. Validates the decrypted request body.
4. Finds the original payee transaction using `originalTransactionUpiRequestId`.
5. Finds the existing non-self-initiated complaint using `originalUpiRequestId`.
6. If the complaint status is `CLOSED` or `FAILURE`, returns the stored complaint state without calling NPCI.
7. Otherwise builds an NPCI `RespComplaint` using the resolve adjustment fields and sends it downstream.
8. If NPCI ACKs without an error, Newton stores `code = "00"`, updates adjustment fields and remarks, marks the complaint `CLOSED`, and returns a success payload.
9. If NPCI returns an ACK error with an error code, Newton records the error details and returns a normal API response with the resulting gateway code/status in the payload.
10. If the downstream call times out or produces an invalid response shape, Newton returns a top-level failure response instead of a normal complaint payload.

## Response

### Response Envelope

On successful API processing, Newton returns:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. Success value is `SUCCESS`. This means Newton processed the API call and returned a complaint payload; it is not the only business status to inspect. |
| `responseCode` | string | Top-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level response message. Success value is `SUCCESS`. |
| `payload` | object | Resolve result and complaint details. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

When `status` is `SUCCESS`, clients must inspect `payload.gatewayResponseStatus` and `payload.gatewayResponseCode`:

| `payload.gatewayResponseStatus` | Meaning | Client interpretation |
| --- | --- | --- |
| `SUCCESS` | Stored gateway response code is `00`. | Complaint resolution was accepted and Newton has marked the complaint closed. Store the returned adjustment fields and stop retrying this resolve. |
| `PENDING` | Stored gateway response code is `01`. | Resolution is not final. Store identifiers and follow up using Complaint Status/List or configured callbacks. |
| `FAILURE` | Stored gateway response code is neither `00` nor `01`. | Newton processed the call but the complaint resolution is not successful from the gateway/business perspective, or the stored terminal complaint result is failed. Inspect `gatewayResponseCode` and `gatewayResponseMessage`. |

If the top-level `status` is `FAILURE`, the request failed before a normal resolve payload could be returned. In that case, use top-level `responseCode` and `responseMessage`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id for the authenticated merchant. |
| `merchantChannelId` | string | Merchant channel id for the authenticated merchant. |
| `merchantRequestId` | string | Merchant request id supplied in the current resolve request. For terminal no-op responses, this is still the current request id, not proof that a new downstream resolve happened. |
| `transactionAmount` | string | Original transaction amount formatted with two decimals. |
| `payerVpa` | string | Payer VPA from the original transaction. |
| `payeeVpa` | string | Payee VPA from the original transaction. |
| `reqAdjFlag` | string | Requested adjustment flag stored on the original complaint when it was raised/received. |
| `reqAdjCode` | string | Requested adjustment code stored on the original complaint when it was raised/received. |
| `reqAdjAmount` | string | Requested adjustment amount stored on the original complaint, formatted with two decimals. |
| `adjAmount` | string | Resolution adjustment amount when present. This is usually the request `adjAmount`, or the original transaction amount if request `adjAmount` was omitted and the resolve succeeded. Omitted when not stored. |
| `adjFlag` | string | Resolution adjustment flag when present. Omitted when no resolve adjustment flag is stored. |
| `adjCode` | string | Resolution adjustment code when present. Omitted when no resolve adjustment code is stored. |
| `crn` | string | Complaint reference number when available. Omitted when not available. |
| `gatewayComplaintId` | string | Complaint UPI request id. This should match request `originalUpiRequestId`. |
| `gatewayReferenceId` | string | Complaint UPI response/reference id stored by Newton. |
| `gatewayResponseCode` | string | Response code stored in the complaint NPCI response. `00` maps to `SUCCESS`; `01` maps to `PENDING`; other values map to `FAILURE`. |
| `gatewayResponseMessage` | string | Human-readable message derived from `gatewayResponseCode`. For `00`, Newton returns `Your complaint is resolved successfully`. For unknown non-success codes, Newton can return `Resolve complaint failed`. |
| `gatewayResponseStatus` | string | Derived resolve result: `SUCCESS`, `PENDING`, or `FAILURE`. |

Fields with no value are omitted from JSON responses. In particular, `adjAmount`, `adjFlag`, `adjCode`, `crn`, and `udfParameters` are omitted when unavailable.

## Success Response Examples

### Resolved Successfully

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "RES202607020001",
    "transactionAmount": "100.00",
    "payerVpa": "customer@bank",
    "payeeVpa": "merchant@bank",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U005",
    "reqAdjAmount": "100.00",
    "adjAmount": "100.00",
    "adjFlag": "TCC",
    "adjCode": "102",
    "crn": "601234567890",
    "gatewayComplaintId": "CMP202607010001",
    "gatewayReferenceId": "601234567890",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your complaint is resolved successfully",
    "gatewayResponseStatus": "SUCCESS"
  },
  "udfParameters": "{\"supportTicketId\":\"SUP-908171\"}"
}
```

### Explicit Adjustment Amount

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "RES202607020002",
    "transactionAmount": "250.00",
    "payerVpa": "customer@bank",
    "payeeVpa": "merchant@bank",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U008",
    "reqAdjAmount": "250.00",
    "adjAmount": "75.00",
    "adjFlag": "TCC",
    "adjCode": "103",
    "gatewayComplaintId": "CMP202607010002",
    "gatewayReferenceId": "601234567891",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your complaint is resolved successfully",
    "gatewayResponseStatus": "SUCCESS"
  }
}
```

### Stored Pending Result

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "RES202607020004",
    "transactionAmount": "500.00",
    "payerVpa": "customer@bank",
    "payeeVpa": "merchant@bank",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U009",
    "reqAdjAmount": "500.00",
    "crn": "601234567892",
    "gatewayComplaintId": "CMP202607010004",
    "gatewayReferenceId": "601234567892",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Transaction is in pending state",
    "gatewayResponseStatus": "PENDING"
  }
}
```

### Stored Failure or Downstream Rejection Result

The top-level API can still be `SUCCESS` when Newton processed the resolve request but the stored gateway/business outcome is not successful.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "RES202607020005",
    "transactionAmount": "500.00",
    "payerVpa": "customer@bank",
    "payeeVpa": "merchant@bank",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U010",
    "reqAdjAmount": "500.00",
    "gatewayComplaintId": "CMP202607010005",
    "gatewayReferenceId": "601234567893",
    "gatewayResponseCode": "U48",
    "gatewayResponseMessage": "Resolve complaint failed",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

## Error Handling

Failure responses use the same Newton response transport configured for the merchant. The examples below show decrypted response bodies. HTTP status may be `200`, `400`, `401`, or `500` depending on the layer that rejected the request, so clients should parse the decrypted body when one is returned.

### Request Validation Failure

Invalid body values fail before lookup or downstream calls. For example, `adjAmount` without two decimals fails amount validation.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Other validation examples:

- `merchantRequestId` is empty, too long, or contains unsupported characters.
- `originalUpiRequestId` or `originalTransactionUpiRequestId` is empty, longer than 35 characters, or not alphanumeric.
- `remarks` is empty, longer than 255 characters, or fails remarks character validation.
- `adjFlag` or `adjCode` is empty.
- `udfParameters` is not a stringified JSON object.

### Missing or Invalid `iat`

For encrypted/signed envelopes, `iat` is required by signature validation.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

### Authentication, Signature, Encryption, or IP Failure

Invalid JWS signatures, failed JWE decryption, missing signature headers in unsigned mode, missing raw body/timestamp headers, or IP allowlist failure can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Merchant API Not Enabled

If merchant configuration blocks this API or an allowlist is configured and this API is not present:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### Original Transaction Not Found

If `originalTransactionUpiRequestId` does not resolve to an eligible payee transaction in the searched partitions:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid upiRequestId"
}
```

### Existing Complaint Not Found

If Newton cannot find a non-self-initiated complaint with request `originalUpiRequestId` linked to the supplied original transaction:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

### Downstream NPCI Timeout or Transport Failure

If the NPCI `RespComplaint` call fails as a downstream service call, Newton returns a service-unavailable transaction error.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U30",
  "responseMessage": "UPI service is not reachable at the moment for transactional apis"
}
```

When no downstream code is available, the response code suffix can be `NA`.

### Invalid Downstream Response

If Newton receives an invalid NPCI response shape, for example an error response without an error code:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

### Unexpected Internal Error

Unexpected missing stored data, such as required response code or VPA fields being unavailable while building the response, can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Idempotency Guidance

- Store `gatewayComplaintId`, `gatewayReferenceId`, `crn`, `originalTransactionUpiRequestId`, and the resolve `merchantRequestId` with your support ticket or operations record.
- Treat top-level `SUCCESS` plus `payload.gatewayResponseStatus = "SUCCESS"` as terminal. Do not retry the resolve.
- Treat top-level `SUCCESS` plus `payload.gatewayResponseStatus = "PENDING"` as non-terminal. Do not immediately submit a new resolve attempt; follow up through Complaint Status/List or callbacks.
- Treat top-level `SUCCESS` plus `payload.gatewayResponseStatus = "FAILURE"` as a business/downstream failure. Retry only if the code/message is known to be transient for your integration; otherwise route it to manual or support handling.
- For top-level `SERVICE_UNAVAILABLE_NPCI_*`, retry with backoff using the same complaint identifiers and the same intended adjustment details. Because transport failures can be ambiguous, check Complaint Status before retrying when possible.
- Do not retry validation, authentication, encryption, API-not-enabled, or lookup failures without correcting the request, headers, merchant configuration, or identifiers.
- `merchantRequestId` is a trace/correlation field here, not a deduplication key. If the complaint is still non-terminal, another call can attempt another downstream resolve. If the complaint is already `CLOSED` or `FAILURE`, Newton returns the stored state and does not call NPCI again.

## Source References

- Route type for `/api/{apiVersion}/merchants/complaints/resolve`: [Core.hs](../../src/Newton/App/Routes/Core.hs:650)
- Route handler, request decryption, signature verification, and transformer dispatch: [Core.hs](../../src/Newton/App/Routes/Core.hs:4705)
- Encrypted/signed request and response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- S2S payload verification and merchant selection: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API allowlist/blocklist, timestamp, and IP checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request type, validation, and core response payload type: [Types.hs](../../src/Newton/Product/Merchant/Complaints/Types.hs:227)
- S2S transformer route and response wrapper: [ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:245), [ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:205), [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:185)
- Generic response payload mapping: [Generic/Types.hs](../../src/Newton/Services/Transformer/Generic/Types.hs:193), [Generic/Helper.hs](../../src/Newton/Services/Transformer/Generic/Helper.hs:53)
- Product resolve route, lookup, terminal handling, and downstream response validation: [Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:267)
- Resolve request transformation, response payload construction, and gateway status mapping: [Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:242)
- NPCI `RespComplaint` call, success update, ACK-error handling, and timeout handling: [ComplaintV2.hs](../../src/Newton/Product/ComplaintV2.hs:210)
- Request validation helpers: [Common.hs](../../src/Newton/Validation/Common.hs:275), [Common.hs](../../src/Newton/Validation/Common.hs:292), [Common.hs](../../src/Newton/Validation/Common.hs:351), [Common.hs](../../src/Newton/Validation/Common.hs:385), [Common.hs](../../src/Newton/Validation/Common.hs:575)
- Transaction and complaint lookup helpers: [Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:1815), [Complaint.hs](../../src/Newton/Storage/QueriesMiddleware/Complaint.hs:127)
- Error response constants used by this flow: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:34), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:133), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:401)
