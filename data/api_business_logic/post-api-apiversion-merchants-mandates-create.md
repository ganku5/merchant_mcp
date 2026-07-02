# Create Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/create`

## Overview

Create Mandate is a merchant server-to-server API used to initiate a payer-side UPI mandate creation request through Newton.

The merchant calls this API after the customer profile, device, VPA, and bank account are already available in Newton. Newton verifies the merchant S2S envelope, validates the customer's device fingerprint and account, creates the Newton mandate and mandate history records, sends the mandate request to the UPI/NPCI wrapper, and returns the gateway creation status.

For this S2S route, the implementation supports only payer-initiated creation: send `initiatedBy: "PAYER"`. The response can be `SUCCESS` at the API envelope level while the mandate itself is still `PENDING`; clients must interpret `payload.gatewayResponseStatus` for the mandate creation state.

## Business Use Case

Use this API when the merchant backend needs to create a UPI mandate for an already-onboarded customer from a server-to-server flow, for example:

- Subscription or recurring payment setup where the customer authorizes the mandate from the merchant app.
- One-time mandate setup where funds may be blocked up to the authorized amount.
- Intent or QR mandate creation where NPCI-required transaction metadata such as `mcc`, `transactionReference`, `purpose`, `initiationMode`, and `currency` must be bound to the request.
- Pre-approved mandate creation where the merchant is enabled to send `isPreApproved: true` instead of an MPIN credential block.
- UPI Lite autopay mandate creation only when the merchant/customer/account are enabled for that specific flow.

Do not use this API to onboard a customer, link an account, create a VPA, execute an existing mandate, notify an execution cycle, pause/unpause a mandate, or check mandate status. Those are separate APIs.

## Integration Flow

1. Merchant completes customer onboarding, device binding, account linking, and VPA setup.
2. Merchant collects the mandate details and either a UPI credential block or pre-approved authorization signal.
3. Merchant sends the encrypted or signed S2S request with a unique `upiRequestId`.
4. Newton unwraps the request envelope and verifies merchant headers, API access, timestamp, signature, and optional IP allowlist.
5. Newton loads the merchant customer, customer, device, VPA, and account records.
6. Newton validates field formats, device fingerprint, recurrence rules, validity dates, mandate business rules, account eligibility, duplicate `upiRequestId`, and payee VPA configuration.
7. Newton creates a mandate and mandate-history record, sends the create request to the UPI/NPCI wrapper, and maps the resulting mandate status to `payload.gatewayResponseStatus`.
8. Merchant stores `gatewayMandateId`/`orgMandateId`, `umn`, `gatewayReferenceId`, `merchantRequestId`, and `gatewayResponseStatus`, then reconciles final status through mandate callbacks or the mandate status API.

Important identifiers:

- `upiRequestId`: Merchant-supplied UPI transaction id for this mandate creation. This route uses it for duplicate detection.
- `merchantRequestId`: Merchant order/reference id. It is returned in the response and stored in mandate metadata, but this route's duplicate check is based on `upiRequestId`.
- `gatewayMandateId` and `orgMandateId`: Newton returns both as the mandate's UPI request id. Use this id in follow-up mandate APIs.
- `gatewayReferenceId`: Newton/NPCI response reference id generated for the create request.
- `umn`: Unique mandate number. If omitted, Newton generates one using the payer VPA handle; if supplied, it must be unique and have the expected domain.

## Handler Path

The route is mounted under `/api/{apiVersion}` in the main `ServerToServerAPIs` route group.

The request path is:

1. `getReqBody` unwraps `EncRequest CreateMandateS2SRequest` through S2S merchant payload verification.
2. `merchantSignatureVerificationV2` validates `iat` for signed/encrypted bodies, merchant headers, API allow/block configuration, request timestamp, signature, and merchant-customer/customer context.
3. `createMandateS2STransformerRoute` validates the decrypted request body and transforms it to `CreateMandateCoreRequest`.
4. `validateS2SMandateRequest` validates the merchant customer's stored device against `deviceFingerPrint` or `fallbackDeviceFingerPrint`.
5. `createMandateCoreRoute` loads DB records, applies defaults, validates mandate business rules, creates mandate records, calls the mandate wrapper, and builds the core response.
6. `mkCreateMandateCoreS2SResponse` maps the core response to the S2S response and echoes `udfParameters`.
7. `flowWithTrace` signs or encrypts the response according to the merchant response strategy.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/create
```

Payloads use Newton's standard server-to-server request and response envelope. Examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Current request timestamp used for S2S verification. |
| `x-merchant-signature` | Required when sending the configured unsigned/plain JSON body protected by header signature. For JWS/JWE modes, request signing/encryption is carried in the envelope. |
| `x-api-version` | Use the response version shared during onboarding. If omitted or invalid, Newton uses base version `0`. Send `2` or higher to receive all currently version-gated create-mandate response fields. |
| `x-request-id` | Optional request id for troubleshooting and reconciliation. Newton generates one if omitted. |
| `x-session-id` | Optional session id. Defaults to `x-request-id` when omitted. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Path version segment configured for the merchant. |

## Authentication and Payload Handling

The route request type is `EncRequest CreateMandateS2SRequest`. Depending on merchant configuration, the wire request can be:

- JWE encrypted payload containing a signed payload.
- JWS signed payload.
- Plain decrypted JSON payload accepted only where merchant configuration permits it and protected by `x-merchant-signature`.

For signed or encrypted request bodies, the decrypted business payload must include `iat`, and `iat` must pass timestamp validation. Plain-body header-signature mode does not validate request-body `iat`, but still requires merchant headers, `x-timestamp`, and a valid header signature.

The response is returned according to the merchant response strategy:

- JWS response when response strategy is `JWS`.
- JWE response when response strategy is `JWS_AND_JWE`.
- Plain decrypted JSON body with `X-Response-Signature` when using the non-JWS/JWE response path.

The examples in this guide are decrypted response bodies, not the exact encrypted wire envelope.

## Request

### Required Minimum

For a standard payer-initiated UPI mandate, send at least:

```json
{
  "merchantCustomerId": "CUST10001",
  "merchantRequestId": "MANDATE10001",
  "upiRequestId": "MND1000120260801",
  "amount": "999.00",
  "bankAccountUniqueId": "acc_hash_9f8e7d",
  "deviceFingerPrint": "stored-device-fingerprint",
  "payerVpa": "asha@okbank",
  "payeeVpa": "merchant@newton",
  "recipientName": "Example Internet Pvt Ltd",
  "mandateName": "Monthly subscription",
  "initiatedBy": "PAYER",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "1",
  "validityStart": "2026/8/1",
  "validityEnd": "2027/8/1",
  "amountRule": "MAX",
  "transactionType": "UPI_MANDATE",
  "credBlock": "{\"cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\"}}}",
  "iat": "1782998400000"
}
```

Use `accountReferenceId` instead of `bankAccountUniqueId` only when that is the account identifier returned for your integration. For signed/encrypted production calls, replace the example `iat` with the current request timestamp in the format agreed during onboarding.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer id. Newton uses it during signature verification to load the merchant customer and customer records. Max 256 characters. |
| `merchantRequestId` | string | Yes | No default. | Merchant order/reference id. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Echoed in response. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this mandate creation. Max 35 alphanumeric characters. Duplicate `upiRequestId` is rejected. |
| `amount` | string | Yes | No default. | Mandate amount in two-decimal format, for example `999.00`. Must be greater than zero and within configured mandate amount limits. |
| `bankAccountUniqueId` | string | Conditional | No default. | Account hash/unique id returned by account APIs. Send either this or `accountReferenceId`, according to the account identifier used by your integration. |
| `accountReferenceId` | string | Conditional | No default. | Newton account id or migrated account reference. Required for some GPay ICICI flows; when it is a migrated account reference, also send `ifsc`. |
| `ifsc` | string | Conditional | No default. | Required only for migrated-account lookup flows where `accountReferenceId` is not the Newton account id. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint for the merchant customer's stored device. Although typed optional, S2S mandate validation requires it. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate device fingerprint accepted by the same validation check. |
| `payerVpa` | string | Yes | No default. | Customer/payer VPA. Must be 3 to 255 characters and match the VPA format. The VPA must already exist for the customer. |
| `payeeVpa` | string | Yes | No default. | Payee VPA for the mandate. May also be checked against merchant configuration `payeeVpasForMandateCreation`. |
| `recipientName` | string | Yes | No default. | Payee/recipient display name included in the mandate request. Must be non-empty. |
| `mandateName` | string | Yes | No default. | Mandate display name stored on the mandate and returned in response. Must be non-empty. |
| `initiatedBy` | string enum | Yes | No default. | Must be `PAYER` for this S2S route. `PAYEE` is rejected by business validation. |
| `credBlock` | string | Conditional | No default. | String-encoded UPI credential block. Required for normal payer-authorized creation unless using a valid `isPreApproved: true` flow. |
| `isPreApproved` | boolean | Conditional | No default. | Set `true` only for enabled pre-approved creation flows where `credBlock` is intentionally omitted. Do not send `false` as a substitute for `credBlock`. |
| `recurrencePattern` | string enum | Yes | No default. | Allowed values: `ONETIME`, `DAILY`, `WEEKLY`, `FORTNIGHTLY`, `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, `YEARLY`, `ASPRESENTED`. |
| `recurrenceRule` | string enum | Conditional | Omit for `ONETIME`, `DAILY`, and `ASPRESENTED`. | Required for recurrence patterns that need a debit rule. Allowed values: `ON`, `AFTER`, `BEFORE`. |
| `recurrenceValue` | string integer | Conditional | Omit for `ONETIME`, `DAILY`, and `ASPRESENTED`. | Debit day/value. Required with `recurrenceRule` for weekly and longer recurrence patterns. |
| `validityStart` | string | Yes | No default. | Mandate validity start date. Use `YYYY/M/D`, for example `2026/8/1`. Start date must be today or future, subject to code-level grace handling. |
| `validityEnd` | string | Yes | No default. | Mandate validity end date. Use `YYYY/M/D`. Must be after `validityStart`; `ONETIME` mandates must be within 90 days. |
| `amountRule` | string enum | Yes | No default. | `EXACT` or `MAX`. |
| `transactionType` | string enum | Yes | No default. | Allowed values: `UPI_MANDATE`, `QR_MANDATE`, `INTENT_MANDATE`, `P2M_MANDATE`, `PREPAID_VOUCHER`, `LITE_MANDATE`. |
| `blockFund` | string boolean | No | Defaults to `"false"`. | `"true"` or `"false"`. Some recurrence and purpose combinations restrict this value. |
| `payerRevocable` | string boolean | No | Defaults from merchant/MCC configuration for payer mandates. | `"true"` or `"false"`. Non-one-time payer mandates usually must remain revocable unless purpose/configuration allows otherwise. |
| `shareToPayee` | string boolean | No | Defaults to `"true"`. | `"true"` or `"false"`. `false` is restricted for some recurrence patterns. |
| `makeAsync` | string boolean | No | Defaults to `"false"`. | `"true"` submits through the async mandate wrapper path. Reconcile through callbacks/status. |
| `expiry` | string integer | No | Do not send for this payer S2S route. | Expiry is accepted only for payee-initiated validation, but this route rejects `initiatedBy: "PAYEE"`. Sending `expiry` with `PAYER` fails. |
| `mcc` | string | Conditional | For non-Intent/QR flows, omitted payee MCC is derived from merchant/default behavior. | Four-digit payee MCC. Required for `QR_MANDATE` and `INTENT_MANDATE`. |
| `currency` | string | Conditional | No default. | Required for `QR_MANDATE` and `INTENT_MANDATE`, for example `INR`. |
| `transactionReference` | string | Conditional | If omitted for non-Intent/QR flows, mandate reference falls back to sanitized `merchantRequestId`. | Required for `QR_MANDATE` and `INTENT_MANDATE`. Credit-card bill flows may resolve/override this internally. |
| `purpose` | string | No | Defaults to `"14"` in mandate creation payload when omitted. | Two-character uppercase alphanumeric NPCI purpose code. Certain purposes trigger special validation. |
| `initiationMode` | string | Conditional | Defaults to `"00"` in the mandate payload when omitted. | Two-character initiation mode. Required for `QR_MANDATE` and `INTENT_MANDATE`. |
| `refUrl` | string | No | Response uses Newton's default ref URL when omitted. Mandate metadata may use configured NPCI ref URL. | Merchant/order reference URL. Must be non-empty if supplied. |
| `refCategory` | string | No | Mandate metadata may use configured NPCI ref category when omitted. | Merchant reference category. Must be non-empty if supplied. |
| `remarks` | string | No | Defaults to `"No Remarks"`. | Customer/payment note. 1 to 255 characters, with restricted characters. |
| `udfParameters` | string | No | Omitted from response when not supplied. | String-encoded JSON object for merchant metadata. Echoed in success response. |
| `clVersion` | string | No | No default. | Customer library/app credential version sent to the mandate wrapper when supplied. |
| `umn` | string | No | Newton generates a UMN when omitted. | Optional merchant-supplied UMN. Must be unique and use the expected merchant/VPA domain. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. | Issued-at timestamp used by request verification. Required for JWS/JWE payloads. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not returned when omitted.

