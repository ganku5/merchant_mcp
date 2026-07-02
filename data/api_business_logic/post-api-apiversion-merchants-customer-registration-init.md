# Init Customer Registration API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/registration/init`

## Overview

Init Customer Registration is a Newton merchant server-to-server API used to start a customer/device registration attempt for UPI onboarding.

The endpoint supports two active registration paths:

- `SMS`, the default path, delegates to Newton's Get SMS Token flow. Newton creates a merchant customer registration token, returns VMN/service-provider details, and returns the registration SMS content as `payload.attemptIdentifier`.
- `OTP` triggers an onboarding OTP for the customer mobile number through Newton's SMS retriever flow. Newton creates or reuses a registration token, triggers an OTP SMS, and returns the registration content as `payload.attemptIdentifier`.

`SMV` is part of the enum accepted by the request type, but this S2S endpoint rejects it with `BAD_REQUEST`.

Examples below show decrypted business payloads for readability. Production payloads use the encrypted/signed/plain transport mode assigned during merchant onboarding.

## Business Use Case

Use this API when the merchant backend needs to start customer registration before continuing with device binding and activation.

Init Customer Registration helps merchants:

- Create a Newton registration token for a customer/device onboarding attempt.
- Ask Newton for VMN and SMS content when the device will send a registration SMS.
- Trigger an OTP to the customer's mobile number when the merchant has been enabled for the OTP registration path.
- Bind the attempt to merchant customer id, device id, package name, OS/provider hints, and merchant metadata.
- Receive the registration content/attempt identifier that later registration, bind-device, or activation calls use to locate the same attempt.

Do not use this API to complete registration by itself. A successful response means the registration attempt has been started; the merchant must continue with the configured bind-device and activation flow before treating the customer as onboarded.

## Integration Flow

1. Merchant identifies the customer and device in its own system.
2. Merchant chooses `registrationFlow`:
   - omit it or send `SMS` when the device will send a registration SMS to a returned VMN;
   - send `OTP` only when Newton has enabled OTP registration for the merchant.
3. Merchant sends the S2S request with merchant headers and the encrypted/signed/plain body mode configured during onboarding.
4. Newton verifies the request envelope or signature, merchant API access, timestamp, and request body.
5. For `SMS`, Newton creates a registration token through the Get SMS Token path and returns `serviceProviders[]`, `attemptIdentifier`, and `expiryTimestamp`.
6. For `OTP`, Newton normalizes the mobile number, creates or loads the registration token, checks expiry/decline/OTP retry limits, optionally checks app hash or Play Integrity configuration, and sends an OTP SMS.
7. Merchant stores the returned `attemptIdentifier` and continues with the next device-binding/activation step before `expiryTimestamp`.

Important identifiers:

- `merchantCustomerId`: Merchant-owned customer profile id. Send it for normal customer-specific registration.
- `deviceId`: Merchant/device fingerprint. Newton hashes it for token/device-attempt checks.
- `attemptIdentifier`: In the request, this is optional and meaningful for the OTP path to retry/reuse an existing registration token. In the response, this is the registration content returned by Newton and should be carried into the next registration step.
- `serviceProviders[]`: Returned only for the `SMS` path. The customer device should send the returned `attemptIdentifier` SMS content to one returned service-provider `number`.
- `expiryTimestamp`: Registration-token expiry. Continue the bind/activation flow before this time.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/registration/init
```

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | JSON transport envelope. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-api-version` | Conditional | Header read by the delegated Get SMS Token path. For the default `SMS` path, omit it or send `0` unless Newton explicitly confirms a newer compatible response mode for this endpoint. For `OTP`, it is not used by product logic. |
| `x-timestamp` | Yes | Current timestamp used in merchant signature verification. |
| `x-raw-body` | Conditional | Exact raw HTTP body used for merchant signature verification in plain signed mode. |
| `x-merchant-signature` | Conditional | Required for plain signed business payload mode. JWS/JWE modes verify through the configured envelope. |
| `x-forwarded-for` | Conditional | Required only when merchant IP allowlisting is configured. |
| `x-request-id` | No | Merchant/client request id for tracing. Newton generates one when omitted. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. The route accepts Newton's common `EncRequest` transport: JWE encrypted body, JWS signed body, or plain JSON only where merchant configuration permits it.

