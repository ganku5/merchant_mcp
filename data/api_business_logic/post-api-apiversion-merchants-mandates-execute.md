# Execute Mandate API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/execute`

## Overview

Execute Mandate is a server-to-server API used to execute an existing payer-side UPI Lite mandate. The public path is retained for backward compatibility; in code it is routed through the same `LiteExecuteMandateRequest` and `LiteExecuteMandateResponse` flow as `/merchants/mandates/liteExecute`.

The merchant calls this API after a mandate has already been created, approved, and linked to the merchant customer. Newton validates the merchant, customer, stored mandate, mandate amount/date/status rules, duplicate transaction id, and UPI Lite/autotopup conditions. Newton then creates a `PAY` transaction and sends `ReqPay` to NPCI.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope. The examples below show the decrypted business payload for readability.

## Business Use Case

Use this API when a merchant backend needs to initiate a UPI Lite mandate execution for a registered customer. Typical use cases include:

- Executing a customer-approved UPI Lite autopay or top-up mandate.
- Charging a mandate by `umn`, original mandate id, or both, without requiring the customer to start a new authorization journey.
- Receiving the execute attempt result synchronously as Newton's current gateway status: `SUCCESS`, `PENDING`, or `FAILURE`.
- Reconciling the execution with merchant identifiers, Newton UPI transaction id, original mandate id, gateway reference id, and optional `udfParameters`.

Do not use this API for the web mandate execution-cycle notification flow. For scheduled mandate cycles that require notification, use the `webExecuteCycle` and `webExecuteCycleStatus` APIs instead.

## Integration Flow

1. Merchant creates and approves a mandate through the appropriate mandate creation flow.
2. Merchant stores the returned `umn`, original mandate id, merchant customer id, and mandate amount/rules.
3. When execution is required, merchant generates a new `merchantRequestId` and a new unique `upiRequestId`.
4. Merchant builds the decrypted business payload, signs/encrypts it using the Newton S2S process, and calls this endpoint.
5. Newton decrypts/verifies the envelope, validates merchant access and request signature, resolves the merchant customer/customer, and validates the body.
6. Newton finds the payer-role mandate by `orgMandateId` and/or `umn`, validates mandate status, expiry, amount rule, pause window, first-execution timing, purpose, and duplicate `upiRequestId`.
7. Newton creates a `PAY` transaction and sends a mandate `ReqPay` to NPCI.
8. Merchant decrypts the response and stores `payload.gatewayTransactionId`, `payload.gatewayReferenceId`, `payload.gatewayResponseStatus`, and response codes for reconciliation.

Important identifiers:

- `merchantRequestId`: Merchant-generated idempotency/order reference for this execute attempt.
- `upiRequestId`: Merchant-generated UPI transaction id for this execute attempt. It must be unique for retries that create a new attempt.
- `orgMandateId`: Original mandate UPI request id stored on the mandate.
- `umn`: Unique mandate number assigned to the approved mandate.
- `gatewayReferenceId`: Gateway/NPCI response id returned after the execute attempt is processed.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/execute
```

The same request and response types are also exposed at `/api/{apiVersion}/merchants/mandates/liteExecute`. The `/execute` path is the backward-compatible alias.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON containing the Newton encrypted/signed envelope. |
| `x-merchant-id` | Yes | Merchant id used to resolve merchant configuration and keys. |
| `x-merchant-channel-id` | Yes | Merchant channel id used with `x-merchant-id`. |
| `x-sub-merchant-id` | Conditional | Required only for sub-merchant integrations onboarded with sub-merchant credentials. |
| `x-sub-merchant-channel-id` | Conditional | Required only for sub-merchant integrations onboarded with sub-merchant credentials. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness except for specific non-production checksum-bypass paths. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain envelopes. Signature is calculated over merchant ids, timestamp, and raw body using the merchant API key and configured signature strategy. |
| `Authorization` | Conditional | Required only when your onboarding process uses an authorization header for the selected envelope mode. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP in the header must be whitelisted. |
| `x-request-id` | No | Optional trace id. Newton generates one when absent. |
| `x-session-id` | No | Optional session id. Defaults to `x-request-id` when absent. |

### Auth, Encryption, and Signing

Newton first verifies the server-to-server envelope and resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.

Accepted envelope modes are implementation-dependent by environment and onboarding:

- `JWE` encrypted payload: Newton decrypts the payload using the key id (`kid`) in the protected header.
- `JWS` signed payload: Newton verifies the payload signature using the key id (`kid`) and merchant public key.
- Plain/unsigned payload: accepted only where explicitly allowed by environment/onboarding; for this route, Newton requires `x-merchant-signature` unless the request is a signed or encrypted envelope.

For signed or encrypted payloads, the decrypted body must include `iat`; Newton validates it as a timestamp. For plain payloads, `iat` is optional at this layer, but new integrations should still send it when instructed during onboarding.

After envelope verification, Newton checks:

- API access is not blocked by merchant config `blockedApiNames`.
- API access is included in the merchant/sub-merchant allowed API list when such a list is configured.
- Merchant signature or signed/encrypted envelope is valid.
- Source IP is allowed when `whitelistedIps` is configured.
- `x-timestamp` is fresh.
- `merchantCustomerId` resolves to a merchant customer and customer for this merchant.

## Request

The examples show the decrypted business payload. The actual transport body is the Newton `EncRequest` envelope.

### Minimum Request With UMN

```json
{
  "merchantRequestId": "LITEEXEC0001",
  "merchantCustomerId": "CUST12345",
  "umn": "8b4c6c77f3d145df9a11122334455667@upi",
  "amount": "100.00",
  "upiRequestId": "LITEEXECTXN0001",
  "purpose": "71",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Minimum Request With Original Mandate Id

```json
{
  "merchantRequestId": "LITEEXEC0002",
  "merchantCustomerId": "CUST12345",
  "orgMandateId": "MANDATECREATE0001",
  "amount": "250.00",
  "upiRequestId": "LITEEXECTXN0002",
  "purpose": "71",
  "iat": "2026-07-02T10:16:00+05:30"
}
```

### Request With Both Identifiers and Optional Metadata

```json
{
  "merchantRequestId": "LITEEXEC0003",
  "merchantCustomerId": "CUST12345",
  "umn": "8b4c6c77f3d145df9a11122334455667@upi",
  "orgMandateId": "MANDATECREATE0001",
  "amount": "500.00",
  "upiRequestId": "LITEEXECTXN0003",
  "purpose": "82",
  "remarks": "Lite mandate execution",
  "refUrl": "https://merchant.example/orders/LITEEXEC0003",
  "refCategory": "00",
  "clVersion": "2.0",
  "udfParameters": "{\"orderId\":\"ORDER123\",\"cycle\":\"1\"}",
  "iat": "2026-07-02T10:17:00+05:30"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and rules | Description |
| --- | --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | 1 to 35 characters. Allowed characters are letters, numbers, hyphen, dot, and underscore; must contain at least one alphanumeric character. | Merchant-generated reference for this execute attempt. Returned in the response payload. |
| `merchantCustomerId` | string | Yes | No default. | 1 to 256 characters. Allowed characters: letters, numbers, `.`, `_`, `+`, `/`, `=`, and `-`; first character must be alphanumeric, `+`, `/`, or `=`. Must resolve to a merchant customer for the authenticated merchant. | Merchant's customer identifier linked to the mandate. |
| `umn` | string | Conditional | No default. | Required when `orgMandateId` is absent. If supplied, length must be 34 to 70 and match the UMN pattern with a 32-character prefix before `@`. | Unique mandate number. Newton searches for a payer-role mandate by this value. |
| `orgMandateId` | string | Conditional | No default. | Required when `umn` is absent. If supplied, follows `upiRequestId` validation: 1 to 35 alphanumeric characters. | Original mandate UPI request id. Newton searches for a payer-role mandate by this value. |
| `amount` | string | Yes | No default. | Must match `^[0-9]+\\.[0-9][0-9]$` and be greater than `0.00`. Must satisfy the stored mandate amount rule: exact amount for `EXACT`, not greater than mandate amount for `MAX`. | Execution amount. Returned with two decimals. |
| `upiRequestId` | string | Yes | No default. | 1 to 35 alphanumeric characters. Must not already exist as a self-initiated transaction. | UPI transaction id for this execute attempt; returned as `gatewayTransactionId`. |
| `purpose` | string | Yes | No default. | Allowed values: `71`, `82`. The request validator and business logic both enforce this set. | UPI purpose code for lite mandate execution. |
| `remarks` | string | No | Defaults to Newton's default remarks value in the transaction and response when omitted. | 1 to 255 characters when supplied. Must start, after optional leading spaces, with a letter, number, or hyphen; then letters, numbers, spaces, or hyphens. | Transaction note. |
| `refUrl` | string | No | No default. Omitted from response when omitted. | Must be non-empty when supplied. | Merchant reference URL. |
| `refCategory` | string | No | No default. Omitted from response when omitted. | Must be non-empty when supplied. | Merchant reference category. |
| `iat` | string | Conditional | No default. | Required and timestamp-validated for signed or encrypted envelope modes. | Issued-at timestamp used in request freshness validation. |
| `udfParameters` | string | No | No default. Omitted from response when omitted. | Must be a JSON-object string and must not contain disallowed special characters checked by the validator. | Merchant-defined metadata. Echoed at the top level of the response. |
| `clVersion` | string | No | No default. | Must be non-empty when supplied. | UPI common library version, forwarded into the transaction request. |

### Conditional Rules

- Send at least one of `umn` or `orgMandateId`. If both are absent, validation fails with `OrgMandateId or UMN should be present`.
- If both identifiers are sent, Newton uses both in mandate lookup. They must refer to the same payer-role mandate.
- `merchantCustomerId` must match the merchant customer linked to the stored mandate. A valid mandate for a different customer is rejected.
- The stored mandate must be executable: not completed, declined, expired, paused, pending, revoked, failed, timed out, or dormant.
- Current execution time must be between mandate `validityStart` and `validityEnd`.
- If the mandate has a pause window, execution during that window is rejected.
- For first execution, Newton enforces the stored first-execution time rule. A late first execution returns `JPFET`.
- For UPI Lite autopay/autotopup mandates, stored UPI Lite state is also checked. The request does not contain a separate lite object; Newton derives this from the mandate and merchant customer records.
- `upiRequestId` is the duplicate guard. Reusing it after Newton has created a transaction returns `DUPLICATE_REQUEST`.

## Response

The examples show the decrypted business response. The actual transport body is the Newton `EncResponse` envelope.

### Success Response: Execution Accepted and Successful

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "LITEEXEC0001",
    "payeeMcc": "0000",
    "merchantCustomerId": "CUST12345",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "amount": "100.00",
    "remarks": "Lite mandate execution",
    "refUrl": "https://merchant.example/orders/LITEEXEC0001",
    "refCategory": "00",
    "gatewayTransactionId": "LITEEXECTXN0001",
    "orgMandateId": "MANDATECREATE0001",
    "transactionTimestamp": "2026-07-02 10:15:31",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayReferenceId": "620212345678"
  },
  "udfParameters": "{\"orderId\":\"ORDER123\"}"
}
```

### Success Response: Execution Pending

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "LITEEXEC0002",
    "payeeMcc": "0000",
    "merchantCustomerId": "CUST12345",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "amount": "250.00",
    "remarks": "UPI",
    "gatewayTransactionId": "LITEEXECTXN0002",
    "orgMandateId": "MANDATECREATE0001",
    "transactionTimestamp": "2026-07-02 10:16:01",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "PENDING",
    "gatewayResponseStatus": "PENDING",
    "gatewayReferenceId": "620212345679"
  }
}
```

### Success Response: Gateway Rejected the Execution

Newton returns `status: SUCCESS` when the API request was processed and a transaction result was produced. Check `payload.gatewayResponseStatus` to decide the execution outcome.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "LITEEXEC0003",
    "payeeMcc": "0000",
    "merchantCustomerId": "CUST12345",
    "umn": "8b4c6c77f3d145df9a11122334455667@upi",
    "amount": "500.00",
    "remarks": "Lite mandate execution",
    "gatewayTransactionId": "LITEEXECTXN0003",
    "orgMandateId": "MANDATECREATE0001",
    "transactionTimestamp": "2026-07-02 10:17:02",
    "gatewayResponseCode": "U30",
    "gatewayResponseMessage": "Debit has failed",
    "gatewayResponseStatus": "FAILURE",
    "gatewayReferenceId": "620212345680",
    "gatewayPayerResponseCode": "U30"
  },
  "udfParameters": "{\"orderId\":\"ORDER123\",\"cycle\":\"1\"}"
}
```

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. For processed execute attempts this is `SUCCESS`; the transaction result is in `payload.gatewayResponseStatus`. |
| `responseCode` | string | API-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | API-level response message. Success value is `SUCCESS`. |
| `payload` | object | Execute mandate result payload. Present on success responses. |
| `udfParameters` | string | Echo of request `udfParameters`, omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant record. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant record. |
| `merchantRequestId` | string | Merchant request id for this execute attempt, read back from the created transaction. |
| `payeeMcc` | string | Always returned as `0000` for this lite execute path. |
| `merchantCustomerId` | string | Merchant customer id resolved from the authenticated merchant customer record. |
| `umn` | string | UMN from the stored mandate. |
| `amount` | string | Transaction amount formatted to two decimals. |
| `remarks` | string | Request remarks, or Newton's default remarks when omitted. |
| `refUrl` | string | Echo of request `refUrl`, omitted when not supplied. |
| `refCategory` | string | Echo of request `refCategory`, omitted when not supplied. |
| `gatewayTransactionId` | string | Echo of request `upiRequestId`. |
| `orgMandateId` | string | Original mandate UPI request id from the stored mandate. |
| `transactionTimestamp` | string | Created-at timestamp of the Newton transaction. |
| `gatewayResponseCode` | string | Gateway response code derived from the transaction's NPCI response/status. `00` maps to success and `01` maps to pending; other values map to failure. |
| `gatewayResponseMessage` | string | Gateway response message derived from the transaction's NPCI response/status. |
| `gatewayResponseStatus` | string | `SUCCESS` when `gatewayResponseCode` is `00`; `PENDING` when it is `01`; otherwise `FAILURE`. |
| `gatewayReferenceId` | string | Transaction `upiResponseId`/gateway reference id. |
| `gatewayPayerResponseCode` | string | Optional payer response code, returned only when UDIR response-code configuration and gateway data provide it. |
| `gatewayPayerReversalResponseCode` | string | Optional payer reversal response code, returned only when UDIR response-code configuration and gateway data provide it. |
| `arpc` | string | Optional ARPC value returned from the execution response when available. |

