# Deregister Customer API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/deregister`

## Overview

Deregister Customer is a server-to-server API used to remove or delink a customer's Newton UPI profile for a merchant.

The merchant calls this API when a customer closes their UPI profile, withdraws consent, changes their mobile/profile relationship, needs to be re-onboarded cleanly, or needs a specific merchant/app profile delinked. Newton validates the merchant, identifies the customer by `merchantCustomerId` or mobile number, checks blocking business rules such as active mandates, active UPI Lite, and active delegate links, then soft-deletes or delinks the applicable customer profile data.

Use this API only after the customer has completed the merchant-side action that authorizes deregistration or profile delinking.

## Business Use Case

Deregister Customer helps merchants:

- Remove a customer's merchant UPI profile when the customer opts out or closes the profile.
- Clear existing VPA, account-linking, contact, and device-binding state before a new onboarding journey.
- Delink a merchant/customer profile without deleting every customer-level relationship where the `delink` mode supports that behavior.
- Delink selected child/app profiles for partner or P2M SDK configurations.
- Prevent deregistration while active mandates, active UPI Lite accounts, or active delegate links would make profile removal unsafe.

Do not call this API as a routine cleanup step after every transaction. Call it only for explicit profile-removal, customer-consent withdrawal, re-onboarding, or configured delink flows.

## Integration Flow

1. Merchant identifies the customer profile to deregister.
2. Merchant sends either `merchantCustomerId` or, for eligible non-multibank flows, `customerMobileNumber` with `countryCode`.
3. Merchant optionally sends `delink` to request a narrower delink mode instead of the default deregistration behavior.
4. Newton verifies the encrypted/signed S2S envelope, merchant headers, API access configuration, timestamp, and request body.
5. Newton validates customer/profile lookup and checks active mandates, active UPI Lite, and active delegate links where applicable.
6. Newton soft-deletes or delinks the applicable profile data and returns `SUCCESS` when the requested state is achieved.
7. Merchant updates its customer-profile cache and prevents further UPI actions on the deregistered profile unless the customer is onboarded again.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. Required for multibank-enabled deregister flows.
- `customerMobileNumber`: Alternate lookup key for eligible non-multibank flows.
- `delink`: Optional mode that changes the scope of deregistration.
- `appIds[]`: Optional selected merchant/app profiles to delink. Used only with `delink: "PROFILE"`.

## Handler Path

