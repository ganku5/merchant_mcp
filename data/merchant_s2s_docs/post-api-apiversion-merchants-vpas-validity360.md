# VPA Validity360 API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/validity360`

## Overview

VPA Validity360 is a server-to-server API used to validate a UPI VPA and return enriched verification details from Newton's VPA verification wrapper. In addition to the validated VPA/name details, the response can include merchant classification, IFSC/IIN, UPI-number mapping, account type, amount/global-address details returned by the verification provider, feature tags, and risk information.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

Use this API when the merchant backend needs a direct VPA verification call before initiating a payment, mandate, delegate payment, account-routing, or risk decision. This API is not a debit or collect request; it only verifies and enriches the payee/customer VPA.

## Business Use Case

VPA Validity360 helps merchants:

- Check whether a VPA can be resolved before presenting or submitting a UPI payment flow.
- Retrieve the registered payee name returned by the VPA verification provider.
- Distinguish merchant VPAs from customer VPAs using MCC and merchant-verification indicators.
- Resolve UPI-number mapper VPAs, such as `9876543210@mapper.npci`, to the underlying `upiNumber`.
- Pass transaction context such as purpose, initiation mode, amount, UMN, mobile number, and payer VPA to the VPA verification provider where required.
- Support delegate payment validation, where delegate purpose codes require the delegate mobile number.
- Store `gatewayTransactionId`, gateway response code/message, and risk/feature details for reconciliation and downstream decisioning.

Important identifiers:

- `upiRequestId`: Merchant-generated UPI request id for this verification call. Newton returns it as `payload.gatewayTransactionId`.
- `vpa`: VPA to verify. For `@mapper.npci` VPAs, Newton validates the VPA id as a UPI number and returns it in `payload.upiNumber`.
- `merchantCustomerId`: Optional merchant customer id. If supplied, Newton uses it for request logging and merchant-customer context in the S2S middleware.

## Integration Flow

1. Merchant backend creates a unique `upiRequestId` for the VPA verification attempt.
2. Merchant prepares the decrypted business payload with `vpa`, `upiRequestId`, and any optional transaction context.
3. Merchant signs/encrypts the request using the Newton S2S integration process.
4. Merchant calls `POST /api/{apiVersion}/merchants/vpas/validity360`.
5. Newton decrypts/verifies the S2S envelope, loads the merchant from request headers, validates request freshness and API access, and validates the business payload.
6. Newton calls the VPA verification wrapper service configured as `vpaValidity360`.
7. Newton maps provider result code `00` to `payload.gatewayResponseStatus: "SUCCESS"` and all other provider result codes to `payload.gatewayResponseStatus: "FAILURE"`.
8. Merchant decrypts the response and reads the outer API status plus the nested gateway response fields.

