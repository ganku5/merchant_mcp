# Create Voucher API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/voucher/create`

## Overview

Create Voucher is a merchant server-to-server API used to create or revoke an e-RUPI / prepaid-voucher mandate through Newton.

For `requestType: "CREATE"`, Newton validates the voucher request, creates a payer-side prepaid-voucher mandate, blocks voucher funds through the mandate flow, and returns the voucher id and mandate identifiers needed for redemption and reconciliation. For `requestType: "REVOKE"`, Newton looks up the original voucher mandate and sends a payer-side revoke request.

The response can be top-level `SUCCESS` while the underlying mandate operation is still `PENDING` or has a gateway-level failure. Always read `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` for the business result.

## Business Use Case

Create Voucher helps merchants:

- Issue prepaid e-RUPI vouchers with a fixed or maximum redeemable amount.
- Bind a voucher to an NPCI e-RUPI purpose code and validity window.
- Define whether the voucher can be revoked by the payer side.
- Create one-time or recurring voucher mandates where supported by the downstream mandate flow.
- Include optional sub-merchant/store details for voucher issuance and redemption context.
- Revoke an existing voucher mandate before redemption or expiry, subject to mandate revocability and downstream state.
- Reconcile voucher creation and revoke attempts using merchant request ids, UPI request ids, UMN, and gateway response fields.

Do not use this API for normal UPI mandate creation, mandate execution, mandate status polling, or voucher redemption/debit confirmation. Those are separate flows.

## Integration Flow

1. Merchant decides whether the call is a voucher `CREATE` or `REVOKE`.
2. For create, merchant generates a unique `upiRequestId`, `merchantRequestId`, voucher VPA, amount, purpose code, validity dates, and recurrence details.
3. Merchant signs or encrypts the request using the Newton S2S envelope and sends required merchant headers.
4. Newton unwraps the request, resolves the merchant, verifies API access, validates timestamp/signature/encryption, validates the decrypted business payload, and applies voucher-specific business rules.
5. For create, Newton checks whether a mandate already exists for the `upiRequestId`.
6. If no mandate exists, Newton creates a prepaid-voucher mandate through the mandate route and returns the created mandate details.
7. If a mandate already exists for the same `upiRequestId`, Newton returns the existing mandate details instead of creating a second voucher.
8. For revoke, Newton looks up the original mandate by `orgMandateId` and sends a revoke request using the new `upiRequestId`.
9. Merchant stores `payload.orgMandateId`, `payload.gatewayMandateId`, `payload.uuid`, `payload.umn`, `payload.gatewayResponseStatus`, and request ids for reconciliation.

Important identifiers:

| Identifier | Meaning |
| --- | --- |
| `upiRequestId` | Merchant-generated UPI request id for this API attempt. For create, it becomes the voucher mandate id and `payload.gatewayMandateId`. For revoke, it identifies the revoke attempt. |
| `merchantRequestId` | Merchant-side order/reference id. Required for create and recommended for revoke. Echoed from mandate history when available. |
| `orgMandateId` | Original voucher mandate id. Required for revoke. In responses it is the mandate's original `upiRequestId`. |
| `voucherVpa` | Voucher VPA assigned for the e-RUPI voucher. Stored as the mandate payee VPA and returned as `payload.uuid`. |
| `umn` | UPI mandate number. May be generated downstream or supplied for compatible flows. Returned when present. |

## Handler Path

The route is mounted under `/api/{apiVersion}` in the main `ServerToServerAPIs` route group.

The request path is:

1. `getReqBody` unwraps `EncRequest VoucherInitiationS2SRequest` through S2S merchant payload verification.
2. `merchantPayloadVerificationS2S` resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`, resolves optional sub-merchant headers, and verifies the JWS/JWE/plain payload shape.
3. `merchantSignatureVerificationV2` validates `iat` for signed/encrypted bodies, merchant headers, blocked/allowed API configuration, request timestamp, signature for unsigned payloads, and optional IP allowlisting.
4. `voucherInitiationS2SRoute` validates the decrypted request and loads the merchant and default merchant account.
5. Product logic branches on `requestType`:
   - `CREATE`: return existing mandate if `upiRequestId` already exists; otherwise validate voucher business rules and create a prepaid-voucher mandate.
   - `REVOKE`: find the original mandate and send a revoke request.
6. `mkVoucherInitiationS2SMandateSuccessResponse` maps mandate and mandate-history records to the S2S response.
7. `flowWithTrace` signs or encrypts the response according to the merchant response strategy.

## Endpoint

```http
POST /api/{apiVersion}/merchants/voucher/create
```

Payloads use Newton's standard server-to-server request and response envelope. Examples in this guide show decrypted business payloads and decrypted response bodies for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body must be JSON. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. Used to resolve the merchant before payload/business processing. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-timestamp` | Yes | Current request timestamp as 13-digit epoch milliseconds. Newton rejects malformed timestamps and timestamps outside the allowed freshness window. |
| `x-merchant-signature` | Conditional | Required when sending an unsigned/plain business payload. Signature is verified over merchant ids, optional sub-merchant ids, timestamp, and raw request body. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant flows. Included in signature material when sent. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP in the comma-separated value must be allowlisted. |
| `x-api-version` | Recommended | Use the version shared during onboarding. This route does not currently branch response fields by this header, but it is part of the common S2S contract. |
| `x-request-id` | No | Optional client request id for tracing. Newton generates one if omitted. |
| `x-session-id` | No | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