The route is mounted under `/api/{apiVersion}` in `ServerToServerAPIs`. Unlike many transformer-backed S2S APIs, this endpoint does not call a named `TfS2S.*TransformerRoute`. The Core route handler decodes the S2S envelope with `getReqBody`, verifies merchant signature/API access through `merchantSignatureVerificationV2`, calls `MerchantV2.deregisterCustomerRoute` directly, and builds the success response with `mkDeRegisterCustomerResponse`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/deregister
```

Payloads use the standard Newton server-to-server request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit Unix timestamp in milliseconds. |
| `x-merchant-signature` | Required for unsigned-body signature mode. For JWS/JWE modes, signature/encryption is carried in the request envelope. |
| `x-api-version` | Use the version shared during onboarding. The traced deregister flow does not add response-version-specific fields. |
| `x-request-id` | Optional request id for troubleshooting and reconciliation. Newton generates one if omitted. |
| `x-session-id` | Optional session id. Defaults to `x-request-id` when omitted. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Production integrations should send the configured signed or encrypted envelope. For signed/encrypted requests, `iat` in the decrypted business payload is required and must be a valid timestamp.

## Request

### Required Minimum

For multibank-enabled merchants, send `merchantCustomerId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "iat": "1719835200000"
}
```

For eligible non-multibank merchants, send either `merchantCustomerId` or a mobile-number lookup:

```json
{
  "countryCode": "91",
  "customerMobileNumber": "9876543210",
  "iat": "1719835200000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Conditional | No default. Omitted only for eligible non-multibank mobile-number lookup flows. | Merchant's customer identifier. Required when the merchant has deregister enabled for multibank. Length must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `countryCode` | string | Conditional | No default. If omitted with `customerMobileNumber`, validation expects a 12-digit numeric mobile value. | Country code for `customerMobileNumber`. May include a leading `+`. Length must be at most 7 digits after validation. For India, use `91` or `+91`. |
| `customerMobileNumber` | string | Conditional | No default. Required when `merchantCustomerId` is omitted. | Customer mobile number used for non-multibank lookup. For domestic numbers, send a 10-digit mobile with `countryCode: "91"` or `"+91"`, or send a 12-digit `91`-prefixed number when omitting `countryCode`. |
| `delink` | string | No | If omitted, Newton performs the default deregistration for the target merchant customer profile. | Optional delink mode. Allowed values are `CUSTOMER`, `PROFILE`, `FASTAG`, and `TRANSACTIONAL_PROFILE`. Send only a value enabled for your merchant use case. |
| `appIds` | array of objects | Conditional | No default. Ignored by the core flow unless `delink` is `PROFILE`; rejected for some P2M SDK child-merchant configurations. | Selected merchant/app profiles to delink. Use only with `delink: "PROFILE"` where Newton has enabled this partner/app delink flow. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Missing `iat` is rejected before business logic for signed/encrypted requests. | Issued-at timestamp used by request verification. Send a 13-digit Unix timestamp in milliseconds within the allowed clock-skew window. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in the success response. The value must parse as a JSON object string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not returned when omitted.

- `merchantCustomerId`: Mandatory for multibank-enabled deregister. For non-multibank, Newton accepts `merchantCustomerId` or `customerMobileNumber`.
- `customerMobileNumber`: Normalized before lookup. Domestic mobile inputs are stored/processed as country-code-prefixed values, for example `919876543210`.
- `delink`: Omitted means default deregistration of the target profile. This removes the profile's UPI state after business-rule checks.
- `appIds`: Use only with `delink: "PROFILE"`. When sent with selected app profiles, the response contains only the app ids that Newton actually delinked.
- `iat`: Required by signature verification for signed/encrypted calls even though the request type allows null.
- `udfParameters`: Echoed on success only when supplied.

### Delink Modes

| `delink` value | Behavior |
| --- | --- |
| Omitted | Default deregistration for the target merchant customer. Newton checks mandates, UPI Lite, and delegate links, then removes the profile's VPA/account/contact/device-binding state as applicable. |
| `CUSTOMER` | Customer-level deregistration mode. Newton preserves the merchant customer record where the internal flow requires it, while removing applicable UPI customer state after active mandate, UPI Lite, and delegate-link checks. |
| `PROFILE` | Profile delink mode. Without `appIds`, Newton delinks the current merchant profile and checks active UPI Lite for that profile. With `appIds`, Newton delinks only the selected app profiles that are eligible; app profiles with active mandates are skipped and are not returned in `payload.appIds`. |
| `FASTAG` | FASTag-specific delink mode. Newton limits VPA deletion to FASTag-restricted VPAs and preserves other profile state where configured. |
| `TRANSACTIONAL_PROFILE` | Transactional-profile delink mode. Newton removes transactional VPA/profile state and unbinds the profile device while preserving configured non-transactional profile state. |

### Nested Request Objects

#### `appIds[]`

Use `appIds` only with `delink: "PROFILE"` and only when Newton has enabled selected app/profile delinking for your merchant.

| Field | Type | Required | Description |
| --- | --- | --- |
| `merchantId` | string | Yes | Merchant id of the app/profile to delink. Newton resolves it with `merchantChannelId`. |
| `merchantChannelId` | string | Yes | Merchant channel id of the app/profile to delink. |

## Request Examples

### Default Deregistration By Merchant Customer Id

```json
{
  "merchantCustomerId": "CUST12345",
  "iat": "1719835200000",
  "udfParameters": "{\"reason\":\"customer_closed_profile\"}"
}
```

### Non-Multibank Deregistration By Mobile Number

```json
{
  "countryCode": "91",
  "customerMobileNumber": "9876543210",
  "iat": "1719835200000"
}
```

### Profile Delink For Selected App Profiles

```json
{
  "merchantCustomerId": "CUST12345",
  "delink": "PROFILE",
  "appIds": [
    {
      "merchantId": "APP_MERCHANT_1",
      "merchantChannelId": "APP_CHANNEL_1"
    },
    {
      "merchantId": "APP_MERCHANT_2",
      "merchantChannelId": "APP_CHANNEL_2"
    }
  ],
  "iat": "1719835200000"
}
```

### FASTag-Specific Delink

```json
{
  "merchantCustomerId": "CUST12345",
  "delink": "FASTAG",
  "iat": "1719835200000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Deregistration result. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton for the calling merchant. |
| `merchantChannelId` | string | Merchant channel id configured with Newton for the calling merchant. |
| `merchantCustomerId` | string | Echoed from the request when supplied. Omitted when the request used only `customerMobileNumber`. |
| `customerMobileNumber` | string | Customer mobile number associated with the deregistered profile, with leading zero padding removed. For India domestic flows this is commonly returned as `91` plus the 10-digit mobile number. |
| `appIds` | array of objects | Present only when selected app/profile delinking returns app ids. Contains app profiles Newton actually delinked; skipped profiles are not included. |

### `payload.appIds[]`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id of the delinked app/profile. |
| `merchantChannelId` | string | Merchant channel id of the delinked app/profile. |

### Example Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210"
  },
  "udfParameters": "{\"reason\":\"customer_closed_profile\"}"
}
```

### Mobile-Number Lookup Success Response

When `merchantCustomerId` is not sent, it is not returned.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "customerMobileNumber": "919876543210"
  }
}
```

### Selected App/Profile Delink Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "appIds": [
      {
        "merchantId": "APP_MERCHANT_1",
        "merchantChannelId": "APP_CHANNEL_1"
      }
    ]
  }
}
```

