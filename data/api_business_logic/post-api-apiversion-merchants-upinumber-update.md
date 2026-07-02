# Update UPI Number API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/upiNumber/update`

## Overview

Update UPI Number modifies an existing UPI Number mapper record for a merchant customer.

The merchant calls this API after a customer already has a UPI Number mapped to one of the customer's VPAs. Newton validates the request, verifies merchant signature and customer context, validates the registered device fingerprint, finds the existing mapper record, checks whether the requested action is allowed for the mapper's current state, marks the mapper as pending, and sends an NPCI modify-mapper request.

Use this API when the merchant needs to disable, reactivate, delete, or change the linked VPA for an existing UPI Number.

## Business Use Case

Update UPI Number helps merchants:

- Disable a currently active UPI Number without deleting the mapper permanently.
- Reactivate a disabled or deregistered UPI Number when the customer wants to use it again.
- Delete or deregister a UPI Number mapping.
- Move a UPI Number from one customer VPA to another VPA owned by the same merchant customer.
- Track the downstream NPCI modify-mapper result using the merchant-provided `upiRequestId`.
- Reconcile customer-visible mapper status using Newton's normalized statuses: `ACTIVE`, `DISABLED`, and `DELETED`.

## Integration Flow

1. Customer selects an update action for an existing UPI Number.
2. Merchant backend identifies the merchant customer, current mapper UPI Number, current linked VPA, and registered device fingerprint.
3. For `CHANGE_VPA`, merchant also identifies the new VPA and sends the current VPA as `existingVpa`.
4. Merchant signs and/or encrypts the request using the Newton server-to-server envelope.
5. Merchant calls `POST /api/{apiVersion}/merchants/upiNumber/update`.
6. Newton verifies the request envelope, merchant signature, API access, IP restrictions, timestamp, customer context, device fingerprint, VPA ownership, mapper record, and action/state compatibility.
7. Newton marks the mapper as pending, calls NPCI modify-mapper, and then updates or reverts local mapper state based on the downstream result.
8. Merchant reads `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.status` for business handling.

Important identifiers:

- `merchantCustomerId`: Merchant's customer/profile identifier. Newton uses it for signature-scoped customer lookup and mapper ownership.
- `upiRequestId`: Merchant-generated request id for this update attempt. Newton forwards it as the downstream transaction id and returns it as `payload.gatewayTransactionId`.
- `upiNumber`: Existing numeric UPI Number to modify.
- `vpa`: For `DELETE`, `DISABLE`, and `REACTIVATE`, this is the current linked VPA. For `CHANGE_VPA`, this is the new target VPA.
- `existingVpa`: Required only for `CHANGE_VPA`; this is the current linked VPA before the change.

## Endpoint

```http
POST /api/{apiVersion}/merchants/upiNumber/update
```

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show decrypted business payloads for readability.

## Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured during onboarding. The handler reads `x-api-version` for version-gated response behavior; the path segment is required by the route. |

## Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body must be JSON. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain business payloads. Signature is verified over merchant ids, timestamp, and raw request body. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness unless checksum-bypass behavior is explicitly enabled for non-production use. |
| `x-forwarded-for` | Conditional | Required when the merchant has configured `whitelistedIps`; the first IP in this header must be allowlisted. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-api-version` | Recommended | Use the version shared during onboarding. `coolingPeriodEndTime` is returned only when this parsed value is greater than `0`. |
| `x-request-id` | No | Optional client request id for tracing. Newton can echo or generate tracing headers depending on the response path. |
| `x-session-id` | No | Optional session id for tracing. |

Response headers:

| Header | Description |
| --- | --- |
| `x-requestid` | Newton request id used for tracing, when response header wrapping applies. |
| `x-sessionid` | Newton session id used for tracing, when response header wrapping applies. |
| `X-Response-Signature` | Present for unsigned response mode. For JWS/JWE response strategies, the response body itself is signed/encrypted. |

## Authentication, Signing, and Encryption

Newton accepts the common `EncRequest` transport:

- Plain decrypted business JSON, signed through `x-merchant-signature`.
- JWS signed body.
- JWE encrypted body containing a signed payload.

Encrypted JWE body shape:

```json
{
  "protected": "base64url-jwe-protected-header",
  "encryptedKey": "base64url-encrypted-content-encryption-key",
  "iv": "base64url-initialization-vector",
  "cipherText": "base64url-ciphertext",
  "tag": "base64url-authentication-tag"
}
```

Signed JWS body shape:

```json
{
  "payload": "base64url-json-payload",
  "signature": "base64url-signature",
  "protected": "base64url-jws-protected-header"
}
```

For JWS/JWE, Newton validates the key id (`kid`), signature, and/or decryption key configured for the merchant. For plain JSON, Newton validates `x-merchant-signature`. The decrypted business payload must include `iat` for signed/encrypted request modes because request verification validates it as an issued-at timestamp.

Before product logic runs, Newton also:

- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- Rejects blocked APIs and enforces `allowedApiNames` when configured.
- Resolves `merchantCustomerId` to the merchant customer and customer records.
- Enforces IP allowlisting when `whitelistedIps` is configured.
- Validates `x-timestamp`.
- Tracks VPA activity using the request `vpa`.

## Request

Route request type: `API.EncRequest TfS2S.ModifyMapperRequest`

Business payload type: `TfS2S.ModifyMapperRequest`

### Disable UPI Number

Use `DISABLE` when the customer wants the mapper inactive but not deleted.

```json
{
  "upiNumber": "9876543210",
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMUPD12345",
  "vpa": "customer@bank",
  "action": "DISABLE",
  "deviceFingerPrint": "3f9a3a6d8c0f9d2e",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

### Reactivate UPI Number

Use `REACTIVATE` to move an eligible disabled or deregistered mapper back to active status.

```json
{
  "upiNumber": "9876543210",
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMUPD12346",
  "vpa": "customer@bank",
  "action": "REACTIVATE",
  "deviceFingerPrint": "3f9a3a6d8c0f9d2e",
  "fallbackDeviceFingerPrint": "ab2d0d2f0f20c9e1",
  "udfParameters": "{\"journey\":\"upi-number-reactivate\"}",
  "iat": "2026-07-02T10:31:00+05:30"
}
```

### Delete UPI Number

Use `DELETE` to deregister the mapper. The response can include a downstream cooling-period end time when NPCI returns one and `x-api-version` is greater than `0`.

```json
{
  "upiNumber": "9876543210",
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMUPD12347",
  "vpa": "customer@bank",
  "action": "DELETE",
  "deviceFingerPrint": "3f9a3a6d8c0f9d2e",
  "iat": "2026-07-02T10:32:00+05:30"
}
```

### Change Linked VPA

For `CHANGE_VPA`, send the current linked VPA in `existingVpa` and the new target VPA in `vpa`. Both VPAs must belong to the same merchant customer, and the current mapper must be eligible for a VPA change.

```json
{
  "upiNumber": "9876543210",
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "UPINUMUPD12348",
  "existingVpa": "customerold@bank",
  "vpa": "customernew@bank",
  "action": "CHANGE_VPA",
  "deviceFingerPrint": "3f9a3a6d8c0f9d2e",
  "udfParameters": "{\"journey\":\"upi-number-change-vpa\"}",
  "iat": "2026-07-02T10:33:00+05:30"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `upiNumber` | string | Yes | No default. | Existing UPI Number to update. Must pass UPI-number format validation and must resolve to a mapper record for the merchant customer and linked VPA. |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id. Must resolve to a merchant customer under the authenticated merchant. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated id for this update attempt. Must be 1 to 35 alphanumeric characters. Returned as `payload.gatewayTransactionId`. |
| `vpa` | string | Yes | No default. | Customer VPA. For `DELETE`, `DISABLE`, and `REACTIVATE`, this must be the currently linked VPA. For `CHANGE_VPA`, this must be the new target VPA. |
| `existingVpa` | string | Conditional | No default. | Required for `CHANGE_VPA`; must be the current linked VPA for the existing mapper. Omit for `DELETE`, `DISABLE`, and `REACTIVATE`. |
| `action` | string | Yes | No default. | Supported product actions are `DELETE`, `DISABLE`, `REACTIVATE`, and `CHANGE_VPA`. The shared enum can parse `BLOCK` and `UNBLOCK`, but this API rejects them with `Action is invalid`. |
| `payeeUpiNumber` | string | No | No default. | Optional field accepted by the S2S request type and validated as a UPI Number when supplied. The current S2S transformer does not pass it into the core update request or response. |
| `deviceFingerPrint` | string | Yes | No default. | Current device fingerprint for the merchant customer. Newton compares it with the stored device fingerprint or SSID-derived fingerprint. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate device fingerprint accepted by device validation when supplied. |
| `udfParameters` | string | No | No default. Echoed in the response when supplied. | JSON-object string for merchant-defined metadata. Must parse as a JSON object and must not contain characters rejected by the validator (`/`, `$`, `-`, `*`, `!`, `%`, `~`, backtick). |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by encrypted/signed request verification. Required for signed/encrypted request modes because middleware validates it. |

No request field is defaulted by the update route. Optional fields are omitted from downstream payloads and responses when not supplied, except `udfParameters`, which is echoed if present. There are no nested request objects for this API.

## Validation and Processing Behavior

### Request Format Validation

Newton rejects the request before business processing when:

- `upiNumber` fails UPI-number validation.
- `merchantCustomerId` is empty, longer than 256 characters, or fails its allowed-character rule.
- `upiRequestId` is empty, longer than 35 characters, or non-alphanumeric.
- `vpa` or `existingVpa` fails VPA format validation.
- `payeeUpiNumber` is supplied and fails UPI-number validation.
- `deviceFingerPrint` is empty.
- `udfParameters` is not a JSON-object string or contains disallowed characters.
- `action` cannot be parsed as the shared action enum.
- `iat` is missing or stale for encrypted/signed request types.

### UPI Number Validation

`upiNumber` and optional `payeeUpiNumber` must be numeric.

For a 10-digit UPI Number:

- Any 10 numeric digits pass the format validator.
- The update route does not separately compare the 10 digits to the customer's mobile number; the existing mapper lookup must still match the merchant customer and linked VPA.

For an 8- or 9-digit numeric ID:

- Length must be between 8 and 10 digits.
- It must not start with zero.
- The last three digits must not all be the same.

Numbers shorter than 8 digits, longer than 10 digits, non-numeric values, numeric IDs that start with zero, and numeric IDs with the same last three digits are rejected.

### Action Semantics

| Action | Required VPA fields | Downstream `setStatus` | Successful client-facing `payload.status` | Notes |
| --- | --- | --- | --- | --- |
| `DISABLE` | `vpa` is the current linked VPA. | `INACTIVE` | `DISABLED` | Current mapper must not already be `INACTIVE` or `DEREGISTER`. |
| `REACTIVATE` | `vpa` is the current linked VPA. | `ACTIVE` | `ACTIVE` | Current mapper must not already be `ACTIVE`, pending, ported out, or expired. |
| `DELETE` | `vpa` is the current linked VPA. | `DEREGISTER` | `DELETED` | Current mapper must not already be `DEREGISTER`. NPCI can return a cooling-period expiry. |
| `CHANGE_VPA` | `existingVpa` is the current linked VPA; `vpa` is the new target VPA. | `ACTIVE` | `ACTIVE` | Current mapper must not be inactive, deleted, pending, ported out, or expired, and the new VPA must belong to the same customer/profile. |

### Mapper, Customer, Device, and VPA Checks

Newton checks:

- Merchant id and channel id identify a valid merchant.
- The API name `modifyMapperS2S` is enabled for the merchant or sub-merchant.
- If IP allowlisting is configured, the first `x-forwarded-for` IP is present and allowlisted.
- `merchantCustomerId` resolves to a merchant customer and customer under the merchant.
- A registered device exists for the merchant customer.
- `deviceFingerPrint` or `fallbackDeviceFingerPrint` matches the stored device fingerprint.
- For `DELETE`, `DISABLE`, and `REACTIVATE`, `vpa` is the linked VPA used to find the existing mapper.
- For `CHANGE_VPA`, `existingVpa` is present and is the linked VPA used to find the existing mapper.
- For `CHANGE_VPA`, the new `vpa` belongs to the same customer and merchant customer.
- The UPI Number mapper exists for the merchant customer, linked VPA, and UPI Number.
- The mapper is not expired, `PORTED_OUT`, `PENDING`, `PENDING_CHANGE_VPA`, or `PENDING_DEREGISTER`.
- The requested action is compatible with the current mapper status.

The update route does not require a prior UPI Number availability/check cache entry. That cache is used by create/port flows, not by this modify-mapper route.

### Local State and Downstream NPCI Behavior

Before calling NPCI, Newton updates the mapper locally:

- `CHANGE_VPA` sets local status to `PENDING_CHANGE_VPA`.
- Other supported actions set local status to `PENDING`.
- The mapper store records the last action, `upiRequestId`, gateway timestamp, and pending result.

Newton then sends an NPCI `ReqRegMapper` request with transaction operation `MODIFY`.

Downstream status mapping:

- `DELETE` sends `setStatus = "DEREGISTER"`.
- `DISABLE` sends `setStatus = "INACTIVE"`.
- `REACTIVATE` sends `setStatus = "ACTIVE"`.
- `CHANGE_VPA` sends `setStatus = "ACTIVE"` and uses the new VPA as the mapper address.

On downstream success, Newton updates the mapper to the successful status and returns a top-level `SUCCESS` response. On downstream business failure with an error code, Newton reverts the mapper to its previous status and returns a top-level `SUCCESS` response with `payload.gatewayResponseStatus = "FAILURE"`. On timeout or malformed downstream response, Newton can return a top-level failure such as `SERVICE_UNAVAILABLE_NPCI_*`, `BAD_RESPONSE_FROM_NPCI`, or `INTERNAL_SERVER_ERROR`; clients should reconcile the mapper state before retrying because the local mapper may have been marked pending before the downstream failure was detected.

## Response

Route response type: `RespHeaders (API.EncResponse TfS2S.ModifyMapperResponse)`

Business response type: `TfS2S.ModifyMapperResponse`

### Success Response: Disable

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
    "gatewayTimestamp": "2026-07-02T10:30:01+05:30",
    "gatewayTransactionId": "UPINUMUPD12345",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Upi number was updated successfully",
    "upiNumber": "9876543210",
    "vpa": "customer@bank",
    "status": "DISABLED"
  }
}
```

### Success Response: Change VPA

The response `payload.vpa` is the VPA that remains linked after the update. For `CHANGE_VPA`, that is the new target VPA from request `vpa`.

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
    "gatewayTimestamp": "2026-07-02T10:33:01+05:30",
    "gatewayTransactionId": "UPINUMUPD12348",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Upi number was updated successfully",
    "upiNumber": "9876543210",
    "vpa": "customernew@bank",
    "status": "ACTIVE"
  },
  "udfParameters": "{\"journey\":\"upi-number-change-vpa\"}"
}
```

### Success Response: Delete With Cooling Period

`coolingPeriodEndTime` is included only when the downstream response has an expiry timestamp and parsed `x-api-version` is greater than `0`.

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
    "gatewayTimestamp": "2026-07-02T10:32:01+05:30",
    "gatewayTransactionId": "UPINUMUPD12347",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Upi number was updated successfully",
    "upiNumber": "9876543210",
    "vpa": "customer@bank",
    "status": "DELETED",
    "coolingPeriodEndTime": "2026-07-09T10:32:01+05:30"
  }
}
```

