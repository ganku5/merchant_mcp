# Web Collect360 API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/webCollect360`

## Overview

Web Collect360 is a server-to-server API used to create a UPI collect request against a payer VPA.

The merchant backend sends the payer VPA, payee VPA, amount, expiry, remarks, and optional TPV, split settlement, mutual fund, or sub-merchant information. Newton creates a merchant order, registers any enabled TPV or split-settlement metadata, initiates the collect request with the UPI gateway, and returns a synchronous 360 response containing the gateway transaction identifiers and gateway response status.

Use this API when the merchant wants Newton to initiate a collect request that the customer can approve in a UPI app. This is different from an intent or QR flow, where the customer opens a UPI app from the merchant checkout.

## Business Use Case

Web Collect360 helps merchants:

- Create a UPI collect request from a merchant backend without using an SDK checkout.
- Track the request by merchant order id and Newton gateway transaction id.
- Support dynamic VPA or aggregator/sub-merchant collect flows where enabled.
- Support TPV by restricting the payment to configured payer account hashes.
- Support split settlement where enabled for the merchant.
- Support mutual fund transaction metadata where enabled.
- Receive a synchronous acknowledgement from the gateway, then use status/callback APIs for the final customer approval outcome.

Important identifiers:

- `merchantRequestId`: Merchant-generated idempotency/order reference. It must be unique for each collect request for the resolved merchant.
- `upiRequestId`: UPI transaction id. For `x-api-version: 0`, the merchant may send it or Newton generates it. For `x-api-version: 1` and `2`, the merchant must not send it and Newton generates it.
- `gatewayTransactionId`: The UPI transaction id returned in the response. Persist this for status checks and reconciliation.
- `gatewayReferenceId`: Gateway response/reference id returned after collect initiation.

## Integration Flow

