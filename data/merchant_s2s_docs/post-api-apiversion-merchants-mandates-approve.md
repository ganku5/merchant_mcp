# Approve Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/approve`

## Overview

Approve Mandate is a server-to-server API used to approve or decline a pending UPI mandate action for a merchant customer.

Despite the endpoint name, this API handles both customer approval and customer decline. The action is selected with `requestType`:

- `APPROVE`: approve the pending mandate request with the customer's device, account, and credential context.
- `DECLINE`: decline the pending mandate request and trigger the normal decline callback flow.

Use this API after Newton has created or received a pending mandate action that the merchant customer needs to respond to. The pending action is identified by `mandateRequestId` or, where available, `umn`.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Approve Mandate helps merchants:

- Complete customer authorization for a pending UPI mandate creation.
- Approve pending mandate modifications, revocations, or port actions where the mandate history type supports the action.
- Decline a pending mandate request when the customer rejects it or the merchant wants to stop the authorization flow.
- Bind the final mandate authorization to the expected merchant customer, device, payer account, and mandate identifiers.
- Receive a normalized response containing the Newton mandate ids, UMN, gateway/NPCI outcome, recurrence details, payer/payee details, and merchant reference values.

Call this API only when the merchant backend has a pending mandate action for the same `merchantCustomerId`. For a new mandate creation, use the pending `mandateRequestId` because the `umn` may not exist until the mandate is approved.

## Integration Flow

1. Merchant receives or creates a pending mandate action through the mandate journey.
2. Merchant customer approves or declines the mandate in the merchant experience.
3. For `APPROVE`, merchant backend sends the device fingerprint, account identifier, and credential information. For `DECLINE`, merchant backend sends the mandate identifier and decline action.
4. Newton verifies the S2S envelope, merchant signature/configuration, request fields, merchant customer, pending mandate history, account, device, and VPA consistency.
5. Newton sends the approve/decline response to NPCI and updates mandate records.
6. Newton returns a transport-level success response when the API call is processed. The actual mandate outcome is in `payload.gatewayResponseCode` and `payload.gatewayResponseStatus`.
7. Merchant stores the returned identifiers and continues reconciliation through mandate status APIs and callbacks.

Important identifiers:

- `merchantCustomerId`: Merchant's customer id. Used for authentication context and lookup.
- `mandateRequestId`: Pending mandate action id, represented internally as the mandate history UPI request id.
- `umn`: UPI mandate number. Useful for existing mandates; usually not available before a create mandate is approved.
- `merchantRequestId`: Merchant-generated reference for this approve/decline attempt. Newton stores it on the mandate history and echoes it in the response.
- `gatewayMandateId`: Newton id for the mandate action being approved or declined.
- `orgMandateId`: Newton id for the original mandate.
- `gatewayReferenceId`: Gateway/NPCI response reference id for this approve/decline call.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/approve
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. Use the latest onboarded version for new integrations. |
| `x-merchant-id` | Merchant id configured with Newton. |
| `x-merchant-channel-id` | Merchant channel id configured with Newton. |
| `x-timestamp` | Request timestamp used by the S2S signature flow. |
| `x-merchant-signature` | Required for integrations using unsigned business payloads with header signature verification. |
| `x-request-id` | Optional client request id for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

Authentication, signature verification, IP allow-listing, API enablement checks, and response signing/encryption follow the Newton S2S process shared during onboarding.

The route accepts the standard Newton `EncRequest` envelope. Depending on onboarding, the wire request may be a JWE encrypted payload, a JWS signed payload, or an unsigned payload with request-signature headers. For encrypted or signed S2S requests, include `iat` in the decrypted business payload; Newton validates it as a timestamp.

## Request

### Required Minimum

