# Block And Spam API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/blockAndSpam`

## Overview

Block And Spam is a merchant server-to-server API used when a customer reports the payee VPA of an incoming UPI collect request or mandate as unwanted.

The merchant calls this API with the customer profile, the original `upiRequestId`, the payee VPA shown to the customer, and text flags that identify whether Newton should block the payee VPA for that customer and/or mark it as spam. Newton validates the referenced transaction or mandate, confirms that the submitted payee VPA matches the stored payee, rejects verified payees, and then records the block/spam action.

Payloads use the standard Newton encrypted/signed server-to-server envelope. The examples below show the decrypted business payload for readability.

## Business Use Case

Use this API when a merchant app lets a customer report an incoming collect or mandate request as spam or block the sender/payee VPA.

Block And Spam helps merchants:

- Block a payee VPA in the customer's Newton contact list after the customer reports it.
- Record a spam signal against the referenced collect transaction or mandate.
- Accumulate spam reports so Newton can block a repeatedly reported VPA at the platform level.
- Optionally auto-decline pending collect requests or pending mandate requests from the same payee VPA when the merchant configuration `declinePendingCollectOrMandateInBlockAndSpam` is enabled.
- Prevent a customer from blocking a payee VPA that Newton has already identified as verified in the referenced transaction or mandate.

## Integration Flow

1. Customer receives or views an incoming UPI collect request or mandate request.
2. Merchant shows the payee VPA and gives the customer a report/block action.
3. Merchant calls `blockAndSpam` with the customer profile id, original `upiRequestId`, payee VPA, and action flags.
4. Newton authenticates the merchant request and resolves the merchant customer and customer from `merchantCustomerId`.
5. Newton locates the referenced collect transaction by default, or the referenced mandate when `requestType` is `MANDATE`.
6. Newton verifies that `payeeVpa` matches the payee VPA/hash stored on the referenced transaction or mandate.
7. Newton rejects the request if the stored payee is marked as verified.
8. Newton blocks the contact and/or records the spam signal according to the request flags.
9. Newton returns a success response with the action status in `payload.status`.

Important identifiers:

- `merchantCustomerId`: Merchant's customer profile id. Newton uses it for authentication context, contact updates, spam records, and optional pending-request auto-decline.
- `upiRequestId`: UPI request id of the original payer-side collect transaction or payer-side mandate.
- `payeeVpa`: Payee VPA being reported. It must match the referenced transaction or mandate.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/blockAndSpam
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment assigned during onboarding. The current product logic for this API does not branch on this value. |

### Headers

Use the headers and key material shared during Newton S2S onboarding.

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | API version header used by Newton S2S integrations. Use the version shared during onboarding. |
| `x-merchant-id` | Yes | Merchant id used by the authentication middleware. |
| `x-merchant-channel-id` | Yes | Merchant channel id used by the authentication middleware. |
| `x-timestamp` | Yes | 13-digit epoch timestamp in milliseconds. Newton accepts timestamps within a 30 minute clock-skew window. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payload integrations. JWS/JWE integrations use the configured signed/encrypted envelope. |
| `Authorization` | Conditional | Send only if it is part of the merchant's onboarding configuration. |
| `x-forwarded-for` | Conditional | Used for IP allow-list checks when the merchant is configured with whitelisted IPs. Usually supplied by the gateway/proxy layer. |

Authentication and encryption follow the standard Newton S2S process. The route uses `merchantSignatureVerificationV2`, checks blocked/allowed API configuration, validates timestamp freshness, binds `MerchantCustomerKey` and `CustomerKey` from `merchantCustomerId`, clears the merchant-customer KV cache entry, and then invokes product logic.

### Request Envelope

Route request type: `API.EncRequest API.BlockSpamRequest`.

The outer request can be one of the standard Newton S2S envelope shapes:

- JWE encrypted payload with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed payload with `payload`, `signature`, and `protected`.
- Plain decrypted business payload when explicitly enabled for the merchant.

For JWE/JWS requests, include `iat` in the decrypted business payload. The route validates it as a 13-digit epoch-milliseconds timestamp within the same 30 minute freshness window. For plain payloads, `iat` is not required by this route, but `x-timestamp` is still checked.

## Request

### Required Minimum

Block a transaction payee VPA and report it as spam:

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "YBL12345678901234567890",
  "payeeVpa": "unwanted-payee@bank",
  "shouldBlock": "true",
  "shouldSpam": "true",
  "requestType": "TRANSACTION"
}
```

Mark a transaction payee VPA as spam without blocking the customer contact:

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "YBL12345678901234567891",
  "payeeVpa": "suspect-payee@bank",
  "shouldBlock": "false",
  "shouldSpam": "true",
  "requestType": "TRANSACTION"
}
```

