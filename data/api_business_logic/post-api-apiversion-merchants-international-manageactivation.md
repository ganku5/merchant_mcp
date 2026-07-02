# Manage Activation API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/international/manageActivation`

## Overview

Manage Activation is a server-to-server API used to activate, deactivate, or query a customer's bank account for UPI international use.

The merchant sends the customer, bound-device, account, action, and credential context. Newton validates the request and merchant security envelope, verifies the merchant customer and bound device, resolves the customer account, and then either:

- sends NPCI `ReqActivation` for the normal `UPI_INTERNATIONAL` feature, or
- updates/query-checks Newton's local `INTERNATIONAL_FIR` consent activation record for the `UPI_INTERNATIONAL_FIR` feature.

Use this API before allowing a customer to complete an international UPI payment when the customer account must be enabled for international transactions. Use the query actions to refresh or reconcile activation state after an activation attempt, a timeout, or a gateway pending result. Do not use this API to validate an international QR payload; use `validateQr` for that.

Payloads use the standard Newton server-to-server signed/encrypted request and response envelope shared during onboarding. Examples below show decrypted business payloads for readability.

## Business Use Case

Manage Activation helps merchants:

- Enable international UPI payments for a customer's selected account.
- Disable international UPI capability for a selected account.
- Check Newton's local activation state and, when required, query NPCI for the latest activation state.
- Support GPay ICICI style account-reference flows where the account is identified by `accountReferenceId` and `ifsc`.
- Support FIR consent flows used by NPCI `ReqValCust` international service checks.
- Distinguish an API transport/security failure from an NPCI gateway-level activation failure.

Typical normal international activation sequence:

1. Customer selects an account in the merchant app and gives consent to enable UPI international.
2. Merchant backend calls `manageActivation` with `action: "ACTIVATE"`, the account identifier, and the CL/NPCI MPIN credential block.
3. Newton authenticates the merchant request and validates merchant-customer, customer, device, account, dates, and credential rules.
4. Newton sends NPCI `ReqActivation`.
5. Newton returns top-level API status plus `payload.gatewayResponseStatus`.
6. If `payload.gatewayResponseStatus` is `SUCCESS`, treat the normal international activation as successful. Store the returned `payload.status`, `payload.startDate`, and `payload.endDate` when present.
7. If the gateway response is pending or failed, use `QUERY` or `FORCE_QUERY` based on your integration's reconciliation policy before letting the customer retry.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. Newton uses it to resolve the active merchant customer and customer.
- `deviceFingerPrint`: Fingerprint of the bound customer device. It must match Newton's stored device fingerprint for the merchant customer.
- `upiRequestId`: Merchant-generated request id for this activation API attempt. It must be 1 to 35 alphanumeric characters.
- `bankAccountUniqueId`: Account hash/reference used by most Newton S2S integrations.
- `accountReferenceId`: Account id or migrated account reference. For GPay ICICI flows, this is the account reference number and may require `ifsc`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/international/manageActivation
```

The route segment is case-sensitive: use `manageActivation`.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Request timestamp used by the S2S signature flow. |
| `x-merchant-signature` | Required for plain S2S payload/signature mode. For JWS/JWE payloads, integrity is validated through the envelope. |
| `x-request-id` | Optional but recommended for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional. Defaults to `x-request-id` when omitted. |
| `x-psp-encryption` | Optional response override. Supported values include `JWS` and `JWS_AND_JWE`, subject to onboarding/key configuration. |

Path parameters:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Route version shared during onboarding. The route captures this path segment before dispatching to S2S APIs. |

Authentication, request signing, encryption, and response verification follow the standard Newton S2S process configured for your merchant. Depending on onboarding, the request body can be a plain signed payload, JWS, or JWS wrapped in JWE. Response bodies can be plain with `X-Response-Signature`, JWS, or JWS+JWE.

## Request

### Required Minimum

For normal UPI international activation, send the customer, device, request id, account identifier, action, and credential block:

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLACT10001",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "ACTIVATE",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20260702\",\"encryptedBase64String\":\"BASE64_CL_PAYLOAD\"},\"type\":\"PIN\"}}"
}
```