For JWS/JWE request bodies, send `iat` in the decrypted business payload. The middleware validates it before product logic runs. Plain signed payload mode ignores payload `iat`, but sending it is safe.

Responses use the matching onboarded response mode. Verify/decrypt the response before reading the business fields.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the URL path. Use the value assigned during onboarding. This is separate from the optional `x-api-version` header read by some product logic. |

## Request

### Required Minimum

For the default `SMS` path, omit `registrationFlow` or send `SMS`. Use `x-api-version: 0` or omit the header.

```json
{
  "merchantCustomerId": "CUST000123",
  "countryCode": "91",
  "mobileNumber": "9876543210",
  "packageName": "com.merchant.app",
  "deviceId": "android-fingerprint-7f4a9d",
  "provider": "JIO",
  "os": "Android",
  "iat": "1782990600000"
}
```

For the `OTP` path:

```json
{
  "merchantCustomerId": "CUST000124",
  "registrationFlow": "OTP",
  "countryCode": "91",
  "mobileNumber": "9876543211",
  "packageName": "com.merchant.app",
  "deviceId": "android-fingerprint-8a5c1e",
  "appHash": "FA+9qCX9VSu",
  "iat": "1782990600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Recommended; conditional | For `SMS`, required unless `merchantProfileSharingEnabled=true`. For `OTP`, omission is accepted by the current product path, but the token is not linked to a merchant customer. | Merchant's customer/profile id. Must be 1 to 256 characters and match Newton's merchant-customer-id pattern. |
| `countryCode` | string | No | If omitted, `mobileNumber` must be a 12-digit domestic number such as `919876543210`. | Optional country code. Allows digits with optional leading `+`, max 7 characters. Used to normalize the mobile number in `OTP`; validated but not forwarded to Get SMS Token in `SMS`. |
| `mobileNumber` | string | Yes | No default. | Customer mobile number. With `countryCode`, must be numeric and shorter than 19 digits. Without `countryCode`, must be exactly 12 numeric digits. Used in `OTP`; validated but not used by the delegated `SMS` product path. |
| `attemptIdentifier` | string | No | No default. | For `OTP`, reuses an existing registration token looked up by registration content/SMS content. If omitted, Newton creates a new OTP registration token. In `SMS`, this request field is validated but not forwarded. |
| `integrityToken` | string | Conditional | No default. | Used only by the `OTP` path when Play Integrity checks are enabled for the registration token/configuration. Must be non-empty when sent. |
| `registrationFlow` | string | No | Defaults to `SMS`. | Allowed enum values are `SMS`, `OTP`, `SMV`. Current S2S behavior supports `SMS` and `OTP`; `SMV` returns `BAD_REQUEST`. |
| `packageName` | string | Yes | No default. | App package name. Required by the type. Used by `OTP` token creation and integrity/app-hash checks; validated but not forwarded in `SMS`. |
| `deviceId` | string | Yes | No default. | Merchant/device fingerprint. Forwarded to Get SMS Token in `SMS`; used for hashing and device-attempt limits in both supported paths. |
| `appHash` | string | No | For `OTP`, Newton falls back to merchant config `appHashForOtpDeviceBind` when present, and may use `multipleAppHashForOtpDeviceBind` when deriving app hash from Play Integrity certificate hashes. No effect in `SMS`. | Android SMS Retriever app hash used when sending OTP SMS. Must be non-empty when sent. |
| `provider` | string | No | No default. | Provider/operator hint for VMN selection in `SMS`. Also checked against Newton's blacklisted provider list. Validated but not used in `OTP`. |
| `os` | string | No | No default. | Device OS hint. Forwarded only in `SMS`, where it can affect stored token metadata and SMS-token expiry selection. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp used by S2S JWS/JWE validation. Send a fresh 13-digit epoch-milliseconds timestamp for signed/encrypted body modes. |
| `udfParameters` | string | No | Omitted from response when omitted. | JSON-object string for merchant metadata, for example `"{\"journeyId\":\"REG123\"}"`. Echoed in success and shaped OTP failure responses. |
| `androidAPILevel` | integer | No | No default. | Passed to the `OTP` Play Integrity check path when that check is enabled. No effect in `SMS`. |

### Nested Request Objects

This API has no nested business request objects.

### Validation Notes

- Empty required strings are rejected.
- Empty optional text fields are rejected when supplied.
- `merchantCustomerId` must be non-empty, at most 256 characters, and match Newton's allowed merchant-customer-id pattern.
- `countryCode` must be at most 7 characters and match digits with an optional leading `+`.
- `mobileNumber` must contain only digits. If `countryCode` is omitted, send a 12-digit value. If sending a 10-digit Indian mobile number, include `countryCode` as `91` or `+91`.
- `udfParameters` must be a string containing a JSON object and must pass Newton's character validation.
- `SMV` is rejected even though it is part of the enum.
- For the `SMS` path, a positive `x-api-version` header causes the delegated Get SMS Token path to omit top-level `smsContent`; this init wrapper currently requires that field to build `payload.attemptIdentifier`. Use `x-api-version: 0` or omit the header for `SMS` unless Newton confirms otherwise.

### Defaults and Omitted Field Behavior

Fields not listed here have no generated default.

- `registrationFlow`: omitted behaves as `SMS`.
- `x-api-version`: omitted or non-numeric behaves as `0`.
- `merchantCustomerId`: in `SMS`, product logic requires it unless merchant profile sharing is enabled. In `OTP`, omission creates/uses an unlinked token and is not recommended for normal merchant-customer onboarding.
- `countryCode`: omission changes mobile validation to the 12-digit domestic format.
- `attemptIdentifier`: in `OTP`, omission creates a new registration token; presence reuses an existing token and counts against OTP retry rules.
- `appHash`: in `OTP`, request value wins; if omitted, Newton tries configured app-hash fallbacks.
- `udfParameters`: echoed only when supplied.

## Request Examples

### SMS Registration Init

Use this when the customer device will send an SMS to a VMN returned by Newton. Omit `x-api-version` or send `x-api-version: 0`.

```json
{
  "merchantCustomerId": "CUST000123",
  "registrationFlow": "SMS",
  "countryCode": "91",
  "mobileNumber": "9876543210",
  "packageName": "com.merchant.app",
  "deviceId": "android-fingerprint-7f4a9d",
  "provider": "JIO",
  "os": "Android",
  "iat": "1782990600000",
  "udfParameters": "{\"journeyId\":\"REG-20260702-000123\"}"
}
```

### SMS Registration Init With 12-Digit Mobile Number

Use this shape when omitting `countryCode`.

```json
{
  "merchantCustomerId": "CUST000126",
  "mobileNumber": "919876543213",
  "packageName": "com.merchant.app",
  "deviceId": "android-fingerprint-7f4a9e",
  "os": "Android",
  "iat": "1782990600000"
}
```

### OTP Registration Init

Use this only when Newton has enabled OTP registration for the merchant.

```json
{
  "merchantCustomerId": "CUST000124",
  "registrationFlow": "OTP",
  "countryCode": "+91",
  "mobileNumber": "9876543211",
  "packageName": "com.merchant.app",
  "deviceId": "android-fingerprint-8a5c1e",
  "appHash": "FA+9qCX9VSu",
  "iat": "1782990600000",
  "udfParameters": "{\"journeyId\":\"REG-20260702-000124\",\"channel\":\"android\"}"
}
```

### OTP Retry With Existing Attempt Identifier

Use the same `attemptIdentifier` only when retrying the OTP trigger for an existing, unexpired registration attempt.

```json
{
  "merchantCustomerId": "CUST000124",
  "registrationFlow": "OTP",
  "countryCode": "91",
  "mobileNumber": "9876543211",
  "attemptIdentifier": "OTP pp9f7c4c2d1e8f4a6b8c0d2e4f6a8b0c2d4",
  "packageName": "com.merchant.app",
  "deviceId": "android-fingerprint-8a5c1e",
  "appHash": "FA+9qCX9VSu",
  "iat": "1782990600000"
}
```

## Response

Route response type: `RespHeaders (API.EncResponse DBT.InitRegistrationResponse)`.

Treat a response as successful only when the decrypted body has a success status/code for the selected flow:

- `SMS`: `status = "SUCCESS"` and `responseCode = "SUCCESS"`.
- `OTP`: `status = "SUCCESS"` and `responseCode = "TRIGGER_OTP_SUCCESS"`.

For `OTP`, `status = "FAILURE"` with `responseCode = "TRIGGER_OTP_FAILURE"` is a completed business response indicating Newton could not trigger the OTP. It can still include a payload with the registration content and expiry; do not treat that as a successful OTP send.

### SMS Success Response

Decrypted business response for the default `SMS` path:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST000123",
    "attemptIdentifier": "JUSPAY pp9f7c4c2d1e8f4a6b8c0d2e4f6a8b0c2d4",
    "serviceProviders": [
      {
        "name": "JIO",
        "number": "919876543210"
      },
      {
        "name": "AIRTEL",
        "number": "919812345678"
      }
    ],
    "expiryTimestamp": "2026-07-02T15:45:00+05:30"
  },
  "udfParameters": "{\"journeyId\":\"REG-20260702-000123\"}"
}
```

