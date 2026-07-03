# Web Execute Cycle Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/webExecuteCycleStatus`

## Overview

Web Execute Cycle Status is a server-to-server reconciliation API for mandate execution cycles created through `webExecuteCycle`.

Use this API after calling `webExecuteCycle` to check where that cycle currently stands: notification pending or failed, notification succeeded but execution not yet initiated, execution pending, execution failed and retryable, execution failed finally, execution skipped, or execution completed successfully. Newton derives the response from the stored mandate notification, the latest matching mandate execution transaction, and, for pay-mode mandate executions, the merchant validation/intent record.

This API does not create a notification, debit a mandate, skip a cycle, or call NPCI/gateway directly. It reads Newton state and returns a merchant-facing status for the existing cycle.

## Business Use Case

Use Web Execute Cycle Status when the merchant backend needs to:

- Reconcile a scheduled mandate debit cycle after `webExecuteCycle`.
- Decide whether to wait, retry later, mark a cycle failed, or close the order as paid.
- Distinguish notification status from execution status.
- Distinguish pay-mode mandate intent status from collect-mode execution status.
- Retrieve optional notification and execution attempt history when enabled for the merchant.
- Store the mandate sequence number and execution identifiers for audit and support.

Important identifiers:

- `umn`: UPI mandate number for the mandate being executed.
- `merchantRequestId`: The merchant request id used for the `webExecuteCycle` notification cycle. Do not send the mandate creation request id unless it is also the execute-cycle request id.
- `orgMandateId`: Returned by this API as the mandate's UPI request id stored by Newton.
- `seqNumber`: Returned sequence number of the mandate notification cycle.

## Integration Flow