### Processed Response: Downstream Business Failure

Newton can return top-level `SUCCESS` while the downstream modify-mapper action failed. Treat `payload.gatewayResponseStatus = "FAILURE"` as the business failure. The downstream code and message vary by NPCI response and Newton's error-code mapping; this is a representative decrypted body.

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
    "gatewayTransactionId": "UPINUMUPD12349",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "MM18",
    "gatewayResponseMessage": "Update Upi number failed",
    "upiNumber": "9876543210",
    "vpa": "customer@bank",
    "status": "ACTIVE"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level Newton API processing status. For processed update responses, success is `SUCCESS`. |
| `responseCode` | string | Top-level Newton response code. For processed update responses, success is `SUCCESS`. |
| `responseMessage` | string | Top-level Newton response message. |
| `payload` | object | UPI-number update result. Present for processed responses. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id. |
| `merchantChannelId` | string | Merchant channel id. |
| `merchantCustomerId` | string | Merchant customer id from Newton's merchant-customer record. |
| `customerMobileNumber` | string | Customer mobile number stored by Newton, usually with country code. |
| `gatewayTimestamp` | string | NPCI response timestamp when available. Omitted if downstream did not return it. |
| `gatewayTransactionId` | string | Echo of request `upiRequestId`; used as the downstream transaction id. |
| `gatewayResponseStatus` | string | `SUCCESS` when `gatewayResponseCode` is `00`; otherwise `FAILURE`. |
| `gatewayResponseCode` | string | `00` for gateway success. Any other value indicates gateway/business failure. Missing gateway code in the core response is treated as an internal error. |
| `gatewayResponseMessage` | string | Downstream/user-facing message when available; otherwise `Update Upi number failed`. Successful updates return `Upi number was updated successfully`. |
| `upiNumber` | string | UPI Number returned by downstream or echoed by failure handling. |
| `vpa` | string | VPA linked after the update. For `CHANGE_VPA`, this is the new VPA. For other actions, this is the request `vpa`. |
| `status` | string | Normalized mapper status. Downstream `ACTIVE` maps to `ACTIVE`, `INACTIVE` maps to `DISABLED`, and `DEREGISTER` maps to `DELETED`. If a downstream failure returns an unmapped status, Newton can return an empty string. |
| `coolingPeriodEndTime` | string | Downstream expiry/cooling timestamp for delete-style responses when available and `x-api-version > 0`. Omitted otherwise. |

