# VPA Availability API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/availability`

## Overview

VPA Availability is a merchant server-to-server API used to check whether one or more customer VPAs can be used before a merchant attempts VPA creation or account/VPA linking.

The API has two request modes:

- With `merchantCustomerId`: checks one candidate `customerVpa` in the context of an existing Newton merchant customer and returns customer metadata plus optional VPA suggestions.
- Without `merchantCustomerId`: checks a list of candidate `customerVpas` without customer context and returns per-VPA availability flags.

Use the customer-context mode when the customer is already onboarded and you want Newton to apply customer-specific VPA rules. Use the list mode when your backend only needs a merchant-scoped pre-check for candidate VPAs.

Payloads use the standard Newton S2S encrypted/signed request and response envelope. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

VPA Availability helps merchants:

- Check whether a customer VPA is free before calling VPA add/link APIs.
- Avoid user-facing failures during customer onboarding or VPA setup.
- Generate alternative VPA suggestions when a requested VPA is unavailable.
- Pre-check multiple candidate VPAs in one call when a merchant customer context is not yet available.
- Respect merchant VPA handle/domain configuration and mobile-number VPA restrictions.

This API only checks availability. It does not create, reserve, or link a VPA. Availability can change after a successful check, so the follow-up create/link call must still handle VPA-unavailable failures.

## Integration Flow

### With `merchantCustomerId`

1. Merchant onboards or resolves the Newton merchant customer.
2. Merchant generates a candidate `customerVpa`.
3. Merchant calls this API with `merchantCustomerId` and `customerVpa`.
4. Newton validates the S2S envelope, merchant signature, request freshness, merchant configuration, merchant customer, customer profile, and VPA format.
5. Newton returns `available: "true"` when the VPA can be used, or `available: "false"` with optional `vpaSuggestions` when it cannot.
6. Merchant proceeds to the VPA create/link flow or asks the customer to choose a suggested VPA.

### Without `merchantCustomerId`

1. Merchant prepares one or more candidate VPAs.
2. Merchant calls this API with `customerVpas`.
3. Newton validates each candidate against merchant VPA format rules and checks whether each normalized VPA already exists.
4. Newton returns `vpaResults[]` with one `available` flag per requested VPA.
5. Merchant chooses an available candidate and continues the customer/VPA setup flow.

Important behavior:

- Presence of the JSON key `merchantCustomerId` selects the single-VPA customer-context mode.
- Absence of the JSON key `merchantCustomerId` selects the list mode.
- The response uses strings `"true"` and `"false"` for availability, not JSON booleans.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/availability
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, required by merchant signature validation. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding when your request mode uses header-level merchant signatures. JWS/JWE request modes verify the payload signature through the envelope itself. |
| `x-request-id` | Optional merchant request id for tracing. Newton generates one when omitted. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Authentication and Payload Handling

The route accepts Newton's `EncRequest` envelope:

- Signed JWS.
- Encrypted JWE containing a signed payload.
- Plain JSON only where the merchant configuration permits it, protected by the S2S merchant headers and signature.

Production integrations should use the encrypted and/or signed request mode configured during onboarding. Plain JSON examples below are decrypted business payloads only.