1. Merchant creates or ports a mandate and stores the returned `umn`.
2. Merchant calls `webExecuteCycle` for a scheduled debit cycle using a unique `merchantRequestId`.
3. Newton creates a mandate notification for that cycle, and may initiate execution depending on the cycle path and customer/UPI state.
4. Merchant calls `webExecuteCycleStatus` with the same `umn` and execute-cycle `merchantRequestId`.
5. Newton decrypts the request, verifies merchant authentication/signature, validates fields, loads the mandate, loads the notification, optionally loads merchant validation, loads the latest execution transaction or attempt history, and maps those records into the response.
6. Merchant stores `gatewayResponseStatus`, `notificationDetails.status`, `executionDetails.status`, `executionDetails.mandateIntentStatus`, `seqNumber`, and any attempt arrays for reconciliation.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/webExecuteCycleStatus
```

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope. Examples below show decrypted business payloads for readability.

## Headers, Auth, Encryption, and Signing

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-api-version` | Yes | API version shared during onboarding. The route path also contains `{apiVersion}`; keep both aligned with your integration contract. |
| `x-merchant-id` | Yes | Merchant id used to identify and authorize the merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id used with `x-merchant-id`. |
| `x-timestamp` | Yes | Timestamp used by signature/timestamp validation. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain payload integrations. The signature is calculated over merchant ids, optional sub-merchant ids, timestamp, and raw body using the merchant signature strategy. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. Newton validates the first IP in the comma-separated header. |
| `x-request-id` | No | Client-supplied request id. Newton generates one when omitted and returns it in response headers. |
| `x-session-id` | No | Client-supplied session id. Defaults to `x-request-id` when omitted. |
| `x-sub-merchant-id` | Conditional | Required only for onboarded sub-merchant flows where the parent merchant sends sub-merchant context. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` for sub-merchant flows. |

Envelope expectations:

- `EncRequest` accepts encrypted JWE, signed JWS, or unsigned payload shapes at the type level.
- S2S merchant integrations normally use the encrypted/signed envelope configured during onboarding.
- For encrypted or signed payloads, the decrypted/signed business payload must include `iat`; Newton validates it as a timestamp before product logic.
- For successful responses, Newton returns either an encrypted JWE response, signed JWS response, or unsigned response plus response signature, based on the merchant response signature strategy.
- Error responses may be returned before response encryption is possible, especially for malformed encrypted payloads, failed decryption, failed signature verification, missing headers, or merchant auth failures.

## Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Version segment in the URL, for example `4` if that is the version assigned to the merchant integration. |

## Request

### Minimum Status Lookup

```json
{
  "umn": "12345678901234567890123456789012@upi",
  "merchantRequestId": "EXECYCLE000123"
}
```

### Status Lookup With Merchant Metadata

`udfParameters` must be a JSON object serialized as a string. It is echoed in the successful response.

```json
{
  "umn": "12345678901234567890123456789012@upi",
  "merchantRequestId": "EXECYCLE000123",
  "udfParameters": "{\"cycleId\":\"CYCLE202607\",\"invoiceId\":\"INV8821\"}"
}
```

### Encrypted or Signed Payload With `iat`

Send `iat` when your request envelope is JWE or JWS. The value must pass Newton timestamp validation.

```json
{
  "umn": "12345678901234567890123456789012@upi",
  "merchantRequestId": "EXECYCLE000123",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

There are no additional request variants for this endpoint. The response variant is determined by the stored notification, execution transaction, and merchant configuration.

### Field Reference

| Field | Type | Required | Validation | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- | --- |
| `umn` | string | Yes | Length 34 to 70. Must match `.{32}@.+`. | No default. | UPI mandate number. Newton looks up a PAYEE mandate by this UMN. |
| `merchantRequestId` | string | Yes | Length 1 to 35. Allowed pattern: letters, numbers, hyphen, dot, underscore; must contain at least one letter or number. | No default. | Merchant request id of the execute cycle created through `webExecuteCycle`. Newton looks up the PAYEE notification for this mandate and request id. |
| `udfParameters` | string | No | Must be a JSON object encoded as a string. The text must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. | Omitted from the response when omitted. | Merchant-defined metadata for reconciliation. |
| `iat` | string | Conditional | Valid timestamp according to Newton timestamp validation. | Required for JWE/JWS payloads. Ignored for unsigned payload validation. | Issued-at timestamp used by request auth/replay checks. |

### Conditional Rules

- Send the same `merchantRequestId` that was used in `webExecuteCycle` for the cycle being reconciled.
- Send a UMN that belongs to a PAYEE mandate accessible to the authenticated merchant context.
- Send `iat` for encrypted or signed envelope payloads. Missing `iat` on JWE/JWS requests is rejected before product logic.
- If IP whitelisting is configured for the merchant, include `x-forwarded-for` and send the request from an allow-listed egress IP.
- If the merchant or sub-merchant has API allow-list restrictions, `webExecuteCycleStatus` must be included in the configured allowed APIs and must not be present in blocked APIs.

## Success Response

For a successful lookup, top-level `status` is `SUCCESS`. The business state is in `gatewayResponseStatus`, `notificationDetails.status`, `executionDetails.status`, and `executionDetails.mandateIntentStatus`.

### Notification Pending

Returned when the stored notification status is `PENDING`, `FAILURE_RETRY`, or `UNINITIATED`.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "01",
  "gatewayResponseStatus": "PENDING",
  "gatewayResponseMessage": "Mandate notification pending",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000123",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "PENDING"
  },
  "executionDetails": {
    "status": "UNINITIATED",
    "mandateIntentStatus": "N/A"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "3"
}
```

### Notification Failed

Returned when notification has failed and execution has not started.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "01",
  "gatewayResponseStatus": "FAILURE",
  "gatewayResponseMessage": "Mandate notification failed",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000123",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "FAILURE"
  },
  "executionDetails": {
    "status": "UNINITIATED",
    "mandateIntentStatus": "N/A"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "3"
}
```

### Collect Execution Successful

For collect-mode execution, `mandateIntentStatus` is `N/A`.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "00",
  "gatewayResponseStatus": "SUCCESS",
  "gatewayResponseMessage": "Mandate execution successful",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000123",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "SUCCESS"
  },
  "executionDetails": {
    "upiRequestId": "EXECUPIREQ000123",
    "upiResponseId": "NPCIRESP000123",
    "status": "SUCCESS",
    "mandateIntentStatus": "N/A",
    "amount": "100.00"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "3",
  "udfParameters": "{\"cycleId\":\"CYCLE202607\",\"invoiceId\":\"INV8821\"}"
}
```

### Pay Execution Successful

For pay-mode execution, `mandateIntentStatus` is `SUCCESS` after the mandate intent and execution are complete.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "00",
  "gatewayResponseStatus": "SUCCESS",
  "gatewayResponseMessage": "Mandate execution successful",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000124",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "SUCCESS"
  },
  "executionDetails": {
    "upiRequestId": "EXECUPIREQ000124",
    "upiResponseId": "NPCIRESP000124",
    "status": "SUCCESS",
    "mandateIntentStatus": "SUCCESS",
    "amount": "100.00"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "4"
}
```

