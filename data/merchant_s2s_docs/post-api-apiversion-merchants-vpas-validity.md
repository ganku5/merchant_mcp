# VPA Validity API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/validity`

## Overview

VPA Validity is a merchant server-to-server API used to verify whether a customer, payee, merchant, UPI-number mapper, voucher, or dynamic VPA can be resolved before the merchant continues a UPI payment or onboarding journey.

The merchant sends the VPA to be validated as `customerVpa`. Newton authenticates the S2S request, optionally resolves the merchant customer context, validates the request fields, checks on-us records where possible, and calls NPCI `ReqValAdd` for off-us VPAs. The response tells the merchant whether the target VPA is valid and returns the resolved account or merchant display metadata when available.

Payloads use the standard Newton S2S encrypted/signed request and response envelope. Examples in this guide show decrypted business payloads for readability.

Important distinction: an invalid target VPA is usually not an API failure. When Newton/NPCI processes the lookup and concludes that the VPA is invalid, the API still returns top-level `SUCCESS` with `payload.isCustomerVpaValid = false`. Failure responses are reserved for malformed requests, authentication/signature failures, expired timestamps, merchant/customer setup failures, and downstream timeout/bad-response cases.

## Business Use Case

VPA Validity helps merchants:

- Confirm that a payee or customer-entered UPI VPA exists before showing it for confirmation.
- Resolve a display name for the VPA so the customer can confirm the intended recipient.
- Identify merchant VPAs through `isMerchant`, `mcc`, `merchantType`, and `isMerchantVerified`.
- Validate `@mapper.npci` UPI-number mapper addresses where the local part is a supported UPI number.
- Support payment journeys that need NPCI VPA validation context before initiating send-money, collect, mandate, or delegate flows.
- Reduce failed downstream payment attempts caused by mistyped or stale VPAs.
- Echo merchant-defined `udfParameters` so merchants can correlate the validation with their own journey/session.

This API only validates/resolves the VPA at the time of the call. It does not reserve the VPA, create a payment, create a mandate, register an intent, or guarantee that a later payment authorization will succeed.

## Integration Flow

1. Merchant collects or derives the target VPA to validate.
2. Merchant prepares the decrypted business payload with `customerVpa` and optional context fields.
3. Merchant wraps the payload in the Newton S2S transport configured during onboarding: JWE, JWS, or merchant-signed plain JSON where enabled.
4. Merchant calls `POST /api/{apiVersion}/merchants/vpas/validity` with merchant identity, timestamp, and signature/envelope headers.
5. Newton unwraps the request, resolves the merchant, verifies signature/envelope, checks API allow/block configuration, checks timestamp freshness, and enforces IP allowlisting when configured.
6. If `merchantCustomerId` is supplied, Newton resolves the active merchant-customer and linked customer profile and uses that context during validation.
7. Newton validates the decrypted business payload.
8. Newton trims `customerVpa`, detects `@mapper.npci` UPI-number addresses, then validates on-us, voucher/dynamic, or off-us NPCI paths.
9. Newton returns a success payload with `isCustomerVpaValid`, resolved name, VPA, merchant/account metadata, and optional risk/feature metadata based on `x-api-version`.
10. Merchant decrypts/verifies the response and uses `payload.isCustomerVpaValid` as the business result.

Recommended client decision:

- Continue the journey only when `status = "SUCCESS"` and `payload.isCustomerVpaValid = true`.
- Treat `status = "SUCCESS"` with `payload.isCustomerVpaValid = false` as a completed lookup with an invalid or unresolved VPA.
- Treat top-level `status = "FAILURE"` as an API/request/platform failure and follow the retry guidance below.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/validity
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API route version assigned during onboarding. The handler for this endpoint does not branch directly on the path value; response shaping is controlled by `x-api-version`. |

### Headers

