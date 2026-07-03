# UPI Number Availability API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/upiNumber/availability`

## Overview

UPI Number Availability checks the current mapper status of a UPI Number for a merchant customer and VPA. Newton validates the customer profile, registered device fingerprint, and VPA ownership, then checks the UPI Number state through the mapper flow.

Despite the path name, this API is not only a yes/no lookup. The `action` value controls whether the call is a normal availability check, a fetch-style status check, or a pre-check for porting a mobile-number UPI Number. Successful checks are cached temporarily and are used by follow-up UPI Number create or port flows.

Use this API before creating or porting a UPI Number, or when the merchant backend needs to verify the mapper status of a UPI Number for a customer profile.

## Business Use Case

This API helps merchants:

- Check whether a numeric UPI Number can be claimed for a customer.
- Check whether a mobile-number UPI Number belongs to the same registered customer before a port/create flow.
- Verify that the UPI Number is associated with the expected VPA and profile.
- Detect existing mapper states such as `ACTIVE`, `INACTIVE`, `DEREGISTER`, or `NEW`.
- Cache a successful `CHECK` or `PORT` result so a later create/port request can prove that availability was checked recently.

## Integration Flow

1. Merchant identifies the registered customer profile, device fingerprint, VPA, and UPI Number.
2. Merchant signs and/or encrypts the request using the Newton server-to-server envelope.
3. Merchant calls `POST /api/{apiVersion}/merchants/upiNumber/availability`.
4. Newton verifies the merchant, signature, API access, IP restrictions, timestamp, and request payload.
5. Newton validates the merchant customer, customer, device fingerprint, and VPA.
6. Newton checks local mapper state when mapper-table mode is enabled, and calls the downstream mapper service/NPCI where required.
7. Newton returns a top-level API result and a nested gateway result. Use `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.status` for business handling.

## Endpoint

