# Transaction Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/status`

## Overview

Transaction Status is a server-to-server API used to fetch the latest known status for a P2M transaction created by a merchant order or registered intent.

The merchant calls this API with its original `merchantRequestId`. Newton looks up the merchant order, finds the linked transaction, and returns the transaction amount, timestamp, gateway transaction id, gateway response code/message, and optional payer/account details. If the order is not already final, Newton may also perform a status refresh before responding, subject to merchant configuration and status-check rate limits.

Use this API for reconciliation, customer-support checks, payment polling, or to recover the result of a customer journey when callbacks were delayed or missed.

## Business Use Case

Transaction Status helps merchants:

- Confirm whether a registered intent or P2M payment is still pending, successful, failed, declined, timed out, or deemed.
- Reconcile merchant orders against Newton transaction ids and gateway response codes.
- Safely poll a transaction without creating a new payment request.
- Recover from missed callbacks by checking the latest stored or refreshed transaction status.
- Receive optional payer/account metadata where enabled for the merchant.
- Inspect TPV response data, including TPV type and TPV validation status, where applicable.

## Integration Flow

1. Merchant creates an order or register-intent request and stores its `merchantRequestId`.
2. Customer completes, abandons, or is still processing the payment journey.
3. Merchant calls `status` with the same `merchantRequestId`.
4. Newton authenticates the merchant, validates the request, and checks API/IP access controls.
5. Newton looks up the merchant order and linked transaction.
6. If the merchant order is already `SUCCESS` or `FAILURE`, Newton returns the stored transaction details.
7. If the order is not final, Newton checks status-refresh limits. When allowed and enabled for the merchant, Newton calls the transaction-status wrapper/NPCI path, updates the merchant order status, and returns the refreshed details.
8. Merchant decrypts the response and uses `payload.gatewayResponseCode` and `payload.gatewayResponseMessage` as the transaction result for the checked order.

Important identifiers:

- `merchantRequestId`: Merchant-generated order/reference id originally used for the payment or register-intent flow.
- `gatewayTransactionId`: Newton UPI transaction id for the matched transaction.
- `merchantId` and `merchantChannelId`: Merchant identifiers from the authenticated merchant account.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/status
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | API version shared during onboarding. Use `4` for new integrations unless Newton has provided a different value. |
| `x-merchant-id` | Yes | Merchant id issued by Newton. Used to load the merchant account. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued by Newton. |
| `x-sub-merchant-id` | Conditional | Required only for sub-merchant integrations where Newton has enabled sub-merchant routing. |
| `x-sub-merchant-channel-id` | Conditional | Required only with `x-sub-merchant-id`. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness for signed/plain requests. |
| `x-merchant-signature` | Yes for unsigned/plain request envelopes | Signature over merchant ids, timestamp, and raw request body. Not rechecked when the body itself is already a signed or encrypted envelope. |
| `Authorization` | Conditional | Use only if specified in the onboarding profile for this merchant. |
| `x-forwarded-for` | Conditional | Required when the merchant is configured with whitelisted IPs. Newton validates the first IP in this header. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the integration, for example `4`. |

## Authentication, Signing, and Encryption

This route accepts Newton's shared `EncRequest` transport shape. Depending on the onboarding profile, the request body can be:

- an encrypted JWE payload,
- a signed JWS payload,
- or a plain JSON business payload with a merchant signature header.

For encrypted or signed payloads, the decrypted business body must match the request schema documented below. For plain/unsigned payloads, Newton validates `x-merchant-signature` using the merchant API key and the raw request body. Newton also validates:

- `iat` inside signed/encrypted business payloads,
- `x-timestamp` on the request headers,
- merchant API access configuration,
- optional sub-merchant access configuration,
- optional IP whitelist configuration.

The response is returned in the corresponding Newton S2S response envelope. In normal client integration docs and examples, read the decrypted business body fields shown below.

## Request

### Required Minimum

```json
{
  "merchantRequestId": "ORDER12345"
}
```

### With Issued-At and UDF Metadata

```json
{
  "merchantRequestId": "ORDER12345",
  "iat": "2026-07-02T12:30:00+05:30",
  "udfParameters": {
    "cartId": "CART123",
    "source": "reconciliation"
  }
}
```

`udfParameters` may also be sent as a JSON-object string when your integration profile uses stringified metadata:

