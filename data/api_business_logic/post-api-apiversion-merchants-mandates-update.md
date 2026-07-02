# Update Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/update`

## Overview

Update Mandate is a server-to-server API used to modify or revoke an existing UPI mandate for a merchant customer.

The action is selected with `requestType`:

- `UPDATE`: modify the mandate amount and/or validity end date.
- `REVOKE`: revoke the mandate.

This endpoint is for the P2P mandate update path. Newton looks up the existing mandate by `umn` or `orgMandateId`, validates the merchant customer, mandate state, payer/payee role rules, account and device details where applicable, then sends the update or revoke request to the downstream UPI/NPCI path.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Update Mandate helps merchants:

- Increase or decrease the amount limit of an active mandate, subject to mandate type and configured UPI limits.
- Extend or change the mandate validity end date where the mandate rules allow it.
- Revoke an active mandate from the payer or payee side.
- Support payer-authorized updates with account, device, and credential validation.
- Support payee-initiated update/revoke flows where the mandate was created as a payee-side/self-initiated mandate.
- Receive a normalized response with the Newton mandate ids, UMN, gateway/NPCI status, payer/payee details, recurrence details, and merchant references.

Call this API only after the mandate exists in Newton and belongs to the `merchantCustomerId` in the request.

## Integration Flow

1. Merchant identifies the existing mandate using `umn` or `orgMandateId`.
2. Merchant creates a unique `upiRequestId` for this update/revoke attempt and a `merchantRequestId` for merchant-side reconciliation.
3. For `UPDATE`, merchant sends at least one changed value: `amount` or `validityEnd`.
4. For payer-side actions, merchant sends the customer's account identifier, device fingerprint, and either `credBlock` or `isPreApproved: true`.
5. Newton verifies the S2S envelope, merchant signature/configuration, API enablement, IP allow-listing, request fields, merchant customer, mandate lookup, mandate status, account, VPA, device, and credential rules.
6. Newton initiates the mandate update/revoke with the downstream UPI/NPCI path.
7. Newton returns a transport-level success response when the API call is processed. The actual mandate action outcome is in `payload.gatewayResponseCode` and `payload.gatewayResponseStatus`.
8. Merchant stores the returned identifiers and continues reconciliation through mandate callbacks and status APIs.

Important identifiers:

- `merchantCustomerId`: Merchant's customer id. Used during signature/auth context and mandate lookup.
- `orgMandateId`: Newton UPI request id of the original mandate.
- `umn`: UPI mandate number. Either `umn` or `orgMandateId` must be sent.
- `upiRequestId`: Unique Newton/gateway id for this update or revoke attempt. Reuse is treated as a duplicate action.
- `merchantRequestId`: Merchant reference for this attempt. If `transactionReference` is supplied, Newton uses it internally as the downstream merchant request id for S2S processing, while the API response still echoes `merchantRequestId`.
- `gatewayMandateId`: Newton id for this update/revoke action. In this API, it is the mandate history `upiRequestId`.
- `gatewayReferenceId`: Gateway/NPCI response id for this action.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/update
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. If omitted or not an integer, Newton uses base version `0`. |
| `x-merchant-id` | Merchant id configured with Newton. |
| `x-merchant-channel-id` | Merchant channel id configured with Newton. |
| `x-timestamp` | Request timestamp used by the S2S signature flow. |
| `x-merchant-signature` | Required for integrations using unsigned business payloads with header signature verification. |
| `x-forwarded-for` | Required only when the merchant is configured with `whitelistedIps`; the first IP is checked. |
| `x-request-id` | Optional client request id for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

Authentication, signature verification, API enablement checks, IP allow-listing, and response signing/encryption follow the Newton S2S process shared during onboarding.

The route accepts the standard Newton `EncRequest` envelope. Depending on onboarding, the wire request may be a JWE encrypted payload, a JWS signed payload, or an unsigned payload with request-signature headers. For encrypted or signed S2S requests, include `iat` in the decrypted business payload; Newton validates it as a timestamp before route processing.

