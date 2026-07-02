# Get SMS Token API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/getSmsToken`

## Overview

Get SMS Token is a server-to-server API used at the start of SMS-based UPI customer registration and device binding.

The merchant calls this API before the customer device sends the registration SMS. Newton validates the S2S envelope, merchant signature, request body, merchant configuration, and device-attempt limits, then creates a merchant customer registration token and returns one or more service-provider VMNs with SMS content. The customer device should send exactly one returned `smsContent` value to the corresponding `number`; the merchant then continues with `bindDevice` using the same token/content and device details.

Use this API when your Newton onboarding flow requires Newton to generate the SMS registration content and VMN details for a customer/device registration attempt.

## Business Use Case

Get SMS Token helps merchants:

- Start an SMS-based customer registration attempt for UPI device binding.
- Receive the VMN/service-provider number that the customer device must send the registration SMS to.
- Receive registration SMS content that Newton can later use to locate and verify the registration token.
- Optionally bind the attempt to a merchant customer id, device id, provider, and OS.
- Support multiple service providers in newer API versions, so the client can choose an available VMN.
- Enforce merchant-side registration attempt limits before the customer spends time sending SMS.

Do not use this API for integrations where Newton has enabled `isGetSMSTokenDisabledS2S`; those integrations provide SMS content through a different flow and normally continue directly to the bind-device path with the configured VMN.

## Integration Flow

1. Merchant identifies the customer/device registration attempt in its own system.
2. Merchant calls `getSmsToken` with `merchantCustomerId` when required, plus optional device/provider/OS metadata.
3. Newton verifies the S2S request and creates a merchant customer registration token.
4. Newton returns `serviceProviders[]` and SMS content.
5. The customer device sends exactly one returned SMS content value to the matching service-provider number.
6. Merchant calls `POST /api/{apiVersion}/merchants/customer/bindDevice` with the same `smsContent` and device details.
7. Merchant completes activation through the configured activation flow.

Important identifiers:

- `merchantCustomerId`: Merchant-owned customer profile id. Required unless `merchantProfileSharingEnabled` is enabled for the merchant.
- `deviceId`: Merchant/device fingerprint supplied by the client. When sent, Newton stores a hash on the registration token and `bindDevice` must use the same device.
- `provider`: Optional provider/operator hint used during VMN selection and blacklist checks.
- `smsContent`: Registration content returned by Newton. Use this exact value in the SMS body and in the following bind-device call.
- `expiryTimestamp`: Time until which the returned registration token should be treated as usable for the SMS registration flow.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/getSmsToken
```

Examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | JSON transport envelope. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-api-version` | Recommended | Use the API version shared during onboarding. Send a positive integer for the newer response shape where each `serviceProviders[]` entry carries its own `smsContent`. If omitted or invalid, Newton treats it as version `0`. |
| `x-timestamp` | Yes | Current 13-digit epoch milliseconds used for signature freshness checks. |
| `x-raw-body` | Conditional | Exact raw HTTP request body used for signature verification. Usually supplied or preserved by the integration gateway/client middleware; if sent directly, it must match the submitted body byte-for-byte. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain business payload mode. JWS/JWE request modes verify through the configured envelope. |
| `x-forwarded-for` | Conditional | Required only when Newton has IP allowlisting configured for the merchant. |
| `x-request-id` | No | Merchant/client request id for tracing. Newton generates one when omitted. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. The route accepts Newton's `EncRequest` transport: JWE encrypted body, JWS signed body, or plain JSON only where merchant configuration permits it. Production integrations should use the signed/encrypted mode assigned during onboarding. For unsigned/plain business payload mode, the merchant signature is calculated over the merchant ids, timestamp, and exact raw request body.

For signed or encrypted request bodies, send `iat` inside the decrypted business payload. Newton validates it as a timestamp before running the business flow. For plain unsigned payload mode, the signature layer ignores payload `iat`, but sending it is still safe and recommended for consistency.

Responses use the matching onboarded response mode. Verify/decrypt the response before reading the business fields.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the URL path. Use the value assigned during onboarding. |

## Request

### Required Minimum

For most integrations, send at least `merchantCustomerId`, `deviceId`, `os`, and `iat`:

```json
{
  "merchantCustomerId": "CUST000123",
  "deviceId": "device-fingerprint-7f4a9d",
  "os": "Android",
  "iat": "1782990600000"
}
```

If the merchant has `merchantProfileSharingEnabled=true`, `merchantCustomerId` may be omitted:

