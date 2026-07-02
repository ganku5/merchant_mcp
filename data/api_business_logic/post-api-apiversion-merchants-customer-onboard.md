# Customer Onboard API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/onboard`

## Overview

Customer Onboard is a server-to-server API used to create or refresh a Newton merchant-customer profile and bind it to the customer's mobile number and device details.

This endpoint is intended for PPI customer onboarding, or for customer onboarding flows where the merchant backend is allowed to onboard the customer without the normal SMS-token initiation step. Newton creates or reuses the merchant customer, customer, device, and registration-token state needed by later UPI customer journeys. The response returns the merchant identifiers, normalized mobile number, and device details that the merchant should store against the customer profile.

Use this API when the merchant backend already has the customer mobile number and device information and needs Newton to register the customer/device profile before follow-up account, VPA, wallet, or device-binding workflows.

## Business Use Case

Customer Onboard helps merchants:

- Create a Newton customer profile for a merchant-owned `merchantCustomerId`.
- Register the customer's mobile number and current device details server-to-server.
- Seed the merchant-customer registration token state used by downstream onboarding and device-binding flows.
- Reuse an already-onboarded same mobile/device profile and return the existing device details where possible.
- Re-onboard a merchant customer with a different mobile number only when the merchant explicitly sends `deregisterOldCustomer: true`.
- Optionally verify customer name/mobile details against a remitter switch integration when that merchant configuration is enabled.

Do not use this API to create a bank account, create a VPA, authorize a payment, or confirm device activation by itself. It prepares customer/device onboarding state; later APIs still perform account discovery/linking, VPA, wallet, mandate, or transaction work.

## Integration Flow

1. Merchant chooses a stable `merchantCustomerId` for the customer.
2. Merchant collects the customer's mobile number and device details from the app or trusted backend source.
3. Merchant calls Customer Onboard with the encrypted or signed S2S envelope configured during onboarding.
4. Newton verifies the request envelope, merchant headers, timestamp, API access configuration, optional IP allowlist, and request signature.
5. Newton validates the decrypted request body.
6. Newton creates or reuses the merchant customer, checks existing customer/device state, and decides whether this is a new registration, same-device reuse, device update, or old-customer deregistration flow.
7. Newton creates or reuses the device and customer records, stores the registration token state, updates the merchant-customer profile, clears relevant registration rate-limit state, and returns `SUCCESS`.
8. Merchant stores the returned normalized mobile number and `deviceDetails` for later customer-profile reconciliation.

Important identifiers:

- `merchantCustomerId`: Merchant-generated customer id. This is the stable profile key for this endpoint.
- `merchantRequestId`: Optional merchant trace/reference id. It is echoed in the response but is not used by this code path as the idempotency lookup key.
- `device.deviceId` plus `device.ssid`: Used as the primary device identity for onboarding and same-device checks.
- `smsContent`: Optional registration-token content. If omitted, Newton generates a random value and does not return it.

## Handler Path

The route is mounted under `/api/{apiVersion}` as part of `WalletS2SAPIs`, rather than the main `ServerToServerAPIs` type alias. The server handler order maps the wallet S2S customer onboard route to `Core.customerOnboard`.

The request path is:

1. `getReqBody` unwraps the `EncRequest` by calling S2S merchant payload verification.
2. `merchantSignatureVerificationV2` checks `iat` for signed/encrypted calls, merchant headers, merchant configuration, API allow/block lists, optional IP allowlist, header signature for unsigned payload mode, and request timestamp.
3. `customerOnboardRoute` runs product validation and onboarding business logic.
4. `mkCustomerOnboardResponse` builds the decrypted success body.
5. `flowWithTrace` signs or encrypts the response according to the merchant response strategy.

This endpoint does not call a `TfS2S.*TransformerRoute`. The relevant transformer/helper behavior is the `OnboardRequest` PII encryption instance used before storing mobile/device fields and the `mkCustomerOnboardResponse` response builder.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/onboard
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
| `x-api-version` | Use the version shared during onboarding. The traced onboard flow does not add endpoint-specific behavior from this header. |
| `x-request-id` | Optional request id for troubleshooting and reconciliation. Newton generates one if omitted. |
| `x-session-id` | Optional session id. Defaults to `x-request-id` when omitted. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Path version segment. Use the value assigned during onboarding. |

