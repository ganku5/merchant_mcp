# Bank Status Check API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/bankStatusCheck`

## Overview

Bank Status Check is a merchant server-to-server API used to fetch the latest bank-side status for an existing incoming merchant transaction.

The merchant calls this API with either Newton's UPI transaction id (`upiRequestId`), the merchant order/reference id (`merchantRequestId`), or both, plus the callback/transaction category being checked. Newton locates the matching transaction, performs the same transaction-status refresh path used by status polling when the transaction is not already terminal, and returns a callback-shaped payload enriched with payer bank/account/device details when available.

Use this API when a backend support, reconciliation, or polling workflow needs to verify the status of an incoming merchant credit transaction with bank/NPCI context.

## Business Use Case

Bank Status Check helps merchants:

- Reconcile incoming pay or collect transactions against bank/NPCI status.
- Poll a pending transaction without waiting for a callback retry.
- Validate whether a registered or initiated request is still pending, expired, dropped out, not found, or completed.
- Retrieve callback-equivalent transaction details for support and operations teams.
- Retrieve payer bank/account metadata from CBS or payer transaction records when Newton has it.

Supported transaction categories are:

| `transactionType` | Use when checking |
| --- | --- |
| `MERCHANT_CREDITED_VIA_PAY` | Incoming merchant credit through a pay/intent/QR flow. |
| `MERCHANT_CREDITED_VIA_COLLECT` | Incoming merchant credit through a collect flow. |

## Integration Flow

1. Merchant creates or receives a transaction through an existing Newton payment flow.
2. Merchant stores `upiRequestId`/`gatewayTransactionId` and `merchantRequestId`.
3. If status verification is needed, merchant calls `bankStatusCheck` with the identifier and the matching `transactionType`.
4. Newton verifies the encrypted/signed S2S request, merchant access, timestamp, and IP restrictions.
5. Newton validates the business payload and locates the transaction or pending validation request.
6. If the transaction is not terminal and status-check throttling permits it, Newton refreshes the status through the configured downstream status path.
7. Merchant decrypts the response and uses `status`, `responseCode`, `responseMessage`, and `payload.gatewayResponseCode`/`payload.gatewayResponseMessage` for handling and reconciliation.

Important identifiers:

- `upiRequestId`: Newton UPI transaction id. The success response returns the same identifier as `payload.gatewayTransactionId`.
- `merchantRequestId`: Merchant order/reference id associated with the transaction.
- `transactionType`: Determines which transaction shape Newton searches for and which response payload is returned.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/bankStatusCheck
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id issued by Newton. Required by S2S signature verification. |
| `x-merchant-channel-id` | Merchant channel id issued by Newton. Required by S2S signature verification. |
| `x-merchant-signature` | Request signature, unless the request is sent through an encrypted/signed envelope mode that bypasses raw signature validation. |
| `x-timestamp` | Current request timestamp. Validated for replay protection. |
| `x-forwarded-for` | Required when the merchant has `whitelistedIps` configured. Newton checks the first IP in this header. |
| `x-api-version` | Use the version shared during onboarding. This API does not add version-specific request fields in the inspected code. |
| `Authorization` | Include when shared during onboarding for your S2S envelope mode. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API namespace version in the route path, for example `v1` or the value shared during onboarding. |

### Authentication, Signing, and Encryption

The route accepts Newton's standard S2S envelope:

```json
{
  "protected": "<jwe-protected-header>",
  "encryptedKey": "<encrypted-key>",
  "iv": "<initialization-vector>",
  "cipherText": "<encrypted-business-payload>",
  "tag": "<authentication-tag>"
}
```

Signed payload envelopes use:

```json
{
  "payload": "<base64-or-encoded-payload>",
  "signature": "<signature>",
  "protected": "<protected-header>"
}
```

For plain unsigned payloads in lower environments, Newton verifies `x-merchant-signature` over merchant headers, `x-timestamp`, and the raw request body. Production integrations should follow the encrypted/signing process and keys shared during onboarding.

The decrypted business payload must include `iat` when sent in an encrypted or signed envelope. Newton validates `iat` before signature verification. Newton also validates `x-timestamp` unless a development/UAT checksum bypass path is active.

