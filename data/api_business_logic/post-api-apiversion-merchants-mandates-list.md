# List Mandates API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/list`

## Overview

List Mandates is a merchant server-to-server API for fetching UPI mandates linked to a merchant customer. Use it for mandate management screens, customer support lookup, reconciliation, scheduled polling, and back-office jobs that need the current or pending mandate state without asking the customer to open a UPI app.

The API returns stored mandate data from Newton. It does not initiate, execute, pause, revoke, or call NPCI while listing mandates. Payloads use the standard Newton S2S encrypted request and response envelope shared during onboarding. Examples below show decrypted business payloads for readability.

## Business Use Case

Use this API when the merchant backend needs to:

- Show all active, paused, completed, inactive, or pending mandates for a customer.
- Retrieve mandate identifiers such as `gatewayMandateId`, `orgMandateId`, `umn`, and `merchantRequestId` for later status, update, pause, execute, or reconciliation calls.
- Page through a customer's mandate history with `limit` and `offset`.
- Filter non-pending mandates by creation date.
- Fetch mandates across child apps for a P2M SDK parent merchant by sending `appIds`.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. It is also used during signature verification to resolve the Newton merchant-customer and customer records.
- `status`: The list category requested by the merchant. `PENDING` uses pending mandate-history rows; other statuses use mandate rows.
- `gatewayMandateId` and `orgMandateId`: Newton mandate UPI request id returned for each mandate. Use this as the mandate identifier for follow-up mandate APIs where applicable.
- `umn`: UPI mandate number, present after the mandate has one.

## Integration Flow

1. Merchant backend identifies the customer and the mandate state to list.
2. Merchant prepares the decrypted business payload with `merchantCustomerId`, `status`, and optional pagination or filters.
3. Merchant wraps the payload in the onboarded Newton S2S transport format, then signs and/or encrypts it as configured.
4. Merchant calls `POST /api/{apiVersion}/merchants/mandates/list`.
5. Newton decrypts/parses the request, validates the body, verifies merchant headers/signature/timestamp/IP/API access, and resolves the merchant customer.
6. Newton queries mandate storage:
   - `PENDING`: pending, non-self-initiated mandate-history rows that have not expired, joined with their original mandate.
   - Other statuses: mandate rows matching the resolved customer, status category, pagination, and date filters where supported by the configured storage mode.
7. Newton maps the records into the S2S list response, encrypts/signs the response as configured, and returns it to the merchant.
8. Merchant decrypts the response and stores the returned identifiers/statuses for reconciliation and follow-up calls.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/list
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. For this endpoint, versions greater than `1` enable multibank-style account id response behavior in product logic. |

### Headers, Auth, Encryption, and Signing

The route accepts `API.EncRequest ListMandateCoreRequest` and returns `API.EncResponse ListMandateS2SResponse`. The outer request/response may be encrypted JWE, signed JWS, or plain JSON depending on onboarding and environment; the decrypted business payload is the JSON shown in this guide.

Send the headers configured during onboarding:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | `application/json`. |
| `x-api-version` | Recommended | API version header used by shared S2S logic. New integrations should use the version shared during onboarding. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. Used to resolve the merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. Used with `x-merchant-id`. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows. |
| `x-sub-merchant-channel-id` | Conditional | Required only for onboarded sub-merchant flows. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payloads unless a non-production checksum bypass is configured. Signature is verified over merchant ids, timestamp, sub-merchant ids when present, and raw body. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness except for limited checksum-enabled non-production behavior. |
| `x-forwarded-for` | Conditional | Required when the merchant has configured `whitelistedIps`; the first IP must be in that list. |
| `Authorization` | As configured | Read by the authentication middleware when present. Use the value shared during onboarding. |

Encrypted or signed payloads must include `iat` inside the decrypted business payload. Newton validates `iat` as a timestamp before signature checks for signed/encrypted requests.

## Request

### Minimum Request

List active/ongoing mandates:

```json
{
  "merchantCustomerId": "CUST12345",
  "status": "ONGOING"
}
```