```json
{
  "merchantRequestId": "ORDER12345",
  "udfParameters": "{\"cartId\":\"CART123\",\"source\":\"reconciliation\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Merchant order/reference id whose status is being checked. Must be the same id used when the transaction/order was created. |
| `iat` | string | Conditional | No default. Required by middleware for signed/encrypted request envelopes. Plain/unsigned envelopes do not require it. | Issued-at timestamp used for request freshness validation. Use the timestamp format shared during onboarding. |
| `udfParameters` | object or JSON-object string | No | No default. Omitted from the response if not supplied. | Merchant-defined metadata. When supplied and valid, Newton echoes it in the success response. |

## Validation Rules

### `merchantRequestId`

`merchantRequestId` must:

- be present,
- be 1 to 35 characters,
- contain letters, numbers, hyphen, dot, or underscore,
- include at least one alphanumeric character.

Valid examples:

```text
ORDER12345
ORDER-12345
order_123.45
```

Invalid examples:

```text
""
"ORDER/123"
"ORDER 123"
"------------------------------------"
```

### `udfParameters`

When supplied, `udfParameters` must be either:

- a JSON object, or
- a string that parses to a JSON object.

The encoded object/string must not contain these special characters rejected by validation:

```text
/ # - ( ) * ! % ~ `
```

Because hyphen is rejected inside `udfParameters`, use values such as `"ORDER12345"` rather than `"ORDER-12345"` inside metadata fields.

### Request Freshness

For signed/encrypted payloads, `iat` is required and must pass Newton timestamp validation. Separately, `x-timestamp` is required by merchant signature middleware and is checked for freshness except in the configured non-production checksum-bypass modes.

## Transaction Lookup and Status Refresh Behavior

Newton processes a valid request as follows:

1. Loads the authenticated merchant from `x-merchant-id` and `x-merchant-channel-id`.
2. Finds a merchant order for the supplied `merchantRequestId`. Sub-merchant-aware lookup is used.
3. If no merchant order is found, checks the merchant-validation/registered-intent table for the same merchant request id.
4. If a merchant-validation record exists and has expired, returns `REQUEST_EXPIRED`.
5. If a merchant-validation record exists and is still pending, returns `REQUEST_PENDING`.
6. If neither a merchant order nor merchant-validation record exists, returns `REQUEST_NOT_FOUND`.
7. If the merchant order exists but has no linked transaction id, returns `UNINITIATED_REQUEST`.
8. If the linked transaction exists and the merchant order status is `SUCCESS` or `FAILURE`, returns the stored transaction details without a fresh upstream check.
9. If the order is not final, checks Newton status-check rate limits and lower/upper bounds.
10. If the request is allowed to refresh and upstream transaction-status refresh is enabled for the merchant, calls the upstream transaction-status path and updates the merchant order status from the refreshed transaction.
11. If refresh is not allowed by rate limits/window, or upstream refresh is not enabled for the merchant, returns the current stored transaction details.

Rate limiting is intentionally silent from the response contract for this endpoint: the API returns the current status payload rather than a rate-limit error when the refresh is skipped. Polling clients should still use a reasonable backoff because repeated calls may be served from stored state until the configured window allows another upstream refresh.

## Success Response

The decrypted success body follows this shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "ORDER12345",
    "amount": "100.00",
    "transactionTimestamp": "2026-07-02 12:30:00",
    "gatewayTransactionId": "TXN1234567890",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS"
  }
}
```

### Pending Transaction Example

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "ORDER12346",
    "amount": "250.00",
    "transactionTimestamp": "2026-07-02 12:31:00",
    "gatewayTransactionId": "TXN1234567891",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your transaction is in pending state"
  }
}
```

### Response With Optional Payer, Account, TPV, and UDF Fields

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "ORDER12347",
    "amount": "500.00",
    "transactionTimestamp": "2026-07-02 12:32:00",
    "gatewayTransactionId": "TXN1234567892",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "bankCode": "123456",
    "maskedAccountNumber": "XXXXXX1234",
    "bankAccountUniqueId": "ACCOUNT_HASH_OR_REFERENCE",
    "payerVpa": "customer@upi",
    "payerIfsc": "HDFC0000001",
    "payerAccType": "SAVINGS",
    "payerAccBin": "123456",
    "payerAccountHash": "PAYER_ACCOUNT_HASH",
    "payeeMcc": "5411",
    "refUrl": "https://merchant.example/orders/ORDER12347",
    "tpvType": "FULL",
    "tpvValidationStatus": "SUCCESS"
  },
  "udfParameters": {
    "cartId": "CART123",
    "source": "reconciliation"
  }
}
```