For normal UPI international query, omit `credBlock`:

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLQRY10001",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "QUERY"
}
```

For FIR consent activation, send `featureName: "UPI_INTERNATIONAL_FIR"` and omit `credBlock`:

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "FIRACT10001",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "featureName": "UPI_INTERNATIONAL_FIR",
  "action": "ACTIVATE"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters and match Newton's merchant-customer id format. Newton uses it during merchant signature verification to load the merchant customer and customer. |
| `deviceFingerPrint` | string | Yes | No default. | Fingerprint of the customer's bound device. Must be non-empty and must match the device stored for the merchant customer. This API does not accept a fallback fingerprint. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated id for this activation API attempt. Must be 1 to 35 alphanumeric characters. Used for tracing and NPCI request construction. |
| `featureName` | string | No | Defaults to `UPI_INTERNATIONAL`. | `UPI_INTERNATIONAL` for normal international activation through NPCI. `UPI_INTERNATIONAL_FIR` for FIR consent activation/query using Newton's local activation record. |
| `bankAccountUniqueId` | string | Conditional | No default. | Account hash/reference for the customer account. Required unless `accountReferenceId` is supplied. If both account identifiers are supplied, the account lookup path prefers `accountReferenceId` in some flows and `bankAccountUniqueId` in others; send one clear identifier unless onboarding says otherwise. |
| `accountReferenceId` | string | Conditional | No default. | Newton account id or migrated account reference. Required unless `bankAccountUniqueId` is supplied. For GPay ICICI migrated-user account references, `ifsc` is also required. |
| `ifsc` | string | Conditional | No default. | Required for GPay ICICI migrated account-reference lookup when `accountReferenceId` is not a Newton account id. Otherwise optional and used only for account resolution in those flows. |
| `credBlock` | string | Conditional | No default. | Required for `ACTIVATE` and `DEACTIVATE` when `featureName` is omitted or `UPI_INTERNATIONAL`. Must be omitted for `QUERY` and `FORCE_QUERY`. Not required for `UPI_INTERNATIONAL_FIR`. The value is a JSON string containing CL/NPCI credential data; Newton parses and forwards `mpincred`. |
| `startDate` | string | No | Defaults to current server time for normal activation. Ignored for FIR local consent responses. | Activation validity start timestamp. Must parse as an offset timestamp, for example `2026-07-02T10:15:30+05:30`. For `ACTIVATE`, it cannot be before the current day. |
| `endDate` | string | No | Defaults to `startDate + INTERNATIONAL_DEFAULT_ACTIVATION_VALIDITY_DAYS`; the environment default is 90 days. Ignored for FIR local consent responses. | Activation validity end timestamp. Must parse as an offset timestamp. For `ACTIVATE`, it must be on or after `startDate` and the activation duration cannot exceed 90 days. |
| `action` | string | Yes | No default. | Allowed values: `ACTIVATE`, `DEACTIVATE`, `QUERY`, `FORCE_QUERY`. `FORCE_QUERY` is valid only for normal `UPI_INTERNATIONAL`, not for `UPI_INTERNATIONAL_FIR`. |
| `note` | string | No | Defaults in the downstream NPCI request to `ReqActivation`. | Optional note forwarded to NPCI for normal `UPI_INTERNATIONAL`. |
| `udfParameters` | string | No | Omitted from the response if omitted. | Merchant-defined metadata as a JSON-object string. It must parse as a JSON object and must not contain characters rejected by Newton's UDF validator. Echoed in the response when supplied. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by signed/encrypted request body flows. Required for JWS/JWE payloads because Newton validates it before processing. Plain S2S signature mode ignores this field. |
| `clVersion` | string | No | Omitted from the downstream NPCI request when not supplied. | Customer library version forwarded to NPCI as `clVersion` in the `ReqActivation` transaction block. |

### `credBlock` String

`credBlock` is not a nested JSON object in the S2S request type. Send it as a string containing a JSON object generated by the UPI Common Library. Newton decodes the string as a credential block and uses `mpincred`.

Readable credential-block structure before JSON string escaping:

```json
{
  "mpincred": {
    "subType": "MPIN",
    "data": {
      "code": "NPCI",
      "ki": "20260702",
      "encryptedBase64String": "BASE64_CL_PAYLOAD",
      "hmac": "OPTIONAL_HMAC",
      "pid": "OPTIONAL_PID",
      "skey": "OPTIONAL_SKEY",
      "type": "OPTIONAL_DATA_TYPE"
    },
    "type": "PIN"
  }
}
```

### Nested Request Objects

This request has no nested business objects. Send `credBlock` and `udfParameters` as strings when supplied.

### Validation Notes

- Missing required JSON fields can be rejected before business validation because the request type requires them.
- `merchantCustomerId` must be non-empty, at most 256 characters, and match Newton's merchant-customer id regex.
- `deviceFingerPrint`, `bankAccountUniqueId`, `accountReferenceId`, `ifsc`, `credBlock`, and `clVersion`, when supplied, must be non-empty.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `udfParameters`, when supplied, must be a JSON object encoded as a string.
- `startDate` and `endDate`, when supplied, must parse as offset timestamps accepted by Newton's timestamp parser.
- For normal `UPI_INTERNATIONAL`, `ACTIVATE` and `DEACTIVATE` require `credBlock`; `QUERY` and `FORCE_QUERY` reject `credBlock`.
- For `UPI_INTERNATIONAL_FIR`, only `ACTIVATE`, `DEACTIVATE`, and `QUERY` are valid.
- At least one account identifier, `bankAccountUniqueId` or `accountReferenceId`, must resolve to an active account for the merchant customer.

## Request Examples

### Normal Activation With Explicit Validity

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLACT10002",
  "featureName": "UPI_INTERNATIONAL",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "ACTIVATE",
  "startDate": "2026-07-02T10:15:30+05:30",
  "endDate": "2026-09-30T10:15:30+05:30",
  "note": "Enable international payments",
  "clVersion": "1.8",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20260702\",\"encryptedBase64String\":\"BASE64_CL_PAYLOAD\"},\"type\":\"PIN\"}}",
  "udfParameters": "{\"consentId\":\"CONSENT10002\"}"
}
```