1. Merchant creates an order in its own system.
2. Merchant calls `webCollect360` with payer VPA, payee VPA, amount, expiry, and remarks.
3. Newton authenticates the merchant, validates the encrypted/signed payload, validates API access, and resolves the merchant or sub-merchant.
4. Newton validates request fields, TPV rules, platform restrictions, purpose-code restrictions, split settlement, duplicate request id, and payee VPA/dynamic VPA configuration.
5. Newton creates a merchant order in `PENDING` state.
6. Newton initiates the collect request with the UPI gateway.
7. Newton returns a synchronous 360 response with gateway identifiers and gateway response status.
8. Merchant listens to callbacks or calls status APIs for the final approval, failure, expiry, or reversal outcome.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/webCollect360
```

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. Examples in this guide show the decrypted business payload for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | Controls Web Collect360 version behavior. Missing or non-numeric values are treated as `0`. Supported values in the current implementation are `0`, `1`, and `2`. Use `2` for new integrations unless onboarding specifies otherwise. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Conditional | Required only when calling on behalf of a configured sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required only when calling on behalf of a configured sub-merchant. |
| `x-timestamp` | Yes | Timestamp used for merchant request signature/timestamp validation. |
| `x-merchant-signature` | Conditional | Required for plaintext signed-by-header integrations. For JWS/JWE envelope integrations, the envelope signature/encryption is verified instead. |
| `x-forwarded-for` | Conditional | Required when the merchant has IP allowlisting configured. Newton validates the first IP in the comma-separated value. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Route namespace version. The Web Collect360 product behavior is controlled by `x-api-version`, not this path value. |

### Authentication, Signing, and Encryption

The route accepts the standard Newton `EncRequest` envelope:

- JWE encrypted body: `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`.
- JWS signed body: `payload`, `signature`, `protected`.
- Plain business JSON, only when enabled for the merchant integration.

Before business logic runs, Newton:

- Resolves merchant and optional sub-merchant from merchant headers.
- Verifies JWS signatures or decrypts JWE payloads using onboarded keys.
- For plaintext requests, verifies `x-merchant-signature` over merchant id, merchant channel id, optional sub-merchant ids, `x-timestamp`, and the raw request body.
- Validates `iat` for signed/encrypted payloads when present in the decrypted business payload.
- Validates `x-timestamp` freshness, except for limited lower-environment bypass paths.
- Rejects requests from non-allowlisted IPs when `whitelistedIps` is configured.
- Rejects merchants for which the API is blocked or not included in allowed APIs.

## Request

### Required Minimum

For new integrations using `x-api-version: 2`, send at least:

```json
{
  "merchantRequestId": "ORDER12345",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant@psp",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "remarks": "Order payment",
  "platform": "IOS"
}
```

For `x-api-version: 0`, a merchant-supplied `upiRequestId` is allowed:

```json
{
  "merchantRequestId": "ORDER12346",
  "upiRequestId": "TXN123456789",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant@psp",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "remarks": "Order payment",
  "platform": "IOS"
}
```

For `x-api-version: 1` and `2`, do not send `upiRequestId`; Newton generates it.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Unique merchant order/reference id. Must be unique for the resolved merchant. Length `1` to `35`. Allowed characters: letters, numbers, hyphen, dot, underscore; must contain at least one alphanumeric character. |
| `upiRequestId` | string | Version-specific | For `x-api-version: 0`, generated if omitted. For `x-api-version: 1` and `2`, this field is rejected if supplied. | UPI transaction id. Length `1` to `35`; letters and numbers only. Returned as `gatewayTransactionId`. |
| `payerVpa` | string | Yes | No default. | Customer/payer VPA. Length `3` to `255`; format `name@handle` with letters, numbers, dots, and hyphens. |
| `payerName` | string | No | No default. | Optional payer display name. Must be non-empty if supplied. |
| `payeeVpa` | string | Yes | No default. | Merchant or dynamic payee VPA. Length `3` to `255`; format `name@handle` with letters, numbers, dots, and hyphens. Newton must be able to resolve it to a merchant account or valid dynamic VPA. |
| `collectRequestExpiryMinutes` | string | Yes | No default. | Expiry duration as an integer-string number of minutes. Allowed range: `1` to `64800`. Newton converts it to an absolute `expiryTimestamp` in the response. |
| `amount` | string | Yes | No default. | Collect amount in two-decimal format, for example `100.00`. Must be greater than `0.0`. |
| `remarks` | string | Yes | No default. | Payment note. Length `1` to `255`. Allowed pattern: optional leading spaces, then an alphanumeric or hyphen, followed by letters, numbers, spaces, or hyphens. Newton URL-decodes this before creating the downstream collect request. |
| `subMerchantDetails` | object | Conditional | Ignored for non-dynamic-VPA flows. For dynamic VPA flows, account fields may be accepted or cleared based on merchant configuration. | Aggregator/sub-merchant details. Use only when enabled. |
| `mutualFundDetails` | array of objects | Conditional | No default. | Required only for enabled mutual fund or clearing corporation use cases. Newton validates and stores mutual fund metadata against the generated UPI request id. |
| `initiationMode` | string | No | No default. | UPI initiation mode. Must be exactly 2 alphanumeric characters if supplied. |
| `purpose` | string | No | No default. | UPI purpose code. Must be exactly 2 uppercase alphanumeric characters if supplied. Purpose codes can also be blocked by merchant/business configuration. |
| `refUrl` | string | Conditional with `refCategory` | If omitted with `refCategory`, Newton uses configured gateway defaults downstream. | Merchant reference URL. Must be non-empty if supplied. Newton URL-decodes it before creating the downstream collect request. If sent, `refCategory` must also be sent. |
| `refCategory` | string | Conditional with `refUrl` | If omitted with `refUrl`, Newton uses configured gateway defaults downstream. | Merchant reference category. Must be non-empty if supplied. If sent, `refUrl` must also be sent. |
| `invoiceName` | string | No | No default. | Optional invoice name used in GST invoice metadata. Must be non-empty if supplied. |
| `invoiceNum` | string | No | No default. | Optional invoice number used in GST invoice metadata. Must be non-empty if supplied. |
| `invoiceDate` | string | No | No validation/default in this route. | Optional invoice date passed into downstream invoice metadata. |
| `split` | string | No | No default. | Optional GST amount split string consumed by downstream collect payload construction. Use only if enabled and shared during onboarding. |
| `payerAccountHashes` | array of strings | Conditional | No default. | Required when merchant TPV flag is `ENFORCE`; rejected when merchant TPV flag is `FALSE`. Must be a non-empty array when supplied. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by signed/encrypted request validation. Required for non-plaintext envelope flows. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Must parse as a JSON object string and must not contain disallowed characters from validation. Echoed in the top-level response. |
| `platform` | string | Conditional | No default. | Allowed values: `ANDROID`, `IOS`, `WEB`. For merchants subject to collect-platform validation, this is mandatory and only `IOS` is accepted; `ANDROID` or `WEB` are rejected with guidance to use UPI Intent. Certain approved MCC, eRUPI, IPO, or bypass-configured flows can skip this restriction. |
| `geocode` | string | No | No default. | Latitude/longitude string in `lat,long` format. Latitude absolute value must be `<= 90`; longitude absolute value must be `<= 180`. |
| `splitSettlementDetails` | object | Conditional | No default. | Required when split settlement is enabled for the merchant. Rejected when split settlement is not enabled. |
| `tpvType` | string | No | If omitted, TPV handling is non-`PARTIAL`. | Allowed values: `FULL`, `PARTIAL`. `PARTIAL` is supported only from `x-api-version: 2`. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are simply omitted from the downstream payload or response when omitted.

- `upiRequestId`: generated by Newton when omitted. However, merchant-supplied `upiRequestId` is allowed only for `x-api-version: 0`; it is rejected for `x-api-version: 1` and `2`.
- `collectRequestExpiryMinutes`: no default; it is mandatory.
- `platform`: no default. It is mandatory when collect-platform validation applies.
- `refUrl` and `refCategory`: must be sent together or omitted together. If both are omitted, downstream gateway defaults are used.
- `subMerchantDetails`: used only for dynamic VPA flows. In dynamic VPA flows where `allowSubmerchantAccountDetails` is disabled, Newton clears sub-merchant account fields before creating the collect request.
- `payerAccountHashes`: no default. Required or rejected depending on merchant TPV configuration.
- `splitSettlementDetails`: no default. Required or rejected depending on merchant split-settlement configuration.
- `udfParameters`: echoed back in the top-level response when supplied.

### API Version Behavior

| `x-api-version` | Behavior |
| --- | --- |
| Missing/non-numeric | Treated as `0`. |
| `0` | `upiRequestId` may be supplied. If omitted, Newton generates one. `tpvType: PARTIAL` is rejected. |
| `1` | `upiRequestId` must not be supplied. Newton generates it. `tpvType: PARTIAL` is rejected. |
| `2` | `upiRequestId` must not be supplied. Newton generates it. `tpvType: PARTIAL` is allowed. |
| Other values | Currently rejected as unsupported and surfaced as an internal-error style response. |

### Nested Request Objects

Nested objects do not have field-level defaults unless called out below.

#### `subMerchantDetails`

Use `subMerchantDetails` only for enabled dynamic VPA or aggregator/sub-merchant integrations. If account details are supplied, `accountNumber`, `ifsc`, and `accountType` must all be supplied together.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Sub-merchant display name. Must be non-empty. |
| `mcc` | string | Yes | Sub-merchant MCC. Must be exactly 4 numeric characters. |
| `brandName` | string | Yes | Sub-merchant brand name. Alphanumeric plus spaces, length `1` to `99`. |
| `legalName` | string | Yes | Sub-merchant legal name. Alphanumeric plus spaces, length `1` to `99`. |
| `franchise` | string | Yes | Franchise/store-chain name. Alphanumeric plus spaces, length `1` to `99`. |
| `merchantType` | string | Yes | Allowed values: `SMALL`, `LARGE`. |
| `ownershipType` | string | Yes | Allowed values: `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. |
| `genre` | string | Yes | Allowed values: `ONLINE`, `OFFLINE`. |
| `onboardingType` | string | Yes | Allowed values: `BANK`, `AGGREGATOR`. |
| `accountNumber` | string | Conditional | Required if `ifsc` or `accountType` is supplied. Numeric, maximum 18 digits. |
| `ifsc` | string | Conditional | Required if `accountNumber` or `accountType` is supplied. Must match standard IFSC format: 4 uppercase letters, `0`, then 6 uppercase alphanumeric characters. |
| `accountType` | string | Conditional | Required if `accountNumber` or `ifsc` is supplied. Must be non-empty. |
| `bankName` | string | No | Must be non-empty if supplied. |
| `bankIIN` | string | No | Numeric bank code, maximum 20 digits. |
| `gstin` | string | No | Must be non-empty if supplied. |
| `mid` | string | No | Sub-merchant MID. Alphanumeric, length `1` to `20`. |
| `sid` | string | No | Sub-merchant SID. Alphanumeric, length `1` to `20`. |
| `tid` | string | No | Sub-merchant TID. Alphanumeric, length `1` to `20`. |

