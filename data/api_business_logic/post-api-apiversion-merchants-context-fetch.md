# Fetch Context API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/context/fetch`

## Overview

Fetch Context is a server-to-server API used to ask the UPI/NPCI context service whether a customer's linked accounts can be used for a contextual payment and what contextual benefits or constraints apply.

The merchant calls this API after the customer is registered with Newton and has active linked accounts. Newton verifies the S2S envelope, merchant configuration, and merchant-customer context; loads the customer's active accounts and registered device; sends an NPCI `ReqGetContext` request with account indices, payee, amount, and context details; and returns the `RespGetContext` result as merchant-facing JSON.

Use this API before building a UPI payment, intent, or QR journey that needs account-specific contextual data, such as account acceptance, convenience fee, surcharge, EMI offer, discount offer, lounge offer, or payee-account metadata.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Fetch Context helps merchants:

- Check which of the customer's linked accounts are accepted for a contextual payment.
- Fetch per-account contextual offer information before the customer authorizes payment.
- Retrieve EMI, offer, lounge, convenience-fee, surcharge, and payee-address context returned by the downstream UPI path.
- Send payee merchant metadata when the contextual payment depends on merchant identity fields.
- Send customer consent attributes when required by the onboarded context use case.
- Reuse the resulting `transactionReference`, `gatewayTransactionId`, and account context while constructing the next payment step.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton. This scopes account and device lookup.
- `upiRequestId`: Merchant-supplied UPI transaction id for the `ReqGetContext` call. Newton uses this as the downstream transaction id and returns it as `payload.gatewayTransactionId`.
- `transactionReference`: Merchant/order reference sent as the UPI transaction reference. Newton returns the NPCI response reference when present, otherwise this request value.
- `bankAccountUniqueId`: Merchant-facing linked-account identifier returned in successful S2S responses for each account context.

## Integration Flow

1. Merchant ensures the customer is registered with Newton, device-bound, and has active linked accounts.
2. Merchant selects the contextual-payment use case and sends the configured `contextDetails.ctxtCode`, optional `prodCode`, and optional `attribute`.
3. Merchant calls this endpoint using the standard Newton S2S envelope and signature process.
4. Newton decrypts/verifies the request and loads merchant, merchant-customer, and customer context from `merchantCustomerId`.
5. Newton validates the business payload.
6. Newton fetches the customer's active accounts. For normal S2S merchants, only accounts mapped to the merchant customer are used. For P2M-SDK parent merchants, all active customer accounts are used.
7. Newton builds account indices starting at `"01"` and sends them to NPCI. The maximum indexed account count is controlled by merchant configuration `accountsCountForFetchContext`; if absent, Newton uses `50`.
8. Newton calls NPCI `ReqGetContext` using `upiRequestId`.
9. Newton maps `RespGetContext` into the S2S response. A Newton top-level success can still contain `payload.gatewayResponseStatus = "FAILURE"` when NPCI returned a contextual lookup failure.

## Endpoint

```http
POST /api/{apiVersion}/merchants/context/fetch
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. This endpoint does not currently have response-version branching. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within Newton's configured clock-skew window. |
| `x-merchant-signature` | Required for plaintext/unsigned envelope integrations. Signature input includes merchant ids, timestamp, and raw body. |
| `x-request-id` | Optional. If omitted, Newton generates one and returns it in the response headers. |
| `x-session-id` | Optional. If omitted, Newton uses `x-request-id` as the session id. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Depending on merchant configuration, the request body can be plaintext, JWS, or JWE. Signed/encrypted calls must include a valid payload `iat`; plaintext signed calls must include the configured merchant signature headers.

Newton responses follow the merchant's configured response strategy. A plaintext response is returned with `X-Response-Signature`; JWS or JWS-and-JWE merchants receive signed or signed-and-encrypted response envelopes.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the value shared during onboarding. |

## Handler Path

The direct handler path is:

1. `Core.ServerToServerAPIs` accepts `EncRequest FetchContextS2SRequest`.
2. `Core.fetchContextS2S` decrypts/parses the envelope with `getReqBody`.
3. `merchantSignatureVerificationV2` validates `iat`, merchant headers, signature/envelope mode, merchant API access, IP allowlist if configured, and loads merchant/customer context.
4. `fetchContextS2STransformerRoute` validates the decrypted request and converts it to the core request.
5. `fetchContextCoreRoute` applies additional fetch-context validation, loads accounts/device/customer data, builds the NPCI payload, and calls `ReqGetContext`.
6. `mkFetchContextS2SResponse` wraps the core response with merchant ids and echoes `udfParameters` when supplied.

## Request

### Required Minimum

For new integrations, send at least:

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "FCTX123456789",
  "transactionReference": "ORDER12345",
  "amount": "1000.00",
  "payeeVpa": "merchant@upi",
  "payeeMcc": "5411",
  "contextDetails": {
    "ctxtCode": "C01"
  },
  "iat": "1735689600000"
}
```

