# Mandate Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/status`

## Overview

Mandate Status is a server-to-server API used by a merchant backend to fetch the latest known state of a UPI mandate or a specific mandate operation.

Use it after mandate creation, update, revoke, pause, unpause, completion, or execution-related flows when your system needs a deterministic status read for reconciliation, customer support, retry decisions, or callback recovery. The API can return either:

- The current mandate-level status, when you identify only the mandate.
- A specific mandate history/action status, when you also pass an action `merchantRequestId` or action `upiRequestId`.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

Mandate Status helps merchants:

- Confirm whether a mandate is active, pending, expired, declined, paused, revoked, completed, failed, or dormant.
- Reconcile Newton mandate records against merchant orders or mandate creation records.
- Recover from missed callbacks by polling the mandate state.
- Fetch the status of a specific mandate action such as update, revoke, pause, unpause, or completed history when the action id is known.
- Refresh pending mandate state. For pending mandates, Newton may perform a controlled status-check path against PSP/backoffice/NPCI subject to configured rate limits.
- Return mandate details needed for downstream reconciliation, including amount, UMN, validity dates, payer/payee VPAs, recurrence, account identifiers, gateway response fields, and optional TPV/account details.

## Integration Flow

1. Merchant creates or receives a mandate through the relevant mandate API or UPI flow.
2. Merchant stores at least one mandate identifier:
   - `orgMandateId`, Newton's mandate UPI request id.
   - `umn`, the UPI mandate number after it is available.
   - `originalMerchantRequestId`, the merchant request id used for mandate creation.
3. Merchant calls Mandate Status with `role` and one of the mandate identifiers.
4. Optionally, merchant passes `merchantRequestId` or `upiRequestId` to fetch a specific mandate action/history status.
5. Newton authenticates the merchant, validates the request, verifies API access and IP restrictions, resolves the mandate, optionally refreshes pending status, and maps the stored mandate/history into the response.
6. Merchant decrypts/verifies the response, stores the status fields, and decides whether to stop polling, retry later, or investigate a failure.

Important identifiers:

| Identifier | Meaning |
| --- | --- |
| `orgMandateId` | Newton mandate UPI request id. This is returned as `payload.orgMandateId` and usually also as `payload.gatewayMandateId` for mandate-level status. |
| `umn` | UPI mandate number. Usually available after successful mandate creation. |
| `originalMerchantRequestId` | Merchant request id used when the original mandate was created. |
| `merchantRequestId` | Merchant request id for a mandate action/history record. Use this only when checking a specific action. |
| `upiRequestId` | UPI request id for a mandate action/history record. Use this only when checking a specific action. The response echoes it as `payload.gatewayTransactionId`. |

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/status
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version segment in the route. New integrations should use the version assigned during onboarding. Response fields are version-gated as described below. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | Numeric API version used by response transformation. New integrations should use the latest onboarded S2S version. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. Used to resolve and authorize the merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. |
| `x-merchant-signature` | Conditional | Required for plaintext/unsigned request bodies. Signature verification uses merchant id, channel id, optional sub-merchant ids, timestamp, and raw body. For encrypted or JWS bodies, the encrypted/signed payload path is used. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness except in specific non-production checksum bypass modes. |
| `x-sub-merchant-id` | Conditional | Required only when acting as a configured sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required only when acting as a configured sub-merchant. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP in the comma-separated header must be whitelisted. |
| `Authorization` | Conditional | Read by signature middleware for some integrations. Use only when shared during onboarding. |

### Encryption, Signing, and Envelope

The route accepts `EncRequest MandateStatusRequest`. The outer wire body can be one of:

- Encrypted JWE-like body with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- Signed JWS-like body with `payload`, `signature`, and `protected`.
- Plain JSON business payload only where the merchant/integration is explicitly configured to allow it.

Encrypted or signed requests must include `iat` in the decrypted business payload. Newton validates this timestamp before running product logic. Responses use `EncResponse MandateStatusResponse`; on encrypted integrations the decrypted JSON shown below is wrapped in the encrypted response body.

## Request

### Minimum Mandate-Level Status By `orgMandateId`

