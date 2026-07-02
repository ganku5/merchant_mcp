# List Pending Collect Requests API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/listPending`

## Overview

List Pending Collect Requests is a server-to-server API used by a merchant backend to fetch the currently actionable incoming UPI collect requests for one merchant customer.

The merchant sends the `merchantCustomerId`. Newton resolves the merchant customer, finds active pending collect transactions for that customer, and returns the collect-request details that the merchant can show in its own app or backend workflow. The response includes payer/payee identifiers, amount, expiry, collect type, mandate identifiers where applicable, and merchant/customer identifiers for reconciliation.

This endpoint is specifically for pending incoming collect requests. It is not the same as `/merchants/transactions/pending`, which uses a different request type and supports limit/offset pagination.

## Business Use Case

Use this API when the merchant needs to:

- Show a customer the list of pending collect requests that can still be approved or declined.
- Poll for pending collect requests after a notification, app resume, or customer login.
- Reconcile pending collect requests before calling the collect approve/decline API.
- Display mandate-related collect requests with `collectType`, `orgMandateId`, `umn`, and sequence number where available.
- Avoid showing expired or already terminal collect requests to the customer.

## Integration Flow

1. Merchant backend identifies the customer in its own system.
2. Merchant calls `listPending` with the Newton `merchantCustomerId`.
3. Newton verifies the S2S request envelope, merchant headers, signature/timestamps, API access, and IP allowlist where configured.
4. Newton resolves the merchant customer and linked customer record.
5. Newton returns all unexpired `PENDING` collect transactions for that merchant customer.
6. Merchant decrypts/verifies the response, displays the pending collect requests, and uses `gatewayTransactionId` for follow-up approve/decline flows.

Important identifiers:

- `merchantCustomerId`: Merchant-scoped customer identifier supplied by the merchant.
- `gatewayTransactionId`: Newton UPI transaction id for the collect request. Use this identifier in follow-up transaction actions.
- `gatewayReferenceId`: UPI/NPCI response/reference id stored with the pending collect request.
- `umn` and `orgMandateId`: Mandate identifiers returned when the pending collect request is mandate-linked and the transaction data contains them.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/listPending
```

Payloads use Newton's standard S2S request and response envelope. Examples in this guide show the decrypted business payload for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment, for example `4`. The handler also reads `x-api-version`; if the header is missing or not an integer, Newton treats it as version `0` for response-field gating. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. The JSON can be a plain business payload, a JWS signed body, or a JWE encrypted body depending on onboarding. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. Used to resolve the merchant before request verification. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-api-version` | Recommended | Integer API version used by transformer logic. If omitted or invalid, Newton uses version `0`. Send the version shared during onboarding; version `2` or higher is needed for the `purpose` response field. |
| `x-timestamp` | Yes | 13-digit epoch-millisecond request timestamp used for signature and freshness validation. |
| `x-merchant-signature` | Conditional | Required for plain unsigned payload mode. The signature is calculated over merchant id, merchant channel id, optional sub-merchant ids, `x-timestamp`, and the exact raw request body, using the merchant API key and configured signing strategy. For JWS/JWE modes, integrity is verified through the envelope. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature input when present. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature input when present. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. Newton checks the first comma-separated IP in this header against the allowlist. |

Newton also reads the exact raw request body internally while verifying plain-payload signatures. Clients normally do not send `x-raw-body` directly unless their integration gateway explicitly requires it.

### Authentication, Signing, and Encryption

The route accepts the shared `EncRequest` envelope:

| Request mode | Body shape | Verification behavior |
| --- | --- | --- |
| Plain JSON | Decrypted business fields directly in the body | Allowed only where configured. Newton verifies `x-merchant-signature`, merchant headers, `x-timestamp`, and raw body bytes. The request-body `iat` field is not checked in this mode. |
| JWS | Signed payload body | Newton verifies the JWS using the onboarded merchant key, parses the business payload, and validates `iat`. |
| JWE | Encrypted payload body | Newton decrypts the JWE using Newton's private key, expects the decrypted content to be a signed payload, verifies the JWS, parses the business payload, and validates `iat`. |

