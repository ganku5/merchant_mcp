# Web Execute Cycle API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/webExecuteCycle`

## Overview

Web Execute Cycle is a server-to-server UPI mandate API used by a merchant backend to run a mandate debit cycle through Newton.

The API has two operational modes:

- Create/send an execution notification for a future debit cycle.
- Execute a debit cycle immediately, including the first execution flow when `firstCharge` is `"true"`.

Payloads use the standard Newton S2S encrypted or signed request and response envelope. JSON examples in this guide show the decrypted business payloads for readability.

Use this API after a mandate has already been created and the merchant has stored the mandate `umn`, original mandate creation `merchantRequestId`, and any cycle-level merchant references needed for reconciliation.

## Business Use Case

Web Execute Cycle helps merchants:

- Notify Newton/NPCI of a scheduled debit before the execution window.
- Execute the first debit for a newly authorized mandate when the first execution is still pending.
- Execute a later debit cycle for active recurring or as-presented mandates.
- Attach mutual fund order metadata to a mandate notification or execution when the merchant is configured for mutual fund processing.
- Reconcile a cycle using the cycle `merchantRequestId`, `orgMandateId`, `seqNumber`, and gateway response status.

This API does not create, update, pause, revoke, or delete the mandate itself. It operates on execution cycles for an existing mandate.

## Integration Flow

1. Merchant creates a UPI mandate through the mandate creation flow and stores `umn`, mandate creation `merchantRequestId`, and `orgMandateId` when returned by prior APIs.
2. For a scheduled cycle, merchant calls `webExecuteCycle` without `firstCharge` or with `firstCharge: "false"` to create the notification for the upcoming debit.
3. For first-charge execution, merchant calls `webExecuteCycle` with `firstCharge: "true"` after mandate authorization when Newton has not already recorded a first notification or first execution.
4. Newton decrypts and authenticates the S2S request, validates the business payload, loads the merchant context, and checks API enablement/IP/timestamp/signature rules.
5. Newton validates the mandate and cycle state:
   - For notification mode, it creates or reuses the notification and sends the notification to the downstream mandate notification flow.
   - For execution mode, it validates mandate status, amount, expiry, pause state, recurrence, notification eligibility, and merchant order idempotency, then starts the mandate execution flow.
6. Merchant decrypts the response and stores the returned `merchantRequestId`, `gatewayResponseStatus`, `gatewayResponseCode`, `orgMandateId`, and `seqNumber` when present.
7. Merchant uses callbacks or `webExecuteCycleStatus` for final reconciliation when the returned status is pending or when a network timeout prevents response handling.

Important identifiers:

| Identifier | Meaning |
| --- | --- |
| `umn` | Unique Mandate Number for the mandate being notified or executed. |
| `merchantRequestId` | Merchant-generated id for this cycle request. In notification mode it is the notification merchant request id. In execution mode it is the execution merchant order/request id. |
| `originalMerchantRequestId` | Optional original mandate creation `merchantRequestId`. Send it when your integration stores it; Newton also resolves by `umn`. |
| `orgMandateId` | Newton/UPI mandate identifier returned in the response payload. |
| `seqNumber` | Mandate execution sequence number. Present in notification-mode response; omitted in this API's immediate execution response wrapper. |

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/webExecuteCycle
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant, for example `v1` or the value shared during onboarding. The handler does not branch on this value. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-merchant-id` | Yes | Merchant id used to resolve the authenticated merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id used with `x-merchant-id`. |
| `x-sub-merchant-id` | Conditional | Required only for enabled sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Conditional | Required only for enabled sub-merchant integrations. |
| `x-timestamp` | Yes | Request timestamp used for freshness checks. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain S2S payloads unless a configured checksum bypass is active in a non-production environment. The signature is over merchant ids, timestamp, and raw body. |
| `Authorization` | Conditional | Present when required by the merchant's S2S transport setup. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. Newton validates the first IP in the comma-separated header. |
| `x-request-id` | No | Optional client request id for tracing. Newton generates one when omitted. |
| `x-session-id` | No | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

### Authentication, Encryption, and Signing

The route accepts the shared `EncRequest` transport shapes:

- Encrypted JWE request body.
- Signed JWS request body.
- Unsigned/plain business JSON only in explicitly configured environments or flows.

For encrypted or signed payloads, include `iat` in the decrypted business payload. Newton validates `iat` before signature verification. Plain unsigned payloads do not require `iat` at this middleware layer.

Merchant authorization checks include:

- Merchant lookup from `x-merchant-id` and `x-merchant-channel-id`.
- Optional sub-merchant lookup and validation.
- API blocked/allowed checks using merchant configuration.
- Signature verification for unsigned/plain payloads.
- JWS/JWE verification for signed or encrypted payloads during request body extraction.
- IP allow-list validation when `whitelistedIps` is configured.
- Request timestamp freshness validation using `x-timestamp`.

Responses are returned in the merchant's configured `EncResponse` shape. The response examples below are the decrypted JSON bodies.

## Request

Route request type: `API.EncRequest API.ExecuteCycleRequest`

Decrypted business payload type: `API.ExecuteCycleRequest`

### Notification Request

Use this form to create/send an execution notification. Omit `firstCharge` or send `"false"`.

```json
{
  "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
  "amount": "100.00",
  "mandateExecutionTimestamp": "2026-07-05T10:00:00+05:30",
  "merchantRequestId": "EXECYCLE-NOTIFY-001",
  "originalMerchantRequestId": "MANDATECREATE001",
  "firstCharge": "false",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Notification Request With UDF Parameters

`udfParameters` must be a JSON object encoded as a string.

```json
{
  "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
  "amount": "100.00",
  "mandateExecutionTimestamp": "2026-07-05T10:00:00+05:30",
  "merchantRequestId": "EXECYCLE-NOTIFY-002",
  "originalMerchantRequestId": "MANDATECREATE001",
  "udfParameters": "{\"invoiceId\":\"INV10001\",\"cycle\":\"2026-07\"}",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### First-Charge Execution Request

Use this form when the mandate's first execution is pending and Newton has not already recorded the first execution or first notification.

```json
{
  "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
  "amount": "100.00",
  "mandateExecutionTimestamp": "2026-07-02T10:20:00+05:30",
  "merchantRequestId": "EXECYCLE-FIRST-001",
  "originalMerchantRequestId": "MANDATECREATE001",
  "firstCharge": "true",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

Newton generates the downstream execution `upiRequestId` internally for this path and sets `collectRequestExpiryMinutes` from merchant configuration `mandateExecuteRequestExpiryMinutes`, defaulting to `"1440"` when not configured.

### Mutual Fund Notification Request

Use `mutualFundDetails` only when enabled for the merchant. Newton validates and creates mutual fund records before creating the mandate notification.

```json
{
  "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
  "amount": "2500.00",
  "mandateExecutionTimestamp": "2026-07-05T10:00:00+05:30",
  "merchantRequestId": "MF-EXECYCLE-001",
  "originalMerchantRequestId": "MANDATECREATE001",
  "mutualFundDetails": [
    {
      "memberId": "MEM001",
      "userId": "USER001",
      "mfPartner": "NSE",
      "investmentType": "SIP",
      "orderNumber": "MFORDER001",
      "amount": "2500.00",
      "amcCode": "AMC001",
      "folioNumber": "FOLIO123",
      "schemeCode": "SCHEME001",
      "panNumber": "ABCDE1234F",
      "applicationNumber": "ITRN12345"
    }
  ],
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Mutual Fund First-Charge Execution Request

The same `mutualFundDetails` shape can be supplied for the first-charge execution path when the merchant is configured for it.

```json
{
  "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
  "amount": "2500.00",
  "mandateExecutionTimestamp": "2026-07-02T10:20:00+05:30",
  "merchantRequestId": "MF-FIRST-EXEC-001",
  "originalMerchantRequestId": "MANDATECREATE001",
  "firstCharge": "true",
  "mutualFundDetails": [
    {
      "memberId": "MEM001",
      "userId": "USER001",
      "mfPartner": "BSE",
      "investmentType": "LUMPSUM",
      "orderNumber": "MFORDER002",
      "amount": "2500.00"
    }
  ],
  "iat": "2026-07-02T10:15:30+05:30"
}
```

## Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `umn` | string | Yes | No default. | 34 to 70 characters and must match `.{32}@.+`. The mandate is looked up with PAYEE role. | Unique Mandate Number of the mandate to notify or execute. |
| `amount` | string | Yes | No default. | Must match `^[0-9]+\\.[0-9][0-9]$` and be greater than `0.0`. Must satisfy mandate amount rules during execution. | Cycle amount in two-decimal format, for example `"100.00"`. |
| `mandateExecutionTimestamp` | string | Yes | No default. | Must parse as an IST timestamp, for example `2026-07-05T10:00:00+05:30`. Notification mode also validates that the execution time is in the configured notification window. | Intended execution timestamp for the cycle. |
| `merchantRequestId` | string | Yes | No default. | 1 to 35 characters; allowed pattern `^[-._]*([a-zA-Z0-9][-._]*)+$`. Must be unique for a new cycle. Duplicate handling depends on notification/execution state. | Merchant idempotency and reconciliation id for this cycle request. |
| `originalMerchantRequestId` | string | No | Omit when the mandate is resolved only by `umn`. | If supplied, same validation as `merchantRequestId`. Must belong to the same merchant and mandate. | Merchant request id used when creating the original mandate. |
| `firstCharge` | string | No | Omitted behaves like notification mode. | If supplied, must be `"true"` or `"false"` case-insensitively. `"true"` triggers immediate first-charge execution. `"false"` triggers notification mode and is rejected if the first execution has not yet been notified/executed. | Selects first-charge execution versus notification mode. |
| `mutualFundDetails` | array of objects | Conditional | No default. | Each item is validated as described below. Required only for merchants/configurations that mandate MF details. | Mutual fund order metadata associated with the cycle. |
| `udfParameters` | string | No | Echoed in success response when supplied; omitted otherwise. | Must be a string containing a JSON object and must not contain characters rejected by ``^[^/$-*!%~`]+$``. | Merchant-defined metadata. |
| `iat` | string | Conditional | No default. | Required for signed/encrypted S2S payloads and validated as a timestamp by middleware. | Issued-at timestamp used for request freshness/signature validation. |

### `mutualFundDetails[]`

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `memberId` | string | Yes | No default. | No additional validation in this request type. | Mutual fund member identifier. |
| `userId` | string | Yes | No default. | No additional validation in this request type. | Mutual fund user identifier. |
| `mfPartner` | string | Yes | No default. | Enum: `NSE`, `BSE`, `KFIN`, `CAMS`. | Mutual fund partner. |
| `investmentType` | string | Yes | No default. | Enum: `LUMPSUM`, `SIP`. | Investment type. |
| `orderNumber` | string | Yes | No default. | Same validation as `merchantRequestId`: 1 to 35 characters and `^[-._]*([a-zA-Z0-9][-._]*)+$`. | Mutual fund order number. |
| `amount` | string | Yes | No default. | Must be two-decimal amount greater than `0.0`. | Mutual fund order amount. |
| `amcCode` | string | No | Omitted when not applicable. | No additional validation in this request type. | AMC code. |
| `folioNumber` | string | No | Omitted when not applicable. | No additional validation in this request type. | Folio number. |
| `ihNumber` | string | No | Omitted when not applicable. | No additional validation in this request type. | IH number. |
| `schemeCode` | string | No | Omitted when not applicable. | No additional validation in this request type. | Scheme code. |
| `panNumber` | string | No | Omitted when not applicable. | Must pass PAN validation when supplied. | Investor PAN. |
| `applicationNumber` | string | No | Omitted when not applicable. | No additional validation in this request type. | Partner reference number, also called ITRN in code comments. |

## Mode and Business Rules

### Notification Mode

Notification mode is selected when `firstCharge` is omitted or is `"false"`.

Newton:

- Validates the decrypted request body.
- Finds the mandate by `umn` and PAYEE role.
- Creates mutual fund records when `mutualFundDetails` is present.
- Builds a core notification request with `retryEnabled: "true"`, no supplied downstream `upiRequestId`, and `initiatedByProcessTracker: false`.
- Sends the notification through the core mandate notification flow.
- Returns `nextExecution` and `seqNumber` from the notification response payload.

Duplicate behavior:

- If the same notification request already exists and its status is `SUCCESS` or `EXECUTED`, Newton can return the existing notification response.
- If a duplicate exists in an ineligible state for the current retry path, Newton can reject the request with `DUPLICATE_REQUEST`.

### First-Charge Execution Mode

First-charge execution mode is selected only when `firstCharge` is `"true"`.

Newton:

- Generates a downstream execution `upiRequestId`.
- Sets `collectRequestExpiryMinutes` from merchant configuration `mandateExecuteRequestExpiryMinutes`, defaulting to `"1440"`.
- Builds a core web-execute request with `retryEnabled: "true"`.
- Validates the mandate, merchant order, notification/sequence rules, and execution restrictions.
- Initiates the mandate execution.
- Returns an execution response payload without `nextExecution` and without `seqNumber` in this wrapper.

`firstCharge` state checks:

| Existing mandate state | Request `firstCharge` | Result |
| --- | --- | --- |
| Mandate `txnInfo.isExecutedOnce` is `true` | `"true"` | Rejected: `firstCharge cannot be true when mandate is already executed`. |
| First notification already exists | `"true"` | Rejected: `firstCharge cannot be true when first notification already exists`. |
| First execution is not yet present/notified | `"false"` | Rejected: `firstCharge must be true for first execution`. |
| First execution is not yet present/notified | omitted | Allowed by this specific first-charge validator; request proceeds through notification mode. |

### Execution Eligibility

During execution, Newton can reject the request when:

- The mandate is not found for the merchant/UMN.
- The mandate is not in a status that allows execution.
- The mandate amount rule, blocked amount, expiry, pause window, or recurrence date does not allow execution.
- A required notification is missing.
- The notification is not `SUCCESS`.
- The notification amount does not match the execution amount.
- Execution attempts for the notification exceed the configured retry count.
- A previous merchant order for the same `merchantRequestId` is still pending or already completed.
- The generated or supplied downstream UPI transaction id already exists.
- Mutual fund details are required for the merchant but not supplied.
- Peak-hour, sequence-number, interoperability, or dynamic-VPA validations fail for merchant-specific configurations.

## Success Response

Route response type: `RespHeaders (API.EncResponse API.ExecuteCycleResponse)`

Decrypted business response type: `API.ExecuteCycleResponse`

### Notification Success

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "EXECYCLE-NOTIFY-001",
    "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
    "nextExecution": "2026-07-05T10:00:00+05:30",
    "amount": "100.00",
    "orgMandateId": "MANDATE-UPI-001",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "seqNumber": "4"
  }
}
```

### First-Charge Execution Success

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "EXECYCLE-FIRST-001",
    "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
    "amount": "100.00",
    "orgMandateId": "MANDATE-UPI-001",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS"
  }
}
```