Client interpretation:

- Send `payload.attemptIdentifier` as the SMS content from the customer device to one returned `serviceProviders[].number`.
- Store `payload.attemptIdentifier` for the next bind-device/activation step as configured.
- Continue before `payload.expiryTimestamp`.

### OTP Trigger Success Response

Decrypted business response for `registrationFlow = "OTP"` when Newton successfully triggers the OTP:

```json
{
  "status": "SUCCESS",
  "responseCode": "TRIGGER_OTP_SUCCESS",
  "responseMessage": "Trigger OTP Success",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST000124",
    "attemptIdentifier": "OTP pp8c6f4d2b0a1e9c7f5d3b1a9e0c8f6d4b2a",
    "expiryTimestamp": "2026-07-02T15:45:00+05:30"
  },
  "udfParameters": "{\"journeyId\":\"REG-20260702-000124\",\"channel\":\"android\"}"
}
```

Client interpretation:

- Prompt the customer to complete the configured OTP verification/bind flow.
- Store `payload.attemptIdentifier`; reuse it only for the same registration attempt.
- `serviceProviders` is omitted for OTP because no VMN list is returned by this path.

### OTP Trigger Failure Response

If the SMS notification provider does not report a successful OTP send, Newton returns a shaped failure response:

```json
{
  "status": "FAILURE",
  "responseCode": "TRIGGER_OTP_FAILURE",
  "responseMessage": "Trigger OTP Failure",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST000124",
    "attemptIdentifier": "OTP pp8c6f4d2b0a1e9c7f5d3b1a9e0c8f6d4b2a",
    "expiryTimestamp": "2026-07-02T15:45:00+05:30"
  }
}
```

