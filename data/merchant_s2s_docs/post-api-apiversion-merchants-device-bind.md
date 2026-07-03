# Bind Device API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/device/bind`

## Overview

Bind Device is a Newton merchant server-to-server API used to complete the device-binding step after a customer registration attempt has been started and the registration SMS/OTP verification state has been recorded in Newton.

The merchant calls this API with the registration-token reference returned by the registration flow, the merchant customer id, and the SIM slot/index that should be bound. Newton validates the encrypted/signed request, verifies merchant API access, resolves the registration token, checks device-binding attempt limits, binds the verified customer/device to the merchant customer profile, and returns the customer mobile number and `deviceFingerPrint` that later S2S APIs use.

Examples below show decrypted business payloads for readability. Production payloads use the encrypted/signed/plain transport mode assigned during merchant onboarding.

## Business Use Case

Use this API when the customer device has completed the registration verification step and the merchant backend needs Newton to mark that device as bound for the merchant customer.

Bind Device helps merchants:

- Complete the customer/device onboarding flow started by registration init or Get SMS Token.
- Attach the verified registration token to the merchant customer profile.
- Persist the selected SSID/SIM value from the registration token for future device validation.
- Receive `deviceFingerPrint` for subsequent account, VPA, transaction, MPIN, bio-auth, and customer-context APIs.
- Detect registration attempts that are still unverified, expired, declined, rate-limited, or otherwise unusable.

Do not use this API to start registration. Call the registration-init/Get SMS Token flow first, have the customer's device complete the configured SMS/OTP verification, then call Bind Device.

## Integration Flow

1. Merchant starts customer/device registration through the configured registration API.
2. Customer completes the configured registration verification step.
3. Merchant calls `device/bind` with the registration-token reference, merchant customer id, and `simId`.
4. Newton verifies the request envelope/signature, merchant API access, timestamp, optional IP allowlist, and request body.
5. Newton loads the registration token and checks expiry/decline state.
6. If the token is verified, Newton resolves the customer/device, applies device-bind attempt limits when enabled, selects the SSID from the token's stored `ssids` list using `simId`, links the token/device/customer to the merchant customer, and updates caches.
7. Newton returns top-level `SUCCESS` with binding flags and, when binding is complete, `customerMobileNumber` and `deviceFingerPrint`.

Important identifiers:

- `merchantCustomerRegistrationTokenReferenceId`: Newton registration-token id/reference from the prior registration step. This same value is returned in the success payload as Newton's registration-token reference.
- `merchantCustomerId`: Merchant-owned customer profile id. This is used for request tracing and cache invalidation; the registration token itself also carries the merchant customer record that Newton updates.
- `simId`: Index into the `ssids` list stored on the registration token. Send the SIM slot/index selected during registration, not a raw SIM serial/IMSI value.
- `deviceFingerPrint`: Hash returned by Newton after a completed bind. Store it and send it in later APIs that require device validation.

## Endpoint