```json
{
  "orgMandateId": "MND202407010001",
  "role": "PAYEE",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Mandate-Level Status By `umn`

```json
{
  "umn": "9f6d6a4c5b2e4a8d9c0f1a2b3c4d5e6f@upi",
  "role": "PAYER",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Mandate-Level Status By Original Merchant Request Id

```json
{
  "originalMerchantRequestId": "MANDATECREATE123",
  "role": "PAYEE",
  "iat": "2026-07-02T10:15:30+05:30",
  "udfParameters": "{\"source\":\"reconciliation\"}"
}
```

### Specific Action Status By Action Merchant Request Id

Use this variant when the mandate itself is identified by `orgMandateId`, `umn`, or `originalMerchantRequestId`, and you also want the status of a mandate action/history row.

```json
{
  "orgMandateId": "MND202407010001",
  "role": "PAYEE",
  "merchantRequestId": "MANDATEUPDATE123",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Specific Action Status By Action UPI Request Id

When both `merchantRequestId` and `upiRequestId` are sent, Newton uses `upiRequestId` to find mandate history.

```json
{
  "originalMerchantRequestId": "MANDATECREATE123",
  "role": "PAYEE",
  "upiRequestId": "UPIUPDATE202407010001",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `orgMandateId` | string | Conditional | No default. | If supplied, must be non-empty. At least one of `orgMandateId`, `umn`, or `originalMerchantRequestId` must be present. | Newton mandate UPI request id. Used as one of the primary mandate lookup keys. |
| `umn` | string | Conditional | No default. | If supplied, length must be 34 to 70 and match `.{32}@.+`. At least one primary mandate identifier must be present. | UPI mandate number. |
| `originalMerchantRequestId` | string | Conditional | No default. | If supplied, must be non-empty. At least one primary mandate identifier must be present. | Merchant request id used to create the original mandate. |
| `role` | string | Yes | No default. | Must parse as mandate role. Allowed values: `PAYEE`, `PAYER`. | Role of the caller with respect to the mandate. It is part of the lookup. |
| `merchantRequestId` | string | No | No default. | If supplied, must be non-empty. Used only for mandate history lookup. | Merchant request id of a specific mandate action. |
| `upiRequestId` | string | No | No default. | If supplied, must be non-empty. If present, it takes precedence over `merchantRequestId` for action/history lookup. | UPI request id of a specific mandate action. |
| `iat` | string | Conditional | No default. | Required for encrypted/signed requests; timestamp freshness is validated by middleware. Not required for explicitly allowed plaintext payloads. | Issued-at timestamp used by request authentication. |
| `udfParameters` | string | No | No default. Echoed in response if supplied. | Must be a JSON-object string and must not contain the characters blocked by the validation regex: `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. | Merchant-defined metadata. |

### Lookup Precedence

Mandate lookup uses the first available key in this order:

1. `originalMerchantRequestId`
2. `orgMandateId`
3. `umn`

Action/history lookup is applied only after the mandate is found:

1. If `upiRequestId` is present, Newton looks up mandate history by action UPI request id and mandate id.
2. If `merchantRequestId` is present and `upiRequestId` is absent, Newton looks up mandate history by action merchant request id, merchant customer id, and mandate id.
3. If neither is present, the response represents the mandate-level status.

If an action id is supplied but no matching mandate history is found, Newton treats it as a merchant-validation/lookup failure rather than silently returning the mandate-level status.

## Response

### Success Response: Mandate-Level Active Mandate

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "blockFund": "true",
    "gatewayMandateId": "MND202407010001",
    "gatewayReferenceId": "401234567890",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Mandate is in active state",
    "gatewayResponseStatus": "SUCCESS",
    "initiatedBy": "PAYEE",
    "mandateApprovalTimestamp": "2024-07-01 10:12:30",
    "mandateTimestamp": "2024-07-01 10:10:00",
    "mandateType": "CREATE",
    "merchantChannelId": "MERCHANTAPP",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "MANDATECREATE123",
    "mandateName": "Monthly subscription",
    "orgMandateId": "MND202407010001",
    "originalMerchantRequestId": "MANDATECREATE123",
    "payeeMcc": "5411",
    "payeeName": "Example Merchant",
    "payeeVpa": "merchant@upi",
    "payerName": "Customer Name",
    "payerRevocable": "true",
    "payerVpa": "customer@upi",
    "recurrencePattern": "MONTHLY",
    "recurrenceRule": "ON",
    "recurrenceValue": "5",
    "refUrl": "https://merchant.example/mandates/MANDATECREATE123",
    "remarks": "Monthly subscription",
    "role": "PAYEE",
    "amountRule": "MAX",
    "shareToPayee": "true",
    "transactionType": "UPI_MANDATE",
    "umn": "9f6d6a4c5b2e4a8d9c0f1a2b3c4d5e6f@upi",
    "validityEnd": "2027-07-01",
    "validityStart": "2024-07-01"
  },
  "udfParameters": "{\"source\":\"reconciliation\"}"
}
```

### Success Response: Specific Pending Action

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "150.00",
    "blockFund": "true",
    "gatewayMandateId": "UPIUPDATE202407010001",
    "gatewayTransactionId": "UPIUPDATE202407010001",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Mandate Action is in pending state",
    "gatewayResponseStatus": "PENDING",
    "initiatedBy": "PAYEE",
    "mandateTimestamp": "2024-07-01 10:10:00",
    "mandateType": "UPDATE",
    "merchantChannelId": "MERCHANTAPP",
    "merchantId": "MERCHANT001",
    "merchantRequestId": "MANDATEUPDATE123",
    "orgMandateId": "MND202407010001",
    "originalMerchantRequestId": "MANDATECREATE123",
    "payeeMcc": "5411",
    "payeeVpa": "merchant@upi",
    "payerRevocable": "true",
    "payerVpa": "customer@upi",
    "recurrencePattern": "MONTHLY",
    "refUrl": "https://merchant.example/mandates/MANDATECREATE123",
    "remarks": "Monthly subscription",
    "role": "PAYEE",
    "amountRule": "MAX",
    "shareToPayee": "true",
    "transactionType": "UPI_MANDATE",
    "validityEnd": "2027-07-01",
    "validityStart": "2024-07-01"
  }
}
```

### Response Envelope Notes

The decrypted business response has:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API wrapper status. Successful API execution returns `SUCCESS`, even if the mandate or mandate action status inside `payload.gatewayResponseStatus` is `PENDING`, `FAILURE`, `DECLINED`, `EXPIRED`, or another mandate state. |
| `responseCode` | string | API wrapper response code. Successful API execution returns `SUCCESS`. |
| `responseMessage` | string | API wrapper message. Successful API execution returns `SUCCESS`. |
| `payload` | object | Mandate status payload. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted when absent. |

For encrypted/JWS integrations, this decrypted body is carried inside the configured encrypted or signed response envelope. On failures raised before response encryption is available, the HTTP response may contain the common error body directly.

### Payload Field Reference

Optional fields are omitted from JSON when absent.

| Field | Type | Presence | Description |
| --- | --- | --- | --- |
| `accountReferenceId` | string | Optional | Account reference id returned by account lookup when available. For multibank-enabled merchants this may be omitted in favor of `bankAccountUniqueId`. |
| `amount` | string | Always | Mandate amount formatted with two decimals. If a mandate history row is returned, this is the history/action amount; otherwise it is the mandate amount. |
| `bankAccountUniqueId` | string | Optional | Bank account unique id returned for multibank-enabled response mapping when available. |
| `blockFund` | string | Always | Boolean mandate `blockFund` value rendered as text, for example `"true"` or `"false"`. |
| `currentBlockedAmount` | string | Optional | Current blocked amount formatted with two decimals when present on the mandate. |
| `expiry` | string | Optional | Mandate expiry timestamp. Returned only when the mandate is currently `PENDING` and expiry is present. |
| `gatewayMandateId` | string | Always | For mandate-level status, the mandate UPI request id. For action/history status, the mandate history UPI request id. |
| `gatewayPayerResponseCode` | string | Optional; API version > 2 | Payer response code parsed from mandate history NPCI response when present. |
| `gatewayReferenceId` | string | Optional | UPI response/reference id stored on the mandate. |
| `gatewayTransactionId` | string | Optional | Echoes request `upiRequestId`; present when the request checked a specific action by UPI request id. |
| `gatewayResponseCode` | string | Always | Gateway/business response code mapped from mandate or mandate history status and stored NPCI response. Common defaults include `00` for success, `01` for pending, `JPMX` for expired, `JPMD` for declined, `JPMR` for revoked, `JPMP` for paused, and `JPNL` for generic failure when no better NPCI code is stored. |
| `gatewayResponseMessage` | string | Always | Human-readable gateway/business message mapped from status and stored NPCI response. |
| `gatewayResponseStatus` | string | Always | Mandate-level status or action status. Mandate-level values follow stored mandate statuses such as `SUCCESS`, `PENDING`, `FAILURE`, `EXPIRED`, `DECLINED`, `PAUSE`, `REVOKED`, `COMPLETED`, `TIMED_OUT`, `DORMANT`, `EXECUTE_REVOKE_PENDING`, `EXECUTE_REVOKE_INITIATED`, `REVOKE_PENDING`, `FAILURE_TPV_REVOKE_PENDING`, and `BLOCKED_MCC_REVOKE_PENDING`. Action history statuses include `SUCCESS`, `PENDING`, `FAILURE`, `EXPIRED`, `DECLINED`; `PAUSE_ACTIVATED`, `PAUSE_COMPLETED`, and `TIMED_OUT` are returned as `SUCCESS`, `SUCCESS`, and `PENDING` respectively. |
| `initiatedBy` | string | Always | Derived from mandate role and self-initiated flag. Usually indicates `PAYER` or `PAYEE`. |
| `isExecutedOnce` | string | Optional | Returned only when merchant config enables mandate creation with auto first execution and the mandate stores `firstExecutionAmount`. |
| `mandateApprovalTimestamp` | string | Optional | Approval timestamp when it can be derived from mandate data. |
| `mandateTimestamp` | string | Always | Mandate creation timestamp. |
| `mandateType` | string | Always | `CREATE` when no history is requested; otherwise the mandate history type, for example `UPDATE`, `REVOKE`, `PAUSE`, `UNPAUSE`, `COMPLETED`, `DEACTIVATION`, `REACTIVATION`, `INTEROPERABILITY_UPDATE`, or `PORT_IN`. |
| `merchantChannelId` | string | Always | Merchant channel id from Newton merchant configuration. |
| `merchantCustomerId` | string | Optional | Merchant customer id. Returned when the mandate is tied to a merchant customer rather than merchant-level mandate ownership. |
| `merchantId` | string | Always | Merchant id from Newton merchant configuration. |
| `merchantRequestId` | string | Optional | Merchant request id stored in mandate or mandate history transaction info. For action status, this is the action's merchant request id when present. |
| `mandateName` | string | Optional | Mandate display name. |
| `orgMandateId` | string | Always | Original mandate UPI request id. |
| `originalMerchantRequestId` | string | Optional; API version > 1 | Merchant request id used to create the original mandate. |
| `pauseStart` | string | Optional | Pause start date/time. For `x-api-version > 0`, the transformer formats returned history pause dates as date strings. |
| `pauseEnd` | string | Optional | Pause end date/time. For `x-api-version > 0`, the transformer formats returned history pause dates as date strings. |
| `payeeIfsc` | string | Optional; API version > 3 | Payee IFSC when available from mandate data. |
| `payeeMcc` | string | Always | Payee MCC derived from mandate payee information. |
| `payeeName` | string | Optional | Payee name when available and allowed by role/data. |
| `payeeVpa` | string | Always | Payee VPA. If payee info stores a `vpa`, that value is used; otherwise the mandate payee VPA is used. |
| `payerName` | string | Optional | Payer name when available and allowed by role/data. |
| `payerRevocable` | string | Always | Boolean revocable flag rendered as text. |
| `payerVpa` | string | Always | Payer VPA. If payer info stores a `vpa`, that value is used; otherwise the mandate payer VPA is used. |
| `payerAccountHash` | string | Optional | Payer account hash derived for TPV/KYC merchants when payer account details and TPV type allow it. |
| `payerAccNum` | string | Optional | Payer account number. Returned only for create-status responses when the merchant feature flag `sendPayerAccountDetailsForMandate` is enabled. |
| `payerIfsc` | string | Optional | Payer IFSC. Returned only for create-status responses when the merchant feature flag `sendPayerAccountDetailsForMandate` is enabled. |
| `recurrencePattern` | string | Always | Mandate recurrence pattern, for example `ONETIME`, `DAILY`, `WEEKLY`, `FORTNIGHTLY`, `MONTHLY`, `BIMONTHLY`, `QUARTERLY`, `HALFYEARLY`, `YEARLY`, depending on stored mandate type support. |
| `recurrenceRule` | string | Optional | Recurrence rule, commonly `ON`, `BEFORE`, or `AFTER` when present. |
| `recurrenceValue` | string | Optional | Recurrence value when present. |
| `refUrl` | string | Always | Reference URL from mandate transaction info. If absent, Newton uses configured default NPCI `refUrl`. |
| `remarks` | string | Always | Mandate remarks. If absent, Newton uses its default remarks value. |
| `role` | string | Always | Mandate role stored on the mandate: `PAYEE` or `PAYER`. |
| `subMerchantChannelId` | string | Optional; API version > 1 | Sub-merchant channel id when request is processed for a sub-merchant. |
| `subMerchantId` | string | Optional; API version > 1 | Sub-merchant id when request is processed for a sub-merchant. |
| `amountRule` | string | Always | Mandate amount rule, such as `EXACT` or `MAX`. |
| `shareToPayee` | string | Always | Boolean `shareToPayee` value rendered as text. |
| `tpvValidationStatus` | string | Optional | TPV validation status derived from stored `tpvRefFailed` data when present. |
| `transactionType` | string | Always | Stored `payType` from mandate transaction info, or `UPI_MANDATE` when not stored. |
| `umn` | string | Optional | UPI mandate number. |
| `validityEnd` | string | Always | Validity end date. If history is returned, this is the history/action validity end; otherwise it is the mandate validity end. |
| `validityStart` | string | Always | Mandate validity start date. |
| `tpvType` | string | Optional | TPV type stored in mandate transaction info, for example `FULL` or `PARTIAL`. |

## Status Interpretation

Treat the response as two layers:

- Top-level `status = SUCCESS` means Newton processed your status request successfully.
- `payload.gatewayResponseStatus` is the mandate or mandate-action status you are asking about.

Recommended terminal handling:

| `payload.gatewayResponseStatus` | Client handling |
| --- | --- |
| `SUCCESS` | Mandate/action succeeded. Store the response and stop polling for this action. |
| `PENDING` | Mandate/action is still pending. Retry status later with backoff. Do not create a duplicate mandate/action solely because this API is pending. |
| `FAILURE`, `DECLINED`, `EXPIRED` | Treat the mandate/action as failed or not completed. Use `gatewayResponseCode` and `gatewayResponseMessage` for customer/support messaging and next action. |
| `PAUSE` | Mandate is paused. Do not initiate mandate execution until unpaused. |
| `REVOKED`, `EXECUTE_REVOKE_PENDING`, `EXECUTE_REVOKE_INITIATED`, `REVOKE_PENDING` | Mandate is revoked or in a revoke-related internal state. Stop mandate execution unless Newton explicitly confirms a recovery path. |
| `COMPLETED` | Mandate has completed. Stop future executions. |
| `DORMANT` | Mandate is inactive/dormant. Do not execute; investigate or re-initiate as per business process. |

## Failure Scenarios

Error responses are usually returned in the same encrypted/signed response transport as successful responses. After decryption, the common error shape is:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"OrgMandateId or UMN or originaMerchantRequestId should be present\""
}
```