Merchant access checks happen before product logic:

- Merchant id and channel id must resolve to an active merchant configuration.
- The API must not be listed in the merchant's blocked API list.
- If the merchant has an allowed API list, `bankStatusCheck` must be present.
- If `whitelistedIps` is configured, the first IP in `x-forwarded-for` must be in that list.

## Request

### Minimum Request By UPI Transaction Id

```json
{
  "upiRequestId": "UPI123456789012345",
  "transactionType": "MERCHANT_CREDITED_VIA_PAY",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Minimum Request By Merchant Reference

```json
{
  "merchantRequestId": "ORDER12345",
  "transactionType": "MERCHANT_CREDITED_VIA_COLLECT",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Request With Both Identifiers

```json
{
  "upiRequestId": "UPI123456789012345",
  "merchantRequestId": "ORDER12345",
  "transactionType": "MERCHANT_CREDITED_VIA_PAY",
  "transactionTimestamp": "2026-07-02T10:10:00+05:30",
  "iat": "2026-07-02T10:15:30+05:30",
  "udfParameters": "{\"caseId\":\"SUPPORT-1001\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `upiRequestId` | string | Conditional | No default. | Newton UPI transaction id. Required when `merchantRequestId` is omitted. Length must be 1 to 35 characters. Allowed characters: letters and numbers only. |
| `merchantRequestId` | string | Conditional | No default. | Merchant order/reference id. Required when `upiRequestId` is omitted. Length must be 1 to 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `transactionType` | string | Yes | No default. | Transaction category to check. Must be `MERCHANT_CREDITED_VIA_PAY` or `MERCHANT_CREDITED_VIA_COLLECT`. |
| `transactionTimestamp` | string | No | If omitted, Newton searches recent transaction partitions according to server configuration. | Optional IST timestamp used to narrow transaction lookup to the current, previous, or next partition for that date. Must parse as a Newton timestamp, for example `2026-07-02T10:10:00+05:30`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp. Required for encrypted/signed envelopes because Newton validates it before signature verification. Not validated for the plain unsigned payload branch. |
| `udfParameters` | string | No | No default. Echoed at top level in a success response when supplied. | JSON-object string for merchant-defined metadata. Must parse as a JSON object and must not contain characters rejected by validation: `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### Defaults and Omitted Field Behavior

This API does not create a new transaction and does not generate identifiers.

- Send at least one of `upiRequestId` or `merchantRequestId`.
- When both identifiers are supplied, Newton verifies that they refer to the same transaction/order. A mismatch is rejected.
- `transactionTimestamp` is optional, but sending it can improve lookup precision for older transactions or partitioned storage.
- `udfParameters` is not added or inferred when omitted.

## Validation Rules

Newton validates the decrypted request before product logic:

- At least one of `upiRequestId` or `merchantRequestId` must be present.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `merchantRequestId` must be 1 to 35 characters and match the merchant request id format: letters, numbers, hyphen, dot, underscore.
- `transactionType` must be exactly `MERCHANT_CREDITED_VIA_PAY` or `MERCHANT_CREDITED_VIA_COLLECT`.
- `transactionTimestamp`, when supplied, must parse as a valid local timestamp.
- `udfParameters`, when supplied, must be a JSON-object string and must pass the configured character filter.
- Encrypted or signed requests must include a valid `iat`.
- Merchant signature, timestamp, API access, and IP whitelist checks must pass before the business route runs.

## Response

On success, Newton returns:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "...": "..."
  },
  "udfParameters": "{\"caseId\":\"SUPPORT-1001\"}"
}
```

The `payload` shape depends on `transactionType`.

### Success Response: `MERCHANT_CREDITED_VIA_PAY`

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "customResponse": "SUCCESS",
    "gatewayReferenceId": "321654987012",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "UPI123456789012345",
    "merchantChannelId": "MERCHANTAPP",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "ORDER12345",
    "payeeMcc": "5411",
    "payeeVpa": "merchant@bank",
    "payerAccountNumber": "1234567890",
    "payerActype": "SAVINGS",
    "payerIfsc": "HDFC0000001",
    "payerMcc": "0000",
    "payerName": "Customer Name",
    "payerVpa": "customer@upi",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "transactionTimestamp": "2026-07-02T10:12:15+05:30",
    "type": "MERCHANT_CREDITED_VIA_PAY"
  },
  "udfParameters": "{\"caseId\":\"SUPPORT-1001\"}"
}
```

