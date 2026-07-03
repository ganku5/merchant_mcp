# Web Collect API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/webCollect`

## Overview

Web Collect is a server-to-server API used to create a UPI collect request from a merchant backend to a payer VPA.

The merchant calls this API with a merchant order/reference id, payer VPA, amount, and collect expiry. Newton validates the request, creates a merchant order, registers TPV data when applicable, and sends a UPI collect request through the payment switch. The API returns Newton and gateway identifiers plus the immediate gateway response metadata.

Use this API when the merchant wants Newton to initiate a collect request directly to the customer's UPI app. For checkout journeys that need the customer to open a UPI app through an intent or QR, use the intent/QR flows instead.

## Business Use Case

Web Collect helps merchants:

- Initiate UPI collect requests to a known payer VPA.
- Track each collect request using a merchant-generated `merchantRequestId`.
- Control collect expiry in minutes.
- Enforce TPV by allowing only configured payer account hashes where enabled.
- Pass purpose, initiation mode, reference URL/category, invoice, GST split, geocode, and merchant-defined metadata.
- Support split settlement where enabled for the merchant.
- Support mutual fund or clearing corporation reporting where enabled.
- Receive immediate gateway response details for reconciliation and follow-up status checks.

## Integration Flow

1. Merchant creates an order in its own system.
2. Merchant calls `webCollect` with payer VPA, amount, expiry, and optional feature fields.
3. Newton authenticates the merchant, validates request fields and merchant configuration, and rejects duplicate `merchantRequestId` values.
4. Newton creates a merchant order and internal transaction id.
5. Newton sends the collect request to the downstream UPI switch/NPCI path.
6. Newton returns the immediate response with `gatewayTransactionId`, optional `gatewayReferenceId`, gateway response code, and gateway response status.
7. Merchant stores identifiers and uses transaction status/callbacks for the final collect outcome if the customer action is still pending.

Important identifiers:

- `merchantRequestId`: Merchant-generated unique order/reference id and duplicate guard for this API.
- `gatewayTransactionId`: Newton-generated UPI request id for the collect transaction.
- `gatewayReferenceId`: Downstream/gateway reference id when the switch returns one.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/webCollect
```

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope. The examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. `1` or higher is recommended so response fields gated above legacy version `0` are included. |
| `x-merchant-id` | Merchant id issued during onboarding. |
| `x-merchant-channel-id` | Merchant channel id issued during onboarding. |
| `x-sub-merchant-id` | Required only for enabled sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Required only for enabled sub-merchant integrations. |
| `x-timestamp` | Request timestamp used by signature/timestamp validation. |
| `x-merchant-signature` | Merchant request signature for unsigned/plain business payload mode. |
| `x-forwarded-for` | Required when the merchant has IP whitelisting configured. Newton checks the first IP in the comma-separated list. |
| `x-request-id` | Optional request correlation id. Newton generates one if omitted. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding:

- The route accepts the common `EncRequest` envelope: encrypted JWE, signed JWS, or unsigned/plain JSON depending on merchant configuration and environment.
- Encrypted requests must decrypt to a signed body; otherwise the request is rejected before business validation.
- Signed/unsigned request signature verification uses `x-merchant-id`, `x-merchant-channel-id`, optional sub-merchant headers, `x-timestamp`, and raw request body.
- Merchant API access, blocked/allowed API configuration, timestamp validity, and optional IP whitelist are checked before product logic runs.

## Request

### Required Minimum

For merchants that are not exempt from collect platform validation, send `platform: "IOS"` for standard UPI collect. Collect on `ANDROID` and `WEB` can be blocked by configuration with a message instructing the client to use UPI Intent.

```json
{
  "merchantRequestId": "ORDER12345",
  "customerVpa": "customer@bank",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "platform": "IOS"
}
```

With references and remarks:

```json
{
  "merchantRequestId": "ORDER12346",
  "customerVpa": "customer@bank",
  "collectRequestExpiryMinutes": "10",
  "amount": "250.00",
  "platform": "IOS",
  "remarks": "Order payment",
  "refUrl": "https://merchant.example/orders/ORDER12346",
  "refCategory": "00",
  "udfParameters": {
    "cartId": "CART123"
  }
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Unique merchant order/reference id. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Used as the duplicate guard. |
| `customerVpa` | string | Yes | No default. | Customer/payer VPA that will receive the collect request. Must be a valid VPA. Newton trims/lowercases this value when sending to the downstream collect request. |
| `collectRequestExpiryMinutes` | string | Yes | No default. | Collect expiry in minutes. Numeric string from `1` to `64800`. Newton converts this to an absolute expiry timestamp for the downstream collect request. |
| `amount` | string | Yes | No default. | Collect amount in two-decimal format, for example `100.00`. Must be greater than `0.00`. |
| `platform` | string | Conditional | No default. | Allowed values: `ANDROID`, `IOS`, `WEB`. Required unless platform validation is bypassed/config-exempt or the purpose/MCC flow is exempt. Standard collect is allowed only for `IOS` when platform validation applies; `ANDROID` and `WEB` are rejected with a use-intent message. |
| `initiationMode` | string | No | Defaults to `"00"` in the downstream collect request. | UPI initiation mode. Must be exactly 2 alphanumeric characters when supplied. |
| `purpose` | string | No | Defaults to `"00"` in the downstream collect request. For merchants configured as B2B, downstream purpose is forced to `"20"`. | UPI purpose code. Must be exactly 2 uppercase alphanumeric characters. Merchant configuration can block specific purpose codes. eRupi purpose codes use `M2M_COLLECT`; other purposes use `P2M_COLLECT`. |
| `refUrl` | string | Conditional with `refCategory` | If both `refUrl` and `refCategory` are omitted, Newton uses configured NPCI defaults downstream. If one is supplied without the other, validation fails. | Merchant reference URL. Must be non-empty when supplied. If `remarks` contains URL-encoded parameters, Newton may decode parameters and update `refUrl`/`remarks` before downstream submission. |
| `refCategory` | string | Conditional with `refUrl` | If both are omitted, Newton uses configured NPCI defaults downstream. If one is supplied without the other, validation fails. | Merchant reference category. Must be non-empty when supplied. |
| `remarks` | string | No | Downstream default is `Collect Request from {configured PSP name} UPI`. Response `remarks` is omitted if request omitted it. | Payment note. Length `1` to `255`; must match the remarks regex accepted by Newton. |
| `invoiceName` | string | No | No default. | Optional invoice name included in downstream GST invoice details. Must be non-empty when supplied. |
| `invoiceNum` | string | No | No default. | Optional invoice number included in downstream GST invoice details. Must be non-empty when supplied. |
| `invoiceDate` | string | No | No default. | Optional invoice date included in downstream GST invoice details. The Web Collect request validator does not enforce a date format. |
| `split` | string | No | No default. | Optional GST amount split payload consumed by Newton's GST split transformer. Use only if enabled and format has been shared during onboarding. |
| `payerAccountHashes` | array of strings | Conditional | No default. | Required when TPV is enforced for the merchant. Rejected when the merchant is not TPV enabled. If supplied, the list must not be empty. Echoed in the response. |
| `tpvType` | string | No | If omitted, TPV handling is non-`PARTIAL`. | Allowed values: `FULL`, `PARTIAL`. `PARTIAL` is rejected when `x-api-version < 1` for this API. Echoed in the response when supplied. |
| `splitSettlementDetails` | object | Conditional | No default. If split settlement is enabled for the merchant, this field is required. If split settlement is not enabled, sending it is rejected. | Split settlement instruction. The amount split is validated against `amount`. Echoed in the response when supplied. |
| `mutualFundDetails` | array | Conditional | No default. Required only when merchant configuration blocks transactions without MF details. | Mutual fund/clearing corporation details. Merchant must be enabled for MF transactions. Total MF detail amount must equal `amount`. Echoed in the response when supplied. |
| `geocode` | string | No | No default. | Latitude/longitude in `lat,long` format. Latitude must be within `90`, longitude within `180`. Sent in downstream payee info. |
| `iat` | string | Conditional by envelope | Required for encrypted/signed payload timestamp validation; plain payload validation ignores it. | Issued-at timestamp in the decrypted payload for signed/encrypted request validation. |
| `udfParameters` | JSON object or JSON-object string | No | No default. | Merchant-defined metadata. Must pass Newton's UDF validation. Stored on the merchant order and echoed in the top-level response when supplied. |

Fields not listed here are not accepted by the `WebCollectRequest` type.

### Defaults and Omitted Field Behavior

- `initiationMode`: downstream default is `"00"`.
- `purpose`: downstream default is `"00"` unless the merchant is configured as B2B, where downstream purpose is forced to `"20"`.
- `remarks`: downstream default uses the configured PSP name, for example `Collect Request from Example UPI`, but the response only echoes request remarks.
- `refUrl` and `refCategory`: both must be supplied together. If both are omitted, downstream defaults from NPCI configuration are used.
- `platform`: no request default. It may be mandatory depending on merchant/config/MCC/purpose.
- `gatewayTransactionId`: generated by Newton; merchants do not send it in this API.
- `payeeVpa`: not supplied by the merchant in this API. Newton uses the merchant account VPA.

## Nested Request Objects

### `splitSettlementDetails`

Use `splitSettlementDetails` only when split settlement is enabled for the merchant.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `splitType` | string | Yes | Settlement split mode. Allowed values: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. |
| `merchantSplit` | string | Conditional | Merchant's own settlement share. Required with `partnersSplit` for explicit `AMOUNT` or `PERCENTAGE` splits. Omit for `DEFAULT` and `LATER`. |
| `partnersSplit` | array of objects | Conditional | Partner settlement shares. Omit for `DEFAULT` and `LATER`. |

Validation rules:

- For `AMOUNT`, `merchantSplit` plus all `partnersSplit[].value` values must equal `amount`.
- For `PERCENTAGE`, `merchantSplit` plus all `partnersSplit[].value` values must equal `100.00`.
- For `DEFAULT` and `LATER`, do not send `merchantSplit` or `partnersSplit`.
- If vendor validation is enabled, each partner id is checked against the merchant's configured vendor list.

### `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `partnerId` | string | Yes | Partner/vendor identifier configured for the merchant. Must be non-empty. |
| `value` | string | Yes | Partner share amount or percentage in two-decimal format. |

### `mutualFundDetails[]`

Use `mutualFundDetails` only for merchants enabled for mutual fund or clearing corporation flows.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `memberId` | string | Yes | Mutual fund member id. |
| `userId` | string | Yes | Mutual fund user/customer id. |
| `mfPartner` | string | Yes | Mutual fund partner. Allowed values are defined by the storage enum; code paths explicitly handle `NSE`, `BSE`, `KFIN`, and `CAMS`. |
| `investmentType` | string | Yes | Investment type configured for MF transactions, for example `LUMPSUM` or `SIP` where supported. |
| `orderNumber` | string | Yes | Mutual fund order number. Follows `merchantRequestId` format rules; for `NSE` and `BSE`, length must be at most 25 characters. |
| `amount` | string | Yes | MF order amount in two-decimal format. Must be greater than `0.00`. |
| `amcCode` | string | No | AMC code. |
| `folioNumber` | string | No | Investor folio number. |
| `ihNumber` | string | No | Internal holding/reference number. |
| `schemeCode` | string | No | Mutual fund scheme code. |
| `panNumber` | string | No | Investor PAN. Must be valid when supplied. |
| `applicationNumber` | string | No | Partner reference number, also known as ITRN. |

The total of all `mutualFundDetails[].amount` values must equal the Web Collect `amount`.

## Request Examples

### Standard iOS Collect

```json
{
  "merchantRequestId": "ORDER12345",
  "customerVpa": "customer@bank",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "platform": "IOS",
  "remarks": "Order payment",
  "refUrl": "https://merchant.example/orders/ORDER12345",
  "refCategory": "00"
}
```

### Collect With TPV

```json
{
  "merchantRequestId": "ORDER12347",
  "customerVpa": "customer@bank",
  "collectRequestExpiryMinutes": "10",
  "amount": "250.00",
  "platform": "IOS",
  "payerAccountHashes": [
    "expected-account-hash"
  ],
  "tpvType": "FULL",
  "remarks": "TPV order payment"
}
```

### Collect With Split Settlement

```json
{
  "merchantRequestId": "ORDER12348",
  "customerVpa": "customer@bank",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "platform": "IOS",
  "splitSettlementDetails": {
    "splitType": "AMOUNT",
    "merchantSplit": "90.00",
    "partnersSplit": [
      {
        "partnerId": "partner-1",
        "value": "10.00"
      }
    ]
  }
}
```

### Collect With Mutual Fund Details

```json
{
  "merchantRequestId": "MFORDER123",
  "customerVpa": "investor@bank",
  "collectRequestExpiryMinutes": "15",
  "amount": "1000.00",
  "platform": "IOS",
  "mutualFundDetails": [
    {
      "memberId": "MEMBER123",
      "userId": "USER123",
      "mfPartner": "NSE",
      "investmentType": "LUMPSUM",
      "orderNumber": "MFORDER123",
      "amount": "1000.00",
      "panNumber": "ABCDE1234F"
    }
  ]
}
```

## Collect Behavior

Newton creates a merchant order before calling the downstream UPI collect path. The downstream pay request uses:

- merchant account VPA as payee VPA
- `customerVpa` as payer VPA
- generated `gatewayTransactionId` as UPI request id
- merchant order id as the transaction reference (`tr`)
- `P2M_COLLECT` pay type for normal purpose codes
- `M2M_COLLECT` pay type for eRupi purpose codes
- configured merchant account and merchant information for payee account details

This API does not return a redirect URL, deeplink, or web checkout link. It initiates a collect request to the payer VPA. The customer completes or declines the request in their UPI app. Use transaction status APIs and callbacks to reconcile final state after the immediate API response.

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. |
| `payload` | object | Web Collect result. |
| `udfParameters` | JSON object or string | Echoed from request when supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier. |
| `subMerchantId` | string | Present for applicable sub-merchant calls when `x-api-version > 0`. |
| `subMerchantChannelId` | string | Present for applicable sub-merchant calls when `x-api-version > 0`. |
| `merchantRequestId` | string | Merchant request id supplied in the request. |
| `payeeMcc` | string | Payee MCC when returned for the merchant/config version. |
| `customerVpa` | string | Customer/payer VPA supplied in the request. |
| `transactionTimestamp` | string | Newton transaction creation timestamp. |
| `gatewayTransactionId` | string | Newton-generated UPI request id for this collect request. |
| `gatewayReferenceId` | string | Downstream/gateway reference id when returned and when `x-api-version > 0`. |
| `gatewayResponseCode` | string | Immediate downstream response code from the UPI switch/NPCI path. `00` indicates immediate gateway success. |
| `gatewayResponseStatus` | string | Present when `x-api-version > 0`. Derived from `gatewayResponseCode`: `SUCCESS` for `00`, otherwise `FAILURE`. |
| `gatewayResponseMessage` | string | Immediate downstream response message/result. |
| `remarks` | string | Request remarks when supplied. |
| `refUrl` | string | Response reference URL according to merchant/config response behavior. |
| `payerAccountHashes` | array of strings | Echoed when supplied. |
| `mutualFundDetails` | array | Echoed when supplied. |
| `splitSettlementDetails` | object | Echoed when supplied/stored. |
| `tpvType` | string | Echoed when supplied. |

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
    "payeeMcc": "5411",
    "customerVpa": "customer@bank",
    "transactionTimestamp": "2026-07-02 12:30:45",
    "gatewayTransactionId": "YBL0000000000000000000000000000001",
    "gatewayReferenceId": "619812345678",
    "gatewayResponseCode": "00",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseMessage": "SUCCESS",
    "remarks": "Order payment",
    "refUrl": "https://merchant.example/orders/ORDER12345"
  },
  "udfParameters": {
    "cartId": "CART123"
  }
}
```

### Example Accepted But Pending Customer Action

The immediate API response can be successful because the collect request was created, while the customer action is still pending in their UPI app. In that case, store the identifiers and poll or consume callbacks for the final transaction state.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "ORDER12346",
    "customerVpa": "customer@bank",
    "transactionTimestamp": "2026-07-02 12:31:10",
    "gatewayTransactionId": "YBL0000000000000000000000000000002",
    "gatewayResponseCode": "00",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseMessage": "SUCCESS"
  }
}
```

