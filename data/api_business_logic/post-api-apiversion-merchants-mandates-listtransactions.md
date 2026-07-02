# List Mandate Transactions API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/mandates/listTransactions`

## Overview

List Mandate Transactions is a merchant server-to-server API for retrieving the execution transaction history for a specific UPI mandate.

The merchant sends the customer identifier, UMN, and a date range. Newton validates the request, authenticates the merchant, verifies that the merchant customer belongs to the authenticated merchant, finds the mandate for that merchant customer and UMN, then returns mandate execution transactions in reverse creation-time order.

Use this API for reconciliation, customer support, execution-status display, and back-office reporting after a mandate has been created.

## Business Use Case

This API helps merchants:

- Reconcile debit executions for one mandate identified by UMN.
- Display mandate debit history for one merchant customer.
- Page through execution attempts for support or settlement investigation.
- Confirm gateway response details, payer/payee details, amount, reference ids, and execution timestamps returned from Newton's transaction store.

This API does not create, update, pause, approve, or execute a mandate. It only reads transaction history for an existing mandate.

## Integration Flow

1. Merchant creates or receives a mandate and stores the UMN with its customer record.
2. Merchant backend calls `listTransactions` with `merchantCustomerId`, `umn`, `startDate`, and `endDate`.
3. Newton decrypts/verifies the S2S request envelope and validates the request body.
4. Newton verifies merchant authentication, API enablement, optional IP allowlisting, and request timestamp/signature requirements.
5. Newton looks up the merchant customer, customer, and mandate for the supplied UMN.
6. Newton queries mandate execution transactions for the date window, applying `limit` and `offset`.
7. Merchant decrypts the response and stores or displays `payload.txnList`.

Important identifiers:

- `merchantCustomerId`: Merchant's customer id for the payer/customer.
- `umn`: Unique Mandate Number used to locate the mandate.
- `gatewayTransactionId`: Newton/UPI transaction id for a mandate execution transaction.
- `gatewayReferenceId`: UPI response/reference id from the transaction record.
- `merchantRequestId`: Merchant request id stored inside the transaction metadata, when present.

## Endpoint

```http
POST /api/{apiVersion}/merchants/mandates/listTransactions
```

Payloads use Newton's standard server-to-server encrypted/signed request and response envelope. The examples in this guide show the decrypted business payload for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version segment in the route, for example `v1` or the version shared during onboarding. |

