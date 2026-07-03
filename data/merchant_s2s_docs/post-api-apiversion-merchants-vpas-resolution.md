# VPA Resolution API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/resolution`

## Overview

VPA Resolution is a server-to-server API used by a merchant backend to send Newton the result of an asynchronous dynamic-VPA resolution request.

In dynamic VPA integrations, Newton can call the merchant to resolve the payee VPA/sub-merchant details needed to continue a UPI authorization. When the merchant's callback endpoint receives that request, the merchant resolves the payee details in its own system and posts the result back to this Newton endpoint with the same `npciTxnId`.

This endpoint is an asynchronous acknowledgment API. A `SUCCESS` response from this API means Newton accepted the response payload and attempted to publish it to the waiting internal flow. It does not by itself mean the customer's UPI transaction has completed successfully.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

Use the VPA Validity APIs for direct VPA validation. Use this API only when Newton has initiated an async VPA resolution flow and supplied an `npciTxnId` to correlate the response.

## Business Use Case

VPA Resolution helps merchants:

- Complete asynchronous dynamic-VPA resolution for a UPI payment authorization.
- Return the resolved payee or sub-merchant identity, MCC, account, and approval result to Newton.
- Approve a dynamic VPA transaction with response code `00`.
- Decline or fail a dynamic VPA transaction with a concrete UPI/gateway response code such as `ZH`, `SA`, or another code agreed during onboarding.
- Correlate the merchant's response to the original Newton callback using `npciTxnId`.
- Carry sub-merchant metadata such as brand name, legal name, franchise, ownership type, genre, MID, SID, and TID into Newton's downstream transaction processing.

Important identifiers:

- `npciTxnId`: Correlation id from Newton's VPA resolution callback. This is the primary key for matching the merchant response to the waiting Newton flow.
- `orderId`: Order/reference id from the authorization context. Send the value supplied by Newton in the callback when available.
- `responseCode`: Merchant's resolution decision. Use `00` only when the VPA is resolved and the transaction may proceed.

## Integration Flow