### Mutual Fund Success

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "MF-EXECYCLE-001",
    "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
    "nextExecution": "2026-07-05T10:00:00+05:30",
    "amount": "2500.00",
    "orgMandateId": "MANDATE-UPI-001",
    "mutualFundDetails": [
      {
        "memberId": "MEM001",
        "userId": "USER001",
        "mfPartner": "NSE",
        "investmentType": "SIP",
        "orderNumber": "MFORDER001",
        "amount": "2500.00",
        "amcCode": "AMC001",
        "folioNumber": "FOLIO123",
        "schemeCode": "SCHEME001",
        "panNumber": "ABCDE1234F",
        "applicationNumber": "ITRN12345"
      }
    ],
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "seqNumber": "5"
  },
  "udfParameters": "{\"invoiceId\":\"INV10001\",\"cycle\":\"2026-07\"}"
}
```

### Response Field Reference

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `status` | string | Yes | `SUCCESS` for a successful decrypted business response. |
| `responseCode` | string | Yes | `SUCCESS` for success. |
| `responseMessage` | string | Yes | `SUCCESS` for success. |
| `payload` | object | Yes | Cycle result payload. |
| `udfParameters` | string | No | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### `payload`

| Field | Type | Present | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Always | Merchant id. |
| `merchantChannelId` | string | Always | Merchant channel id. |
| `merchantRequestId` | string | Always | Cycle request id from the request or underlying core response. |
| `umn` | string | Always | UMN for the mandate. |
| `nextExecution` | string | Notification mode only | Next execution timestamp returned by the notification flow. Omitted for first-charge execution mode. |
| `amount` | string | Always | Cycle amount. |
| `orgMandateId` | string | Always | Original mandate id used by Newton/UPI systems. |
| `mutualFundDetails` | array of objects | When supplied | Echo of request `mutualFundDetails`. Omitted otherwise. |
| `gatewayResponseCode` | string | Always | Downstream/core response code. For success this is commonly `"00"`, but use the returned value. |
| `gatewayResponseMessage` | string | Always | Downstream/core response message. |
| `gatewayResponseStatus` | string | Always | Downstream/core response status such as `SUCCESS`, `PENDING`, or `FAILURE`. Treat non-success values as requiring reconciliation. |
| `seqNumber` | string | Notification mode only | Mandate notification sequence number. Omitted for first-charge execution response mapping. |

## Failure Responses and Client Handling

Failure responses use the same encrypted/signed response transport as success responses when the request reaches the response-wrapping layer. Some auth, malformed envelope, or routing failures may be returned as plain HTTP error bodies depending on deployment and where the failure occurs. The examples below show the underlying decrypted JSON shape used by Newton error helpers.

### Validation Failure

Request body validation failures are returned as `BAD_REQUEST` with the validation errors rendered in `responseMessage`.

Example: invalid `amount`, `umn`, `merchantRequestId`, `mandateExecutionTimestamp`, `firstCharge`, `udfParameters`, or mutual fund field.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "amount regex match failed"
}
```