- `blockFund`: omitted behaves as `"false"`.
- `shareToPayee`: omitted behaves as `"true"`.
- `makeAsync`: omitted behaves as `"false"` and is returned as `"false"` in the response.
- `remarks`: omitted becomes `"No Remarks"`.
- `payerRevocable`: omitted is derived from merchant/MCC configuration for payer mandates.
- `purpose`: omitted becomes `"14"` when creating the mandate payload.
- `initiationMode`: omitted becomes `"00"` in the stored mandate payload.
- `umn`: omitted is generated by Newton from the payer VPA handle.
- `transactionReference`: omitted falls back to sanitized `merchantRequestId` as mandate reference for non-Intent/QR flows.
- `expiry`: do not send for successful S2S payer create flows; it is omitted from successful responses.
- `gatewayPayerResponseCode`: response field is included only when `x-api-version > 0` and the payer response code is available.
- `payeeIfsc`: response field is included only when `x-api-version > 1` and payee IFSC is available.

### Validation Notes

Newton validates the decrypted body before mandate product logic:

- `amount` must match `^[0-9]+\.[0-9][0-9]$` and be greater than zero.
- `merchantRequestId` must be 1 to 35 characters and match the allowed id pattern.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `merchantCustomerId` must be 1 to 256 characters and match the allowed customer-id pattern.
- `payerVpa` and `payeeVpa` must match VPA format and length rules.
- String boolean fields must be `"true"` or `"false"` when supplied.
- `mcc` must be exactly four digits when supplied.
- `purpose` must be exactly two uppercase alphanumeric characters when supplied.
- `initiationMode` must be exactly two alphanumeric characters when supplied.
- `expiry`, if supplied, must be an integer from `1` to `64800`, but it is not valid with `initiatedBy: "PAYER"`.
- `validityStart` and `validityEnd` must parse as dates. Use slash format `YYYY/M/D` because product logic parses that format.
- `udfParameters` must be a JSON-object string and must not contain disallowed special characters.
- `remarks` must be 1 to 255 characters and match the remarks regex.

