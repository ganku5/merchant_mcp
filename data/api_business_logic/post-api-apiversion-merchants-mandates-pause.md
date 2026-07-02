# Pause Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/pause`

## Overview

Pause Mandate is a server-to-server API used to pause or unpause an active UPI mandate for a merchant customer.

Despite the endpoint name, this API handles two actions selected by `requestType`:

- `PAUSE`: pause a mandate for a supplied pause date range.
- `UNPAUSE`: remove the existing pause state from a mandate.

Use this API after a mandate has already been created and is in an eligible state. The mandate is identified by `orgMandateId` or `umn`, and the request is bound to the same `merchantCustomerId`, device, optional payee VPA, and optional account identifiers stored for the mandate.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Pause Mandate helps merchants:

- Temporarily stop mandate executions for a known date range without revoking the mandate.
- Resume a previously paused mandate through `UNPAUSE`.
- Protect the operation by validating the merchant customer, registered device fingerprint, optional payee VPA, mandate account identifiers, and mandate state.
- Reconcile the pause or unpause attempt using Newton identifiers, gateway response fields, and callbacks/status APIs.

Call this API only for recurring mandates that are allowed to be paused. Loan/EMI or non-revocable mandates can be blocked by business rules, and one-time block-fund mandates cannot be paused or unpaused through this API.

## Integration Flow

1. Merchant identifies the mandate to pause or unpause using `orgMandateId` or `umn`.
2. Merchant backend generates a new unique `upiRequestId` for this pause/unpause attempt and a `merchantRequestId` for merchant-side tracking.
3. For `PAUSE`, merchant sends `pauseStart` and `pauseEnd`. For `UNPAUSE`, merchant omits both date fields.
4. Merchant sends the request through the Newton S2S envelope and merchant signature flow.
5. Newton verifies the envelope, merchant headers, signature, timestamp, API enablement, IP allow-list, and merchant customer context.
6. Newton validates request fields, mandate lookup, duplicate action id, device fingerprint, optional payee VPA, optional account ids, mandate status, and pause/unpause business rules.
7. Newton sends the pause/unpause request to the mandate wrapper/NPCI path, or completes an already effective unpause where the stored pause state can be resolved locally.
8. Newton returns a transport-level success response when the API call is processed. The mandate action outcome is in `payload.gatewayResponseCode`, `payload.gatewayResponseMessage`, and `payload.gatewayResponseStatus`.
9. Merchant stores returned identifiers and continues reconciliation through mandate status, callbacks, and mandate history APIs.

Important identifiers:

- `merchantCustomerId`: Merchant's customer id. Used for merchant-customer lookup and auth context.
- `upiRequestId`: Newton/UPI id for this pause or unpause action. Must be unique; duplicate action ids are rejected.
- `merchantRequestId`: Merchant reference for this API attempt. Echoed in the response.
- `orgMandateId`: Newton id of the original mandate. Send this or `umn`.
- `umn`: UPI mandate number. Send this or `orgMandateId`.
- `gatewayMandateId`: Newton id for the pause/unpause mandate-history action.
- `gatewayReferenceId`: Gateway/NPCI response reference for this action.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/pause
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
| `x-forwarded-for` | Required only when the merchant is configured with `whitelistedIps`; the first IP must be allow-listed. |
| `x-request-id` | Optional client request id for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

Path parameters:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API route version segment, for example `4` where supported for the merchant. |

Authentication, signature verification, IP allow-listing, API enablement checks, and response signing/encryption follow the Newton S2S process shared during onboarding.

The route accepts the standard Newton `EncRequest` envelope. Depending on onboarding, the wire request may be a JWE encrypted payload, a JWS signed payload, or an unsigned payload with request-signature headers. For encrypted or signed S2S requests, include `iat` in the decrypted business payload; Newton validates it as a timestamp.

Responses are returned in the configured response mode:

- `JWS`: response body is a signed JWS envelope.
- `JWS_AND_JWE`: response body is signed and then encrypted.
- Other configured strategies: response body is unsigned JSON with `X-Response-Signature`.

The decrypted examples below show the business JSON after envelope processing.

## Request

### Required Minimum