For signed or encrypted requests, include `iat` in the decrypted business payload as a 13-digit epoch-millisecond timestamp within Newton's freshness window. For every retry, regenerate `iat`, `x-timestamp`, and the signature/envelope.

Responses use the shared `EncResponse` envelope. Depending on merchant response configuration, the transport response can be encrypted, signed, plain JSON with `X-Response-Signature`, or a direct error response. Always decrypt/verify the response first, then inspect `status`, `responseCode`, and `responseMessage`.

## Request

### Required Minimum

```json
{
  "merchantCustomerId": "CUST12345"
}
```

### Signed or Encrypted Request Example

```json
{
  "merchantCustomerId": "CUST12345",
  "iat": "1720000000000",
  "udfParameters": "{\"screen\":\"collectInbox\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant-scoped customer id. Must identify an active merchant customer belonging to the merchant in the request headers. |
| `iat` | string | Conditional | No default. Required for JWS/JWE request modes; ignored by validation for plain unsigned payload mode. | Issued-at timestamp as 13-digit epoch milliseconds. Used for signed/encrypted request freshness validation. |
| `udfParameters` | string | No | No default. If supplied and valid, Newton echoes it in the response. | Merchant-defined metadata encoded as a JSON object string, for example `"{\"screen\":\"collectInbox\"}"`. |

### Validation Rules

| Field | Rule | Failure response |
| --- | --- | --- |
| `merchantCustomerId` | Required, non-empty, maximum 256 characters. Must match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. | `BAD_REQUEST` with either `merchantCustomerId length is not in between 1 and 256` or `merchantCustomerId is not alphanumeric`. |
| `udfParameters` | When supplied, must parse as a JSON object string and must not contain restricted characters rejected by the configured regex. | `BAD_REQUEST` with `JSON Text parse failed for udfParameters`. |
| `iat` | Required for JWS/JWE payloads. Must be a valid 13-digit epoch-millisecond timestamp within the accepted freshness window. | `INVALID_DATA`, `BAD_REQUEST`, or request-expiry style errors depending on which timestamp check fails. |

The JSON parser also rejects malformed JSON or missing required fields before business logic runs. For example, omitting `merchantCustomerId` from the decrypted business payload causes a JSON decoding failure rather than an empty-list response.

## Filter and List Behavior

`listPending` does not accept filter fields, date ranges, `limit`, or `offset`.

Newton derives the filter from the authenticated merchant and the request `merchantCustomerId`:

| Filter dimension | Behavior |
| --- | --- |
| Merchant | Resolved from `x-merchant-id` and `x-merchant-channel-id`. |
| Merchant customer | Resolved from `merchantCustomerId` for the authenticated merchant. The record must be active. |
| Customer | Resolved from the merchant customer record. |
| Transaction type | Only `COLLECT` transactions are returned. |
| Initiation direction | Only non-self-initiated collect requests are returned. |
| Transaction status | Only transactions whose status is exactly `PENDING` are returned. |
| Expiry | Only transactions whose `expiry` is later than Newton's current local time are returned. Expired collect requests are excluded. |

When sharding is enabled, the query uses the merchant-customer transaction secondary index. Without sharding, Newton scans the latest three transaction partitions and applies the same filter. If no matching transaction is found, the API succeeds with `pendingTransactions: []`.

There is no server-side pagination for this endpoint. A large number of pending collect requests is unusual; clients should still handle an empty array and multiple items.

## Success Response

### Response Example With Pending Collect Requests

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "pendingTransactions": [
      {
        "payerVpa": "customer@upi",
        "payeeVpa": "merchant@bank",
        "payeeName": "Merchant Store",
        "payeeMcc": "5411",
        "isVerifiedPayee": "true",
        "isMarkedSpam": "false",
        "amount": "100.00",
        "transactionTimestamp": "2024-07-03T10:15:30",
        "gatewayTransactionId": "UPI1234567890",
        "gatewayReferenceId": "NPCI1234567890",
        "remarks": "Collect request",
        "expiry": "2024-07-03T10:45:30",
        "refUrl": "https://merchant.example/orders/ORDER123",
        "refCategory": "00",
        "collectType": "TRANSACTION",
        "seqNumber": "1",
        "isGstPayee": "false"
      }
    ]
  },
  "udfParameters": "{\"screen\":\"collectInbox\"}"
}
```