#### `mutualFundDetails[]`

Use `mutualFundDetails` only for merchants enabled for mutual fund or clearing corporation flows.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `memberId` | string | Yes | Mutual fund member id. No additional validation in this request validator. |
| `userId` | string | Yes | Mutual fund user/customer id. No additional validation in this request validator. |
| `mfPartner` | string | Yes | Allowed values: `NSE`, `BSE`, `KFIN`, `CAMS`. |
| `investmentType` | string | Yes | Allowed values: `LUMPSUM`, `SIP`. |
| `orderNumber` | string | Yes | Partner order number. Follows `merchantRequestId` validation: length `1` to `35`, letters/numbers/hyphen/dot/underscore, at least one alphanumeric character. |
| `amount` | string | Yes | Mutual fund order amount in two-decimal format. Must be greater than `0.0`. |
| `amcCode` | string | No | AMC code. No additional validation in this request validator. |
| `folioNumber` | string | No | Investor folio number. No additional validation in this request validator. |
| `ihNumber` | string | No | Internal holding/reference number. No additional validation in this request validator. |
| `schemeCode` | string | No | Mutual fund scheme code. No additional validation in this request validator. |
| `panNumber` | string | No | Investor PAN. Must be exactly 10 uppercase alphanumeric characters if supplied. |
| `applicationNumber` | string | No | Partner reference number, also known as ITRN. |