```http
POST /api/{apiVersion}/merchants/device/bind
```

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | JSON transport envelope. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-timestamp` | Yes | Current timestamp used in merchant signature verification. |
| `x-raw-body` | Conditional | Exact raw HTTP body used for merchant signature verification in plain signed mode. Required by the signature middleware. |
| `x-merchant-signature` | Conditional | Required for permitted plain signed business payload mode. JWS/JWE modes verify through the configured envelope. |
| `x-forwarded-for` | Conditional | Required only when merchant IP allowlisting is configured. Must contain an allowlisted client IP. |
| `x-request-id` | No | Merchant/client request id for tracing. Newton generates one when omitted. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. The route accepts Newton's common `EncRequest` transport: JWE encrypted body, JWS signed body, or plain JSON only where merchant configuration permits it.

For JWS/JWE request bodies, send `iat` in the decrypted business payload. The middleware validates it before product logic runs. Plain signed payload mode ignores payload `iat`, but sending it is safe.

Responses use the matching onboarded response mode. Verify/decrypt the response before reading the business fields.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the URL path. Use the value assigned during onboarding. |

## Request

### Required Minimum

```json
{
  "merchantCustomerRegistrationTokenReferenceId": "MCRT_8sQp3J2kL9",
  "merchantCustomerId": "CUST000123",
  "simId": "0",
  "iat": "1782990600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerRegistrationTokenReferenceId` | string | Yes | No default. | Registration-token id/reference from the prior registration step. Must be non-empty. Newton looks up this token and returns `INVALID_DATA` if it is unknown. |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer/profile id. Must be 1 to 256 characters and match Newton's merchant-customer-id pattern. |
| `simId` | string | Yes | No default. | SIM slot/index used to pick an SSID from the registration token's stored `ssids` list. Must be non-empty and parse as an integer for product logic. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp used by S2S JWS/JWE validation. Send a fresh 13-digit epoch-milliseconds timestamp for signed/encrypted body modes. |
| `udfParameters` | string | No | Omitted from response when omitted. | JSON-object string for merchant metadata, for example `"{\"journeyId\":\"REG123\"}"`. Echoed in success responses. |

### Nested Request Objects

This API has no nested business request objects.

### Validation Notes

- `merchantCustomerRegistrationTokenReferenceId` and `simId` must be non-empty strings.
- `merchantCustomerId` must be non-empty, at most 256 characters, and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`.
- `udfParameters`, when supplied, must be a string containing a JSON object and must not contain characters rejected by Newton's UDF validator.
- For JWS/JWE bodies, `iat` is required and must pass timestamp validation.
- `simId` is parsed later in product logic. Non-numeric values or indexes that do not resolve to a stored SSID produce business failures, not request-type validation failures.

### Defaults and Omitted Field Behavior

Fields not listed here have no generated default.

- `iat`: required only for JWS/JWE request-body modes.
- `udfParameters`: not stored in binding state; echoed only when supplied in a success response.
- `simId`: no fallback. Newton cannot bind the device without selecting a stored SSID.
- `merchantCustomerId`: no fallback in the request type. Product logic uses the merchant customer linked to the registration token for the actual update, so clients should keep this value consistent with the customer used in the prior registration step.

## Request Examples

### Bind First SIM Slot

Use this when the registration token contains the selected SSID at index `0`.

```json
{
  "merchantCustomerRegistrationTokenReferenceId": "MCRT_8sQp3J2kL9",
  "merchantCustomerId": "CUST000123",
  "simId": "0",
  "iat": "1782990600000",
  "udfParameters": "{\"journeyId\":\"REG-20260702-000123\",\"channel\":\"android\"}"
}
```

### Bind Second SIM Slot

Use this only when the prior registration step stored multiple SSIDs and the customer selected the second slot.

```json
{
  "merchantCustomerRegistrationTokenReferenceId": "MCRT_8sQp3J2kL9",
  "merchantCustomerId": "CUST000123",
  "simId": "1",
  "iat": "1782990600000"
}
```

## Success Response

### Completed Binding

When the registration token is verified and the bind update succeeds, Newton returns:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "isDeviceBound": "true",
    "isDeviceActivated": "false",
    "merchantCustomerRegistrationTokenReferenceId": "MCRT_8sQp3J2kL9",
    "customerMobileNumber": "9876543210",
    "deviceFingerPrint": "4f53d8d2c7a3a7f4f1d0a7c44f3d0f8b7ce8d8b2e5e2a0a5f1a9c1b2d3e4f567"
  },
  "udfParameters": "{\"journeyId\":\"REG-20260702-000123\",\"channel\":\"android\"}"
}
```

Client interpretation:

- Treat binding as complete only when `status = "SUCCESS"` and `payload.isDeviceBound = "true"`.
- Store `payload.deviceFingerPrint`; later S2S APIs use it to validate the bound device.
- `payload.isDeviceActivated` is derived from the registration token's activation state. A normal bind-only response can have `"false"`; continue to the activation API if your integration requires activation as a separate step.
- `customerMobileNumber` and `deviceFingerPrint` are present only when Newton can derive them from the verified customer/device.

### Token Not Yet Verified

For this route, a registration token that is not verified can still produce top-level `SUCCESS` with `isDeviceBound = "false"`:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "isDeviceBound": "false",
    "isDeviceActivated": "false",
    "merchantCustomerRegistrationTokenReferenceId": "MCRT_8sQp3J2kL9"
  }
}
```

Client interpretation: do not proceed to activation or account-linking. Have the customer complete the registration verification step, then retry Bind Device with a fresh timestamp/signature while the registration token is still valid.

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. `SUCCESS` means the route completed and returned the current binding state; check `payload.isDeviceBound` for the business outcome. |
| `responseCode` | string | Machine-readable response code. Success uses `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success uses `SUCCESS`. |
| `payload` | object | Bind-device result object. Present in success responses. |
| `udfParameters` | string | Echo of request `udfParameters`; omitted when not supplied. |