## Authentication and Payload Handling

The request body type is `EncRequest OnboardRequest`. Depending on merchant configuration, the wire request can be:

- JWE encrypted payload containing a signed payload.
- JWS signed payload.
- Plain decrypted JSON payload accepted only where the merchant configuration permits it and protected by `x-merchant-signature`.

For signed or encrypted request bodies, the decrypted business payload must include `iat`, and `iat` must pass timestamp validation. All modes require merchant headers and a valid `x-timestamp`. For plain JSON signature mode, the signature is verified over merchant id, merchant channel id, optional sub-merchant headers, timestamp, and raw body, using the signing strategy and API key configured for the merchant.

The response body is returned according to the merchant's response strategy:

- JWS response when response strategy is `JWS`.
- JWE response when response strategy is `JWS_AND_JWE`.
- Plain decrypted JSON body with `X-Response-Signature` when using the non-JWS/JWE response path.

The examples in this guide are decrypted response bodies, not the exact encrypted wire envelope.

## Request

### Required Minimum

For most new domestic integrations, send a country code plus a 10-digit mobile number:

```json
{
  "merchantCustomerId": "CUST10001",
  "countryCode": "91",
  "mobileNumber": "9876543210",
  "packageName": "com.merchant.app",
  "device": {
    "deviceId": "a1b2c3d4e5",
    "manufacturer": "Google",
    "model": "Pixel 8",
    "version": "14",
    "os": "ANDROID",
    "ssid": "sim-slot-1"
  },
  "iat": "1719835200000"
}
```

If `countryCode` is omitted, request validation expects a 12-digit numeric mobile value:

```json
{
  "merchantCustomerId": "CUST10001",
  "mobileNumber": "919876543210",
  "packageName": "com.merchant.app",
  "device": {
    "deviceId": "a1b2c3d4e5",
    "manufacturer": "Google",
    "model": "Pixel 8",
    "version": "14",
    "os": "ANDROID",
    "ssid": "sim-slot-1"
  },
  "iat": "1719835200000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's stable customer identifier. The validator requires it to be non-empty. This value is used to find or create the Newton merchant-customer profile. |
| `smsContent` | string | No | If omitted, Newton generates a random 35-character value for registration-token creation. The generated value is not returned. | Optional SMS/registration-token content used when creating or finding the merchant-customer registration token. Send a stable value if the merchant wants retries to reuse the same token-content lookup. |
| `device` | object | Yes | No default. | Customer device details. `device.deviceId` and `device.ssid` are used for device lookup and same-device checks. |
| `countryCode` | string | No | If omitted, `mobileNumber` must be exactly 12 numeric digits. | Country code for `mobileNumber`. May include a leading `+`. Length must be at most 7 characters and must otherwise be numeric. For India, use `91` or `+91`. |
| `mobileNumber` | string | Yes | No default. | Customer mobile number. With `countryCode: "91"` or `"+91"`, send a 10-digit domestic number. Without `countryCode`, send a 12-digit value such as `919876543210`. |
| `packageName` | string | Yes | No default. | Merchant app package name stored on the registration token and merchant-customer profile. This top-level field controls the response `deviceDetails.packageName` for new registrations. |
| `deregisterOldCustomer` | boolean | No | Omitted behaves like `false`. | Set `true` only when the same `merchantCustomerId` already points to a different mobile/customer and the merchant intentionally wants Newton to deregister the old customer before onboarding the new one. |
| `merchantRequestId` | string | No | Omitted from response when not supplied. | Optional merchant trace/reference id. Max 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore. Echoed in the response payload; not used as the main idempotency lookup key in this code path. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Plain-body header-signature mode does not validate request-body `iat`, but production signed/encrypted modes require it. | Issued-at timestamp used by request verification. Send a valid timestamp in the format shared during onboarding, commonly Unix milliseconds. |
| `udfParameters` | string | No | Omitted from response when not supplied. | Merchant-defined metadata. Stored on the registration token and echoed in the success response. This request type does not apply additional `udfParameters` validation. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not returned when omitted.

- `smsContent`: omitted generates a random 35-character token content internally. Because the generated value is not returned, retries without `smsContent` can create or point the merchant-customer profile at a new registration token.
- `countryCode`: omitted requires a 12-digit numeric `mobileNumber` during validation. Domestic 10-digit mobile numbers should be sent with `countryCode`.
- `mobileNumber`: normalized before storage and response. Domestic values are normalized to `91` plus the 10-digit mobile number.
- `deregisterOldCustomer`: omitted behaves as `false` and will not delink a different old customer/mobile association.
- `merchantRequestId`: echoed only when supplied; it does not prevent duplicate processing by itself.
- `device.packageName`: optional nested value. The onboarding flow uses the top-level `packageName` for registration-token/profile updates and response fallback.
- `customerName`: not request-supplied. It is returned only when Newton can get it from existing stored customer data or from enabled remitter-switch verification.

### Validation Notes

Newton validates the decrypted request before product logic:

- `merchantCustomerId`, `packageName`, and required device text fields must be non-empty.
- `smsContent`, `device.deviceFingerPrint`, and `device.packageName` must be non-empty if supplied.
- `countryCode`, when supplied, must be at most 7 characters and match `+` optional followed by digits.
- `mobileNumber` must be numeric. With no `countryCode`, it must be exactly 12 digits. With `countryCode`, it must be shorter than 19 digits.
- `merchantRequestId`, when supplied, must be 1 to 35 characters and match the allowed merchant request id pattern.

After validation, domestic mobile normalization is stricter for `countryCode` values `91` and `+91`: valid forms are 10 digits, `91` plus 10 digits, `0` plus 10 digits, or `+91` plus 10 digits.

## Nested Request Objects

### `device`

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `deviceFingerPrint` | string | No | Omitted from stored encrypted request payload when not supplied. The response fingerprint is computed independently. | Optional merchant/app-provided device fingerprint. This is not the same as response `deviceDetails.deviceFingerPrint`. |
| `deviceId` | string | Yes | No default. | Primary device identifier used as the stored device fingerprint and same-device comparison value. |
| `manufacturer` | string | Yes | No default. | Device manufacturer. Newton logs a mismatch if an existing device with the same `deviceId`/`ssid` has different manufacturer or model. |
| `model` | string | Yes | No default. | Device model. |
| `version` | string | Yes | No default. | Device/OS version. If the existing device version differs, Newton updates it. |
| `os` | string | Yes | No default. | Device OS, for example `ANDROID` or `IOS`. The validator only checks non-empty text. |
| `ssid` | string | Yes | No default. | SIM/subscription identifier used with `deviceId` for device lookup. |
| `packageName` | string | No | No default. | Optional nested package name. The top-level `packageName` remains the value used by onboarding/profile update behavior. |

## Request Examples

### New Domestic Customer

```json
{
  "merchantCustomerId": "CUST10001",
  "countryCode": "91",
  "mobileNumber": "9876543210",
  "packageName": "com.merchant.app",
  "device": {
    "deviceId": "android-device-abc123",
    "manufacturer": "Google",
    "model": "Pixel 8",
    "version": "14",
    "os": "ANDROID",
    "ssid": "sim-slot-1"
  },
  "merchantRequestId": "ONBOARD10001",
  "iat": "1719835200000",
  "udfParameters": "{\"source\":\"merchant_app\"}"
}
```

### Customer With Merchant-Supplied Registration Content

Send `smsContent` when the merchant wants repeated attempts to reuse the same registration-token content instead of letting Newton generate a new random value.

```json
{
  "merchantCustomerId": "CUST10002",
  "smsContent": "REG-CUST10002-20240701",
  "countryCode": "+91",
  "mobileNumber": "9812345678",
  "packageName": "com.merchant.app",
  "device": {
    "deviceId": "ios-device-def456",
    "manufacturer": "Apple",
    "model": "iPhone 15",
    "version": "17.5",
    "os": "IOS",
    "ssid": "primary-sim",
    "packageName": "com.merchant.app"
  },
  "merchantRequestId": "ONBOARD10002",
  "iat": "1719835200000"
}
```

### Re-Onboard Same Merchant Customer With New Mobile Number

Use this only when the merchant has intentionally decided to replace the old customer/mobile association.

```json
{
  "merchantCustomerId": "CUST10003",
  "countryCode": "91",
  "mobileNumber": "9900011122",
  "packageName": "com.merchant.app",
  "device": {
    "deviceId": "android-device-xyz789",
    "manufacturer": "Samsung",
    "model": "Galaxy S24",
    "version": "14",
    "os": "ANDROID",
    "ssid": "sim-2"
  },
  "deregisterOldCustomer": true,
  "merchantRequestId": "ONBOARD10003-RETRY1",
  "iat": "1719835200000"
}
```

### Domestic Customer Without `countryCode`

```json
{
  "merchantCustomerId": "CUST10004",
  "mobileNumber": "919812345678",
  "packageName": "com.merchant.app",
  "device": {
    "deviceId": "android-device-no-cc",
    "manufacturer": "OnePlus",
    "model": "OnePlus 12",
    "version": "14",
    "os": "ANDROID",
    "ssid": "sim-slot-1"
  },
  "iat": "1719835200000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Customer onboard result. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton for the calling merchant. |
| `merchantChannelId` | string | Merchant channel id configured with Newton for the calling merchant. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `merchantRequestId` | string | Echoed from the request when supplied. Omitted when not supplied. |
| `customerMobileNumber` | string | Normalized customer mobile number with leading zero padding removed. For India domestic flows this is commonly `91` plus the 10-digit mobile number. |
| `customerName` | string | Returned only when available from remitter-switch verification or existing stored customer data. Omitted otherwise. |
| `deviceDetails` | object | Device details Newton registered or reused for this merchant customer. |

### `payload.deviceDetails`

| Field | Type | Description |
| --- | --- | --- |
| `deviceFingerPrint` | string | SHA-256 hash of the returned `deviceId` concatenated with returned `ssid`. This is generated by Newton and is not an echo of request `device.deviceFingerPrint`. |
| `deviceId` | string | Registered device identifier. For a new registration, this is based on request `device.deviceId`. |
| `manufacturer` | string | Device manufacturer. |
| `model` | string | Device model. |
| `version` | string | Device/OS version after any version update. |
| `os` | string | Device OS. |
| `ssid` | string | Registered SIM/subscription identifier. |
| `packageName` | string | Existing stored merchant-customer package name for same-device reuse when available; otherwise the request top-level `packageName`. |

### Example Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST10001",
    "merchantRequestId": "ONBOARD10001",
    "customerMobileNumber": "919876543210",
    "deviceDetails": {
      "deviceFingerPrint": "6a78f7e5b5e5e1a9c5cf21c4f2f3d4e1c7a44cf6a8e8f0a91b7b58e9b8f6d123",
      "deviceId": "android-device-abc123",
      "manufacturer": "Google",
      "model": "Pixel 8",
      "version": "14",
      "os": "ANDROID",
      "ssid": "sim-slot-1",
      "packageName": "com.merchant.app"
    }
  },
  "udfParameters": "{\"source\":\"merchant_app\"}"
}
```

### Response With Customer Name

When remitter-switch verification is enabled for the merchant and the downstream lookup succeeds, or when an existing same-device customer profile already has a stored name, `customerName` is returned.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST10002",
    "merchantRequestId": "ONBOARD10002",
    "customerMobileNumber": "919812345678",
    "customerName": "Asha Sharma",
    "deviceDetails": {
      "deviceFingerPrint": "5e84a6d22d8072caa0b78f8f0b76b2f93f44a68b14e3d72c8f66e22c7aa15d90",
      "deviceId": "ios-device-def456",
      "manufacturer": "Apple",
      "model": "iPhone 15",
      "version": "17.5",
      "os": "IOS",
      "ssid": "primary-sim",
      "packageName": "com.merchant.app"
    }
  }
}
```