The outer API response can be `SUCCESS` even when the verified VPA is invalid or the provider returns a non-`00` result. In that case, inspect `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/validity360
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. Use `2` or higher if your integration consumes `diuRisk`; use `1` or higher if it consumes `featureTags`. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Optional. Send only when your integration uses sub-merchant headers for this flow. |
| `x-sub-merchant-channel-id` | Optional. Send only when your integration uses sub-merchant headers for this flow. |
| `x-timestamp` | 13-digit epoch milliseconds within Newton's freshness window. |
| `x-merchant-signature` | Required for plaintext/unsigned envelope integrations. Signature input includes merchant ids, timestamp, and raw body. |
| `x-request-id` | Optional merchant-generated request id for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Depending on merchant configuration, the request body can be plaintext, JWS, or JWE:

- JWE request body fields: `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`.
- JWS request body fields: `payload`, `signature`, `protected`.
- Plaintext business payloads are supported by the generic route type but are normally limited to configured plaintext or test integrations.

For signed or encrypted requests, include `iat` in the decrypted business payload. Newton validates `iat` before product logic. `iat` and `x-timestamp` must be 13-digit epoch milliseconds within the accepted clock-skew window.

Newton responses follow the merchant's configured response strategy:

- `JWS`: signed response envelope.
- `JWS_AND_JWE`: signed then encrypted response envelope.
- Other configured strategies: plaintext business response with `X-Response-Signature`.

Response headers include `x-requestid`, `x-sessionid`, and, for plaintext response strategies, `X-Response-Signature`.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the value shared during onboarding. The response transformer uses this version to omit or include some optional fields. |

## Request

### Required Minimum

At API decode level, the decrypted business payload requires `vpa` and `upiRequestId`; signed/encrypted production requests also require `iat` through the S2S verification layer.

```json
{
  "vpa": "payee@upi",
  "upiRequestId": "VPAVAL360000001",
  "iat": "1782967530000"
}
```

For delegate payment validation, send the delegate purpose code and `mobileNumber`:

```json
{
  "vpa": "delegatee@upi",
  "upiRequestId": "VPAVAL360000002",
  "purposeCode": "87",
  "mobileNumber": "919876543210",
  "payerVpa": "payer@upi",
  "iat": "1782967530000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `vpa` | string | Yes | No default. | VPA to verify. Must be 3 to 255 characters and match `^[a-zA-Z0-9.-]+@[a-zA-Z0-9.-]+$`. The field is validated with the customer VPA validator. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated request id for this VPA verification call. Must be 1 to 35 alphanumeric characters. Returned as `payload.gatewayTransactionId`. |
| `iat` | string | Conditional | No business default. Required for JWS/JWE requests; ignored for plaintext request validation. | Issued-at timestamp used by the S2S signature/encryption validation layer. Send a 13-digit epoch-millisecond timestamp within the accepted freshness window. |
| `udfParameters` | string | No | No default. If omitted, it is omitted from the response. | Merchant-defined JSON object encoded as a string. Must parse as a JSON object and must not contain the disallowed characters rejected by `udfParametersTextValidation`. Echoed at the top level of the response when supplied. |
| `payerVpa` | string | No | No default. | Payer VPA context passed to the VPA verification wrapper. Must pass VPA format validation when supplied. |
| `purposeCode` | string | No | No default. | Two-character uppercase alphanumeric UPI purpose code. Purpose codes `87` and `59` are treated as delegate flows and require `mobileNumber`. |
| `mobileNumber` | string | Conditional | No default. | Required when `purposeCode` is `87` or `59`. Must be a 12-digit numeric mobile number when supplied without a country-code field; use the format shared during onboarding, commonly `91` plus 10-digit mobile number. |
| `initiationMode` | string | No | No default. | Two-character alphanumeric UPI initiation mode. Passed to the VPA verification wrapper when supplied. |
| `amount` | string | No | No default. | Amount context for verification. Must be in two-decimal format, for example `100.00`, and greater than `0.0` when supplied. |
| `umn` | string | No | No default. | UMN context for mandate-related verification. Must be 34 to 70 characters and match the UMN validator when supplied. |
| `merchantCustomerId` | string | No | No default. | Merchant's customer identifier. Must be 1 to 256 characters and match the merchant-customer-id validator when supplied. Used in logging and to load merchant-customer/customer context in the S2S middleware. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not generated by this API.

- `vpa` and `upiRequestId`: required by the request type. Missing or `null` values are rejected during JSON decode.
- `iat`: nullable in the business type but required by the S2S layer for signed/encrypted requests.
- `allowMultibank`: not a client field. The S2S transformer sets it to `true` internally before calling core product logic.
- `merchantCustomerId`: optional. If omitted, Newton still verifies the VPA but does not load merchant-customer/customer context from this field.
- `mobileNumber`: optional except for delegate purpose codes `87` and `59`.
- `upiNumber`: not a request field. It is derived only when `vpa` uses the `@mapper.npci` handle.
- Unknown extra fields: ignored by JSON parsing and not included in the core request.
- Optional fields omitted or sent as `null`: not passed to the wrapper unless product logic explicitly derives a value.

### Nested Request Objects

There are no nested JSON objects in the decrypted request body. `udfParameters`, when used, is a JSON object encoded as a string.

## Request Examples

### Standard VPA Verification

```json
{
  "vpa": "payee@upi",
  "upiRequestId": "VPAVAL360000001",
  "iat": "1782967530000"
}
```

### VPA Verification With Payment Context

```json
{
  "vpa": "merchant@bank",
  "upiRequestId": "VPAVAL360000003",
  "payerVpa": "customer@upi",
  "purposeCode": "00",
  "initiationMode": "00",
  "amount": "100.00",
  "udfParameters": "{\"orderId\":\"ORDER12345\"}",
  "merchantCustomerId": "CUST12345",
  "iat": "1782967530000"
}
```

### Delegate Flow Verification

```json
{
  "vpa": "delegatee@upi",
  "upiRequestId": "VPAVAL360000004",
  "payerVpa": "delegator@upi",
  "purposeCode": "87",
  "mobileNumber": "919876543210",
  "amount": "50.00",
  "iat": "1782967530000"
}
```

### UPI Number Mapper VPA

```json
{
  "vpa": "9876543210@mapper.npci",
  "upiRequestId": "VPAVAL360000005",
  "iat": "1782967530000"
}
```

For this request, Newton validates `9876543210` using UPI-number rules and, when accepted, returns `"upiNumber": "9876543210"` in the response payload.

## Validation and Processing Behavior

Before product logic, Newton:

1. Parses the body as a Newton S2S envelope or plaintext business payload.
2. Finds and loads the merchant using `x-merchant-id` and `x-merchant-channel-id`; optional sub-merchant headers are also resolved when supplied.
3. Decrypts JWE or verifies JWS where applicable.
4. Validates `iat` for signed/encrypted requests.
5. Runs `merchantSignatureVerificationV2`, which validates merchant API access, blocked/allowed API configuration, IP allowlist if configured, `x-timestamp`, and plaintext request signature where applicable.
6. Runs the request-field validation for `VpaValidity360Request`.

Business validation and processing:

1. If `vpa` uses handle `mapper.npci`, Newton validates the VPA id as a UPI number and stores it as `upiNumber` for the response.
2. If `purposeCode` is `87` or `59`, Newton requires `mobileNumber` before calling the wrapper.
3. Newton calls `verifyVpaFromWrapperForMerchant` with `vpa`, merchant details, `upiRequestId`, derived `upiNumber`, service name `vpaValidity360`, and the optional context fields.
4. Newton considers provider/wrapper result code `00` a gateway success and maps it to `gatewayResponseStatus: "SUCCESS"` and `gatewayResponseCode: "00"`.
5. Newton maps any other provider/wrapper result code to `gatewayResponseStatus: "FAILURE"` and preserves the provider code as `gatewayResponseCode`.
6. If the wrapper reports an NPCI timeout, Newton returns an API-level failure instead of a success envelope.
7. Newton calculates `isMerchant` from the returned MCC. MCC values other than `0000` are treated as merchant VPAs.
8. Newton returns `isMerchantVerified`, `mcc`, and `merchantType` only for merchant VPAs.
9. Newton looks up FRI/DIU risk for the requested `vpa` and merchant and returns it as `diuRisk` when the requested API version allows it.

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | API response code. Success value is `SUCCESS`. |
| `responseMessage` | string | API response message. Success value is `SUCCESS`. |
| `payload` | object | VPA verification result. Present on successful API processing, even when the nested gateway status is `FAILURE`. |
| `udfParameters` | string | Echoed from request when supplied. Omitted otherwise. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `gatewayTransactionId` | string | `upiRequestId` from the request. |
| `gatewayResponseStatus` | string | Gateway-level VPA verification status. `SUCCESS` when provider code is `00`; otherwise `FAILURE`. |
| `gatewayResponseCode` | string | Provider/wrapper response code. `00` indicates verified/success. Missing provider codes are mapped to `JP91` by the response transformer. |
| `gatewayResponseMessage` | string | Provider/wrapper user message. Defaults to `Vpa verification failed` when the wrapper does not send a message. |
| `vpa` | string | VPA returned by the wrapper. Falls back to the requested `vpa` when the wrapper does not return one. |
| `name` | string | Registered payee/customer name returned by the wrapper, when available. |
| `ifsc` | string | IFSC returned by the wrapper, when available. |
| `iin` | string | IIN/bank code returned by the wrapper, when available. |
| `isMerchant` | string | Text boolean, `true` or `false`. `true` when MCC is present and not `0000`. |
| `isMerchantVerified` | string | Text boolean for verified-merchant status. Returned only when `isMerchant` is `true`. |
| `mcc` | string | Merchant category code. Returned only when `isMerchant` is `true`. |
| `merchantType` | object/string/number | Merchant type/category value returned by the wrapper for merchant VPAs. Shape depends on the wrapper response. |
| `upiNumber` | string | Derived UPI number when the request VPA handle is `mapper.npci`; omitted otherwise. |
| `accType` | string | Account type returned by the wrapper, for example `SAVINGS` or `CURRENT`, when available. |
| `amount` | string | Amount returned by the wrapper, when available. This is not necessarily the request amount. |
| `globalAddress` | string | Global address returned by the wrapper, when available. |
| `featureTags` | array of strings | Feature tags returned by the wrapper. Included only when `x-api-version > 0`; omitted for version `0`. |
| `mobileNumber` | string | Request `mobileNumber`, echoed in the payload when supplied. |
| `diuRisk` | string | Risk level returned by Newton's risk lookup. Included only when `x-api-version > 1`; omitted for version `0` and `1`. |

Optional payload fields use `omitNothingFields`; if the value is unavailable or filtered by API version, the field is omitted from the JSON response.

### Example Success Response: Verified Merchant VPA

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "gatewayTransactionId": "VPAVAL360000003",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "vpa": "merchant@bank",
    "name": "ACME RETAIL",
    "ifsc": "HDFC0001234",
    "iin": "123456",
    "isMerchant": "true",
    "isMerchantVerified": "true",
    "mcc": "5411",
    "merchantType": {
      "merchantGenre": "ONLINE"
    },
    "accType": "CURRENT",
    "featureTags": [
      "UPI"
    ],
    "diuRisk": "LOW"
  },
  "udfParameters": "{\"orderId\":\"ORDER12345\"}"
}
```

### Example Success Response: Customer VPA

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "gatewayTransactionId": "VPAVAL360000001",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "vpa": "payee@upi",
    "name": "PAYEE NAME",
    "ifsc": "HDFC0001234",
    "iin": "123456",
    "isMerchant": "false",
    "accType": "SAVINGS",
    "featureTags": [
      "UPI"
    ],
    "diuRisk": "LOW"
  }
}
```

