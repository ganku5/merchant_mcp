# CBS Balance API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/cbs/balance`

## Overview

CBS Balance is a server-to-server API used to fetch the balance of the merchant's configured CBSHub virtual account.

The merchant calls this API from its backend when it needs the latest available balance for an operational CBS or virtual-account ledger. Newton verifies the merchant S2S envelope, validates the request, resolves the merchant CBSHub configuration, sends a `FETCH_VA_BALANCE` request to the configured CBSHub endpoint, and returns the downstream balance result.

Use this API for merchant-side virtual-account balance checks. Do not use it to fetch a customer's linked UPI bank-account balance; use the customer account balance API for that flow.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

CBS Balance helps merchants:

- Check available funds before initiating payout, push-to-VPA, refund, or settlement operations that depend on the merchant virtual-account balance.
- Refresh an internal treasury, operations, or reconciliation dashboard with the latest CBSHub balance.
- Investigate failed or delayed disbursement flows where available balance may be a factor.
- Keep an auditable request id for each balance-check attempt.

This endpoint does not select an account from the request body. Newton uses the merchant's configured CBSHub partner identifier, currently `yesbankPayoutPartnerKey` for the supported Yespay/CBSHub path, to determine the virtual account whose balance is checked.

## Integration Flow

1. Merchant backend creates a unique `merchantRequestId` for the balance-check attempt.
2. Merchant wraps the request in the agreed Newton S2S signed or encrypted envelope.
3. Merchant calls `POST /api/{apiVersion}/merchants/cbs/balance` with the configured merchant headers.
4. Newton verifies the merchant payload/envelope, merchant signature, timestamp, API access, and request body.
5. Newton confirms the runtime PSP mode supports this API. The current product path supports the `YESBIZ` PSP mode.
6. Newton builds a CBSHub check-balance request using `merchantRequestId` as the CBSHub `requestId`, action `FETCH_VA_BALANCE`, and the merchant's configured CBSHub partner identifier.
7. Newton decrypts and maps the CBSHub response into the S2S response.
8. Merchant decrypts the response and reads the gateway fields inside `payload` to determine the actual balance-check result.

Important identifiers:

- `merchantRequestId`: Merchant-generated request id for this balance-check attempt. Newton forwards it to CBSHub as `requestId` and returns it in `payload.merchantRequestId`.
- `udfParameters`: Optional merchant metadata. When supplied and valid, Newton echoes it at the top level of the response.

## Endpoint

```http
POST /api/{apiVersion}/merchants/cbs/balance
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Request timestamp used for merchant signature freshness checks. |
| `x-merchant-signature` | Merchant signature for unsigned/plain S2S envelopes, unless your configured encrypted/signed envelope does not require this header. |
| `x-sub-merchant-id` | Conditional. Send only if your onboarding uses sub-merchant credentials. |
| `x-sub-merchant-channel-id` | Conditional. Send only if your onboarding uses sub-merchant credentials. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. The route accepts the shared `EncRequest` envelope shape, but production integrations should use the signed/encrypted mode configured for the merchant. For signed or encrypted payloads, include `iat` in the decrypted business payload so Newton can validate request freshness.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Request

### Required Minimum

```json
{
  "merchantRequestId": "CBSBAL202607020001",
  "iat": "1782973800000"
}
```

With merchant metadata:

```json
{
  "merchantRequestId": "CBSBAL202607020002",
  "iat": "1782973800000",
  "udfParameters": "{\"ledger\":\"PAYOUTS\",\"runId\":\"RUN20260702\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Merchant-generated id for the balance-check attempt. Must be non-empty. Newton sends this downstream as the CBSHub `requestId` and returns it in the response payload. |
| `iat` | string | Conditional | No default. Plain unsigned test payloads do not require it; signed or encrypted S2S payloads require it for freshness validation. | Issued-at timestamp used by the S2S signature/encryption validation path. Use the timestamp format agreed during onboarding. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Must parse as a JSON object string and must not contain characters rejected by Newton's UDF validation. Echoed in the response when supplied. |

### Defaults and Omitted Field Behavior

Fields not listed here are not part of the public request contract for this endpoint.

- `merchantRequestId`: no default. Empty values are rejected.
- `iat`: no default. Required when the configured S2S envelope needs freshness validation.
- `udfParameters`: no default. If omitted, `udfParameters` is omitted from the response.
- CBSHub partner/account selection: not supplied by the client. Newton reads the merchant's configured CBSHub partner identifier from merchant configuration.

### Nested Request Objects

This request has no nested business objects. Do not send customer, account, credential, amount, or VPA fields for this API; they are not used by the CBS balance flow.

## Response

### How To Interpret Status

A top-level `status` of `SUCCESS` means Newton accepted the request and received a parseable CBSHub response. It does not by itself mean the balance was fetched successfully.

Use the gateway fields inside `payload` for the actual CBSHub balance result:

- Treat the balance check as successful when `payload.gatewayResponseCode == "00"` and `payload.gatewayResponseStatus == "SUCCESS"`.
- Treat any other `payload.gatewayResponseCode` as a failed CBSHub balance check.
- Read `payload.balance` only on a successful gateway result and only when the field is present.

Newton computes `payload.gatewayResponseStatus` from the CBSHub response code: `00` becomes `SUCCESS`; every other code becomes `FAILURE`.

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton wrapper status. For accepted CBSHub responses, this is `SUCCESS`. |
| `responseCode` | string | Newton wrapper response code. For accepted CBSHub responses, this is `SUCCESS`. |
| `responseMessage` | string | Newton wrapper response message. For accepted CBSHub responses, this is `SUCCESS`. |
| `payload` | object | CBSHub balance-check result mapped by Newton. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when request `udfParameters` is omitted. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantRequestId` | string | CBSHub request id. This is the request `merchantRequestId` returned from the downstream response. |
| `gatewayResponseStatus` | string | `SUCCESS` when `gatewayResponseCode` is `00`; otherwise `FAILURE`. |
| `gatewayResponseCode` | string | CBSHub result code. Success value is `00`. |
| `gatewayResponseMessage` | string | CBSHub result message. |
| `balance` | string | Available balance returned by CBSHub. Omitted when CBSHub does not return a balance, including failure responses. |

### Example Successful Balance Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantRequestId": "CBSBAL202607020001",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Balance fetched successfully",
    "balance": "1250000.50"
  }
}
```

With echoed merchant metadata:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantRequestId": "CBSBAL202607020002",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Balance fetched successfully",
    "balance": "1250000.50"
  },
  "udfParameters": "{\"ledger\":\"PAYOUTS\",\"runId\":\"RUN20260702\"}"
}
```

### Example CBSHub Business Failure Response

When CBSHub returns a valid response with a non-success code, Newton keeps the top-level wrapper as `SUCCESS` and places the CBSHub result in `payload`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantRequestId": "CBSBAL202607020003",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "P013",
    "gatewayResponseMessage": "Unable to fetch balance please try again after sometime"
  }
}
```

