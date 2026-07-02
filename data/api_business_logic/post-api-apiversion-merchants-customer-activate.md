# Activate Customer API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/activate`

## Overview

Activate Customer is a server-to-server API used to complete a multibank customer/device activation after Newton has already created a registration token and verified the device-binding step.

The merchant calls this API with the merchant customer id, the customer's mobile number, and the registration content returned or used during the preceding registration/bind flow. Newton validates the merchant, request signature or encrypted payload, registration token state, activation expiry, mobile number, and customer/device records. On success, Newton links the merchant customer to the verified customer/device, marks the registration token activated, refreshes the merchant-customer session state, and returns the customer and device identifiers that the merchant should store for later customer APIs.

Use this API after `getSmsToken` plus `bindDevice`, or after the corresponding SMV-based bind flow, when the merchant backend is ready to activate the customer profile for subsequent UPI account, VPA, token, or transaction journeys.

## Business Use Case

Activate Customer helps merchants:

- Finalize customer onboarding after SMS or SMV device verification has succeeded.
- Bind the merchant's `merchantCustomerId` to the customer/mobile/device discovered during registration.
- Reuse a previously activated registration token safely when the client retries after an uncertain network result.
- Control whether an old merchant-customer profile for the same customer may be deregistered during activation.
- Receive the normalized customer mobile number and device fingerprint required by later S2S customer APIs.

Do not use this API as the first step in onboarding. The registration token must already exist, and the token must be bound/verified unless it has already been activated by an earlier successful call.

## Integration Flow

1. Merchant starts customer registration and obtains registration content through the applicable registration or SMS-token API.
2. Merchant completes the device binding verification step through `POST /api/{apiVersion}/merchants/customer/bindDevice` or an SMV flow.
3. Merchant calls `activate` with `merchantCustomerId`, mobile number, `deregisterOldCustomer`, and one of `smsContent`, `attemptIdentifier`, or `smvContent`.
4. Newton validates the encrypted/signed S2S payload and merchant configuration.
5. Newton normalizes the mobile number, looks up the registration token, checks expiry/decline/bound state, and validates the mobile number against the verified customer where merchant configuration requires it.
6. If activation is allowed, Newton attaches the merchant customer to the verified customer/device, optionally deregisters older profiles, marks the registration token activated, and returns success.
7. Merchant stores `merchantCustomerId`, `customerMobileNumber`, and `deviceFingerPrint` for later customer-profile calls.

Important identifiers:

- `merchantCustomerId`: Merchant-owned customer identifier. This becomes the merchant-facing profile id for subsequent S2S calls.
- `smsContent`: Registration SMS content/token from the SMS registration flow.
- `attemptIdentifier`: Alternate registration attempt identifier. Used only when `smsContent` and `smvContent` are not sent.
- `smvContent`: Registration content for SMV flows. If present, Newton treats the request as an SMV activation and uses this value for token lookup.
- `deviceFingerPrint`: Newton-returned device fingerprint derived from the verified device record. Store it for later APIs that ask for device fingerprint.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/activate
```

Examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | JSON transport envelope. |
| `x-merchant-id` | Yes | Merchant id configured during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id configured during onboarding. |
| `x-timestamp` | Yes | Timestamp included in merchant signature verification and freshness checks. |
| `x-merchant-signature` | Yes for the plain signed S2S request mode | Merchant signature over the configured S2S signing string. |
| `x-forwarded-for` | Conditional | Required only when the merchant has IP whitelisting configured. |
| `x-request-id` | No | Merchant/client request id for tracing. Newton generates one when omitted. |

The path variable `apiVersion` is required. Use the API version assigned during onboarding.

Authentication follows the Newton S2S process shared during onboarding. This route's Servant type is `EncRequest ActivateCustomerS2SRequest`, but the decrypted business payload type does not contain an `iat` field. In the current handler, the plain business payload signed with merchant headers is the path that bypasses payload-`iat` validation. Use JWS/JWE for this endpoint only if Newton has explicitly confirmed that mode for your merchant and route.

The common `EncRequest` transport shapes are:

| Transport body | Fields | Notes |
| --- | --- | --- |
| JWE encrypted body | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag` | Use only if explicitly enabled for this endpoint. |
| JWS signed body | `payload`, `signature`, `protected` | Use only if explicitly enabled for this endpoint. |
| Plain signed business payload | Business fields directly | Current route-supported path for this API; Newton verifies `x-merchant-signature`. |