Some authentication, encryption, and middleware failures can be returned as direct HTTP error bodies before the business response envelope is created. HTTP status may be `200`, `400`, `401`, or `500` depending on the layer. Always parse the response body when available.

### Validation Failures

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| Missing all primary mandate identifiers | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"OrgMandateId or UMN or originaMerchantRequestId should be present\""}` | Send one of `orgMandateId`, `umn`, or `originalMerchantRequestId`. Note the misspelling in the current response text. |
| `orgMandateId`, `originalMerchantRequestId`, `upiRequestId`, or `merchantRequestId` is present but empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"orgMandateId field is empty\""}` | Populate the field or omit it. |
| Invalid `umn` length | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"umn length is not between 34 and 70\""}` | Send the complete UMN. |
| Invalid `umn` format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"umn regex failed\""}` | Send a UMN with at least 32 characters before `@` and a suffix after `@`. |
| Invalid `role` enum or parse failure | Body can vary because `role` is parsed as a Haskell enum before Newton validation. | Use exactly `PAYEE` or `PAYER`. |
| Invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` | Send a JSON-object string such as `"{\"key\":\"value\"}"` and avoid blocked special characters. |
| Encrypted/signed request missing `iat` | Usually an error body from middleware such as `BAD_REQUEST` or another configured error wrapper. | Include `iat` in the decrypted payload for encrypted/signed requests. |
| Stale or invalid `iat` or `x-timestamp` | Usually `REQUEST_EXPIRED`, `BAD_REQUEST`, or `UNAUTHORIZED`, depending on which timestamp check fails. | Recreate the request with the current timestamp and a fresh signature/envelope. |

### Authentication, Signature, Encryption, and Access Failures

| Scenario | Example body | Client handling |
| --- | --- | --- |
| Missing merchant headers, invalid merchant id/channel id, missing raw body for signature verification, missing signature, or signature mismatch | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Verify merchant headers, signature base string, API key, timestamp, and exact raw JSON body used for signing. |
| API blocked or not allowed for the merchant/sub-merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Ask Newton to enable Mandate Status for the merchant/sub-merchant. For sub-merchants this maps to the `ALLOW_MANDATE_STATUS` feature. |
| IP whitelist configured but `x-forwarded-for` missing or first IP is not whitelisted | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Send requests only through whitelisted egress IPs and ensure the first forwarded IP is correct. |
| Encrypted payload cannot be decrypted, key id/public key/private key is unavailable, JWS cannot be verified, or response signing/encryption fails | Commonly `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` or `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` depending on the failing layer. | Check onboarding keys, `kid`, encryption algorithm, payload encoding, and whether keys are active. Escalate persistent server-side key errors. |

### Lookup and Business Failures

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| No mandate found for the supplied mandate identifier and role, but a merchant-validation record exists and is still pending | `{"status":"FAILURE","responseCode":"REQUEST_PENDING","responseMessage":"REQUEST_PENDING"}` | Treat original mandate creation/registration as still pending. Retry later with backoff. |
| No mandate found, but merchant-validation record exists and is expired | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` | Treat the original initiation as expired. Do not poll indefinitely. Start a new mandate flow if needed. |
| No mandate found, but merchant-validation record stores dropout/error data | `{"status":"FAILURE","responseCode":"DROPOUT","responseMessage":"U16-Customer exited before completing mandate authorization"}` | Treat as customer dropout or pre-mandate failure. Use the message for support/reconciliation. |
| No mandate or merchant-validation record found | `{"status":"FAILURE","responseCode":"REQUEST_NOT_FOUND","responseMessage":"REQUEST_NOT_FOUND"}` | Verify identifier, role, merchant id/channel id, and whether you are querying the correct environment. |
| Mandate belongs to another merchant | `{"status":"FAILURE","responseCode":"REQUEST_NOT_FOUND","responseMessage":"REQUEST_NOT_FOUND"}` | Do not retry unchanged. Correct merchant credentials or identifier. |
| Action `merchantRequestId` or `upiRequestId` supplied but no matching mandate history exists | Usually `{"status":"FAILURE","responseCode":"REQUEST_NOT_FOUND","responseMessage":"REQUEST_NOT_FOUND"}` or pending/expired/dropout if a merchant-validation record matches. | Verify that the action id belongs to this mandate. To fetch mandate-level status, omit action identifiers. |
| Delegate or IoT mandate purpose is blocked for this API path | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Delegate Mandate Operation Restricted"}` | Do not use this endpoint for restricted delegate/IoT mandate flows unless Newton enables a supported path. |