### Same Customer And Same Device

If the merchant customer already has an old customer and device, the request mobile matches the stored mobile, the request device matches stored `deviceId`/`ssid`, and a customer name is present, Newton returns `SUCCESS` with existing device details instead of creating a new registration. Treat this as an already-onboarded/same-profile success.

### Status Interpretation

Treat `status: "SUCCESS"` and `responseCode: "SUCCESS"` as confirmation that Newton accepted or reused the merchant customer/device onboarding state. It does not mean that a bank account has been linked, a VPA has been created, or a payment/mandate has been authorized.

For all non-success bodies, use `responseCode` for programmatic handling and `responseMessage` for diagnostics. HTTP status can vary by layer: validation can be returned with an HTTP 200 error body, business conflicts can use 422, authentication can use 401, malformed signed/encrypted payloads can use 400, and unexpected/downstream failures can use 500.

## Error Handling

Failure responses use the standard Newton error body shape after decryption when the response is wrapped by the configured S2S response strategy: `status: "FAILURE"` with a concrete `responseCode` and diagnostic `responseMessage`.

### Request Validation Failures

Validation runs before customer onboarding logic. Typical examples include empty required fields, invalid mobile length, invalid country code, or invalid `merchantRequestId`.

Invalid mobile without `countryCode`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mobile length is not equal to 12\""
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

