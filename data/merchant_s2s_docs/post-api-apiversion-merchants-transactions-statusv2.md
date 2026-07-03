# Status V2 API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/statusV2`

## Overview

Status V2 is a merchant server-to-server API for fetching the current status and reconciliation details for a Newton UPI transaction.

Use this API after initiating or registering a transaction when the merchant backend needs to confirm the latest known outcome, reconcile an order, support a customer query, or resolve an ambiguous callback or timeout.

The API can look up a transaction by Newton's UPI transaction id (`upiRequestId`), the merchant's order/reference id (`merchantRequestId`), or both. When the transaction is still non-terminal and the merchant/status-check configuration allows it, Newton can refresh the transaction status from the downstream status-check path before returning the response.

## Business Use Case

Status V2 helps merchants:

- Poll the current payment status for a merchant order.
- Reconcile callbacks against Newton's stored transaction.
- Resolve customer-support disputes using payer/payee, amount, RRN, and account metadata.
- Distinguish merchant-credit and customer-credit/debit transaction views.
- Continue a checkout flow when the payment is still pending.
- Detect expired, declined, failed, reversed, or otherwise terminal outcomes without creating a duplicate payment attempt.

For new integrations that need callback-shaped responses and additional status-check controls, Newton may recommend `status360`; however, this document describes the existing `statusV2` route and its behavior.

## Integration Flow

1. Merchant creates or receives a Newton transaction through a payment, collect, register-intent, or related flow.
2. Merchant stores `upiRequestId` and/or `merchantRequestId`.
3. Merchant calls `statusV2` with one or both identifiers.
4. Newton authenticates the merchant, validates the request, and checks merchant/sub-merchant access.
5. Newton locates matching transaction records.
6. If needed, Newton chooses the payer-side or payee-side record using `vpa`, `mobileNumber`, or the default payee-side behavior.
7. If a merchant order exists and the transaction is not terminal, Newton may run the configured status-refresh path.
8. Newton returns a top-level successful API response containing the current transaction payload. The payment outcome is represented inside `payload.gatewayResponseCode`, `payload.gatewayResponseMessage`, and related transaction fields.

Important identifiers:

- `upiRequestId`: Newton UPI transaction id, returned by payment-initiation APIs as `gatewayTransactionId`.
- `merchantRequestId`: Merchant order/reference id stored on the transaction or merchant order.
- `vpa`: Optional payer/payee VPA selector when more than one side of a transaction can match the same identifiers.
- `mobileNumber`: Optional customer mobile-number selector. Newton resolves the customer's active VPAs and uses them to choose the matching side.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/statusV2
```

Payloads use the standard Newton server-to-server request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | Header API version used by the response transformer. Newer versions expose additional fields. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Conditional | Required only when the request is made in a configured sub-merchant context. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` for sub-merchant requests. |
| `x-timestamp` | Yes | Request timestamp used for freshness checks and unsigned-payload signature construction. |
| `x-merchant-signature` | Conditional | Required for plaintext/unsigned payload mode. Newton verifies it over merchant ids, timestamp, and raw body. |
| `Authorization` | Conditional | Used by configured authenticated/encrypted flows. |
| `x-forwarded-for` | Conditional | Required when the merchant has IP allowlisting configured. The first IP in the header is checked. |
| `x-request-id` | No | Client request id for tracing. Newton returns it in response headers when available. |
| `x-session-id` | No | Session/correlation id. Defaults to `x-request-id` if omitted. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API path version, for example `v1` depending on the base URL shared during onboarding. |

### Authentication, Signing, and Encryption

The route accepts the standard Newton `EncRequest` envelope:

- JWE encrypted request: object with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed request: object with `payload`, `signature`, and `protected`.
- Plain JSON payload: allowed only for merchant configurations that use the older server-side signature/checksum path.

For encrypted or signed requests, the decrypted/signed payload must contain the business fields documented in this guide. If the request is encrypted or signed, `iat` must be present and must be a valid timestamp. For plaintext requests, Newton validates `x-merchant-signature` using the raw body and `x-timestamp`.

Response format depends on the merchant's configured response strategy:

- `JWS`: Newton signs the response.
- `JWS_AND_JWE`: Newton signs and encrypts the response.
- Other/plain response mode: Newton returns the business response and adds a response signature header.

## Request

### Required Minimum

Lookup by Newton transaction id:

```json
{
  "upiRequestId": "TXN1234567890"
}
```

Lookup by merchant order/reference id:

```json
{
  "merchantRequestId": "ORDER12345"
}
```

Lookup by both identifiers:

```json
{
  "upiRequestId": "TXN1234567890",
  "merchantRequestId": "ORDER12345"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `upiRequestId` | string | Conditional | No default. | Newton UPI transaction id. Required when `merchantRequestId` is omitted. Must be 1 to 35 alphanumeric characters. |
| `merchantRequestId` | string | Conditional | No default. | Merchant order/reference id. Required when `upiRequestId` is omitted. Must be 1 to 35 characters and may contain letters, numbers, hyphen, dot, and underscore. |
| `vpa` | string | No | If both `vpa` and `mobileNumber` are omitted, Newton defaults to the payee-side transaction. | VPA selector used to choose the matching payer or payee side from the transaction records found for the identifiers. |
| `mobileNumber` | string | No | If omitted, no customer mobile lookup is done. | Customer mobile-number selector. Newton resolves the active customer and their VPAs, then chooses the matching payer or payee side. |
| `iat` | string | Conditional | No default. | Issued-at timestamp. Required for JWS/JWE flows by the route authentication layer. |
| `udfParameters` | string | No | No default. | JSON-object string containing merchant-defined metadata. It is validated as JSON text and echoed at the top level of the response. |

At least one of `upiRequestId` or `merchantRequestId` must be present. Supplying both is supported and recommended for reconciliation when both values are available.

### Request Examples

#### Merchant Order Polling

```json
{
  "merchantRequestId": "ORDER12345",
  "udfParameters": "{\"source\":\"checkout-poll\"}"
}
```

#### Transaction Id Polling

```json
{
  "upiRequestId": "TXN1234567890"
}
```

#### Disambiguate By VPA

```json
{
  "upiRequestId": "TXN1234567890",
  "merchantRequestId": "ORDER12345",
  "vpa": "customer@upi"
}
```

#### Disambiguate By Mobile Number

```json
{
  "merchantRequestId": "ORDER12345",
  "mobileNumber": "9876543210"
}
```

## Validation and Lookup Behavior

### Request Validation

Newton validates the decrypted business payload before lookup:

- At least one of `upiRequestId` or `merchantRequestId` is mandatory.
- `upiRequestId` must be alphanumeric and 1 to 35 characters.
- `merchantRequestId` must be 1 to 35 characters and match the allowed merchant-reference format: letters, numbers, hyphen, dot, and underscore.
- `udfParameters`, when present, must be a JSON-object string and must pass the shared UDF text validation.
- `vpa` and `mobileNumber` are not format-validated by this request type, but invalid or unknown values can prevent Newton from selecting a transaction side.

### Transaction Lookup

Newton uses the identifiers as follows:

| Request identifiers | Lookup behavior |
| --- | --- |
| Only `upiRequestId` | Finds all transactions with that UPI request id. |
| Only `merchantRequestId` | Finds the merchant order for that merchant/sub-merchant and then the linked transaction. |
| Both identifiers | First finds transactions by `upiRequestId`, then filters them to the supplied `merchantRequestId`. If no transaction is found by `upiRequestId`, it falls back to the merchant-order lookup using `merchantRequestId`. |

If the identifiers resolve only to a pending register-intent/merchant-validation record and no transaction exists yet, Newton returns the merchant-validation state, such as `REQUEST_PENDING`, `REQUEST_EXPIRED`, `DROPOUT`, or `REQUEST_NOT_FOUND`.

### Payer/Payee Side Selection

The identifiers can resolve to multiple stored records. Newton chooses the response transaction using these rules:

1. If `mobileNumber` is supplied, Newton finds the active customer for that mobile number and merchant context, loads that customer's active VPAs, and matches those VPAs against the payer/payee side.
2. Else if `vpa` is supplied, Newton matches that VPA against the payer/payee side.
3. Else Newton defaults to the payee-side transaction.

For passetto-encrypted or migration-enabled data, Newton compares hashes as well as decrypted VPA values where applicable.

### Status Refresh

If the selected transaction has an associated merchant order, Newton calls the shared transaction status-check helper:

- Terminal transactions are returned from storage without a live refresh.
- Terminal statuses include `SUCCESS`, `FAILURE`, `EXPIRED`, `DECLINED`, `REVERSED`, `UNINITIATED`, `DEEMED_DEBIT`, and, for normal statusV2 checks, `DEEMED`.
- Non-terminal statuses include `PENDING`, `TIMED_OUT`, `COLLECT_PAY_INITIATED`, and `DECLINE_INITIATED`.
- For non-terminal transactions, Newton refreshes from the configured status-check path when the merchant/store configuration enables it and the status-check rate limiter permits it.
- If live status-check is not enabled for the merchant, or the rate limiter returns the request to PSP/storage handling, Newton returns the stored transaction state.
- If the downstream status check times out, Newton returns a service-unavailable transaction error.

When a merchant order is still non-terminal and retry-expiry settings are configured, the helper can also update the merchant order status after the retry window is exhausted.

### V2-Specific Response Behavior

Status V2 returns a normalized transaction-status payload rather than a callback-specific payload:

- Top-level `status` is `SUCCESS` when the status query itself succeeded.
- The payment result is not represented by top-level `status`; use `payload.gatewayResponseCode`, `payload.gatewayResponseMessage`, and the returned transaction metadata.
- Merchant-order transactions return merchant-centric fields such as `merchantRequestId`, payee/payer VPA, TPV information, and merchant/sub-merchant ids.
- Customer-side transactions can include bank details such as `bankCode`, `maskedAccountNumber`, and `bankAccountUniqueId`.
- For merchant-credit transaction types, `payerName` and `payeeName` are returned only when `x-api-version > 1`.
- `subMerchantId` and `subMerchantChannelId` are returned only when `x-api-version > 1`.
- `purpose` is returned only when `x-api-version > 2`.
- `refCategory` is returned only when `x-api-version > 0`.
- `statusSource` is returned only when the environment configuration enables that response field. Its value is `NPCI` when a live status-check happened in the request path, otherwise `PSP`.

## Success Response

The top-level success response has this decrypted business shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "customerResponse": "{}",
    "gatewayReferenceId": "123456789012",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayTransactionId": "TXN1234567890",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12345",
    "payeeVpa": "merchant@upi",
    "payerName": "Customer Name",
    "payerVpa": "customer@upi",
    "type": "MERCHANT_CREDITED_VIA_PAY",
    "transactionTimestamp": "2026-07-02 10:15:30",
    "statusSource": "NPCI"
  },
  "udfParameters": "{\"source\":\"checkout-poll\"}"
}
```

