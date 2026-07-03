# Manage Secondary Device API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/secondaryDevice/manage`

## Overview

Manage Secondary Device is a merchant server-to-server API for onboarding and maintaining a secondary or IoT-style UPI device for a merchant customer.

Use this API when a customer needs a non-primary device, such as a wearable, TV, car, or other supported secondary device, to participate in UPI journeys. The API covers the device lifecycle:

- Trigger an OTP to the customer's primary mobile number.
- Register the secondary device after OTP verification.
- Check whether a secondary-device VPA is available.
- Add or delete a VPA for the secondary device.
- Deregister the secondary device.

Payloads use the standard Newton S2S encrypted or signed request and response envelope shared during onboarding. Examples below show decrypted business payloads only.

Important terms:

- `deviceId`: Raw device identifier sent during registration. Newton encrypts/hashes it and does not return it.
- `deviceFingerPrint`: SHA-256 fingerprint derived from `deviceId` and returned after registration. Use this value in later `ADD_VPA` and `DEREGISTER` calls.
- `secondaryDeviceVpa`: VPA assigned to, checked for, added to, or deleted for the secondary device.
- `merchantCustomerId`: Merchant's stable customer identifier under the authenticated merchant/channel.

## Business Use Case

Manage Secondary Device helps merchants:

- Prove that the user controlling the primary mobile number approved the secondary-device onboarding.
- Store device metadata required for IoT or secondary-device UPI use cases.
- Bind a VPA to the secondary device without linking a bank account in this API path.
- Keep the customer's secondary-device VPA state in sync when the VPA is no longer required.
- Deregister the secondary device and clear its linked VPA/customer state when the device is retired or replaced.

Typical lifecycle:

1. Merchant calls `TRIGGER_OTP` with the customer id and primary mobile number.
2. Customer receives the OTP through the configured SMS notification path.
3. Merchant calls `REGISTER` with the OTP, raw `deviceId`, mobile number, package name, device type, and device metadata.
4. Newton returns `payload.deviceFingerPrint`; merchant stores it for subsequent secondary-device actions.
5. Merchant optionally calls `IS_AVAILABLE_VPA` to check a proposed secondary-device VPA.
6. Merchant calls `ADD_VPA` with the returned `deviceFingerPrint` and the chosen `secondaryDeviceVpa`.
7. Merchant later calls `DELETE_VPA` or `DEREGISTER` when the VPA or secondary device should be removed.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/secondaryDevice/manage
```

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Use `application/json`. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-timestamp` | Yes | 13-digit epoch milliseconds. Must be within the accepted request freshness window. |
| `x-merchant-signature` | Conditional | Required for legacy/plain payload signing. JWS/JWE integrations verify the signed payload instead. |
| `x-api-version` | Recommended | Use the version shared during onboarding. |
| `x-request-id` | Recommended | Merchant request correlation id. Newton echoes or generates it in response headers. |
| `x-session-id` | Recommended | Merchant session correlation id. Defaults to `x-request-id` when omitted. |
| `x-forwarded-for` | Conditional | Required when the merchant has IP allow-listing configured. |
| `x-psp-encryption` | Optional | Response protection override when enabled for the merchant, for example `JWS` or `JWS_AND_JWE`. |

Path parameter:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant integration. |

## Authentication and Encryption

Newton accepts the S2S envelope configured for the merchant:

- `JWS_AND_JWE`: request body is encrypted as JWE and contains a signed JWS payload.
- `JWS`: request body is a signed JWS payload.
- Legacy/plain integrations: request body is plain JSON and must be protected by the configured merchant signature headers.

For JWS/JWE requests, include `iat` in the decrypted business payload. Newton validates `iat` and the `x-timestamp` header as 13-digit epoch millisecond timestamps within the accepted freshness window.

Responses use the corresponding configured response protection. Legacy/plain response mode includes the configured response signature behavior; JWS/JWE response mode returns a signed or encrypted body. All examples below are decrypted response bodies.

## Actions