### Headers and Authentication

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-merchant-id` | Yes for unsigned payload signature verification | Merchant id issued by Newton. Included in the signature base string for unsigned S2S requests. |
| `x-merchant-channel-id` | Yes for unsigned payload signature verification | Merchant channel id issued by Newton. Included in the signature base string for unsigned S2S requests. |
| `x-sub-merchant-id` | Conditional | Required only for sub-merchant flows enabled during onboarding. Included in the signature base string when present. |
| `x-sub-merchant-channel-id` | Conditional | Required only for sub-merchant flows enabled during onboarding. Included in the signature base string when present. |
| `x-timestamp` | Yes | Request timestamp used by middleware. Must be valid and within Newton's accepted skew window. |
| `x-merchant-signature` | Conditional | Required for unsigned/plain S2S requests except development-only checksum bypass modes. Signature is verified over merchant ids, timestamp, and raw request body. |
| `x-forwarded-for` | Conditional | Required when the merchant configuration contains `whitelistedIps`. The first IP in this header must be allowlisted. |
| `x-api-version` | Conditional | Send only if your onboarding pack requires this header in addition to the path version. |

Authentication and envelope handling:

- The route accepts `API.EncRequest ListMandateTxnHistoryRequest`, so the transport body can be encrypted, signed, or explicitly enabled plaintext according to onboarding configuration.
- Newton decrypts/verifies the envelope before product logic receives the business payload.
- For encrypted or signed payloads, the body field `iat` is mandatory and must be a valid timestamp.
- For unsigned/plain payloads, `x-merchant-signature`, `x-timestamp`, and the raw body are used for signature verification.
- Merchant configuration can block this API or restrict it to an allowed API list. In those cases Newton returns an authorization failure.
- If `whitelistedIps` is configured for the merchant, `x-forwarded-for` is enforced.

## Request

Business payload type: `ListMandateTxnHistoryRequest`.

### Minimum Request

```json
{
  "merchantCustomerId": "CUST12345",
  "umn": "12345678901234567890123456789012@upi",
  "startDate": "2026/1/1",
  "endDate": "2026/1/31"
}
```

### Request With Pagination

```json
{
  "merchantCustomerId": "CUST12345",
  "umn": "12345678901234567890123456789012@upi",
  "startDate": "2026/1/1",
  "endDate": "2026/1/31",
  "limit": "50",
  "offset": "0"
}
```

### Request With UDF Echo

```json
{
  "merchantCustomerId": "CUST12345",
  "umn": "12345678901234567890123456789012@upi",
  "startDate": "2026/1/1",
  "endDate": "2026/1/31",
  "limit": "20",
  "offset": "20",
  "udfParameters": "{\"reconBatchId\":\"BATCH-2026-01\"}"
}
```

### Encrypted or Signed Payload Business Body

When using an encrypted or signed envelope, include `iat` inside the decrypted business payload:

```json
{
  "merchantCustomerId": "CUST12345",
  "umn": "12345678901234567890123456789012@upi",
  "startDate": "2026/1/1",
  "endDate": "2026/1/31",
  "limit": "20",
  "offset": "0",
  "iat": "1798713000000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Validation and description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Must be 1 to 256 characters and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. Newton looks this up under the authenticated merchant. |
| `umn` | string | Yes | No default. | Unique Mandate Number. Must be 34 to 70 characters and match `.{32}@.+`. Newton looks up a mandate with this UMN for the resolved merchant customer. |
| `startDate` | string | Yes | No default. | Start date of the query window. Validation accepts date text that Newton can parse after replacing `/` with `-`. Product query parsing uses the slash-style pattern, so send `YYYY/M/D`, for example `2026/1/1`. |
| `endDate` | string | Yes | No default. | End date of the query window. The product layer uses end-of-day for this date. Send `YYYY/M/D`, for example `2026/1/31`. |
| `limit` | string | No | Defaults to `"20"` if omitted. | Page size. Must parse as a non-negative integer. A value of `"0"` is accepted and returns no transaction rows. No endpoint-specific maximum is enforced in this code path. |
| `offset` | string | No | Defaults to `"0"` if omitted. | Zero-based row offset. Must parse as a non-negative integer. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON object encoded as a string. Must parse as a JSON object and must not contain characters rejected by `udfParametersTextValidation`. Echoed in the response. |
| `iat` | string | Conditional | No default. | Required for encrypted or signed envelopes. Ignored by business validation, but timestamp validation happens during signature/envelope middleware. |

### Date Window and Pagination Rules

- The date window must span at most 6 transaction table partitions by month. A wider range fails with `Difference between start and End month should be less than or equal to 6 months`.
- `limit` and `offset` are strings in this API, not JSON numbers.
- Results are queried in descending `createdAt` order.
- Pagination is offset-based. To read the next page, repeat the same filter values and increase `offset` by the previous page size.
- The query is scoped to the resolved customer, merchant customer, and mandate id. The API does not support listing by status, amount, callback status, app id, or account type.

## Response

Business response type: `ListMandateTxnHistoryResponse`.

### Success Response With Transactions

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "txnList": [
      {
        "amount": "499.00",
        "bankAccountUniqueId": "BAU123456",
        "bankCode": "HDFC",
        "expiry": "2026-01-31T23:59:59+05:30",
        "gatewayReferenceId": "UPIREF1234567890",
        "gatewayResponseCode": "00",
        "gatewayResponseMessage": "SUCCESS",
        "gatewayTransactionId": "TXN1234567890",
        "maskedAccountNumber": "XXXX1234",
        "merchantRequestId": "EXEC-REQ-001",
        "payeeMobileNumber": "9876543210",
        "payeeName": "Merchant Name",
        "payeeVpa": "merchant@bank",
        "payerMobileNumber": "9123456789",
        "payerName": "Customer Name",
        "payerVpa": "customer@bank",
        "remarks": "Mandate execution",
        "transactionTimestamp": "2026-01-15T10:30:45+05:30",
        "umn": "customer@bank",
        "seqNumber": "3"
      }
    ]
  },
  "udfParameters": "{\"reconBatchId\":\"BATCH-2026-01\"}"
}
```

### Success Response With No Transactions

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "txnList": []
  }
}
```

