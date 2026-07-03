# Decline Bind Device API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/bindDevice/decline`

## Overview

Decline Bind Device is a server-to-server API used to cancel a pending customer device-binding registration after the bind-device SMS/token step has been initiated.

The merchant calls this API with the `merchantCustomerId` and the `smsContent` that identifies the pending registration token. Newton validates the S2S payload, merchant credentials, API access configuration, merchant-customer profile, and registration token. If the token is still unbound, Newton marks the registration token as declined. If the token is already bound, Newton does not change it and returns a success envelope with a gateway-level "already bound" result.

Use this API when your backend has determined that the customer has declined, cancelled, or should not continue a pending device-binding journey. Typical examples are a customer pressing "Cancel" during device binding, a risk decision that stops the flow before binding completes, or merchant-side cleanup after a customer abandons an initiated bind-device attempt.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Decline Bind Device helps merchants:

- Stop an in-progress customer device-binding registration before it becomes bound.
- Persist a Newton-side decline marker against the SMS registration token.
- Prevent later activation/binding logic from treating the same pending registration as active.
- Distinguish "declined successfully" from "device was already bound before the decline request arrived."
- Retry a lost decline response safely for the same pending `smsContent`, with client-side handling for a possible already-bound result.

This API does not initiate a UPI transaction, does not call NPCI/bank payment rails, and does not create a merchant idempotency record. It only validates and updates Newton's customer registration-token state.

## Integration Flow

1. Merchant starts the customer device-binding journey through the configured bind-device/get-SMS-token flow.
2. Merchant receives or stores the `smsContent` that identifies the pending registration token.
3. Customer cancels the journey, the merchant backend rejects the journey, or the merchant decides to stop the pending bind.
4. Merchant calls `bindDevice/decline` with `merchantCustomerId` and `smsContent`.
5. Newton verifies the S2S envelope, merchant identity, timestamp, API access, optional IP allowlist, and merchant-customer profile.
6. Newton validates the request body and looks up the registration token by `smsContent`.
7. If the registration token is not already bound, Newton marks it declined and records `declinedAt`.
8. Merchant decrypts the response and reads `payload.gatewayResponseCode` to decide whether the decline took effect.

Important response behavior:

- `status = "SUCCESS"` and top-level `responseCode = "SUCCESS"` mean Newton processed the decline API call.
- `payload.gatewayResponseCode = "00"` means the registration token was declined, or was already in an unbound/declined state and the decline update was accepted again.
- `payload.gatewayResponseCode = "JPAB"` means the device was already bound before this API could decline it. Treat this as a terminal "decline did not cancel binding" outcome and reconcile the customer/device state through your normal customer status flow.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/bindDevice/decline
```

### Path and Headers

| Name | Location | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | path | Yes | API route version shared during onboarding. |
| `Content-Type` | header | Yes | Use `application/json`. |
| `x-api-version` | header | Recommended | Version selector shared during onboarding. This route does not currently branch business response fields by this header. |
| `x-merchant-id` | header | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | header | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | header | Conditional | Required only for configured sub-merchant flows. |
| `x-sub-merchant-channel-id` | header | Conditional | Required only for configured sub-merchant flows. |
| `x-timestamp` | header | Yes | Current request timestamp used for merchant signature and replay validation. Use 13-digit epoch milliseconds. |
| `x-raw-body` | header | Yes | Raw request body used by Newton's signature middleware. In integrations where an API gateway populates this internally, ensure the exact raw body reaches the Newton signature layer. |
| `x-merchant-signature` | header | Conditional | Required for unsigned/plain business payload transport. For JWS/JWE transport, request authentication is carried by the envelope. |
| `x-forwarded-for` | header | Conditional | Required when IP allowlisting is configured for the merchant. |
| `x-request-id` | header | Recommended | Merchant correlation id. Newton echoes/generates it in `x-requestid` response header. |
| `x-session-id` | header | Recommended | Merchant session correlation id. Defaults to `x-request-id` when omitted. |

### Authentication and Encryption

The route accepts the standard Newton `EncRequest` transport:

- JWE encrypted payload with fields `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed payload with fields `payload`, `signature`, and `protected`.
- Plain business payload only where the merchant integration is configured to allow it.

For JWE transport, Newton decrypts the body, expects the decrypted content to be a signed payload, then verifies the signature. For JWS transport, Newton verifies the signature before parsing the business body. For unsigned/plain payload transport, Newton verifies `x-merchant-signature` over the merchant ids, timestamp, and raw body.

For encrypted or signed request bodies, send `iat` inside the decrypted business payload. Newton validates it as a 13-digit epoch-milliseconds timestamp before running the business flow. For unsigned/plain business payloads, `iat` is ignored by the signature layer.