For approval with a customer-entered credential block:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-APPROVE-0001",
  "mandateRequestId": "MNDREQ000000000000000000000001",
  "requestType": "APPROVE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "accountReferenceId": "ACCREF1234567890",
  "credBlock": "{\"Cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20150822\",\"encryptedBase64String\":\"<encrypted-credential>\"}}}",
  "iat": "1735689600000"
}
```

For pre-approved mandate approval:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-APPROVE-0002",
  "mandateRequestId": "MNDREQ000000000000000000000002",
  "requestType": "APPROVE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "isPreApproved": true,
  "iat": "1735689600000"
}
```

For decline:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-DECLINE-0001",
  "mandateRequestId": "MNDREQ000000000000000000000003",
  "requestType": "DECLINE",
  "iat": "1735689600000",
  "udfParameters": "{\"reason\":\"customer_declined\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id associated with the pending mandate. Max 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character from the allowed base set. |
| `merchantRequestId` | string | Yes | No default. | Merchant reference for this approve/decline attempt. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Stored on the mandate history and echoed in the response/callback context. |
| `requestType` | string | Yes | No default. | Mandate action. Allowed values: `APPROVE`, `DECLINE`. |
| `mandateRequestId` | string | Conditional | No default. | Pending mandate action id. Send either `mandateRequestId` or `umn`. For create mandate approval, use `mandateRequestId` because UMN is normally not assigned yet. Must be 1 to 35 alphanumeric characters when supplied. |
| `umn` | string | Conditional | No default. | UPI mandate number. Send either `umn` or `mandateRequestId`. Must be 34 to 70 characters and match the UMN pattern when supplied. |
| `deviceFingerPrint` | string | Conditional | No default. | Required for `APPROVE`. Newton validates it against the merchant customer's registered device. If supplied for `DECLINE`, it is also validated. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate fingerprint. Device validation succeeds if either `deviceFingerPrint` or this fallback matches the stored device. |
| `accountReferenceId` | string | Conditional | No default. | Account reference id for the payer account. For `APPROVE`, send exactly one of `accountReferenceId` or `bankAccountUniqueId`. For non-create mandate actions, Newton validates the supplied account against the mandate's stored account. |
| `bankAccountUniqueId` | string | Conditional | No default. | Bank account unique id/account hash for the payer account. For `APPROVE`, send exactly one of `bankAccountUniqueId` or `accountReferenceId`. For non-create mandate actions, Newton validates the supplied account against the mandate's stored account. |
| `ifsc` | string | Conditional | No default. | Required for some migrated-account or PSP-specific account lookup flows when using `accountReferenceId`. Otherwise omit unless shared during onboarding. |
| `credBlock` | string | Conditional | No default. | Required for `APPROVE` unless `isPreApproved` is `true`. Must be a valid credential block JSON string accepted by the UPI credential provider. Omit for `DECLINE`. |
| `isPreApproved` | boolean | No | Omitted behaves like non-pre-approved for `APPROVE`, so `credBlock` is required. | Set `true` only for pre-approved flows where Newton should create the pre-approved credential block internally. Ignored for `DECLINE`. |
| `clVersion` | string | No | No default. | UPI Common Library version, forwarded to NPCI where applicable. |
| `payeeVpa` | string | No | No default. | Optional payee VPA guard. If supplied, it must match the mandate payee VPA. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by S2S signature/encryption validation. Required for encrypted or signed requests. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant metadata. Stored with the action, used in callbacks, and echoed in this API response. |

### Credential Block

`credBlock` is a string field containing serialized credential data. For normal `APPROVE` requests, it must parse as a supported credential payload. If the value is missing or malformed, Newton returns `INVALID_DATA` with `Invalid credBlock`.

When `isPreApproved` is `true`, Newton generates the pre-approved credential block internally and `credBlock` can be omitted. Use this only when the pre-approved flow is enabled for your integration.

### Defaults and Omitted Field Behavior

Fields not listed here have no implicit default and are not stored or returned when omitted.

