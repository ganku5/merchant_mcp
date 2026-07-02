# Bind Device API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/bindDevice`

## Overview

Bind Device is a server-to-server API used during UPI customer registration to complete the device-binding step after an SMS token, attempt identifier, or SMV verification token has been created.

The merchant calls this API after the customer device has initiated the registration proof, usually by sending the Newton-provided SMS token from the device SIM or by completing an enabled SMV flow. Newton validates the encrypted/signed request, merchant configuration, token state, device details, optional VMN/SMV/OTP checks, and then binds and activates the customer-device context for the merchant.

Use this API before customer account discovery, account linking, balance enquiry, Set MPIN, VPA creation, or any other flow that requires an active merchant customer and device binding.

## Business Use Case

Bind Device helps merchants:

- Prove that a customer controls the mobile device/SIM used for UPI registration.
- Bind the merchant customer id to Newton's customer and device records.
- Activate the registration token created by the preceding SMS/SMV registration step.
- Receive the device fingerprint that must be used in later S2S account and VPA APIs.
- Support polling until the SMS/SMV verification is complete.
- Support configured OTP hardening for device binding.
- Support merchant-profile-sharing flows where the merchant receives the customer's mobile number after binding.
- Enforce merchant risk controls such as device/mobile binding limits, blocked entities, VMN validation, and optional IP/user-agent validation for SMV.

## Integration Flow

1. Merchant starts customer registration using the onboarding flow shared by Newton. This produces or correlates a registration token using `smsContent`, `attemptIdentifier`, or `smvContent`.
2. The customer device sends the registration SMS, or the configured SMV provider verifies the device.
3. Merchant calls `bindDevice` with the token correlation value, merchant customer id when required, device details, SIM/SSID details, and optional OTP fields.
4. Newton validates the S2S envelope, merchant signature, timestamp freshness, API enablement, request body, token state, and device details.
5. If SMS/SMV verification is still pending, Newton returns a pending failure response. The merchant may poll again with the same token correlation data.
6. If verification is complete, Newton binds and activates the customer/device for the merchant and returns `deviceFingerPrint`.
7. Merchant stores `deviceFingerPrint`, `customerMobileNumber`, and the merchant customer/device binding state, then continues with account discovery or other UPI registration APIs.

Important identifiers:

- `smsContent`: SMS token/content used to locate the merchant customer registration token. This is the normal polling identifier for SMS-based flows.
- `attemptIdentifier`: Alternate polling identifier. Newton resolves it through the SMS-token Redis mapping when present.
- `smvContent`: Token/content used for SMV-assisted registration. SMV flows require `merchantCustomerId`.
- `merchantCustomerId`: Merchant's stable customer id. Required for most integrations. It can be omitted only when `merchantProfileSharingEnabled` is enabled for the merchant and the flow is not one of the branches that explicitly requires it.
- `deviceId`: Raw device fingerprint/device identifier supplied by the merchant application. Newton stores/encrypts/hashes it and returns a derived `deviceFingerPrint`.
- `deviceFingerPrint`: Newton-generated hash of device fingerprint plus SSID. Use this value in later S2S APIs that ask for the registered device fingerprint.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/bindDevice
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the API version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, when required by the configured signature process. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding, when your configured request mode uses header-level merchant signatures. JWS/JWE request modes verify through the configured envelope. |
| `x-forwarded-for` | Required only when Newton has IP allowlisting configured for the merchant. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. The route accepts Newton's `EncRequest` envelope: signed JWS, encrypted JWE containing a signed payload, or plain JSON only where merchant configuration permits it. Production integrations should send the configured encrypted and/or signed request envelope. Plain JSON examples in this guide are decrypted business payloads only.

For signed/encrypted requests, `iat` in the decrypted business payload and `x-timestamp` in request headers are validated for freshness. Timestamps must be 13-digit epoch milliseconds and within the configured freshness window.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Request

### Required Minimum

