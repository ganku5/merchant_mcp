# Web Update Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/webUpdate`

## Overview

Web Update Mandate is a server-to-server API used by a merchant backend to update or revoke an existing UPI mandate that Newton already knows about.

Use `UPDATE` to change the mandate amount, validity end date, or both, subject to mandate type and purpose-code rules. Use `REVOKE` to cancel an active mandate. Newton resolves the merchant from the S2S headers, verifies the encrypted/signed request, looks up the existing mandate by original mandate identifiers, calls the mandate update wrapper, and returns the current gateway outcome.

Payloads use the standard Newton S2S encrypted or signed request and response envelope. Examples in this guide show decrypted business payloads and decrypted business responses for readability.

## Business Use Case

Use `webUpdate` when the merchant needs to:

- Increase or reduce the mandate amount for an approved mandate.
- Extend or shorten the validity end date where the mandate category allows it.
- Update both amount and validity end date in a single mandate modification request.
- Revoke an active mandate from the merchant side.
- Re-send a revoke request for a mandate that Newton already has in `REVOKED` state; Newton returns the prior revoke success details and triggers the revoked callback path.
- Submit an asynchronous update request when `makeAsync` is enabled for the integration.

Do not use this API to create, execute, notify, pause, unpause, approve, list, or check a mandate. Those workflows have separate mandate APIs.

## Integration Flow

1. Merchant creates a UPI mandate through the mandate creation flow and stores the original mandate identifiers.
2. Customer approves the mandate and Newton stores the mandate as an active mandate.
3. Merchant decides to update or revoke the mandate.
4. Merchant sends `webUpdate` with a new `merchantRequestId` for this action, `requestType`, and at least one mandate lookup identifier.
5. Newton unwraps the S2S envelope, resolves merchant and optional sub-merchant headers, verifies signature/API access/IP allowlisting, and validates request fields.
6. Newton generates `upiRequestId` when the decrypted payload omits it.
7. Newton rejects duplicate mandate action requests using `upiRequestId`, `merchantRequestId`, and the merchant customer id.
8. Newton looks up the existing mandate by `originalMerchantRequestId`, else `orgMandateId`, else `umn`.
9. Newton validates mandate state, amount limits, validity-end rules, SBMD/BASBA restrictions, and request-type rules.
10. Newton calls the mandate update wrapper and returns the current gateway result in `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

Important identifiers:

- `merchantRequestId`: Unique merchant idempotency/action reference for this update or revoke request. Do not reuse it for a different mandate action.
- `upiRequestId`: Gateway mandate action id. If omitted, Newton generates one before business logic.
- `originalMerchantRequestId`: Merchant request id from the original mandate creation. Preferred lookup key.
- `orgMandateId`: Original mandate UPI request id. Used only when `originalMerchantRequestId` is not supplied.
- `umn`: UPI Mandate Number. Used only when both `originalMerchantRequestId` and `orgMandateId` are not supplied.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/webUpdate
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Path version configured for the merchant. The response includes `payload.originalMerchantRequestId` only when the resolved API version is greater than `0`. |

### Headers, Authentication, and Envelope

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. In production this is normally a Newton `EncRequest` envelope, not the decrypted business JSON shown below. |
| `x-api-version` | Recommended | API behavior version shared during onboarding. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. Used to resolve the merchant before business logic. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required only for configured sub-merchant routing. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` where configured. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payload mode. Signature is computed as configured during onboarding. |
| `x-timestamp` | Conditional | Required for unsigned/plain payload mode and validated for freshness. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured; the first IP in the comma-separated value must be allowlisted. |

The route request type is `EncRequest WebUpdateMandateRequest`. Depending on onboarding, the wire request can be:

- JWE encrypted payload with fields `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed payload with fields `payload`, `signature`, and `protected`.
- Plain decrypted JSON payload, accepted only where merchant configuration permits it and protected by merchant signature headers.

For signed or encrypted request bodies, include `iat` in the decrypted business payload. Newton validates it before business logic. The response is returned according to the merchant response strategy: encrypted, signed, error body, or plain JSON. The examples below show decrypted response bodies.

## Request

The examples show decrypted business payloads.

### Update Amount

```json
{
  "merchantRequestId": "UPDMANDATE000001",
  "originalMerchantRequestId": "MANDATE000000001",
  "requestType": "UPDATE",
  "amount": "750.00",
  "mandateRequestExpiryMinutes": "15",
  "upiRequestId": "UPDUPI000000001",
  "remarks": "Update mandate amount",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Update Validity End

```json
{
  "merchantRequestId": "UPDMANDATE000002",
  "originalMerchantRequestId": "MANDATE000000001",
  "requestType": "UPDATE",
  "validityEnd": "2026-12-31",
  "mandateRequestExpiryMinutes": "15",
  "upiRequestId": "UPDUPI000000002",
  "remarks": "Extend mandate validity",
  "iat": "2026-07-02T10:16:00+05:30"
}
```

### Update Amount and Validity End

```json
{
  "merchantRequestId": "UPDMANDATE000003",
  "originalMerchantRequestId": "MANDATE000000001",
  "requestType": "UPDATE",
  "amount": "900.00",
  "validityEnd": "2027-03-31",
  "mandateRequestExpiryMinutes": "30",
  "upiRequestId": "UPDUPI000000003",
  "remarks": "Update amount and validity",
  "udfParameters": "{\"changeTicket\":\"CHG10001\"}",
  "iat": "2026-07-02T10:17:00+05:30"
}
```

### BASBA Amount-Only Update

BASBA mandate updates are restricted to amount modification. Do not send `validityEnd`.

```json
{
  "merchantRequestId": "BASBAUPD000001",
  "originalMerchantRequestId": "BASBAMANDATE0001",
  "requestType": "UPDATE",
  "amount": "1500.00",
  "mandateRequestExpiryMinutes": "15",
  "upiRequestId": "BASBAUPI000001",
  "remarks": "BASBA amount update",
  "iat": "2026-07-02T10:18:00+05:30"
}
```

### Revoke by Original Merchant Request Id

For `REVOKE`, do not send `amount` or `validityEnd`.

```json
{
  "merchantRequestId": "REVOKEMANDATE0001",
  "originalMerchantRequestId": "MANDATE000000001",
  "requestType": "REVOKE",
  "mandateRequestExpiryMinutes": "15",
  "upiRequestId": "REVUPI000000001",
  "remarks": "Customer cancelled subscription",
  "iat": "2026-07-02T10:19:00+05:30"
}
```

### Revoke by UMN

Use this only when original merchant request id and original mandate UPI request id are unavailable. The UMN must identify a payee-side mandate.

```json
{
  "merchantRequestId": "REVOKEMANDATE0002",
  "requestType": "REVOKE",
  "umn": "8b4c6c77f3d145df9a11122334455667@upi",
  "mandateRequestExpiryMinutes": "15",
  "upiRequestId": "REVUPI000000002",
  "remarks": "Merchant side revoke",
  "iat": "2026-07-02T10:20:00+05:30"
}
```

### Update by Original Mandate UPI Request Id

Use `orgMandateId` only when `originalMerchantRequestId` is unavailable.

```json
{
  "merchantRequestId": "UPDMANDATE000004",
  "orgMandateId": "ORGMANDATEUPI000001",
  "requestType": "UPDATE",
  "amount": "1200.00",
  "mandateRequestExpiryMinutes": "15",
  "upiRequestId": "UPDUPI000000004",
  "remarks": "Update using original mandate id",
  "iat": "2026-07-02T10:21:00+05:30"
}
```

### Asynchronous Update

Send `makeAsync` only when Newton has enabled asynchronous mandate update handling for the merchant.

```json
{
  "merchantRequestId": "ASYNCUPD000001",
  "originalMerchantRequestId": "MANDATE000000001",
  "requestType": "UPDATE",
  "amount": "1000.00",
  "mandateRequestExpiryMinutes": "15",
  "upiRequestId": "ASYNCUPI000001",
  "makeAsync": "true",
  "refId": "SUBSCRIPTION-1001",
  "remarks": "Async mandate update",
  "iat": "2026-07-02T10:22:00+05:30"
}
```

## Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | 1 to 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Must be unique for each mandate action for the merchant customer. |
| `originalMerchantRequestId` | string | Conditional | No default. | Preferred mandate lookup key. 1 to 35 characters; same format as `merchantRequestId`. If present, Newton looks up the mandate by this field first. |
| `orgMandateId` | string | Conditional | No default. | Original mandate UPI request id. 1 to 35 alphanumeric characters. Used only when `originalMerchantRequestId` is absent. |
| `requestType` | string | Yes | No default. | Client-facing values for this endpoint: `UPDATE`, `REVOKE`. Other mandate-history enum values belong to other mandate workflows or require fields that are not part of this S2S schema. |
| `mandateRequestExpiryMinutes` | string | No | If omitted, no expiry is generated from this field for the wrapper payload. | Digits only, greater than `0`, maximum `64800`. When supplied, Newton converts it to an absolute expiry timestamp before calling the mandate wrapper. |
| `amount` | string | Conditional | No default. | Required for amount-only updates and BASBA updates. Optional for validity-only updates. Must be `^[0-9]+\\.[0-9][0-9]$` and greater than `0.00`. Must not exceed the configured mandate amount limit for the mandate purpose, merchant MCC, and payee VPA. Must be absent for `REVOKE`. |
| `upiRequestId` | string | No | Newton generates one if omitted. | 1 to 35 alphanumeric characters when supplied. Used for duplicate-action detection and returned as `payload.gatewayMandateId`. |
| `validityEnd` | string | Conditional | No default. | Required only for validity-only updates. Optional when `amount` is also present. Must parse as a date after replacing `/` with `-`. Must be absent for `REVOKE`. For one-time mandates, the end date must not be more than 90 days after original `validityStart`. For recurring mandates, it must not be in the past. BASBA updates must not send it. |
| `remarks` | string | No | Defaults to Newton's default remarks in the wrapper payload when omitted. | 1 to 255 characters. Must start, after optional spaces, with a letter, number, or hyphen, and can contain letters, numbers, spaces, and hyphens. |
| `iat` | string | Conditional | No default. | Required for signed/encrypted request-body modes. Newton validates it as a timestamp before signature verification continues. |
| `umn` | string | Conditional | No default. | Mandate lookup key used only when both `originalMerchantRequestId` and `orgMandateId` are absent. Length 34 to 70 and must match `.{32}@.+`. |
| `udfParameters` | string | No | Omitted from the response when absent. | Must be a JSON object encoded as a string. The text cannot contain characters rejected by the UDF validator, including `/`, `$`, `-`, `*`, `!`, `%`, `~`, and backtick. Echoed as top-level `udfParameters` in the response. |
| `makeAsync` | string | No | No default. | Must be `true` or `false`, case-insensitive. Passed through to the wrapper and returned when supplied. Use only when enabled for your integration. |
| `refId` | string | No | No default. | Optional merchant reference passed to the wrapper. The S2S request validator does not apply a format rule to this field. |

### Conditional Rules

- `UPDATE` requires at least one of `amount` or `validityEnd`.
- `REVOKE` must not include `amount` or `validityEnd`.
- At least one mandate lookup identifier is required: `originalMerchantRequestId`, `orgMandateId`, or `umn`.
- Lookup precedence is `originalMerchantRequestId`, then `orgMandateId`, then `umn`.
- `upiRequestId` is optional in the decrypted request, but the core business logic always receives a value because Newton generates one when omitted.
- `requestType` is parsed through the mandate-history enum, but this endpoint's product validation and wrapper path support only `UPDATE` and `REVOKE` for client use.
- `UPDATE` is sent to the wrapper only when the current mandate status is `SUCCESS` or `PAUSE`; other non-terminal statuses may be rejected by earlier state validation.
- BASBA mandate updates allow amount modification only, require `amount`, reject `validityEnd`, and allow only one successful modification with no pending modification.
- For SBMD secondary-market purpose-code cases, `UPDATE` is rejected. For SBMD e-commerce cases, validity-end modification is restricted by configured time windows.

### Nested Request Objects

This request has no nested business objects. All fields in the decrypted payload are top-level fields.

## Response

The route response type is `EncResponse WebUpdateMandateResponse`. The examples below are decrypted business responses.

Top-level `status`, `responseCode`, and `responseMessage` describe Newton API processing. The actual mandate action outcome is in `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

### Successful Update Request

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "UPDMANDATE000001",
    "mandateName": "Subscription mandate",
    "customerVpa": "customer@okbank",
    "amount": "750.00",
    "expiry": "2026-07-02T10:30:30",
    "remarks": "Update mandate amount",
    "orgMandateId": "ORGMANDATEUPI000001",
    "originalMerchantRequestId": "MANDATE000000001",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "mandateType": "UPDATE",
    "gatewayMandateId": "UPDUPI000000001",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Mandate update Request Sent Successfully",
    "gatewayResponseStatus": "SUCCESS",
    "mandateTimestamp": "2026-06-01T09:00:00"
  }
}
```

### Successful Revoke Request Sent

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "REVOKEMANDATE0001",
    "mandateName": "Subscription mandate",
    "customerVpa": "customer@okbank",
    "expiry": "2026-07-02T10:34:00",
    "remarks": "Customer cancelled subscription",
    "orgMandateId": "ORGMANDATEUPI000001",
    "originalMerchantRequestId": "MANDATE000000001",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "mandateType": "REVOKE",
    "gatewayMandateId": "REVUPI000000001",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate revoke Request Sent Successfully",
    "gatewayResponseStatus": "PENDING",
    "mandateTimestamp": "2026-06-01T09:00:00"
  }
}
```

### API Success With Gateway Failure

If the wrapper returns a mandate and mandate history but the mandate-history status is a gateway failure, the API-level status can still be `SUCCESS`. Treat the payload gateway fields as the source of truth for the mandate action outcome.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "UPDMANDATE000005",
    "customerVpa": "customer@okbank",
    "amount": "900.00",
    "orgMandateId": "ORGMANDATEUPI000001",
    "originalMerchantRequestId": "MANDATE000000001",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "mandateType": "UPDATE",
    "gatewayMandateId": "UPDUPI000000005",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "Mandate Request Failed",
    "gatewayResponseStatus": "FAILURE",
    "mandateTimestamp": "2026-06-01T09:00:00"
  }
}
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. Success responses are built from Newton `successResp` and use `SUCCESS`. |
| `responseCode` | string | API processing code. Success value is `SUCCESS`. |
| `responseMessage` | string | API processing message. Success value is `SUCCESS`. |
| `payload` | object | Mandate update/revoke result payload. Present on success responses. |
| `udfParameters` | string | Echo of request `udfParameters`, omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Newton merchant id from the resolved parent merchant. |
| `merchantChannelId` | string | Newton merchant channel id from the resolved parent merchant. |
| `merchantRequestId` | string | Merchant action id sent in this `webUpdate` request. |
| `subMerchantId` | string | Sub-merchant id, present only when sub-merchant headers resolve to a sub-merchant. |
| `subMerchantChannelId` | string | Sub-merchant channel id, present only when sub-merchant headers resolve to a sub-merchant. |
| `mandateName` | string | Mandate name stored on the existing mandate, omitted if absent. |
| `customerVpa` | string | Payer/customer VPA from the existing mandate. |
| `amount` | string | Requested update amount, present only when `amount` was supplied. |
| `validityEnd` | string | Requested updated validity end date, present only when `validityEnd` was supplied. |
| `expiry` | string | Expiry timestamp stored on the mandate history, generated from `mandateRequestExpiryMinutes` when supplied. |
| `remarks` | string | Remarks stored on the mandate history. |
| `orgMandateId` | string | Existing mandate's original UPI request id. |
| `originalMerchantRequestId` | string | Existing mandate's original merchant request id. Omitted for API version `0`. |
| `umn` | string | UPI Mandate Number from the existing mandate, omitted if absent. |
| `mandateType` | string | Action type for this request, `UPDATE` or `REVOKE`. |
| `gatewayMandateId` | string | `upiRequestId` used for this mandate action, generated by Newton if omitted in the request. |
| `gatewayResponseCode` | string | Gateway/NPCI action code derived from the mandate-history status and NPCI response. `00` indicates success or sent-success for payee update; `01` is commonly pending for revoke request sent. |
| `gatewayResponseMessage` | string | Gateway/NPCI action message, for example `Mandate update Request Sent Successfully` or `Mandate Request Failed`. |
| `gatewayResponseStatus` | string | Mandate action status derived from mandate history. Values include `SUCCESS`, `PENDING`, and `FAILURE`. |
| `mandateTimestamp` | string | Original mandate creation timestamp. |
| `makeAsync` | string | Echo of request `makeAsync`, omitted when not supplied. |

## Error Handling

Failure responses may be returned as encrypted/signed envelopes or as direct error JSON depending on the layer that rejects the request and the merchant response configuration. After decrypting any envelope, the underlying business error shape is:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Need atleast one value, validityEnd or amount",
  "payload": null
}
```

