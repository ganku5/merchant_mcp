# Delegate Pay API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/delegatePay`

## Overview

Delegate Pay is a server-to-server API for UPI delegated payment flows. It lets a merchant backend create a payment request for a linked delegator/delegatee relationship, acknowledge or decline a pending delegate payment request, approve a pending request and initiate payment, or initiate a delegate payment directly.

Use this API only after the customer relationship has been set up through the delegate-link APIs or through an incoming NPCI delegate-link flow. Newton validates the merchant customer, device fingerprint, delegate link, purpose code, account details, request expiry, and transaction limits before calling NPCI or payment processing.

The examples in this guide show decrypted business payloads. On the wire, requests and responses use the standard Newton server-to-server envelope.

## Business Use Case

Delegate Pay supports:

- Partial delegation, where one customer requests or approves payments through a linked delegate relationship.
- Full delegation, where a successful delegate mandate must exist before payment requests can be created.
- IoT delegate payments, identified by purpose code `BH`, where a secondary device can be used for the delegatee flow.
- Merchant P2M payments through delegation, including optional merchant validation records when `transactionType` is `P2M_PAY`.
- Customer-facing pending payment journeys where a delegatee receives a pending request and the delegator later acknowledges, approves, or declines it.

## Integration Flow

1. Merchant creates or confirms a delegate link for the merchant customer.
2. Merchant calls `delegatePay` with one of the supported `action` values.
3. Newton verifies the S2S envelope, merchant access, API allowlisting, timestamp, optional IP allowlisting, and merchant-customer context.
4. Newton validates the request body and delegate business rules.
5. Newton creates or updates the delegate payment/transaction record and, when applicable, calls NPCI or payment processing.
6. Merchant decrypts the response and uses `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` as the business outcome.

Important: a top-level API response of `status = "SUCCESS"` means the request was accepted and mapped into a delegate-pay response. It does not always mean the payment is complete. Always inspect `payload.gatewayResponseStatus`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/delegatePay
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment. The route also supports the standard `x-api-version` header used by other Newton S2S APIs. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-merchant-id` | Yes | Merchant id issued by Newton. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued by Newton. |
| `x-timestamp` | Yes | Current request timestamp used by signature and replay validation. |
| `x-raw-body` | Yes | Exact raw HTTP body read by the signature middleware. It is required before the request mode branch, even when JWS/JWE carries cryptographic verification. |
| `x-merchant-signature` | Conditional | Required for plain unsigned business payload transport. JWS/JWE modes carry request authentication in the envelope. |
| `x-forwarded-for` | Conditional | Required when the merchant has IP allowlisting configured. The first comma-separated IP must be allowlisted. |
| `x-sub-merchant-id` | Conditional | Required only when the integration is configured to authenticate through a sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` when sub-merchant authentication is used. |
| `Authorization` | Conditional | Read by signature middleware for some configured integrations. Use only when shared during onboarding. |
| `x-api-version` | Recommended | API version header used by Newton S2S integrations. Use the value shared during onboarding. |

### Authentication, Signing, and Encryption

The route accepts Newton's standard `EncRequest` request body. Depending on onboarding, the wire body can be:

- JWE encrypted body with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed body with `payload`, `signature`, and `protected`.
- Plain business JSON only where the merchant configuration permits it, signed with request headers.

For encrypted or signed request bodies, include `iat` in the decrypted business payload. Newton validates it as a timestamp before product logic runs. Plain JSON examples below are the decrypted business payloads only.

Before invoking delegate-pay logic, Newton verifies:

- Merchant headers and merchant identity.
- Merchant API access and blocked/allowed API configuration.
- Merchant customer lookup using `merchantCustomerId`.
- Request signature or encrypted/signed envelope.
- `iat` for JWS/JWE requests.
- `x-timestamp` freshness.
- Optional IP allowlist through `x-forwarded-for`.

## Actions

