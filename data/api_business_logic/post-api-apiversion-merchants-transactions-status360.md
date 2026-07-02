# Status360 API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/status360`

## Overview

Status360 is a merchant server-to-server API for fetching the latest known status and callback-style details for a UPI transaction.

Use this API when your backend needs to reconcile a payment, poll during checkout, investigate a support case, or recover from a missed callback. Newton looks up the transaction by `upiRequestId`, `merchantRequestId`, or both, optionally refreshes the transaction from the upstream status-check flow, and returns a 360-degree payload shaped like the merchant callback for the requested `transactionType`.

Unlike the basic transaction status API, Status360 returns a rich callback payload. The `payload.type` field identifies which callback shape was returned, for example `MERCHANT_CREDITED_VIA_PAY` or `CUSTOMER_DEBITED_FOR_MERCHANT_VIA_PAY`.

## Business Use Case

Status360 helps merchants:

- Check whether a payment, collect request, customer debit, customer credit, voucher debit, UPI Lite top-up, or delegate payment is `SUCCESS`, `FAILURE`, or still `PENDING`.
- Reconcile Newton identifiers with merchant order identifiers.
- Refresh non-terminal transaction status through Newton's status-check flow when allowed by throttling and configuration.
- Retrieve gateway response code, message, reference id, RRN, payer/payee details, TPV details, split details, mandate identifiers, UTR, and settlement metadata where available.
- Confirm that a transaction belongs to the calling merchant or an allowed merchant entity group.
- Receive a response payload that is consistent with the merchant callback contract configured for the same transaction type.

## Integration Flow

1. Store `merchantRequestId` and, when available, `upiRequestId` when creating or initiating a transaction.
2. Call Status360 with `transactionType` and either `upiRequestId`, `merchantRequestId`, or both.
3. Newton validates the encrypted/signed request, merchant access, timestamp, IP whitelist, request fields, and transaction ownership.
4. Newton looks up the transaction. If the transaction is non-terminal and status refresh is allowed, Newton may call the configured upstream status-check path.
5. Newton returns a success response with a callback-shaped `payload`, or a failure response with `status`, `responseCode`, and `responseMessage`.
6. Use `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` as the business status fields. Persist `gatewayReferenceId`/RRN and `gatewayTransactionId` for reconciliation.

Important identifiers:

| Identifier | Meaning |
| --- | --- |
| `upiRequestId` | Newton/UPI transaction id. Returned in responses as `payload.gatewayTransactionId`. |
| `merchantRequestId` | Merchant order/request id. For merchant-order transactions, this is matched against the merchant order record. |
| `originalMerchantRequestId` | Optional original mandate merchant request id. Returned for supported mandate collect flows. |
| `gatewayReferenceId` | Gateway/UPI reference id, often used as RRN/reference for reconciliation. |

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/status360
```

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope. The examples in this guide show decrypted business payloads for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment. Use the version shared during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request content type. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required for sub-merchant/aggregator flows when calling as a sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` for sub-merchant/aggregator flows. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain request envelopes. Signature is verified over merchant headers, timestamp, and raw body using the onboarded merchant API key and signature strategy. |
| `x-timestamp` | Yes | Request timestamp used by signature verification and replay protection. Must be within Newton's accepted timestamp window. |
| `x-forwarded-for` | Conditional | Required when `whitelistedIps` is configured for the merchant. Newton checks the first IP in this header against the configured list. |
| `Authorization` | Conditional | Send only if Newton onboarding instructs your integration to use it. |

### Authentication, Signing, and Encryption

The route accepts the common Newton S2S envelope:

- `JWE` encrypted payload.
- `JWS` signed payload.
- Plain business payload where that mode is enabled for the environment/integration.

For encrypted payloads, Newton decrypts the JWE, expects the decrypted content to be a signed body, verifies the signing key id (`kid`), and then parses the business payload. For signed payloads, Newton verifies the JWS before processing. For plain payloads, the route verifies `x-merchant-signature`.

After payload verification, Newton enforces:

- Merchant and optional sub-merchant resolution from headers.
- Merchant API block list and allow list (`blockedApiNames`, `allowedApiNames`).
- Optional source IP restriction through merchant `whitelistedIps`.
- Request timestamp validity through `x-timestamp`.
- `iat` validity for signed/encrypted business payloads.

## Request

Route request type: `API.EncRequest MTT.TransactionStatus360Request`