Responses use the matching onboarded response mode and should be verified/decrypted before reading the business response. Do not add `iat` to the decrypted business payload; it is not part of `ActivateCustomerS2SRequest`.

## Request

### Required Minimum

For the standard SMS registration path, send `smsContent`:

```json
{
  "merchantCustomerId": "CUST000123",
  "smsContent": "NEWTON-SMS-CONTENT-9f3a",
  "countryCode": "+91",
  "mobileNumber": "9876543210",
  "deregisterOldCustomer": "true"
}
```

For a flow where Newton gave an alternate attempt identifier, send `attemptIdentifier` instead of `smsContent`:

```json
{
  "merchantCustomerId": "CUST000124",
  "attemptIdentifier": "ATTEMPT-20260702-000124",
  "mobileNumber": "919876543211",
  "deregisterOldCustomer": "false"
}
```

For an SMV flow, send `smvContent`:

```json
{
  "merchantCustomerId": "CUST000125",
  "smvContent": "SMV-CONTENT-7b8c",
  "countryCode": "91",
  "mobileNumber": "9876543212",
  "deregisterOldCustomer": "true",
  "udfParameters": "{\"registrationSource\":\"smv\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer/profile id. Must be 1 to 256 characters and match Newton's merchant-customer-id character rules. |
| `smsContent` | string | Conditional | No default. Required unless `attemptIdentifier` or `smvContent` is supplied. | Registration content from the SMS-token/device-bind flow. Used for token lookup when `smvContent` is omitted. If both `smsContent` and `attemptIdentifier` are sent, `smsContent` takes precedence. |
| `attemptIdentifier` | string | Conditional | No default. Used only when `smsContent` and `smvContent` are omitted. | Alternate registration attempt identifier accepted by the same token lookup path. Must be non-empty when sent. |
| `smvContent` | string | Conditional | No default. If sent, Newton treats the request as an SMV activation and ignores `smsContent`/`attemptIdentifier` for token lookup. | Registration content for SMV-based verification. Must be non-empty when sent. |
| `countryCode` | string | No | If omitted, `mobileNumber` must be a 12-digit domestic number such as `919876543210`. | Optional country code. For Indian 10-digit numbers, send `91` or `+91`. Max length is 7 and only digits with optional leading `+` are allowed. |
| `mobileNumber` | string | Yes | No default. | Customer mobile number. With no `countryCode`, validation expects exactly 12 digits. With `countryCode`, validation allows fewer than 19 digits. Newton normalizes domestic numbers to a `91`-prefixed value before activation. |
| `deregisterOldCustomer` | string | Yes | No default. Must be supplied as `true` or `false`. | Controls whether Newton may deregister/delink an old merchant-customer profile for the same verified customer. Send `true` when the customer is intentionally moving to this `merchantCustomerId`. Send `false` to fail if an old/existing profile would need deregistration. |
| `udfParameters` | string | No | Omitted from the response when omitted in the request. | JSON-object string for merchant metadata. Echoed in the success response. Must parse as a JSON object and pass Newton's text validation. |

### Validation Notes

- At least one of `smsContent`, `attemptIdentifier`, or `smvContent` is required for a successful business flow. The type validator only checks these fields when present, so clients should enforce this requirement before sending the request.
- `deregisterOldCustomer` must be the string `true` or `false`, case-insensitive.
- Empty optional strings are rejected when supplied.
- `merchantCustomerId` must be non-empty, at most 256 characters, and match the allowed merchant-customer-id pattern.
- `udfParameters` must be a JSON object encoded as a string, for example `"{\"key\":\"value\"}"`.
- If `countryCode` is omitted, send a 12-digit domestic mobile number. If sending a 10-digit Indian mobile number, include `countryCode` as `91` or `+91`.
- Newton may validate the supplied mobile number against the mobile number discovered during verification, depending on merchant configuration.

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not returned when omitted.

- `countryCode`: no value is stored from the request when omitted. Mobile validation then treats the mobile number as a domestic 12-digit value.
- `smsContent` / `attemptIdentifier` / `smvContent`: no generated fallback. One of these must identify the registration token.
- `deregisterOldCustomer`: no default. The API rejects the request if it is missing or not a boolean string.
- `udfParameters`: no default. It is echoed on success only when supplied.

## Request Examples

### SMS Registration Activation

```json
{
  "merchantCustomerId": "CUST000123",
  "smsContent": "NEWTON-SMS-CONTENT-9f3a",
  "countryCode": "+91",
  "mobileNumber": "9876543210",
  "deregisterOldCustomer": "true",
  "udfParameters": "{\"journey\":\"upi_onboarding\",\"appSessionId\":\"S123\"}"
}
```

### Activation With 12-Digit Mobile Number

Use this shape when you omit `countryCode`.

```json
{
  "merchantCustomerId": "CUST000126",
  "smsContent": "NEWTON-SMS-CONTENT-1a2b",
  "mobileNumber": "919876543213",
  "deregisterOldCustomer": "true"
}
```

### Activation With Attempt Identifier

```json
{
  "merchantCustomerId": "CUST000124",
  "attemptIdentifier": "ATTEMPT-20260702-000124",
  "mobileNumber": "919876543211",
  "deregisterOldCustomer": "false"
}
```

### SMV Activation

```json
{
  "merchantCustomerId": "CUST000125",
  "smvContent": "SMV-CONTENT-7b8c",
  "countryCode": "91",
  "mobileNumber": "9876543212",
  "deregisterOldCustomer": "true"
}
```

## Response

### Success Response

Decrypted business response:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST000123",
    "customerMobileNumber": "919876543210",
    "deviceFingerPrint": "a1f6b0f1c8d4e9"
  },
  "udfParameters": "{\"journey\":\"upi_onboarding\",\"appSessionId\":\"S123\"}"
}
```