## Failure Scenarios

Failure responses use the same response transport strategy as the rest of the S2S integration. If the response is encrypted/signed, decrypt/verify it before reading the body. Examples below show decrypted response bodies.

Clients should distinguish:

- Transport/auth/request/business-rule failures: top-level `status = "FAILURE"` response body or non-2xx HTTP status depending on the layer.
- Completed update with negative downstream result: top-level `status = "SUCCESS"` and `payload.gatewayResponseStatus = "FAILURE"`.

### Request Validation Failure

Invalid request fields are rejected before business processing. Validation messages come from the field validators and may contain multiple comma-separated items.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"Upi Number should be between 8 to 10 digits\""
}
```

Other validation examples:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"upiRequestId length is not between 1 and 35\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Validation messages can also include:

- `merchantCustomerId length is not in between 1 and 256`
- `merchantCustomerId is not alphanumeric`
- `upiRequestId regex match failed`
- `customerVpa length is not between 3 and 255`
- `deviceFingerPrint field is empty`
- `Upi Number is not a valid number input`
- `Upi Number contains same last 3 digits`
- `Upi Number starts with zero`

### JSON Parse or Unknown Enum Failure

If a required field is missing from the decrypted business payload, has the wrong JSON type, or `action` cannot be parsed as the shared enum, the request can fail before product validation. The exact parser text depends on the failing field.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.action: parsing Newton.Types.Intermediate.Action failed"
}
```