Business payload type: `MTT.TransactionStatus360Request`

Type source: [TransactionStatus360Request](../../src/Newton/Product/Merchant/Transactions/Types.hs:21)

### Required Minimum

Query by merchant request id:

```json
{
  "merchantRequestId": "ORDER12345",
  "transactionType": "MERCHANT_CREDITED_VIA_PAY"
}
```

Query by UPI request id:

```json
{
  "upiRequestId": "TXN1234567890",
  "transactionType": "MERCHANT_CREDITED_VIA_PAY"
}
```

Query with both identifiers:

```json
{
  "upiRequestId": "TXN1234567890",
  "merchantRequestId": "ORDER12345",
  "transactionType": "MERCHANT_CREDITED_VIA_PAY",
  "npciStatusCheck": "true"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `upiRequestId` | string | Conditional | No default. | Newton/UPI transaction id. At least one of `upiRequestId` or `merchantRequestId` is required. |
| `merchantRequestId` | string | Conditional | No default. | Merchant order/request id. At least one of `upiRequestId` or `merchantRequestId` is required. |
| `originalMerchantRequestId` | string | No | No default. | Original mandate merchant request id. Validated for non-empty text when supplied; mainly relevant for mandate-linked status checks. |
| `transactionType` | string | Yes | No default. | Callback/transaction category to look up and to shape the response payload. Must map to a supported transaction type for Status360. |
| `checkWithUdir` | string | No | Merchant/configuration logic decides whether UDIR status check is required when omitted. | Boolean string, `true` or `false`. If true and enabled for the merchant/transaction type, Newton may invoke UDIR-aware status-check behavior for non-terminal transactions. |
| `transactionTimestamp` | string | No | If omitted, Newton searches the configured transaction partitions without timestamp narrowing. | IST timestamp used to narrow archived/partitioned transaction lookup. Must parse as a valid Newton timestamp. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used for replay validation on signed/encrypted requests. Required by middleware for non-plain envelopes. |
| `udfParameters` | string | No | No default. Echoed at response envelope level when supplied. | Merchant-defined metadata as a JSON object encoded as a string, for example `"{\"source\":\"recon\"}"`. |
| `npciStatusCheck` | string | No | Defaults to `true`. | Boolean string, `true` or `false`. When `false`, Newton serves the current database status instead of attempting an upstream NPCI/status-check refresh. |

### Supported `transactionType` Values

Status360 accepts the common Newton callback type enum, but only the following types are returned by this route. Other values can parse successfully and still fail at the Status360 response-construction stage.

| `transactionType` | Returned payload shape | Typical use |
| --- | --- | --- |
| `MERCHANT_CREDITED_VIA_PAY` | Incoming money merchant pay callback | Merchant received a pay transaction. |
| `MERCHANT_CREDITED_VIA_COLLECT` | Incoming money merchant collect status callback | Merchant received a collect transaction or collect status update. |
| `MERCHANT_DEBITED_FOR_VOUCHER` | Outgoing money merchant callback | Merchant was debited for voucher/eRupi flow. |
| `CUSTOMER_DEBITED_FOR_MERCHANT_VIA_PAY` | Outgoing money customer callback | Customer paid a merchant through pay. |
| `CUSTOMER_DEBITED_FOR_MERCHANT_VIA_COLLECT` | Outgoing money customer callback | Customer paid a merchant through collect. |
| `CUSTOMER_DEBITED_VIA_PAY` | Outgoing money customer callback | Customer outgoing pay transaction. |
| `CUSTOMER_DEBITED_VIA_COLLECT` | Outgoing money customer callback | Customer outgoing collect transaction. |
| `CUSTOMER_CREDITED_VIA_PAY` | Incoming money customer pay callback | Customer incoming pay/credit transaction. |
| `CUSTOMER_CREDITED_VIA_COLLECT` | Incoming money customer collect status callback | Customer incoming collect credit/status. |
| `COLLECT_REQUEST_SENT` | Outgoing collect customer callback | Collect request status before or after approval/decline. |
| `UPI_LITE_TOPUP` | Outgoing money customer callback | UPI Lite top-up. |
| `UPI_LITE_DEREGISTRATION` | Outgoing money customer callback | UPI Lite deregistration. |
| `CUSTOMER_DEBITED_FOR_MERCHANT_VIA_DELEGATE` | Outgoing money customer callback | Delegate payment to merchant. |
| `CUSTOMER_DEBITED_VIA_DELEGATE` | Outgoing money customer callback | Delegate customer debit. |
| `DELEGATEE_DEBITED_FOR_MERCHANT_VIA_PAY` | Outgoing money customer callback | Delegatee paid merchant. |
| `DELEGATEE_DEBITED_VIA_PAY` | Outgoing money customer callback | Delegatee outgoing pay. |

### Validation Rules

- `transactionType` is required by the JSON type. Missing or invalid enum values fail request parsing before business logic.
- At least one of `upiRequestId` or `merchantRequestId` is required.
- If supplied, `upiRequestId` must pass Newton UPI request id validation.
- If supplied, `merchantRequestId` must pass Newton merchant request id validation.
- If both `upiRequestId` and `merchantRequestId` are supplied, both are validated and later cross-checked against the located transaction/order.
- `originalMerchantRequestId` must be non-empty when supplied.
- `checkWithUdir` and `npciStatusCheck` must be boolean strings: `true` or `false`, case-insensitive.
- `transactionTimestamp` must parse as a valid IST timestamp.
- `udfParameters` must be a JSON object encoded as text and must not contain characters rejected by the common UDF validator.
- For signed/encrypted requests, `iat` must be present and timestamp-valid.

### Defaults and Omitted Field Behavior

- `npciStatusCheck` defaults to `true`.
- `checkWithUdir` does not have a literal request default. Newton combines the request value with merchant/transaction-type configuration to decide whether UDIR status-check behavior is enabled.
- `transactionTimestamp` has no default. When omitted, lookup uses the configured transaction partition search behavior.
- `udfParameters`, `originalMerchantRequestId`, and `iat` are omitted from JSON when absent.

## Lookup and Status-Refresh Behavior

Newton first validates the request body and derives the internal transaction type, self-initiated flag, and payer/payee role from `transactionType`. If this mapping fails, the response is `BAD_REQUEST` with message `Invalid transactionType`.

Lookup behavior depends on the identifiers supplied:

| Request identifiers | Lookup behavior |
| --- | --- |
| `upiRequestId` only | Newton searches for a transaction matching UPI request id, derived transaction type, role, and self-initiated flag. For `MERCHANT_CREDITED_VIA_PAY`, if no transaction is found, Newton also checks merchant validation records. |
| `merchantRequestId` only | Newton looks up the merchant order/transaction by merchant request id for the resolved merchant and derived transaction type. |
| Both identifiers | Newton first searches by `upiRequestId`. If a merchant order is found, its order id must match `merchantRequestId`; otherwise the request fails with `incorrect merchantRequestId or upiRequestId`. If the transaction is not found by UPI request id, Newton falls back to the merchant request id lookup constrained by the UPI request id. |

After lookup, Newton verifies that the transaction belongs to the calling merchant. A transaction is allowed when:

- The transaction has no merchant id stored, or
- The transaction merchant id matches the calling merchant, or
- The transaction merchant belongs to the same merchant entity group as the caller.

If ownership validation fails, Newton returns `Restricted Transaction`.

### Status Refresh

If the located transaction is terminal, Newton returns the stored transaction without an upstream status check.

If the transaction is non-terminal:

- When `npciStatusCheck` is omitted or `"true"`, Newton may run the configured status-check path, subject to rate limits/backoff and merchant configuration.
- When `npciStatusCheck` is `"false"`, Newton returns the current database status and marks the internal rate-limit event as merchant-limited behavior.
- If upstream status-check is throttled or configured to use PSP passthrough, the response may still reflect the currently stored transaction.
- If upstream status-check times out, Newton returns a service-unavailable failure such as `SERVICE_UNAVAILABLE_NPCI_NA`.
- If upstream status-check returns an unexpected error response, Newton returns `INTERNAL_SERVER_ERROR`.

For successful merchant orders, Newton may fetch recon/settlement details before responding when the merchant is enabled for recon details and order split/UTR information is incomplete. This can populate fields such as `utrNumber`, `settlementDate`, and `splitSettlementDetails`.

## Request Examples

### Merchant Pay Status

```json
{
  "merchantRequestId": "ORDER12345",
  "transactionType": "MERCHANT_CREDITED_VIA_PAY",
  "npciStatusCheck": "true",
  "udfParameters": "{\"source\":\"checkout-poll\"}"
}
```

### Merchant Collect Status With Timestamp Narrowing

```json
{
  "upiRequestId": "TXN1234567890",
  "merchantRequestId": "ORDER12346",
  "transactionType": "MERCHANT_CREDITED_VIA_COLLECT",
  "transactionTimestamp": "2026-07-02T10:15:30+05:30",
  "checkWithUdir": "false"
}
```

### Serve Stored Status Without Upstream NPCI Refresh

```json
{
  "upiRequestId": "TXN1234567890",
  "transactionType": "CUSTOMER_DEBITED_FOR_MERCHANT_VIA_PAY",
  "npciStatusCheck": "false"
}
```

## Success Response

Route response type: `RespHeaders (API.EncResponse TfS2S.TransactionStatus360Response)`

Business response type: `TfS2S.TransactionStatus360Response`

Type source: [TransactionStatus360Response](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:217)

The decrypted business response has this envelope:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "customResponse": "{}",
    "gatewayReferenceId": "326512345678",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "TXN1234567890",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "ORDER12345",
    "payeeMcc": "5411",
    "payeeVpa": "merchant@upi",
    "payerVpa": "customer@upi",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "transactionTimestamp": "2026-07-02T10:15:30+05:30",
    "type": "MERCHANT_CREDITED_VIA_PAY"
  },
  "udfParameters": "{\"source\":\"checkout-poll\"}"
}
```

