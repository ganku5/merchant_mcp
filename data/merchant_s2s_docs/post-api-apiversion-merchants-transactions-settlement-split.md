# Settlement Split API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/settlement/split`

## Overview

Settlement Split is a server-to-server API used to provide the final settlement split for a transaction whose split was intentionally deferred at payment registration time.

Use this API only for transactions that were created with `splitSettlementDetails.splitType = "LATER"` and later completed as merchant orders. The call updates the stored merchant order with the actual merchant and partner settlement shares. Newton validates the merchant, request signature/envelope, merchant API access, optional IP allowlist, original order state, refund state, split-settlement enablement, partner ids where configured, and split totals before storing the split.

The API is not a general split override API. It does not apply to transactions that already carried an `AMOUNT`, `PERCENTAGE`, or resolved `DEFAULT` split, and it cannot be used after a refund has been initiated for the same `merchantRequestId`.

## Business Use Case

Settlement Split helps merchants and aggregators:

- Register or create a payment first, while deferring partner allocation until after customer payment.
- Calculate vendor, seller, marketplace, or partner shares after order confirmation.
- Apply the final split to an already initiated transaction before settlement processing.
- Keep the original customer payment flow simple while still reconciling partner-level settlement.

Typical use:

1. Merchant creates a payment or intent using a split-settlement-capable transaction API.
2. Merchant sends `splitSettlementDetails.splitType = "LATER"` in that original transaction request.
3. Customer initiates or completes the UPI payment, creating a merchant order in Newton.
4. Merchant calculates the final settlement allocation.
5. Merchant calls this API with the same `merchantRequestId` and final split details.
6. Newton stores the split on the merchant order and returns the stored split details.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/settlement/split
```

Payloads use the standard Newton server-to-server request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the API version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Current request timestamp used by common S2S signature validation. |
| `x-merchant-signature` | Required for unsigned/plain business payload mode. Signature is calculated using the merchant's configured signature strategy. |
| `x-forwarded-for` | Required when the merchant has `whitelistedIps` configured. Newton checks the first comma-separated IP. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. The route accepts the common `EncRequest` envelope variants:

- Encrypted request body with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- Signed request body with `payload`, `signature`, and `protected`.
- Plain business payload only where enabled for the merchant/environment.

For signed or encrypted requests, include `iat` in the decrypted business payload. Newton validates `iat` before merchant signature verification.

## Request

### Minimum Final Amount Split

```json
{
  "merchantRequestId": "ORDER12345",
  "splitSettlementDetails": {
    "splitType": "AMOUNT",
    "merchantSplit": "90.00",
    "partnersSplit": [
      {
        "partnerId": "SELLER001",
        "value": "10.00"
      }
    ]
  },
  "iat": "1717675200000"
}
```

### Minimum Final Percentage Split

```json
{
  "merchantRequestId": "ORDER12346",
  "splitSettlementDetails": {
    "splitType": "PERCENTAGE",
    "merchantSplit": "85.00",
    "partnersSplit": [
      {
        "partnerId": "SELLER001",
        "value": "15.00"
      }
    ]
  },
  "iat": "1717675200000"
}
```

### Use Merchant Default Split

```json
{
  "merchantRequestId": "ORDER12347",
  "splitSettlementDetails": {
    "splitType": "DEFAULT"
  },
  "iat": "1717675200000"
}
```

`DEFAULT` uses the merchant's configured `defaultSplitSettlementDetails`. The configured default must be a percentage split.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantRequestId` | string | Yes | No default. | Merchant-generated transaction/order reference from the original payment request. Must be non-empty. This API looks up the merchant order and refund state using this value and the authenticated merchant. |
| `splitSettlementDetails` | object | Yes | No default. | Final split details to store on the merchant order. The original merchant order must have been created with split type `LATER` and no stored split details yet. |
| `iat` | string | Conditional | No default. | Issued-at timestamp. Required for signed/encrypted S2S request modes because the route validates it before signature verification. |
| `udfParameters` | string | No | No default. If supplied, it is echoed in the success response. | Merchant-defined metadata as a JSON-object string. Must parse as a JSON object and must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### `splitSettlementDetails`

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `splitType` | string | Yes | No default. | Final split mode. Allowed by the type: `AMOUNT`, `PERCENTAGE`, `DEFAULT`, `LATER`. For this endpoint, `LATER` is rejected because this call is meant to resolve a previously deferred split. |
| `merchantSplit` | string | Conditional | Treated as `0.00` for total calculation when omitted, but omission is valid only when the split-type rule allows it. | Merchant's own settlement share. For `AMOUNT`, this is an amount such as `90.00`. For `PERCENTAGE`, this is a percentage such as `85.00`. Must match the decimal format `^[0-9]{1,9}\.[0-9][0-9]$`. |
| `partnersSplit` | array of objects | Conditional | Treated as an empty list for total calculation when omitted, but omission is valid only when the split-type rule allows it. | Partner/vendor settlement shares. Required when partners receive part of an `AMOUNT` or `PERCENTAGE` split. Must be omitted for `DEFAULT`. |