The route first extracts and verifies the business payload, resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`, then runs merchant signature verification for the `vpaAvailabilityS2S` API. For signed/encrypted requests, `iat` in the decrypted business payload is validated for freshness. `x-timestamp` is also validated for freshness. Timestamps must be 13-digit epoch milliseconds and within the configured 30-minute freshness window.

## Request

Route request type: `API.EncRequest API.CheckVPAAvailabilityS2SRequest`

Business payload type: `API.CheckVPAAvailabilityS2SRequest`

`CheckVPAAvailabilityS2SRequest` is a two-branch type. If the decrypted JSON object contains the key `merchantCustomerId`, Newton parses it as `CheckVPAWithMCIDRequest`. Otherwise, Newton parses it as `CheckVPAWithoutMCIDRequest`.

### Required Minimum: With `merchantCustomerId`

```json
{
  "merchantCustomerId": "CUST12345",
  "customerVpa": "rahul.kumar@okbank",
  "iat": "1735689600000"
}
```

### Required Minimum: Without `merchantCustomerId`

```json
{
  "customerVpas": [
    "rahul.kumar@okbank",
    "rahul.kumar01@okbank"
  ],
  "iat": "1735689600000"
}
```

### Field Reference: With `merchantCustomerId`

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. If the key is omitted, Newton switches to the list-mode request shape instead of treating this field as missing. | Merchant's customer identifier for an existing Newton merchant customer. Must be 1 to 256 characters and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. The merchant customer must belong to the calling merchant and be active or active-by-default. |
| `customerVpa` | string | Yes | No default. | Candidate customer VPA to check. Must be 3 to 255 characters and match the generic VPA pattern `local-part@handle`. Product validation also enforces the merchant's allowed VPA handle/domain and mobile-number VPA rules. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by S2S request freshness validation. Required for signed/encrypted production requests. Plain unsigned payloads can be accepted without it only where merchant configuration permits that request mode. |
| `udfParameters` | string | No | Omitted from response when not supplied. | Merchant-defined metadata. Must be a JSON object encoded as a string, for example `"{\"journeyId\":\"JRN123\"}"`. Newton echoes it back on success. |

### Field Reference: Without `merchantCustomerId`

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `customerVpas` | array of strings | Yes | No default. An empty array is accepted and returns an empty `vpaResults` array. | Candidate customer VPAs to check. Each entry must pass the generic customer VPA validator and the merchant VPA handle/domain validator. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by S2S request freshness validation. Required for signed/encrypted production requests. |
| `udfParameters` | string | No | Omitted from response when not supplied. | Merchant-defined metadata. Must be a JSON object encoded as a string. Newton echoes it back on success. |

### Defaults and Omitted Field Behavior

- `merchantCustomerId`: branch selector. If the key is present, `customerVpa` is required. If the key is absent, `customerVpas` is required.
- `iat`: no business default. Required by the signed/encrypted request freshness layer.
- `udfParameters`: no default and omitted from the response when absent.
- `vpaSuggestions`: response-only. Omitted when the response value is empty at the type level, which is the normal available-VPA case. For an unavailable VPA, Newton can return either a suggestions array or an empty array.
- `customerVpas`: empty list is accepted and returns `vpaResults: []`.

Unknown JSON fields are ignored by normal record parsing, but the branch-specific required fields still apply. For example, sending `customerVpa` without `merchantCustomerId` does not run the single-VPA mode; Newton expects `customerVpas` because `merchantCustomerId` is absent.

## Request Examples

### Customer-Context Availability Check

```json
{
  "merchantCustomerId": "CUST12345",
  "customerVpa": "rahul.kumar@okbank",
  "iat": "1735689600000",
  "udfParameters": "{\"journeyId\":\"JRN123\"}"
}
```

### Customer-Context Check for a Mobile-Number VPA

When the VPA local part is a mobile number and matches the merchant's VPA handle, Newton validates it against the customer mobile number in the merchant-customer context.

```json
{
  "merchantCustomerId": "CUST12345",
  "customerVpa": "9876543210@okbank",
  "iat": "1735689600000"
}
```

### Multiple Candidate Check Without Customer Context

```json
{
  "customerVpas": [
    "rahul.kumar@okbank",
    "rahulkumar01@okbank",
    "rahul-kumar@okbank"
  ],
  "iat": "1735689600000",
  "udfParameters": "{\"journeyId\":\"JRN124\"}"
}
```

### Empty Candidate List

```json
{
  "customerVpas": [],
  "iat": "1735689600000"
}
```

## Validation and Processing Behavior

### Shared Validation

Newton validates:

- S2S payload/envelope and merchant identity.
- Merchant signature, request timestamp, API access, allowed/blocked API configuration, and IP whitelist when configured.
- `iat` freshness for signed/encrypted requests.
- `udfParameters` as a JSON-object string with restricted special characters.
- VPA length and generic format: `local-part@handle`, 3 to 255 characters.
- Merchant VPA handle/domain rules. The product validator accepts VPAs whose handle matches the merchant-specific VPA domain or the platform default VPA domain.

### With `merchantCustomerId`

Newton:

1. Validates `merchantCustomerId`, `customerVpa`, `iat`, and `udfParameters`.
2. Loads the merchant customer for the calling merchant.
3. Loads the customer linked to that merchant customer.
4. Validates the candidate VPA against merchant VPA rules.
5. For mobile-number VPAs, verifies that the VPA prefix maps to the customer's mobile number.
6. Checks whether the VPA is already used by another active merchant customer or customer.
7. Checks deleted/deactivated VPA restrictions that can temporarily block reuse.
8. Returns `available` and, when unavailable, optional suggestions based on the customer's latest account and merchant configuration.

Suggestion behavior:

- If `available` is `"true"`, `vpaSuggestions` is omitted.
- If `available` is `"false"`, `vpaSuggestions` can contain generated alternatives or an empty array.
- The suggestion count is limited by merchant configuration `vpaSuggestionsLimit`; the current default fallback is 3.
- Suggestions are lowercased by the response helper.

### Without `merchantCustomerId`

Newton:

1. Validates `customerVpas`, `iat`, and `udfParameters`.
2. Applies merchant VPA handle/domain validation to each VPA.
3. Skips customer mobile-number ownership validation because no customer context is available.
4. Checks whether each lowercased/normalized VPA already exists in Newton.
5. Returns one `vpaResults[]` entry for each input VPA, preserving the requested VPA text in the `vpa` field.

Merchant configuration `blockMobileVpa = true` makes 10-digit mobile-number VPAs unavailable. This is returned as `available: "false"`, not as a failure response.

### VPA Normalization

Availability checks compare both direct VPA values and normalized VPA values. Normalization lowercases the VPA and removes characters outside letters, numbers, `@`, and space. As a result, visually different VPAs such as `rahul-kumar@okbank` and `rahulkumar@okbank` can conflict after normalization.

## Response

Route response type: `RespHeaders (API.EncResponse API.CheckVPAAvailabilityS2SResponse)`

Business response type: `API.CheckVPAAvailabilityS2SResponse`

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API wrapper status. Success value is `SUCCESS`. |
| `responseCode` | string | Wrapper response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Wrapper response message. Success value is `SUCCESS`. |
| `payload` | object | Availability result. Shape depends on whether the request used `merchantCustomerId`. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when absent. |

### Payload Fields: With `merchantCustomerId`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Echoed merchant customer id from the request. |
| `customerMobileNumber` | string | Trimmed mobile number from the Newton customer profile. |
| `available` | string | `"true"` if the candidate VPA can be used for this merchant customer; `"false"` otherwise. |
| `vpaSuggestions` | array of strings | Optional suggested VPAs. Present only when Newton generated a suggestions list. Can be an empty array. |

### Payload Fields: Without `merchantCustomerId`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `vpaResults` | array of objects | Per-VPA availability results. Present on success, including as an empty array when `customerVpas` is empty. |

### `vpaResults[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Candidate VPA from the request. |
| `available` | string | `"true"` if the candidate VPA appears available; `"false"` if it is blocked by merchant configuration or an existing normalized VPA record. |

## Success Response Examples

### Customer-Context Response: Available

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "available": "true"
  },
  "udfParameters": "{\"journeyId\":\"JRN123\"}"
}
```

### Customer-Context Response: Unavailable With Suggestions

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "available": "false",
    "vpaSuggestions": [
      "rahulkumar01@okbank",
      "rahul9876@okbank",
      "kumar321@okbank"
    ]
  }
}
```