### Authentication, Signature, Encryption, and Timestamp Failures

Missing merchant headers, invalid signature, failed JWE decryption, failed JWS verification, missing/invalid `iat`, invalid `x-timestamp`, and IP whitelist failures are rejected before product logic.

Typical authorization failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

JWS/JWE signature-source failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Invalid timestamp examples:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid timestamp format"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Timestamp difference with actual current time"
}
```

Invalid encrypted payload parsing can return an invalid-data response. The parser path in `responseMessage` varies with the malformed field.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload"
}
```

### Merchant API Access Disabled or Not Allowed

Returned when merchant configuration blocks this API or an allow-list is configured and `modifyMapperS2S` is not allowed.

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

### Unsupported Action

`BLOCK` and `UNBLOCK` can parse as shared enum values but are not supported by this endpoint's product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Action is invalid"
}
```

### Missing `existingVpa` for `CHANGE_VPA`

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Existing vpa is mandatory for CHANGE_VPA"
}
```

### New VPA Does Not Belong to Customer

Returned for `CHANGE_VPA` when request `vpa` is not an active VPA for the resolved customer/profile.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "New VPA does not belong to customer"
}
```

### UPI Number Mapper Not Found or Details Mismatch

Returned when Newton cannot find the mapper for the supplied `merchantCustomerId`, linked VPA, and `upiNumber`, or when mapper details are otherwise invalid.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "UPI number details not valid"
}
```

