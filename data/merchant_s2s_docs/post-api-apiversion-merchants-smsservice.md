# SMS Service API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/smsService`

## Overview

SMS Service is a server-to-server API used to initiate or retry debit SMS notifications through Newton's configured SMS delivery service.

The merchant calls this API with the customer's mobile number, an SMS event, a merchant-side or Newton-side request identifier, and the values needed by the configured SMS template. Newton either creates a new `SmsDetail` record and attempts delivery through the configured SMS aggregator, or finds an existing `SmsDetail` for the same identifier and event and returns or advances its delivery state.

Use this API only after Newton has enabled the SMS template and SMS delivery configuration for the merchant. Payloads use the standard Newton S2S encrypted/signed request and response envelope. Examples in this guide show the decrypted business payload for readability.

## Business Use Case

SMS Service helps merchants:

- Trigger customer debit SMS notifications for non-UPI debit events.
- Trigger or retry debit SMS notifications for UPI-linked debit events by request id.
- Reuse the same merchant-generated identifier for idempotent non-UPI SMS initiation.
- Avoid duplicate sends when a message is already pending or delivered.
- Retry previously failed SMS attempts when retry budget remains.
- Track the Newton SMS detail id indirectly through the response payload.

## Integration Flow

1. Merchant creates or identifies the debit event in its own system.
2. Merchant calls `smsService` with the customer mobile number, event, identifier, and template parameters.
3. Newton authenticates the S2S request, verifies merchant API access and IP restrictions, and validates the decrypted body.
4. Newton normalizes the mobile number to a 10-digit domestic mobile number.
5. Newton looks up an existing `SmsDetail` by identifier and event.
6. If no record exists, Newton creates one, renders the configured SMS template, and attempts aggregator delivery.
7. If a record exists, Newton returns delivered/pending state, rejects a mobile-number mismatch, or retries a failed message when allowed.
8. Merchant decrypts/verifies the response and uses the payload status/code to decide whether the SMS was accepted, pending, delivered, failed, or should be retried later.

Important identifiers:

- `merchantRequestId`: Merchant-generated idempotency key for `NON_UPI_DEBIT_SMS`. Newton stores this in the `SmsDetail.upiRequestId` column for non-UPI SMS records because the flow has no UPI request id.
- `requestId`: Existing UPI/Newton request id for all other supported SMS events. In the response it is returned as `payload.requestId`.
- `smsId`: Internal Newton SMS detail id. It is not returned directly as `smsId`; it is used internally to retry, track delivery callbacks, and set retry counters.

## Endpoint

```http
POST /api/{apiVersion}/merchants/smsService
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment under `/api`. This endpoint does not branch on the value in the SMS service code path, but merchants should send the version shared during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. The body can be JWE, JWS, or plain JSON depending on merchant setup; production S2S integrations should use the agreed signed/encrypted mode. |
| `x-merchant-id` | Yes | Merchant id used to resolve the merchant record. |
| `x-merchant-channel-id` | Yes | Merchant channel id used with `x-merchant-id`. |
| `x-timestamp` | Yes | Timestamp used by signature verification and replay checks. |
| `x-merchant-signature` | Conditional | Required for unsigned business payloads unless a development-only checksum bypass is enabled. Signature input includes merchant ids, timestamp, and raw request body. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. Newton checks the first comma-separated IP against that list. |
| `x-request-id` | No | Optional request tracing id. Newton generates one if omitted and returns it as a response header. |
| `x-session-id` | No | Optional session tracing id. Newton uses `x-request-id` if omitted. |
| `x-sub-merchant-id` | Conditional | Required only for configured sub-merchant integrations. |
| `x-sub-merchant-channel-id` | Conditional | Required only for configured sub-merchant integrations. |

### Authentication, Signing, and Encryption

The route accepts `API.EncRequest SMSServiceRequest`, so the request can be:

- JWE encrypted payload with fields `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed payload with fields `payload`, `signature`, and `protected`.
- Plain decrypted JSON for environments or merchants configured to allow it.