### Customer-Context Response: Unavailable With No Suggestions

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "available": "false",
    "vpaSuggestions": []
  }
}
```

### Multiple Candidate Response Without Customer Context

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "vpaResults": [
      {
        "vpa": "rahul.kumar@okbank",
        "available": "false"
      },
      {
        "vpa": "rahulkumar01@okbank",
        "available": "true"
      },
      {
        "vpa": "rahul-kumar@okbank",
        "available": "false"
      }
    ]
  },
  "udfParameters": "{\"journeyId\":\"JRN124\"}"
}
```

### Empty Candidate List Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "vpaResults": []
  }
}
```

## Failure Responses

Failure responses use the same configured S2S response transport as success responses when Newton can construct a response body. After decryption, most failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\""
}
```

`payload` is usually omitted when empty. HTTP status can vary by layer: many business validation failures are returned with an encrypted response body and HTTP 200, some product validation failures use HTTP 400, and authentication/decryption failures use HTTP 401. Clients should inspect decrypted `status`, `responseCode`, and `responseMessage` whenever a response body is available.

### JSON Shape or Missing Field Failure

Occurs when the decrypted payload cannot be parsed into the selected branch.

If `merchantCustomerId` is absent and `customerVpas` is also absent, Newton parses the request as list mode and the JSON parser reports the missing field. Parser wording can vary by runtime and response layer; a representative response is:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Error in $.customerVpas: key \"customerVpas\" not found"
}
```

If `merchantCustomerId` is present but `customerVpa` is absent:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Error in $.customerVpa: key \"customerVpa\" not found"
}
```

Client handling: fix the request shape. Do not send both shapes at once; choose single-VPA mode or list mode explicitly.

### Request Validation Failure

Occurs when fields parse but fail Newton validation.

Invalid `merchantCustomerId` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

Invalid `merchantCustomerId` characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
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

Invalid VPA length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"customerVpa length is not between 3 and 255\""
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

When multiple fields fail validation, Newton joins the individual validation messages with commas.

Client handling: correct the payload and regenerate the S2S envelope/signature before retrying.

### Authentication, Signature, Encryption, or API Access Failure