`payload` is an untagged callback payload. Optional fields with `null` values are omitted from JSON. The exact field set can also be filtered by the merchant callback query configured for the transaction type; if no custom query is configured, Newton uses the default Status360 callback field selection for that type.

### Response Envelope Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful Status360 calls. Transaction business status is inside `payload.gatewayResponseStatus`. |
| `responseCode` | string | `SUCCESS` for successful Status360 calls. |
| `responseMessage` | string | `SUCCESS` for successful Status360 calls. |
| `payload` | object | Callback-shaped transaction status payload. Shape depends on `transactionType`. |
| `udfParameters` | string | Echoes request `udfParameters` when supplied. |

### Common Payload Fields

These fields appear across most Status360 payload shapes when available and selected by callback configuration.

| Field | Type | Description |
| --- | --- | --- |
| `type` | string | Callback type returned for the transaction. Use this to interpret the payload shape. |
| `amount` | string | Transaction amount. |
| `customResponse` | string | Current implementation returns `{}` for these callback-shaped payloads. |
| `gatewayTransactionId` | string | Newton/UPI transaction id, usually the same as `upiRequestId`. |
| `gatewayReferenceId` | string | Gateway/UPI reference id/RRN. |
| `gatewayResponseCode` | string | Gateway response code after stored status or status refresh. |
| `gatewayResponseMessage` | string | Gateway response message. |
| `gatewayResponseStatus` | string | Business status such as `SUCCESS`, `FAILURE`, or `PENDING`, when included for the flow/configuration. |
| `gatewayPayeeResponseCode` | string | Payee-side response code, when available and enabled. |
| `gatewayPayerResponseCode` | string | Payer-side response code, when available and enabled. |
| `gatewayPayeeReversalResponseCode` | string | Payee reversal response code, when available and enabled. |
| `gatewayPayerReversalResponseCode` | string | Payer reversal response code, when available and enabled. |
| `merchantId` | string | Merchant id. |
| `merchantChannelId` | string | Merchant channel id. |
| `subMerchantId` | string | Sub-merchant id for aggregator/sub-merchant flows when returned. |
| `subMerchantChannelId` | string | Sub-merchant channel id when returned. |
| `merchantRequestId` | string | Merchant request/order id when known. |
| `merchantCustomerId` | string | Merchant customer id for customer-side flows when known. |
| `payerVpa` | string | Payer VPA. May be hidden for some P2M SDK parent/sub-merchant configurations. |
| `payerName` | string | Payer display name when available and allowed by merchant configuration. |
| `payerMobileNumber` | string | Payer mobile number for customer-side flows when available. |
| `payerMerchantCustomerId` | string | Merchant customer id associated with the payer when available. |
| `payeeVpa` | string | Payee VPA. |
| `payeeName` | string | Payee display name when available. |
| `payeeMcc` | string | Payee MCC. |
| `payeeMobileNumber` | string | Payee mobile number when available. |
| `payeeMerchantCustomerId` | string | Merchant customer id associated with the payee when available. |
| `bankCode` | string | Bank code for customer account details when returned. |
| `bankAccountUniqueId` | string | Bank account unique id/account hash when returned. |
| `maskedAccountNumber` | string | Masked payer/payee account number for customer-side flows when returned. |
| `payerAccountNumber` | string | Encrypted payer account number for eligible merchant-credit flows. |
| `payerMaskedAccNumber` | string | Masked payer account number for eligible merchant-credit flows. |
| `payerAccountHash` | string | Payer account hash for TPV/KYC merchant flows. |
| `payerAccBin` | string | Payer account BIN when available. |
| `payerAccRefId` | string | Payer account reference id when available. |
| `payerIfsc` | string | Payer IFSC when allowed by configuration. |
| `payerAcType` / `payerActype` / `payerAccType` | string | Account type fields. Field spelling depends on merchant/version configuration. |
| `payeeIfsc` | string | Payee IFSC for outgoing customer flows when available. |
| `payeeAcType` | string | Payee account type for outgoing customer flows when available. |
| `transactionTimestamp` | string | Transaction timestamp selected by merchant/version configuration. |
| `refUrl` | string | Reference URL from the transaction/order. |
| `refId` | string | UPI transaction reference id (`tr`/`refId`) when present. |
| `remarks` | string | Transaction remarks/note when returned. |
| `riskScore` | string | Risk score when configured. |
| `udfParameters` | string | UDF metadata stored with the transaction/order. This is separate from the response envelope `udfParameters`. |
| `tpvValidationStatus` | string | TPV validation status when TPV was applied. |
| `tpvType` | string | TPV type such as full or partial, when present. |
| `splitDetails` | array | Split/convenience fee details filtered for merchant response. |
| `splitSettlementDetails` | object | Split settlement/UTR details when recon details are available. |
| `utrNumber` | string | UTR from recon/settlement details when available. |
| `settlementDate` | string | Settlement date from recon/settlement details when available. |
| `orgMandateId` | string | Original mandate id for mandate-linked transactions. |
| `originalMerchantRequestId` | string | Original mandate merchant request id for supported collect/mandate flows. |
| `umn` | string | UPI mandate number when relevant. |
| `seqNumber` | string | Mandate execution sequence number when relevant. |
| `collectType` | string | Collect type for multibank/customer-side flows when returned. |
| `requestType` | string | Request type for customer-side flows when returned. |
| `expiry` / `expiryTimestamp` | string | Collect or delegate payment expiry when relevant. |
| `autoUpdateNote` | string | UDIR auto-update note when UDIR behavior is enabled and available. |
| `throttlingStatus` | string | Status-check throttling/source indicator included for supported callback versions. |