Pause a mandate by original mandate id:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-PAUSE-0001",
  "upiRequestId": "PAUSE202501010000000000000001",
  "orgMandateId": "MND202401010000000000000001",
  "requestType": "PAUSE",
  "pauseStart": "2025/1/10",
  "pauseEnd": "2025/1/31",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "iat": "1735689600000"
}
```

Unpause a mandate by original mandate id:

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UNPAUSE-0001",
  "upiRequestId": "UNPAUSE202501010000000000001",
  "orgMandateId": "MND202401010000000000000001",
  "requestType": "UNPAUSE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "iat": "1735689600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id associated with the mandate. Length: 1 to 256 characters. First character must be a letter, number, plus, slash, or equals sign; remaining characters may also include dot, underscore, and hyphen. |
| `merchantRequestId` | string | Yes | No default. | Merchant reference for this pause/unpause attempt. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `upiRequestId` | string | Yes | No default. | Unique UPI/Newton id for this pause/unpause action. Must be 1 to 35 alphanumeric characters. Reusing an existing mandate-history UPI request id returns `DUPLICATE_REQUEST`. |
| `requestType` | string | Yes | No default. | Action to perform. Allowed values: `PAUSE`, `UNPAUSE`. |
| `orgMandateId` | string | Conditional | No default. | Original Newton mandate id. Send either `orgMandateId` or `umn`. Must be 1 to 35 alphanumeric characters when supplied. |
| `umn` | string | Conditional | No default. | UPI mandate number. Send either `umn` or `orgMandateId`. Must be 34 to 70 characters and match the UMN pattern when supplied. |
| `pauseStart` | string | Conditional | No default. | Required for `PAUSE`; prohibited for `UNPAUSE`. Date parsed in `YYYY/M/D`, `YYYY/MM/DD`, or slash/dash-equivalent date form accepted by Newton date validation. Must be on or after mandate validity start. |
| `pauseEnd` | string | Conditional | No default. | Required for `PAUSE`; prohibited for `UNPAUSE`. Date parsed in the same format as `pauseStart`. Must be on or after `pauseStart` and on or before mandate validity end. |
| `deviceFingerPrint` | string | Yes for S2S | No default. | Registered device fingerprint. Newton requires it for this S2S API and validates it against the merchant customer's stored device. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate device fingerprint. Validation succeeds if either fingerprint matches the stored device fingerprint. |
| `payeeVpa` | string | No | No default. | Optional payee VPA guard. If supplied, it must match the mandate payee VPA. Must be 3 to 255 characters and match VPA format. |
| `bankAccountUniqueId` | string | No | No default. | Optional account guard. If supplied, it must match the mandate `bankAccountUniqueId` stored in mandate transaction info. Non-empty when supplied. |
| `accountReferenceId` | string | No | No default. | Optional account guard. If supplied, it must match the mandate account id. In ICICI PSP mode, non-prefixed values are resolved through account lookup and compared with the mandate account. Non-empty when supplied. |
| `ifsc` | string | Conditional | No default. | Used only in ICICI PSP account lookup when account identifiers require it. Non-empty when supplied. |
| `remarks` | string | No | Defaults to the platform default remarks in the response if mandate history has no remarks. | Optional note for the pause/unpause action. Length: 1 to 255 characters. May have leading spaces, then must start with a letter, number, or hyphen; remaining characters may include letters, numbers, spaces, and hyphens. |
| `clVersion` | string | No | No default. | Optional UPI Common Library version forwarded to downstream processing where applicable. Non-empty when supplied. |
| `credBlock` | string | No | No default. | Optional credential block field present in the shared type. The S2S pause flow does not require it in current code. Non-empty when supplied. |
| `isPreApproved` | boolean | No | No default. | Optional flag present in the shared type for PSP-specific flows. The S2S pause flow does not branch on it in current code. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant metadata. Must parse as a JSON object string and avoid disallowed characters. Echoed in the response. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by encrypted/signed request validation. Required for JWS/JWE payloads. |

### Defaults and Omitted Field Behavior

Fields not listed here have no implicit default and are not stored or returned when omitted.

- `orgMandateId` and `umn`: one is required for mandate lookup. If both are omitted, Newton returns `BAD_REQUEST` with `umn or OrgMandateId is mandatory`.
- `pauseStart` and `pauseEnd`: both are required for `PAUSE`; both must be omitted for `UNPAUSE`.
- `deviceFingerPrint`: required for this S2S endpoint. `fallbackDeviceFingerPrint` cannot replace the primary field, but it can help matching once the primary field is present.
- `payeeVpa`, `bankAccountUniqueId`, and `accountReferenceId`: optional guard fields. Send them only if you want Newton to reject the operation when the request does not match the stored mandate details.
- `udfParameters`: echoed only when supplied.

## Request Examples

### Pause By Original Mandate Id

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-PAUSE-1001",
  "upiRequestId": "PAUSE202501010000000000000101",
  "orgMandateId": "MND202401010000000000000001",
  "requestType": "PAUSE",
  "pauseStart": "2025/1/10",
  "pauseEnd": "2025/1/31",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "fallbackDeviceFingerPrint": "aabbccddeeff00112233445566778899",
  "payeeVpa": "merchant@bank",
  "remarks": "Customer requested payment pause",
  "iat": "1735689600000",
  "udfParameters": "{\"ticketId\":\"SUP-1001\"}"
}
```

