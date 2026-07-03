# Pending Transactions API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/pending`

## Overview

Pending Transactions is a server-to-server API used by a merchant backend to fetch the currently actionable incoming UPI collect requests for one merchant customer.

The merchant sends a `merchantCustomerId`. Newton resolves that merchant customer under the authenticated merchant, finds unexpired collect transactions that are still in `PENDING` status, decrypts the transaction data needed for response construction, and returns a list of pending transactions.

Use this API when the merchant wants to show or reconcile pending collect requests for a customer before the customer approves, declines, or ignores the collect request.

## Business Use Case

Use Pending Transactions to:

- Show a customer their pending incoming collect requests in a merchant-owned app or web experience.
- Poll for pending collect requests after customer login, app resume, or a collect notification.
- Reconcile collect requests that are still actionable before calling an approve/decline flow.
- Display payer/payee, amount, expiry, reference, and optional mandate-related fields for each pending collect request.
- Avoid showing collect requests that are expired, terminal, self-initiated, or not associated with the requested merchant customer.

This endpoint is specifically a lookup/list endpoint. It does not create, approve, decline, expire, or refresh pending transactions.

## Integration Flow

1. Merchant backend identifies the customer in its own system.
2. Merchant calls `POST /api/{apiVersion}/merchants/transactions/pending` with the Newton `merchantCustomerId`.
3. Newton verifies the request envelope, merchant headers, signature/timestamp requirements, API access configuration, and IP allowlist where configured.
4. Newton resolves the merchant customer and linked customer record.
5. Newton finds unexpired, non-self-initiated, `PENDING` collect transactions for that merchant customer.
6. Newton returns `pendingTransactions`; the array is empty when no actionable collect request exists.
7. Merchant decrypts/verifies the response and uses `gatewayTransactionId` for follow-up transaction actions where applicable.

Important identifiers:

- `merchantCustomerId`: Merchant-scoped customer identifier supplied by the merchant.
- `gatewayTransactionId`: Newton UPI transaction id for the pending collect request.
- `gatewayReferenceId`: UPI/NPCI response/reference id stored with the pending collect request.
- `merchantRequestId`: Merchant order/request id from transaction metadata when present.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/pending
```

Payloads use Newton's standard server-to-server request and response envelope. Examples in this guide show decrypted business payloads for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment, for example `4`. The pending-transaction product logic does not branch on this value. Use the version shared during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. The body can be plain business JSON, JWS, or JWE depending on onboarding. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. Used to resolve the merchant before request verification. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-api-version` | Recommended | Send the API version shared during onboarding. This endpoint's current business logic does not use this header directly, but it is part of the standard S2S integration surface. |
| `x-timestamp` | Yes | 13-digit epoch-millisecond timestamp. Newton validates it against a 30-minute freshness window. |
| `x-merchant-signature` | Conditional | Required for plain payload mode. The signature is calculated over merchant id, merchant channel id, optional sub-merchant ids, `x-timestamp`, and the exact raw request body, using the merchant API key and configured signing strategy. For JWS/JWE modes, integrity is verified through the envelope. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature input when present. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature input when present. |
| `x-forwarded-for` | Conditional | Required when the merchant has an IP allowlist configured. Newton checks the first comma-separated IP in this header against the configured `whitelistedIps`. |

Newton internally reads the exact raw request body while verifying plain-payload signatures. Clients normally do not send an `x-raw-body` header directly unless their integration gateway has explicitly been configured to do so.

### Authentication, Signing, and Encryption

The route accepts the shared `EncRequest` envelope.

| Request mode | Body shape | Verification behavior |
| --- | --- | --- |
| Plain JSON | Decrypted business fields directly in the request body. | Newton resolves the merchant from headers, parses the body, then verifies `x-merchant-signature`, `x-timestamp`, API access, and IP allowlist. The request-body `iat` field is not checked in this mode. |
| JWS | Signed body containing `payload`, `signature`, and `protected`. | Newton verifies the JWS using the onboarded merchant key, decodes the business payload, then validates request-body `iat`. |
| JWE | Encrypted body containing `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`. | Newton decrypts the JWE, expects the decrypted content to be a signed payload, verifies the JWS, decodes the business payload, then validates request-body `iat`. |