For production merchant S2S traffic, use the signing/encryption strategy and key ids shared during onboarding. Newton first resolves the merchant from headers, verifies/decrypts the payload, then runs merchant signature verification, API enablement checks, IP allowlist checks, and timestamp validation before invoking SMS business logic.

Response transport follows the merchant's negotiated strategy. A successful business response can be returned as a signed response, an encrypted response, or an unsigned JSON response with `X-Response-Signature`. The response examples below show the decrypted business JSON.

## Request

### Supported Request Variants

Use `NON_UPI_DEBIT_SMS` for a merchant-owned, non-UPI debit event. This variant requires `merchantRequestId`.

```json
{
  "phoneNo": "9876543210",
  "merchantRequestId": "DEBIT-ORDER-10001",
  "event": "NON_UPI_DEBIT_SMS",
  "parameters": {
    "amount": "250.00",
    "balance": "10250.45",
    "merchantName": "Acme Store"
  },
  "iat": "1720000000"
}
```

Use `DEBIT_SMS` for a UPI/Newton request where the existing request id is the idempotency key. This variant requires `requestId`.

```json
{
  "phoneNo": "919876543210",
  "requestId": "UPI-REQ-10001",
  "event": "DEBIT_SMS",
  "parameters": {
    "amount": "250.00",
    "balance": "10250.45",
    "merchantName": "Acme Store"
  },
  "iat": "1720000000"
}
```

`SmsNotificationEvent` contains many internal SMS event constructors. For this endpoint, new merchant integrations should use only the event values explicitly enabled during onboarding. In practice, this API's S2S helper gives `NON_UPI_DEBIT_SMS` special identifier handling; every other event uses `requestId` and shares the non-`NON_UPI_DEBIT_SMS` response shape.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `phoneNo` | string | Yes | No default. | Customer mobile number. Accepted forms are `9876543210`, `919876543210`, or `09876543210`. The later normalization step also accepts `+919876543210`, but the explicit request validator for this API does not accept `+91`, so do not send a plus sign. |
| `requestId` | string | Conditional | No default. If missing for non-`NON_UPI_DEBIT_SMS` events, the helper throws an internal error before product logic. | Existing UPI/Newton request id used to find or create the SMS record for all events except `NON_UPI_DEBIT_SMS`. Must be non-empty when supplied. |
| `merchantRequestId` | string | Conditional | No default. If missing for `NON_UPI_DEBIT_SMS`, the helper throws an internal error before product logic. | Merchant-generated idempotency key for `NON_UPI_DEBIT_SMS`. Must be non-empty when supplied. |
| `event` | string | Yes | No default. | SMS notification event enum. Client-facing use is `NON_UPI_DEBIT_SMS` or `DEBIT_SMS`, unless Newton explicitly enables another event for the merchant. |
| `parameters` | object | Yes | No default. | Values used by the SMS template for this event. |
| `iat` | string | Conditional | Required for JWS/JWE payloads by route-level `validateIAT`. Plain unsigned payloads skip `iat` validation. | Issued-at timestamp used for request signing/replay validation where applicable. |

### `event` Values

The enum accepted by JSON parsing includes:

`UPI_REGISTRATION_START`, `UPI_REGISTRATION_COOLDOWN`, `UPI_REGISTRATION_COOLDOWN_IOS`, `INCOMING_COLLECT_REQUEST`, `COLLECT_REQUEST_EXPIRED`, `COLLECT_REQUEST_DECLINED`, `CREDIT_MONEY_TO_CUSTOMER`, `OUTGOING_MONEY_FROM_CUSTOMER`, `APPROVE_MANDATE_PAYER`, `DECLINE_MANDATE`, `MANDATE_NOTIFICATION`, `MANDATE_NOTIFICATION_ABOVE_LIMIT`, `PAUSE_MANDATE`, `UNPAUSE_MANDATE`, `APPROVE_MANDATE_PAYEE`, `REVOKE_MANDATE`, `UDIR_TRANSACTION_SUCCESS`, `UDIR_TRANSACTION_FAILURE`, `UDIR_TRANSACTION_REVERSED_DRC`, `UDIR_TRANSACTION_REVERSED_RET`, `UDIR_TRANSACTION_REVERSED_RET_RRC_RUU`, `LITE_SERVICE_ENABLED`, `LITE_SERVICE_DISABLED`, `LITE_SERVICE_ENABLED_SUCCESS`, `LITE_SERVICE_DISABLED_SUCCESS`, `LITE_SERVICE_ENABLED_FAILURE`, `LITE_SERVICE_DISABLED_FAILURE`, `LITE_TOPUP_SUCCESS`, `LITE_TOPUP_FAILURE`, `SET_RESET_MPIN_SUCCESS`, `SET_RESET_MPIN_FAILURE`, `MANDATE_EXECUTION_SUCCESS`, `ONBOARDING_OTP_VERIFICATION`, `TRANSACTION_SUCCESS_AGENT_NOTIFICATION`, `DEBIT_SMS`, `NON_UPI_DEBIT_SMS`, `DELEGATE_LINK_REQUEST_SMS`, `DELEGATE_PAY_REQUEST_RECEIVED_SMS`, `CREATE_MANDATE_FAILURE`, `MODIFY_MANDATE_FAILURE`, `REVOKE_MANDATE_FAILURE`, `PAUSE_MANDATE_FAILURE`, `UNPAUSE_MANDATE_FAILURE`, `CREATE_MANDATE_SUCCESS`, `MODIFY_MANDATE_SUCCESS`.

Do not treat this list as a list of enabled client use cases. If the event has no SMS template for the merchant, Newton returns an SMS outcome failure such as event-not-applicable.

### `parameters`

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `amount` | string | Conditional | No default. Required if the SMS template contains the `amount` placeholder. | Debit amount. Must match `^[0-9]+\.[0-9][0-9]$` and be greater than `0.0`, for example `250.00`. |
| `balance` | string | Conditional | No default. Required if the SMS template contains the `balance` placeholder. | Account balance or available balance text used in the SMS body. No format validation is applied by the request validator. |
| `merchantName` | string | Conditional | No default. Required if the SMS template contains the `merchantName` placeholder. | Merchant display name used in the SMS body. Must be non-empty when supplied. Newton may shorten it based on template placeholder sizing. |

Template rendering is dynamic. If the configured SMS template references `amount`, `balance`, or `merchantName` and the corresponding parameter is absent, Newton fails while building the SMS body.

### Validation Rules

- `phoneNo` must be in one of the accepted domestic formats listed above.
- `requestId`, when supplied, must be non-empty.
- `merchantRequestId`, when supplied, must be non-empty.
- `amount`, when supplied, must be a positive two-decimal string such as `1.00`; `0.00`, `1`, and `1.0` are invalid.
- `merchantName`, when supplied, must be non-empty.
- `parameters` is required even if a given template does not use every parameter.
- `requestId` is required for `DEBIT_SMS` and every non-`NON_UPI_DEBIT_SMS` event.
- `merchantRequestId` is required for `NON_UPI_DEBIT_SMS`.
- `requestId` and `merchantRequestId` are not interchangeable. Supplying only `requestId` for `NON_UPI_DEBIT_SMS` or only `merchantRequestId` for `DEBIT_SMS` fails before SMS delivery.

## Success Responses

The top-level response is the S2S business envelope:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Set to `SUCCESS` when SMS product logic returns a response object to the S2S transformer. |
| `responseCode` | string | Set to `SUCCESS` for the S2S transformer success path. |
| `responseMessage` | string | Set to `SUCCESS` for the S2S transformer success path. |
| `payload` | object | SMS-specific delivery outcome. Clients must inspect this object for the actual SMS state. |