Send `iat` for signed or encrypted S2S calls. Plaintext development payloads may not require it, depending on environment and onboarding configuration.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `upiRequestId` | string | Yes | No default. | UPI transaction id for this context fetch. Must be 1 to 35 alphanumeric characters. Returned as `payload.gatewayTransactionId`. |
| `transactionReference` | string | Yes | No default. | Merchant/order reference sent as NPCI transaction `refId`. Must be 1 to 35 alphanumeric characters. |
| `amount` | string | Yes | No default. | Context amount in two-decimal format, for example `1000.00`. Must be greater than `0.00`. |
| `payeeVpa` | string | Yes | No default. | Payee VPA for the contextual payment. Must be 3 to 255 characters and match Newton's VPA format. |
| `payeeMcc` | string | Yes | No default. | Payee MCC. Must be exactly four digits. `0000` is treated as a person payee; any other valid MCC is treated as an entity payee. |
| `contextDetails` | object | Yes | No default. | NPCI context request details. The correct `ctxtCode`, `prodCode`, and `attribute` values are provided for the merchant's onboarded use case. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Plaintext development payloads may not require it. | Issued-at timestamp used by signature/envelope validation. Send a 13-digit Unix timestamp in milliseconds within the allowed clock-skew window. |
| `contextOrigin` | string | No | Defaults by behavior to `PAYER` in the response and to the NPCI requester side equivalent of payee/acquirer when omitted in the outbound request. | Who originated the requested context. Allowed values: `PAYER`, `PAYEE`. When set to `PAYER`, Newton sends NPCI subtype `ISSUER`; otherwise it sends `ACQUIRER`. |
| `currency` | string | No | Defaults to `INR` in the NPCI request and response. | Currency for `amount`. Validation only requires a non-empty value when supplied. Use `INR` unless Newton has explicitly enabled another currency. |
| `geocode` | string | No | Omitted from the device payload when absent. | Customer/device geocode in `latitude,longitude` format. Latitude must be within `-90..90`; longitude within `-180..180`. |
| `initiatedBy` | string | No | Defaults by behavior to user-initiated in the NPCI request. | Initiator used to derive NPCI context type. Allowed values: `USER`, `MERCHANT`. `MERCHANT` maps to `MERCHANTINIT`; all other omitted/allowed values map to `USERINIT`. |
| `initiationMode` | string | No | Defaults to `00`. | Two-character alphanumeric UPI initiation mode. |
| `payeeName` | string | No | If omitted, Newton sends `payeeVpa` as the payee display name in the NPCI request. On gateway failure, the response omits `payeeName` unless it was supplied. | Payee display name. Must be non-empty when supplied. |
| `payerMcc` | string | No | Defaults to `0000`. | Payer MCC. Must be exactly four digits when supplied. `0000` is treated as a person payer. |
| `payerName` | string | No | Defaults to the name on the first indexed active account. | Payer display name sent to NPCI. Must be non-empty when supplied. |
| `purposeCode` | string | No | Defaults to `00`. | Two-character uppercase alphanumeric UPI purpose code. |
| `refUrl` | string | No | Defaults to Newton's configured NPCI reference URL when omitted. If supplied, `refCategory` is required. | Merchant reference URL sent as NPCI `refUrl`. Must be non-empty when supplied. |
| `refCategory` | string | Conditional | Defaults to `00` when `refUrl` is omitted. Required when `refUrl` is supplied. | Merchant reference category sent as NPCI `refCategory`. Must be non-empty when supplied. |
| `remarks` | string | No | Defaults to `ReqGetContext` in the NPCI request. | Note/remarks for the context request. Must be 1 to 255 characters and match the allowed remarks format. |
| `consentDetails` | array of objects | No | Omitted when absent or when an empty array is supplied. | Optional consent attributes sent under the NPCI payer. Use only when required for the onboarded context use case. |
| `merchantDetails` | object | No | Omitted when absent. | Optional payee merchant information sent to NPCI. Use for aggregator/sub-merchant or merchant-identity contextual flows when Newton has enabled it. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in normal success responses. The value must parse as a JSON object string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `currency`: defaults to `INR`.
- `remarks`: defaults to `ReqGetContext` in the NPCI request.
- `refUrl`: defaults to Newton's configured NPCI reference URL when omitted.
- `refCategory`: defaults to `00` when `refUrl` is omitted. If `refUrl` is supplied, `refCategory` must also be supplied.
- `purposeCode`: defaults to `00`.
- `initiationMode`: defaults to `00`.
- `payerMcc`: defaults to `0000`.
- `payerName`: defaults to the name on the first active indexed account.
- `payeeName`: defaults to `payeeVpa` in the NPCI request.
- `contextOrigin`: response defaults to `PAYER` when omitted. The outbound NPCI subtype uses `ISSUER` only for `PAYER`; omitted or `PAYEE` is sent as `ACQUIRER`.
- `initiatedBy`: outbound NPCI context type defaults to `USERINIT`; only `MERCHANT` changes it to `MERCHANTINIT`.
- `consentDetails`: `null`, omitted, or `[]` means no consent list is sent.
- `merchantDetails`: omitted means no merchant-info block is sent to NPCI.
- `bankAccountsContext`: present only when NPCI returns `SUCCESS`. It is omitted for gateway failures and for errors before a valid `RespGetContext`.
- `udfParameters`: echoed only in normal Newton success responses and only when supplied.