### Normal Deactivation

`DEACTIVATE` also requires `credBlock` for normal `UPI_INTERNATIONAL`.

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLDEA10001",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "DEACTIVATE",
  "note": "Disable international payments",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20260702\",\"encryptedBase64String\":\"BASE64_CL_PAYLOAD\"},\"type\":\"PIN\"}}"
}
```

### Query Existing Status

Use `QUERY` when you want Newton to use local state where configured and query NPCI only when required by the product flow, such as a pending activation state.

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLQRY10002",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "QUERY"
}
```

### Force Query NPCI

Use `FORCE_QUERY` only for normal `UPI_INTERNATIONAL` when you explicitly want a downstream NPCI query even if Newton has a local activation record.

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLFQ10001",
  "featureName": "UPI_INTERNATIONAL",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "FORCE_QUERY"
}
```

### GPay ICICI Account-Reference Flow

For GPay ICICI migrated-user account references, include `accountReferenceId` and `ifsc`.

```json
{
  "merchantCustomerId": "PSP_PROFILE_10001",
  "deviceFingerPrint": "device-fingerprint-from-binding",
  "upiRequestId": "INTLACT10003",
  "featureName": "UPI_INTERNATIONAL",
  "accountReferenceId": "ACREF1234567890",
  "ifsc": "ICIC0000001",
  "action": "ACTIVATE",
  "startDate": "2026-07-02T10:15:30+05:30",
  "endDate": "2026-09-30T10:15:30+05:30",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"ki\":\"20260702\",\"encryptedBase64String\":\"BASE64_CL_PAYLOAD\"},\"type\":\"PIN\"}}"
}
```

### FIR Consent Activation

FIR consent updates local activation state. It does not call NPCI `ReqActivation` and does not require `credBlock`.

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "FIRACT10002",
  "featureName": "UPI_INTERNATIONAL_FIR",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "ACTIVATE",
  "udfParameters": "{\"consentId\":\"FIRCONSENT10002\"}"
}
```