Response headers:

| Header | Description |
| --- | --- |
| `x-requestid` | Newton request id used for tracing. |
| `x-sessionid` | Newton session id used for tracing. |
| `X-Response-Signature` | Present for unsigned response mode. For JWS/JWE response strategies, the response body itself is signed/encrypted. |

## Authentication, Signing, and Envelope

The route request type is `EncRequest VoucherInitiationS2SRequest`. Depending on merchant configuration, the wire request can be:

- Plain decrypted JSON business payload, protected by `x-merchant-signature`.
- JWS signed body.
- JWE encrypted body containing a signed payload.

For signed or encrypted request bodies, the decrypted business payload must include `iat`, and `iat` must be a current 13-digit epoch-milliseconds timestamp. Plain-body header-signature mode does not validate request-body `iat`, but still requires merchant headers, `x-timestamp`, and a valid header signature.

The response type is `EncResponse VoucherInitiationS2SResponse`. Depending on merchant response strategy, the wire response can be a signed JWS response, encrypted JWE response, or plain decrypted JSON with `X-Response-Signature`.

## Request

### Create Voucher Minimum

```json
{
  "amount": "1000.00",
  "validityStart": "2026/7/3",
  "validityEnd": "2026/12/31",
  "requestType": "CREATE",
  "amountRule": "MAX",
  "iat": "1782968400000",
  "mandateName": "Meal voucher July",
  "merchantRequestId": "VOUCHERCREATE1001",
  "payerRevocable": "true",
  "purpose": "A1",
  "recipientName": "Example Store",
  "recurrencePattern": "ONETIME",
  "upiRequestId": "VCHRCR1001",
  "voucherVpa": "meal.1001@prepaid.npci"
}
```

### Revoke Voucher Minimum