For a standard SMS-token polling request for a new device, send at least:

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "JUSPAY pp9f7c4c2d1e8f4a6b",
  "deviceId": "device-fingerprint-7f4a9d",
  "manufacturer": "Samsung",
  "model": "SM-S928B",
  "version": "14",
  "os": "Android",
  "ssid": "SIM_SLOT_1_SSID",
  "packageName": "com.merchant.app",
  "iat": "1735689600000"
}
```

For polling by attempt identifier:

```json
{
  "merchantCustomerId": "CUST12345",
  "attemptIdentifier": "ATTEMPT-REG-12345",
  "deviceId": "device-fingerprint-7f4a9d",
  "manufacturer": "Samsung",
  "model": "SM-S928B",
  "version": "14",
  "os": "Android",
  "ssid": "SIM_SLOT_1_SSID",
  "packageName": "com.merchant.app",
  "iat": "1735689600000"
}
```

For an SMV-assisted flow:

```json
{
  "merchantCustomerId": "CUST12345",
  "smvContent": "SMV-REG-12345",
  "deviceId": "ios-device-fingerprint-123",
  "manufacturer": "Apple",
  "model": "iPhone16,2",
  "version": "17.5",
  "os": "iOS",
  "ssid": "SIM_PRIMARY_SSID",
  "packageName": "com.merchant.app",
  "ipAddress": "203.0.113.10",
  "userAgent": "MerchantApp/5.4 iOS/17.5",
  "iat": "1735689600000"
}
```

For a merchant configured with `isGetSMSTokenDisabledS2S`, send the VMN that received/sent the registration SMS:

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "pp9f7c4c2d1e8f4a6b",
  "vmn": "919876543210",
  "deviceId": "device-fingerprint-7f4a9d",
  "manufacturer": "Samsung",
  "model": "SM-S928B",
  "version": "14",
  "os": "Android",
  "ssid": "SIM_SLOT_1_SSID",
  "packageName": "com.merchant.app",
  "iat": "1735689600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Conditional | No default. If `merchantProfileSharingEnabled=true`, normal polling can omit it and Newton can return the customer mobile number for later activation mapping. | Merchant's customer identifier. Required for SMV flow, for `isGetSMSTokenDisabledS2S`, and for normal integrations where merchant profile sharing is not enabled. Max 256 characters; allowed characters are alphanumeric plus `.`, `_`, `+`, `/`, `=`, `-`. |
| `smsContent` | string | Conditional | No default. | SMS token/content used to locate the registration token. Send exactly one of `smsContent`, `attemptIdentifier`, or `smvContent` for normal integrations. |
| `attemptIdentifier` | string | Conditional | No default. | Alternate registration attempt identifier. Newton treats it as the token lookup value when `smsContent` and `smvContent` are not sent. |
| `smvContent` | string | Conditional | No default. | SMV token/content. When supplied, Newton uses the SMV path and requires `merchantCustomerId`. |
| `merchantCustomerRegistrationTokenReferenceId` | string | No for standard integrations | No default. Do not send with `smsContent`, `attemptIdentifier`, or `smvContent`; that combination is rejected. | Registration-token reference id. The product code has an id lookup path, but the current validator still requires one of the token-content fields. Use content-based polling unless Newton explicitly instructs otherwise for your integration. |
| `deviceId` | string | Conditional | No default. | Device fingerprint/device id from the customer device. Required when the registration token does not already have a device stored. The value is encrypted/hashed before storage where Passetto is enabled. |
| `manufacturer` | string | Conditional | No default. | Device manufacturer. Required when Newton has to create the device record. |
| `model` | string | Conditional | No default. | Device model. Required when Newton has to create the device record. |
| `version` | string | Conditional | No default. | OS/app/device version associated with the device record. Required when Newton has to create the device record. |
| `os` | string | Conditional | No default. | Device operating system, for example `Android` or `iOS`. Required when Newton has to create the device record. If the registration token stored an OS from the preceding get-SMS-token step, bindDevice validates that this value matches case-insensitively. |
| `ssid` | string | Conditional | No default. | SIM/SSID value used with `deviceId` to derive `deviceFingerPrint`. Send it for new integrations. If omitted, limited fallback through `simId` is available only where Newton has stored SSIDs for the session/token and the device does not need to be newly created. |
| `simId` | string | No | No default. | SIM slot/index used only as a fallback to derive SSID from the stored registration-token session data. |
| `countryCode` | string | No | If omitted, `mobileNumber` must be a 12-digit value including country code. | Country code used to normalize `mobileNumber`, for example `+91` or `91`. Max 7 characters; digits with optional leading `+`. |
| `mobileNumber` | string | No | No default. If omitted, Newton uses the customer/mobile context available from the verified registration token. | Customer mobile number. With `countryCode`, length must be below 19 digits and is normalized. Without `countryCode`, the validator expects a 12-digit mobile value. If merchant mobile validation is enabled, this must match the verified token customer. |
| `packageName` | string | Conditional | No default. | Application package/bundle id. Required when Newton enables a registration token that does not already have a package name. Returned only when merchant `sendDeviceDetails=true`. |
| `deregisterOldCustomer` | string | No | Omitted behaves as `"false"`. | Boolean string, `"true"` or `"false"`. Set `"true"` only when the merchant intends to replace/deregister an old customer binding for the same customer/device flow. |
| `isOtpRequired` | string | No | Omitted behaves as `"false"`. | Boolean string. Set `"true"` to trigger OTP behavior for merchants configured for OTP hardening. Must be `"true"` when `appHash` is supplied. |
| `appHash` | string | Conditional | No default. | App hash used for OTP trigger. Allowed only with `isOtpRequired="true"`. Do not send with `otp` or `senderId` in the same request. |
| `otp` | string | Conditional | No default. | OTP value for the OTP verification step. Must be sent together with `senderId`. Do not send in the same request as an OTP trigger. |
| `senderId` | string | Conditional | No default. | Sender id for the OTP SMS. Required with `otp`; validated against configured sender-id regex, defaulting to `JUSPAY` when no custom regex is configured. |
| `aggregator` | string | No | No default. | Optional aggregator metadata. The current handler validates non-empty text but does not use it for core binding decisions. |
| `ipAddress` | string | Conditional for some SMV merchants | No default. | Required only when SMV merchant configuration enables IP validation. Must match the IP stored on the SMV registration token. |
| `userAgent` | string | Conditional for some SMV merchants | No default. | Required only when SMV merchant configuration enables user-agent validation. Must match the user agent stored on the SMV registration token. |
| `vmn` | string | Conditional | No default. | VMN used in `isGetSMSTokenDisabledS2S` and optional VMN-match validation. Must be 10 to 12 digits; an 11-digit VMN must start with `0`. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the normal success response. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by S2S signature/encryption verification and freshness checks. Required for signed/encrypted production requests, even though the business type is nullable. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are simply not used when omitted.

- Token correlation: send one of `smsContent`, `attemptIdentifier`, or `smvContent`. Omission of all three is rejected.
- Device details: `deviceId`, `manufacturer`, `model`, `version`, `os`, `ssid`, and `packageName` are effectively required for a new token/device even though the JSON type marks them nullable. They may be reused only when already present on the token/device record.
- `deregisterOldCustomer`: omitted behaves as `false`.
- `isOtpRequired`: omitted behaves as `false`.
- `mobileNumber`: optional, but when supplied it can be used for mobile-number match validation.
- `countryCode`: controls mobile-number normalization. Omit it only when sending a 12-digit mobile number with country code included.
- `udfParameters`: echoed back only in the normal bind success response.
- `merchantCustomerRegistrationTokenReferenceId`: do not combine it with token-content fields.

### Validation Notes

- Empty optional strings are invalid when the field is present. Send `null`/omit the field instead of an empty string.
- `merchantCustomerId` must be 1 to 256 characters and match Newton's merchant-customer-id regex.
- `deregisterOldCustomer` and `isOtpRequired` must be boolean strings: `"true"` or `"false"`.
- `udfParameters` must be a JSON-object string and cannot contain the blocked characters enforced by the shared UDF validator.
- `mobileNumber` and `countryCode` are validated together.
- `vmn` uses a separate VMN validator and may be required by merchant configuration even though the type is nullable.
- OTP trigger and OTP verification cannot be combined in one request.
- `appHash` is allowed only when `isOtpRequired="true"`.
- `otp` and `senderId` must be supplied together.

## Request Examples

### Standard SMS Polling With UDF

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "JUSPAY pp9f7c4c2d1e8f4a6b",
  "deviceId": "device-fingerprint-7f4a9d",
  "manufacturer": "Samsung",
  "model": "SM-S928B",
  "version": "14",
  "os": "Android",
  "ssid": "SIM_SLOT_1_SSID",
  "countryCode": "+91",
  "mobileNumber": "9876543210",
  "packageName": "com.merchant.app",
  "deregisterOldCustomer": "false",
  "udfParameters": "{\"registrationId\":\"REG12345\"}",
  "iat": "1735689600000"
}
```