### Pause By UMN With Account Guards

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-PAUSE-1002",
  "upiRequestId": "PAUSE202501010000000000000102",
  "umn": "YBL0000000000000000000000000000001@okbank",
  "requestType": "PAUSE",
  "pauseStart": "2025/2/1",
  "pauseEnd": "2025/2/15",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "accountReferenceId": "ACCREF1234567890",
  "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
  "ifsc": "HDFC0000001",
  "iat": "1735689600000"
}
```

### Unpause By Original Mandate Id

Do not send `pauseStart` or `pauseEnd` for `UNPAUSE`.

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UNPAUSE-1001",
  "upiRequestId": "UNPAUSE202501010000000000101",
  "orgMandateId": "MND202401010000000000000001",
  "requestType": "UNPAUSE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "payeeVpa": "merchant@bank",
  "iat": "1735689600000",
  "udfParameters": "{\"ticketId\":\"SUP-1002\"}"
}
```

### Unpause By UMN

```json
{
  "merchantCustomerId": "CUST12345",
  "merchantRequestId": "MANDATE-UNPAUSE-1002",
  "upiRequestId": "UNPAUSE202501010000000000102",
  "umn": "YBL0000000000000000000000000000001@okbank",
  "requestType": "UNPAUSE",
  "deviceFingerPrint": "f7e6d5c4b3a291807060504030201000",
  "fallbackDeviceFingerPrint": "aabbccddeeff00112233445566778899",
  "iat": "1735689600000"
}
```

## Response

### Success Response