1. A customer initiates a UPI payment flow involving a dynamic VPA.
2. Newton receives the NPCI authorization request and determines that merchant-side VPA resolution is required.
3. Newton sends the merchant a configured `VPA_RESOLUTION_REQAUTHDETAIL` callback payload. The callback includes `type: "R"`, `npciTxnId`, `vpa`, `payerVpa`, amount, order id, and payer account details based on the configured callback version/query.
4. The merchant validates Newton's callback, resolves the dynamic VPA/sub-merchant details in its own system, and decides whether to approve or fail the authorization.
5. The merchant calls `POST /api/{apiVersion}/merchants/vpas/resolution` with the same `npciTxnId`.
6. Newton decrypts and verifies the S2S payload, validates merchant headers and request freshness, then publishes the resolution payload using correlation key `vpaResolution_` plus the request `npciTxnId`.
7. Newton returns an API acknowledgment:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS"
}
```

8. The waiting Newton transaction flow consumes the resolution result if it is still within the async wait window, then continues the payment or marks it failed based on the merchant response.

The default async wait timeout is configured as 9 seconds in the codebase and can be overridden by environment or merchant configuration. Treat the timeout shared during onboarding as authoritative for production.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/resolution
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. This endpoint does not currently branch response shape by `x-api-version`. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Optional. Send only when your integration uses sub-merchant headers for this flow. |
| `x-sub-merchant-channel-id` | Optional. Send only when your integration uses sub-merchant headers for this flow. |
| `x-timestamp` | 13-digit epoch milliseconds within Newton's freshness window. |
| `x-merchant-signature` | Required for plaintext/unsigned envelope integrations. Signature input includes merchant ids, timestamp, and raw body. |
| `x-request-id` | Optional merchant-generated request id for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Depending on merchant configuration, the request body can be plaintext, JWS, or JWE:

- JWE request body fields: `protected`, `encryptedKey`, `iv`, `cipherText`, `tag`.
- JWS request body fields: `payload`, `signature`, `protected`.
- Plaintext business payloads are supported by the generic type but are normally limited to configured plaintext or test integrations.

For signed or encrypted requests, include `iat` in the decrypted business payload. Newton validates `iat` before product logic. `iat` and `x-timestamp` must be 13-digit epoch milliseconds within the accepted clock-skew window.

Newton responses follow the merchant's configured response strategy:

- `JWS`: signed response envelope.
- `JWS_AND_JWE`: signed then encrypted response envelope.
- Other configured strategies: plaintext business response with `X-Response-Signature`.

Response headers include `x-requestid`, `x-sessionid`, and, for plaintext response strategies, `X-Response-Signature`.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the value shared during onboarding. |

## Request

### Required Minimum

At API decode level, the business payload requires only `status`, `responseCode`, `responseMessage`, and `npciTxnId`; signed/encrypted production requests also require `iat` through the S2S verification layer.

```json
{
  "status": "FAILURE",
  "responseCode": "ZH",
  "responseMessage": "Beneficiary payment address incorrect",
  "npciTxnId": "NPCI000000000000001",
  "iat": "1782967530000"
}
```

For a successful dynamic-VPA payment resolution, send the full resolved merchant/sub-merchant context:

```json
{
  "status": "SUCCESS",
  "responseCode": "00",
  "responseMessage": "SUCCESS",
  "merchantName": "Acme Retail",
  "accountNumber": "123456789012",
  "ifsc": "HDFC0001234",
  "mcc": "5411",
  "txnApproval": "Y",
  "orderId": "ORDER12345",
  "brandName": "Acme",
  "legalName": "Acme Retail Private Limited",
  "franchise": "Acme Store",
  "merchantType": "SMALL",
  "ownershipType": "PRIVATE",
  "genre": "ONLINE",
  "onboardingType": "AGGREGATOR",
  "gstin": "27ABCDE1234F1Z5",
  "businessName": "Acme Retail",
  "mid": "ACME000123",
  "sid": "ACMEWEB01",
  "tid": "ACMETERM01",
  "payeeAccType": "CURRENT",
  "udfParameters": "{\"storeId\":\"S001\"}",
  "npciTxnId": "NPCI000000000000001",
  "iat": "1782967530000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `status` | string | Yes | No default. | Merchant resolution status. Send `SUCCESS` when `responseCode` is `00`; send `FAILURE` for a failed/declined resolution. The API route requires this field but does not validate the value beyond JSON type. |
| `responseCode` | string | Yes | No default. | Merchant resolution response code. Use `00` for approved/resolved VPA details. Use a concrete failure code such as `ZH`, `SA`, or another onboarded code when the transaction must not proceed. |
| `responseMessage` | string | Yes | No default. | Human-readable message for the merchant resolution result, for example `SUCCESS` or `Beneficiary payment address incorrect`. |
| `merchantName` | string | Conditional | No default. If omitted, Newton publishes no merchant name. | Resolved payee/sub-merchant display name. Required by the downstream dynamic-VPA payment flow for an accepted `00` response and for preserving a specific non-`00` failure code. |
| `accountNumber` | string | No | No default. | Resolved payee account number. The immediate API route does not require it; downstream dynamic-VPA validation treats account number as optional. Send only over the encrypted/signed transport agreed during onboarding. |
| `ifsc` | string | No | No default. | Resolved payee IFSC. The immediate API route does not require it; downstream dynamic-VPA validation treats IFSC as optional. |
| `mcc` | string | Conditional | No default. | Resolved merchant category code. Required by the downstream dynamic-VPA payment flow for accepted `00` responses and for honoring a specific non-`00` failure code. |
| `txnApproval` | string | Conditional | No default. | Transaction approval flag. Expected values are `Y` or `N`. Required by the downstream dynamic-VPA payment flow. |
| `orderId` | string | Conditional | No default. | Order/reference id associated with the authorization. Send the `orderId` from Newton's VPA-resolution callback when available. Required by downstream dynamic-VPA payment validation. |
| `brandName` | string | Conditional | No default. | Resolved merchant brand name. Required by downstream dynamic-VPA payment validation. |
| `legalName` | string | Conditional | No default. | Resolved merchant legal name. Required by downstream dynamic-VPA payment validation. |
| `franchise` | string | Conditional | No default. | Franchise/store-chain name. Required by downstream dynamic-VPA payment validation. |
| `merchantType` | string | Conditional | No default. | Merchant size/type. Expected values are `SMALL` or `LARGE`. Required by downstream dynamic-VPA payment validation. |
| `ownershipType` | string | Conditional | No default. | Ownership category. Expected values are `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, or `OTHERS`. Required by downstream dynamic-VPA payment validation. |
| `genre` | string | Conditional | No default. | Commerce channel. Expected values are `ONLINE` or `OFFLINE`. Required by downstream dynamic-VPA payment validation. |
| `onboardingType` | string | Conditional | No default. | Onboarding source. Expected values are `BANK` or `AGGREGATOR`. Required by downstream dynamic-VPA payment validation. |
| `gstin` | string | No | No default. | GSTIN for the resolved merchant/sub-merchant, when available. |
| `businessName` | string | No | No default. | Business name for the resolved merchant/sub-merchant, when different from display/legal name. |
| `mid` | string | No | No default. | Merchant identifier for the resolved merchant/sub-merchant. |
| `sid` | string | No | No default. | Store/sub-merchant identifier for the resolved merchant/sub-merchant. |
| `tid` | string | No | No default. | Terminal identifier for the resolved merchant/sub-merchant. |
| `payeeAccType` | string | No | No default. | Payee account type, for example `CURRENT`, `SAVINGS`, or another account type agreed during onboarding. |
| `iat` | string | Conditional | No business default. Required for JWS/JWE requests. | Issued-at timestamp used by the S2S signature/encryption validation layer. Send a 13-digit epoch-millisecond timestamp within the accepted freshness window. |
| `udfParameters` | string | No | No default. | Merchant-defined JSON object encoded as a string. If supplied, it is published with the resolution payload and may be carried into downstream transaction/order data. |
| `npciTxnId` | string | Yes | No default. | NPCI transaction id from Newton's VPA-resolution callback. Newton uses it to publish to `vpaResolution_` plus this value. Do not generate a new value. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned by this API when omitted.

- `npciTxnId`, `status`, `responseCode`, and `responseMessage`: required by the request type. Missing or `null` values are rejected during JSON decode.
- `iat`: nullable in the business type but required by the S2S layer for signed/encrypted requests.
- Optional fields: omitted or `null` values become absent in the published internal payload.
- Unknown extra fields: ignored by JSON parsing and not included in the published payload. Do not rely on undeclared fields being preserved.
- Blank strings: the immediate API route does not perform field-format or length validation. However, downstream dynamic-VPA validation expects non-empty values for the conditional fields listed above.
- `responseCode`: the endpoint does not enforce `00` vs non-`00`. The waiting transaction flow uses the value after this API acknowledges the request.

### Nested Request Objects

There are no nested JSON objects in the decrypted request body. `udfParameters`, when used, is a JSON object encoded as a string.

### Validation and Processing Behavior

Before product logic, Newton:

1. Parses the request as a Newton S2S envelope or plaintext business payload.
2. Finds and loads the merchant using `x-merchant-id` and `x-merchant-channel-id`; optional sub-merchant headers are also resolved when supplied.
3. Decrypts JWE or verifies JWS where applicable.
4. Validates `iat` for signed/encrypted requests.
5. Runs `merchantSignatureVerificationV2`, which validates merchant API access, blocked/allowed API configuration, IP allowlist if configured, `x-timestamp`, and plaintext request signature where applicable.

Product behavior:

1. Newton computes `resolvedPubSubId` by prefixing `npciTxnId` with `vpaResolution_`.
2. Newton records async external latency for the `npciTxnId`.
3. Newton forks a publish operation for the payload with API name `vpaResolution`.
4. The publish helper looks up the Redis key formed by prefixing `resolvedPubSubId` with `pubSub-txnId_` to find the waiting channel.
5. If the channel exists, Newton publishes the resolution payload through Redis pub/sub or Redis Streams depending on deployment configuration.
6. If the channel is missing, Newton records a monitor event and still returns the normal success acknowledgment.
7. The HTTP response is built immediately after the publish fork is scheduled; the API does not wait for the waiting transaction flow to finish downstream validation.

Downstream dynamic-VPA validation is stricter than this API's immediate request decoder. In the payment authorization flow, a successful `responseCode: "00"` is expected to include non-empty `brandName`, `legalName`, `franchise`, `merchantType`, `ownershipType`, `genre`, `onboardingType`, `merchantName`, `mcc`, `orderId`, and `txnApproval`. If these are missing, the waiting flow can treat the merchant response as invalid and fail the transaction with a generic VPA-resolution failure.

## Request Examples

### Approved Dynamic-VPA Resolution

```json
{
  "status": "SUCCESS",
  "responseCode": "00",
  "responseMessage": "SUCCESS",
  "merchantName": "Acme Retail",
  "accountNumber": "123456789012",
  "ifsc": "HDFC0001234",
  "mcc": "5411",
  "txnApproval": "Y",
  "orderId": "ORDER12345",
  "brandName": "Acme",
  "legalName": "Acme Retail Private Limited",
  "franchise": "Acme Store",
  "merchantType": "SMALL",
  "ownershipType": "PRIVATE",
  "genre": "ONLINE",
  "onboardingType": "AGGREGATOR",
  "gstin": "27ABCDE1234F1Z5",
  "businessName": "Acme Retail",
  "mid": "ACME000123",
  "sid": "ACMEWEB01",
  "tid": "ACMETERM01",
  "payeeAccType": "CURRENT",
  "udfParameters": "{\"storeId\":\"S001\",\"terminal\":\"T01\"}",
  "npciTxnId": "NPCI000000000000001",
  "iat": "1782967530000"
}
```

### Declined Dynamic-VPA Resolution

Send a concrete failure code and keep the same `npciTxnId`. When you want Newton to preserve the specific failure code, include the same merchant-resolution metadata you would send for an approved response whenever it is available.

```json
{
  "status": "FAILURE",
  "responseCode": "ZH",
  "responseMessage": "Beneficiary payment address incorrect",
  "merchantName": "Acme Retail",
  "mcc": "5411",
  "txnApproval": "N",
  "orderId": "ORDER12345",
  "brandName": "Acme",
  "legalName": "Acme Retail Private Limited",
  "franchise": "Acme Store",
  "merchantType": "SMALL",
  "ownershipType": "PRIVATE",
  "genre": "ONLINE",
  "onboardingType": "AGGREGATOR",
  "npciTxnId": "NPCI000000000000002",
  "iat": "1782967560000"
}
```

### Minimal Technical Failure Response

Use this only when the merchant genuinely cannot resolve the VPA metadata. Newton may treat the downstream transaction as a generic resolution failure instead of preserving a more specific response code.

```json
{
  "status": "FAILURE",
  "responseCode": "ZH",
  "responseMessage": "Beneficiary payment address incorrect",
  "npciTxnId": "NPCI000000000000003",
  "iat": "1782967590000"
}
```

## Newton Callback Context

This API is normally called after Newton sends the merchant a dynamic-VPA resolution callback. The callback payload is not the request body for this endpoint, but it supplies the values the merchant should use for correlation and decisioning.

Example decrypted callback payload from Newton:

```json
{
  "type": "R",
  "vpa": "store123@bank",
  "payerVpa": "customer@upi",
  "payerName": "Customer Name",
  "payerMaskedAccNum": "XXXXXX7890",
  "payerIfsc": "HDFC0001234",
  "payerMcc": "0000",
  "amount": "100.00",
  "custRefId": "123456789012",
  "npciTxnId": "NPCI000000000000001",
  "purposeCode": "00",
  "initiationMode": "00",
  "payerAccType": "SAVINGS",
  "orderId": "ORDER12345",
  "remarks": "Order payment"
}
```

The actual callback fields can vary by merchant callback version and configured GraphQL query. For example, payer account number may be masked or omitted based on configuration. The `npciTxnId` must still be preserved and sent back in this API.

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API acknowledgment status. Success value is `SUCCESS`. |
| `responseCode` | string | API acknowledgment response code. Success value is `SUCCESS`. |
| `responseMessage` | string | API acknowledgment response message. Success value is `SUCCESS`. |

There is no success `payload` object for this API.

### Example Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS"
}
```

### Success Semantics

Treat the success response as "Newton accepted this S2S response payload." It does not guarantee:

- the waiting `npciTxnId` channel still existed;
- the internal publish consumer had already read the payload;
- the downstream dynamic-VPA transaction validation succeeded;
- the customer-facing payment status is `SUCCESS`.

Use normal transaction status or callbacks to determine the final payment outcome.

## Failure Scenarios

Failure responses use the same encrypted/signed response transport as successful responses when the merchant context and response strategy are available. The examples below show decrypted business bodies.

HTTP status can vary by deployment and failure layer; some environments normalize error HTTP status to `200`. Clients should read decrypted `status`, `responseCode`, and `responseMessage`.

### Malformed JSON or Request Envelope

Returned when the HTTP request body cannot be parsed as a valid Newton S2S request envelope or plaintext business payload.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Error in requestBody : Invalid requestBody Format"
}
```

If the body is syntactically valid JSON but a signed payload decodes to the wrong business shape, the parser can expose the underlying Aeson message. The exact field path can vary. Example missing `npciTxnId`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.npciTxnId: key \"npciTxnId\" not found"
}
```