Block a mandate payee VPA:

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "YBLMANDATE123456789",
  "payeeVpa": "mandate-payee@bank",
  "shouldBlock": "true",
  "shouldSpam": "true",
  "requestType": "MANDATE"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer profile id. Must be 1 to 256 characters and match Newton's merchant-customer id format: starts with an alphanumeric, `+`, `/`, or `=`, followed by alphanumeric, `.`, `_`, `+`, `/`, `=`, or `-` characters. It must resolve to a merchant customer under the authenticated merchant. |
| `iat` | string | Conditional | Required for signed/encrypted envelopes. Ignored by this route for plain payloads. | Issued-at timestamp in epoch milliseconds. Must be a valid 13-digit timestamp within 30 minutes of Newton server time. |
| `upiRequestId` | string | Yes | No default. | UPI request id of the original collect transaction or mandate. Must be 1 to 35 alphanumeric characters. |
| `payeeVpa` | string | Yes | No default. | Payee VPA to report or block. Request validation only checks that it is non-empty; product logic then verifies that it matches the payee VPA/hash stored on the referenced transaction or mandate. |
| `shouldBlock` | string | Yes | No default. | Text flag. Only exact lowercase `"true"` triggers customer-contact blocking. Send `"false"` when the customer is only reporting spam. Empty string is rejected. Other non-empty values pass request validation but are treated as not true by product logic. |
| `shouldSpam` | string | Yes | No default. | Text flag. Only exact lowercase `"true"` triggers spam-only handling when `shouldBlock` is not `"true"`. Empty string is rejected. When `shouldBlock` is `"true"`, Newton records a spam signal even if `shouldSpam` is `"false"`. |
| `requestType` | string | No | If omitted, Newton uses the transaction path. | Allowed enum values are `TRANSACTION`, `MANDATE`, and `MANAGEMENT`. Use `MANDATE` for mandates. Omitted, `TRANSACTION`, and `MANAGEMENT` all route to the collect-transaction path in the current product code. Do not use `MANAGEMENT` unless Newton explicitly enables that behavior for your integration. |
| `udfParameters` | string | No | Omitted from the response when not supplied. | Merchant-defined metadata as a JSON-object string, for example `"{\"caseId\":\"CASE123\"}"`. It must parse as a JSON object and avoid punctuation disallowed by Newton's UDF validator, such as `/`, `$`, `*`, `!`, `%`, `~`, and the backtick character. Echoed in the success response. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and must be sent when required by the field table.

- `requestType`: omitted means transaction collect flow. Send `MANDATE` for mandate reports.
- `iat`: required for signed/encrypted envelopes; not required for plain payloads.
- `udfParameters`: omitted means it is not returned.
- `shouldBlock` and `shouldSpam`: no default. Both fields are required non-empty strings. Use exact `"true"` or `"false"`.

Avoid sending both `shouldBlock` and `shouldSpam` as `"false"`. The current product path returns success with `payload.status = "SPAMMED"` when `shouldBlock` is not `"true"`, even if `shouldSpam` is also not `"true"`, but no block or spam mutation is performed in that case.

## Request Examples

### Block And Report Spam For A Collect

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "YBL12345678901234567890",
  "payeeVpa": "unwanted-payee@bank",
  "shouldBlock": "true",
  "shouldSpam": "true",
  "requestType": "TRANSACTION",
  "iat": "1783000000000",
  "udfParameters": "{\"caseId\":\"CASE123\",\"source\":\"customer_app\"}"
}
```

The `iat` value above illustrates the required 13-digit epoch-milliseconds format. Generate a fresh timestamp for every signed or encrypted production request.

### Spam Only For A Collect

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "YBL12345678901234567891",
  "payeeVpa": "suspect-payee@bank",
  "shouldBlock": "false",
  "shouldSpam": "true",
  "requestType": "TRANSACTION"
}
```