## Error Handling

Failure responses are returned in the same Newton encrypted response transport when the request reached the API layer. After decryption, failures generally follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid amount",
  "payload": null
}
```

This example shows the underlying decrypted failure shape. The concrete `responseCode` and `responseMessage` vary by validation, middleware, and downstream failure. Some middleware failures can also vary by deployment or envelope mode, especially before the business payload is decrypted. Clients should always parse decrypted `status`, `responseCode`, and `responseMessage` when present, and should not depend only on HTTP status.

### Validation Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Neither `umn` nor `orgMandateId` supplied | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"OrgMandateId or UMN should be present","payload":null}` | Send at least one mandate identifier. |
| Invalid amount format or non-positive amount | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"amount regex match failed","payload":null}` | Send a two-decimal amount greater than `0.00`, for example `100.00`. Exact validation message may include the validator detail. |
| Invalid `merchantRequestId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"merchantRequestId length not between 1 and 35","payload":null}` | Generate a 1 to 35 character id using only supported characters. |
| Invalid `merchantCustomerId` format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"merchantCustomerId is not alphanumeric","payload":null}` | Use the exact merchant customer id registered with Newton. |
| Invalid `upiRequestId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"upiRequestId regex match failed","payload":null}` | Use a 1 to 35 character alphanumeric UPI request id. |
| Invalid `umn` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"umn length is not between 34 and 70","payload":null}` | Use the UMN returned by the mandate approval/status flow. |
| Invalid `purpose` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Enum match failed \"99\"","payload":null}` | Send only `71` or `82`. |
| Invalid `remarks` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"remarks regex match failed","payload":null}` | Use a simple alphanumeric note up to 255 characters. |
| Invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"JSON Text parse failed for udfParameters","payload":null}` | Send a JSON-object string and avoid disallowed special characters. |