### Pending Mandates

Use `PENDING` to list pending create/update mandate requests that have not expired:

```json
{
  "merchantCustomerId": "CUST12345",
  "status": "PENDING",
  "limit": "20",
  "offset": "0",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Date-Filtered Mandates

Date filters apply to the non-pending mandate list path where the underlying storage query supports them. Dates are parsed as IST dates using the format `YYYY/M/D`; slash and hyphen date separators pass request validation, but the product parser expects slash-separated dates for filtering.

```json
{
  "merchantCustomerId": "CUST12345",
  "status": "ALL",
  "startDate": "2026/7/1",
  "endDate": "2026/7/31",
  "limit": "50",
  "offset": "0"
}
```

### P2M SDK Parent Merchant With App Filters

For a P2M SDK parent merchant, `appIds` can narrow the list to child app merchant ids. For non-parent merchants, Newton ignores `appIds` and lists mandates for the resolved `merchantCustomerId`.

```json
{
  "merchantCustomerId": "CUST12345",
  "status": "ONGOING",
  "appIds": [
    {
      "merchantId": "childMerchantA",
      "merchantChannelId": "APP_A"
    },
    {
      "merchantId": "childMerchantB",
      "merchantChannelId": "APP_B"
    }
  ],
  "limit": "20",
  "offset": "0"
}
```

### With UDF Metadata

`udfParameters` must be a JSON-object string. It is echoed in a successful response.

```json
{
  "merchantCustomerId": "CUST12345",
  "status": "PAUSED",
  "udfParameters": "{\"source\":\"support_console\",\"ticketId\":\"TCK123\"}"
}
```

## Field Reference

| Field | Type | Required | Default / Omitted Behavior | Validation and Rules | Description |
| --- | --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | 1 to 256 characters. Must match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. Also used by auth middleware to resolve merchant-customer and customer records. | Merchant's customer identifier. |
| `status` | string | Yes | No default. | Must be one of `PENDING`, `ONGOING`, `COMPLETED`, `PAUSED`, `INACTIVE`, `ALL`. | Mandate category to list. |
| `limit` | string | No | Defaults to `20`. Product logic caps it at configured `maxListMandateLimit`. | Must parse as a non-negative integer when supplied. | Page size. |
| `offset` | string | No | Defaults to `0`. | Must parse as a non-negative integer when supplied. | Number of matching rows to skip. |
| `appIds` | array of objects | No | For P2M SDK parent merchants, supplied app ids are resolved to child merchant-customer records. If omitted for a parent merchant, no child records are supplied and result scope follows the configured storage mode for the resolved customer/customer id. For non-parent merchants, ignored. | No field-level validation beyond JSON shape. | Optional child app merchant filters. |
| `startDate` | string | No | If omitted and `endDate` is present, the query has only an upper bound. If both dates are omitted, no date filter is applied. | Request validation accepts valid dates after replacing `/` with `-`. Product parsing expects `YYYY/M/D`. | Start date for non-pending mandate creation-date filtering. |
| `endDate` | string | No | If `startDate` is present and `endDate` is omitted, product logic defaults `endDate` to the current IST date and uses end-of-day. | Same date validation as `startDate`. | End date for non-pending mandate creation-date filtering. |
| `iat` | string | Conditional | No default. Required for signed/encrypted payload variants. | Must pass timestamp freshness validation for signed/encrypted requests. | Issued-at timestamp used by request verification. |
| `udfParameters` | string | No | Omitted from response when not sent. | Must be a JSON-object string and must not contain characters rejected by ``^[^/$-*!%~`]+$``. | Merchant-defined metadata echoed on success. |

### `status` Semantics