Product/business validation then applies mandate rules:

- `initiatedBy` must be `PAYER`.
- `deviceFingerPrint` is required and must match the stored device fingerprint, or `fallbackDeviceFingerPrint` must match.
- Either a valid `credBlock` or an enabled `isPreApproved: true` flow is expected.
- The payer VPA must exist for the merchant customer/customer.
- The account must resolve from `bankAccountUniqueId` or `accountReferenceId`.
- `payeeVpa` must be in the merchant's allowed payee VPA list when that configuration exists.
- `upiRequestId` must not already belong to an existing mandate.
- `ONETIME`, `DAILY`, and `ASPRESENTED` must not include `recurrenceRule` or `recurrenceValue`.
- `WEEKLY` requires `recurrenceRule` and `recurrenceValue` from `1` to `7`.
- `FORTNIGHTLY` requires `recurrenceRule` and `recurrenceValue` from `1` to `16`.
- `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, and `YEARLY` require `recurrenceRule` and `recurrenceValue` from `1` to `31`.
- `validityEnd` must be after `validityStart`; for `ONETIME`, the difference must be less than or equal to 90 days.
- `QR_MANDATE` and `INTENT_MANDATE` require `mcc`, `transactionReference`, `purpose`, `initiationMode`, and `currency`.
- UPI Lite autopay mandates require the Lite-specific recurrence, purpose, amount rule, active Lite account, and active-mandate limits configured for the merchant.

## String-Encoded Nested Values

This request type does not expose nested JSON objects directly. Two fields commonly carry nested data as strings:

| Field | Format | Notes |
| --- | --- | --- |
| `credBlock` | JSON string | Contains UPI credential material from the customer app/SDK. Newton decodes it into NPCI credential data. Invalid JSON or unsupported credential combinations can fail with `INVALID_DATA` or internal error depending on the branch. |
| `udfParameters` | JSON-object string | Merchant metadata. It is validated as a JSON object string and echoed in successful responses. |

## Request Examples

### Monthly Payer-Authorized Mandate

```json
{
  "merchantCustomerId": "CUST10001",
  "merchantRequestId": "MANDATE10001",
  "upiRequestId": "MND1000120260801",
  "amount": "999.00",
  "bankAccountUniqueId": "acc_hash_9f8e7d",
  "deviceFingerPrint": "stored-device-fingerprint",
  "payerVpa": "asha@okbank",
  "payeeVpa": "merchant@newton",
  "recipientName": "Example Internet Pvt Ltd",
  "mandateName": "Monthly subscription",
  "initiatedBy": "PAYER",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "1",
  "validityStart": "2026/8/1",
  "validityEnd": "2027/8/1",
  "amountRule": "MAX",
  "transactionType": "UPI_MANDATE",
  "credBlock": "{\"cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\"}}}",
  "payerRevocable": "true",
  "blockFund": "false",
  "shareToPayee": "true",
  "remarks": "Monthly subscription",
  "refUrl": "https://merchant.example/mandates/MANDATE10001",
  "udfParameters": "{\"plan\":\"gold\",\"source\":\"app\"}",
  "iat": "1782998400000"
}
```

### Pre-Approved One-Time Mandate

Use this only when the merchant and flow are enabled for pre-approved mandate creation.

```json
{
  "merchantCustomerId": "CUST10002",
  "merchantRequestId": "MANDATE10002",
  "upiRequestId": "MND1000220260801",
  "amount": "5000.00",
  "accountReferenceId": "acc_1234567890",
  "deviceFingerPrint": "stored-device-fingerprint",
  "payerVpa": "rahul@okbank",
  "payeeVpa": "merchant@newton",
  "recipientName": "Example Investments",
  "mandateName": "One time block mandate",
  "initiatedBy": "PAYER",
  "recurrencePattern": "ONETIME",
  "validityStart": "2026/8/1",
  "validityEnd": "2026/8/20",
  "amountRule": "EXACT",
  "transactionType": "UPI_MANDATE",
  "isPreApproved": true,
  "blockFund": "true",
  "payerRevocable": "true",
  "shareToPayee": "true",
  "purpose": "14",
  "remarks": "One time mandate",
  "iat": "1782998400000"
}
```

### Intent Mandate With NPCI Transaction Metadata

For `INTENT_MANDATE` or `QR_MANDATE`, include `mcc`, `transactionReference`, `purpose`, `initiationMode`, and `currency`.

```json
{
  "merchantCustomerId": "CUST10003",
  "merchantRequestId": "MANDATE10003",
  "upiRequestId": "MND1000320260801",
  "amount": "1499.00",
  "bankAccountUniqueId": "acc_hash_445566",
  "deviceFingerPrint": "stored-device-fingerprint",
  "payerVpa": "meera@okbank",
  "payeeVpa": "merchant@newton",
  "recipientName": "Example Services",
  "mandateName": "App membership",
  "initiatedBy": "PAYER",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "5",
  "validityStart": "2026/8/5",
  "validityEnd": "2027/8/5",
  "amountRule": "MAX",
  "transactionType": "INTENT_MANDATE",
  "mcc": "4899",
  "transactionReference": "APP-MEM-10003",
  "purpose": "14",
  "initiationMode": "04",
  "currency": "INR",
  "credBlock": "{\"cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\"}}}",
  "remarks": "App membership mandate",
  "iat": "1782998400000"
}
```

### GPay ICICI Migrated Account Lookup

Some migrated-account flows require `accountReferenceId` plus `ifsc` instead of `bankAccountUniqueId`.

```json
{
  "merchantCustomerId": "CUST10004",
  "merchantRequestId": "MANDATE10004",
  "upiRequestId": "MND1000420260801",
  "amount": "750.00",
  "accountReferenceId": "migrated-account-998877",
  "ifsc": "HDFC0001234",
  "deviceFingerPrint": "stored-device-fingerprint",
  "fallbackDeviceFingerPrint": "alternate-stored-device-fingerprint",
  "payerVpa": "nisha@okbank",
  "payeeVpa": "merchant@newton",
  "recipientName": "Example Utilities",
  "mandateName": "Utility autopay",
  "initiatedBy": "PAYER",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "10",
  "validityStart": "2026/8/10",
  "validityEnd": "2027/8/10",
  "amountRule": "MAX",
  "transactionType": "UPI_MANDATE",
  "credBlock": "{\"cred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\"}}}",
  "iat": "1782998400000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. `SUCCESS` means Newton processed the create request and built a business response; it does not always mean the mandate is active. |
| `responseCode` | string | API response code. Success envelope value is `SUCCESS`. |
| `responseMessage` | string | API response message. Success envelope value is `SUCCESS`. |
| `payload` | object | Create mandate result. Present on success envelope responses. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `amount` | string | Mandate amount formatted with two decimals. |
| `bankAccountUniqueId` | string | Payer account hash/unique id used for mandate creation. |
| `blockFund` | string | `"true"` or `"false"` after defaults/business logic. |
| `expiry` | string | Omitted for successful S2S payer-created mandates. |
| `gatewayMandateId` | string | Mandate UPI request id. Same value as `orgMandateId` for this create response. |
| `gatewayPayerResponseCode` | string | Payer-side NPCI response code when available and `x-api-version > 0`; otherwise omitted. |
| `gatewayReferenceId` | string | Newton/NPCI reference id for the create request. |
| `gatewayResponseCode` | string | Mandate gateway code. `01` means creation is pending for payer-initiated create; `00` means success; other values indicate failure/decline conditions. |
| `gatewayResponseMessage` | string | Human-readable gateway message mapped from mandate status/NPCI response. |
| `gatewayResponseStatus` | string | Mandate creation status: `PENDING`, `SUCCESS`, or `FAILURE`. Use this for mandate-state handling. |
| `initiatedBy` | string | Mandate initiator. For this route, successful responses are `PAYER`. |
| `makeAsync` | string | `"true"` or `"false"` after defaults. |
| `mandateTimestamp` | string | Mandate creation timestamp. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id from request. |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantRequestId` | string | Merchant request id from request. |
| `mandateName` | string | Mandate name from request. Omitted only if unavailable in stored mandate data. |
| `orgMandateId` | string | Mandate id to use in follow-up mandate APIs. Same as `gatewayMandateId` for create. |
| `payeeIfsc` | string | Payee IFSC when available and `x-api-version > 1`; otherwise omitted. |
| `payeeMcc` | string | Payee MCC derived from request, merchant config, or default behavior. |
| `payeeName` | string | Payee name when available for the mandate role/status. |
| `payeeVpa` | string | Payee VPA from request. |
| `payerName` | string | Payer account/customer name when available for the mandate role/status. |
| `payerRevocable` | string | `"true"` or `"false"` after defaults/business logic. |
| `payerVpa` | string | Payer VPA from request. |
| `recurrencePattern` | string | Mandate recurrence pattern. |
| `recurrenceRule` | string | Recurrence rule when applicable. Omitted for `ONETIME`, `DAILY`, and `ASPRESENTED`. |
| `recurrenceValue` | string | Recurrence value when applicable. |
| `refUrl` | string | Request `refUrl` or Newton default ref URL. |
| `remarks` | string | Request remarks or default remarks. |
| `role` | string | Stored mandate role. For this route, usually `PAYER`. |
| `amountRule` | string | `EXACT` or `MAX`. |
| `shareToPayee` | string | `"true"` or `"false"` after defaults/business logic. |
| `transactionType` | string | Mandate transaction type stored for the request. |
| `umn` | string | Unique mandate number when generated or supplied and available. |
| `validityEnd` | string | Mandate validity end date. |
| `validityStart` | string | Mandate validity start date. |

### Example Success Envelope With Pending Mandate Creation

For payer-initiated create, `PENDING` is a normal outcome. Treat it as "request accepted/sent", not as final mandate activation.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "999.00",
    "bankAccountUniqueId": "acc_hash_9f8e7d",
    "blockFund": "false",
    "gatewayMandateId": "MND1000120260801",
    "gatewayReferenceId": "624511987432",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate Create Request Sent Successfully",
    "gatewayResponseStatus": "PENDING",
    "initiatedBy": "PAYER",
    "makeAsync": "false",
    "mandateTimestamp": "2026-08-01T10:15:30+05:30",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST10001",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "MANDATE10001",
    "mandateName": "Monthly subscription",
    "orgMandateId": "MND1000120260801",
    "payeeMcc": "0000",
    "payeeName": "Example Internet Pvt Ltd",
    "payeeVpa": "merchant@newton",
    "payerName": "Asha Sharma",
    "payerRevocable": "true",
    "payerVpa": "asha@okbank",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "1",
    "refUrl": "https://merchant.example/mandates/MANDATE10001",
    "remarks": "Monthly subscription",
    "role": "PAYER",
    "amountRule": "MAX",
    "shareToPayee": "true",
    "transactionType": "UPI_MANDATE",
    "umn": "8f7b2d3a4c5e6f708192a3b4c5d6e7f8@okbank",
    "validityEnd": "2027/08/01",
    "validityStart": "2026/08/01"
  },
  "udfParameters": "{\"plan\":\"gold\",\"source\":\"app\"}"
}
```

### Example Success Envelope With Gateway Failure

The API envelope can still be `SUCCESS` when the downstream mandate result is terminal failure. In that case, handle the mandate as failed based on `payload.gatewayResponseStatus`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "999.00",
    "bankAccountUniqueId": "acc_hash_9f8e7d",
    "blockFund": "false",
    "gatewayMandateId": "MND1000120260802",
    "gatewayReferenceId": "624511987433",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "Mandate Request Failed",
    "gatewayResponseStatus": "FAILURE",
    "initiatedBy": "PAYER",
    "makeAsync": "false",
    "mandateTimestamp": "2026-08-01T10:17:30+05:30",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST10001",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "MANDATE10002",
    "mandateName": "Monthly subscription",
    "orgMandateId": "MND1000120260802",
    "payeeMcc": "0000",
    "payeeVpa": "merchant@newton",
    "payerRevocable": "true",
    "payerVpa": "asha@okbank",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "1",
    "refUrl": "https://merchant.example/mandates/MANDATE10002",
    "remarks": "Monthly subscription",
    "role": "PAYER",
    "amountRule": "MAX",
    "shareToPayee": "true",
    "transactionType": "UPI_MANDATE",
    "umn": "7e6d5c4b3a291807f6e5d4c3b2a19087@okbank",
    "validityEnd": "2027/08/01",
    "validityStart": "2026/08/01"
  }
}
```

### Status Interpretation

Use both layers:

- Top-level `status: "SUCCESS"` and `responseCode: "SUCCESS"` mean Newton processed the API call and returned a create-mandate business result.
- `payload.gatewayResponseStatus: "PENDING"` means the payer-initiated mandate request was sent and final activation/decline is pending. Wait for callback or call mandate status.
- `payload.gatewayResponseStatus: "SUCCESS"` means the mandate creation is successful/active.
- `payload.gatewayResponseStatus: "FAILURE"` means mandate creation failed or was declined at the gateway/bank/NPCI layer, even though the API envelope is `SUCCESS`.

For non-success top-level bodies, use `responseCode` for programmatic handling and `responseMessage` for diagnostics. HTTP status can vary by layer; validation and business failures may be returned with HTTP 200 error bodies in this codebase.

## Error Handling

Failure responses use the standard Newton error body shape after decryption when the response is wrapped by the configured S2S response strategy:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

### Request Validation Failures

Validation runs before product logic. Fix the request and send a new request; do not retry unchanged validation failures.

Invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Invalid `merchantRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchant request id regex failed\""
}
```

Invalid boolean string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "BoolStringValidation \"Parameter is not true or false\""
}
```

