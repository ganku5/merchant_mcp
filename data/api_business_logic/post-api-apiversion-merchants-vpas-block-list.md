# List Blocked VPAs API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/block/list`

## Overview

List Blocked VPAs is a server-to-server API used to fetch the VPAs that are currently blocked as contacts for one merchant customer.

The merchant calls this API with a `merchantCustomerId`, `limit`, and `offset`. Newton authenticates the S2S request, resolves the merchant customer and customer profile, reads active `BLOCKED` contact rows for that merchant customer, decrypts stored PII fields where required, and returns the requested page ordered by most recent update first.

Use this API after a customer or merchant backend blocks payees through `POST /api/{apiVersion}/merchants/vpas/blockAndSpam` or contact-management flows and needs to display or reconcile the customer's blocked payee list.

Important distinction: this endpoint lists blocked contact VPAs from the `Contacts` storage path. It does not list VPA status rows updated by `POST /api/{apiVersion}/merchants/blockUnblockEntity`, and it does not directly list spam-threshold `BlockedVpas` storage records unless the contact itself was marked `BLOCKED`.

## Business Use Case

List Blocked VPAs helps merchants:

- Show a customer's current blocked payee list in a trusted backend or support workflow.
- Reconcile customer block state after `blockAndSpam`, `unblock`, or contact-management operations.
- Page through blocked payees without fetching the full contact set.
- Display the blocked payee VPA, stored display name, and last block/update timestamp.
- Confirm that an unblock action removed a VPA from the blocked-contact list.

This API is read-only. It does not block, unblock, spam-mark, unspam, validate a VPA at NPCI, or mutate contact state.

## Integration Flow

1. Merchant backend identifies the customer profile by `merchantCustomerId`.
2. Merchant sends `limit` and a zero-based row `offset`.
3. Merchant signs/encrypts the request using the Newton S2S process configured during onboarding.
4. Newton unwraps the request, verifies merchant headers, request signature/envelope, timestamp freshness, API access configuration, and optional IP allowlist.
5. Newton resolves the active merchant-customer profile and linked customer profile.
6. Newton validates the decrypted business payload.
7. Newton reads active blocked contacts for the merchant customer, ordered by `updatedAt` descending.
8. Newton decrypts contact PII and returns the blocked VPA list.
9. Merchant decrypts the response and uses `blockedVpas` for display or reconciliation.

Pagination behavior:

- `limit` is the maximum number of rows to return.
- `offset` is a raw row offset, not a page number. Send `0` for the first page, `20` for the next page when `limit` is `20`, and so on.
- The response does not include a total count, total pages, or cursor.
- Stop paging when `blockedVpas` is empty or contains fewer rows than `limit`.
- Because the list is ordered by current `updatedAt`, concurrent block/unblock changes can shift rows between page requests.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/block/list
```

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show decrypted business payloads for readability.

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
| `Authorization` | header | Conditional | Send only when required by the merchant's onboarding profile. |

### Authentication and Encryption

The route accepts the standard Newton `EncRequest` transport:

| Transport mode | Request body shape | Authentication behavior |
| --- | --- | --- |
| Plain business JSON | Decrypted business payload directly. | Allowed only when merchant configuration permits it. Newton verifies `x-merchant-signature` over merchant ids, optional sub-merchant ids, `x-timestamp`, and the raw request body. |
| JWS | `payload`, `signature`, and `protected`. | Newton verifies the JWS `kid` and signature, then parses the business payload. |
| JWE | `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`. | Newton decrypts the JWE, expects a signed payload inside it, verifies the signature, then parses the business payload. |

For JWS/JWE request bodies, include `iat` inside the decrypted business payload. Newton validates `iat` as a 13-digit epoch milliseconds timestamp before running the business flow. For plain unsigned payloads, `iat` is not used by the signature layer, but `x-timestamp` is still required.

## Request

### Required Minimum

Fetch the first 20 blocked VPAs:

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 20,
  "offset": 0
}
```

Fetch the next 20 blocked VPAs:

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 20,
  "offset": 20
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Must be non-empty and must belong to the authenticated merchant. Newton uses it during authentication to resolve the active merchant-customer and customer profiles. |
| `limit` | integer | Yes | No default. | Maximum number of blocked VPA rows to return. Must be greater than `0`. There is no route-specific maximum in this API's request validator; use a reasonable page size agreed during onboarding. |
| `offset` | integer | Yes | No default. | Number of matching rows to skip before returning results. Must be greater than or equal to `0`. This is a raw row offset, not a page number. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp used by JWS/JWE request validation. Required for signed/encrypted request bodies. Send a current 13-digit epoch milliseconds value. |
| `udfParameters` | string | No | Omitted from the response when omitted from the request. | JSON-object string for merchant-defined metadata. Must parse as a JSON object string and must not contain characters rejected by Newton validation, including `/`, `$`, `-`, `*`, `!`, `%`, `~`, or the backtick character. Echoed in the top-level response when supplied. |