For signed or encrypted requests, include `iat` in the decrypted business payload as a 13-digit epoch-millisecond timestamp within Newton's freshness window. For every retry, regenerate `iat`, `x-timestamp`, and the signature/envelope.

Responses use the shared `EncResponse` envelope. Depending on merchant response configuration, the transport response can be encrypted, signed, plain JSON with response-signature headers, or a direct error response. Always decrypt/verify the response first, then inspect `status`, `responseCode`, and `responseMessage`.

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
| `iat` | string | Conditional | No default. Required for JWS/JWE request modes; not validated for plain payload mode. | Issued-at timestamp as 13-digit epoch milliseconds. Used for signed/encrypted request freshness validation. |
| `udfParameters` | string | No | No default. If supplied and valid, Newton echoes it in the response. | Merchant-defined metadata encoded as a JSON object string, for example `"{\"screen\":\"collectInbox\"}"`. |

### Defaults and Omitted Field Behavior

This API does not apply request-level defaults. It does not accept `limit`, `offset`, date ranges, transaction ids, status filters, or type filters. The list criteria are derived from the authenticated merchant, the `merchantCustomerId`, and Newton's pending-collect query rules.

`udfParameters` is omitted from the response when it is not supplied in the request.

### Validation Rules

| Field | Rule | Failure response |
| --- | --- | --- |
| `merchantCustomerId` | Required, non-empty, maximum 256 characters. Must match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. | `BAD_REQUEST` with a length or regex validation message. |
| `udfParameters` | When supplied, must parse as a JSON object string and must not contain restricted characters rejected by ``^[^/$-*!%~`]+$``. | `BAD_REQUEST` with `JSON Text parse failed for udfParameters`. |
| `iat` | Required for JWS/JWE payloads. Must be a valid 13-digit epoch-millisecond timestamp within the accepted freshness window. | `INVALID_DATA`, `BAD_REQUEST`, or `REQUEST_EXPIRED`, depending on which timestamp check fails. |
| JSON body | Must parse into the pending-transactions request type. | Malformed JSON or missing required fields fail before business logic. |

## Pending Transaction Lookup Behavior

Newton resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`, then resolves `merchantCustomerId` for that merchant. The resolved merchant customer must have a linked customer record.

The transaction query returns only rows matching all of these conditions:

| Filter dimension | Behavior |
| --- | --- |
| Merchant customer | Transaction belongs to the resolved merchant customer. |
| Customer | Transaction belongs to the customer linked to the merchant customer. |
| Transaction type | Only `COLLECT` transactions are returned. |
| Initiation direction | Only non-self-initiated collect requests are returned. |
| Transaction status | Only transactions whose status is exactly `PENDING` are returned. |
| Expiry | Only transactions whose `expiry` is later than Newton's current local time are returned. Expired collect requests are excluded. |

When sharding is enabled, Newton queries the merchant-customer transaction secondary index and fetches matching transactions. Without sharding, Newton scans the latest transaction partitions and applies the same filter.

There is no request-level pagination for this S2S endpoint. If no matching transaction exists, Newton returns `SUCCESS` with `pendingTransactions: []`.

## Success Response

### Response Example With Pending Transactions

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "pendingTransactions": [
      {
        "merchantRequestId": "ORDER12345",
        "payerVpa": "customer@upi",
        "payeeVpa": "merchant@bank",
        "payeeName": "Merchant Store",
        "payeeMcc": "5411",
        "isVerifiedPayee": true,
        "isMarkedSpam": false,
        "type": "COLLECT",
        "amount": "100.00",
        "transactionTimestamp": "2024-07-03T10:15:30",
        "gatewayTransactionId": "UPI1234567890",
        "gatewayReferenceId": "NPCI1234567890",
        "remarks": "Collect request",
        "expiry": "2024-07-03T10:45:30",
        "refUrl": "https://merchant.example/orders/ORDER123",
        "refCategory": "00",
        "isGstPayee": "false",
        "seqNumber": "1",
        "collectType": "TRANSACTION",
        "accountReferenceId": "ACCREF123"
      }
    ]
  },
  "udfParameters": "{\"screen\":\"collectInbox\"}"
}
```

### Response Example With No Pending Transactions

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
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
| `payload` | object | Pending-transactions response payload. Present on successful lookups. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `pendingTransactions` | array | List of unexpired pending collect requests. Empty when there are no actionable pending collect requests. |

### `pendingTransactions[]` Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantRequestId` | string | Merchant order/request id read from transaction metadata when available. Omitted if the transaction does not contain it. |
| `payerVpa` | string | Payer/customer VPA for the collect request. Omitted only if not present in stored transaction data. |
| `payeeVpa` | string | Payee/merchant VPA for the collect request. Omitted only if not present in stored transaction data. |
| `payeeName` | string | Payee display name. Required in stored transaction payee info; missing data causes an internal error instead of a partial item. |
| `payeeMcc` | string | Payee MCC when merchant configuration enables MCC/ref URL in responses and transaction data contains MCC details. Omitted otherwise. |
| `isVerifiedPayee` | boolean | Payee verification flag when Newton configuration enables `isVerifiedPayeeInPendingCollect` and payee info contains the flag. Omitted otherwise. |
| `isMarkedSpam` | boolean | Payee spam flag when Newton configuration enables `isMarkedSpamInPendingCollect` and payee info contains the flag. Omitted otherwise. |
| `type` | string | Transaction type. For this endpoint, returned transactions are `COLLECT`. |
| `amount` | string | Collect amount formatted with two decimal places. |
| `transactionTimestamp` | string | Transaction creation timestamp formatted by Newton's local-time formatter. |
| `gatewayTransactionId` | string | Newton UPI transaction id, sourced from the stored `upiRequestId`. Use this for follow-up transaction actions. |
| `gatewayReferenceId` | string | UPI/NPCI response/reference id, sourced from stored `upiResponseId`. |
| `remarks` | string | Transaction remarks/note. |
| `expiry` | string | Collect request expiry timestamp when present. Returned transactions have expiry later than Newton's current local time. |
| `refUrl` | string | Reference URL from transaction metadata. This field is expected in stored transaction data; missing data causes an internal error. |
| `refCategory` | string | Reference category derived from transaction data/configuration. |
| `isGstPayee` | string | GST-payee indicator when derivable from configuration/transaction data. Omitted otherwise. |
| `seqNumber` | string | Mandate sequence number when merchant store flag `sendMandateFieldsInListTxn` is enabled and the transaction has a sequence number. Omitted otherwise. |
| `collectType` | string | Returned only when merchant store flag `sendMandateFieldsInListTxn` is enabled. Value is `MANDATE` when the transaction has mandate identifiers, otherwise `TRANSACTION`. |
| `accountReferenceId` | string | Mandate account reference id from transaction metadata when present. Omitted otherwise. |