### `splitSettlementDetails.partnersSplit[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `partnerId` | string | Yes | Partner/vendor identifier configured for the merchant. Must be non-empty. When `vendorValidationEnabled` is enabled in platform configuration, every partner id must exist in the merchant's vendor list. |
| `value` | string | Yes | Partner share. For `AMOUNT`, this is an amount such as `10.00`. For `PERCENTAGE`, this is a percentage such as `15.00`. Must match the decimal format `^[0-9]{1,9}\.[0-9][0-9]$`. |

## Split Rules

### Prerequisites

- Split settlement must be enabled for the merchant through merchant configuration.
- The original merchant order must exist for the authenticated merchant and `merchantRequestId`.
- The original merchant order must have `splitSettlementType = LATER` and no stored split settlement details.
- No refund record may exist for the same merchant and `merchantRequestId`.

### Split Type Behavior

| `splitType` | Allowed in this API | `merchantSplit` / `partnersSplit` behavior | Stored behavior |
| --- | --- | --- | --- |
| `AMOUNT` | Yes | At least one split value must be supplied through `merchantSplit` or `partnersSplit`. The sum of merchant and partner values must equal the original merchant order amount, formatted to two decimals. | Stores the supplied amount split details. |
| `PERCENTAGE` | Yes | At least one split value must be supplied through `merchantSplit` or `partnersSplit`. The sum of merchant and partner values must equal `100.00`. | Stores the supplied percentage split details. |
| `DEFAULT` | Yes | Do not send `merchantSplit` or `partnersSplit`. | Resolves and stores the merchant's configured default split. The configured default must be a percentage split. |
| `LATER` | No | Rejected even if split fields are omitted. | Not stored by this endpoint. `LATER` belongs on the original transaction/register-intent request, not on the final settlement split call. |

Important validation details:

- Split values are strings, not JSON numbers.
- Valid value format is exactly two decimal places, for example `"0.00"`, `"10.00"`, or `"999999999.99"`.
- Field-level validation allows `"0.00"`, but `AMOUNT` and `PERCENTAGE` still require totals that match the transaction amount or `100.00`.
- For `AMOUNT`, Newton compares the two-decimal precise total to the original merchant order amount.
- For `PERCENTAGE`, Newton compares the numeric total to `100.00`.
- For `DEFAULT`, the merchant default must be configured and must itself validate as a percentage split.

## Success Response

### Amount Split Success

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12345",
    "splitSettlementDetails": {
      "splitType": "AMOUNT",
      "merchantSplit": "90.00",
      "partnersSplit": [
        {
          "partnerId": "SELLER001",
          "value": "10.00"
        }
      ]
    }
  }
}
```

### Default Split Success

If the request uses `splitType = "DEFAULT"`, Newton returns the resolved configured split details, not the literal `DEFAULT` marker.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantRequestId": "ORDER12347",
    "splitSettlementDetails": {
      "splitType": "PERCENTAGE",
      "merchantSplit": "80.00",
      "partnersSplit": [
        {
          "partnerId": "SELLER001",
          "value": "20.00"
        }
      ]
    }
  },
  "udfParameters": "{\"traceId\":\"TRACE123\"}"
}
```