```json
{
  "requestType": "REVOKE",
  "orgMandateId": "VCHRCR1001",
  "upiRequestId": "VCHRRV1001",
  "merchantRequestId": "VOUCHERREVOKE1001",
  "remarks": "Customer requested voucher revoke",
  "iat": "1782968400000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `requestType` | string enum | Yes | No default. | Operation for this endpoint. Supported product values are `CREATE` and `REVOKE`. Other shared mandate-history enum values can parse but are rejected by this route with `Invalid requestType`. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated UPI request id for this API attempt. Must be 1 to 35 alphanumeric characters. For create, Newton uses it as the mandate id and returns it as `payload.gatewayMandateId` and `payload.orgMandateId`. |
| `amount` | string | Required for `CREATE` | No default. Missing value can fail before successful voucher creation because product logic requires it. | Voucher amount in two-decimal format, for example `1000.00`. Must be greater than `0.00` and not exceed `100000.00` for voucher creation. |
| `validityStart` | string | Required for `CREATE` | No default. | Voucher validity start date. Use `YYYY/M/D`, for example `2026/7/3`. It must parse as a date and must not be in the past at processing time. |
| `validityEnd` | string | Required for `CREATE` | No default. | Voucher validity end date. Use `YYYY/M/D`. It must not be before `validityStart`. For `ONETIME`, the difference from `validityStart` must not exceed 365 days. |
| `orgMandateId` | string | Required for `REVOKE` | For revoke, omission makes the lookup fall back to `upiRequestId`, which usually does not identify the original voucher. | Original voucher mandate id, represented as the create call's `upiRequestId`. Must be 1 to 35 alphanumeric characters when supplied. |
| `amountRule` | string enum | No | Defaults to `MAX` during create processing. | Voucher mandate amount rule. Allowed values: `MAX`, `EXACT`. Returned as `payload.amountRule`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by signed/encrypted request verification. Must be a current 13-digit epoch-milliseconds timestamp when required by the configured S2S envelope. |
| `mandateName` | string | No | Defaults to `Voucher Mandate` during create processing. | Voucher mandate display name. If supplied, must be non-empty. Returned when stored on the mandate. |
| `merchantRequestId` | string | Required for `CREATE`; recommended for `REVOKE` | Revoke generates a UUID internally if omitted. Create has no useful default and product logic requires it. | Merchant order/reference id. Must be 1 to 35 characters and match the merchant-request-id pattern: letters, numbers, hyphen, dot, and underscore. |
| `payerRevocable` | string boolean | No | No explicit default in this route; downstream mandate behavior may derive a stored revocable value. | `"true"` or `"false"` ignoring case. If the stored voucher is not payer-revocable, revoke fails with `Mandate is not payer revocable`. |
| `purpose` | string | Required for `CREATE` | No default. | Two-character e-RUPI purpose code. Format validation allows uppercase letter/digit combinations where at least one character is a letter; business validation requires the stricter e-RUPI pattern: uppercase letter plus non-zero digit, or non-zero digit plus uppercase letter. |
| `recipientName` | string | No | No default. | Payee/recipient display name included in payee info. If supplied, must be non-empty. |
| `recurrencePattern` | string enum | Required for `CREATE` | No default. | Voucher mandate recurrence pattern. Allowed enum values are `ONETIME`, `DAILY`, `WEEKLY`, `FORTNIGHTLY`, `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, `YEARLY`, and `ASPRESENTED`. Voucher business validation only adds a special 365-day max window check for `ONETIME`. |
| `refUrl` | string | No | Response defaults to an empty string if neither mandate metadata nor request value is present. | Merchant reference URL. The current request validator does not apply URL-format validation for this field. |
| `refCategory` | string | No | Response defaults to `00` if neither mandate metadata nor request value is present. | Merchant reference category. Must be exactly two digits when supplied. |
| `remarks` | string | No | Create defaults to `remarks`; revoke defaults to `Revoke Mandate`; response defaults to `remarks` if no stored remarks are present. | Customer/payment note. Must be 1 to 255 characters and match the remarks regex when supplied. |
| `subMerchantDetails` | object | No | No default. | Optional sub-merchant/store details used in payer info for voucher creation. See nested object reference. |
| `udfParameters` | string | No | Omitted from response if not supplied. | String-encoded JSON object for merchant metadata. Must parse as a JSON object and must not contain characters rejected by the validator. Echoed in successful responses. |
| `umn` | string | No | No default. Downstream mandate flow can generate/store a UMN. | UPI mandate number to pass into the create or revoke flow when available/required by the integration. This route does not run UMN format validation directly. |
| `voucherVpa` | string | Required for `CREATE` | No default. | Voucher VPA. Must be 3 to 255 characters and match `^[a-zA-Z0-9]+[.][a-zA-Z0-9]+@prepaid[.]npci$`, for example `meal.1001@prepaid.npci`. Stored lowercased as the mandate payee VPA and returned as `payload.uuid`. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and should be treated as omitted by the route.

- `amountRule`: omitted becomes `MAX` during voucher create payload construction.
- `mandateName`: omitted becomes `Voucher Mandate`.
- `remarks`: omitted becomes `remarks` for create and `Revoke Mandate` for revoke; response also defaults to `remarks` when stored remarks are absent.
- `refUrl`: response defaults to an empty string when absent from both stored mandate metadata and request.
- `refCategory`: response defaults to `00` when absent from both stored mandate metadata and request.
- `merchantRequestId` on revoke: if omitted, revoke payload generation creates an internal UUID for the downstream request. Send your own value if you need deterministic reconciliation.
- `payerVpa` is not a request field. During create, Newton sets it to `eRupiVoucher` plus the merchant VPA domain, or the global configured VPA domain when the merchant does not have one.
- Voucher create expiry is fixed at 1440 minutes in the generated mandate payload.
- Payee MCC is derived from configured `erupiPurposeCodeMccMapping` for the supplied purpose code when configured; otherwise it falls back to `0000`.

For `CREATE`, several type-level optional fields are product-required: `amount`, `validityStart`, `validityEnd`, `merchantRequestId`, `purpose`, `recurrencePattern`, and `voucherVpa`. Do not omit them. Missing values can surface as `BAD_REQUEST`, `INVALID_DATA`, or `INTERNAL_SERVER_ERROR` depending on which branch first dereferences the value.

### Nested Request Object: `subMerchantDetails`

