# Push To VPA Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/pushToVpa/status`

## Overview

Push To VPA Status is a server-to-server API used to check the current state of a payout initiated through `POST /api/{apiVersion}/merchants/transactions/pushToVpa`.

The merchant calls this API with the original `merchantRequestId` and merchant payout VPA. Newton finds the payout for the authenticated merchant, validates that the supplied payout VPA belongs to an active refund/payout merchant account, optionally refreshes the status with the configured downstream rail, and returns the latest payout state.

Use this API for backend reconciliation, polling after a `PENDING` or `DEEMED` Push To VPA response, and recovery after a network timeout where the original create-payout response was not received.

Payloads use the standard Newton server-to-server encrypted request and response envelope shared during onboarding. Examples in this guide show decrypted business payloads for readability.

## Business Use Case

Push To VPA Status helps merchants:

- Reconcile a Push To VPA payout using the original merchant idempotency key.
- Distinguish API transport success from payout success or failure.
- Poll a payout that is still `PENDING` or `DEEMED`.
- Fetch gateway response code, message, reference id, and transaction id for settlement and support workflows.
- Receive payee bank-account details after successful reverse penny drop style flows, where enabled.
- Avoid creating duplicate payouts when the first create-payout request may already have reached Newton.

## Integration Flow

1. Merchant initiates a payout through `pushToVpa` and stores the `merchantRequestId`.
2. If the payout response is `PENDING`, `DEEMED`, or unavailable because of a timeout, merchant calls `pushToVpa/status`.
3. Newton decrypts/verifies the S2S envelope and validates merchant headers, timestamp, signature, API access, and IP allowlist where configured.
4. Newton validates the decrypted business payload.
5. Newton finds the payout by `merchantRequestId` and authenticated merchant.
6. Newton validates the supplied `merchantVpa` against the merchant's active refund/payout account configuration.
7. Newton returns the stored terminal status, or refreshes the status with the downstream rail when the payout is non-terminal and the configured PSP/PPI flow requires it.
8. If the payout status changes during the status call, Newton asynchronously triggers the `CUSTOMER_PUSH_TO_VPA` callback.

Important identifiers:

- `merchantRequestId`: Merchant-generated idempotency key sent in the original Push To VPA request. This is the primary lookup key for this status API.
- `merchantVpa`: Merchant payout/source VPA used for the original payout. It must map to an active refund/payout merchant account for the authenticated merchant.
- `gatewayTransactionId`: Newton/UPI transaction id for the payout.
- `gatewayReferenceId`: Downstream gateway/UPI reference id when available.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/pushToVpa/status
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API route version shared during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-merchant-id` | Yes | Merchant id configured with Newton. |
| `x-merchant-channel-id` | Yes | Merchant channel id configured with Newton. |
| `x-timestamp` | Yes | Current request timestamp used for request freshness and merchant signature verification. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain business payload transport. JWS/JWE request modes carry signature verification in the envelope. |
| `x-api-version` | Recommended | API behavior version. Use the version shared during onboarding. `payeeAcType` is returned only when this header resolves to a value greater than `0`. |
| `x-request-id` | No | Merchant request trace id. If omitted, Newton generates one and returns it in the response headers. |
| `x-session-id` | No | Merchant session trace id. If omitted, Newton uses `x-request-id`. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP in the comma-separated value must be allowlisted. |
| `Authorization` | Conditional | Used only for merchant configurations that require it. Follow the onboarding contract. |

Response headers include `x-requestid`, `x-sessionid`, and, for unsigned/plain response mode, `X-Response-Signature`.

### Authentication, Signing, and Encryption

The route accepts Newton's standard S2S request envelope:

- JWE encrypted payload with fields `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- JWS signed payload with fields `payload`, `signature`, and `protected`.
- Plain JSON business payload only where the merchant configuration permits unsigned transport.