Client handling rule: use HTTP status for transport diagnostics, but use the decrypted `responseCode`, `responseMessage`, and, on API success, `payload.gatewayResponseStatus` for business handling.

### Request Validation Failures

Newton validates the decrypted request before product logic. Most field-validation failures are returned through an HTTP 200 error envelope with `BAD_REQUEST`; some request-type rule failures use HTTP 400 with the same decrypted body shape.

Invalid `merchantRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\"",
  "payload": null
}
```

Invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\"",
  "payload": null
}
```

`UPDATE` without `amount` or `validityEnd`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Need atleast one value, validityEnd or amount",
  "payload": null
}
```

`REVOKE` with `amount` or `validityEnd`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "amount and validityEnd are not valid",
  "payload": null
}
```

Missing mandate lookup identifier:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "originalMerchantRequestId or upiRequestId or umn is mandatory",
  "payload": null
}
```

Client handling: fix the request and retry with the same `merchantRequestId` only if Newton did not create a mandate-history record. For simple validation failures before duplicate check or mandate wrapper call, reuse is safe; for uncertainty, generate a new `merchantRequestId` and check mandate status separately.

### Authentication, Signature, Encryption, and IP Failures

Missing merchant headers, invalid merchant lookup, missing signature, bad signature, stale timestamp, decryption/JWS verification failure, or IP allowlist failure can be rejected before business logic.