- `mandateRequestId` and `umn`: one is required. If both are omitted, Newton returns `BAD_REQUEST`.
- `deviceFingerPrint`: required for `APPROVE`. If omitted for `APPROVE`, Newton returns `BAD_REQUEST`.
- `accountReferenceId` / `bankAccountUniqueId`: one account identifier is required for `APPROVE`. Omit account identifiers for `DECLINE`.
- `credBlock`: required for `APPROVE` unless `isPreApproved` is `true`.
- `payeeVpa`: optional, but if supplied it is validated against the pending mandate's payee VPA.
- `udfParameters`: echoed only when supplied.

## Request Examples

### Approve Pending Create Mandate

Use this when the customer approves a pending mandate creation and UMN is not yet assigned.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-APPROVE-1001",
  "mandateRequestId": "MNDREQ202501010000000000000001",
  "requestType": "APPROVE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "fallbackDeviceFingerPrint": "aabbccddeeff00112233445566778899",
  "accountReferenceId": "ACCREF1234567890",
  "credBlock": "{\"Cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20150822\",\"encryptedBase64String\":\"<encrypted-credential>\"}}}",
  "clVersion": "2.0",
  "iat": "1735689600000",
  "udfParameters": "{\"checkoutId\":\"CHK1001\"}"
}
```

### Approve Existing Mandate Action By UMN

Use this for pending actions on an existing mandate when the UMN is known.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UPDATE-APPROVE-1002",
  "umn": "YBL0000000000000000000000000000001@okbank",
  "requestType": "APPROVE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "payeeVpa": "merchant@bank",
  "credBlock": "{\"Cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20150822\",\"encryptedBase64String\":\"<encrypted-credential>\"}}}",
  "iat": "1735689600000"
}
```

### Pre-Approved Mandate Approval