Optional fields are omitted from JSON when they are not available or not enabled.

## Response Field Reference

### Top-Level Body

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API wrapper status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Transaction status payload. Present on successful status lookup. |
| `udfParameters` | object or string | Echo of request `udfParameters` when supplied and valid. Omitted otherwise. |

### `payload`

| Field | Type | Always present? | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Yes | Merchant id for the authenticated merchant. |
| `merchantChannelId` | string | Yes | Merchant channel id for the authenticated merchant. |
| `merchantRequestId` | string | Yes | Merchant order/reference id for the matched merchant order. |
| `amount` | string | Yes | Transaction amount formatted with exactly two decimal places. |
| `transactionTimestamp` | string | Yes | Transaction creation timestamp in Newton local-time text format. |
| `gatewayTransactionId` | string | Yes | Newton UPI transaction id. |
| `gatewayResponseCode` | string | Yes | Gateway/status code derived from the transaction status and NPCI response. |
| `gatewayResponseMessage` | string | Yes | Gateway/status message derived from the transaction status and NPCI response. |
| `bankCode` | string | No | Debit bank IIN/bank code. Returned only when debit account hash data is available from the linked payer-side transaction. |
| `maskedAccountNumber` | string | No | Masked debit account number. Returned only when debit account hash data is available. |
| `bankAccountUniqueId` | string | No | Debit account unique id/account hash. Returned only when debit account hash data is available. |
| `payerVpa` | string | No | Payer VPA. Returned only when merchant configuration `payerVpaInTransactionStatusResponse` is enabled. |
| `payerIfsc` | string | No | Payer account IFSC, returned according to merchant/version-controlled response settings. |
| `payerAccType` | string | No | Payer account type, returned according to merchant/version-controlled response settings. |
| `payerAccBin` | string | No | Payer account BIN, returned according to merchant/version-controlled response settings. |
| `payerAccountHash` | string | No | Hash of the account from which money was debited. Used for TPV/KYC-enabled merchants where enough account data is available. |
| `payeeMcc` | string | No | Payee MCC derived from merchant/transaction data. |
| `refUrl` | string | No | Merchant reference URL. Returned only when merchant configuration `mccRefUrlInResponse` is enabled. |
| `tpvType` | string | No | TPV mode for the transaction, for example `FULL` or `PARTIAL`, when stored on the transaction. |
| `tpvValidationStatus` | string | No | TPV validation status derived from transaction metadata. Omitted when no TPV reference-failure status is present. |

### Gateway Response Code Mapping

For this endpoint, the top-level `status` is `SUCCESS` when Newton successfully found and returned the transaction status payload. The transaction result is represented by `payload.gatewayResponseCode` and `payload.gatewayResponseMessage`.

| Stored/refreshed transaction state | `gatewayResponseCode` | `gatewayResponseMessage` |
| --- | --- | --- |
| Pending-like states: `PENDING`, `TIMED_OUT`, `DECLINE_INITIATED`, `COLLECT_PAY_INITIATED` | `01` | `Your transaction is in pending state` or the configured message for `01`. |
| `DEEMED` | `00` | Configured message for `00`. |
| `DEEMED_DEBIT` | `00` | `Your transaction is deemed debit`. |
| `DECLINED` | `ZA` | Configured message for `ZA`. |
| Other terminal or updated states | NPCI `code` from the transaction response when present, otherwise an empty string. | NPCI `result` from the transaction response when present, otherwise an empty string. |

## Error Handling

Failure responses use the same Newton S2S error body. Depending on where the failure occurs, the HTTP status may be `200`, `400`, `401`, `410`, `422`, or `500`; clients should read the decrypted body whenever one is available.

Most business failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

When `payload` is empty, it is omitted from JSON.

### Status API Failure Bodies

Use the body pattern shown in the `Response body` column for each scenario.