Responses use the merchant's configured S2S response protection. JWS response mode returns a signed body, JWS-and-JWE mode returns an encrypted body, and legacy/plain response mode returns a decrypted body plus `X-Response-Signature`.

## Request

### Required Minimum

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "NWTN-CUST12345-874512"
}
```

For signed/encrypted transport, include `iat` in the decrypted business payload:

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "NWTN-CUST12345-874512",
  "iat": "1782950400000"
}
```

Generate `iat` at request time. The value above is illustrative only.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. It must belong to the authenticated merchant and resolve to an active merchant-customer profile. Maximum length is 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen; the first character must be alphanumeric, plus, slash, or equals. |
| `smsContent` | string | Yes | No default. | SMS registration-token content for the pending bind-device attempt. Must be non-empty. Newton uses this value, or its Redis-mapped canonical value when present, to find the `MerchantCustomerRegistrationToken`. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp used only by encrypted/signed S2S request timestamp validation. Required for JWS/JWE transport; ignored for unsigned/plain payload transport. Use 13-digit epoch milliseconds within the accepted freshness window. |
| `udfParameters` | string | No | Omitted from the response when omitted from the request. | JSON-object string for merchant-defined metadata. It must parse as a JSON object string and must not contain restricted characters rejected by Newton validation. Echoed back in the top-level response when supplied and valid. |

### Defaults and Omitted Field Behavior

There are no business defaults for `merchantCustomerId` or `smsContent`; both must be sent.

Optional fields behave as follows:

- `iat`: required by the authentication layer for JWS/JWE requests. It is not stored as business data and has no effect on the decline decision.
- `udfParameters`: not stored by the decline operation. When supplied and valid, it is echoed in the top-level response.

There are no nested business request objects for this API. The only nested objects are the standard S2S JWE/JWS envelope objects used for transport.

## Request Examples

### Decline Pending Device Binding

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "NWTN-CUST12345-874512",
  "udfParameters": "{\"requestId\":\"decline-bind-001\"}"
}
```

### Decline Pending Device Binding With `iat`

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "NWTN-CUST12345-874512",
  "iat": "1782950400000",
  "udfParameters": "{\"journeyId\":\"BD-20260702-001\",\"reason\":\"CUSTOMER_CANCELLED\"}"
}
```

### Retry After Lost Response

Use the same business payload when the first request timed out before your backend received a response:

```json
{
  "merchantCustomerId": "CUST12345",
  "smsContent": "NWTN-CUST12345-874512",
  "iat": "1782950400000",
  "udfParameters": "{\"requestId\":\"decline-bind-001\",\"retry\":\"1\"}"
}
```

If you regenerate the S2S envelope for a retry, regenerate `iat`, `x-timestamp`, and the envelope signature/encryption values as well.

## Response

### Success: Device Binding Declined

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Device binding declined"
  },
  "udfParameters": "{\"requestId\":\"decline-bind-001\"}"
}
```

Interpretation:

- The API call was accepted and processed.
- Newton marked the registration token declined, or accepted the same decline update again for an unbound token.
- Stop the pending bind-device journey for the customer.

### Success: Device Already Bound

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "gatewayResponseCode": "JPAB",
    "gatewayResponseMessage": "Device already binded"
  }
}
```

Interpretation:

- The API call itself succeeded, but the token was already bound.
- Newton did not mark the registration token declined in this case.
- Treat this as a terminal already-bound outcome and reconcile the customer/device state before showing the next action to the customer.

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. Success responses use `SUCCESS`. |
| `responseCode` | string | Top-level API result code. Success responses use `SUCCESS`. |
| `responseMessage` | string | Top-level API result message. Success responses use `SUCCESS`. |
| `payload` | object | Decline business outcome. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted when the request omits it. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id associated with the authenticated merchant. |
| `merchantChannelId` | string | Merchant channel id associated with the authenticated merchant. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `gatewayResponseCode` | string | Business outcome for the registration token. `00` means declined; `JPAB` means the device was already bound. |
| `gatewayResponseMessage` | string | Human-readable business outcome. Current values are `Device binding declined` and `Device already binded`. |

## Error Handling

Failure responses use the standard S2S response transport where possible. The JSON examples below show decrypted bodies.

### Validation Failures

Request validation runs after S2S payload verification and merchant access checks. These failures are non-retryable until the request body is corrected.

Invalid `merchantCustomerId` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Empty `smsContent`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"smsContent field is empty\""
}
```

Invalid `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Malformed JSON, missing required non-null fields, or type mismatches can fail during JSON parsing before request validation. Treat these as non-retryable request errors and correct the decrypted business payload or S2S envelope payload.