### Payload Shape by Transaction Type

| `payload.type` | Important fields in addition to common fields |
| --- | --- |
| `MERCHANT_CREDITED_VIA_PAY` | `merchantRequestId`, `payerAccountHash`, `payerAccountNumber`, `payerMaskedAccNumber`, `payerAccBin`, `payerAccRefId`, `payerIfsc`, `tpvValidationStatus`, `tpvType`, `splitDetails`, `utrNumber`, `settlementDate`, `splitSettlementDetails`, `mdrAmount`, `gstAmount`, `netSettlementAmount`, `merchantType`. |
| `MERCHANT_CREDITED_VIA_COLLECT` | `merchantRequestId`, `originalMerchantRequestId`, `payerAccountHash`, `payerAccountNumber`, `payerMaskedAccNumber`, `tpvValidationStatus`, `tpvType`, `mandateIntentPayUrl`, `currentBlockedAmount`, `utrNumber`, `settlementDate`, `splitSettlementDetails`. |
| `CUSTOMER_DEBITED_FOR_MERCHANT_VIA_PAY`, `CUSTOMER_DEBITED_FOR_MERCHANT_VIA_COLLECT`, `CUSTOMER_DEBITED_VIA_PAY`, `CUSTOMER_DEBITED_VIA_COLLECT`, delegate debit types, UPI Lite types | `merchantCustomerId`, `payerMobileNumber`, `payeeName`, `payeeIfsc`, `payeeAcType`, `collectType`, `requestType`, `orgMandateId`, `seqNumber`, `splitDetails`, `refId`, `lrn`, `purpose`, international fields such as `baseAmount`, `baseCurr`, `fx`, `mkup`, and delegate fields such as `delegateeVpa`, `delegatorVpa`, `linkType`, `linkedUpiRequestId`. |
| `CUSTOMER_CREDITED_VIA_PAY` | `merchantCustomerId`, `payeeMobileNumber`, `payeeMerchantCustomerId`, `payerName`, `payerIfsc`, `payerMcc`, `refId`, `lrn`, `payeeUpiNumber`, `remarks`. |
| `CUSTOMER_CREDITED_VIA_COLLECT` | `merchantCustomerId`, `merchantRequestId`, `payeeMobileNumber`, `payeeMerchantCustomerId`, `payerName`, `payerIfsc`, `expiry`, `purpose`, `remarks`. |
| `COLLECT_REQUEST_SENT` | `merchantCustomerId`, `merchantRequestId`, `expiry`, `payerName`, `payeeMobileNumber`, `payeeMerchantCustomerId`, `remarks`, `riskScore`. |
| `MERCHANT_DEBITED_FOR_VOUCHER` | `merchantRequestId`, `orgMandateId`, `seqNumber`, `umn`, `voucherBalance`, `expiry`, `payeeName`, `payerName`. |

