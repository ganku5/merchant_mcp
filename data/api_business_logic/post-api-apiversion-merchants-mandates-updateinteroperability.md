# Update Interoperability API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/updateInteroperability`

## Overview

Update Interoperability is a server-to-server API used to convert an existing Newton payee-side UPI mandate into an interoperability mandate. The API does not create a new mandate and does not change amount, validity, recurrence, or payer details. Newton looks up the original mandate by its merchant request id, validates that the mandate can be converted, creates an internal payee-side mandate update request with interoperability purpose code `AZ`, sends the update to NPCI through the normal mandate update flow, and returns the gateway result.

Use this API only after the original mandate already exists in Newton and the merchant has been enabled for the interoperability update flow.

## Business Use Case

This API helps merchants:

- Mark an existing eligible mandate as interoperable without re-creating the mandate.
- Preserve the original mandate identifiers while creating a separate update attempt for reconciliation.
- Add the required merchant identifier code for interoperability when the mandate payee is a dynamic VPA.
- Reuse the same merchant request id safely for retries after a terminal update result is stored.

Eligibility is enforced by Newton. The original mandate must:

- Belong to the authenticated merchant or resolved sub-merchant.
- Be active enough for update operations.
- Have current purpose `14` or `00`.
- Not already have interoperability purpose `AZ`.
- Not be a prepaid voucher mandate.
- Not have recurrence pattern `ONETIME`.
- Have a valid 20-character merchant identifier code, either from merchant configuration or from the request when dynamic VPA rules require it.

## Integration Flow

1. Merchant creates and stores a normal UPI mandate through the existing mandate creation integration.
2. Merchant decides that the mandate should become interoperable.
3. Merchant generates a new `merchantRequestId` for this interoperability update attempt.
4. Merchant calls `updateInteroperability` with `originalMerchantRequestId` set to the mandate creation request id.
5. Newton authenticates the S2S request, resolves the merchant or sub-merchant, validates request fields, and fetches the original mandate.
6. Newton checks business eligibility and builds a mandate update request with purpose `AZ`, role `PAYEE`, generated gateway update id, and optional `merchantIdentifierCode`.
7. Newton sends the update through the mandate update path and returns the final or pending gateway result.
8. Merchant stores `gatewayMandateId`, `gatewayResponseStatus`, `gatewayResponseCode`, and `gatewayResponseMessage` against the update attempt.

Important identifiers:

| Identifier | Description |
| --- | --- |
| `merchantRequestId` | Merchant-generated idempotency key for this interoperability update attempt. Use a new value for each distinct update attempt. |
| `originalMerchantRequestId` | Merchant request id of the original mandate being converted. This is how Newton looks up the existing mandate. |
| `orgMandateId` | Newton/gateway mandate id from the original mandate. Returned in the response. |
| `gatewayMandateId` | Newton-generated UPI request id for this interoperability update attempt. Returned in the response. |
| `umn` | UPI mandate number, returned when available on the original mandate. |

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/updateInteroperability
```

Payloads use the standard Newton S2S encrypted or signed envelope. Request and response examples below show decrypted business payloads for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured during onboarding. The route also accepts the `x-api-version` header used by other S2S APIs when supplied by the client. |

### Headers and Authentication

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Use `application/json`. |
| `x-merchant-id` | Yes | Merchant id issued by Newton. Used to resolve the merchant before payload validation. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued by Newton. |
| `x-sub-merchant-id` | Conditional | Required when calling as a sub-merchant under a parent merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id`. |
| `x-timestamp` | Yes | Request timestamp used for signature and freshness validation. |
| `x-merchant-signature` | Required for unsigned/plain request bodies | Signature over the merchant id, channel id, optional sub-merchant ids, timestamp, and raw request body. Encrypted or JWS request bodies are verified through their cryptographic envelope instead. |
| `x-request-id` | No | Client request id for tracing. Newton generates one if omitted. |
| `x-session-id` | No | Client session id for tracing. Defaults to `x-request-id` when omitted. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP must be allowlisted. |

Transport expectations:

- Newton accepts `JWE`, `JWS`, and plain JSON envelope variants at the type level. Production S2S integrations should use the encryption/signing mode shared during onboarding.
- For `JWE`, the decrypted content must be a signed body; Newton verifies the nested signature before parsing the business payload.
- For `JWS`, Newton verifies the JWS using the configured merchant public key and `kid`.
- For plain/unsigned payloads, Newton verifies `x-merchant-signature`.
- Newton also checks merchant API block/allow configuration, timestamp freshness, and IP allowlisting when configured.

## Request

### Standard Merchant-Configured MIC