For JWE transport, Newton decrypts the body and expects the decrypted content to be a signed payload, then verifies that signature. For JWS transport, Newton verifies the signature before parsing the business body. For plain payload transport, Newton verifies `x-merchant-signature` over merchant headers, timestamp, and raw body.

For signed or encrypted request bodies, send `iat` inside the decrypted business payload. Newton validates `iat` as a freshness timestamp before running product logic. For plain payload transport, `iat` is not used by the signature layer.

Newton also verifies:

- Merchant existence from `x-merchant-id` and `x-merchant-channel-id`.
- API access for `pushToVpaStatus`.
- Merchant API block/allow configuration.
- Optional IP allowlist through `x-forwarded-for`.
- `x-timestamp` freshness.

## Request

The examples below show the decrypted business payload. Production requests must be wrapped in the configured S2S envelope.

### Required Minimum

```json
{
  "merchantRequestId": "PAYOUT12345",
  "merchantVpa": "merchant@bank"
}
```

### With Request Freshness and UDF Metadata

```json
{
  "merchantRequestId": "PAYOUT12345",
  "merchantVpa": "merchant@bank",
  "iat": "1720000000000",
  "udfParameters": "{\"ticketId\":\"SUPPORT-4921\",\"source\":\"recon\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Original merchant idempotency/order reference sent in `pushToVpa`. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `merchantVpa` | string | Yes | No default. | Merchant payout/source VPA. The request validator only rejects an empty value; product logic then verifies that this VPA maps to an active refund/payout merchant account for the authenticated merchant. |
| `iat` | string | Conditional | No business default. | Issued-at timestamp used by S2S signature/encryption freshness validation. Required for JWS/JWE transport even though the business type is nullable. |
| `udfParameters` | string | No | No default. Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the top-level response when supplied. |

### Defaults and Omitted Field Behavior

This API does not create a new payout and does not default any business fields.

- `merchantRequestId` and `merchantVpa` are always required.
- `iat` has no product-level default. It is required by the authentication layer for signed/encrypted request modes.
- `udfParameters` is not stored on the payout by this status API; it is echoed in the synchronous response and passed to the callback if this status call changes the payout state.

## Validation Rules

Newton validates the decrypted request body before status lookup:

- `merchantRequestId` must be non-empty, at most 35 characters, and match `^[-._]*([a-zA-Z0-9][-._]*)+$`.
- `merchantVpa` must be non-empty. VPA format and merchant ownership are enforced by the refund/payout account lookup rather than the request validator.
- `udfParameters`, when supplied, must be a string containing a valid JSON object and must not contain disallowed characters matched by the validation regex.

Newton then performs business lookup and status processing:

- The payout must exist for the authenticated merchant and the supplied `merchantRequestId`.
- The supplied `merchantVpa` must map to an active refund/payout merchant account for that merchant. Depending on encryption migration flags, Newton may match by encrypted VPA hash, plaintext VPA, or either.
- The status API does not use `merchantVpa` to find the payout. It finds the payout by `merchantRequestId`, then separately validates that the merchant VPA is configured.
- If the stored payout is terminal (`SUCCESS`, `FAILURE`, `EXPIRED`, or `DECLINED`) on the Olive/Mprepay path, Newton returns the stored payout without calling the downstream status check.
- For YESBIZ and PPI-enabled flows, `PENDING` and `DEEMED` statuses can cause Newton to check CBS/debit state or NPCI status and update the payout before returning.
- If merchant configuration contains `pushToVpaTimeLimit`, old pending payouts can be marked `FAILURE` with a payout timeout code once the configured limit has expired.
- If the status changes during the call, Newton forks a `CUSTOMER_PUSH_TO_VPA` callback after the synchronous response path updates the payout.

## Status Behavior

Top-level response fields describe API processing. Payout state is in `payload.gatewayResponseStatus`.

| Payout state | Meaning | Client action |
| --- | --- | --- |
| `SUCCESS` | Payout is successful. | Mark successful after normal reconciliation/callback checks. Store gateway ids and response code/message. |
| `PENDING` | Payout is still being processed or downstream status is not final. | Poll status with the same `merchantRequestId` and wait for callback. Do not create a new payout. |
| `DEEMED` | Downstream status is uncertain and may later become success or failure. | Continue polling or wait for callback. Do not create a new payout unless Newton confirms the original can be abandoned. |
| `FAILURE` | Payout failed. | Treat as failed unless your Newton integration team advises otherwise for a specific gateway code. |
| `EXPIRED` or `DECLINED` | Payout reached another terminal state. | Treat as terminal and reconcile using gateway code/message. |

Gateway code/message are derived from stored NPCI/downstream response where available. For example, non-terminal statuses usually map to gateway code `01`, `DEEMED` maps to `RB`, `DECLINED` maps to `ZA`, and missing/unknown downstream response can map to fallback code `JP91`.

## Success Response

The examples below show decrypted business responses. Production responses are signed or encrypted according to the merchant response strategy.

### Pending Payout

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "customerVpa": "customer@bank",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "PAYOUT12345",
    "transactionAmount": "100.00",
    "gatewayReferenceId": "123456789012",
    "gatewayTransactionId": "NEWTONUPI123456",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Pending",
    "gatewayResponseStatus": "PENDING"
  }
}
```