## Response Versioning

Use the onboarded `x-api-version` for your merchant. For new integrations, avoid legacy version `0`.

| `x-api-version` | Response behavior |
| --- | --- |
| `0` | Legacy behavior. `subMerchantId`, `subMerchantChannelId`, `gatewayReferenceId`, and `gatewayResponseStatus` are removed from the response. |
| `> 0` | Includes `subMerchantId`, `subMerchantChannelId`, `gatewayReferenceId`, and `gatewayResponseStatus` when values are available. |

## Validation Rules

Request validation runs before product/business logic:

- `merchantRequestId` must be 1 to 35 characters and match the allowed id regex.
- `customerVpa` must be a valid VPA.
- `collectRequestExpiryMinutes` must be numeric and between `1` and `64800`.
- `amount` must match `^[0-9]+\.[0-9][0-9]$` and be greater than `0.00`.
- `refUrl` and `refCategory` must either both be present or both be omitted.
- `remarks`, `invoiceName`, and `invoiceNum` must be non-empty when supplied; `remarks` has additional length and regex checks.
- `initiationMode` must be exactly 2 alphanumeric characters when supplied.
- `purpose` must be exactly 2 uppercase alphanumeric characters when supplied.
- `payerAccountHashes` must not be an empty list when supplied.
- `udfParameters` must be a valid JSON object or JSON-object string and must pass the configured character validation.
- `geocode` must be `lat,long` with valid latitude/longitude ranges.
- `tpvType` must be `FULL` or `PARTIAL`.
- `platform` must be `ANDROID`, `IOS`, or `WEB`.
- Nested `mutualFundDetails` and `splitSettlementDetails` are validated using their own rules.

