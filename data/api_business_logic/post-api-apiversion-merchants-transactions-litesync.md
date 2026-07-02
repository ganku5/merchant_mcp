# LiteSync API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/litesync`

## Overview

LiteSync is a server-to-server API used to synchronize a customer's UPI Lite account state with NPCI.

The merchant backend calls this API with the Lite Reference Number (`lrn`), the merchant customer id, and a merchant-generated UPI request id. Newton sends an NPCI `ReqChkTxn` request of type `LiteSync` and returns the gateway sync result. For normal sync calls, the response can include the sync data returned by NPCI. For Lite account disable/deregistration flows, send the configured disable purpose code; Newton validates that no active Lite mandates are present before sending the disable sync request.

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Use LiteSync when the merchant backend needs to:

- Fetch the latest UPI Lite sync data for a customer's Lite Reference Number.
- Reconcile client/auth-engine Lite state with NPCI after a UPI Lite lifecycle event.
- Disable a zero-balance UPI Lite account by sending the configured disable purpose code.
- Receive NPCI gateway status, error code, error message, and sync data in a server-to-server response.

Important identifiers:

- `merchantCustomerId`: Merchant's customer profile id. Newton uses it to load the customer context and verify the request belongs to the merchant.
- `upiRequestId`: Merchant-generated UPI request id for this LiteSync attempt. Newton forwards it as the NPCI transaction id.
- `lrn`: Lite Reference Number for the UPI Lite account being synchronized.
- `purpose`: Optional NPCI purpose code. The current default disable-LRN purpose code in configuration is `50`.

## Integration Flow

1. Merchant backend identifies the customer profile and the UPI Lite `lrn`.
2. Merchant creates a unique `upiRequestId` for this LiteSync attempt.
3. Merchant signs and/or encrypts the request using the onboarded Newton S2S envelope.
4. Newton decrypts/verifies the envelope, loads merchant and merchant-customer context, checks API access, validates timestamp/IP restrictions where configured, and calls the LiteSync product logic.
5. Newton builds an NPCI `ReqChkTxn` request with transaction type `LiteSync`, the supplied `lrn`, `purpose`, and `clVersion`.
6. Newton maps the NPCI response into the LiteSync response payload.
7. Merchant decrypts/verifies the Newton response and uses `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, `payload.gatewayResponseMessage`, and `payload.arpc` for client handling and reconciliation.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/litesync
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment. The route also reads `x-api-version` from headers where version-specific platform behavior is enabled. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-api-version` | Recommended | API version header shared during onboarding. |
| `x-merchant-id` | Yes | Merchant id issued by Newton. Used to resolve merchant configuration and keys. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued by Newton. |
| `x-timestamp` | Yes | Request timestamp used by Newton's S2S signature/timestamp checks. Must be within the allowed timestamp window. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain business payload mode. The signature is computed over merchant id, channel id, optional sub-merchant ids, timestamp, and raw request body using the onboarded merchant API key/signature strategy. |
| `x-sub-merchant-id` | Conditional | Required only for sub-merchant integrations where Newton has onboarded sub-merchant credentials. |
| `x-sub-merchant-channel-id` | Conditional | Required only with `x-sub-merchant-id`. |
| `x-forwarded-for` | Conditional | Required when the merchant is configured with whitelisted IPs. The first IP in the comma-separated value must be whitelisted. |
| `x-request-id` | No | Optional request correlation id. Newton generates one if omitted. |
| `x-session-id` | No | Optional session correlation id. Defaults to `x-request-id` if omitted. |

Authentication and encryption follow the standard Newton S2S process:

- JWE request body: send an encrypted envelope with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS request body: send a signed envelope with `payload`, `signature`, and `protected`.
- Plain business payloads are accepted only for integrations/environments configured for that mode and must pass `x-merchant-signature`.
- For JWE/JWS requests, the decrypted business payload must include `iat`; Newton validates it as a timestamp.
- Responses are returned using the merchant's configured response strategy: JWS, JWS+JWE, or unsigned JSON with `x-response-signature`.

## Request

### Required Minimum

```json
{
  "upiRequestId": "LITESYNC123456",
  "lrn": "123456789012",
  "merchantCustomerId": "CUST12345"
}
```

### Normal Sync With Client Version