### Execution Failure Retry Pending

When notification succeeded, an execution transaction failed, and configured execution retries remain, Newton returns `gatewayResponseStatus: "PENDING"` with `executionDetails.status: "FAILURE_RETRY"`. For pay-mode executions, `mandateIntentStatus` can be `PENDING` while the merchant validation has not expired.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "01",
  "gatewayResponseStatus": "PENDING",
  "gatewayResponseMessage": "Mandate execution pending",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000125",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "SUCCESS"
  },
  "executionDetails": {
    "upiRequestId": "EXECUPIREQ000125",
    "upiResponseId": "NPCIRESP000125",
    "status": "FAILURE_RETRY",
    "mandateIntentStatus": "PENDING",
    "amount": "100.00"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "5"
}
```

### Execution Failed Finally

When no configured retries remain, or the mandate intent has expired with no retry path left, Newton returns execution failure.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "01",
  "gatewayResponseStatus": "FAILURE",
  "gatewayResponseMessage": "Mandate execution failed",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000126",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "SUCCESS"
  },
  "executionDetails": {
    "upiRequestId": "EXECUPIREQ000126",
    "upiResponseId": "NPCIRESP000126",
    "status": "FAILURE",
    "mandateIntentStatus": "EXPIRED",
    "amount": "100.00"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "6"
}
```

### Execute Cycle Skipped

Returned when the notification was marked `SKIPPED`, for example after a successful `deleteExecuteCycle`.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "01",
  "gatewayResponseStatus": "SKIPPED",
  "gatewayResponseMessage": "ExecuteCycle is Skipped",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000127",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "SKIPPED"
  },
  "executionDetails": {
    "status": "UNINITIATED",
    "mandateIntentStatus": "N/A"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "7"
}
```

### Response With Attempt History

When merchant config `executeCycleAttemptHistory` is `true`, Newton includes up to 10 matching execution transactions in ascending order and all notification attempts for the notification. When disabled or absent, `notificationAttempts` and `executionAttempts` are omitted.

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "01",
  "gatewayResponseStatus": "PENDING",
  "gatewayResponseMessage": "Mandate execution pending",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000128",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "SUCCESS"
  },
  "executionDetails": {
    "upiRequestId": "EXECUPIREQ000128B",
    "upiResponseId": "NPCIRESP000128B",
    "status": "FAILURE_RETRY",
    "mandateIntentStatus": "N/A",
    "amount": "100.00"
  },
  "notificationAttempts": [
    {
      "attemptNumber": "1",
      "gatewayResponseStatus": "FAILURE",
      "gatewayResponseCode": "01",
      "gatewayResponseMessage": "Notification failed"
    },
    {
      "attemptNumber": "2",
      "gatewayResponseStatus": "SUCCESS",
      "gatewayResponseCode": "00",
      "gatewayResponseMessage": "Notification successful"
    }
  ],
  "executionAttempts": [
    {
      "attemptNumber": "1",
      "upiRequestId": "EXECUPIREQ000128A",
      "gatewayResponseStatus": "FAILURE",
      "gatewayResponseCode": "01",
      "gatewayResponseMessage": "Mandate execution failed"
    },
    {
      "attemptNumber": "2",
      "upiRequestId": "EXECUPIREQ000128B",
      "gatewayResponseStatus": "PENDING",
      "gatewayResponseCode": "01",
      "gatewayResponseMessage": "Mandate execution pending"
    }
  ],
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "8"
}
```

Attempt messages and codes are derived from stored notification attempt and transaction gateway details, so exact values can vary by gateway/PSP response.

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API lookup status. Successful lookups return `SUCCESS` even if the underlying mandate cycle is pending, failed, or skipped. |
| `gatewayResponseCode` | string | Merchant-facing status code derived from the cycle state. `00` is returned for successful execution; `01` is returned for pending, failed, and skipped cycle states. |
| `gatewayResponseStatus` | string | Overall cycle status. Possible values from this mapper are `SUCCESS`, `PENDING`, `FAILURE`, and `SKIPPED`. |
| `gatewayResponseMessage` | string | Overall cycle message: `Mandate notification pending`, `Mandate notification failed`, `ExecuteCycle is Skipped`, `Mandate execution successful`, `Mandate execution failed`, or `Mandate execution pending`. |
| `merchantId` | string | Authenticated merchant id. |
| `merchantRequestId` | string | Echoes the request's execute-cycle merchant request id. |
| `umn` | string | Echoes the request UMN. |
| `notificationDetails` | object | Notification status object. Present on successful lookups. |
| `executionDetails` | object | Execution status object. Present on successful lookups. |
| `notificationAttempts` | array | Present only when merchant config `executeCycleAttemptHistory` is enabled. |
| `executionAttempts` | array | Present only when merchant config `executeCycleAttemptHistory` is enabled. |
| `merchantChannelId` | string | Authenticated merchant channel id. |
| `orgMandateId` | string | Mandate UPI request id stored on the mandate. |
| `seqNumber` | string | Mandate notification sequence number for this cycle. |
| `udfParameters` | string | Echoes request `udfParameters` when supplied. |