Business validation then checks:

- merchant/sub-merchant validity and API access
- TPV enforcement for the merchant
- split settlement enablement and split totals
- blocked purpose codes
- `tpvType = PARTIAL` API-version support
- duplicate `merchantRequestId`
- collect platform restrictions
- merchant account availability and VPA decryption
- mandatory MF details and MF merchant enablement
- downstream UPI switch/NPCI response availability

## Duplicate and Idempotency Behavior

`merchantRequestId` is the duplicate guard. Newton looks up an existing merchant order for the resolved merchant before creating a new collect request.

- First request with a new `merchantRequestId`: processed normally.
- Repeat request with the same `merchantRequestId`: rejected with `DUPLICATE_REQUEST`.
- Web Collect does not replay and return the original success response for duplicate requests.

Recommended client behavior:

- Generate a new `merchantRequestId` for each logical collect/order attempt.
- Store `merchantRequestId`, `gatewayTransactionId`, and `gatewayReferenceId` when returned.
- If the HTTP call times out after submission, do not immediately create a new collect with a different id. First call transaction status using stored identifiers if available, or retry once with the same `merchantRequestId`. A duplicate response means Newton likely accepted the first request; reconcile by status/callback or support lookup.

## Error Handling

Failure responses use the same encrypted response transport as successful responses when the response can be produced through the normal S2S path. The examples below show decrypted bodies.