```json
{
  "deviceId": "device-fingerprint-7f4a9e",
  "os": "Android",
  "iat": "1782990600000"
}
```

If the merchant wants Newton to prefer or validate against a provider/operator hint, include `provider`:

```json
{
  "merchantCustomerId": "CUST000124",
  "deviceId": "device-fingerprint-3c8e2b",
  "provider": "JIO",
  "os": "Android",
  "iat": "1782990600000",
  "udfParameters": "{\"registrationSource\":\"merchant-app\",\"journeyId\":\"REG-20260702-000124\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Conditional | No default. If `merchantProfileSharingEnabled=true`, Newton accepts omission and creates an unlinked registration token. Otherwise omission fails. | Merchant's customer identifier. Max 256 characters. Allowed characters are alphanumeric plus `.`, `_`, `+`, `/`, `=`, `-`; the first character must be alphanumeric, `+`, `/`, or `=`. |
| `deviceId` | string | Recommended; conditional when attempt limiting is enabled | No default. If omitted, Newton cannot store a device hash for later `bindDevice` cross-checks. If `isGetSmsTokenRMD004LimitEnabled=true`, omission fails because the limit is keyed by device hash. | Merchant/device fingerprint for the customer device. Must be non-empty when sent. |
| `provider` | string | No | No default. Newton selects from the merchant's configured VMNs without this hint. | Optional provider/operator hint used in VMN selection and blacklist checks. Must be non-empty when sent. |
| `os` | string | Recommended | No default. If sent, Newton stores it on the registration token and later `bindDevice` must send the same OS case-insensitively. Also used to choose configured SMS-token expiry. | Device operating system, for example `Android` or `iOS`. Must be non-empty when sent. |
| `iat` | string | Conditional | No business default. Required for signed/encrypted request envelopes. | Issued-at timestamp used by S2S signature/encryption validation. Send a 13-digit Unix timestamp in milliseconds within the freshness window shared during onboarding. |
| `udfParameters` | string | No | No default. Omitted from the response when omitted from the request. | JSON-object string for merchant metadata. Must parse as a JSON object string and pass Newton's UDF character validation. Echoed back on success. |

### Nested Request Objects

This API has no nested business request objects.

### Validation Notes

- `merchantCustomerId` is validated for length and allowed characters when present.
- `deviceId`, `provider`, and `os` must be non-empty when present.
- `udfParameters` must be a string containing a JSON object, for example `"{\"journeyId\":\"REG123\"}"`.
- `iat` is nullable in the business type, but signed/encrypted S2S calls require it before product validation runs.
- `x-api-version` is read from the header, not the JSON body. Missing or non-numeric values behave as version `0`.

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `merchantCustomerId`: required by product logic unless merchant profile sharing is enabled.
- `deviceId`: no generated fallback. Send it for new integrations so `bindDevice` can verify continuity with this step.
- `provider`: no generated fallback. Newton uses merchant VMN selection configuration without a provider hint.
- `os`: no generated fallback. If omitted, bind-device OS continuity validation is not applied for this token.
- `udfParameters`: no generated fallback. Echoed only when supplied.
- `x-api-version`: omitted or invalid behaves as `0`, returning the legacy top-level `smsContent` response shape.

## Request Examples

### Standard Android Registration

```json
{
  "merchantCustomerId": "CUST000123",
  "deviceId": "android-fingerprint-7f4a9d",
  "provider": "JIO",
  "os": "Android",
  "iat": "1782990600000",
  "udfParameters": "{\"journeyId\":\"REG-20260702-000123\"}"
}
```

### iOS Registration

```json
{
  "merchantCustomerId": "CUST000125",
  "deviceId": "ios-device-96f41c",
  "provider": "AIRTEL",
  "os": "iOS",
  "iat": "1782990600000"
}
```

### Merchant Profile Sharing Enabled

```json
{
  "deviceId": "shared-profile-device-1a2b3c",
  "os": "Android",
  "iat": "1782990600000",
  "udfParameters": "{\"journeyId\":\"REG-20260702-000126\"}"
}
```

## Response

Route response type: `RespHeaders (API.EncResponse API.GetSmsTokenResponse)`.

Treat the call as successful only when the decrypted body has `status = "SUCCESS"` and `responseCode = "SUCCESS"`. On success, Newton has created a registration token and persisted SMS lookup data for the returned content. The merchant should use one returned `smsContent` value for the customer SMS and later `bindDevice` call.

### Success Response for `x-api-version > 0`

For new integrations, send a positive `x-api-version`. In this response shape, each service provider carries its own SMS content.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST000123",
    "serviceProviders": [
      {
        "name": "JIO",
        "number": "919876543210",
        "smsContent": "JUSPAY pp9f7c4c2d1e8f4a6b8c0d2e4f6a8b0c2d4"
      },
      {
        "name": "AIRTEL",
        "number": "919812345678",
        "smsContent": "JUSPAY pp7a6b5c4d3e2f1098a7b6c5d4e3f2a1b0c9d"
      }
    ],
    "expiryTimestamp": "2026-07-02T15:45:00+05:30"
  },
  "udfParameters": "{\"journeyId\":\"REG-20260702-000123\"}"
}
```