| Action | Use when | Main result |
| --- | --- | --- |
| `TRIGGER_OTP` | Start secondary-device registration by sending an OTP to the customer's primary mobile number. | Creates a merchant customer registration token and attempts to send OTP. |
| `REGISTER` | Complete secondary-device registration after the customer provides OTP. | Creates or reactivates the secondary-device record and returns `deviceFingerPrint`. |
| `IS_AVAILABLE_VPA` | Check whether a proposed secondary-device VPA can be used. | Returns `available` and optional `vpaSuggestions`. |
| `ADD_VPA` | Attach a VPA to an already registered active secondary device. | Adds the VPA through the IoT VPA path and stores the VPA id on the secondary-device record. |
| `DELETE_VPA` | Delete a secondary-device VPA while keeping the registered secondary device. | Deletes the VPA through the VPA management path and returns the deleted VPA. |
| `DEREGISTER` | Retire the secondary device. | Marks the secondary-device record inactive, deletes its linked VPA, and soft-deletes/unbinds the merchant customer record used by this secondary-device flow. |

## Request

Business request type: `ManageSecondaryDeviceS2SRequest`

### Required Minimum by Action

`TRIGGER_OTP`:

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "TRIGGER_OTP",
  "mobileNumber": "919876543210"
}
```

`REGISTER`:

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "REGISTER",
  "mobileNumber": "919876543210",
  "deviceId": "iot-watch-serial-91A7F2",
  "otp": "483921",
  "packageName": "com.merchant.iot",
  "deviceType": "WATCH",
  "os": "WearOS",
  "manufacturer": "Acme",
  "model": "Acme Watch 4",
  "version": "4.2.1",
  "capability": "UPI_PAY",
  "attributes": "eyJibHVldG9vdGgiOnRydWUsIm5mYyI6dHJ1ZX0="
}
```

`IS_AVAILABLE_VPA`:

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "IS_AVAILABLE_VPA",
  "secondaryDeviceVpa": "custwatch10001@merchant"
}
```

`ADD_VPA`:

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "ADD_VPA",
  "deviceFingerPrint": "cb459cdeaafc9ee64063e9b90df4a5b02dba620d1d6817ce5d05a184d8565c62",
  "secondaryDeviceVpa": "custwatch10001@merchant"
}
```