## Request

### Required Minimum

Payer-side update with a credential block:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UPD-0001",
  "upiRequestId": "UPD202501010000000000000000001",
  "orgMandateId": "MND202412010000000000000000001",
  "requestType": "UPDATE",
  "amount": "1500.00",
  "validityEnd": "2025/12/31",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "credBlock": "{\"Cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20150822\",\"encryptedBase64String\":\"<encrypted-credential>\"}}}",
  "iat": "1735689600000"
}
```

Payee-side update:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UPD-0002",
  "upiRequestId": "UPD202501010000000000000000002",
  "umn": "YBL0000000000000000000000000000001@okbank",
  "requestType": "UPDATE",
  "amount": "1500.00",
  "expiry": "15",
  "iat": "1735689600000"
}
```

Revoke:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-REVOKE-0001",
  "upiRequestId": "RVK202501010000000000000000001",
  "orgMandateId": "MND202412010000000000000000001",
  "requestType": "REVOKE",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "credBlock": "{\"Cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20150822\",\"encryptedBase64String\":\"<encrypted-credential>\"}}}",
  "iat": "1735689600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id associated with the mandate. Max 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character from the allowed base set. |
| `merchantRequestId` | string | Yes | No default. | Merchant reference for this update/revoke attempt. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Echoed in the API response. |
| `upiRequestId` | string | Yes | No default. | Unique id for this update/revoke attempt. Must be 1 to 35 alphanumeric characters. If a mandate history already exists for this value, Newton returns a duplicate request error. |
| `requestType` | string | Yes | No default. | Mandate action. Allowed values: `UPDATE`, `REVOKE`. |
| `orgMandateId` | string | Conditional | No default. | Original mandate id, represented as the original mandate `upiRequestId`. Send either `orgMandateId` or `umn`. Must be 1 to 35 alphanumeric characters when supplied. |
| `umn` | string | Conditional | No default. | UPI mandate number. Send either `umn` or `orgMandateId`. Must be 34 to 70 characters and match `.{32}@.+` when supplied. |
| `amount` | string | Conditional | No default. | New mandate amount in two-decimal format, for example `1500.00`. Required for `UPDATE` if `validityEnd` is not supplied. Must be greater than `0.00` and not exceed the configured max mandate amount for the payee/purpose. |
| `validityEnd` | string | Conditional | No default. | New validity end date. Required for `UPDATE` if `amount` is not supplied. Date format accepted by validation is `YYYY/M/D`, `YYYY/MM/DD`, or the same date with hyphens. For one-time mandates, the end date cannot be more than 90 days from validity start. For recurring mandates, it cannot be in the past. |
| `expiry` | string | Conditional | No default. | Expiry in minutes for payee-initiated `UPDATE`. Must be digits from `1` to `64800`. For payer-side `UPDATE`, do not send `expiry`; Newton rejects payer updates that include it. |
| `bankAccountUniqueId` | string | Conditional | No default. | Payer account unique id/account hash. Required for stored payer-side mandates on this S2S route. It must match the account stored on the mandate. Do not send account ids for payee-side mandates. |
| `deviceFingerPrint` | string | Conditional | No default. | Required for payer-side actions except Lite mandate payee-initiated revoke. Newton validates it against the registered device, allowing `fallbackDeviceFingerPrint` as an alternate. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate device fingerprint used only for device validation. |
| `credBlock` | string | Conditional | No default. | Required for payer-side actions unless `isPreApproved` is `true`, except Lite mandate payee-initiated revoke. Must be a valid UPI credential block JSON string accepted by the credential parser. |
| `isPreApproved` | boolean | No | Omitted behaves like non-pre-approved, so `credBlock` is required for payer-side actions. | Set `true` only for pre-approved flows enabled for your integration. |
| `payeeVpa` | string | No | No default. | Optional payee VPA guard. If supplied, it must be 3 to 255 characters, match `local@handle` format, and match the mandate payee VPA. |
| `remarks` | string | No | Downstream request payload uses `"Update Mandate"` if omitted. | Merchant note for the update/revoke action. Must pass remarks validation when supplied. The response returns the remarks stored on mandate history, or Newton default remarks when absent. |
| `clVersion` | string | No | No default. | UPI Common Library version. Must be non-empty when supplied. |
| `makeAsync` | string | No | No default. | Optional async marker. If supplied, must be `"true"` or `"false"` ignoring case. Echoed in `payload.makeAsync`; this route still waits for product logic to return the API response. |
| `transactionReference` | string | No | No default. | Optional merchant reference used internally as the downstream merchant request id for S2S processing. Must be non-empty when supplied. |
| `initiatedBy` | string | Conditional | No default for normal mandates. Required for Lite mandate revoke. | Allowed values: `PAYEE`, `PAYER`. For Lite mandate `REVOKE`, `initiatedBy` is required. For non-Lite S2S processing, Newton generally derives the initiator from the stored mandate role before downstream processing. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant metadata. Must parse as a JSON object string and must not contain disallowed characters from validation. Echoed in this API response. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by encrypted/signed S2S request validation. Required for encrypted or signed requests. |

