# Port Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/portMandate`

## Overview

Port Mandate is a server-to-server API used to port an existing UPI mandate into Newton as a payee-side interoperability mandate.

The merchant sends the details of an existing mandate, including the original mandate id, UMN, payer VPA, amount, validity, recurrence, and current active or paused state. Newton validates the merchant, request signature, merchant API configuration, mandate constraints, and duplicate references, then creates a new Newton mandate record and mandate history with request type `PORT_IN` and role `PAYEE`.

Use this API when a merchant is migrating existing active or paused mandates to Newton and needs Newton to recognize those mandates for later status, update, pause, execute, notify, and reconciliation flows.

## Business Use Case

Port Mandate helps merchants:

- Bring an existing UPI mandate into Newton without asking the payer to create a fresh mandate.
- Preserve the original mandate reference through `orgMandateId`, `originalMerchantRequestId`, and `umn`.
- Store the mandate as a payee-side `PORT_IN` mandate with Newton-generated `gatewayMandateId`.
- Carry forward amount, amount rule, recurrence, validity, revocability, payer details, and pause state.
- Support dynamic VPA and aggregator/sub-merchant mandate migration where enabled.
- Attach optional split settlement, mutual fund details, and merchant-defined metadata for downstream processing and reconciliation.

## Integration Flow

1. Merchant identifies an existing UPI mandate to migrate.
2. Merchant generates a unique `merchantRequestId` for this port-in attempt.
3. Merchant calls `portMandate` with the original mandate identifiers and full mandate terms.
4. Newton decrypts or verifies the encrypted/signed S2S payload, resolves the merchant from headers, and validates signature/checksum, timestamp, API enablement, and IP whitelist.
5. Newton validates the decrypted request body and business rules.
6. Newton creates the internal port-in mandate request using `_type = PORT_IN`, `_role = PAYEE`, a generated UPI request id, the interoperability purpose code, and the resolved payee VPA.
7. Newton persists the mandate and mandate history through the mandate route.
8. Merchant decrypts the response and stores `gatewayMandateId`, `orgMandateId`, `umn`, `merchantRequestId`, and gateway response fields for reconciliation.

Important identifiers:

- `merchantRequestId`: Unique merchant idempotency key for this port-in request. Do not reuse it for a different port-in attempt.
- `orgMandateId`: Original mandate UPI request id from the existing mandate being ported. Newton rejects a second port-in for the same `orgMandateId` and `umn` for the same merchant.
- `originalMerchantRequestId`: Merchant request id from the original mandate, preserved in the response as the original mandate's merchant reference.
- `gatewayMandateId`: Newton-generated UPI request id for the port-in action. Use this as Newton's mandate action id.
- `umn`: UPI mandate number of the original mandate.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/portMandate
```

Payloads use the standard Newton server-to-server request and response envelope. Examples in this guide show the decrypted business payload for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | JSON request envelope. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. Used to resolve merchant configuration. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required when calling on behalf of a configured sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id`. |
| `x-timestamp` | Yes | Request timestamp used for signature/timestamp validation. |
| `x-raw-body` | Yes | Exact raw request body string used by Newton for signature verification. |
| `x-merchant-signature` | Conditional | Required for plain unsigned payloads, unless an onboarded checksum/bypass mode applies. |
| `x-merchant-checksum` | Conditional | Merchant checksum header when checksum mode is used. |
| `Authorization` | Conditional | Present when required by the merchant's onboarded S2S mode. |
| `x-forwarded-for` | Conditional | Required if the merchant has `whitelistedIps` configured. The first comma-separated IP must be whitelisted. |
| `x-request-id` | No | Optional trace id. Newton generates one if omitted. |
| `x-session-id` | No | Optional session id. Defaults to `x-request-id` if omitted. |
| `x-api-version` | Recommended | Use the version shared during onboarding. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant integration. |

### Authentication, Encryption, And Signing

The route accepts Newton's standard S2S envelope variants:

- JWE encrypted payload.
- JWS signed payload.
- Plain business JSON payload, subject to merchant signature/checksum validation.

For encrypted or signed payloads, `iat` is required in the decrypted payload and is validated as a timestamp. For plain payloads, `iat` is accepted but not required by the signature validator.

The public request envelope is `EncRequest PortMandateRequest`; the public response envelope is `EncResponse PortMandateResponse`. Depending on onboarding, the wire response may be encrypted, signed, an error envelope, or plain in lower environments. The JSON examples below show the decrypted business body.

