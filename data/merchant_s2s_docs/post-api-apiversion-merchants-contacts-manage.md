# Manage Contact API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/contacts/manage`

## Overview

Manage Contact is a server-to-server API used to add, block, or unblock a customer's UPI contact for a merchant profile.

The merchant calls this API with a `merchantCustomerId`, payee VPA, and contact action. Newton validates the S2S payload, merchant signature, API access configuration, and customer profile, then creates or updates the contact record for that merchant customer.

Use this API when your backend needs to manage a customer's saved payee list or blocklist directly, for example after a customer marks a payee as trusted, blocks a suspicious payee, or unblocks a previously blocked payee.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Manage Contact helps merchants:

- Add a customer payee as an active contact.
- Block a payee VPA for one customer profile.
- Unblock a previously blocked payee VPA.
- Reconcile contact state through `POST /api/{apiVersion}/merchants/contacts/list` after a write operation.
- Optionally trigger Newton-side cleanup for pending collect or mandate requests from a newly blocked payee when the merchant configuration enables it.

This API manages contact state for a single onboarded merchant customer. It does not validate that the payee exists at NPCI, does not initiate payment, and does not return a server-side idempotency key.

## Integration Flow

1. Merchant backend identifies the customer profile by `merchantCustomerId`.
2. Merchant chooses `ADD`, `BLOCK`, or `UNBLOCK` and sends the payee VPA.
3. Merchant signs and encrypts the request using the configured Newton S2S process.
4. Newton verifies the encrypted/signed payload, merchant identity, request timestamp, API access, optional IP allowlist, and merchant-customer profile.
5. Newton validates the business payload and performs the requested contact state transition.
6. Merchant decrypts the response and uses top-level `status`, `responseCode`, and `responseMessage` as the operation result.
7. Merchant can call `contacts/list` to refresh the customer-facing contact list.

Important action behavior:

- `ADD` creates a new active contact. If the same customer already has a matching contact for the VPA, Newton rejects the request with `Contact already exists.`
- `BLOCK` creates a blocked contact when none exists, updates an existing contact to `BLOCKED`, and succeeds unchanged when the contact is already actively blocked.
- `UNBLOCK` requires an existing contact. If the contact is actively blocked, Newton updates it to `ACTIVE`; if it is already active, Newton returns the current contact state.
- `BLOCK` can asynchronously decline pending collect or mandate requests for the payee VPA when merchant configuration `declinePendingCollectOrMandateInManageContact` is enabled. The API response is based on the contact update and does not wait for the asynchronous decline work to finish.

## Endpoint

```http
POST /api/{apiVersion}/merchants/contacts/manage
```

### Path and Headers

| Name | Location | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | path | Yes | API route version shared during onboarding. |
| `Content-Type` | header | Yes | Use `application/json`. |
| `x-api-version` | header | Recommended | Response-version selector. Use a value greater than `0` when clients need `payload.payeeName` in the response. If omitted or invalid, Newton treats it as version `0`. |
| `x-merchant-id` | header | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | header | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | header | Conditional | Required only for configured sub-merchant flows. |
| `x-sub-merchant-channel-id` | header | Conditional | Required only for configured sub-merchant flows. |
| `x-timestamp` | header | Yes | Current request timestamp used for merchant signature and replay validation. |
| `x-merchant-signature` | header | Conditional | Required for unsigned/plain business payload transport. For JWS/JWE transport, request authentication is carried by the envelope. |
| `x-forwarded-for` | header | Conditional | Required when IP allowlisting is configured for the merchant. |

### Authentication and Encryption

The route accepts the standard Newton `EncRequest` transport:

- JWE encrypted payload with fields `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed payload with fields `payload`, `signature`, and `protected`.
- Plain business payload only where the merchant integration is configured to allow it.

For JWE transport, Newton decrypts the body, expects the decrypted content to be a signed payload, then verifies the signature. For JWS transport, Newton verifies the signature before parsing the business body. For unsigned/plain payload transport, Newton verifies `x-merchant-signature` over the merchant ids, timestamp, and raw body.

For encrypted or signed request bodies, send `iat` inside the decrypted business payload. Newton validates it as a timestamp before running the business flow. For unsigned/plain business payloads, `iat` is ignored by the signature layer.

## Request

### Required Minimum

Add a contact:

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "ravi@examplebank",
  "action": "ADD"
}
```