Client handling: fix the JSON/envelope or required field set and resend only if the original async VPA-resolution wait window is still open.

### Missing or Invalid `iat`

For signed/encrypted requests, `iat` is required by the S2S layer even though the business type is nullable.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

If the timestamp format is invalid:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

If the timestamp is outside the accepted freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Client handling: regenerate `iat`, `x-timestamp`, the envelope, and the signature before retrying. Do not replay a stale encrypted/signed request body.

### Missing Merchant Headers

Returned when Newton cannot resolve required merchant headers such as `x-merchant-id`, `x-merchant-channel-id`, or required timestamp/signature headers.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: correct the header set and signature input. This is an integration/configuration error, not a payment outcome.

### Signature or Encryption Verification Failure

Returned when plaintext `x-merchant-signature` verification fails, JWS verification fails, JWE decryption fails, or the configured key id cannot be used.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

For a malformed or missing JWS/JWE `kid`, the request can instead fail before authorization with an invalid-data body such as:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding kId"
}
```

Client handling: verify key id, key version, payload signing, encryption, and raw-body signature construction. Retry with a newly signed/encrypted body.

### API Not Enabled or Blocked for Merchant

Returned when merchant configuration blocks this API or the merchant's allowed API list does not include `vpaResolution`.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: do not retry automatically. Ask Newton operations/onboarding to enable the API for the merchant profile.

### IP Allowlist Failure

If the merchant has configured whitelisted IPs and the request source from `x-forwarded-for` is absent or not allowed, Newton rejects the call.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: send from an allowlisted egress IP or update the merchant allowlist through the standard onboarding process.

### Internal Server, Cache, or Response-Signing Failure

Unexpected server failures, missing runtime configuration, response signing/encryption failures, or infrastructure errors can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry the same business decision with a fresh envelope only if the async wait window is still open. If the wait window may have elapsed, rely on transaction status/callbacks and coordinate with Newton support using `npciTxnId`.

## Downstream Outcomes Not Returned by This API

The following outcomes can happen after this API has already returned `SUCCESS`:

| Scenario | Downstream behavior |
| --- | --- |
| `npciTxnId` does not match an active waiting async request, or the response arrives after the timeout | The API can still acknowledge `SUCCESS`, but the waiting transaction flow may already have failed with a generic VPA-resolution failure such as beneficiary payment address incorrect. |
| `responseCode` is non-`00` and the payload passes downstream validation | The transaction is failed using the supplied merchant response code where supported. |
| `responseCode` is `00` but required merchant/sub-merchant metadata is missing or blank | Downstream validation can fail and map to a generic `ZH`/beneficiary-address failure. |
| The internal publish fork records a missing Redis pub/sub channel | The API can still acknowledge `SUCCESS`; the response is not guaranteed to affect the already-ended waiting flow. |

Client handling: use the final transaction callback/status APIs for customer-facing state. Do not treat the API acknowledgment as the final payment status.

## Retry and Client Handling Guidance

- Respond as soon as possible after receiving Newton's VPA-resolution callback. The default async wait timeout in code is 9 seconds and may be changed by configuration.
- Reuse the exact `npciTxnId` from Newton's callback. Do not generate a new id and do not use the merchant order id in its place.
- For network timeouts while calling this API, retry the same business decision with a freshly generated `iat`, `x-timestamp`, signature, and encrypted/signed envelope.
- Keep the business response stable for a given `npciTxnId`. Do not retry a failed resolution as success unless Newton explicitly instructs you to correct an integration error.
- If you receive an authentication, timestamp, API-not-enabled, or IP-allowlist failure, fix the integration/configuration issue first. Blind retries will usually fail until headers, keys, or merchant configuration are corrected.
- If the API returns `SUCCESS` after the timeout window, it may be too late for the waiting transaction flow. Reconcile using transaction status/callbacks and `npciTxnId`.
- Include the full merchant/sub-merchant metadata for `responseCode: "00"`, and include it for non-`00` responses when you want the specific response code to be preserved downstream.

## Source References

- Route type: [Core.hs](../../src/Newton/App/Routes/Core.hs:176)
- Route handler: [Core.vpaResolution](../../src/Newton/App/Routes/Core.hs:5104)
- Request type: [Newton.Product.Merchant.Vpa.Types.VpaResolutionRequest](../../src/Newton/Product/Merchant/Vpa/Types.hs:206)
- Response type: [Newton.Product.Merchant.Vpa.Types.VpaResolutionResponse](../../src/Newton/Product/Merchant/Vpa/Types.hs:250)
- Product route and ack response: [VpaResolution.hs](../../src/Newton/Product/Merchant/Vpa/VpaResolution.hs:16)
- Redis publish helper: [NpciSwitchHelper.publish](../../src/Newton/Utils/NpciSwitchHelper.hs:193)
- Async outbound callback flow: [DynamicVpaResolution.Flow](../../src/Newton/External/DynamicVpaResolution/Flow.hs:76)
- Outbound callback payload builder: [DynamicVpaResolution.Helper](../../src/Newton/External/DynamicVpaResolution/Helper.hs:20)
- Outbound callback field selection: [GqlHelper.populateGqlQueryForVpaResolutionReqAuthDetails](../../src/Newton/External/MerchantCallback/Newton/GqlHelper.hs:234)
- Downstream merchant-response validation: [ReqAuthDetails.DynamicVpa](../../src/Newton/Product/NpciSwitch/Financial/ReqAuthDetails/DynamicVpa.hs:203)
- S2S request envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request decryption and payload verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/API access verification: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- S2S response signing/encryption wrapper: [RoutesHelper.flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:38)
- Timestamp validation: [DateTime.isValidTimestamp](../../src/Newton/Utils/DateTime.hs:108)
- Success and common error constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