### Success Example: Merchant Pay

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "customResponse": "{}",
    "gatewayReferenceId": "326512345678",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "TXN1234567890",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "ORDER12345",
    "payeeMcc": "5411",
    "payeeVpa": "merchant@upi",
    "payerName": "Customer Name",
    "payerVpa": "customer@upi",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "transactionTimestamp": "2026-07-02T10:15:30+05:30",
    "type": "MERCHANT_CREDITED_VIA_PAY",
    "udfParameters": "{\"cartId\":\"CART123\"}"
  }
}
```

### Success Example: Pending Collect Request

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "250.00",
    "customResponse": "{}",
    "expiry": "2026-07-02T10:30:30+05:30",
    "gatewayReferenceId": "326512345679",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "PENDING",
    "gatewayResponseStatus": "PENDING",
    "gatewayTransactionId": "TXN1234567891",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST123",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "ORDER12346",
    "payeeMcc": "5411",
    "payeeVpa": "merchant@upi",
    "payerName": "Customer Name",
    "payerVpa": "customer@upi",
    "transactionTimestamp": "2026-07-02T10:15:30+05:30",
    "type": "COLLECT_REQUEST_SENT"
  }
}
```

## Failure Responses

Failure responses use the standard Newton error body. Depending on where the failure occurs, the response can be inside the encrypted/signed envelope or can be returned before payload protection is possible, such as malformed encryption or authentication failures.