Use this when the original mandate is not on a dynamic VPA and the merchant's 20-character `merchantIdentifierCode` is configured in Newton.

```json
{
  "merchantRequestId": "UPDINTEROP001",
  "originalMerchantRequestId": "MANDATECREATE001",
  "remarks": "Convert mandate to interoperability",
  "udfParameters": "{\"ticket\":\"INT-1001\"}"
}
```

### Dynamic VPA With Request MIC

When the merchant has dynamic VPA enabled and the mandate payee VPA resolves as a dynamic VPA, `merchantIdentifierCode` must be sent in the request.

```json
{
  "merchantRequestId": "UPDINTEROP002",
  "originalMerchantRequestId": "MANDATECREATE002",
  "merchantIdentifierCode": "MIC12345678901234567",
  "remarks": "Dynamic VPA interoperability update"
}
```

### Minimal Request

This is accepted only when merchant configuration supplies the required MIC and the original mandate is otherwise eligible.

```json
{
  "merchantRequestId": "UPDINTEROP003",
  "originalMerchantRequestId": "MANDATECREATE003"
}
```

## Request Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Idempotency key for this update attempt. Must be 1 to 35 characters. Allowed pattern permits letters, numbers, hyphen, dot, and underscore, with at least one alphanumeric character. |
| `originalMerchantRequestId` | string | Yes | No default. | Merchant request id of the existing mandate. Same validation as `merchantRequestId`. Newton uses this field to find the mandate for the authenticated merchant. |
| `iat` | string | Conditional | No business default. | Required inside encrypted or signed payloads because the handler validates issued-at time for non-plain request bodies. Not validated by request field rules beyond timestamp validation in auth middleware. |
| `remarks` | string | No | If omitted, Newton uses its internal default remarks while creating the mandate update request. | 1 to 255 characters when supplied. Must start, after optional spaces, with a letter, number, or hyphen; subsequent characters may be letters, numbers, spaces, or hyphens. |
| `udfParameters` | string | No | No default. Echoed in the response when supplied. | Must be a JSON object encoded as a string. The string must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |
| `merchantIdentifierCode` | string | Conditional | If omitted for non-dynamic-VPA mandates, Newton falls back to `merchantIdentifierCode` from merchant configuration. | Required in the request when dynamic VPA is enabled and the mandate payee VPA is a dynamic VPA. Not allowed in the request when the mandate is not dynamic VPA. Whether supplied or configured, the final MIC must be exactly 20 characters. |

### Business Validation Rules

Newton rejects the request before calling NPCI when any of these rules fail:

- The original mandate cannot be found for the authenticated merchant or resolved sub-merchant.
- The original mandate status is `COMPLETED`, `DECLINED`, `EXPIRED`, `PENDING`, `REVOKED`, `EXECUTE_REVOKE_PENDING`, `EXECUTE_REVOKE_INITIATED`, `REVOKE_PENDING`, `FAILURE`, `TIMED_OUT`, or `DORMANT`.
- The original mandate already has interoperability purpose `AZ`.
- The original mandate purpose is not `14` or `00`.
- The original mandate transaction type is `PREPAID_VOUCHER`.
- The original mandate recurrence pattern is `ONETIME`.
- Dynamic VPA rules require `merchantIdentifierCode` in the request and it is missing.
- Non-dynamic-VPA rules disallow `merchantIdentifierCode` in the request and it is present.
- The final MIC is missing or not 20 characters.

## Success Response

The decrypted business response uses this shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "UPDINTEROP001",
    "mandateName": "Monthly subscription",
    "customerVpa": "customer@bank",
    "remarks": "Convert mandate to interoperability",
    "orgMandateId": "MANDATEUPI001",
    "originalMerchantRequestId": "MANDATECREATE001",
    "umn": "12345678901234567890123456789012@upi",
    "gatewayMandateId": "UPIUPDATE001",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Mandate interoperability_update Success",
    "gatewayResponseStatus": "SUCCESS"
  },
  "udfParameters": "{\"ticket\":\"INT-1001\"}"
}
```

For a sub-merchant call, the payload also includes `subMerchantId` and `subMerchantChannelId`:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "PARENTMERCHANT",
    "merchantChannelId": "APP",
    "merchantRequestId": "UPDINTEROP002",
    "subMerchantId": "SUBMERCHANT001",
    "subMerchantChannelId": "SUBAPP",
    "customerVpa": "customer@bank",
    "orgMandateId": "MANDATEUPI002",
    "originalMerchantRequestId": "MANDATECREATE002",
    "gatewayMandateId": "UPIUPDATE002",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate interoperability_update Request Sent Successfully",
    "gatewayResponseStatus": "PENDING"
  }
}
```

