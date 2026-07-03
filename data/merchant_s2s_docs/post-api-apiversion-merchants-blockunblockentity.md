# Block Unblock Entity API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/blockUnblockEntity`

## Overview

Block Unblock Entity is a server-to-server API used by a merchant backend to block or unblock a customer's UPI entity on Newton.

The merchant can target one mobile number, one device id, one VPA, a list of VPAs, or all VPAs linked to a `merchantCustomerId`. Newton updates the corresponding block state and returns either a single operation result or per-VPA results.

Use this API for risk, fraud, account takeover, customer support, or lifecycle-management workflows where the merchant must stop or restore a customer's ability to use specific UPI identifiers.

## Business Use Case

Block Unblock Entity helps merchants:

- Block a customer's mobile number or device id from participating in merchant UPI journeys.
- Block one customer VPA, a small batch of VPAs, or every VPA linked to a merchant customer.
- Restore a previously blocked mobile number, device id, or VPA.
- Apply directional VPA blocks where supported: inward-pay, debit, or credit blocking.
- Optionally delete UPI numbers mapped to a VPA when that VPA is blocked.
- Trigger customer deregistration side effects for mobile/device blocking when Newton's DB lookup path finds active customer/device records.

Call this API only from a trusted backend system after your own risk/support decision has been made. It is not a customer-facing discovery API.

## Integration Flow