Block a contact:

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "fraudster@examplebank",
  "action": "BLOCK"
}
```

Unblock a contact:

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "ravi@examplebank",
  "action": "UNBLOCK"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. It must belong to the authenticated merchant and resolve to an active merchant-customer profile. Maximum length is 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen; the first character must be alphanumeric, plus, slash, or equals. |
| `payeeVpa` | string | Yes | No default. | Payee VPA to add, block, or unblock. Must be 3 to 255 characters and match `local-part@handle`, where both sides contain letters, numbers, dots, or hyphens. Newton lowercases the VPA for hashing/storage lookup but echoes the submitted value in the response. |
| `action` | string | Yes | No default. | Contact operation. Allowed values are `ADD`, `BLOCK`, and `UNBLOCK`. |
| `payeeName` | string | No | Omitted when not applicable. If omitted while creating a blocked contact, Newton derives the stored name from the VPA local part before `@`. | Optional payee display name. Used by `BLOCK` when creating or updating the contact nickname. Currently not applied by `ADD`; an added contact is named from the VPA local part. Must not be empty if supplied. |
| `udfParameters` | string | No | Omitted from the response when omitted from the request. | JSON-object string for merchant-defined metadata. It must parse as a JSON object string and must not contain restricted characters rejected by Newton validation. Echoed back in the top-level response when supplied and valid. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp used for encrypted/signed payload timestamp validation. Required for JWS/JWE transport; ignored for unsigned/plain payload transport. |

### Defaults and Omitted Field Behavior

There are no business defaults for `merchantCustomerId`, `payeeVpa`, or `action`; all three must be sent.

Optional fields behave as follows:

- `payeeName`: if omitted during `BLOCK`, a newly created contact uses the VPA local part as the name. If omitted while blocking an existing contact, Newton keeps the existing nickname. In `ADD`, the request value is not used for the stored nickname.
- `udfParameters`: not stored by the contact-management operation. When supplied and valid, it is echoed in the top-level response.
- `iat`: used only by the authentication layer for encrypted/signed payload timestamp validation.

There are no nested business request objects for this API. The only nested objects are the standard S2S JWE/JWS envelope objects used for transport.

### Request Examples

#### Add Active Contact

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "ravi@examplebank",
  "action": "ADD",
  "udfParameters": "{\"requestId\":\"contact-add-001\"}"
}
```

#### Block Contact With Payee Name

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "unknown-shop@examplebank",
  "payeeName": "Unknown Shop",
  "action": "BLOCK",
  "udfParameters": "{\"reason\":\"customer_reported\"}"
}
```

#### Unblock Contact

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "unknown-shop@examplebank",
  "action": "UNBLOCK"
}
```

#### Encrypted/Signed Payload Business Body

```json
{
  "merchantCustomerId": "CUST12345",
  "payeeVpa": "unknown-shop@examplebank",
  "payeeName": "Unknown Shop",
  "action": "BLOCK",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

## Response

Successful decrypted business responses use this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` when the contact-management operation completed. |
| `responseCode` | string | `SUCCESS` when the operation completed. |
| `responseMessage` | string | `SUCCESS` when the operation completed. |
| `payload` | object | Contact-management result. |
| `udfParameters` | string | Echo of request `udfParameters`; omitted when not supplied. |

Treat top-level `status`, `responseCode`, and `responseMessage` as the API operation result. The nested `payload.status` is the resulting contact state: `ACTIVE` or `BLOCKED`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number from the resolved customer profile, trimmed of leading zeroes. |
| `payeeVpa` | string | Payee VPA from the request. |
| `payeeName` | string | Payee nickname/display name after the operation. Present only when `x-api-version > 0`; omitted for version `0` or an omitted/invalid `x-api-version` header. |
| `action` | string | Action from the request: `ADD`, `BLOCK`, or `UNBLOCK`. |
| `status` | string | Resulting contact state. Allowed values are `ACTIVE` and `BLOCKED`. |