### FIR Consent Query

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "FIRQRY10001",
  "featureName": "UPI_INTERNATIONAL_FIR",
  "bankAccountUniqueId": "8a25f1f6f0c2b6f7d3c2d0a7c4b0a99f",
  "action": "QUERY"
}
```

## Response

### How To Interpret Status

There are two status layers:

- Top-level `status`, `responseCode`, and `responseMessage` describe whether Newton processed the API request and built a manage-activation response.
- For normal `UPI_INTERNATIONAL`, `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` describe the NPCI/downstream activation result when a downstream call was made.

A valid API response can have top-level `status: "SUCCESS"` and `payload.gatewayResponseStatus: "FAILURE"`. For normal `UPI_INTERNATIONAL`, treat activation/deactivation as completed only when the top-level status is `SUCCESS` and the relevant payload state indicates success:

- For normal activation/deactivation through NPCI, prefer `payload.gatewayResponseStatus == "SUCCESS"` when present.
- When merchant international checks are enabled, `payload.status` is Newton's local activation state: `ACTIVE`, `INACTIVE`, `PENDING`, or `FAILURE`.
- When merchant international checks are disabled, such as ICICI/GPay flows, `payload.status` can be omitted and dates can come directly from NPCI.
- For `UPI_INTERNATIONAL_FIR`, top-level `SUCCESS` plus `payload.status` is the local FIR consent outcome. Gateway fields are omitted because the FIR branch does not call NPCI `ReqActivation`.

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. For processed manage-activation responses, this is `SUCCESS`. |
| `responseCode` | string | API processing code. For processed manage-activation responses, this is `SUCCESS`. |
| `responseMessage` | string | API processing message. For processed manage-activation responses, this is `SUCCESS`. |
| `payload` | object | Manage-activation business result. Present on processed responses. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted otherwise. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton local activation status when available: `ACTIVE`, `INACTIVE`, `PENDING`, or `FAILURE`. Omitted in some normal activation flows when international checks are disabled. |
| `startDate` | string | Activation start timestamp from Newton's local activation record when checks are enabled, or from NPCI response when checks are disabled. Omitted when unavailable. |
| `endDate` | string | Activation end timestamp from Newton's local activation record when checks are enabled, or from NPCI response when checks are disabled. Omitted when unavailable. |
| `startDateNpci` | string | NPCI validity start timestamp returned by `FORCE_QUERY`. Omitted for most non-force responses. |
| `endDateNpci` | string | NPCI validity end timestamp returned by `FORCE_QUERY`. Omitted for most non-force responses. |
| `gatewayResponseStatus` | string | Downstream NPCI result when a downstream call was made, usually `SUCCESS` or `FAILURE`. Omitted for local-only FIR responses and some local query responses. |
| `gatewayResponseCode` | string | `00` on gateway success. On gateway failure, this is the NPCI/downstream error code when available. Omitted when no downstream call was made. |
| `gatewayResponseMessage` | string | `SUCCESS` on gateway success, otherwise the mapped downstream message when available. Omitted when no downstream call was made. |

## Response Examples

### Normal Activation Accepted By NPCI

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "ACTIVE",
    "startDate": "2026-07-02T10:15:30+05:30",
    "endDate": "2026-09-30T10:15:30+05:30",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS"
  },
  "udfParameters": "{\"consentId\":\"CONSENT10002\"}"
}
```

### Normal Activation Gateway Failure

The API call was processed, but activation failed at the gateway/business layer. Do not treat the account as internationally active.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "FAILURE",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U17",
    "gatewayResponseMessage": "Bank is unreachable. Please try after sometime!"
  }
}
```

### Activation Pending After Gateway Response

For `ACTIVATE`, code `UG1` is treated by product logic as `PENDING`. Use `QUERY` or `FORCE_QUERY` later instead of immediately starting a new activation.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "PENDING",
    "startDate": "2026-07-02T10:15:30+05:30",
    "endDate": "2026-09-30T10:15:30+05:30",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "UG1",
    "gatewayResponseMessage": "Response Activation TimeOut"
  }
}
```

### Normal Deactivation Accepted By NPCI

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "INACTIVE",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS"
  }
}
```

### Query Served From Local State

When international checks are enabled and Newton already has a non-pending activation record, `QUERY` can return local state without gateway fields.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "ACTIVE",
    "startDate": "2026-07-02T10:15:30+05:30",
    "endDate": "2026-09-30T10:15:30+05:30"
  }
}
```

### Force Query With NPCI Dates

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "ACTIVE",
    "startDate": "2026-07-02T10:15:30+05:30",
    "endDate": "2026-09-30T10:15:30+05:30",
    "startDateNpci": "2026-07-02T10:15:30+05:30",
    "endDateNpci": "2026-09-30T10:15:30+05:30",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS"
  }
}
```

### FIR Consent Activation

FIR responses contain the local FIR activation status and omit gateway/date fields.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "ACTIVE"
  },
  "udfParameters": "{\"consentId\":\"FIRCONSENT10002\"}"
}
```