### Nested Request Objects

Nested objects do not have field-level defaults unless called out below.

#### `contextDetails`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `ctxtCode` | string | Yes | NPCI context code. Allowed values by type: `C01`, `C02`, `C03`, `C04`, `C05`, `C06`, `C08`. Use the code configured for the merchant's contextual-payment use case. |
| `prodCode` | string | No | Product/context code. Must be 1 to 99 characters when supplied. |
| `attribute` | string | No | Additional context attribute. Must be 1 to 99 characters when supplied. |

#### `consentDetails[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Consent attribute name. Must be non-empty. |
| `value` | string | Yes | Consent attribute value. Must be non-empty. |

#### `merchantDetails`

Use this object only when the contextual-payment use case requires merchant information to be sent to NPCI.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `aggregator` | string | No | Aggregator name/id. Must be alphanumeric with spaces allowed and 1 to 99 characters when supplied. |
| `brandName` | string | No | Merchant brand name. Must be alphanumeric with spaces allowed and 1 to 99 characters when supplied. |
| `franchiseName` | string | No | Franchise/store-chain name. Must be alphanumeric with spaces allowed and 1 to 99 characters when supplied. |
| `merchantGenre` | string | No | Commerce channel. Allowed values: `OFFLINE`, `ONLINE`. |
| `legalName` | string | No | Legal merchant name. Must be alphanumeric with spaces allowed and 1 to 99 characters when supplied. |
| `mid` | string | No | Merchant MID. Must be 1 to 20 alphanumeric characters when supplied. |
| `onBoardingType` | string | No | Onboarding source/type. Allowed values: `BANK`, `AGGREGATOR`, `NETWORK`, `TPAP`. |
| `ownershipType` | string | No | Ownership category. Allowed values: `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. |
| `sid` | string | No | Merchant SID. Must be 1 to 20 alphanumeric characters when supplied. |
| `subCode` | string | No | Sub-code/MCC. Must be exactly four digits when supplied. |
| `tid` | string | No | Merchant TID. Must be 1 to 20 alphanumeric characters when supplied. |
| `merchantType` | string | No | Merchant size/type. Allowed values: `SMALL`, `LARGE`. |
| `verified` | string | No | Boolean string. Use `true` or `false`. Newton maps this to NPCI merchant verification `T`/`F`. |

### Validation Notes

- `amount` must match `^[0-9]+\.[0-9][0-9]$` and be greater than `0.00`.
- `merchantCustomerId`, `upiRequestId`, and `transactionReference` must satisfy Newton's identifier validators.
- `payeeVpa` must match Newton's VPA format.
- `payeeMcc`, `payerMcc`, and `merchantDetails.subCode` must be exactly four digits.
- `contextOrigin`, `initiatedBy`, and merchant enum fields must match their allowed values exactly.
- `purposeCode` must be exactly two uppercase alphanumeric characters.
- `initiationMode` must be exactly two alphanumeric characters.
- `remarks`, `payeeName`, `payerName`, `refUrl`, `refCategory`, and consent fields must be non-empty when supplied.
- `refCategory` is required whenever `refUrl` is supplied.
- `contextDetails.prodCode` and `contextDetails.attribute` must be 1 to 99 characters when supplied.
- `udfParameters` must be a JSON object encoded as a string and pass the special-character restriction.

## Request Examples

### Standard Context Fetch

Use this when the merchant needs account-level contextual data before building the next UPI payment step.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "FCTX123456789",
  "transactionReference": "ORDER12345",
  "amount": "1000.00",
  "payeeVpa": "merchant@upi",
  "payeeMcc": "5411",
  "contextDetails": {
    "ctxtCode": "C01",
    "prodCode": "PROD123",
    "attribute": "EMI"
  },
  "remarks": "Context fetch",
  "iat": "1735689600000",
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

### Merchant-Initiated Context With Merchant Details

Use this variant only when Newton has enabled a merchant/sub-merchant contextual flow for your integration.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "FCTX123456790",
  "transactionReference": "ORDER12346",
  "amount": "2500.00",
  "currency": "INR",
  "payeeVpa": "submerchant@upi",
  "payeeName": "Newton Store",
  "payeeMcc": "5411",
  "contextOrigin": "PAYEE",
  "initiatedBy": "MERCHANT",
  "initiationMode": "00",
  "purposeCode": "00",
  "refUrl": "https://merchant.example/orders/ORDER12346",
  "refCategory": "00",
  "geocode": "12.9716,77.5946",
  "contextDetails": {
    "ctxtCode": "C02",
    "prodCode": "PROD456",
    "attribute": "OFFER"
  },
  "merchantDetails": {
    "aggregator": "Acme Aggregator",
    "brandName": "Newton Store",
    "franchiseName": "Newton Retail",
    "merchantGenre": "ONLINE",
    "legalName": "Newton Store Private",
    "mid": "MID12345",
    "sid": "SID12345",
    "tid": "TID12345",
    "subCode": "5411",
    "onBoardingType": "AGGREGATOR",
    "ownershipType": "PRIVATE",
    "merchantType": "LARGE",
    "verified": "true"
  },
  "consentDetails": [
    {
      "name": "customerConsent",
      "value": "Y"
    }
  ],
  "remarks": "Offer context",
  "iat": "1735689600000"
}
```