Occurs when merchant headers are missing, merchant id/channel id is invalid, the request signature does not match, the JWS/JWE envelope cannot be verified, the source IP is not whitelisted, or the API is blocked/not allowed for the merchant.

Generic authentication failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API disabled or not present in `allowedApiNames`:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Missing or invalid key id in a JWE/JWS header can surface as invalid data. The exact capitalization of `KID`/`kId` depends on the envelope branch:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding kId"
}
```

Malformed signed payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: not enough input"
}
```

Client handling: fix server-side credentials, key ids, allowed API configuration, IP allowlisting, and request signing. Regenerate `iat`, `x-timestamp`, signature, and encrypted/signed body before retrying.

### Timestamp or Request Freshness Failure

Occurs when `x-timestamp` or signed/encrypted request `iat` is missing, malformed, or outside the freshness window.

Missing `iat` in a signed/encrypted request:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Malformed timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Client handling: generate a fresh request envelope with current timestamps. Do not replay stale signed/encrypted payloads.

### Merchant Customer or Customer Lookup Failure

Applies only to requests that include `merchantCustomerId`.

Unknown, inactive, or wrong-merchant `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Merchant customer has no active customer binding:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Linked customer cannot be loaded:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
}
```

Client handling: refresh or recreate the customer/merchant-customer mapping before retrying. If the request was intended to be list mode, remove `merchantCustomerId` and send `customerVpas`.

### VPA Business Validation Failure

The generic request-level VPA regex can pass while product-level validation rejects the VPA because the handle/domain is not configured for the merchant, the VPA has an invalid local-part shape for that handle, or a mobile-number VPA does not match the customer mobile number in customer-context mode.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "vpa is not valid"
}
```

Normalized/deactivated VPA conflicts can surface as:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Normalized VPA already exists"
}
```

Many unavailable VPA cases are not failures. They return a successful wrapper with `available: "false"` or a `vpaResults[]` item with `available: "false"`.

Client handling: for `"vpa is not valid"`, correct the VPA handle or local part. For `"Normalized VPA already exists"` or successful `"available": "false"`, choose another VPA or use the returned suggestions.

### Internal Configuration or Dependency Failure

Unexpected missing internal configuration, missing passetto hash key, encryption/decryption failures while building suggestions or response data, Redis/DB failures, or other unhandled dependency failures can surface as:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry later with the same business payload and fresh S2S timestamps/signature. If repeated, contact Newton support with merchant id, merchant channel id, `merchantCustomerId` if supplied, request timestamp, and `x-request-id`.

## Retry, Idempotency, and Client Handling

- This API does not accept a merchant request id or create an idempotency record.
- The API does not reserve the VPA. Treat availability as a point-in-time signal and handle a later VPA-create failure if another request claims the VPA first.
- If a call times out before a decrypted response is available, retry the same business payload with new `iat`, `x-timestamp`, and signature/envelope.
- If the response is `SUCCESS` with `available: "true"`, proceed to the VPA create/link flow promptly.
- If the response is `SUCCESS` with `available: "false"`, do not retry the same VPA expecting a different result. Choose a new VPA or one of `vpaSuggestions`.
- If the list-mode response contains mixed availability, use only entries with `available: "true"`.
- Do not retry validation, VPA-format, auth, timestamp, merchant-customer, or API-access errors until the input or configuration is fixed.
- Retry `INTERNAL_SERVER_ERROR` only with the same business payload and fresh S2S auth material. Escalate repeated failures to Newton support.

## Source References

- API route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:303)
- Route handler and middleware chain: [Core.hs](../../src/Newton/App/Routes/Core.hs:3895)
- Request body extraction: [Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Request/response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload/envelope verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature and timestamp verification: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp freshness validation: [DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Request and response types: [Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:309)
- Sum-type branch selection: [Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:380)
- S2S transformer branch: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:896)
- Product flow with `merchantCustomerId`: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1026)
- Product flow without `merchantCustomerId`: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1044)
- Success response builders: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1700)
- Request validation wrapper: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Merchant customer id and VPA validators: [Common.hs](../../src/Newton/Validation/Common.hs:125)
- UDF parameters validator: [Common.hs](../../src/Newton/Validation/Common.hs:275)
- Product VPA format and mobile-number VPA validation: [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2701)
- VPA suggestion post-processing and limit: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:92)
- VPA availability and suggestion logic: [VpaV2.hs](../../src/Newton/Product/VpaV2.hs:702)
- VPA normalization helper: [Vpa.hs](../../src/Newton/Storage/QueriesMiddleware/Vpa.hs:66)
- Error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