| `action` | Use case | Main effects |
| --- | --- | --- |
| `REQUEST_PAY` | Create a pending delegate payment request. | Requires an active delegate link, `expiry`, and a valid purpose code. Creates a pending delegate payment and a pending transaction, then calls NPCI `ReqDelegateAuth`. |
| `ACK` | Acknowledge that the pending request is being taken up for payment. | Finds a pending delegate payment by `upiRequestId`, updates it to `PAY_INITIATED`, and sends NPCI `RespDelegateAuth`. |
| `APPROVE_PAY` | Approve a pending delegate request and initiate payment. | Requires payer VPA and account reference. Finds the pending request, creates a payment transaction, sends approval asynchronously, and initiates payment. |
| `DECLINE_PAY` | Decline a pending delegate payment request. | Finds a pending delegate payment by `upiRequestId`, updates it to `DECLINED`, and sends NPCI `RespDelegateAuth` with decline result. |
| `PAY` | Initiate a delegate payment directly. | Requires payer VPA and account reference. Creates a payment transaction and initiates payment without requiring a pending delegate payment request. |

## Request

### Minimum `REQUEST_PAY`

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint",
  "merchantRequestId": "ORDER12345",
  "delegatorVpa": "primaryuser@upi",
  "delegateeVpa": "secondaryuser@upi",
  "payeeVpa": "merchant@upi",
  "amount": "500.00",
  "action": "REQUEST_PAY",
  "upiRequestId": "DPREQ12345",
  "expiry": "15",
  "linkType": "PARTIAL"
}
```

### Minimum `APPROVE_PAY`

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint",
  "merchantRequestId": "ORDER12345",
  "delegatorVpa": "primaryuser@upi",
  "delegateeVpa": "secondaryuser@upi",
  "payeeVpa": "merchant@upi",
  "payerVpa": "primaryuser@upi",
  "amount": "500.00",
  "action": "APPROVE_PAY",
  "bankAccountUniqueId": "BANKACC123",
  "upiRequestId": "DPREQ12345",
  "linkType": "PARTIAL"
}
```

### Minimum Direct `PAY`

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint",
  "merchantRequestId": "ORDER12346",
  "delegatorVpa": "primaryuser@upi",
  "delegateeVpa": "secondaryuser@upi",
  "payeeVpa": "merchant@upi",
  "payerVpa": "primaryuser@upi",
  "amount": "250.00",
  "action": "PAY",
  "accountReferenceId": "ACCOUNTREF123",
  "upiRequestId": "DPPAY12346",
  "linkType": "PARTIAL"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer identifier. Newton uses it to load the merchant-customer and customer context. Max 256 characters. Allowed characters: letters, numbers, `.`, `_`, `+`, `/`, `=`, `-`; first character must be alphanumeric or one of `+`, `/`, `=`. |