### Request Variants

#### Payer-Side Update With Credential Block

Use this when the mandate role is payer-side and the customer authorizes the update with credentials.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UPD-1001",
  "upiRequestId": "UPD202501010000000000000000101",
  "orgMandateId": "MND202412010000000000000000101",
  "requestType": "UPDATE",
  "amount": "2500.00",
  "validityEnd": "2025/12/31",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "fallbackDeviceFingerPrint": "aabbccddeeff00112233445566778899",
  "credBlock": "{\"Cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20150822\",\"encryptedBase64String\":\"<encrypted-credential>\"}}}",
  "payeeVpa": "merchant@bank",
  "clVersion": "2.0",
  "iat": "1735689600000",
  "udfParameters": "{\"reason\":\"limit_increase\"}"
}
```

#### Payer-Side Update With Pre-Approval

Use this only when Newton has enabled the pre-approved mandate update flow for your integration.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UPD-1002",
  "upiRequestId": "UPD202501010000000000000000102",
  "umn": "YBL0000000000000000000000000000001@okbank",
  "requestType": "UPDATE",
  "amount": "2500.00",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "isPreApproved": true,
  "iat": "1735689600000"
}
```

#### Payee-Side Update

Use this only for mandates where the stored mandate role/initiator allows payee-side update. Payee-side `UPDATE` requires `expiry` and must not include payer account identifiers.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UPD-1003",
  "upiRequestId": "UPD202501010000000000000000103",
  "orgMandateId": "MND202412010000000000000000103",
  "requestType": "UPDATE",
  "validityEnd": "2025/12/31",
  "expiry": "15",
  "makeAsync": "false",
  "iat": "1735689600000",
  "udfParameters": "{\"updatedBy\":\"merchant_console\"}"
}
```

#### Payer-Side Revoke

Use this when the payer is revoking a revocable mandate.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-REVOKE-1001",
  "upiRequestId": "RVK202501010000000000000000101",
  "umn": "YBL0000000000000000000000000000001@okbank",
  "requestType": "REVOKE",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "credBlock": "{\"Cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20150822\",\"encryptedBase64String\":\"<encrypted-credential>\"}}}",
  "iat": "1735689600000",
  "udfParameters": "{\"reason\":\"customer_requested\"}"
}
```

#### Lite Mandate Payee-Initiated Revoke