Invalid or missing recurrence rule/value:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "recurrenceValue and recurrenceRule are not valid"
}
```

### Authentication, Signature, Encryption, And Access Failures

These fail before mandate product logic. Check merchant ids, configured API access, timestamp freshness, request body canonicalization, key id, JWS/JWE format, IP allowlist, and signing/encryption keys. Retry only after correcting the envelope/auth issue.

Missing or mismatched request signature:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not enabled for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Signed or encrypted request without `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Encrypted payload that cannot be decrypted:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Encrypted payload that decrypts but does not parse as the expected signed payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

### Merchant Configuration Failures

Payee VPA not allowed by merchant configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid payeeVpa"
}
```

Account/MCC/purpose combination not allowed for mandate creation:

```json
{
  "status": "FAILURE",
  "responseCode": "JPCC",
  "responseMessage": "Mandate creation not allowed"
}
```

Client handling: do not retry unchanged. Verify merchant mandate enablement, allowed payee VPAs, account type, MCC, purpose, and any UPI Lite or pre-approved mandate feature flags with Newton.

### Lookup And Business Rule Failures

Missing account identifier:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory"
}
```

Merchant customer not found or inactive for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Payer VPA not found for the customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Vpa not found"
}
```

Device fingerprint mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

Missing `deviceFingerPrint`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "value required deviceFingerPrint"
}
```