The shared validation layer may wrap validator details differently by deployment. Treat any `BAD_REQUEST` or `INVALID_DATA` response before transaction creation as non-retryable until the request is corrected.

### Auth, Encryption, Signature, and Merchant Access Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Missing or invalid merchant headers | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Verify `x-merchant-id` and `x-merchant-channel-id` match onboarding. |
| Invalid JWS signature or envelope verification failure | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Rebuild the envelope with the active key id and signing/encryption material. |
| Missing `iat` for signed/encrypted payload | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"IAT is empty","payload":null}` | Include a fresh `iat` in the decrypted business payload. |
| Missing or invalid `x-merchant-signature` for unsigned/plain payload | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Sign the exact raw body with the merchant API key, timestamp, and configured strategy. |
| API disabled or not allowed for merchant/sub-merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED","payload":null}` | Ask Newton to enable the lite mandate execute API for the merchant or sub-merchant. |
| IP restriction failure | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Send from an onboarded IP and ensure `x-forwarded-for` contains the whitelisted client IP first. |
| Stale or invalid `x-timestamp` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED","payload":null}` | Use a current timestamp and correct clock skew. |

### Lookup Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Mandate not found for `umn`/`orgMandateId` and payer role | `{"status":"FAILURE","responseCode":"REQUEST_NOT_FOUND","responseMessage":"REQUEST_NOT_FOUND","payload":null}` | Confirm the mandate was created and approved for this merchant customer, and pass the original mandate id or UMN exactly as returned. |
| `merchantCustomerId` does not resolve under the merchant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid merchantCustomerId","payload":null}` | Use the same customer id that was used during mandate setup. |
| Stored mandate is missing linked account/device/customer data | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Do not retry blindly. Contact Newton with `merchantRequestId`, `upiRequestId`, and `orgMandateId`. |
| Stored mandate is missing UMN or digital signature needed for `ReqPay` | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Treat as setup/data issue and contact Newton support. |

