# Fetch UPI Number API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/upiNumber/fetch`

## Overview

Fetch UPI Number is a merchant server-to-server API used to fetch the mapper status returned by NPCI for a customer's VPA, or for a specific UPI Number under that VPA.

Newton validates the merchant, customer profile, registered device fingerprint, and VPA ownership, then sends a downstream mapper `FETCH` request. When `upiNumber` is supplied, Newton fetches that UPI Number as an ID lookup. When `upiNumber` is omitted, Newton fetches by VPA.

Use this API for reconciliation and status display after UPI Number create/update flows, or whenever the merchant backend needs the current mapper state for a customer VPA.

## Business Use Case

This API helps merchants:

- Show a customer the UPI Numbers currently mapped to a VPA.
- Confirm whether a specific mobile-number UPI Number or numeric ID is active, inactive, deregistered, or otherwise unavailable according to the mapper response.
- Reconcile create/update outcomes after a timeout, callback delay, or ambiguous client state.
- Verify mapper state before allowing a customer to update, deregister, or recreate a UPI Number.
- Store the downstream mapper code and message for customer support and audit trails.

## Integration Flow

1. Merchant identifies the customer profile, registered device fingerprint, and VPA.
2. Merchant optionally includes `upiNumber` to fetch one UPI Number. Omit it to fetch mapper details for the VPA.
3. Merchant signs and/or encrypts the request using the Newton server-to-server envelope.
4. Merchant calls `POST /api/{apiVersion}/merchants/upiNumber/fetch`.
5. Newton verifies the merchant headers, payload signature/encryption, timestamp, API access, and IP allowlist.
6. Newton resolves `merchantCustomerId` to the merchant customer and customer records.
7. Newton validates the request body, registered device fingerprint, and VPA ownership.
8. Newton calls NPCI mapper `FETCH`.
9. Merchant decrypts/verifies the response and uses `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.upiNumbers` for business handling.

Important identifiers:

- `merchantCustomerId`: Merchant's customer/profile identifier. Used for authentication context and customer lookup.
- `upiRequestId`: Merchant-generated id for this fetch attempt. Newton forwards it as the downstream transaction id and returns it as `payload.gatewayTransactionId`.
- `vpa`: Customer VPA used as the downstream mapper address. It must already belong to the resolved customer/profile.
- `upiNumber`: Optional UPI Number to fetch. If absent, the call is a VPA-level fetch.

## Endpoint

```http
POST /api/{apiVersion}/merchants/upiNumber/fetch
```

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show decrypted business payloads for readability.

## Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured during onboarding. The fetch handler does not branch on this path value, but the route requires it. |

## Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body must be JSON. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-merchant-signature` | Conditional | Required for plain unsigned business payloads. Signature is verified over merchant ids, optional sub-merchant ids, timestamp, and raw request body. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness except for limited checksum-bypass development/UAT cases. |
| `x-forwarded-for` | Conditional | Required when the merchant has configured `whitelistedIps`; the first IP in this header must be allowlisted. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-request-id` | No | Optional request id for tracing. Newton echoes it in response headers; if omitted Newton generates one. |
| `x-session-id` | No | Optional session id for tracing. Defaults to `x-request-id` when omitted. |
| `x-api-version` | Recommended | Use the version shared during onboarding. The fetch product logic does not branch on this header. |

Response headers:

| Header | Description |
| --- | --- |
| `x-requestid` | Newton request id used for tracing. |
| `x-sessionid` | Newton session id used for tracing. |
| `X-Response-Signature` | Present for unsigned response mode. For JWS/JWE response strategies, the response body itself is signed or encrypted. |

## Authentication and Encryption

Newton accepts the common `EncRequest` transport:

- JWE encrypted body with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed body with `payload`, `signature`, and `protected`.
- Plain business JSON, still protected by `x-merchant-signature` in production S2S integrations.

For JWS/JWE, Newton validates the `kid`, merchant key configuration, signature, and/or decryption key. For plain JSON, Newton validates `x-merchant-signature`.

The decrypted business payload must include `iat` for signed or encrypted request modes because the signature middleware validates it before product logic runs. Plain unsigned payloads do not use `iat` for this middleware check, but production S2S integrations should follow the signed/encrypted onboarding process.

Before product logic runs, Newton also:

- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- Loads merchant configuration.
- Rejects blocked APIs and enforces `allowedApiNames` when configured. The API name for this route is `fetchUpiNumber`.
- Resolves `merchantCustomerId` to the merchant customer and customer records.
- Enforces IP allowlisting when configured.
- Validates `x-timestamp`.

## Request

### Fetch by VPA

Omit `upiNumber` when you want the mapper response for the VPA.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMFETCH12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "vpa": "customer@bank",
  "udfParameters": "{\"journey\":\"upi-number-status\"}",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

### Fetch a Specific UPI Number

Send `upiNumber` when you want Newton to fetch one mobile-number UPI Number or numeric ID.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMFETCH12346",
  "upiNumber": "9876543210",
  "deviceFingerPrint": "registered-device-fingerprint",
  "fallbackDeviceFingerPrint": "fallback-device-fingerprint",
  "vpa": "customer@bank",
  "iat": "2026-07-02T10:31:00+05:30"
}
```