### FIR Consent Deactivation

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "INACTIVE"
  }
}
```

## Defaults and Omitted Field Behavior

- `featureName`: omitted defaults to `UPI_INTERNATIONAL`.
- `startDate`: omitted defaults to the current server time for normal activation.
- `endDate`: omitted defaults to `startDate + internationalDefaultActivationValidityDays`; the environment default is 90 days unless configured otherwise.
- `note`: omitted defaults to `ReqActivation` in the downstream NPCI request.
- `credBlock`: required only for normal `ACTIVATE` and `DEACTIVATE`; omitted for `QUERY`, `FORCE_QUERY`, and FIR.
- `clVersion`: omitted from the NPCI request when not supplied.
- `udfParameters`: omitted from the response when not supplied.
- `iat`: no default. Required for JWS/JWE payloads; not used for plain S2S signature mode.
- Optional response fields are omitted, not returned as `null`.

When an existing `ACTIVE` local activation record is outside its stored validity window, Newton updates it to `INACTIVE` during status evaluation.

## Retry and Client Handling

- For normal `UPI_INTERNATIONAL`, proceed only when the top-level status is `SUCCESS` and `payload.gatewayResponseStatus` is `SUCCESS`, or when your integration is intentionally reading a local-only query response with `payload.status: "ACTIVE"`.
- For `UPI_INTERNATIONAL_FIR`, use top-level `SUCCESS` and `payload.status` because there is no gateway layer.
- If `ACTIVATE` returns `payload.status: "PENDING"` or gateway code `UG1`, wait and call `QUERY` or `FORCE_QUERY` for the same account before starting a fresh activation.
- Do not retry validation failures, device fingerprint mismatch, missing account identifiers, API-not-enabled errors, or "already active/inactive" responses without changing the request, state, or merchant configuration.
- Retry transient downstream failures such as `SERVICE_UNAVAILABLE_NPCI_NA`, `SERVICE_UNAVAILABLE_NPCI_U09`, HTTP 5xx, or network timeouts with bounded exponential backoff.
- If the client did not receive any response, retry the same logical request with the same `upiRequestId`, account, action, dates, and credential context where possible. This endpoint does not implement a separate merchant idempotency key.
- Generate a new `upiRequestId` for a new customer action, a different account, a different validity window, or a changed credential block.
- Repeated `ACTIVATE` or `DEACTIVATE` calls can be rejected as already active/inactive when international checks are enabled. Use `QUERY` for reconciliation.

## Error Handling

Failure responses use the same S2S response transport configured for the merchant. The examples below show decrypted bodies.

### Request Validation Failures

Validation failures usually return a Newton error response body with `status: "FAILURE"`. HTTP status can vary by validation layer; parse the decrypted body whenever one is present.

Missing `credBlock` for normal activation:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Missing CredBlock\""
}
```

Unexpected `credBlock` on query:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"CredBlock Not Required\""
}
```

Invalid `upiRequestId` characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\""
}
```

Invalid `merchantCustomerId` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Invalid timestamp format for `startDate` or `endDate`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"timestamp value not valid\""
}
```

Invalid action for FIR:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Invalid action for UPI_INTERNATIONAL_FIR\""
}
```

Invalid `udfParameters` string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

### Auth, Signature, and Encryption Failures

Missing merchant headers, missing signature material, signature mismatch, invalid JWS signature, invalid JWE decryption, IP whitelist failure, or timestamp failure can stop the request before manage-activation business logic runs.

Example unauthorized body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Example auth-failure body:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Signed/encrypted payload missing `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Invalid JWE/JWS payload parsing can return an invalid-data body:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"action\" not present"
}
```

### Merchant Configuration Failures

If the API is blocked for the merchant, or an allow-list exists and does not include `manageInternationalActivationS2S`, Newton rejects the call before product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If the UPI international feature is disabled in the environment, the current product code returns an internal error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Merchant Customer, Customer, Device, and Account Failures

If `merchantCustomerId` does not resolve for the merchant, or the customer/device binding is incomplete, Newton returns a failure before calling NPCI. Exact messages depend on the failed lookup.

Example merchant/customer lookup failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "MerchantCustomer not found"
}
```

Example missing stored device id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid DeviceId cannot be null for merchantCustomer"
}
```

Example fingerprint mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

Missing account identifier:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory"
}
```

Account not found or not active for the customer/merchant-customer mapping:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

### Date and Activation-State Business Failures

`startDate` before the current day:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "start cannot be less than today"
}
```