### Pending Response Example

A pending transaction is still returned as a successful status query:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "customerResponse": "{}",
    "expiry": "2026-07-02 10:30:30",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "PENDING",
    "gatewayTransactionId": "TXN1234567890",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12345",
    "payeeVpa": "merchant@upi",
    "payerVpa": "customer@upi",
    "type": "MERCHANT_CREDITED_VIA_COLLECT",
    "transactionTimestamp": "2026-07-02 10:15:30",
    "statusSource": "PSP"
  }
}
```

### Customer-Side Transaction Example

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "25.00",
    "bankAccountUniqueId": "bank-account-unique-id",
    "bankCode": "123456",
    "customerResponse": "{}",
    "gatewayReferenceId": "123456789012",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayTransactionId": "TXN9876543210",
    "maskedAccountNumber": "XXXXXX1234",
    "merchantCustomerId": "CUST123",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER98765",
    "payeeMobileNumber": "9876543210",
    "payeeVpa": "customer@upi",
    "payerVpa": "merchant@upi",
    "type": "CUSTOMER_CREDITED_VIA_PAY",
    "transactionTimestamp": "2026-07-02 10:15:30"
  }
}
```

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API query status. `SUCCESS` means Newton found and returned a transaction status payload. |
| `responseCode` | string | Top-level API response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level API response message. Success value is `SUCCESS`. |
| `payload` | object | Transaction status payload. |
| `udfParameters` | string | Echo of request `udfParameters`, when supplied in the statusV2 request. |