## Response

### Interpreting Status

Fetch Context has two status layers:

- Top-level `status`, `responseCode`, and `responseMessage` describe whether Newton accepted, processed, and wrapped the API call.
- `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` describe the NPCI/context lookup result.

When NPCI returns a normal `RespGetContext` with result `FAILURE`, Newton still returns top-level `SUCCESS` because the API call completed. Clients must inspect `payload.gatewayResponseStatus` before showing contextual offers or allowing the customer to proceed with account-specific context.

### Top-Level Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton API status. Normal processed responses use `SUCCESS`. |
| `responseCode` | string | Newton response code. Normal processed responses use `SUCCESS`. |
| `responseMessage` | string | Newton response message. Normal processed responses use `SUCCESS`. |
| `payload` | object | Fetch Context business payload. Present for normal processed responses. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when absent. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant context. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant context. |
| `merchantCustomerId` | string | Echoes request `merchantCustomerId`. |
| `gatewayResponseStatus` | string | NPCI/context status. `SUCCESS` means account context is available; `FAILURE` means the downstream context lookup failed. |
| `gatewayResponseCode` | string | NPCI response or error code. Defaults to `00` on success when NPCI did not send a code; defaults to `NA` for gateway failure without a code. |
| `gatewayResponseMessage` | string | Newton's mapped message for `gatewayResponseCode`, or `NA` when no mapping is available. |
| `gatewayTransactionId` | string | NPCI transaction id, normally the request `upiRequestId`. |
| `gatewayReferenceId` | string | NPCI customer reference number (`custRef`) from `RespGetContext`. |
| `transactionReference` | string | NPCI response `refId` when present; otherwise request `transactionReference`. |
| `isVpaValid` | boolean | `true` when gateway context succeeds; `false` when gateway context fails. |
| `isMerchant` | boolean | Present only on gateway success. `false` when `payeeMcc` is `0000`; otherwise `true`. |
| `payeeName` | string | Payee name from NPCI on success. On gateway failure, this is the request `payeeName` if supplied; otherwise omitted. |
| `payeeVpa` | string | Echoes request `payeeVpa`. |
| `payeeAccType` | string | Payee account type from NPCI. Omitted on gateway failure or when NPCI omits it. |
| `payeeMcc` | string | Echoes request `payeeMcc`. |
| `payeeBankCode` | string | Payee bank/IIN from NPCI. Omitted on gateway failure or when NPCI omits it. |
| `amount` | string | Echoes request `amount`. |
| `currency` | string | Request `currency`, or `INR` when omitted. |
| `contextOrigin` | string | Request `contextOrigin`, or `PAYER` when omitted. |
| `initiatedBy` | string | Current response transformer value for the initiation/context origin. Defaults to `USER` when no contextual origin value is available. Do not use this field alone to infer the NPCI `contextType`; use the submitted request and gateway status. |
| `transactionTimestamp` | string | NPCI transaction timestamp from `RespGetContext`. |
| `expiryTimestamp` | string | Expiry timestamp from NPCI when supplied. Omitted when absent. |
| `remarks` | string | NPCI response note, typically request `remarks` or the default `ReqGetContext`. Omitted when NPCI omits it. |
| `refUrl` | string | NPCI response reference URL. Omitted when absent. |
| `refCategory` | string | NPCI response reference category. Omitted when absent. |
| `purposeCode` | string | Request `purposeCode`, or `00` when omitted. |
| `initiationMode` | string | Request `initiationMode`, or `00` when omitted. |
| `featureSupported` | array of strings | Feature tags returned by NPCI. Omitted when none are returned. |
| `merchantDetails` | object | Filtered NPCI payee merchant fields. Only `Identifier`, `Name`, and `Ownership` are retained. Omitted when absent or not an object. |
| `bankAccountsContext` | array of objects | Per-account contextual response. Present only on gateway success. Omitted on gateway failure. |

