# Create UPI Number API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/upiNumber/create`

## Overview

Create UPI Number registers or links a customer-facing UPI number to one of the customer's VPAs.

The merchant calls this API after completing the UPI Number availability/check step for the same customer, UPI number, and VPA. Newton validates the request, verifies the merchant signature and customer context, confirms the previous availability/check result, verifies the customer's device fingerprint, and then sends the register-mapper request to NPCI.

Use this API when a customer has selected a UPI number and the merchant needs Newton to register that number as an active mapper record against the customer's VPA.

## Business Use Case

Create UPI Number helps merchants:

- Register a mobile-number-style UPI number for a customer.
- Register a numeric UPI ID, also called a numeric ID, for a customer.
- Link the UPI number to the customer VPA that passed the availability/check flow.
- Port or modify the linked VPA by sending `existingVpa` when the preceding availability/check flow was for port/change-VPA behavior.
- Track the NPCI registration result using the merchant-provided `upiRequestId`.

## Integration Flow

1. The customer completes the merchant's device binding and VPA setup flow.
2. Merchant calls the UPI Number availability API for the same `merchantCustomerId`, `upiNumber`, and target `vpa`.
3. If the customer is porting/changing from an existing VPA, the availability/check flow records the expected `existingVpa`.
4. Merchant calls `create` with the same customer, UPI number, VPA, and optional `existingVpa`.
5. Newton validates request format, signature, API access, IP restrictions, customer ownership, device fingerprint, prior check result, duplicate mapper state, and customer UPI-number limits.
6. Newton sends the registration request to NPCI.
7. Merchant reads `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.status` to decide whether registration is active, failed, or pending.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. Newton uses it for merchant-customer lookup and signature-scoped customer context.
- `upiRequestId`: Merchant-generated request id for this create call. Newton forwards it as the NPCI transaction id and returns it as `payload.gatewayTransactionId`.
- `upiNumber`: The numeric UPI number being registered.
- `vpa`: The customer VPA that should be linked to the UPI number.

## Endpoint

```http
POST /api/{apiVersion}/merchants/upiNumber/create
```

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show decrypted business payloads for readability.

## Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured during onboarding. |

## Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body must be JSON. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain business payloads. Signature is verified over merchant ids, timestamp, and raw request body. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness unless checksum-based development/UAT bypass behavior is enabled. |
| `x-forwarded-for` | Conditional | Required when the merchant has configured `whitelistedIps`; the first IP in this header must be whitelisted. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-api-version` | Recommended | Use the version shared during onboarding. |

## Authentication and Encryption

Newton accepts the standard `EncRequest` transport:

- Encrypted JWE body:

```json
{
  "protected": "eyJhbGciOiJSU0EtT0FFUCIsImVuYyI6IkEyNTZHQ00iLCJraWQiOiJtZXJjaGFudC1rZXktaWQifQ",
  "encryptedKey": "ZGVtb19lbmNyeXB0ZWRfa2V5",
  "iv": "ZGVtb19pdjEy",
  "cipherText": "ZGVtb19jaXBoZXJ0ZXh0",
  "tag": "ZGVtb19hdXRoX3RhZw"
}
```

- Signed JWS body:

```json
{
  "payload": "eyJtZXJjaGFudEN1c3RvbWVySWQiOiJDVVNUMTIzNDUifQ",
  "signature": "ZGVtb19zaWduYXR1cmU",
  "protected": "eyJhbGciOiJSUzI1NiIsImtpZCI6Im1lcmNoYW50LWtleS1pZCJ9"
}
```

- Plain unsigned business payload can be parsed by the server type, but production server-to-server integrations should use the encrypted/signed onboarding process. For unsigned payloads, Newton still requires `x-merchant-signature`.

The route first decrypts/verifies the request envelope, then verifies merchant signature and access using `merchantCustomerId`, `iat`, headers, and the configured API name for UPI Number registration. Responses use the standard Newton encrypted/signed response transport. The response examples below are decrypted business bodies.

## Request

### Required Minimum

```json
{
  "deviceFingerPrint": "3f9a3a6d8c0f9d2e",
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMREG12345",
  "upiNumber": "9876543210",
  "vpa": "customer@bank"
}
```

### Port or Change Linked VPA

Send `existingVpa` only when the preceding availability/check flow was for port/change-VPA behavior and recorded the previous VPA.

```json
{
  "deviceFingerPrint": "3f9a3a6d8c0f9d2e",
  "fallbackDeviceFingerPrint": "ab2d0d2f0f20c9e1",
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMPORT12345",
  "upiNumber": "9876543210",
  "existingVpa": "customerold@bank",
  "vpa": "customernew@bank",
  "udfParameters": "{\"customerSegment\":\"gold\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `deviceFingerPrint` | string | Yes | No default. | Current device fingerprint for the merchant customer. Newton compares it with the stored device fingerprint or SSID-derived fingerprint for the customer. |
| `existingVpa` | string | Conditional | No default. | Previous VPA for port/change-VPA registration. If supplied, it must match the `prevVpa` recorded by the preceding availability/check flow, except for the ICICI PSP-mode special case where missing check data can be tolerated for `existingVpa` flows. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate device fingerprint accepted by the device check. Use this when the client may have both a primary and fallback fingerprint for the same bound device. |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id. Must be 1 to 256 characters and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. |
| `udfParameters` | string | No | No default. Echoed in the response when supplied. | JSON-object string for merchant-defined metadata. Must parse as a JSON object and must not contain characters rejected by the validator (`/`, `$`, `-`, `*`, `!`, `%`, `~`, backtick). |
| `upiRequestId` | string | Yes | No default. | Merchant-generated id for this create request. Must be 1 to 35 alphanumeric characters. Returned as `payload.gatewayTransactionId`. |
| `upiNumber` | string | Yes | No default. | UPI number to register. Must pass UPI-number validation described below. |
| `vpa` | string | Yes | No default. | Customer VPA to link to the UPI number. Must be 3 to 255 characters and match `localpart@handle` using letters, numbers, dot, and hyphen. The VPA must belong to the merchant customer. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by encrypted/signed request verification. Required for encrypted/signed request types because the signature middleware validates it. |

No request field is defaulted by the create route. Optional fields are omitted from downstream payloads and responses when not supplied, except `udfParameters`, which is echoed if present.

## Validation and Create Behavior

### Request Format Validation

Newton rejects the request before business processing when:

- `deviceFingerPrint` is empty.
- `merchantCustomerId` is empty, longer than 256 characters, or fails its allowed-character rule.
- `upiRequestId` is empty, longer than 35 characters, or non-alphanumeric.
- `upiNumber` fails UPI-number validation.
- `vpa` or `existingVpa` fails VPA format validation.
- `udfParameters` is not a JSON-object string or contains disallowed characters.
- `iat` is missing or stale for encrypted/signed request types.

### UPI Number Validation

`upiNumber` must be numeric.

For a 10-digit UPI number:

- Any 10 numeric digits pass the format validator.
- Product logic additionally requires the customer mobile number to equal `91` plus the requested UPI number.

For an 8- or 9-digit numeric ID:

- Length must be between 8 and 10 digits.
- It must not start with zero.
- The last three digits must not all be the same.

Numbers shorter than 8 digits, longer than 10 digits, non-numeric values, numeric IDs that start with zero, and numeric IDs with the same last three digits are rejected.

### Prior Availability/Check Requirement

Create validates the cached result from the earlier UPI Number availability/check call. The cache key is scoped by `merchantCustomerId` and `upiNumber` or its protected hash. The cached result has a configured expiry.

Newton verifies:

- The requested `vpa` equals the `newVpa` saved by the availability/check call.
- If `existingVpa` is omitted, the last saved availability action must be `CHECK`.
- If `existingVpa` is supplied, the last saved availability action must be `PORT`.
- If `existingVpa` is supplied, it must equal the saved previous VPA.

After a create call reaches NPCI processing, Newton deletes the cached availability/check entry for that customer and UPI number.

### Customer, Device, VPA, and Mapper Checks

Newton also checks:

- Merchant id and channel id identify a valid merchant.
- The API is enabled for the merchant or sub-merchant and is not blocked by merchant configuration.
- If IP allowlisting is configured, the first `x-forwarded-for` IP is present and allowlisted.
- `merchantCustomerId` resolves to a merchant customer and customer under the merchant.
- The customer's stored device exists and the request fingerprint matches the stored device fingerprint or fallback path.
- The requested `vpa` belongs to the same customer and merchant customer.
- The requested 10-digit UPI number matches the customer's registered mobile number with country code `91`.
- The requested UPI number is not already active for the same merchant customer. If the existing mapper is pending, Newton returns a pending-status error.
- Customer limits are not exceeded. The code allows at most three active/inactive/cooling mapper records for a customer, at most one 10-digit mobile-style UPI number, and at most two numeric IDs.

### Downstream NPCI Behavior

Newton creates an NPCI register-mapper request:

- `op` is `ADD` when `existingVpa` is omitted.
- `op` is `MODIFY` when `existingVpa` is supplied.
- UPI number type is `MOBILE` for 10-digit numbers and `NUMERICID` for shorter numeric IDs.
- The requested UPI number is registered with desired mapper status `ACTIVE`.

When the mapper-table path is enabled, Newton creates a pending mapper record before calling NPCI and updates it to `ACTIVE` or failed based on the NPCI response. A merchant configuration can require mapper callbacks even for create responses.

## Response

### Success Response: NPCI Registration Active

Top-level `status` indicates Newton processed the API call. For the actual registration result, use `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.status`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "gatewayTimestamp": "2026-07-02T10:15:30+05:30",
    "gatewayTransactionId": "UPINUMREG12345",
    "gatewayResponseCode": "00",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseMessage": "SUCCESS",
    "upiNumber": "9876543210",
    "vpa": "customer@bank",
    "status": "ACTIVE"
  },
  "udfParameters": "{\"customerSegment\":\"gold\"}"
}
```

### Processed Response: NPCI Registration Failed

Newton can return top-level `SUCCESS` while the NPCI registration failed. Treat `payload.gatewayResponseStatus = "FAILURE"` as the business failure.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "gatewayTimestamp": "2026-07-02T10:15:30+05:30",
    "gatewayTransactionId": "UPINUMREG12345",
    "gatewayResponseCode": "JPMM17",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseMessage": "FAILURE",
    "upiNumber": "9876543210",
    "vpa": "customer@bank",
    "status": "FAILED"
  },
  "udfParameters": "{\"customerSegment\":\"gold\"}"
}
```