### Example Success Response With Gateway Failure

A non-`00` provider response is not always an API failure. The outer response can be `SUCCESS` while the nested gateway result is `FAILURE`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "gatewayTransactionId": "VPAVAL360000006",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "ZH",
    "gatewayResponseMessage": "Vpa verification failed",
    "vpa": "unknown@upi",
    "isMerchant": "false",
    "featureTags": [],
    "diuRisk": "HIGH"
  }
}
```

Client handling: treat this as a completed verification call with an invalid/unresolved VPA result. Do not retry automatically unless the response code/message indicates a transient provider issue agreed during onboarding.

### Example Success Response: UPI Number Mapper

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "gatewayTransactionId": "VPAVAL360000005",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "vpa": "9876543210@mapper.npci",
    "name": "PAYEE NAME",
    "isMerchant": "false",
    "upiNumber": "9876543210",
    "featureTags": []
  }
}
```

## Response Versioning

The route does not branch the overall response shape by version, but the transformer filters some optional payload fields:

| `x-api-version` | Response behavior |
| --- | --- |
| `0` | `featureTags` is omitted. `diuRisk` is omitted. |
| `1` | `featureTags` can be returned. `diuRisk` is omitted. |
| `2` and higher | `featureTags` and `diuRisk` can be returned when values are available. |