Newton also runs business validation for mutual fund details during processing and associates the records with the generated UPI request id.

#### `splitSettlementDetails`

Use `splitSettlementDetails` only when split settlement is enabled for the merchant. If split settlement is enabled, this object is mandatory for Web Collect360. If split settlement is disabled, this object is rejected.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `splitType` | string | Yes | Allowed values: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. |
| `merchantSplit` | string | Conditional | Merchant's own settlement share. For `AMOUNT`, send an amount such as `90.00`. For `PERCENTAGE`, send a percentage such as `90.00`. Omit for `DEFAULT` and `LATER`. |
| `partnersSplit` | array of objects | Conditional | Partner settlement shares. Required when partners receive part of an `AMOUNT` or `PERCENTAGE` split. Omit for `DEFAULT` and `LATER`. |

Validation rules:

- `merchantSplit` and `partnersSplit[].value` use two-decimal non-negative numeric format.
- For `AMOUNT`, `merchantSplit` plus all partner values must equal the request `amount`.
- For `PERCENTAGE`, `merchantSplit` plus all partner values must equal `100.00`.
- For `DEFAULT` and `LATER`, do not send `merchantSplit` or `partnersSplit`.
- Partner ids can be validated against the merchant's configured vendor list when vendor validation is enabled.

#### `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `partnerId` | string | Yes | Partner/vendor identifier configured for the merchant. Must be non-empty. |
| `value` | string | Yes | Partner share. For `AMOUNT`, this is an amount such as `10.00`. For `PERCENTAGE`, this is a percentage such as `10.00`. |

## Request Examples

### Standard iOS Collect