Use the headers and key material shared during Newton S2S onboarding.

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | Response-version selector. If omitted or not an integer, Newton uses version `0`. Use `2` or higher when you want both `featureTags` and `diuRisk` returned where available. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. Used to resolve the authenticated merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Conditional | Required only for configured sub-merchant flows. |
| `x-sub-merchant-channel-id` | Conditional | Required only for configured sub-merchant flows. |
| `x-timestamp` | Yes | Current 13-digit epoch milliseconds timestamp used for merchant signature and replay validation. Must be within 30 minutes of Newton server time. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain business payload transport. JWS/JWE transports use the configured signed/encrypted envelope; the route does not verify this header for those transports. |
| `x-forwarded-for` | Conditional | Required when the merchant is configured with `whitelistedIps`; Newton checks the first IP in the comma-separated value. |
| `Authorization` | Conditional | Send only when required by the merchant's onboarding profile. |
| `x-request-id` | No | Optional tracing id. Newton generates one when omitted. |

### Authentication and Payload Handling

The route accepts Newton's standard `EncRequest` transport:

| Transport mode | Request body shape | Authentication behavior |
| --- | --- | --- |
| Plain business JSON | Decrypted business payload directly. | Allowed only when configured. Newton verifies `x-merchant-signature` over merchant ids, optional sub-merchant ids, `x-timestamp`, and the raw body. |
| JWS | `payload`, `signature`, and `protected`. | Newton extracts `kid` from `protected`, verifies the JWS signature, base64url-decodes `payload`, and parses the business JSON. |
| JWE | `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`. | Newton decrypts the JWE, expects a signed JWS payload inside it, then verifies and parses that signed payload. |

For JWS/JWE requests, include `iat` in the decrypted business payload. Newton validates `iat` as a 13-digit epoch milliseconds timestamp within the same 30-minute freshness window. For plain unsigned payloads, `iat` is not required by this route, but `x-timestamp` is still required and checked.

The route authenticates against the API name `verifyVpa`. Merchant configuration can block or allow APIs by this name.

## Request

Route request type: `API.EncRequest TfS2S.VpaValidityRequest`.

Business payload type: `TfS2S.VpaValidityRequest`.

### Required Minimum

Validate a standard VPA:

```json
{
  "customerVpa": "rahul.kumar@okbank"
}
```

Validate a VPA in the context of an existing merchant customer:

```json
{
  "customerVpa": "rahul.kumar@okbank",
  "merchantCustomerId": "CUST12345"
}
```

Signed or encrypted production payloads should include a fresh `iat`:

```json
{
  "customerVpa": "rahul.kumar@okbank",
  "merchantCustomerId": "CUST12345",
  "iat": "1783000000000"
}
```

Generate `iat` and `x-timestamp` at request time. The values above illustrate the required 13-digit epoch-milliseconds format.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `customerVpa` | string | Yes | No default. | Target VPA to validate. Newton trims leading/trailing whitespace before product processing. Must be 3 to 255 characters and match `local-part@handle` with letters, numbers, dot, or hyphen in each part. For UPI-number mapper validation, send the mapper address form such as `9876543210@mapper.npci`. |
| `payerVpa` | string | No | If omitted, Newton derives the payer address from merchant/customer context for off-us NPCI validation. | Optional payer/source VPA used as context in the NPCI `ReqValAdd` request for off-us validation. Must pass the same generic VPA format validation. |
| `purposeCode` | string | No | No default. Standard VPA validation should omit it. | Optional two-character uppercase alphanumeric purpose code. Purpose codes `87` and `59` select delegate-flow behavior; `BH` selects IoT behavior. e-RUPI/voucher-style purpose codes are not recommended on this endpoint because this request type cannot send `amount`, `umn`, or `initiationMode`; use `validity360` for those flows. |
| `merchantCustomerId` | string | No | If omitted, Newton validates in merchant context only and does not bind `MerchantCustomerKey`/`CustomerKey`. | Merchant's customer profile id. If supplied, it must be 1 to 256 characters and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`; it must resolve to an active merchant-customer profile under the authenticated merchant. |
| `mobileNumber` | string | Conditional | No default. | Required for delegate-flow validation where `purposeCode` is `87` or `59`. Must be a 12-digit numeric mobile number when no country-code field exists, for example `919876543210`. |
| `iat` | string | Conditional | Required for JWS/JWE transports. Ignored by this route for plain unsigned payloads. | Issued-at timestamp in epoch milliseconds. Must be a 13-digit timestamp within 30 minutes of Newton server time. |
| `udfParameters` | object or string | No | Omitted from response when omitted from request. | Merchant-defined metadata. Accepts either a JSON object or a JSON-object string. It must parse as an object and avoid characters rejected by the shared UDF validator, including `/`, `#`, `-`, `(`, `)`, `*`, `!`, `%`, `~`, and the backtick character. Echoed in the top-level success response. |