If `udfParameters` was omitted in the request, it is omitted in the response:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST000126",
    "customerMobileNumber": "919876543213",
    "deviceFingerPrint": "d8b3f6a9c0e1"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when activation is complete or the registration token was already activated successfully. |
| `responseCode` | string | `SUCCESS` for successful activation. |
| `responseMessage` | string | `SUCCESS` for successful activation. |
| `payload` | object | Activation result identifiers. |
| `udfParameters` | string | Echo of request `udfParameters`; omitted when not supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Newton merchant id associated with the request headers. |
| `merchantChannelId` | string | Newton merchant channel id associated with the request headers. |
| `merchantCustomerId` | string | Merchant customer id supplied in the request. |
| `customerMobileNumber` | string | Customer mobile number from the verified customer record after decryption. Domestic numbers are normally returned with the `91` prefix. Leading zeroes are trimmed. |
| `deviceFingerPrint` | string | Device fingerprint derived from the verified device record. Store this for APIs that require device fingerprint validation. |

### Interpreting Success

Treat `status = "SUCCESS"` and `responseCode = "SUCCESS"` as the activation result. The response does not include VPA/account details or separate `isDeviceBound` / `isDeviceActivated` flags. After success, use the normal customer/account APIs to fetch account state.

If the same registration token has already been activated and still has a customer/device record, Newton returns the same success shape instead of failing the request. This makes retrying the same request safe after a client timeout.

## Error Handling

Failures are returned through the same S2S response transport. After decryption or verification, business errors use this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "ERROR_CODE",
  "responseMessage": "Human readable message"
}
```

Some business failures are intentionally returned with HTTP 200 and a decrypted `status` of `FAILURE`. Auth/encryption failures generally use HTTP 401, malformed encrypted payloads can use HTTP 400, and unexpected server failures can use HTTP 500. Clients should always read the decrypted `status`, `responseCode`, and `responseMessage` in addition to HTTP status.

### Concrete Failure Scenarios

#### Validation Failure

`deregisterOldCustomer` is missing or not a boolean string, `merchantCustomerId` fails format validation, an optional string is empty, `mobileNumber` has the wrong length, or `udfParameters` is not a JSON-object string.

Example, `deregisterOldCustomer: "yes"`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "BoolStringValidation \"Parameter is not true or false\""
}
```

Example, `countryCode` omitted but a 10-digit mobile is sent:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mobile length is not equal to 12\""
}
```

#### Authentication, Signature, or Encryption Failure

The merchant headers are missing, the encrypted payload cannot be decrypted, the JWS signature fails verification, `x-merchant-signature` is missing/invalid for a plain payload, the timestamp is invalid, or the request IP is not allowed.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

#### Merchant Configuration Failure

The merchant exists but this API is blocked or not present in the merchant's allowed API list.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

#### Registration Token Not Found

The selected `smsContent`, `attemptIdentifier`, or `smvContent` does not map to a registration token.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid smsContent"
}
```

#### Activation Token Expired