## Failure Scenarios

Failure responses use the same response envelope when Newton reaches a layer that can produce a business error body. Some authentication, signature, or envelope failures are returned before a normal encrypted response can be constructed; handle those by HTTP status and response body.

Clients should always:

- Decrypt/verify the response when it is an `EncResponse`.
- Inspect `status`, `responseCode`, and `responseMessage`.
- Treat HTTP `401` as an authentication, signature, API-access, or IP-allowlist failure.
- Treat retryable infrastructure errors separately from validation or configuration errors.

### Request Validation Failures

Invalid `merchantCustomerId` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

Invalid `merchantCustomerId` characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
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

Client handling: fix the request payload. Do not retry unchanged.

### Missing or Invalid `iat`

For signed or encrypted requests, missing `iat` fails before business logic:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Invalid timestamp format:

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

Client handling: regenerate `iat`, `x-timestamp`, and the request signature/envelope. Keep clocks synchronized; Newton accepts timestamps within a 30-minute window.

### Authentication, Signature, and Encryption Failures

Missing merchant headers, unknown merchant/channel, invalid JWS/JWE key id, JWS verification failure, JWE decryption failure, missing plain-payload signature, or signature mismatch can return HTTP `401` with:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Some SDK-oriented envelope verification paths use:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Malformed signed/encrypted payload content can return HTTP `400` with:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