In this example, only `APP_MERCHANT_1` was delinked. If another requested app profile had an active mandate, Newton skips it and omits it from `payload.appIds`.

## Retry and Idempotency

This API does not take a merchant-generated idempotency key. Treat the operation target as `merchantCustomerId` or, for eligible non-multibank flows, the normalized `customerMobileNumber`.

- Multibank-enabled deregister by `merchantCustomerId` is idempotent for already-inactive merchant customer or customer records: Newton can return `SUCCESS` when the desired deregistered state is already present.
- Non-multibank retries against an already inactive profile can return `DUPLICATE_REQUEST` or a lookup failure instead of `SUCCESS`.
- Retry network timeouts or unknown transport outcomes with the exact same payload and identifiers.
- Do not retry validation, authentication, API access, active mandate, active UPI Lite, or active delegate-link failures until the underlying issue is fixed.
- After a retry returns `SUCCESS`, reconcile your local profile state from the latest response and block further UPI actions until the customer is onboarded again.
- If selected `appIds` are used, treat `payload.appIds` as the list of profiles actually delinked, not as an echo of every requested app id.

## Error Handling

Failure bodies follow the standard Newton error response shape after decoding/decryption where applicable:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantCustomerId or mobileNumber is mandatory"
}
```

Clients should read `status`, `responseCode`, and `responseMessage` from the body. Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, or `500`; the body is the stable integration contract.

Authentication, signature, and encryption failures can happen before the deregister business payload is processed. In those cases Newton returns the standard error body for that layer, for example `UNAUTHORIZED`.

### Validation Failures

| Scenario | Decrypted response body |
| --- | --- |
| Non-multibank request omits both `merchantCustomerId` and `customerMobileNumber` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"merchantCustomerId or mobileNumber is mandatory"}` |
| Multibank-enabled request omits `merchantCustomerId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"merchantCustomerId is mandatory for Multibank"}` |
| `merchantCustomerId` is empty or longer than 256 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` |
| `merchantCustomerId` contains unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| `countryCode` has unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"countryCode regex match not found\""}` |
| `countryCode` is longer than 7 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"countryCode length greater than 7\""}` |
| `countryCode` is omitted and `customerMobileNumber` is not 12 digits | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"mobile length is not equal to 12\""}` |
| `countryCode` is supplied and `customerMobileNumber` is longer than 18 digits | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"mobile length is greater then 18\""}` |
| `customerMobileNumber` fails request validation | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"mobileNumber regex match not found\""}` |
| Domestic mobile cannot be normalized | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mobile number validation failed for domestic"}` |
| International mobile cannot be normalized | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mobile number validation failed for international"}` |
| `udfParameters` is not a valid JSON-object string or contains disallowed characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| Signed/encrypted request omits `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| `iat` or `x-timestamp` is not a 13-digit millisecond timestamp | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` |
| `iat` or `x-timestamp` is outside the allowed clock-skew window | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` |

### Authentication, Encryption, and Merchant Configuration Failures

| Scenario | Decrypted response body |
| --- | --- |
| Missing merchant headers, invalid merchant credentials, signature mismatch, invalid IP whitelist, or JWE decryption failure | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| API is blocked or not in the merchant's allowed API list | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| Encrypted payload cannot be parsed after decryption | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: not enough input"}` |

