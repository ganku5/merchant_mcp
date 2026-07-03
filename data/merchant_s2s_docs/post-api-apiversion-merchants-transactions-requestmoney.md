# Request Money API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/requestMoney`

## Overview

Request Money is a server-to-server API used to initiate an outgoing UPI collect request from a merchant-linked customer account to a payer VPA or UPI number.

The merchant calls this API after the customer and account have already been onboarded with Newton. Newton verifies the encrypted/signed request, resolves the merchant customer, validates the payer and payee details, validates the customer device fingerprint, finds the payee VPA and debit account, creates the collect request through the downstream UPI/NPCI wrapper, and returns Newton plus gateway identifiers for reconciliation.

Use this API when the merchant backend needs to request money from another UPI user on behalf of an onboarded merchant customer.

## Business Use Case

Request Money helps merchants:

- Initiate a UPI collect request from a known customer account.
- Send a collect to a payer VPA or payer UPI number.
- Tie the collect to merchant identifiers such as `merchantRequestId` and `upiRequestId`.
- Enforce that the collect is initiated only from the expected device/customer/account context.
- Reconcile the collect using Newton identifiers and downstream gateway response details.
- Receive an outgoing collect callback when configured for the merchant and PSP mode.

This API only sends the collect request. Final payer approval, decline, expiry, or timeout is completed later in the UPI network and should be tracked through transaction status and callbacks.

## Integration Flow

1. Merchant identifies an already-onboarded `merchantCustomerId`.
2. Merchant selects the customer's payee VPA and debit account reference.
3. Merchant generates a unique `upiRequestId` and `merchantRequestId`.
4. Merchant signs and/or encrypts the request using the configured Newton S2S integration.
5. Newton decrypts/verifies the envelope and authenticates the merchant headers.
6. Newton validates request fields, payer/payee VPA rules, device fingerprint, payee VPA status, account ownership, and duplicate `upiRequestId`.
7. Newton initiates a collect request through the downstream UPI/NPCI service.
8. Newton returns a response containing request identifiers, account details, collect expiry, and gateway response fields.
9. Merchant uses transaction status or callbacks to track final payer action.

Important identifiers:

- `upiRequestId`: Merchant-supplied UPI transaction id for this API call. Newton uses it as the duplicate guard and returns it as `payload.gatewayTransactionId`.
- `merchantRequestId`: Merchant-supplied order/reference id. It is forwarded to downstream collect creation and returned in the response.
- `gatewayReferenceId`: Downstream/NPCI response id from the created transaction.
- `bankAccountUniqueId` or `accountReferenceId`: Account selector for the customer account used to initiate the collect.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/requestMoney
```

Payloads use the standard Newton server-to-server request/response envelope configured during onboarding. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | API version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. Required by merchant authentication. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. Required by merchant authentication. |
| `x-sub-merchant-id` | Optional. Required only for configured sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Optional. Required only for configured sub-merchant integrations. |
| `x-timestamp` | Request timestamp used for merchant signature verification. |
| `x-merchant-signature` | Required for unsigned/plain business payload requests. Signature is computed over merchant headers, timestamp, and raw request body as configured. |
| `x-merchant-checksum` | Legacy/checksum mode where enabled. |
| `x-forwarded-for` | Required when the merchant has IP allow-listing configured. The first IP in the comma-separated value is checked. |
| `Authorization` | Used by integrations that are configured to require it. |
| `x-request-id` | Optional client request id. If omitted, Newton generates one and returns it as `x-requestid`. |
| `x-session-id` | Optional client session id. If omitted, Newton uses the request id and returns it as `x-sessionid`. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Version segment in the URL. Runtime behavior is also driven by the `x-api-version` header and merchant configuration. |

## Authentication, Signing, and Encryption

The route accepts `API.EncRequest API.RequestMoneyRequest` and returns `API.EncResponse API.RequestMoneyResponse`.

Depending on merchant configuration, the request envelope can be:

| Envelope | JSON shape | Notes |
| --- | --- | --- |
| JWE encrypted payload | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag` | Newton decrypts the payload, expects a signed inner body, verifies the source, and then parses the business JSON. |
| JWS signed payload | `payload`, `signature`, `protected` | Newton verifies the JWS signature using the configured public key. |
| Plain business payload | Business fields directly in JSON | Supported by the generic type, but merchant signature headers are then verified explicitly. Use only if this is the mode enabled for your merchant. |