Use the API version shared during onboarding. If your integration depends on `diuRisk`, use version `2` or higher.

## Failure Scenarios

Failure responses use the same encrypted/signed response transport as successful responses when the merchant context and response strategy are available. The examples below show decrypted business bodies.

HTTP status can vary by deployment and failure layer; some product validations return an error body with HTTP `200`, while authentication/envelope/timestamp failures can return `400`, `401`, or `500`. Clients should read decrypted `status`, `responseCode`, and `responseMessage`.

### Malformed JSON or Request Envelope

Returned when the HTTP request body cannot be parsed as a valid Newton S2S request envelope or when the signed payload decodes to invalid JSON.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.vpa: key \"vpa\" not found"
}
```

The exact Aeson field path and text vary with the missing or malformed field. Example missing `upiRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.upiRequestId: key \"upiRequestId\" not found"
}
```

Client handling: fix the JSON/envelope and resend with a new `upiRequestId` unless you are retrying the same logical verification request.

### Missing or Invalid `iat`

For signed/encrypted requests, `iat` is required by the S2S layer even though the business type is nullable.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

If the timestamp format is invalid:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

If the timestamp is outside the accepted freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Client handling: regenerate `iat`, `x-timestamp`, the envelope, and the signature before retrying. Do not replay a stale encrypted/signed request body.

### Missing Merchant Headers

Returned when Newton cannot resolve required merchant headers such as `x-merchant-id`, `x-merchant-channel-id`, or required timestamp/signature headers.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: correct the header set and signature input. This is an integration/configuration error, not a VPA-verification outcome.

### Signature or Encryption Verification Failure

Returned when plaintext `x-merchant-signature` verification fails, JWS verification fails, JWE decryption fails, or the configured key id cannot be used.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

For a malformed or missing JWS/JWE `kid`, the request can fail before authorization with an invalid-data body such as:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding kId"
}
```

