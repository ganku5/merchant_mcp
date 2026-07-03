# NPCI Token API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/npci/token`

## Overview

The NPCI Token API is a server-to-server API used by a merchant backend to fetch an NPCI credential token for a bound UPI customer device. Newton validates the merchant, merchant customer, customer, bound device fingerprint, and NPCI response before returning the token or the NPCI gateway result.

Use this API when your backend is coordinating a UPI device or credential workflow and the client application needs an NPCI token generated from the customer's bound device, package name, mobile number, and common-library challenge.

Payloads use the standard Newton server-to-server request and response envelope. Examples in this guide show the decrypted business payload for readability.

## Business Use Case

NPCI Token helps merchants:

- Fetch the NPCI token required by UPI common-library credential flows.
- Bind the token request to an existing Newton merchant customer and customer profile.
- Validate that the request came from the customer's bound device before calling NPCI.
- Preserve the merchant's `upiRequestId` as the gateway transaction id for tracing.
- Return NPCI business failures in a structured gateway response without hiding the original NPCI code.

## Integration Flow

1. Merchant backend receives or generates the token challenge from the client/common-library workflow.
2. Merchant backend sends the decrypted business payload inside the standard S2S JWS or JWE envelope.
3. Newton unwraps the payload, validates merchant authentication, API access, timestamp, optional IP allowlisting, and merchant customer/customer lookup.
4. Newton validates the decrypted request fields.
5. Newton fetches the merchant customer's bound device and recomputes the expected device fingerprint.
6. Newton accepts the request only when `deviceFingerPrint` or `fallbackDeviceFingerPrint` matches the bound device.
7. Newton builds an NPCI `ReqListKeys` `GetToken` request. For `tokenRequestType = "initial"`, Newton also sends registration-flow metadata to NPCI.
8. Newton calls NPCI and returns either the token or the NPCI gateway failure details.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. Newton uses it during auth to load the merchant customer and customer records.
- `upiRequestId`: Merchant-generated request id for this token call. Newton uses it for monitoring and returns it as `gatewayTransactionId`.
- `deviceFingerPrint`: Hash/fingerprint value for the device currently attempting the flow.
- `fallbackDeviceFingerPrint`: Optional previous or alternate device fingerprint accepted for this request.

## Endpoint

```http
POST /api/{apiVersion}/merchants/npci/token
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version segment configured for the merchant integration. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Use `application/json`. |
| `x-merchant-id` | Yes | Merchant id issued by Newton. Used to resolve the merchant before payload verification. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued by Newton. Used with `x-merchant-id` to resolve the merchant. |
| `x-sub-merchant-id` | Conditional | Required only when the integration is configured to authenticate a sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required only when the integration is configured to authenticate a sub-merchant channel. |
| `x-timestamp` | Yes | 13-digit epoch milliseconds. Newton rejects timestamps outside the configured freshness window; current code enforces +/- 30 minutes. |
| `x-merchant-signature` | Conditional | Required for plaintext unsigned payloads. For JWS/JWE integrations, integrity is verified from the envelope. Production integrations should use the signed/encrypted onboarding flow. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. Newton checks the first comma-separated IP against the merchant allowlist. |

Newton also reads the raw request body internally while verifying signatures. Clients normally do not send `x-raw-body` directly; it is populated by the gateway/application middleware.

### Authentication, Signing, and Encryption

The route accepts the standard `EncRequest` union:

- JWE encrypted request:

```json
{
  "protected": "<base64url-jwe-header-with-kid>",
  "encryptedKey": "<base64url-encrypted-key>",
  "iv": "<base64url-iv>",
  "cipherText": "<base64url-ciphertext>",
  "tag": "<base64url-auth-tag>"
}
```

- JWS signed request:

```json
{
  "protected": "<base64url-jws-header-with-kid>",
  "payload": "<base64url-json-business-payload>",
  "signature": "<base64url-signature>"
}
```

- Plain JSON business payload, only where explicitly enabled for the environment/integration:

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "TOKREQ12345",
  "deviceFingerPrint": "b0f5f6d6f07b7c2f...",
  "tokenRequestType": "initial",
  "tokenChallenge": "CL_CHALLENGE_VALUE",
  "iat": "1782980250123"
}
```

For JWS and JWE requests, the decrypted business payload must include `iat`; Newton validates it as a 13-digit epoch-milliseconds timestamp. For plaintext unsigned requests, `iat` is not checked by this route, but `x-timestamp` is still checked.