Unsupported initiator:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Only initiatedBy Payer"
}
```

Missing `credBlock` for a normal payer-authorized mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "value required credBlock"
}
```

Invalid credential block:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid credBlock"
}
```

Duplicate `upiRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST"
}
```

Intent/QR mandate missing required metadata:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "mcc, transactionReference, purpose, intiationMode, currency are required for Intent & QR Mandates"
}
```

Invalid validity dates:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "end-date should be more than start-date"
}
```

Client handling: correct the request or customer/account state. For duplicate responses after a timeout, reconcile the original `upiRequestId` through mandate status/list or callbacks before creating a new mandate attempt.

### Downstream Or Gateway Failures

If the mandate wrapper returns a mandate record with a failure status, Newton can return a top-level `SUCCESS` response with `payload.gatewayResponseStatus: "FAILURE"`. Treat that as a failed mandate creation and do not retry the same business attempt blindly.

If the downstream wrapper response is unusable, missing required mandate data, or times out in a way Newton treats as service unavailable, the API can fail with a top-level error:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U91",
  "responseMessage": "NPCI service is not reachable at the moment (U91)"
}
```

Client handling: retry transient downstream failures with bounded exponential backoff only after checking whether the original `upiRequestId` produced a mandate record or callback. If a retry with the same `upiRequestId` returns `DUPLICATE_REQUEST`, reconcile status instead of creating a second mandate.

