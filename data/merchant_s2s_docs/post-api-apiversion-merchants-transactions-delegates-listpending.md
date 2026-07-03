# List Pending Delegate Payments API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/delegates/listPending`

## Overview

List Pending Delegate Payments is a merchant server-to-server API used to fetch pending UPI delegate-payment requests for one merchant customer.

Call this API when your backend needs to show, reconcile, or refresh delegate-payment collect requests that are still waiting for customer action. Newton returns pending, non-expired delegate-payment records for the authenticated merchant customer and backing customer record. The response is read-only; it does not approve, decline, expire, or otherwise mutate a delegate payment.

Payloads use the standard Newton S2S encrypted/signed request and response envelope shared during onboarding. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

Use `listPending` for delegate payments when the merchant backend needs to:

- Display pending delegate-payment requests to the customer.
- Refresh pending payment state after a timeout or ambiguous client-side result.
- Decide whether the app should ask the customer to approve or decline a delegate payment.
- Reconcile pending delegate-payment requests created by `delegatePay`.
- Avoid showing stale requests after Newton has no matching pending, non-expired record.

A successful response with an empty `pendingDelegatePayments` array means Newton did not find any currently pending, non-expired delegate payments for that merchant customer.

## Integration Flow

1. Merchant backend identifies the Newton `merchantCustomerId`.
2. Merchant sends the encrypted/signed S2S request.
3. Newton decrypts/verifies the request payload and validates merchant identity, API access, request timestamp/signature, and customer ownership.
4. Newton validates the request body.
5. Newton loads the merchant customer and customer, then fetches matching delegate-payment rows with status `PENDING`, link type `PARTIAL`, and expiry greater than or equal to the current time.
6. Merchant decrypts/verifies the response and uses `pendingDelegatePayments[]` to drive UI or follow-up delegate-payment actions.

Important identifiers:

- `merchantCustomerId`: Merchant's customer reference, used to scope the lookup.
- `gatewayTransactionId`: Original UPI transaction/request id for the pending delegate payment. Use this to correlate with a prior `delegatePay` request and follow-up payment handling.
- `payerVpa`: Delegator VPA from the stored delegate payment.
- `delegateeVpa`: Delegatee VPA from the stored delegate payment.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/delegates/listPending
```

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-merchant-id` | Yes | Merchant id issued during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued during onboarding. |
| `x-timestamp` | Yes | Request timestamp used by S2S signature/timestamp validation. Send a 13-digit epoch-milliseconds value within the allowed clock-skew window. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain S2S payload mode. JWS/JWE integrations use the onboarded signed/encrypted envelope instead. |
| `x-request-id` | No | Client request id for tracing. Newton generates one if omitted. |
| `x-session-id` | No | Client session id for tracing. Defaults to `x-request-id` if omitted. |
| `x-api-version` | Conditional | Send the version/header value shared for your S2S onboarding, if your integration standard requires it. |

The path `apiVersion` is captured from the URL. This endpoint does not branch product behavior by version in the traced code path, but clients should use the version agreed during onboarding.

### Authentication And Encryption

The route accepts the standard Newton S2S request transport variants:

- Encrypted JWE-style body: `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`.
- Signed JWS-style body: `payload`, `signature`, `protected`.
- Plain decrypted business JSON only where explicitly allowed for the environment/onboarding.

For encrypted or signed request modes, include `iat` in the decrypted business payload. Newton validates it before running the business flow as a 13-digit epoch-milliseconds value within the allowed clock-skew window. For plain unsigned request mode, Newton verifies the merchant signature using merchant headers, `x-timestamp`, and the raw request body.

Successful S2S responses are returned according to the merchant's response crypto configuration:

- JWS response when response signing is configured.
- JWS plus JWE response when response signing and encryption are configured.
- Plain JSON business response with `X-Response-Signature` when that is the onboarded strategy.

Decrypted examples below are the business payload inside the transport envelope.

## Request

Route request type: `API.EncRequest TfS2S.ListPendingDelegatePaymentsS2SRequest`

Business payload type: `TfS2S.ListPendingDelegatePaymentsS2SRequest`

### Required Minimum

```json
{
  "merchantCustomerId": "CUST-100045"
}
```

