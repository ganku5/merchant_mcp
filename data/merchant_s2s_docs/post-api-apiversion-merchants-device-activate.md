# Activate Device API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/device/activate`

## Overview

Activate Device is a Newton server-to-server API used to finalize a customer's device registration after the device-bind flow has produced a merchant customer registration token.

The merchant calls this API with the merchant customer id, the registration token reference id, the customer mobile number, and a `shouldActivate` decision. When activation is requested, Newton links the token's customer and device to the merchant customer profile, marks the registration token as activated, refreshes the merchant-customer cache, activates linked merchant-customer accounts for supported PSP modes, and returns the device/account state.

Use this API after the customer has completed the upstream device-binding or SMS-verification step and the merchant backend wants Newton to treat that device as active for subsequent UPI journeys.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Activate Device helps merchants:

- Complete S2S customer device registration after device bind verification.
- Confirm whether a registration token is bound and activated.
- Move the merchant customer profile to the latest customer, device, package, mobile, and registration-token mapping.
- Receive the customer's linked VPA/account list after successful activation.
- Detect already-activated tokens, stale or invalid registration tokens, mobile mismatch, and merchant-customer lookup failures before starting UPI actions that require an active device.

Call this API only for a registration token issued for the same customer/device registration journey. Do not call it as a general account-fetch API; use the account or customer-info APIs for later account refreshes.

## Integration Flow

1. Merchant completes the Newton device-bind flow and stores the returned `merchantCustomerRegistrationTokenReferenceId`.
2. Merchant calls `activate` with `shouldActivate: "true"` when the customer should be activated on that bound device.
3. Newton decrypts/verifies the request envelope and validates the merchant signature, timestamp, IP allowlist, merchant configuration, and request body.
4. Newton resolves the active merchant customer by `merchantCustomerId`, resolves the registration token by `merchantCustomerRegistrationTokenReferenceId`, and loads the token's customer and device.
5. If `shouldActivate` is `"true"`, Newton validates the request mobile number against the registered customer when mobile validation is enabled for the merchant, deregisters older merchant-customer bindings where required, updates the merchant-customer record, activates the registration token, and builds the VPA/account response.
6. If `shouldActivate` is `"false"`, Newton does not activate the token and returns the current bound/unactivated state. If the token is already activated, Newton rejects the call as a duplicate activation-token use.
7. Merchant decrypts the response and uses `payload.isDeviceActivated` as the source of truth for whether subsequent device-bound UPI APIs can proceed.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. Newton uses this with the authenticated merchant to find the active merchant customer profile.
- `merchantCustomerRegistrationTokenReferenceId`: Registration-token id/reference from the device-bind journey. This is the token whose bound and activated state is returned.
- `deviceFingerPrint`: Response hash derived from the stored device fingerprint and SSID. Treat it as an opaque device identifier for comparison and audit, not as the raw device fingerprint.

## Endpoint

```http
POST /api/{apiVersion}/merchants/device/activate
```

### Recommended Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | Use the version shared during onboarding. The response account shape can vary by version and merchant configuration. |
| `x-merchant-id` | Yes | Merchant id used to resolve merchant configuration and keys. |
| `x-merchant-channel-id` | Yes | Merchant channel id used with `x-merchant-id`. |
| `x-timestamp` | Yes | 13-digit epoch milliseconds. For signed/encrypted requests, Newton also validates the decrypted `iat` field. |
| `x-merchant-signature` | Conditional | Required for plaintext signed-by-header integrations. JWS/JWE payloads are verified through their envelope and key id. |
| `x-forwarded-for` | Conditional | Required when the merchant has IP allowlisting configured. The first IP must be allowlisted. |
| `x-request-id` | No | Optional merchant request id for tracing. Newton returns it in response headers when supplied. |
| `x-session-id` | No | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant integration. |

### Authentication and Encryption

The route accepts the shared Newton S2S `EncRequest` envelope. Depending on onboarding, the wire request may be JWE encrypted, JWS signed, or a plaintext payload with header signature validation. Client integrations should use the encrypted/signed mode shared during onboarding.

For JWS/JWE requests:

- The `iat` field inside the decrypted business payload is required.
- `iat` must be a 13-digit epoch-millisecond timestamp and must be within 30 minutes of Newton server time.
- The envelope `kid` must resolve to a configured merchant key.

For plaintext payloads:

- Newton verifies the header signature over merchant id, channel id, optional sub-merchant ids, timestamp, and raw request body.
- Plaintext is generally a controlled integration mode; do not use it unless explicitly enabled during onboarding.

All examples in this page are decrypted business payloads, not the encrypted wire envelope.

## Request

### Required Minimum

To activate a bound device:

```json
{
  "merchantCustomerId": "CUST_000123",
  "merchantCustomerRegistrationTokenReferenceId": "mcrt_9f5a2d8c",
  "shouldActivate": "true",
  "customerMobileNumber": "9876543210",
  "iat": "1736245800000"
}
```

To check the current bound/unactivated state without changing it:

```json
{
  "merchantCustomerId": "CUST_000123",
  "merchantCustomerRegistrationTokenReferenceId": "mcrt_9f5a2d8c",
  "shouldActivate": "false",
  "customerMobileNumber": "9876543210",
  "iat": "1736245800000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Must be 1 to 256 characters and match Newton's merchant-customer-id format: starts with an alphanumeric, `+`, `/`, or `=`, followed by letters, numbers, `.`, `_`, `+`, `/`, `=`, or `-`. |
| `merchantCustomerRegistrationTokenReferenceId` | string | Yes | No default. | Registration-token id/reference produced by the device-bind journey. Newton looks it up directly by id. |
| `shouldActivate` | string | Yes | No default. | Send `"true"` to activate. Send `"false"` to perform a read-only bound/unactivated status check. Only the string value `true`, case-insensitive, triggers activation. |
| `customerMobileNumber` | string | Yes | No default. | Customer mobile number associated with the registration token. For merchants with `validateMobileNumber` enabled, this must match the customer mobile number or mobile hash stored during registration. |
| `iat` | string | Conditional | No default. | Required for signed/encrypted request envelopes. Must be a 13-digit epoch-millisecond timestamp within 30 minutes of Newton server time. |
| `countryCode` | string | No | No default. If omitted, Newton does not apply or store a country-code value for this request. | Optional country code. If supplied, it must be numeric with an optional leading `+` and length at most 7. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the success response. Must parse as a JSON object string and pass Newton UDF character validation. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default.

- `shouldActivate` is required. Use `"true"` or `"false"` only. Non-empty values other than `"true"` currently fall into the non-activating branch, but clients should not rely on unsupported values.
- `iat` is required for signed or encrypted envelopes. It is not validated for plaintext `UnSignedPayload`, but production clients should still follow the onboarding security contract.
- `countryCode` is optional and is only validated when present.
- `udfParameters` is optional and is echoed only when present.
- `vpaAccounts` in the response is not controlled by a request flag. Newton includes it only after the token is activated and linked VPA/account data is available.

### Validation Notes

Newton validates the decrypted business payload before running activation logic:

- `merchantCustomerId` must be present, length 1 to 256, and match the configured regex.
- `merchantCustomerRegistrationTokenReferenceId`, `shouldActivate`, and `customerMobileNumber` must be non-empty.
- `countryCode`, when supplied, must be numeric with optional `+` and max length 7.
- `udfParameters`, when supplied, must be a JSON-object string.
- For signed/encrypted requests, `iat` must be valid and fresh.
- Merchant authentication, API allowlisting, optional IP allowlisting, and signature verification run before product logic.

## Request Examples

### Activate Bound Device

```json
{
  "merchantCustomerId": "CUST_000123",
  "merchantCustomerRegistrationTokenReferenceId": "mcrt_9f5a2d8c",
  "shouldActivate": "true",
  "customerMobileNumber": "9876543210",
  "countryCode": "+91",
  "iat": "1736245800000",
  "udfParameters": "{\"deviceSessionId\":\"DS-12345\",\"channel\":\"android\"}"
}
```

### Check Current Activation State

Use this before activation when the merchant wants to verify whether the token is bound. This call does not activate the token. If the token has already been activated, Newton returns an already-activated failure instead of a success status response.

```json
{
  "merchantCustomerId": "CUST_000123",
  "merchantCustomerRegistrationTokenReferenceId": "mcrt_9f5a2d8c",
  "shouldActivate": "false",
  "customerMobileNumber": "9876543210",
  "iat": "1736245800000"
}
```

## Response

### Success Envelope

On success, the decrypted business response has this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for a successful API execution. |
| `responseCode` | string | `SUCCESS` on success. |
| `responseMessage` | string | `SUCCESS` on success. |
| `payload` | object | Device activation state and linked VPA/account data when available. |
| `udfParameters` | string | Echo of request `udfParameters`. Omitted when request `udfParameters` is omitted. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `isDeviceBound` | string | `"true"` when the registration token is verified/bound. `"false"` when the token is not verified. This is separate from activation. |
| `isDeviceActivated` | string | `"true"` when the registration token is activated. Use this as the main client decision field. |
| `deviceFingerPrint` | string | Opaque SHA-256 hash of stored device fingerprint plus SSID. Included only when the token is bound/verified. Omitted otherwise. |
| `customerMobileNumber` | string | Customer mobile number from the registration token's customer record. Included only when the token is bound/verified. Omitted otherwise. |
| `vpaAccounts` | array | Linked VPA/account objects. Included only when `isDeviceActivated` is `"true"` and linked accounts are available. Omitted for non-activating status checks and unactivated tokens. |

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA. |
| `account` | object | Account details associated with the VPA. |
| `isDefault` | boolean | Whether this VPA/account mapping is default, when available for the merchant/version. |

### `vpaAccounts[].account`

The exact account fields vary by merchant configuration, PSP mode, API version, and account type. Common fields include:

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Bank code. |
| `bankName` | string | Bank name. |
| `maskedAccountNumber` | string | Masked account number for display. |
| `mpinLength` | string | MPIN length expected by the PSP. |
| `mpinSet` | string | `"true"` or `"false"` indicating whether MPIN is set. |
| `referenceId` | string | Account reference id when exposed for the merchant/version. |
| `type` | string | Account type, for example `SAVINGS`, `CURRENT`, or `CREDIT`. |
| `branchName` | string | Branch name when available and applicable. |
| `bankAccountUniqueId` | string | Newton account unique id/hash used for later account APIs. |
| `ifsc` | string | Account IFSC when available. |
| `isPrimary` | string | `"true"` or `"false"` when primary-flag response format is enabled. |
| `name` | string | Account holder name. |
| `otpLength` | string | OTP credential length. |
| `atmPinLength` | string | ATM PIN credential length when format/version enables it. |
| `kycStatus` | string | KYC status for supported account types. |
| `accountNumber` | string | Encrypted account number when enabled for the merchant. Do not treat it as a display value. |
| `accBIN` | string | Account BIN for supported credit-account responses. |
| `aadhaarEnabled` | string | Aadhaar support flag when returned. |
| `isAadhaarNumberAvailable` | string | Aadhaar-number availability flag when returned. |
| `bankAccountHash` | string | TPV account hash when TPV account-hash response is enabled. |
| `accSubType` | string | Account subtype, including credit-line account subtypes where applicable. |
| `allowedMCC` | array of strings | MCC allowlist for the account when available. |
| `notallowedMCC` | array of strings | MCC denylist for the account when available. |
| `lrn` | string | UPI Lite LRN when available. |
| `isInitialTopUpDone` | string | UPI Lite initial top-up status when available. |
| `liteDetails` | object | UPI Lite details when requested/enabled in related flows. |
| `bioAuthConsentUrl` | string | Bio-auth consent URL when available. |
| `bioAuthEnabled` | string | `"true"` or `"false"` when biometric auth consent state is returned. |
| `credsAllowed` | string | Credential types allowed by PSP/account configuration when returned. |
| `payerAccountHash` | string | Account-number-only payer hash when enabled for the merchant. |

Fields with `null`/`Nothing` values are omitted from the JSON response.

## Response Examples

### Activated Device With Linked Account

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "isDeviceBound": "true",
    "isDeviceActivated": "true",
    "deviceFingerPrint": "b7f0f4f1457b86d8b5f3a6c7f2c9c1a0a8a7d3a4f4a1f2d7d4f3c9a2b1e0d8c6",
    "customerMobileNumber": "9876543210",
    "vpaAccounts": [
      {
        "vpa": "cust000123@upi",
        "isDefault": true,
        "account": {
          "bankCode": "HDFC",
          "bankName": "HDFC Bank",
          "maskedAccountNumber": "XXXXXX1234",
          "mpinLength": "4",
          "mpinSet": "true",
          "referenceId": "acc_ref_123",
          "type": "SAVINGS",
          "branchName": "MUMBAI",
          "bankAccountUniqueId": "bank_acc_uid_123",
          "ifsc": "HDFC0000001",
          "isPrimary": "true",
          "name": "Ravi Kumar",
          "otpLength": "6",
          "atmPinLength": "4",
          "bioAuthEnabled": "false"
        }
      }
    ]
  },
  "udfParameters": "{\"deviceSessionId\":\"DS-12345\",\"channel\":\"android\"}"
}
```