For plain/unsigned payloads, Newton verifies the merchant request signature using:

```text
x-merchant-id
+ x-merchant-channel-id
+ x-sub-merchant-id, when present
+ x-sub-merchant-channel-id, when present
+ x-timestamp
+ raw request body
```

For signed/encrypted payloads, the `iat` field in the decrypted business payload is required and must be a valid timestamp. The route also checks `x-timestamp` unless the environment/checksum mode explicitly bypasses timestamp validation.

The response is returned using the merchant's configured response strategy:

- JWE response: encrypted JSON with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS response: signed JSON with `payload`, `signature`, and `protected`.
- Plain response plus `X-Response-Signature`: used when no JWS/JWE response strategy is configured.

Response headers include `x-requestid` and `x-sessionid`. `X-Response-Signature` is present for the plain response strategy.

## Request

### Required Minimum

For a standard collect request using `bankAccountUniqueId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint-from-registration",
  "merchantRequestId": "ORDER12345",
  "payeeVpa": "customer@bank",
  "payerVpa": "payer@bank",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "upiRequestId": "UPIREQ12345",
  "bankAccountUniqueId": "bank-account-unique-id",
  "remarks": "Order payment",
  "currency": "INR"
}
```

For migrated-account or account-reference based integrations:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "device-fingerprint-from-registration",
  "merchantRequestId": "ORDER12346",
  "payeeVpa": "customer@bank",
  "payerVpa": "payer@bank",
  "collectRequestExpiryMinutes": "10",
  "amount": "250.00",
  "upiRequestId": "UPIREQ12346",
  "accountReferenceId": "account-reference-id",
  "ifsc": "HDFC0000001",
  "remarks": "Order payment",
  "currency": "INR",
  "iat": "2026-07-02T10:00:00Z"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Newton uses it during signature/auth processing to load the merchant customer and customer. Length 1 to 256. Allowed characters: letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letter/number/plus/slash/equals. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint associated with the merchant customer. Must be non-empty and must match the stored device fingerprint or the request's `fallbackDeviceFingerPrint`. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate fingerprint accepted during device validation. |
| `merchantRequestId` | string | Yes | No default. | Merchant order/reference id. Length 1 to 35. Allowed characters: letters, numbers, hyphen, dot, underscore. Must contain at least one alphanumeric character. |
| `payeeVpa` | string | Yes | No default. | Customer/payee VPA from which the collect is initiated. Newton lowercases this before downstream processing. Must be a valid VPA, must belong to the authenticated merchant customer, and must not be credit-blocked. |
| `payerVpa` | string | Yes | No default. | Payer VPA receiving the collect request. Must be a valid VPA and cannot equal `payeeVpa`, case-insensitively. |
| `payerName` | string | No | No default. | Optional display name for the payer. Returned as `payload.payerName` when supplied. |
| `upiNumber` | string | No | No default. | Optional payer UPI number. If supplied, it must be numeric. Exactly 10 digits is accepted when numeric. For 8 or 9 digit values, it must not start with zero and must not have the same last three digits. |
| `collectRequestExpiryMinutes` | string | Yes | No default. | Collect expiry duration in minutes. Must be an integer string from `1` to `64800`. |
| `amount` | string | Yes | No default. | Collect amount. Must match `^[0-9]+\\.[0-9][0-9]$` and be greater than `0.0`, for example `100.00`. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this collect. Length 1 to 35. Allowed characters: letters and numbers only. Reuse is rejected as duplicate. |
| `bankAccountUniqueId` | string | Conditional | No default. | Account selector for non-reference-id integrations. Must be non-empty when supplied. If account-id migration is enabled and this value is an account hash, Newton resolves and stores the account hash. |
| `accountReferenceId` | string | Conditional | No default. | Alternate account selector. Must be non-empty when supplied. Used directly for account lookup in several Newton modes and required for GPay ICICI mode. |
| `ifsc` | string | Conditional | No default. | IFSC used with migrated account-reference flows. Must be non-empty when supplied. Required in GPay ICICI migrated account mode when `accountReferenceId` does not contain the configured account-id prefix. |
| `remarks` | string | Yes | No default. | Collect note. Length 1 to 255. Must start, after optional leading spaces, with an alphanumeric or hyphen, and may contain letters, numbers, spaces, and hyphen. URL-encoded values are decoded before downstream processing. |
| `currency` | string | Yes | No default. | Currency field accepted by the API type. The validator does not enforce a value in this route; use `INR` unless Newton has onboarded a different value. |
| `iat` | string | Conditional | No default. | Issued-at timestamp. Required for signed/encrypted request envelopes because `validateIAT` rejects missing `iat` for non-plain payloads. |
| `udfParameters` | string | No | No default. | Merchant-defined metadata as a JSON-object string. Must parse as a JSON object and must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. Echoed back as top-level `udfParameters` in the response when supplied. |
| `location` | string | No | No default. | Optional location text. Must be non-empty when supplied. |
| `geocode` | string | No | No default. | Optional latitude/longitude string in `lat,long` format. Latitude absolute value must be `<= 90`; longitude absolute value must be `<= 180`. |