`endDate` before `startDate`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "end cannot be less than start"
}
```

Activation duration greater than 90 days:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Max duration cannot be of more than 90 days"
}
```

Already active or already inactive when international checks are enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "JPI01",
  "responseMessage": "Account is already active / inactive for international transactions"
}
```

Inactive or missing activation record for query/deactivation paths when checks require a record:

```json
{
  "status": "FAILURE",
  "responseCode": "JPI02",
  "responseMessage": "Account is inactive for international transactions / Activation record is not available"
}
```

FIR invalid-action fallback supported by product error constants:

```json
{
  "status": "FAILURE",
  "responseCode": "JPAC",
  "responseMessage": "Requested action is not applicable for FIR feature"
}
```

### Gateway and Business Failures

When NPCI returns `RespActivation` with result `FAILURE`, Newton returns a processed API response with top-level `SUCCESS` and a gateway failure in `payload`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "status": "FAILURE",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U17",
    "gatewayResponseMessage": "Bank is unreachable. Please try after sometime!"
  }
}
```

When a downstream immediate failure contains NPCI error details, the same processed-response shape is used with `gatewayResponseStatus: "FAILURE"` and the mapped error code/message.

### Downstream Timeout or Service Unavailable

NPCI timeout:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

NPCI timeout with a downstream timeout code:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "NPCI service is not reachable at the moment (U09)"
}
```

### Unexpected Errors

Unexpected server, database, cache, encryption, credential-block parse, NPCI response parsing, or decode failures return an internal error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Source References

- Route type and endpoint definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:112), [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:692)
- S2S handler and middleware sequence: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3975)
- S2S API wiring: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:235), [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:324)
- S2S request, validation, and response types: [src/Newton/Types/API/ServerToServer/International.hs](../../src/Newton/Types/API/ServerToServer/International.hs:20)
- General international request/response, action, and feature types: [src/Newton/Types/UpiInternational.hs](../../src/Newton/Types/UpiInternational.hs:26), [src/Newton/Types/UpiInternational.hs](../../src/Newton/Types/UpiInternational.hs:45), [src/Newton/Types/UpiInternational.hs](../../src/Newton/Types/UpiInternational.hs:89)
- S2S product route, request validation, device lookup, and device fingerprint validation: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1312)
- S2S-to-general request transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2460)
- S2S response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1851)
- Product activation flow, FIR branch, normal branch, and NPCI response handling: [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:39), [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:179), [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:207)
- Date validation, activation-record refresh, and downstream error handling: [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:445), [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:466), [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:505)
- Timestamp parsing and formatting helpers: [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:174), [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:400)
- Activation record update rules: [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:545)
- UPI international feature flag check: [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:598)
- Default international activation validity configuration: [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs:236), [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs:2473)
- General response builders for normal and force-query responses: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:4612), [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:4644)
- NPCI `ReqActivation` request builder and credential-block parser: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:4697), [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:4866)
- CL credential block type: [src/Newton/Types/API/CredBlock.hs](../../src/Newton/Types/API/CredBlock.hs:24), [src/Newton/Types/API/CredBlock.hs](../../src/Newton/Types/API/CredBlock.hs:47)
- Activation storage statuses and types: [src/Newton/Types/Storage/Activation.hs](../../src/Newton/Types/Storage/Activation.hs:53), [src/Newton/Types/Storage/Activation.hs](../../src/Newton/Types/Storage/Activation.hs:86)
- Activation storage helpers: [src/Newton/Storage/QueriesMiddleware/Activation.hs](../../src/Newton/Storage/QueriesMiddleware/Activation.hs:13)
- Account lookup and account-identifier requirements: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:538), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:609), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:657)
- Device fingerprint comparison: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Request validation helpers and validation failure response builder: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:311), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:575), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:623), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification and merchant signature/API allow-block checks: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- S2S response signing/encryption wrapper: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:31)
- Generic success, bad-request, auth, service-unavailable, and internal-error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:16), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
- International activation error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1002), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1011), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1158)
- NPCI error-code mapping used for gateway messages: [src/Newton/Constants/ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:20)
- ICICI adapter confirming client-level result interpretation: [src/Newton/Services/Transformer/Icici/Core.hs](../../src/Newton/Services/Transformer/Icici/Core.hs:2951)