| Scenario | Response body |
| --- | --- |
| `merchantRequestId` is empty or longer than 35 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` |
| `merchantRequestId` contains invalid characters or no alphanumeric characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\""}` |
| `udfParameters` is not an object or JSON-object string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"Expected Object or String type for udfParamaters\""}` |
| `udfParameters` string cannot be parsed as a JSON object | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| `udfParameters` object/string contains rejected special characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"JSON Object regex match failed for udfParameters\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| Request uses a signed/encrypted envelope but `iat` is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"IAT is empty"}` |
| No merchant order or merchant-validation record exists for the merchant request id | `{"status":"FAILURE","responseCode":"REQUEST_NOT_FOUND","responseMessage":"REQUEST_NOT_FOUND"}` |
| A merchant-validation/register-intent record exists, but the customer flow has not produced a transaction yet | `{"status":"FAILURE","responseCode":"REQUEST_PENDING","responseMessage":"REQUEST_PENDING"}` |
| A merchant-validation/register-intent record exists but has expired before a transaction was initiated | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` |
| Merchant-validation record contains a stored dropout/error code | `{"status":"FAILURE","responseCode":"DROPOUT","responseMessage":"U16-User dropped out"}` |
| Merchant order exists but no transaction id has been linked yet | `{"status":"FAILURE","responseCode":"UNINITIATED_REQUEST","responseMessage":"UNINITIATED_REQUEST"}` |
| Upstream transaction-status call times out while refreshing a non-final transaction | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"UPI service is not reachable at the moment for transactional apis"}` |
| Upstream transaction-status call returns an error while refreshing a non-final transaction | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Unexpected server, database, decryption, transformer, or cache failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

Authentication, signature, encryption, merchant access, and IP restriction failures happen before status business logic runs. They use the standard Newton S2S error body, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

or, when API access is disabled for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

or, for authentication failures in shared middleware paths:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

### Authentication and Access Failure Scenarios

| Scenario | Expected handling |
| --- | --- |
| Missing `x-merchant-id` or `x-merchant-channel-id` | Fix the request headers. Newton cannot identify the merchant. |
| Missing `x-timestamp` | Fix request construction/signing. |
| Missing or invalid `x-merchant-signature` for plain/unsigned requests | Regenerate the signature using the exact raw JSON body and onboarding signing strategy. |
| Signed/encrypted payload cannot be verified/decrypted | Verify the active key pair, payload format, and onboarding encryption profile. |
| Request timestamp or `iat` is stale/invalid | Regenerate the request with the current timestamp. |
| API is blocked or not in the merchant's allowed API list | Ask Newton to enable the Transaction Status API for the merchant. |
| Merchant has whitelisted IPs and the first `x-forwarded-for` IP is missing or not whitelisted | Send traffic from an onboarded IP or update the whitelist with Newton. |

## Retry and Client Handling Guidance

- Treat this API as an idempotent read for a fixed `merchantRequestId`.
- Do not create a new payment or register-intent request just because status is pending.
- If `payload.gatewayResponseCode` is `01`, continue polling with backoff. Repeated rapid polling may return stored state because upstream refresh is rate-limited.
- If the body is `REQUEST_PENDING`, the payment was registered/validated but no transaction has been linked yet. Retry only if the customer journey is still expected to continue.
- If the body is `REQUEST_EXPIRED`, stop polling for that payment attempt and create a new payment/register-intent flow if the customer still wants to pay.
- If the body is `REQUEST_NOT_FOUND`, verify that the `merchantRequestId`, merchant id, channel id, and environment are correct before retrying.
- If the body is `UNINITIATED_REQUEST`, the merchant order exists but the payment transaction has not started; retry only while the customer flow is active.
- For service-unavailable responses from the upstream status path or transient HTTP/network failures, retry with exponential backoff.
- For validation, auth/signature, API access, or IP whitelist failures, do not retry unchanged. Fix request construction or merchant configuration first.
- Store `gatewayTransactionId`, `gatewayResponseCode`, `gatewayResponseMessage`, `amount`, and `transactionTimestamp` for reconciliation.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:346)
- Route handler and signature middleware call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2223)
- Request type and validation instance: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:309)
- Response type and payload type: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:360)
- Field validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:256)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Encrypted/signed/plain request envelope: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Status business logic: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:174)
- Status refresh rate-limit decision: [src/Newton/Product/Sherlock/TxnStatus.hs](../../src/Newton/Product/Sherlock/TxnStatus.hs:28)
- Upstream status wrapper behavior: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:142)
- Status response transformer and gateway code mapping: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:567)
- Merchant-validation fallback failures: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1730)
- Shared error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
