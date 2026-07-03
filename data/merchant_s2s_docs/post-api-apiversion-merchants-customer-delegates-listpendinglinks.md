# List Pending Links API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/delegates/listPendingLinks`

## Overview

List Pending Links is a merchant server-to-server API used to fetch pending UPI delegate-link requests for one merchant customer.

Call this API when your backend needs to show or reconcile delegate-link actions that are still awaiting approval, expiry, or completion. Newton returns pending delegate links for the requested customer, including pending full-link conversion requests when applicable. The response is read-only; it does not create, approve, decline, expire, or otherwise mutate a link.

Payloads use the standard Newton S2S encrypted/signed request and response envelope shared during onboarding. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

Use `listPendingLinks` when the merchant backend needs to:

- Display pending delegate-link requests to a customer before the customer approves or declines them.
- Decide whether to call `manageLink` for a pending link action.
- Reconcile a link initiation or convert-to-full journey that is still pending at Newton.
- Refresh the merchant app state after a customer returns from an external UPI authorization flow.
- Poll conservatively for pending link state after a timeout or ambiguous client-side outcome.

The API returns only pending work. A successful response with an empty `pendingLinkRequest` array means Newton did not find any currently pending matching link requests for that merchant customer and filter.

## Integration Flow

1. Merchant backend identifies the Newton `merchantCustomerId`.
2. Merchant optionally chooses a `userType` filter: `DELEGATOR`, `DELEGATEE`, or omitted for all pending links.
3. Merchant sends the encrypted/signed S2S request.
4. Newton verifies merchant identity, merchant API access, request timestamp/signature, and customer ownership.
5. Newton validates the request body and fetches pending delegate-link records.
6. Merchant decrypts/verifies the response and uses `pendingLinkRequest[]` to drive UI or follow-up `manageLink` calls.

Important identifiers:

- `merchantCustomerId`: Merchant's customer reference, used to scope the lookup.
- `gatewayTransactionId`: Newton UPI request id for the pending link action. Use this as the transaction/link identifier in follow-up handling.
- `userType`: Customer role for the returned link from Newton's delegate-link record.
- `linkType`: `PARTIAL` or `FULL`. `FULL` pending links can include mandate/account-limit details.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/delegates/listPendingLinks
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

The route accepts the standard `EncRequest` transport variants:

- Encrypted JWE-style body: `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`.
- Signed JWS-style body: `payload`, `signature`, `protected`.
- Plain decrypted business JSON only where explicitly allowed for the environment/onboarding.

For encrypted or signed request modes, include `iat` in the decrypted business payload. Newton validates it before running the business flow as a 13-digit epoch-milliseconds value within the allowed clock-skew window. For plain unsigned request mode, Newton verifies the merchant signature using merchant headers, `x-timestamp`, and the raw request body.

Decrypted examples below are the business payload inside the transport envelope.

## Request

Route request type: `API.EncRequest TfS2S.ListPendingLinksS2SRequest`

Business payload type: `TfS2S.ListPendingLinksS2SRequest`

### Required Minimum

```json
{
  "merchantCustomerId": "CUST-100045"
}
```

This returns all direct `LINK_PENDING` delegate-link records for the customer, regardless of role, and also includes pending convert-to-full requests where the customer is the delegatee.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Must be 1 to 256 characters and match Newton's allowed identifier pattern. Newton uses it to load the merchant customer and customer context before listing links. |
| `userType` | string | No | If omitted, Newton lists all direct pending delegate links for the customer and includes pending delegatee convert-to-full requests. | Optional role filter. Allowed values: `DELEGATOR`, `DELEGATEE`. |
| `udfParameters` | string | No | Omitted from the response when not supplied. | Merchant-defined metadata string. This API does not parse it for business behavior; it is echoed in the top-level success response when supplied. |
| `iat` | string | Conditional | No business default. Required for signed/encrypted request modes. | Issued-at timestamp used by S2S signature/encryption validation. Send a 13-digit epoch-milliseconds value. It does not affect which links are returned. |

### Filter Behavior

| Request | Direct pending links returned | Convert-to-full pending requests returned |
| --- | --- | --- |
| Omit `userType` | `DELEGATOR` and `DELEGATEE` links with `LINK_PENDING` status. | Yes, pending `CONVERT_TO_FULL` histories where role is `DELEGATEE`. |
| `userType: "DELEGATEE"` | Only `DELEGATEE` links with `LINK_PENDING` status. | Yes, pending `CONVERT_TO_FULL` histories where role is `DELEGATEE`. |
| `userType: "DELEGATOR"` | Only `DELEGATOR` links with `LINK_PENDING` status. | No. |

There are no nested request objects, pagination fields, limit fields, or offset fields for this endpoint in the current implementation.

### Validation Notes