Client handling: verify key id, key version, payload signing, encryption, and raw-body signature construction. Retry with a newly signed/encrypted body.

### API Not Enabled or Blocked for Merchant

Returned when merchant configuration blocks this API or the merchant's allowed API list does not include `vpaValidity360`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: do not retry automatically. Ask Newton operations/onboarding to enable the API for the merchant profile.

### IP Allowlist Failure

If the merchant has configured whitelisted IPs and the request source from `x-forwarded-for` is absent or not allowed, Newton rejects the call.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: send from an allowlisted egress IP or update the merchant allowlist through the standard onboarding process.

### Invalid `vpa`

Returned when `vpa` does not pass VPA format validation.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\""
}
```

For a length violation:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"customerVpa length is not between 3 and 255\""
}
```

Client handling: ask the customer or upstream system for a corrected VPA. Do not retry the same invalid value.

### Invalid `upiRequestId`

Returned when `upiRequestId` is blank, longer than 35 characters, or contains non-alphanumeric characters.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\""
}
```

Length failures return the same body shape with:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"upiRequestId length is not between 1 and 35\""
}
```

Client handling: generate a valid 1 to 35 character alphanumeric id.

### Invalid Optional Context Fields

Validation errors are combined when multiple fields fail. The response message contains the Haskell validation constructor text. Representative examples:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"payerVpa regex failed\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"Purpose Code length is not 2\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"initiationMode regex match failed\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mobile length is not equal to 12\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Client handling: fix field format locally before retrying. These are deterministic request-validation failures.

### Delegate Purpose Missing `mobileNumber`