Use this only when your integration has been enabled for pre-approved mandate authorization.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-PREAPPROVED-1003",
  "mandateRequestId": "MNDREQ202501010000000000000003",
  "requestType": "APPROVE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "accountReferenceId": "ACCREF1234567890",
  "isPreApproved": true,
  "iat": "1735689600000"
}
```

### Decline Pending Mandate

Use this when the customer declines the pending mandate. Do not send device, account, or credential fields unless Newton has specifically asked for them.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-DECLINE-1004",
  "mandateRequestId": "MNDREQ202501010000000000000004",
  "requestType": "DECLINE",
  "iat": "1735689600000",
  "udfParameters": "{\"reason\":\"customer_declined\"}"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Transport/API processing status. Success value is `SUCCESS`. This does not by itself mean the mandate was approved. |
| `responseCode` | string | Transport/API response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Transport/API response message. Success value is `SUCCESS`. |
| `payload` | object | Mandate approval/decline result. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id supplied in the request. |
| `merchantRequestId` | string | Merchant request id supplied in the request. |
| `gatewayMandateId` | string | Newton id for the mandate action/history being approved or declined. |
| `orgMandateId` | string | Newton id for the original mandate. |
| `gatewayReferenceId` | string | Gateway/NPCI response reference id. |
| `gatewayResponseCode` | string | Gateway outcome code. `00` indicates successful approval. Decline success can use decline-specific NPCI codes such as `ZA` or `QT`. Other values indicate a failed gateway outcome. |
| `gatewayResponseMessage` | string | Gateway outcome message, for example `Mandate create Approve Success`, `Create Mandate Decline Success`, or an NPCI failure result. |
| `gatewayResponseStatus` | string | Mandate action outcome. Expected values include `SUCCESS`, `DECLINED`, and `FAILURE`. Clients should use this with `gatewayResponseCode` to decide the final action state. |
| `gatewayPayerResponseCode` | string | Payer-side response code parsed from NPCI response. Returned only above response version `0` when present. |
| `bankAccountUniqueId` | string | Payer account unique id/account hash. Returned only for `APPROVE` responses when multibank is enabled for this API and value is available. |
| `amount` | string | Mandate amount formatted to two decimals. |
| `amountRule` | string | Mandate amount rule, for example `EXACT` or `MAX`. |
| `blockFund` | string | `true` or `false` as a string, based on mandate block-fund setting. |
| `transactionType` | string | Transaction type from mandate metadata. Defaults to `UPI_MANDATE` when not stored. |
| `mandateType` | string | Pending mandate action type, for example `CREATE`, `UPDATE`, `REVOKE`, or `PORT`. |
| `mandateName` | string | Mandate name when available. |
| `mandateTimestamp` | string | Timestamp when the mandate action/history was created. |
| `mandateApprovalTimestamp` | string | Present only for successful create mandate approval when the approval timestamp is available. Omitted for declines, failures, and most non-create actions. |
| `umn` | string | UPI mandate number when available. |
| `payerVpa` | string | Payer VPA from mandate data. |
| `payerName` | string | Payer name when available and applicable for the mandate role. |
| `payerRevocable` | string | `true` or `false` as a string, based on mandate revocability. |
| `payeeVpa` | string | Payee VPA from mandate data. |
| `payeeName` | string | Payee name when available and applicable for the mandate role. |
| `payeeMcc` | string | Payee MCC. Defaults to `0000` when no MCC is stored. |
| `payeeIfsc` | string | Payee IFSC when available. Returned only above response version `1`. |
| `initiatedBy` | string | Party that initiated the mandate action, derived from mandate role and self-initiated flag. |
| `role` | string | Mandate history role, for example `PAYER` or `PAYEE`. |
| `recurrencePattern` | string | Mandate recurrence pattern such as `ONETIME`, `DAILY`, `WEEKLY`, `MONTHLY`, or `ASPRESENTED`. |
| `recurrenceRule` | string | Optional recurrence rule such as `ON`, `AFTER`, or `BEFORE`. |
| `recurrenceValue` | string | Optional recurrence value. |
| `validityStart` | string | Mandate validity start date. |
| `validityEnd` | string | Mandate validity end date. |
| `expiry` | string | Mandate expiry timestamp when available. |
| `refUrl` | string | Merchant reference URL from mandate metadata, or Newton default when not stored. |
| `remarks` | string | Mandate note/remarks, or Newton default when not stored. |
| `shareToPayee` | string | `true` or `false` as a string, based on mandate share-to-payee setting. |

### Success Response: Approved

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "MANDATE-APPROVE-1001",
    "gatewayMandateId": "MNDREQ202501010000000000000001",
    "orgMandateId": "YBL0000000000000000000000000000001",
    "gatewayReferenceId": "NPCIREF1234567890",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Mandate create Approve Success",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayPayerResponseCode": "00",
    "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
    "amount": "500.00",
    "amountRule": "MAX",
    "blockFund": "false",
    "transactionType": "UPI_MANDATE",
    "mandateType": "CREATE",
    "mandateName": "Monthly subscription",
    "mandateTimestamp": "2025-01-01 10:15:30",
    "mandateApprovalTimestamp": "2025-01-01 10:16:05",
    "umn": "YBL0000000000000000000000000000001@okbank",
    "payerVpa": "customer@bank",
    "payerName": "Customer Name",
    "payerRevocable": "true",
    "payeeVpa": "merchant@bank",
    "payeeName": "Merchant Name",
    "payeeMcc": "5411",
    "payeeIfsc": "HDFC0000001",
    "initiatedBy": "PAYEE",
    "role": "PAYER",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "1",
    "validityStart": "2025-01-01",
    "validityEnd": "2025-12-31",
    "expiry": "2025-01-01 10:30:00",
    "refUrl": "https://merchant.example/mandates/MANDATE-APPROVE-1001",
    "remarks": "Monthly subscription",
    "shareToPayee": "true"
  },
  "udfParameters": "{\"checkoutId\":\"CHK1001\"}"
}
```

### Success Response: Declined