Domestic mobile value that passes field validation but cannot be normalized:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mobile number validation failed for domestic"
}
```

Client handling: fix the request and send a new request. Do not retry unchanged validation failures.

### Authentication, Signature, Encryption, And Access Failures

Missing or invalid merchant headers, missing signature in unsigned-body mode, signature mismatch, invalid IP allowlist, blocked API, or not-allowed API configuration fail before product logic.

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
  "responseMessage": "Error in $: not enough input"
}
```

Client handling: check merchant ids, configured API access, timestamp freshness, request body canonicalization, key id, JWS/JWE format, and signature/encryption keys. Retry only after correcting the auth/envelope issue.

### Existing Customer Or Device Business Failures

If the same `merchantCustomerId` already points to a different mobile/customer and `deregisterOldCustomer` is absent or `false`, Newton rejects the request.

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_DEREGISTER_CUSTOMER",
  "responseMessage": "OPERATION_RESTRICTED_DEREGISTER_CUSTOMER"
}
```

Client handling: confirm the customer really needs to be re-onboarded with a new mobile. If yes, resend with `deregisterOldCustomer: true`; otherwise keep using the existing profile.

When `deregisterOldCustomer: true` is sent, Customer Onboard calls the deregister flow for the old profile before continuing. That delegated flow can still block replacement if the old profile has active mandates, active UPI Lite, active delegate links, invalid/missing profile state, or another deregister business failure.

Active mandate on the old profile:

```json
{
  "status": "FAILURE",
  "responseCode": "JPDL",
  "responseMessage": "You have active mandate(s), deregistration is not allowed. Please deregister after all the mandates are executed or revoke existing mandates before deregistering."
}
```

Active UPI Lite on the old profile:

```json
{
  "status": "FAILURE",
  "responseCode": "JPLA",
  "responseMessage": "You have an active UPI LITE Account, de-registration is not allowed. Please de-register yourself after the UPI LITE account is de-registered."
}
```

Active delegate links on the old profile:

```json
{
  "status": "FAILURE",
  "responseCode": "JPDA",
  "responseMessage": "You have active delegate links, deregistration is not allowed. Please remove all the delegate links before deregistering."
}
```

Client handling: resolve the blocking old-profile state first, then retry the onboard request with the same replacement details.

If the merchant configuration `disableDeviceUpdateInOnboardApi` is enabled and the request has the same mobile/customer but a different `deviceId` or `ssid`, Newton rejects the device update.

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_NOT_ALLOWED",
  "responseMessage": "OPERATION_RESTRICTED_DIFFERENT_DEVICE"
}
```

Client handling: do not retry unchanged. Use the merchant-supported device-change or deregister/re-onboard process.

### Remitter-Switch Verification Failures

When both `isRemitterSwitchEnabled` and `verifyCustomerDetailsFromRemitter` are enabled for the merchant, Newton fetches customer details from the remitter switch. If the mobile number from the switch does not match the request, onboarding fails.

```json
{
  "status": "FAILURE",
  "responseCode": "JPMNC",
  "responseMessage": "Passed mobileNumber does not match with mobileNumber from CBS"
}
```