### Response Envelope Notes

The examples above are decrypted business payloads. The actual HTTP body depends on the merchant's configured response strategy:

- `JWS`: Newton returns a signed response body.
- `JWS_AND_JWE`: Newton returns an encrypted response body containing a signed response.
- Other configured strategies: Newton returns the plain business JSON wrapped as an unsigned response and sends `X-Response-Signature`.

All S2S responses include `x-requestid` and `x-sessionid` response headers. `X-Response-Signature` is present for unsigned response mode.

### Response Field Reference

Top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Transport/business wrapper status. The route sets this to `SUCCESS` when it can return a mapped mandate update result, even if the nested gateway status is `FAILURE`. |
| `responseCode` | string | Top-level API code. Success wrapper value is `SUCCESS`. |
| `responseMessage` | string | Top-level API message. Success wrapper value is `SUCCESS`. |
| `payload` | object | Mandate update result. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted otherwise. |

`payload` fields:

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated parent merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated parent merchant record. |
| `merchantRequestId` | string | Merchant idempotency key for this interoperability update attempt. |
| `subMerchantId` | string | Sub-merchant id when the call is made for a sub-merchant. Omitted otherwise. |
| `subMerchantChannelId` | string | Sub-merchant channel id when present. Omitted otherwise. |
| `mandateName` | string | Name from the original mandate, when present. |
| `customerVpa` | string | Payer/customer VPA from the original mandate. |
| `remarks` | string | Remarks stored on the mandate history for this update. |
| `orgMandateId` | string | Original mandate UPI request id. |
| `originalMerchantRequestId` | string | Original mandate's merchant request id. |
| `umn` | string | UPI mandate number when present. |
| `gatewayMandateId` | string | Generated UPI request id for the interoperability update attempt. |
| `gatewayResponseCode` | string | Gateway-mapped response code. `00` indicates success; `01` can indicate pending; other values come from NPCI response or default to `JPNL` when the gateway response has no code. |
| `gatewayResponseMessage` | string | Gateway-mapped message. For success it is `Mandate interoperability_update Success`; for pending it is `Mandate interoperability_update Request Sent Successfully`; failures use the NPCI result text or `Mandate Request Failed`. |
| `gatewayResponseStatus` | string | Gateway-mapped status: `SUCCESS`, `PENDING`, or `FAILURE`. |

## Failure Scenarios

Failure responses use the same transport mode as other S2S responses when they are produced after response wrapping is available. Some authentication, decryption, or parsing failures may be returned directly as an error JSON body. The examples below show the underlying decrypted JSON shape clients should handle.

### Request Validation Failures

Missing required JSON fields can fail during JSON parsing before business validation. Invalid field values fail Newton validation. Validation messages are built from the validation error constructors, so the exact `responseMessage` may contain constructor text such as `LengthValidation`, `RegexValidation`, or `UnexpectedType`.

Examples:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\"",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchant request id regex failed\"",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"remarks regex match failed\"",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\"",
  "payload": null
}
```

Client handling: fix the request and send a new request. Do not retry unchanged validation failures.

### Authentication, Signature, Encryption, and Timestamp Failures

Typical failure body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Invalid encrypted payload JSON can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload",
  "payload": null
}
```

Failure causes include:

- Missing `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, `x-raw-body`, or required signature headers.
- JWS signature verification failure.
- JWE decryption failure.
- JWE payload is not a signed body.
- Missing or invalid `kid`.
- Invalid `iat` for signed/encrypted payloads.
- Stale or invalid `x-timestamp`.
- Plain request body without a valid `x-merchant-signature`.

Client handling: do not retry blindly. Check keys, `kid`, timestamp clock skew, raw-body canonicalization, signature strategy, and onboarding headers.

### Merchant Configuration, API Disabled, or IP Restriction

If the API is blocked or not in the allowed API list for the merchant/sub-merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

If `whitelistedIps` is configured and the first IP in `x-forwarded-for` is missing or not allowlisted:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Client handling: confirm merchant enablement, allowed API names, blocked API configuration, sub-merchant enablement, and IP allowlist with Newton onboarding/support.

### Mandate Lookup Failures

If `originalMerchantRequestId` does not match a mandate for the authenticated merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate not found",
  "payload": null
}
```

Client handling: verify that `originalMerchantRequestId` is the original mandate creation request id, not the new update attempt id, and that the call is made with the same merchant/sub-merchant context that owns the mandate.

### Mandate State Failures