### Fetch a Numeric ID

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMFETCH12347",
  "upiNumber": "12345678",
  "deviceFingerPrint": "registered-device-fingerprint",
  "vpa": "customer@bank",
  "iat": "2026-07-02T10:32:00+05:30"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer/profile identifier. Must resolve to a merchant customer under the authenticated merchant. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated request id for this fetch attempt. Returned as `payload.gatewayTransactionId` and used as the downstream transaction id. |
| `upiNumber` | string | No | If omitted, Newton sends a VPA-level mapper fetch with downstream subtype `VPA`. | UPI Number to fetch. When supplied, Newton validates the UPI Number format and sends downstream subtype `ID`. |
| `udfParameters` | string | No | No default. Omitted from response when absent. | JSON object encoded as a string. Echoed in the response when supplied. |
| `deviceFingerPrint` | string | Yes | No default. | Fingerprint of the device registered to the merchant customer profile. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate fingerprint accepted by device validation. |
| `vpa` | string | Yes | No default. | Customer VPA to fetch mapper details for. It must belong to the resolved customer and merchant customer. |
| `iat` | string | Conditional | No default. | Issued-at timestamp. Required by signed/encrypted request verification; not used by product logic after middleware validation. |
| `accountHolderName` | string | No | No default. In the normal merchant S2S route this field is accepted by the type but ignored; Newton derives the payer name from the VPA/account linkage. | Reserved for an alternate no-table/mobile-app transformer path. Merchants should omit it unless Newton explicitly asks for it. |

No business request field is defaulted by this route. Optional fields are either omitted from downstream/response behavior (`udfParameters`, `fallbackDeviceFingerPrint`, `accountHolderName`) or change the fetch mode (`upiNumber`).

## Validation and Processing Behavior

### Request Format Validation

Newton rejects the request before business processing when:

- `merchantCustomerId` is empty, longer than 256 characters, or fails its allowed-character rule.
- `upiRequestId` is empty, longer than 35 characters, or non-alphanumeric.
- `upiNumber` is supplied and fails UPI-number validation.
- `udfParameters` is supplied but is not a JSON-object string or contains restricted characters.
- `deviceFingerPrint` is empty.
- `vpa` fails VPA format validation.
- `iat` is missing or stale for signed/encrypted request types.

Validation rules:

| Field | Rule |
| --- | --- |
| `merchantCustomerId` | 1-256 characters. Must match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. |
| `upiRequestId` | 1-35 characters. Alphanumeric only: `^[a-zA-Z0-9]+$`. |
| `upiNumber` | Optional. If supplied, must be numeric. A 10-digit value is accepted as a mobile-number UPI Number. Non-10-digit numeric ids must be 8-10 digits, must not start with zero, and must not have the same last three digits. |
| `udfParameters` | Must be a JSON object encoded as text and must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |
| `deviceFingerPrint` | Must be non-empty and must match the registered device fingerprint or accepted fallback fingerprint during product validation. |
| `fallbackDeviceFingerPrint` | No format validator is applied by the request type. When supplied, it is considered during device fingerprint validation. |
| `vpa` | 3-255 characters and must match `local@handle` style VPA regex `^[a-zA-Z0-9.-]{1,}@[a-zA-Z0-9.-]{1,}$`. |
| `iat` | Timestamp format must be valid when request signing/encryption expects it. |
| `accountHolderName` | No request validator is applied in this route. It is ignored by the normal merchant S2S product path. |

