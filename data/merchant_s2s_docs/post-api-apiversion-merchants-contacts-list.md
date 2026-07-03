# List Contacts API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/contacts/list`

## Overview

List Contacts is a server-to-server API used to fetch a customer's saved or blocked UPI contacts for a merchant profile.

The merchant calls this API with a `merchantCustomerId`, contact `status`, and page controls. Newton validates the merchant request, resolves the merchant customer and customer profile, reads the matching contacts, decrypts PII fields where required, and returns the requested page.

Use this API when your backend needs to show or reconcile the customer's current contact state, for example before rendering a payee/contact list, after a contact-management operation, or when checking which VPAs are currently blocked for that customer.

## Business Use Case

List Contacts helps merchants:

- Fetch contacts for one onboarded merchant customer.
- Separate active contacts from blocked contacts using the `status` filter.
- Page through large contact lists without transferring the full contact set.
- Reconcile state after `POST /api/{apiVersion}/merchants/contacts/manage`.
- Display the customer's latest contact action date for each returned VPA.

This API is read-only. It does not create, update, block, unblock, or delete contacts.

## Integration Flow

1. Merchant backend chooses the customer profile by `merchantCustomerId`.
2. Merchant selects `ACTIVE` or `BLOCKED` and sends `limit` plus zero-based page `offset`.
3. Merchant signs and encrypts the request using the Newton S2S integration process.
4. Newton verifies the encrypted/signed payload, merchant signature, timestamp, IP allowlist, and API access configuration.
5. Newton resolves the active merchant customer and customer profile.
6. Newton reads matching contacts ordered by most recent update first.
7. Merchant decrypts the response and uses `status`, `totalPages`, and `contacts` for display or reconciliation.

Important behavior:

- `offset` is a page number, not a raw row offset. Newton calculates the datastore offset as `offset * limit`.
- Empty pages are returned as successful responses with `contacts: []`.
- `totalPages` is calculated from the total number of matching contacts and the requested `limit`.
- Contact PII, including VPA and customer mobile number, is decrypted before the business response is built.

## Endpoint

```http
POST /api/{apiVersion}/merchants/contacts/list
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Current request timestamp used for signature validation. |
| `x-merchant-signature` | Required for unsigned/plain business payload transport. |
| `x-forwarded-for` | Required when IP allowlisting is configured for the merchant. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. Depending on the configured transport, the request can be a JWE/JWS envelope or a plain business payload with merchant signature verification. For encrypted or signed transport, include `iat` inside the decrypted business payload when required by the integration; Newton validates it as a timestamp before running the business flow.

## Request

### Required Minimum

Fetch the first page of active contacts:

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 20,
  "offset": 0,
  "status": "ACTIVE"
}
```

Fetch the first page of blocked contacts:

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 20,
  "offset": 0,
  "status": "BLOCKED"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. It must belong to the authenticated merchant and resolve to an active merchant-customer profile. Maximum length is 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen; the first character must be alphanumeric, plus, slash, or equals. |
| `limit` | integer | Yes | No default. | Page size. Must be greater than `0` and less than or equal to the configured `LIST_CONTACTS_RESPONSE_MAX_PAGE_SIZE`. The current default maximum is `100` unless configured differently for the environment. |
| `offset` | integer | Yes | No default. | Zero-based page number. Send `0` for the first page, `1` for the second page, and so on. Must be greater than or equal to `0`. |
| `status` | string | Yes | No default. | Contact status filter. Allowed values are `ACTIVE` and `BLOCKED`. |
| `udfParameters` | string | No | Omitted from the response when omitted from the request. | JSON-object string for merchant-defined metadata. Echoed back in the response when supplied. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used for encrypted/signed payload timestamp validation where applicable. Required for encrypted/signed request bodies, not used for unsigned/plain payload bodies. |

### Defaults and Omitted Field Behavior

There are no business defaults for `merchantCustomerId`, `limit`, `offset`, or `status`; all four must be sent.

Optional fields behave as follows:

- `udfParameters`: not stored by this read-only API. When supplied and valid, it is echoed in the top-level response.
- `iat`: only used by the authentication layer for encrypted/signed payload timestamp validation.

There are no nested business request objects for this API. The only nested objects are the standard S2S JWE/JWS envelope objects used for transport.

### Request Examples

#### Active Contacts, First Page

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 20,
  "offset": 0,
  "status": "ACTIVE",
  "udfParameters": "{\"requestId\":\"contact-list-001\"}"
}
```

#### Active Contacts, Second Page

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 20,
  "offset": 1,
  "status": "ACTIVE"
}
```

Newton reads rows `20` through `39` for this request because `offset` is multiplied by `limit`.

#### Blocked Contacts

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 10,
  "offset": 0,
  "status": "BLOCKED"
}
```

#### Encrypted/Signed Payload Business Body

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 10,
  "offset": 0,
  "status": "BLOCKED",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

## Response

### Response Envelope

Successful decrypted business responses use this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when the list operation completed. |
| `responseCode` | string | `SUCCESS` when the list operation completed. |
| `responseMessage` | string | `SUCCESS` when the list operation completed. |
| `payload` | object | Contact-list payload. |
| `udfParameters` | string | Echo of request `udfParameters`; omitted when not supplied. |

Treat top-level `status`, `responseCode`, and `responseMessage` as the operation result. The `payload.status` field is the contact status filter that was applied, not a second success/failure indicator.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `status` | string | Contact status filter used for this page: `ACTIVE` or `BLOCKED`. |
| `totalPages` | integer | Number of pages for the requested `status` and `limit`. `0` means there are no matching contacts. |
| `customerMobileNumber` | string | Customer mobile number from the resolved customer profile, trimmed of leading zeroes. |
| `contacts` | array | Contacts on the requested page, ordered by most recent update first. Empty when the page has no rows. |

### `contacts[]`

| Field | Type | Description |
| --- | --- | --- |
| `payeeVpa` | string | Contact VPA. |
| `lastActionDate` | string | Contact `updatedAt` timestamp formatted by Newton. This represents when the contact was last added, blocked, unblocked, or otherwise updated. |

### Success Response With Contacts

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "status": "ACTIVE",
    "totalPages": 2,
    "customerMobileNumber": "919876543210",
    "contacts": [
      {
        "payeeVpa": "ravi@examplebank",
        "lastActionDate": "2026-07-02 10:20:30"
      },
      {
        "payeeVpa": "store123@upi",
        "lastActionDate": "2026-07-01 18:45:10"
      }
    ]
  },
  "udfParameters": "{\"requestId\":\"contact-list-001\"}"
}
```