## Request

### Required Minimum For Active Mandate Port-In

```json
{
  "amount": "100.00",
  "amountRule": "MAX",
  "blockFund": false,
  "initiationMode": "00",
  "isExecutedOnce": false,
  "isP2MMandate": true,
  "mandateName": "Monthly subscription",
  "mandateStatus": "SUCCESS",
  "merchantRequestId": "PORTIN000001",
  "orgMandateId": "ORGMANDATE000001",
  "originalMerchantRequestId": "ORIGINAL000001",
  "payerName": "Rahul Sharma",
  "payerRevocable": "true",
  "payerVpa": "rahul@examplebank",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "5",
  "transactionType": "UPI_MANDATE",
  "umn": "12345678901234567890123456789012@examplebank",
  "validityStart": "2026/07/01",
  "validityEnd": "2027/07/01"
}
```

### Paused Mandate Port-In

When `mandateStatus` is `PAUSE`, both `pauseStart` and `pauseEnd` are required. The current date/time must fall inside the pause window.

```json
{
  "amount": "250.00",
  "amountRule": "EXACT",
  "blockFund": false,
  "initiationMode": "00",
  "isExecutedOnce": false,
  "isP2MMandate": true,
  "mandateName": "Paused insurance mandate",
  "mandateStatus": "PAUSE",
  "merchantRequestId": "PORTINPAUSE001",
  "orgMandateId": "ORGMANDATEPAUSE001",
  "originalMerchantRequestId": "ORIGINALPAUSE001",
  "pauseStart": "2026/07/01",
  "pauseEnd": "2026/07/31",
  "payerName": "Asha Mehta",
  "payerRevocable": "true",
  "payerVpa": "asha@examplebank",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "10",
  "remarks": "Porting paused mandate",
  "transactionType": "UPI_MANDATE",
  "umn": "12345678901234567890123456789098@examplebank",
  "validityStart": "2026/01/01",
  "validityEnd": "2027/01/01"
}
```

### Dynamic VPA And Sub-Merchant Port-In

Send `payeeVpa` only when dynamic VPA is enabled for the merchant. If `confirmVpaResolution` is also enabled, send `subMerchantDetails`.

```json
{
  "amount": "500.00",
  "amountRule": "MAX",
  "blockFund": false,
  "initiationMode": "00",
  "isExecutedOnce": false,
  "isP2MMandate": true,
  "mandateName": "Aggregator mandate",
  "mandateStatus": "SUCCESS",
  "merchantRequestId": "PORTINDYN001",
  "orgMandateId": "ORGMANDATEDYN001",
  "originalMerchantRequestId": "ORIGINALDYN001",
  "payeeVpa": "merchant.store1@examplebank",
  "payerName": "Neha Iyer",
  "payerRevocable": "true",
  "payerVpa": "neha@examplebank",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "15",
  "refCategory": "SUBSCRIPTION",
  "refId": "STORE1-MANDATE-001",
  "refUrl": "https://merchant.example/orders/STORE1-MANDATE-001",
  "remarks": "Store subscription port-in",
  "transactionType": "UPI_MANDATE",
  "subMerchantDetails": {
    "name": "Store One",
    "mcc": "5411",
    "brandName": "StoreOne",
    "legalName": "StoreOneRetail",
    "franchise": "StoreOne",
    "merchantType": "SMALL",
    "ownershipType": "PRIVATE",
    "genre": "ONLINE",
    "onboardingType": "AGGREGATOR",
    "mid": "STOREMID001",
    "sid": "STORESID001",
    "tid": "STORETID001"
  },
  "udfParameters": "{\"migrationBatch\":\"BATCH-42\"}",
  "umn": "12345678901234567890123456789099@examplebank",
  "validityStart": "2026/07/01",
  "validityEnd": "2027/07/01"
}
```

### Port-In With Split Settlement

```json
{
  "amount": "1000.00",
  "amountRule": "MAX",
  "blockFund": false,
  "initiationMode": "00",
  "isExecutedOnce": false,
  "isP2MMandate": true,
  "mandateName": "Split settlement mandate",
  "mandateStatus": "SUCCESS",
  "merchantRequestId": "PORTINSPLIT001",
  "orgMandateId": "ORGMANDATESPLIT001",
  "originalMerchantRequestId": "ORIGINALSPLIT001",
  "payerName": "Ravi Kumar",
  "payerRevocable": "true",
  "payerVpa": "ravi@examplebank",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "1",
  "splitSettlementDetails": {
    "splitType": "AMOUNT",
    "merchantSplit": "900.00",
    "partnersSplit": [
      {
        "partnerId": "PARTNER001",
        "value": "100.00"
      }
    ]
  },
  "transactionType": "UPI_MANDATE",
  "umn": "12345678901234567890123456789100@examplebank",
  "validityStart": "2026/07/01",
  "validityEnd": "2027/07/01"
}
```