Use `subMerchantDetails` only when the merchant is enabled to send sub-merchant/store data for voucher creation.

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `name` | string | Yes | No default. | Sub-merchant display name. Must be non-empty. |
| `accountNumber` | string | Conditional | No default. | Settlement/account number. Product logic requires `accountNumber` and `accountType` when `subMerchantDetails` is supplied. If `accountNumber`, `ifsc`, and `accountType` are all supplied, `accountNumber` must be numeric and no longer than 18 characters. |
| `ifsc` | string | No | No default. | Optional for voucher creation. If all account fields are supplied, must be an 11-character IFSC matching `^[A-Z]{4}0[A-Z0-9]{6}$`. |
| `bankName` | string | No | No default. | Optional bank name. Must be non-empty if supplied. |
| `accountType` | string | Conditional | No default. | Product logic requires `accountNumber` and `accountType` when `subMerchantDetails` is supplied. If all account fields are supplied, must be non-empty. |
| `bankIIN` | string | No | No default. | Bank IIN/code. Must be numeric and no longer than 20 characters when supplied. |
| `mcc` | string | Yes | No default. | Sub-merchant MCC. Must be exactly four digits. |
| `brandName` | string | Yes | No default. | Brand name. Must be alphanumeric including spaces and 1 to 99 characters. |
| `legalName` | string | Yes | No default. | Legal name. Must be alphanumeric including spaces and 1 to 99 characters. |
| `franchise` | string | Yes | No default. | Franchise/store-chain name. Must be alphanumeric including spaces and 1 to 99 characters. |
| `merchantType` | string enum | Yes | No default. | Allowed values: `SMALL`, `LARGE`. |
| `ownershipType` | string enum | Yes | No default. | Allowed values: `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. |
| `genre` | string enum | Yes | No default. | Allowed values: `ONLINE`, `OFFLINE`. |
| `onboardingType` | string enum | Yes | No default. | Allowed values: `BANK`, `AGGREGATOR`. |
| `gstin` | string | No | No default. | Optional GSTIN. The validator only checks that it is non-empty when supplied. |
| `mid` | string | No | No default. | Sub-merchant MID. Must be 1 to 20 alphanumeric characters when supplied. |
| `sid` | string | No | No default. | Sub-merchant SID. Must be 1 to 20 alphanumeric characters when supplied. |
| `tid` | string | No | No default. | Sub-merchant TID. Must be 1 to 20 alphanumeric characters when supplied. |

## Request Examples

### Create One-Time Voucher

```json
{
  "amount": "1000.00",
  "validityStart": "2026/7/3",
  "validityEnd": "2026/12/31",
  "requestType": "CREATE",
  "amountRule": "MAX",
  "iat": "1782968400000",
  "mandateName": "Meal voucher July",
  "merchantRequestId": "VOUCHERCREATE1001",
  "payerRevocable": "true",
  "purpose": "A1",
  "recipientName": "Example Store",
  "recurrencePattern": "ONETIME",
  "refUrl": "https://merchant.example/vouchers/VOUCHERCREATE1001",
  "refCategory": "00",
  "remarks": "Meal voucher",
  "upiRequestId": "VCHRCR1001",
  "udfParameters": "{\"program\":\"meal\",\"batch\":\"2026-07\"}",
  "voucherVpa": "meal.1001@prepaid.npci"
}
```

### Create Voucher With Sub-Merchant Details

```json
{
  "amount": "2500.00",
  "validityStart": "2026/7/3",
  "validityEnd": "2026/10/31",
  "requestType": "CREATE",
  "amountRule": "EXACT",
  "iat": "1782968400000",
  "mandateName": "Benefits voucher",
  "merchantRequestId": "VOUCHERCREATE1002",
  "payerRevocable": "false",
  "purpose": "B2",
  "recipientName": "Example Pharmacy",
  "recurrencePattern": "ONETIME",
  "subMerchantDetails": {
    "name": "Example Pharmacy Koramangala",
    "accountNumber": "123456789012",
    "accountType": "CURRENT",
    "bankName": "Example Bank",
    "bankIIN": "123456",
    "mcc": "5912",
    "brandName": "Example Pharmacy",
    "legalName": "Example Healthcare Private Limited",
    "franchise": "Example Pharmacy",
    "merchantType": "SMALL",
    "ownershipType": "PRIVATE",
    "genre": "OFFLINE",
    "onboardingType": "AGGREGATOR",
    "gstin": "29ABCDE1234F1Z5",
    "mid": "MID1002",
    "sid": "SID1002",
    "tid": "TID1002"
  },
  "upiRequestId": "VCHRCR1002",
  "voucherVpa": "benefit.1002@prepaid.npci"
}
```

### Revoke Existing Voucher

```json
{
  "requestType": "REVOKE",
  "orgMandateId": "VCHRCR1001",
  "upiRequestId": "VCHRRV1001",
  "merchantRequestId": "VOUCHERREVOKE1001",
  "remarks": "Voucher cancelled before redemption",
  "udfParameters": "{\"reason\":\"order_cancelled\"}",
  "iat": "1782968400000"
}
```

## Validation and Processing Behavior

### Request Format Validation

Newton rejects the request before business processing when:

- `requestType` or another enum value cannot be parsed from JSON.
- `upiRequestId` is empty, longer than 35 characters, or contains non-alphanumeric characters.
- `orgMandateId`, when supplied, fails the same `upiRequestId` format validation.
- `amount`, when supplied, does not match `^[0-9]+\.[0-9][0-9]$` or is not greater than `0.00`.
- `validityStart` or `validityEnd`, when supplied, cannot be parsed as a date after replacing `/` with `-` and appending `T00:00:01+05:30`.
- `mandateName` or `recipientName`, when supplied, is empty.
- `merchantRequestId`, when supplied, is empty, longer than 35 characters, or fails the allowed id pattern.
- `payerRevocable`, when supplied, is not `"true"` or `"false"` ignoring case.
- `purpose`, when supplied, is not exactly two characters or fails voucher purpose-code format validation.
- `remarks`, when supplied, is empty, longer than 255 characters, or contains characters rejected by the remarks regex.
- `refCategory`, when supplied, is not exactly two digits.
- `subMerchantDetails`, when supplied, fails nested validation.
- `udfParameters`, when supplied, is not a JSON-object string or contains characters rejected by the validator.
- `voucherVpa`, when supplied, does not match the prepaid-voucher VPA regex.

### Create Processing

For `requestType: "CREATE"`, Newton:

- Looks for an existing mandate by `upiRequestId`.
- If found, returns the existing mandate and pending create mandate-history record. The request body is validated, but voucher business validation and downstream creation are not run again.
- If not found, validates create-only business rules.
- Requires `validityStart`, `validityEnd`, `purpose`, `amount`, `merchantRequestId`, `recurrencePattern`, and `voucherVpa`.
- Requires `accountNumber` and `accountType` when `subMerchantDetails` is supplied. `ifsc` is optional for voucher creation.
- Rejects voucher amount greater than `100000.00`.
- Requires purpose to be an e-RUPI purpose code matching uppercase-letter/non-zero-digit or non-zero-digit/uppercase-letter, such as `A1` or `1A`.
- Rejects validity windows where `validityStart` is in the past, `validityEnd` is before `validityStart`, or `ONETIME` spans more than 365 days.
- Builds a prepaid-voucher mandate with transaction type `PREPAID_VOUCHER`, role `PAYER`, `blockFund: "true"`, initiation mode `00`, expiry of 1440 minutes, and payer VPA `eRupiVoucher` plus the merchant/default VPA domain.
- Calls the underlying mandate route and maps the resulting mandate and mandate-history rows into this API response.

### Revoke Processing

For `requestType: "REVOKE"`, Newton:

- Looks up the original voucher mandate by `orgMandateId` when supplied; otherwise it falls back to `upiRequestId`.
- Returns `INVALID_DATA` with `Mandate not found` when no original mandate is found.
- Rejects payer-side revoke when the stored mandate is not revocable.
- Builds a payer-side revoke payload with request `upiRequestId`, request `merchantRequestId` when supplied, `remarks` defaulting to `Revoke Mandate`, and the merchant's device metadata defaults.
- Calls the underlying mandate route and maps the returned mandate-history status into this API response.

### Idempotency

Create is idempotent by `upiRequestId` in this route: a repeated `CREATE` with the same `upiRequestId` returns the existing mandate details rather than creating another voucher. The route does not compare every request field with the original create request before returning the existing record, so keep retries byte-for-byte consistent and reconcile the returned payload.

Revoke uses `upiRequestId` as the new revoke attempt id and `orgMandateId` as the original voucher id. Use a new `upiRequestId` for each revoke attempt unless Newton support advises otherwise.

## Response

Route response type: `RespHeaders (API.EncResponse API.VoucherInitiationS2SResponse)`

Business response type: `API.VoucherInitiationS2SResponse`

### Success Response: Create Pending

For payer-side mandate creation, `payload.gatewayResponseStatus` is commonly `PENDING` with `gatewayResponseCode: "01"` while the downstream mandate create request is in progress.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "1000.00",
    "amountRule": "MAX",
    "gatewayMandateId": "VCHRCR1001",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate Create Request Sent Successfully",
    "gatewayResponseStatus": "PENDING",
    "mandateName": "Meal voucher July",
    "mandateTimestamp": "2026-07-02T10:30:01+05:30",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "VOUCHERCREATE1001",
    "orgMandateId": "VCHRCR1001",
    "payerRevocable": "true",
    "recurrencePattern": "ONETIME",
    "requestType": "CREATE",
    "refCategory": "00",
    "refUrl": "https://merchant.example/vouchers/VOUCHERCREATE1001",
    "remarks": "Meal voucher",
    "uuid": "meal.1001@prepaid.npci",
    "validityEnd": "2026-12-31T00:00:01+05:30",
    "validityStart": "2026-07-03T00:00:01+05:30"
  },
  "udfParameters": "{\"program\":\"meal\",\"batch\":\"2026-07\"}"
}
```