Client handling: fix the payload. Do not retry unchanged.

### Invalid `firstCharge` State

If the request contradicts stored mandate/notification state, Newton returns `BAD_REQUEST`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "firstCharge cannot be true when mandate is already executed"
}
```

Other concrete messages from this route include:

- `firstCharge cannot be true when first notification already exists`
- `firstCharge must be true for first execution`

Client handling: reconcile the mandate using mandate status and `webExecuteCycleStatus`, then call the correct notification or execution flow.

### Authentication, Signature, Encryption, or Timestamp Failure

Missing merchant headers, missing raw body/timestamp, invalid signature, invalid `iat`, stale `x-timestamp`, failed JWS/JWE verification, or IP allow-list failures return an unauthorized or invalid-data style response.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

When signed/encrypted payloads omit `iat`, the middleware uses an invalid-data error:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Client handling: correct credentials, headers, clock sync, IP allow-list, encryption keys, and signing input. Do not retry rapidly without changing the bad auth input.

### API Disabled, Merchant Disabled, or API Not Allowed

If merchant configuration blocks this API or the merchant/sub-merchant is constrained by `allowedApiNames`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: contact Newton onboarding/operations to enable `webExecuteCycle` for the merchant or sub-merchant.

### Mandate or Notification Lookup Failure

When the mandate or required execution notification cannot be found, responses use `REQUEST_NOT_FOUND`, `INVALID_DATA`, or mandate-specific notification errors depending on the exact lookup.

Mandate not found during the route's first-charge validation:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

Required execution notification not found:

```json
{
  "status": "FAILURE",
  "responseCode": "JPEN",
  "responseMessage": "Mandate execution notification not found"
}
```

Client handling: verify `umn`, `originalMerchantRequestId`, merchant identity, notification timing, and whether a notification was required before execution.

### Duplicate or In-Progress Request

Duplicate notification/execution attempts can fail when an existing record is not safely reusable.

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST"
}
```