### Payload Field Reference

| Field | Type | Returned when | Description |
| --- | --- | --- | --- |
| `amount` | string | Always | Transaction amount formatted with two decimal places. Merchant-order responses use the merchant-order amount; customer-side responses use the transaction amount. |
| `bankAccountUniqueId` | string | Customer-side account responses only, when available | Unique bank-account identifier for the selected customer-side account. |
| `expiry` | string | Collect transactions, when expiry exists | Collect request expiry timestamp. |
| `bankCode` | string | Customer-side account responses only, when available | Bank code/IIN from the selected account details. |
| `customerResponse` | string | Always | Currently returned as `"{}"`. |
| `gatewayReferenceId` | string | When available/configured | Gateway/NPCI reference id or RRN. For merchant-order responses, this is returned only when the merchant/environment configuration enables RRN in status responses. For customer-side responses, it uses the transaction response id. |
| `gatewayResponseCode` | string | Always | Payment/gateway result code derived from transaction status and stored NPCI response. Common values include `00` for success/deemed merchant-order success, `01` for pending/in-progress statuses, `RB` for deemed customer-side status, `ZA` for declined, and stored NPCI error codes for failures. |
| `gatewayResponseMessage` | string | When available | Human-readable gateway result message derived from NPCI response, status defaults, or error-code mapping. |
| `gatewayTransactionId` | string | Always | Newton UPI transaction id. |
| `maskedAccountNumber` | string | Customer-side account responses only, when available | Masked payer/payee account number for the selected side. |
| `merchantCustomerId` | string | Customer-side transaction, when stored | Merchant customer id from transaction metadata. Merchant-order responses set this field to null/omit it. |
| `merchantId` | string | Always | Merchant id. |
| `merchantChannelId` | string | Always | Merchant channel id. |
| `subMerchantId` | string | Merchant-order sub-merchant requests with `x-api-version > 1` | Sub-merchant id, if a sub-merchant context is active. |
| `subMerchantChannelId` | string | Merchant-order sub-merchant requests with `x-api-version > 1` | Sub-merchant channel id, if a sub-merchant context is active. |
| `merchantRequestId` | string | When stored | Merchant order/reference id. Merchant-order responses use the merchant order value; customer-side responses use transaction metadata. |
| `payeeMcc` | string | When merchant config `mccRefUrlInResponse` is enabled | Payee MCC resolved from the transaction. |
| `payeeMerchantCustomerId` | string | Customer-side responses, when resolvable | Merchant customer id for the payee side. |
| `payeeMobileNumber` | string | Customer-credit customer-side responses, when available | Payee mobile number from transaction payee information. |
| `payeeVpa` | string | When available | Payee VPA. |
| `payerMerchantCustomerId` | string | Customer-side responses, when resolvable | Merchant customer id for the payer side. |
| `payerName` | string | When available; merchant-credit names require `x-api-version > 1` | Payer display name from transaction payer information. |
| `payeeName` | string | When available; merchant-credit names require `x-api-version > 1` | Payee display name from transaction payee information. |
| `payerVpa` | string | When available | Payer VPA. |
| `payerIfsc` | string | Merchant-order responses, when available | Payer IFSC resolved with version-control/account masking rules. |
| `payerAccType` | string | Merchant-order responses, when available | Payer account type. |
| `payerAccBin` | string | Merchant-order responses, when available | Payer account BIN, subject to merchant/version-control rules. |
| `purpose` | string | When available and `x-api-version > 2` | UPI purpose code. |
| `refUrl` | string | When merchant config `mccRefUrlInResponse` is enabled | Transaction reference URL. |
| `refCategory` | string | When stored and `x-api-version > 0` | Transaction reference category. |
| `type` | string | Always | Normalized transaction view. Values include `MERCHANT_CREDITED_VIA_PAY`, `MERCHANT_CREDITED_VIA_COLLECT`, `CUSTOMER_CREDITED_VIA_PAY`, `CUSTOMER_CREDITED_VIA_COLLECT`, `CUSTOMER_DEBITED_VIA_PAY`, and `CUSTOMER_DEBITED_VIA_COLLECT`. |
| `udfParameters` | string | Customer-side or merchant-order payload when stored on the original order/transaction | UDF metadata stored on the original transaction or merchant order. This is separate from the top-level echo of the statusV2 request UDF. |
| `transactionTimestamp` | string | Always | Original transaction creation timestamp. |
| `remarks` | string | Customer-side collect responses, when available | Transaction remarks/note. Merchant-order responses set this field to null/omit it. |
| `payerAccountHash` | string | Merchant-order TPV/KYC responses, when available | Payer account hash derived for TPV/KYC merchants. |
| `tpvValidationStatus` | string | Merchant-order responses, when TPV reference validation failed | TPV validation status derived from transaction metadata. |
| `tpvType` | string | Merchant-order responses, when stored | TPV type, for example full or partial account-hash handling. |
| `statusSource` | string | When enabled by environment configuration | `NPCI` when the request performed a live status check; otherwise `PSP`. |