### Block And Report Spam For A Mandate

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "YBLMANDATE123456789",
  "payeeVpa": "mandate-payee@bank",
  "shouldBlock": "true",
  "shouldSpam": "true",
  "requestType": "MANDATE"
}
```

## Validation and Processing Behavior

### Request Validation

Newton applies structural request validation after decrypting/parsing the business payload:

- `merchantCustomerId` must pass merchant-customer id length and format validation.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `payeeVpa`, `shouldBlock`, and `shouldSpam` must be non-empty strings.
- `requestType`, when supplied, must decode to one of `TRANSACTION`, `MANDATE`, or `MANAGEMENT`.
- `udfParameters`, when supplied, must be a JSON-object string that passes Newton's UDF character validation.

The request validator does not enforce boolean-string validation for `shouldBlock` or `shouldSpam`. Product logic compares them to exact lowercase `"true"`.

### Transaction vs Mandate Selection

`requestType = "MANDATE"` selects the mandate path.

Any other value accepted by the type, including omitted `requestType`, `TRANSACTION`, or `MANAGEMENT`, selects the transaction path.

The transaction path searches for a payer-side collect transaction using:

- `upiRequestId` from the request
- transaction role `PAYER`
- transaction type `COLLECT`
- `selfInitiated = false`
- the latest three transaction partitions

The mandate path searches for a payer-side mandate using:

- `upiRequestId` from the request
- mandate role `PAYER`

### Payee Validation

After Newton finds the transaction or mandate, it compares the request `payeeVpa` with the stored payee VPA and/or payee VPA hash. If they do not match, the API fails with `Invalid payeeVpa`.

If the stored payee information marks the payee as verified, the API fails with `Cannot block a verified payeeVpa`.

### Action Semantics

The fields are processed as text flags:

| Request flags | Product behavior | Response `payload.status` |
| --- | --- | --- |
| `shouldBlock = "true"` and any `shouldSpam` value | Creates or updates a blocked contact for the customer, records a spam signal for the referenced transaction/mandate, and evaluates the global VPA spam threshold. | `BLOCKED` |
| `shouldBlock != "true"` and `shouldSpam = "true"` | Records a spam signal for the referenced transaction/mandate and evaluates the global VPA spam threshold. Does not block the customer contact. | `SPAMMED` |
| `shouldBlock != "true"` and `shouldSpam != "true"` | No block or spam mutation is performed. The current response transformer still returns success with `payload.status = "SPAMMED"`. Treat this as an invalid client state and avoid sending it. | `SPAMMED` |

Blocking a contact is idempotent for an already blocked, active contact belonging to the same customer. If the contact does not exist, Newton creates it with status `BLOCKED`. If the contact exists but is not active/blocked for the same customer, Newton updates the contact to blocked for this customer.

Spam recording uses find-or-create behavior for the referenced transaction or mandate, payee VPA/hash, and customer. Repeating the same successful request does not produce a duplicate-request response.

### Spam Threshold and Global VPA Blocking

Each spam/block action contributes a `SPAM` record. Newton compares spam count minus unspam count for the payee VPA:

- If the VPA is not already globally blocked, the count window starts one day before the current time.
- If the VPA is already globally blocked, the count window starts from the existing `blockedUpto` value.
- When `spamCount - unspamCount >= 5`, Newton creates or extends a global blocked-VPA record.
- For an existing global block, the next `blockedUpto` extension is 7 days while the stored block count is less than 2, and 180 days after that threshold.

This global blocked-VPA behavior is internal to Newton. It is not returned in the `blockAndSpam` response body.

### Optional Pending Request Auto-Decline

If merchant configuration `declinePendingCollectOrMandateInBlockAndSpam` is enabled:

- A successful transaction block forks an async flow to decline pending collect requests for the same customer, merchant customer, and payee VPA.
- A successful mandate block forks an async flow to decline pending mandate requests for the same customer, merchant customer, and payee VPA.

This async flow does not change the immediate API response. Failures in the forked decline flow are logged separately and may surface through the normal transaction/mandate status or callback flow.

## Response

### Response Envelope

Route response type: `RespHeaders (API.EncResponse API.BlockSpamResponse)`.

The decrypted business response has this shape on success:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Block/spam result. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `payeeVpa` | string | Payee VPA from the request. |
| `status` | string | `BLOCKED` when `shouldBlock` is exact `"true"`; otherwise `SPAMMED`. |
| `gatewayResponseCode` | string | Constant success code `00`. |
| `gatewayResponseMessage` | string | Constant success message `Vpa blocked/spammed successfully`. |

`upiRequestId` and `requestType` are not returned in this API response. Store them from the request for audit/reconciliation.

### Example Success Response - Blocked

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "payeeVpa": "unwanted-payee@bank",
    "status": "BLOCKED",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Vpa blocked/spammed successfully"
  },
  "udfParameters": "{\"caseId\":\"CASE123\",\"source\":\"customer_app\"}"
}
```

### Example Success Response - Spam Only

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "payeeVpa": "suspect-payee@bank",
    "status": "SPAMMED",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Vpa blocked/spammed successfully"
  }
}
```

## Error Handling

Failure responses use the same encrypted/signed/plain response transport as other Newton S2S APIs. The examples below show decrypted bodies.

Clients should read `status`, `responseCode`, and `responseMessage` from the body. HTTP status varies by layer:

- request-body validation can return HTTP `200` with a failure body
- timestamp format failures return HTTP `400`
- authentication and API allow-list failures return HTTP `401`
- business validation failures return HTTP `422`
- unexpected server/storage/crypto failures return HTTP `500` or HTTP `200` with `INTERNAL_SERVER_ERROR` depending on the layer

When `payload` is empty, it is omitted from the JSON response.

### Validation and Auth Failure Bodies

For parser-level failures, such as a missing required JSON key, the exact `responseMessage` is generated by the JSON decoder and can include the concrete key name or type path. This representative body shows the integration shape:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"upiRequestId\" not found"
}
```