### Lookup and Business Failures

| Scenario | Decrypted response body |
| --- | --- |
| `merchantCustomerId` does not resolve to a merchant customer profile | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"User profile not found"}` |
| Merchant customer exists but is already inactive in a non-multibank flow | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| Merchant customer has no linked customer id | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer"}` |
| Mobile-number lookup cannot find an active customer profile | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| P2M SDK child-merchant request does not use `delink: "PROFILE"` or sends `appIds` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"DELINK is mandatory. No appId allowed."}` |
| `delink: "PROFILE"` with `appIds` references merchants Newton cannot resolve | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Merchant not found"}` |
| `delink: "PROFILE"` with `appIds` has no matching merchant customer records for the customer | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"MerchantCustomer not found"}` |
| Active mandates block deregistration | `{"status":"FAILURE","responseCode":"JPDL","responseMessage":"You have active mandate(s), deregistration is not allowed. Please deregister after all the mandates are executed or revoke existing mandates before deregistering."}` |
| Active UPI Lite account blocks deregistration | `{"status":"FAILURE","responseCode":"JPLA","responseMessage":"You have an active UPI LITE Account, de-registration is not allowed. Please de-register yourself after the UPI LITE account is de-registered."}` |
| Active delegate links block deregistration | `{"status":"FAILURE","responseCode":"JPDA","responseMessage":"You have active delegate links, deregistration is not allowed. Please remove all the delegate links before deregistering."}` |

For some PSP modes or delink modes, active-mandate failures can use a PSP-specific response code such as `JPMN1` or `JPMN2` with the same active-mandate guidance.

### Downstream and Unexpected Failures

The deregistration helper passes through explicit error codes/messages returned by the internal deregister checks. If a check returns an error code and message, Newton returns them as a failure body:

```json
{
  "status": "FAILURE",
  "responseCode": "JPDA",
  "responseMessage": "You have active delegate links, deregistration is not allowed. Please remove all the delegate links before deregistering."
}
```

If an internal deregister check reports an error without an error code/message, or an unexpected database, cache, encryption, or server failure occurs, clients can receive:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Retry `INTERNAL_SERVER_ERROR` only with the same payload. If repeated attempts fail, stop retries and reconcile with Newton support using `x-request-id`, `merchantCustomerId`, and the timestamp.

## Source References

- Route API prefix and `{apiVersion}` capture: [NewtonAPIs](../../src/Newton/App/Routes/Core.hs:112)
- Route definition: [ServerToServerAPIs](../../src/Newton/App/Routes/Core.hs:310)
- Route handler and signature flow: [deregister](../../src/Newton/App/Routes/Core.hs:2003)
- S2S request decode and payload verification: [getReqBody](../../src/Newton/Utils/Routes.hs:40), [merchantPayloadVerificationS2S](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- S2S envelope and response wrapping: [EncRequest and EncResponse](../../src/Newton/Types/API/RequestBody.hs:48), [flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Signature, API access, and `iat` checks: [merchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Product route and multibank rules: [deregisterCustomerRoute](../../src/Newton/Product/MerchantV2.hs:765)
- Request and response types: [DeregisterRequest](../../src/Newton/Types/API/ServerToServer/Customer.hs:521), [DeregisterResponse](../../src/Newton/Types/API/ServerToServer/Customer.hs:578)
- Nested request enums/types: [MerchantIds](../../src/Newton/Types/Intermediate.hs:699), [Delink](../../src/Newton/Types/Intermediate.hs:787)
- Core deregistration flow: [callDeregister](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1220), [deregisterMerchantCustomer](../../src/Newton/Utils/BusinessLogic/RegistrationHelper.hs:1340)
- Product deletion and blocking checks: [CustomerV2.deregisterCustomer](../../src/Newton/Product/CustomerV2.hs:38), [active mandate, UPI Lite, and delegate checks](../../src/Newton/Product/CustomerV2.hs:168)
- Response builder: [mkDeRegisterCustomerResponse](../../src/Newton/Utils/Transformers/Transformer9.hs:2134)
- Validators and normalization: [DeregisterRequest validation](../../src/Newton/Types/API/ServerToServer/Customer.hs:566), [common validators](../../src/Newton/Validation/Common.hs:275), [mobile normalization](../../src/Newton/Utils/Utils.hs:155)
- Error helpers and constants: [APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:7)