If Newton cannot map a gateway error code, `gatewayResponseCode` is `JP91` and `gatewayResponseStatus` is `FAILURE`.

### Processed Response: NPCI Timeout / Pending

For some timeout paths, Newton throws a service-unavailable failure response. In lower-level create-mapper handling, timeout responses can also map the mapper status to `PENDING`. When a processed response is returned with pending status, do not immediately recreate the UPI number; reconcile with fetch/status or wait for mapper status callback if enabled.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "UPINUMREG12345",
    "gatewayResponseCode": "JP91",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseMessage": "Request timed out",
    "upiNumber": "9876543210",
    "vpa": "customer@bank",
    "status": "PENDING"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level Newton API processing status. For processed create responses, success is `SUCCESS`. |
| `responseCode` | string | Top-level Newton response code. For processed create responses, success is `SUCCESS`. |
| `responseMessage` | string | Top-level Newton response message. |
| `payload` | object | UPI-number create result. Present for processed responses. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id. |
| `merchantChannelId` | string | Merchant channel id. |
| `merchantCustomerId` | string | Merchant customer id from Newton's merchant-customer record. |
| `customerMobileNumber` | string | Customer mobile number stored by Newton, usually with country code. |
| `gatewayTimestamp` | string | NPCI response timestamp when available. Omitted if downstream did not return it. |
| `gatewayTransactionId` | string | Echo of request `upiRequestId`; used as the NPCI transaction id. |
| `gatewayResponseCode` | string | `00` for gateway success. Any other value indicates gateway/business failure. `JP91` is used when no downstream error code is available. |
| `gatewayResponseStatus` | string | `SUCCESS` when `gatewayResponseCode` is `00`; otherwise `FAILURE`. |
| `gatewayResponseMessage` | string | Downstream message when available; otherwise `Create UpiNumber failed`. |
| `upiNumber` | string | Echo of request `upiNumber`. |
| `vpa` | string | Echo of request `vpa`. |
| `status` | string | UPI number mapper status produced by processing, for example `ACTIVE`, `FAILED`, or `PENDING`. |

## Failure Scenarios

Failure responses use the same encrypted response transport as success responses. Examples below show decrypted bodies.

### Validation Failure

Returned when field-level validation fails, such as empty `deviceFingerPrint`, invalid `upiRequestId`, invalid VPA, invalid JSON in `udfParameters`, or invalid UPI number format.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"Upi Number should be between 8 to 10 digits\""
}
```

Other validation messages can include:

- `Field is empty`
- `merchantCustomerId length is not in between 1 and 256`
- `merchantCustomerId is not alphanumeric`
- `upiRequestId length is not between 1 and 35`
- `upiRequestId regex match failed`
- `customerVpa length is not between 3 and 255`
- `customerVpa regex failed`
- `JSON Text parse failed for udfParameters`
- `Upi Number is not a valid number input`
- `Upi Number contains same last 3 digits`
- `Upi Number starts with zero`

### Authentication, Signature, Encryption, and Timestamp Failures

Returned when request envelope verification, signature verification, required auth headers, `iat`, or timestamp validation fails.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Invalid encrypted payload parsing can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload"
}
```

### Merchant API Access Disabled or Not Allowed

Returned when merchant configuration blocks this API or an allow-list is configured and the registration API name is not allowed.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### IP Restriction Failure