### `NON_UPI_DEBIT_SMS` Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantRequestId": "DEBIT-ORDER-10001",
    "aggregatorStatus": "SUCCESS",
    "aggregatorResponseCode": "00"
  }
}
```

| Payload field | Type | Description |
| --- | --- | --- |
| `merchantRequestId` | string | Echoes the merchant idempotency key supplied for `NON_UPI_DEBIT_SMS`. |
| `aggregatorStatus` | string | SMS outcome returned by SMS product logic. Expected values are `SUCCESS` or `FAILURE`. |
| `aggregatorResponseCode` | string | SMS outcome code. See "SMS Outcome Codes". |

### `DEBIT_SMS` / Other Non-`NON_UPI_DEBIT_SMS` Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "SUCCESS",
    "responseCode": "00"
  }
}
```

| Payload field | Type | Description |
| --- | --- | --- |
| `requestId` | string | Echoes the `requestId` supplied in the request. Internally this is the lookup key for `SmsDetail`. |
| `status` | string | SMS outcome returned by SMS product logic. Expected values are `SUCCESS` or `FAILURE`. |
| `responseCode` | string | SMS outcome code. See "SMS Outcome Codes". |

### SMS Outcome Codes

| Code | Payload status | Meaning | Client handling |
| --- | --- | --- | --- |
| `00` | `SUCCESS` | New SMS attempt accepted by the SMS delivery layer, retry accepted, or pending record has at least one successful aggregator acknowledgement. | Treat as accepted. Reconcile final delivery through configured status/callback processes if applicable. |
| `02` | `FAILURE` | SMS delivery attempts failed or no configured aggregator produced a successful acknowledgement. | Retry only according to the retry guidance below; otherwise investigate aggregator/template configuration. |
| `03` | `FAILURE` | SMS template exists but is disabled for the merchant/event. | Do not retry unchanged. Ask Newton to enable/configure the event. |
| `04` | `FAILURE` | SMS template is not configured for the merchant/event. | Do not retry unchanged. Ask Newton to configure the event template. |
| `05` | `FAILURE` | Existing failed SMS has exhausted merchant retry attempts. | Do not retry automatically. Escalate or create a new business event only if appropriate. |
| `06` | `SUCCESS` | Existing SMS record is already marked delivered. | Treat as idempotent success. |
| `07` | `FAILURE` | Existing SMS record is pending and no successful acknowledgement has been recorded yet. | Do not immediately retry in a tight loop. Wait for status callback or retry later with backoff. |
| `08` | `FAILURE` | Same identifier/event already exists for a different mobile number. | Treat as idempotency conflict. Correct the identifier or mobile number; do not retry unchanged. |
| `01` | `FAILURE` | Current PSP mode and SMS initiation mode are not applicable for this SMS flow. | Do not retry unchanged. Confirm merchant SMS initiation configuration. |

## Failure Scenarios

Failures can appear in two broad forms:

- Transport/auth/validation failures: the response body is an error object, often still inside the configured response envelope.
- SMS business outcome failures: the top-level response is `SUCCESS`, but `payload.status` or `payload.aggregatorStatus` is `FAILURE`.

Always parse the decrypted JSON body. Do not rely only on HTTP status.

### Request Validation Failure

Invalid `phoneNo`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"Phone Number regex match failed\""
}
```

Invalid `amount`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Empty `requestId`, `merchantRequestId`, or `merchantName`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"requestId field is empty\""
}
```

Client handling: fix the request and send a new call. Validation errors are deterministic and should not be retried unchanged.

### Missing Conditional Identifier

If `event` is `NON_UPI_DEBIT_SMS` and `merchantRequestId` is omitted, or if `event` is not `NON_UPI_DEBIT_SMS` and `requestId` is omitted, the helper raises an internal error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: treat this as a request construction error even though the response code is internal. Send `merchantRequestId` for `NON_UPI_DEBIT_SMS`; send `requestId` for `DEBIT_SMS`.

### Authentication, Signature, Timestamp, or Encryption Failure