`DELETE_VPA`:

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "DELETE_VPA",
  "secondaryDeviceVpa": "custwatch10001@merchant"
}
```

`DEREGISTER`:

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "DEREGISTER",
  "deviceFingerPrint": "cb459cdeaafc9ee64063e9b90df4a5b02dba620d1d6817ce5d05a184d8565c62"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Max 256 characters. First character must be a letter, number, plus, slash, or equals; subsequent characters may also include dot, underscore, and hyphen. |
| `action` | string enum | Yes | No default. | One of `TRIGGER_OTP`, `REGISTER`, `IS_AVAILABLE_VPA`, `ADD_VPA`, `DELETE_VPA`, `DEREGISTER`. |
| `mobileNumber` | string | Required for `TRIGGER_OTP` and `REGISTER` | Not used when omitted for other actions. | Customer primary mobile number. With the current validator, send a 12-digit numeric value, for example country code plus 10-digit mobile number. |
| `deviceId` | string | Required for `REGISTER` | No default. | Raw secondary-device identifier. Newton encrypts/hashes this value, stores it, and returns a SHA-256 `deviceFingerPrint`. |
| `deviceFingerPrint` | string | Required for `ADD_VPA` and `DEREGISTER` | No default. | Fingerprint returned by a successful `REGISTER` response. This is not the raw `deviceId`. |
| `secondaryDeviceVpa` | string | Required for `IS_AVAILABLE_VPA`, `ADD_VPA`, and `DELETE_VPA` | No default. | Secondary-device VPA. Must be 3 to 255 characters, match `local@handle` format, and satisfy merchant/VPA-handle rules. |
| `otp` | string | Required for `REGISTER` | No default. | OTP received after `TRIGGER_OTP`. Newton looks up a registration token by `OTP: <otp>` and `merchantCustomerId`. |
| `packageName` | string | Required for `REGISTER` | No default. | Merchant app/package name associated with the secondary-device registration. |
| `deviceType` | string enum | Required for `REGISTER` | No default. | Secondary-device category. Allowed values: `GLAS`, `TV`, `WATCH`, `CAR`, `RFGR`, `RNG`, `VNDM`, `SOFT`, `OTHER`. |
| `os` | string | Required for `REGISTER` | No default. | Secondary-device OS. The registration handler requires this field. |
| `manufacturer` | string | Required for `REGISTER` | No default. | Device manufacturer. The registration handler requires this field. |
| `model` | string | Required for `REGISTER` | No default. | Device model. The registration handler requires this field. |
| `version` | string | Required for `REGISTER` | No default. | OS, firmware, or device software version. The registration handler requires this field. |
| `capability` | string | Required for `REGISTER` | No default. | Capability string for the secondary device. Must be 1 to 99 characters. |
| `attributes` | string | Required for `REGISTER` | No default. | Opaque device attributes string. Newton stores it as text. Merchant integrations commonly send base64-encoded JSON device details. |
| `iat` | string | Conditional | No default. | Issued-at timestamp required for JWS/JWE request freshness validation. Use 13-digit epoch milliseconds. |
| `udfParameters` | string | No | Omitted from response when omitted. | JSON-object string for merchant-defined metadata. Echoed in the response when supplied and valid. |

### Nested and Encoded Request Data

This API does not accept nested JSON objects in the decrypted business payload. Two fields carry structured data as strings:

| Field | Expected content | Notes |
| --- | --- | --- |
| `attributes` | Merchant-defined device detail string, commonly base64-encoded JSON. | Required for `REGISTER`. Newton validates only that it is non-empty, then stores it on the secondary-device record. |
| `udfParameters` | JSON object encoded as a string, for example `"{\"flow\":\"watch-registration\"}"`. | Must parse as a JSON object string and must pass the configured restricted-character regex. Echoed back in success responses. |

### Defaults and Omitted Field Behavior

No request field has a business default in this API. Optional fields are ignored unless the selected action uses them.

Action-specific omissions behave as follows:

- `TRIGGER_OTP` without `mobileNumber` fails with `BAD_REQUEST`.
- `REGISTER` without `mobileNumber`, `attributes`, `deviceId`, `packageName`, `otp`, `capability`, or `deviceType` fails with `BAD_REQUEST`.
- `REGISTER` also requires `os`, `manufacturer`, `model`, and `version` in the product handler. Treat them as required even though the action validator does not produce a friendly action-level error for those fields.
- `IS_AVAILABLE_VPA` without `secondaryDeviceVpa` fails with `BAD_REQUEST`.
- `ADD_VPA` without `secondaryDeviceVpa` or `deviceFingerPrint` fails with `BAD_REQUEST`.
- `DELETE_VPA` without `secondaryDeviceVpa` fails with `BAD_REQUEST`.
- `DEREGISTER` without `deviceFingerPrint` fails with `BAD_REQUEST`.
- `udfParameters` is echoed only when supplied.

## Request Examples

### Trigger OTP

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "TRIGGER_OTP",
  "mobileNumber": "919876543210",
  "iat": "1720617600000",
  "udfParameters": "{\"journey\":\"watch-registration\",\"cartId\":\"CART10001\"}"
}
```

### Register Secondary Device

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "REGISTER",
  "mobileNumber": "919876543210",
  "deviceId": "iot-watch-serial-91A7F2",
  "otp": "483921",
  "packageName": "com.merchant.iot",
  "deviceType": "WATCH",
  "os": "WearOS",
  "manufacturer": "Acme",
  "model": "Acme Watch 4",
  "version": "4.2.1",
  "capability": "UPI_PAY",
  "attributes": "eyJibHVldG9vdGgiOnRydWUsIm5mYyI6dHJ1ZX0=",
  "iat": "1720617660000",
  "udfParameters": "{\"journey\":\"watch-registration\",\"cartId\":\"CART10001\"}"
}
```

### Check VPA Availability

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "IS_AVAILABLE_VPA",
  "secondaryDeviceVpa": "custwatch10001@merchant",
  "iat": "1720617720000"
}
```