### Authentication, Encryption, and Signature Failures

Authentication failures occur before product logic runs. Common causes include missing or invalid merchant headers, unknown merchant keys, failed JWS verification, failed JWE decryption, missing timestamp headers, stale timestamps, missing `iat` for encrypted/signed payloads, or failed IP allowlist checks.

Failed JWS verification, failed JWE decryption, invalid merchant signature, missing merchant signature, missing merchant headers, or IP allowlist failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Missing `iat` in an encrypted or signed request body:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

`iat` or `x-timestamp` is not a 13-digit epoch-milliseconds value:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

`iat` or `x-timestamp` is outside the accepted freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Missing `kid` in a signed payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding KID"
}
```

Malformed decrypted JWE payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: not enough input"
}
```

### Merchant Configuration and Access Failures

Newton checks whether the API is blocked or allowed for the merchant before running decline logic. If this endpoint is disabled for the merchant or sub-merchant configuration, the response is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If response signing/encryption keys are misconfigured for the merchant response mode, the request can be processed but response construction can fail with a generic internal error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Contact Newton onboarding/support to enable the API or correct merchant key/configuration issues. Do not retry unchanged requests indefinitely.

### Merchant Customer and Registration Lookup Failures

If the authenticated merchant does not have an active profile for `merchantCustomerId`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

If `smsContent` does not resolve to a registration token, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid smsContent"
}
```

These are business/lookup failures. Correct the customer id, ensure the customer belongs to the authenticated merchant, and ensure you are sending the exact `smsContent` from the pending bind-device registration.

### Downstream and Infrastructure Failures

This route does not call NPCI or bank payment downstream systems. The relevant dependencies are Newton's merchant/customer lookup, Redis SMS-content mapping, registration-token storage, and response signing/encryption.

Registration-token update, storage, cache, or key/encryption failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

If a shared platform dependency surfaces a service outage through the common S2S error layer, clients may see a service-unavailable style response:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE",
  "responseMessage": "UPI service is not reachable at the moment"
}
```

Retry transient infrastructure failures with exponential backoff and jitter. Include `x-request-id`, timestamp, `merchantCustomerId`, and `smsContent` when escalating repeated failures.

### Unexpected Errors

Unexpected exceptions are returned with the generic internal error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Do not assume the decline did not happen if the response was lost or an internal error occurred after the update. Retry the same decline request after regenerating the S2S timestamps/signature, then interpret `payload.gatewayResponseCode`.

## Retry and Client Handling Guidance

- This API has no `merchantRequestId` or server-side idempotency key. Treat `merchantCustomerId` plus `smsContent` as your client-side correlation pair.
- A repeat request for the same unbound token is safe for practical retry handling: Newton marks the token declined and returns `payload.gatewayResponseCode = "00"`.
- A repeat request after the token becomes bound returns `payload.gatewayResponseCode = "JPAB"`. Do not treat this as a decline success; reconcile customer/device state.
- For `REQUEST_EXPIRED` or timestamp-format errors, regenerate `iat`, `x-timestamp`, and the S2S envelope/signature before retrying the same business intent.
- Retry `INTERNAL_SERVER_ERROR` and service-unavailable responses with exponential backoff and jitter, because the first attempt may or may not have updated the token.
- Do not retry validation errors, `UNAUTHORIZED`, `API NOT ENABLED`, `User profile not found`, or `Invalid smsContent` without changing the request, credentials, or merchant configuration.
- Store the final gateway-level outcome. Use `00` to close the pending bind journey as declined; use `JPAB` to move into already-bound reconciliation.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:224)
- Route handler, S2S body extraction, merchant signature verification, and product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1888)
- S2S request and response wrapper behavior: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:31), [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35), [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:85)
- S2S payload verification and JWS/JWE/plain handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:200)
- Merchant signature, timestamp, API access, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:168), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- Request/response types and request validator: [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:371), [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:393), [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:403), [src/Newton/Types/API/ServerToServer/Customer.hs](../../src/Newton/Types/API/ServerToServer/Customer.hs:419)
- Shared request validation helpers: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:311)
- Merchant and merchant-customer lookup helpers: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:106), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:209), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:218)
- Product decline flow: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:475)
- Registration-token lookup and invalid `smsContent` error: [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:651), [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:1117)
- Registration-token decline update: [src/Newton/Product/MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:1286), [src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantCustomerRegistrationToken.hs:621)
- Success response construction and gateway response codes: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2113)
- Common error bodies and timestamp validation: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:16), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:169), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:797), [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