There are no nested business request objects for this API. The only nested request objects are the standard JWS/JWE transport envelopes.

### Defaults and Omitted Field Behavior

- `customerVpa`: required at type level. It is trimmed before validation/resolution logic, but the request validator still requires the original value to match the VPA regex.
- `payerVpa`: optional. If omitted on off-us validation, Newton uses the resolved customer VPA when `merchantCustomerId` is present and available; otherwise it uses the merchant account VPA.
- `merchantCustomerId`: optional. When present, the authentication middleware resolves and stores merchant-customer and customer context before product logic. Invalid or inactive profiles fail the API before VPA validation.
- `purposeCode`: optional. Omission means standard VPA validation.
- `mobileNumber`: optional for standard validation; required in practice for delegate purpose flows.
- `iat`: no business default. It is transport-required for JWS/JWE requests and ignored for plain unsigned requests.
- `udfParameters`: no default and not stored by this API; echoed when supplied and valid.
- Response `featureTags`: omitted for `x-api-version <= 0`; included for `x-api-version > 0`, often as an empty array when no tags are available.
- Response `diuRisk`: omitted for `x-api-version <= 1`; included for `x-api-version > 1` when fraud-risk lookup returns a value.

Unknown JSON fields are ignored by normal record parsing, but required fields and validators still apply.

## Request Examples

### Standard VPA Validation

```json
{
  "customerVpa": "rahul.kumar@okbank",
  "udfParameters": {
    "journeyId": "JRN12345"
  }
}
```

### VPA Validation With Merchant Customer Context

```json
{
  "customerVpa": "rahul.kumar@okbank",
  "merchantCustomerId": "CUST12345",
  "iat": "1783000000000",
  "udfParameters": {
    "orderId": "ORDER12345"
  }
}
```

### VPA Validation With Explicit Payer VPA

Use this when Newton has enabled a flow where NPCI validation should use the payer/source VPA you supply instead of deriving it from merchant/customer context.

```json
{
  "customerVpa": "merchant.payee@okbank",
  "payerVpa": "customer.payer@okbank",
  "merchantCustomerId": "CUST12345",
  "iat": "1783000000000"
}
```

### UPI-Number Mapper Validation

When `customerVpa` uses `@mapper.npci`, Newton validates the local part as a UPI number and runs the UPI-number resolution path.

```json
{
  "customerVpa": "9876543210@mapper.npci",
  "merchantCustomerId": "CUST12345",
  "iat": "1783000000000"
}
```

### Delegate-Flow VPA Validation

Send `mobileNumber` when using delegate purpose codes. The mobile number must be 12 numeric digits.

```json
{
  "customerVpa": "delegatee@okbank",
  "purposeCode": "87",
  "mobileNumber": "919876543210",
  "merchantCustomerId": "CUST12345",
  "iat": "1783000000000"
}
```

## Validation and Processing Behavior

### Request Validation

Newton validates the decrypted business payload after authentication:

- `customerVpa` must be 3 to 255 characters and match `^[a-zA-Z0-9.-]{1,}@[a-zA-Z0-9.-]{1,}$`.
- `payerVpa`, when supplied, must pass the same VPA length and regex rules.
- `purposeCode`, when supplied, must be exactly 2 characters and match `^[A-Z0-9]+$`.
- `merchantCustomerId`, when supplied, must be 1 to 256 characters and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`.
- `mobileNumber`, when supplied, must be exactly 12 numeric digits.
- `udfParameters`, when supplied, must be either a JSON object or a JSON-object string and pass Newton's restricted-character regex.
- If `customerVpa` is an `@mapper.npci` address, the local part is additionally validated as a UPI number: 10 digits are accepted when numeric; 8 to 10 digit non-mobile UPI numbers must be numeric, must not start with `0`, and must not have the same last three digits.

When request validation fails, Newton returns `BAD_REQUEST` with a comma-joined list of serialized validation errors. The exact `responseMessage` can contain one or more field errors depending on the submitted payload.

### Authentication and Merchant Context

Before product validation, Newton:

- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- Resolves and validates optional sub-merchant headers.
- Verifies JWS/JWE payloads or merchant signature for plain payloads.
- Validates `iat` for JWS/JWE requests.
- Validates `x-timestamp` for all request modes, except a configured checksum bypass in limited non-production environments.
- Checks merchant `blockedApiNames` and `allowedApiNames` for API name `verifyVpa`.
- Checks `x-forwarded-for` against `whitelistedIps` when configured.
- If `merchantCustomerId` is present, resolves the merchant-customer under the authenticated merchant and resolves the linked active customer.

### Product Processing

After request validation, Newton:

1. Trims `customerVpa`.
2. If the VPA handle is `mapper.npci`, validates and extracts the local UPI number.
3. Calls the core VPA verification wrapper using API service `verifyVpa`.
4. Checks cached VPA-resolution data where merchant VPA caching is enabled and the request is not a delegate flow.
5. For on-us VPAs in Newton's configured VPA domains, checks merchant accounts, customer VPAs, mandates, delegate VPAs, IoT VPAs, and dynamic VPA rules from local records.
6. For off-us VPAs, builds an NPCI `ReqValAdd` request using merchant/customer context and calls NPCI.
7. Converts the verification result into the S2S response payload.

### Valid vs Invalid VPA Semantics

`payload.isCustomerVpaValid` is derived only from the final verification code:

- `true` when the core verification code is `00`.
- `false` for other resolvable verification codes, such as an invalid/unregistered VPA, missing on-us primary account mapping, inactive/deregistered UPI number, delegate mobile mismatch, or NPCI response failure code.

For these business-invalid results, the top-level response remains:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS"
}
```

The older `validity` response does not expose the underlying NPCI/gateway response code for invalid VPA results. Use `payload.isCustomerVpaValid`, `customerName`, and optional metadata to decide the next client action. If your integration needs gateway response status/code/message, use `POST /api/{apiVersion}/merchants/vpas/validity360` where enabled.

### Merchant and Feature Metadata

Newton sets merchant-related response fields from the verification result:

- `isMerchant` is `true` when `mcc` is present and not `0000`.
- `isMerchantVerified` is derived from Newton's verified-merchant check and defaults to `false` when unavailable.
- `merchantType` is returned when the VPA verification result includes merchant info and the calling merchant has not disabled Verify VPA V2 response metadata.
- `featureTags` are split from a pipe-separated internal feature string into an array.
- `diuRisk` is read from fraud-risk lookup for the requested `customerVpa` and calling merchant.

`ifsc`, `iin`, `mcc`, and `merchantType` can be suppressed by merchant store configuration `disableVerifyVpaV2Response = true`.

### UPI-Number Mapper Behavior

For `customerVpa` values like `9876543210@mapper.npci`, Newton:

- Validates `9876543210` as a UPI number.
- Checks the UPI-number mapper table unless merchant configuration `skipUpiNumberMapperTable` disables that local check.
- If the mapper is active, resolves the mapped VPA and validates it on-us.
- If the mapper is inactive or deregistered but not expired, returns an invalid-VPA success response.
- If the mapper is missing or eligible for fallback, calls NPCI off-us as a mapper validation.

### Purpose-Code-Specific Behavior

For standard VPA validation, omit `purposeCode`.

When `purposeCode` is supplied:

- `87` or `59`: delegate flow. Newton uses delegate-specific VPA handling and expects `mobileNumber` where a mobile link is needed.
- `BH`: IoT payment flow. Newton checks secondary-device mapping for on-us VPAs.
- e-RUPI/voucher-style purpose codes matching one letter plus one non-zero digit, such as `A1`, trigger voucher-specific validation paths. This legacy `validity` request type does not include `amount`, `umn`, or `initiationMode`, so merchants should use `validity360` for voucher validation instead.

## Response

Route response type: `RespHeaders (API.EncResponse TfS2S.VpaValidityResponse)`.

Business response type: `TfS2S.VpaValidityResponse`.

Successful decrypted business responses use this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API wrapper status. Success value is `SUCCESS`. |
| `responseCode` | string | Wrapper response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Wrapper response message. Success value is `SUCCESS`. |
| `payload` | object | VPA validity result. Always present on success. |
| `udfParameters` | object or string | Echo of request `udfParameters`; omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `isCustomerVpaValid` | boolean | `true` only when verification code is `00`; `false` when the VPA was checked but not considered valid. |
| `customerVpa` | string | Resolved VPA returned by verification. Falls back to the requested `customerVpa` when the resolver does not return a VPA. |
| `customerName` | string | Resolved/masked account or merchant name when available. Empty string when unavailable. |
| `isMerchant` | boolean | `true` when the resolved VPA has an MCC and the MCC is not `0000`. |
| `isMerchantVerified` | boolean | Newton verified-merchant flag. Defaults to `false` when unavailable. |
| `ifsc` | string | Resolved IFSC when available and not suppressed by merchant configuration. Omitted otherwise. |
| `iin` | string | Resolved bank code/IIN when available and not suppressed by merchant configuration. Omitted otherwise. |
| `mcc` | string | Resolved merchant category code when available and not suppressed by merchant configuration. Omitted otherwise. |
| `merchantType` | object | NPCI/Newton merchant-info object when available and not suppressed by merchant configuration. Shape can include `Identifier`, `Name`, `Ownership`, or `Invoice` sections depending on source data. |
| `featureTags` | array of strings | Feature support tags. Included only when `x-api-version > 0`. Empty array means no tags were available. |
| `diuRisk` | string | Fraud-risk indicator for the requested VPA and merchant. Included only when `x-api-version > 1` and a value is available. |

## Success Response Examples

### Valid Person VPA

Response shown for `x-api-version: 2`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "isCustomerVpaValid": true,
    "customerVpa": "rahul.kumar@okbank",
    "customerName": "RAHUL KUMAR",
    "isMerchant": false,
    "isMerchantVerified": false,
    "ifsc": "HDFC0001234",
    "iin": "607152",
    "mcc": "0000",
    "featureTags": [
      "01",
      "02"
    ],
    "diuRisk": "LOW"
  },
  "udfParameters": {
    "journeyId": "JRN12345"
  }
}
```

### Valid Merchant VPA

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "isCustomerVpaValid": true,
    "customerVpa": "store123@okbank",
    "customerName": "NEWTON TEST STORE",
    "isMerchant": true,
    "isMerchantVerified": true,
    "ifsc": "HDFC0001234",
    "iin": "607152",
    "mcc": "5411",
    "merchantType": {
      "Identifier": {
        "merchantType": "LARGE",
        "merchantGenre": "ONLINE",
        "onBoardingType": "AGGREGATOR"
      },
      "Name": {
        "brand": "NEWTON TEST STORE",
        "legal": "NEWTON TEST STORE PRIVATE LIMITED"
      }
    },
    "featureTags": [
      "01"
    ],
    "diuRisk": "LOW"
  }
}
```