### Success Response: Create Gateway Success

If the mandate is already successful by the time the API response is built, gateway fields can indicate success.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "1000.00",
    "amountRule": "MAX",
    "gatewayMandateId": "VCHRCR1001",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Mandate Creation Success",
    "gatewayResponseStatus": "SUCCESS",
    "mandateName": "Meal voucher July",
    "mandateTimestamp": "2026-07-02T10:30:01+05:30",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "VOUCHERCREATE1001",
    "orgMandateId": "VCHRCR1001",
    "payerRevocable": "true",
    "recurrencePattern": "ONETIME",
    "requestType": "CREATE",
    "refCategory": "00",
    "refUrl": "https://merchant.example/vouchers/VOUCHERCREATE1001",
    "remarks": "Meal voucher",
    "umn": "12345678901234567890123456789012@upi",
    "uuid": "meal.1001@prepaid.npci",
    "validityEnd": "2026-12-31T00:00:01+05:30",
    "validityStart": "2026-07-03T00:00:01+05:30"
  }
}
```

### Success Response: Revoke Pending

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "1000.00",
    "amountRule": "MAX",
    "gatewayMandateId": "VCHRRV1001",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate revoke Request Sent Successfully",
    "gatewayResponseStatus": "PENDING",
    "mandateName": "Meal voucher July",
    "mandateTimestamp": "2026-07-02T10:30:01+05:30",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "VOUCHERREVOKE1001",
    "orgMandateId": "VCHRCR1001",
    "payerRevocable": "true",
    "recurrencePattern": "ONETIME",
    "requestType": "REVOKE",
    "refCategory": "00",
    "refUrl": "https://merchant.example/vouchers/VOUCHERCREATE1001",
    "remarks": "Meal voucher",
    "umn": "12345678901234567890123456789012@upi",
    "uuid": "meal.1001@prepaid.npci",
    "validityEnd": "2026-12-31T00:00:01+05:30",
    "validityStart": "2026-07-03T00:00:01+05:30"
  },
  "udfParameters": "{\"reason\":\"order_cancelled\"}"
}
```

