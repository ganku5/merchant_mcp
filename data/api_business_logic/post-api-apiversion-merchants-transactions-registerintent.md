# Register Intent API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/registerIntent`

## Overview

Register Intent is a server-to-server API used before starting a customer UPI intent, QR, or mandate authorization journey.

The merchant calls this API with the expected payment details, such as order id, amount, expiry, flow type, payee, and optional TPV or split details. Newton returns identifiers and payee information that the merchant should use to create the UPI intent or QR payload. When the customer later authorizes the payment in a UPI app, Newton validates the incoming payment against the registered intent.

Use this API when the merchant wants the payment to be tied to a known checkout/order before the customer opens the UPI app.

## Business Use Case

Register Intent helps merchants:

- Bind a UPI payment to a merchant order before collecting payment.
- Prevent unintended direct payments to a merchant VPA when an order reference is mandatory.
- Enforce amount, expiry, payee, and flow validation during payment authorization.
- Support dynamic VPA and aggregator/sub-merchant payment journeys.
- Support TPV by restricting payment to pre-approved payer accounts.
- Support tips, convenience fees, and split settlement where enabled.
- Support UPI mandate creation flows with optional first execution amount.
- Support mutual fund or clearing corporation use cases where additional transaction details are required.

## Integration Flow

1. Merchant creates an order in its own system.
2. Merchant calls `registerIntent` with the order and payment details.
3. Newton returns `gatewayTransactionId`, `orderId`, payee VPA, amount, and other payment metadata.
4. Merchant uses the returned values to create the UPI intent link or QR payload.
5. Customer opens a UPI app and authorizes the payment or mandate.
6. Newton validates the incoming UPI request against the registered intent.
7. Merchant receives the normal transaction or mandate status/callback through the existing integration.

Important identifiers:

- `merchantRequestId`: Merchant-generated idempotency key for this intent.
- `gatewayTransactionId`: Newton UPI transaction id. Use this as the UPI transaction id when building the intent or QR payload.
- `orderId`: Newton-generated reference/order id. Use this as the UPI reference/order id where required by your integration.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/registerIntent
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

Recommended header:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | `4` recommended for new integrations |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding.

## Request

### Required Minimum

For new integrations, send at least:

```json
{
  "merchantRequestId": "ORDER12345",
  "amount": "100.00",
  "flow": "TRANSACTION",
  "intentRequestExpiryMinutes": "15",
  "remarks": "Order payment"
}
```

For mandate intent:

```json
{
  "merchantRequestId": "MANDATE12345",
  "amount": "100.00",
  "flow": "MANDATE",
  "intentRequestExpiryMinutes": "15",
  "remarks": "Mandate creation"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Unique merchant order/reference id for this intent. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `merchantCustomerId` | string | No | No default. | Merchant's customer identifier for the payer/customer associated with this intent. |
| `amount` | string | Recommended | No default. If omitted, Newton does not bind the final UPI authorization to an expected amount. | Expected base amount in two-decimal format, for example `100.00`. If supplied, the final UPI payment amount is validated against this value. |
| `flow` | string | Yes for new integrations | No default. For `x-api-version <= 1`, omission is allowed for backward compatibility and no flow is stored. | `TRANSACTION` for payment intent, `MANDATE` for mandate creation intent. Required when `x-api-version > 1`. |
| `upiRequestId` | string | Conditional | Newton generates it if omitted, except when multibank mode requires the merchant to send it. | Optional for most merchants. Required if multibank mode is enabled for the merchant. Returned as `gatewayTransactionId`. |
| `remarks` | string | No | No default. | Payment note shown/used for the transaction. Max 255 characters. |
| `refUrl` | string | No | No default. | Merchant reference URL for the order/payment. |
| `refCategory` | string | No | No default. | Merchant reference category. |
| `intentRequestExpiryMinutes` | string | No | Falls back to merchant-configured `intentRequestExpiryMinutes` when available. If neither request nor config is present, no explicit register-intent expiry is set from minutes. | Expiry duration in minutes. Allowed range: `1` to `64800`. |
| `intentRequestExpirySeconds` | string | No | No default. If omitted, Newton uses `intentRequestExpiryMinutes` or merchant-configured minutes when available. | Expiry duration in seconds. Allowed range: `1` to `3888000`. Takes precedence over minutes when both are supplied. |
| `payerAccountHashes` | array of strings | Conditional | No default. If omitted, no expected payer account hash is stored. | Required when TPV is enforced for the merchant. Do not send unless TPV is enabled for the merchant. |
| `tpvType` | string | No | If omitted, TPV hash handling is treated as non-`PARTIAL`, equivalent to the full-account-hash behavior. | `FULL` or `PARTIAL`. `PARTIAL` requires `x-api-version >= 4`. |
| `splitDetails` | array | No | No default. If omitted, no convenience-fee or split component is registered. | Tips/convenience fee components. Supported split names depend on merchant configuration. |
| `enableTips` | boolean | No | Defaults by behavior to `false`. Tips are rejected unless this is sent as `true`. | Set `true` if tips are allowed for this intent. |
| `splitSettlementDetails` | object | No | No default. If `applyRefundOnSuccess = "true"`, this field is cleared during processing even if supplied. | Split settlement details. Supported from `x-api-version >= 3`. |
| `mutualFundDetails` | array | Conditional | No default. If `applyRefundOnSuccess = "true"`, this field is cleared during processing even if supplied. | Required only for enabled mutual fund/clearing corporation use cases. |
| `firstExecutionAmount` | string | Conditional | No default normally. If `applyRefundOnSuccess = "true"`, Newton sets it to the configured `defaultFirstExecutionAmount` during processing. Current default configuration is `1.00`, unless changed for the environment. | Used for mandate first execution flows when enabled for the merchant. Must not exceed `amount`. |
| `applyRefundOnSuccess` | string | No | Defaults by behavior to `"false"` when omitted. | `"true"` or `"false"`. Used only for enabled mandate first execution flows. |
| `payeeVpa` | string | Conditional | For non-dynamic-VPA integrations, Newton uses the merchant account VPA. For dynamic VPA integrations, no default; this field is required. | Required for dynamic VPA integrations. Must be the dynamic VPA assigned to the merchant. |
| `subMerchantDetails` | object | Conditional | No default. | Required only for enabled dynamic VPA/sub-merchant aggregator integrations. |
| `iat` | string | No | No default. | Issued-at timestamp used as part of request signature verification where applicable. |
| `udfParameters` | string | No | No default. Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the response. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are simply not stored/returned when omitted.

- `upiRequestId`: generated by Newton when omitted for non-multibank integrations.
- `payeeVpa`: defaults to the merchant account VPA for non-dynamic-VPA integrations.
- `intentRequestExpiryMinutes`: falls back to merchant configuration when available.
- `intentRequestExpirySeconds`: no direct default; if omitted, minutes/configured minutes are used when available.
- `enableTips`: omitted behaves as `false`.
- `applyRefundOnSuccess`: omitted behaves as `"false"`.
- `tpvType`: omitted behaves as non-`PARTIAL` TPV hash handling.
- `firstExecutionAmount`: only defaulted when `applyRefundOnSuccess = "true"`, using configured `defaultFirstExecutionAmount`.

When `applyRefundOnSuccess = "true"`, Newton also clears `mutualFundDetails` and `splitSettlementDetails` during register intent processing.

### Nested Request Objects

Nested objects do not have field-level defaults unless called out below. If an optional nested object is omitted, that feature is not applied for the registered intent.

#### `splitDetails[]`

Use `splitDetails` for tips or convenience-fee components configured for the merchant.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Split component name configured for the merchant, for example a convenience-fee or tip component. Must be non-empty. Duplicate names in the same request are rejected. |
| `value` | string | Yes | Split component amount in two-decimal format, for example `5.00`. Must be greater than zero. |

#### `splitSettlementDetails`

Use `splitSettlementDetails` only when split settlement is enabled for the merchant. This object is supported from `x-api-version: 3`.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `splitType` | string | Yes | Settlement split mode. Allowed values: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. |
| `merchantSplit` | string | Conditional | Merchant's own settlement share. For `AMOUNT`, send an amount such as `90.00`. For `PERCENTAGE`, send a percentage value such as `90.00`. Omit for `DEFAULT` and `LATER`. |
| `partnersSplit` | array of objects | Conditional | Partner settlement shares. Required when partners receive part of an `AMOUNT` or `PERCENTAGE` split. Omit for `DEFAULT` and `LATER`. |

Validation rules:

- For `AMOUNT`, `merchantSplit` plus all `partnersSplit[].value` values must equal the registered `amount`.
- For `PERCENTAGE`, `merchantSplit` plus all `partnersSplit[].value` values must equal `100.00`.
- For `DEFAULT` and `LATER`, do not send `merchantSplit` or `partnersSplit`.
- Partner ids may be validated against the merchant's configured partner/vendor list.

#### `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `partnerId` | string | Yes | Partner/vendor identifier configured for the merchant. Must be non-empty. |
| `value` | string | Yes | Partner's share. For `AMOUNT`, this is an amount such as `10.00`. For `PERCENTAGE`, this is a percentage such as `10.00`. |