### Add VPA

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "ADD_VPA",
  "deviceFingerPrint": "cb459cdeaafc9ee64063e9b90df4a5b02dba620d1d6817ce5d05a184d8565c62",
  "secondaryDeviceVpa": "custwatch10001@merchant",
  "iat": "1720617780000"
}
```

### Delete VPA

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "DELETE_VPA",
  "secondaryDeviceVpa": "custwatch10001@merchant",
  "iat": "1720617840000"
}
```

### Deregister Secondary Device

```json
{
  "merchantCustomerId": "CUST-IOT-10001",
  "action": "DEREGISTER",
  "deviceFingerPrint": "cb459cdeaafc9ee64063e9b90df4a5b02dba620d1d6817ce5d05a184d8565c62",
  "iat": "1720617900000"
}
```

## Response

Business response type: `ManageSecondaryDeviceS2SResponse`

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for completed successful operations. `TRIGGER_OTP_FAILURE` responses use `status: "FAILURE"` even though they include this API's normal payload shape. |
| `responseCode` | string | Machine-readable response code. Non-OTP success uses `SUCCESS`. OTP trigger uses `TRIGGER_OTP_SUCCESS` or `TRIGGER_OTP_FAILURE`. |
| `responseMessage` | string | Human-readable response message. |
| `payload` | object | Secondary-device operation result. Present for this API's normal success/OTP result responses. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### Payload Fields

| Field | Type | Present when | Description |
| --- | --- | --- | --- |
| `merchantId` | string | All normal responses | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | All normal responses | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | All normal responses | Merchant customer id from the request. |
| `customerMobileNumber` | string | All normal responses | Customer mobile number used or loaded for the operation. |
| `deviceFingerPrint` | string | `REGISTER`, `DEREGISTER` | SHA-256 fingerprint of the registered secondary device. Store this after `REGISTER`. |
| `available` | boolean | `IS_AVAILABLE_VPA` | Whether the requested VPA is available. `false` is a valid business result under top-level `SUCCESS`. |
| `vpaSuggestions` | array of strings | `IS_AVAILABLE_VPA`, when suggestions are produced | Suggested VPA prefixes/handles. Omitted when Newton has no suggestions or the availability path omits suggestions. |
| `vpa` | string | `IS_AVAILABLE_VPA`, `ADD_VPA`, `DELETE_VPA` | VPA checked, added, or deleted. |

Fields whose value is `null` internally are omitted from JSON responses.

## Response Examples

### OTP Triggered

```json
{
  "status": "SUCCESS",
  "responseCode": "TRIGGER_OTP_SUCCESS",
  "responseMessage": "Trigger OTP Success",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "919876543210"
  },
  "udfParameters": "{\"journey\":\"watch-registration\",\"cartId\":\"CART10001\"}"
}
```

If OTP could not be sent but the API completed its OTP attempt, Newton can return:

```json
{
  "status": "FAILURE",
  "responseCode": "TRIGGER_OTP_FAILURE",
  "responseMessage": "Trigger OTP Failure",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "919876543210"
  }
}
```

Do not proceed to `REGISTER` unless the OTP trigger response is `TRIGGER_OTP_SUCCESS` and the customer has entered the OTP received on the primary mobile.

### Device Registered

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "919876543210",
    "deviceFingerPrint": "cb459cdeaafc9ee64063e9b90df4a5b02dba620d1d6817ce5d05a184d8565c62"
  },
  "udfParameters": "{\"journey\":\"watch-registration\",\"cartId\":\"CART10001\"}"
}
```

### VPA Available

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "9876543210",
    "available": true,
    "vpa": "custwatch10001@merchant"
  }
}
```