```http
POST /api/{apiVersion}/merchants/upiNumber/availability
```

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope. Examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-merchant-id` | Yes | Merchant id issued during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued during onboarding. |
| `x-timestamp` | Yes | Request timestamp validated by Newton. |
| `x-merchant-signature` | Yes for unsigned/plain business payloads | Signature over merchant id, channel id, optional sub-merchant ids, timestamp, and raw body. |
| `x-request-id` | No | Optional client request id. Newton echoes it as a response header; if omitted Newton generates one. |
| `x-session-id` | No | Optional session id. Defaults to `x-request-id` when omitted. |
| `x-forwarded-for` | Conditional | Required when the merchant is configured with `whitelistedIps`; first IP in the header must be whitelisted. |
| `x-sub-merchant-id` | Conditional | Required only for configured sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Conditional | Required only for configured sub-merchant integrations. |

Response headers:

| Header | Description |
| --- | --- |
| `x-requestid` | Newton request id used for tracing. |
| `x-sessionid` | Newton session id used for tracing. |
| `X-Response-Signature` | Present for unsigned response mode. For JWS/JWE response strategies, the response body itself is signed/encrypted instead. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the URL path, as shared during onboarding. The handler for this endpoint does not branch on this value, but the route requires it. |

## Authentication, Signing, and Encryption

The route accepts the common Newton `EncRequest` envelope:

- Plain business JSON, signed through `x-merchant-signature`.
- JWS signed body.
- JWE encrypted body containing a signed payload.

For JWS/JWE, Newton validates the key id (`kid`), signature, and/or decryption key configured for the merchant. For plain JSON, Newton validates `x-merchant-signature`. The decrypted business payload must include `iat` for signed/encrypted request modes; Newton validates it as a timestamp before signature/API checks.

Before product logic runs, Newton also:

- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- Loads merchant configuration.
- Rejects blocked APIs and enforces `allowedApiNames` when configured.
- Resolves `merchantCustomerId` to the merchant customer and customer records.
- Enforces IP whitelisting when `whitelistedIps` is configured.
- Validates `x-timestamp`, except for limited checksum-bypass development/UAT cases.

## Request

### Minimum Request

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMCHECK12345",
  "upiNumber": "9876543210",
  "deviceFingerPrint": "registered-device-fingerprint",
  "action": "CHECK",
  "vpa": "customer@psp",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

### Port Pre-check Request

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMPORT12345",
  "upiNumber": "9876543210",
  "deviceFingerPrint": "registered-device-fingerprint",
  "fallbackDeviceFingerPrint": "fallback-device-fingerprint",
  "action": "PORT",
  "vpa": "customer@psp",
  "udfParameters": "{\"journey\":\"upi-number-port\"}",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer/profile identifier. Used for authentication context, customer lookup, and UPI Number check-cache keying. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated request id for this check. Returned as `payload.gatewayTransactionId` and used as the downstream transaction id. |
| `upiNumber` | string | Yes | No default. | Numeric UPI Number to check. Can be a 10-digit mobile number or an 8-10 digit numeric id. |
| `udfParameters` | string | No | No default. Omitted from response when absent. | JSON object encoded as a string. Echoed in the response when supplied. |
| `deviceFingerPrint` | string | Yes | No default. | Fingerprint of the device registered to the merchant customer profile. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate fingerprint accepted by device validation. |
| `action` | string | Yes | No default. | One of `CHECK`, `FETCH`, or `PORT`. |
| `vpa` | string | Yes | No default. | Customer VPA that must belong to the resolved customer/profile. Used as the mapper address in the downstream request. |
| `iat` | string | Conditional | No default. | Issued-at timestamp. Required by signed/encrypted request verification; not used by product logic after middleware validation. |

### Validation Rules

Newton applies request validation before business processing:

| Field | Rule |
| --- | --- |
| `merchantCustomerId` | 1-256 characters. Must match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. |
| `upiRequestId` | 1-35 characters. Alphanumeric only: `^[a-zA-Z0-9]+$`. |
| `upiNumber` | Numeric only. A 10-digit value is accepted as a mobile-number UPI Number. Non-10-digit numeric ids must be 8-10 digits, must not start with zero, and must not have the same last three digits. |
| `udfParameters` | Must be a JSON object encoded as text and must not contain restricted characters matched by the validator. |
| `deviceFingerPrint` | Must be non-empty and must match the registered device fingerprint. `fallbackDeviceFingerPrint` is also accepted when supplied. |
| `action` | Must parse as one of `CHECK`, `FETCH`, or `PORT`. Unknown values fail JSON parsing or validation before business logic. |
| `vpa` | 3-255 characters and must match `local@handle` style VPA regex `^[a-zA-Z0-9.-]{1,}@[a-zA-Z0-9.-]{1,}$`. |
| `iat` | Timestamp format must be valid when request signing/encryption expects it. |

Business validation also requires:

- The merchant customer must exist for the authenticated merchant.
- The merchant customer must have a customer record.
- A registered device must exist for the merchant customer.
- `vpa` must exist for the customer and merchant customer.
- If a 10-digit `upiNumber` is supplied, it must equal the customer's registered mobile number without country code. In storage, the customer mobile is compared as `91` + `upiNumber`.
- Existing mapper records are checked when mapper-table mode is enabled. An active mapping for another merchant customer is rejected.
- If an existing mapper record is not in `PENDING_CHANGE_VPA`, the request VPA must match the mapper record's VPA.
- For `PORT`, numeric ids shorter than 10 digits are rejected because only mobile-number UPI Numbers can be ported.
- For `PORT`, Newton expects a recent prior check-cache record except in the ICICI PSP mode path where this may be skipped for prior-VPA cases.
- For `PORT`, the VPA in the cached check result must match the current request VPA.

### Availability and Eligibility Behavior

The downstream mapper response drives the nested gateway result:

- `payload.gatewayResponseStatus = "SUCCESS"` and `payload.gatewayResponseCode = "00"` means the check call completed successfully.
- `payload.status = "NEW"` generally means the UPI Number is available for creation.
- `payload.status = "ACTIVE"` or `payload.status = "DISABLED"` means the UPI Number already maps to an active/inactive mapper state.
- `payload.status = "DELETED"` means downstream returned `DEREGISTER`.
- `payload.existingVpa` is returned when downstream provides the existing mapper VPA. For numeric ids, Newton may return the request VPA as the existing address in successful check handling.
- For non-ICICI PSP modes, Newton normalizes mapper statuses in the response: `DEREGISTER` to `DELETED`, `INACTIVE` to `DISABLED`, `ACTIVE` to `ACTIVE`, and `NEW` to `NEW`. ICICI mode returns the raw downstream status.

Caching behavior:

- A successful downstream response writes a check-cache record under the merchant customer and UPI Number.
- The default cache TTL is 600 seconds.
- For `CHECK`, the cache stores the requested VPA and marks the number available only when downstream status is `NEW`.
- For `PORT`, the cache stores the requested VPA and previous VPA information, and marks the number eligible only when downstream status is `ACTIVE` or `INACTIVE`.
- Some downstream `MM18` failures also write a negative cache entry so follow-up validation can fail consistently.

## Response

### Available UPI Number

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantCustomerId": "CUST12345",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT123",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "UPINUMCHECK12345",
    "gatewayTimestamp": "2026-07-02T10:30:01+05:30",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your CHECK call was successful",
    "upiNumber": "9876543210",
    "status": "NEW"
  },
  "udfParameters": "{\"journey\":\"upi-number-create\"}"
}
```