| `deviceFingerPrint` | string | Yes | No default. | Fingerprint of the customer device or configured secondary device. Must be non-empty and must match the stored device for the delegate flow. |
| `merchantRequestId` | string | No | No default. | Merchant order/reference id. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Used to derive a transaction reference when `transactionReference` is omitted. |
| `delegatorVpa` | string | Yes | No default. | Primary/delegator VPA. Must be a valid VPA, 3 to 255 characters. |
| `delegateeVpa` | string | Yes | No default. | Secondary/delegatee VPA. Must be a valid VPA, 3 to 255 characters. |
| `payeeVpa` | string | Yes | No default. | Merchant or recipient VPA. Must be a valid VPA. For `APPROVE_PAY` and `PAY`, Newton also validates it as a global VPA. |
| `payerVpa` | string | Conditional | No default. | Required for `APPROVE_PAY` and `PAY`. VPA from which payment is made. Must be a valid VPA. |
| `payerName` | string | No | For payment transaction creation, Newton can fall back to account name or delegate VPA when available. | Optional payer display name. Must be non-empty if supplied. |
| `payeeName` | string | No | No default. | Optional payee display name. Not explicitly length-validated by this request validator. |
| `amount` | string | Yes | No default. | Payment amount. Must match `^[0-9]+\.[0-9][0-9]$` and be greater than `0.0`, for example `500.00`. |
| `action` | string | Yes | No default. | One of `REQUEST_PAY`, `ACK`, `APPROVE_PAY`, `DECLINE_PAY`, `PAY`. |
| `bankAccountUniqueId` | string | Conditional | No default. | Required with `APPROVE_PAY` or `PAY` unless `accountReferenceId` is supplied. Must be non-empty if supplied. |
| `accountReferenceId` | string | Conditional | No default. | Required with `APPROVE_PAY` or `PAY` unless `bankAccountUniqueId` is supplied. Must be non-empty if supplied. |
| `ifsc` | string | No | No default. | Optional IFSC hint used while resolving the account. Must be non-empty if supplied. |
| `credBlock` | string | No | No default. | Optional credential block. Must be non-empty if supplied. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated UPI request id. For `REQUEST_PAY` and `PAY`, this is the new transaction id. For `ACK`, `APPROVE_PAY`, and `DECLINE_PAY`, this identifies the existing pending delegate payment request. Must be alphanumeric and 1 to 35 characters. |
| `remarks` | string | No | For created payment transactions, omitted remarks default to `Delegate Payment`. For delegate-payment-only responses, omitted remarks remain absent. | Customer/payment note. Must be 1 to 255 characters and match the remarks validator. |
| `expiry` | string | Conditional | No default. | Required for `REQUEST_PAY`. Number of minutes after which the delegate payment request expires. It must parse as an integer and must not exceed the configured `maxTimeLimitForDelegateRequestPay`. For created transactions, a parsed value becomes `expiryTimestamp`; invalid optional values outside `REQUEST_PAY` are ignored by transaction expiry creation. |
| `currency` | string | No | Payment transaction records are created with `INR`; for `REQUEST_PAY`, this value is passed in the NPCI amount tag when supplied. | Currency value. Must be non-empty if supplied. |
| `transactionType` | string | No | No default. | If set to `P2M_PAY`, Newton also creates merchant validation data for the payee VPA and requires `merchantRequestId`. Must be non-empty if supplied. |
| `linkType` | string | Yes | No default. | Delegate link type. One of `FULL`, `PARTIAL`. |
| `transactionReference` | string | No | If omitted and `merchantRequestId` is supplied, Newton derives a reference/order id from `merchantRequestId`. | Transaction reference. Must be alphanumeric and 1 to 35 characters when supplied. |
| `refUrl` | string | No | Defaults from Newton NPCI configuration when omitted. | Merchant reference URL included in NPCI/payment metadata. Must be non-empty if supplied. |
| `refCategory` | string | No | Defaults from Newton NPCI configuration when omitted. | Merchant reference category included in NPCI/payment metadata. Must be non-empty if supplied. |
| `mcc` | string | No | For payment creation, payee MCC defaults by behavior to `0000` when omitted. | Payee MCC. Must be exactly 4 digits when supplied. |
| `initiationMode` | string | No | Payment transaction creation defaults to `00` when omitted. | UPI initiation mode. Must be exactly 2 alphanumeric characters when supplied. |
| `purpose` | string | No | Defaults to `59` when `linkType = FULL`; defaults to `87` when `linkType = PARTIAL`. | UPI purpose code. Must be exactly 2 uppercase alphanumeric characters. After defaulting, only delegate or IoT purpose codes are accepted: `59`, `87`, or `BH`. |
| `udfParameters` | string | No | No default. Echoed in the response when supplied. | Merchant-defined metadata as a JSON object encoded as a string, for example `"{\"cartId\":\"CART123\"}"`. Must parse as a JSON object and must not contain the disallowed special characters checked by the validator. |
| `iat` | string | Conditional | No default. | Required by the S2S signature/encryption layer for encrypted or signed request bodies. It is ignored by plain unsigned business payload validation. |
| `featureTags` | array of strings | No | No default. | Optional feature tags sent to NPCI as a `|`-joined feature-supported value for `REQUEST_PAY`. Each list item must be valid per common list validation. |
| `location` | string | No | No default. | Optional device/location value for NPCI device payload. Must be non-empty if supplied. |
| `geocode` | string | No | No default. | Latitude and longitude string, for example `12.9716,77.5946`. Latitude must be within `+/-90`; longitude within `+/-180`. |
| `ip` | string | No | No default. | IPv4 or IPv6 address sent in the NPCI device payload. |
| `capability` | string | No | No default. | Device capability value. Length must be 1 to 99 when supplied. |
| `clVersion` | string | No | No default. | UPI common library version. Must be non-empty if supplied. |
| `mid` | string | No | No default. | NPCI merchant info MID. Must be non-empty if supplied. |
| `msid` | string | No | No default. | NPCI merchant info SID/store id. Must be non-empty if supplied. |
| `mtid` | string | No | No default. | NPCI merchant info TID/terminal id. Must be non-empty if supplied. |
| `mOnBoardingType` | string | No | No default. | Merchant onboarding type sent in NPCI merchant info. No request-level validation beyond JSON enum/string parsing. |
| `mGenre` | string | No | No default. | Merchant genre sent in NPCI merchant info. |
| `mType` | string | No | No default. | Merchant type sent in NPCI merchant info. |
| `mBrand` | string | No | No default. | Merchant brand sent in NPCI merchant info. |
| `mLegal` | string | No | No default. | Merchant legal name sent in NPCI merchant info. |
| `mFranchise` | string | No | No default. | Merchant franchise name sent in NPCI merchant info. |
| `mOwnershipType` | string | No | No default. | Merchant ownership type sent in NPCI merchant info. |
| `mPinCode` | string | No | No default. | Merchant pin code sent in NPCI merchant info. |