```json
{
  "upiRequestId": "LITESYNC123457",
  "lrn": "123456789012",
  "merchantCustomerId": "CUST12345",
  "clVersion": "2.1.0",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Disable Lite Account

Use this only for the Lite account disable/deregistration journey. The current configured disable purpose code is `50`.

```json
{
  "upiRequestId": "LITEDISABLE123458",
  "lrn": "123456789012",
  "merchantCustomerId": "CUST12345",
  "purpose": "50",
  "clVersion": "2.1.0",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `upiRequestId` | string | Yes | No default. | Unique request id for this LiteSync attempt. Newton forwards this as the NPCI transaction id and uses it for monitoring. Clients should send 1 to 35 alphanumeric characters. |
| `lrn` | string | Yes | No default. | Lite Reference Number for the UPI Lite account. Newton forwards it to NPCI as the `lrn`. For disable requests, Newton also uses it to check active Lite mandates. |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id for the payer/customer. Newton uses this value during signature verification to load the merchant-customer and customer records. |
| `iat` | string | Conditional | No default. | Issued-at timestamp in the decrypted business payload. Required and timestamp-validated for JWE/JWS envelopes. Not required for plain signed-by-header payload mode. |
| `purpose` | string | No | If omitted, Newton performs a normal Lite sync. | NPCI purpose code to include in the LiteSync request. Send the configured disable purpose code, currently `50`, only for Lite disable/deregistration. |
| `clVersion` | string | No | No default. | Client library/app version forwarded to NPCI. If supplied, it must be non-empty. |

### Defaults and Omitted Field Behavior

- `purpose`: omitted means normal Lite sync. The NPCI note is set to `CL and Auth Engine Sync up`.
- `purpose = "50"`: treated as a disable-LRN request in the current configuration. The NPCI note is set to `Disable Lrn`.
- `clVersion`: omitted means Newton does not send client version to NPCI.
- `iat`: no server-side default. Include it for encrypted/signed envelope modes.
- No request field is generated by Newton for this API; the merchant must provide `upiRequestId`, `lrn`, and `merchantCustomerId`.

## Validation and Access Rules

Newton applies the following checks before or during LiteSync processing:

- The request body must match the configured Newton S2S envelope. Invalid JWE/JWS, missing key id, decryption failure, or JWS verification failure is rejected before product logic.
- `x-merchant-id` and `x-merchant-channel-id` must resolve to an onboarded merchant.
- If sub-merchant headers are supplied, they must resolve to an allowed sub-merchant.
- The API must be enabled for the merchant. Merchant configuration can explicitly block `liteSync` or restrict the merchant to an allow-list of APIs.
- If IP whitelisting is configured, the first IP in `x-forwarded-for` must be present and whitelisted.
- `x-timestamp` must be present and within the allowed timestamp window.
- For encrypted/signed request envelopes, `iat` in the decrypted payload must be present and within the allowed timestamp window.
- `merchantCustomerId` must identify a merchant-customer under the calling merchant, because the handler sets merchant-customer and customer context before product logic.
- Required JSON fields are `upiRequestId`, `lrn`, and `merchantCustomerId`. Missing fields or wrong JSON types fail request decoding.
- Clients should keep `upiRequestId` alphanumeric and 1 to 35 characters, and send a non-empty `clVersion` when present. These are the request type's defined validation rules; this route path does not show an explicit field-validation call before constructing the NPCI request, so merchants should enforce these rules before calling Newton.
- For disable-LRN requests, Newton checks whether active Lite mandates exist for the `lrn`. If active Lite mandates are present, the disable request is rejected with code `JPLM`.

## Response

### Success Response: Normal Sync

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Sync data fetched successfully",
    "lrn": "123456789012",
    "arpc": "NPCI_SYNC_DATA"
  }
}
```

### Success Response: Disable Lite Account

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Account disabled successfully",
    "lrn": "123456789012",
    "arpc": "NPCI_SYNC_DATA"
  }
}
```

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton API status. `SUCCESS` means Newton completed LiteSync handling and received a successful NPCI result. `FAILURE` means Newton or NPCI returned a failure. |
| `responseCode` | string | Newton response code. For successful LiteSync this is `SUCCESS`. For mapped downstream failures this can be `BAD_RESPONSE_FROM_NPCI`, `JPL7`, `SERVICE_UNAVAILABLE`, or another platform error code. |
| `responseMessage` | string | Human-readable Newton response message. |
| `payload` | object or null | LiteSync gateway payload when available. Omitted/null for some platform, timeout, or internal failures. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `gatewayResponseStatus` | string | NPCI/gateway result status, for example `SUCCESS` or `FAILURE`. |
| `gatewayResponseCode` | string | Gateway response code. Newton sets `00` for successful NPCI LiteSync. For NPCI failures this is the NPCI error code when available, otherwise a fallback such as `JPL7`. |
| `gatewayResponseMessage` | string | Gateway response message. For successful normal sync this is `Sync data fetched successfully`; for successful disable this is `Account disabled successfully`; for failures this is the NPCI error detail or mapped error message. |
| `lrn` | string | LRN returned by NPCI on successful LiteSync. Omitted/null on failure responses. |
| `arpc` | string | Sync data returned by NPCI in the first response reference's `syncData` field. Omitted/null when NPCI does not return sync data or when the response is a failure. |

## Failure Scenarios

Failure bodies below show decrypted examples. Depending on where the failure occurs, the HTTP status can be 200, 400, 401, 500, or 503, and the response may be an encrypted/signed Newton envelope or a plain platform error body.

### Missing or Malformed Required Field

Missing required fields or invalid JSON types fail request decoding before product logic.