### Existing UPI Number

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantCustomerId": "CUST12345",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT123",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "UPINUMCHECK12346",
    "gatewayTimestamp": "2026-07-02T10:31:01+05:30",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your CHECK call was successful",
    "upiNumber": "9876543210",
    "existingVpa": "customer@psp",
    "status": "ACTIVE"
  }
}
```

### Downstream Negative Result

A downstream business failure is returned as a completed API call with nested gateway failure fields:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantCustomerId": "CUST12345",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT123",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "UPINUMCHECK12347",
    "gatewayTimestamp": "2026-07-02T10:32:01+05:30",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "MM18",
    "gatewayResponseMessage": "UPI number is not available for linking",
    "upiNumber": "9876543210"
  }
}
```

### Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level Newton API status. A completed check response uses `SUCCESS` even when the nested gateway result is negative. |
| `responseCode` | string | Top-level Newton API code. Successful handler completion returns `SUCCESS`. |
| `responseMessage` | string | Top-level Newton API message. |
| `payload` | object | Business response payload. |
| `udfParameters` | string | Echo of request `udfParameters`, when supplied. |

### `payload` Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `merchantChannelId` | string | Merchant channel id from merchant configuration. |
| `merchantId` | string | Merchant id from merchant configuration. |
| `customerMobileNumber` | string | Customer mobile number from Newton records. |
| `gatewayTransactionId` | string | Echo of request `upiRequestId`. |
| `gatewayTimestamp` | string | Downstream mapper/NPCI timestamp or local mapper timestamp, when available. |
| `gatewayResponseStatus` | string | `SUCCESS` when `gatewayResponseCode` is `00`; otherwise `FAILURE`. If downstream did not provide a code, Newton uses `FAILURE`. |
| `gatewayResponseCode` | string | Downstream error/code. `00` means the check completed successfully. If absent from downstream, Newton maps it to `JP91`. |
| `gatewayResponseMessage` | string | Downstream/user-facing message, or `CheckUpiNumber failed` when unavailable. |
| `upiNumber` | string | UPI Number from the request. |
| `existingVpa` | string | Existing mapper VPA when downstream/local data provides it. Omitted otherwise. |
| `status` | string | Mapper status. Normalized values can include `NEW`, `ACTIVE`, `DISABLED`, and `DELETED`; ICICI PSP mode may return raw downstream status values such as `INACTIVE` or `DEREGISTER`. |

## Error Handling

Failure responses use the same response transport strategy as the rest of the S2S integration. If the response is encrypted/signed, decrypt/verify it before reading the body. The examples below show decrypted response bodies.

Clients should distinguish:

- Transport/auth/request failures: top-level `status = "FAILURE"` response body or non-2xx HTTP status depending on the layer.
- Completed check with negative downstream result: top-level `status = "SUCCESS"` and `payload.gatewayResponseStatus = "FAILURE"`.

### Request Validation Failure

Invalid request fields are rejected before business processing. Validation messages come from the field validators and may contain multiple comma-separated items.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"upiRequestId length is not between 1 and 35\"",
  "payload": null
}
```

Other validation examples:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"Upi Number should be between 8 to 10 digits\"",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\"",
  "payload": null
}
```

### Authentication, Signature, Encryption, and Timestamp Failures

Missing merchant headers, invalid signature, failed JWE decryption, failed JWS verification, missing/invalid `iat`, invalid `x-timestamp`, and IP whitelist failures are rejected before product logic.