Most failure bodies follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

When `payload` is empty, it is omitted from the JSON response. Clients should read `status`, `responseCode`, and `responseMessage` from the body. Depending on where validation fails, HTTP status can be `200`, `400`, `401`, `403`, or `500`; the body is the stable integration contract.

### Request Validation Failures

| Scenario | Decrypted response body |
| --- | --- |
| Invalid JSON/body shape or encrypted payload parses to an unexpected body | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: key \"merchantRequestId\" not found"}` |
| Missing required business field such as `merchantRequestId`, `customerVpa`, `collectRequestExpiryMinutes`, or `amount` | Usually rejected during JSON parsing or validation. Body can be `INVALID_DATA` for parse failures, or `BAD_REQUEST` with validation details when parsed. |
| Invalid `merchantRequestId` length or characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\""}` |
| Invalid `customerVpa` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"customerVpa regex failed\""}` |
| Invalid `collectRequestExpiryMinutes` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"expiry regex match failed\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"expiry is not valid\""}` |
| Invalid `amount` format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"amount regex match failed\""}` |
| Amount is `0.00` or less | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"amount is not greater than 0.0\""}` |
| Only one of `refUrl` / `refCategory` is present | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"RefUrl or Ref Category not present.\""}` |
| Empty `refUrl` or `refCategory` when supplied | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"refUrl field is empty\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"refCategory field is empty\""}` |
| Invalid `remarks` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"remarks length is not between 1 and 255\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"remarks regex match failed\""}` |
| Invalid `invoiceName` or `invoiceNum` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"Field is empty\""}` |
| Invalid `initiationMode` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"InitiationMode length is not 2\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"initiationMode regex match failed\""}` |
| Invalid `purpose` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"Purpose Code length is not 2\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"Purpose Code regex match failed\""}` |
| Empty `payerAccountHashes` list | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ListValidation \"Field is empty\""}` |
| Invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"JSON Object regex match failed for udfParameters\""}` or a related UDF JSON validation message. |
| Invalid `geocode` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"geocode not valid\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"Incorrect latitude/longitude value\""}` |
| Invalid `tpvType` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"EnumValidation \"Enum match failed LIMITED\""}` |
| Invalid `platform` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"EnumValidation \"Enum match failed DESKTOP\""}` |

### Merchant, Auth, and Access Failures

Authentication, signature, encryption, timestamp, merchant access, and IP failures can occur before Web Collect business logic runs.

| Scenario | Decrypted response body |
| --- | --- |
| Missing merchant id/channel id headers, raw body header, timestamp, signature, or invalid signature | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| JWE decryption fails or encrypted request cannot be validated to the expected signed payload | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| JWS signature verification fails during payload verification | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| SDK-style payload auth failure paths, where applicable to the merchant envelope | `{"status":"FAILURE","responseCode":"AUTH_FAILURE","responseMessage":"AUTH_FAILURE"}` |
| API blocked for merchant or not present in merchant/sub-merchant allowed API list | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| Request IP is not in configured `whitelistedIps`, or `x-forwarded-for` is missing while whitelist exists | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Timestamp is missing or outside allowed range | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` or a timestamp-specific unauthorized body depending on the validation layer. |