## Request

### Initial Token Request

Use `tokenRequestType = "initial"` for an initial token request. This is the only value that changes the NPCI payload shape in this code path: Newton includes the merchant customer's registration flow metadata in the outgoing NPCI request.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "TOKREQ12345",
  "deviceFingerPrint": "b0f5f6d6f07b7c2f9cf3120a5d0d39b3e3a6e0d47c64b4f315e4d3d3d44219a4",
  "fallbackDeviceFingerPrint": "3f94c9d70807c8b16a99738d2f8e21c3f59b6ac07290e6f7b7dd0f8c32b5c9e1",
  "tokenRequestType": "initial",
  "tokenChallenge": "CL_CHALLENGE_VALUE",
  "iat": "1782980250123",
  "udfParameters": "{\"cartId\":\"CART123\"}",
  "clVersion": "2.1"
}
```

### Non-Initial Token Request

For any non-`initial` token subtype supported by the UPI/NPCI common-library flow, Newton passes `tokenRequestType` through to NPCI as the credential subtype and does not add the initial registration metadata.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "TOKREQ12346",
  "deviceFingerPrint": "b0f5f6d6f07b7c2f9cf3120a5d0d39b3e3a6e0d47c64b4f315e4d3d3d44219a4",
  "tokenRequestType": "rotate",
  "tokenChallenge": "CL_REFRESH_CHALLENGE",
  "iat": "1782980251123",
  "clVersion": "2.1"
}
```

### Minimal Plaintext Example

This is the smallest decrypted business payload accepted by the API type and request validator. It is shown only to explain the business fields; production transport should follow the signed/encrypted S2S setup shared during onboarding.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "TOKREQ12347",
  "deviceFingerPrint": "b0f5f6d6f07b7c2f9cf3120a5d0d39b3e3a6e0d47c64b4f315e4d3d3d44219a4",
  "tokenRequestType": "initial",
  "tokenChallenge": "CL_CHALLENGE_VALUE"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | 1 to 256 characters. Must match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. Used during merchant auth to load merchant customer and customer records. |
| `upiRequestId` | string | Yes | No default. | 1 to 35 characters. Must be alphanumeric only. Returned as `payload.gatewayTransactionId`. |
| `deviceFingerPrint` | string | Yes | No default. | Must be non-empty. Compared with the fingerprint Newton recomputes from the bound device. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Not format-validated by this request validator. If supplied, Newton accepts it as an alternate value during device fingerprint comparison. |
| `tokenRequestType` | string | Yes | No default. | Must be non-empty. The code does not enforce an enum. Newton passes it to NPCI as the credential subtype. `initial` additionally sends registration-flow metadata. |
| `tokenChallenge` | string | Yes | No default. | Must be non-empty. Newton combines stored device fingerprint, package name, customer mobile number, and this challenge before calling NPCI. |
| `iat` | string | Conditional | No default. | Required for JWS/JWE payloads because the auth middleware validates it. Must be a 13-digit epoch-milliseconds timestamp within +/- 30 minutes. Not checked for plaintext unsigned payloads. |
| `udfParameters` | string | No | Omitted from response when absent. | Must be a JSON object encoded as a string. The string must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. Echoed in the top-level response when supplied. |
| `clVersion` | string | No | No default. | Must be non-empty when supplied. Forwarded to NPCI as the common-library version. |

### Processing Rules and Defaults

- Newton does not generate `upiRequestId` for this API. Send a new alphanumeric id for each attempt.
- Newton does not default `tokenRequestType`, `tokenChallenge`, or `deviceFingerPrint`.
- Newton finds the bound device from the merchant customer. If the merchant customer has no device id, the request fails.
- Newton requires the merchant customer to have a stored package name before building the NPCI request.
- For normal PSP mode, Newton recomputes the expected fingerprint as the hash of stored device fingerprint plus stored SSID. For ICICI PSP mode, the stored fingerprint itself is used.
- Either `deviceFingerPrint` or `fallbackDeviceFingerPrint` may match the expected fingerprint.
- `tokenRequestType = "initial"` is special because Newton includes the merchant customer's registration flow metadata in the NPCI request. Stored values `SMS` and `SMV` are forwarded as-is; stored value `OTP` is sent as `SID`; absent/other values default to `SMS` at the NPCI payload layer.
- If the merchant has the internal `x-send-xml` option enabled, the response `npciToken` can contain the full NPCI XML response instead of only the token value. Most integrations receive only the token value.