Client interpretation:

- Select one `serviceProviders[]` entry and send its exact `smsContent` to its `number`.
- Use the same exact `smsContent` in the following `bindDevice` request.
- The top-level `payload.smsContent` field is omitted in this response shape.

### Legacy Success Response for `x-api-version = 0`

When `x-api-version` is missing, invalid, or `0`, Newton returns one top-level `smsContent`. Provider-level `smsContent` fields are omitted.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST000123",
    "serviceProviders": [
      {
        "name": "JIO",
        "number": "919876543210"
      }
    ],
    "smsContent": "JUSPAY pp9f7c4c2d1e8f4a6b8c0d2e4f6a8b0c2d4",
    "expiryTimestamp": "2026-07-02T15:45:00+05:30"
  }
}
```

Client interpretation:

- Send `payload.smsContent` to one of the returned `serviceProviders[].number` values.
- Use `payload.smsContent` in the following `bindDevice` request.

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for a successful token creation. |
| `responseCode` | string | `SUCCESS` on success. |
| `responseMessage` | string | Human-readable response message. `SUCCESS` on success. |
| `payload` | object | Business payload containing merchant identifiers, VMN/service provider details, SMS content, and expiry. |
| `udfParameters` | string | Echo of request `udfParameters`. Omitted when not supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured in Newton. |
| `merchantChannelId` | string | Merchant channel id configured in Newton. |
| `merchantCustomerId` | string | Echo of request `merchantCustomerId`. Omitted when the request omitted it under merchant profile sharing. |
| `serviceProviders` | array of objects | VMN/service-provider choices that the customer device can use for the registration SMS. |
| `smsContent` | string | Legacy response content returned only when `x-api-version` is `0`, missing, or invalid. Omitted for `x-api-version > 0`. |
| `expiryTimestamp` | string | Registration token expiry timestamp in Newton local timestamp format, for example `2026-07-02T15:45:00+05:30`. Call `bindDevice` before this time. |

### `serviceProviders[]`

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Operator/provider name from Newton's configured SMS aggregator data. |
| `number` | string | VMN/service-provider mobile number to which the customer device should send the registration SMS. |
| `smsContent` | string | SMS content for this provider. Present only when `x-api-version > 0`; omitted in the legacy response shape. |

## Error Handling

Failure responses generally use Newton's standard error body after decrypting/verifying the response envelope: `status: "FAILURE"` with a concrete `responseCode` and diagnostic `responseMessage`. The examples below show common values.

Some failures are thrown before the normal success response transformer, so HTTP status can be `200`, `400`, `401`, or `500` depending on the layer. Client integrations should use the decrypted `status`, `responseCode`, and `responseMessage` for handling, and should also log HTTP status and `x-request-id` for support.

### Request Validation Failures

Empty optional text fields are rejected when present. For example, `deviceId: ""` can return:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"Field is empty\""
}
```

Invalid `merchantCustomerId` characters can return:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
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

Client handling: fix the request body, regenerate the S2S signature/envelope, and retry. Do not ask the customer to send SMS for a failed token response.

### Missing Merchant Customer Id When Required

