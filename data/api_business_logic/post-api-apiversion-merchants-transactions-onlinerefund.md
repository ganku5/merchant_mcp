# Online Refund API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/onlineRefund`

## Overview

Online Refund is a merchant server-to-server API used to initiate a UPI refund for a successful merchant transaction.

The merchant calls this API with a new refund reference, the original merchant transaction reference, the refund amount, the refund source VPA, and a refund reason. Newton validates the merchant, the original transaction, refund eligibility, refund amount limits, refund window, optional split-settlement details, and then creates or resumes the online refund flow through the configured refund rail.

Use this API when the merchant wants Newton to push the refund online instead of only recording an offline refund.

## Business Use Case

Online Refund helps merchants:

- Refund a full or partial amount against an existing successful merchant transaction.
- Use the merchant's refund VPA as the source for the refund debit.
- Track the refund against a merchant-generated refund id.
- Avoid duplicate refund processing through `merchantRequestId`.
- Prevent over-refunds across multiple refund attempts for the same original transaction.
- Support split-settlement refund allocation when split settlement is enabled and the original transaction used split settlement.
- Receive a synchronous acknowledgement containing the current gateway/refund status and identifiers for reconciliation.

## Integration Flow

1. Merchant identifies the original successful transaction to refund.
2. Merchant calls `onlineRefund` with a unique `merchantRequestId` for this refund and the original transaction's `merchantTransactionId`.
3. Newton verifies the merchant headers, request signature/envelope, API access, IP restrictions, and request body.
4. Newton looks up the original merchant order and transaction.
5. Newton checks refund enablement, refund expiry, refund amount limits, duplicate/idempotency state, and split-settlement rules.
6. Newton creates or fetches the online refund transaction and attempts/status-checks the downstream refund flow.
7. Merchant decrypts/verifies the response and stores `refundMerchantRequestId`, `refundGatewayReferenceId`, and `gatewayResponseCode` for reconciliation.

Important identifiers:

- `merchantRequestId`: Merchant-generated refund idempotency key. Use a new value for each distinct refund attempt.
- `merchantTransactionId`: Merchant request/order id of the original transaction being refunded.
- `gatewayTransactionId`: Newton UPI transaction id of the original payment.
- `refundGatewayReferenceId`: Gateway/NPCI reference for the refund attempt when available.
- `refundMerchantRequestId`: Merchant refund id returned in the response. For this API it is the same logical id as `merchantRequestId`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/onlineRefund
```

Payloads use the standard Newton server-to-server request and response envelope configured during onboarding. The examples below show decrypted business payloads for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant integration. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | JSON request body. |
| `x-merchant-id` | Yes | Merchant identifier issued by Newton. Used to resolve the merchant before payload verification. |
| `x-merchant-channel-id` | Yes | Merchant channel id issued by Newton. |
| `x-sub-merchant-id` | Conditional | Required only when the request is made for a configured sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` when the request is made for a configured sub-merchant. |
| `x-timestamp` | Yes | 13-digit epoch milliseconds timestamp. For unsigned/plain requests, Newton validates it is within the configured freshness window. |
| `x-merchant-signature` | Conditional | Required for plain/unsigned S2S payloads. Signature is computed over merchant ids, timestamp, and raw request body using the merchant API key and configured signature strategy. |
| `x-request-id` | No | Client request id for tracing. Newton generates one if omitted and echoes it in the response headers. |
| `x-session-id` | No | Client session/correlation id. Defaults to `x-request-id` when omitted and is echoed in response headers. |
| `x-forwarded-for` | Conditional | Required when merchant IP allowlisting is configured. Newton validates the first IP in the comma-separated list. |
| `x-api-version` | Recommended | API behavior/version selector. For this response, sub-merchant response fields are included only above version 0 when applicable. |

### Authentication, Signing, and Encryption

`onlineRefund` is handled by the standard S2S payload verification path:

- Plain/unsigned payload: request body is the decrypted business JSON. Send `x-merchant-signature`; Newton verifies the signature and timestamp.
- JWS payload: request body contains `payload`, `signature`, and `protected`. Newton verifies the JWS with the merchant public key configured in Newton.
- JWE payload: request body contains `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`. Newton decrypts the JWE, expects the decrypted payload to be a signed JWS, and then verifies the JWS.
- Response: Newton returns either a plain response with `X-Response-Signature`, a signed JWS response, or an encrypted JWE response, based on the merchant's configured response strategy.