### Success Response: `MERCHANT_CREDITED_VIA_COLLECT`

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "customResponse": "SUCCESS",
    "gatewayReferenceId": "321654987013",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "UPI123456789012346",
    "merchantChannelId": "MERCHANTAPP",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "ORDER12346",
    "payeeMcc": "5411",
    "payeeVpa": "merchant@bank",
    "payerAccountNumber": "1234567890",
    "payerActype": "SAVINGS",
    "payerIfsc": "HDFC0000001",
    "payerMcc": "0000",
    "payerName": "Customer Name",
    "payerVpa": "customer@upi",
    "refUrl": "https://merchant.example/orders/ORDER12346",
    "transactionTimestamp": "2026-07-02T10:12:15+05:30",
    "type": "MERCHANT_CREDITED_VIA_COLLECT"
  }
}
```

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API result. Success value is `SUCCESS`. |
| `responseCode` | string | Top-level Newton response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level response message. Success value is `SUCCESS`. |
| `payload` | object | Transaction status payload. Its field set depends on `transactionType`. |
| `udfParameters` | string | Echo of request `udfParameters`, when supplied. |

### Pay Payload Field Reference

Returned for `transactionType = MERCHANT_CREDITED_VIA_PAY`.

| Field | Type | Description |
| --- | --- | --- |
| `amount` | string | Transaction amount. |
| `autoUpdateNote` | string | UDIR/auto-update note when present. |
| `customResponse` | string | Merchant callback custom response/status text. |
| `deviceTags` | JSON value | Payer device tags from CBS payer information when available. |
| `gatewayPayeeResponseCode` | string | Gateway/NPCI payee response code when available. |
| `gatewayPayeeReversalResponseCode` | string | Payee reversal response code when available. |
| `gatewayPayerResponseCode` | string | Gateway/NPCI payer response code when available. |
| `gatewayPayerResponseMessage` | string | Gateway/NPCI payer response message when available. |
| `gatewayPayerReversalResponseCode` | string | Payer reversal response code when available. |
| `gatewayReferenceId` | string | Gateway/NPCI reference id/RRN. |
| `gatewayResponseCode` | string | Gateway/NPCI transaction response code. Use with `gatewayResponseMessage` for reconciliation. |
| `gatewayResponseMessage` | string | Gateway/NPCI transaction response message. |
| `gatewayResponseStatus` | string | Gateway response status when available. |
| `gatewayTransactionId` | string | Newton UPI transaction id. |
| `merchantChannelId` | string | Merchant channel id. |
| `merchantId` | string | Merchant id. |
| `merchantRequestId` | string | Merchant order/reference id. |
| `payeeMcc` | string | Payee MCC. |
| `payeeVpa` | string | Payee/merchant VPA. |
| `payerAccBin` | string | Payer account BIN when available. |
| `payerAccRefId` | string | Payer account reference id when available. |
| `payerAccountHash` | string | Payer account hash when available. |
| `payerAccountNumber` | string | Payer account number from CBS or payer transaction details when available. |
| `payerAcType` | string | Payer account type from callback data when available. |
| `payerActype` | string | Payer account type added from CBS or payer transaction details when available. |
| `payerIfsc` | string | Payer IFSC from CBS or payer transaction details when available. |
| `payerMcc` | string | Payer MCC from CBS/payer details when available. |
| `payerMerchantCustomerId` | string | Merchant customer id for payer when available. |
| `payerName` | string | Payer display name. |
| `payerVpa` | string | Payer VPA. |
| `purpose` | string | UPI purpose code when available. |
| `refUrl` | string | UPI reference URL. |
| `riskScore` | string | Risk score when available. |
| `subMerchantChannelId` | string | Sub-merchant channel id when available. |
| `subMerchantId` | string | Sub-merchant id when available. |
| `tpvValidationStatus` | string | TPV validation status when available. |
| `transactionTimestamp` | string | Transaction timestamp. |
| `type` | string | Callback/transaction type. For this payload, `MERCHANT_CREDITED_VIA_PAY`. |
| `udfParameters` | string | Merchant metadata on the callback payload when available. Separate from top-level response `udfParameters`. |
| `umn` | string | Mandate UMN when available. |
| `orgMandateId` | string | Original mandate id when available. |
| `seqNumber` | string | Mandate sequence number when available. |

### Collect Payload Field Reference

Returned for `transactionType = MERCHANT_CREDITED_VIA_COLLECT`.

| Field | Type | Description |
| --- | --- | --- |
| `amount` | string | Transaction amount. |
| `autoUpdateNote` | string | UDIR/auto-update note when present. |
| `customResponse` | string | Merchant callback custom response/status text. |
| `deviceTags` | JSON value | Payer device tags from CBS payer information when available. |
| `expiry` | string | Collect expiry when available. |
| `gatewayPayeeResponseCode` | string | Gateway/NPCI payee response code when available. |
| `gatewayPayeeReversalResponseCode` | string | Payee reversal response code when available. |
| `gatewayPayerResponseCode` | string | Gateway/NPCI payer response code when available. |
| `gatewayPayerReversalResponseCode` | string | Payer reversal response code when available. |
| `gatewayReferenceId` | string | Gateway/NPCI reference id/RRN. |
| `gatewayResponseCode` | string | Gateway/NPCI transaction response code. Use with `gatewayResponseMessage` for reconciliation. |
| `gatewayResponseMessage` | string | Gateway/NPCI transaction response message. |
| `gatewayResponseStatus` | string | Gateway response status when available. |
| `gatewayTransactionId` | string | Newton UPI transaction id. |
| `merchantChannelId` | string | Merchant channel id. |
| `merchantId` | string | Merchant id. |
| `merchantRequestId` | string | Merchant order/reference id. |
| `originalMerchantRequestId` | string | Original merchant request id for related mandate/collect flows when available. |
| `payeeMcc` | string | Payee MCC. |
| `payeeVpa` | string | Payee/merchant VPA. |
| `payerAccBin` | string | Payer account BIN when available. |
| `payerAccountHash` | string | Payer account hash when available. |
| `payerMerchantCustomerId` | string | Merchant customer id for payer when available. |
| `payerName` | string | Payer display name. |
| `payerVpa` | string | Payer VPA when available. |
| `payerAcType` | string | Payer account type from callback data when available. |
| `payerActype` | string | Payer account type added from CBS or payer transaction details when available. |
| `payerIfsc` | string | Payer IFSC from CBS or payer transaction details when available. |
| `payerAccountNumber` | string | Payer account number from CBS or payer transaction details when available. |
| `payerMcc` | string | Payer MCC from CBS/payer details when available. |
| `purpose` | string | UPI purpose code when available. |
| `refUrl` | string | UPI reference URL. |
| `riskScore` | string | Risk score when available. |
| `orgMandateId` | string | Original mandate id when available. |
| `seqNumber` | string | Mandate sequence number when available. |
| `subMerchantChannelId` | string | Sub-merchant channel id when available. |
| `subMerchantId` | string | Sub-merchant id when available. |
| `tpvValidationStatus` | string | TPV validation status when available. |
| `transactionTimestamp` | string | Transaction timestamp. |
| `type` | string | Callback/transaction type. For this payload, `MERCHANT_CREDITED_VIA_COLLECT`. |
| `udfParameters` | string | Merchant metadata on the callback payload when available. Separate from top-level response `udfParameters`. |
| `umn` | string | Mandate UMN when available. |
| `mandateIntentPayUrl` | string | Mandate intent pay URL when available. |

## Failure Handling

Failure responses can be returned as encrypted/signed envelopes or as direct error bodies depending on where the failure happens. After decryption, client-facing errors generally use:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"upiRequestId and merchantRequestId not present.\""
}
```