Missing merchant headers, missing timestamp, signature mismatch, invalid JWS, failed JWE decryption, or invalid request IP can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: do not retry unchanged. Verify `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, key id, signature input, request body bytes used for signing, encryption keys, and whitelisted source IP.

### Malformed JSON or Unsupported Event

If the decrypted payload cannot be parsed, or if `event` is not one of the `SmsNotificationEvent` enum values, the request is rejected before SMS product logic. The exact body can vary by JSON parsing layer, but the decrypted error shape is:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"event\" not found"
}
```

Client handling: fix the JSON shape or event value. Do not retry unchanged.

### Merchant or Key Lookup Failure

Newton resolves the merchant from `x-merchant-id` and `x-merchant-channel-id` before verifying the payload. JWS/JWE requests also resolve the key id from the protected header. Missing or unknown merchant/key data can surface as an auth or invalid-data response, depending on which lookup fails first:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding KID"
}
```

Client handling: verify merchant ids, channel ids, sub-merchant ids if used, key id, and onboarding status. Do not retry unchanged.

### Merchant API Disabled or Not Allowed

If merchant configuration blocks `smsService` through `blockedApiNames`, or the merchant is disabled and `allowedApiNames` does not include `smsService`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: do not retry. Ask Newton/onboarding support to enable this API for the merchant and channel.

### IP Restriction Failure

When `whitelistedIps` is configured, Newton checks the first IP in `x-forwarded-for`. Missing or non-whitelisted IP returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: send traffic from an onboarded IP and ensure the gateway forwards `x-forwarded-for` correctly.

### SMS Template Not Configured

For Newton/JUSPAY SMS initiation mode, if the event has no merchant SMS template:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "FAILURE",
    "responseCode": "04"
  }
}
```

For `NON_UPI_DEBIT_SMS`, the same outcome is mapped into aggregator fields:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantRequestId": "DEBIT-ORDER-10001",
    "aggregatorStatus": "FAILURE",
    "aggregatorResponseCode": "04"
  }
}
```

Client handling: do not retry unchanged. Ask Newton to configure the SMS template for the event.

### SMS Template Disabled

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "FAILURE",
    "responseCode": "03"
  }
}
```

Client handling: do not retry unchanged. Ask Newton to enable the event template.

### Template Parameter Missing

If a configured template references a placeholder such as `amount`, `balance`, or `merchantName` but the request omits that parameter, Newton fails during SMS body construction. This commonly surfaces as:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: send every parameter required by the onboarded template. Confirm the template placeholders with Newton if unsure.

### Existing Identifier With Different Mobile Number

If the same identifier/event already exists but with a different normalized mobile number:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantRequestId": "DEBIT-ORDER-10001",
    "aggregatorStatus": "FAILURE",
    "aggregatorResponseCode": "08"
  }
}
```

Client handling: treat this as an idempotency conflict. Do not retry unchanged. Use the original mobile number for that identifier or create a new identifier for a different customer/event.

### Existing SMS Already Delivered

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "SUCCESS",
    "responseCode": "06"
  }
}
```

Client handling: treat as idempotent success.

### Existing SMS Pending

If an existing pending SMS has a successful aggregator acknowledgement in stored response info:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "SUCCESS",
    "responseCode": "00"
  }
}
```

If no successful acknowledgement has been recorded yet:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "FAILURE",
    "responseCode": "07"
  }
}
```

Client handling: for `07`, wait and poll/retry later with backoff or rely on the configured delivery callback/status process. Do not send rapid duplicate calls.

### Existing SMS Failed and Retry Attempts Exhausted

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "FAILURE",
    "responseCode": "05"
  }
}
```

Client handling: stop automatic retries for that identifier. Escalate or start a new business event only if the merchant process permits it.

### Downstream Aggregator Failure

If all configured aggregators fail, are unavailable, or produce unsuccessful acknowledgements:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "FAILURE",
    "responseCode": "02"
  }
}
```

Some downstream transport errors are thrown through shared external-call helpers and can instead return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with backoff only if the request is idempotent and the response is a transient downstream failure. Keep the same identifier when retrying the same SMS event.