### Response Example With No Pending Collect Requests

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "pendingTransactions": []
  }
}
```

### Response Envelope Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Success value is `SUCCESS`. |
| `responseMessage` | string | Success value is `SUCCESS`. |
| `payload` | object | List-pending response payload. Always present on success. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number associated with the resolved merchant customer. This value is decrypted before response construction when Passetto-backed PII handling is enabled. |
| `pendingTransactions` | array | List of unexpired pending collect requests. Empty when there are no actionable collect requests. |

### `pendingTransactions[]` Fields

| Field | Type | Description |
| --- | --- | --- |
| `payerVpa` | string | VPA of the customer/payer who must approve or decline the collect request. PII-protected and decrypted before response construction when required. |
| `payeeVpa` | string | Payee/merchant VPA for the collect request. PII-protected and decrypted before response construction when required. |
| `payeeName` | string | Payee display name from stored payee information. If this value is missing in the stored transaction, response construction fails with an internal/invalid-data style error. |
| `payeeMcc` | string | Payee MCC. Defaults to `"0000"` when MCC cannot be derived from transaction or merchant data. |
| `isVerifiedPayee` | string | `"true"` or `"false"`. Populated from payee information when merchant/configuration enables verified-payee information for pending collect responses; otherwise defaults to `"false"`. |
| `isMarkedSpam` | string | `"true"` or `"false"`. Populated from payee information when merchant/configuration enables spam information for pending collect responses; otherwise defaults to `"false"`. |
| `amount` | string | Collect amount formatted with two decimal places. |
| `transactionTimestamp` | string | Transaction creation timestamp formatted according to merchant configuration where applicable. |
| `gatewayTransactionId` | string | Newton UPI transaction id (`upiRequestId`). Use this for follow-up approve/decline calls. |
| `gatewayReferenceId` | string | Gateway/NPCI reference id (`upiResponseId`). Required in stored transaction data for successful response construction. |
| `remarks` | string | Collect remarks stored on the transaction. |
| `expiry` | string | Collect request expiry timestamp. Only rows with expiry later than Newton's current time are returned. |
| `refUrl` | string | Reference URL from transaction metadata when present. Omitted when not present. |
| `refCategory` | string | Reference category derived from transaction/configuration when available. Omitted when unavailable. |
| `collectType` | string | `MANDATE` when the collect request is linked to a mandate (`umn` or mandate id exists); otherwise `TRANSACTION`. |
| `seqNumber` | string | Mandate sequence number or transaction sequence number when present. Omitted when not present. |
| `isGstPayee` | string | GST payee flag derived from configuration/transaction data when available. Omitted when unavailable. |
| `orgMandateId` | string | Original mandate request id when available. For records that only store internal mandate id, Newton fetches mandate details only when `x-api-version > 0`. Omitted otherwise. |
| `umn` | string | Unique mandate number when available. For records that only store internal mandate id, Newton fetches mandate details only when `x-api-version > 0`. Omitted otherwise. |
| `purpose` | string | Transaction purpose code. Returned only when `x-api-version > 1` and the stored transaction has a purpose value. |

## Failure Scenarios

Failure responses follow Newton's shared S2S error body after decryption/parsing:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

The HTTP status depends on the failing layer. Product validation often returns HTTP `200` with a failure body, auth failures commonly return `401`, malformed signed/encrypted payload parsing can return `400`, and unexpected product/storage failures can return `500` or HTTP `200` with `INTERNAL_SERVER_ERROR`. Clients should branch on the decrypted body first.

### Request Validation Failure

Invalid `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Empty or too-long `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

Invalid `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Client handling: fix the payload and retry. These errors are deterministic.

### Malformed JSON or Payload Envelope

