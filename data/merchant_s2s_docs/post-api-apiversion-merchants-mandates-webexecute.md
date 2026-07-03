# Web Execute Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/webExecute`

## Overview

Web Execute Mandate is a server-to-server API used by a merchant backend to initiate a mandate execution collect request against an existing UPI mandate, or against an interoperable mandate where Newton can resolve the execution context from request data.

Use this API after the mandate has been created and approved. For scheduled recurring mandates, call the notify flow first when notification is required, then call `webExecute` to execute the notified cycle. The API creates or reuses a Newton merchant order, creates a transaction attempt, calls the mandate execution wrapper, and returns Newton's current gateway execution status in the response payload.

Payloads use the standard Newton S2S encrypted or signed request and response envelope. Examples in this guide show decrypted business payloads and decrypted business responses for readability.

## Business Use Case

Use `webExecute` when the merchant needs to:

- Debit a customer under an approved UPI mandate.
- Execute the first debit for an approved mandate after the required waiting period, when applicable.
- Execute recurring mandate cycles after a successful mandate notification.
- Execute `ASPRESENTED` mandates where the next valid notification may be selected by amount and time.
- Execute mandate interoperability flows where Newton does not already have the full mandate row but can build execution context from `orgMandateId`, payer data, purpose, sequence number, and recurrence pattern.
- Attach optional mutual fund details, split settlement details, sub-merchant information, or clearing corporation flags for enabled merchant use cases.

Do not use this API to create, update, pause, revoke, notify, or check a mandate. Those workflows have separate mandate APIs.

## Integration Flow

1. Merchant creates and receives approval for a UPI mandate.
2. For cycles that require advance notification, merchant calls the mandate notify API and stores the notification identifier or sequence number.
3. Merchant calls `webExecute` with a unique `merchantRequestId`, mandate identifier, amount, expiry, and optional execution metadata.
4. Newton unwraps the S2S envelope, resolves the merchant, validates signature/API access/IP allowlisting, and validates request fields.
5. Newton looks up the stored mandate using `originalMerchantRequestId` plus `umn`; for interoperability purpose codes it may proceed without a stored mandate if required request fields are present.
6. Newton validates mandate state, amount rules, expiry, pause state, notification state, recurrence timing, sequence number, and peak-hour rules.
7. Newton creates or updates the merchant order and transaction attempt, initiates the mandate execution, and returns a decrypted business response after the response envelope is unwrapped by the client.

Important identifiers:

- `merchantRequestId`: Merchant-generated idempotency/order reference for this execution attempt. Do not reuse it for a new execution.
- `upiRequestId`: UPI transaction id for this execution. If omitted, Newton generates one before product logic.
- `originalMerchantRequestId`: Merchant request id of the original mandate creation. Required for `x-api-version > 1`.
- `umn`: UPI Mandate Number of the approved mandate.
- `orgMandateId`: Original mandate UPI request id. Required for interoperability executions without a stored mandate.
- `notificationMerchantRequestId`: Merchant request id used for the notification cycle, when the execution must be tied to a specific notification.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/webExecute
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Path version configured for the merchant. `x-api-version > 1` requires `originalMerchantRequestId` in the decrypted request body. |