### Defaults and Omitted Field Behavior

Fields not listed below have no code-supplied default.

- `purpose`: defaults to `59` for `FULL` links and `87` for `PARTIAL` links before product validation.
- `refUrl` and `refCategory`: default from Newton NPCI configuration when omitted.
- `remarks`: created payment transactions default to `Delegate Payment`; delegate-payment-only responses do not synthesize this default.
- `initiationMode`: created payment transactions default to `00` when omitted.
- `mcc`: payment/payee construction treats omitted MCC as `0000`.
- `transactionReference`: when omitted, Newton uses an order/reference derived from `merchantRequestId` where applicable.
- `expiryTimestamp`: returned only when `expiry` parses and was stored on the transaction/delegate payment.
- `currency`: created payment transaction records use `INR`; the request `currency` is still passed to NPCI in the `REQUEST_PAY` amount tag when supplied.

## Validation Rules

### Common Request Validation

- Required JSON fields must be present and parse to the expected type.
- `merchantCustomerId` must identify a merchant customer under the authenticated merchant.
- `deviceFingerPrint`, `bankAccountUniqueId`, `accountReferenceId`, `ifsc`, `credBlock`, `expiry`, `currency`, `transactionType`, `refUrl`, `refCategory`, `location`, `clVersion`, `mid`, `msid`, and `mtid` must be non-empty when supplied.
- `delegatorVpa`, `delegateeVpa`, `payeeVpa`, and `payerVpa` must match Newton's VPA validator.
- `amount` must be a positive two-decimal string.
- `upiRequestId` must be alphanumeric and 1 to 35 characters.
- `merchantRequestId`, when supplied, must be 1 to 35 characters and contain only letters, numbers, hyphen, dot, or underscore.
- `transactionReference`, when supplied, must be alphanumeric and 1 to 35 characters.
- `remarks`, when supplied, must be 1 to 255 characters and match the remarks validator.
- `mcc`, when supplied, must be exactly four digits.
- `initiationMode`, when supplied, must be exactly two alphanumeric characters.
- `purpose`, after defaulting, must be exactly two uppercase alphanumeric characters and must be a delegate or IoT purpose code: `59`, `87`, or `BH`.
- `udfParameters`, when supplied, must be a JSON object encoded as a string.
- `geocode`, when supplied, must be `latitude,longitude` with valid numeric ranges.
- `ip`, when supplied, must be a valid IPv4 or IPv6 value.
- `capability`, when supplied, must be 1 to 99 characters.

### Conditional Business Validation

