# Refund Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/refund/status`

## Overview

Refund Status is a server-to-server API used to fetch the latest status of a refund that was already initiated with Newton.

The merchant calls this API with the refund request id and either the merchant's original transaction id or the original Newton UPI transaction id. Newton locates the original payment, locates the refund, optionally performs an online status refresh for pending online or UDIR refunds, and returns the refund state and gateway details.

Use this API for merchant-side refund tracking, customer support lookups, reconciliation, and safe retry decisions after a refund initiation response or callback is delayed.

## Business Use Case

Refund Status helps merchants:

- Confirm whether a refund is `SUCCESS`, `PENDING`, `DEEMED`, or `FAILURE`.
- Reconcile a merchant refund request id with the original transaction and gateway refund references.
- Refresh pending online refund status from the configured downstream status-check path when allowed.
- Refresh pending UDIR refund or complaint status when the refund is backed by a UDIR complaint.
- Return split settlement, CRN, risk-score, and UDIR adjustment details where supported by the response version and merchant configuration.

## Integration Flow

1. Merchant initiates an online, offline, or UDIR refund and stores the refund request id.
2. Merchant calls `refund/status` with `merchantRequestId` and either `merchantTransactionId` or `originalUpiRequestId`.
3. Newton validates the encrypted/signed payload, merchant identity, API access, IP restrictions, and business request fields.
4. Newton finds the original payment and the merchant order.
5. Newton finds the refund by `merchantRequestId`.
6. For online refunds, Newton may check and update the online refund status if the refund is still eligible for a status refresh.
7. For UDIR refunds, Newton may check and update the complaint/refund status if the refund is still pending or deemed and the configured rate-limit window allows a check.
8. Newton returns the current refund details in the configured response envelope.

Important identifiers:

- `merchantRequestId`: Merchant refund request id used when the refund was initiated. This is the primary refund lookup key.
- `merchantTransactionId`: Merchant order/original transaction id. Newton uses it to locate the original merchant order and transaction.
- `originalUpiRequestId`: Newton UPI transaction id of the original payment. Use this when the merchant order id is not available.
- `gatewayTransactionId`: Newton UPI transaction id of the original payment in the response.
- `gatewayRefundTransactionId`: Newton UPI transaction id of the refund, returned in the version 2 response when available.
- `gatewayRefundReferenceId`: Gateway/NPCI refund reference id, returned in the version 2 response when available.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/refund/status
```

Payloads use the standard Newton S2S request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Required only for sub-merchant/aggregator integrations. |
| `x-sub-merchant-channel-id` | Required only when `x-sub-merchant-id` is sent. |
| `x-timestamp` | 13-digit epoch-millisecond request timestamp used by merchant signature verification. Must be within 30 minutes of Newton server time. |
| `x-merchant-signature` | Merchant request signature for unsigned/plain business payload requests. |
| `x-request-id` | Optional merchant correlation id. Newton generates one if omitted. |
| `x-session-id` | Optional merchant session/correlation id. Defaults to `x-request-id` if omitted. |
| `x-api-version` | Send `2` for the richer refund-status response. Missing or non-integer values are treated as version `0`. |
| `x-forwarded-for` | Required when the merchant has IP allowlisting configured. The first IP in the header must be allowlisted. |

Path and version parameters:

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route namespace, for example `v1` or the value shared during onboarding. |
| `x-api-version` | header | integer string | No | Response-version selector used by this API. `2` returns the richer response. Omitted/invalid values select the base response. |

Authentication and encryption:

- The route accepts Newton's `EncRequest` envelope forms: JWE encrypted payload, JWS signed payload, or plain business payload where enabled for the merchant.
- JWE requests are decrypted using the key id (`kid`) from the protected header and the Newton/PSP private key. The decrypted content must be a JWS signed body for standard S2S encrypted requests.
- JWS requests are verified using the public key resolved by `kid`.
- Plain business payload requests still go through merchant signature verification. The signature input includes merchant headers, timestamp, and the raw request body.
- For encrypted/signed payloads, `iat` inside the decrypted business payload is required and must be a valid 13-digit epoch-millisecond timestamp.
- Merchant configuration can require JWS or JWS+JWE response wrapping. Otherwise, Newton returns an unsigned response with `X-Response-Signature`.

## Request

### Required Minimum

Lookup by the merchant's original transaction id:

```json
{
  "merchantRequestId": "REFUND12345",
  "merchantTransactionId": "ORDER12345",
  "iat": "1782987330000"
}
```

Lookup by the original Newton UPI transaction id:

```json
{
  "merchantRequestId": "REFUND12345",
  "originalUpiRequestId": "UPI1234567890",
  "iat": "1782987330000"
}
```

`merchantRefundVpa` is accepted for compatibility with refund flows and is validated when sent:

```json
{
  "merchantRequestId": "UDIRREF12345",
  "originalUpiRequestId": "UPI1234567890",
  "merchantRefundVpa": "refunds@merchantbank",
  "iat": "1782987330000",
  "udfParameters": "{\"ticketId\":\"CS-9841\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Merchant refund request id used when the refund was initiated. Must be non-empty. Newton uses this to find the refund record. |
| `merchantTransactionId` | string | Conditional | No default. | Merchant id/reference of the original payment order. Required when `originalUpiRequestId` is omitted. Length 1 to 35. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `originalUpiRequestId` | string | Conditional | No default. | Newton UPI request id of the original payment. Required when `merchantTransactionId` is omitted. Length 1 to 35. Allowed characters: letters and numbers only. |
| `merchantRefundVpa` | string | No | No default. This endpoint validates the field when supplied but does not use it for refund lookup. | Refund VPA field accepted for compatibility with refund APIs. Must be a valid VPA, length 3 to 255, formatted as `name@handle`. |
| `iat` | string | Conditional | No default. Required for encrypted/signed payloads because merchant signature verification validates it. | Issued-at timestamp used for request freshness/signature validation. Send a 13-digit epoch-millisecond value and generate it at request time. |
| `udfParameters` | string | No | No default. Omitted from response if not supplied. | Merchant-defined metadata, usually a JSON-object string. Echoed back in the top-level response. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default.

- `merchantTransactionId` and `originalUpiRequestId`: at least one must be present. If both are present, the product lookup uses `merchantTransactionId`.
- `merchantRefundVpa`: omitted has no impact on the current refund-status lookup. If supplied, it must pass VPA validation.
- `iat`: omitted is accepted only for plain unsigned payload parsing, but encrypted/signed S2S requests fail merchant signature verification without it.
- `x-api-version`: omitted or non-integer values behave as version `0`, returning the base/legacy response shape.

### Validation Rules

Newton validates the decrypted business payload before product lookup:

- `merchantRequestId` must be non-empty.
- At least one of `merchantTransactionId` or `originalUpiRequestId` must be supplied.
- `merchantTransactionId`, when supplied, must be 1 to 35 characters and match the merchant transaction id character rules.
- `originalUpiRequestId`, when supplied, must be 1 to 35 alphanumeric characters.
- `merchantRefundVpa`, when supplied, must be 3 to 255 characters and match VPA format `local-part@handle`.
- `iat`, when required by the request envelope, must be present, be a 13-digit epoch-millisecond timestamp, and be within 30 minutes of Newton server time.

## Refund Lookup and Status Behavior

Original transaction lookup:

- If `merchantTransactionId` is supplied, Newton finds the merchant order for that id and then resolves the original transaction from the order.
- If only `originalUpiRequestId` is supplied, Newton finds the original transaction for the current merchant or sub-merchant and then reads the original `merchantRequestId` from the transaction metadata to find the merchant order.
- If the original transaction/order cannot be resolved, the API returns an error rather than a refund status.

Refund lookup:

- Newton finds the refund using `merchantRequestId` under the authenticated merchant/sub-merchant.
- If no refund exists for that id, the API returns `REQUEST_NOT_FOUND`.
- Refund status is not recreated by this API. Call the refund initiation API first.

Status refresh:

- Online refunds use the online refund status path when the stored refund is eligible for online refund checking.
- UDIR refunds may trigger an NPCI/Olive status check only when the stored refund status is `PENDING`, or when it is `DEEMED` and the configured UDIR mode allows another check.
- UDIR status checks are rate-limited by the transaction-status lower-bound configuration. If the lower-bound interval has not passed, Newton returns the stored refund/complaint state without calling the downstream status service.
- Offline refunds return the stored refund state; this API does not initiate a new offline refund.

## Response

### Top-Level Response

Successful decrypted response:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "originalMerchantRequestId": "ORDER12345",
    "refundRequestId": "REFUND12345",
    "refundAmount": "100.00",
    "refundType": "ONLINE",
    "refundTimestamp": "2026-07-02 10:10:30",
    "remarks": "Customer refund",
    "gatewayTransactionId": "UPI1234567890",
    "gatewayRefundReferenceId": "RRN9876543210",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "gatewayRefundTransactionId": "RFNDUPI123456"
  },
  "udfParameters": "{\"ticketId\":\"CS-9841\"}"
}
```

Top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable top-level API response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable top-level response message. |
| `payload` | object | Refund-status business payload. Shape depends on `x-api-version`. |
| `udfParameters` | string | Echo of request `udfParameters`, omitted when not supplied. |

### Version 2 Payload

Send `x-api-version: 2` to receive this richer payload.

```json
{
  "merchantId": "MERCHANT123",
  "merchantChannelId": "APP",
  "subMerchantId": "SUBMERCHANT123",
  "subMerchantChannelId": "SUBAPP",
  "originalMerchantRequestId": "ORDER12345",
  "refundRequestId": "REFUND12345",
  "refundAmount": "100.00",
  "refundType": "UDIR",
  "refundTimestamp": "2026-07-02 10:10:30",
  "remarks": "Customer complaint refund",
  "merchantRefundVpa": "refunds@merchantbank",
  "riskScore": "LOW",
  "gatewayTransactionId": "UPI1234567890",
  "gatewayRefundReferenceId": "RRN9876543210",
  "gatewayResponseStatus": "PENDING",
  "gatewayResponseCode": "01",
  "gatewayResponseMessage": "PENDING",
  "gatewayRefundTransactionId": "RFNDUPI123456",
  "splitSettlementDetails": {
    "splitType": "AMOUNT",
    "merchantSplit": "90.00",
    "partnersSplit": [
      {
        "partnerId": "PARTNER1",
        "value": "10.00"
      }
    ]
  },
  "crn": "CRN123456",
  "reqAdjCode": "U005",
  "reqAdjFlag": "R",
  "adjFlag": "TCC",
  "adjCode": "S"
}
```

Version 2 field reference:

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Authenticated parent merchant id. |
| `merchantChannelId` | string | Authenticated parent merchant channel id. |
| `subMerchantId` | string | Authenticated sub-merchant id, when the request is made in a sub-merchant context. |
| `subMerchantChannelId` | string | Authenticated sub-merchant channel id, when present. |
| `originalMerchantRequestId` | string | Merchant request/order id of the original payment. |
| `refundRequestId` | string | Merchant refund request id stored on the refund record. |
| `refundAmount` | string | Refund amount formatted with two decimal places. |
| `refundType` | string | Refund category, for example `ONLINE`, `OFFLINE`, or `UDIR`. |
| `refundTimestamp` | string | Timestamp when the refund record was created. |
| `remarks` | string | Refund remarks stored with the refund. |
| `merchantRefundVpa` | string | Decrypted refund payer VPA for online refunds when available and allowed by response construction. |
| `riskScore` | string | Risk score extracted from refund transaction metadata when configured to return risk score as a parameter. |
| `gatewayTransactionId` | string | Newton UPI request id of the original payment. |
| `gatewayRefundReferenceId` | string | Gateway/NPCI refund response/reference id. For UDIR refunds, this can come from the complaint response id. |
| `gatewayResponseStatus` | string | Normalized refund status derived from the gateway response code. Values include `SUCCESS`, `PENDING`, `DEEMED`, and `FAILURE`. |
| `gatewayResponseCode` | string | Gateway/NPCI/refund response code stored or refreshed for the refund. |
| `gatewayResponseMessage` | string | Gateway/NPCI/refund response message stored or refreshed for the refund. |
| `gatewayRefundTransactionId` | string | Newton UPI request id of the refund transaction when available. |
| `splitSettlementDetails` | object | Split settlement details returned when present on the refund record. |
| `crn` | string | UDIR complaint/reference number when available. |
| `reqAdjCode` | string | UDIR requested adjustment code when available. |
| `reqAdjFlag` | string | UDIR requested adjustment flag when available. |
| `adjFlag` | string | UDIR final adjustment flag when available. |
| `adjCode` | string | UDIR final adjustment code when available. |

Version 2 `gatewayResponseStatus` mapping:

| Gateway response code | `gatewayResponseStatus` |
| --- | --- |
| `00` | `SUCCESS` |
| `01`, `91`, `09`, `060`, `070`, `080` | `PENDING` |
| `RB`, `96`, `JPRTO` | `DEEMED` |
| `JPREFD` | `DEEMED` by default for UDIR, or `SUCCESS` when merchant/configuration marks UDIR deemed refunds as success. |
| Any other code | `FAILURE` |

### Base Payload

When `x-api-version` is omitted, invalid, or not `2`, Newton returns the base payload shape.

```json
{
  "merchantId": "MERCHANT123",
  "merchantChannelId": "APP",
  "subMerchantId": "SUBMERCHANT123",
  "subMerchantChannelId": "SUBAPP",
  "merchantRequestId": "REFUND12345",
  "transactionAmount": "500.00",
  "refundAmount": "100.00",
  "gatewayTransactionId": "UPI1234567890",
  "refundGatewayReferenceId": "RRN9876543210",
  "refundMerchantRequestId": "REFUND12345",
  "gatewayResponseCode": "00",
  "gatewayResponseMessage": "SUCCESS"
}
```

Base field reference:

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Authenticated parent merchant id. |
| `merchantChannelId` | string | Authenticated parent merchant channel id. |
| `subMerchantId` | string | Sub-merchant id when `x-api-version > 0` and a sub-merchant context is present. |
| `subMerchantChannelId` | string | Sub-merchant channel id when `x-api-version > 0` and present. |
| `merchantRequestId` | string | Refund request id from the status request. |
| `transactionAmount` | string | Original payment amount formatted with two decimal places. |
| `refundAmount` | string | Refund amount formatted with two decimal places. |
| `gatewayTransactionId` | string | Newton UPI request id of the original payment. |
| `refundGatewayReferenceId` | string | Refund gateway response/reference id when an online refund transaction is available. |
| `refundMerchantRequestId` | string | Refund transaction reference id when an online refund transaction is available. |
| `gatewayResponseCode` | string | Gateway/refund response code stored on the refund. |
| `gatewayResponseMessage` | string | Gateway/refund response message stored on the refund. |

## Error Handling

Errors use the same `EncResponse` transport selected for the integration where possible. The examples below show decrypted error bodies.

HTTP status is not always the same as the business status. Some validation and lookup failures are returned with HTTP 200 and a decrypted `status: "FAILURE"` body; authorization and malformed encrypted payload errors use HTTP 4xx.

### Validation Failure

When both `merchantTransactionId` and `originalUpiRequestId` are omitted:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Both upiRequestId and merchantTransactionId cannot be Nothing.\"",
  "payload": null
}
```