### Headers, Authentication, and Envelope

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. In production this is normally a Newton `EncRequest` envelope, not the decrypted business JSON shown below. |
| `x-api-version` | Recommended | API behavior version. New integrations should use the version shared during onboarding. |
| `x-merchant-id` | Yes for header-signature/plain mode | Merchant id assigned by Newton. |
| `x-merchant-channel-id` | Yes for header-signature/plain mode | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required for configured sub-merchant routing. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` where configured. |
| `x-merchant-checksum` or configured merchant signature header | Conditional | Required when the request is not already trusted through a signed/encrypted envelope. Signature is computed as configured during onboarding. |
| `x-timestamp` | Conditional | Required for header-signature/plain mode and validated for freshness. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured; the first IP must be allowed. |

The route request type is `EncRequest WebExecuteMandateRequest`. Depending on onboarding, the wire request can be:

- JWE encrypted payload containing a signed payload.
- JWS signed payload.
- Plain decrypted JSON payload accepted only where merchant configuration permits it and protected by merchant signature headers.

For signed or encrypted request bodies, include `iat` in the decrypted business payload. Newton validates the timestamp before business logic. The response is returned according to the merchant response strategy: JWS, JWE, or plain JSON with response signature headers. The JSON examples below are decrypted business bodies, not the exact wire envelope.

## Request

The examples show decrypted business payloads.

### Minimum Existing-Mandate Execution

Use this when Newton already has the mandate row and the execution can be identified by original mandate request id and UMN.

```json
{
  "merchantRequestId": "EXEC0000000001",
  "originalMerchantRequestId": "MANDATE0000000001",
  "umn": "8b4c6c77f3d145df9a11122334455667@upi",
  "collectRequestExpiryMinutes": "15",
  "amount": "100.00",
  "upiRequestId": "EXECUPI0000000001",
  "remarks": "Mandate debit",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Recurring Execution With Notification

Use this when a prior notify call created a notification for the cycle and your configuration requires notification lookup by merchant request id or sequence number.

```json
{
  "merchantRequestId": "EXEC0000000002",
  "originalMerchantRequestId": "MANDATE0000000001",
  "notificationMerchantRequestId": "NOTIFY0000000002",
  "umn": "8b4c6c77f3d145df9a11122334455667@upi",
  "collectRequestExpiryMinutes": "30",
  "amount": "499.00",
  "upiRequestId": "EXECUPI0000000002",
  "seqNumber": "2",
  "remarks": "Monthly mandate debit",
  "refUrl": "https://merchant.example/mandates/EXEC0000000002",
  "refCategory": "00",
  "retryEnabled": "true",
  "udfParameters": "{\"invoiceId\":\"INV-2026-07\"}",
  "iat": "2026-07-02T10:16:00+05:30"
}
```

### Interoperability Execution

Use this only when Newton has enabled mandate interoperability for your merchant and purpose code. If Newton does not find a local mandate row, it builds the resolved mandate from request fields.

```json
{
  "merchantRequestId": "EXECINTEROP0001",
  "originalMerchantRequestId": "MANDATEINTEROP0001",
  "umn": "9c5d7e88aabbccddeeff001122334455@upi",
  "collectRequestExpiryMinutes": "15",
  "amount": "250.00",
  "upiRequestId": "EXECINTEROPUPI001",
  "orgMandateId": "ORGMANDATEUPI000001",
  "payerVpa": "customer@okbank",
  "payerName": "Asha Sharma",
  "payeeVpa": "merchant@okbank",
  "seqNumber": "1",
  "recurrencePattern": "MONTHLY",
  "purpose": "14",
  "remarks": "Interop mandate debit",
  "iat": "2026-07-02T10:17:00+05:30"
}
```

### Dynamic VPA or Sub-Merchant Execution

Use this only for merchants enabled for dynamic VPA/sub-merchant execution. When sending account details inside `subMerchantDetails`, `accountNumber`, `ifsc`, and `accountType` must be supplied together.

```json
{
  "merchantRequestId": "EXECSUB0001",
  "originalMerchantRequestId": "MANDATESUB0001",
  "umn": "7f6e5d44aabbccddeeff778899001122@upi",
  "collectRequestExpiryMinutes": "15",
  "amount": "750.00",
  "upiRequestId": "EXECSUBUPI0001",
  "payeeVpa": "store123@okbank",
  "remarks": "Store mandate debit",
  "subMerchantDetails": {
    "name": "Example Store 123",
    "mcc": "5411",
    "brandName": "ExampleStore",
    "legalName": "Example Retail Private Limited",
    "franchise": "ExampleRetail",
    "merchantType": "SMALL",
    "ownershipType": "PRIVATE",
    "genre": "OFFLINE",
    "onboardingType": "AGGREGATOR",
    "mid": "MID12345",
    "sid": "SID12345",
    "tid": "TID12345"
  },
  "iat": "2026-07-02T10:18:00+05:30"
}
```

### Mutual Fund or Clearing Corporation Execution

Use this only when Newton has enabled mutual fund or clearing corporation processing for your merchant. The sum of `mutualFundDetails[].amount` must match the execution amount.

```json
{
  "merchantRequestId": "EXECMF0001",
  "originalMerchantRequestId": "MANDATEMF0001",
  "umn": "aa11bb22cc33dd44ee55ff6677889900@upi",
  "collectRequestExpiryMinutes": "15",
  "amount": "1000.00",
  "upiRequestId": "EXECMFUPI0001",
  "isClearingCorpRequest": true,
  "mutualFundDetails": [
    {
      "memberId": "MEM001",
      "userId": "USER001",
      "mfPartner": "NSE",
      "investmentType": "SIP",
      "orderNumber": "MFORDER0001",
      "amount": "1000.00",
      "panNumber": "ABCDE1234F",
      "applicationNumber": "ITRN000001"
    }
  ],
  "remarks": "SIP mandate debit",
  "iat": "2026-07-02T10:19:00+05:30"
}
```

### Split Settlement Execution

Use this only when split settlement is enabled for your merchant. For `AMOUNT`, the merchant split plus all partner splits must equal `amount`. For `PERCENTAGE`, the sum must equal `100.00`.

```json
{
  "merchantRequestId": "EXECSPLIT0001",
  "originalMerchantRequestId": "MANDATESPLIT0001",
  "umn": "bb22cc33dd44ee55ff6677889900aa11@upi",
  "collectRequestExpiryMinutes": "15",
  "amount": "1000.00",
  "upiRequestId": "EXECSPLITUPI001",
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
  "remarks": "Split settlement mandate debit",
  "iat": "2026-07-02T10:20:00+05:30"
}
```

## Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | 1 to 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore; must contain at least one alphanumeric character. Must not already be in a non-failed execution order state. | Merchant-generated idempotency/order reference for this execution attempt. |
| `originalMerchantRequestId` | string | Conditional | No default. | Same format as `merchantRequestId`. Required when `x-api-version > 1`. Required for interoperability when Newton has no stored mandate row. | Merchant request id from the original mandate creation. |
| `umn` | string | Yes | No default. | 34 to 70 characters and must match the UMN shape with 32 characters before `@`. | UPI Mandate Number. Used with `originalMerchantRequestId` to find the payee mandate. |
| `collectRequestExpiryMinutes` | string | Yes | No default. | Numeric string from `1` to `64800`. | Execution collect expiry in minutes. Newton converts this to an expiry timestamp by adding minutes to the current time. |
| `amount` | string | Yes | No default. | Two-decimal positive amount, for example `100.00`. Must satisfy stored mandate amount rule: exact amount for `EXACT`, up to mandate amount for `MAX`, and not above remaining blocked amount where applicable. | Execution amount. |
| `upiRequestId` | string | No | Newton generates a transaction id if omitted. | 1 to 35 alphanumeric characters when supplied. Must not already exist as a self-initiated transaction. | UPI transaction id for this execution; returned as `gatewayTransactionId`. |
| `refUrl` | string | No | No default. | Non-empty when supplied. | Merchant reference URL stored on the execution. |
| `refCategory` | string | No | No default. | Exactly 2 numeric characters. | UPI reference category. |
| `remarks` | string | No | Defaults to Newton's default remarks in execution request/response. | 1 to 255 characters. Must start, after optional spaces, with an alphanumeric or hyphen and then contain letters, numbers, spaces, or hyphen. | Customer/payment note for the execution. |
| `mutualFundDetails` | array of objects | Conditional | No default. | Each object is validated. Merchant must be enabled for mutual fund transactions. Total amount must match execution amount. Duplicate mutual fund rows for the same `upiRequestId` are rejected. | Mutual fund/SIP order details. |
| `retryEnabled` | string | No | Omitted behaves as `false`. | Parsed with Newton's boolean-text helper. Send `"true"` or `"false"`. | Stored in transaction/notification metadata to control downstream retry behavior where supported. |
| `iat` | string | Conditional | No default. | Required for signed/encrypted envelope freshness validation. | Issued-at timestamp used by S2S signature/envelope validation. |
| `udfParameters` | string | No | No default. | Must be a JSON-object string and must not contain restricted characters from the common UDF validator. | Merchant-defined metadata. Echoed in top-level response when supplied. |
| `notificationMerchantRequestId` | string | Conditional | No default. | Non-empty when supplied. Required when merchant configuration requires notification id lookup; otherwise used when present to find the exact notification. | Merchant request id of the notification cycle to execute. |
| `subMerchantDetails` | object | Conditional | No default. | Validated as described below. Required for some dynamic VPA/sub-merchant flows. | Sub-merchant metadata for aggregator/dynamic VPA processing. |
| `splitSettlementDetails` | object | No | No default. | Validated as described below. Split totals are checked against `amount` by shared split settlement validation. | Split settlement instruction for the execution order. |
| `isClearingCorpRequest` | boolean | No | Omit for normal execution. | Any present value changes some downstream error handling and notification-update behavior. | Marks clearing corporation execution handling. |
| `purpose` | string | Conditional | No default. | Exactly 2 uppercase alphanumeric characters. Required for interoperability flows where Newton cannot infer purpose from a stored mandate. Must not conflict with stored mandate purpose. | UPI purpose code. |
| `payerName` | string | Conditional | No default. | No direct format validator in this request type. Required for interoperability when no stored mandate row exists. | Payer display name used to build resolved mandate context. |
| `payeeVpa` | string | Conditional | Defaults internally to the merchant account VPA when resolving interoperability context and no payee VPA is supplied. | Valid VPA, 3 to 255 characters, `local@handle` shape. Required by dynamic VPA configuration when enabled. | Payee VPA for dynamic VPA/interoperability flows. |
| `payerVpa` | string | Conditional | No default. | Valid customer VPA, 3 to 255 characters, `local@handle` shape. Required for interoperability when no stored mandate row exists. | Payer VPA used to build resolved mandate context. |
| `seqNumber` | string | Conditional | For stored non-interoperability mandates, Newton may derive the sequence from the selected notification. For some skip-notification and interoperability cases, request value is used. | Non-negative integer string. Required for interoperability. If merchant config `seqNumberFromRequestBody` is enabled, request sequence must match notification sequence for non-interoperability flows. | Mandate execution sequence number. |
| `orgMandateId` | string | Conditional | No default. | 1 to 35 alphanumeric characters. Required for interoperability when no stored mandate row exists. | Original mandate UPI request id. |
| `recurrencePattern` | string enum | Conditional | For stored mandates, Newton uses the recurrence pattern from the mandate. | Required for interoperability when no stored mandate row exists. Allowed values: `ONETIME`, `DAILY`, `WEEKLY`, `FORTNIGHTLY`, `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, `YEARLY`, `ASPRESENTED`. | Mandate recurrence pattern. |

### Nested Object: `mutualFundDetails[]`

| Field | Type | Required | Validation and rules | Description |
| --- | --- | --- | --- | --- |
| `memberId` | string | Yes | No field-level validator beyond JSON parsing. | Mutual fund member id. |
| `userId` | string | Yes | No field-level validator beyond JSON parsing. | Mutual fund user/customer id. |
| `mfPartner` | string enum | Yes | `NSE`, `BSE`, `KFIN`, `CAMS`. | Mutual fund partner. |
| `investmentType` | string enum | Yes | `LUMPSUM`, `SIP`. | Investment type. |
| `orderNumber` | string | Yes | Same format as `merchantRequestId`: 1 to 35 characters with letters, numbers, hyphen, dot, underscore. | Mutual fund order number. |
| `amount` | string | Yes | Two-decimal positive amount. Total across all rows must match execution amount. | Mutual fund order amount. |
| `amcCode` | string | No | No direct validator. | AMC code. |
| `folioNumber` | string | No | No direct validator. | Investor folio number. |
| `ihNumber` | string | No | No direct validator. | Internal holding/reference number. |
| `schemeCode` | string | No | No direct validator. | Mutual fund scheme code. |
| `panNumber` | string | No | 10 uppercase alphanumeric characters. | Investor PAN. |
| `applicationNumber` | string | No | No direct validator. | Partner reference number/ITRN. |

### Nested Object: `subMerchantDetails`

| Field | Type | Required | Validation and rules | Description |
| --- | --- | --- | --- | --- |
| `name` | string | Yes | Non-empty. | Sub-merchant display name. |
| `accountNumber` | string | Conditional | Digits only, length at most 18. Required when either `ifsc` or `accountType` is sent. | Sub-merchant settlement account number. |
| `ifsc` | string | Conditional | 11 characters, `^[A-Z]{4}0[A-Z0-9]{6}$`. Required when `accountNumber` or `accountType` is sent. | Settlement account IFSC. |
| `bankName` | string | No | Non-empty when supplied. | Bank name. |
| `accountType` | string | Conditional | Non-empty. Required when `accountNumber` or `ifsc` is sent. | Settlement account type. |
| `bankIIN` | string | No | Numeric string, length at most 20. | Bank IIN/code. |
| `mcc` | string | Yes | Exactly 4 digits. | Sub-merchant MCC. |
| `brandName` | string | Yes | Alphanumeric, length 1 to 99. | Brand name. |
| `legalName` | string | Yes | Alphanumeric, length 1 to 99. | Legal name. |
| `franchise` | string | Yes | Alphanumeric, length 1 to 99. | Franchise/store-chain name. |
| `merchantType` | string enum | Yes | `SMALL`, `LARGE`. | Sub-merchant type. |
| `ownershipType` | string enum | Yes | `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. | Ownership category. |
| `genre` | string enum | Yes | `ONLINE`, `OFFLINE`. | Commerce channel. |
| `onboardingType` | string enum | Yes | `BANK`, `AGGREGATOR`. | Onboarding source. |
| `gstin` | string | No | Non-empty when supplied. | GSTIN. |
| `mid` | string | No | Alphanumeric, 1 to 20 characters. | Sub-merchant MID. |
| `sid` | string | No | Alphanumeric, 1 to 20 characters. | Sub-merchant SID. |
| `tid` | string | No | Alphanumeric, 1 to 20 characters. | Sub-merchant TID. |

### Nested Object: `splitSettlementDetails`

| Field | Type | Required | Validation and rules | Description |
| --- | --- | --- | --- | --- |
| `splitType` | string enum | Yes | `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. | Settlement split mode. |
| `merchantSplit` | string | Conditional | Amount/percentage format: 1 to 9 digits plus two decimals, for example `900.00`. Must be non-negative. Required for `AMOUNT` or `PERCENTAGE` if merchant receives a defined share. | Merchant share. |
| `partnersSplit` | array of objects | Conditional | Each row is validated. Required when partners receive a defined share. | Partner shares. |

For `AMOUNT`, all shares must total the execution `amount`. For `PERCENTAGE`, all shares must total `100.00`. For `DEFAULT` and `LATER`, do not send explicit split shares unless Newton has instructed otherwise.

### Nested Object: `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Validation and rules | Description |
| --- | --- | --- | --- | --- |
| `partnerId` | string | Yes | Non-empty. | Partner/vendor id configured for the merchant. |
| `value` | string | Yes | Amount/percentage format: 1 to 9 digits plus two decimals, non-negative. | Partner share. |

## Success Response

API-level success means Newton accepted the request and created or processed an execution attempt. The actual debit result is in `payload.gatewayResponseStatus`, not the top-level `status`.

### Successful Execution

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "EXEC0000000001",
    "payeeMcc": "5411",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "expiry": "2026-07-02 10:30:30",
    "amount": "100.00",
    "remarks": "Mandate debit",
    "refUrl": "https://merchant.example/mandates/EXEC0000000001",
    "refCategory": "00",
    "gatewayTransactionId": "EXECUPI0000000001",
    "orgMandateId": "MANDATEUPI0000000001",
    "originalMerchantRequestId": "MANDATE0000000001",
    "transactionTimestamp": "2026-07-02 10:15:30",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS"
  },
  "udfParameters": "{\"invoiceId\":\"INV-2026-07\"}"
}
```

### Pending Execution

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "EXEC0000000002",
    "payeeMcc": "5411",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "expiry": "2026-07-02 10:46:00",
    "amount": "499.00",
    "remarks": "Monthly mandate debit",
    "gatewayTransactionId": "EXECUPI0000000002",
    "orgMandateId": "MANDATEUPI0000000001",
    "originalMerchantRequestId": "MANDATE0000000001",
    "transactionTimestamp": "2026-07-02 10:16:00",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Collect request sent successfully",
    "gatewayResponseStatus": "PENDING"
  }
}
```