### Success Response: Add Contact

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
    "payeeVpa": "ravi@examplebank",
    "payeeName": "ravi",
    "action": "ADD",
    "status": "ACTIVE"
  },
  "udfParameters": "{\"requestId\":\"contact-add-001\"}"
}
```

For `ADD`, `payeeName` is typically derived from the VPA local part because the add path does not apply request `payeeName`.

### Success Response: Block Contact

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
    "payeeVpa": "unknown-shop@examplebank",
    "payeeName": "Unknown Shop",
    "action": "BLOCK",
    "status": "BLOCKED"
  },
  "udfParameters": "{\"reason\":\"customer_reported\"}"
}
```

### Success Response: Unblock Contact

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
    "payeeVpa": "unknown-shop@examplebank",
    "payeeName": "Unknown Shop",
    "action": "UNBLOCK",
    "status": "ACTIVE"
  }
}
```

### Response Versioning

Use `x-api-version: 1` or higher for new integrations that need `payload.payeeName`.

| `x-api-version` | Response behavior |
| --- | --- |
| Omitted, invalid, or `0` | Base response. `payload.payeeName` is omitted even when Newton has a nickname. |
| `1` or higher | `payload.payeeName` is included when available. |

Example base-version response:

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
    "payeeVpa": "ravi@examplebank",
    "action": "ADD",
    "status": "ACTIVE"
  }
}
```

## Error Handling

Failure responses use the standard Newton S2S error body. Depending on where the failure occurs, the HTTP status may be `200`, `400`, `401`, `422`, or `500`; clients should always inspect the decrypted business body.

When `payload` is empty, it is omitted from the JSON response.

Failure bodies include `status`, `responseCode`, and `responseMessage`; examples below show the concrete validation, authentication, access, and downstream values clients should handle.

### Validation Failures

Validation runs before the contact state transition.

Invalid `merchantCustomerId` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Invalid `payeeVpa` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"payeeVpa regex failed\""
}
```

Empty `payeeName` when the field is present:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"payeeName field is empty\""
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

Invalid `action` enum values, malformed JSON, or type mismatches can fail during JSON parsing before request validation. Treat these as non-retryable request errors and correct the payload.

### Authentication, Encryption, and Signature Failures

Authentication failures occur before product logic runs. Common causes include missing or invalid merchant headers, unknown merchant keys, failed JWS verification, failed JWE decryption, missing timestamp headers, stale timestamps, missing `iat` for encrypted/signed payloads, or failed IP allowlist checks.

Failed JWS verification, failed JWE decryption, invalid merchant signature, missing merchant signature, missing merchant headers, or IP allowlist failure:

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

Missing `kid` in a signed payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding KID"
}
```

Malformed decrypted JWE payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload"
}
```

### Merchant Configuration and Access Failures

Newton checks whether the API is blocked or allowed for the merchant before managing contacts. If this endpoint is disabled for the merchant or sub-merchant configuration, the response is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Contact Newton onboarding/support to enable the API or correct merchant configuration. Do not retry unchanged requests indefinitely.

### Merchant Customer and Customer Lookup Failures

If the authenticated merchant does not have an active profile for `merchantCustomerId`, Newton returns an invalid-data response:

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

These are normally non-retryable until the merchant customer is onboarded or the identifier is corrected.

### Contact Business Failures

Duplicate `ADD` for an existing contact:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Contact already exists."
}
```

`UNBLOCK` when no matching contact exists for the customer and VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Cannot unblock a non-existing contact."
}
```

`BLOCK` for a verified payee VPA is rejected. By default the response uses `INVALID_DATA`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Cannot block a verified payeeVpa."
}
```

When merchant configuration `throwSpecificErrorCode` is enabled, the same failure uses a specific response code:

```json
{
  "status": "FAILURE",
  "responseCode": "JPVB",
  "responseMessage": "Cannot block a verified payeeVpa."
}
```

