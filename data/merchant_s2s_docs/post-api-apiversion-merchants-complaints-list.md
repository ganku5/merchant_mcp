# List Complaints API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/complaints/list`

## Overview

List Complaints is a server-to-server API used by a merchant backend to fetch UPI complaint records known to Newton.

The API returns complaint records with the linked original transaction identifiers, VPAs, complaint status, requested adjustment details, and optional sub-merchant metadata. It is read-only: calling this API does not raise, resolve, or refresh a complaint with NPCI. Use the complaint raise, status, and resolve APIs for those actions.

Payloads use the standard Newton server-to-server encrypted request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Use this API when the merchant needs to:

- Show a customer's complaint history in a support, operations, or customer-service screen.
- Reconcile complaints created through UDIR/NPCI flows with merchant order or transaction records.
- Poll Newton for complaints in a date range for back-office reporting.
- Fetch complaints filtered by Newton complaint status, for example only `OPEN` or `PENDING` complaints.
- In a P2M SDK parent setup, list complaints for a customer across selected child merchant apps using `appIds`.

This API is most useful after a complaint has already been raised or received. It should not be used as a substitute for complaint status refresh when the client needs a real-time NPCI status check for one complaint.

## Integration Flow

1. Merchant backend chooses the lookup scope:
   - send `merchantCustomerId` to list complaints for one merchant customer; or
   - omit `merchantCustomerId` to list merchant-scoped complaints for the calling merchant.
2. Merchant optionally adds date, pagination, status, and app filters.
3. Merchant signs/encrypts the request using the Newton S2S integration process.
4. Newton decrypts/verifies the request, validates merchant access, and applies merchant/API configuration checks.
5. Newton validates the business payload and reads matching complaints plus their linked transactions.
6. Merchant decrypts the response and uses `status`, `responseCode`, and `payload.complaintsList` for reconciliation or display.

Important identifiers:

- `merchantCustomerId`: Merchant's customer id. When supplied, Newton lists complaints for the corresponding customer.
- `transactionUpiRequestId`: UPI request id of the original transaction against which the complaint exists.
- `upiRequestId`: UPI request id / gateway complaint id for the complaint itself.
- `merchantRequestId`: Merchant request id stored in complaint metadata when available, usually from the complaint raise flow.

## Endpoint