Fields whose value is `null` are omitted from JSON because the response encoder omits absent optional fields.

## Error Handling

Failure responses use the same response transport as success responses whenever the request reaches Newton's normal API layer. After decryption, failures generally follow this body shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"upiRequestId and merchantRequestId not present.\"",
  "payload": null
}
```

HTTP status can vary by layer. Some business failures are returned with HTTP 200 and a failure body; authentication/IP failures commonly use HTTP 401; bad encrypted payloads or sub-merchant validation failures can use HTTP 400.

### Validation Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Both `upiRequestId` and `merchantRequestId` omitted | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"upiRequestId and merchantRequestId not present.\"","payload":null}` | Send at least one identifier. |
| `upiRequestId` is empty, longer than 35 characters, or not alphanumeric | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"upiRequestId regex match failed\"","payload":null}` | Correct the id. Do not retry unchanged. |
| `merchantRequestId` is empty, longer than 35 characters, or has unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\"","payload":null}` | Correct the merchant reference. Do not retry unchanged. |
| `udfParameters` is not a JSON-object string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\"","payload":null}` | Send a JSON-object string, for example `"{\"key\":\"value\"}"`. |
| Encrypted payload decrypts, but the inner JSON cannot be parsed | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: key \"upiRequestId\" not found","payload":null}` | Fix the encrypted/signed payload contents. |

### Authentication, Access, and Envelope Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Missing merchant headers such as `x-merchant-id`, `x-merchant-channel-id`, or `x-timestamp` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Send all onboarding headers. |
| Plaintext request has missing or invalid `x-merchant-signature` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Recompute signature over the exact raw body and timestamp. |
| JWS signature verification fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Verify `kid`, signing key, canonical payload, and onboarding key material. |
| JWE decryption fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Verify encryption key id, recipient public key, and JWE construction. |
| JWE decrypts to a payload whose source cannot be validated | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Ensure the encrypted object wraps the expected signed payload or permitted merchant payload. |
| API is blocked or not allowed for the merchant/sub-merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED","payload":null}` | Contact Newton to enable `transactionStatusV2` for the merchant configuration. |
| Merchant has IP allowlisting configured and `x-forwarded-for` is missing or not allowlisted | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Send traffic from an allowlisted IP and include the forwarding header as agreed during onboarding. |
| Sub-merchant headers resolve to a sub-merchant that does not belong to the parent merchant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Submerchant does not belong to the specified merchant","payload":null}` | Correct the sub-merchant credentials or use parent merchant headers. |
| Encrypted/signed request is missing `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty","payload":null}` | Include a valid issued-at timestamp in the business payload. |