Client handling: do not retry unchanged. Verify merchant ids, key id, key material, signature base string, body canonicalization, timestamp, and envelope construction.

### Merchant API Access or IP Restriction Failures

If the API is blocked or not enabled for the merchant or sub-merchant, Newton returns HTTP `401` with:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If an IP allowlist is configured and `x-forwarded-for` is missing or the first IP is not allowlisted, Newton returns HTTP `401` with:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: treat these as onboarding/configuration issues. Confirm merchant API access, sub-merchant setup, and outbound IP configuration with Newton.

### Merchant Customer or Customer Lookup Failures

The route resolves `merchantCustomerId` under the authenticated merchant, then resolves the linked customer. If either record is missing, inactive, or malformed, the API fails before the transaction list is built. Depending on which lookup fails, the response can be an invalid-data or internal-error style body, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "MerchantCustomer not found"
}
```

or:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: verify that the customer has completed the merchant customer onboarding/binding flow and that the same merchant id/channel id is used for the lookup.

### No Pending Transactions

No matching pending collect requests is not an error. Newton returns:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "pendingTransactions": []
  }
}
```

Client handling: show an empty pending list or stop polling until the next customer action/notification.

### Stored Transaction Data Issues

While constructing each pending transaction item, Newton expects stored transaction data such as `payeeName`, `upiResponseId`, and `refUrl`. If a matching pending transaction is missing required stored fields, response construction can fail with:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry once after a short delay if this appears transient. If it repeats for the same customer, contact Newton support with request id, merchant customer id, and timestamp.

### Storage or Internal Failures

Unexpected database, cache, partition, decryption, or internal processing failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with exponential backoff and a fresh signature/envelope. Do not retry indefinitely; escalate repeated failures with request ids.

## Retry and Client Handling Guidance

- Safe to retry: This API is read-only and has no idempotency key. Retrying the same logical lookup is safe.
- Refresh signatures: On every retry, regenerate `x-timestamp`, signed/encrypted payload `iat`, and signatures/envelope values.
- Backoff: Use short exponential backoff for `5xx`, internal errors, or transient network failures.
- Do not retry unchanged: Validation errors, malformed envelopes, signature failures, API-not-enabled failures, and IP allowlist failures require request or configuration changes.
- Empty array is terminal for the current instant: `pendingTransactions: []` means Newton found no currently actionable pending collect request. A future collect request can still appear later.
- Use returned identifiers carefully: Use `gatewayTransactionId` as the transaction identifier for follow-up flows. `gatewayReferenceId` is the UPI/NPCI reference and is useful for reconciliation.

## Source References

- Route declaration: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:337)
- Route handler and middleware chain: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2187)
- Request and response types: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:165)
- Pending transaction response item type: [src/Newton/Types/API/PendingTransaction.hs](../../src/Newton/Types/API/PendingTransaction.hs:13)
- Product route and lookup flow: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:131)
- Pending transaction query: [src/Newton/Storage/QueriesMiddleware/Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:192)
- Response transformer: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:502)
- Request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275)
- Request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:13)
- Payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API/IP verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:45)
- Standard error bodies: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