### `bankAccountsContext[]`

For S2S responses, Newton returns `bankAccountUniqueId` for each active indexed account. `accountReferenceId` is used by the SDK variant and is normally omitted for this S2S endpoint.

| Field | Type | Description |
| --- | --- | --- |
| `bankAccountUniqueId` | string | Merchant-facing account identifier/account hash. Present for S2S successful account context. |
| `accountReferenceId` | string | SDK account reference id. Normally omitted for S2S responses. |
| `context` | object | Context result for this account. |

### `bankAccountsContext[].context`

| Field | Type | Description |
| --- | --- | --- |
| `accepted` | string | NPCI account-acceptance flag for this context. Interpret using the values shared for the onboarded context use case, commonly `Y`/`N`. |
| `conFee` | string | Convenience fee amount when returned. |
| `surcharge` | string | Surcharge amount when returned. |
| `emiOffer` | object | EMI offer context for this account. Omitted when no EMI context applies. |
| `offer` | object | Discount/offer context for this account. Omitted when no offer context applies. |
| `loungeOffer` | object | Lounge benefit context for this account. Omitted when no lounge context applies. |
| `payeeAddress` | string | Payee address for this account context when returned. |

NPCI can return context blocks for a specific account index or for common index `"00"`. Newton applies the account-specific block first and falls back to the `"00"` block for `emiOffer`, `offer`, and `loungeOffer` when no account-specific block is present.

### `emiOffer`

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | EMI offer name. |
| `tnC` | string | Terms and conditions text or URL from NPCI. |
| `prodName` | string | Product name. |
| `prodCode` | string | Product code. |
| `amount` | string | Amount associated with the EMI offer. |
| `emiDetails` | array of objects | Available EMI tenures/options. |
| `note` | string | Optional note from NPCI. |
| `payeeAddress` | string | Optional payee address associated with this EMI context. |

### `emiOffer.emiDetails[]`

| Field | Type | Description |
| --- | --- | --- |
| `seqNum` | string | EMI option sequence number. |
| `offerId` | string | Offer id to use if the customer selects this EMI option in a later payment step. |
| `tenure` | string | EMI tenure. |
| `intRatePct` | string | Interest rate percentage. |
| `intRateAmt` | string | Interest amount. |
| `procFee` | string | Processing fee. |
| `otherFee` | string | Optional other fee. |
| `totalAmt` | string | Total amount. |
| `discAmt` | string | Optional discount amount. |
| `emiAmt` | string | EMI installment amount. |