### OTP Trigger Request

Use this only for merchants configured for OTP hardening. A trigger response is not the final bind success payload.

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "JUSPAY pp9f7c4c2d1e8f4a6b",
  "deviceId": "device-fingerprint-7f4a9d",
  "manufacturer": "Samsung",
  "model": "SM-S928B",
  "version": "14",
  "os": "Android",
  "ssid": "SIM_SLOT_1_SSID",
  "packageName": "com.merchant.app",
  "isOtpRequired": "true",
  "appHash": "FA+9qCX9VSu",
  "iat": "1735689600000"
}
```

### OTP Verification Request

After OTP trigger, call again with both `otp` and `senderId`.

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "JUSPAY pp9f7c4c2d1e8f4a6b",
  "deviceId": "device-fingerprint-7f4a9d",
  "manufacturer": "Samsung",
  "model": "SM-S928B",
  "version": "14",
  "os": "Android",
  "ssid": "SIM_SLOT_1_SSID",
  "packageName": "com.merchant.app",
  "otp": "123456",
  "senderId": "JUSPAY",
  "iat": "1735689600000"
}
```

### SMV Flow With Validation Metadata

```json
{
  "merchantCustomerId": "CUST12345",
  "smvContent": "SMV-REG-12345",
  "deviceId": "ios-device-fingerprint-123",
  "manufacturer": "Apple",
  "model": "iPhone16,2",
  "version": "17.5",
  "os": "iOS",
  "ssid": "SIM_PRIMARY_SSID",
  "packageName": "com.merchant.app",
  "ipAddress": "203.0.113.10",
  "userAgent": "MerchantApp/5.4 iOS/17.5",
  "udfParameters": "{\"smvSessionId\":\"SMVSESSION123\"}",
  "iat": "1735689600000"
}
```