- `merchantCustomerId` must be present, non-empty, at most 256 characters, and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`.
- `userType`, when supplied, must parse as `DELEGATOR` or `DELEGATEE`.
- `udfParameters` is not validated by this request validator beyond JSON type parsing as a string.
- Unknown JSON fields are ignored by the Haskell generic parser, but clients should not send unsupported fields.

## Request Examples

### List All Pending Links

```json
{
  "merchantCustomerId": "CUST-100045"
}
```

### List Pending Links Where Customer Is Delegatee

```json
{
  "merchantCustomerId": "CUST-100045",
  "userType": "DELEGATEE",
  "iat": "1782977130000",
  "udfParameters": "{\"screen\":\"delegate_approval\"}"
}
```

### List Pending Links Where Customer Is Delegator

```json
{
  "merchantCustomerId": "CUST-100045",
  "userType": "DELEGATOR"
}
```

## Response

Route response type: `RespHeaders (API.EncResponse TfS2S.ListPendingLinksS2SResponse)`

Business response type: `TfS2S.ListPendingLinksS2SResponse`

### Success Envelope

On success, the decrypted response body is:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when Newton successfully processed the lookup. This is API-call status, not the lifecycle status of each link. |
| `responseCode` | string | `SUCCESS` on success. |
| `responseMessage` | string | `SUCCESS` on success. |
| `payload` | object | Business response payload. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters`. Omitted when request `udfParameters` is omitted. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Newton merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id for the loaded merchant customer. |
| `customerMobileNumber` | string | Decrypted mobile number for the customer. The implementation sets this when the customer record is available; optional encoding means clients should still tolerate omission. |
| `pendingLinkRequest` | array | Pending link records. Empty array means there are no matching pending link requests. |

### `pendingLinkRequest[]` Fields

| Field | Type | Always present | Description |
| --- | --- | --- | --- |
| `delegateeVpa` | string | Yes | Delegatee VPA. For a `DELEGATEE` record this is the customer's VPA; for a `DELEGATOR` record this is the linked VPA. |
| `delegatorVpa` | string | Yes | Delegator VPA. For a `DELEGATOR` record this is the customer's VPA; for a `DELEGATEE` record this is the linked VPA. |
| `userType` | string | Yes | Customer role from the delegate-link record: `DELEGATOR` or `DELEGATEE`. |
| `expiryTimestamp` | string | Yes | Link request expiry timestamp from Newton, serialized as a local timestamp. |
| `gatewayTransactionId` | string | Yes | UPI request id for the pending link request. For pending convert-to-full histories, this is the history UPI request id. |
| `linkType` | string | Yes | `PARTIAL` or `FULL`. Pending convert-to-full histories are returned as `FULL`. |
| `linkedMobileNumber` | string | Yes | Decrypted mobile number for the linked party. |
| `linkedName` | string | No | Name of the linked party, when stored. |
| `relation` | string | No | Relationship value from the link's `linkedInfo.relation`, when stored. |
| `umn` | string | No | Mandate UMN. Returned only when the pending link has an associated mandate. |
| `ifsc` | string | No | Payer account IFSC from the mandate payer info, when available. |
| `bankCode` | string | No | Payer bank IIN/code from the mandate payer info, when available. |
| `maskedAccountNumber` | string | No | Masked payer account number from the mandate payer info, when available. |
| `limit` | number | No | Mandate amount/limit for full delegate linking, when available. |
| `validityEnd` | string | No | Mandate validity end timestamp, when available. |
| `documentId` | string | No | Document id from mandate payee info, when available. |
| `documentType` | string | No | Document type from mandate payee info, when available. |

Optional fields are omitted rather than returned as `null`.

## Success Response Examples

### No Pending Links

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
    "pendingLinkRequest": []
  }
}
```

### Pending Partial Link

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
    "pendingLinkRequest": [
      {
        "delegateeVpa": "child@upi",
        "delegatorVpa": "parent@upi",
        "userType": "DELEGATEE",
        "expiryTimestamp": "2026-07-02T18:30:00",
        "gatewayTransactionId": "LNK202607021001",
        "linkType": "PARTIAL",
        "linkedName": "Parent User",
        "linkedMobileNumber": "9123456780",
        "relation": "PARENT"
      }
    ]
  }
}
```