Clients should always read:

- HTTP status for transport/auth class.
- `status`, `responseCode`, and `responseMessage` from the decrypted body when available.
- `payload` only on successful business responses.

### Validation Failure: Missing Both Identifiers

At least one of `upiRequestId` or `merchantRequestId` is required.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "upiRequestId and merchantRequestId not present.",
  "payload": null
}
```

The exact validation serialization may include the validator category, but the client action is the same: send one or both identifiers.

### Validation Failure: Invalid Boolean String

`checkWithUdir` and `npciStatusCheck` must be boolean strings.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Parameter is not true or false",
  "payload": null
}
```

### Validation Failure: Invalid Timestamp

`transactionTimestamp` and signed/encrypted request `iat` must be valid timestamps.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "timestamp value not valid",
  "payload": null
}
```

### Validation Failure: Invalid `transactionType`

If Newton cannot map the supplied transaction type to an internal transaction type/role:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid transactionType",
  "payload": null
}
```

If the value maps to the broad enum but is not one of the Status360-supported response shapes, Newton may return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Use only the supported Status360 `transactionType` values listed above.

### Lookup Failure: Transaction Not Found

When Newton cannot find the requested transaction by the supplied identifiers:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND",
  "payload": null
}
```

Client handling:

- Verify `transactionType` matches the original flow.
- Prefer sending both `upiRequestId` and `merchantRequestId` when available.
- If the transaction was just initiated, retry with backoff because asynchronous writes/callbacks may still be in progress.

### Lookup Failure: Identifier Mismatch

When both identifiers are supplied but the located transaction's merchant order does not match the supplied merchant request id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "incorrect merchantRequestId or upiRequestId",
  "payload": null
}
```

Do not retry unchanged. Fix the identifier pair.

### Missing Identifier Fallback Failure