Client interpretation: treat this as OTP not sent. Retry only with bounded backoff and awareness of OTP retry limits, or restart the registration attempt according to merchant policy.

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Business status. `SUCCESS` for `SMS` token creation or OTP trigger success; `FAILURE` for shaped OTP trigger failure. |
| `responseCode` | string | `SUCCESS`, `TRIGGER_OTP_SUCCESS`, `TRIGGER_OTP_FAILURE`, or an error code. |
| `responseMessage` | string | Human-readable message. |
| `payload` | object | Registration-init business payload. Present in normal success and shaped OTP trigger failure responses. |
| `udfParameters` | string | Echo of request `udfParameters`. Omitted when not supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured in Newton. |
| `merchantChannelId` | string | Merchant channel id configured in Newton. |
| `merchantCustomerId` | string | Echo of request `merchantCustomerId`. Omitted when the request omitted it. |
| `attemptIdentifier` | string | Registration content/attempt identifier returned by Newton. For `SMS`, this is the SMS content from the delegated Get SMS Token response. For `OTP`, this is the registration token content used to continue or retry the OTP registration attempt. |
| `serviceProviders` | array of objects | Returned only for the `SMS` path. Omitted for `OTP`. |
| `expiryTimestamp` | string | Registration-token expiry timestamp in Newton local timestamp format, for example `2026-07-02T15:45:00+05:30`. |

### `serviceProviders[]`

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Operator/provider name from Newton's SMS aggregator configuration. |
| `number` | string | VMN/service-provider mobile number to which the customer device should send the registration SMS. |
| `smsContent` | string | Normally omitted by this endpoint's supported `SMS` response shape. Use top-level `payload.attemptIdentifier` as the SMS content. |

## Error Handling

Failure responses generally use Newton's standard error body after decrypting/verifying the response envelope: `status: "FAILURE"` with a concrete `responseCode` and diagnostic `responseMessage`. The examples below show common values.