### Failed Execution Attempt Returned in Success Envelope

If the execution attempt is created but the gateway/transaction status is failed, Newton can still return top-level `SUCCESS` with failed gateway status.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "EXEC0000000003",
    "payeeMcc": "5411",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "expiry": "2026-07-02 10:47:00",
    "amount": "999.00",
    "remarks": "Mandate debit",
    "gatewayTransactionId": "EXECUPI0000000003",
    "orgMandateId": "MANDATEUPI0000000001",
    "originalMerchantRequestId": "MANDATE0000000001",
    "transactionTimestamp": "2026-07-02 10:17:00",
    "gatewayResponseCode": "JPNL",
    "gatewayResponseMessage": "FAILURE",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

### Response Field Reference

Top-level response:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. For accepted execution attempts this is `SUCCESS`. |
| `responseCode` | string | API-level response code. For accepted execution attempts this is `SUCCESS`. |
| `responseMessage` | string | API-level response message. |
| `payload` | object | Execution response payload. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. |

Payload:

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Newton merchant id. |
| `merchantChannelId` | string | Newton merchant channel id. |
| `merchantRequestId` | string | Execution `merchantRequestId` from the request. |
| `subMerchantId` | string | Present when a sub-merchant is resolved. |
| `subMerchantChannelId` | string | Present when a sub-merchant is resolved. |
| `payeeMcc` | string | MCC from the resolved mandate or merchant context. |
| `umn` | string | UMN from the request. |
| `expiry` | string | Execution collect expiry timestamp generated from `collectRequestExpiryMinutes`, when present on the created transaction. |
| `amount` | string | Executed amount formatted with two decimals. |
| `remarks` | string | Request remarks, or Newton default remarks when omitted. |
| `refUrl` | string | Request reference URL when supplied. |
| `refCategory` | string | Request reference category when supplied. |
| `gatewayTransactionId` | string | Execution UPI transaction id, from request `upiRequestId` or generated by Newton. |
| `orgMandateId` | string | Original mandate UPI request id from the resolved mandate. |
| `originalMerchantRequestId` | string | Original mandate merchant request id. Included when API version is greater than 0. |
| `transactionTimestamp` | string | Newton transaction creation timestamp. |
| `gatewayResponseCode` | string | Mapped execution result code: `00` for success, `01` for pending, or failure code from NPCI/gateway response with fallback `JPNL`. |
| `gatewayResponseMessage` | string | Mapped execution result message: `SUCCESS`, `Collect request sent successfully`, or failure message from NPCI/gateway response with fallback `FAILURE`. |
| `gatewayResponseStatus` | string | Execution status: `SUCCESS`, `PENDING`, or `FAILURE`. |
| `mutualFundDetails` | array | Echoed from request when supplied. |
| `splitSettlementDetails` | object | Split settlement details returned from the stored merchant order when applicable. |