## Response

The route returns `EncResponse GetNpciTokenResponse`. Depending on onboarding configuration and runtime handling, the HTTP response can be encrypted, signed, or plaintext. The examples below show the decrypted business response.

### Token Fetched

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
    "gatewayTransactionId": "TOKREQ12345",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Npci token fetched successfully",
    "npciToken": "NPCI_TOKEN_VALUE"
  },
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

### NPCI Business Failure Returned by Gateway

When NPCI responds with a non-success result and an error code, Newton still returns the S2S response wrapper with top-level `SUCCESS`; the NPCI result is represented inside `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

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
    "gatewayTransactionId": "TOKREQ12346",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U16",
    "gatewayResponseMessage": "NPCI error message mapped for U16"
  }
}
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton API status for the S2S call. Successful processing uses `SUCCESS`. |
| `responseCode` | string | Newton API response code. Successful processing uses `SUCCESS`. |
| `responseMessage` | string | Newton API response message. Successful processing uses `SUCCESS`. |
| `payload` | object | Business response payload. Present on successful Newton processing. |
| `udfParameters` | string | Echo of request `udfParameters`, omitted when not supplied. |

### `payload` Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the merchant customer record resolved during auth. |
| `customerMobileNumber` | string | Customer mobile number resolved from the merchant customer. |
| `gatewayTransactionId` | string | Same value as request `upiRequestId`. |
| `gatewayResponseStatus` | string | `SUCCESS` when NPCI/Galileo error code is `00`; `FAILURE` for any other code or missing code. |
| `gatewayResponseCode` | string | NPCI/Galileo error code. `00` means token fetched. Missing code is mapped to `JP91`. |
| `gatewayResponseMessage` | string | NPCI/Galileo user message. Defaults to `Fetch npci token failed` if no user message is available. |
| `npciToken` | string | NPCI token value. Omitted when NPCI did not return a token or when the gateway response is a business failure. |

## Failure Handling

Failure responses can be returned as an encrypted/signed `EncResponse` error or as a plain shared error body depending on where the failure occurs. After decrypting/unwrapping, client handling should use the underlying JSON shapes below.

### Request JSON or Envelope Cannot Be Parsed

Examples:

- Body does not match plaintext, JWS, or JWE shape.
- JWS payload is not valid base64url JSON.
- JWE decrypts to an unsupported payload shape.

Representative body:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload",
  "payload": null
}
```

Client handling: do not retry unchanged. Fix JSON, JWS/JWE construction, `kid`, payload encoding, or key configuration.

### Authentication, Signature, Encryption, or Timestamp Failure

Examples:

- Missing or invalid `x-merchant-id` or `x-merchant-channel-id`.
- JWS verification fails.
- JWE decryption fails.
- Plaintext `x-merchant-signature` is missing or invalid.
- `iat` is missing for JWS/JWE.
- `x-timestamp` or `iat` is not a 13-digit epoch-milliseconds value.
- Timestamp is outside the accepted +/- 30 minute window.

Representative unauthorized body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Representative timestamp body:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number",
  "payload": null
}
```

Client handling: do not retry blindly. Regenerate the envelope/signature with the exact raw body, current timestamp, correct key id, and merchant credentials.

### Merchant API Disabled, Not Allowed, or IP Restricted

If the merchant configuration blocks this API or has an allowlist that does not include this API, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

If `whitelistedIps` is configured and the request IP is absent or not in the list, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Client handling: confirm merchant onboarding, API allowlist, sub-merchant setup if used, and network egress IPs with Newton.

### Request Validation Failure

Newton validates the decrypted business payload before calling NPCI. Validation failures are returned as `BAD_REQUEST` with a message describing the failed field rule.

Example:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"deviceFingerPrint field is empty\"",
  "payload": null
}
```

Other realistic validation messages include:

- `RegexValidation "merchantCustomerId is not alphanumeric"`
- `LengthValidation "merchantCustomerId length is not in between 1 and 256"`
- `RegexValidation "upiRequestId regex match failed"`
- `LengthValidation "upiRequestId length is not between 1 and 35"`
- `LengthValidation "tokenRequestType field is empty"`
- `LengthValidation "tokenChallenge field is empty"`
- `UnexpectedType "JSON Text parse failed for udfParameters"`
- `LengthValidation "Field is empty"` for an empty `clVersion`