The registration token was found, but the activate-call expiry window has passed.

```json
{
  "status": "FAILURE",
  "responseCode": "REGISTRATION_TOKEN_EXPIRED",
  "responseMessage": "SMS token expired for activation"
}
```

#### Device Binding Declined

The registration token was declined before activation. For SMV flows, Newton returns the stored decline reason when available. For SMS flows, the stored reason is returned only when dynamic decline messages are enabled for the merchant; otherwise the default message is returned.

```json
{
  "status": "FAILURE",
  "responseCode": "REGISTRATION_DECLINED",
  "responseMessage": "Device binding was declined"
}
```

#### SMS Verification Still Pending

The registration token exists but has not been marked bound/verified yet.

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_PENDING",
  "responseMessage": "SMS verification pending"
}
```

#### Mobile Number Mismatch

When merchant configuration enables mobile-number validation, the supplied mobile number hash must match the verified customer's mobile number.

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_MISMATCH",
  "responseMessage": "SMS verification mismatch",
  "payload": {
    "tag": "SMSVerificationMismatchPayload",
    "contents": {
      "customerMobileNumber": "919876543210"
    }
  }
}
```

#### Old Customer Deregistration Required

If the verified customer is already linked to another merchant-customer profile and the request sends `deregisterOldCustomer: "false"`, Newton fails instead of moving the customer.

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_DEREGISTER_CUSTOMER",
  "responseMessage": "Deregister customer to continue device binding"
}
```

#### Downstream Deregistration Failure

When `deregisterOldCustomer: "true"` requires Newton to deregister an old profile, a downstream UPI/deregistration service can return a failure code and message. Newton passes that downstream code/message through when available.

```json
{
  "status": "FAILURE",
  "responseCode": "U91",
  "responseMessage": "UPI service is not reachable at the moment"
}
```

If the downstream failure does not include a usable code/message, Newton returns an internal server error response.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

#### Unexpected Processing Error

Unexpected missing records or encryption/decryption failures can return a generic internal server error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling

- If the client times out after sending `activate`, retry the same decrypted business request with the same registration content. If the first call completed, Newton returns `SUCCESS` for the already activated token.
- Do not retry with a new `merchantCustomerId` for the same customer unless the user is intentionally moving profiles and the request uses the correct `deregisterOldCustomer` value.
- Do not retry expired, declined, or pending-verification failures blindly. Restart the registration/bind flow, ask the user to complete verification, or surface the decline as appropriate.
- Retry auth/encryption failures only after correcting headers, timestamp, signature, key id, or encryption format.
- For `OPERATION_RESTRICTED_DEREGISTER_CUSTOMER`, retry with `deregisterOldCustomer: "true"` only if the merchant has confirmed that the old customer profile should be deregistered.
- For `SERVICE_UNAVAILABLE`, downstream pass-through errors, or `INTERNAL_SERVER_ERROR`, use bounded retries with the same request and reconcile by checking the customer profile before starting a new registration attempt.

## Source References

- API path capture: [NewtonAPIs](../../src/Newton/App/Routes/Core.hs:114)
- Route definition: [ServerToServerAPIs activate customer route](../../src/Newton/App/Routes/Core.hs:218)
- Route handler: [activateCustomerS2S](../../src/Newton/App/Routes/Core.hs:1874)
- Request envelope types: [EncRequest and EncResponse](../../src/Newton/Types/API/RequestBody.hs:48)
- Payload verification: [merchantPayloadVerificationS2S](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature and API enablement checks: [merchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request, response, encryption/decryption, and validation types: [ActivateCustomerS2SRequest](../../src/Newton/Types/API/ServerToServer/Customer.hs:787)
- Product route and token state checks: [activateCustomerS2SRoute](../../src/Newton/Product/MerchantV2.hs:379)
- Mobile normalization: [getMobileNumber](../../src/Newton/Utils/Utils.hs:155)
- Registration token lookup: [findMerchantCustomerRegistrationToken](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:651)
- Activation business logic: [activateDeviceSDK](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:988)
- Old-profile deregistration branch: [deregisterOldMerchantCustomer](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1151)
- Success response transformer: [mkActivateCustomerS2SResponse](../../src/Newton/Utils/Transformers/Transformer9.hs:2425)
- Shared validation helpers: [Newton.Validation.Common](../../src/Newton/Validation/Common.hs:174)
- Error response constants: [Newton.Constants.APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:43)