1. Merchant identifies the entity to block or unblock in its own system.
2. Merchant prepares exactly one targeting mode: `mobileNumber`, `deviceId`, `vpa`, `vpaList`, or `merchantCustomerId`.
3. Merchant signs/encrypts the request using the standard Newton S2S envelope.
4. Newton verifies merchant headers, API enablement, signature/envelope, timestamp, and optional IP allow-list configuration.
5. Newton validates the decrypted business payload and applies the requested action.
6. Merchant decrypts the response and records the top-level result. For `vpaList` and `merchantCustomerId` requests, merchant must also inspect every item in `vpaResponseList`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/blockUnblockEntity
```

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the API version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Current request timestamp used by the S2S authentication layer. |
| `x-merchant-signature` | Required for unsigned payload mode where enabled. |
| `Authorization` | Send if required by your onboarding profile. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. For encrypted or signed payloads, include `iat` in the decrypted business payload so Newton can validate the issued-at timestamp.

## Request

### Targeting Rules

Send `action` and exactly one target:

| Targeting mode | Fields to send | Result shape | Notes |
| --- | --- | --- | --- |
| Mobile number | `mobileNumber`, optional `countryCode` | Single top-level result | Newton normalizes Indian numbers to a `91` prefix. Mobile/device blocking writes to blocked-entity records, not VPA records. |
| Device id | `deviceId` | Single top-level result | Blocks or unblocks the device fingerprint/id for the merchant. |
| Single VPA | `vpa` | Single top-level result | Looks up the VPA and updates its VPA status. |
| VPA list | `vpaList` | Top-level success with `vpaResponseList` | Each VPA has its own `responseCode` and `responseMessage`. Maximum list size is configuration-driven; current default is `3`. |
| Merchant customer VPAs | `merchantCustomerId` | Top-level success with `vpaResponseList` | Blocks or unblocks every VPA linked to that merchant customer. Only `BLOCK` and `UNBLOCK` are valid for this mode. |

Do not combine `vpaList` with `merchantCustomerId`. Do not send more than one of `mobileNumber`, `deviceId`, and `vpa` when `vpaList` and `merchantCustomerId` are omitted.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `action` | string | Yes | No default. | Action to apply. Allowed values: `BLOCK`, `UNBLOCK`, `INWARD_PAY_BLOCK`, `INWARD_PAY_UNBLOCK`, `DEBIT_BLOCK`, `DEBIT_UNBLOCK`, `CREDIT_BLOCK`, `CREDIT_UNBLOCK`. |
| `merchantCustomerId` | string | Conditional | Omit unless blocking/unblocking all VPAs for one merchant customer. | Merchant customer identifier. Must be 1 to 256 characters and match Newton's merchant-customer-id format. Cannot be sent with `vpaList`. |
| `countryCode` | string | No | If omitted, send a 12-digit domestic mobile number with `91` prefix. | Optional country code for `mobileNumber`, for example `91` or `+91`. Must contain only digits with an optional leading `+`, max 7 characters. |
| `deviceId` | string | Conditional | No default. | Device fingerprint/id to block or unblock. Must be non-empty when sent. Send only one of `mobileNumber`, `deviceId`, or `vpa`. |
| `iat` | string | Conditional | Required for signed or encrypted payloads. | Issued-at timestamp used by the S2S verification layer. |
| `mobileNumber` | string | Conditional | No default. | Mobile number to block or unblock. If `countryCode` is omitted, send `919876543210`. If `countryCode` is supplied, send the national number such as `9876543210`; Newton stores the normalized value. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in the response. |
| `vpa` | string | Conditional | No default. | Single VPA to block or unblock. Must be non-empty when sent. |
| `vpaList` | array of strings | Conditional | No default. | List of VPAs to block or unblock. The list must be non-empty and within the configured max list size. |
| `deleteUpiNumbersForVpa` | string | No | Omitted behaves as `false`. | `"true"` or `"false"`. When `true`, Newton attempts to delete UPI numbers mapped to a VPA when the VPA block update succeeds. Applies only to VPA block flows. |

### Action Behavior

| Action | Applies to | Behavior |
| --- | --- | --- |
| `BLOCK` | Mobile number, device id, VPA, VPA list, merchant customer VPAs | For mobile/device, creates or activates a blocked-entity record. For VPA, sets status to blocked. Existing blocked VPA returns success; existing blocked mobile/device returns a failure saying it is already blocked. |
| `UNBLOCK` | Mobile number, device id, VPA, VPA list, merchant customer VPAs | For mobile/device, marks the blocked-entity record inactive. For VPA, restores enabled/disabled state based on VPA account availability or stored active flag. |
| `INWARD_PAY_BLOCK` / `INWARD_PAY_UNBLOCK` | VPA or VPA list | Blocks or unblocks inward pay for the VPA. Not valid for mobile/device or `merchantCustomerId` mode. |
| `DEBIT_BLOCK` / `DEBIT_UNBLOCK` | VPA or VPA list | Blocks or unblocks debit-side UPI actions for the VPA. Not valid for mobile/device or `merchantCustomerId` mode. |
| `CREDIT_BLOCK` / `CREDIT_UNBLOCK` | VPA or VPA list | Blocks or unblocks credit-side UPI actions for the VPA. Not valid for mobile/device or `merchantCustomerId` mode. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `deleteUpiNumbersForVpa`: omitted behaves as `false`.
- `countryCode`: omitted treats `mobileNumber` as Indian/domestic, but the validator expects a 12-digit value such as `919876543210`.
- `udfParameters`: omitted from the response when omitted from the request.
- `vpaResponseList`: omitted for mobile number, device id, and single VPA requests.
- `vpaList` max length: configuration-driven; current default is `3`.
- Mobile/device blocking may require the entity to already exist in Newton DB depending on merchant configuration `checkInDBForBlockUnblock`.

## Request Examples

### Block a Mobile Number

```json
{
  "action": "BLOCK",
  "mobileNumber": "9876543210",
  "countryCode": "91",
  "iat": "2026-07-02T10:15:30+05:30",
  "udfParameters": "{\"caseId\":\"RISK-1001\"}"
}
```

### Unblock a Device

```json
{
  "action": "UNBLOCK",
  "deviceId": "device-fingerprint-abc123",
  "iat": "2026-07-02T10:20:30+05:30"
}
```

### Block a Single VPA and Delete Mapped UPI Numbers

```json
{
  "action": "BLOCK",
  "vpa": "customer123@okbank",
  "deleteUpiNumbersForVpa": "true",
  "iat": "2026-07-02T10:25:30+05:30",
  "udfParameters": "{\"ticketId\":\"SUP-771\"}"
}
```

### Block a VPA for Debits Only

```json
{
  "action": "DEBIT_BLOCK",
  "vpa": "customer123@okbank",
  "iat": "2026-07-02T10:30:30+05:30"
}
```

### Block a List of VPAs

```json
{
  "action": "BLOCK",
  "vpaList": [
    "customer123@okbank",
    "customer456@okbank"
  ],
  "deleteUpiNumbersForVpa": "false",
  "iat": "2026-07-02T10:35:30+05:30"
}
```

### Block All VPAs for a Merchant Customer

```json
{
  "action": "BLOCK",
  "merchantCustomerId": "MCUST12345",
  "deleteUpiNumbersForVpa": "true",
  "iat": "2026-07-02T10:40:30+05:30"
}
```

## Response

### Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. `SUCCESS` means Newton accepted and completed the top-level request path. For list-style requests, still inspect `vpaResponseList`. |
| `responseCode` | string | Top-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level response message. Single-target success includes the entity value and action; list-style success is usually `SUCCESS`. |
| `udfParameters` | string | Echo of request `udfParameters`. Omitted when not supplied. |
| `vpaResponseList` | array | Present for `vpaList` and `merchantCustomerId` requests. Omitted for mobile number, device id, and single VPA requests. |

### `vpaResponseList[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | VPA from the request or linked merchant-customer records. |
| `responseCode` | string | Per-VPA result. `SUCCESS` means that VPA was updated or was already in the target block state. Other values such as `INVALID_DATA` or `INTERNAL_SERVER_ERROR` must be handled as item failures. |
| `responseMessage` | string | Per-VPA result message. |

## Success Response Examples

### Single Mobile Number Success

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "919876543210 BLOCKED SUCCESSFULLY",
  "udfParameters": "{\"caseId\":\"RISK-1001\"}"
}
```

### Single VPA Directional Block Success

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "customer123@okbank DEBIT_BLOCKED SUCCESSFULLY"
}
```

