# Raise Complaint API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/complaints/raise`

## Overview

Raise Complaint is a merchant server-to-server API used to raise a UPI complaint against an existing Newton transaction.

The merchant calls this API after a customer or operations workflow determines that a completed, deemed, deemed-debit, or otherwise complaint-eligible transaction needs a UDIR/NPCI complaint. Newton validates the merchant, customer, original transaction, complaint timing window, duplicate state, and adjustment details, then creates a Newton complaint and sends the complaint onward to NPCI where applicable.

Payloads use the standard Newton server-to-server encrypted request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Use this API when the merchant needs to:

- Raise a customer support complaint for a UPI transaction processed through Newton.
- Initiate a UDIR/NPCI complaint for a payer-side transaction that is eligible for complaint handling.
- Raise a complaint for the full transaction amount, or for an explicit requested adjustment amount.
- Track the complaint using Newton's complaint id, CRN, gateway reference id, and later complaint status callbacks/status APIs.

Do not call this API to look up an existing complaint. Use the complaint status or list APIs when the complaint has already been raised and the merchant only needs the latest known state.

## Integration Flow

1. Merchant identifies the original UPI transaction that needs a complaint.
2. Merchant generates a new complaint `upiRequestId` and a merchant-side `merchantRequestId`.
3. Merchant prepares the decrypted business payload with the original transaction id, complaint id, complaint type, and requested adjustment details.
4. Merchant signs/encrypts the request using the Newton S2S integration process.
5. Newton decrypts/verifies the request, validates merchant/API configuration, and validates the business payload.
6. Newton looks up the original payer transaction using `originalUpiRequestId`.
7. Newton validates complaint business rules, creates a complaint record, and calls NPCI for off-us complaints. For configured on-us complaints, Newton can create the pending complaint records without an external NPCI call.
8. Merchant decrypts the response and stores `gatewayComplaintId`, `gatewayReferenceId`, `crn`, and `gatewayResponseStatus`.
9. Merchant uses complaint status/list APIs or callbacks for final reconciliation when the raise response is pending.

Important identifiers:

- `originalUpiRequestId`: UPI request id of the original transaction being complained about. Newton uses this to find the original payer-side transaction.
- `upiRequestId`: New UPI request id for this complaint raise request. This becomes `payload.gatewayComplaintId`.
- `merchantRequestId`: Merchant-generated reference for this raise attempt. It is stored with complaint metadata and used for merchant correlation, but duplicate complaint detection is based on the original transaction/complaint record.
- `gatewayReferenceId`: Newton/NPCI complaint reference returned for this complaint.
- `crn`: Complaint reference number when available, especially for pending/accepted complaints.

## Endpoint

```http
POST /api/{apiVersion}/merchants/complaints/raise
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. If omitted or invalid, Newton falls back to base version `0`. |
| `x-merchant-id` | Merchant id issued by Newton. |
| `x-merchant-channel-id` | Merchant channel id issued by Newton. |
| `x-timestamp` | Request timestamp used for signature/timestamp validation. |
| `x-raw-body` | Raw request body used for signature verification. |
| `x-merchant-signature` | Required for unsigned transport mode; not required for JWE/JWS payloads where the envelope supplies cryptographic verification. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. In production, send the encrypted/signed envelope configured for the merchant. The decrypted examples in this guide are not the wire format unless Newton has explicitly enabled that mode for your environment.

## Request

### Required Minimum

For most merchant integrations, send at least:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "CMPREQ202601030001",
  "upiRequestId": "CMP202601030001",
  "originalUpiRequestId": "TXN202601010001",
  "adjFlag": "PBRB",
  "adjCode": "U005",
  "type": "COMPLAINT"
}
```

If the merchant is configured with `allowWithoutMerchantCustomerId`, `merchantCustomerId` can be omitted and Newton uses the merchant customer linked to the original transaction:

```json
{
  "merchantRequestId": "CMPREQ202601030002",
  "upiRequestId": "CMP202601030002",
  "originalUpiRequestId": "TXN202601010002",
  "adjFlag": "PBRB",
  "adjCode": "U009",
  "type": "COMPLAINT"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Conditional | If omitted, Newton uses the merchant customer linked to the original transaction only when merchant configuration `allowWithoutMerchantCustomerId` is enabled. Otherwise the request fails with `merchantCustomerId is mandatory`. | Merchant's customer identifier. When supplied, it must match the merchant customer linked to the original transaction and the authenticated merchant. |
| `merchantRequestId` | string | Yes | No default. | Merchant-generated reference for this complaint raise attempt. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `upiRequestId` | string | Yes | No default. | New UPI request id for the complaint itself. Must be 1 to 35 alphanumeric characters. If UDIR transaction-id prefix validation is enabled, it must start with the configured Newton prefix. |
| `originalUpiRequestId` | string | Yes | No default. | UPI request id of the original transaction being complained about. Newton looks up a payer transaction with this value. |
| `remarks` | string | No | Defaults to `Complaint raise` in the stored complaint when omitted. | Complaint note/remarks. Must be 1 to 255 characters when supplied. |
| `adjAmount` | string | No | Defaults to the original transaction amount when omitted. | Requested adjustment amount in two-decimal format, for example `100.00`. Must be greater than zero when supplied. |
| `adjFlag` | string | Yes | No default. | UDIR/NPCI requested adjustment flag agreed for the complaint use case. The current S2S validator requires exactly 4 characters. |
| `adjCode` | string | Yes | No default. | UDIR/NPCI requested adjustment code. The current validator requires 3 or 4 characters. |
| `initiationMode` | string | No | Defaults to `U1` in the stored complaint when omitted. | UPI initiation mode. Must be exactly 2 alphanumeric characters when supplied. |
| `purpose` | string | No | Defaults to `00` in the stored complaint when omitted. | UPI purpose code. Must be exactly 2 uppercase alphanumeric characters when supplied. |
| `type` | string | Yes | No default. | Complaint type enum. Supported by the type: `COMPLAINT`, `DISPUTE`, `REFUND`, `REVERSAL`, `STATUSUPDATE`, `CHKSTATUS`. Most merchant raise flows use `COMPLAINT` unless Newton has enabled a different complaint type for the use case. |
| `refUrl` | string | No | No default. Omitted fields are not returned by this API. | Merchant reference URL. |
| `refCategory` | string | No | Defaults to `00` in the stored complaint metadata when omitted. | Merchant/reference category used in complaint metadata. |
| `iat` | string | Conditional | No default. Required by signature/encryption validation for signed or encrypted envelopes. | Issued-at timestamp used by the S2S signature/encryption layer. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the raise response. |

### Defaults and Omitted Field Behavior

- `adjAmount` omitted means Newton uses the original transaction amount as `reqAdjAmount`.
- `remarks` omitted is stored as `Complaint raise`.
- `initiationMode` omitted is stored as `U1`.
- `purpose` omitted is stored as `00`.
- `refCategory` omitted is stored as `00`.
- `merchantCustomerId` omitted is accepted only for merchants configured to allow omission. Otherwise the request is rejected.
- Optional fields with `null` values are treated the same as omitted by the Haskell `Maybe` request type. Prefer omitting unused fields.
- `udfParameters` must be a JSON object encoded as a string, for example `"{\"ticketId\":\"SUP-123\"}"`.

### Nested Request Objects

This API has no nested request objects. The decrypted business payload is a flat JSON object. `udfParameters`, if used, is a JSON-object string rather than a nested JSON object.

## Request Examples

### Full-Amount Complaint

`adjAmount` is omitted, so Newton uses the original transaction amount as the requested adjustment amount.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "CMPREQ202601030001",
  "upiRequestId": "CMP202601030001",
  "originalUpiRequestId": "TXN202601010001",
  "remarks": "Customer reports amount debited but payment not completed",
  "adjFlag": "PBRB",
  "adjCode": "U005",
  "type": "COMPLAINT",
  "udfParameters": "{\"ticketId\":\"SUP-12345\"}"
}
```