### Account Selection

Send one of the account selectors enabled for your merchant:

- `bankAccountUniqueId` for standard Newton account-id/account-hash based integrations.
- `accountReferenceId` for integrations that use account ids directly.
- `accountReferenceId` plus `ifsc` for migrated GPay ICICI style account references.

If the account cannot be resolved for the authenticated customer and merchant customer, the API fails before sending the collect request downstream.

### Defaults and Omitted Field Behavior

The request-money route does not create business defaults for required fields. Omitted optional fields remain absent unless the downstream transaction or merchant configuration supplies derived values for the response.

- `fallbackDeviceFingerPrint`: no default; only the primary fingerprint is checked if omitted.
- `payerName`: no default; omitted from the response when not supplied.
- `upiNumber`: no default; collect is addressed by `payerVpa` unless downstream PSP behavior uses the supplied UPI number.
- `bankAccountUniqueId`, `accountReferenceId`, `ifsc`: no default; account lookup uses the identifiers that are present.
- `udfParameters`, `location`, `geocode`: no default.
- `refUrl`: there is no request field for `refUrl`. The response `payload.refUrl` is derived from the stored downstream transaction or configured NPCI reference URL.

### Validation Rules and Conditional Requirements

Newton applies these validations before or during collect creation:

| Area | Rule |
| --- | --- |
| Envelope and headers | Merchant id/channel headers must identify a valid merchant. Signature/JWS/JWE verification must pass. `iat` is required for signed/encrypted payloads. `x-timestamp` must be valid unless an enabled bypass applies. |
| Merchant/API access | The API must not be blocked by `blockedApiNames`, and if the merchant has `allowedApiNames`, `requestMoneyS2S` must be included. If IP allow-listing is configured, the first `x-forwarded-for` IP must be present and allowed. |
| Merchant customer | `merchantCustomerId` must resolve under the authenticated merchant. Newton loads the customer from that merchant customer before product logic. |
| Required strings | Required text fields must be present, non-null, and pass their validators. A missing required JSON field generally fails JSON parsing or request validation before downstream processing. |
| Amount | `amount` must be a two-decimal positive string such as `100.00`. |
| Expiry | `collectRequestExpiryMinutes` must be an integer string between `1` and `64800`. |
| VPA format | `payeeVpa` and `payerVpa` must be 3 to 255 characters and match the `local@handle` VPA pattern. |
| Payer/payee relation | `payerVpa` and `payeeVpa` cannot be the same value, ignoring case. |
| Payee VPA ownership | The payee VPA is looked up for the loaded customer and merchant customer. It must exist and must not be credit-blocked. |
| Account ownership | The selected account must resolve for the loaded customer and merchant customer and must be active where the account lookup enforces active records. |
| Device | The stored device for the merchant customer is loaded. `deviceFingerPrint` or `fallbackDeviceFingerPrint` must match the stored fingerprint. |
| Duplicate collect | `upiRequestId` is checked against existing transactions across the configured partition search. If a transaction already exists, the request is rejected as duplicate. |
| UDF metadata | `udfParameters` must be a JSON-object string and pass the restricted-character check. |
| Geocode | `geocode`, when supplied, must be parseable as latitude and longitude in valid ranges. |