### Product Validation

After request format validation, Newton checks:

- The merchant customer exists under the authenticated merchant.
- The merchant customer has a linked customer record.
- The merchant customer has a registered device.
- Either `deviceFingerPrint` or `fallbackDeviceFingerPrint` matches the registered device. In non-ICICI PSP modes, Newton compares against the hash derived from stored SSID and fingerprint. In ICICI PSP mode, it compares against the stored fingerprint.
- `vpa` exists for the customer and merchant customer. The normal route looks for active VPAs, where `active = true` or `active` is unset.
- The VPA/account linkage can provide an account-holder name. If no primary VPA account is found, Newton uses the VPA as the name. If a primary VPA account is found but the account lookup fails, the API fails.

The fetch route does not validate the UPI Number against the customer's registered mobile number. That stricter mobile-number ownership check exists in create/check flows, not in this fetch product path.

### Downstream Mapper Behavior

Newton sends an NPCI `ReqGetAddress` mapper request with:

- Transaction type/action `FETCH`.
- `txn.id = upiRequestId`.
- Payer address `vpa`.
- Payer name derived from the VPA/account linkage.
- Consent `CMREGISTRATION = Y`.
- Subtype `ID` and a `RegId` when `upiNumber` is supplied.
- Subtype `VPA` and no `RegId` when `upiNumber` is omitted.
- UPI number type `MOBILE` for 10-digit values and `NUMERICID` for shorter numeric IDs in the downstream request. The response item reports these as `MOBILE_NUMBER` and `NUMERIC_ID`.

When NPCI returns success, Newton requires `RegIdDetails` and at least one `Id` inside each returned detail. Newton maps each item into `payload.upiNumbers[]`.

When NPCI returns a business failure code, Newton usually returns a top-level successful API response with nested gateway failure fields. When the downstream failure does not include a usable error code, Newton returns a bad-NPCI-response failure instead of a processed payload.

Unlike the availability/check API, this fetch route does not write the UPI Number check cache and does not validate a prior availability/check result.

## Response

### Success Response: Fetch by VPA

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
    "gatewayTransactionId": "UPINUMFETCH12345",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your FETCH call was successful",
    "upiNumbers": [
      {
        "upiNumber": "9876543210",
        "upiNumberType": "MOBILE_NUMBER",
        "status": "ACTIVE",
        "vpa": "customer@bank"
      },
      {
        "upiNumber": "12345678",
        "upiNumberType": "NUMERIC_ID",
        "status": "INACTIVE",
        "vpa": "customer@bank"
      }
    ]
  },
  "udfParameters": "{\"journey\":\"upi-number-status\"}"
}
```

### Success Response: Fetch a Specific UPI Number

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
    "gatewayTransactionId": "UPINUMFETCH12346",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your FETCH call was successful",
    "upiNumbers": [
      {
        "upiNumber": "9876543210",
        "upiNumberType": "MOBILE_NUMBER",
        "status": "ACTIVE",
        "vpa": "customer@bank"
      }
    ]
  }
}
```

### Processed Response: Downstream Business Failure

Newton can return top-level `SUCCESS` while the downstream mapper fetch failed. Treat `payload.gatewayResponseStatus = "FAILURE"` as the business failure.

The exact `gatewayResponseCode` and `gatewayResponseMessage` depend on NPCI and Newton's error-code table. This example uses code `MM18`, which maps in this codebase to `Upi Number is mapped to different Vpa`.

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
    "gatewayTransactionId": "UPINUMFETCH12348",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "MM18",
    "gatewayResponseMessage": "Upi Number is mapped to different Vpa"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level Newton API processing status. A completed fetch response uses `SUCCESS` even when the nested gateway result is a business failure. |