### Processed Response: Gateway Business Failure

When the underlying mandate route returns a mandate record with a failure status, this API can still return top-level `SUCCESS`. Treat nested `payload.gatewayResponseStatus: "FAILURE"` as the business failure. The gateway response code and message vary by downstream/NPCI response.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "1000.00",
    "amountRule": "MAX",
    "gatewayMandateId": "VCHRCR1003",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "Mandate Request Failed",
    "gatewayResponseStatus": "FAILURE",
    "mandateName": "Meal voucher July",
    "mandateTimestamp": "2026-07-02T10:30:01+05:30",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "VOUCHERCREATE1003",
    "orgMandateId": "VCHRCR1003",
    "payerRevocable": "true",
    "recurrencePattern": "ONETIME",
    "requestType": "CREATE",
    "refCategory": "00",
    "refUrl": "",
    "remarks": "remarks",
    "uuid": "meal.1003@prepaid.npci",
    "validityEnd": "2026-12-31T00:00:01+05:30",
    "validityStart": "2026-07-03T00:00:01+05:30"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Top-level Newton API processing status. Successful API processing returns `SUCCESS`; business result is in `payload.gatewayResponseStatus`. |
| `responseCode` | string | Top-level Newton response code. Successful API processing returns `SUCCESS`. |
| `responseMessage` | string | Top-level Newton response message. Successful API processing returns `SUCCESS`. |
| `payload` | object | Voucher mandate result. Present on processed responses. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from Newton's merchant record. |
| `merchantChannelId` | string | Merchant channel id from Newton's merchant record. |
| `merchantRequestId` | string | Merchant request id stored on the mandate-history row. |
| `mandateName` | string | Stored voucher mandate name. Omitted if the mandate record has no name. |
| `amount` | string | Voucher mandate amount formatted with two decimals. |
| `payerRevocable` | string | Stored mandate revocability as `"true"` or `"false"`. |
| `amountRule` | string | Stored mandate amount rule, usually `MAX` or `EXACT`. |
| `validityStart` | string | Stored validity start timestamp in IST text format. |
| `validityEnd` | string | Stored validity end timestamp in IST text format. |
| `recurrencePattern` | string | Stored recurrence pattern. |
| `recurrenceRule` | string | Stored recurrence rule when present. Omitted otherwise. |
| `recurrenceValue` | string | Stored recurrence value when present. Omitted otherwise. |
| `remarks` | string | Stored remarks or Newton default `remarks`. |
| `refUrl` | string | Stored request reference URL, request `refUrl`, or default empty string. |
| `refCategory` | string | Stored request reference category, request `refCategory`, or default `00`. |
| `requestType` | string | Request operation echoed from the decrypted request, usually `CREATE` or `REVOKE`. |
| `gatewayMandateId` | string | Request `upiRequestId`. For create, this is also the original mandate id; for revoke, this is the revoke attempt id. |
| `gatewayResponseCode` | string | Normalized gateway response code. `00` indicates gateway success; `01` commonly indicates pending for payer-side create/revoke. Other values indicate gateway/business failure. |
| `gatewayResponseMessage` | string | Normalized gateway response message. Failure text may come from downstream/NPCI response data and can vary. |
| `gatewayResponseStatus` | string | `SUCCESS`, `PENDING`, or `FAILURE` as mapped from mandate or mandate-history status. |
| `mandateTimestamp` | string | Mandate creation timestamp in IST text format. |
| `orgMandateId` | string | Original voucher mandate `upiRequestId`. Use this in revoke or status/reconciliation calls. |
| `umn` | string | UPI mandate number when available. Omitted until the mandate has one. |
| `uuid` | string | Stored mandate payee VPA, which is the voucher VPA for this API. |