`BLOCK` for the customer's own on-us VPA can be rejected when merchant configuration `disableSelfVpaBlocking` is enabled. By default it uses `INVALID_DATA`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Cannot block a self Vpa."
}
```

When `throwSpecificErrorCode` is enabled, the same failure uses:

```json
{
  "status": "FAILURE",
  "responseCode": "JPSBD",
  "responseMessage": "Cannot block a self Vpa."
}
```

### Datastore, Crypto, Downstream, and Unexpected Failures

The synchronous contact-management path reads and writes Newton storage, hashes/encrypts the VPA, decrypts the customer mobile number, and decrypts the stored contact nickname before responding. Storage failures, key/PII crypto failures, missing required stored values, or unexpected exceptions can surface as:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Shared Newton platform dependencies can also surface standard transient errors such as:

```json
{
  "status": "FAILURE",
  "responseCode": "GATEWAY_TIMEOUT",
  "responseMessage": "Timed out from NPCI"
}
```

or:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "UPI service is not reachable at the moment for transactional apis"
}
```

The optional pending collect/mandate decline work triggered by `BLOCK` runs asynchronously after the contact update is prepared. A failure in that asynchronous cleanup is not returned as the synchronous `contacts/manage` response.

## Retry and Client Handling Guidance

- This API has no `merchantRequestId` or idempotency key. Treat the customer/VPA/action combination as your client-side correlation data.
- `ADD` is not idempotent. A retry after a successful first attempt returns `Contact already exists.` If the first response is lost, call `contacts/list` or treat that duplicate error as evidence that the contact already exists.
- `BLOCK` is effectively safe to retry for the same customer and VPA: an already blocked active contact returns success with `payload.status = "BLOCKED"`.
- `UNBLOCK` is safe to retry only after confirming the contact exists. If no contact exists, Newton returns `Cannot unblock a non-existing contact.`
- Retry transient failures such as `INTERNAL_SERVER_ERROR`, `GATEWAY_TIMEOUT`, or `SERVICE_UNAVAILABLE...` with exponential backoff and jitter.
- Do not retry validation errors, `UNAUTHORIZED`, `API NOT ENABLED`, verified-payee block rejection, self-VPA block rejection, or lookup failures without changing the request or merchant configuration.
- Store the resulting `payload.status` alongside your customer/VPA state. For user-facing lists, refresh through `contacts/list` after successful writes.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:237)
- Route handler, merchant signature verification, cache invalidation, and transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2021)
- Request envelope and response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:16), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48), [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:69)
- S2S payload verification and JWS/JWE handling: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature, timestamp, API access, IP allowlist, and merchant-customer setup: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:131), [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- Merchant and customer lookup helpers: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:106), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:209), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:503)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:418)
- Request/response transformer helpers and response versioning: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:383), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:389)
- Request and response types plus request validator: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4901), [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4925), [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4937)
- Contact action and status enums: [src/Newton/Types/API/Contact.hs](../../src/Newton/Types/API/Contact.hs:20), [src/Newton/Types/Storage/Contact.hs](../../src/Newton/Types/Storage/Contact.hs:55)
- Product manage-contact flow and action behavior: [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:33), [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:57), [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:83), [src/Newton/Product/Merchant/Contact/ManageContact.hs](../../src/Newton/Product/Merchant/Contact/ManageContact.hs:133)
- Block-contact business validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:3274)
- Contact creation, lookup, and update helpers: [src/Newton/Storage/QueriesMiddleware/Contact.hs](../../src/Newton/Storage/QueriesMiddleware/Contact.hs:115), [src/Newton/Storage/QueriesMiddleware/Contact.hs](../../src/Newton/Storage/QueriesMiddleware/Contact.hs:187), [src/Newton/Storage/QueriesMiddleware/Contact.hs](../../src/Newton/Storage/QueriesMiddleware/Contact.hs:208)
- Response construction: [src/Newton/Product/Merchant/Contact/Helper.hs](../../src/Newton/Product/Merchant/Contact/Helper.hs:46)
- Common validators and validation error wrapping: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:311), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- `x-api-version` defaulting: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:960)
- Shared response and error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:70), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:79), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:142), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:761), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:797)