| Request `status` | Records returned |
| --- | --- |
| `PENDING` | Pending, non-self-initiated mandate-history rows whose expiry is greater than or equal to current time. Response status is `PENDING`. |
| `ONGOING` | Mandate rows with stored status `SUCCESS`. Response status is usually `SUCCESS`. |
| `COMPLETED` | Mandate rows with stored status `COMPLETED`. |
| `PAUSED` | Mandate rows with stored status `PAUSE`. |
| `INACTIVE` | Mandate rows with stored status `FAILURE`, `REVOKED`, `EXPIRED`, `DECLINED`, `TIMED_OUT`, `EXECUTE_REVOKE_PENDING`, `EXECUTE_REVOKE_INITIATED`, or `REVOKE_PENDING`. Revoke-like statuses are mapped to response status `REVOKED`. |
| `ALL` | No status predicate in the mandate query; returns all matching mandate rows subject to merchant-customer, date, pagination, and storage behavior. |

### `appIds[]`

| Field | Type | Required | Validation and Rules | Description |
| --- | --- | --- | --- | --- |
| `merchantId` | string | Yes | Parsed as text. | Child merchant id. |
| `merchantChannelId` | string | Yes | Parsed as text. | Child merchant channel id. |

## Pagination and Filtering

- `limit` and `offset` are string-encoded non-negative integers.
- If `limit` is omitted, Newton uses `20`.
- If `offset` is omitted, Newton uses `0`.
- `limit` is capped to the configured `maxListMandateLimit`; if you send a larger value, Newton silently uses the configured maximum.
- Results are returned newest first on the standard non-sharded mandate query path. Pending mandates are sorted by updated time in the sharded path before `limit` and `offset` are applied.
- `startDate` and `endDate` are only meaningful for the non-pending mandate list path. Pending mandates are filtered by pending-history expiry instead.
- `appIds` is a parent-merchant filter. For predictable parent-merchant results, send the child app ids you want to include.
- Delegate and IoT payment mandates are filtered out before the response is built.

## Success Response

The decrypted success body has this shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "merchant123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "mandates": [
      {
        "accountReferenceId": null,
        "amount": "500.00",
        "bankAccountUniqueId": "BAU123",
        "blockFund": "false",
        "currentBlockedAmount": null,
        "gatewayMandateId": "MANDATEUPI123",
        "gatewayReferenceId": "NPCIREF123",
        "gatewayResponseCode": "00",
        "gatewayResponseMessage": "Mandate is in active state",
        "gatewayResponseStatus": "SUCCESS",
        "initiatedBy": "PAYER",
        "mandateApprovalTimestamp": "2026-07-01T12:30:00+05:30",
        "mandateTimestamp": "2026-07-01T12:25:00+05:30",
        "mandateType": "CREATE",
        "merchantRequestId": "MANDATE_ORDER_123",
        "mandateName": "Monthly subscription",
        "orgMandateId": "MANDATEUPI123",
        "payeeMcc": "5411",
        "payeeName": "Example Merchant",
        "payeeVpa": "merchant@upi",
        "payerName": "Example Customer",
        "payerRevocable": "true",
        "payerVpa": "customer@upi",
        "recurrencePattern": "MONTHLY",
        "recurrenceRule": "ON",
        "recurrenceValue": "1",
        "refUrl": "https://merchant.example/mandates/MANDATE_ORDER_123",
        "remarks": "Monthly subscription",
        "role": "PAYER",
        "amountRule": "MAX",
        "shareToPayee": "true",
        "transactionType": "UPI_MANDATE",
        "umn": "UMN1234567890",
        "validityEnd": "2027-07-01",
        "validityStart": "2026-07-01",
        "nextExecutionDateStart": "2026-08-01T00:00:00+05:30",
        "nextExecutionDateEnd": "2026-08-01T23:59:59+05:30",
        "subMerchantId": "subMerchant123",
        "subMerchantChannelId": "SUBAPP"
      }
    ]
  },
  "udfParameters": "{\"source\":\"support_console\",\"ticketId\":\"TCK123\"}"
}
```

Fields whose value is `null` may be omitted by the encrypted response JSON serializer.

### Empty Result

No matching mandates is a successful response with an empty `mandates` array:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "merchant123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST_NO_MANDATES",
    "mandates": []
  }
}
```