Other field-validation failures use the same `BAD_REQUEST` shape with messages such as:

- `LengthValidation "Field is empty"` for empty `merchantRequestId`.
- `LengthValidation "merchantTransactionId length is not between 1 and 35"`.
- `RegexValidation "merchantTransactionId regex match failed"`.
- `LengthValidation "upiRequestId length is not between 1 and 35"`.
- `RegexValidation "upiRequestId regex match failed"`.
- `RegexValidation "merchantRefundVpaVpa regex failed"`.
- `LengthValidation "merchantRefundVpaVpa length is not between 3 and 255"`.

### Missing or Invalid `iat`

For encrypted/signed requests where `iat` is missing:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty",
  "payload": null
}
```

If the timestamp format is invalid, timestamp validation returns:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number",
  "payload": null
}
```

If the timestamp is too far from server time, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED",
  "payload": null
}
```

### Authentication, Signature, Encryption, and IP Failures

Missing merchant headers, missing raw body/timestamp context, failed JWS verification, failed JWE decryption, invalid merchant request signature, blocked API access, disallowed API access, or IP allowlist failure return an unauthorized response:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

When the merchant exists but the API is blocked or not allowed for that merchant, the message is:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

Malformed decrypted JWE/JWS payload JSON can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantRequestId\" not found",
  "payload": null
}
```