| Scenario | Response body |
| --- | --- |
| `merchantCustomerId` is empty or too long | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` |
| `merchantCustomerId` has an invalid format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| `upiRequestId` is empty or longer than 35 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"upiRequestId length is not between 1 and 35\""}` |
| `upiRequestId` contains non-alphanumeric characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"upiRequestId regex match failed\""}` |
| `payeeVpa` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"payeeVpa field is empty\""}` |
| `shouldBlock` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"shouldBlock field is empty\""}` |
| `shouldSpam` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"shouldSpam field is empty\""}` |
| `udfParameters` is not a JSON-object string or fails UDF character validation | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| `requestType` is not a decodable enum value such as `TRANSACTION`, `MANDATE`, or `MANAGEMENT` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $.requestType: parsing RequestTypeForBlockSpam failed"}` |
| JWE/JWS payload omits `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| `iat` or `x-timestamp` is not a valid 13-digit timestamp | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` |
| `iat` or `x-timestamp` is outside the 30 minute freshness window | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` |
| Missing merchant auth headers, missing raw body/timestamp context, IP allow-list failure, or signature mismatch | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| JWE/JWS source validation or payload signature verification fails | `{"status":"FAILURE","responseCode":"AUTH_FAILURE","responseMessage":"AUTH_FAILURE"}` |
| API is blocked or not present in the merchant's allowed API list | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |

### Business Failure Bodies

| Scenario | Response body |
| --- | --- |
| `merchantCustomerId` does not map to a merchant customer under the authenticated merchant, or the merchant customer is inactive | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"User profile not found"}` |
| Merchant customer exists but has no active customer/device binding where required by customer resolution | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer"}` |
| Customer mapped to the merchant customer is not found or inactive | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Customer not found"}` |
| Transaction path cannot find a payer-side collect transaction for `upiRequestId` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Transaction not found"}` |
| Mandate path cannot find a payer-side mandate for `upiRequestId` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Mandate not found"}` |
| `payeeVpa` does not match the payee on the referenced transaction or mandate | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid payeeVpa"}` |
| Referenced transaction or mandate has payee info marked as verified | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Cannot block a verified payeeVpa"}` |
| Stored transaction/mandate data required for hashing/comparison is missing, existing contact has no status, or storage/cache/encryption fails unexpectedly | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

## Retry and Client Handling Guidance

- Treat `SUCCESS` with `payload.status = "BLOCKED"` as a completed block action.
- Treat `SUCCESS` with `payload.status = "SPAMMED"` as a completed spam-only action only when the request sent `shouldSpam = "true"` and `shouldBlock != "true"`.
- Do not send both flags as `"false"`. The current response shape can still say `SPAMMED`, but the product code performs no block/spam mutation.
- Use exact lowercase `"true"` and `"false"` for `shouldBlock` and `shouldSpam`.
- Retry network timeouts, response decryption failures, and `INTERNAL_SERVER_ERROR` with the same request body after a short backoff. Repeating the same successful block/spam request is safe because the contact update and spam record creation are idempotent for the same customer, payee, and referenced transaction/mandate.
- Do not retry validation, authentication, `Invalid payeeVpa`, `Transaction not found`, `Mandate not found`, or `Cannot block a verified payeeVpa` failures without correcting the request or user flow.
- If the customer is reporting a mandate, always send `requestType = "MANDATE"`. Otherwise Newton searches the transaction path and can return `Transaction not found`.
- Store the original `upiRequestId`, `payeeVpa`, request flags, and returned `payload.status` in the merchant system. The response does not echo `upiRequestId`.
- If optional pending-request auto-decline is enabled, expect follow-up transaction/mandate status updates or callbacks to arrive separately from this API response.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:249)
- Route handler, auth, KV cache clear, product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2066)
- Request enum, request type, validation, response type: [src/Newton/Types/API/ServerToServer/Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:538)
- Product entrypoint and transaction/mandate branch: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:815)
- Mandate payee validation and verified-payee failure: [src/Newton/Product/Merchant/Contact/Helper.hs](../../src/Newton/Product/Merchant/Contact/Helper.hs:116)
- Transaction lookup, payee validation, and verified-payee failure: [src/Newton/Product/Merchant/Contact/Helper.hs](../../src/Newton/Product/Merchant/Contact/Helper.hs:156)
- Block/spam action semantics, spam threshold, and optional pending auto-decline: [src/Newton/Product/Merchant/Contact/Helper.hs](../../src/Newton/Product/Merchant/Contact/Helper.hs:226)
- Response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2303)
- S2S auth middleware: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp validation: [src/Newton/Utils/DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Request validation error wrapper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Common field validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