### `payload` Fields

| Field | Type | Description |
| --- | --- | --- |
| `isDeviceBound` | string | `"true"` when the registration token was verified and binding is complete; `"false"` when binding is not complete. |
| `isDeviceActivated` | string | `"true"` when the registration token is already activated; otherwise `"false"`. |
| `merchantCustomerRegistrationTokenReferenceId` | string | Newton registration-token id/reference used for the bind flow. |
| `customerMobileNumber` | string | Customer mobile number from the verified customer record. Omitted when the token is not verified or customer data cannot be derived. |
| `deviceFingerPrint` | string | SHA-256 hash derived from the stored device fingerprint and selected SSID. Omitted when the token is not verified. |

## Error Handling

Failure responses use the same response transport configured for the merchant where possible. After decryption/verification, business failures generally include `status: "FAILURE"` plus a concrete `responseCode` and diagnostic `responseMessage`.

HTTP status can vary by validation layer. Some business failures are returned with HTTP 200 and a decrypted `status: "FAILURE"` body. Auth/encryption failures commonly return HTTP 401 or 400 with the error body.

### Validation Failures

Empty required fields are rejected by request validation:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerRegistrationTokenReferenceId field is empty\""
}
```

Invalid merchant customer id format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Invalid UDF JSON string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Client handling: fix the request body. Do not retry unchanged validation failures.

### Authentication, Encryption, and Merchant Access Failures

Missing or invalid merchant headers, invalid JWS signature, JWE decryption failure, missing `x-raw-body`/`x-timestamp`, timestamp outside the accepted window, or non-allowlisted IP can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the merchant exists but this API is blocked or not in the merchant's allowed API list:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If encrypted payload parsing fails after decryption:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: parsing signed payload failed"
}
```

Client handling: regenerate the JWS/JWE or signature with the exact raw body and a fresh timestamp, verify the merchant/channel ids and key id, and confirm API allowlisting before retrying.

### Registration Token Failures

Unknown registration token:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid merchantCustomerRegistrationTokenId"
}
```

Registration token declined:

```json
{
  "status": "FAILURE",
  "responseCode": "REGISTRATION_DECLINED",
  "responseMessage": "Device binding was declined"
}
```

Registration token expired:

```json
{
  "status": "FAILURE",
  "responseCode": "SMS_VERIFICATION_EXPIRED",
  "responseMessage": "SMS token expired"
}
```

Client handling: do not keep retrying the same token after unknown, declined, or expired-token failures. Restart registration and bind with the new registration-token reference.

### SIM/SSID Selection Failures

If `simId` cannot be read as an integer or the registration token does not contain usable SSID data, Newton returns an `INVALID_DATA` failure from the SSID lookup helper. Examples include:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid getSsidFromSimId-invalid-simId"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "simId not found"
}
```

Client handling: send the selected SIM index from the prior registration step. If the registration token has no SSID list, restart registration.

### Device Bind Attempt Limits and Business Blocks