### Downstream and Unexpected Failures

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| Pending mandate status refresh calls PSP/backoffice/NPCI and downstream is unavailable or returns invalid status response | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_NA","responseMessage":"NPCI service is not reachable at the moment (NA)"}` | Retry with backoff. Do not assume the mandate failed. Preserve the prior known state until a successful status response or callback arrives. |
| Pending mandate status refresh returns a timeout code | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_U09","responseMessage":"NPCI service is not reachable at the moment (U09)"}` | Retry later. If repeated, reconcile through callbacks or support. The `U09` suffix is an example; Newton uses the downstream timeout code returned for the failed refresh. |
| Database, cache, key, encryption, or unexpected server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry with backoff for transient failures. Escalate if repeated with the same identifiers. |

## Retry and Idempotency Guidance

Mandate Status is a read/status API. Retrying the same request does not create a new mandate or mandate action.

Recommended retry behavior:

- For authentication, signature, validation, API-disabled, IP restriction, and malformed identifier errors, do not retry unchanged. Fix the request or merchant configuration first.
- For `REQUEST_PENDING` or `payload.gatewayResponseStatus = "PENDING"`, retry with exponential backoff. Avoid high-frequency polling because pending mandates can trigger rate-limited status-check logic.
- For `SERVICE_UNAVAILABLE_*`, network timeouts, and `INTERNAL_SERVER_ERROR`, retry with backoff and jitter.
- For terminal mandate statuses such as `SUCCESS`, `FAILURE`, `DECLINED`, `EXPIRED`, `REVOKED`, `COMPLETED`, or `DORMANT`, stop polling that action unless your support process explicitly requires a later reconciliation check.
- Keep using the same identifiers for the same status question. Do not generate a new mandate or action id to poll an existing mandate.