Envelope examples:

```json
{
  "payload": "<base64url-jws-payload>",
  "signature": "<base64url-jws-signature>",
  "protected": "<base64url-jws-header>"
}
```

```json
{
  "protected": "<base64url-jwe-header>",
  "encryptedKey": "<base64url-encrypted-key>",
  "iv": "<base64url-iv>",
  "cipherText": "<base64url-ciphertext>",
  "tag": "<base64url-auth-tag>"
}
```

For signed or encrypted requests, include `iat` in the decrypted business payload. Newton validates it before route processing.

## Request

### Minimum Decrypted Request

```json
{
  "merchantRequestId": "REFUND12345",
  "refundAmount": "100.00",
  "merchantRefundVpa": "refunds@merchantbank",
  "merchantTransactionId": "ORDER12345",
  "merchantRefundReason": "Customer cancellation",
  "iat": "1793511000000"
}
```

### Request With Original Transaction Timestamp

Use `originalTransactionTimestamp` when the original transaction date is known and the integration needs partitioned lookup. The value must parse as an IST timestamp with timezone offset.

```json
{
  "merchantRequestId": "REFUND12346",
  "refundAmount": "25.00",
  "merchantRefundVpa": "refunds@merchantbank",
  "merchantTransactionId": "ORDER12346",
  "originalTransactionTimestamp": "2026-07-02T11:30:00+05:30",
  "merchantRefundReason": "Partial refund",
  "iat": "1793511000000",
  "udfParameters": {
    "refundBatchId": "BATCH-20260702"
  }
}
```

### Request With Split Settlement

Send `splitSettlementDetails` only when split settlement is enabled and the original transaction was a split-settlement transaction. For a partial refund of a split-settlement transaction, the refund split must be `AMOUNT`.

```json
{
  "merchantRequestId": "REFUND12347",
  "refundAmount": "30.00",
  "merchantRefundVpa": "refunds@merchantbank",
  "merchantTransactionId": "ORDER12347",
  "merchantRefundReason": "Item returned",
  "iat": "1793511000000",
  "splitSettlementDetails": {
    "splitType": "AMOUNT",
    "merchantSplit": "20.00",
    "partnersSplit": [
      {
        "partnerId": "PARTNER001",
        "value": "10.00"
      }
    ]
  }
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Unique merchant refund reference/idempotency key. Length 1 to 35. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `refundAmount` | string | Yes | No default. | Refund amount in exact two-decimal format, for example `100.00`. Must be greater than `0.00`. |
| `merchantRefundVpa` | string | Yes | No default. | Merchant VPA to debit for the refund. Must be a valid VPA, length 3 to 255. Newton also looks up a configured refund merchant for this VPA. |
| `merchantTransactionId` | string | Yes | No default. | Merchant request/order id of the original transaction. Length 1 to 35. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `originalTransactionTimestamp` | string | No | If omitted, Newton searches without the explicit timestamp partition. | Timestamp of the original transaction, for example `2026-07-02T11:30:00+05:30`. Used for original transaction lookup and refund expiry validation when supplied. |
| `merchantRefundReason` | string | Yes | No default. | Refund remarks/reason. Must be non-empty. Stored as refund remarks. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by signed/encrypted request validation. Required by the route for JWS/JWE payloads. Plain/unsigned payloads do not use this field for `validateIAT`, but `x-timestamp` is still required. |
| `udfParameters` | object or JSON-object string | No | Omitted from response when absent. | Merchant-defined metadata. Must be either a JSON object or a string containing a JSON object. Characters `/ # - ( ) * ! % ~ \`` are rejected by validation. Echoed in the success response. |
| `splitSettlementDetails` | object | Conditional | No default. | Required only for partial refunds of split-settlement original transactions. Rejected when split settlement is not enabled or not applicable. |

Fields not listed here are not part of the documented business payload and are not used by this API. There are no request-level defaults for this API.

### `splitSettlementDetails`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `splitType` | string | Yes | Allowed values: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. For online refund partial split-settlement refunds, the product logic requires `AMOUNT`. |
| `merchantSplit` | string | Conditional | Merchant share. Must be a non-negative amount or percentage with two decimals when supplied. |
| `partnersSplit` | array of objects | Conditional | Partner/vendor shares. Partner ids may be validated against the merchant vendor list when vendor validation is enabled. |