### Explicit Adjustment Amount

Use `adjAmount` when the requested adjustment amount is not the full original transaction amount.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "CMPREQ202601030002",
  "upiRequestId": "CMP202601030002",
  "originalUpiRequestId": "TXN202601010002",
  "remarks": "Partial service dispute",
  "adjAmount": "50.00",
  "adjFlag": "PBRB",
  "adjCode": "U008",
  "initiationMode": "U1",
  "purpose": "00",
  "type": "COMPLAINT",
  "refUrl": "https://merchant.example/support/SUP-12346",
  "refCategory": "00"
}
```

### Merchant-Customer Omitted by Configuration

Use this variant only when Newton has enabled `allowWithoutMerchantCustomerId` for the merchant. Newton resolves the merchant customer from the original transaction.

```json
{
  "merchantRequestId": "CMPREQ202601030003",
  "upiRequestId": "CMP202601030003",
  "originalUpiRequestId": "TXN202601010003",
  "remarks": "Complaint raised from operations workflow",
  "adjFlag": "PBRB",
  "adjCode": "U009",
  "type": "COMPLAINT"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. `SUCCESS` means Newton processed the raise request and returned a complaint payload. It does not always mean the complaint is finally successful at NPCI. |
| `responseCode` | string | Top-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level response message. Success value is `SUCCESS`. |
| `payload` | object | Present on successful API processing. Contains merchant, original transaction, complaint, and gateway/NPCI result fields. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

When `status` is `SUCCESS`, clients must still inspect `payload.gatewayResponseStatus`:

| `payload.gatewayResponseStatus` | Meaning | Client interpretation |
| --- | --- | --- |
| `SUCCESS` | Gateway response code was `00`. | Store complaint identifiers and continue reconciliation. |
| `PENDING` | Gateway response code was `01`. | Complaint has been accepted/sent and final handling is pending. Store identifiers and follow up through complaint status/list or callbacks. |
| `FAILURE` | Gateway response code was not `00` or `01`. | Newton processed the API call, but the complaint raise failed or was rejected downstream. Inspect `gatewayResponseCode` and `gatewayResponseMessage`; retry only when the failure is known to be transient or retryable. |

If the top-level `status` is `FAILURE`, the request failed before a normal complaint payload could be returned. In that case, use top-level `responseCode` and `responseMessage`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id for the authenticated merchant. |
| `merchantChannelId` | string | Merchant channel id for the authenticated merchant. |
| `merchantRequestId` | string | Merchant request id supplied in the request. |
| `merchantCustomerId` | string | Merchant customer id resolved for the original transaction. |
| `customerMobileNumber` | string | Customer mobile number, trimmed to the merchant-facing mobile number format. |
| `transactionAmount` | string | Original transaction amount formatted with two decimals. |
| `payerVpa` | string | Payer VPA from the original transaction. |
| `payeeVpa` | string | Payee VPA from the original transaction. |
| `reqAdjFlag` | string | Requested adjustment flag sent in the raise request and stored on the complaint. |
| `reqAdjCode` | string | Requested adjustment code sent in the raise request and stored on the complaint. |
| `reqAdjAmount` | string | Requested adjustment amount. This is `adjAmount` from the request, or the original transaction amount when `adjAmount` was omitted. |
| `adjAmount` | string | Final/response adjustment amount when available. Omitted when no final adjustment amount is present. |
| `adjFlag` | string | Final/response adjustment flag when available. Omitted when no final adjustment flag is present. |
| `adjCode` | string | Final/response adjustment code when available. Omitted when no final adjustment code is present. |
| `crn` | string | Complaint reference number when available. Omitted when no CRN is present. |
| `gatewayComplaintId` | string | Complaint UPI request id. This is normally the request `upiRequestId`. |
| `gatewayReferenceId` | string | Gateway/NPCI reference id for the complaint. |
| `gatewayResponseCode` | string | Gateway/NPCI response code. `00` maps to `SUCCESS`; `01` maps to `PENDING`; other values map to `FAILURE`. |
| `gatewayResponseMessage` | string | Human-readable message derived from the gateway/NPCI response code when available. |
| `gatewayResponseStatus` | string | Derived complaint raise result: `SUCCESS`, `PENDING`, or `FAILURE`. |

Fields with no value are omitted from JSON responses. In particular, `adjAmount`, `adjFlag`, `adjCode`, `crn`, and `udfParameters` are omitted when unavailable.

### Example Pending/Accepted Response

Most successful raise flows return a pending complaint state because final complaint handling may complete later.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "CMPREQ202601030001",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "transactionAmount": "100.00",
    "payerVpa": "customer@bank",
    "payeeVpa": "merchant@bank",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U005",
    "reqAdjAmount": "100.00",
    "crn": "601234567890",
    "gatewayComplaintId": "CMP202601030001",
    "gatewayReferenceId": "601234567890",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your complaint is raised successfully",
    "gatewayResponseStatus": "PENDING"
  },
  "udfParameters": "{\"ticketId\":\"SUP-12345\"}"
}
```

### Example Downstream Rejection Response

Some downstream/NPCI rejections are returned in a successful API envelope because Newton processed the request and stored the gateway result. In this case, `payload.gatewayResponseStatus` is the decisive field.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "CMPREQ202601030004",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "transactionAmount": "100.00",
    "payerVpa": "customer@bank",
    "payeeVpa": "merchant@bank",
    "reqAdjFlag": "PBRB",
    "reqAdjCode": "U005",
    "reqAdjAmount": "100.00",
    "gatewayComplaintId": "CMP202601030004",
    "gatewayReferenceId": "CMP202601030004",
    "gatewayResponseCode": "C26",
    "gatewayResponseMessage": "Complaint ReqAdjCode not present",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

## Business Rules and Idempotency

Newton raises a complaint only when the original transaction and merchant/customer context pass the complaint rules.

Key rules:

- `originalUpiRequestId` must resolve to a payer-side transaction in Newton.
- The transaction must belong to the authenticated merchant/customer context.
- The transaction must be complaint eligible. The code allows payer transactions in configured deemed/deemed-debit/success/DRC complaint cases and rejects unsupported statuses.
- The complaint must be outside the configured minimum waiting period after the original transaction and inside the configured maximum age window. Current code defaults are 5 minutes and 60 days unless overridden by configuration.
- A secondary delegatee transaction cannot raise this complaint.
- If an active non-failed self-initiated complaint already exists for the same original transaction, Newton rejects the duplicate request.

`merchantRequestId` is a merchant correlation id, not the only idempotency key. The duplicate check is tied to the original transaction and existing complaint state. A second raise for the same original transaction can fail with `DUPLICATE_REQUEST` even if the merchant changes `merchantRequestId`.

Recommended client behavior:

- Generate one `upiRequestId` for each complaint raise attempt and store it with `merchantRequestId` and `originalUpiRequestId`.
- Treat `DUPLICATE_REQUEST` as "a complaint already exists for this transaction"; do not keep raising new complaints for the same original transaction. Use complaint status/list to reconcile.
- If no response is received because of a client/network timeout, first check complaint status/list using the complaint/original transaction identifiers where available before creating another raise attempt.
- Retry only transient failures such as network failures, temporary NPCI/service-unavailable responses, or internal errors, and use bounded backoff.
- Do not retry validation, authentication, API-not-enabled, invalid user profile, or operation-not-allowed failures without correcting the request/configuration.
- For top-level `SUCCESS` with `payload.gatewayResponseStatus = "FAILURE"`, retry only if the specific `gatewayResponseCode` is operationally retryable for the merchant's UDIR process.

## Error Handling

Failure responses use the same encrypted response transport as successful responses where encryption/signing has been established. The examples below show decrypted business bodies.

Most top-level failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

When `payload` is empty, it is omitted from the JSON response. Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, `404`, or `500`; clients should primarily use `status`, `responseCode`, and `responseMessage`.

### Common Failure Scenarios

| Scenario | Example decrypted response body | Client handling |
| --- | --- | --- |
| `merchantRequestId` is empty, too long, or has invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\""}` | Correct the merchant reference before retrying. |
| `upiRequestId` or `originalUpiRequestId` is too long or contains non-alphanumeric characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"upiRequestId regex match failed\""}` | Send a 1 to 35 character alphanumeric id. |
| `adjAmount` is not in two-decimal positive amount format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"amount regex match failed\""}` | Send an amount such as `100.00`, or omit `adjAmount` to use the original transaction amount. |
| `adjFlag` length is not 4 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \" adjFlag length is not equal to 4\""}` | Send the configured 4-character adjustment flag. |
| `adjCode` length is not 3 or 4 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \" adjCode length is not equal to 3 or 4\""}` | Send the configured adjustment code. |
| `initiationMode` or `purpose` has invalid length/format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"InitiationMode length is not 2\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"Purpose Code regex match failed\""}` | Send 2-character values such as `U1` and `00`, or omit them to use defaults. |
| `udfParameters` is not a JSON-object string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` | Send a JSON object encoded as a string, or omit the field. |
| `merchantCustomerId` is omitted but the merchant is not configured to allow omission | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"merchantCustomerId is mandatory"}` | Send `merchantCustomerId`, or ask Newton to enable omission for the merchant if appropriate. |
| `upiRequestId` does not match the configured UDIR transaction id prefix | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Request can't be raised with this upiRequestIdPrefix"}` | Generate the complaint `upiRequestId` with the prefix configured during onboarding. |
| Request body cannot be decrypted, JWE/JWS verification fails, required auth headers are missing, timestamp is invalid, IP whitelist check fails, or signature verification fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` or `{"status":"FAILURE","responseCode":"AUTH_FAILURE","responseMessage":"AUTH_FAILURE"}` | Fix the S2S envelope, keys, signature headers, timestamp, IP allowlist, or merchant credentials before retrying. |
| Complaint Raise API is blocked or not enabled for the merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Ask Newton to enable the API for the merchant/channel. |
| `originalUpiRequestId` does not resolve to an original payer transaction | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Original record not found"}` | Verify the original transaction id and that the transaction belongs to this Newton merchant integration. |
| Merchant/customer context does not match the original transaction | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"User profile not found"}` | Verify `merchantCustomerId` and the original transaction's merchant/customer linkage. |
| Complaint is raised too soon after the original transaction | `{"status":"FAILURE","responseCode":"OPERATION_NOT_ALLOWED","responseMessage":"Complaint cannot initiate within threshold time"}` | Wait until the configured complaint waiting period has elapsed. |
| Complaint is raised after the configured maximum age window | `{"status":"FAILURE","responseCode":"OPERATION_NOT_ALLOWED","responseMessage":"Complaint can't be raised now"}` | Do not retry without operational approval; the complaint window has expired. |
| Original transaction is not complaint-eligible | `{"status":"FAILURE","responseCode":"OPERATION_NOT_ALLOWED","responseMessage":"Complaint can't be raised for this transaction"}` | Do not retry unless the original transaction status/data changes and Newton confirms it is eligible. |
| Complaint is attempted on a delegatee secondary transaction | `{"status":"FAILURE","responseCode":"OPERATION_NOT_ALLOWED","responseMessage":"Complaint cannot be raised by DELEGATEE"}` | Raise the complaint only from the supported payer/original transaction context. |
| Complaint already exists for the original transaction | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"Complaint for this transaction is already raised"}` | Treat as existing complaint; query complaint status/list instead of raising again. |
| NPCI call times out or is temporarily unavailable | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_U09","responseMessage":"UPI service is not reachable at the moment for transactional apis"}` | Retry with bounded backoff, then reconcile through status/list if the outcome is uncertain. |
| NPCI response is malformed or missing required error code details | `{"status":"FAILURE","responseCode":"BAD_RESPONSE_FROM_NPCI","responseMessage":"Invalid response from NPCI"}` | Retry if transient; escalate with `upiRequestId` and `originalUpiRequestId` if persistent. |
| NPCI/business rejection is returned inside the payload | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseCode":"C26","gatewayResponseMessage":"Complaint ReqAdjCode not present","gatewayResponseStatus":"FAILURE"}}` | Treat the complaint raise as failed even though top-level status is `SUCCESS`; fix the adjustment data or follow the UDIR handling for that code. |
| Database, cache, encryption, missing decrypted transaction fields, or other unexpected server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry with backoff for transient failures; escalate with request ids if persistent. |