## Response

### Normal Bind Success

When device binding is complete, Newton returns:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "deviceFingerPrint": "6a7b7b64f6bbf7902e2eb8e7e4a983e0f7ccda43b827df42d9a3cc0c12345678"
  },
  "udfParameters": "{\"registrationId\":\"REG12345\"}"
}
```

Interpretation:

- `status=SUCCESS`, `responseCode=SUCCESS` means Newton has completed or read back an already completed binding.
- Store `payload.deviceFingerPrint`. Later account/VPA APIs expect this Newton-generated device fingerprint, not necessarily the raw `deviceId` from the request.
- `customerMobileNumber` is trimmed before returning. Use it to map the customer in merchant-profile-sharing flows.
- `merchantCustomerId` is omitted when it was omitted in the request.
- `udfParameters` is returned only when supplied in the request.

### Success With Device Details Enabled

If the merchant store has `sendDeviceDetails=true`, the payload can also include the optional device detail fields:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "deviceFingerPrint": "6a7b7b64f6bbf7902e2eb8e7e4a983e0f7ccda43b827df42d9a3cc0c12345678",
    "merchantCustomerRegistrationTokenReferenceId": "MCRT12345",
    "deviceId": "device-fingerprint-7f4a9d",
    "manufacturer": "Samsung",
    "model": "SM-S928B",
    "version": "14",
    "os": "Android",
    "ssid": "SIM_SLOT_1_SSID",
    "packageName": "com.merchant.app"
  }
}
```

Optional response fields are omitted when `sendDeviceDetails` is not enabled or when the source value is not available.

### OTP Trigger Control Response

OTP trigger uses Newton's standard status body, not the normal bind response type. If OTP was already triggered or the OTP SMS was sent successfully, the response can be:

```json
{
  "status": "SUCCESS",
  "responseCode": "TRIGGER_OTP_SUCCESS",
  "responseMessage": "Trigger OTP Success"
}
```

Interpretation: do not treat this as final device binding. Ask the customer for the OTP and call `bindDevice` again with `otp` and `senderId`.

## Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level Newton status. Normal final bind success is `SUCCESS`. Some OTP trigger control responses also use `SUCCESS` but do not include the bind payload. |
| `responseCode` | string | Machine-readable response code. Final bind success is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. |
| `payload` | object | Present for final bind success. Omitted for standard error/control responses. |
| `udfParameters` | string | Echo of request `udfParameters` for normal final bind success. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from Newton's merchant record. |
| `merchantChannelId` | string | Merchant channel id from Newton's merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request, omitted if the request omitted it. |
| `customerMobileNumber` | string | Customer mobile number associated with the verified registration token, returned in trimmed form. |
| `deviceFingerPrint` | string | Newton-generated SHA-256 hash of device fingerprint plus SSID. Use this value in later S2S APIs. |
| `merchantCustomerRegistrationTokenReferenceId` | string | Returned only when merchant `sendDeviceDetails=true` and the request supplied this reference id. |
| `deviceId` | string | Raw/decrypted device fingerprint returned only when `sendDeviceDetails=true`. |
| `manufacturer` | string | Device manufacturer returned only when `sendDeviceDetails=true`. |
| `model` | string | Device model returned only when `sendDeviceDetails=true`. |
| `version` | string | Device version returned only when `sendDeviceDetails=true`. |
| `os` | string | Device OS returned only when `sendDeviceDetails=true`. |
| `ssid` | string | SSID used for fingerprint derivation returned only when `sendDeviceDetails=true`. |
| `packageName` | string | Package name on the registration token returned only when `sendDeviceDetails=true`. |

## Error Handling

Failures before normal product-response creation use the same encrypted/signed response transport configured for the integration where possible. After decryption, the body generally follows Newton's standard error shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"At least one of the smsContent, attemptIdentifier or smvContent should not be not null\""
}
```

The exact `responseCode` and `responseMessage` depend on the validation or business rule that failed. HTTP status can vary by validation layer. Always parse the decrypted body first, then use HTTP status for transport-level troubleshooting.

### Concrete Failure Scenarios

Missing all token-correlation fields:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"At least one of the smsContent, attemptIdentifier or smvContent should not be not null\""
}
```

Invalid OTP trigger/verify combination:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Invalid Request Parameters\""
}
```

`appHash` sent without `isOtpRequired="true"`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"appHash not allowed\""
}
```

Only one of `otp` or `senderId` supplied:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Invalid otp and senderId\""
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

Missing `merchantCustomerId` in a flow that requires it:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bindDeviceS2S2Route: merchantCustomerId"
}
```

Both content-based token lookup and token reference id sent:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Both smsContent and mcrtReferenceId are not valid"
}
```

Unknown SMS token/content:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid smsContent"
}
```

Unknown registration token reference:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid merchantCustomerRegistrationTokenId"
}
```

Missing required device detail for a new token/device:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid findOrCreateDevice - deviceId"
}
```

Other missing new-device fields produce the same `INVALID_DATA` shape with messages such as `Invalid findOrCreateDevice - os`, `Invalid findOrCreateDevice - model`, `Invalid findOrCreateDevice - version`, `Invalid findOrCreateDevice - manufacturer`, or `Invalid findOrCreateDevice - ssid`.

Missing package name while enabling the registration token:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid enableMerchantCustomerRegistrationToken-packageName"
}
```

SMS/SMV verification still pending:

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_PENDING",
  "responseMessage": "SMS verification pending"
}
```

Expired SMS token:

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_EXPIRED",
  "responseMessage": "SMS token expired"
}
```

Registration declined:

```json
{
  "status": "FAILURE",
  "responseCode": "REGISTRATION_DECLINED",
  "responseMessage": "Device binding was declined"
}
```

Mobile number mismatch when merchant mobile validation is enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_MISMATCH",
  "responseMessage": "SMS verification mismatch",
  "payload": {
    "customerMobileNumber": "9876543210"
  }
}
```

Device id does not match the preceding get-SMS-token step:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "invalid deviceId: deviceId was different in getSmsToken"
}
```

OS does not match the preceding get-SMS-token step:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "invalid os: os was different in getSmsToken"
}
```

VMN required but missing:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bindDeviceS2S2Route: vmnNumber"
}
```

VMN mismatch against the registration token's configured provider:

```json
{
  "status": "FAILURE",
  "responseCode": "VMN_MISMATCH",
  "responseMessage": "VMN Mismatch"
}
```

SMV IP validation failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IP Address"
}
```

SMV user-agent validation failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid User Agent"
}
```

OTP trigger pending before SMS/SMV verification is complete:

```json
{
  "status": "FAILURE",
  "responseCode": "TRIGGER_OTP_PENDING",
  "responseMessage": "Trigger OTP Pending"
}
```

OTP trigger failure:

```json
{
  "status": "FAILURE",
  "responseCode": "TRIGGER_OTP_FAILURE",
  "responseMessage": "Trigger OTP Failure"
}
```