### Pending Mandate Response

`PENDING` responses use pending-history fields for amount, expiry, request type, role, remarks, and gateway status, while mandate configuration fields come from the original mandate.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "merchant123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "mandates": [
      {
        "amount": "500.00",
        "blockFund": "false",
        "expiry": "2026-07-02T10:30:00+05:30",
        "gatewayMandateId": "PENDINGUPI123",
        "gatewayReferenceId": "NPCIREFPENDING123",
        "gatewayResponseCode": "01",
        "gatewayResponseMessage": "Create Mandate request is in pending state",
        "gatewayResponseStatus": "PENDING",
        "initiatedBy": "PAYER",
        "mandateApprovalTimestamp": null,
        "mandateTimestamp": "2026-07-02T10:00:00+05:30",
        "mandateType": "CREATE",
        "merchantRequestId": "MANDATE_ORDER_124",
        "mandateName": "Monthly subscription",
        "orgMandateId": "ORIGINALMANDATEUPI123",
        "payeeMcc": "5411",
        "payeeVpa": "merchant@upi",
        "payerRevocable": "true",
        "payerVpa": "customer@upi",
        "recurrencePattern": "MONTHLY",
        "refUrl": "",
        "remarks": "Monthly subscription",
        "role": "PAYER",
        "amountRule": "MAX",
        "shareToPayee": "true",
        "transactionType": "UPI_MANDATE",
        "validityEnd": "2027-07-01",
        "validityStart": "2026-07-01"
      }
    ]
  }
}
```

## Response Field Reference

### Top-Level Response

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for a successful list response. |
| `responseCode` | string | `SUCCESS` for a successful list response. |
| `responseMessage` | string | `SUCCESS` for a successful list response. |
| `payload` | object | List mandate payload. |
| `udfParameters` | string | Echoed from request when supplied. Omitted otherwise. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Newton merchant id from the merchant record. |
| `merchantChannelId` | string | Newton merchant channel id from the merchant record. |
| `merchantCustomerId` | string | The `merchantCustomerId` sent in the request. |
| `mandates` | array of objects | Matching mandates. Empty when no mandate matches. |

### `payload.mandates[]`

| Field | Type | Description |
| --- | --- | --- |
| `accountReferenceId` | string | Account reference id for non-multibank/non-ICICI flows when available. Not returned for merchant-scoped mandates or when `bankAccountUniqueId` is returned. |
| `amount` | string | Mandate amount formatted with two decimals. |
| `bankAccountUniqueId` | string | Returned for ICICI or multibank response behavior when stored in mandate transaction info. |
| `blockFund` | string | Boolean text, `true` or `false`, indicating whether mandate funds are blocked. |
| `currentBlockedAmount` | string | Current blocked amount with two decimals when present. |
| `expiry` | string | Pending mandate-history expiry timestamp. Present for `PENDING` list results; omitted for normal mandate rows. |
| `gatewayMandateId` | string | UPI request id of the mandate or pending mandate-history row. |
| `gatewayReferenceId` | string | Gateway/NPCI response id when available. |
| `gatewayResponseCode` | string | `01` for pending rows; otherwise derived from mandate status and NPCI response. Defaults include `00`, `JPMC`, `JPMD`, `JPMX`, `JPMP`, `JPMR`, and `JPNL`. |
| `gatewayResponseMessage` | string | Human-readable status message, for example `Mandate is in active state` or `Create Mandate request is in pending state`. |
| `gatewayResponseStatus` | string | Response status for the mandate. Revoke-like statuses are normalized to `REVOKED`; active mandates usually return `SUCCESS`; pending rows return `PENDING`. |
| `initiatedBy` | string | Initiator derived from mandate role and self-initiated flag. |
| `mandateApprovalTimestamp` | string | Approval timestamp from mandate transaction info when present. Null/omitted for pending rows. |
| `mandateTimestamp` | string | Mandate or pending-history creation timestamp. |
| `mandateType` | string | Stored mandate or mandate-history type, such as `CREATE` or `UPDATE`. |
| `merchantRequestId` | string | Merchant request id from stored transaction info when present. |
| `mandateName` | string | Mandate display name when present. |
| `orgMandateId` | string | Original mandate UPI request id. For normal mandate rows, this equals `gatewayMandateId`. |
| `pauseEnd` | string | Pause end date from mandate transaction info when present. |
| `pauseStart` | string | Pause start date from mandate transaction info when present. |
| `payeeMcc` | string | Payee MCC resolved from mandate data. |
| `payeeName` | string | Payee name when available for the mandate role. |
| `payeeVpa` | string | Payee VPA, preferring VPA stored inside payee info when available. |
| `payerName` | string | Payer name when available for the mandate role. |
| `payerRevocable` | string | Boolean text, `true` or `false`, indicating whether payer can revoke. |
| `payerVpa` | string | Payer VPA, preferring VPA stored inside payer info when available. |
| `purpose` | string | Purpose code only when merchant config `sendPurposeCodeInListMandates` is `true`. |
| `recurrencePattern` | string | Mandate recurrence pattern, for example `ONETIME`, `DAILY`, `WEEKLY`, `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, `YEARLY`, or values supported by the stored mandate enum. |
| `recurrenceRule` | string | Recurrence rule when present. |
| `recurrenceValue` | string | Recurrence value when present. |
| `refUrl` | string | Reference URL from mandate transaction info; defaults to an empty string when absent. |
| `remarks` | string | Mandate remarks; defaults to `remarks` when absent. |
| `role` | string | Mandate role from mandate or pending-history data, usually `PAYER` or `PAYEE`. |
| `amountRule` | string | Mandate amount rule, for example `MAX` or `EXACT`, as stored. |
| `shareToPayee` | string | Boolean text, `true` or `false`, indicating whether mandate details are shared to payee. |
| `transactionType` | string | Pay type from transaction info; defaults to `UPI_MANDATE`. |
| `umn` | string | UPI mandate number when present. |
| `validityEnd` | string | Mandate validity end date. |
| `validityStart` | string | Mandate validity start date. |
| `isMarkedSpam` | string | Present only for pending create responses when block/spam behavior is enabled and stored in payee info. Boolean text in lowercase. |
| `isVerifiedPayee` | string | Present only for pending create responses when stored in payee info. Boolean text in lowercase. |
| `nextExecutionDateStart` | string | For API versions greater than `0`, returned for `PAUSE` or `SUCCESS` mandates when Newton can calculate the next execution window. |
| `nextExecutionDateEnd` | string | End of the next execution window when calculated. |
| `subMerchantId` | string | Sub-merchant id from stored transaction info when present. |
| `subMerchantChannelId` | string | Sub-merchant channel id from stored transaction info when present. |