Lite mandate revoke requires `initiatedBy`. For Lite payee-initiated revoke, Newton allows the request without payer credential/account/device fields.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "LITE-REVOKE-1001",
  "upiRequestId": "LRV202501010000000000000000101",
  "orgMandateId": "LMT202412010000000000000000101",
  "requestType": "REVOKE",
  "initiatedBy": "PAYEE",
  "iat": "1735689600000"
}
```

### Defaults and Omitted Field Behavior

Fields not listed here have no implicit default and are not stored or returned when omitted.

- `orgMandateId` / `umn`: one is required. If both are omitted, validation fails before product logic.
- `amount` / `validityEnd`: for `UPDATE`, at least one must be supplied, and at least one supplied value must differ from the current mandate value.
- `expiry`: required for payee-side `UPDATE`; not allowed for payer-side `UPDATE`.
- `remarks`: if omitted, downstream processing uses `"Update Mandate"`. The API response returns the stored mandate history remarks, falling back to Newton's default remarks.
- `bankAccountUniqueId`: for payer-side actions, the supplied value must match the account stored in mandate transaction info. For payee-side mandates, account ids are rejected.
- `deviceFingerPrint`: for payer-side actions, must match the registered device fingerprint or fallback fingerprint.
- `payeeVpa`: if supplied, it must match the mandate payee VPA. If omitted, Newton uses the stored mandate payee VPA downstream.
- `transactionReference`: if supplied, Newton uses it as the internal downstream `merchantRequestId` for S2S processing.
- `makeAsync`: echoed in the response payload only when supplied.
- `gatewayPayerResponseCode`: returned only above base API version `0`.
- `transactionType`: response defaults to `UPI_MANDATE` when no `payType` is stored on the mandate.

## Response

### Success Response

The outer wire response follows your onboarded `EncResponse` mode: encrypted, signed, or plain. After decryption, the business response has this shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "accountReferenceId": "ACCREF1234567890",
    "amount": "2500.00",
    "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
    "blockFund": "false",
    "gatewayMandateId": "UPD202501010000000000000000101",
    "gatewayPayerResponseCode": "00",
    "gatewayReferenceId": "501010123456",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate update Request Sent Successfully",
    "gatewayResponseStatus": "PENDING",
    "initiatedBy": "PAYER",
    "mandateTimestamp": "2025-01-01T10:15:30",
    "mandateType": "UPDATE",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "MANDATE-UPD-1001",
    "mandateName": "Subscription",
    "orgMandateId": "MND202412010000000000000000101",
    "payeeMcc": "5411",
    "payeeName": "Merchant Store",
    "payeeVpa": "merchant@bank",
    "payerName": "Customer Name",
    "payerRevocable": "true",
    "payerVpa": "customer@bank",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "1",
    "refUrl": "https://merchant.example/mandates/MND202412010000000000000000101",
    "remarks": "Update Mandate",
    "role": "PAYER",
    "amountRule": "MAX",
    "shareToPayee": "false",
    "transactionType": "UPI_MANDATE",
    "umn": "YBL0000000000000000000000000000001@okbank",
    "validityEnd": "2025-12-31",
    "validityStart": "2024-12-01",
    "makeAsync": "false"
  },
  "udfParameters": "{\"reason\":\"limit_increase\"}"
}
```

### Response Field Reference

Top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Transport/business API status for this HTTP call. A processed call returns `SUCCESS`; inspect `payload.gatewayResponseStatus` for the mandate action outcome. |
| `responseCode` | string | Newton response code for route processing. Successful processing uses Newton success response code. |
| `responseMessage` | string | Newton response message for route processing. |
| `payload` | object | Mandate update/revoke action details. |
| `udfParameters` | string | Echoed only when supplied in the request. |

`payload` fields:

| Field | Type | Description |
| --- | --- | --- |
| `accountReferenceId` | string | Account reference id resolved from the stored mandate when multibank/account response is enabled. Omitted when not available. |
| `amount` | string | Mandate history amount after this action, formatted with two decimals. |
| `bankAccountUniqueId` | string | Bank account unique id resolved from the stored mandate when multibank/account response is enabled. Omitted when not available. |
| `blockFund` | string | `"true"` or `"false"` from the mandate's block-fund flag. |
| `expiry` | string | Expiry timestamp for payee-initiated `UPDATE` responses. Omitted for payer-side updates and revoke. |
| `gatewayMandateId` | string | Update/revoke action id, from mandate history `upiRequestId`. |
| `gatewayPayerResponseCode` | string | Payer-side NPCI response code parsed from `npciResponse`. Returned only above base API version `0`; omitted for base version. |
| `gatewayReferenceId` | string | Gateway/NPCI response id stored on mandate history. |
| `gatewayResponseCode` | string | Normalized action code. Examples: `00` for success, `01` for pending/request sent, or an NPCI/gateway failure code such as `JPNL`. |
| `gatewayResponseMessage` | string | Normalized action message. Examples include `Mandate update Success`, `Mandate update Request Sent Successfully`, `Mandate revoke Success`, or a downstream failure result. |
| `gatewayResponseStatus` | string | Mandate action outcome: `SUCCESS`, `PENDING`, or `FAILURE`. |
| `initiatedBy` | string | Derived action initiator: `PAYER` or `PAYEE`. |
| `mandateTimestamp` | string | Timestamp when this mandate history/action was created. |
| `mandateType` | string | Request action: `UPDATE` or `REVOKE`. |
| `merchantChannelId` | string | Newton merchant channel id. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `merchantId` | string | Newton merchant id. |
| `merchantRequestId` | string | Merchant request id from the request. |
| `mandateName` | string | Mandate display name, when stored. |
| `orgMandateId` | string | Original mandate `upiRequestId`. |
| `payeeMcc` | string | Payee MCC resolved from mandate payee info. |
| `payeeName` | string | Payee name when available for the mandate role. |
| `payeeVpa` | string | Payee VPA from mandate payee info, falling back to the stored mandate payee VPA. |
| `payerName` | string | Payer name when available for the mandate role. |
| `payerRevocable` | string | `"true"` or `"false"` from the mandate revocable flag. |
| `payerVpa` | string | Payer VPA from mandate payer info, falling back to the stored mandate payer VPA. |
| `recurrencePattern` | string | Mandate recurrence pattern, for example `ONETIME`, `DAILY`, `WEEKLY`, `MONTHLY`, `ASPRESENTED`. |
| `recurrenceRule` | string | Recurrence rule when present on the mandate. |
| `recurrenceValue` | string | Recurrence value when present on the mandate. |
| `refUrl` | string | Merchant reference URL from mandate transaction info, when stored. |
| `remarks` | string | Remarks stored on mandate history, or Newton default remarks when absent. |
| `role` | string | Mandate history role: `PAYER` or `PAYEE`. |
| `amountRule` | string | Mandate amount rule, for example `MAX` or `EXACT`. |
| `shareToPayee` | string | `"true"` or `"false"` from the mandate share-to-payee flag. |
| `transactionType` | string | Mandate transaction type. Known values: `UPI_MANDATE`, `QR_MANDATE`, `INTENT_MANDATE`, `P2M_MANDATE`, `PREPAID_VOUCHER`, `LITE_MANDATE`. Defaults to `UPI_MANDATE` if absent in stored mandate info. |
| `umn` | string | UPI mandate number, when available. |
| `validityEnd` | string | Mandate history validity end date. |
| `validityStart` | string | Original mandate validity start date. |
| `makeAsync` | string | Echo of request `makeAsync`, when supplied. |

### Gateway Status Interpretation

Newton can return `status: "SUCCESS"` even when the mandate action is pending or failed at the gateway. Use these fields for action outcome:

| `payload.gatewayResponseStatus` | Meaning | Client handling |
| --- | --- | --- |
| `SUCCESS` | Update/revoke completed successfully. | Mark the mandate action successful and reconcile with callbacks/status APIs. |
| `PENDING` | Request was accepted/sent and final outcome is pending, commonly payer-side update or revoke. | Do not retry immediately with the same `upiRequestId`. Poll status or wait for callback. |
| `FAILURE` | Downstream/gateway returned a terminal failure code/result. | Treat the action as failed. Fix the cause if actionable, then create a new attempt with a new `upiRequestId`. |

## Error Handling

Failure responses use the same response transport as success responses when the request reaches the S2S response layer. Some authentication, envelope, and gateway/system failures can be returned as HTTP `4xx`/`5xx` with the same decrypted `ErrorResponse` JSON shape.

