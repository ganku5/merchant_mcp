# Unblock VPA API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/unblock`

## Overview

Unblock VPA is a server-to-server API used to restore a customer's blocked payee contact for a merchant profile.

The merchant calls this API with `merchantCustomerId` and `payeeVpa`. Newton authenticates the S2S request, resolves the merchant customer and linked customer, finds an active `BLOCKED` contact row for that merchant customer and VPA, updates that contact to `ACTIVE`, and returns a success payload with gateway-style response details.

Use this API when a trusted merchant backend has decided that a previously blocked payee VPA should be unblocked for one onboarded customer profile.

Important distinction: this endpoint updates the `Contacts` storage path. It does not update VPA status rows managed by `POST /api/{apiVersion}/merchants/blockUnblockEntity`, does not delete or reset spam-threshold `BlockedVpas` records, does not validate the VPA at NPCI, and does not initiate a payment.

Payloads use the standard Newton server-to-server encrypted, signed, or plain request and response envelope configured during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Unblock VPA helps merchants:

- Restore a payee VPA that a customer previously blocked through `blockAndSpam` or contact-management flows.
- Remove a payee from the customer's blocked-contact list so future merchant journeys can treat the payee as active again.
- Support customer support, risk review, false-positive, or customer-initiated unblock workflows from a trusted backend.
- Reconcile block state through `POST /api/{apiVersion}/merchants/vpas/block/list` or contact-list APIs after the update.

This API is scoped to one merchant customer and one payee VPA. It does not return an idempotency key and should not be exposed directly to untrusted clients.

## Integration Flow

1. Merchant backend identifies the customer profile by `merchantCustomerId`.
2. Merchant chooses the blocked payee VPA to restore. Send the normalized lowercase VPA used for the original block whenever possible.
3. Merchant signs and encrypts the request using the Newton S2S process configured during onboarding.
4. Newton unwraps the request body, verifies merchant headers, request signature/envelope, timestamp freshness, API access configuration, and optional IP allowlist.
5. Newton validates the decrypted business payload.
6. Newton resolves the active merchant-customer profile for the authenticated merchant and its linked customer profile.
7. Newton hashes the submitted `payeeVpa`, finds an active `BLOCKED` contact row for that merchant customer, and updates it to `ACTIVE`.
8. Merchant decrypts the response and treats top-level `status`, `responseCode`, and `responseMessage` as the operation result.
9. Merchant can call `vpas/block/list` or `contacts/list` to refresh customer-facing state.

Important behavior:

- The API succeeds only when a matching active blocked contact exists.
- A retry after a successful unblock can return `Contact not found`, because the contact is no longer `BLOCKED`.
- The route hashes the submitted `payeeVpa` as-is. For best compatibility, send the lowercase VPA stored during blocking, especially when the block was created by `contacts/manage`, which normalizes VPAs to lowercase.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/unblock
```

### Path and Headers

| Name | Location | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | path | Yes | API route version shared during onboarding. |
| `Content-Type` | header | Yes | Use `application/json`. |
| `x-api-version` | header | Recommended | Standard Newton response-version selector. This endpoint currently does not branch response fields by `x-api-version`. |
| `x-merchant-id` | header | Yes | Merchant id shared during onboarding. Used to resolve the authenticated merchant. |
| `x-merchant-channel-id` | header | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | header | Conditional | Required only for configured sub-merchant flows. |
| `x-sub-merchant-channel-id` | header | Conditional | Required only for configured sub-merchant flows. |
| `x-timestamp` | header | Yes | Current 13-digit epoch milliseconds timestamp used for signature and replay validation. |
| `x-merchant-signature` | header | Conditional | Required for unsigned/plain business payload transport. For JWS/JWE transport, request authentication is carried by the envelope. |
| `x-forwarded-for` | header | Conditional | Required when IP allowlisting is configured for the merchant. |
| `x-request-id` | header | No | Optional merchant request id for tracing. If omitted, Newton generates one and returns it as `x-requestid`. |
| `x-session-id` | header | No | Optional session/correlation id for tracing. If omitted, Newton uses the request id. |
| `Authorization` | header | Conditional | Send only when required by the merchant onboarding profile. |

### Authentication and Encryption

The route accepts the standard Newton `EncRequest` transport:

| Transport mode | Request body shape | Authentication behavior |
| --- | --- | --- |
| Plain business JSON | Decrypted business payload directly. | Allowed only when merchant configuration permits it. Newton verifies `x-merchant-signature` over merchant ids, optional sub-merchant ids, `x-timestamp`, and the raw request body. |
| JWS | `payload`, `signature`, and `protected`. | Newton verifies the JWS `kid` and signature, then parses the business payload. |
| JWE | `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`. | Newton decrypts the JWE, expects a signed payload inside it, verifies the inner signature, then parses the business payload. |

For JWS/JWE request bodies, include `iat` inside the decrypted business payload. Newton validates `iat` as a 13-digit epoch milliseconds timestamp before running product logic. For plain unsigned payloads, `iat` is not used by the signature layer, but `x-timestamp` is still required.

### Response Transport

Success responses are returned as `API.EncResponse API.UnblockVpaResponse`.

| Response mode | Body shape |
| --- | --- |
| Unsigned/plain response | The decrypted business response is returned directly and `X-Response-Signature` is returned as a response header. |
| JWS response | `payload`, `signature`, and `protected`. The decoded payload is the business response shown in this guide. |
| JWE response | `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`. The decrypted payload contains a signed business response. |

Newton also returns `x-requestid` and `x-sessionid` response headers for tracing.

## Request

### Required Minimum

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "unknownshop@examplebank"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. It must belong to the authenticated merchant and resolve to an active merchant-customer profile. Maximum length is 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen; the first character must be alphanumeric, plus, slash, or equals. |
| `payeeVpa` | string | Yes | No default. | Payee VPA to unblock. The request validator only checks that this field is not empty; product logic uses the submitted value to compute the lookup hash and to echo the response. Send the normalized lowercase VPA that was blocked. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp used by JWS/JWE request validation. Required for signed/encrypted request bodies. Send a current 13-digit epoch milliseconds value. |
| `udfParameters` | string | No | Omitted from the response when omitted from the request. | JSON-object string for merchant-defined metadata. It must parse as a JSON object string and pass Newton's restricted-character validation. Do not include `/`, `$`, `-`, `*`, `!`, `%`, `~`, or the grave-accent character. Echoed in the top-level response when supplied and valid. |

There are no nested business request objects for this API. The only nested request objects are the standard JWS/JWE transport envelopes.

### Defaults and Omitted Field Behavior

There are no business defaults for `merchantCustomerId` or `payeeVpa`; both must be sent.

Optional fields behave as follows:

- `iat`: required only by encrypted/signed request transport. It is not stored and is not returned.
- `udfParameters`: not stored by the contact update. If supplied and valid, it is echoed in the top-level response.
- Unknown extra JSON fields are ignored by the generic JSON parser unless the surrounding gateway layer rejects them.

### Request Examples

#### Unblock a Blocked Payee

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "unknownshop@examplebank"
}
```