For `AMOUNT`, `merchantSplit` plus all partner `value` fields must equal `refundAmount`.

For `PERCENTAGE`, `merchantSplit` plus all partner `value` fields must equal `100.00`.

For `DEFAULT` and `LATER`, do not send `merchantSplit` or `partnersSplit`.

### `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `partnerId` | string | Yes | Partner/vendor id. Must be non-empty. |
| `value` | string | Yes | Partner amount or percentage with two decimals. |

## Validation and Processing Rules

### Request Validation

Newton validates the decrypted request before product logic:

- Required JSON fields must be present and of the expected type.
- `merchantRequestId` and `merchantTransactionId` must be 1 to 35 characters and match the allowed id pattern.
- `refundAmount` must match `^[0-9]+\\.[0-9][0-9]$` and be greater than `0.00`.
- `merchantRefundVpa` must pass VPA format and length validation.
- `originalTransactionTimestamp`, when present, must parse as an offset timestamp such as `2026-07-02T11:30:00+05:30`.
- `merchantRefundReason` must be non-empty.
- `udfParameters`, when present, must be a JSON object or a string containing a JSON object and must pass the configured restricted-character check.
- `splitSettlementDetails`, when present, is validated for amount/percentage formatting, totals, feature enablement, and partner/vendor validity where configured.

Validation errors are returned as `BAD_REQUEST` with details in `responseMessage` where the validation layer constructs a body.

### Merchant, API Access, and IP Checks

Before product logic, Newton:

- Resolves the merchant using `x-merchant-id` and `x-merchant-channel-id`.
- Resolves the sub-merchant when sub-merchant headers are sent.
- Verifies request signature/envelope.
- Checks `blockedApiNames` and `allowedApiNames` merchant configuration for `onlineRefund`.
- Checks `whitelistedIps` if configured. The first value from `x-forwarded-for` must be present in the allowlist.
- Loads merchant configuration used by refund validation.

### Original Transaction Lookup

For this API, `merchantTransactionId` is mapped to the original transaction lookup path:

1. Newton finds the merchant order for refund using `merchantTransactionId`, merchant/sub-merchant context, and `originalTransactionTimestamp` if supplied.
2. The merchant order must have an associated transaction id. Otherwise, the request is treated as uninitiated.
3. Newton finds a valid successful/deemed merchant transaction for that merchant order.
4. Newton attempts to find the paired customer-side transaction when needed for on-us refund processing.

The request type does not expose `originalUpiRequestId`; this API identifies the original transaction by `merchantTransactionId`.

### Refund Enablement and Expiry

For a new refund id, Newton checks whether `ONLINE` refunds are allowed for the merchant/sub-merchant through `allowedRefundTypes`. If merchant-specific config is absent, parent/global config may be used.

Refund expiry is based on `transactionExpiryForOnlineRefund` from sub-merchant or merchant store configuration. If neither is set, the code defaults to `180` days. If `originalTransactionTimestamp` is present, it is checked before original lookup; the stored original transaction timestamp is also checked for new refunds.

### Duplicate and Idempotency Behavior

`merchantRequestId` is the refund idempotency key.

- If no existing refund is found for `merchantRequestId`, Newton creates a new online refund.
- If an existing online refund is found for the same `merchantRequestId` and it belongs to the same original transaction, Newton does not create a second refund. It fetches the existing refund transaction and may perform a status check if the current status is non-terminal.
- If the existing refund id belongs to a different original transaction, Newton rejects the request with `INVALID_DATA` and message `Refund Transaction Id mismatch`.
- If the existing refund record has no linked refund transaction id, Newton rejects with `INVALID_DATA` and message `RefundTransactionId not found`.

Newton also uses a Redis refund lock per merchant and original UPI transaction id while validating total refunded amount. Parallel refund attempts for the same original transaction can be rejected with `Multiple Parallel Refund Request Raised`.

### Amount and Split-Settlement Rules

Newton sums previous refunds for the original transaction and rejects the request if:

```text
current refundAmount + previous refunded amount > original transaction amount
```

Split-settlement behavior:

- If the original transaction was not a split-settlement flow, sending `splitSettlementDetails` is rejected.
- If the refund is a full refund for a split-settlement transaction, sending `splitSettlementDetails` is rejected because the original split can be used.
- If the refund is a partial refund for a split-settlement transaction, `splitSettlementDetails` is required and must use `splitType: "AMOUNT"`.
- The current refund split plus prior refund splits must not exceed each participant's original transaction split amount.