## Failure Scenarios

Failure responses use the same response transport strategy as the rest of the S2S integration. If the response is encrypted or signed, decrypt/verify it before reading the body. Examples below show decrypted response bodies.

Clients should distinguish:

- Transport/auth/request/business-rule failures: top-level `status: "FAILURE"` response body or non-2xx HTTP status depending on the layer.
- Processed voucher operation with negative gateway result: top-level `status: "SUCCESS"` and `payload.gatewayResponseStatus: "FAILURE"`.

### Request Validation Failure

Invalid request fields are rejected before voucher business processing. The response message is built from validator constructors and can include multiple comma-separated validation errors.

Invalid amount format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Zero amount:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"amount is not greater than 0.0\""
}
```

Invalid date value:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"date value not valid\""
}
```

Invalid voucher VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"VoucherVpa regex failed\""
}
```

Invalid merchant request id:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
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

Nested sub-merchant enum failure:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed SOLE_PROPRIETOR\""
}
```

Other validation messages can include:

- `LengthValidation "upiRequestId length is not between 1 and 35"`
- `RegexValidation "upiRequestId regex match failed"`
- `LengthValidation "Purpose Code length is not 2"`
- `RegexValidation "Purpose Code regex match failed."`
- `BoolStringValidation "Parameter is not true or false"`
- `LengthValidation "remarks length is not between 1 and 255"`
- `RegexValidation "remarks regex match failed"`
- `LengthValidation "refCategory length is not exactly 2"`
- `RegexValidation "refCategory regex match failed"`
- `LengthValidation "VoucherVpa length is not between 3 and 255"`
- `RegexValidation "accountNumber regex match failed"`
- `LengthValidation "ifsc length is not 11"`
- `RegexValidation "mcc regex match failed"`
- `LengthValidation "brandName length not between 1 and 99"`
- `RegexValidation "mid regex failed"`

### JSON Parse, Missing Required Field, or Unknown Enum Failure

If a type-level required field is missing, has the wrong JSON type, or an enum value cannot be parsed, the request can fail before request-field validation runs. Parser text varies by JSON parser path and field name.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.requestType: parsing Newton.Types.Storage.MandateHistory.MandateHistoryType failed"
}
```

Missing `upiRequestId` can surface as parser text naming the missing key:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"upiRequestId\" not found"
}
```

### Authentication, Signature, Encryption, and Timestamp Failures

Missing merchant headers, invalid merchant signature, failed JWE decryption, failed JWS verification, missing/invalid `iat`, invalid `x-timestamp`, stale timestamp, and IP whitelist failures are rejected before product logic.

Typical authorization failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

JWS/JWE signature-source failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Malformed `iat` or `x-timestamp`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
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

Malformed encrypted payload parsing can return invalid-data text. The parser text varies with the malformed field.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload"
}
```

### Merchant API Access Disabled or Not Allowed

Returned when merchant configuration blocks this API or an allow-list is configured and `voucherInitiationS2S` is not allowed.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### IP Restriction Failure

Returned when merchant IP allowlisting is configured and `x-forwarded-for` is missing or the first IP is not allowlisted.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Missing Product-Required Create Field

Although several create fields are optional in the Haskell request type, product logic requires them for successful voucher creation. Missing `amount`, `validityStart`, `validityEnd`, `merchantRequestId`, `purpose`, `recurrencePattern`, or `voucherVpa` can surface as an internal server error from current dereference paths.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: treat these fields as required for `CREATE`; correct the request rather than retrying unchanged.

### Sub-Merchant Account Fields Missing

If `subMerchantDetails` is supplied but either `accountNumber` or `accountType` is absent, create validation fails. `ifsc` is optional for voucher creation.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "accountNumber and accountType must be present in subMerchantDetails"
}
```