### `offer`

| Field | Type | Description |
| --- | --- | --- |
| `offerId` | string | Offer id to use in later payment steps when applicable. |
| `name` | string | Offer name. |
| `category` | string | Offer category. |
| `description` | string | Optional offer description. |
| `updatedAmt` | string | Updated amount after applying offer context. |
| `note` | string | Optional offer note. |
| `payeeAddress` | string | Optional payee address associated with this offer. |

### `loungeOffer`

| Field | Type | Description |
| --- | --- | --- |
| `offerId` | string | Lounge offer id. |
| `freePasses` | string | Number of free lounge passes. |
| `amount` | string | Amount associated with the lounge offer. |
| `note` | string | Optional lounge note. |
| `payeeAddress` | string | Optional payee address associated with this lounge offer. |

## Response Examples

### Gateway Success With Account Context

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your transaction is successful",
    "gatewayTransactionId": "FCTX123456789",
    "gatewayReferenceId": "123456789012",
    "transactionReference": "ORDER12345",
    "isVpaValid": true,
    "isMerchant": true,
    "payeeName": "Newton Store",
    "payeeVpa": "merchant@upi",
    "payeeAccType": "CURRENT",
    "payeeMcc": "5411",
    "payeeBankCode": "123456",
    "amount": "1000.00",
    "currency": "INR",
    "contextOrigin": "PAYER",
    "initiatedBy": "USER",
    "transactionTimestamp": "2026-07-02T10:15:30+05:30",
    "remarks": "Context fetch",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "refCategory": "00",
    "purposeCode": "00",
    "initiationMode": "00",
    "featureSupported": [
      "EMI",
      "OFFER"
    ],
    "merchantDetails": {
      "Identifier": {
        "mid": "MID12345",
        "sid": "SID12345",
        "tid": "TID12345"
      },
      "Name": {
        "brand": "Newton Store",
        "legal": "Newton Store Private"
      },
      "Ownership": {
        "type": "PRIVATE"
      }
    },
    "bankAccountsContext": [
      {
        "bankAccountUniqueId": "ACC_HASH_1",
        "context": {
          "accepted": "Y",
          "conFee": "5.00",
          "surcharge": "0.00",
          "payeeAddress": "merchant@upi",
          "offer": {
            "offerId": "OFFER123",
            "name": "Instant Discount",
            "category": "DISCOUNT",
            "description": "Instant discount on eligible account",
            "updatedAmt": "950.00",
            "note": "Offer applied",
            "payeeAddress": "merchant@upi"
          },
          "emiOffer": {
            "name": "EMI",
            "tnC": "https://merchant.example/emi-terms",
            "prodName": "Mobile Phone",
            "prodCode": "PROD123",
            "amount": "1000.00",
            "emiDetails": [
              {
                "seqNum": "1",
                "offerId": "EMI123",
                "tenure": "3",
                "intRatePct": "12.00",
                "intRateAmt": "20.00",
                "procFee": "10.00",
                "totalAmt": "1030.00",
                "discAmt": "50.00",
                "emiAmt": "343.33"
              }
            ]
          }
        }
      },
      {
        "bankAccountUniqueId": "ACC_HASH_2",
        "context": {
          "accepted": "N",
          "conFee": "0.00",
          "surcharge": "0.00"
        }
      }
    ]
  },
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

Client handling: proceed only with accounts whose `context.accepted` value is acceptable for the onboarded use case. If an `offerId` or EMI option is selected later, preserve the relevant context identifiers with the merchant order.