### Response Envelope Notes

- The HTTP response body is returned as `API.EncResponse ListMandateTxnHistoryResponse`.
- Depending on onboarding, the transport response can be encrypted, signed, or returned as an error envelope. The JSON examples above show the decrypted business response.
- `payload` is present on success in this route.
- `udfParameters` is included only when it was present in the request.

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful reads. |
| `responseCode` | string | `SUCCESS` on success. |
| `responseMessage` | string | `SUCCESS` on success. |
| `payload` | object | Mandate transaction list payload. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters`, when supplied. |

### `payload` Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Authenticated merchant id. |
| `merchantChannelId` | string | Authenticated merchant channel id. |
| `merchantCustomerId` | string | Echo of the request merchant customer id after merchant-scoped lookup succeeds. |
| `txnList` | array of objects | List of mandate execution transaction records. Empty when no executions match the query. |

### `txnList[]` Fields

| Field | Type | Presence | Description |
| --- | --- | --- | --- |
| `amount` | string | Always | Transaction amount formatted with two decimal places. |
| `bankAccountUniqueId` | string | Optional | Bank account unique id parsed from payer account details, when present. |
| `bankCode` | string | Optional | Payer bank code parsed from payer account details, when present. |
| `expiry` | string | Optional | Transaction expiry timestamp, when present. |
| `gatewayReferenceId` | string | Always | Transaction `upiResponseId`. If the stored transaction is missing this field, response mapping fails as an unexpected server error. |
| `gatewayResponseCode` | string | Always | Gateway/NPCI response code derived from transaction gateway response and status. |
| `gatewayResponseMessage` | string | Always | Gateway/NPCI response message. Defaults to `Transaction pending` if no gateway response message is available. |
| `gatewayTransactionId` | string | Always | Transaction `upiRequestId`. |
| `maskedAccountNumber` | string | Optional | Masked payer account number parsed from payer account details, when present. |
| `merchantRequestId` | string | Optional | Merchant request id read from transaction metadata, when present. |
| `payeeMobileNumber` | string | Optional | Payee mobile number from stored payee info, when present. |
| `payeeName` | string | Optional | Payee name from stored payee info, when present. |
| `payeeVpa` | string | Always | Payee VPA. If absent in stored data, response mapping fails as an unexpected server error. |
| `payerMobileNumber` | string | Optional | Payer mobile number from payer info, when present. |
| `payerName` | string | Optional | Payer name from payer info, when present. |
| `payerVpa` | string | Always | Payer VPA. If absent in stored data, response mapping fails as an unexpected server error. |
| `remarks` | string | Optional by schema, usually present | Transaction remarks. Current mapper wraps stored remarks as present. |
| `transactionTimestamp` | string | Always | Transaction creation timestamp. |
| `umn` | string | Optional | Current mapper populates this from the transaction payer VPA field, not directly from the request UMN. Use the request UMN or mandate record as the canonical mandate identifier. |
| `seqNumber` | string | Optional | Mandate execution sequence number, when present. |

## Error Handling

Failure responses use the same response transport configured for the merchant. After decryption, errors generally follow this underlying JSON shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"umn length is not between 34 and 70\""
}
```

Some failures are thrown before the business response is built, so HTTP status can be `200`, `400`, `401`, or `500` depending on the layer. Client code should always inspect the decrypted `status`, `responseCode`, and `responseMessage`.

### Validation Failures

Missing or malformed required fields are rejected by request validation.

Example invalid UMN:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"umn length is not between 34 and 70\""
}
```

Example invalid date:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"date value not valid\""
}
```

Example invalid pagination value:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Expected Positive Integer, found -1\""
}
```

Client handling: fix the request and do not retry unchanged.

### Date Window Too Large

The product layer rejects date windows spanning more than 6 monthly partitions.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Difference between start and End month should be less than or equal to 6 months"
}
```

Client handling: split the query into smaller date windows.

### Authentication, Signature, Timestamp, Encryption, and IP Failures