There are no filter, pagination, limit, offset, or date-range fields for this endpoint in the current implementation.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Must identify an active merchant customer under the authenticated merchant. Newton uses it to load merchant-customer and customer context before listing pending delegate payments. |
| `udfParameters` | string | No | Omitted from the response when not supplied. | Merchant-defined metadata string. Must be a JSON-object string when supplied. This API does not use it for business filtering; it is echoed in the top-level success response. |
| `iat` | string | Conditional | No business default. Required for signed/encrypted request modes. | Issued-at timestamp used by S2S signature/encryption validation. Send a 13-digit epoch-milliseconds value. It does not affect which delegate payments are returned. |

### Validation Rules

- `merchantCustomerId` must be present, non-empty, at most 256 characters, and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`.
- `udfParameters`, when supplied, must parse as a JSON object string and must not contain characters rejected by Newton's UDF validation regex. Characters `/`, `$`, `-`, `*`, `!`, `%`, `~`, and backtick are rejected by the current text validator.
- `iat` is not business-validated by the request type, but the authentication middleware requires and validates it for signed/encrypted request modes.
- Unknown JSON fields are ignored by the Haskell generic parser, but clients should not send unsupported fields.

### Request Examples

#### List Pending Delegate Payments

```json
{
  "merchantCustomerId": "CUST-100045"
}
```

#### Signed Or Encrypted Request Payload

```json
{
  "merchantCustomerId": "CUST-100045",
  "iat": "1782977130000",
  "udfParameters": "{\"screen\":\"delegate_payments\"}"
}
```

## Response

Route response type: `RespHeaders (API.EncResponse TfS2S.ListPendingDelegatePaymentsS2SResponse)`

Business response type: `TfS2S.ListPendingDelegatePaymentsS2SResponse`

### Success Envelope

On success, the decrypted response body is:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when Newton successfully processed the lookup. This is API-call status, not the lifecycle status of each delegate payment. |
| `responseCode` | string | `SUCCESS` on success. |
| `responseMessage` | string | `SUCCESS` on success. |
| `payload` | object | Business response payload. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters`. Omitted when request `udfParameters` is omitted. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Newton merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Decrypted mobile number for the loaded customer. |
| `pendingDelegatePayments` | array | Pending delegate-payment records. Empty array means there are no matching pending, non-expired delegate payments. |

### `pendingDelegatePayments[]` Fields

| Field | Type | Always present | Description |
| --- | --- | --- | --- |
| `amount` | string | Yes | Delegate-payment amount formatted with two decimal places. |
| `collectType` | string | Yes | Always `DELEGATE` for this endpoint. |
| `expiry` | string | Yes | Delegate-payment expiry timestamp serialized as a local timestamp. Only records whose expiry is not in the past are returned. |
| `gatewayTransactionId` | string | Yes | Original transaction UPI request id stored on the delegate-payment record. |
| `isVerifiedPayee` | string | Yes | Payee verification flag from stored delegate metadata. Defaults to `"false"` in the response when not present in stored data. |
| `isMarkedSpam` | string | Yes | Spam flag from stored delegate metadata. Defaults to `"false"` in the response when not present in stored data. |
| `payeeMcc` | string | Yes | Payee MCC from stored payee metadata. If the stored field is missing, Newton currently serializes an empty string. |
| `payeeName` | string | Yes | Payee name from stored payee metadata. If the stored field is missing, Newton currently serializes an empty string. |
| `payeeVpa` | string | Yes | Payee VPA. |
| `payerVpa` | string | Yes | Delegator VPA. |
| `refUrl` | string | No | Reference URL from stored delegate metadata. The current mapper can include this as an empty string if the stored value is absent. |
| `refCategory` | string | No | Reference category from stored delegate metadata. The current mapper can include this as an empty string if the stored value is absent. |
| `remarks` | string | Yes | Payment remarks from stored delegate metadata. If the stored field is missing, Newton currently serializes an empty string. |
| `delegateeVpa` | string | Yes | Delegatee VPA. |
| `featureTags` | array of strings | No | Feature tags from stored payee metadata, split on `|` when present. |

Optional fields are omitted when the response value is `Nothing`. Some stored metadata fields are mapped through empty-string defaults, so clients should treat empty strings as missing information where appropriate.

## Success Response Examples