```json
{
  "merchantRequestId": "ORDER12345",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant@psp",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "remarks": "Order payment",
  "platform": "IOS",
  "refUrl": "https://merchant.example/orders/ORDER12345",
  "refCategory": "00",
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

### Collect With TPV

```json
{
  "merchantRequestId": "ORDER12346",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant@psp",
  "collectRequestExpiryMinutes": "10",
  "amount": "250.00",
  "remarks": "TPV order payment",
  "platform": "IOS",
  "payerAccountHashes": [
    "expected-account-hash"
  ],
  "tpvType": "FULL"
}
```

### Collect With Partial TPV (`x-api-version: 2`)

```json
{
  "merchantRequestId": "ORDER12347",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant@psp",
  "collectRequestExpiryMinutes": "10",
  "amount": "250.00",
  "remarks": "Partial TPV order",
  "platform": "IOS",
  "payerAccountHashes": [
    "partial-account-hash"
  ],
  "tpvType": "PARTIAL"
}
```

### Collect With Split Settlement

```json
{
  "merchantRequestId": "ORDER12348",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant@psp",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "remarks": "Split settlement collect",
  "platform": "IOS",
  "splitSettlementDetails": {
    "splitType": "AMOUNT",
    "merchantSplit": "90.00",
    "partnersSplit": [
      {
        "partnerId": "PARTNER001",
        "value": "10.00"
      }
    ]
  }
}
```

### Dynamic VPA With Sub-Merchant Details

```json
{
  "merchantRequestId": "ORDER12349",
  "payerVpa": "customer@bank",
  "payeeVpa": "store123@merchant",
  "collectRequestExpiryMinutes": "15",
  "amount": "500.00",
  "remarks": "Store payment",
  "platform": "IOS",
  "subMerchantDetails": {
    "name": "Store 123",
    "mcc": "5411",
    "brandName": "Store Brand",
    "legalName": "Store Legal Name",
    "franchise": "Store Franchise",
    "merchantType": "SMALL",
    "ownershipType": "PRIVATE",
    "genre": "ONLINE",
    "onboardingType": "AGGREGATOR"
  }
}
```

## Validation and Processing Behavior

### Request Validation

Newton validates the decrypted request before product logic:

- Required JSON fields must be present and have the expected JSON type.
- `merchantRequestId`, `upiRequestId`, VPA, amount, expiry, remarks, purpose, initiation mode, geocode, UDF, enum, and nested object validations are applied as described above.
- `refUrl` and `refCategory` must be sent together. Sending only one fails validation.
- `payerAccountHashes` must be non-empty when sent.
- `platform` must be one of `ANDROID`, `IOS`, or `WEB` when sent.

Validation failures are returned as `BAD_REQUEST` with a response message containing the validation error text.

### Merchant, Sub-Merchant, and API Access

Newton resolves the merchant using `x-merchant-id` and `x-merchant-channel-id`. If sub-merchant headers are supplied, Newton validates that the sub-merchant belongs to the parent merchant.

The route can be rejected before business logic when:

- Merchant headers are missing or invalid.
- The merchant/sub-merchant is not configured for this API.
- The API is listed in the merchant's blocked APIs.
- The request IP does not match the configured `whitelistedIps`.
- Signature, encryption, `iat`, or timestamp validation fails.

### Duplicate and Idempotency Behavior

`merchantRequestId` is treated as the idempotency/order reference for this API. Before initiating a new collect, Newton checks whether a merchant order already exists for the same `merchantRequestId` and resolved merchant.

If a matching order exists, Newton rejects the request as `DUPLICATE_REQUEST`. The API does not return the previous success response for duplicate retries.

Client guidance:

- Generate one stable `merchantRequestId` per merchant order.
- Do not reuse a `merchantRequestId` for a different amount, payer, or payee.
- If the first call times out at the client but may have reached Newton, first call the status API using `merchantRequestId` or the known `gatewayTransactionId` before retrying with a new id.
- If Newton returns `DUPLICATE_REQUEST`, treat it as "an order already exists" and reconcile with status APIs instead of repeatedly retrying the same create call.

### Collect and 360 Response Behavior

A success response means Newton created the merchant order and received a collect-initiation response from the UPI gateway. It does not mean the customer has approved the collect.

The response payload includes:

- Merchant and optional sub-merchant identifiers.
- `gatewayTransactionId`, the UPI transaction id.
- `gatewayReferenceId`, the gateway reference/response id.
- `gatewayResponseStatus`, mapped from the gateway response code.
- `gatewayResponseCode` and `gatewayResponseMessage`.
- `expiryTimestamp`, the absolute expiry time derived from `collectRequestExpiryMinutes`.

Use callbacks or transaction/status APIs to determine the final outcome of the collect request after the payer approves, declines, ignores, or lets the collect expire.

### Platform, Redirect, Deeplink, and Web Behavior

This API creates a UPI collect request. It does not return a redirect URL, deeplink, intent URI, or web checkout URL.

The `platform` field is used only for collect-platform validation. For merchants subject to platform validation, Newton requires `platform` and allows only `IOS`; `ANDROID` and `WEB` are rejected with `UPI Collect is restricted on this platform. Please use UPI Intent.` For Android or web checkout experiences, use the appropriate UPI intent/register-intent integration instead of Web Collect360 unless Newton onboarding explicitly enables a collect-platform bypass.

### Payee VPA and Dynamic VPA Behavior

Newton resolves `payeeVpa` as follows:

- If sub-merchant headers are present, Newton looks up the payee VPA under that sub-merchant.
- Otherwise, Newton first looks up a merchant account by the payee VPA.
- If no merchant account is found and dynamic VPA is enabled for the merchant, Newton validates that the VPA matches the dynamic VPA pattern, then uses the merchant's dynamic merchant account.
- If no merchant account is found and dynamic VPA is not enabled, the request fails with `Vpa not found`.
- If dynamic VPA is enabled but the VPA does not match the expected dynamic VPA pattern, the request fails with `Vpa Regex Not Matched`.

For dynamic VPA requests, `subMerchantDetails` can be included when configured. If `allowSubmerchantAccountDetails` is not enabled, Newton clears account-related fields from `subMerchantDetails` before creating the downstream collect request.

### TPV Behavior

Newton reads the merchant TPV flag during processing:

- If TPV is `ENFORCE`, `payerAccountHashes` is mandatory.
- If TPV is `FALSE`, `payerAccountHashes` is rejected.
- If TPV is enabled and hashes are supplied, Newton registers TPV validation data against the generated UPI request id, merchant order id, merchant request id, amount, UDF, and `tpvType`.
- `tpvType: PARTIAL` requires `x-api-version: 2` or higher.

### Split Settlement Behavior

Newton validates split-settlement enablement and body consistency before initiating the collect:

- If split settlement is enabled for the merchant, `splitSettlementDetails` is required.
- If split settlement is disabled, `splitSettlementDetails` is rejected.
- For `AMOUNT`, the split total must equal the request `amount`.
- For `PERCENTAGE`, the split total must equal `100.00`.
- For `DEFAULT`, Newton loads configured default split details and stores those details.
- For `LATER`, Newton stores the split type without split details and returns `{ "splitType": "LATER" }` in the response.

### Mutual Fund Behavior

When `mutualFundDetails` is present, Newton runs mutual fund business validation and creates mutual fund records against:

- Resolved merchant.
- Generated or accepted UPI request id.
- `merchantRequestId`.
- Request `amount`.
- Transaction flow `TRANSACTION`.

Use this only when your merchant is enabled for this use case.

## Response

### Success Response Example

Decrypted business response:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "ORDER12345",
    "amount": "100.00",
    "payerVpa": "customer@bank",
    "payerName": "Customer Name",
    "payeeVpa": "merchant@psp",
    "payeeMcc": "5411",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "remarks": "Order payment",
    "transactionTimestamp": "2026-07-02 10:15:30",
    "expiryTimestamp": "2026-07-02 10:30:30",
    "gatewayReferenceId": "123456789012",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "TXN123456789",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS"
  },
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level API status. Success responses use Newton's standard success status. |
| `responseCode` | string | Top-level response code. Success responses use Newton's standard success code. |
| `responseMessage` | string | Human-readable top-level response message. |
| `payload` | object | Web Collect360 business response payload. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Parent merchant id. |
| `merchantChannelId` | string | Parent merchant channel id. |
| `submerchantId` | string | Sub-merchant id when the request was made for a sub-merchant. Omitted otherwise. |
| `submerchantChannelId` | string | Sub-merchant channel id when the request was made for a sub-merchant. Omitted otherwise. |
| `merchantRequestId` | string | Merchant order/reference id from the request. |
| `amount` | string | Amount from the request. |
| `payerVpa` | string | Payer VPA from the request. |
| `payerName` | string | Payer name from the request, if supplied. |
| `payeeVpa` | string | Payee VPA from the request. |
| `payeeMcc` | string | Payee MCC resolved from merchant/sub-merchant/account data. |
| `refUrl` | string | Reference URL included in the response according to MCC/ref-url response configuration. |
| `remarks` | string | Remarks from the request. |
| `mutualFundDetails` | array | Mutual fund details from the request, if supplied. |
| `transactionTimestamp` | string | Newton transaction creation timestamp. |
| `expiryTimestamp` | string | Absolute collect expiry timestamp. |
| `gatewayReferenceId` | string | Gateway response/reference id. |
| `gatewayResponseStatus` | string | Status derived from the gateway response code, for example `SUCCESS`, `PENDING`, or `FAILURE` depending on gateway mapping. |
| `gatewayTransactionId` | string | UPI transaction id used for the collect request. |
| `gatewayResponseCode` | string | Gateway response code returned for collect initiation. |
| `gatewayResponseMessage` | string | Gateway response message returned for collect initiation. |
| `payerAccountHashes` | array of strings | TPV payer account hashes from the request, if supplied. |
| `splitSettlementDetails` | object | Split settlement details persisted for the merchant order, if applicable. |
| `tpvType` | string | TPV type from the request, if supplied. |

## Error Handling

Failure responses use the same response transport as success responses. Examples below show decrypted response bodies. Depending on the failure layer, HTTP status may be `200`, `400`, or `401`; clients should always parse the decrypted `status`, `responseCode`, and `responseMessage`.

### Validation Error

Example: invalid amount format.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\"",
  "payload": null
}
```