#### `notificationDetails`

| Field | Type | Description |
| --- | --- | --- |
| `upiRequestId` | string | Currently omitted by the response builder for this endpoint. |
| `status` | string | Derived notification status. Values returned by the mapper: `PENDING`, `FAILURE`, `SKIPPED`, `SUCCESS`. |

#### `executionDetails`

| Field | Type | Description |
| --- | --- | --- |
| `upiRequestId` | string | Execution transaction UPI request id. Omitted when execution is `UNINITIATED`. |
| `upiResponseId` | string | Gateway/NPCI response id from the execution transaction when present. Omitted when execution is `UNINITIATED` or the transaction has no response id. |
| `status` | string | Derived execution status. Values include `UNINITIATED`, `PENDING`, `SUCCESS`, `FAILURE`, `FAILURE_RETRY`, and transaction status values stored by Newton. |
| `mandateIntentStatus` | string | Pay-mode mandate intent status. Values returned by this mapper include `N/A`, `PENDING`, `EXPIRED`, `SUCCESS`, and `SKIPPED`. Collect-mode executions normally return `N/A`. |
| `amount` | string | Execution transaction amount formatted with two decimal places. Omitted when execution is `UNINITIATED`. |

#### `notificationAttempts[]`

| Field | Type | Description |
| --- | --- | --- |
| `attemptNumber` | string | 1-based attempt index. |
| `gatewayResponseStatus` | string | Gateway/mapper status for that notification attempt. |
| `gatewayResponseCode` | string | Gateway/mapper code for that notification attempt. |
| `gatewayResponseMessage` | string | Gateway/mapper message for that notification attempt. |

#### `executionAttempts[]`

| Field | Type | Description |
| --- | --- | --- |
| `attemptNumber` | string | 1-based attempt index. |
| `upiRequestId` | string | Execution transaction UPI request id for the attempt. |
| `gatewayResponseStatus` | string | Gateway/mapper status for that execution transaction. |
| `gatewayResponseCode` | string | Gateway/mapper code for that execution transaction. |
| `gatewayResponseMessage` | string | Gateway/mapper message for that execution transaction. |

## Status Mapping

| Stored notification state | Stored execution / transaction state | Merchant validation / intent state | Response summary |
| --- | --- | --- | --- |
| `PENDING`, `FAILURE_RETRY`, `UNINITIATED` | Not used | Not used | `notificationDetails.status = "PENDING"`, `executionDetails.status = "UNINITIATED"`, `gatewayResponseStatus = "PENDING"`. |
| `FAILURE` | Not used | Not used | Notification failed, execution uninitiated, `gatewayResponseStatus = "FAILURE"`. |
| `SKIPPED` | Collect transaction exists | Not used | Notification and execution are `SKIPPED`, mandate intent is `N/A`. |
| `SKIPPED` | Pay transaction exists | Skipped | Notification, execution, and mandate intent are `SKIPPED`. |
| `SKIPPED` | No transaction | Not used | Notification skipped, execution uninitiated. |
| `SUCCESS` | Transaction status `FAILURE`, retries remain | No merchant validation or validation expired | Execution `FAILURE_RETRY`; mandate intent `N/A` or `EXPIRED`; overall status remains pending. |
| `SUCCESS` | Transaction status `FAILURE`, retries exhausted | Merchant validation pending or expired | Execution `FAILURE`; mandate intent `PENDING`, `EXPIRED`, or `N/A`; overall status failure. |
| `SUCCESS` | Transaction status other than `FAILURE` | Not used | Execution status mirrors the stored transaction status; overall success only when execution is `SUCCESS`. |
| `SUCCESS` | No transaction | Not used | Notification success, execution uninitiated, overall pending. |
| `EXECUTE_PENDING` | Collect transaction | Not used | Notification success, execution pending, mandate intent `N/A`. |
| `EXECUTE_PENDING` | Pay transaction | Pending | Notification success, execution pending, mandate intent pending. |
| `EXECUTED` | Collect transaction | Not used | Notification success, execution success, mandate intent `N/A`, overall success. |
| `EXECUTED` | Pay transaction | Success | Notification success, execution success, mandate intent success, overall success. |