Returned when merchant IP allowlisting is configured and `x-forwarded-for` is missing or the first IP is not allowlisted.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Prior Availability/Check Missing

Returned when the create request cannot find a valid prior availability/check cache entry for the same customer and UPI number.

```json
{
  "status": "FAILURE",
  "responseCode": "JP40",
  "responseMessage": "Check request not found for the UPI number"
}
```

For `existingVpa`/port flows, the equivalent missing-port-check failure is:

```json
{
  "status": "FAILURE",
  "responseCode": "JP42",
  "responseMessage": "Port request not found for the UPI number"
}
```

### Prior Availability/Check VPA Mismatch

Returned when `vpa` does not match the VPA recorded by the availability/check call.

```json
{
  "status": "FAILURE",
  "responseCode": "JP41",
  "responseMessage": "User's VPA doesnot match with the CHECK call"
}
```

Returned when `existingVpa` does not match the previous VPA recorded by the availability/check call.

```json
{
  "status": "FAILURE",
  "responseCode": "JPMM8",
  "responseMessage": "Existing VPA doesnot match with the CHECK call"
}
```

### Duplicate or Pending UPI Number

Returned when the same UPI number mapping already exists or is not available for creation.

```json
{
  "status": "FAILURE",
  "responseCode": "JPMM17",
  "responseMessage": "UPI number mapping already exists"
}
```

If an existing mapper is pending sync:

```json
{
  "status": "FAILURE",
  "responseCode": "JP44",
  "responseMessage": "UPI number status is pending to be synced"
}
```

### Customer Mobile Number Mismatch

Returned when a 10-digit UPI number does not equal the customer's registered mobile number without the `91` country code.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mobile number must be registered with same customer"
}
```

### Invalid UPI Number Details

Returned for product-level UPI-number detail mismatches, such as an existing mapper linked to a different VPA.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "UPI number details not valid"
}
```

### Customer UPI Number Limit Reached

Returned when the customer already has the maximum allowed mapper records or exceeds the mobile-number/numeric-ID limits.

```json
{
  "status": "FAILURE",
  "responseCode": "JP43",
  "responseMessage": "Max allowed UPI number registrations reached"
}
```

### Device Fingerprint Mismatch

The create route validates `deviceFingerPrint` and optional `fallbackDeviceFingerPrint` against the stored customer device. The shared device validator can reject mismatches with an invalid-data or fingerprint-mismatch style response depending on the path that raises the error.

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

### NPCI Timeout or Service Unavailable

Returned when the NPCI register-mapper call times out and Newton treats it as a service-unavailable route failure.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

If NPCI supplies a timeout code, the last segment of `responseCode` and the parenthesized value in `responseMessage` contain that code.

### Bad NPCI Response

Returned when downstream returns an error shape without an error code or Newton cannot decode the expected response.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

### Internal Server Error

Returned for unexpected server-side failures, missing required internal state, or unhandled downstream decode failures.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Do not retry blindly with a new `upiRequestId` after a timeout or `PENDING` mapper status. First fetch/reconcile the UPI number state or wait for the configured mapper callback.
- If the response has top-level `SUCCESS`, still check `payload.gatewayResponseStatus`. Treat only `payload.gatewayResponseStatus = "SUCCESS"` and `payload.status = "ACTIVE"` as successful registration.
- If create fails with `JP40`, `JP42`, `JP41`, or `JPMM8`, repeat the availability/check flow and then call create again with matching values.
- If create fails with `JPMM17`, `JP44`, or `JP43`, do not retry immediately. Show the current status to the customer or use fetch/update flows as appropriate.
- If create fails with validation or authentication errors, fix the request, envelope, headers, timestamp, or merchant configuration before retrying.
- If create returns a downstream failure code in `payload.gatewayResponseCode`, use that code and message for customer support/reconciliation; a repeated call may be rejected as duplicate or pending depending on the mapper state.

## Source References

- API route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:660)
- Route handler and authentication wrapper: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3246)
- Request and response types: [src/Newton/Types/API/ServerToServer/UPIMapper.hs](../../src/Newton/Types/API/ServerToServer/UPIMapper.hs:19)
- Request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:13)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Create route product logic: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1284)
- NPCI register-mapper logic: [src/Newton/Product/UpiNumberV2.hs](../../src/Newton/Product/UpiNumberV2.hs:57)
- Prior availability/check validation: [src/Newton/Product/UpiNumberV2.hs](../../src/Newton/Product/UpiNumberV2.hs:577)
- UPI-number limits and duplicate checks: [src/Newton/Product/UpiNumberV2.hs](../../src/Newton/Product/UpiNumberV2.hs:620)
- UPI-number request validation rules: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:809)
- Response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2153)
- Error constructors: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:872)