| Condition | Rule |
| --- | --- |
| `action = REQUEST_PAY` | `expiry` is mandatory, must parse as an integer number of minutes, and must not exceed the merchant/configured maximum for delegate request pay. |
| `action = REQUEST_PAY` | An active delegate link must exist. For `FULL`, a successful mandate must be present. For a non-IoT full link, payment may be blocked until the configured first-transaction waiting period has passed after link activation. |
| `action = REQUEST_PAY` and stored link is `PARTIAL` | Requesting `linkType = FULL` is rejected. |
| `action = ACK`, `DECLINE_PAY`, or `APPROVE_PAY` | A pending delegate payment must exist for the same `upiRequestId` and merchant customer. The request `linkType` and `delegateeVpa` must match the stored pending request. Expired pending requests are marked `EXPIRED` and rejected. |
| `action = APPROVE_PAY` | `payerVpa` is mandatory. Either `bankAccountUniqueId` or `accountReferenceId` is mandatory. The linked user type must be `DELEGATOR`. |
| `action = PAY` | `payerVpa` is mandatory. Either `bankAccountUniqueId` or `accountReferenceId` is mandatory. |
| `action = APPROVE_PAY` or `PAY` | Newton must resolve a payer account from the supplied account identifier and merchant customer. ICCW restrictions are validated using purpose, initiation mode, MCC, and account bank code. |
| Delegate purpose `59` or `87` | A stored device must exist and `deviceFingerPrint` must match it. |
| IoT purpose `BH` and delegatee-initiated link | A stored secondary device must exist and `deviceFingerPrint` must match it. |
| `linkType = FULL` | A delegate mandate must be present and in `SUCCESS` state. Only `REQUEST_PAY` is allowed for full linking in this route. |
| `transactionType = P2M_PAY` | Newton creates merchant validation data for the payee merchant VPA. `merchantRequestId` must be present. If same-entity validation is enabled, the payee merchant VPA must belong to the same merchant entity/group. |

## Request Examples

### Partial Delegate Payment Request

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint",
  "merchantRequestId": "ORDER12345",
  "delegatorVpa": "primaryuser@upi",
  "delegateeVpa": "secondaryuser@upi",
  "payeeVpa": "merchant@upi",
  "payeeName": "Example Merchant",
  "amount": "500.00",
  "action": "REQUEST_PAY",
  "upiRequestId": "DPREQ12345",
  "remarks": "Delegated order payment",
  "expiry": "15",
  "currency": "INR",
  "transactionType": "P2M_PAY",
  "linkType": "PARTIAL",
  "transactionReference": "ORDER12345",
  "refUrl": "https://merchant.example/orders/ORDER12345",
  "refCategory": "00",
  "mcc": "5411",
  "initiationMode": "00",
  "purpose": "87",
  "udfParameters": "{\"cartId\":\"CART123\"}",
  "iat": "1714567890123",
  "geocode": "12.9716,77.5946",
  "ip": "203.0.113.10",
  "capability": "011001",
  "clVersion": "2.0"
}
```

### Full Delegate Payment Request

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint",
  "merchantRequestId": "ORDER12347",
  "delegatorVpa": "primaryuser@upi",
  "delegateeVpa": "secondaryuser@upi",
  "payeeVpa": "merchant@upi",
  "amount": "1000.00",
  "action": "REQUEST_PAY",
  "upiRequestId": "DPREQ12347",
  "expiry": "30",
  "linkType": "FULL",
  "purpose": "59",
  "remarks": "Full delegation payment"
}
```

### Acknowledge Pending Delegate Payment

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint",
  "delegatorVpa": "primaryuser@upi",
  "delegateeVpa": "secondaryuser@upi",
  "payeeVpa": "merchant@upi",
  "amount": "500.00",
  "action": "ACK",
  "upiRequestId": "DPREQ12345",
  "linkType": "PARTIAL"
}
```

### Decline Pending Delegate Payment

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint",
  "delegatorVpa": "primaryuser@upi",
  "delegateeVpa": "secondaryuser@upi",
  "payeeVpa": "merchant@upi",
  "amount": "500.00",
  "action": "DECLINE_PAY",
  "upiRequestId": "DPREQ12345",
  "linkType": "PARTIAL"
}
```

## Response

### Success Response Shape