## Request Examples

### Standard VPA Collect

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "8f7d0b6f6d6d4c7b9b0f8f0a1a2b3c4d",
  "fallbackDeviceFingerPrint": "fallback-device-fingerprint",
  "merchantRequestId": "ORDER10001",
  "payeeVpa": "customer@okbank",
  "payerVpa": "payer@upi",
  "payerName": "Ravi Kumar",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "upiRequestId": "UPI100010001",
  "bankAccountUniqueId": "ACCUNIQUE123",
  "remarks": "Order payment",
  "currency": "INR",
  "udfParameters": "{\"cartId\":\"CART10001\"}",
  "location": "Bengaluru",
  "geocode": "12.9716,77.5946"
}
```

### Collect With Payer UPI Number

```json
{
  "merchantCustomerId": "CUST10002",
  "deviceFingerPrint": "8f7d0b6f6d6d4c7b9b0f8f0a1a2b3c4d",
  "merchantRequestId": "ORDER10002",
  "payeeVpa": "customer@okbank",
  "payerVpa": "payer@upi",
  "upiNumber": "9876543210",
  "collectRequestExpiryMinutes": "10",
  "amount": "250.00",
  "upiRequestId": "UPI100020001",
  "bankAccountUniqueId": "ACCUNIQUE123",
  "remarks": "Invoice 10002",
  "currency": "INR"
}
```

### Signed or Encrypted Envelope

The decrypted payload above is wrapped using the merchant's onboarded envelope. For JWE, the HTTP body has this outer shape:

```json
{
  "protected": "<base64url-protected-header>",
  "encryptedKey": "<base64url-encrypted-key>",
  "iv": "<base64url-iv>",
  "cipherText": "<base64url-ciphertext>",
  "tag": "<base64url-tag>"
}
```

For JWS, the HTTP body has this outer shape:

```json
{
  "payload": "<base64url-payload>",
  "signature": "<base64url-signature>",
  "protected": "<base64url-protected-header>"
}
```

## Response

### Success Response

A successful HTTP/API call means Newton accepted and processed the collect creation request. It does not mean the payer has approved the collect.

The top-level response is built from Newton's standard success response:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST10001",
    "merchantRequestId": "ORDER10001",
    "customerMobileNumber": "9876543210",
    "payeeVpa": "customer@okbank",
    "payeeMcc": "0000",
    "payerVpa": "payer@upi",
    "payerName": "Ravi Kumar",
    "remarks": "Order payment",
    "refUrl": "https://www.npci.org.in/",
    "bankAccountUniqueId": "ACCUNIQUE123",
    "bankCode": "HDFC",
    "maskedAccountNumber": "XXXX1234",
    "amount": "100.00",
    "expiryTimestamp": "2026-07-02 10:15:00",
    "transactionTimestamp": "2026-07-02 10:00:00",
    "gatewayTransactionId": "UPI100010001",
    "gatewayReferenceId": "RESP123456789",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Collect request sent successfully"
  },
  "udfParameters": "{\"cartId\":\"CART10001\"}"
}
```