If `merchantProfileSharingEnabled` is not enabled and `merchantCustomerId` is omitted, product logic rejects the request:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in getMaybeMerchantCustomerId : mcId not found"
}
```

Client handling: send a valid `merchantCustomerId`, unless Newton has explicitly enabled merchant profile sharing for this merchant.

### Authentication, Signature, Encryption, or IP Failures

Missing or invalid merchant headers, failed JWS verification, failed JWE decryption, missing or invalid `x-merchant-signature` in unsigned mode, source IP not allowlisted, or signature mismatch can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the API is blocked or not allowed for the merchant:

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

Client handling: fix credentials, key id, timestamp, payload canonicalization, signature, encryption format, API enablement, or IP allowlist. Regenerate the request; do not replay a stale encrypted/signed envelope.

### Provider and Merchant Configuration Failures

If `provider` is blacklisted by Newton configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the merchant is configured with no usable SMS aggregator/VMN data, or if `isGetSMSTokenDisabledS2S` is enabled and this endpoint is called anyway, the code path can fail as an internal merchant configuration error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: do not retry continuously. Confirm merchant SMS aggregator configuration, provider values, and whether this merchant should use the alternate get-SMS-token-disabled flow.

### Device Attempt Limit Failures

When `isGetSmsTokenRMD004LimitEnabled` is enabled, Newton validates recent attempts per device hash over a 24-hour window. If `deviceId` is missing in that configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in validateDeviceBindAttemptForDeviceInGetSmsToken : deviceId hash not found"
}
```

When the device exceeds the merchant-configured attempt limit:

```json
{
  "status": "FAILURE",
  "responseCode": "BIND_DEVICE_LIMIT_EXCEEDED",
  "responseMessage": "Device bind attempted more than 3 times for this device/mobile number"
}
```

Client handling: stop retrying for the same device. Ask the customer to wait for the configured window or contact support according to the merchant's policy.

### Downstream, Storage, or Unexpected Failures

This API does not call NPCI as part of the normal flow. Downstream failures for this route are usually Newton storage, Redis, key/config lookup, or token-persistence failures. They generally return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry only with short bounded backoff when the failure appears transient. If a retry succeeds, use only the latest returned `smsContent` and `expiryTimestamp`.

## Retry and Idempotency Guidance

`getSmsToken` has no merchant idempotency key. Each successful call creates a new merchant customer registration token and SMS content.

- If the client receives a successful response, do not call `getSmsToken` again for the same customer/device attempt. Continue with the returned SMS content.
- If the HTTP request times out and no usable response is available, the merchant may retry with a fresh timestamp/signature. If the retry succeeds, discard any older SMS content that may later surface in logs or delayed client state.
- Repeated successful calls can consume configured device-attempt limits and can rotate VMN/provider choices.
- Do not retry validation, authentication, API enablement, provider blacklist, or merchant configuration failures without changing the request or configuration.
- Call `bindDevice` before `expiryTimestamp`. If the token has expired, restart the registration attempt with a fresh `getSmsToken` call.

## Source References

- API root path and `apiVersion` capture: [Core.hs](../../src/Newton/App/Routes/Core.hs:112)
- S2S route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:472)
- S2S handler, request decryption, signature verification, cache invalidation, and product dispatch: [Core.hs](../../src/Newton/App/Routes/Core.hs:2711)
- Request, validation, response, and nested service-provider types: [Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:435)
- Common encrypted/signed/plain transport shapes: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification and JWS/JWE handling: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:73)
- Merchant signature, timestamp, API allow/block, and IP allowlist checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:145), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:202)
- Request validation failure wrapper: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Field validators: [Common.hs](../../src/Newton/Validation/Common.hs:174), [Common.hs](../../src/Newton/Validation/Common.hs:275), [Common.hs](../../src/Newton/Validation/Common.hs:311)
- Product flow, merchant-customer requirement, device hash, SMS details, token creation, Redis write, and response transformer call: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1061)
- Merchant profile sharing behavior: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1118)
- SMS aggregator selection strategies and merchant store/config failures: [SMSAgg.hs](../../src/Newton/Utils/SMSAgg.hs:32)
- SMS content generation and aggregator metadata mapping: [MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:1034)
- Registration token defaults, stored device hash/OS, SMS content, and expiry seconds: [MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:267)
- SMS lookup Redis write and TTL: [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1543)
- Get-SMS-token device-attempt limit: [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:429)
- SMS-token expiry configuration and iOS fallback handling: [DB.hs](../../src/Newton/Utils/DB.hs:939)
- `x-api-version` defaulting: [Utils.hs](../../src/Newton/Utils/Utils.hs:960)
- Success response transformer and versioned SMS-content placement: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1876)
- Timestamp response formatter: [DateTime.hs](../../src/Newton/Utils/DateTime.hs:174)
- Error response constructors: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:286)
- Provider blacklist failure: [Utils.hs](../../src/Newton/Utils/Utils.hs:5705)
- `isGetSMSTokenDisabledS2S` feature flag: [FeatureEnabled.hs](../../src/Newton/Utils/FeatureEnabled.hs:160)
- Later bind-device continuity checks for `deviceId` and `os`: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:332)