Example decrypted/platform body:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Error in $: key \"lrn\" not found"
}
```

### Field Validation Failure

The LiteSync request type defines field validation for `upiRequestId` and `clVersion`. If this validation is applied by the platform path, invalid request ids or empty optional values are returned as bad requests. Examples include an empty `upiRequestId`, a non-alphanumeric `upiRequestId`, an `upiRequestId` longer than 35 characters, or an empty `clVersion`.

Example decrypted body:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"upiRequestId length is not between 1 and 35\""
}
```

### Authentication, Signature, or Encryption Failure

This includes missing merchant headers, unknown merchant/channel, invalid key id, JWE decryption failure, JWS verification failure, invalid `x-merchant-signature`, missing/invalid `iat`, or stale `x-timestamp`.

Example decrypted/platform body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### API Not Enabled or Merchant Not Allowed

If merchant configuration blocks LiteSync or the merchant is restricted to an allow-list that does not include `liteSync`, Newton rejects the request.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### IP Restriction Failure

If merchant IP whitelisting is configured and `x-forwarded-for` is missing or the first IP is not whitelisted, Newton rejects the request.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Invalid Merchant Customer

If `merchantCustomerId` does not map to a valid merchant-customer/customer for the calling merchant, Newton fails while loading customer context. The exact response depends on the underlying lookup path.

Representative decrypted body:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

### Active Lite Mandates Present During Disable

For disable-LRN requests (`purpose = "50"` in the current configuration), Newton checks active Lite mandates before calling NPCI. If any active Lite mandate exists, the request is rejected.

```json
{
  "status": "FAILURE",
  "responseCode": "JPLM",
  "responseMessage": "You have active lite mandate(s). Please retry after revoking all lite mandates."
}
```

### NPCI Failure Response

If NPCI returns a non-success `RespChkTxn`, Newton returns a LiteSync failure with Newton response code `BAD_RESPONSE_FROM_NPCI` and the NPCI error code/message inside `payload`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI",
  "payload": {
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U30",
    "gatewayResponseMessage": "NPCI mapped error message"
  }
}
```

### NPCI Immediate Acknowledgement Failure

If the NPCI call fails immediately with acknowledgement error messages, Newton returns code `JPL7`. If NPCI supplies an error code/detail, those values are placed in the payload; otherwise Newton falls back to `JPL7`.

```json
{
  "status": "FAILURE",
  "responseCode": "JPL7",
  "responseMessage": "Invalid response from NPCI",
  "payload": {
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JPL7",
    "gatewayResponseMessage": "Invalid response from NPCI"
  }
}
```

### NPCI Error Body Failure

If the downstream NPCI error body contains a code/message, Newton returns `BAD_RESPONSE_FROM_NPCI` and copies that downstream code/message into the payload.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI",
  "payload": {
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "NPCI_ERROR_CODE",
    "gatewayResponseMessage": "NPCI error message"
  }
}
```

### NPCI Timeout

If the NPCI LiteSync call times out, Newton returns service unavailable without a LiteSync payload.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE",
  "responseMessage": "UPI service is not reachable at the moment"
}
```

### Invalid NPCI Success Shape

If NPCI reports success but does not include the expected response reference list, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

### Internal Error

Unexpected decode failures, missing runtime context, missing Redis entries, response-signing/encryption failures, or other unhandled exceptions return an internal error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Treat `status = SUCCESS` and `payload.gatewayResponseStatus = SUCCESS` as a completed LiteSync.
- For a successful normal sync, consume `payload.arpc` as the NPCI sync data if present.
- For a successful disable request, treat `payload.gatewayResponseMessage = "Account disabled successfully"` as the disable confirmation and reconcile the local Lite account state accordingly.
- Do not retry validation, authentication, API-access, IP-whitelist, invalid merchant-customer, or active-mandate failures without correcting the request/configuration or revoking active Lite mandates.
- Retry `SERVICE_UNAVAILABLE` with backoff and the same `upiRequestId` only if your integration's idempotency policy allows it; otherwise generate a new `upiRequestId` for a new LiteSync attempt.
- For `BAD_RESPONSE_FROM_NPCI` or `JPL7`, inspect `payload.gatewayResponseCode` and `payload.gatewayResponseMessage`. Retry only when the downstream code is transient according to your NPCI/Newton operational guidance.
- Log and reconcile using `upiRequestId`, `lrn`, `merchantCustomerId`, `gatewayResponseCode`, and `gatewayResponseStatus`.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:451)
- Route handler and S2S middleware chain: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2620)
- Request and response types: [src/Newton/Types/API/ServerToServer/UPILite.hs](../../src/Newton/Types/API/ServerToServer/UPILite.hs:18)
- LiteSync product logic and response mapping: [src/Newton/Product/TransactionV2.hs](../../src/Newton/Product/TransactionV2.hs:1156)
- NPCI LiteSync request construction: [src/Newton/Product/TransactionV2.hs](../../src/Newton/Product/TransactionV2.hs:1666)
- Active Lite mandate check for disable flow: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2954)
- S2S request envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Payload verification and JWE/JWS handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API allow-list, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response signing/encryption selection: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Common error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:10)