### No Pending Delegate Payments

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST-100045",
    "customerMobileNumber": "9876543210",
    "pendingDelegatePayments": []
  }
}
```

### Pending Delegate Payment

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST-100045",
    "customerMobileNumber": "9876543210",
    "pendingDelegatePayments": [
      {
        "amount": "250.00",
        "collectType": "DELEGATE",
        "expiry": "2026-07-02T18:30:00",
        "gatewayTransactionId": "TXN202607021001",
        "isVerifiedPayee": "true",
        "isMarkedSpam": "false",
        "payeeMcc": "5411",
        "payeeName": "Merchant Store",
        "payeeVpa": "store@upi",
        "payerVpa": "parent@upi",
        "refUrl": "https://merchant.example/orders/ORDER123",
        "refCategory": "00",
        "remarks": "Delegate payment",
        "delegateeVpa": "child@upi",
        "featureTags": [
          "DELEGATE_PAY"
        ]
      }
    ]
  }
}
```

### Pending Delegate Payment With UDF Echo

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST-100045",
    "customerMobileNumber": "9876543210",
    "pendingDelegatePayments": [
      {
        "amount": "99.00",
        "collectType": "DELEGATE",
        "expiry": "2026-07-02T19:00:00",
        "gatewayTransactionId": "TXN202607021002",
        "isVerifiedPayee": "false",
        "isMarkedSpam": "false",
        "payeeMcc": "5812",
        "payeeName": "Food Merchant",
        "payeeVpa": "food@upi",
        "payerVpa": "parent@upi",
        "refUrl": "",
        "refCategory": "",
        "remarks": "Dinner",
        "delegateeVpa": "child@upi"
      }
    ]
  },
  "udfParameters": "{\"screen\":\"delegate_payments\"}"
}
```

## Client Interpretation

- Treat `status = SUCCESS` and `responseCode = SUCCESS` as successful retrieval only.
- Inspect `pendingDelegatePayments[]` to decide whether any delegate-payment action is pending.
- Use `gatewayTransactionId`, `payerVpa`, `delegateeVpa`, `payeeVpa`, `amount`, and `expiry` when correlating with a `delegatePay` initiation or customer approval/decline flow.
- If `pendingDelegatePayments` is empty, do not show stale pending delegate-payment UI for that customer.
- The current implementation returns only `PENDING`, non-expired delegate payments for `PARTIAL` delegate links. Terminal, expired, full-link, or already initiated/approved/declined records are not returned by this endpoint.
- This endpoint does not call NPCI. It reads Newton storage and decrypts stored PII before building the response.

## Error Handling

Failures use the shared Newton error body shape. If the transport response is encrypted/signed, decrypt/verify it first. Some pre-crypto authentication failures can be returned as a plain error body because Newton cannot safely build a merchant-specific encrypted response.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

HTTP status can vary by layer. Client logic should primarily use `status`, `responseCode`, and `responseMessage`.

### Validation Failure

Invalid `merchantCustomerId` format or length is rejected by request validation.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

If `merchantCustomerId` is empty or longer than 256 characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

If `udfParameters` is supplied but is not a JSON-object string accepted by the UDF validator:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Missing required JSON fields or type mismatches can fail JSON parsing before product logic. Treat these as non-retryable request-shape errors and correct the payload.

### Authentication, Signature, Encryption, Or Timestamp Failure

Missing merchant headers, unknown merchant/channel, signature mismatch, invalid source IP, malformed JWS/JWE, failed decryption, or missing encrypted/signed `iat` fails before the lookup.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

For signed/encrypted payloads with missing `iat`, the body can be:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

For malformed 13-digit timestamp values in `x-timestamp` or `iat`, the body can be:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

For timestamps outside the allowed window, the shared timestamp validator can return:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

For malformed encrypted payload JSON after decryption, the body can be:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantCustomerId\" not found"
}
```

### Merchant Configuration Or Access Failure

If merchant configuration blocks this API or restricts the merchant through `allowedApiNames`, Newton rejects the call.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If the request IP is not present in the merchant whitelist, or the `x-forwarded-for` header is missing while an IP whitelist is configured, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Merchant Or Customer Lookup Failure

If the merchant id/channel cannot be resolved, the request fails before product logic with `UNAUTHORIZED`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the `merchantCustomerId` does not belong to the authenticated merchant or is inactive/not found, the merchant-customer lookup can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