Examples include missing raw body/timestamp in middleware, invalid `iat` for encrypted/signed payloads, invalid `x-timestamp`, missing or mismatched `x-merchant-signature`, invalid envelope parsing, and IP allowlist failure.

Typical unauthorized response:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the API is blocked or not allowed for the merchant, the middleware uses:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Envelope parsing/decryption failures can surface as `INVALID_DATA` or HTTP `400` with the parse error in `responseMessage`.

Client handling: do not retry blindly. Recreate the signature over the exact raw request body, verify timestamp freshness, verify `iat` for encrypted/signed payloads, confirm merchant credentials and API enablement, and confirm source IP allowlisting.

### Merchant Customer or Customer Lookup Failures

Newton looks up `merchantCustomerId` under the authenticated merchant, then resolves the customer linked to that merchant customer. If records are missing or inactive, the response usually has `INVALID_DATA`.

Example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "MerchantCustomer not found"
}
```

Another possible lookup failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
}
```

Client handling: verify that the merchant customer was onboarded under the same merchant credentials used for this request.

### Mandate Lookup Failures

Newton must find a mandate for the request `umn` and resolved merchant customer. Missing UMN or a UMN belonging to another customer fails lookup.

Example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Request not found"
}
```

Client handling: verify the UMN, merchant customer id, and merchant credentials. Do not retry unchanged unless the mandate was just created and indexing delay is expected.

### No Matching Transactions

No matching transactions is not an error. Newton returns `SUCCESS` with an empty `txnList`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "txnList": []
  }
}
```

Client handling: treat as a valid empty page.

### Response Mapping or Stored Data Inconsistency

The response mapper expects `upiResponseId`, `payerVpa`, and `payeeVpa` on each returned transaction. If stored transaction data is inconsistent, Newton can fail while building the success response.

Example shape:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "Unexpected error"
}
```

Client handling: retry once after a short delay. If it repeats for the same date range, raise the `merchantCustomerId`, `umn`, date window, and Newton request id to Newton support.

### Downstream or Gateway Failures

This endpoint reads Newton's stored mandate transactions and does not call NPCI/gateway execution APIs in the normal path. Gateway failures from the original mandate execution are returned as transaction-level `gatewayResponseCode` and `gatewayResponseMessage`, not as API call failures.

Client handling: do not retry the list API because a transaction row has a failed gateway code. Use transaction-level status/reason for reconciliation.

## Retry and Idempotency Guidance

- This is a read-only API. Retrying the same request does not create or modify mandates or transactions.
- Use the same `merchantCustomerId`, `umn`, `startDate`, `endDate`, `limit`, and `offset` when retrying a failed page.
- Retry transient HTTP `5xx`, network timeouts, and response mapping errors with exponential backoff and jitter.
- Do not retry validation, authentication, API-disabled, IP allowlist, or lookup failures unchanged.
- For complete reconciliation, page until `txnList.length` is less than `limit`.
- Because offset pagination reads newest-first data, new executions arriving during pagination can shift later pages. For stable reconciliation, use bounded historical date windows and rerun the most recent window after settlement cut-off.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:655)
- Route handler, envelope extraction, signature middleware, and product call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4778)
- Server wiring: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:318)
- API service constant: [src/Newton/Types/Domain/Constants.hs](../../src/Newton/Types/Domain/Constants.hs:1023)
- Request, validation, response, and transaction-history types: [src/Newton/Types/API/ServerToServer/Mandate.hs](../../src/Newton/Types/API/ServerToServer/Mandate.hs:507)
- Product route validation and merchant/customer lookup: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:818)
- Business query defaults, mandate lookup, date-window rule, and transaction query call: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2273)
- Response mapping: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:740)
- Request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:246), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:629)
- Validation error wrapping: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Envelope request/response variants: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification entry point: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Signature, API enablement, timestamp, and IP allowlist middleware: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Merchant customer and customer lookup helpers: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:106), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:503)
- Mandate lookup: [src/Newton/Storage/QueriesMiddleware/Mandate.hs](../../src/Newton/Storage/QueriesMiddleware/Mandate.hs:527)
- Mandate transaction query: [src/Newton/Storage/QueriesMiddleware/Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:1940)
- Shared success/error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