### VPA Not Available With Suggestions

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "9876543210",
    "available": false,
    "vpaSuggestions": [
      "custwatch10001-1@merchant",
      "custwatch10001-2@merchant"
    ],
    "vpa": "custwatch10001@merchant"
  }
}
```

### VPA Added

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "9876543210",
    "vpa": "custwatch10001@merchant"
  }
}
```

### VPA Deleted

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "9876543210",
    "vpa": "custwatch10001@merchant"
  }
}
```

### Device Deregistered

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST-IOT-10001",
    "customerMobileNumber": "9876543210",
    "deviceFingerPrint": "cb459cdeaafc9ee64063e9b90df4a5b02dba620d1d6817ce5d05a184d8565c62"
  }
}
```

## Error Handling

Failure responses use the same S2S response protection as success responses. The examples below show decrypted response bodies. When `payload` is empty, it is omitted.

Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, or `500`; clients should read `status`, `responseCode`, and `responseMessage` from the decrypted body.

### Failure Scenarios

| Scenario | Example decrypted response body | Client handling |
| --- | --- | --- |
| Request field validation fails, such as invalid `merchantCustomerId`, empty `deviceId`, invalid `secondaryDeviceVpa`, invalid mobile number, invalid `capability`, or invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"deviceId field is empty\""}` | Fix the request. Do not retry unchanged. |
| `action` or `deviceType` cannot be parsed as an enum | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $: parsing ManageSecondaryDeviceAction failed, expected one of REGISTER,DEREGISTER,IS_AVAILABLE_VPA,ADD_VPA,DELETE_VPA,TRIGGER_OTP"}` | Send only documented enum values. |
| `TRIGGER_OTP` is missing `mobileNumber` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mobile Number not found for trigger Otp"}` | Send the customer's primary mobile number. |
| `REGISTER` is missing an action-required field such as `deviceId`, `otp`, `packageName`, `attributes`, `capability`, or `deviceType` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"deviceId not found for Registration"}` | Send the complete registration payload. |
| `REGISTER` is missing handler-required metadata such as `os`, `manufacturer`, `model`, or `version` | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Treat these fields as required and resend with full device metadata. |
| `IS_AVAILABLE_VPA` is missing `secondaryDeviceVpa` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"vpa not found for checking vpa Availability"}` | Send the VPA to check. |
| `ADD_VPA` is missing `secondaryDeviceVpa` or `deviceFingerPrint` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"deviceFingerPrint not found for adding VPA"}` | Use the fingerprint returned by `REGISTER` and send the VPA. |
| `DELETE_VPA` is missing `secondaryDeviceVpa` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"vpa not found for delete vpa"}` | Send the VPA to delete. |
| `DEREGISTER` is missing `deviceFingerPrint` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"deviceFingerPrint not found for deregister device"}` | Send the fingerprint returned by `REGISTER`. |
| Missing or stale `iat` for signed/encrypted requests, or stale `x-timestamp` | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` | Regenerate the timestamp, signature/envelope, and request. |
| Timestamp is not a 13-digit epoch millisecond value | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` | Fix timestamp generation. |
| JWS verification, JWE decryption, missing key id/private key, malformed protected payload, missing merchant headers, or legacy signature verification fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Check keys, `kid`, encryption mode, body canonicalization, merchant headers, and onboarding configuration. |
| Merchant configuration blocks or does not allow `manageSecondaryDeviceS2S` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Enable the API for the merchant/channel before retrying. |
| Merchant IP allow-list rejects the request | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Call from an allow-listed IP or update merchant configuration. |
| `REGISTER` OTP does not match an existing registration token for the merchant customer | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No record found for given otp and merchant customer"}` | Ask the customer for the latest OTP or trigger a fresh OTP. |
| `DEREGISTER` finds no customer on the merchant customer record | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No customer found for merchantCustomer"}` | Reconcile customer/device state before retrying. |
| `ADD_VPA` or `DEREGISTER` cannot find an active secondary device for the supplied fingerprint | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Device not found for the given deviceFingerPrint and merchantCustomer"}` | Use the `deviceFingerPrint` returned by successful registration or register the device again. |
| `ADD_VPA` attempts to link a different VPA while the secondary device is already linked to another active VPA | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Secondary Device Already linked to other active Vpa"}` | Delete/deregister the existing linked VPA/device before adding a different VPA. |
| `ADD_VPA` VPA is unavailable or reserved | `{"status":"FAILURE","responseCode":"VPA_NOT_AVAILABLE","responseMessage":"CustomerVpa not available"}` | Ask the user to choose another VPA or use `IS_AVAILABLE_VPA` suggestions. |
| `ADD_VPA` normalized VPA conflicts with an existing VPA | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Normalized VPA already exists"}` | Choose a different VPA. |
| `ADD_VPA` repeats a VPA/account mapping that the underlying VPA path treats as a duplicate | `{"status":"FAILURE","responseCode":"DUPLICATE_VPA","responseMessage":"customerVpa passed is already added"}` | Treat as already linked only if it matches the same customer/device context; otherwise reconcile state. |
| VPA format fails merchant handle or mobile-number VPA rules | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"vpa is not valid"}` | Use a valid VPA handle/prefix for the merchant and customer. |
| `DELETE_VPA` VPA has active delegate links | `{"status":"FAILURE","responseCode":"JPADL","responseMessage":"You have active DelegateLink(s). Please try again after all the links are delinked"}` | Delink delegate relationships before deleting the VPA. |
| `DELETE_VPA` VPA has active mandates | `{"status":"FAILURE","responseCode":"JPDL","responseMessage":"You have active mandate(s). Please try again after all the mandates are executed or revoked"}` | Revoke or complete mandates before deleting the VPA. |
| `DELETE_VPA` cannot find the VPA | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Vpa not found"}` | Refresh customer VPA state before retrying. |
| OTP SMS notification path completes but SMS is not sent successfully | `{"status":"FAILURE","responseCode":"TRIGGER_OTP_FAILURE","responseMessage":"Trigger OTP Failure","payload":{"merchantId":"MERCHANT123","merchantChannelId":"CHANNEL123","merchantCustomerId":"CUST-IOT-10001","customerMobileNumber":"919876543210"}}` | Do not call `REGISTER`. Retry OTP trigger only after applying resend limits and user messaging. |
| Shared downstream service is temporarily unavailable | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_U09","responseMessage":"NPCI service is not reachable at the moment (U09)"}` | Retry with bounded exponential backoff if the customer is still in the journey. |
| Database, cache, key, encryption/decryption, missing stored `VpaId`, or other unexpected server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry transiently with backoff; escalate with `x-request-id`, `merchantCustomerId`, `action`, and any VPA/fingerprint if persistent. |