Returned when `purposeCode` is `87` or `59` and `mobileNumber` is absent.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "mobileNumber Not Found For purpose Just \"87\""
}
```

For purpose code `59`, the message contains `Just "59"` instead. Client handling: resend with the delegate mobile number in the onboarded format.

### Invalid UPI Number Mapper VPA

Returned when `vpa` uses `@mapper.npci` but the VPA id is not a valid UPI number.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"Upi Number should be between 8 to 10 digits\""
}
```

Other mapper validation messages include `Upi Number is not a valid number input`, `Upi Number starts with zero`, and `Upi Number contains same last 3 digits`.

Client handling: ask for a valid UPI number or use the customer's normal VPA.

### NPCI or Wrapper Timeout

If the wrapper indicates an NPCI timeout, Newton returns a service-unavailable failure.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "NPCI service is not reachable at the moment (U09)"
}
```

If the wrapper does not provide a timeout code, the suffix and message code can be `NA`.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Client handling: retry with a fresh `upiRequestId` or retry the same logical verification according to the retry policy agreed during onboarding. Keep retries bounded.

### Invalid Response From NPCI or Wrapper

Returned when the wrapper reports an error but does not include a usable error code.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

Client handling: treat as a transient provider/integration failure. Retry later or reconcile with Newton support if persistent.

### Internal Server, Database, Cache, or Response-Signing Failure

Unexpected runtime failures, missing runtime options, database/cache errors, response signing/encryption failures, or risk lookup failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with a fresh envelope using bounded backoff. If the issue persists, raise the `upiRequestId`, `x-request-id`, merchant id, and timestamp to Newton support.

## Retry and Client Handling Guidance

- Generate a unique `upiRequestId` for each verification attempt. Store it with the merchant order/customer action for support and logs.
- For network timeouts with no decrypted response, retry with a freshly generated `iat`, `x-timestamp`, signature, and encrypted/signed envelope.
- Do not retry deterministic validation failures such as invalid VPA, invalid amount format, invalid `upiRequestId`, or missing delegate `mobileNumber`; fix the request first.
- Do not treat outer `status: "SUCCESS"` as proof that the VPA is valid. Always inspect `payload.gatewayResponseStatus` and `payload.gatewayResponseCode`.
- For `payload.gatewayResponseStatus: "FAILURE"` with a stable non-`00` code such as `ZH`, show a corrected-entry flow to the user rather than blind retries.
- For `SERVICE_UNAVAILABLE_*`, `BAD_RESPONSE_FROM_NPCI`, or `INTERNAL_SERVER_ERROR`, retry with bounded backoff if the business flow still needs verification.
- For authentication, timestamp, API-not-enabled, or IP-allowlist failures, fix the integration/configuration issue before retrying.
- For delegate payment purpose codes `87` and `59`, always send `mobileNumber`; without it the API fails before calling the wrapper.

## Source References

- Route type: [Core.hs](../../src/Newton/App/Routes/Core.hs:168)
- Route handler: [Core.vpaValidity360](../../src/Newton/App/Routes/Core.hs:1717)
- Server-to-server request and response types: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:342)
- Server-to-server transformer route: [ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:622)
- S2S request/response transformer helpers: [ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:879)
- Core product request and response payload types: [Vpa/Types.hs](../../src/Newton/Product/Merchant/Vpa/Types.hs:146)
- Core product route and delegate mobile validation: [Validity360.hs](../../src/Newton/Product/Merchant/Vpa/Validity360.hs:22)
- Response payload builder: [Vpa/Transformer.hs](../../src/Newton/Product/Merchant/Vpa/Transformer.hs:112)
- VPA wrapper response validation: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:227)
- VPA wrapper call: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:68)
- UPI-number mapper extraction: [VpaV2.hs](../../src/Newton/Product/VpaV2.hs:882)
- Request validators: [Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- S2S request envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Request decryption and payload verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API access verification: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- S2S response signing/encryption wrapper: [RoutesHelper.flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:38)
- Timestamp validation: [DateTime.isValidTimestamp](../../src/Newton/Utils/DateTime.hs:108)
- Success and common error constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