Top-level `status`, `responseCode`, and `responseMessage` come from Newton's generic success response when the API call was processed. The mandate action result is in the nested payload gateway fields.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "accountReferenceId": "ACCREF1234567890",
    "amount": "1000.00",
    "bankAccountUniqueId": "b2f0f66c0d0b0d5a9f7a7b2c3d4e5f60",
    "blockFund": "false",
    "gatewayMandateId": "PAUSE202501010000000000000101",
    "gatewayPayerResponseCode": "00",
    "gatewayReferenceId": "501001234567",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Mandate pause Success",
    "gatewayResponseStatus": "SUCCESS",
    "initiatedBy": "PAYER",
    "mandateTimestamp": "2025-01-01T10:15:30+05:30",
    "mandateType": "PAUSE",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "merchantId": "MERCHANT123",
    "merchantRequestId": "MANDATE-PAUSE-1001",
    "mandateName": "Monthly subscription",
    "orgMandateId": "MND202401010000000000000001",
    "pauseStart": "2025/1/10",
    "pauseEnd": "2025/1/31",
    "payeeMcc": "5815",
    "payeeName": "Example Merchant",
    "payeeVpa": "merchant@bank",
    "payerName": "Example Customer",
    "payerRevocable": "true",
    "payerVpa": "customer@bank",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "15",
    "refUrl": "https://www.juspay.in",
    "remarks": "Customer requested payment pause",
    "role": "PAYER",
    "amountRule": "MAX",
    "shareToPayee": "false",
    "transactionType": "UPI_MANDATE",
    "umn": "YBL0000000000000000000000000000001@okbank",
    "validityStart": "2024-01-01",
    "validityEnd": "2025-12-31"
  },
  "udfParameters": "{\"ticketId\":\"SUP-1001\"}"
}
```

For `UNPAUSE`, the response shape is the same. `mandateType` is usually `UNPAUSE`, and `pauseStart` / `pauseEnd` are omitted unless the processed downstream history still carries those values.

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Transport/API processing status. Success value is `SUCCESS`. |
| `responseCode` | string | Transport/API processing code. Success value is `SUCCESS`. |
| `responseMessage` | string | Transport/API processing message. Success value is `SUCCESS`. |
| `payload` | object | Pause/unpause business response. |
| `udfParameters` | string | Echo of request `udfParameters`; omitted when not supplied. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `accountReferenceId` | string | Mandate account reference id returned when account id exposure is enabled for the merchant/multibank setup. |
| `amount` | string | Mandate amount formatted with two decimals. |
| `bankAccountUniqueId` | string | Mandate bank-account unique id returned when available. |
| `blockFund` | string | Text form of the mandate block-fund flag: `true` or `false`. |
| `gatewayMandateId` | string | UPI request id of the pause/unpause mandate-history action. |
| `gatewayPayerResponseCode` | string | Payer-side response code parsed from NPCI response. Returned only for API versions above `0`. |
| `gatewayReferenceId` | string | Gateway/NPCI response id from mandate history. |
| `gatewayResponseCode` | string | Normalized action result code. `00` means the pause/unpause request was accepted/successful; other values come from downstream/NPCI response codes. |
| `gatewayResponseMessage` | string | Normalized action result message, for example `Mandate pause Success`, `Mandate unpause Request Sent Successfully`, or a downstream failure result. |
| `gatewayResponseStatus` | string | Business status for the action. Values are `SUCCESS` or `FAILURE` in this mapper. |
| `initiatedBy` | string | Always `PAYER` for this S2S pause/unpause response. |
| `mandateTimestamp` | string | Creation timestamp of the mandate-history action in local time text format. |
| `mandateType` | string | Mandate-history action type, typically `PAUSE` or `UNPAUSE`. |
| `merchantChannelId` | string | Merchant channel id from Newton merchant configuration. |
| `merchantCustomerId` | string | Echo of request `merchantCustomerId`. |
| `merchantId` | string | Merchant id from Newton merchant configuration. |
| `merchantRequestId` | string | Echo of request `merchantRequestId`. |
| `mandateName` | string | Stored mandate display name, when available. |
| `orgMandateId` | string | Original Newton mandate id. |
| `pauseStart` | string | Echo of request `pauseStart` for `PAUSE`; omitted when absent. |
| `pauseEnd` | string | Echo of request `pauseEnd` for `PAUSE`; omitted when absent. |
| `payeeMcc` | string | Payee MCC from the stored mandate. |
| `payeeName` | string | Payee display name from the stored mandate when available. |
| `payeeVpa` | string | Payee VPA from stored mandate details. |
| `payerName` | string | Payer display name from the stored mandate when available. |
| `payerRevocable` | string | Text form of the mandate revocable flag: `true` or `false`. |
| `payerVpa` | string | Payer VPA from stored mandate details. |
| `recurrencePattern` | string | Mandate recurrence pattern, for example `DAILY`, `WEEKLY`, `MONTHLY`, `ONETIME`. |
| `recurrenceRule` | string | Mandate recurrence rule when stored, for example `ON`, `BEFORE`, or `AFTER`. |
| `recurrenceValue` | string | Mandate recurrence value when stored. |
| `refUrl` | string | Stored mandate reference URL, or Newton default reference URL when absent. |
| `remarks` | string | Mandate-history remarks, or Newton default remarks when absent. |
| `role` | string | Mandate-history role. |
| `amountRule` | string | Mandate amount rule, for example `MAX` or `EXACT`. |
| `shareToPayee` | string | Text form of the mandate share-to-payee flag: `true` or `false`. |
| `transactionType` | string | Pay type from mandate transaction info, defaulting to `UPI_MANDATE`. |
| `umn` | string | UPI mandate number when stored on the mandate. |
| `validityStart` | string | Mandate validity start date. |
| `validityEnd` | string | Mandate validity end date. |

## Error Handling

Failure responses use the same response transport configured for the merchant when the request reaches the S2S response layer. Authentication/envelope failures can be returned before a normal encrypted response is possible. After decryption, the underlying JSON error shape is generally:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "pauseStart or pauseEnd is not valid"
}
```

The exact `responseMessage` varies by validation or business-rule branch. Some business-rule errors use HTTP 200 with a failure body, while auth and malformed envelope errors can use HTTP 400/401. Client handling should be based on both HTTP status and the decrypted `status`, `responseCode`, and `responseMessage`.

### Realistic Failure Scenarios