### VPA List Success With Per-Item Results

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "vpaResponseList": [
    {
      "vpa": "customer123@okbank",
      "responseCode": "SUCCESS",
      "responseMessage": "customer123@okbank BLOCKED SUCCESSFULLY"
    },
    {
      "vpa": "missing@okbank",
      "responseCode": "INVALID_DATA",
      "responseMessage": "missing@okbank is not available"
    }
  ]
}
```

In the list example, the HTTP/top-level response is successful, but the second VPA failed. Treat `vpaResponseList` as the source of truth for each VPA.

## Failure Handling

Failure responses use the same S2S response transport as success responses where possible. HTTP status may vary by layer. Several business validation failures are returned with HTTP 200 or 422 and a decrypted failure body; authentication/envelope failures are usually HTTP 401; incompatible target combinations can be HTTP 400. Clients should inspect `status`, `responseCode`, and `responseMessage` whenever a decrypted body is available.

### Validation Failure

Example: invalid boolean string in `deleteUpiNumbersForVpa`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "BoolStringValidation \"Parameter is not true or false\""
}
```

Other validation examples include empty `deviceId`, empty `vpa`, empty `vpaList`, invalid `countryCode`, invalid `mobileNumber`, invalid `merchantCustomerId`, invalid action enum, or non-object/non-JSON `udfParameters`.

### Auth, Encryption, or API Enablement Failure

Examples include missing merchant headers, invalid signature, invalid encrypted payload, expired/invalid timestamp, disallowed source IP, or merchant configuration blocking this API.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the merchant is valid but the API is blocked or not in the allow-list, Newton can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### Invalid Target Combination

Example: request includes both `vpaList` and `merchantCustomerId`.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "blockUnblockTransformerRoute : Either vpaList or merchantCustomerId must be present, not both"
}
```

Example: request sends more than one of `mobileNumber`, `deviceId`, and `vpa`.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Only one of mobileNumber, deviceId or vpa must be present"
}
```

### Lookup or Business Failure

Example: single VPA does not exist or does not belong to the merchant's customer context.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "customer123@okbank is not available"
}
```

Example: unblocking a mobile number that is not currently blocked.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "919876543210 is already unblocked"
}
```

Example: unblocking merchant-customer VPAs before they were blocked through the merchant-customer mode.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Vpas are not blocked for MerchantCustomerId MCUST12345"
}
```

Example: directional block conflict.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "customer123@okbank is already INWARD PAY BLOCKED. DEBIT Blocking not allowed."
}
```

### VPA List Partial Failure

For `vpaList` and `merchantCustomerId` modes, Newton catches item-level VPA errors and returns them inside `vpaResponseList`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "vpaResponseList": [
    {
      "vpa": "customer123@okbank",
      "responseCode": "SUCCESS",
      "responseMessage": "customer123@okbank INWARD_PAY_BLOCKED SUCCESSFULLY"
    },
    {
      "vpa": "customer456@okbank",
      "responseCode": "INVALID_DATA",
      "responseMessage": "customer456@okbank is already DEBIT BLOCKED. Inward Pay Blocking not allowed."
    }
  ]
}
```

### Merchant Config or Limit Failure

Example: `vpaList` exceeds the configured limit.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "vpaList has more than 3elements"
}
```

Example: merchant-customer record is inactive.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Merchant Customer is inactive"
}
```

### Downstream or Unexpected Failure

If the storage update returns no updated record for a single-target request, Newton returns an internal server failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

For VPA list requests, unexpected item-level exceptions can appear inside that item:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "vpaResponseList": [
    {
      "vpa": "customer123@okbank",
      "responseCode": "FAILURE",
      "responseMessage": "INTERNAL_SERVER_ERROR"
    }
  ]
}
```

## Retry, Idempotency, and Client Handling

- This API does not take a merchant request id or idempotency key. Treat retries as repeat state-change attempts, not as deduplicated operations.
- For VPA `BLOCK`, `INWARD_PAY_BLOCK`, `DEBIT_BLOCK`, and `CREDIT_BLOCK`, retrying after success usually remains safe because an already-matching VPA block state returns per-item or top-level success.
- For mobile/device `BLOCK`, retrying after success can return `INVALID_DATA` with an "already blocked" message. Treat that as a terminal state conflict and reconcile against your own case history.
- For `UNBLOCK` actions, retrying after success can return "already unblocked" or "not in blocked status". Treat those as terminal unless you have reason to believe the first response was lost before Newton processed it.
- For `vpaList` and `merchantCustomerId`, retry only the failed VPAs where possible. A top-level `SUCCESS` is not enough; inspect each `vpaResponseList[].responseCode`.
- Retry transport failures, HTTP 5xx, and transient encryption/network errors with backoff. Do not blindly retry validation, auth, API enablement, or invalid-state errors without changing the request or merchant configuration.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:269)
- Route handler and S2S auth call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2122)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:455)
- Transformer target-selection logic: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:378)
- Success response builder: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:470)
- Mobile/device block logic: [src/Newton/Product/Merchant/Customer/BlockUnblock.hs](../../src/Newton/Product/Merchant/Customer/BlockUnblock.hs:27)
- VPA block logic and per-item responses: [src/Newton/Product/Merchant/Vpa/BlockVpa.hs](../../src/Newton/Product/Merchant/Vpa/BlockVpa.hs:67)
- S2S request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API-allowlist middleware: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Validation dispatch: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Common field validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:215)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:36)