### Unexpected Failures

Unexpected missing stored records, database failures, encryption/decryption failures, malformed merchant configuration, Passetto/key/hash issues, or unhandled downstream conditions can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry transient 5xx-style failures with backoff if the request is otherwise valid. If repeated failures occur for the same customer or mandate, contact Newton with `x-request-id`, `merchantCustomerId`, `merchantRequestId`, `upiRequestId`, timestamp, and the decrypted error body.

## Retry, Idempotency, And Client Handling

- Generate a unique `upiRequestId` for each mandate creation attempt. This route checks duplicate mandates by `upiRequestId`.
- Keep `merchantRequestId` stable for the merchant order/reference and store it with the mandate, but do not rely on it as this route's deduplication key.
- If the client times out before receiving a response, first check callbacks or call the mandate status/list API for the original `upiRequestId`, `orgMandateId`, `umn`, or merchant reference before issuing another create request.
- If you retry with the same `upiRequestId` and receive `DUPLICATE_REQUEST`, treat it as evidence that Newton already has a mandate for that UPI request id; reconcile status instead of generating a new mandate immediately.
- Do not retry unchanged validation failures, authentication/encryption failures, API-not-enabled failures, device fingerprint mismatches, account/VPA lookup failures, or merchant-configuration failures.
- For `payload.gatewayResponseStatus: "PENDING"`, wait for mandate callbacks or poll mandate status according to the agreed operational cadence.
- For `payload.gatewayResponseStatus: "FAILURE"`, mark the mandate creation as failed unless Newton support or a later status response indicates otherwise.
- For transient `SERVICE_UNAVAILABLE_*` or `INTERNAL_SERVER_ERROR`, use bounded exponential backoff and avoid creating multiple mandates for the same customer/order without reconciliation.