### Downstream Refund Status

The synchronous response is an API-level success when Newton accepts/processes the refund request. Read the nested gateway fields for the actual refund outcome:

- `gatewayResponseCode = "00"` maps to a successful refund.
- `gatewayResponseCode` in `01`, `91`, `09`, `060`, `070`, `080` maps to a pending refund.
- `gatewayResponseCode` in `RB`, `96` maps to deemed.
- Other response codes generally map to failure.

For some downstream timeouts or unavailable responses, Newton may return the existing/original refund state rather than failing the HTTP/API call. Clients should store the returned identifiers and use the refund status API or callbacks to reconcile pending outcomes.

## Response

### Success Response Example

This is the decrypted business response body.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12345",
    "transactionAmount": "100.00",
    "refundAmount": "25.00",
    "gatewayTransactionId": "UPI1234567890",
    "refundGatewayReferenceId": "527412345678",
    "refundMerchantRequestId": "REFUND12346",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS"
  },
  "udfParameters": {
    "refundBatchId": "BATCH-20260702"
  }
}
```

### Pending Response Example

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12345",
    "transactionAmount": "100.00",
    "refundAmount": "25.00",
    "gatewayTransactionId": "UPI1234567890",
    "refundGatewayReferenceId": "527412345678",
    "refundMerchantRequestId": "REFUND12346",
    "gatewayResponseCode": "91",
    "gatewayResponseMessage": "PENDING"
  }
}
```

### Response Envelope Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API-level status. For a successfully processed route response this is `SUCCESS`. |
| `responseCode` | string | API-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | API-level response message. Success value is `SUCCESS`. |
| `payload` | object | Refund response payload. Present on success. |
| `udfParameters` | object or string | Echo of request `udfParameters` when supplied. Omitted when absent. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Parent merchant id. |
| `merchantChannelId` | string | Parent merchant channel id. |
| `subMerchantId` | string | Sub-merchant id. Present only for sub-merchant requests and API versions above 0. |
| `subMerchantChannelId` | string | Sub-merchant channel id. Present only for sub-merchant requests and API versions above 0. |
| `merchantRequestId` | string | Original transaction merchant request/order id, not the refund id. |
| `transactionAmount` | string | Original transaction amount formatted to two decimals. |
| `refundAmount` | string | Refund amount formatted to two decimals. |
| `gatewayTransactionId` | string | Original transaction UPI request id. |
| `refundGatewayReferenceId` | string | Gateway/NPCI refund reference id. Normally present in successful route responses. |
| `refundMerchantRequestId` | string | Refund merchant request id. For this API, this corresponds to request `merchantRequestId`. |
| `gatewayResponseCode` | string | Gateway/refund response code. Use this field for refund outcome and reconciliation. |
| `gatewayResponseMessage` | string | Gateway/refund response message. |
| `splitSettlementDetails` | object | Split-settlement details applied to the refund, when present. |

## Failure Scenarios

Failure bodies use the standard Newton error shape when the failure path constructs an `ErrorResponse`. Depending on where the failure occurs, the HTTP status may be `400`, `401`, or in several product/business cases `200` with a failure body. For signed/encrypted integrations, failures that occur before response encryption/signing may be returned as a plain error body.

Always parse the decrypted body and use `status`, `responseCode`, and `responseMessage`.

### Validation Failure

Example: invalid amount format or invalid id.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Other request validation messages can include:

- `merchantRequestId length not between 1 and 35`
- `merchant request id regex failed`
- `merchantTransactionId length is not between 1 and 35`
- `merchantRefund Vpa length is not between 3 and 255`
- `merchantRefundVpa regex failed`
- `timestamp value not valid`
- `merchantRefundReason field is empty`
- `JSON Object regex match failed for udfParameters`
- `Expected Object or String type for udfParamaters`

### Missing or Malformed Required JSON Field

If a required business field such as `merchantRequestId`, `refundAmount`, `merchantRefundVpa`, `merchantTransactionId`, or `merchantRefundReason` is absent or has the wrong JSON type, JSON parsing can fail before business validation. Treat this as a non-retryable request error and correct the payload.