When `payerName` or `udfParameters` is omitted, it is omitted from JSON because response serialization omits `null` optional fields.

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API processing status. Success value is `SUCCESS`. |
| `responseCode` | string | Top-level API response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Top-level API response message. Success value is `SUCCESS`. |
| `payload` | object | Request-money business response payload. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from Newton merchant configuration. |
| `merchantChannelId` | string | Merchant channel id from Newton merchant configuration. |
| `merchantCustomerId` | string | Merchant customer id resolved from the request. |
| `merchantRequestId` | string | Echo of request `merchantRequestId`. |
| `customerMobileNumber` | string | Customer mobile number with country-code trimming applied by Newton. |
| `payeeVpa` | string | Echo of request `payeeVpa`. |
| `payeeMcc` | string | Payee MCC derived from the stored transaction and MCC/ref-url version logic. |
| `payerVpa` | string | Echo of request `payerVpa`. |
| `payerName` | string | Echo of request `payerName` when supplied. |
| `remarks` | string | URL-decoded request remarks. |
| `refUrl` | string | Reference URL derived from the stored downstream transaction or configured NPCI reference URL. |
| `bankAccountUniqueId` | string | Migrated id or account hash returned for the debit account. |
| `bankCode` | string | Bank code on the resolved debit account. |
| `maskedAccountNumber` | string | Masked debit account number. |
| `amount` | string | Echo of request `amount`. |
| `expiryTimestamp` | string | Transaction expiry timestamp computed from `collectRequestExpiryMinutes` by downstream collect creation. |
| `transactionTimestamp` | string | Transaction creation timestamp, adjusted by merchant configuration when configured. |
| `gatewayTransactionId` | string | Echo of request `upiRequestId`. |
| `gatewayReferenceId` | string | Downstream transaction response id (`upiResponseId`) from the stored transaction. |
| `gatewayResponseStatus` | string | Derived gateway status. `SUCCESS` when `gatewayResponseCode` is `00`; `PENDING` when code is `01` and pending responses are enabled; otherwise `FAILURE`. |
| `gatewayResponseCode` | string | Downstream response code. Pending stored transactions return `00`; timeout/error code `U09` maps to `01`; otherwise Newton reads the code from downstream response data. |
| `gatewayResponseMessage` | string | Downstream response message. Pending stored transactions return `Collect request sent successfully`; timeout/error code `U09` maps to the configured `01` message; otherwise Newton reads the message from downstream response data. |

### Gateway Status Handling

Do not treat the top-level `SUCCESS` as payer approval. Read the nested fields:

| `payload.gatewayResponseStatus` | Client meaning |
| --- | --- |
| `SUCCESS` | The collect request was sent/accepted by the downstream UPI flow. Track final payer action separately. |
| `PENDING` | Downstream returned a pending-style response and merchant/environment config enables pending responses. Poll transaction status or wait for callback. |
| `FAILURE` | Downstream returned a non-success response. Do not retry blindly with the same `upiRequestId`; check the code/message and transaction status first. |

## Error Handling

Failure responses use the same S2S response transport as success responses when possible. After decryption, failures generally use this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

The `payload` field is normally omitted for failures.

Depending on where validation fails, HTTP status can be `200`, `400`, `401`, `422`, or `500`. Clients should use the decrypted body fields as the integration contract and log HTTP status, `x-requestid`, merchant ids, `upiRequestId`, and `merchantRequestId` for support.

### Request Money Failure Bodies