Invalid merchant or bad signature:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Missing `iat` for a signed or encrypted body:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "IAT is empty",
  "payload": null
}
```

Client handling: do not retry unchanged. Verify merchant ids, channel ids, sub-merchant ids, timestamp freshness, request body canonicalization, signature key, encryption key id, and source IP allowlisting.

### Merchant Configuration and API Access Failures

If `webUpdateMandate` is blocked or not in the merchant's allowed API list, Newton returns an unauthorized API-not-enabled error.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

If `whitelistedIps` is configured and the first `x-forwarded-for` IP is missing or not allowlisted:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Client handling: contact Newton onboarding/support to enable the API, correct allowed API configuration, or add the calling IP.

### Duplicate and Idempotency Failures

Newton rejects a duplicate mandate action if it finds an existing mandate-history row by the generated/supplied `upiRequestId`, or by `merchantRequestId` with the merchant customer id.

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST",
  "payload": null
}
```

Client handling: do not create a new action blindly. Query mandate status or reconcile by your original `merchantRequestId`/`upiRequestId`. Use a new `merchantRequestId` only for a genuinely new update/revoke action.

### Mandate Lookup Failures

No stored mandate matched the supplied lookup identifiers:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate not found",
  "payload": null
}
```

Client handling: verify that the mandate was created through Newton for the same merchant/sub-merchant, that the original mandate id belongs to the same merchant, and that the UMN is the payee-side UMN.

### Mandate State and Business-Rule Failures

Completed mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMC",
  "responseMessage": "Mandate is already completed",
  "payload": null
}
```