For `OPERATION_NOT_ALLOWED`, `x-api-version` matters. With `x-api-version > 0`, Newton returns `responseCode: "OPERATION_NOT_ALLOWED"`. In base version `0`, the same operation failure can be mapped to `responseCode: "INVALID_DATA"` with the same response message.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:631)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4652)
- S2S request body parsing: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Payload JWS/JWE verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature/API configuration verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- API allowed/blocked checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- `x-api-version` lookup: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:960)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:222)
- S2S response helper and complaint error mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:154)
- S2S response type: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:137)
- Generic response payload type: [src/Newton/Services/Transformer/Generic/Types.hs](../../src/Newton/Services/Transformer/Generic/Types.hs:116)
- Generic response payload/error helper: [src/Newton/Services/Transformer/Generic/Helper.hs](../../src/Newton/Services/Transformer/Generic/Helper.hs:35)
- Request and core response payload types: [src/Newton/Product/Merchant/Complaints/Types.hs](../../src/Newton/Product/Merchant/Complaints/Types.hs:18)
- Complaint raise product flow: [src/Newton/Product/Merchant/Complaints/Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:47)
- Product business validations: [src/Newton/Product/Merchant/Complaints/Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:69)
- Duplicate/timing/eligibility checks: [src/Newton/Product/Merchant/Complaints/Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:86)
- Downstream NPCI response validation: [src/Newton/Product/Merchant/Complaints/Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:146)
- Core complaint/NPCI initiation: [src/Newton/Product/ComplaintV2.hs](../../src/Newton/Product/ComplaintV2.hs:38)
- NPCI complaint request payload: [src/Newton/Product/ComplaintV2.hs](../../src/Newton/Product/ComplaintV2.hs:88)
- Product request/response mapping: [src/Newton/Product/Merchant/Complaints/Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:32)
- Product success response payload helper: [src/Newton/Product/Merchant/Complaints/Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:78)
- Product failure response payload helper: [src/Newton/Product/Merchant/Complaints/Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:304)
- Merchant-customer lookup and validation: [src/Newton/Product/Merchant/Complaints/Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:351)
- Stored complaint defaults: [src/Newton/Utils/Transformers/Transformer3.hs](../../src/Newton/Utils/Transformers/Transformer3.hs:233)
- Request validation entry points: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:162)
- Common field validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:292)
- Complaint type enum: [src/Newton/Types/Storage/Complaint.hs](../../src/Newton/Types/Storage/Complaint.hs:138)
- Original transaction lookup: [src/Newton/Storage/QueriesMiddleware/Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:1846)
- Downstream/NPCI failure handling: [src/Newton/Product/NpciSwitch/Meta/Complaints/Helper.hs](../../src/Newton/Product/NpciSwitch/Meta/Complaints/Helper.hs:553)
- Complaint timing config defaults: [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs:2433)
- Gateway/NPCI error message lookup: [src/Newton/Constants/ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:112)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:34)