OTP verification failure:

```json
{
  "status": "FAILURE",
  "responseCode": "OTP_VERIFICATION_FAILURE",
  "responseMessage": "OTP verification failure"
}
```

Device/mobile binding limit exceeded:

```json
{
  "status": "FAILURE",
  "responseCode": "BIND_DEVICE_LIMIT_EXCEEDED",
  "responseMessage": "Device bind attempted more than 3 times for this device/mobile number"
}
```

Configured daily bind limit exceeded:

```json
{
  "status": "FAILURE",
  "responseCode": "BIND_DEVICE_DAILY_LIMIT_EXCEEDED",
  "responseMessage": "Device bind attempted more than 5 times"
}
```

Configured short-window bind limit exceeded:

```json
{
  "status": "FAILURE",
  "responseCode": "BIND_DEVICE_TIME_LIMIT_EXCEEDED",
  "responseMessage": "Device bind attempted more than 2 times"
}
```

Blocked mobile number or device id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mobile number or DeviceId is blocked"
}
```

MNRL blocked mobile number:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMNRL",
  "responseMessage": "Mobile number blocked for MNRL"
}
```

Missing or invalid merchant headers/signature, signature mismatch, invalid request IP for an IP-whitelisted merchant, or disabled/blocked API:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the merchant is authenticated but the API is not enabled/allowed, the message can be:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Malformed `iat` or `x-timestamp`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired/stale `iat` or `x-timestamp`:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Merchant configuration missing for VMN/service-provider lookup, missing Passetto/hash key, Redis/decode issues, or unexpected internal processing error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Client Handling and Retry Guidance

- Treat `status=SUCCESS` and `responseCode=SUCCESS` as final device-binding success. Store `payload.deviceFingerPrint` and continue to account-discovery or activation-dependent flows.
- Treat `status=SUCCESS` and `responseCode=TRIGGER_OTP_SUCCESS` as OTP-trigger success only. It is not final device binding; call again with `otp` and `senderId`.
- Poll with backoff when you receive `SMS_VERIFICATION_PENDING` or `TRIGGER_OTP_PENDING`. Reuse the same token correlation data and regenerate `iat`, timestamp, signature, and encrypted envelope for each retry.
- Do not retry unchanged requests for validation errors, unknown token/content, missing device details, merchant auth/signature failures, API enablement failures, VMN mismatch, device-id/OS mismatch, blocked entity responses, or OTP verification failure. Fix the request, customer/device setup, merchant configuration, or customer-entered OTP first.
- For `SMS_VERIFICATION_EXPIRED` or `REGISTRATION_DECLINED`, restart the registration/SMS/SMV flow and use a new token.
- For bind-rate-limit responses, stop polling or repeated attempts for that device/customer until the configured cooling period expires.
- For `INTERNAL_SERVER_ERROR` caused by merchant configuration, contact Newton support or confirm onboarding configuration before retrying. For transient transport failures where no decrypted body is available, retry with backoff using a freshly signed/encrypted request.
- The endpoint does not provide a merchant idempotency key. Repeated calls with the same verified token are generally safe as a readback once the token is already activated, but clients should not create parallel registration attempts for the same customer/device.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:211)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1850)
- S2S envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S signature, API enablement, IP, and IAT validation: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp freshness validation: [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Request and response types: [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:161)
- Bind Device request validation: [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:282)
- Product route and flow branching: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:167)
- Merchant profile sharing behavior: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1118)
- Response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2358)
- Device fingerprint generation: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:1056)
- Registration-token state checks: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:94)
- Bind-and-activate business flow: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:313)
- Registration-token enablement and package-name requirement: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:366)
- Device binding attempt limits: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:396)
- OTP device-binding logic: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1350)
- VMN match validation: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1558)
- Shared bind-and-activate route: [src/Newton/Product/MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:1569)
- Bind-device rate limiter call: [src/Newton/Product/MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:922)
- Get-SMS-token-disabled and VMN service-provider configuration: [src/Newton/Utils/FeatureEnabled.hs](../../src/Newton/Utils/FeatureEnabled.hs:160)
- Registration-token lookup helpers: [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:651)
- SMS-content Redis lookup: [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:1117)
- Shared request validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:174)
- Mobile and VMN validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:501)
- Standard error helpers: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