If notification state is `EXECUTE_PENDING` or `EXECUTED` but no transaction is found, Newton logs the inconsistency and returns an internal error.

## Error Handling

Error transport can vary by failure layer and merchant envelope configuration. If Newton can authenticate and encrypt/sign the response, the error may arrive inside the configured response envelope. If the failure occurs before that point, the HTTP response can contain the plain error JSON.

The underlying decrypted error shape is:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchant request id regex failed\""
}
```

### Request Validation Failures

`validateRequestBody` returns HTTP 200 with `BAD_REQUEST` and a message containing the failing validation constructors.

Invalid `merchantRequestId` example:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchant request id regex failed\""
}
```

Invalid UMN example:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"umn length is not between 34 and 70\""
}
```

Invalid `udfParameters` example:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Client handling:

- Fix the payload. Do not retry unchanged.
- Ensure `merchantRequestId` is 1 to 35 characters and contains only letters, numbers, hyphen, dot, or underscore.
- Ensure `umn` is the full UMN value returned by mandate creation/porting.
- Send `udfParameters` as a JSON object string, not as a nested JSON object.

### Encryption, Decryption, Parsing, and Signature Failures

Malformed encrypted payloads can return HTTP 400 with `INVALID_DATA`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"cipherText\" not found"
}
```

Failed JWE decryption, invalid source validation, missing auth headers, missing `x-raw-body`, missing `x-timestamp`, signature mismatch, invalid IP, or invalid timestamp can return HTTP 401:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Missing or invalid `iat` on encrypted/signed payloads can return HTTP 200 with an invalid-data style response, or timestamp validation failure depending on environment configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Client handling:

- Rebuild the request envelope with the current key id and merchant keys.
- Include `iat` in the decrypted business payload for JWE/JWS requests.
- Include `x-timestamp`, `x-merchant-id`, `x-merchant-channel-id`, and the raw body/signature headers required by your onboarding mode.
- Use a fresh timestamp and check for clock skew before retrying.
- If IP whitelisting is enabled, send from an allow-listed egress IP and include `x-forwarded-for`.

### Merchant Config, API Disabled, or API Not Allowed

If the merchant's `blockedApiNames` contains this API, or an API allow-list exists and does not include this API, Newton returns HTTP 401 with:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If the merchant id/channel id cannot be resolved, the shared merchant lookup returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Merchant not found"
}
```

Client handling:

- Confirm the merchant and channel headers match the onboarded credentials.
- Ask Newton to enable `webExecuteCycleStatus` for the merchant or sub-merchant if API allow-listing is configured.
- Do not retry unchanged; this is a configuration or credential issue.

### Mandate Lookup Failure

If Newton cannot find a PAYEE mandate for the supplied UMN, it returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate not found"
}
```

Client handling:

- Verify that the UMN belongs to a mandate created/ported for the same merchant context.
- Do not use a customer VPA, mandate name, or `orgMandateId` in the `umn` field.
- Do not retry unchanged.

### Notification Lookup Failure