Suggested polling pattern for pending states:

1. Retry after a short delay, for example 30 to 60 seconds.
2. Increase delay up to a few minutes for long-pending mandates.
3. Stop or move to manual reconciliation after your business SLA or mandate expiry.
4. Prefer callbacks as the primary source of final state when available; use this API for recovery and reconciliation.

## Source References

- Route definition for `POST /merchants/mandates/status`: [Core.hs](../../src/Newton/App/Routes/Core.hs:559)
- Route handler, request decryption, signature verification, monitoring, transformer call: [Core.hs](../../src/Newton/App/Routes/Core.hs:3045)
- S2S transformer validation, merchant/sub-merchant selection, multibank flag, response shaping: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:459)
- Request type and validation rules: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:514)
- Response and payload types: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:563)
- Core request mapping and API-version response gating: [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:481)
- Product lookup and mandate/action history logic: [MandateStatus.hs](../../src/Newton/Product/Merchant/Mandate/MandateStatus.hs:25)
- Mandate lookup precedence: [Mandate.hs](../../src/Newton/Storage/QueriesMiddleware/Mandate.hs:213)
- Mandate history filters for action lookup: [MandateHistory.hs](../../src/Newton/Storage/QueriesMiddleware/MandateHistory.hs:55)
- Pending mandate status-check wrapper and downstream error handling: [MandateHelper.hs](../../src/Newton/Utils/BusinessLogic/MandateHelper.hs:74)
- Response field mapping: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:5049)
- Gateway response code/message mappings: [Utils.hs](../../src/Newton/Utils/Utils.hs:1533)
- Mandate roles and statuses: [Mandate.hs](../../src/Newton/Types/Storage/Mandate.hs:95)
- Mandate history types and statuses: [MandateHistory.hs](../../src/Newton/Types/Storage/MandateHistory.hs:73)
- Shared request/response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Request body verification path: [Routes.hs](../../src/Newton/Utils/Routes.hs:40) and [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, timestamp, API access, and IP whitelist checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- API blocked/not-allowed behavior: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:200)
- Sub-merchant `ALLOW_MANDATE_STATUS` feature mapping: [Helper.hs](../../src/Newton/Product/Merchant/SubMerchant/Helper.hs:250)
- Validation helper messages: [Common.hs](../../src/Newton/Validation/Common.hs:168)
- Validation failure response construction: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Common error response bodies: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:25)