### Gateway Failure Returned In A Newton Success Body

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "VY",
    "gatewayResponseMessage": "PAYEE VPA IS INCORRECT (REMITTER)",
    "gatewayTransactionId": "FCTX123456791",
    "gatewayReferenceId": "123456789013",
    "transactionReference": "ORDER12347",
    "isVpaValid": false,
    "payeeVpa": "badpayee@upi",
    "payeeMcc": "5411",
    "amount": "1000.00",
    "currency": "INR",
    "contextOrigin": "PAYER",
    "initiatedBy": "USER",
    "transactionTimestamp": "2026-07-02T10:16:30+05:30",
    "remarks": "Context fetch",
    "refCategory": "00",
    "purposeCode": "00",
    "initiationMode": "00"
  }
}
```

Client handling: treat this as a failed contextual lookup even though the top-level `status` is `SUCCESS`. Do not show contextual offers or account acceptance based on this response.

## Failure Responses

Failure responses use the same configured S2S response transport as success responses when the request reaches response wrapping. After decryption, failures include `status: "FAILURE"` plus a concrete `responseCode` and diagnostic `responseMessage`; the examples below show common response bodies.

`payload` is usually omitted when empty. HTTP status can vary by layer: request validator failures are often returned with HTTP 200, the `refUrl`/`refCategory` rule uses HTTP 400, authentication/decryption failures use HTTP 401, and downstream/unexpected failures can use HTTP 500. Clients should inspect the decrypted `status`, `responseCode`, and `responseMessage` whenever a response body is available.

### Validation Failure

Occurs when the decrypted business payload fails Newton validation.

Invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Invalid `contextOrigin` enum:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed \\\"CUSTOMER\\\"\""
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

Client handling: fix the payload and retry only after regenerating the S2S signature/envelope.

### Conditional Validation Failure

Returned when `refUrl` is supplied without `refCategory`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "refCategory must be present if refURL is present"
}
```

Client handling: either omit both fields and use Newton defaults, or send both `refUrl` and `refCategory`.

### Authentication, Signature, or Encryption Failure

Occurs when merchant headers are missing, the merchant id/channel id is unknown, plaintext signature verification fails, source IP is not whitelisted, JWS verification fails, JWE decryption fails, or the encrypted payload cannot be trusted.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Malformed encrypted payloads can surface as invalid data when the decrypted payload cannot be parsed:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: not enough input"
}
```

Client handling: do not retry the same envelope. Regenerate `iat`, timestamp, signature, and encrypted payload after credentials, key id, body canonicalization, or IP allowlist issues are fixed.

### Timestamp or Request Freshness Failure

Signed or encrypted payloads require `iat`; all production S2S requests require a valid `x-timestamp`.

Missing `iat` in a signed/encrypted payload:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Expired timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Client handling: regenerate the request envelope with current timestamps. Do not replay old signed or encrypted payloads.

### Merchant Configuration or API Access Failure

Returned when the merchant is valid but the API is blocked, not present in the merchant's allowed API list, or blocked through merchant/sub-merchant configuration.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: treat this as an integration/configuration issue. Do not ask the customer to retry until the merchant API configuration is corrected.

### Merchant Customer, Customer, Device, or Account Lookup Failure

Fetch Context requires the verification layer to load a merchant customer and customer, and product logic to find a registered device and active accounts.

Unknown merchant customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

No active linked accounts for the customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No accounts found for the customer"
}
```

Missing active device/customer binding can also be returned by shared lookup helpers, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Client handling: refresh or re-run the customer onboarding, device binding, and account-linking flow before retrying Fetch Context.

### Gateway Business Failure

When NPCI returns a valid `RespGetContext` with result `FAILURE`, Newton returns top-level `SUCCESS` with a gateway failure payload rather than a top-level failure body.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "VY",
    "gatewayResponseMessage": "PAYEE VPA IS INCORRECT (REMITTER)",
    "gatewayTransactionId": "FCTX123456791",
    "gatewayReferenceId": "123456789013",
    "transactionReference": "ORDER12347",
    "isVpaValid": false,
    "payeeVpa": "badpayee@upi",
    "payeeMcc": "5411",
    "amount": "1000.00",
    "currency": "INR",
    "contextOrigin": "PAYER",
    "initiatedBy": "USER",
    "transactionTimestamp": "2026-07-02T10:16:30+05:30",
    "purposeCode": "00",
    "initiationMode": "00"
  }
}
```

Client handling: read `payload.gatewayResponseStatus`; do not treat top-level `SUCCESS` alone as contextual success.

### Downstream NPCI Immediate Failure or Timeout

Returned when Newton cannot complete the NPCI call or times out waiting for the async response.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "NPCI service is not reachable at the moment (U09)"
}
```

If NPCI returns a negative ACK with structured error messages, Newton can return a custom code and message from that ACK:

```json
{
  "status": "FAILURE",
  "responseCode": "U90",
  "responseMessage": "REMITTER BANK DEEMED HIGH RESPONSE TIME CHECK DECLINE"
}
```