`DECLINE` can return top-level `SUCCESS` because Newton processed the API call successfully. The mandate action outcome is `payload.gatewayResponseStatus`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "MANDATE-DECLINE-1004",
    "gatewayMandateId": "MNDREQ202501010000000000000004",
    "orgMandateId": "YBL0000000000000000000000000000004",
    "gatewayReferenceId": "NPCIREF1234567894",
    "gatewayResponseCode": "ZA",
    "gatewayResponseMessage": "Create Mandate Decline Success",
    "gatewayResponseStatus": "DECLINED",
    "amount": "500.00",
    "amountRule": "MAX",
    "blockFund": "false",
    "transactionType": "UPI_MANDATE",
    "mandateType": "CREATE",
    "mandateTimestamp": "2025-01-01 10:15:30",
    "payerVpa": "customer@bank",
    "payerRevocable": "true",
    "payeeVpa": "merchant@bank",
    "payeeMcc": "5411",
    "initiatedBy": "PAYEE",
    "role": "PAYER",
    "recurrencePattern": "MONTHLY",
    "validityStart": "2025-01-01",
    "validityEnd": "2025-12-31",
    "refUrl": "https://merchant.example/mandates/MANDATE-DECLINE-1004",
    "remarks": "Monthly subscription",
    "shareToPayee": "true"
  },
  "udfParameters": "{\"reason\":\"customer_declined\"}"
}
```

### Processed Response With Gateway Failure

If Newton reaches NPCI and receives a business failure, the API response can still have top-level `SUCCESS`. Treat the mandate action as failed when `payload.gatewayResponseStatus` is `FAILURE`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "MANDATE-APPROVE-1005",
    "gatewayMandateId": "MNDREQ202501010000000000000005",
    "orgMandateId": "YBL0000000000000000000000000000005",
    "gatewayReferenceId": "NPCIREF1234567895",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "Mandate Request Failed",
    "gatewayResponseStatus": "FAILURE",
    "amount": "500.00",
    "amountRule": "MAX",
    "blockFund": "false",
    "transactionType": "UPI_MANDATE",
    "mandateType": "CREATE",
    "mandateTimestamp": "2025-01-01 10:15:30",
    "payerVpa": "customer@bank",
    "payerRevocable": "true",
    "payeeVpa": "merchant@bank",
    "payeeMcc": "5411",
    "initiatedBy": "PAYEE",
    "role": "PAYER",
    "recurrencePattern": "MONTHLY",
    "validityStart": "2025-01-01",
    "validityEnd": "2025-12-31",
    "refUrl": "https://merchant.example/mandates/MANDATE-APPROVE-1005",
    "remarks": "Monthly subscription",
    "shareToPayee": "true"
  }
}
```

## Response Versioning and Omitted Fields

Use the newest `x-api-version` available for your integration.

| Field | Version / condition |
| --- | --- |
| `gatewayPayerResponseCode` | Included only above response version `0` and only when parsed from NPCI response. |
| `payeeIfsc` | Included only above response version `1` and only when available from mandate payee information. |
| `bankAccountUniqueId` | Included only for `APPROVE` responses when the merchant is enabled for multibank on this API and the stored value is available. |
| `mandateApprovalTimestamp` | Included only for successful create mandate approval when available. |
| `udfParameters` | Included only when supplied in the request. |

Optional payload fields use `omitNothingFields`; absent fields should be treated as unavailable rather than empty strings.

## Error Handling

Failure responses use Newton's shared error object after decryption or after the configured response transport is applied:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "deviceFingerPrint and bankAccountUniqueId required for approve"
}
```

HTTP status is not always the business status. Some validation and business failures are returned with HTTP 200 and a failure body, while signature, bad-request, and internal failures can use HTTP 400, 401, or 500. Clients should always parse `status`, `responseCode`, and `responseMessage`.

### Validation Failure: Missing Device Fingerprint For Approve

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "deviceFingerPrint and bankAccountUniqueId required for approve"
}
```

Client handling: send `deviceFingerPrint` and exactly one payer account identifier for `APPROVE`.

### Validation Failure: Invalid Field Format