### Status Check Without Activation

When `shouldActivate` is `"false"`, Newton returns the current token state and omits `vpaAccounts`. If the token is already activated, the API returns `MerchantCustomerRegistrationToken is already activated` instead of this success body.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "isDeviceBound": "true",
    "isDeviceActivated": "false",
    "deviceFingerPrint": "b7f0f4f1457b86d8b5f3a6c7f2c9c1a0a8a7d3a4f4a1f2d7d4f3c9a2b1e0d8c6",
    "customerMobileNumber": "9876543210"
  }
}
```

### Token Not Bound

If the token exists but is not verified/bound, the response can omit mobile and fingerprint details because those fields are emitted only for verified tokens.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "isDeviceBound": "false",
    "isDeviceActivated": "false"
  }
}
```

## Interpreting Status

Use both the envelope status and payload state:

- `status = "SUCCESS"` means Newton processed the API call.
- `payload.isDeviceActivated = "true"` means the device registration token is active and the merchant can continue with device-bound UPI flows.
- `payload.isDeviceBound = "true"` means the registration token is verified/bound. It does not by itself mean the token is activated.
- `vpaAccounts` is a convenience payload after activation. Its absence does not always mean activation failed; check `isDeviceActivated`.

## Error Handling

Failure responses follow the standard Newton error response shape after decryption: `status: "FAILURE"` with a concrete `responseCode` and diagnostic `responseMessage`. The examples below show common values.