If the request reaches the explicit business guard without either identifier:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "upiRequestid or merchantRequestId is mandatory for status360",
  "payload": null
}
```

### Ownership Failure: Restricted Transaction

If the transaction belongs to another merchant and is not in an allowed merchant entity group:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Restricted Transaction",
  "payload": null
}
```

Do not retry unchanged. Use credentials for the merchant that owns the transaction, or confirm merchant entity-group configuration with Newton.

### Authentication, Signature, and Encryption Failures

Missing merchant headers, missing/invalid `x-timestamp`, missing/invalid `x-merchant-signature`, invalid JWS signature, JWE decryption failure, missing/invalid `kid`, API allow-list failure, API block-list failure, and IP whitelist failure are rejected before business logic.

Common decrypted/plain body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

If the API is not enabled or explicitly blocked for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

Client handling:

- Do not retry rapidly. Fix headers, key id, signature generation, clock skew, encryption, API enablement, or IP allow-listing.
- Ensure `x-forwarded-for` contains the merchant source IP as the first comma-separated value when IP whitelisting is configured.

### Encrypted Payload Parse Failure

If JWE decrypts but the decrypted payload cannot be parsed as the expected signed/body JSON:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"transactionType\" not found",
  "payload": null
}
```

Fix envelope construction before retrying.

### Upstream NPCI/Status-Check Timeout

If Newton attempts an upstream status refresh and the upstream service times out:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "UPI service is not reachable at the moment for transactional apis",
  "payload": null
}
```

Client handling:

- Retry with exponential backoff.
- If the status is needed only for display and not final reconciliation, retry later or call with `"npciStatusCheck": "false"` to read Newton's current stored status.

### Upstream/Downstream Unexpected Failure

If upstream status-check returns an unexpected error, recon details fail unexpectedly, required transaction fields are missing, or internal processing fails:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling:

- Retry with backoff for transient failures.
- If repeated for the same transaction, share `upiRequestId`, `merchantRequestId`, `transactionType`, timestamp, and Newton request id/log reference with Newton support.

## Retry and Client Handling Guidance

- Treat the API call result separately from the transaction result. `status: "SUCCESS"` means the Status360 call succeeded; the transaction result is in `payload.gatewayResponseStatus`.
- For `PENDING` or missing terminal status, retry with exponential backoff. Avoid tight polling; Newton applies status-check throttling/backoff.
- For recently initiated transactions, allow a short delay before the first Status360 call because transaction/order persistence and upstream callbacks may be asynchronous.
- For reconciliation jobs, prefer sending `transactionTimestamp` when available to narrow archived/partitioned lookup.
- Use `"npciStatusCheck": "false"` when you only need Newton's stored status and want to avoid an upstream refresh.
- Use `"npciStatusCheck": "true"` or omit the field when you want Newton to refresh non-terminal status if allowed.
- Do not retry unchanged for validation errors, identifier mismatch, ownership failure, API not enabled, signature failure, or IP whitelist failure.
- Persist `gatewayTransactionId`, `gatewayReferenceId`, `gatewayResponseCode`, `gatewayResponseMessage`, `gatewayResponseStatus`, and `transactionTimestamp` from every successful response.

## Source References

- API route declaration: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:439)
- Route handler and S2S auth call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2584)
- Encrypted/signed request envelope: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API/IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request type and validation: [src/Newton/Product/Merchant/Transactions/Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:21)
- Common validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:918)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:321)
- Response envelope transformer: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:366)
- Response envelope type: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:217)
- Status360 business logic: [src/Newton/Product/Merchant/Transactions/Status360.hs](../../src/Newton/Product/Merchant/Transactions/Status360.hs:38)
- Status refresh helper: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:64)
- Status360 payload selection: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:167)
- Generic callback payload construction: [src/Newton/Utils/Transformers/Transformer8.hs](../../src/Newton/Utils/Transformers/Transformer8.hs:123)
- Status360 payload union type: [src/Newton/Services/Transformer/Generic/Types.hs](../../src/Newton/Services/Transformer/Generic/Types.hs:100)
- Callback payload field types: [src/Newton/External/MerchantCallback/Newton/Types.hs](../../src/Newton/External/MerchantCallback/Newton/Types.hs:404)
- Callback field filtering/default queries: [src/Newton/External/MerchantCallback/Newton/GqlHelper.hs](../../src/Newton/External/MerchantCallback/Newton/GqlHelper.hs:282)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:34)