### Voucher Amount Exceeds Limit

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid amount value for voucher"
}
```

### Invalid e-RUPI Purpose Code

This happens when `purpose` passes basic two-character validation but is not accepted by voucher business logic as an e-RUPI purpose code.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid purpose value for voucher"
}
```

### Invalid Voucher Validity Window

Returned when `validityStart` is in the past, `validityEnd` is before `validityStart`, or an `ONETIME` voucher spans more than 365 days.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "validityStart and validityEnd is not valid"
}
```

### Unsupported Parsed Request Type

The shared enum can parse values such as `UPDATE`, `PAUSE`, or `UNPAUSE`, but this route supports only `CREATE` and `REVOKE`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid requestType"
}
```

### Revoke Mandate Not Found

Returned when `requestType` is `REVOKE` and Newton cannot find the original mandate by `orgMandateId` or the fallback lookup key.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate not found"
}
```

### Revoke Not Allowed

Returned when the stored voucher mandate is not payer-revocable.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate is not payer revocable"
}
```

### Downstream Mandate or NPCI Failure

If the underlying mandate route returns a usable mandate record with a failure status, the API can return top-level success with nested gateway failure. The gateway code/message are mapped from the downstream response and can vary.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "1000.00",
    "amountRule": "MAX",
    "gatewayMandateId": "VCHRCR1003",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "Mandate Request Failed",
    "gatewayResponseStatus": "FAILURE",
    "mandateTimestamp": "2026-07-02T10:30:01+05:30",
    "merchantChannelId": "APP",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "VOUCHERCREATE1003",
    "orgMandateId": "VCHRCR1003",
    "payerRevocable": "true",
    "recurrencePattern": "ONETIME",
    "requestType": "CREATE",
    "refCategory": "00",
    "refUrl": "",
    "remarks": "remarks",
    "uuid": "meal.1003@prepaid.npci",
    "validityEnd": "2026-12-31T00:00:01+05:30",
    "validityStart": "2026-07-03T00:00:01+05:30"
  }
}
```

If the downstream wrapper response is unusable, times out, or required records are missing, the route can return a top-level failure:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U91",
  "responseMessage": "NPCI service is not reachable at the moment (U91)"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Downstream NPCI error-code descriptions that can be relevant later in voucher validation/redemption include `J10` (`Voucher Expired`), `J11` (`Voucher Incorrect date format`), and `T28` (`Mandate Voucher amount should not exceed`). They are not directly thrown by the create route's own business validation, but can appear in related voucher/mandate gateway or callback contexts.

## Retry, Idempotency, and Client Handling

- Use a unique `upiRequestId` for each new voucher create attempt.
- If a create call times out, retry with the same `upiRequestId` and the same business payload. This route returns the existing mandate if the first create reached mandate creation.
- Store `orgMandateId` from the create response; send it for revoke and status/reconciliation flows.
- Do not retry unchanged validation failures, authentication failures, API-not-enabled failures, IP allowlist failures, invalid purpose/validity/amount failures, or non-revocable revoke failures.
- For create responses with `payload.gatewayResponseStatus: "PENDING"`, wait for callbacks or poll mandate status with the returned identifiers according to the agreed operational cadence.
- For `payload.gatewayResponseStatus: "FAILURE"`, treat the voucher operation as failed unless a later status/callback from Newton indicates otherwise.
- For transient `SERVICE_UNAVAILABLE_*`, gateway timeout, or `INTERNAL_SERVER_ERROR`, use bounded exponential backoff and reconcile by `upiRequestId`/`orgMandateId` before creating a new voucher id.
- For revoke, use a new `upiRequestId` for the revoke attempt and keep `orgMandateId` fixed to the original voucher mandate id.

## Source References

- S2S route definition for `/merchants/voucher/create`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:523)
- Voucher route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2901)
- Server handler mapping: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:296)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request body unwrap path: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- S2S response signing/encryption path: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API access/IP verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request type and validator: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:631)
- Response payload type: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:698)
- Response wrapper type: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:733)
- Sub-merchant request type and validator: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:237)
- Voucher product route and business validation: [src/Newton/Product/MerchantMandateV2.hs](../../src/Newton/Product/MerchantMandateV2.hs:56)
- Create/revoke payload and response transformers: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:3088)
- Gateway response mapping: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:1488)
- Common field validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- Voucher purpose/VPA validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:938)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
- Voucher expiry/date NPCI error-code descriptions: [src/Newton/Constants/ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:301)
- Voucher amount NPCI error-code description: [src/Newton/Constants/ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:749)