If an execution for the same merchant order is still pending:

```json
{
  "status": "FAILURE",
  "responseCode": "JPME",
  "responseMessage": "EXECUTION_ALREADY_IN_PROGRESS"
}
```

Client handling: do not create a new `merchantRequestId` blindly. First call `webExecuteCycleStatus` or wait for the callback/reconciliation result for the original id.

### Mandate State or Business-Rule Failure

Execution can fail because the mandate is paused, completed, declined, expired, outside recurrence dates, beyond allowed amount, missing required MF details, or otherwise not executable.

Examples:

```json
{
  "status": "FAILURE",
  "responseCode": "JPMP",
  "responseMessage": "Mandate is Paused"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "JPMC",
  "responseMessage": "Mandate is already completed"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Notification is not SUCCESSful / Amount from the notification does not match"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "mandateExecutionTimestamp is not in valid"
}
```

Client handling: treat these as business failures. Correct the cycle amount/timestamp, unpause or recreate the mandate if needed, or wait for the required notification state before executing.

### Execution Attempts Exceeded

When a notification has already been executed/retried more than the configured limit:

```json
{
  "status": "FAILURE",
  "responseCode": "JPEN",
  "responseMessage": "Mandate execution attempts exceeded"
}
```

Client handling: stop retrying this execution id and reconcile with Newton support/operations or create the next eligible cycle as per business rules.