### SMS Initiation Mode Not Applicable

If the current PSP mode and SMS initiation mode do not support this SMS flow:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "requestId": "UPI-REQ-10001",
    "status": "FAILURE",
    "responseCode": "01"
  }
}
```

Client handling: do not retry unchanged. Confirm merchant SMS initiation mode with Newton.

### Unexpected Errors

Examples include missing merchant record, missing retry-count configuration, missing aggregator list, missing response error code where the transformer requires one, Redis/DB failures, or other unhandled exceptions.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry only after a short backoff if the operation is safe to retry with the same identifier. If repeated, escalate with `x-request-id`, `x-session-id`, `event`, and the relevant `requestId` or `merchantRequestId`.

## Retry and Idempotency Guidance

- Use a stable `merchantRequestId` for each `NON_UPI_DEBIT_SMS` event. Reusing it with the same mobile number is idempotent; reusing it with a different mobile number returns outcome code `08`.
- Use the stable `requestId` for `DEBIT_SMS` and other onboarded UPI-linked events.
- Retry network timeouts or transport failures with the same identifier and event.
- Do not retry validation, auth, API-disabled, IP-restriction, template-disabled, template-missing, or mobile-mismatch errors unchanged.
- For `payload.status = FAILURE` / `responseCode = 07`, wait before retrying because the SMS may still be in process.
- For `responseCode = 05`, stop retrying that identifier because merchant retry attempts are exhausted.
- For `responseCode = 06`, treat the response as successful idempotent replay.
- For `responseCode = 02`, use bounded exponential backoff. Newton also tracks retry counts in Redis and merchant configuration can cap retries through `smsServiceRetryCount`.

## Source References

- API root captures `apiVersion`: [Core.hs](../../src/Newton/App/Routes/Core.hs:112)
- SMS route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:1298)
- SMS route handler, request decryption, signature verification, and transformer call: [Core.hs](../../src/Newton/App/Routes/Core.hs:3533)
- S2S request body verification helper: [Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- S2S response signing/encryption wrapper: [RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:31)
- Request envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:13)
- Merchant payload verification and JWS/JWE handling: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:67)
- Merchant signature, API enabled, timestamp, and IP checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- S2S transformer route: [ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:861)
- Request, parameter, and response types with validation: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3783)
- Request-to-core identifier mapping and response mapping: [ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1612)
- SMS service core request/response types and retry modes: [SMSService/Types.hs](../../src/Newton/Product/Merchant/SMSService/Types.hs:17)
- SMS service business logic and existing-record handling: [SMSService.hs](../../src/Newton/Product/Merchant/SMSService/SMSService.hs:27)
- SMS service response transformer: [SMSService/Transformer.hs](../../src/Newton/Product/Merchant/SMSService/Transformer.hs:15)
- SMS pending acknowledgement helper: [SMSService/Helper.hs](../../src/Newton/Product/Merchant/SMSService/Helper.hs:13)
- SMS event enum: [SmsNotification/Types.hs](../../src/Newton/External/SmsNotification/Types.hs:77)
- SMS notification send flow and template checks: [SmsNotification/Class.hs](../../src/Newton/External/SmsNotification/Class.hs:234)
- SMS aggregator retry attempts: [SmsNotification/Flow.hs](../../src/Newton/External/SmsNotification/Flow.hs:537)
- SMS template parameter substitution: [SMSInfo.hs](../../src/Newton/External/SmsNotification/SMSInfo.hs:84)
- Mobile number validation and normalization: [Common.hs](../../src/Newton/Validation/Common.hs:979), [Utils.hs](../../src/Newton/Utils/Utils.hs:156)
- Amount and non-empty field validation: [Common.hs](../../src/Newton/Validation/Common.hs:168), [Common.hs](../../src/Newton/Validation/Common.hs:351)
- Validation error response behavior: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Shared success, bad request, unauthorized, invalid-data, and internal-error bodies: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