Many product/business failures are returned with HTTP 200 and a failure body. Authentication, timestamp, and malformed-envelope failures can use HTTP 400/401/500 depending on the layer. Always read the decrypted `status`, `responseCode`, and `responseMessage`.

### Failure Scenarios

| Scenario | Typical response code | Client handling |
| --- | --- | --- |
| Empty or invalid request fields | `BAD_REQUEST` | Fix the request and retry. |
| Missing/invalid merchant headers, signature mismatch, or IP allowlist failure | `UNAUTHORIZED` | Do not retry unchanged. Fix credentials, signature, timestamp, or source IP. |
| Signed/encrypted `iat` missing or stale | `INVALID_DATA`, `BAD_REQUEST`, or request-expiry response | Regenerate the envelope with a fresh 13-digit millisecond timestamp. |
| Merchant or API configuration blocks the route | `UNAUTHORIZED`, `INVALID_DATA`, or configured block response | Confirm API enablement and merchant configuration with Newton. |
| `merchantCustomerId` not found for the authenticated merchant | `INVALID_DATA` | Use the correct merchant customer id or complete customer onboarding/binding first. |
| `merchantCustomerRegistrationTokenReferenceId` not found | `INVALID_DATA` | Use the token reference returned by the latest device-bind flow. |
| Registration token already activated | `INVALID_DATA` | Treat as a terminal duplicate activation attempt for this token. Use the appropriate follow-up status, customer-info, or account API if current state/details are needed. |
| Token has no active customer or device | `INVALID_DATA` | Restart the device-bind journey. |
| Mobile number mismatch while merchant mobile validation is enabled | `SMS_VERIFICATION_MISMATCH` | Ask the customer to complete registration with the expected mobile number or restart binding. |
| Another merchant-customer binding must be deregistered first | `OPERATION_RESTRICTED_DEREGISTER_CUSTOMER` | Complete deregistration or use the appropriate binding flow before activating. |
| Downstream deregistration service returns an error | Downstream/custom code or `INTERNAL_SERVER_ERROR` | Retry only after reconciling token/customer state through an appropriate follow-up API. Escalate if repeated. |
| Passetto/decryption, database update, Sherlock renewal, or unexpected internal failure | `INTERNAL_SERVER_ERROR` | Treat as transient or unknown state. Check activation status before retrying activation. |