### Port-In With Mutual Fund Details

```json
{
  "amount": "1500.00",
  "amountRule": "MAX",
  "blockFund": false,
  "initiationMode": "00",
  "isExecutedOnce": false,
  "isP2MMandate": true,
  "mandateName": "SIP mandate port-in",
  "mandateStatus": "SUCCESS",
  "merchantRequestId": "PORTINMF001",
  "mutualFundDetails": [
    {
      "memberId": "MEM001",
      "userId": "INVESTOR001",
      "mfPartner": "NSE",
      "investmentType": "SIP",
      "orderNumber": "MFORDER001",
      "amount": "1500.00",
      "amcCode": "ABC",
      "schemeCode": "SCHEME001",
      "panNumber": "ABCDE1234F",
      "applicationNumber": "ITRN001"
    }
  ],
  "orgMandateId": "ORGMANDATEMF001",
  "originalMerchantRequestId": "ORIGINALMF001",
  "payerName": "Meera Rao",
  "payerRevocable": "true",
  "payerVpa": "meera@examplebank",
  "recurrencePattern": "MONTHLY",
  "recurrenceRule": "ON",
  "recurrenceValue": "7",
  "transactionType": "UPI_MANDATE",
  "umn": "12345678901234567890123456789101@examplebank",
  "validityStart": "2026/07/01",
  "validityEnd": "2027/07/01"
}
```

## Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `amount` | string | Yes | No default. | Mandate amount in two-decimal format, for example `100.00`. Must be greater than `0.00` and must not exceed the configured mandate amount limit for the merchant, MCC, VPA, and interoperability purpose. |
| `amountRule` | string | Yes | No default. | Mandate amount rule. Allowed values: `MAX`, `EXACT`. |
| `blockFund` | boolean | Yes | No default. | Must match the configured interoperability/multi-debit purpose behavior. For this port-in path the purpose is set internally to the interoperability purpose code. The examples use `false`, which matches the default code configuration where interoperability purpose `AZ` is not in the one-block/multi-debit purpose list; use the value confirmed during onboarding if your stack differs. |
| `initiationMode` | string | Yes | Validated but internal port-in payload uses `00`. | Two-character alphanumeric initiation mode. Accepted for request compatibility. |
| `isExecutedOnce` | boolean | Yes | Parsed but not used by this port-in mapping. | Compatibility field for the mandate being migrated. |
| `isP2MMandate` | boolean | Yes | Parsed but not used by this port-in mapping. | Compatibility field indicating a P2M mandate. |
| `mandateName` | string | Yes | No default. | Non-empty mandate display name. Stored as mandate name. |
| `mandateStatus` | string | Yes | No default. | Current status of the mandate being ported. Allowed values: `SUCCESS`, `PAUSE`. |
| `merchantRequestId` | string | Yes | No default. | Unique merchant id for this port-in action. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Duplicate `merchantRequestId` for a `PORT_IN` mandate action is rejected. |
| `mutualFundDetails` | array | No | Omitted when not applicable. | Optional mutual fund details. Validated when supplied and echoed in the response. |
| `orgMandateId` | string | Yes | No default. | Original mandate UPI request id. Must be 1 to 35 alphanumeric characters. Newton rejects a mandate already present for the same original mandate id, UMN, merchant, and payee role. |
| `originalMerchantRequestId` | string | Yes | No default. | Merchant request id from the original mandate. Must be 1 to 35 alphanumeric characters because this field uses UPI request id validation in this endpoint. |
| `pauseEnd` | string | Conditional | Omit for active mandates. | Required when `mandateStatus` is `PAUSE`; not allowed when `mandateStatus` is `SUCCESS`. Date format accepted by validator: `YYYY/MM/DD` or `YYYY-MM-DD`. The current time must be before the end of this date. |
| `pauseStart` | string | Conditional | Omit for active mandates. | Required when `mandateStatus` is `PAUSE`; not allowed when `mandateStatus` is `SUCCESS`. Date format accepted by validator: `YYYY/MM/DD` or `YYYY-MM-DD`. The current time must be after the start of this date. |
| `payeeVpa` | string | Conditional | For non-dynamic-VPA merchants, Newton uses the primary merchant account VPA and rejects request `payeeVpa`. | Required when dynamic VPA is enabled. Must be 3 to 255 characters and match VPA format. Echoed in the response only if supplied in the request. |
| `payerName` | string | Yes | No default. | Non-empty payer name. |
| `payerRevocable` | string | Yes | No default. | Revocability flag as a string. Typical values are `"true"` or `"false"`. The field is stored as the mandate revocable flag. |
| `payerVpa` | string | Yes | No default. | Payer/customer VPA. Must be 3 to 255 characters and match VPA format. Returned as `customerVpa`. |
| `recurrencePattern` | string | Yes | No default. | Allowed values: `DAILY`, `WEEKLY`, `FORTNIGHTLY`, `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, `YEARLY`, `ASPRESENTED`. `ONETIME` is part of the enum but is rejected for interoperability port mandates. |
| `recurrenceRule` | string | Conditional | Omit only for `DAILY` or `ASPRESENTED`. | Allowed values: `ON`, `AFTER`, `BEFORE`. Required for `WEEKLY`, `FORTNIGHTLY`, `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, and `YEARLY`. Must be omitted for `DAILY` and `ASPRESENTED`. |
| `recurrenceValue` | string | Conditional | Omit only for `DAILY` or `ASPRESENTED`. | Non-negative integer string. Required with `recurrenceRule` for patterns that need a debit day/value. `WEEKLY`: 1 to 7. `FORTNIGHTLY`: 1 to 16. Other recurring patterns: 1 to 31. Must be omitted for `DAILY` and `ASPRESENTED`. |
| `refCategory` | string | No | If absent, response falls back to Newton's default ref category when mandate storage has no value. | Merchant reference category stored in mandate transaction info. |
| `refId` | string | No | Omitted when not applicable. | Merchant reference id passed to the internal port-in mandate payload. |
| `refUrl` | string | No | If absent, response falls back to Newton's default ref URL when mandate storage has no value. | Merchant reference URL. |
| `remarks` | string | No | Defaults to `remarks` in internal payload and response when absent. | Mandate note. If supplied, 1 to 255 characters; must start with an alphanumeric or hyphen after optional spaces and contain only letters, numbers, spaces, and hyphen. |
| `transactionType` | string | Yes | Parsed but not used by this port-in mapping. | Mandate transaction category. Allowed enum values: `UPI_MANDATE`, `QR_MANDATE`, `INTENT_MANDATE`, `P2M_MANDATE`, `PREPAID_VOUCHER`, `LITE_MANDATE`. |
| `udfParameters` | string | No | Omitted from response if absent. | JSON-object string for merchant metadata. Echoed at top level in the response. |
| `shareToPayee` | string | No | Omitted when not applicable. | Optional boolean string. If supplied, must be `"true"` or `"false"`. Validated but not used by this port-in mapping. |
| `splitSettlementDetails` | object | No | Omitted when not applicable. | Optional split settlement details. Validated when supplied and echoed in the response. |
| `subMerchantDetails` | object | Conditional | Omitted unless dynamic VPA/sub-merchant flow needs it. | Required when dynamic VPA is enabled and merchant config `confirmVpaResolution` is enabled. |
| `umn` | string | Yes | No default. | UPI mandate number. Length 34 to 70 and must match `.{32}@.+`. |
| `validityEnd` | string | Yes | No default. | Mandate validity end date. Date format accepted by validator: `YYYY/MM/DD` or `YYYY-MM-DD`. Must be after `validityStart`. |
| `validityStart` | string | Yes | No default. | Mandate validity start date. Date format accepted by validator: `YYYY/MM/DD` or `YYYY-MM-DD`. For port mandates, past start dates are allowed by this validation path. |
| `iat` | string | Conditional | Required for encrypted/signed payloads; optional for plain payloads. | Issued-at timestamp used for encrypted/signed request timestamp validation. |

## Defaults And Omitted Field Behavior