### Pending Full Link With Mandate Details

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
    "pendingLinkRequest": [
      {
        "delegateeVpa": "child@upi",
        "delegatorVpa": "parent@upi",
        "userType": "DELEGATEE",
        "expiryTimestamp": "2026-07-02T18:30:00",
        "gatewayTransactionId": "LNK202607021002",
        "umn": "MERCHANT001000000000000000000000000001",
        "ifsc": "HDFC0001234",
        "bankCode": "607152",
        "maskedAccountNumber": "XXXXXX1234",
        "limit": 5000,
        "validityEnd": "2027-07-02T23:59:59",
        "linkType": "FULL",
        "linkedName": "Parent User",
        "linkedMobileNumber": "9123456780",
        "documentId": "DOC12345",
        "documentType": "PAN",
        "relation": "PARENT"
      }
    ]
  },
  "udfParameters": "{\"screen\":\"delegate_approval\"}"
}
```

## Client Interpretation

- Treat `status = SUCCESS` and `responseCode = SUCCESS` as successful retrieval only.
- Inspect `pendingLinkRequest[]` to decide whether any customer action is pending.
- Use `gatewayTransactionId`, `userType`, `delegateeVpa`, `delegatorVpa`, and `linkType` when correlating with a link initiation or a follow-up `manageLink` action.
- If `pendingLinkRequest` is empty, do not show stale pending-link UI for that filter.
- If a field such as `umn`, `limit`, or `validityEnd` is absent, the pending link either is not associated with a mandate or Newton did not have that mandate attribute available.

## Error Handling

Failures use the shared Newton error body shape with `status: "FAILURE"`, a concrete `responseCode`, and a diagnostic `responseMessage`. If the transport response is encrypted/signed, decrypt/verify it first. Some pre-crypto authentication failures can be returned as a plain error body because Newton cannot safely build a merchant-specific encrypted response.

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

Missing required JSON fields or invalid enum values can fail JSON parsing before product logic. Treat these as non-retryable request-shape errors and correct the payload.

### Authentication, Signature, Or Timestamp Failure

Missing merchant headers, signature mismatch, invalid source IP, or missing encrypted/signed `iat` fails before the lookup.

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

### Merchant Configuration Failure

If merchant configuration blocks this API or restricts the merchant through `allowedApiNames`, Newton rejects the call.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### Merchant Or Customer Lookup Failure

If the merchant id/channel cannot be resolved, the signature middleware returns `UNAUTHORIZED`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the `merchantCustomerId` does not belong to the authenticated merchant or is inactive/not found, the merchant-customer lookup returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

If the loaded merchant customer no longer has an active customer record, Newton can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
}
```

### Pending Link Business Data Failure

For a pending full-link or convert-to-full record, Newton loads the associated mandate to populate mandate/account fields. If the delegate link points to a mandate that cannot be found, the product flow rejects the response build.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "pendingLinkFromDelegateLink - mandate not found in DB "
}
```

### Downstream Storage Or Decryption Failure

This endpoint does not call NPCI. Downstream failures are primarily database/Redis lookups or Passetto decrypt operations for customer, delegate-link, or mandate PII. Depending on the failing dependency and where it fails, clients can see internal or service-unavailable style failures.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Unexpected Error

Unexpected missing flow context, malformed stored data, or unhandled dependency exceptions are returned as internal failures.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry And Idempotency Guidance

`listPendingLinks` is read-only and does not create or update delegate-link state. It does not require a merchant idempotency key.

- Retry on transport errors, timeouts, `INTERNAL_SERVER_ERROR`, or dependency/service-unavailable responses using bounded exponential backoff.
- Reuse the same business payload for a retry. Send a fresh `x-request-id` if you want each attempt to be traceable separately; reuse it if your operations team wants all attempts grouped.
- Do not retry validation, authentication, API-not-enabled, or not-found responses without changing credentials, configuration, or payload.
- Poll conservatively. The endpoint currently has no limit/offset fields, so a single response returns all matching pending links for the merchant customer.

## Source References

- API prefix and version capture: [Newton.App.Routes.Core](../../src/Newton/App/Routes/Core.hs:114)
- S2S route declaration: [Newton.App.Routes.Core](../../src/Newton/App/Routes/Core.hs:753)
- Handler and middleware sequence: [Newton.App.Routes.Core.listPendingLinksS2S](../../src/Newton/App/Routes/Core.hs:5211)
- Server wiring: [Newton.App.Server](../../src/Newton/App/Server.hs:334)
- S2S flow response wrapping: [Newton.App.Routes.RoutesHelper.flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Request envelope types: [Newton.Types.API.RequestBody](../../src/Newton/Types/API/RequestBody.hs:12)
- Merchant signature and API access checks: [Newton.App.Middlewares.Authentication.MerchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:46)
- Request and response types: [Newton.Services.Transformer.ServerToServer.Types](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4512)
- S2S transformer route: [Newton.Services.Transformer.ServerToServer.Core](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:765)
- S2S/core request and response mapping: [Newton.Services.Transformer.ServerToServer.Helper](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1419)
- Product list-pending flow: [Newton.Product.Merchant.Delegates.ListPendingLink](../../src/Newton/Product/Merchant/Delegates/ListPendingLink.hs:24)
- Core response and pending-link field types: [Newton.Product.Merchant.Delegates.Types](../../src/Newton/Product/Merchant/Delegates/Types.hs:525)
- Delegate-link enums: [Newton.Types.Storage.DelegateLink](../../src/Newton/Types/Storage/DelegateLink.hs:67)
- Delegate-link history enums: [Newton.Types.Storage.DelegateLinkHistory](../../src/Newton/Types/Storage/DelegateLinkHistory.hs:49)
- Pending-link query filter: [Newton.Storage.Queries.DelegateLink](../../src/Newton/Storage/Queries/DelegateLink.hs:136)
- Pending convert-to-full query filter: [Newton.Storage.Queries.DelegateLinkHistory](../../src/Newton/Storage/Queries/DelegateLinkHistory.hs:106)
- Request validation helper: [Newton.Utils.Utils.validateRequestBody](../../src/Newton/Utils/Utils.hs:251)
- `merchantCustomerId` validation: [Newton.Validation.Common](../../src/Newton/Validation/Common.hs:311)
- Shared error constants: [Newton.Constants.APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:43)