### Device Not Bound or Fingerprint Mismatch

Returned when the merchant customer has no active device binding:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Returned when neither `deviceFingerPrint` nor `fallbackDeviceFingerPrint` matches the registered device:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

If the stored device id points to missing internal device data, the lookup path can return an internal server error instead:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Current Linked VPA Lookup Failure

For `DELETE`, `DISABLE`, and `REACTIVATE`, Newton uses request `vpa` as the current linked VPA. For `CHANGE_VPA`, it uses `existingVpa`. If the linked VPA cannot be found for the customer/profile, the current implementation can surface an internal server error from the lookup helper.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Mapper Pending Sync

Returned when the current mapper is already in `PENDING` or `PENDING_CHANGE_VPA`.

```json
{
  "status": "FAILURE",
  "responseCode": "JP44",
  "responseMessage": "UPI number status is pending to be synced"
}
```

### Mapper Pending Deregister

Returned when the current mapper is in `PENDING_DEREGISTER`.

```json
{
  "status": "FAILURE",
  "responseCode": "JP45",
  "responseMessage": "Action cannot be performed as UPI number status is PENDING_DEREGISTER"
}
```

### Mapper Expired or Deleted

If the mapper expiry has passed, the route treats the mapper as deleted for action validation.

```json
{
  "status": "FAILURE",
  "responseCode": "JP45",
  "responseMessage": "Action cannot be performed as UPI number status is DELETED"
}
```

The same response is returned when `DISABLE` or `CHANGE_VPA` is attempted on a `DEREGISTER` mapper.

### Mapper Ported Out

```json
{
  "status": "FAILURE",
  "responseCode": "JP45",
  "responseMessage": "Action cannot be performed as UPI number status is PORTED_OUT"
}
```

### Redundant Reactivate

Returned when `REACTIVATE` is requested for an already active mapper.

```json
{
  "status": "FAILURE",
  "responseCode": "JP46",
  "responseMessage": "Status is already ACTIVE"
}
```

### Redundant Delete

Returned when `DELETE` is requested for an already deregistered mapper.

```json
{
  "status": "FAILURE",
  "responseCode": "JP46",
  "responseMessage": "Status is already DELETED"
}
```

### Disable or Change VPA on Disabled Mapper

Returned when `DISABLE` or `CHANGE_VPA` is requested for an inactive mapper.

```json
{
  "status": "FAILURE",
  "responseCode": "JP45",
  "responseMessage": "Action cannot be performed as UPI number status is DISABLED"
}
```

### Downstream Mapper/NPCI Business Failure