- `payeeVpa`: if dynamic VPA is disabled, Newton uses the primary merchant account VPA; sending `payeeVpa` is rejected. If dynamic VPA is enabled, `payeeVpa` is required.
- `remarks`: omitted behaves as `"remarks"` internally and in response fallback behavior.
- `refCategory` and `refUrl`: response falls back to Newton defaults if the stored mandate transaction info does not contain values.
- `gatewayMandateId`: generated by Newton for the port-in action; merchants do not send it.
- `pauseStart` and `pauseEnd`: omitted for active mandates; both required for paused mandates.
- `recurrenceRule` and `recurrenceValue`: omitted only for recurrence patterns that do not accept debit-day rules.
- `udfParameters`: no default; echoed only when supplied.
- `mutualFundDetails` and `splitSettlementDetails`: no default; validated and echoed when supplied.

## Nested Request Objects

### `subMerchantDetails`

Use this only for enabled dynamic VPA or aggregator/sub-merchant integrations. If any account detail among `accountNumber`, `ifsc`, and `accountType` is supplied, all three must be supplied.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Non-empty sub-merchant display name. |
| `accountNumber` | string | Conditional | Sub-merchant settlement account number. Required only when sending sub-merchant account details. |
| `ifsc` | string | Conditional | Sub-merchant account IFSC. Required when `accountNumber` or `accountType` is supplied. |
| `bankName` | string | No | Non-empty bank name when supplied. |
| `accountType` | string | Conditional | Sub-merchant account type. Required when `accountNumber` or `ifsc` is supplied. |
| `bankIIN` | string | No | Bank IIN/bank code. Validated when supplied. |
| `mcc` | string | Yes | Four-digit merchant category code. |
| `brandName` | string | Yes | Alphanumeric brand name, 1 to 99 characters. |
| `legalName` | string | Yes | Alphanumeric legal name, 1 to 99 characters. |
| `franchise` | string | Yes | Alphanumeric franchise/store-chain name, 1 to 99 characters. |
| `merchantType` | string | Yes | Allowed values: `SMALL`, `LARGE`. |
| `ownershipType` | string | Yes | Allowed values: `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. |
| `genre` | string | Yes | Allowed values: `ONLINE`, `OFFLINE`. |
| `onboardingType` | string | Yes | Allowed values accepted by this validator: `BANK`, `AGGREGATOR`. |
| `gstin` | string | No | Non-empty GSTIN when supplied. |
| `mid` | string | No | Sub-merchant MID. Alphanumeric, 1 to 20 characters when supplied. |
| `sid` | string | No | Sub-merchant SID. Alphanumeric, 1 to 20 characters when supplied. |
| `tid` | string | No | Sub-merchant TID. Alphanumeric, 1 to 20 characters when supplied. |

### `splitSettlementDetails`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `splitType` | string | Yes | Allowed values: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. |
| `merchantSplit` | string | Conditional | Merchant share. If supplied, must be an amount/percentage in two-decimal format and may be zero. |
| `partnersSplit` | array of objects | Conditional | Partner split details. Each entry is validated when supplied. |

The endpoint validates field format for split settlement details. Merchant/partner totals and partner eligibility may be enforced by downstream settlement configuration.

### `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `partnerId` | string | Yes | Non-empty partner/vendor id configured for the merchant. |
| `value` | string | Yes | Partner share in two-decimal amount/percentage format. May be zero by field validation. |

### `mutualFundDetails[]`

Use this only for merchants enabled for mutual fund or clearing corporation migration use cases.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `memberId` | string | Yes | Mutual fund member id. |
| `userId` | string | Yes | Mutual fund user/customer id. |
| `mfPartner` | string | Yes | Allowed values: `NSE`, `BSE`, `KFIN`, `CAMS`. |
| `investmentType` | string | Yes | Allowed values: `LUMPSUM`, `SIP`. |
| `orderNumber` | string | Yes | Mutual fund order number. Uses `merchantRequestId` validation: max 35 characters; letters, numbers, hyphen, dot, underscore. |
| `amount` | string | Yes | Mutual fund amount in two-decimal format. Must be greater than `0.00`. |
| `amcCode` | string | No | AMC code. |
| `folioNumber` | string | No | Investor folio number. |
| `ihNumber` | string | No | Internal holding/reference number. |
| `schemeCode` | string | No | Mutual fund scheme code. |
| `panNumber` | string | No | Investor PAN. Must be valid when supplied. |
| `applicationNumber` | string | No | Partner reference number, also known as ITRN. |

## Business Rules And Validation

Newton rejects the request when any of these conditions fail:

- Body validation fails for amount, dates, VPA, UMN, merchant request id, original ids, remarks, UDF JSON string, recurrence value, split settlement, mutual fund details, or sub-merchant details.
- `orgMandateId` plus `umn` already exists as a payee-side mandate for the resolved merchant.
- `merchantRequestId` already exists for a `PORT_IN` mandate action for the merchant customer id.
- `amount` exceeds the configured mandate creation amount limit for the interoperability purpose, merchant MCC, VPA, and verified/enhanced merchant configuration.
- `recurrencePattern` is `ONETIME`.
- `mandateStatus = SUCCESS` and either `pauseStart` or `pauseEnd` is present.
- `mandateStatus = PAUSE` and either pause date is missing, or the current time is not within the pause window.
- Dynamic VPA is enabled and `payeeVpa` is missing.
- Dynamic VPA plus `confirmVpaResolution` is enabled and `subMerchantDetails` is missing.
- Dynamic VPA is disabled and `payeeVpa` is supplied.
- `recurrenceRule` and `recurrenceValue` do not match the recurrence pattern.
- `validityEnd` is not after `validityStart`.
- `blockFund` does not match the configured one-block/multi-debit behavior for the internal interoperability purpose.

## Success Response

### Active Mandate Port-In Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "amountRule": "MAX",
    "blockFund": "false",
    "customerVpa": "rahul@examplebank",
    "gatewayMandateId": "2307011234567890123456789012345",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "mandateName": "Monthly subscription",
    "mandateTimestamp": "2026-07-02T12:30:00",
    "merchantChannelId": "MERCHANTCHANNEL",
    "merchantId": "MERCHANTID",
    "merchantRequestId": "PORTIN000001",
    "orgMandateId": "ORGMANDATE000001",
    "payerRevocable": "true",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "5",
    "refCategory": "00",
    "refUrl": "https://www.juspay.in",
    "remarks": "remarks",
    "validityEnd": "2027-07-01T23:59:59",
    "validityStart": "2026-07-01T00:00:01",
    "umn": "12345678901234567890123456789012@examplebank",
    "originalMerchantRequestId": "PORTIN000001"
  }
}
```

### Paused Mandate Port-In Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "250.00",
    "amountRule": "EXACT",
    "blockFund": "false",
    "customerVpa": "asha@examplebank",
    "gatewayMandateId": "2307011234567890123456789012399",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "mandateName": "Paused insurance mandate",
    "mandateTimestamp": "2026-07-02T12:35:00",
    "merchantChannelId": "MERCHANTCHANNEL",
    "merchantId": "MERCHANTID",
    "merchantRequestId": "PORTINPAUSE001",
    "orgMandateId": "ORGMANDATEPAUSE001",
    "payerRevocable": "true",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "10",
    "refCategory": "00",
    "refUrl": "https://www.juspay.in",
    "remarks": "Porting paused mandate",
    "validityEnd": "2027-01-01T23:59:59",
    "validityStart": "2026-01-01T00:00:01",
    "pauseStart": "2026/07/01",
    "pauseEnd": "2026/07/31",
    "umn": "12345678901234567890123456789098@examplebank",
    "originalMerchantRequestId": "PORTINPAUSE001"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable API response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Business response payload. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters`, when supplied. Omitted otherwise. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `amount` | string | Stored mandate amount formatted to two decimals. |
| `amountRule` | string | Stored mandate amount rule. |
| `blockFund` | string | Stored mandate block-fund flag as `"true"` or `"false"`. |
| `customerVpa` | string | Payer/customer VPA from the stored mandate. |
| `gatewayMandateId` | string | Newton-generated UPI request id for the port-in action. |
| `gatewayResponseCode` | string | Gateway/NPCI-style response code derived from mandate history status and NPCI response. |
| `gatewayResponseMessage` | string | Gateway/NPCI-style response message derived from mandate history. |
| `gatewayResponseStatus` | string | Gateway/NPCI-style status derived from mandate history. |
| `mandateName` | string | Stored mandate name. Omitted if absent in storage. |
| `mandateTimestamp` | string | Mandate creation timestamp in Newton's local timestamp format. |
| `merchantChannelId` | string | Master merchant channel id. |
| `merchantId` | string | Master merchant id. |
| `merchantRequestId` | string | Merchant request id sent for the port-in action. |
| `orgMandateId` | string | Stored original mandate id. |
| `payeeVpa` | string | Echoed only when `payeeVpa` was supplied in the request. |
| `payerRevocable` | string | Stored revocable flag as `"true"` or `"false"`. |
| `recurrencePattern` | string | Stored recurrence pattern. |
| `recurrenceRule` | string | Stored recurrence rule, when applicable. |
| `recurrenceValue` | string | Stored recurrence value, when applicable. |
| `refCategory` | string | Stored ref category, or Newton default when absent. |
| `refUrl` | string | Stored ref URL, or Newton default when absent. |
| `remarks` | string | Stored remarks, or Newton default `"remarks"` when absent. |
| `subMerchantChannelId` | string | Sub-merchant channel id when request resolved to a sub-merchant. |
| `subMerchantId` | string | Sub-merchant id when request resolved to a sub-merchant. |
| `validityEnd` | string | Stored validity end timestamp. |
| `validityStart` | string | Stored validity start timestamp. |
| `pauseStart` | string | Stored pause start from mandate transaction info, when applicable. |
| `pauseEnd` | string | Stored pause end from mandate transaction info, when applicable. |
| `mutualFundDetails` | array | Echo of request `mutualFundDetails`, when supplied. |
| `splitSettlementDetails` | object | Echo of request `splitSettlementDetails`, when supplied. |
| `umn` | string | Stored UPI mandate number. |
| `originalMerchantRequestId` | string | Stored mandate merchant request id. In this flow, this may reflect the port-in action id stored on the new mandate record. |