`udfParameters` is omitted from the response when it is not supplied in the request.

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for a successful update. |
| `responseCode` | string | `SUCCESS` for a successful update. |
| `responseMessage` | string | `SUCCESS` for a successful update. |
| `payload` | object | Settlement split result payload. |
| `udfParameters` | string | Echo of request `udfParameters`, when supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from the authenticated merchant. |
| `merchantChannelId` | string | Merchant channel id from the authenticated merchant. |
| `merchantRequestId` | string | Original merchant request id/order reference. |
| `splitSettlementDetails` | object | Split details stored on the merchant order. For `DEFAULT` requests, this is the resolved default split. |

## Failure Handling

Failure responses use the same S2S response transport where possible. After decryption, most business failures follow this body shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Amount Sum Mismatch"
}
```

Some authentication, malformed envelope, and routing failures may be returned before a normal encrypted business response can be produced. Always use both HTTP status and decrypted `responseCode`/`responseMessage` when handling failures.

### Business and Validation Failures

| Scenario | HTTP status observed in code | Decrypted response body example | Client action |
| --- | --- | --- | --- |
| `merchantRequestId` is empty | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId field is empty\""}` | Send a non-empty original merchant request id. |
| `splitSettlementDetails` is missing or malformed | `400` or JSON parse failure | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"SplitSettlementDetails not Found"}` | Send a valid object with `splitType`. |
| `merchantSplit` or partner `value` does not match decimal format | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"partner split value regex match failed\""}` | Send string amounts with exactly two decimals. |
| `partnerId` is empty | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"partnerId field is empty\""}` | Send a configured non-empty partner id. |
| `udfParameters` is not a JSON-object string or contains blocked characters | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` | Send a JSON-object string such as `"{\"traceId\":\"TRACE123\"}"` using allowed characters. |
| Merchant is not enabled for split settlement and request contains split details | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"SplitSettlement not Allowed"}` | Confirm split settlement enablement during onboarding. |
| This endpoint is called with `splitType = "LATER"` | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Split Type for Settlement Split"}` | Use `AMOUNT`, `PERCENTAGE`, or `DEFAULT` to resolve a previously deferred split. |
| `AMOUNT` split total does not equal original transaction amount | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Amount Sum Mismatch"}` | Recalculate merchant and partner shares against the original order amount. |
| `PERCENTAGE` split total does not equal `100.00` | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Percentage Split"}` | Recalculate percentages so all shares total exactly `100.00`. |
| `DEFAULT` includes `merchantSplit` or `partnersSplit`, or an amount/percentage split has no split values | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Split Details"}` | For `DEFAULT`, send only `splitType`. For amount/percentage, include at least one split value and satisfy total rules. |
| Partner validation is enabled and a partner id is not in the merchant vendor list | `400` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid Partner"}` | Use a partner/vendor id configured for the merchant. |
| No merchant order or registered validation exists for `merchantRequestId` | `400` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Merchant Request Id"}` | Verify the original transaction was created for the same merchant. |
| Register intent exists, but no merchant order has been initiated yet | `400` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Transaction not initiated by user. Please try again after sometime"}` | Retry later after the customer initiates the transaction and the merchant order exists. |
| Refund exists for the same `merchantRequestId` | `400` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Settlement Split is not allowed as Refund is Initiated"}` | Do not attempt to modify split settlement after refund initiation. Reconcile using refund flows. |
| Original order was not created with unresolved `LATER` split, or split was already stored | `400` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Settlement Split is not allowed"}` | Do not retry as a normal duplicate. Check transaction status/reconciliation to confirm whether a prior split call already applied. |
| Merchant default split is missing or not a valid percentage default | `400` or `500` depending on failure point | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Contact Newton support to correct merchant configuration. |
| Stored split details cannot be parsed while building the response | `400` | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Treat as an uncertain server-side state and check transaction status/reconciliation before retrying. |