There are no nested business request objects for this API. The only nested request objects are the standard JWS/JWE transport envelopes.

### Defaults and Omitted Field Behavior

There are no business defaults for `merchantCustomerId`, `limit`, or `offset`; all three must be sent.

Optional fields behave as follows:

- `iat`: required only by encrypted/signed request transport. It is not stored and is not returned.
- `udfParameters`: not stored by this read-only API. If supplied and valid, it is echoed in the top-level response.
- `customerMobileNumber` in the response: included only when multibank handling is enabled for this API and merchant; otherwise omitted.

### Request Examples

#### First Page

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 10,
  "offset": 0,
  "udfParameters": "{\"requestId\":\"blocklist001\"}"
}
```

#### Second Page Using Row Offset

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 10,
  "offset": 10
}
```

Newton skips the 10 most recently updated blocked contacts and returns up to 10 more rows.

#### Signed or Encrypted Business Body

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 25,
  "offset": 0,
  "iat": "1782968400000"
}
```

When sending a real request, generate `iat` and `x-timestamp` at request time so they are within Newton's configured freshness window.

## Validation and Processing Behavior

Newton performs these checks before returning the list:

- Parses and unwraps the `EncRequest` transport.
- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- For JWS/JWE requests, validates the request `kid`, signature, and `iat`.
- For plain unsigned requests, validates `x-merchant-signature` and `x-timestamp`.
- Checks merchant API block/allow configuration for the `listBlockedVpas` service.
- Checks the source IP when merchant `whitelistedIps` configuration is present.
- Resolves `merchantCustomerId` to an active merchant-customer profile for the authenticated merchant.
- Resolves the linked customer profile from the merchant-customer record.
- Validates the business payload: non-empty `merchantCustomerId`, `limit > 0`, `offset >= 0`, and valid `udfParameters` if supplied.
- Reads active contact rows where status is `BLOCKED` for the merchant customer.
- Orders rows by contact `updatedAt` descending.
- Decrypts stored PII for `payeeVpa`, contact name, and, where multibank response handling is enabled, customer mobile number.
- Builds a success response with `blockedVpas`. No matching rows are returned as success with an empty array.

## Response

Successful decrypted business responses use this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when the list operation completed. |
| `responseCode` | string | `SUCCESS` when the list operation completed. |
| `responseMessage` | string | `SUCCESS` when the list operation completed. |
| `payload` | object | Blocked VPA list payload. Always present on success. |
| `udfParameters` | string | Echo of request `udfParameters`; omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number from the resolved customer profile after PII decryption and leading-zero trimming. Included only when multibank handling is enabled for this API and merchant. |
| `blockedVpas` | array | Blocked contact VPAs for the requested merchant customer, ordered by most recent update first. Empty when there are no matching active blocked contacts. |

### `blockedVpas[]`

| Field | Type | Description |
| --- | --- | --- |
| `payeeVpa` | string | Blocked contact VPA after PII decryption. |
| `name` | string | Contact nickname/display name after decryption. For newly created block contacts, this is usually the payee name supplied during the block call or the VPA local part before `@` when no name was supplied. |
| `blockedAt` | string | Contact `updatedAt` timestamp formatted by Newton. This is the last block/update timestamp for the contact row, not a guaranteed immutable first-block timestamp. |

## Success Response Examples

### Blocked VPAs Returned

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "blockedVpas": [
      {
        "payeeVpa": "unknownshop@examplebank",
        "name": "Unknown Shop",
        "blockedAt": "2026-07-02 10:20:30"
      },
      {
        "payeeVpa": "fraudreport@examplebank",
        "name": "fraudreport",
        "blockedAt": "2026-07-01 18:45:10"
      }
    ]
  },
  "udfParameters": "{\"requestId\":\"blocklist001\"}"
}
```

### No Matching Blocked VPAs

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "blockedVpas": []
  }
}
```

In the second example, `customerMobileNumber` is omitted because that field is only populated when multibank handling is enabled for this API and merchant.

## Failure Handling

Failure responses use the standard Newton S2S error body where possible. Depending on where the failure occurs, HTTP status may be `200`, `400`, `401`, or `500`; clients should inspect the decrypted business body.

Newton error bodies omit `payload` when there is no error payload.

### Validation Failures

Validation runs after merchant authentication and before the contact list query.

Empty `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId field is empty\""
}
```

`limit` equal to `0`, negative `limit`, or negative `offset`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Value is not valid\""
}
```

Invalid `udfParameters`, for example a non-JSON-object string or a string containing restricted characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

When more than one validator fails, Newton can combine validation messages into one comma-separated `responseMessage`.