Client handling: retry with the same business intent only after a short backoff and only if the customer journey can tolerate a fresh context fetch. Use a fresh S2S envelope and consider using a fresh `upiRequestId` if the previous request might still complete asynchronously.

### Unexpected Downstream Shape or Internal Error

Returned when NPCI returns an unexpected `RespGetContext` shape, an unknown result value, a decode failure, or another internal error.

Unexpected NPCI result:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_NPCI_RESULT",
  "responseMessage": "Unexpected result from NPCI in RespGetContext"
}
```

Generic unexpected error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry only with backoff. If repeated for the same request/customer, capture `x-request-id`, `upiRequestId`, and `merchantCustomerId` for Newton support.

## Retry, Idempotency, and Client Handling

This API does not accept a merchant idempotency key such as `merchantRequestId`. `upiRequestId` is the downstream transaction id for the context request, not a general idempotent order key.

- On top-level `SUCCESS` with `payload.gatewayResponseStatus = "SUCCESS"`, use `bankAccountsContext` to decide which account/context options to show.
- On top-level `SUCCESS` with `payload.gatewayResponseStatus = "FAILURE"`, do not show contextual offers or account-specific acceptance. Show a user-safe failure and let the customer retry or choose a non-contextual path if supported.
- If the HTTP call times out or the response cannot be decrypted, the previous NPCI request may still complete asynchronously. Prefer issuing a fresh Fetch Context call with a new `upiRequestId` rather than replaying an old encrypted payload.
- Do not retry validation failures without correcting the request.
- Do not retry `UNAUTHORIZED`, `API NOT ENABLED`, or `REQUEST_EXPIRED` until credentials, headers, IP allowlist, merchant API configuration, or timestamps are fixed.
- Do not retry lookup failures until the customer profile, device binding, and active linked accounts exist.
- Retry `SERVICE_UNAVAILABLE_NPCI_*` and transient `INTERNAL_SERVER_ERROR` with short backoff. Preserve `x-request-id`, `x-session-id`, and `upiRequestId` in logs for reconciliation and support.

## Source References

- Route type: [Core.ServerToServerAPIs](../../src/Newton/App/Routes/Core.hs:744)
- Endpoint handler: [Core.fetchContextS2S](../../src/Newton/App/Routes/Core.hs:5157)
- S2S request/response types and validator: [FetchContextS2SRequest and FetchContextS2SResponse](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3870)
- S2S transformer route: [fetchContextS2STransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:819)
- Request/response transformers: [mkFetchContextCoreRequest and mkFetchContextS2SResponse](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1534)
- Core product route and NPCI handling: [fetchContextCoreRoute](../../src/Newton/Product/Merchant/Context/FetchContext.hs:28)
- Account/device lookup and NPCI request construction: [Context.Helper getDbRecordsForFetchContextCore/getReqGetContextPayload](../../src/Newton/Product/Merchant/Context/Helper.hs:45)
- Success/failure response mapping: [Context.Helper handleSuccessRespGetContext/handleFailureRespGetContext](../../src/Newton/Product/Merchant/Context/Helper.hs:176)
- Account-context mapping and common `"00"` fallback: [Context.Helper getBankAccountsPayload](../../src/Newton/Product/Merchant/Context/Helper.hs:263)
- Core request, nested request, response, and nested response types: [Newton.Product.Merchant.Context.Types](../../src/Newton/Product/Merchant/Context/Types.hs:15)
- Additional `refUrl`/`refCategory` validation: [validateFetchContextCoreRoute](../../src/Newton/Utils/ApiValidation.hs:256)
- Request validation wrapper: [Utils.validateRequestBody](../../src/Newton/Utils/Utils.hs:251)
- Field validators: [Validation.Common](../../src/Newton/Validation/Common.hs:125)
- S2S envelope type: [EncRequest and EncResponse](../../src/Newton/Types/API/RequestBody.hs:48)
- Request-body decryption/verification entry point: [Utils.Routes.getReqBody](../../src/Newton/Utils/Routes.hs:40)
- Merchant payload verification: [MerchantPayloadVerification.payloadVerification](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- S2S signature, merchant-config, customer-context, timestamp, and IP checks: [MerchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response signing/encryption wrapper: [RoutesHelper.flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Error helpers/constants: [Newton.Constants.APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:7)
- NPCI error-code mapping: [Newton.Constants.ErrorCodes](../../src/Newton/Constants/ErrorCodes.hs:19)