Example: `merchantRequestId` has unsupported characters or exceeds 35 characters.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "[RegexValidation \"merchant request id regex failed\"]"
}
```

Client handling: correct the request and do not retry unchanged.

### Validation Failure: Missing Mandate Identifier

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "umn or mandateRequestId is mandatory"
}
```

Client handling: send the pending `mandateRequestId`, or send `umn` for an existing mandate when UMN is available.

### Authentication, Signature, Or Encryption Failure

Bad merchant headers, invalid signature, invalid/decryption-failed JWE, untrusted signed content, non-whitelisted IP, or timestamp problems can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the encrypted payload decrypts but does not parse as the expected signed payload, Newton can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

Client handling: verify the encryption key id, signature key, `iat`, `x-timestamp`, merchant headers, raw body used for signing, and IP allow-listing.

### Merchant Configuration Failure

If the merchant or sub-merchant is configured with allowed/blocked API lists and this API is not enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: contact Newton onboarding/support to enable `approveMandateS2S` for the merchant or sub-merchant.

### Lookup Failure: Pending Mandate Not Found

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

Client handling: check whether the `mandateRequestId` is the pending mandate action id, whether the action already completed or expired, and whether the `merchantCustomerId` belongs to the same customer.

### Lookup Failure: Account Not Found

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

Client handling: refresh the customer's linked accounts and retry only after selecting a valid `accountReferenceId` or `bankAccountUniqueId`.

### Business Validation Failure: Mandate Expired

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate has expired"
}
```

Client handling: do not retry the same pending mandate action. Start a new mandate flow if the customer still wants to proceed.

### Business Validation Failure: Device Fingerprint Mismatch

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

Client handling: re-bind or refresh the customer's device context before retrying.

### Business Validation Failure: Account Or VPA Mismatch

For a mismatched account reference:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid accountReferenceId"
}
```

For a mismatched bank account unique id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid bankAccountUniqueId"
}
```

For a supplied payee VPA that does not match the mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "CustomerVpa does not match"
}
```

Client handling: do not override the stored mandate/account context. Fetch mandate/account details again and send the identifier matching the pending mandate.

### Business Validation Failure: Invalid Credential Block

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid credBlock"
}
```

Client handling: regenerate the credential block through the UPI credential flow. Do not retry the same malformed credential payload.

### Business Rule Failure: Blocked Mandate For Account/MCC/Purpose

For certain credit-card or credit-line mandate combinations, Newton can reject the action after evaluating account type, payee MCC, purpose, and merchant configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "JPCC",
  "responseMessage": "Mandate creation for IPO and blocked mcc through credit card is not allowed"
}
```

Client handling: treat this as a terminal business failure for the selected account or mandate purpose.

### Downstream Failure: NPCI Timeout Or Unavailable