In gateway failures, `balance` is omitted.

## Failure Responses

Failures before a parseable CBSHub business response use the standard Newton error response body after decryption. HTTP status can vary by layer, but clients should read the decrypted `status`, `responseCode`, and `responseMessage`.

### Validation Failure

`merchantRequestId` is present but empty:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId field is empty\""
}
```

`udfParameters` is not a valid JSON-object string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

The decrypted payload cannot be parsed as `CoreCbsCheckBalanceRequest`, for example because `merchantRequestId` is missing:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantRequestId\" not found"
}
```

### Authentication, Encryption, Or Timestamp Failure

Missing merchant headers, signature mismatch, invalid encrypted payload, invalid key id, invalid IP whitelist, or stale timestamps are rejected before product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the merchant or sub-merchant is configured but this API is not allowed or is blocked:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

For signed or encrypted requests where `iat` is missing or invalid, Newton can return an invalid-data response from freshness validation:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

### Merchant Configuration Failure

The CBS balance product route currently supports the `YESBIZ` PSP mode. If the running PSP configuration is not supported for this API:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "API not supported"
}
```

If the merchant is enabled for this API but the required CBSHub partner identifier is missing from merchant configuration, the request cannot be built:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### CBSHub Lookup Or Business Failure

CBSHub may reject the configured partner, deny API access, find no eligible balance record, or be unable to fetch the virtual-account balance. When CBSHub still returns a valid business response, Newton returns top-level `SUCCESS` and marks the gateway result as `FAILURE`:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantRequestId": "CBSBAL202607020004",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "P005",
    "gatewayResponseMessage": "API access not given"
  }
}
```

Clients should treat this as a failed balance check even though the wrapper status is `SUCCESS`.

### Downstream Transport, Proxy, Or Decryption Failure

If Newton cannot reach CBSHub through the proxy, the CBSHub response cannot be decrypted, or the response cannot be parsed as the expected check-balance response, the downstream call path maps the failure to an internal-server response for this external service:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Unexpected Errors

Unexpected runtime errors, missing internal options, unavailable keys, or other unhandled server-side failures also return the standard internal error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry, Idempotency, And Client Handling

- Store `merchantRequestId` with each balance-check attempt. Newton does not perform endpoint-specific idempotency lookup for this API; the id is primarily used as the CBSHub request id and response correlation id.
- For a retry of the same network-uncertain attempt, reuse the same `merchantRequestId` only if your CBSHub onboarding confirms duplicate request ids are safe for balance enquiries.
- For a new balance refresh attempt, generate a new `merchantRequestId`.
- Do not infer balance success from top-level `status`. Use `payload.gatewayResponseCode == "00"` and `payload.gatewayResponseStatus == "SUCCESS"`.
- Display or store `payload.balance` only when it is present on a successful gateway result.
- For validation, authentication, API-enabled, or merchant-configuration errors, correct the request or onboarding configuration before retrying.
- For downstream transport or temporary CBSHub failures, retry with backoff according to your operational policy. Avoid tight polling loops.

## Source References

- Route type: [Core.hs](../../src/Newton/App/Routes/Core.hs:415)
- Route handler and middleware sequence: [Core.hs](../../src/Newton/App/Routes/Core.hs:2438)
- Request and payload types: [Types.hs](../../src/Newton/Product/Merchant/Transactions/Types.hs:676)
- S2S transformer route and validation call: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:284)
- S2S response wrapper: [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:312)
- S2S response type: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4030)
- Product flow and supported PSP mode: [Payout.hs](../../src/Newton/Product/Merchant/Transactions/Payout.hs:121)
- CBSHub response-to-payload mapping: [Payout.hs](../../src/Newton/Product/Merchant/Transactions/Payout.hs:551)
- CBSHub check-balance call: [Flow.hs](../../src/Newton/External/YespayHub/Flow.hs:39)
- CBSHub request construction: [Helper.hs](../../src/Newton/External/YespayHub/Helper.hs:213)
- CBSHub request and response types: [Types.hs](../../src/Newton/External/YespayHub/Types.hs:230)
- Merchant payload verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature and API-access verification: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request validators: [Common.hs](../../src/Newton/Validation/Common.hs:168)
- Validation error wrapping: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Downstream proxy error mapping: [External.hs](../../src/Newton/Utils/External.hs:99)
- Standard success and invalid-data constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
- Bad-request and internal-error constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124)
- Unauthorized/API-not-enabled constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