#### `subMerchantDetails`

Use `subMerchantDetails` only for enabled dynamic VPA or aggregator/sub-merchant integrations. If account fields are supplied, `accountNumber`, `ifsc`, and `accountType` must all be supplied together. Sensitive account fields are used for processing and are not returned in the register intent response.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Sub-merchant display name. |
| `mcc` | string | Yes | Sub-merchant MCC. Must be a valid MCC. |
| `brandName` | string | Yes | Sub-merchant brand name. Must be alphanumeric and 1 to 99 characters. |
| `legalName` | string | Yes | Sub-merchant legal name. Must be alphanumeric and 1 to 99 characters. |
| `franchise` | string | Yes | Franchise or store-chain name. Must be alphanumeric and 1 to 99 characters. |
| `merchantType` | string | Yes | Sub-merchant size/type. Allowed values: `SMALL`, `LARGE`. |
| `ownershipType` | string | Yes | Ownership category. Allowed values: `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. |
| `genre` | string | Yes | Commerce channel. Allowed values: `ONLINE`, `OFFLINE`. |
| `onboardingType` | string | Yes | Onboarding source. Allowed values: `BANK`, `AGGREGATOR`. |
| `accountNumber` | string | Conditional | Sub-merchant settlement account number. Required only when sending sub-merchant account details. If supplied, also send `ifsc` and `accountType`. |
| `ifsc` | string | Conditional | Sub-merchant account IFSC. Required when `accountNumber` or `accountType` is supplied. |
| `accountType` | string | Conditional | Sub-merchant account type. Required when `accountNumber` or `ifsc` is supplied. |
| `bankName` | string | No | Sub-merchant bank name. |
| `bankIIN` | string | No | Sub-merchant bank IIN/bank code. Must be valid when supplied. |
| `gstin` | string | No | Sub-merchant GSTIN, if available. |
| `mid` | string | No | Sub-merchant MID. Must be alphanumeric and 1 to 20 characters when supplied. |
| `sid` | string | No | Sub-merchant SID. Must be alphanumeric and 1 to 20 characters when supplied. |
| `tid` | string | No | Sub-merchant TID. Must be alphanumeric and 1 to 20 characters when supplied. |

#### `mutualFundDetails[]`

Use `mutualFundDetails` only for merchants enabled for mutual fund or clearing corporation flows.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `memberId` | string | Yes | Mutual fund member id. |
| `userId` | string | Yes | Mutual fund user/customer id. |
| `mfPartner` | string | Yes | Mutual fund partner. Allowed values: `NSE`, `BSE`, `KFIN`, `CAMS`. |
| `investmentType` | string | Yes | Investment type. Allowed values: `LUMPSUM`, `SIP`. |
| `orderNumber` | string | Yes | Mutual fund order number. Follows `merchantRequestId` format rules; for `NSE` and `BSE`, length must be at most 25 characters. |
| `amount` | string | Yes | Mutual fund order amount in two-decimal format. Must be greater than zero. |
| `amcCode` | string | No | AMC code. |
| `folioNumber` | string | No | Investor folio number. |
| `ihNumber` | string | No | Internal holding/reference number. |
| `schemeCode` | string | No | Mutual fund scheme code. |
| `panNumber` | string | No | Investor PAN. Must be valid when supplied. |
| `applicationNumber` | string | No | Partner reference number, also known as ITRN. |

The total of all `mutualFundDetails[].amount` values must match the applicable register intent amount. For mandate first-execution flows, the total is validated against `firstExecutionAmount`; otherwise it is validated against `amount`.

## Request Examples

### Standard Payment Intent

```json
{
  "merchantRequestId": "ORDER12345",
  "amount": "100.00",
  "flow": "TRANSACTION",
  "intentRequestExpiryMinutes": "15",
  "remarks": "Order payment",
  "refUrl": "https://merchant.example/orders/ORDER12345",
  "refCategory": "00",
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

### Payment Intent With TPV

```json
{
  "merchantRequestId": "ORDER12346",
  "amount": "250.00",
  "flow": "TRANSACTION",
  "intentRequestExpiryMinutes": "10",
  "payerAccountHashes": [
    "expected-account-hash"
  ],
  "tpvType": "FULL",
  "remarks": "TPV order payment"
}
```

### Payment Intent With Convenience Fee

```json
{
  "merchantRequestId": "ORDER12347",
  "amount": "100.00",
  "flow": "TRANSACTION",
  "intentRequestExpiryMinutes": "15",
  "splitDetails": [
    {
      "name": "CCONFEE",
      "value": "5.00"
    }
  ],
  "remarks": "Order payment"
}
```

In this example, `amount` is the base amount. The final UPI authorization can include the configured split amount, and Newton validates the split details during payment authorization.

### Dynamic VPA / Sub-Merchant Intent

```json
{
  "merchantRequestId": "ORDER12348",
  "amount": "100.00",
  "flow": "TRANSACTION",
  "payeeVpa": "store123@bank",
  "subMerchantDetails": {
    "name": "Store Name",
    "mcc": "5411",
    "brandName": "Store Brand",
    "legalName": "Store Legal Name",
    "franchise": "Store Franchise",
    "merchantType": "SMALL",
    "ownershipType": "PROPRIETARY",
    "genre": "ONLINE",
    "onboardingType": "AGGREGATOR",
    "mid": "MID123",
    "sid": "SID123",
    "tid": "TID123"
  },
  "intentRequestExpiryMinutes": "15",
  "remarks": "Sub merchant payment"
}
```

### Mandate Intent

```json
{
  "merchantRequestId": "MANDATE12345",
  "amount": "500.00",
  "flow": "MANDATE",
  "intentRequestExpiryMinutes": "30",
  "firstExecutionAmount": "100.00",
  "applyRefundOnSuccess": "false",
  "remarks": "Mandate setup"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. |
| `payload` | object | Register intent result. |
| `udfParameters` | string | Echoed from request when supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier. |
| `subMerchantId` | string | Present for applicable sub-merchant flows from response version 3 onward. |
| `subMerchantChannelId` | string | Present for applicable sub-merchant flows from response version 3 onward. |
| `merchantCustomerId` | string | Merchant customer id supplied in the request, when supplied. |
| `merchantRequestId` | string | Merchant request id supplied in the request. |
| `gatewayTransactionId` | string | UPI transaction id to use for the intent/QR payload. |
| `orderId` | string | Newton reference/order id to use for the intent/QR payload. |
| `payeeName` | string | Payee display name. |
| `payeeVpa` | string | Payee VPA to use for the UPI intent/QR. |
| `payeeMcc` | string | Payee MCC. |
| `amount` | string | Registered amount, formatted to two decimals. |
| `currency` | string | Currency configured for the merchant. |
| `remarks` | string | Registered remarks. |
| `refUrl` | string | Registered reference URL. |
| `refCategory` | string | Registered reference category. |
| `flow` | string | `TRANSACTION` or `MANDATE`. Present from response version 2 onward. |
| `tpvType` | string | `FULL` or `PARTIAL`. Present from response version 4 onward when supplied. |
| `splitDetails` | array | Returned from response version 3 onward when supplied. |
| `enableTips` | boolean | Returned from response version 3 onward when supplied. |
| `splitSettlementDetails` | object | Returned from response version 3 onward when supplied. |
| `mutualFundDetails` | array | Returned when supplied. |
| `payerAccountHashes` | array | Returned when supplied. |
| `firstExecutionAmount` | string | Returned when supplied or defaulted. |
| `applyRefundOnSuccess` | string | Returned when supplied. |

### Example Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "ORDER12345",
    "gatewayTransactionId": "YBL0000000000000000000000000000001",
    "orderId": "ORDER12345",
    "payeeName": "Merchant Name",
    "payeeVpa": "merchant@bank",
    "payeeMcc": "5411",
    "amount": "100.00",
    "currency": "INR",
    "remarks": "Order payment",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "refCategory": "00",
    "flow": "TRANSACTION",
    "tpvType": "FULL"
  },
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

## Response Versioning

Use `x-api-version: 4` for new integrations.

| `x-api-version` | Response behavior |
| --- | --- |
| `0` | Legacy behavior. Some fields may be omitted, especially for non-multibank merchants. |
| `1` | Includes payee VPA, MCC, amount, currency, remarks, ref URL, and ref category. |
| `2` | Adds `flow`. |
| `3` | Adds sub-merchant fields, `splitDetails`, `enableTips`, and `splitSettlementDetails`. |
| `4` | Adds `tpvType`. Recommended for new integrations. |

## Idempotency

`merchantRequestId` is the idempotency key.

- For standard integrations, a duplicate `merchantRequestId` is rejected as a duplicate request.
- For multibank-enabled integrations, a repeated request can succeed only when the existing registered intent has the same `upiRequestId` and amount.
- If the repeated request has a different amount, Newton returns an amount mismatch error.
- If the repeated request has a different `upiRequestId`, Newton returns a UPI request id mismatch error.

Recommended client behavior:

- Generate a new `merchantRequestId` for each merchant order.
- Reuse the same `merchantRequestId` only for retrying the same logical register intent call.
- Store `merchantRequestId`, `gatewayTransactionId`, and `orderId` against the merchant order.

## Expiry

Use one of:

- `intentRequestExpirySeconds` for precise expiry.
- `intentRequestExpiryMinutes` for minute-level expiry.

If both are sent, seconds take precedence.

Once the intent expires, a later payment authorization for that intent can fail. Choose an expiry that covers the expected customer payment window but does not leave unused payment links active for too long.

## Validation During Payment

When the customer authorizes the payment, Newton validates the incoming UPI request against the registered intent.

For `TRANSACTION` flow, Newton can validate:

- intent is not expired
- flow is `TRANSACTION`
- amount matches
- split/tip details match, when supplied
- TPV payer account hash matches, when enabled
- direct pay is not being attempted where register intent is mandatory

For `MANDATE` flow, Newton can validate:

- intent is not expired
- flow is `MANDATE`
- payee VPA matches, when applicable
- mandate amount matches
- TPV payer account hash matches, when enabled

## Feature-Specific Notes

### TPV

Send `payerAccountHashes` only if TPV is enabled for the merchant.

If TPV is enforced, `payerAccountHashes` is mandatory. If TPV is not enabled, sending `payerAccountHashes` is rejected.

`tpvType` can be:

- `FULL`
- `PARTIAL`

`PARTIAL` requires `x-api-version: 4`.

### Split Details, Tips, and Convenience Fee

`splitDetails` is used to register additional amount components such as convenience fees. Supported split names are configured during onboarding.

Rules:

- `splitDetails` must not be an empty list.
- Duplicate split names are rejected.
- Split values must be in two-decimal amount format.
- If tips are expected, set `enableTips` to `true`.

### Split Settlement

`splitSettlementDetails` is supported from `x-api-version: 3`.

Supported `splitType` values:

- `AMOUNT`
- `PERCENTAGE`
- `DEFAULT`
- `LATER`

Example:

```json
{
  "splitType": "AMOUNT",
  "merchantSplit": "90.00",
  "partnersSplit": [
    {
      "partnerId": "partner-1",
      "value": "10.00"
    }
  ]
}
```

### Dynamic VPA and Sub-Merchant

For dynamic VPA integrations, send `payeeVpa`.

For aggregator/sub-merchant integrations, send `subMerchantDetails` when enabled for your merchant profile. Newton validates that the dynamic VPA belongs to the merchant. Sensitive account details in `subMerchantDetails`, if supplied, are not returned in the response.

### Mutual Fund Details

Send `mutualFundDetails` only for merchants enabled for mutual fund or clearing corporation flows. Some merchants are configured to require these details.

### Mandate First Execution

`firstExecutionAmount` and `applyRefundOnSuccess` are available only when mandate first execution is enabled for the merchant.

Rules:

- `firstExecutionAmount` must not exceed `amount`.
- `applyRefundOnSuccess` must be `"true"` or `"false"` when supplied.

## Error Handling

Failure responses use the same encrypted response transport as successful responses. The examples below show the decrypted business body.

Most failure bodies follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Flow Should be Present"
}
```

When `payload` is empty, it is omitted from the JSON response.

Clients should read `status`, `responseCode`, and `responseMessage` from the body. Depending on where validation fails, the HTTP status can be `200`, `400`, `422`, or `500`; the body is the stable integration contract.

### Register Intent Failure Bodies

Use the body pattern shown in the `Response body` column for each scenario.

| Scenario | Response body |
| --- | --- |
| Request field validation failure, such as invalid `remarks`, expiry, `payeeVpa`, `tpvType`, `applyRefundOnSuccess`, or nested object fields | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"payeeVpa regex failed\""}` |
| Amount not in `100.00` format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"amount regex match failed\""}` |
| `merchantRequestId` is empty, too long, or has invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\""}` |
| `flow` value is not `TRANSACTION` or `MANDATE` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"EnumValidation \"Enum match failed COLLECT\""}` |
| Missing `flow` when `x-api-version > 1` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Flow Should be Present"}` |
| Multibank request missing `upiRequestId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"upiRequestId not present in Multibank request"}` |
| TPV is enforced but `payerAccountHashes` is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"PayerAccountHashes Should be Present"}` |
| `payerAccountHashes` is sent for a merchant where TPV is not supported | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"TPV not Supported"}` |
| `tpvType` is `PARTIAL` with `x-api-version < 4` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"TpvType Partial is supported only in api version 4 or higher"}` |
| `splitDetails` is an empty list | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"splitDetails should not be an empty list"}` |
| `splitDetails` contains an unsupported split type or duplicate split type | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Not a valid split type / Duplicate split type"}` |
| `splitSettlementDetails` is sent with `x-api-version < 3` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Split Settlement not supported in this API Version"}` |
| Split settlement is enabled for the merchant but details are missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"SplitSettlementDetails not Found"}` |
| Split settlement is not enabled for the merchant but details are sent | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"SplitSettlement not Allowed"}` |
| `splitSettlementDetails` is sent for an unsupported/non-transaction flow | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Split Settlement not allowed for Non Transaction flows"}` |
| Split settlement amount sum does not match expected amount | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Amount Sum Mismatch"}` |
| Split settlement percentage values do not sum to `100.00` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Percentage Split"}` |
| Split settlement body does not match the selected `splitType` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Split Details"}` |
| Split settlement partner id is not valid for the merchant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Partner"}` |
| `firstExecutionAmount` is sent but mandate first execution is not enabled for the merchant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"AutoFirstExecution Not Enabled"}` |
| `firstExecutionAmount` is greater than `amount`, or amount data required to validate it is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid firstExecutionAmount"}` |
| `subMerchantDetails` is sent when dynamic VPA is not enabled | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"sub merchant details not allowed"}` |
| Dynamic VPA is enabled but `payeeVpa` is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"payeeVpa not found"}` |
| `payeeVpa` does not match a configured dynamic VPA row | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Vpa Regex Not Matched"}` |
| Dynamic VPA exists but is not mapped to the merchant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Merchant validation failed"}` |
| Merchant is configured to require `mutualFundDetails`, but they are missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"MF details are mandatory for this merchant"}` |
| `mutualFundDetails` is sent but `amount` is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Amount field is missing"}` |
| Mandate mutual-fund first execution path requires `firstExecutionAmount`, but it is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"firstExecutionAmount field is missing"}` |
| `mutualFundDetails` is sent but `flow` is missing or invalid | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Flow is missing or invalid"}` |
| `mutualFundDetails` is sent for a merchant not enabled for mutual fund transactions | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Merchant is not enabled for mutual fund transactions"}` |
| Mutual fund detail total does not match request amount | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Expected Amount does matches with Actual Amount"}` |
| Mutual fund order number length is invalid for NSE/BSE | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Order Number Length should be at most 25 for NSE/BSE MF Partner"}` |
| Mutual fund record already exists for the same UPI request id | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| Duplicate `merchantRequestId` for a standard/non-multibank register intent | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| Multibank retry uses the same `merchantRequestId` but a different amount | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Amount Mismatch"}` |
| Multibank retry uses the same `merchantRequestId` but a different `upiRequestId` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"UpiRequestId Mismatch"}` |
| Unexpected server, database, encryption, or cache failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

Authentication, signature, and encryption failures can occur before the register-intent business payload is processed. Those failures use the standard Newton S2S error body, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

or:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Payment-Time Failures

Some failures happen later, when the customer authorizes the UPI payment or mandate. These are not returned by the `registerIntent` API call because registration has already succeeded. They appear in transaction status, mandate status, or callbacks.

| Later validation scenario | Result surfaced later |
| --- | --- |
| Intent expired | Payment/mandate authorization fails |
| Amount mismatch | Payment/mandate authorization fails |
| Flow mismatch | Payment/mandate authorization fails |
| TPV account mismatch | Payment/mandate authorization fails |
| Direct pay attempted where register intent is mandatory | Payment authorization fails |