Some failures are thrown before the normal response transformer, so HTTP status can be `200`, `400`, `401`, or `500` depending on the layer. Client integrations should use decrypted `status`, `responseCode`, and `responseMessage` for handling, and log HTTP status plus `x-request-id` for support.

### Request Validation Failures

Empty required fields are rejected. For example, `packageName: ""` can return:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"packageName field is empty\""
}
```

If `countryCode` is omitted and `mobileNumber` is not 12 digits:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mobile length is not equal to 12\""
}
```

Invalid country code format can return:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"countryCode regex match not found\""
}
```

Invalid `udfParameters` can return:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Unsupported `registrationFlow = "SMV"` returns:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SMV not supported"
}
```

Client handling: fix the request body, regenerate the S2S signature/envelope, and retry. Do not ask the customer to send SMS or enter OTP for a failed init response.

### Authentication, Signature, Encryption, or IP Failures

Missing merchant headers, missing `x-raw-body`/`x-timestamp` in plain signed mode, signature mismatch, JWS/JWE verification failure, decryption failure, or source IP not allowlisted can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the API is blocked or not enabled for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If a signed/encrypted request omits `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Client handling: fix merchant ids, key id, timestamp freshness, canonical raw body, signature, encryption format, API enablement, or IP allowlist. Regenerate the request; do not replay a stale envelope.

### Merchant Configuration and Lookup Failures

For `SMS`, if `merchantCustomerId` is omitted and merchant profile sharing is not enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in getMaybeMerchantCustomerId : mcId not found"
}
```

If `provider` is blacklisted:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the `OTP` path cannot derive the required app hash from request/configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "APP_HASH_CONFIG_ERROR",
  "responseMessage": "App hash configuration error"
}
```

If Play Integrity certificate hashes do not match configured app-hash data:

```json
{
  "status": "FAILURE",
  "responseCode": "APP_HASH_MISMATCH",
  "responseMessage": "App hash check mismatch"
}
```

If Play Integrity verification fails:

```json
{
  "status": "FAILURE",
  "responseCode": "INTEGRITY_CHECK_FAILURE",
  "responseMessage": "PLAY_INTEGRITY_FAILURE"
}
```

Client handling: these are normally non-retryable until merchant configuration, provider value, app package/hash configuration, or integrity-token handling is corrected.

### Registration Token Business Failures

If `OTP` is retried with an unknown `attemptIdentifier`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid smsContent"
}
```

If the registration token was declined:

```json
{
  "status": "FAILURE",
  "responseCode": "REGISTRATION_DECLINED",
  "responseMessage": "Device binding was declined"
}
```

If the registration token expired:

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_EXPIRED",
  "responseMessage": "SMS token expired"
}
```

If OTP retry attempts are exhausted:

```json
{
  "status": "FAILURE",
  "responseCode": "RETRY_ATTEMPTS_EXHAUSTED",
  "responseMessage": "Trigger otp retry attempts exhausted"
}
```

Client handling: do not keep retrying the same attempt. Restart registration with a fresh init call after the customer or merchant policy permits it.

### Device Attempt Limit Failures

When `isGetSmsTokenRMD004LimitEnabled` is enabled, Newton validates recent registration attempts per device hash over a 24-hour window.

If the device id hash is missing in that configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in validateDeviceBindAttemptForDeviceInGetSmsToken : deviceId hash not found"
}
```

When the device exceeds the configured limit:

```json
{
  "status": "FAILURE",
  "responseCode": "BIND_DEVICE_LIMIT_EXCEEDED",
  "responseMessage": "Device bind attempted more than 3 times for this device/mobile number"
}
```

Client handling: stop retrying for the same device within the configured window. Ask the customer to wait or contact support according to merchant policy.

### SMS Path Response-Shape Compatibility Failure