Malformed JSON, missing required fields, or type mismatches can fail while parsing the request before business validation. Parser wording depends on the JSON layer and transport mode. A signed-payload parse failure for a missing field can look like:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"limit\" not found"
}
```

Client handling: fix the payload and regenerate the S2S signature/envelope before retrying.

### Authentication, Encryption, and Signature Failures

Authentication failures occur before product logic runs. Common causes include missing merchant headers, unknown merchant/channel ids, failed JWS verification, failed JWE decryption, invalid plain-body merchant signature, missing raw timestamp data, or IP allowlist failure.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Missing `iat` in a JWS/JWE business payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
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

Malformed timestamp in `x-timestamp` or signed/encrypted `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired timestamp outside the configured freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Malformed decrypted JWE payload or malformed JWS payload can return an `INVALID_DATA` body whose `responseMessage` contains the JSON parser error. The exact parser text can vary by payload shape.

### Merchant Configuration and API Access Failures

Newton checks whether `listBlockedVpas` is blocked or excluded by the merchant's allow-list configuration. If this API is not enabled for the merchant or configured sub-merchant, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: contact Newton onboarding/support to enable the API or correct merchant/sub-merchant configuration. Do not retry unchanged requests.

### Merchant Customer and Customer Lookup Failures

If the authenticated merchant does not have an active profile for `merchantCustomerId`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

If the merchant-customer profile does not have an active linked customer/device binding:

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

Client handling: correct the `merchantCustomerId` or complete customer onboarding before retrying.

### Datastore, PII, and Response Construction Failures

This endpoint does not call NPCI in the direct list path. It reads Newton contact storage and decrypts stored PII. Storage errors, PII decryption failures, missing required contact VPA data, response signing/encryption failures, or other unexpected exceptions can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry transient internal failures with backoff. Escalate repeated failures with Newton support, including your request id, `merchantCustomerId`, `limit`, `offset`, and timestamp.

## Retry and Client Handling Guidance

- This is a read-only API, so retrying a successfully authenticated request does not create duplicate records.
- Regenerate `x-timestamp`, `iat`, and `x-merchant-signature` or JWS/JWE envelope for every retry; stale signed material can fail even when the business payload is unchanged.
- Retry transient network errors and `INTERNAL_SERVER_ERROR` with exponential backoff.
- Do not retry `BAD_REQUEST`, `UNAUTHORIZED`, `API NOT ENABLED`, `REQUEST_EXPIRED`, or merchant-customer lookup failures without fixing the payload, clock, credentials, or merchant configuration.
- Page using raw row offsets: next `offset = previous offset + number of rows requested` or `previous offset + number of rows received`, depending on your reconciliation strategy.
- Because this is not a snapshot cursor, avoid long delays between page requests if the customer may be actively blocking or unblocking payees.
- Treat an empty `blockedVpas` array as a successful "no blocked VPAs found" result.
- Store the request `merchantCustomerId`, `limit`, `offset`, response timestamp from your system, and returned `blockedAt` values if you need audit or reconciliation metadata.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:260)
- Route handler and authentication flow: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2104)
- S2S envelope request/response types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request payload verification: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:65)
- Merchant signature, timestamp, API access, IP allowlist, and merchant-customer setup: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:368)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:405)
- Request and response helpers: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:376), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:460)
- Product list flow: [src/Newton/Product/Merchant/Vpa/BlockVpa.hs](../../src/Newton/Product/Merchant/Vpa/BlockVpa.hs:51)
- Response payload construction: [src/Newton/Product/Merchant/Vpa/Transformer.hs](../../src/Newton/Product/Merchant/Vpa/Transformer.hs:28)
- Blocked contact query and ordering: [src/Newton/Storage/QueriesMiddleware/Contact.hs](../../src/Newton/Storage/QueriesMiddleware/Contact.hs:51), [src/Newton/Storage/Queries/Contact.hs](../../src/Newton/Storage/Queries/Contact.hs:113), [src/Newton/Storage/Queries/Contact.hs](../../src/Newton/Storage/Queries/Contact.hs:225)
- Contact storage fields and status enum: [src/Newton/Types/Storage/Contact.hs](../../src/Newton/Types/Storage/Contact.hs:25), [src/Newton/Types/Storage/Contact.hs](../../src/Newton/Types/Storage/Contact.hs:55)
- PII decryption and contact reconstruction: [src/Newton/Utils/Passetto.hs](../../src/Newton/Utils/Passetto.hs:398), [src/Newton/Utils/Transformers/Transformer2.hs](../../src/Newton/Utils/Transformers/Transformer2.hs:293)
- Request validation and validation error wrapping: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:422), [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:928), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:234), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Merchant customer and customer lookup: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:106), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:503)
- Shared response/error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:797)