Validation error text is assembled from the validation error constructors, so exact messages can include prefixes such as `RegexValidation`, `LengthValidation`, or `UnexpectedType`.

### Authentication, Envelope, and Access Failures

| Scenario | HTTP status observed in code | Decrypted/plain response body example | Client action |
| --- | --- | --- | --- |
| Missing `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, `x-raw-body`, or required merchant signature | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Send all onboarding-required S2S headers and signature fields. |
| Invalid merchant signature | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Recreate the signature using the exact raw request body and configured signature strategy. |
| API is blocked for the merchant or not present in the merchant allowed API list | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Ask Newton to enable `settlementSplit` for the merchant/channel. |
| Merchant has `whitelistedIps` configured and `x-forwarded-for` is missing or first IP is not allowed | `401` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Send traffic from an onboarded IP and include `x-forwarded-for` as required by your integration path. |
| Signed/encrypted request omits `iat` | `200` in the helper path, with failure body | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` | Include a valid issued-at timestamp in the decrypted business payload. |
| `x-timestamp` or encrypted/signed `iat` is outside the allowed time window or malformed | `400` or common auth failure status | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid timestamp format"}` | Regenerate the request with the current timestamp. |
| Encrypted body cannot be decrypted or parsed | Common envelope failure | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $: key \"splitSettlementDetails\" not found"}` | Verify JWE/JWS fields, keys, and that the decrypted payload matches the request schema. |
| Merchant id/channel id is unknown | Common merchant lookup failure | `{"status":"FAILURE","responseCode":"INVALID_MERCHANT","responseMessage":"INVALID_MERCHANT"}` or `UNAUTHORIZED` depending on lookup path | Verify merchant headers and onboarding credentials. |

## Retry and Client Handling Guidance

- Treat `SUCCESS` as final. Store `payload.splitSettlementDetails` for reconciliation.
- This API is not idempotent after a successful update. A second call for the same original order usually fails with `Settlement Split is not allowed` because the split is already stored.
- If the HTTP request times out or the connection drops before a response is received, do not blindly retry in a tight loop. First check the transaction/status or reconciliation view for the order. If the split is already present, treat the previous call as applied.
- Retry later only for `Transaction not initiated by user. Please try again after sometime`, because that means the register/validation record exists but the merchant order has not been created yet.
- Do not retry validation errors such as `Amount Sum Mismatch`, `Invalid Percentage Split`, `Invalid Partner`, `Invalid Split Details`, or `Invalid Split Type for Settlement Split` without changing the request.
- Do not retry `API NOT ENABLED`, `UNAUTHORIZED`, IP allowlist failures, or merchant lookup failures until onboarding, credentials, headers, or allowlist configuration has been fixed.
- Do not retry after `Settlement Split is not allowed as Refund is Initiated`; use refund/reconciliation handling instead.
- Treat `INTERNAL_SERVER_ERROR` as an uncertain state if it happens after Newton may have written the split. Confirm order state before sending another split request.

## Source References

- Route type and endpoint: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:713)
- Route handler and middleware call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:5087)
- Request and response types: [src/Newton/Types/API/ServerToServer/SplitSettlement.hs](../../src/Newton/Types/API/ServerToServer/SplitSettlement.hs:19)
- Split API nested types: [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:1012), [src/Newton/Types/Intermediate.hs](../../src/Newton/Types/Intermediate.hs:1281)
- Split type enum: [src/Newton/Types/Storage/Common.hs](../../src/Newton/Types/Storage/Common.hs:35)
- Product/business logic: [src/Newton/Product/SplitSettlement.hs](../../src/Newton/Product/SplitSettlement.hs:22)
- Split validation/default transformation helpers: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4529), [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4578)
- Merchant signature, API allowlist/blocklist, and IP allowlist checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:15)
- Error response constructors: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