Do not rely only on HTTP status. Several product/business errors are thrown with HTTP 200 and a failure body; authentication/IP failures use HTTP 401; downstream status unavailability can use `SERVICE_UNAVAILABLE_*`.

### Validation Failures

Missing both identifiers:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"upiRequestId and merchantRequestId not present.\""
}
```

Invalid `transactionType`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed CUSTOMER_DEBITED_VIA_PAY\""
}
```

Invalid timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"timestamp value not valid\""
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

### Identifier and Business Lookup Failures

No transaction or pending validation request found:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

Request exists but no transaction has been initiated:

```json
{
  "status": "FAILURE",
  "responseCode": "UNINITIATED_REQUEST",
  "responseMessage": "UNINITIATED_REQUEST"
}
```

Request is still pending before customer authorization/completion:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_PENDING",
  "responseMessage": "REQUEST_PENDING"
}
```

Request expired before authorization:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Customer dropped out or a stored validation failure code exists:

```json
{
  "status": "FAILURE",
  "responseCode": "DROPOUT",
  "responseMessage": "DROPOUT-Customer exited before payment"
}
```

Both identifiers are supplied but do not point to the same transaction/order:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "incorrect merchantRequestId or upiRequestId"
}
```

Product logic also has a defensive invalid-type failure, though request validation should normally catch this first:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid transactionType"
}
```

### Authentication, Signature, API Access, and IP Failures

Signature mismatch, missing required auth/signature headers, invalid merchant headers, or invalid IP whitelist:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not allowed for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Authentication/session mismatch in shared auth paths:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

### Downstream Status Refresh and Internal Failures

If Newton attempts a downstream status refresh and the downstream/NPCI path times out:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "UPI service is not reachable at the moment for transactional apis"
}
```