### Success Response With No Matching Contacts

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "status": "BLOCKED",
    "totalPages": 0,
    "customerMobileNumber": "919876543210",
    "contacts": []
  }
}
```

### Interpreting Pagination

- Continue requesting pages while `offset + 1 < totalPages`.
- Stop when `contacts` is empty or when the requested page is the last page.
- If contacts change between page requests, the page contents and `totalPages` can change because this API reads current state each time.

## Error Handling

Failure responses use the standard Newton S2S error body. Depending on where the failure occurs, the HTTP status may be `200`, `400`, `401`, or `500`; clients should always inspect the decrypted business body.

Failure bodies include `status`, `responseCode`, and `responseMessage`; `payload` is usually `null` for validation and authentication failures.

### Validation Failures

Validation runs before the contact lookup.

Invalid `merchantCustomerId` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\"",
  "payload": null
}
```

Invalid `limit` or `offset`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Value is not valid\"",
  "payload": null
}
```

`limit` above the configured page-size maximum:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"limit field value is not between 0 and 100\"",
  "payload": null
}
```

Invalid `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\"",
  "payload": null
}
```

Invalid `status` enum values, malformed JSON, or type mismatches can fail during JSON parsing before request validation. Treat these as non-retryable request errors and correct the payload.

### Authentication, Encryption, and Signature Failures

Authentication failures occur before product logic runs. Common causes include missing or invalid merchant headers, failed JWE decryption, failed JWS/signature verification, missing raw body/timestamp headers, stale timestamp, missing `iat` for encrypted/signed payloads, or failed IP allowlist checks.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

### Merchant Configuration and Access Failures

Newton checks whether the API is blocked or allowed for the merchant before listing contacts. If this endpoint is disabled for the merchant or sub-merchant configuration, the response is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

Contact Newton onboarding/support to enable the API or correct merchant configuration. Do not retry unchanged requests indefinitely.

### Merchant Customer and Customer Lookup Failures

If the authenticated merchant does not have an active profile for `merchantCustomerId`, Newton returns an invalid-data response:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found",
  "payload": null
}
```

If the linked customer profile cannot be resolved:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found",
  "payload": null
}
```

These are normally non-retryable until the merchant customer is onboarded or the identifier is corrected.

### Datastore and Downstream PII Failures

The list operation reads contact rows from Newton storage and decrypts stored PII before responding. This endpoint does not call NPCI in the direct list path. Storage errors, PII decryption failures, or missing required contact data can surface as an internal error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

### Unexpected Errors

Unexpected failures in request processing, response signing/encryption, datastore access, or response construction use the standard internal-error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

## Retry and Client Handling Guidance

- This is a read-only API, so retrying the same request does not create duplicate contacts.
- Retry transient `INTERNAL_SERVER_ERROR` failures with exponential backoff.
- Do not retry validation errors, `UNAUTHORIZED`, `API NOT ENABLED`, or lookup errors without changing the request or merchant configuration.
- Because the response is not a snapshot across pages, avoid long gaps between page requests if the customer may be actively changing contacts.
- For reconciliation, store the requested `status`, `limit`, `offset`, `totalPages`, and response timestamp from your own system; the API does not return a server-side cursor or idempotency key.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:243)
- Route handler and authentication flow: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2044)
- Request payload verification: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:65)
- Merchant signature, timestamp, API access, and merchant-customer setup: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:48)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:426)
- Request/response transformer helpers: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:403)
- Request and response types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4973)
- Product list flow and pagination: [src/Newton/Product/Merchant/Contact/ListContacts.hs](../../src/Newton/Product/Merchant/Contact/ListContacts.hs:22)
- Related contact state mutations: [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:33), [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:66), [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:92), [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:142)
- Response construction: [src/Newton/Product/Merchant/Contact/Helper.hs](../../src/Newton/Product/Merchant/Contact/Helper.hs:74)
- Contact query filters and ordering: [src/Newton/Storage/QueriesMiddleware/Contact.hs](../../src/Newton/Storage/QueriesMiddleware/Contact.hs:55), [src/Newton/Storage/Queries/Contact.hs](../../src/Newton/Storage/Queries/Contact.hs:96), [src/Newton/Storage/Queries/Contact.hs](../../src/Newton/Storage/Queries/Contact.hs:225)
- Contact response item and status enum: [src/Newton/Types/API/Contact.hs](../../src/Newton/Types/API/Contact.hs:26), [src/Newton/Types/Storage/Contact.hs](../../src/Newton/Types/Storage/Contact.hs:55)
- Request validators and validation error wrapping: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4997), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:234), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:311), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4690)
- Page-size configuration default: [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs:2546)
- Shared response/error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:797)