## Failure Responses and Client Handling

Failure responses use the same S2S response transport as success responses when the request reaches response wrapping. Some auth/envelope failures can be returned as plain encrypted-error envelopes or HTTP errors depending on deployment middleware. After decryption, use `status`, `responseCode`, and `responseMessage` as the source of truth.

### Validation Failure

Examples: missing required fields, invalid `status`, invalid date, negative/non-integer `limit` or `offset`, malformed `merchantCustomerId`, or invalid `udfParameters`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed \\\"ACTIVE\\\"\"",
  "payload": null
}
```

Client handling: fix the request. Do not retry unchanged. Use one of the documented status values and send pagination as non-negative integer strings.

### Missing or Invalid `iat`

Signed/encrypted requests without `iat`, or with a stale/invalid timestamp, fail before product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty",
  "payload": null
}
```

Client handling: generate a fresh timestamp and rebuild the encrypted/signed payload. Do not reuse old payloads.

### Authentication or Signature Failure

Examples: missing merchant headers, bad merchant id/channel id, missing `x-raw-body` in middleware, missing `x-timestamp`, missing `x-merchant-signature` for plain payloads, or signature mismatch.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Client handling: verify merchant headers, timestamp, raw body canonicalization, signing key, and signature algorithm configured during onboarding. Retrying the same bad signature will not help.