| Scenario | Underlying decrypted response body | Client handling |
| --- | --- | --- |
| Missing required JSON field such as `merchantCustomerId`, `merchantRequestId`, `upiRequestId`, or `requestType` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $: parsing Newton.Services.Transformer.ServerToServer.Types.PauseUnpauseMandateS2SRequest failed, key merchantCustomerId not found"}` | Fix payload construction. Do not retry unchanged. |
| Invalid `requestType` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"EnumValidation \"Enum match failed \\\"SUSPEND\\\"\""}` | Send only `PAUSE` or `UNPAUSE`. |
| Invalid `upiRequestId` or `orgMandateId` format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"upiRequestId regex match failed\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"upiRequestId length is not between 1 and 35\""}` | Use 1 to 35 alphanumeric characters. Do not retry unchanged. |
| Invalid `merchantRequestId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\""}` | Use max 35 characters with letters, numbers, hyphen, dot, underscore. |
| Invalid `umn` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"umn length is not between 34 and 70\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"umn regex failed\""}` | Send a valid UMN or use `orgMandateId`. |
| Invalid `pauseStart` or `pauseEnd` date format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"date value not valid\""}` | Send a valid date accepted by Newton date validation, for example `2025/1/10`. |
| Invalid `payeeVpa` format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"customerVpa regex failed\""}` or length validation | Correct the VPA format. |
| Invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` | Send a JSON-object string without disallowed characters, or omit it. |
| Missing `iat` for JWS/JWE payloads | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` | Include a valid issued-at timestamp in signed/encrypted requests. |
| Invalid request timestamp or expired timestamp | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Timestamp difference with actual current time"}` or `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid timestamp format"}` | Regenerate timestamp/signature and retry once. |
| Missing or invalid encrypted/signed envelope | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` or `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: parsing Newton.Types.API.RequestBody.SignedBody failed"}` | Fix JWE/JWS construction, key id, payload encoding, or signature. Do not blindly retry. |
| Missing merchant headers, signature mismatch, or bad `x-merchant-signature` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Verify `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, raw body canonicalization, and merchant API key/signing strategy. |
| Merchant API blocked or not allowed | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Contact Newton/onboarding to enable `pauseMandateS2S` or update allowed APIs. Do not retry unchanged. |
| IP allow-list failure | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Send from an allow-listed IP and ensure `x-forwarded-for` carries the expected first IP. |
| Unknown merchant customer | Typically `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"MerchantCustomer not found"}` | Confirm `merchantCustomerId` belongs to the merchant and environment. |
| Missing both `orgMandateId` and `umn` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"umn or OrgMandateId is mandatory"}` | Send one mandate identifier. |
| Mandate lookup failure | Typically `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Mandate Not Found"}` or equivalent storage lookup message | Confirm `orgMandateId`/`umn`, merchant customer, and environment. Do not retry unchanged. |
| Duplicate `upiRequestId` | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` | Treat as idempotency conflict. Query mandate status/history before deciding whether to create a new action id. |
| Missing `deviceFingerPrint` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"value required deviceFingerPrint"}` | Send the registered device fingerprint. |
| Device fingerprint mismatch | `{"status":"FAILURE","responseCode":"DEVICE_FINGERPRINT_MISMATCH","responseMessage":"DEVICE_FINGERPRINT_MISMATCH"}` | Refresh device binding or send the correct primary/fallback fingerprint. |
| `payeeVpa` does not match mandate | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"CustomerVpa does not match"}` | Verify the stored mandate payee VPA and retry only with the correct value. |
| `bankAccountUniqueId` does not match mandate | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"bankAccountUniqueId not valid"}` | Remove the guard or send the mandate's stored account id. |
| `accountReferenceId` does not match mandate | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"accountReferenceId not valid"}` | Remove the guard or send the mandate's stored account reference. |
| Delegate/IoT mandate operation attempted | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Delegate Mandate Operation Restricted"}` | This mandate purpose cannot be paused through this API. |
| Mandate is completed | `{"status":"FAILURE","responseCode":"JPMC","responseMessage":"Invalid Operation , Mandate is Completed"}` | Do not retry. A completed mandate cannot be paused/unpaused. |
| Mandate is declined | `{"status":"FAILURE","responseCode":"JPMD","responseMessage":"Invalid Operation , Mandate is Declined"}` | Do not retry. |
| Mandate is expired | `{"status":"FAILURE","responseCode":"JPMX","responseMessage":"Invalid Operation , Mandate is Expired"}` | Do not retry. |
| Mandate is pending | `{"status":"FAILURE","responseCode":"JPMW","responseMessage":"Invalid Operation , Mandate is in pending state"}` | Wait for mandate creation/approval to complete, then retry with a new `upiRequestId` if appropriate. |
| Mandate is revoked or revoke-pending | `{"status":"FAILURE","responseCode":"JPMR","responseMessage":"Invalid Operation , Mandate is Revoked"}` | Do not retry. |
| Mandate is inactive, failed, timed out, or dormant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mandate is inactive"}` | Do not retry unless the mandate status changes through another flow. |
| `UNPAUSE` sent with `pauseStart` or `pauseEnd` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"pauseStart and pauseEnd not required when requestType is UNPAUSE"}` | Remove date fields from `UNPAUSE`. |
| One-time block-fund mandate | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Can't pause/unpause ONETIME mandate"}` | This mandate type is not supported for pause/unpause. |
| `PAUSE` on an already paused mandate | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Already Paused Mandate"}` | Treat as already paused. Query status/history before creating another action. |
| `UNPAUSE` when mandate is not paused | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mandate not in pause state"}` | Treat as not paused. Query mandate status/history. |
| Non-revocable loan/EMI pause blocked | ICICI mode: `{"status":"FAILURE","responseCode":"JPPMNA","responseMessage":"Pause mandate operation is not allowed"}`. Other modes: `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Loan AND EMI Can't be Paused"}` | Do not retry. The mandate/business category is not eligible. |
| `PAUSE` missing `pauseStart` or `pauseEnd` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Required pauseStart and pauseEnd date"}` | Send both dates. |
| `PAUSE` date range outside mandate validity or end before start | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"pauseStart or pauseEnd is not valid"}` | Ensure `validityStart <= pauseStart <= pauseEnd <= validityEnd`. |
| Downstream wrapper/NPCI unavailable or invalid response | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE","responseMessage":"NPCI Service Unavailable"}` or deployment-specific service-unavailable text | Retry with the same `upiRequestId` only if Newton confirms no action was created; otherwise query status/history first. |
| Downstream/NPCI business failure after processing | Top-level may be `SUCCESS`, with payload like `{"gatewayResponseStatus":"FAILURE","gatewayResponseCode":"JPNL","gatewayResponseMessage":"Mandate Request Failed"}` | Treat as a completed failed attempt. Do not retry with the same `upiRequestId`; investigate the gateway message or create a new action only when business-correct. |
| Unexpected internal error | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry only after checking whether the action exists by `upiRequestId`; escalate with `x-request-id`. |

