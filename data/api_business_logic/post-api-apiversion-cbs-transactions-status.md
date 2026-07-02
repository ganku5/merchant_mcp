# CBS Transaction Status API Integration Guide

Source endpoint: `POST /api/{apiVersion}/cbs/transactions/status`

## Overview

CBS Transaction Status is a server-to-server API used by an onboarded CBS or bank-side integration to fetch the latest Newton status for a CBS-backed UPI transaction.

The caller sends the Newton `upiRequestId` and the CBS transaction `type`. Newton returns one combined view containing:

- Gateway-side status for the linked self-initiated refund/payout transaction.
- CBS-side status for the debit or credit leg recorded by Newton.
- Amount, timestamp, type, and request id for reconciliation.

Use this API when the CBS partner needs to reconcile whether Newton's UPI gateway flow and CBS ledger flow are both complete, still pending, failed, or reversed.

## Business Use Case

CBS Transaction Status helps partners:

- Poll a CBS-backed payout, refund, debit, or credit leg after Newton has initiated processing.
- Reconcile gateway status and CBS status using the same `upiRequestId`.
- Decide whether an operational retry, reversal follow-up, or support investigation is needed.
- Confirm whether a pending CBS leg has moved to `SUCCESS`, `FAILURE`, or `REVERSED`.
- Build dashboards or reports where gateway and CBS statuses must be shown side by side.

The API is lookup-only. It does not trigger a new debit, credit, refund, reversal, or status sync with an external system.

## Integration Flow

1. Newton creates or updates a CBS transaction during the configured CBS-backed UPI flow.
2. The partner stores the Newton `upiRequestId` and the CBS transaction `type`.
3. The partner calls `cbs/transactions/status` with those values.
4. Newton validates the request payload.
5. Newton looks up the CBS transaction using both `upiRequestId` and `type`.
6. Newton looks up the linked self-initiated refund/payout transaction using the same `upiRequestId`.
7. Newton returns the current gateway and CBS statuses in the response payload.

Important identifiers:

- `upiRequestId`: Newton UPI request id for the CBS-backed transaction being checked.
- `type`: CBS leg to check. Send `DEBIT` or `CREDIT`; it must match the stored CBS transaction.

If `upiRequestId` exists for another `type`, Newton treats the requested record as not found.

## Endpoint

```http
POST /api/{apiVersion}/cbs/transactions/status
```

Payloads use the Newton server-to-server request and response envelope configured during onboarding. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-request-id` | Optional request id for tracing. If omitted, Newton generates one. |
| `x-session-id` | Optional session id for tracing. If omitted, Newton uses the request id. |

Authentication and envelope verification use the CBS key configuration shared during onboarding.

## Request

### Required Minimum

```json
{
  "type": "DEBIT",
  "upiRequestId": "CBSTXN123456789"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `type` | string | Yes | No default. | CBS transaction leg to check. Allowed values: `DEBIT`, `CREDIT`. The value is part of the lookup key. |
| `upiRequestId` | string | Yes | No default. | Newton UPI request id for the CBS-backed transaction. Must be 1 to 35 characters and contain only letters and numbers. |
| `iat` | string | No | No default. Omit when not used by your signing/envelope setup. | Issued-at timestamp included by integrations that send it as part of the request payload. It is not used to select the transaction record. |

### Validation Notes

- `upiRequestId` must be alphanumeric and 1 to 35 characters.
- `type` must be one of `DEBIT` or `CREDIT`.
- `type` and `upiRequestId` must identify an existing CBS transaction.
- A linked self-initiated refund/payout transaction must also exist for the same `upiRequestId`; otherwise Newton returns `REQUEST_NOT_FOUND`.

### Request Examples

#### Debit Leg Status

```json
{
  "type": "DEBIT",
  "upiRequestId": "CBSPAYOUT123456"
}
```

#### Credit Leg Status

```json
{
  "type": "CREDIT",
  "upiRequestId": "CBSCREDIT123456"
}
```

### Defaults and Omitted Field Behavior

No business field is defaulted by this API. Newton does not generate `upiRequestId` or infer `type` for a status request.

Optional fields are omitted from the response when Newton has no stored value for them.

## Response

### Response Envelope

On a successful lookup, the response envelope is:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. Successful lookup returns `SUCCESS`. |
| `responseCode` | string | Successful lookup returns `SUCCESS`. |
| `responseMessage` | string | Successful lookup returns `SUCCESS`. |
| `payload` | object | CBS transaction status payload. |

The top-level `SUCCESS` means Newton found the required records and returned their current statuses. It does not mean the underlying gateway or CBS transaction succeeded. Always use `payload.gatewayResponseStatus` and `payload.cbsResponseStatus` for the business outcome.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `amount` | string | CBS transaction amount, formatted with two decimal places, for example `100.00`. |
| `gatewayResponseStatus` | string | Status of the linked self-initiated refund/payout transaction. Possible values include `SUCCESS`, `FAILURE`, `PENDING`, `EXPIRED`, `DECLINED`, `DEEMED`, `COLLECT_PAY_INITIATED`, `DECLINE_INITIATED`, and `TIMED_OUT`. |
| `gatewayResponseCode` | string | Gateway response code derived from the linked refund/payout transaction status and stored NPCI response. |
| `cbsResponseStatus` | string | CBS transaction status. Returned values are `PENDING`, `SUCCESS`, `FAILURE`, or `REVERSED`. |
| `cbsResponseCode` | string | CBS response code. Omitted when the CBS status is `FAILURE` and no CBS failure code is available in the stored transaction data. |
| `transactionTimestamp` | string | CBS transaction creation timestamp in IST, formatted like `YYYY-MM-DDTHH:MM:SS+05:30`. |
| `type` | string | Echoes the requested CBS transaction type: `DEBIT` or `CREDIT`. |
| `upiRequestId` | string | Echoes the requested Newton UPI request id. |

### Status and Code Mapping

Gateway status comes from the linked self-initiated refund/payout transaction.

| `gatewayResponseStatus` | `gatewayResponseCode` behavior |
| --- | --- |
| `PENDING`, `TIMED_OUT`, `DECLINE_INITIATED`, `COLLECT_PAY_INITIATED` | `01` |
| `DEEMED` | `RB` |
| `DECLINED` | `ZA` |
| `SUCCESS`, `FAILURE`, `EXPIRED` | Stored NPCI `code` when available; otherwise `JP91`. |

CBS status comes from the stored CBS transaction.

| `cbsResponseStatus` | `cbsResponseCode` behavior |
| --- | --- |
| `PENDING` | `JPCP` |
| `SUCCESS` | `00` |
| `REVERSED` | `JPCR` |
| `FAILURE` | Stored CBS failure code when available. If no code is stored, `cbsResponseCode` is omitted. |

### Response Examples

#### Pending Gateway and Pending CBS Leg

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "gatewayResponseStatus": "PENDING",
    "gatewayResponseCode": "01",
    "cbsResponseStatus": "PENDING",
    "cbsResponseCode": "JPCP",
    "transactionTimestamp": "2026-07-02T14:30:45+05:30",
    "type": "DEBIT",
    "upiRequestId": "CBSPAYOUT123456"
  }
}
```

#### Successful Gateway With Failed CBS Leg

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "cbsResponseStatus": "FAILURE",
    "cbsResponseCode": "91",
    "transactionTimestamp": "2026-07-02T14:30:45+05:30",
    "type": "DEBIT",
    "upiRequestId": "CBSPAYOUT123456"
  }
}
```