## Source References

- API mount under `/api/{apiVersion}`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- S2S route definition for `/merchants/mandates/create`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:620)
- Server handler mapping: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:312)
- Create mandate S2S handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3225)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request body unwrap path: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- S2S response signing/encryption path: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:66)
- Merchant signature/API access verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- `iat` validation: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:168)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:716)
- S2S request type and validator: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:895)
- S2S response type: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1001)
- S2S to core request transformer: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1333)
- Core to S2S response transformer and version-gated fields: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1358)
- Create mandate core route and DB lookup/default flow: [src/Newton/Product/Merchant/Mandate/CreateMandate.hs](../../src/Newton/Product/Merchant/Mandate/CreateMandate.hs:47)
- Mandate wrapper call and downstream validation: [src/Newton/Product/Merchant/Mandate/CreateMandate.hs](../../src/Newton/Product/Merchant/Mandate/CreateMandate.hs:119)
- Mandate response builder: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:548)
- Create mandate business validation: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:598)
- Mandate payload construction and stored defaults: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:693)
- Device fingerprint and S2S mandate validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Duplicate mandate check: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:564)
- Recurrence, validity, Intent/QR, Lite, and mandate business validators: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1128)
- Request validation error wrapper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Field validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Account lookup behavior: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:541)
- Merchant customer/customer lookup during auth: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:107)
- Gateway response mapping for create mandate: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:1507)
- Success and generic error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
- Unauthorized/API access constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
- Duplicate, device fingerprint, VPA, user, and account error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:106)