| Scenario | Response body |
| --- | --- |
| Missing or unparsable JSON for a required field | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $: key \"merchantCustomerId\" not found"}` |
| Generic request validation failure | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` |
| `merchantCustomerId` is empty, too long, or has invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| `deviceFingerPrint` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"deviceFingerPrint field is empty\""}` |
| Device fingerprint does not match the stored device | `{"status":"FAILURE","responseCode":"DEVICE_FINGERPRINT_MISMATCH","responseMessage":"DEVICE_FINGERPRINT_MISMATCH"}` |
| `merchantRequestId` is empty, too long, or has invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\""}` |
| `payeeVpa` or `payerVpa` length is invalid | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"payeeVpa length is not between 3 and 255\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"payerVpa length is not between 3 and 255\""}` |
| `payeeVpa` or `payerVpa` does not match the VPA pattern | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"payeeVpa regex failed\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"payerVpa regex failed\""}` |
| `payerVpa` and `payeeVpa` are the same | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"payerVpa and payeeVpa cannot be same"}` |
| Payee VPA is credit-blocked | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"VPA is CREDIT Blocked"}` |
| Invalid `upiNumber` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"Upi Number is not a valid number input\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"Upi Number should be between 8 to 10 digits\""}` |
| `collectRequestExpiryMinutes` is not an integer | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"collectRequestExpiryMinutes regex match failed\""}` |
| `collectRequestExpiryMinutes` is outside `1` to `64800` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"value of collectRequestExpiryMinutes is not between 1 and 64800\""}` |
| `amount` is not in two-decimal format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"amount regex match failed\""}` |
| `amount` is zero or negative | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"amount is not greater than 0.0\""}` |
| `upiRequestId` is empty, too long, or non-alphanumeric | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"upiRequestId length is not between 1 and 35\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"upiRequestId regex match failed\""}` |
| Duplicate `upiRequestId` | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| Optional account/location/IFSC fields are supplied as empty strings | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"bankAccountUniqueId field is empty\""}` |
| `remarks` is empty, too long, or has unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"remarks length is not between 1 and 255\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"remarks regex match failed\""}` |
| `udfParameters` is not a JSON-object string or contains restricted characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| `geocode` is malformed | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"geocode not valid\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"Incorrect latitude/longitude value\""}` |
| Signed/encrypted request missing `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| JWS signature verification fails or JWE decryption fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Encrypted payload decrypts but inner payload cannot be parsed | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: key \"upiRequestId\" not found"}` |
| Merchant headers are missing, merchant cannot be resolved, signature is missing/mismatched, or timestamp is invalid | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| API is blocked or not allowed for this merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| IP allow-list is configured and `x-forwarded-for` is missing or not allowed | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Merchant customer, customer, device, VPA, or account cannot be found | Usually `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid MerchantCustomer not found"}` or `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}`, depending on the lookup that failed. |
| Downstream NPCI/UPI wrapper is unreachable or times out for a transactional API | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"UPI service is not reachable at the moment for transactional apis"}` |
| Downstream NPCI/UPI wrapper is unreachable before a transaction response is created | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"NPCI service is not reachable at the moment (NA)"}` |
| Downstream Sherlock/business validation returns a custom failure | `{"status":"FAILURE","responseCode":"RISK_DECLINED","responseMessage":"Transaction declined by risk checks"}` |
| Unexpected server, database, encryption, or cache failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

## Retry and Client Handling

- Generate a new `upiRequestId` for each new collect request. Newton rejects duplicate `upiRequestId` values.
- If the HTTP call times out or the client does not receive a decryptable response, do not immediately create a new collect with a different `upiRequestId`. First query transaction status for the original `upiRequestId`; the collect may already have been created.
- If a retry with the same `upiRequestId` returns `DUPLICATE_REQUEST`, treat it as "original request may have been accepted" and check transaction status/callbacks.
- If the response is top-level `SUCCESS` but `payload.gatewayResponseStatus` is `PENDING`, continue status polling or wait for callback. Do not present this as payer-approved.
- If `payload.gatewayResponseStatus` is `FAILURE`, use `gatewayResponseCode` and `gatewayResponseMessage` to decide whether the payer/customer should try again with a new collect request.
- Do not retry validation, authentication, API access, IP allow-list, or device fingerprint failures without correcting the request or merchant configuration.
- For downstream `SERVICE_UNAVAILABLE_*` responses, retry only after checking whether a transaction exists for the original `upiRequestId`.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:506)
- Route handler and middleware chain: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2843)
- Request and response types: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:664)
- Request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:14)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:70)
- Merchant signature, API access, and IP allow-list verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:48)
- S2S product route: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:797)
- Generic outgoing collect logic and duplicate check: [src/Newton/Product/MerchantTransactionsSDKV2.hs](../../src/Newton/Product/MerchantTransactionsSDKV2.hs:381)
- Downstream collect creation: [src/Newton/Product/MerchantTransactionsSDKV2.hs](../../src/Newton/Product/MerchantTransactionsSDKV2.hs:1039)
- Request transformer: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:1172)
- Response transformer: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:421)
- Common request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Payer/payee VPA and device fingerprint checks: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Account lookup: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:540)
- Error body constructors: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:16)