Successful API handling returns:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "udfParameters": "{\"cartId\":\"CART123\"}",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "ORDER12345",
    "amount": "500.00",
    "expiryTimestamp": "2024-05-01 12:15:00",
    "payeeVpa": "merchant@upi",
    "mcc": "5411",
    "delegatorVpa": "primaryuser@upi",
    "delegateeVpa": "secondaryuser@upi",
    "payerName": "Primary User",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "remarks": "Delegated order payment",
    "purpose": "87",
    "transactionTimestamp": "2024-05-01 12:00:00",
    "gatewayTransactionId": "DPREQ12345",
    "gatewayReferenceId": "123456789012",
    "gatewayResponseStatus": "PENDING",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Transaction is in pending state"
  }
}
```

Fields without values are omitted from the JSON response.

### Acknowledgement Response Example

For `ACK`, the response can indicate that the delegate payment moved to pay initiation:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "amount": "500.00",
    "expiryTimestamp": "2024-05-01 12:15:00",
    "payeeVpa": "merchant@upi",
    "delegatorVpa": "primaryuser@upi",
    "delegateeVpa": "secondaryuser@upi",
    "transactionTimestamp": "2024-05-01 12:00:00",
    "gatewayTransactionId": "DPREQ12345",
    "gatewayResponseStatus": "PAY_INITIATED",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Pay initiation request send succesfully"
  }
}
```

### Decline Response Example

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "amount": "500.00",
    "payeeVpa": "merchant@upi",
    "delegatorVpa": "primaryuser@upi",
    "delegateeVpa": "secondaryuser@upi",
    "transactionTimestamp": "2024-05-01 12:00:00",
    "gatewayTransactionId": "DPREQ12345",
    "gatewayResponseStatus": "DECLINED",
    "gatewayResponseCode": "ZA",
    "gatewayResponseMessage": "Your payment has been declined successful"
  }
}
```

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Newton merchant id. |
| `merchantChannelId` | string | Newton merchant channel id. |
| `merchantCustomerId` | string | Merchant customer id from the authenticated merchant-customer record. |
| `merchantRequestId` | string | Echoed merchant request id when supplied. |
| `customerMobileNumber` | string | Currently not populated by this response builder. Omitted when absent. |
| `amount` | string | Amount formatted to two decimal places. |
| `expiryTimestamp` | string | Stored transaction or delegate payment expiry timestamp, when present. |
| `payeeVpa` | string | Payee VPA from the request. |
| `umn` | string | Mandate UMN. Currently not populated by this response builder. |
| `mcc` | string | MCC from the request when supplied. |
| `delegatorVpa` | string | Delegator VPA from the request. |
| `delegateeVpa` | string | Delegatee VPA from the request. |
| `payerName` | string | Payer name from the request when supplied. |
| `refUrl` | string | Effective reference URL, including configured default when request omitted it. |
| `remarks` | string | Stored remarks. Created transactions default to `Delegate Payment` when request remarks are omitted. |
| `purpose` | string | Effective purpose code after defaulting. |
| `transactionTimestamp` | string | Transaction or delegate payment creation timestamp. |
| `gatewayTransactionId` | string | Transaction UPI request id or pending delegate payment original UPI request id. |
| `gatewayReferenceId` | string | Transaction gateway/reference id when a transaction was created. |
| `gatewayResponseStatus` | string | Business/gateway outcome. Common values include `SUCCESS`, `PENDING`, `FAILURE`, `PAY_INITIATED`, `DECLINED`, and `EXPIRED`. |
| `gatewayResponseCode` | string | Gateway/NPCI/business code. `00` means success or successful initiation; `01` means pending; `ZA` is used for declined delegate payment; `U69` is used for expired requests. |
| `gatewayResponseMessage` | string | Gateway/business message mapped from the code/status. |
| `gatewayPayeeResponseCode` | string | Payee response code extracted from transaction NPCI response, when present. |
| `gatewayPayeeReversalResponseCode` | string | Payee reversal response code extracted from transaction NPCI response, when present. |
| `gatewayPayerResponseCode` | string | Payer response code extracted from transaction NPCI response, when present. |
| `gatewayPayerReversalResponseCode` | string | Payer reversal response code extracted from transaction NPCI response, when present. |

## Failure Scenarios

Failures can be returned either as encrypted/signed Newton responses or as direct HTTP error bodies before the normal business response is built. HTTP status can be `200`, `400`, `401`, or `500` depending on the failing layer. When a body is available, decrypt/parse it and inspect `status`, `responseCode`, and `responseMessage`.

### Request Validation Failures

Pure request validation failures happen before delegate business logic. Examples:

Invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "amount regex match failed"
}
```