The `U09` suffix is a representative downstream timeout code; other timeout codes may be returned when NPCI or the gateway provides a different value.

If the downstream status response is malformed or Newton cannot map it:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Internal errors can also occur if payer account details are expected in CBS payer information but missing, if transaction decryption fails, or if the response builder reaches an unsupported branch. Treat these as retryable with monitoring/escalation.

## Idempotency, Retries, and Client Handling

Bank Status Check is a read/status-refresh API. It does not create a new payment and does not use `merchantRequestId` as a new idempotency key.

Recommended handling:

- Reuse the original transaction identifiers. Do not generate a new `merchantRequestId` for this API.
- Prefer `upiRequestId` when available because it identifies the transaction directly.
- Send both `upiRequestId` and `merchantRequestId` only when you want Newton to validate that they refer to the same transaction.
- Use `transactionTimestamp` for older transactions when your integration stores the original transaction time.
- Treat top-level `SUCCESS` as "status check succeeded"; then inspect `payload.gatewayResponseCode`, `payload.gatewayResponseMessage`, and `payload.gatewayResponseStatus` for transaction outcome.
- Retry `REQUEST_PENDING` with backoff until your business polling window ends.
- Do not retry `REQUEST_EXPIRED`, `REQUEST_NOT_FOUND`, `UNINITIATED_REQUEST`, or identifier mismatch without checking the original order state and identifiers.
- Retry `SERVICE_UNAVAILABLE_*` and `INTERNAL_SERVER_ERROR` with bounded backoff. Escalate if repeated.
- Fix request construction for `BAD_REQUEST`, `INVALID_DATA`, `UNAUTHORIZED`, `AUTH_FAILURE`, and `API NOT ENABLED` before retrying.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:445)
- Route handler and signature verification call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2566)
- Request type and validation instance: [src/Newton/Product/Merchant/Transactions/Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:65)
- Response payload type: [src/Newton/Product/Merchant/Transactions/Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:524)
- Product logic and identifier lookup: [src/Newton/Product/Merchant/Transactions/BankStatusCheck.hs](../../src/Newton/Product/Merchant/Transactions/BankStatusCheck.hs:28)
- Response payload builder and payer detail enrichment: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:410)
- S2S response wrapper: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2695)
- S2S success response construction: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1271)
- Request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Merchant signature, API access, and IP whitelist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:45)
- Common validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:918)
- Business lookup failures: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1730)
- Transaction status refresh behavior: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:64)
- Error response constructors: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