```http
POST /api/{apiVersion}/merchants/complaints/list
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id issued by Newton. |
| `x-merchant-channel-id` | Merchant channel id issued by Newton. |
| `x-timestamp` | Request timestamp used for signature/timestamp validation. |
| `x-raw-body` | Raw request body used for signature verification. |
| `x-merchant-signature` | Required for unsigned transport mode; not required for JWE/JWS payloads where the envelope supplies cryptographic verification. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. In production, send the encrypted/signed envelope configured for the merchant. The decrypted examples in this guide are not the wire format unless Newton has explicitly enabled that mode for your environment.

## Request

### Required Minimum

The decrypted business payload can be an empty object. When no filters are supplied, Newton returns up to 20 complaints for the calling merchant, from the default date window.

```json
{}
```

For a customer-specific lookup, send:

```json
{
  "merchantCustomerId": "CUST12345"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | No | If omitted, Newton lists complaints scoped to the calling merchant's own customer record and merchant id. | Merchant's customer identifier. Use this for customer-service or customer-history views. Must be 1 to 256 characters and match Newton's merchant-customer id format. |
| `startDate` | string | No | Defaults to the date six months before the current date. | Inclusive complaint-created date lower bound. Format accepted by code is date text parseable after replacing `/` with `-`; use `YYYY/M/D`, for example `2026/1/5`. |
| `endDate` | string | No | Defaults to the current date. | Inclusive complaint-created date upper bound. Newton applies end-of-day to this date. Use `YYYY/M/D`, for example `2026/1/31`. |
| `limit` | string | No | Defaults to `"20"`. | Maximum number of rows to return. Must be a non-negative integer encoded as a string. |
| `offset` | string | No | Defaults to `"0"`. | Number of rows to skip. Must be a non-negative integer encoded as a string. |
| `status` | array of strings | No | No status filter. All supported complaint statuses in the selected scope/date range can be returned. | Complaint status filter. Supported values are `OPEN`, `CLOSED`, `PENDING`, `COMPLAINT_RECEIVED`, and `FAILURE`. Empty arrays are rejected. |
| `appIds` | array of objects | Conditional | Ignored for non-P2M-parent flows. For P2M parent flows with `merchantCustomerId`, send this to constrain the customer lookup to selected child apps; omission does not expand to child app merchant customers. | Child merchant app identifiers used only when the calling merchant is configured as a P2M SDK parent and `merchantCustomerId` is supplied. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the response. |
| `iat` | string | No | No default. | Issued-at value used by the S2S signature/encryption layer where applicable. |

### Defaults and Omitted Field Behavior

- If `startDate` and `endDate` are both omitted, Newton searches from six months before the current date through the current date.
- If only `startDate` is supplied, `endDate` defaults to the current date.
- If only `endDate` is supplied, `startDate` defaults to six months before the current date.
- `limit` defaults to `20`; `offset` defaults to `0`.
- `status` omitted means no complaint-status filter.
- `merchantCustomerId` changes the query scope. With it, Newton first resolves the merchant customer and customer, then lists that customer's complaints. Without it, Newton lists complaints for the merchant's own customer record and merchant id.
- `appIds` is only meaningful for P2M SDK parent merchants with a supplied `merchantCustomerId`. For ordinary merchants, the current merchant customer is used.
- Optional fields with `null` values are treated the same as omitted by the Haskell `Maybe` request type. Prefer omitting unused fields.

### Nested Request Objects

#### `appIds[]`

Use `appIds` only when Newton has enabled parent/child P2M SDK behavior for the merchant.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Yes | Child merchant id. |
| `merchantChannelId` | string | Yes | Child merchant channel id. |

## Request Examples

### Merchant-Scoped Recent Complaints

Returns up to 20 complaints in the default six-month date window for the calling merchant.

```json
{}
```

### Customer Complaint History

```json
{
  "merchantCustomerId": "CUST12345",
  "startDate": "2026/1/1",
  "endDate": "2026/1/31",
  "limit": "50",
  "offset": "0"
}
```

### Filter by Complaint Status

```json
{
  "merchantCustomerId": "CUST12345",
  "status": [
    "OPEN",
    "PENDING"
  ],
  "limit": "25",
  "offset": "0"
}
```

### P2M Parent Lookup Across Child Apps

```json
{
  "merchantCustomerId": "CUST12345",
  "appIds": [
    {
      "merchantId": "CHILD_MERCHANT_1",
      "merchantChannelId": "APP_ANDROID"
    },
    {
      "merchantId": "CHILD_MERCHANT_2",
      "merchantChannelId": "APP_IOS"
    }
  ],
  "startDate": "2026/1/1",
  "endDate": "2026/1/31"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Present on success. Contains merchant identifiers and the complaint list. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

When `status` is `SUCCESS`, the list operation succeeded. An empty `complaintsList` means no records matched the requested scope and filters; it is not an error.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id for the authenticated merchant. |
| `merchantChannelId` | string | Merchant channel id for the authenticated merchant. |
| `merchantCustomerId` | string | Echoed when supplied in the request. Omitted when the request was merchant-scoped. |
| `complaintsList` | array of objects | Matching complaint records. Empty when no complaints match. |

### `complaintsList[]` Fields

| Field | Type | Description |
| --- | --- | --- |
| `payerVpa` | string | Payer VPA from the linked original transaction. |
| `payeeVpa` | string | Payee VPA from the linked original transaction. |
| `orgTxnStatus` | string | Status of the linked original transaction in Newton. |
| `mobileNumber` | string | Customer mobile number from transaction payer metadata, when present. Omitted when not present. |
| `transactionUpiRequestId` | string | UPI request id of the original transaction. |
| `upiRequestId` | string | UPI request id / gateway complaint id of the complaint. |
| `crn` | string | Complaint reference number, when available. |
| `orgTxnDate` | string | Original transaction creation time, serialized from Newton local time. |
| `complaintDate` | string | Complaint creation time, serialized from Newton local time. |
| `status` | string | Current Newton complaint status: `OPEN`, `CLOSED`, `PENDING`, `COMPLAINT_RECEIVED`, or `FAILURE`. |
| `remarks` | string | Complaint remarks stored by Newton. |
| `reqAdjAmount` | string | Requested adjustment amount formatted with two decimal places. |
| `reqAdjCode` | string | Requested adjustment code. |
| `reqAdjFlag` | string | Requested adjustment flag. |
| `subMerchantId` | string | Present only for applicable P2M SDK sub-merchant records. |
| `subMerchantChannelId` | string | Present only for applicable P2M SDK sub-merchant records. |
| `merchantRequestId` | string | Merchant request id stored in complaint metadata, when available. |

Fields with no value are omitted from JSON responses.

### Example Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "complaintsList": [
      {
        "payerVpa": "customer@bank",
        "payeeVpa": "merchant@bank",
        "orgTxnStatus": "SUCCESS",
        "mobileNumber": "9876543210",
        "transactionUpiRequestId": "TXN202601010001",
        "upiRequestId": "CMP202601010001",
        "crn": "601234567890",
        "orgTxnDate": "2026-01-01 10:15:30",
        "complaintDate": "2026-01-03 14:20:10",
        "status": "OPEN",
        "remarks": "Customer raised complaint",
        "reqAdjAmount": "100.00",
        "reqAdjCode": "U009",
        "reqAdjFlag": "PAYER",
        "merchantRequestId": "ORDER12345"
      }
    ]
  },
  "udfParameters": "{\"ticketId\":\"TICKET123\"}"
}
```

### Example Empty Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "complaintsList": []
  }
}
```

## Pagination and Filtering

Use `limit` and `offset` for pagination. Store the same filter set between pages and increment `offset` by the number of rows already consumed.

Recommended client behavior:

- Use small page sizes for customer-service screens, for example `20` or `50`.
- Use explicit `startDate` and `endDate` for reconciliation jobs so repeated runs are deterministic.
- Treat an empty page as end-of-results for that filter set.
- For operational queues, filter by `status` rather than retrieving all complaints and filtering client-side.

## Idempotency and Retry Guidance

This API is read-only and does not use a merchant idempotency key.

Recommended client behavior:

- Retry network timeouts, connection failures, and `INTERNAL_SERVER_ERROR`/temporary service failures with bounded backoff.
- Do not retry validation failures without changing the request.
- Do not retry `UNAUTHORIZED` or `AUTH_FAILURE` until headers, keys, signatures, timestamp, or merchant/API configuration are corrected.
- Because complaint statuses can change over time through callbacks or status/resolve flows, retrying or re-querying can return newer complaint statuses for the same date range.

## Error Handling

Failure responses use the same encrypted response transport as successful responses where encryption/signing has been established. The examples below show decrypted business bodies.

Most failure bodies follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

When `payload` is empty, it is omitted from the JSON response. Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, `404`, or `500`; clients should primarily use `status`, `responseCode`, and `responseMessage`.

### Common Failure Scenarios

| Scenario | Example decrypted response body | Client handling |
| --- | --- | --- |
| `merchantCustomerId` is empty, too long, or contains unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` | Correct the identifier before retrying. |
| `startDate` or `endDate` is not parseable as a date | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"date value not valid\""}` | Send a valid date such as `2026/1/31`. |
| `limit` or `offset` is not a non-negative integer string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"Expected Positive Integer, found -1\""}` | Send a non-negative integer string. |
| `status` is an empty array | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ListValidation \"Field is empty\""}` | Omit `status` for all statuses, or send one or more valid statuses. |
| `status` contains an unsupported enum value | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $: parsing Newton.Types.Storage.Complaint.ComplaintStatus failed, expected one of the tags [\"OPEN\",\"CLOSED\",\"PENDING\",\"COMPLAINT_RECEIVED\",\"FAILURE\"]"}` | Send only supported complaint statuses. |
| `udfParameters` is not a JSON-object string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` | Send a JSON object encoded as a string, or omit the field. |
| Request body cannot be decrypted, JWE/JWS verification fails, required auth headers are missing, timestamp is invalid, IP whitelist check fails, API is not enabled, or signature verification fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` or `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"Signature Verification Mismatch"}` | Fix the S2S envelope, signature headers, timestamp, merchant credentials, IP allowlist, or API enablement before retrying. |
| Auth layer returns a generic auth failure | `{"status":"FAILURE","responseCode":"AUTH_FAILURE","responseMessage":"AUTH_FAILURE"}` | Treat as an authentication/configuration failure and verify onboarding details. |
| Merchant id or merchant channel id in headers does not resolve to a configured merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Verify `x-merchant-id` and `x-merchant-channel-id`. |
| `merchantCustomerId` does not resolve for the merchant, or the merchant customer is not linked to an active customer | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer"}` | Verify the customer has completed the relevant Newton onboarding/device-binding flow. |
| P2M parent `appIds` references merchants that cannot be resolved | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Verify each child `merchantId` and `merchantChannelId` is configured for the parent flow. |
| Complaint metadata is inconsistent and the linked transaction cannot be located | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in finding txn"}` | Retry later only if the data issue may be transient; otherwise escalate with `transactionUpiRequestId`/`upiRequestId`. |
| Complaint or transaction data exists but required decrypted fields such as payer or payee VPA are missing | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Treat as unexpected server/data failure and escalate with request ids. |
| Database, cache, encryption, or other unexpected server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry with backoff for transient failures; escalate if persistent. |

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:643)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4688)
- S2S payload parsing: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:10)
- Merchant signature verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:41)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:238)
- S2S response helper: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:192)
- S2S response type: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:169)
- Generic response payload type: [src/Newton/Services/Transformer/Generic/Types.hs](../../src/Newton/Services/Transformer/Generic/Types.hs:178)
- Generic response payload helper: [src/Newton/Services/Transformer/Generic/Helper.hs](../../src/Newton/Services/Transformer/Generic/Helper.hs:47)
- Request and complaint types: [src/Newton/Product/Merchant/Complaints/Types.hs](../../src/Newton/Product/Merchant/Complaints/Types.hs:174)
- Product route/business logic: [src/Newton/Product/Merchant/Complaints/Complaint.hs](../../src/Newton/Product/Merchant/Complaints/Complaint.hs:240)
- Product response mapping: [src/Newton/Product/Merchant/Complaints/Helper.hs](../../src/Newton/Product/Merchant/Complaints/Helper.hs:197)
- Date default helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4356)
- Request validation helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Field validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275)
- Child-app merchant id object: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:699)
- Child-app lookup helper: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:865)
- Complaint query helper: [src/Newton/Storage/QueriesMiddleware/Complaint.hs](../../src/Newton/Storage/QueriesMiddleware/Complaint.hs:291)
- Complaint query filter type: [src/Newton/Storage/Queries/Complaint.hs](../../src/Newton/Storage/Queries/Complaint.hs:71)
- Complaint query predicate: [src/Newton/Storage/Queries/Complaint.hs](../../src/Newton/Storage/Queries/Complaint.hs:166)
- Complaint status enum: [src/Newton/Types/Storage/Complaint.hs](../../src/Newton/Types/Storage/Complaint.hs:47)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:32)