Invalid VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "payeeVpa regex failed"
}
```

Invalid `merchantRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchant request id regex failed"
}
```

Invalid `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "JSON Text parse failed for udfParameters"
}
```

Client handling: fix the payload and retry with a new S2S envelope/signature. Do not reuse a stale signed/encrypted body.

### Authentication, Signature, Encryption, API Access, and IP Failures

These failures occur before product logic runs. Common causes:

- Missing or invalid `x-merchant-id` or `x-merchant-channel-id`.
- Missing `x-raw-body` or `x-timestamp`.
- Missing or invalid `x-merchant-signature` for plain signed payloads.
- JWS verification failure or JWE decryption failure.
- Missing or stale `iat` for encrypted/signed request bodies.
- Stale or malformed `x-timestamp`.
- API blocked or not allowed for the merchant.
- IP allowlist configured but `x-forwarded-for` missing or first IP not allowlisted.

Typical body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

When the merchant is authenticated but the API is not enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Invalid encrypted/signed request timestamp can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid timestamp format"
}
```

Client handling: fix credentials, API allowlisting, IP routing, timestamp, or envelope construction. Regenerate the request body/signature before retrying.

### Merchant Customer or Customer Lookup Failures

The route verifies `merchantCustomerId` under the authenticated merchant before calling delegate-pay logic. If the merchant customer/customer cannot be loaded, the response depends on the failing lookup layer, commonly `INVALID_DATA`, `UNAUTHORIZED`, or an internal error body.

Example shape:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Merchant Customer Not Found"
}
```

Client handling: verify the customer was created and active for the same merchant id/channel id used in the request.

### Delegate Business Validation Failures

Invalid purpose code:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid Purpose Code"
}
```

Missing account reference for `APPROVE_PAY` or `PAY`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is Mandatory for the actionAPPROVE_PAY"
}
```

Missing `payerVpa` for `APPROVE_PAY` or `PAY`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Payer Vpa and PayeeVpa is Mandatory for the action"
}
```

Missing or invalid `expiry` for `REQUEST_PAY`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "initialValidations : expiry not found"
}
```

Expiry above the configured delegate request maximum:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Expiry limit exceeded 15"
}
```

The numeric limit in the message is configuration-driven.

Missing active link:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Delegate link not found"
}
```

Delegate link exists but is unavailable for this operation:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Delegate Link Not Present"
}
```

Full-link request without successful mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate Not Present"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate Not in Success State"
}
```

Action not allowed for full linking:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "APPROVE_PAY action not allowed for Full Linking"
}
```

Full-link first-payment waiting period:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Delegate Link Not Active For Payment(FP)"
}
```

Partial link cannot be used as full:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "FULL payment not allowed for PARTIAL Linking"
}
```

Device issues:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Device not found for delegate payment flow"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Secondary device not found for IoT payment flow"
}
```

Client handling: correct the delegate link state, device state, purpose/link type, or action-specific inputs. These failures are not fixed by blind retry.

### Pending Delegate Payment Failures

`ACK`, `APPROVE_PAY`, and `DECLINE_PAY` require a pending delegate payment for the same `upiRequestId` and merchant customer.

Pending request not found:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Delegate Payment Not Found"
}
```

Expired pending request:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Link type mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Link Type Mismatch"
}
```

Delegatee VPA mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Delegatee VPA mismatch between request and ReqDelegateAuth"
}
```

Client handling: treat `REQUEST_EXPIRED` as terminal for that pending request. For not-found or mismatch errors, reconcile the original `REQUEST_PAY` identifiers before retrying.

### Duplicate and Idempotency Failures

Newton uses `upiRequestId` as the primary transaction/delegate payment lookup key for this flow. A duplicate insert at the storage layer can surface as an internal server error if the same id is reused for a new create operation instead of a retry of the same state transition.