If the mandate exists but Newton cannot find a PAYEE mandate notification for the mandate id, execute-cycle `merchantRequestId`, and mandate UPI request id, it returns:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Mandate Notification Not Found"
}
```

Client handling:

- Ensure `merchantRequestId` is the `webExecuteCycle` request id for this execution cycle.
- If you need mandate-level status, use the mandate status API instead.
- Do not generate a new `merchantRequestId` for status checks.

### State Inconsistency or Missing Transaction

If notification status says execution is pending or executed but Newton cannot find the corresponding transaction, the status mapper returns an internal error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Retry after a short backoff with the same `umn` and `merchantRequestId`.
- If the error persists, contact Newton support with `x-request-id`, merchant ids, UMN, and `merchantRequestId`.

### Downstream or Gateway Failures

This status API does not call NPCI or a payment gateway directly. Gateway or PSP outcomes appear as stored attempt statuses in:

- `gatewayResponseStatus`
- `gatewayResponseMessage`
- `notificationAttempts[]`
- `executionAttempts[]`

For example, a previous execution failure can still produce a successful API lookup:

```json
{
  "status": "SUCCESS",
  "gatewayResponseCode": "01",
  "gatewayResponseStatus": "FAILURE",
  "gatewayResponseMessage": "Mandate execution failed",
  "merchantId": "MERCHANT001",
  "merchantRequestId": "EXECYCLE000126",
  "umn": "12345678901234567890123456789012@upi",
  "notificationDetails": {
    "status": "SUCCESS"
  },
  "executionDetails": {
    "upiRequestId": "EXECUPIREQ000126",
    "upiResponseId": "NPCIRESP000126",
    "status": "FAILURE",
    "mandateIntentStatus": "N/A",
    "amount": "100.00"
  },
  "merchantChannelId": "APP",
  "orgMandateId": "MANDATEUPIREQ000001",
  "seqNumber": "6"
}
```

Client handling:

- Treat `status: "SUCCESS"` as "status lookup succeeded", not as "mandate debit succeeded".
- Use `gatewayResponseStatus` and `executionDetails.status` to decide order state.
- For `PENDING` or `FAILURE_RETRY`, poll later with backoff.
- For final `FAILURE`, reconcile the failed debit and follow your business retry policy, usually by creating a new execute cycle when allowed.

### Unexpected Internal Errors

Database, Redis, keystore, response encryption/signing, or unexpected application failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Retry with the same payload after a short backoff.
- Use a fresh `iat` and timestamp for each retry.
- If the error persists, contact Newton support with response headers, `x-request-id`, merchant ids, UMN, and `merchantRequestId`.

## Retry and Idempotency Guidance

This API is read-only for the mandate cycle. It does not create a new notification or execution transaction, so retrying the same valid request is safe.

Recommended behavior:

- Use the same `umn` and execute-cycle `merchantRequestId` for every retry and poll attempt for a given cycle.
- Use a fresh `iat`, `x-timestamp`, and signature/envelope for every retry.
- Retry transport timeouts, HTTP 5xx, `INTERNAL_SERVER_ERROR`, and successful lookups with `gatewayResponseStatus: "PENDING"` using exponential backoff.
- Avoid high-frequency polling; the underlying notification and execution state is updated asynchronously by other flows.
- Do not retry validation, auth, API-disabled, mandate-not-found, or notification-not-found failures without correcting the request or configuration.
- Persist every terminal result. Treat `gatewayResponseStatus: "SUCCESS"` as paid/executed, `FAILURE` as terminal failed unless your Newton/business configuration allows a new cycle, and `SKIPPED` as intentionally cancelled/skipped.
- If `executionDetails.status` is `FAILURE_RETRY`, treat the cycle as not terminal yet; Newton may still create another execution attempt subject to configured retry limits.

## Source References

- Route definition for `POST /merchants/mandates/webExecuteCycleStatus`: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:578)
- Route handler, request decryption, signature verification, and product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3099)
- Server wiring: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:305)
- Encrypted request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request and response API types: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:892)
- Request validation instance: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:914)
- Common field validation rules for UMN, UDF, and merchant request id: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:246)
- Product status lookup flow: [src/Newton/Product/MerchantMandateV2.hs](../../src/Newton/Product/MerchantMandateV2.hs:325)
- Mandate lookup helper and `Mandate not found` error: [src/Newton/Storage/QueriesMiddleware/Mandate.hs](../../src/Newton/Storage/QueriesMiddleware/Mandate.hs:276)
- Notification lookup helper and `Mandate Notification Not Found` call site: [src/Newton/Product/MerchantMandateV2.hs](../../src/Newton/Product/MerchantMandateV2.hs:331)
- Transaction lookup for latest transaction or attempt history: [src/Newton/Storage/QueriesMiddleware/Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:1918)
- Attempt-history response builders: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2375)
- Execute-cycle status response builder: [src/Newton/Utils/Transformers/Transformer1.hs](../../src/Newton/Utils/Transformers/Transformer1.hs:2565)
- Status and gateway-response mapping: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4414)
- Request validation error helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Merchant signature, API allow/block, IP, and timestamp checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:57)
- S2S request decryption/parsing helper: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Response envelope/signing behavior: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Shared error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61)