## Failure Scenarios and Client Handling

Failure bodies are returned through the same response transport configured for the merchant. Depending on where the error occurs, the HTTP status may be `200`, `400`, `401`, or `500`, and the outer response may be encrypted/signed/plain. The examples below show the underlying decrypted JSON body.

| Scenario | Decrypted response body | Client handling |
| --- | --- | --- |
| Missing `originalMerchantRequestId` with `x-api-version > 1` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"originalMerchantRequestId not found","payload":null}` | Fix the request. Send the original mandate creation `merchantRequestId`. Do not retry unchanged. |
| Field validation failure, for example invalid amount format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"amount regex match failed","payload":null}` | Fix the field according to the validation table. |
| Invalid `collectRequestExpiryMinutes` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"value of collectRequestExpiryMinutes is not between 1 and 64800","payload":null}` | Send a numeric string from `1` to `64800`. |
| Invalid UMN | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"umn length is not between 34 and 70","payload":null}` | Correct the UMN stored from mandate creation/approval. |
| Invalid signature, missing signature, failed JWE decryption, or IP not whitelisted | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Do not retry blindly. Check keys, signature base string, timestamp, encrypted payload, merchant headers, and source IP allowlist. |
| API disabled, blocked, or not allowed for merchant/sub-merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED","payload":null}` | Ask Newton to enable `webExecuteMandate` or allow the API for the merchant/sub-merchant. |
| Stale or missing timestamp in signed/encrypted mode | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty","payload":null}` | Send a fresh `iat`/timestamp as required by the configured envelope mode. |
| Duplicate `upiRequestId` already used by a self-initiated transaction | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST","payload":null}` | Treat as duplicate. Reconcile the original `upiRequestId`; do not reuse it for a new execution. |
| Same `merchantRequestId` already has a pending execution | `{"status":"FAILURE","responseCode":"JPME","responseMessage":"EXECUTION_ALREADY_IN_PROGRESS","payload":null}` | Do not submit another execution with the same `merchantRequestId`. Query/reconcile status later. |
| Stored mandate not found for non-interoperability request | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mandate not present","payload":null}` | Verify `originalMerchantRequestId`, `umn`, merchant, and that the mandate was created as a payee mandate in Newton. |
| Interoperability request missing required fields | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Fileds missing in executeReqBody for mandate interoperability","payload":null}` | Supply `payerVpa`, `payerName`, `orgMandateId`, `originalMerchantRequestId`, `seqNumber`, and `recurrencePattern`. |
| Purpose code conflicts with stored mandate purpose | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid purpose code","payload":null}` | Use the stored mandate purpose or omit `purpose` for stored-mandate execution. |
| Mandate is completed | `{"status":"FAILURE","responseCode":"JPMC","responseMessage":"Mandate is already completed","payload":null}` | Terminal state. Do not retry execution; create a new mandate if business requires one. |
| Mandate is declined | `{"status":"FAILURE","responseCode":"JPMD","responseMessage":"Mandate is declined by payer","payload":null}` | Terminal state. Ask customer to authorize a new mandate if needed. |
| Mandate is expired | `{"status":"FAILURE","responseCode":"JPMX","responseMessage":"Mandate is expried due to no action by payer","payload":null}` | Terminal state. Do not retry; create a new mandate. |
| Mandate is pending | `{"status":"FAILURE","responseCode":"JPMW","responseMessage":"Invalid Operation , Mandate is in pending state","payload":null}` | Wait for mandate approval/failure callback or status reconciliation before execution. |
| Mandate is paused | `{"status":"FAILURE","responseCode":"JPMP","responseMessage":"Mandate is Paused","payload":null}` | Execute only after mandate is unpaused or outside the pause window. |
| Mandate is revoked | `{"status":"FAILURE","responseCode":"JPMR","responseMessage":"Mandate is revoked","payload":null}` | Terminal state. Do not retry. |
| Mandate inactive/dormant/timed out/failure | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mandate is inactive","payload":null}` | Do not execute; reconcile mandate state or create a new mandate. |
| Execution time outside mandate validity or recurrence window | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"executionTime is not valid","payload":null}` | Retry only when the execution date/time becomes valid. For recurring mandates, check cycle rules and notify timing. |
| Amount violates mandate amount rule | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid amount","payload":null}` | Send an amount matching `EXACT` or within `MAX` mandate rules. |
| Amount exceeds remaining blocked amount | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"execution amount is not valid","payload":null}` | Reduce amount or reconcile blocked amount. |
| Notification required but not found | `{"status":"FAILURE","responseCode":"JPEN","responseMessage":"Mandate execution notification not found","payload":null}` | Call notify first or pass the correct `notificationMerchantRequestId`/sequence. |
| Notification is not successful or amount does not match | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Notification is not SUCCESSful / Amount from the notification does not match","payload":null}` | Wait for notification success or execute with an amount matching the notification. |
| Merchant config requires `notificationMerchantRequestId` but it is absent | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"notificationMerchantRequestId is required but not found","payload":null}` | Send the notification merchant request id for the cycle. |
| Request `seqNumber` does not match selected notification sequence when sequence validation is enabled | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"invalid data","payload":null}` | Send the correct sequence number or omit it when Newton should derive it. |
| Mutual fund details supplied but merchant is not enabled | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Merchant is not enabled for mutual fund transactions","payload":null}` | Enable mutual fund use case with Newton or omit `mutualFundDetails`. |
| Mutual fund duplicate for the same `upiRequestId` | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST","payload":null}` | Reconcile the original execution. Do not resend with same `upiRequestId`. |
| Split settlement body invalid | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Split Type for Settlement Split","payload":null}` | Fix split type and split totals according to merchant split configuration. |
| Dynamic VPA/sub-merchant required fields missing | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"sub merchant details not found","payload":null}` | Send required `subMerchantDetails` and/or `payeeVpa` for the configured dynamic VPA flow. |
| Dynamic VPA payee missing or not allowed | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"payee vpa not found","payload":null}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"payee vpa not allowed","payload":null}` | Send a payee VPA assigned to the merchant/sub-merchant. |
| Peak-hour rate limiting blocks execution | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mandate execution blocked for peak hours","payload":null}` | Retry after the blocked window or ask Newton about merchant-specific peak-hour configuration. |
| NPCI/gateway timeout | `{"status":"FAILURE","responseCode":"GATEWAY_TIMEOUT","responseMessage":"Timed out from NPCI","payload":null}` | Treat status as unknown. Do not create a new execution immediately; reconcile by status/callback before retrying. |
| Downstream service unavailable | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"NPCI service is not reachable at the moment (NA)","payload":null}` | Retry with backoff only after checking whether an execution attempt was created. |
| Unexpected internal error | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Retry only if no order/transaction was created or after Newton/status reconciliation confirms it is safe. |

Validation errors may surface the concrete field-validation text in `responseMessage` with `BAD_REQUEST` or `INVALID_DATA`, depending on the layer that raised the error.

## Retry and Idempotency Guidance

- Use a unique `merchantRequestId` for each business execution attempt.
- Use a unique `upiRequestId` for each new execution transaction. If omitted, Newton generates one and returns it as `gatewayTransactionId`.
- Do not retry immediately with a new id after timeout or service-unavailable responses. First reconcile using execution status/callbacks, because the downstream call may have reached NPCI.
- If `gatewayResponseStatus` is `PENDING`, poll/reconcile using the appropriate mandate execution status flow rather than creating another execution.
- If you receive `DUPLICATE_REQUEST`, `JPME`, or an internal error after reusing an id, treat the request as non-idempotent for new execution purposes and reconcile the original ids.
- For business-rule failures such as invalid amount, invalid sequence, missing notification, paused mandate, expired mandate, or inactive mandate, fix the underlying state before retrying.
- `retryEnabled` controls downstream retry metadata where supported; it does not make the public API call idempotently retryable with the same identifiers.

## Source References

- Route type for `/webExecute`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:536)
- Route handler, envelope unwrap, signature verification, monitoring id, transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2937)
- Request, response, and field-validation types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2207)
- S2S transformer, API-version rule for `originalMerchantRequestId`: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:348)
- S2S request/response mapping and generated `upiRequestId`: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1230)
- Core product route, DB lookup, merchant order, transaction attempt, execution wrapper, response mapping: [src/Newton/Product/Merchant/Mandate/WebExecuteMandate.hs](../../src/Newton/Product/Merchant/Mandate/WebExecuteMandate.hs:33)
- Notification selection, mutual fund creation, dummy notification, skip-notification behavior: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:2150)
- Downstream execute wrapper and NPCI/service-unavailable error mapping: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:403)
- Mandate execution business rules and status/state validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:743)
- Interoperability validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:3181)
- Sequence and peak-hour validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2930)
- Resolved mandate mapping for stored and interoperability flows: [src/Newton/Utils/Transformers/Transformer3.hs](../../src/Newton/Utils/Transformers/Transformer3.hs:1142)
- Execute request creation and expiry calculation: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2422)
- Response payload mapping and gateway status mapping call: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2231)
- Gateway response status mapping: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:1581)
- Common field validation rules: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:575)
- S2S envelope request/response variants: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Signature/API access/IP allowlist middleware: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:90)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