Example: only one of `refUrl` or `refCategory` sent.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"RefUrl or Ref Category not present.\"",
  "payload": null
}
```

Common validation messages include:

- `merchantRequestId length not between 1 and 35`
- `merchant request id regex failed`
- `upiRequestId regex match failed`
- `payerVpa regex failed`
- `payeeVpa regex failed`
- `expiry is not valid`
- `amount regex match failed`
- `amount is not greater than 0.0`
- `remarks regex match failed`
- `JSON Text parse failed for udfParameters`
- `Incorrect latitude/longitude value`
- `Field is empty`

### Unsupported `upiRequestId` for API Version 1 or 2

For `x-api-version: 1` or `2`, sending `upiRequestId` fails.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "upiRequestId not allowed for apiVersion 1 and above",
  "payload": null
}
```

### Unsupported API Version

For Web Collect360, values other than `0`, `1`, or `2` are currently unsupported in the transformer.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

### Duplicate Request

If a merchant order already exists for the same `merchantRequestId` and resolved merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST",
  "payload": null
}
```

### TPV Configuration Errors

If TPV is enforced but `payerAccountHashes` is omitted:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "PayerAccountHashes Should be Present",
  "payload": null
}
```

If TPV is not supported for the merchant but `payerAccountHashes` is supplied:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "TPV not Supported",
  "payload": null
}
```

If `tpvType` is `PARTIAL` below `x-api-version: 2`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "TpvType Partial is supported only in api version 2 or higher",
  "payload": null
}
```