#### Unblock With Merchant Metadata

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "unknownshop@examplebank",
  "udfParameters": "{\"requestId\":\"unblock001\",\"reason\":\"supportreview\"}"
}
```

#### Signed or Encrypted Business Body

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "unknownshop@examplebank",
  "iat": "1782968400000",
  "udfParameters": "{\"requestId\":\"unblock002\"}"
}
```

When sending a real request, generate both `iat` and `x-timestamp` at request time so they are within Newton's configured freshness window.

## Validation and Processing Behavior

Newton performs these checks and updates before returning success:

- Parses the `EncRequest` transport as plain JSON, JWS, or JWE.
- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`, or from configured sub-merchant headers where applicable.
- For JWS/JWE requests, validates the request `kid`, signature, and `iat`.
- For plain unsigned requests, validates `x-merchant-signature` and `x-timestamp`.
- Checks merchant API block/allow configuration for the `unblockVpa` service.
- Checks the source IP when merchant `whitelistedIps` configuration is present.
- Clears Newton's cached data for the supplied `merchantCustomerId`.
- Validates the business payload: `merchantCustomerId` format, non-empty `payeeVpa`, and valid `udfParameters` if supplied.
- Resolves `merchantCustomerId` to an active merchant-customer profile for the authenticated merchant.
- Resolves the linked customer profile from the merchant-customer record.
- Computes a passetto hash for the submitted `payeeVpa`.
- Finds an active contact row where status is `BLOCKED` for the merchant customer and VPA/hash.
- Updates the contact row to `ACTIVE`, sets the resolved customer id on the row, and updates `updatedAt`.
- Builds a success response with fixed nested gateway result `gatewayResponseCode = "00"` and `gatewayResponseMessage = "Vpa unblocked successfully"`.

This endpoint does not call NPCI, does not create a contact, does not change the contact nickname, and does not return the customer mobile number.

## Response

Successful decrypted business responses use this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when the unblock operation completed. |
| `responseCode` | string | `SUCCESS` when the unblock operation completed. |
| `responseMessage` | string | `SUCCESS` when the unblock operation completed. |
| `payload` | object | Unblock result. Always present on success. |
| `udfParameters` | string | Echo of request `udfParameters`; omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. The type allows omission, but the current success transformer always sets it. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `payeeVpa` | string | Payee VPA exactly as supplied in the request. |
| `gatewayResponseCode` | string | Fixed value `00` on success. |
| `gatewayResponseMessage` | string | Fixed value `Vpa unblocked successfully` on success. |

## Success Response Examples

### Unblock Success

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "payeeVpa": "unknownshop@examplebank",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Vpa unblocked successfully"
  }
}
```

### Unblock Success With UDF Echo

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "payeeVpa": "unknownshop@examplebank",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Vpa unblocked successfully"
  },
  "udfParameters": "{\"requestId\":\"unblock001\",\"reason\":\"supportreview\"}"
}
```

## Error Handling

Failure responses use the standard Newton S2S error body. Depending on where the failure occurs, the HTTP status may be `200`, `400`, `401`, `422`, or `500`; clients should always inspect the decrypted business body.

When `payload` is empty, it is omitted from the JSON response.

General failure shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"payeeVpa field is empty\""
}
```