### Error Examples

#### Request Validation Failure

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"shouldActivate field is empty\""
}
```

#### Invalid UDF Parameters

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

#### Authentication or IP Allowlist Failure

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

#### Missing or Invalid `iat`

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

For malformed or expired timestamps, Newton can also return a `BAD_REQUEST` or request-expired response from timestamp validation.

#### Merchant Customer Not Found

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

#### Registration Token Not Found

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid merchantCustomerRegistrationTokenReferenceId"
}
```

#### Registration Token Already Activated

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "MerchantCustomerRegistrationToken is already activated"
}
```

#### Mobile Number Mismatch

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_MISMATCH",
  "responseMessage": "SMS verification mismatch",
  "payload": {
    "SMSVerificationMismatchPayload": {
      "customerMobileNumber": "9876543210"
    }
  }
}
```

Some merchants configured for the older non-multibank error shape may receive the same code/message without the `payload`.

#### Deregistration Required Before Activation

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_DEREGISTER_CUSTOMER",
  "responseMessage": "Deregister customer to continue device binding"
}
```

#### Downstream Deregistration Failure

```json
{
  "status": "FAILURE",
  "responseCode": "DEREGISTER_FAILED",
  "responseMessage": "Customer deregistration failed at downstream PSP"
}
```

Downstream deregistration errors can surface with the PSP-provided code and message. If the downstream response lacks a specific code/message, Newton returns `INTERNAL_SERVER_ERROR`.

#### Unexpected Internal Failure

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry, Idempotency, and Client Handling

This API does not accept a merchant idempotency key. The registration token itself is the state guard.

- Do not blindly retry `shouldActivate: "true"` after a timeout or `INTERNAL_SERVER_ERROR`. First reconcile the token state with `shouldActivate: "false"` before activation has completed, or use another agreed status/read API.
- If a repeat activation or state check returns `MerchantCustomerRegistrationToken is already activated`, treat the token as terminally activated for retry purposes and fetch customer/account state through the appropriate follow-up API if the activation response was lost.
- If a `shouldActivate: "false"` check returns `isDeviceActivated: "false"`, the token is still not activated and the merchant can send a fresh `shouldActivate: "true"` request with a fresh timestamp/envelope.
- For validation, authentication, timestamp, merchant configuration, and lookup errors, fix the request or configuration before retrying.
- For transient downstream/internal failures, retry with backoff only after confirming that the token is still not activated through `shouldActivate: "false"` where applicable or through another agreed status/read API.
- Store `merchantCustomerRegistrationTokenReferenceId`, `isDeviceBound`, `isDeviceActivated`, and the returned account identifiers needed for subsequent UPI APIs.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:206)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1831)
- Server route wiring: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:243)
- Request body decryption/verification entry: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature and allowlist verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp validation: [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Product route: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:130)
- Request and response types: [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:91)
- Request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- Activation business logic: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:914)
- Device activation helper: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:742)
- Merchant-customer update: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:803)
- Account activation helper: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1096)
- Success response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2396)
- Device/mobile response helper: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:317)
- VPA/account response types: [src/Newton/Types/API/Account.hs](../../src/Newton/Types/API/Account.hs:12)
- VPA/account response transformer: [src/Newton/Utils/Transformers/Transformer4.hs](../../src/Newton/Utils/Transformers/Transformer4.hs:223)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