### Platform Restriction

If platform validation applies and `platform` is missing:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Missing mandatory parameter: platform.",
  "payload": null
}
```

If platform validation applies and `platform` is `ANDROID` or `WEB`:

```json
{
  "status": "FAILURE",
  "responseCode": "FORBIDDEN",
  "responseMessage": "UPI Collect is restricted on this platform. Please use UPI Intent.",
  "payload": null
}
```

### Payee VPA / Dynamic VPA Errors

If `payeeVpa` cannot be resolved to a merchant account and dynamic VPA is not enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Vpa not found",
  "payload": null
}
```

If dynamic VPA is enabled but the VPA does not match the expected dynamic pattern:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Vpa Regex Not Matched",
  "payload": null
}
```

### Split Settlement Errors

When split settlement is enabled but details are missing:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SplitSettlementDetails not Found",
  "payload": null
}
```

When split settlement is not enabled but details are supplied:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SplitSettlement not Allowed",
  "payload": null
}
```

Other split-settlement failures:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Amount Sum Mismatch",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid Percentage Split",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid Split Details",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid Partner",
  "payload": null
}
```

### Merchant, API Access, Signature, Encryption, and IP Failures

Examples:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

These can happen when:

- Merchant id or merchant channel id headers are missing or invalid.
- Sub-merchant headers do not identify a valid child of the parent merchant.
- The API is blocked or not allowed for the merchant/sub-merchant.
- `x-merchant-signature` is missing or does not match the expected signature.
- JWS signature verification fails.
- JWE decryption fails or uses an unknown key id.
- `iat` or `x-timestamp` validation fails.
- `x-forwarded-for` is missing or not allowlisted for a merchant with IP restrictions.