Malformed plain JSON, a JWS payload that cannot be base64-decoded to the business request, or a JWE payload that decrypts but cannot be parsed can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantCustomerId\" not found"
}
```

Client handling: verify the request body sent over the wire, the signed payload content, and the content type. For JWE, ensure the decrypted content is a signed payload in the format agreed during onboarding.

### Missing or Invalid `iat` / Timestamp

For JWS/JWE request modes, missing `iat` in the decrypted business payload can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Malformed or stale `iat`/`x-timestamp` can return a bad-request or invalid-data timestamp response, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Client handling: generate fresh 13-digit epoch-millisecond values for both `iat` and `x-timestamp`, then recreate the signature or encrypted envelope. Do not replay old signed material.

### Authentication, Signature, and Encryption Failure

These failures include missing merchant headers, unknown merchant id/channel id, JWS signature failure, JWE decryption failure, missing/invalid key id, missing plain-payload `x-merchant-signature`, signature mismatch, and source IP allowlist failure.

Typical response:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the merchant is resolved but this API is blocked or not allowed for the merchant, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: verify `x-merchant-id`, `x-merchant-channel-id`, optional sub-merchant headers, key id, signing input, exact raw request body, configured signature strategy, encryption keys, timestamp freshness, and allowlisted egress IP. Do not retry unchanged.

### Merchant Customer or Customer Resolution Failure

If `merchantCustomerId` is syntactically valid but no active merchant customer exists for the authenticated merchant, Newton returns the invalid user-profile error:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

If the merchant customer record exists but is missing required customer linkage, the route can fail with an invalid device-binding style response:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Client handling: confirm the customer has completed the Newton onboarding/device-binding flow expected for this merchant customer, and that the `merchantCustomerId` belongs to the merchant credentials in the request headers.

### No Pending Collect Requests

This is not an error. Newton returns success with an empty list:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "pendingTransactions": []
  }
}
```

Client handling: show an empty state or stop polling until the next customer action/notification.

### Stored Transaction Data Missing Required Fields

The response builder requires stored pending collect transactions to have values such as `upiResponseId`, `payerVpa`, `payeeVpa`, `payeeName`, and `expiry`. If a matching stored transaction is missing those fields, Newton returns a generic internal-server failure instead of a partial row.

Representative response:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry once after a short backoff if the failure appears transient. If repeated for the same customer, raise the issue with Newton support and include `merchantCustomerId`, request timestamp, and Newton request id if available.

### Mandate Lookup Failure for Mandate-Linked Collects

When a transaction has an internal mandate id and `x-api-version > 0`, Newton looks up the mandate to populate `orgMandateId` and `umn`. If the mandate id cannot be resolved, the API can fail rather than omit only those fields.

Representative response:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid getMandate: MandateId is not found"
}
```

Client handling: retry later only if the collect was just created and mandate propagation may still be in progress. Escalate repeated failures.

### Internal Errors

Unexpected failures in Redis/database access, merchant configuration lookup, Passetto/PII decrypt, or response construction can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: use bounded retries with backoff. Do not create duplicate customer actions from retries; this API is read-only, but repeated polling should still be rate-limited.

## Pagination, Polling, and Retry Guidance

- This endpoint has no `limit` or `offset`; consume the complete `pendingTransactions` array returned by Newton.
- Treat `pendingTransactions: []` as a successful empty state.
- Do not assume the same collect request will remain in the list. It disappears when it expires or moves out of `PENDING`.
- Use `expiry` to hide stale items in your UI if the customer keeps the screen open.
- Use `gatewayTransactionId` as the stable identifier for approve/decline flows and local de-duplication.
- For auth, validation, and API access failures, fix the request/configuration before retrying.
- For transient `INTERNAL_SERVER_ERROR` or network failures, retry with exponential backoff and fresh signing/encryption timestamps.
- For signed/encrypted retries, regenerate `iat`, `x-timestamp`, and the full request signature/envelope. Do not replay a stale body.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:345)
- Route handler and auth pipeline: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2205)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:70)
- Merchant signature/API access/IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request and response types: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:226)
- Request validation: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:247)
- Common field validations: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:647)
- Product logic and list filter: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:149)
- Pending transaction query: [src/Newton/Storage/QueriesMiddleware/Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:192)
- Response construction: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:649)
- Pending transaction response fields: [src/Newton/Types/API/PendingTransaction.hs](../../src/Newton/Types/API/PendingTransaction.hs:42)
- Shared error response shape: [src/Newton/Types/API/Common.hs](../../src/Newton/Types/API/Common.hs:12)
- Shared error codes: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