### State and Business-Rule Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Duplicate `upiRequestId` | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST","payload":null}` | Do not reuse `upiRequestId`. Query transaction status or reconcile the original attempt. |
| Mandate completed | `{"status":"FAILURE","responseCode":"JPMC","responseMessage":"Mandate is already completed","payload":null}` | Stop executing this mandate. Create a new mandate if required. |
| Mandate declined | `{"status":"FAILURE","responseCode":"JPMD","responseMessage":"Mandate is declined by payer","payload":null}` | Ask the customer to authorize a new mandate if needed. |
| Mandate expired by status | `{"status":"FAILURE","responseCode":"JPMX","responseMessage":"Mandate is expried due to no action by payer","payload":null}` | Do not retry; create a fresh mandate. |
| Mandate currently pending | `{"status":"FAILURE","responseCode":"JPMW","responseMessage":"Invalid Operation , Mandate is in pending state","payload":null}` | Wait for mandate creation/update to reach a terminal approved state before executing. |
| Mandate revoked or revoke pending | `{"status":"FAILURE","responseCode":"JPMR","responseMessage":"Invalid Operation , Mandate is Revoked","payload":null}` | Do not retry; create a new mandate if customer consent is still required. |
| Mandate inactive, failed, timed out, or dormant | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mandate is inactive","payload":null}` | Do not retry against this mandate. |
| Execution outside mandate validity window | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"executionTime is not valid","payload":null}` | Execute only between the mandate validity start and end dates. |
| Mandate paused | `{"status":"FAILURE","responseCode":"JPMP","responseMessage":"Mandate is Paused","payload":null}` | Retry only after the pause period ends or after unpausing the mandate. |
| Invalid execution amount for mandate amount rule | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid amount","payload":null}` | For `EXACT`, send the mandate amount. For `MAX`, send an amount less than or equal to the mandate amount. |
| First execution arrived too late | `{"status":"FAILURE","responseCode":"JPFET","responseMessage":"First mandate execution came after 5 mins","payload":null}` | Do not retry the same first execution. Recreate or reauthorize the mandate as advised by Newton. |
| UPI Lite auto-topup not active/set | `{"status":"FAILURE","responseCode":"JPL4","responseMessage":"Auto-topup is not set","payload":null}` | Ensure the customer's Lite auto-topup setup is active before executing. |
| UPI Lite mandate not linked to the Lite account | `{"status":"FAILURE","responseCode":"JPL5","responseMessage":"UMN not linked to lite account","payload":null}` | Re-link or recreate the Lite mandate for the correct Lite account. |
| UPI Lite recharge amount exceeded | `{"status":"FAILURE","responseCode":"JPL2","responseMessage":"Incorrect amount : executionAmount cannot be more than rechargeAmount","payload":null}` | Send an execution amount within the configured recharge amount. |
| Previous UPI Lite execution pending | `{"status":"FAILURE","responseCode":"JPL3","responseMessage":"Previous lite transaction/execution is in pending state","payload":null}` | Wait for the previous pending Lite execution to complete before retrying with a new `upiRequestId`. |

### Downstream, Gateway, and Risk Failures