### Downstream Gateway Failures

If the UPI gateway/NPCI service is unavailable or times out before a transaction object is returned:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)",
  "payload": null
}
```

If a timeout code is available, the code is appended:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U90",
  "responseMessage": "NPCI service is not reachable at the moment (U90)",
  "payload": null
}
```

If Newton receives an invalid or unusable gateway response:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI",
  "payload": null
}
```

If downstream risk/Sherlock logic returns a business error, Newton can pass through the downstream failure code and user message:

```json
{
  "status": "FAILURE",
  "responseCode": "RISK_DECLINED",
  "responseMessage": "Transaction declined by risk checks",
  "payload": null
}
```

### Internal Errors

Unexpected failures, missing required internal transaction fields, unsupported Web Collect360 version paths, or failures while transforming stored gateway data can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

## Retry and Client Handling Guidance

- Treat a success response as "collect request initiated", not "payment completed".
- Persist `merchantRequestId`, `gatewayTransactionId`, `gatewayReferenceId`, `gatewayResponseCode`, `gatewayResponseStatus`, and `expiryTimestamp`.
- Use callbacks or status APIs to track final approval/failure/expiry.
- For validation, auth, API access, TPV configuration, platform, split-settlement, or duplicate failures, do not retry unchanged.
- For `SERVICE_UNAVAILABLE_NPCI_*`, retry only with careful reconciliation. If the client timed out after sending the request, first check status by `merchantRequestId` or known transaction id to avoid creating a second collect with a different id.
- For `DUPLICATE_REQUEST`, do not call create again with the same id expecting the old response. Reconcile using status APIs.
- For payer-decline, expiry, or final payment failure reported later by status/callback, create a new collect only with a new `merchantRequestId`.

## Source References

- Route type and endpoint: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:361)
- Web Collect360 route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2259)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:631)
- S2S request/response types and request validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1397)
- Web Collect360 core request version rules and response wrapper: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:917)
- Product/business logic: [src/Newton/Product/Merchant/Transactions/WebCollect360.hs](../../src/Newton/Product/Merchant/Transactions/WebCollect360.hs:30)
- Product core request/response payload types: [src/Newton/Product/Merchant/Transactions/Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:329)
- Web collect generic request transformation: [src/Newton/Product/Merchant/Transactions/Helper.hs](../../src/Newton/Product/Merchant/Transactions/Helper.hs:362)
- Success response payload construction: [src/Newton/Product/Merchant/Transactions/Transformer.hs](../../src/Newton/Product/Merchant/Transactions/Transformer.hs:180)
- Gateway collect initiation and duplicate request handling: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:304)
- Common validation rules: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:292)
- TPV and platform validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:132)
- Split settlement validation: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4539)
- Authentication, signature, API access, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