### Successful Payout

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "customerVpa": "customer@bank",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "PAYOUT12345",
    "transactionAmount": "100.00",
    "gatewayReferenceId": "123456789012",
    "gatewayTransactionId": "NEWTONUPI123456",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Success",
    "gatewayResponseStatus": "SUCCESS",
    "bankAccountHash": "8f0e2b8f7f7f4c1b...",
    "payeeAccountNumber": "encrypted-account-number",
    "payeeMaskedAccountNumber": "XXXXX1234",
    "payeeName": "Customer Name",
    "payeeIfsc": "HDFC0000001",
    "payeeAcType": "SAVINGS"
  },
  "udfParameters": "{\"ticketId\":\"SUPPORT-4921\",\"source\":\"recon\"}"
}
```

Notes:

- Payee bank-account fields are returned only when the payout is `SUCCESS` and account details are available in the stored payout. Otherwise they are omitted.
- `payeeAccountNumber` is the encrypted account number and is returned only for merchants enabled for that behavior.
- `payeeMaskedAccountNumber` is derived from the account number as `XXXXX` plus the last four digits.
- `payeeAcType` is included only when `x-api-version` resolves to a value greater than `0`.
- `udfParameters` is included only when supplied in the request.

### Failed Payout With Top-Level Success

A completed status check can return top-level `SUCCESS` while the payout itself is failed. Always read `payload.gatewayResponseStatus`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "customerVpa": "customer@bank",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "PAYOUT12345",
    "transactionAmount": "100.00",
    "gatewayReferenceId": "123456789012",
    "gatewayTransactionId": "NEWTONUPI123456",
    "gatewayResponseCode": "U30",
    "gatewayResponseMessage": "Debit failed",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

## Response Field Reference

### Top-Level Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. Successful processing returns `SUCCESS`; use `payload.gatewayResponseStatus` for payout status. |
| `responseCode` | string | Top-level API response code. Successful processing returns `SUCCESS`. |
| `responseMessage` | string | Top-level API response message. Successful processing returns `SUCCESS`. |
| `payload` | object | Latest payout status payload. Present on successful processing. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `customerVpa` | string | Payee/customer VPA stored on the payout. Omitted if not available. |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantRequestId` | string | Original merchant request id/reference id for the payout. |
| `transactionAmount` | string | Payout amount formatted with two decimal places. |
| `gatewayReferenceId` | string | Gateway/UPI response/reference id when available. |
| `gatewayTransactionId` | string | Newton/UPI transaction id for the payout. |
| `gatewayResponseCode` | string | Gateway or mapped Newton response code for the payout state. |
| `gatewayResponseMessage` | string | Gateway or mapped Newton response message for the payout state. Omitted if no message can be derived. |
| `gatewayResponseStatus` | string | Current payout status, for example `SUCCESS`, `PENDING`, `DEEMED`, `FAILURE`, `EXPIRED`, or `DECLINED`. |
| `bankAccountHash` | string | Hash of payee account details, available only for successful payouts where account details exist. |
| `payeeAccountNumber` | string | Encrypted payee account number, available only for successful payouts and enabled merchants. |
| `payeeMaskedAccountNumber` | string | Masked payee account number, formatted as `XXXXX` plus the last four digits, when account details are available. |
| `payeeName` | string | Payee account name when available. |
| `payeeIfsc` | string | Payee account IFSC when available. |
| `payeeAcType` | string | Payee account type from stored payee info. Returned only for `x-api-version > 0`. |