Typical body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Generate a unique `upiRequestId` for every new `REQUEST_PAY` or direct `PAY`.
- For `ACK`, `APPROVE_PAY`, and `DECLINE_PAY`, reuse the original pending request's `upiRequestId`; do not generate a new id.
- On network timeout for `REQUEST_PAY`, retry once with the same `upiRequestId` only if the first attempt may not have reached Newton. If the retry returns duplicate/internal error, query the related status or pending-delegate-payment APIs before creating a new request.
- On network timeout after `APPROVE_PAY` or `PAY`, check transaction status using the returned/requested `upiRequestId` before initiating another debit.

### Business, Risk, and Downstream Failures

Risk/Sherlock validation or payment processing can mark the transaction or delegate payment as failed while still returning a top-level `SUCCESS` response. In that case, inspect the payload:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "amount": "500.00",
    "payeeVpa": "merchant@upi",
    "delegatorVpa": "primaryuser@upi",
    "delegateeVpa": "secondaryuser@upi",
    "transactionTimestamp": "2024-05-01 12:00:00",
    "gatewayTransactionId": "DPREQ12345",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U30",
    "gatewayResponseMessage": "Transaction failed"
  }
}
```

NPCI `RespDelegateAuth` service failure can return:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE",
  "responseMessage": "UPI service is not reachable at the moment"
}
```

Internal/decode/redis failures in downstream async handling can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: for `PENDING`, poll or wait for callback/status update. For gateway `FAILURE`, treat the transaction as failed unless Newton support instructs otherwise. For transient `SERVICE_UNAVAILABLE` or internal errors, retry with bounded backoff and a fresh S2S signature/envelope; for debit actions, check status before retrying to avoid double initiation.

## Idempotency and Retry Guidance

- Use `upiRequestId` as the idempotency key for this API.
- Use a new `upiRequestId` for each new `REQUEST_PAY` or direct `PAY`.
- Use the same `upiRequestId` from the original `REQUEST_PAY` when calling `ACK`, `APPROVE_PAY`, or `DECLINE_PAY`.
- Regenerate `iat`, `x-timestamp`, signature, and encrypted/signed envelope on every retry.
- Do not retry validation, authentication, API-disabled, IP allowlist, device mismatch, link mismatch, or expired-request failures without changing the underlying request/configuration.
- Treat `payload.gatewayResponseStatus = "SUCCESS"` as completed, `PENDING` or `PAY_INITIATED` as in progress, and `FAILURE`, `DECLINED`, or `EXPIRED` as terminal for that request unless Newton support says otherwise.
- For uncertain outcomes after `APPROVE_PAY` or `PAY`, check transaction status for `gatewayTransactionId`/`upiRequestId` before sending another payment action.

## Source References

- Route type and endpoint: [Core.hs](../../src/Newton/App/Routes/Core.hs:773)
- Route handler, request extraction, signature verification, and transformer call: [Core.hs](../../src/Newton/App/Routes/Core.hs:3281)
- Request and response types plus pure validators: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3613)
- S2S transformer route: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:780)
- S2S request defaulting and response construction: [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1442)
- Product route and `refUrl`/`refCategory` defaults: [DelegatePay.hs](../../src/Newton/Product/Merchant/Delegates/DelegatePay.hs:13)
- Delegate-pay business validation and response payload construction: [Helper.hs](../../src/Newton/Product/Merchant/Delegates/Helper.hs:160)
- Delegate DB lookup and create/update flow: [DB.hs](../../src/Newton/Product/Merchant/Delegates/DB.hs:48)
- Delegate payment record construction: [Transformer.hs](../../src/Newton/Product/Merchant/Delegates/Transformer.hs:55)
- NPCI delegate auth calls and downstream handling: [Helper.hs](../../src/Newton/Product/NpciSwitch/Meta/Delegates/Helper.hs:65)
- Action enum and core response type: [Types.hs](../../src/Newton/Product/Merchant/Delegates/Types.hs:65)
- Link type enum: [DelegateLink.hs](../../src/Newton/Types/Storage/DelegateLink.hs:117)
- Delegate payment status enum: [DelegatePayment.hs](../../src/Newton/Types/Storage/DelegatePayment.hs:54)
- Common validation helpers: [Common.hs](../../src/Newton/Validation/Common.hs:125)
- S2S envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Merchant signature, timestamp, API allowlist, and IP allowlist checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