Generic decrypted failure shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"OrgMandateId or UMN or originaMerchantRequestId should be present\""
}
```

`payload` is omitted for these errors unless a specific error type adds one.

### Validation Failures

Request schema/field validation failures are collected and returned as `BAD_REQUEST`. HTTP status can be `200` for validation errors raised by `validateRequestBody`.

Example: missing both mandate identifiers:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"OrgMandateId or UMN or originaMerchantRequestId should be present\""
}
```

Example: invalid `requestType`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed CANCEL\""
}
```

Example: invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Client handling: fix the request. Do not retry unchanged.

### Authentication, Signature, Encryption, Timestamp, API Enablement, and IP Failures

Missing or invalid merchant headers, invalid signature, invalid request timestamp, invalid/missing `iat` for signed/encrypted payloads, encrypted payload parsing failures, blocked API names, disallowed API names, and IP allow-list failures are rejected before product logic.

Unauthorized example:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API disabled/not allowed example:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Invalid encrypted/signed payload examples vary by envelope mode. The underlying decrypted error body usually has `responseCode` `BAD_REQUEST` or `INVALID_DATA`, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Unable to decrypt or parse payload"
}
```

Client handling: correct credentials, headers, signature payload, timestamp skew, encryption keys, merchant API configuration, or source IP. Retrying unchanged will fail.

### Lookup Failures

Mandate not found for the supplied `umn`/`orgMandateId`, merchant customer, and role:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

Merchant customer or customer lookup failures can return `INVALID_DATA`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
}
```

Client handling: verify `merchantCustomerId`, `umn`, `orgMandateId`, environment, and whether the mandate belongs to this merchant customer. Do not create a blind retry loop.

### Duplicate and Idempotency Failures

If `upiRequestId` was already used for a mandate action, Newton rejects the request as duplicate:

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST"
}
```

Client handling: treat as a duplicate attempt. Query mandate/action status using the original identifiers. If you need a new attempt after a terminal failure, generate a new `upiRequestId`.

### State and Business Rule Failures

Completed, declined, expired, pending, revoked, inactive, or otherwise non-updatable mandates are rejected before downstream initiation.

Completed mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is completed"
}
```

Pending mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is pending"
}
```

Revoked mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is revoked"
}
```

Inactive mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is inactive"
}
```

No changed value for `UPDATE`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Need atleast one value amount or validityEnd"
}
```

Same amount/date as current mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "both amount and validityEnd are same as in mandate"
}
```

Payer update with missing account/device:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "account id details and deviceFingerPrint required for PAYER update"
}
```

Payer update with missing credential:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "credBlock required when initiated by PAYER"
}
```

Invalid stored-account match:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid bankAccountUniqueId"
}
```

Device fingerprint mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "Device fingerprint mismatch"
}
```

Payee VPA mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "CustomerVpa does not match"
}
```

Invalid validity end:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid validityEnd"
}
```

Payer is not allowed to revoke a non-revocable mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is not payer revocable"
}
```

Only the initiator can update non-SBMD mandates:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Only mandate initiator can update"
}
```

Delegate or IoT mandate restriction:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Delegate Mandate Operation Restricted"
}
```

BASBA payer-side restriction:

```json
{
  "status": "FAILURE",
  "responseCode": "FORBIDDEN",
  "responseMessage": "Mandate modification not allowed from payer app"
}
```

Client handling: these are deterministic business-rule failures. Correct the request or stop the action. Do not retry unchanged.

### Lite Auto-Topup Failures

Lite auto-topup mandates have extra checks for active auto-topup status, recharge amount, threshold amount, and mandate amount.

Auto-topup not active:

```json
{
  "status": "FAILURE",
  "responseCode": "JPL4",
  "responseMessage": "Auto-topup is not set"
}
```

Recharge/threshold/mandate amount limit failure:

```json
{
  "status": "FAILURE",
  "responseCode": "JPL2",
  "responseMessage": "Incorrect amount : recharge amount cannot be more than 2000"
}
```

Client handling: use the Lite-specific limits shared during onboarding and retry only with corrected amount values.

### Downstream/Gateway Failures

If the downstream mandate update response is structurally invalid or times out, Newton returns service unavailable:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE",
  "responseMessage": "NPCI service unavailable"
}
```