## Error Handling

Failure responses use the same response transport as successful responses whenever the request reaches a layer that can produce a Newton body. The examples below show decrypted bodies.

Most business and validation failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

When `payload` is empty, it is omitted from the JSON response. HTTP status can vary by layer: request field validation is commonly returned with HTTP 200 and a `BAD_REQUEST` body, authentication and IP failures use HTTP 401, not-found lookups can use HTTP 404 or be wrapped by the common flow handler, and downstream recovery failures can use HTTP 500. Clients should inspect the decrypted body whenever one is available.

### Request Validation Failures

Invalid `merchantRequestId` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

Invalid `merchantRequestId` characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchant request id regex failed\""
}
```

Empty `merchantVpa`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantVpa field is empty\""
}
```

Invalid `udfParameters` JSON-object string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Malformed JSON or wrong field type can fail before business validation, for example with an `INVALID_DATA` body generated by payload parsing:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantRequestId\" not found"
}
```

### Authentication, Signature, Encryption, and Timestamp Failures

Missing merchant headers, missing timestamp, invalid merchant credentials, invalid plain-payload signature, stale timestamp, IP allowlist failure, or unsigned requests where not permitted can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

JWS/JWE verification or decrypt/signature failures can also return:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Signature mismatch in the configured verification layer can return:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "Signature Verification Mismatch"
}
```

Malformed encrypted payload content can return an invalid-data body:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"upiRequestId\" not found"
}
```

Client handling: regenerate the signed/encrypted request with current `x-timestamp` and `iat`. Do not replay stale envelopes.

### Merchant Access, API Access, and IP Restriction Failures

If the merchant exists but `pushToVpaStatus` is blocked or not in the merchant's allowed API list:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If `whitelistedIps` is configured and the first IP in `x-forwarded-for` is missing or not allowlisted:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: do not retry automatically. Fix merchant headers, credentials, API enablement, or IP allowlist configuration.

### Business Lookup Failures

Original payout not found for the authenticated merchant and `merchantRequestId`:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

`merchantVpa` is not an active refund/payout VPA for the authenticated merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Merchant refund vpa is not valid"
}
```

Client handling: verify that the status request uses the same `merchantRequestId` and merchant headers as the original payout, and that `merchantVpa` is the payout VPA configured with Newton.

### Downstream and Status-Refresh Failures

The status API can call downstream services while refreshing non-terminal payouts. If downstream status is inconclusive or times out in the NPCI status check, Newton can keep and return the existing payout status, usually `PENDING` or `DEEMED`, with top-level `SUCCESS`.

If a downstream recovery path itself fails, such as CBS debit status returning an unsupported response or virtual-account reversal/refund failing, Newton can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