## Retry, Idempotency, and Client Handling

This API does not have a `merchantRequestId` idempotency key. Use client-side correlation based on `merchantCustomerId`, `action`, `deviceFingerPrint`, `secondaryDeviceVpa`, and your own request/session ids.

Recommended handling:

- Always decide success or failure from the decrypted response body, not only the HTTP status.
- `TRIGGER_OTP` creates a new OTP registration token and attempts SMS delivery. If repeated, ask the customer to use the latest OTP.
- Do not call `REGISTER` after `TRIGGER_OTP_FAILURE`.
- Store `payload.deviceFingerPrint` from `REGISTER`; later device actions require this value rather than raw `deviceId`.
- `IS_AVAILABLE_VPA` is read-only and safe to retry.
- `ADD_VPA` should be retried only with the same `deviceFingerPrint` and `secondaryDeviceVpa` after a network failure or transient server error. Do not retry with a different VPA while the first result is unknown.
- `DELETE_VPA` can be retried after a lost response only for the same `secondaryDeviceVpa`, but business failures such as active mandates or active delegate links must be resolved first.
- `DEREGISTER` is not safely repeatable after success because it marks the secondary device inactive and soft-deletes/unbinds the merchant customer state used by this flow. If the first response is lost, reconcile state before issuing another deregistration.
- Retry network failures, client timeouts with no decrypted body, `SERVICE_UNAVAILABLE...`, and transient `INTERNAL_SERVER_ERROR` with exponential backoff and jitter.
- Do not retry validation errors, authentication failures, `API NOT ENABLED`, VPA availability conflicts, duplicate VPA conflicts, missing OTP token, or device lookup failures without changing the request or merchant/customer/device state.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:797)
- Route handler, merchant signature verification, cache invalidation, and transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:5356)
- Request envelope and response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:69)
- S2S payload verification and JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature, timestamp, API access, and IP allow-list checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:108), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200), [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Transformer route and response builder: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:889), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1699), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1702)
- Request, response, payload, action, and device-type types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:5131), [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:5194), [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:5269), [src/Newton/Product/Merchant/SecondaryDevice/Types.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Types.hs:16), [src/Newton/Product/Merchant/SecondaryDevice/Types.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Types.hs:64), [src/Newton/Types/Storage/SecondaryDevice.hs](../../src/Newton/Types/Storage/SecondaryDevice.hs:67)
- Request validators and validation error wrapping: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:5165), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:180), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:311), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:501), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Secondary-device product routing and action handlers: [src/Newton/Product/Merchant/SecondaryDevice/Management.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Management.hs:46), [src/Newton/Product/Merchant/SecondaryDevice/Management.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Management.hs:57), [src/Newton/Product/Merchant/SecondaryDevice/Management.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Management.hs:97), [src/Newton/Product/Merchant/SecondaryDevice/Management.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Management.hs:148), [src/Newton/Product/Merchant/SecondaryDevice/Management.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Management.hs:197), [src/Newton/Product/Merchant/SecondaryDevice/Management.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Management.hs:218), [src/Newton/Product/Merchant/SecondaryDevice/Management.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Management.hs:282)
- Secondary-device action validation, fingerprint generation, MCRT update, and VPA availability payload conversion: [src/Newton/Product/Merchant/SecondaryDevice/Helper.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Helper.hs:119), [src/Newton/Product/Merchant/SecondaryDevice/Helper.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Helper.hs:131), [src/Newton/Product/Merchant/SecondaryDevice/Helper.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Helper.hs:149), [src/Newton/Product/Merchant/SecondaryDevice/Helper.hs](../../src/Newton/Product/Merchant/SecondaryDevice/Helper.hs:179)
- Secondary-device storage and query helpers: [src/Newton/Types/Storage/SecondaryDevice.hs](../../src/Newton/Types/Storage/SecondaryDevice.hs:28), [src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs](../../src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs:21), [src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs](../../src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs:33), [src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs](../../src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs:46), [src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs](../../src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs:53), [src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs](../../src/Newton/Storage/QueriesMiddleware/SecondaryDevice.hs:58), [src/Newton/Storage/Queries/SecondaryDevice.hs](../../src/Newton/Storage/Queries/SecondaryDevice.hs:49), [src/Newton/Storage/Queries/SecondaryDevice.hs](../../src/Newton/Storage/Queries/SecondaryDevice.hs:101)
- OTP token and SMS trigger helpers: [src/Newton/Utils/BusinessLogic/RegistrationHelper.hs](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1432), [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:216), [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:538), [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:661)
- VPA availability and VPA account management paths used by this API: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1026), [src/Newton/Types/API/ServerToServer/Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:309), [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1700), [src/Newton/Product/Merchant/VpaAccount/ManageVpaAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/ManageVpaAccount.hs:38), [src/Newton/Product/Merchant/VpaAccount/DeleteVpa.hs](../../src/Newton/Product/Merchant/VpaAccount/DeleteVpa.hs:35), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2701)
- Merchant customer create/update/delete helpers used by the flow: [src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs:58), [src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs:196), [src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomer.hs:379)
- Shared response and error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:527), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:536), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:724), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:734), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1094), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1103)