## Retry and Idempotency Guidance

- Generate a fresh `upiRequestId` for each new pause/unpause attempt.
- Do not retry validation, auth, API-disabled, mandate-state, or account/device mismatch failures without changing the request or configuration.
- If the HTTP request times out, the connection drops, or Newton returns an unexpected 5xx, first query mandate status/history using `upiRequestId`, `orgMandateId`, or `umn`. The action may have been created even if the client did not receive the response.
- If a retry with the same `upiRequestId` returns `DUPLICATE_REQUEST`, treat it as an idempotency conflict and reconcile via status/history instead of creating repeated pause/unpause attempts.
- For downstream/NPCI pending or failure outcomes, use `gatewayResponseStatus`, callbacks, and mandate status APIs as the source of business truth. Top-level `SUCCESS` means Newton processed the API call, not necessarily that the mandate was paused or unpaused.
- Use `x-request-id` on every call and store it with `merchantRequestId` and `upiRequestId` for Newton support and reconciliation.

## Source References

- Route type for `POST /api/{apiVersion}/merchants/mandates/pause`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:613)
- Route handler, payload extraction, signature verification, monitoring id, transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3207)
- Request decryption/verification entrypoint: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40) and [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- `EncRequest` and `EncResponse` envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Merchant signature, API enablement, timestamp, and IP allow-list checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response signing/encryption routing and response headers: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:31)
- S2S transformer route and request validation call: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:747)
- S2S request, response, and payload types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3331)
- S2S core request and response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1373)
- Core mandate request/response types: [src/Newton/Product/Merchant/Mandate/Types.hs](../../src/Newton/Product/Merchant/Mandate/Types.hs:427)
- Pause/unpause product route and downstream call branching: [src/Newton/Product/Merchant/Mandate/PauseMandate.hs](../../src/Newton/Product/Merchant/Mandate/PauseMandate.hs:12)
- DB lookup, mandate/device/account validation, and response field construction: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:1053)
- Delegate/IoT restriction helper: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:218)
- Downstream wrapper/NPCI call and response validation: [src/Newton/Utils/BusinessLogic/MandateHelper.hs](../../src/Newton/Utils/BusinessLogic/MandateHelper.hs:150)
- Shared validation helpers for ids, VPA, UMN, UDF, enum, and dates: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:246)
- Duplicate action id, device fingerprint, VPA match, mandate lookup, and mandate status rules: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Gateway response mapping for pause/unpause outcomes: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:1520)
- Shared success and error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