If the downstream call is processed but NPCI/gateway returns a terminal mandate failure, the API can still return top-level `SUCCESS`; inspect the payload:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayMandateId": "UPD202501010000000000000000101",
    "gatewayReferenceId": "501010123456",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "Mandate Request Failed",
    "gatewayResponseStatus": "FAILURE",
    "mandateType": "UPDATE",
    "merchantRequestId": "MANDATE-UPD-1001",
    "orgMandateId": "MND202412010000000000000000101"
  }
}
```

Client handling: for `SERVICE_UNAVAILABLE`, check whether Newton created an action before retrying. For payload-level `FAILURE`, treat the action as terminal unless Newton support confirms a retryable gateway condition.

### Unexpected Errors

Unexpected missing internal records, decryption failures, or unhandled downstream failures can return `INTERNAL_SERVER_ERROR` or `SERVICE_UNAVAILABLE`.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: use `x-request-id`, `upiRequestId`, `merchantRequestId`, and timestamps when raising the issue to Newton. Before retrying, query status or confirm that no action was created.

## Retry and Idempotency Guidance

- Treat `upiRequestId` as the idempotency key for an update/revoke attempt. It must be unique across mandate action histories.
- Do not retry validation, auth, API-disabled, IP, lookup, state, account, device, or deterministic business-rule failures unchanged.
- For network timeout or `SERVICE_UNAVAILABLE`, first query status or check callbacks using the original `upiRequestId`, `merchantRequestId`, `orgMandateId`, or `umn`.
- If the original attempt is found in `PENDING`, wait for callback/status instead of creating another request.
- If the original attempt is terminal `FAILURE` and the business issue is corrected, create a new attempt with a new `upiRequestId`.
- Reusing the same `upiRequestId` returns `DUPLICATE_REQUEST`; it does not safely replay the response body.
- For payload-level `gatewayResponseStatus: "PENDING"`, do not submit another update/revoke for the same mandate until the current action reaches a terminal state.

## Source References

- Route type for `POST /api/{apiVersion}/merchants/mandates/update`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:608)
- Route handler, request decryption, signature verification, monitoring, and transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3171)
- S2S transformer route, `x-api-version`, request validation, core route, and response mapping: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:707)
- S2S request validation and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2555)
- S2S to core request and response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1247)
- Core request and response types: [src/Newton/Product/Merchant/Mandate/Types.hs](../../src/Newton/Product/Merchant/Mandate/Types.hs:308)
- Core product route and downstream initiation: [src/Newton/Product/Merchant/Mandate/UpdateMandate.hs](../../src/Newton/Product/Merchant/Mandate/UpdateMandate.hs:24)
- DB lookup, product validation, response construction, and S2S request normalization: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:100)
- Mandate status, duplicate, amount, VPA, validity, and Basba business rules: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:592)
- Downstream P2P mandate update wrapper and service-unavailable handling: [src/Newton/Utils/BusinessLogic/MandateHelper.hs](../../src/Newton/Utils/BusinessLogic/MandateHelper.hs:110)
- Downstream P2P payload construction and credential/device requirements: [src/Newton/Utils/Transformers/Transformer2.hs](../../src/Newton/Utils/Transformers/Transformer2.hs:62)
- Gateway response normalization for mandate update/revoke: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:1488)
- S2S envelope request/response variants: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Shared decrypted error response shape: [src/Newton/Types/API/Common.hs](../../src/Newton/Types/API/Common.hs:12)
- S2S route request helper and tracing headers: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Merchant signature verification, API enablement, timestamp, and IP allow-list checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Shared field validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:246)