## Error Handling

Failure responses use the same transport rules as success responses. If the request fails after payload verification, the error is normally returned in the encrypted/signed response envelope. If the request fails before payload verification or signature validation, the HTTP status and envelope can vary by deployment and gateway layer. The decrypted error body follows the Newton error shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "validation message",
  "payload": null
}
```

### Validation Failure

Example: invalid amount format.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "amount regex match failed",
  "payload": null
}
```

Client handling: fix the request and retry with the same `merchantRequestId` only if Newton did not create a mandate. Validation failures occur before creation.

### Missing Or Invalid Encrypted/Signed Timestamp

Example: encrypted/signed payload sent without `iat`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "IAT is empty",
  "payload": null
}
```

Client handling: send a valid `iat` for JWE/JWS payloads and ensure clocks are synchronized.

### Authentication Or Signature Failure

Example: signature mismatch, missing required auth headers, invalid timestamp, or IP whitelist failure.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Client handling: do not retry unchanged. Check `x-merchant-id`, `x-merchant-channel-id`, sub-merchant headers, `x-timestamp`, `x-raw-body`, signature/checksum generation, public key/API key configuration, and whitelisted source IP.

### API Disabled Or Not Allowed For Merchant

When `portMandate` is present in the merchant `blockedApiNames`, or the merchant has an allowlist that does not include `portMandate`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

Client handling: contact Newton onboarding/support to enable the API for the merchant or sub-merchant.

### Dynamic VPA Configuration Failure

Example: dynamic VPA is enabled but `payeeVpa` is missing.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "payee vpa not found",
  "payload": null
}
```

Other dynamic VPA messages include:

- `sub merchant details not found`
- `payee vpa not allowed`

Client handling: align the request with merchant configuration. Send `payeeVpa` only for dynamic VPA merchants; send `subMerchantDetails` when confirm-VPA-resolution is enabled.

### Duplicate Original Mandate

Example: the same original mandate was already ported.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate with same orgMandateId already exists",
  "payload": null
}
```

Client handling: treat as non-retryable for the same `orgMandateId` and `umn`. Use mandate status/list APIs to reconcile the already-created mandate.

### Duplicate Port-In Action Request

Example: `merchantRequestId` already exists for a `PORT_IN` mandate action.

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST",
  "payload": null
}
```

Client handling: if this is a retry of the same original request after a network timeout, query mandate status/list using `orgMandateId`, `umn`, or stored references before sending a new request. If this is a different mandate, generate a new `merchantRequestId`.

### Amount Limit Breach

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Amount should be below or equals to 2000.0",
  "payload": null
}
```

The numeric limit is configuration-driven and can vary by merchant, MCC, VPA, verified merchant setup, IPO/FX/enhanced mandate configuration, and one-block/multi-debit purpose.

Client handling: do not retry unchanged. Lower the mandate amount or request the appropriate merchant configuration.

### Invalid Recurrence Or Validity

Example: `recurrencePattern` is `ONETIME`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Recurrence pattern cannot be ONETIME for interoperability mandate",
  "payload": null
}
```

Example: invalid recurrence rule/value.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "recurrenceValue and recurrenceRule are not valid",
  "payload": null
}
```

Some PSP deployments can return `debit-day and debit-rule is not valid` for the same recurrence failure.

Example: validity end is not after validity start.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "end-date should be more than start-date",
  "payload": null
}
```