### Original Transaction or Order Not Found

If `merchantTransactionId` resolves to a merchant order that does not have an original transaction:

```json
{
  "status": "FAILURE",
  "responseCode": "UNINITIATED_REQUEST",
  "responseMessage": "UNINITIATED_REQUEST",
  "payload": null
}
```

If `originalUpiRequestId` does not resolve to a transaction for the authenticated merchant/sub-merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Original record not found",
  "payload": null
}
```

### Refund Not Found

If Newton finds the original payment but no refund exists for `merchantRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND",
  "payload": null
}
```

### UDIR Refund State Is Inconsistent

If a stored UDIR refund has no linked complaint id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Udir refund not found",
  "payload": null
}
```

If the linked UDIR complaint cannot be found, Newton returns `REQUEST_NOT_FOUND`.

### Downstream Status Check and Internal Failures

This API may call NPCI or Olive status-check services for eligible pending online/UDIR refunds. If the downstream service times out or is unavailable, clients can see failure responses such as:

```json
{
  "status": "FAILURE",
  "responseCode": "GATEWAY_TIMEOUT",
  "responseMessage": "Timed out from NPCI",
  "payload": null
}
```

or:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_UPI_STATUS",
  "responseMessage": "UPI service is not reachable at the moment",
  "payload": null
}
```

If required persisted response fields are missing while formatting a success response, Newton can return an internal server error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

## Retry and Client Handling Guidance

- Treat `gatewayResponseStatus` as the refund business status, not the top-level `status`. A top-level `SUCCESS` means the status lookup succeeded.
- Persist `gatewayResponseCode`, `gatewayResponseStatus`, `gatewayRefundReferenceId`, and `gatewayRefundTransactionId` for reconciliation.
- Do not retry validation failures without changing the request.
- Do not retry `UNAUTHORIZED`; fix credentials, signature, timestamp, API enablement, or IP allowlisting first.
- For `PENDING` or `DEEMED`, retry with backoff. UDIR status checks are internally rate-limited, so very frequent polling can return the same stored state without a downstream refresh.
- For downstream timeouts or service-unavailable responses, retry with exponential backoff and the same identifiers.
- For `REQUEST_NOT_FOUND`, verify that the refund initiation completed and that `merchantRequestId` is the refund request id, not the original payment order id.
- If both `merchantTransactionId` and `originalUpiRequestId` are available, send the one your reconciliation system treats as authoritative. If both are sent, Newton's current lookup path prioritizes `merchantTransactionId`.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:393)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:3675)
- Request envelope and response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S request decryption/signature verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:66)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response wrapping/signing/encryption: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Request and response API types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1346)
- Transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:605)
- S2S/domain transformer helpers: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:863)
- Core request/response payload types: [src/Newton/Product/Merchant/Transactions/Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:244)
- Refund status business logic: [src/Newton/Product/Merchant/Transactions/Refund.hs](../../src/Newton/Product/Merchant/Transactions/Refund.hs:42)
- Refund status response formatter: [src/Newton/Product/Merchant/Transactions/Transformer.hs](../../src/Newton/Product/Merchant/Transactions/Transformer.hs:88)
- UDIR status refresh behavior: [src/Newton/Product/Merchant/Transactions/RefundHelper.hs](../../src/Newton/Product/Merchant/Transactions/RefundHelper.hs:1054)
- Field validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Common API error bodies: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