Declined mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMD",
  "responseMessage": "Mandate is declined by payer",
  "payload": null
}
```

Expired mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMX",
  "responseMessage": "Mandate is expried due to no action by payer",
  "payload": null
}
```

Pending mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMW",
  "responseMessage": "Invalid Operation , Mandate is in pending state",
  "payload": null
}
```

Revoked or revoke-pending mandate for an invalid operation:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMR",
  "responseMessage": "Invalid Operation , Mandate is Revoked",
  "payload": null
}
```

Inactive mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is inactive",
  "payload": null
}
```

Update requested for a state that is not valid for the wrapper update path:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "requestType is not valid for mandate update",
  "payload": null
}
```

Invalid validity end:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid validityEnd",
  "payload": null
}
```

Amount exceeds configured limit:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Amount should be between 1 & 100000.0",
  "payload": null
}
```

The maximum value in the amount-limit response is configuration-dependent.

BASBA validity update:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Only amount modification allowed for BASBA mandates",
  "payload": null
}
```

BASBA update without amount:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Amount is required for BASBA mandate updates",
  "payload": null
}
```

BASBA update already pending:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate update is already in pending state",
  "payload": null
}
```

BASBA modification already completed once:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate modification only allowed once",
  "payload": null
}
```

SBMD secondary-market purpose-code update:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid request type for purpose code",
  "payload": null
}
```

Client handling: do not retry unchanged. Correct the request, use the correct mandate workflow, or treat the mandate as not eligible for update/revoke.

### Downstream, NPCI, and Gateway Failures

If the wrapper marks the Galileo/NPCI call as an error or does not return the required mandate data, Newton returns service-unavailable.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)",
  "payload": null
}
```