`merchantType` is a JSON value sourced from merchant/account metadata or NPCI response. Its exact nested fields vary by merchant and network data.

### Invalid Or Unresolved VPA

The API call succeeded, but the VPA was not valid.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "isCustomerVpaValid": false,
    "customerVpa": "unknown.user@okbank",
    "customerName": "",
    "isMerchant": false,
    "isMerchantVerified": false,
    "featureTags": []
  }
}
```

Do not retry this unchanged as a platform failure. Ask the customer to correct the VPA or choose a different payee.

### Base Response Version

When `x-api-version` is omitted or is not an integer, Newton uses version `0`. `featureTags` and `diuRisk` are omitted even if internally available.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "isCustomerVpaValid": true,
    "customerVpa": "rahul.kumar@okbank",
    "customerName": "RAHUL KUMAR",
    "isMerchant": false,
    "isMerchantVerified": false,
    "ifsc": "HDFC0001234",
    "iin": "607152",
    "mcc": "0000"
  }
}
```

## Error Handling

Failure responses use the same Newton response transport as success responses. After decryption, failures generally have this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "customerVpa regex failed"
}
```

Some layers include `"payload": null`; clients should not depend on either presence or absence of `payload` in failure bodies.

HTTP status can be `200`, `400`, `401`, or `500` depending on the failing layer. Always use decrypted `status`, `responseCode`, and `responseMessage` for business handling.

### Request Validation Failure

Returned when the decrypted business payload fails `VpaValidityRequest` validation. Multiple errors are comma-joined in `responseMessage`; examples below show single-field failures.

Invalid `customerVpa` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\""
}
```

Invalid `customerVpa` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"customerVpa length is not between 3 and 255\""
}
```

Invalid `payerVpa`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"payerVpa regex failed\""
}
```

Invalid `purposeCode`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"Purpose Code length is not 2\""
}
```

Invalid `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Invalid `mobileNumber`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mobile length is not equal to 12\""
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

Invalid `@mapper.npci` UPI number:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"Upi Number should be between 8 to 10 digits\""
}
```

### Timestamp Failures

`iat` or `x-timestamp` is not a 13-digit epoch milliseconds timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

`iat` or `x-timestamp` is older/newer than the 30-minute freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Missing `iat` in a JWS/JWE request:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

### Authentication, Signature, and API Access Failures

Missing or invalid merchant headers, invalid merchant id/channel id, invalid plain-payload signature, failed JWS verification, failed JWE decryption, or failed IP allowlist:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not present in merchant `allowedApiNames`:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Signed/encrypted payload missing or failing `kid` lookup can surface as invalid data:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding KID"
}
```

Signed payload JSON parse failure returns the parse message in `responseMessage`; exact parser text depends on the malformed payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"customerVpa\" not found"
}
```

### Merchant Customer or Customer Resolution Failure

Returned when `merchantCustomerId` is supplied but does not resolve to an active merchant-customer profile for the authenticated merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Returned when the linked customer is missing/inactive:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
}
```

Returned when the merchant-customer record does not have a customer id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

### Merchant Account or Context Failure

Off-us NPCI validation needs a payer/source address. If no `payerVpa` is supplied, Newton derives it from merchant/customer context. Missing merchant account or customer VPA setup can fail before the NPCI call.

No merchant default account:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

No customer address in merchant-customer context:

```json
{
  "status": "FAILURE",
  "responseCode": "invalid details",
  "responseMessage": "Address not found"
}
```

No customer account name in merchant-customer context:

```json
{
  "status": "FAILURE",
  "responseCode": "invalid details",
  "responseMessage": "Name not found"
}
```

### Downstream NPCI or Wrapper Failure

NPCI timeout code `U09` is converted to gateway timeout for this endpoint:

```json
{
  "status": "FAILURE",
  "responseCode": "GATEWAY_TIMEOUT",
  "responseMessage": "Timed out from NPCI"
}
```

NPCI/wrapper timeout with another timeout code:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_91",
  "responseMessage": "NPCI service is not reachable at the moment (91)"
}
```

NPCI response marked as error without a usable error code:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

Decode failures or unexpected missing async response state can return an internal server error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Voucher/e-RUPI Purpose-Code Failures

This endpoint can enter voucher-specific logic when `purposeCode` looks like an e-RUPI purpose code, but the request type lacks the fields needed for complete voucher validation. Use `validity360` for voucher validation.

Invalid or expired voucher id:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid VoucherId"
}
```

Voucher amount validation failure:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid Amount"
}
```

Missing voucher amount on this legacy request shape can also surface as an internal server error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Do not retry unchanged requests when `status = "SUCCESS"` and `payload.isCustomerVpaValid = false`. The lookup completed and the VPA should be treated as invalid or unresolved.
- Do not retry validation failures, malformed JSON/envelope failures, invalid `merchantCustomerId`, API-not-enabled failures, IP allowlist failures, or authentication/signature failures until the request/configuration is corrected.
- Regenerate `iat`, `x-timestamp`, and the request signature/envelope before retrying any request. Reusing an old signed payload can fail freshness validation.
- Retry `GATEWAY_TIMEOUT`, `SERVICE_UNAVAILABLE_NPCI_*`, and transient `INTERNAL_SERVER_ERROR` responses with bounded exponential backoff and jitter.
- If a timeout occurs, retrying this validation API is safe because it does not create a transaction, mandate, reservation, or persistent business mutation. Cache any positive validation result only for a short window because VPA/account status can change.
- For user-facing flows, show the resolved `customerName` and require customer confirmation before initiating payment. Never treat the name as proof that a later payment will succeed.
- For merchant/payee risk decisions, use `isMerchant`, `isMerchantVerified`, `mcc`, `merchantType`, `featureTags`, and `diuRisk` only when present. Their presence depends on VPA type, network response, merchant configuration, and `x-api-version`.
- Use `validity360` instead of this endpoint when your integration needs gateway response code/status/message, amount-aware voucher validation, `upiRequestId`, `amount`, `umn`, `initiationMode`, or enriched 360 response fields.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:158)
- Route handler and middleware chain: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1681)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:264)
- Request validation instance: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:289)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:613)
- S2S request/response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:876)
- Core product route: [src/Newton/Product/Merchant/Vpa/VerifyVpa.hs](../../src/Newton/Product/Merchant/Vpa/VerifyVpa.hs:18)
- Core response transformer: [src/Newton/Product/Merchant/Vpa/Transformer.hs](../../src/Newton/Product/Merchant/Vpa/Transformer.hs:55)
- Verify VPA wrapper and failure semantics: [src/Newton/Utils/BusinessLogic/VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:68)
- Downstream timeout/error handling: [src/Newton/Utils/BusinessLogic/VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:227)
- VPA verification product logic: [src/Newton/Product/VpaV2.hs](../../src/Newton/Product/VpaV2.hs:115)
- On-us/off-us selection: [src/Newton/Product/VpaV2.hs](../../src/Newton/Product/VpaV2.hs:216)
- UPI-number mapper handling: [src/Newton/Product/VpaV2.hs](../../src/Newton/Product/VpaV2.hs:230)
- NPCI `ReqValAdd` response handling: [src/Newton/Product/VpaV2.hs](../../src/Newton/Product/VpaV2.hs:580)
- Generic request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Request-body validation error wrapper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API allowlist/IP/timestamp middleware: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp validation: [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