If the default `SMS` path is called with `x-api-version > 0`, the delegated Get SMS Token response can omit top-level `smsContent`; this wrapper then cannot populate `payload.attemptIdentifier`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "mkInitRegistrationS2SResponsePayloadFromGetSms: smsContent"
}
```

Client handling: omit `x-api-version` or send `x-api-version: 0` for `registrationFlow = "SMS"` unless Newton confirms a newer compatible mode.

### Downstream, Storage, or Unexpected Failures

The `SMS` path does not call NPCI. Downstream failures are usually SMS aggregator selection, token persistence, Redis, configuration, encryption/hash, or storage failures. The `OTP` path also calls Newton's SMS notification provider. Unexpected failures generally return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

For OTP SMS provider declines that are handled by the product flow, Newton can instead return the shaped `TRIGGER_OTP_FAILURE` response shown above.

Client handling: retry transient `INTERNAL_SERVER_ERROR` only with short bounded backoff. Do not retry validation, auth, API enablement, provider blacklist, merchant config, expired-token, declined-token, or attempt-limit failures without changing the request or configuration.

## Retry and Idempotency Guidance

This API has no merchant idempotency key. A successful call can create a new registration token and consume device-attempt limits.

- If an `SMS` call succeeds, do not call init again for the same customer/device attempt. Use the returned `attemptIdentifier` and `serviceProviders[]`.
- If an `SMS` request times out and no usable response is available, retry with a fresh timestamp/signature. If the retry succeeds, use only the latest returned `attemptIdentifier` and expiry.
- If an `OTP` call succeeds but the customer requests another OTP, retry with the same `attemptIdentifier` only while the token is unexpired and within OTP retry limits.
- Repeated `OTP` calls without `attemptIdentifier` create new attempts and can consume device-attempt limits.
- Regenerate the signature/envelope for every retry; do not replay an old signed/encrypted body after the timestamp window.
- Continue the bind-device/activation flow before `expiryTimestamp`. If it expires, restart registration with a fresh init call.

## Source References

- API root path and `apiVersion` capture: [Core.hs](../../src/Newton/App/Routes/Core.hs:112)
- S2S route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:478)
- S2S handler, request decryption, signature verification, cache invalidation, and product dispatch: [Core.hs](../../src/Newton/App/Routes/Core.hs:2730)
- Common encrypted/signed/plain transport shapes: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Merchant signature, timestamp, API allow/block, and plain-signature checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:145)
- Request/response types and validators: [Types.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/Types.hs:118), [Types.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/Types.hs:152), [Types.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/Types.hs:172)
- Registration flow branching and OTP request construction: [S2S.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/S2S.hs:28), [S2S.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/S2S.hs:38)
- Init response transformers and SMS-to-attemptIdentifier mapping: [Transformer.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/Transformer.hs:105), [Transformer.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/Transformer.hs:134), [Transformer.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/Transformer.hs:146), [Transformer.hs](../../src/Newton/Product/Merchant/Customer/DeviceBinding/Transformer.hs:159)
- Delegated Get SMS Token product flow and merchant-profile-sharing behavior: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1066), [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1120)
- Get SMS Token response transformer and versioned `smsContent` placement: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1882)
- `x-api-version` defaulting: [Utils.hs](../../src/Newton/Utils/Utils.hs:960)
- OTP trigger route, token lookup/create, Play Integrity/app-hash checks, and OTP retry checks: [Core.hs](../../src/Newton/Product/SmsRetriever/Core.hs:44), [Core.hs](../../src/Newton/Product/SmsRetriever/Core.hs:93), [Core.hs](../../src/Newton/Product/SmsRetriever/Core.hs:160)
- OTP request/response core types: [Types.hs](../../src/Newton/Product/SmsRetriever/Types.hs:11)
- Field validators: [Common.hs](../../src/Newton/Validation/Common.hs:168), [Common.hs](../../src/Newton/Validation/Common.hs:275), [Common.hs](../../src/Newton/Validation/Common.hs:311), [Common.hs](../../src/Newton/Validation/Common.hs:501), [Common.hs](../../src/Newton/Validation/Common.hs:695)
- Validation failure wrapper: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Registration token defaults, stored metadata, expiry, and SMS content: [MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:267)
- Registration-token lookup by SMS content/attempt identifier: [MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:651), [MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:1117)
- Device-attempt limits and SMS lookup Redis write: [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:429), [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1543)
- OTP SMS trigger and shaped trigger success/failure behavior: [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1436)
- Provider blacklist failure: [Utils.hs](../../src/Newton/Utils/Utils.hs:5702)
- Error response helpers/constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:178), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:187), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:268), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:286), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:373), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1094), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1103), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1203), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1212), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1221)
- Missing-value error helpers used by this path: [Extra.hs](../../src/Newton/Utils/Extra.hs:107), [Extra.hs](../../src/Newton/Utils/Extra.hs:126)