| `responseCode` | string | Top-level Newton response code. For processed fetch responses, success is `SUCCESS`. |
| `responseMessage` | string | Top-level Newton response message. |
| `payload` | object | UPI Number fetch result. Present for processed responses. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `merchantChannelId` | string | Merchant channel id from merchant configuration. |
| `merchantId` | string | Merchant id from merchant configuration. |
| `customerMobileNumber` | string | Customer mobile number stored by Newton, usually with country code. |
| `gatewayTransactionId` | string | Echo of request `upiRequestId`; used as the downstream transaction id. |
| `gatewayResponseStatus` | string | `SUCCESS` when `gatewayResponseCode` is `00`; otherwise `FAILURE`. If no downstream code is available in a processed response, Newton maps the code to `JP91`, but the fetch wrapper usually throws a bad-response failure before returning that case. |
| `gatewayResponseCode` | string | Downstream mapper response code. `00` means the fetch completed successfully. Other values indicate mapper/business failure. |
| `gatewayResponseMessage` | string | Downstream/user-facing message. On successful fetch it is `Your FETCH call was successful`; when unavailable on a processed response, Newton uses `FetchUpiNumber failed`. |
| `upiNumbers` | array | Returned on successful downstream fetches when NPCI provides mapper details. Omitted on downstream business failures. |

The fetch response payload does not include `gatewayTimestamp`, `upiNumber`, `vpa`, or a top-level mapper `status`; those fields are present on some other UPI Number APIs but are not part of `FetchUpiNumberResponsePayload`.

### `payload.upiNumbers[]` Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `upiNumber` | string | UPI Number returned by NPCI for the mapper record. |
| `upiNumberType` | string | Derived from the returned UPI Number length. `MOBILE_NUMBER` for 10-digit values, `NUMERIC_ID` otherwise. |
| `status` | string | Mapper status returned in `RegIdDetails.idStatus`, such as `ACTIVE`, `INACTIVE`, `DEREGISTER`, or another downstream status value. Newton does not normalize this field in the fetch response. |
| `type` | string | Optional field in the shared `UpiNumberStatuses` type. The current fetch mapper sets it to `null`, so it is omitted from JSON. |
| `vpa` | string | VPA/address returned by NPCI for the mapper record. |

## Failure Scenarios

Failure responses use the same encrypted/signed response transport as success responses. Examples below show decrypted bodies. The shared error response omits `payload` when it is `null`; processed downstream responses include `payload`.

Clients should distinguish:

- Transport/auth/request failures: top-level `status = "FAILURE"` response body or non-2xx HTTP status depending on the layer.
- Completed fetch with downstream business failure: top-level `status = "SUCCESS"` and `payload.gatewayResponseStatus = "FAILURE"`.

### Request Validation Failure

Returned when field-level validation fails. Validation messages come from shared validators and may contain multiple comma-separated validation constructor strings when multiple fields fail.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"deviceFingerPrint field is empty\""
}
```

Invalid UPI Number format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"Upi Number should be between 8 to 10 digits\""
}
```

Invalid VPA format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\""
}
```

Invalid UDF string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Other validation messages can include:

- `LengthValidation "merchantCustomerId length is not in between 1 and 256"`
- `RegexValidation "merchantCustomerId is not alphanumeric"`
- `LengthValidation "upiRequestId length is not between 1 and 35"`
- `RegexValidation "upiRequestId regex match failed"`
- `LengthValidation "customerVpa length is not between 3 and 255"`
- `RegexValidation "Upi Number is not a valid number input"`
- `RegexValidation "Upi Number starts with zero"`
- `RegexValidation "Upi Number contains same last 3 digits"`

### Malformed Signed or Encrypted Business Payload

If a JWS/JWE envelope is structurally valid but the decoded business payload cannot be parsed as `FetchUpiNumberRequest`, Newton returns `INVALID_DATA`. The parser text varies by malformed field.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.vpa: parsing Text failed, expected String, but encountered Number"
}
```

If a JWE decrypts but the decrypted content is not the expected signed payload JSON:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If a JWE decrypts but the inner encrypted payload cannot be parsed as JSON, the parser message is returned as invalid data:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.merchantCustomerId: key \"merchantCustomerId\" not found"
}
```

### Authentication, Signature, Timestamp, and IP Failures

Returned when required merchant headers are missing, signature verification fails, JWS verification fails, JWE decryption fails, `iat` is missing/invalid for signed/encrypted requests, `x-timestamp` is missing/invalid, or IP allowlisting fails.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Merchant API Access Disabled or Not Allowed

Returned when merchant configuration blocks `fetchUpiNumber`, or an API allow-list is configured and does not include `fetchUpiNumber`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### Merchant Customer or Customer Setup Failure

Returned when `merchantCustomerId` does not resolve to an active profile under the authenticated merchant.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Returned when the merchant customer exists but does not have an active customer/device-binding context.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

If the stored merchant customer has no device id, the route can return an invalid-data response with the internal missing-field context:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid DeviceId cannot be null for merchantCustomer"
}
```