If the configured `pushToVpaTimeLimit` has expired for an old pending payout, Newton can mark the payout as failed and return top-level `SUCCESS` with failed payout status. The gateway code can be a resolved payout timeout code.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "customerVpa": "customer@bank",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantRequestId": "PAYOUT12345",
    "transactionAmount": "100.00",
    "gatewayReferenceId": "123456789012",
    "gatewayTransactionId": "NEWTONUPI123456",
    "gatewayResponseCode": "JPPTO",
    "gatewayResponseMessage": "Payout timed out",
    "gatewayResponseStatus": "FAILURE"
  }
}
```

Client handling: for `INTERNAL_SERVER_ERROR`, retry status with the same payload after a short delay. Do not create a replacement payout until status/callback/reconciliation confirms the original is terminal.

### Internal Errors

Unexpected database, encryption, missing required stored data, or cache failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry status with the same identifiers using backoff. Escalate to Newton support with `x-requestid`, `merchantRequestId`, and `gatewayTransactionId` if available.

## Retry and Client Handling

- Store `merchantRequestId`, `gatewayTransactionId`, `gatewayReferenceId`, `gatewayResponseStatus`, `gatewayResponseCode`, and `gatewayResponseMessage` from every readable response.
- Treat top-level `status = "SUCCESS"` as "status request processed by Newton"; use `payload.gatewayResponseStatus` for payout state.
- Poll with the same `merchantRequestId` and `merchantVpa`. Do not generate a new `merchantRequestId` for status.
- For `PENDING` or `DEEMED`, poll at a controlled interval or wait for `CUSTOMER_PUSH_TO_VPA` callback. Avoid tight polling because the status path can call downstream systems.
- For network timeout/no HTTP response from status, retry the same status request with a fresh S2S envelope and current timestamps.
- For validation failures, fix the payload and retry with the same original payout identifiers.
- For authentication, signature, encryption, timestamp, API access, or IP failures, fix the integration issue before retrying. Regenerate signatures and encrypted payloads; do not replay stale signed/encrypted bodies.
- For `REQUEST_NOT_FOUND`, confirm whether the original `pushToVpa` call reached Newton. If the create-payout call timed out, retry status after a short delay before initiating a new payout.
- For `INVALID_DATA` with `Merchant refund vpa is not valid`, correct the configured/sent payout VPA. Retrying unchanged will not help.
- For `INTERNAL_SERVER_ERROR` after a payout may exist, retry status and reconcile with callbacks before creating another payout.

## Source References

- Route family and path version capture: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- Route declaration: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:410)
- Route handler and signature middleware call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2420)
- Request and response payload types/validation: [src/Newton/Product/Merchant/Transactions/Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:617)
- Transformer validation and response construction route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:277)
- Response wrapper and `payeeAcType` version gating: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:298)
- Top-level response type: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4014)
- Product status lookup and callback behavior: [src/Newton/Product/Merchant/Transactions/Payout.hs](../../src/Newton/Product/Merchant/Transactions/Payout.hs:101)
- Status refresh logic for PPI, YESBIZ, and Olive/Mprepay paths: [src/Newton/Product/Merchant/Transactions/Payout.hs](../../src/Newton/Product/Merchant/Transactions/Payout.hs:226)
- Status response payload construction and account-field behavior: [src/Newton/Product/Merchant/Transactions/Payout.hs](../../src/Newton/Product/Merchant/Transactions/Payout.hs:501)
- Payout timeout and failure update behavior: [src/Newton/Product/Merchant/Transactions/Payout.hs](../../src/Newton/Product/Merchant/Transactions/Payout.hs:174)
- Refund transaction lookup by merchant request id: [src/Newton/Storage/QueriesMiddleware/RefundTransaction.hs](../../src/Newton/Storage/QueriesMiddleware/RefundTransaction.hs:64)
- Refund/payout merchant VPA lookup: [src/Newton/Storage/QueriesMiddleware/RefundMerchant.hs](../../src/Newton/Storage/QueriesMiddleware/RefundMerchant.hs:27)
- Common validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:12)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:43)
- Response signing/encryption wrapper: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