### Downstream or Gateway Failure

If the request reaches the downstream mandate notification or execution flow, failures may be surfaced either as an error response or as a successful API wrapper with a non-success `payload.gatewayResponseStatus`, depending on the downstream/core response point.

Example transport-level service failure:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Example business response requiring reconciliation:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "EXECYCLE-FIRST-001",
    "umn": "2d68a1e7b4f6473995c7c7d52a15e4a7@upi",
    "amount": "100.00",
    "orgMandateId": "MANDATE-UPI-001",
    "gatewayResponseCode": "91",
    "gatewayResponseMessage": "Timed out from NPCI",
    "gatewayResponseStatus": "PENDING"
  }
}
```

Client handling: for `SERVICE_UNAVAILABLE`, `GATEWAY_TIMEOUT`, or `gatewayResponseStatus: "PENDING"`, use bounded retries and status reconciliation. Do not submit a different `merchantRequestId` until the original request is reconciled.

### Unexpected Error

Unexpected storage, transformer, or downstream failures return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with backoff only if the request is idempotent and you can reconcile by `merchantRequestId`. Escalate with `x-request-id`, `merchantRequestId`, `umn`, and timestamp if the error persists.

## Retry and Idempotency Guidance

- Use a unique `merchantRequestId` for each intended cycle.
- After a network timeout, retry with the same `merchantRequestId`, same `umn`, same amount, and same cycle semantics. Update `iat` and outer timestamp/signature as required by the S2S envelope.
- Do not retry a failed validation, auth, API-disabled, or business-rule response without correcting the cause.
- For notification mode, retrying the same successful notification can return the existing successful notification response; other duplicate states can return `DUPLICATE_REQUEST`.
- For execution mode, Newton checks existing merchant orders by `merchantRequestId`. A pending execution can return `EXECUTION_ALREADY_IN_PROGRESS`; a failed merchant order with the same amount can be retried by the core order helper.
- Treat `payload.gatewayResponseStatus = "PENDING"` as not final. Reconcile through callbacks or `webExecuteCycleStatus`.
- For `SERVICE_UNAVAILABLE`, `GATEWAY_TIMEOUT`, and unexpected 5xx-style failures, use bounded exponential backoff and stop once the cycle status is terminal.

## Source References

- Route type for `POST /api/{apiVersion}/merchants/mandates/webExecuteCycle`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:571)
- Route handler, request body extraction, signature verification, and product handoff: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3081)
- Server route wiring: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:304)
- Encrypted/signed request and response transport types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request body extraction and request/session id handling: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Merchant signature, API enablement, IP allow-list, and timestamp middleware: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- `ExecuteCycleRequest`, validation instance, response, and payload types: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:749)
- Execute-cycle route branching between web execute and notify: [src/Newton/Product/MerchantMandateV2.hs](../../src/Newton/Product/MerchantMandateV2.hs:304)
- First-charge state validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:237)
- Request validation helpers for `umn`, amount, timestamp, merchant request ids, booleans, and UDF parameters: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:215)
- Mutual fund detail type and validation: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:1047)
- Mutual fund enum values: [src/Newton/Types/Storage/MutualFund.hs](../../src/Newton/Types/Storage/MutualFund.hs:57)
- Web execute/notify request and response mapping for this API: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:1924)
- Core notification route and duplicate notification handling: [src/Newton/Product/Merchant/Mandate/NotifyMandate.hs](../../src/Newton/Product/Merchant/Mandate/NotifyMandate.hs:25)
- Core web execute route and merchant order execution flow: [src/Newton/Product/Merchant/Mandate/WebExecuteMandate.hs](../../src/Newton/Product/Merchant/Mandate/WebExecuteMandate.hs:33)
- Duplicate/in-progress merchant order and execution validation helpers: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:665)
- Notification creation, timestamp validation, and retry metadata: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1310)
- Execution notification lookup and eligibility helper: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:2139)
- Shared success and error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