When device-bind rate limiting is enabled, Newton can limit how many customer mobile numbers are bound to one device, or how many device fingerprints are bound to one customer mobile number:

```json
{
  "status": "FAILURE",
  "responseCode": "BIND_DEVICE_LIMIT_EXCEEDED",
  "responseMessage": "Device bind attempted more than 3 times for this device/mobile number"
}
```

If fraud-risk blocking is enabled for the merchant, Newton can reject binding for a blocked mobile/device risk profile:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mobile number or DeviceId is blocked"
}
```

Client handling: stop automatic retries for the same device/mobile within the configured window. Ask the customer to wait or route the case to merchant/Newton support according to policy.

### Customer, Device, and Stored State Lookup Failures

If required ids are missing from the registration token or the linked customer/device cannot be found, shared helpers return `INVALID_DATA` failures. Examples include:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid fetchCustomerFromMCRT - CustomerId cannot be null"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

If the verified token has incomplete device/customer data while building the response, Newton can also return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: restart registration for customer/device lookup failures unless Newton support identifies a recoverable stored-state issue.

### Downstream, Cache, Storage, and Unexpected Failures

Bind Device does not call NPCI directly. Failures in this route are usually registration-token lookup/update, merchant customer update, Redis/cache update, encryption/hash/decryption, or storage failures. Unexpected failures generally return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry transient `INTERNAL_SERVER_ERROR` with short bounded backoff and a fresh timestamp/signature. If repeated retries return the same error for one registration token, do not create an infinite bind loop; start a new registration attempt or contact Newton support.

## Retry and Idempotency Guidance

This API has no merchant-supplied idempotency key. Repeating a successful bind for the same verified token is generally safe only as a status recovery check, but repeated calls can still interact with configured device-bind attempt limits and cache/state updates.

- On `SUCCESS` with `payload.isDeviceBound = "true"`, store `deviceFingerPrint` and move to the next step. Do not call Bind Device again for the same customer journey.
- On `SUCCESS` with `payload.isDeviceBound = "false"`, wait for registration verification to complete and retry with a fresh timestamp/signature before the token expires.
- On network timeout with no readable response, retry the same registration-token reference with a new envelope/signature. If the retry returns `isDeviceBound = "true"`, treat the bind as complete.
- Do not retry unchanged requests for validation, auth, API enablement, unknown token, declined token, expired token, bad `simId`, or bind-limit failures.
- Regenerate the signature/envelope for every retry; do not replay an old signed/encrypted body after the timestamp window.

## Source References

- API root path and `apiVersion` capture: [Core.hs](../../src/Newton/App/Routes/Core.hs:112)
- S2S route definition for `/merchants/device/bind`: [Core.hs](../../src/Newton/App/Routes/Core.hs:200)
- Server handler ordering: [Server.hs](../../src/Newton/App/Server.hs:242)
- Handler request decryption, signature verification, cache invalidation, and product dispatch: [Core.hs](../../src/Newton/App/Routes/Core.hs:1812)
- Common encrypted/signed/plain transport shapes: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification and JWS/JWE failure behavior: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69), [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature, timestamp, API enablement, and IP allowlist checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:84), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:145), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:208)
- Request/response types and validators: [Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:25), [Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:48), [Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:59)
- Field validators: [Common.hs](../../src/Newton/Validation/Common.hs:168), [Common.hs](../../src/Newton/Validation/Common.hs:275), [Common.hs](../../src/Newton/Validation/Common.hs:311)
- Product bind flow: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:94)
- Registration-token expiry/decline handling: [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:94)
- Verified-token binding, SSID selection, merchant-customer update, and stats: [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:179)
- Device-bind attempt limit checks: [RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:467)
- `simId` to SSID lookup: [Utils.hs](../../src/Newton/Utils/Utils.hs:2351)
- Success response transformer and `udfParameters` echo: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2329)
- Mobile number and device-fingerprint derivation: [Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:317)
- Registration-token lookup error: [MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:666)
- Common error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:286), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:373), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:761)