If the loaded merchant customer does not have an active customer record, Newton can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
}
```

If the loaded merchant customer has no backing customer id, Newton can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

### Stored Delegate-Payment Data Failure

The response mapper requires every returned delegate-payment row to have an expiry timestamp. The query already filters on non-null current/future expiry, but malformed stored data can still fail response building.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid expiry missing in getPendingDelegatePaymentsList"
}
```

### Downstream Storage Or Decryption Failure

This endpoint does not call NPCI. Downstream failures are primarily database/Redis lookups or Passetto decrypt operations for customer/delegate-payment PII. Depending on the failing dependency and where it fails, clients can see internal or service-unavailable style failures.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Unexpected Error

Unexpected missing flow context, malformed stored data, crypto/key-store failures, or unhandled dependency exceptions are returned as internal failures.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry And Polling Guidance

`listPending` for delegate payments is read-only and does not require a merchant idempotency key.

- Retry on transport errors, timeouts, `INTERNAL_SERVER_ERROR`, or dependency/service-unavailable responses using bounded exponential backoff.
- Reuse the same business payload for a retry. Send a fresh `x-request-id` if you want each attempt to be traceable separately; reuse it if your operations team wants all attempts grouped.
- Do not retry validation, authentication, API-not-enabled, IP-restriction, or not-found responses without changing credentials, configuration, or payload.
- Poll conservatively. The endpoint currently has no limit/offset fields, so a single response returns all matching pending, non-expired delegate payments for the merchant customer.

## Source References

- API prefix and version capture: [Newton.App.Routes.Core](../../src/Newton/App/Routes/Core.hs:114)
- S2S route declaration: [Newton.App.Routes.Core](../../src/Newton/App/Routes/Core.hs:767)
- Handler and middleware sequence: [Newton.App.Routes.Core.listPendingDelegatePaymentsS2S](../../src/Newton/App/Routes/Core.hs:5265)
- Server wiring: [Newton.App.Server](../../src/Newton/App/Server.hs:336)
- S2S flow response wrapping: [Newton.App.Routes.RoutesHelper.flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Request envelope types: [Newton.Types.API.RequestBody](../../src/Newton/Types/API/RequestBody.hs:12)
- Payload verification and JWS/JWE handling: [Newton.App.Middlewares.Authentication.MerchantPayloadVerification](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:66)
- Merchant signature, API access, timestamp, customer, and IP checks: [Newton.App.Middlewares.Authentication.MerchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:46)
- Request and response types: [Newton.Services.Transformer.ServerToServer.Types](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4576)
- S2S transformer route: [Newton.Services.Transformer.ServerToServer.Core](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:787)
- S2S/core request and response mapping: [Newton.Services.Transformer.ServerToServer.Helper](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1471)
- Product list-pending flow: [Newton.Product.Merchant.Delegates.ListPendingDelegatePayments](../../src/Newton/Product/Merchant/Delegates/ListPendingDelegatePayments.hs:17)
- Core response and pending delegate-payment field types: [Newton.Product.Merchant.Delegates.Types](../../src/Newton/Product/Merchant/Delegates/Types.hs:622)
- Pending delegate-payment response mapper: [Newton.Product.Merchant.Delegates.Transformer](../../src/Newton/Product/Merchant/Delegates/Transformer.hs:900)
- Product response builder: [Newton.Product.Merchant.Delegates.Helper](../../src/Newton/Product/Merchant/Delegates/Helper.hs:834)
- Delegate-payment query filter: [Newton.Storage.QueriesMiddleware.DelegatePayment](../../src/Newton/Storage/QueriesMiddleware/DelegatePayment.hs:60)
- Delegate-payment query predicate: [Newton.Storage.Queries.DelegatePayment](../../src/Newton/Storage/Queries/DelegatePayment.hs:143)
- Delegate-payment storage fields and statuses: [Newton.Types.Storage.DelegatePayment](../../src/Newton/Types/Storage/DelegatePayment.hs:30)
- Request validation helper: [Newton.Utils.Utils.validateRequestBody](../../src/Newton/Utils/Utils.hs:251)
- `merchantCustomerId` and `udfParameters` validation: [Newton.Validation.Common](../../src/Newton/Validation/Common.hs:275)
- Shared timestamp validation: [Newton.Utils.DateTime](../../src/Newton/Utils/DateTime.hs:109)
- Shared error constants: [Newton.Constants.APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:43)