If the downstream response is unavailable or times out in a way Newton cannot convert to a mandate result:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "NPCI service is not reachable at the moment (U09)"
}
```

The `U09` suffix is a representative downstream timeout code; Newton uses the timeout code available on the failed NPCI attempt.

Client handling: do not create a new logical mandate approval immediately. Check mandate status/callback first. Retry the same logical action only if the mandate is still pending and retry is allowed by your integration runbook.

### Unexpected Error

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry only after checking status or after Newton confirms the operation did not reach NPCI. Include `x-request-id`, `merchantCustomerId`, `merchantRequestId`, and `mandateRequestId` when raising support cases.

## Retry And Idempotency Guidance

`merchantRequestId` is required and is stored with the approve/decline attempt, but this route does not perform a register-intent-style idempotency lookup by `merchantRequestId`. The pending mandate action is resolved from `mandateRequestId` or `umn`.

Recommended client behavior:

- Generate one `merchantRequestId` for one logical approve/decline attempt and store it with the pending mandate action.
- Do not retry with a different `merchantRequestId` after a timeout unless the mandate status still shows the action is pending and Newton's runbook allows retry.
- If the HTTP request fails before a decrypted body is received, first check mandate status or wait for callback before retrying.
- Treat `gatewayResponseStatus = SUCCESS` as approved and `gatewayResponseStatus = DECLINED` as declined.
- Treat `gatewayResponseStatus = FAILURE` as a processed gateway failure, even when top-level `status` is `SUCCESS`.
- Treat validation, account/device mismatch, expired mandate, and blocked-MCC/account failures as terminal until the underlying input or customer state changes.

## Source References

- Route type: [Newton.App.Routes.Core.ServerToServerAPIs](../../src/Newton/App/Routes/Core.hs:601)
- Route handler and S2S signature invocation: [approveMandateS2S](../../src/Newton/App/Routes/Core.hs:3153)
- Request envelope type: [Newton.Types.API.RequestBody.EncRequest](../../src/Newton/Types/API/RequestBody.hs:48)
- Response envelope type: [Newton.Types.API.RequestBody.EncResponse](../../src/Newton/Types/API/RequestBody.hs:69)
- Request body extraction and S2S payload verification: [getReqBody](../../src/Newton/Utils/Routes.hs:40), [merchantPayloadVerificationS2S](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- JWE/JWS payload verification errors: [payloadVerification](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- S2S signature, timestamp, merchant config, API enablement, and IP checks: [merchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [API enablement helpers](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- S2S response signing/encryption wrapper and response headers: [flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:31)
- Request and response types: [ApproveMandateS2SRequest](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2431), [MandateApproveS2SResponsePayload](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2489), [ApproveMandateS2SResponse](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2539)
- Request validation rules: [ApproveMandateS2SRequest validation](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2467), [common validators](../../src/Newton/Validation/Common.hs:168)
- Transformer route and approve-specific request checks: [approveMandateTransformerS2SRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:725)
- Core request and response transformer helpers: [mkApproveMandateS2STransformerResponse](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1281), [mkApproveMandateCoreRequest](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1301)
- Product flow: [approveMandateCoreRoute](../../src/Newton/Product/Merchant/Mandate/ApproveMandate.hs:14)
- Mandate lookup, validation, update, NPCI call, and response shaping: [getDBrecordsForApproveMandate](../../src/Newton/Product/Merchant/Mandate/Helper.hs:2043), [validateApproveMandate](../../src/Newton/Product/Merchant/Mandate/Helper.hs:1927), [updateMandateApproveDetails](../../src/Newton/Product/Merchant/Mandate/Helper.hs:1946), [callNPCIForApproveMandate](../../src/Newton/Product/Merchant/Mandate/Helper.hs:2095), [mkApproveMandateResponse](../../src/Newton/Product/Merchant/Mandate/Helper.hs:1978)
- Account, device, VPA, and mandate-history lookup helpers: [getAccount](../../src/Newton/Utils/DB.hs:540), [findDeviceFromMerchantCustomer](../../src/Newton/Utils/DB.hs:654), [isValidDeviceFingerPrint](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387), [validateCustomerVpaMandate](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1598), [getMandateHistoryFromUmnOrUpiReqId](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2253)
- Credential block handling: [getCredBlockFromRequest](../../src/Newton/Utils/Transformers/Transformer.hs:2123)
- Gateway response mapping and versioned response fields: [getMandateApproveGatewayResp](../../src/Newton/Utils/Utils.hs:1470), [response field versioning](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1289)
- Enums and storage statuses: [ApproveMandateRequestType](../../src/Newton/Types/Storage/Mandate.hs:99), [MandateType](../../src/Newton/Types/Storage/Mandate.hs:103), [MandateHistoryStatus](../../src/Newton/Types/Storage/MandateHistory.hs:78)
- Shared error response type and constants: [ErrorResponse](../../src/Newton/Types/API/Common.hs:12), [API error constants](../../src/Newton/Constants/APIErrorCode.hs:43), [API error throw helpers](../../src/Newton/Utils/API.hs:62)