When downstream returns an error code, Newton usually returns top-level success with nested gateway failure. The local mapper is reverted to its previous status.

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
    "gatewayTransactionId": "UPINUMUPD12350",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "MM18",
    "gatewayResponseMessage": "Update Upi number failed",
    "upiNumber": "9876543210",
    "vpa": "customer@bank",
    "status": "ACTIVE"
  }
}
```

The `gatewayResponseCode` and `gatewayResponseMessage` values depend on the downstream response and Newton's error-code mapping.

### NPCI Timeout or Service Unavailable

Returned when the NPCI modify-mapper call times out and Newton treats it as a service-unavailable route failure. If NPCI supplies a timeout code, the last segment of `responseCode` and the parenthesized value in `responseMessage` contain that code.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U90",
  "responseMessage": "NPCI service is not reachable at the moment (U90)"
}
```

When no timeout code is available:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

### Bad NPCI Response

Returned when downstream returns an error shape without an error code.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

### Internal Server Error

Returned for unexpected server-side failures, missing required internal state, missing downstream fields needed to build the response, or unhandled downstream decode failures.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Use a unique `upiRequestId` for each update attempt and store it with the requested action.
- Do not treat top-level `status = "SUCCESS"` alone as a successful update. Always inspect `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.status`.
- Treat top-level `SUCCESS` plus `payload.gatewayResponseStatus = "SUCCESS"` and the expected `payload.status` as the successful business result.
- Treat top-level `SUCCESS` plus `payload.gatewayResponseStatus = "FAILURE"` as a completed but failed downstream action. Show or store the nested gateway code/message and decide retryability from that code.
- Do not retry validation, authentication, API-access, IP allowlist, or device-fingerprint failures without correcting the request, headers, credential setup, or merchant/customer/device setup.
- For `CHANGE_VPA`, verify that `existingVpa` is the current linked VPA and request `vpa` is the intended new active VPA before retrying.
- If the API returns `JP44`, wait for mapper synchronization or use the fetch/status flow before trying another update. Immediate repeats are likely to fail while the mapper remains pending.
- If the API returns `JP45` or `JP46`, do not retry the same action until the customer chooses a valid action for the current mapper status.
- If the API returns `SERVICE_UNAVAILABLE_NPCI_*`, reconcile before retrying. The mapper may have been marked `PENDING` or `PENDING_CHANGE_VPA` locally before the timeout was raised.
- For delete responses with `coolingPeriodEndTime`, avoid creating or reassigning the same UPI Number until the cooling-period and mapper state are confirmed.
- Store `gatewayTransactionId`, `gatewayResponseCode`, `gatewayResponseStatus`, `gatewayTimestamp`, `upiNumber`, `vpa`, `status`, and `coolingPeriodEndTime` for support and reconciliation.

## Source References

- API route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:680)
- Route handler and authentication wrapper: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3956)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3244)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:756)
- Core request and response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1397)
- Core product route: [src/Newton/Product/Merchant/UpiNumber/ModifyUpiNumber.hs](../../src/Newton/Product/Merchant/UpiNumber/ModifyUpiNumber.hs:36)
- Modify-mapper DB lookups and business validation: [src/Newton/Product/Merchant/UpiNumber/Helper.hs](../../src/Newton/Product/Merchant/UpiNumber/Helper.hs:48)
- Product response transformer: [src/Newton/Product/Merchant/UpiNumber/Transformer.hs](../../src/Newton/Product/Merchant/UpiNumber/Transformer.hs:69)
- NPCI modify-mapper request and response handling: [src/Newton/Product/UpiNumberV2.hs](../../src/Newton/Product/UpiNumberV2.hs:725)
- Action enum: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:772)
- UPI Number mapper status enum: [src/Newton/Types/Storage/UpiNumberMapper.hs](../../src/Newton/Types/Storage/UpiNumberMapper.hs:84)
- Request body extraction/envelope verification: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Merchant signature/API/IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Payload verification/JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Device fingerprint validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Request validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:137)
- UPI Number error bodies: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:872)