### JSON and Envelope Parse Failures

Missing a required business key in a plain request can fail before product validation:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Error in $: key \"merchantCustomerId\" not found"
}
```

For signed/encrypted requests, malformed decoded payloads usually surface as `INVALID_DATA` with the JSON parser message:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payeeVpa\" not found"
}
```

The exact parser text can vary with the JSON library and whether the failure happens while parsing the outer envelope, inner signed body, or business payload.

### Request Validation Failures

Invalid `merchantCustomerId` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Empty `merchantCustomerId` or a value longer than 256 characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

Empty `payeeVpa`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"payeeVpa field is empty\""
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

This endpoint does not run the VPA regex validator used by some other contact APIs. A syntactically unusual but non-empty `payeeVpa` can pass request validation and then fail later with `Contact not found`.

### Authentication, Encryption, and Signature Failures

Authentication failures occur before the contact update. Common causes include missing or invalid merchant headers, unknown merchant keys, failed JWS verification, failed JWE decryption, missing timestamp headers, stale timestamps, missing `iat` for encrypted/signed payloads, invalid merchant signature, or failed IP allowlist checks.

Missing merchant headers, invalid merchant signature, failed JWS verification, failed JWE decryption, or IP allowlist failure:

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

Invalid `iat` or `x-timestamp` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired `iat` or `x-timestamp` outside Newton's freshness window:

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

### Merchant Configuration and Access Failures

Newton checks whether the `unblockVpa` service is blocked or allowed for the merchant before product logic runs. If this endpoint is disabled for the merchant or sub-merchant configuration, the response is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If `x-merchant-id` and `x-merchant-channel-id` do not resolve to an enabled merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Do not retry these responses unchanged. Correct onboarding, headers, allowlist, keys, or API-access configuration.

### Merchant Customer and Customer Lookup Failures

If the authenticated merchant does not have an active profile for `merchantCustomerId`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

If the merchant customer has no linked active customer/device binding:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

If the linked customer profile cannot be resolved:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
}
```

These are normally non-retryable until the merchant customer is onboarded, reactivated, or corrected.

### Contact Business Failures

No matching active blocked contact for the merchant customer and VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Contact not found"
}
```

This response can mean that the VPA was never blocked for this merchant customer, was already unblocked, was blocked under a different merchant customer, or was sent with a casing/normalization different from the stored contact hash.

### Storage, Crypto, and Unexpected Failures

The synchronous path reads merchant and customer records, computes PII hashes, updates the contact row, and may sign or encrypt the response. Storage failures, key/PII crypto failures, response-signing failures, or unexpected exceptions can surface as:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Retry these only with bounded exponential backoff and reconciliation, because the contact update might have completed before the failure surfaced.

## Retry and Client Handling Guidance

- This API has no `merchantRequestId` or server-side idempotency key. Use `merchantCustomerId`, `payeeVpa`, and your own support/risk case id as client-side correlation data.
- A successful unblock changes the matching contact from `BLOCKED` to `ACTIVE`.
- Retrying after a successful first attempt is not idempotent at the response level; it can return `Contact not found` because the contact is no longer blocked.
- If a response is lost or times out, call `POST /api/{apiVersion}/merchants/vpas/block/list` or `contacts/list` to verify current state before retrying.
- Treat `Contact not found` as terminal unless reconciliation shows the VPA is still blocked and the submitted VPA normalization is correct.
- Retry transient `INTERNAL_SERVER_ERROR` responses with exponential backoff and jitter. Keep retries bounded.
- Do not retry validation errors, `UNAUTHORIZED`, `API NOT ENABLED`, timestamp failures, merchant-customer lookup failures, or malformed payloads without changing the request or configuration.
- Store the top-level response fields and, on success, the nested `gatewayResponseCode` and `gatewayResponseMessage` for audit/reconciliation.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:255)
- Route handler, merchant signature verification, cache invalidation, and product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2085)
- Request envelope and response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:16), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:69)
- S2S payload verification and JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature, timestamp, API access, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:131), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- Response headers and response signing/encryption selection: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:31), [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:74)
- Request and response types plus request validator: [src/Newton/Types/API/ServerToServer/Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:473), [src/Newton/Types/API/ServerToServer/Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:495), [src/Newton/Types/API/ServerToServer/Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:505)
- Product unblock flow: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:801)
- Contact blocked-row lookup and ACTIVE update: [src/Newton/Storage/QueriesMiddleware/Contact.hs](../../src/Newton/Storage/QueriesMiddleware/Contact.hs:69), [src/Newton/Storage/Queries/Contact.hs](../../src/Newton/Storage/Queries/Contact.hs:120), [src/Newton/Storage/Queries/Contact.hs](../../src/Newton/Storage/Queries/Contact.hs:175), [src/Newton/Storage/DB/Queries.hs](../../src/Newton/Storage/DB/Queries.hs:1238)
- Success response construction: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1775)
- Common validators and validation error wrapping: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:311), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Shared success and invalid-data constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61)