Client handling: fix the request body. Reuse the same `upiRequestId` only if no downstream NPCI call was made; validation failures occur before the NPCI call.

### Merchant Customer, Customer, Device, or Package Lookup Failure

Newton loads the merchant customer and customer during auth, then loads the bound device and package name before calling NPCI. Missing records or missing required stored values are returned as shared error responses.

Representative merchant customer/customer/device data failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid DeviceId cannot be null for merchantCustomer",
  "payload": null
}
```

Representative internal missing package/fingerprint failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling: do not retry unchanged. Ensure the customer has completed registration/device binding successfully before requesting an NPCI token.

### Device Fingerprint Mismatch

If neither `deviceFingerPrint` nor `fallbackDeviceFingerPrint` matches the bound device, Newton rejects the request before calling NPCI.

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH",
  "payload": null
}
```

Client handling: refresh device-binding state on the client. If the device changed legitimately, complete the required device registration/binding flow before retrying.

### NPCI Token Missing in Success Response

If NPCI returns `SUCCESS` but does not include a key/token list, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "NPCI key token not found",
  "payload": null
}
```

Client handling: retry with a new `upiRequestId` after a short delay. If repeated, raise the `upiRequestId` and timestamp to Newton support.

### NPCI Business Failure

NPCI business failures are usually returned as a successful Newton API response with gateway failure fields, not as top-level failures.

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
    "gatewayTransactionId": "TOKREQ12348",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U16",
    "gatewayResponseMessage": "NPCI error message mapped for U16"
  }
}
```

Client handling: treat `payload.gatewayResponseStatus = "FAILURE"` as a failed token fetch even when top-level `status` is `SUCCESS`. Follow the mapped gateway response message/code. Retry only if the code is known to be transient for your UPI flow.

### Downstream Timeout or Unreachable NPCI

If the downstream call reports both `error = true` and `timeout = true`, Newton throws a service-unavailable error.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U90",
  "responseMessage": "NPCI service is not reachable at the moment (U90)",
  "payload": null
}
```

If no downstream code is available, the suffix is `NA`:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)",
  "payload": null
}
```

Client handling: retry with exponential backoff and a new `upiRequestId` unless Newton support has advised otherwise.

### Unexpected Error

Unexpected decode failures, missing downstream Redis entries, or unhandled exceptions can produce:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling: retry once with a new `upiRequestId` after a short delay. If repeated, escalate with `merchantCustomerId`, `upiRequestId`, `x-timestamp`, and the Newton request id if available.

## Retry and Idempotency Guidance

- Treat `upiRequestId` as the trace/idempotency identifier for this token attempt. Newton returns it as `gatewayTransactionId`.
- Use a new `upiRequestId` for each retry after a downstream timeout, internal error, or missing NPCI token. This avoids ambiguity because the endpoint does not persist an idempotency record for token responses.
- Do not retry unchanged for validation, auth/signature/encryption, API-disabled, IP allowlist, lookup, or device fingerprint failures. Fix the underlying request or configuration first.
- For top-level `SUCCESS` with `payload.gatewayResponseStatus = "FAILURE"`, handle the NPCI code as the source of truth. Retry only when your integration's NPCI/common-library guidance classifies that code as transient.
- Keep `x-timestamp` and JWS/JWE `iat` fresh on every retry. The current code rejects values outside +/- 30 minutes.
- Because this API calls NPCI synchronously and returns the token directly, there is no later status-check endpoint for the token result. Preserve `upiRequestId` and gateway fields in your logs.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:485)
- Route handler and middleware chain: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2749)
- Request, response, and validation types: [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:642)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Payload verification and JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant auth, API allowlist/blocklist, IP restriction, and timestamp checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Business route and timeout failure handling: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1129)
- Device/customer PII handling and NPCI token call: [src/Newton/Product/MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:2023)
- Device lookup and fingerprint validation: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:654), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Outgoing Galileo/NPCI request construction: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:911)
- NPCI `ReqListKeys` `GetToken` call and response handling: [src/Newton/External/NPCI/NpciV2.hs](../../src/Newton/External/NPCI/NpciV2.hs:266)
- S2S response mapping: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1909)
- Gateway response status mapping: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:1049)
- Validation error wrapper and validation helpers: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- Shared error responses: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:25)