#### Reversed CBS Leg

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "amount": "100.00",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "cbsResponseStatus": "REVERSED",
    "cbsResponseCode": "JPCR",
    "transactionTimestamp": "2026-07-02T14:30:45+05:30",
    "type": "DEBIT",
    "upiRequestId": "CBSPAYOUT123456"
  }
}
```

## Error Handling

Failure bodies follow the standard Newton error response shape. Depending on where the request fails, the body may be returned as the direct error response or through the configured response envelope. Clients should inspect `status`, `responseCode`, and `responseMessage` in the body whenever it is present.

HTTP status can vary by validation layer. Some business validation and lookup failures are returned with HTTP 200 and a failure body, so clients should always read `status`, `responseCode`, and `responseMessage`.

### Validation Failure

Returned when `upiRequestId` fails length or format validation.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"upiRequestId length is not between 1 and 35\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\""
}
```

### Malformed or Unparseable Payload

Returned when the decrypted or signed payload cannot be parsed, for example because `type` is not a valid enum value or the JSON shape is invalid.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"type\" not found"
}
```

For a raw malformed JSON request, the HTTP framework may reject the request before Newton can build this error body.

### Missing or Invalid Key Id

Returned when the signed/encrypted request does not contain a usable `kid`, or when the configured CBS key cannot be found.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding KID"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Key not found"
}
```

### Authentication or Decryption Failure

Returned when signature verification fails, the encrypted payload cannot be decrypted, or Newton cannot validate the request source.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### CBS Transaction Not Found

Returned when no CBS transaction exists for the requested `upiRequestId` and `type`.

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

### Linked Gateway Transaction Not Found

Returned when the CBS transaction is found but Newton cannot find the linked self-initiated refund/payout transaction for the same `upiRequestId`.

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_NOT_FOUND",
  "responseMessage": "REQUEST_NOT_FOUND"
}
```

### Internal Error

Returned for database errors, response signing/encryption failures, or an unexpected stored CBS status that cannot be mapped into the response payload.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Source References

- Route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:702)
- Handler: [Core.hs](../../src/Newton/App/Routes/Core.hs:4191)
- Product flow: [CbsTransactionV2.hs](../../src/Newton/Product/CbsTransactionV2.hs:17)
- Response transformer: [Transformer3.hs](../../src/Newton/Utils/Transformers/Transformer3.hs:64)
- Request and response types: [Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:1491)
- CBS transaction status/type enums: [CbsTransaction.hs](../../src/Newton/Types/Storage/CbsTransaction.hs:83)
- Refund/payout status enum: [RefundTransaction.hs](../../src/Newton/Types/Storage/RefundTransaction.hs:245)
- Linked refund/payout lookup: [RefundTransaction.hs](../../src/Newton/Storage/QueriesMiddleware/RefundTransaction.hs:79)
- Gateway and CBS code mapping: [Utils.hs](../../src/Newton/Utils/Utils.hs:1198)
- Request validation: [Common.hs](../../src/Newton/Validation/Common.hs:575)
- Error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