### Device Fingerprint Mismatch

Returned when neither `deviceFingerPrint` nor `fallbackDeviceFingerPrint` matches the registered device.

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

### VPA Not Found or Not Owned by Customer

Returned when the request VPA is not an active VPA for the resolved customer and merchant customer.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Vpa not found"
}
```

### Primary Account Lookup Failure

If the VPA has a primary VPA-account linkage but the linked account cannot be found, Newton returns the shared invalid-account response. If no primary VPA account exists, Newton uses the VPA as the payer name and continues.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

### Downstream Mapper Business Failure

When NPCI returns a failure with a usable code, Newton returns a processed response with top-level `SUCCESS` and nested gateway failure fields.

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
    "gatewayTransactionId": "UPINUMFETCH12349",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JPMM2",
    "gatewayResponseMessage": "Upi Number Mapping does not exist"
  }
}
```

Exact downstream code/message pairs can vary by NPCI response and Newton's error-code table. Treat any non-`00` `payload.gatewayResponseCode` as a failed mapper fetch.

### NPCI Timeout or Service Unavailable

Returned when the downstream NPCI fetch times out or the wrapper marks the call as service unavailable.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U90",
  "responseMessage": "NPCI service is not reachable at the moment (U90)"
}
```

If no timeout code is available, the last segment is `NA`:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

### Bad NPCI Response

Returned when NPCI reports an error but Newton cannot find a usable downstream error code.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

### Missing or Undecodable Successful NPCI Response Details

On downstream success, Newton expects `RegIdDetails` and at least one `Id` in each mapper detail. If those required fields are missing, or if a lower-level downstream response cannot be decoded, the route can return an internal server error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Use a unique `upiRequestId` for each fetch attempt.
- Do not rely on top-level `status = "SUCCESS"` alone. For business success, require `payload.gatewayResponseStatus = "SUCCESS"` and `payload.gatewayResponseCode = "00"`.
- Treat `payload.gatewayResponseStatus = "FAILURE"` as a completed mapper fetch with a downstream business failure. Do not retry immediately unless the downstream code is known to be transient.
- Retry `SERVICE_UNAVAILABLE_NPCI_*` and timeout-style failures with backoff. Use a fresh `upiRequestId` for a new attempt unless Newton support asks you to preserve the id for investigation.
- Do not retry validation, authentication, API access, IP allowlist, device fingerprint, customer setup, VPA ownership, or account lookup failures until the request or setup has been corrected.
- If a create/update call timed out, use this fetch API or the configured callback/reconciliation flow before attempting another create/update for the same UPI Number.
- Store `gatewayTransactionId`, `gatewayResponseStatus`, `gatewayResponseCode`, `gatewayResponseMessage`, and every returned `upiNumbers[]` item for support and audit trails.
- When `upiNumbers` is omitted, first inspect `gatewayResponseStatus`. Omission on gateway failure is not the same as a successful fetch with zero mapper records.

## Source References

- API route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:674)
- Route handler and authentication wrapper: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3938)
- Request and response types: [src/Newton/Types/API/ServerToServer/UPIMapper.hs](../../src/Newton/Types/API/ServerToServer/UPIMapper.hs:183)
- Nested `upiNumbers[]` type: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:854)
- Request envelope and response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:37)
- Request body extraction and request/session headers: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Merchant payload verification and JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Fetch product logic and wrapper failures: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:606)
- Downstream NPCI fetch and response handling: [src/Newton/Product/UpiNumberV2.hs](../../src/Newton/Product/UpiNumberV2.hs:497)
- Response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2067)
- Gateway response mapping: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:1049)
- UPI Number type derivation: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:3521)
- Request validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:137)
- UPI Number validation: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:809)
- Error constructors: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:16)