If a timeout code is available, it is included in the response code/message:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U90",
  "responseMessage": "NPCI service is not reachable at the moment (U90)",
  "payload": null
}
```

For some internal clearing-corporation initiated paths, Newton can return the generic service unavailable body:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE",
  "responseMessage": "UPI service is not reachable at the moment",
  "payload": null
}
```

Client handling: retry only after checking whether a mandate-history entry was created. Prefer querying mandate status before retrying a new action, because the downstream request may have reached NPCI.

### Unexpected Errors

Unexpected internal failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling: treat as unknown outcome. Reconcile by mandate status or contact Newton support with `merchantRequestId`, `upiRequestId`, `originalMerchantRequestId`, and request timestamp.

## Retry and Idempotency Guidance

- Use a unique `merchantRequestId` for each mandate action.
- Supply `upiRequestId` if your system owns gateway action ids; otherwise store the Newton-generated `gatewayMandateId` from the response.
- Do not reuse the same `merchantRequestId` or `upiRequestId` for a different update/revoke action.
- If you receive `DUPLICATE_REQUEST`, do not retry with a new id until you reconcile the existing action.
- If the request fails before business logic, such as bad signature, malformed payload, or validation failure, fix the request and retry. Reusing the same `merchantRequestId` is usually safe because no mandate-history row is created before duplicate validation and wrapper initiation.
- If you receive `SERVICE_UNAVAILABLE`, timeout, connection reset, or no response, treat the outcome as unknown. Query mandate status or wait for callback before retrying.
- For gateway `PENDING`, wait for callback or status polling rather than repeatedly calling `webUpdate`.
- For gateway `FAILURE`, retry only if the business reason is retryable and the mandate remains eligible. Use a new `merchantRequestId` and normally a new `upiRequestId`.

## Source References

- Route declaration for `POST /merchants/mandates/webUpdate`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:552)
- Route handler, request unwrap, signature verification, monitoring id, transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2991)
- S2S envelope request/response constructors: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Request decryption/payload verification path: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40) and [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, timestamp, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- API blocked/allowed checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- S2S request and response types plus request validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:793)
- Core request/response types and core validation: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:225)
- S2S-to-core request mapping and `upiRequestId` default generation: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:430)
- Transformer route into product logic: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:439)
- Product route, duplicate check, mandate lookup, business validation, wrapper call, response mapping: [src/Newton/Product/Merchant/Mandate/WebUpdateMandate.hs](../../src/Newton/Product/Merchant/Mandate/WebUpdateMandate.hs:31)
- Update/revoke request-type rules and validity-end checks: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1249)
- BASBA-specific modification rules: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1567)
- Mandate status validation for update/revoke eligibility: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2903)
- Mandate lookup precedence and lookup failures: [src/Newton/Storage/QueriesMiddleware/Mandate.hs](../../src/Newton/Storage/QueriesMiddleware/Mandate.hs:198)
- Request validation helpers for amount, ids, expiry, date, remarks, UMN, UDF, and boolean strings: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:215)
- Response payload mapping: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2067)
- Gateway response-code/status mapping: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:1488)
- Shared error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:16)