### Business Validation Failures

| Scenario | Decrypted response body |
| --- | --- |
| TPV is enforced but `payerAccountHashes` is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"PayerAccountHashes Should be Present"}` |
| `payerAccountHashes` is sent for a merchant where TPV is not supported | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"TPV not Supported"}` |
| `tpvType` is `PARTIAL` with `x-api-version < 1` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"TpvType Partial is supported only in api version 1 or higher"}` |
| Purpose code blocked by merchant configuration | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Purpose Code is Blocked"}` |
| Duplicate `merchantRequestId` for the resolved merchant | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| `platform` is required by collect platform validation but omitted | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Missing mandatory parameter: platform."}` |
| Platform is blocked for UPI collect, for example `ANDROID` or `WEB` when standard platform validation applies | `{"status":"FAILURE","responseCode":"FORBIDDEN","responseMessage":"UPI Collect is restricted on this platform. Please use UPI Intent."}` |
| Split settlement is enabled for the merchant but `splitSettlementDetails` is missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"SplitSettlementDetails not Found"}` |
| Split settlement is not enabled for the merchant but `splitSettlementDetails` is sent | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"SplitSettlement not Allowed"}` |
| Split settlement amount total does not match `amount` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Amount Sum Mismatch"}` |
| Split settlement percentage values do not sum to `100.00` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Percentage Split"}` |
| Split settlement body does not match the selected `splitType` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Split Details"}` |
| Split settlement partner id is not valid for the merchant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Partner"}` |
| Merchant is configured to require MF details but request omitted `mutualFundDetails` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"MF details are mandatory for this merchant"}` |
| `mutualFundDetails` is sent for a merchant not enabled for mutual fund transactions | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Merchant is not enabled for mutual fund transactions"}` |
| Mutual fund detail total does not match `amount` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Expected Amount does matches with Actual Amount"}` |
| Mutual fund `orderNumber` length is invalid for `NSE` or `BSE` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Order Number Length should be at most 25 for NSE/BSE MF Partner"}` |
| Mutual fund record already exists for generated UPI request id | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |

### Downstream and Internal Failures

| Scenario | Decrypted response body |
| --- | --- |
| Downstream UPI switch/NPCI returns no transaction object | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"NPCI service is not reachable at the moment (NA)"}` |
| Downstream response has `error=true` and `timeout=true` | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"NPCI service is not reachable at the moment (NA)"}` |
| Downstream response has `error=true` but no error code | `{"status":"FAILURE","responseCode":"BAD_RESPONSE_FROM_NPCI","responseMessage":"Invalid response from NPCI"}` or equivalent bad-response body. |
| Missing required gateway response code/message in the returned transaction | Usually an internal error body, because Newton cannot format the success response. |
| Unexpected database, cache, crypto, default split settlement config, or server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

## Retry and Client Handling

- Treat a decrypted body with `status = "SUCCESS"` as successful creation of the collect request, not necessarily final customer payment success.
- Use `gatewayResponseCode`, `gatewayResponseStatus`, transaction status APIs, and callbacks to determine final payment state.
- Do not retry validation, auth, platform, split settlement, TPV, or duplicate failures without changing the request/configuration.
- For transient downstream failures such as service unavailable/timeouts, retry with the same `merchantRequestId` only if you are confirming whether Newton already accepted the first request. A `DUPLICATE_REQUEST` on retry should be handled as "first request likely reached Newton"; reconcile using transaction status or support lookup.
- If no `gatewayTransactionId` was received and status is unknown, contact Newton support with `merchantRequestId`, `x-request-id`, merchant id/channel id, and timestamp.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:355)
- Route handler and auth/signature call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2241)
- Request and response types: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:42)
- Encrypted/signed envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:12)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:826)
- Product/business logic: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:78)
- Downstream collect payload construction: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:304)
- Generic request and success response transformer: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:1036)
- Response version gating: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:511)
- Common request validations: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:292)
- TPV and platform validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:132)
- Split settlement validation: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4539)
- Mutual fund validation and creation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2394)