If the remitter switch returns a customer name that starts with `xxx`, onboarding fails.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_CUSTOMER_NAME_CBS",
  "responseMessage": "INVALID_CUSTOMER_NAME_CBS"
}
```

Client handling: verify the customer identity/mobile mapping with the merchant source system or Newton support. Retry only after the customer details are corrected.

### Downstream Or Unexpected Failures

Remitter-switch failures, missing downstream payloads, malformed merchant store configuration, Passetto/key/hash issues, database failures, or unexpected missing records can return internal server errors.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry transient 500s with backoff if the request is otherwise valid. If repeated failures occur for the same customer, contact Newton with `x-request-id`, `merchantCustomerId`, `merchantRequestId` if supplied, and timestamp.

## Retry, Idempotency, And Client Handling

- Use a stable `merchantCustomerId` for the customer. This is the primary profile key used by the onboarding flow.
- `merchantRequestId` is useful for logs and reconciliation because it is placed in the trace id and echoed in the response, but it is not the deduplication key for this endpoint.
- If a request times out and the client did not receive a response, retry with the same `merchantCustomerId`, mobile number, device details, top-level `packageName`, and `smsContent` if one was supplied.
- If `smsContent` is omitted, Newton generates a new random value on each registration attempt. For strict retry behavior around registration-token lookup, send a deterministic `smsContent`.
- Do not switch `deregisterOldCustomer` from omitted/`false` to `true` on an automatic retry. Only send `true` after the merchant has confirmed that replacing the old customer/mobile association is intended.
- Do not retry unchanged validation, authentication, API-not-enabled, mobile mismatch, or device-update-restricted failures.
- Retry transient `INTERNAL_SERVER_ERROR` responses with bounded exponential backoff. Reconcile the latest customer state before issuing downstream account/VPA/payment calls.
- Treat a `SUCCESS` response for an already-onboarded same device as successful idempotent completion for the customer/device profile.

## Source References

- API mount under `/api/{apiVersion}`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- Wallet S2S route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1260)
- Customer onboard handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4851)
- Wallet S2S server handler mapping: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:611)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request body unwrap path: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- S2S response signing/encryption path: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:66)
- Merchant signature/API access verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request and response types, validators, PII encryption: [src/Newton/Product/Merchant/Customer/Types.hs](../../src/Newton/Product/Merchant/Customer/Types.hs:161)
- Product onboarding route: [src/Newton/Product/Merchant/Customer/CustomerOnboard.hs](../../src/Newton/Product/Merchant/Customer/CustomerOnboard.hs:44)
- Customer registration branch: [src/Newton/Product/Merchant/Customer/CustomerOnboard.hs](../../src/Newton/Product/Merchant/Customer/CustomerOnboard.hs:104)
- Remitter-switch verification: [src/Newton/Product/Merchant/Customer/CustomerOnboard.hs](../../src/Newton/Product/Merchant/Customer/CustomerOnboard.hs:196)
- Success response builder: [src/Newton/Product/Merchant/Customer/Helper.hs](../../src/Newton/Product/Merchant/Customer/Helper.hs:119)
- Delegated deregister route for `deregisterOldCustomer`: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:765)
- Deregister active mandate, UPI Lite, and delegate checks: [src/Newton/Product/CustomerV2.hs](../../src/Newton/Product/CustomerV2.hs:168)
- Deregister response error conversion: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1102)
- Request validation error wrapper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Mobile normalization helpers: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:155)
- Field validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- Existing customer/device lookup: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:843)
- Device find/create behavior: [src/Newton/Storage/QueriesMiddleware/Device.hs](../../src/Newton/Storage/QueriesMiddleware/Device.hs:70)
- Merchant-customer find/create behavior: [src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs:58)
- Customer find/create behavior: [src/Newton/Storage/QueriesMiddleware/Customer.hs](../../src/Newton/Storage/QueriesMiddleware/Customer.hs:130)
- Registration-token find/create behavior: [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:962)
- Success and generic error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
- Unauthorized/API access constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
- Device/customer onboard business error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:938)
- Remitter-switch error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1167)