### API Disabled or Merchant Not Allowed

If merchant configuration blocks this API, or an inactive merchant/sub-merchant does not have it in `allowedApiNames`, Newton returns an unauthorized error with a concrete message.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

Client handling: contact Newton onboarding/support to enable `listMandateS2S` for the merchant or sub-merchant. Do not retry until configuration is fixed.

### IP Restriction Failure

If `whitelistedIps` is configured for the merchant, the first IP in `x-forwarded-for` must match.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Client handling: send traffic from an allowlisted egress IP and ensure `x-forwarded-for` is populated correctly by the gateway/proxy.

### Merchant Customer or Customer Lookup Failure

The auth middleware resolves the request `merchantCustomerId` under the authenticated merchant before product logic. If the merchant customer or linked customer is not found, the response is an invalid-data style failure.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "MerchantCustomer not found",
  "payload": null
}
```

Client handling: confirm that the customer was onboarded under the same merchant id/channel id and that the same merchant customer id is being used.

### Account Mapping Missing for Multibank Response

For ICICI/multibank-style responses, the mapper expects `bankAccountUniqueId` in stored mandate transaction info. If old data is missing it, mapping can fail.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid getMandateAccountIds-bankAccountUniqueId",
  "payload": null
}
```

Client handling: share the failing `merchantCustomerId`, status, and time window with Newton support. Retrying unchanged is unlikely to succeed unless the record/configuration is corrected.

### Storage or Unexpected Failure

Database/query failures or unexpected exceptions are returned as internal server errors.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling: retry with backoff for transient failures. If repeated, raise the Newton request id/time window to support.

### Downstream/Gateway Failures

This endpoint does not call NPCI or a payment gateway while listing mandates, so there is no live downstream authorization failure for the list call itself. Gateway/NPCI outcomes may appear inside each mandate's `gatewayResponseCode`, `gatewayResponseMessage`, and `gatewayResponseStatus` because they are mapped from stored mandate data.

Client handling: do not treat a successful API response containing a failed mandate status as a failed API call. Handle each mandate row according to its mandate status.

## Retry and Idempotency Guidance

List Mandates is read-only and has no idempotency key. It does not create or mutate mandates.

- Safe to retry on transport timeouts, HTTP 5xx, and decrypted `INTERNAL_SERVER_ERROR`.
- Use exponential backoff with jitter for retries.
- Do not retry unchanged for validation, auth/signature, API-disabled, IP allowlist, or lookup failures.
- Keep `limit` stable while paginating. Increase `offset` by the effective page size you requested, and stop when `mandates` is empty or fewer records than requested are returned.
- Because mandate state can change while paginating, reconciliation jobs should record the request time window and de-duplicate by `gatewayMandateId` or `orgMandateId`.
- Regenerate `x-timestamp`, `iat`, and signatures for each retry. Do not replay a stale signed/encrypted body.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:564)
- Route handler and auth call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3063)
- Request type and validation: [src/Newton/Product/Merchant/Mandate/Types.hs](../../src/Newton/Product/Merchant/Mandate/Types.hs:31)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:326)
- Product list route: [src/Newton/Product/Merchant/Mandate/ListMandate.hs](../../src/Newton/Product/Merchant/Mandate/ListMandate.hs:15)
- Mandate list business logic, defaults, filters, and pagination: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:610)
- Mandate status predicate mapping: [src/Newton/Storage/QueriesMiddleware/Mandate.hs](../../src/Newton/Storage/QueriesMiddleware/Mandate.hs:135)
- Pending mandate-history query: [src/Newton/Storage/QueriesMiddleware/MandateHistory.hs](../../src/Newton/Storage/QueriesMiddleware/MandateHistory.hs:342)
- Response builder: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2552)
- Response S2S mapper: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:90)
- S2S response type: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:233)
- Mandate response object type: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:934)
- Envelope request/response types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Signature, API enablement, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Common validation error helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Common error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