Example shape can vary by the parse layer:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Error in $: key \"refundAmount\" not found"
}
```

### Authentication, Signature, Encryption, or Timestamp Failure

Examples:

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
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

These are non-retryable until the client fixes headers, keys, JWS/JWE construction, `iat`, `x-timestamp`, or clock skew.

### Merchant API Access or IP Restriction Failure

If `onlineRefund` is blocked or not in the merchant's allowed API list:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If merchant IP allowlisting is configured and `x-forwarded-for` is missing or not allowlisted:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If online refunds are not enabled through `allowedRefundTypes`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ONLINE Refund is not Allowed"
}
```

### Original Transaction or Order Failure

If the original merchant order has no associated transaction:

```json
{
  "status": "FAILURE",
  "responseCode": "UNINITIATED_REQUEST",
  "responseMessage": "UNINITIATED_REQUEST"
}
```

If the original transaction cannot be found or is not valid for refund, the code paths can return `INVALID_DATA`, `REQUEST_NOT_FOUND`, or a lookup-specific error.

Representative example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Original record not found"
}
```

### Refund Window Expired

If the original transaction is older than the configured refund window:

```json
{
  "status": "FAILURE",
  "responseCode": "REFUND_TAT_EXPIRED",
  "responseMessage": "TAT expired for refund"
}
```

### Duplicate or Idempotency Conflict

Same `merchantRequestId`, same original transaction: Newton treats this as idempotent and returns the existing refund's current status.

Same `merchantRequestId`, different original transaction:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Refund Transaction Id mismatch"
}
```

Existing refund record without a refund transaction:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "RefundTransactionId not found"
}
```

Parallel refund lock contention:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Multiple Parallel Refund Request Raised"
}
```

### Invalid Refund Amount

If current refund plus prior refunds exceeds the original transaction amount:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_REFUND_AMOUNT",
  "responseMessage": "INVALID_REFUND_AMOUNT"
}
```

### Split-Settlement Failure

Examples:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SplitSettlement not Allowed"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SplitSettlementDetails not Required"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "SplitSettlementDetails not Found in Request Body"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Split Details"
}
```

Other split validation messages include `Amount Sum Mismatch`, `Invalid Percentage Split`, and `Invalid Partner`.

### Refund Payee VPA Not Active

For certain on-us/NPCI refund paths, Newton validates that the original payer VPA can receive the refund.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Refund payee VPA is not active"
}
```

### Downstream Pending, Timeout, or Failure

Downstream refund rails can return success, pending, deemed, or failure codes. These are normally represented inside a `SUCCESS` API response payload through `gatewayResponseCode` and `gatewayResponseMessage`, not necessarily as an API-level failure.

If the downstream response is unavailable, Newton can return the original refund state. Retry by status-checking first rather than blindly creating another refund id.

### Internal Error

Unexpected server-side failures use the standard internal error shape when mapped by the error layer.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Use a unique `merchantRequestId` for each distinct refund. Do not reuse it for a different original transaction.
- If the HTTP call times out after Newton may have received the request, retry once with the same `merchantRequestId` to get the existing refund state, or call the refund status API using the same refund id.
- Do not retry validation, authentication, API access, IP allowlist, refund-window, or invalid-amount failures until the request/configuration is corrected.
- Treat `gatewayResponseCode` values that map to pending/deemed as non-terminal or reconciliation-required, depending on your business process. Store the identifiers and poll/status-check or wait for callbacks.
- Avoid concurrent refund calls for the same original transaction. Newton uses a refund lock and may reject parallel attempts.
- For partial split-settlement refunds, calculate split participant amounts before calling the API. The current refund split plus prior refund splits cannot exceed the original participant split.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:379)
- Route handler and middleware chain: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2348)
- Request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:11)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request and response business types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1263)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:590)
- Online refund request transformer: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:747)
- Online refund response transformer: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:525)
- API-level online refund validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:125)
- Common field validation rules: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:256)
- Core refund routing and refund enablement: [src/Newton/Product/Merchant/Transactions/Refund.hs](../../src/Newton/Product/Merchant/Transactions/Refund.hs:26)
- Online refund product logic: [src/Newton/Product/Merchant/Transactions/RefundHelper.hs](../../src/Newton/Product/Merchant/Transactions/RefundHelper.hs:77)
- Core refund response mapping: [src/Newton/Product/Merchant/Transactions/Transformer.hs](../../src/Newton/Product/Merchant/Transactions/Transformer.hs:24)
- Split-settlement validation and defaults: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4539)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:41)