Examples:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMC",
  "responseMessage": "Mandate is already completed",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "JPMD",
  "responseMessage": "Mandate is declined by payer",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "JPMX",
  "responseMessage": "Mandate is expried due to no action by payer",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "JPMW",
  "responseMessage": "Invalid Operation , Mandate is in pending state",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "JPMR",
  "responseMessage": "Invalid Operation , Mandate is Revoked",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is inactive",
  "payload": null
}
```

Client handling: do not retry. Use mandate status APIs or callbacks to reconcile the original mandate and choose a different customer flow if needed.

### Interoperability Business Rule Failures

Examples:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantIdentifierCode is required for dynamic vpa",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantIdentifierCode not allowed",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is already interoperable",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantIdentifierCode should be length 20",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantIdentifierCode must be there for purpose AZ",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate purpose can't be interoperable",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Prepaid_Voucher Mandates can't be interoperable",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Onetime mandates can't be interoperable",
  "payload": null
}
```

Client handling: correct the request or merchant configuration if the MIC is the problem. For mandate-purpose, prepaid-voucher, already-interoperable, or one-time mandate failures, do not retry for the same original mandate.

### Gateway, Downstream, and Pending Results

Gateway failures that happen after Newton creates the update history are returned as a successful top-level API wrapper with failure details in `payload`:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "UPDINTEROP004",
    "customerVpa": "customer@bank",
    "orgMandateId": "MANDATEUPI004",
    "originalMerchantRequestId": "MANDATECREATE004",
    "gatewayMandateId": "UPIUPDATE004",
    "gatewayResponseCode": "U09",
    "gatewayResponseMessage": "NPCI timeout",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

When NPCI accepts the request but the final status is not available:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "UPDINTEROP005",
    "customerVpa": "customer@bank",
    "orgMandateId": "MANDATEUPI005",
    "originalMerchantRequestId": "MANDATECREATE005",
    "gatewayMandateId": "UPIUPDATE005",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate interoperability_update Request Sent Successfully",
    "gatewayResponseStatus": "PENDING"
  }
}
```

If NPCI returns a negative acknowledgement with a specific code, Newton maps that gateway code and result text:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "UPDINTEROP006",
    "customerVpa": "customer@bank",
    "orgMandateId": "MANDATEUPI006",
    "originalMerchantRequestId": "MANDATECREATE006",
    "gatewayMandateId": "UPIUPDATE006",
    "gatewayResponseCode": "UO8",
    "gatewayResponseMessage": "Mandate Request Failed",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

Client handling: always inspect `payload.gatewayResponseStatus`, not only top-level `status`. Treat `SUCCESS` as converted, `PENDING` as in progress and reconcile by callback/status process, and `FAILURE` as terminal unless Newton support advises otherwise.

### Unexpected/Internal Errors

Unexpected missing internal records or response mapping failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling: retry with the same `merchantRequestId` after a short backoff only if the request outcome is unknown. If repeated, escalate with `merchantRequestId`, `originalMerchantRequestId`, `x-request-id`, and timestamp.

## Retry and Idempotency Guidance

- Use `merchantRequestId` as the idempotency key for this update attempt.
- If the same `merchantRequestId` already has a terminal `INTEROPERABILITY_UPDATE` mandate history with status `SUCCESS` or `FAILURE`, Newton returns the existing terminal result instead of creating a new update.
- If the previous attempt is still non-terminal, the code path may validate and attempt processing again. Avoid aggressive retries while the first attempt is in flight.
- For network timeouts or unknown client-side failures, retry with the same `merchantRequestId` after backoff.
- For validation, auth, merchant config, lookup, and business-rule failures, fix the cause before sending another request.
- To intentionally start a separate new interoperability update attempt for the same original mandate, use a new `merchantRequestId`. This is normally unnecessary after a terminal result unless advised by Newton.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:802)
- Route handler and auth sequence: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3009)
- Request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request body extraction: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- S2S response signing/encryption: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:38)
- Payload verification and JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature, API allow/block, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4270)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:445)
- Core request/response conversion: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:440)
- Product route, lookup, and idempotent terminal-history behavior: [src/Newton/Product/Merchant/Mandate/UpdateMandateInteroperable.hs](../../src/Newton/Product/Merchant/Mandate/UpdateMandateInteroperable.hs:29)
- Interoperability business validation: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:2192)
- Internal update payload creation: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2805)
- Response mapping: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2114)
- Mandate update execution path: [src/Newton/Product/MandateV2.hs](../../src/Newton/Product/MandateV2.hs:116)
- Gateway response mapping: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:1488)
- Mandate status validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2903)
- Field validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:292)