### Lookup and Business Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| No transaction or merchant-validation record exists for the supplied identifiers | `{"status":"FAILURE","responseCode":"REQUEST_NOT_FOUND","responseMessage":"REQUEST_NOT_FOUND","payload":null}` | Check identifiers and merchant context. Do not create a duplicate payment solely because status is not found. |
| Register-intent/merchant-validation exists but no payment has arrived yet | `{"status":"FAILURE","responseCode":"REQUEST_PENDING","responseMessage":"REQUEST_PENDING","payload":null}` | Continue polling with backoff or wait for callback until the intent expires. |
| Register-intent/merchant-validation expired before a transaction was created | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED","payload":null}` | Stop polling for this attempt and create a new order/intent if the customer should retry. |
| Customer dropped out and merchant-validation stored an error code/message | `{"status":"FAILURE","responseCode":"DROPOUT","responseMessage":"DROPOUT-User dropped out","payload":null}` | Treat the original attempt as not completed. Start a new attempt only if the customer retries. |
| Merchant order exists but no transaction id has been linked yet | `{"status":"FAILURE","responseCode":"UNINITIATED_REQUEST","responseMessage":"UNINITIATED_REQUEST","payload":null}` | The order has not produced a UPI transaction yet. Poll with backoff or wait for callback. |
| Both identifiers are supplied but belong to different transactions | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"incorrect merchantRequestId or upiRequestId","payload":null}` | Fix the identifier pair. |
| `mobileNumber` is supplied but no active customer binding is found | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer","payload":null}` | Use the correct customer mobile number or omit `mobileNumber` and use `vpa`/default payee-side selection. |
| `mobileNumber` resolves to a customer but no active VPA exists | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Vpa not found","payload":null}` | Use `vpa` directly or verify the customer's VPA registration. |
| `vpa` or `mobileNumber` does not match any eligible payer/payee side after lookup | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Recheck the selector. If identifiers are correct, retry without selector to use the default payee-side response. |

### Downstream and Internal Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Live NPCI/downstream status check times out | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"UPI service is not reachable at the moment for transactional apis","payload":null}` | Retry status polling with backoff. Do not initiate a duplicate payment attempt. |
| Live status-check path returns an error response | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Treat the status as unknown and retry later or wait for callback/reconciliation. |
| Recon status-check mode is requested/configured but recon DB is disabled | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Retry later and raise with Newton if persistent. |
| Unexpected storage, decryption, passetto, or response-construction failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Retry with backoff. If repeated for the same identifiers, escalate with `upiRequestId`, `merchantRequestId`, and request id. |

## Retry and Client Handling Guidance

- Always store both `upiRequestId` and `merchantRequestId` when available. Send both for reconciliation, but ensure they belong to the same transaction.
- Do not treat top-level `SUCCESS` as payment success. Inspect `payload.gatewayResponseCode`, `payload.gatewayResponseMessage`, and your configured callback/reconciliation rules.
- For pending codes such as `01`, poll with exponential backoff or wait for callbacks. Avoid tight polling loops because status refresh can be rate-limited.
- For `REQUEST_PENDING` or `UNINITIATED_REQUEST`, the payment may not have reached Newton yet. Continue polling only while the checkout/intent is still valid.
- For `REQUEST_EXPIRED`, `DROPOUT`, validation errors, or identifier mismatch errors, do not retry the same request unchanged.
- For `SERVICE_UNAVAILABLE_*`, timeout, or `INTERNAL_SERVER_ERROR`, retry the status check with backoff. Do not create a new payment attempt until the original order is reconciled.
- When using `vpa` or `mobileNumber`, retry once without the selector if you receive an unexpected selector-related failure and the merchant use case can accept the default payee-side response.
- Include `x-request-id` on every call so Newton support can trace ambiguous status checks.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:433)
- Route handler and authentication call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2529)
- Request type and validation: [src/Newton/Product/Merchant/Transactions/Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:103)
- Shared identifier validation: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:918)
- S2S transformer: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:313)
- Product lookup and side-selection logic: [src/Newton/Product/Merchant/Transactions/StatusV2.hs](../../src/Newton/Product/Merchant/Transactions/StatusV2.hs:31)
- Status refresh helper: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:64)
- Status V2 response construction: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:230)
- API-version response filtering: [src/Newton/Services/Transformer/Generic/Helper.hs](../../src/Newton/Services/Transformer/Generic/Helper.hs:71)
- Response payload type: [src/Newton/Services/Transformer/Generic/Types.hs](../../src/Newton/Services/Transformer/Generic/Types.hs:16)
- S2S response wrapper: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:356)
- Merchant signature, API access, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- JWS/JWE envelope verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Response signing/encryption behavior: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:38)