Client handling: fix recurrence and validity fields. These are deterministic validation failures.

### Invalid Pause State

Example: active mandate sent with pause dates.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "pauseStart and pauseEnd is not allowed for mandateStatus",
  "payload": null
}
```

Example: paused mandate missing pause dates or current time outside the pause window.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "pauseStart and pauseEnd is invalid",
  "payload": null
}
```

Client handling: send pause dates only for `mandateStatus = PAUSE`, and make sure the current date is inside the pause window.

### Merchant, Sub-Merchant, Account, Or VPA Lookup Failure

These failures happen while resolving the merchant from headers, validating a sub-merchant, finding the default merchant account/account, decrypting the merchant VPA, or resolving a dynamic VPA. The exact message can vary by lookup helper and environment.

Typical decrypted body:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Merchant or account details not found",
  "payload": null
}
```

Client handling: verify merchant headers, sub-merchant onboarding, primary merchant account setup, and dynamic VPA assignment. Do not retry unchanged.

### Downstream NPCI/Gateway Failure

If the downstream mandate route or NPCI integration times out or returns an unusable response, Newton can return a service-unavailable style body. The timeout code suffix varies.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_YG",
  "responseMessage": "NPCI service is not reachable at the moment (YG)",
  "payload": null
}
```

Client handling: retry with the same `merchantRequestId` only after checking whether a mandate/history was created. If a retry returns `DUPLICATE_REQUEST`, reconcile using status/list APIs rather than creating a new port-in request immediately.

### Unexpected Error

Unexpected missing mandate, mandate history, storage, or transformation errors can surface as internal server errors.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling: retry only after a short backoff and reconciliation check. Escalate with `x-request-id`, `merchantRequestId`, `orgMandateId`, `umn`, and timestamp if the result remains unknown.

## Retry And Idempotency Guidance

- Use a unique `merchantRequestId` for each distinct port-in attempt.
- For network timeouts, 5xx responses, or downstream service-unavailable responses, first query/reconcile by `orgMandateId`, `umn`, or `merchantRequestId` before retrying.
- If retrying the exact same request after an unknown outcome, reuse the same `merchantRequestId`. A `DUPLICATE_REQUEST` response means Newton has already seen a matching port-in action; reconcile instead of generating a new id.
- Do not reuse the same `merchantRequestId` for a different original mandate.
- Do not retry deterministic validation, auth, API-disabled, IP-whitelist, amount-limit, recurrence, pause-state, or dynamic-VPA configuration failures without changing the request or merchant configuration.

## Source References

- Route declaration: [src/Newton/App/Routes/Core.hs:808](../../src/Newton/App/Routes/Core.hs:808)
- Route handler, payload verification, signature verification, and transformer call: [src/Newton/App/Routes/Core.hs:3027](../../src/Newton/App/Routes/Core.hs:3027)
- S2S route transformer and request validation: [src/Newton/Services/Transformer/ServerToServer/Core.hs:452](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:452)
- Public request and response types plus field validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs:5288](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:5288)
- S2S/core request and response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs:450](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:450)
- Core port mandate route and merchant/account/payee VPA lookup: [src/Newton/Product/Merchant/Mandate/PortMandate.hs:20](../../src/Newton/Product/Merchant/Mandate/PortMandate.hs:20)
- Internal Galileo port mandate payload mapping: [src/Newton/Utils/Transformers/Transformer1.hs:3270](../../src/Newton/Utils/Transformers/Transformer1.hs:3270)
- S2S success response mapping: [src/Newton/Utils/Transformers/Transformer1.hs:2154](../../src/Newton/Utils/Transformers/Transformer1.hs:2154)
- Port mandate business validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs:3140](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:3140)
- Dynamic VPA validation and duplicate action detection: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs:580](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:580)
- Recurrence, validity, purpose, and amount-limit helpers: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1143](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1143)
- Common field validators: [src/Newton/Validation/Common.hs:125](../../src/Newton/Validation/Common.hs:125)
- Envelope request/response variants: [src/Newton/Types/API/RequestBody.hs:48](../../src/Newton/Types/API/RequestBody.hs:48)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API enablement, timestamp, and IP whitelist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Shared success/error response constants: [src/Newton/Constants/APIErrorCode.hs:43](../../src/Newton/Constants/APIErrorCode.hs:43)