Typical authorization failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

API blocked or not enabled for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

JWE payload parses but the decrypted content is invalid JSON for the expected request type:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.field: expected ...",
  "payload": null
}
```

### Device Fingerprint Failure

If neither `deviceFingerPrint` nor `fallbackDeviceFingerPrint` matches the registered device:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH",
  "payload": null
}
```

### UPI Number and Mapper Eligibility Failures

Existing active mapping for another profile, pending deregister state, or otherwise unavailable UPI Number:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMM17",
  "responseMessage": "UPI number mapping already exists",
  "payload": null
}
```

UPI Number record exists but its VPA does not match the requested VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "UPI number details not valid",
  "payload": null
}
```

10-digit UPI Number does not match the customer's registered mobile:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mobile number must be registered with same customer",
  "payload": null
}
```

Numeric id sent with `action = "PORT"`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Numeric ID can't be ported",
  "payload": null
}
```

`PORT` requested without the required prior check-cache record:

```json
{
  "status": "FAILURE",
  "responseCode": "JP40",
  "responseMessage": "Check request not found for the UPI number",
  "payload": null
}
```

VPA does not match the prior cached check:

```json
{
  "status": "FAILURE",
  "responseCode": "JP41",
  "responseMessage": "User's VPA doesnot match with the CHECK call",
  "payload": null
}
```

### Missing Merchant, Customer, Device, or VPA Records

If the merchant customer, customer, device, or VPA lookup fails, the API returns an error response from the lookup layer. Exact `responseCode` and HTTP status depend on the failing lookup/helper. Treat these as non-retryable until the merchant customer/device/VPA setup is corrected.

Client handling:

- Verify the merchant headers identify the expected merchant.
- Verify `merchantCustomerId` belongs to that merchant.
- Verify the customer is onboarded and has a registered device.
- Verify `vpa` is already linked to that customer/profile.

### Downstream Mapper/NPCI Failure

When downstream returns a business error code, Newton usually returns top-level success with nested gateway failure:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantCustomerId": "CUST12345",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT123",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "UPINUMCHECK12347",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "MM18",
    "gatewayResponseMessage": "UPI number is not available for linking",
    "upiNumber": "9876543210"
  }
}
```

When the downstream call times out and is treated as service unavailable by the wrapper:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U90",
  "responseMessage": "NPCI service is not reachable at the moment (U90)",
  "payload": null
}
```

If a downstream response cannot be decoded or required response fields are missing:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

## Retry and Client Handling Guidance

- Use a unique `upiRequestId` for each check attempt.
- Do not retry validation/authentication failures without changing the invalid request, credentials, headers, IP allowlist, or merchant configuration.
- Do not treat top-level `status = "SUCCESS"` alone as availability. Always inspect `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.status`.
- For create flows, proceed only when the check result is successful and the returned mapper status is appropriate for your flow, typically `NEW`.
- For port flows, call this API with `action = "PORT"` shortly before the follow-up port/create request. The default check-cache TTL is 600 seconds.
- Retry `SERVICE_UNAVAILABLE_NPCI_*` or timeout-style failures with backoff. Use a new `upiRequestId` unless Newton support has advised otherwise.
- For nested downstream failures such as `gatewayResponseStatus = "FAILURE"`, follow the downstream code/message. Some failures are business-terminal and should not be retried immediately.
- Store `gatewayTransactionId`, `gatewayResponseCode`, `gatewayResponseStatus`, `gatewayTimestamp`, `upiNumber`, `existingVpa`, and `status` for reconciliation and support.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:669)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3920)
- Request and response types: [src/Newton/Types/API/ServerToServer/UPIMapper.hs](../../src/Newton/Types/API/ServerToServer/UPIMapper.hs:101)
- Action enum: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:781)
- S2S envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request body extraction/envelope verification: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Merchant signature/API/IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:45)
- Payload verification/JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:61)
- Product route and eligibility checks: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:491)
- Downstream check and response handling: [src/Newton/Product/UpiNumberV2.hs](../../src/Newton/Product/UpiNumberV2.hs:229)
- Response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2185)
- Gateway response mapping: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:1049)
- Check-cache read/write: [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs:785)
- Default check-cache TTL: [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs:2449)
- Request validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:137)
- UPI Number error bodies: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:872)