| Scenario | Example decrypted response | Client handling |
| --- | --- | --- |
| Sherlock/risk limits reject the transaction before NPCI | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseStatus":"FAILURE","gatewayResponseCode":"JPHTL","gatewayResponseMessage":"Lite top up limit exceeds 2000.0","gatewayTransactionId":"LITEEXECTXN0004","merchantRequestId":"LITEEXEC0004","orgMandateId":"MANDATECREATE0001","amount":"2500.00","merchantId":"MERCHANT123","merchantChannelId":"APP","merchantCustomerId":"CUST12345","umn":"8b4c6c77f3d145df9a11122334455667@upi","remarks":"UPI","transactionTimestamp":"2026-07-02 10:18:00","gatewayReferenceId":"620212345681"}}` | Treat as a terminal failed execute attempt unless Newton specifically asks for retry. |
| NPCI timeout or asynchronous failure while transaction remains pending | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseStatus":"PENDING","gatewayResponseCode":"01","gatewayResponseMessage":"PENDING","gatewayTransactionId":"LITEEXECTXN0005","merchantRequestId":"LITEEXEC0005","orgMandateId":"MANDATECREATE0001","amount":"100.00","merchantId":"MERCHANT123","merchantChannelId":"APP","merchantCustomerId":"CUST12345","umn":"8b4c6c77f3d145df9a11122334455667@upi","remarks":"UPI","transactionTimestamp":"2026-07-02 10:19:00","gatewayReferenceId":"620212345682"}}` | Do not immediately retry with a new transaction id. Poll/status-check or wait for callback/reconciliation until terminal. |
| NPCI/gateway returns failure code | See "Gateway Rejected the Execution" above. | Treat `gatewayResponseStatus: FAILURE` as terminal for that `upiRequestId`; create a new attempt only if business rules permit. |
| Downstream service unavailable before a transaction result is available | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_U09","responseMessage":"NPCI service is not reachable at the moment (U09)","payload":null}` | Retry later with a new `upiRequestId` only after confirming no transaction was created for the original `upiRequestId`. |
| Unexpected server error | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR","payload":null}` | Use `upiRequestId` to reconcile before retrying. Contact Newton if the status is unknown. |

## Retry and Idempotency Guidance

- Treat `upiRequestId` as the transaction id and duplicate key. Never reuse it for a new execution attempt.
- If the API returns `DUPLICATE_REQUEST`, do not resend the same execute request. Query/reconcile the original `upiRequestId`.
- If the decrypted response has `status: SUCCESS`, inspect `payload.gatewayResponseStatus`:
  - `SUCCESS`: terminal success.
  - `FAILURE`: terminal failure for that `upiRequestId`.
  - `PENDING`: wait for status/callback/reconciliation. Do not create a second attempt until the first is terminal.
- For transport failures, timeouts, or missing responses, first check transaction status using the original `upiRequestId`. Retry with a new `upiRequestId` only if Newton confirms no transaction exists or the previous attempt is terminal and business rules allow another execution.
- Correct request validation, auth, merchant access, mandate lookup, and mandate state errors before retrying.
- If the mandate is paused, expired, revoked, completed, inactive, or first execution has timed out, retries will continue to fail until the mandate state changes or a new mandate is created.

## Source References

- Route type and backward-compatible `/execute` alias: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:540)
- Route handler, envelope decrypt, signature verification, and transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2955)
- Request body extraction and header trace defaults: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Response wrapping via `flowWithTrace`: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- S2S envelope verification and supported request types: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, merchant customer, IP, and timestamp checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request/response types and request validator: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2280)
- S2S transformer and core request/response mapping: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:361), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1209)
- Core lite execute route and NPCI call path: [src/Newton/Product/Merchant/Mandate/LiteExecuteMandate.hs](../../src/Newton/Product/Merchant/Mandate/LiteExecuteMandate.hs:33)
- Mandate/customer/device/account lookups and response construction: [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:1195), [src/Newton/Product/Merchant/Mandate/Helper.hs](../../src/Newton/Product/Merchant/Mandate/Helper.hs:1271)
- Execute request construction and default remarks/expiry behavior: [src/Newton/Product/TransactionV2Helper.hs](../../src/Newton/Product/TransactionV2Helper.hs:320)
- Lite execution validation: [src/Newton/Product/TransactionV2Helper.hs](../../src/Newton/Product/TransactionV2Helper.hs:261)
- Shared validation rules: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:246), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:351), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:575)
- Mandate amount, expiry, pause, duplicate, status, and purpose rules: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:680), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:959), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1077), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:1507), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2903), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2984)
- NPCI async call and pay response handling: [src/Newton/External/NPCI/Flow.hs](../../src/Newton/External/NPCI/Flow.hs:47), [src/Newton/Product/TransactionV2Helper.hs](../../src/Newton/Product/TransactionV2Helper.hs:68)
- Shared response/error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:581), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1149)
