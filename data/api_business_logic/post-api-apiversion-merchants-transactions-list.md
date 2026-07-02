# List Transactions API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/list`

## Overview

List Transactions is a server-to-server API used by a merchant backend to retrieve UPI transaction records that Newton has stored for the merchant.

The API supports two listing modes:

- Customer-scoped listing: send `merchantCustomerId` to list transactions for one customer profile. This mode uses `startDate` and `endDate` date filters.
- Merchant pull listing: omit `merchantCustomerId` and send `startTimestamp` and `endTimestamp` to list transactions for the merchant, and optionally its sub-merchants, over a narrow timestamp window. This mode must be enabled for the merchant.

Use this API for reconciliation, back-office status checks, transaction history screens, support workflows, and merchant-side recovery when callbacks were delayed or missed.

Payloads use the standard Newton server-to-server request and response envelope. Examples below show decrypted business payloads for readability.

## Business Use Case

List Transactions helps merchants:

- Reconcile Newton transaction records against merchant orders and settlements.
- Fetch a customer's recent UPI transaction history.
- Pull merchant-level transactions for a time window when the pull listing feature is enabled.
- Filter by transaction status, callback delivery status, account type, and sub-merchant scope where supported.
- Page through large result sets with `limit` and `offset`.
- Inspect Newton response codes, UPI identifiers, payer/payee details, mandate references, and optional split or sub-merchant metadata.

## Integration Flow

1. Merchant backend chooses the listing mode.
2. Merchant prepares the decrypted business payload.
3. Merchant signs and/or encrypts the payload using the S2S process shared during onboarding.
4. Merchant calls `POST /api/{apiVersion}/merchants/transactions/list` with merchant headers.
5. Newton verifies merchant identity, API access, signature, timestamp, IP restrictions, and request payload.
6. Newton fetches matching transactions, decrypts stored transaction/customer data, maps it to the API response, and returns an encrypted response envelope.
7. Merchant decrypts the response and uses `payload.txnList` for reconciliation or display.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/list
```

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-api-version` | Recommended | API response/version behavior. For S2S list transactions, `x-api-version > 5` suppresses several SDK/customer-only response fields. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required only for sub-merchant calls where onboarding requires sub-merchant routing. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id` when sub-merchant routing is used. |
| `x-merchant-signature` | Yes for unsigned JSON payload mode | Signature over merchant ids, timestamp, and raw request body. Exact signing rules are part of S2S onboarding. |
| `x-timestamp` | Yes | Request timestamp used for request freshness validation. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP in the header must be whitelisted. |
| `Authorization` | Conditional | Used only when enabled for the merchant's S2S integration. |
| `x-request-id` | No | Optional id for tracing. Newton generates one when absent. |
| `x-session-id` | No | Optional session/correlation id. Defaults to `x-request-id` when absent. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Version segment in the URL. The implementation also reads `x-api-version` for version-gated behavior. Use the version shared during onboarding. |

## Authentication, Signing, and Encryption

This route accepts the standard Newton S2S request envelope:

- Encrypted payload: JWE-style fields `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- Signed payload: JWS-style fields `payload`, `signature`, and `protected`.
- Plain JSON payload may be accepted only in environments/configurations where Newton explicitly allows it.

For signed or encrypted payloads, include `iat` inside the decrypted business payload. Newton validates `iat` before running merchant signature verification.

Merchant verification checks:

- `x-merchant-id` and `x-merchant-channel-id` resolve to a merchant.
- If sub-merchant headers are present, the request is evaluated in that sub-merchant context.
- The API is not present in the merchant's blocked API list.
- If the merchant or sub-merchant is disabled, `listTransactionsS2S` must be present in the configured allowed API names.
- The request signature is valid, unless the environment is explicitly configured to bypass it.
- `x-forwarded-for` is present and whitelisted when the merchant has IP restrictions configured.
- `x-timestamp` is valid and fresh, except for specific non-production checksum bypass paths.

## Request Body

### Customer-Scoped Listing

Use this mode when you know the Newton merchant customer id.

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 25,
  "offset": 0,
  "startDate": "2026/6/1",
  "endDate": "2026/6/30",
  "status": ["SUCCESS", "PENDING"],
  "accountTypes": ["SAVINGS"],
  "udfParameters": "{\"reconciliationRunId\":\"RUN-1001\"}",
  "iat": "1782960000000"
}
```

Minimum customer-scoped request:

```json
{
  "merchantCustomerId": "CUST12345",
  "limit": 25,
  "offset": 0,
  "iat": "1782960000000"
}
```

### Merchant Pull Listing

Use this mode only when `isPullTransactionsEnabled` is enabled for the merchant.

```json
{
  "startTimestamp": "2026-06-30T00:00:00+05:30",
  "endTimestamp": "2026-06-30T23:59:59+05:30",
  "limit": 100,
  "offset": 0,
  "status": ["SUCCESS"],
  "callbackStatus": "PENDING",
  "requestType": "BOTH",
  "udfParameters": "{\"reconciliationRunId\":\"RUN-1002\"}",
  "iat": "1782960000000"
}
```

Minimum pull-listing request:

```json
{
  "startTimestamp": "2026-06-30T00:00:00+05:30",
  "endTimestamp": "2026-06-30T23:59:59+05:30",
  "iat": "1782960000000"
}
```

If the merchant configuration `enableListTransactionsLimitOffset` is enabled, `limit` and `offset` are mandatory in pull-listing mode.

## Request Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Conditional | If omitted, Newton enters merchant pull-listing mode and requires `startTimestamp` and `endTimestamp`. | Merchant customer identifier. Required for customer-scoped listing. Length must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `limit` | integer | Conditional | No universal default. Required when `merchantCustomerId` is sent. Required in pull mode only when `enableListTransactionsLimitOffset` is enabled. | Maximum number of transactions to return. Must be greater than `0`. In pull mode, if the merchant has `listTransactionsMaxLimit` configured, the limit must not exceed that value; default max is `100` when the config key is absent. |
| `offset` | integer | Conditional | No universal default. Required when `merchantCustomerId` is sent. Required in pull mode only when `enableListTransactionsLimitOffset` is enabled. | Zero-based offset for pagination. Must be greater than or equal to `0`. |
| `startDate` | string | No | Customer-scoped mode defaults to current local date minus 6 months. Ignored by merchant pull mode. | Start date for customer-scoped listing. Send slash-separated dates such as `2026/6/1` or `2026/06/01`. |
| `endDate` | string | No | Customer-scoped mode defaults to current local date. Ignored by merchant pull mode. | End date for customer-scoped listing. Newton applies end-of-day to this date. Send slash-separated dates such as `2026/6/30` or `2026/06/30`. |
| `startTimestamp` | string | Conditional | No default. Required when `merchantCustomerId` is omitted. Ignored by customer-scoped mode. | Start timestamp for merchant pull-listing mode. Must parse as IST timestamp in the format `YYYY-MM-DDTHH:MM:SS+05:30`. |
| `endTimestamp` | string | Conditional | No default. Required when `merchantCustomerId` is omitted. Ignored by customer-scoped mode. | End timestamp for merchant pull-listing mode. Must parse as IST timestamp in the format `YYYY-MM-DDTHH:MM:SS+05:30`. |
| `appIds` | array of objects | No | If omitted in customer-scoped mode, Newton lists the matching customer for the current merchant context. | Customer-scoped filter for merchant/app identities associated with the same customer. Each item contains `merchantId` and `merchantChannelId`. |
| `status` | array of strings | No | If omitted, no transaction status filter is applied. | Transaction statuses to include. For this S2S API, allowed request values are `SUCCESS`, `PENDING`, and `FAILURE`. The list must not be empty. |
| `callbackStatus` | string | No | If omitted or `ALL`, no callback-status filter is applied. Used only in merchant pull-listing mode. | Filters by merchant callback delivery state. Allowed values are `SUCCESS`, `PENDING`, and `ALL`. `PENDING` matches pending and uninitiated callbacks. |
| `requestType` | string | No | Defaults by behavior to `PARENTMERCHANT`, unless request-type filtering is disabled, in which case Newton also treats the request as `PARENTMERCHANT`. Used only in merchant pull-listing mode. | Merchant scope for pull listing. Allowed values are `PARENTMERCHANT`, `SUBMERCHANT`, and `BOTH`. This field is rejected for sub-merchant list-transaction calls. |
| `accountTypes` | array of strings | No | If omitted, no account-type filter is applied. | Customer-scoped account-type filter. The list must not be empty. Values are account types such as `SAVINGS`, `CURRENT`, `DEFAULT`, `NRE`, `NRO`, `CREDIT`, `PPIWALLET`, `BANKWALLET`, `SOD`, `UOD`, `UPICREDIT`, `CREDITLINE`, `CREDITLINE01` through `CREDITLINE10`, `CL01`, `CL011`, `CL012`, `CL013`, `CL014`, `CL015`, and `CL02` through `CL10`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by signature/encryption verification for signed or encrypted S2S payloads. |
| `udfParameters` | string | No | Omitted from the response when not supplied. | Merchant-defined metadata. Must be a string containing a JSON object and must pass Newton's restricted-character validation. Echoed back in the response. |

### `appIds[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Yes | Merchant id. |
| `merchantChannelId` | string | Yes | Merchant channel id. |

## Filter, Pagination, and Date Behavior

### Customer-Scoped Mode

Customer-scoped mode is selected when `merchantCustomerId` is present.

Rules:

- `limit` and `offset` are mandatory.
- `limit` must be greater than `0`.
- `offset` must be greater than or equal to `0`.
- `startDate` and `endDate` are optional.
- If `startDate` is omitted, Newton uses the current local date minus 6 months.
- If `endDate` is omitted, Newton uses the current local date.
- Results are sorted newest first by transaction creation time.
- `accountTypes` filters transactions by the payer/payee account type resolved from NPCI response or stored transaction data.
- Transactions in uninitiated states are removed from the final result.

### Merchant Pull-Listing Mode

Pull-listing mode is selected when `merchantCustomerId` is omitted.

Rules:

- The merchant must have `isPullTransactionsEnabled` enabled. Otherwise Newton rejects the request with `merchantCustomerId is mandatory`.
- `startTimestamp` and `endTimestamp` are mandatory.
- Timestamps must be in `YYYY-MM-DDTHH:MM:SS+05:30` format.
- `startTimestamp` must be less than or equal to `endTimestamp`.
- The timestamp range cannot exceed merchant configuration `listTransactionMaxDiffInDays`; when absent, the default is `1` day.
- If `enableListTransactionsLimitOffset` is enabled, both `limit` and `offset` are mandatory and `limit` must be less than or equal to `listTransactionsMaxLimit`; when absent, the default max is `100`.
- Results are sorted newest first within the queried table partitions.
- `callbackStatus` applies only in this mode.
- `requestType` applies only when `enableListTransactionsRequestType` is enabled. If that flag is disabled or `requestType` is omitted, Newton uses `PARENTMERCHANT`.

### Status Handling

For S2S requests, `status` accepts only `SUCCESS`, `PENDING`, and `FAILURE`.

Newton also handles internal `DEEMED` transactions:

- In customer-scoped mode, requesting `PENDING` or `SUCCESS` causes Newton to fetch `DEEMED` transactions too. P2P deemed transactions are returned with pending semantics; P2M deemed transactions are returned with success semantics.
- In merchant pull-listing mode, requesting `SUCCESS` causes Newton to fetch `DEEMED` transactions too. The response filters deemed transactions so P2M deemed transactions appear for `SUCCESS`.

### Pagination Guidance

Use stable timestamp or date windows while paging:

1. Send `limit` and `offset: 0`.
2. Increase `offset` by the same `limit` until `txnList.length < limit`.
3. Keep the same `startDate`/`endDate` or `startTimestamp`/`endTimestamp` across pages.
4. Prefer smaller timestamp windows for pull-listing reconciliation so new transactions do not shift records between pages.

For pull listing over a month boundary, Newton may query current and previous transaction partitions and apply the remaining limit/offset across them.

## Success Response

### Response Envelope

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
        "merchantRequestId": "ORDER12345",
        "gatewayResponseCode": "00",
        "gatewayResponseMessage": "SUCCESS",
        "gatewayReferenceId": "UPIREF123456789",
        "gatewayTransactionId": "TXN123456789",
        "amount": "100.00",
        "payeeName": "Merchant Store",
        "payeeVpa": "merchant@bank",
        "payerName": "Customer Name",
        "payerVpa": "customer@bank",
        "remarks": "Order payment",
        "transactionTimestamp": "2026-06-30T12:30:00+05:30",
        "type": "PAY",
        "gatewayResponseStatus": "SUCCESS",
        "refUrl": "https://merchant.example/orders/ORDER12345",
        "payerAccType": "SAVINGS",
        "umn": "MANDATE123@bank"
      }
    ]
  },
  "udfParameters": "{\"reconciliationRunId\":\"RUN-1001\"}"
}
```

When no records match, Newton returns success with an empty list:

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

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful API execution. |
| `responseCode` | string | `SUCCESS` for successful API execution. |
| `responseMessage` | string | `SUCCESS` for successful API execution. |
| `payload` | object | Present on success. Contains merchant identifiers and transactions. |
| `udfParameters` | string | Echoed from request when supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id used for the response. If `enableSubMerchantIdListTxnResponse` is enabled, parent merchant id may be returned even when a sub-merchant context is used. |
| `merchantChannelId` | string | Merchant channel id used for the response. If `enableSubMerchantIdListTxnResponse` is enabled, parent merchant channel id may be returned even when a sub-merchant context is used. |
| `merchantCustomerId` | string | Echoed in customer-scoped mode. Omitted in merchant pull-listing mode. |
| `txnList` | array | Matching transactions, newest first. Empty when no records match. |

### `payload.txnList[]`

Optional fields are omitted when the stored transaction does not contain that data, when the API version does not expose it, or when S2S response trimming suppresses it.

For S2S `x-api-version > 5`, the implementation suppresses several fields that are mainly for SDK/customer views, including split details, expiry, payee and payer mobile numbers, P2M flag, payee MCC, self-initiated flag, bank details, some mandate/list display fields, UDIR payer/payee response-code breakdowns, customer mobile number, international FX details, and complaint auto-update fields.

| Field | Type | Description |
| --- | --- | --- |
| `merchantRequestId` | string | Merchant request/order id stored in transaction metadata, when available. |
| `gatewayResponseCode` | string | Newton/gateway response code for the transaction. |
| `gatewayResponseMessage` | string | Human-readable response message for the transaction. |
| `gatewayResponseStatus` | string | Response status exposed for API versions `>= 5`. |
| `gatewayReferenceId` | string | UPI response/reference id stored for the transaction. |
| `gatewayTransactionId` | string | Newton UPI request id for the transaction. |
| `amount` | string | Transaction amount formatted with two decimals. |
| `transactionAmount` | string | Same transaction amount in older/non-trimmed response modes. Omitted for S2S `x-api-version > 5`. |
| `splitDetails` | array | Split/convenience-fee details, when present and exposed. Omitted for S2S `x-api-version > 5`. |
| `expiry` | string | Collect/intent expiry timestamp, when present and exposed. |
| `payeeMobileNumber` | string | Payee mobile number, when exposed. |
| `payeeName` | string | Payee display name. |
| `payeeVpa` | string | Payee VPA. |
| `payerMobileNumber` | string | Payer mobile number, when exposed. |
| `payerName` | string | Payer display name, when stored. |
| `payerVpa` | string | Payer VPA. |
| `payerAccType` | string | Payer account type. Exposed for API versions `> 4` and in pull-listing mode. |
| `payerAccBin` | string | Payer account BIN. Exposed in pull-listing mode when available. |
| `payerAccountHash` | string | Payer account hash. Exposed in pull-listing mode when available. |
| `remarks` | string | Transaction remarks. |
| `transactionTimestamp` | string | Transaction timestamp. Merchant configuration can choose whether this comes from stored transaction creation time or request authorization details. |
| `type` | string | Transaction type, for example `PAY` or `COLLECT`. |
| `isP2MTransaction` | boolean | Whether the transaction is treated as P2M. Omitted for S2S `x-api-version > 5`. |
| `payeeMcc` | string | Payee MCC, when exposed. |
| `refUrl` | string | Reference URL stored in transaction metadata, when available. |
| `selfInitiated` | string | Whether the transaction was self-initiated, returned as text in non-trimmed response modes. |
| `bankCode` | string | Bank code for the customer-side account. Exposed in older/non-trimmed response modes. |
| `maskedAccountNumber` | string | Masked account number for the customer-side account. Exposed in older/non-trimmed response modes. |
| `bankAccountUniqueId` | string | Bank account unique id. Exposed in older/non-trimmed response modes. |
| `subMerchantId` | string | Sub-merchant id from transaction metadata when it differs from the current merchant or when sub-merchant response exposure is enabled. |
| `subMerchantChannelId` | string | Sub-merchant channel id from transaction metadata when it differs from the current merchant or when sub-merchant response exposure is enabled. |
| `collectType` | string | `TRANSACTION` or `MANDATE` for collect transactions, in older/non-trimmed response modes. |
| `orgMandateId` | string | Original mandate id, in older/non-trimmed response modes. |
| `upiNumber` | string | UPI number, in older/non-trimmed response modes. |
| `intTxnDetails` | object | International transaction FX details, in older/non-trimmed response modes. |
| `transactionType` | string | Mapped transaction type, in older/non-trimmed response modes. |
| `initiationMode` | string | UPI initiation mode. Exposed in pull-listing mode. |
| `payeeMerchantCustomerId` | string | Payee merchant customer id, in older/non-trimmed response modes. |
| `payerMerchantCustomerId` | string | Payer merchant customer id, in older/non-trimmed response modes. |
| `umn` | string | UPI mandate number, when the transaction is mandate-linked. |
| `seqNumber` | string | Mandate execution sequence number, in older/non-trimmed response modes. |
| `lrn` | string | LRN from payer info, in older/non-trimmed response modes. |
| `purpose` | string | UPI purpose code, in older/non-trimmed response modes. |
| `baseCurr` | string | Base currency for international transactions, in older/non-trimmed response modes. |
| `baseAmount` | string | Base amount for international transactions, in older/non-trimmed response modes. |
| `fx` | string | FX rate/details for international transactions, in older/non-trimmed response modes. |
| `mkup` | string | Markup for international transactions, in older/non-trimmed response modes. |
| `gatewayPayeeResponseCode` | string | UDIR payee response code, in older/non-trimmed response modes when enabled. |
| `gatewayPayeeReversalResponseCode` | string | UDIR payee reversal response code, in older/non-trimmed response modes when enabled. |
| `gatewayPayerResponseCode` | string | UDIR payer response code, in older/non-trimmed response modes when enabled. |
| `gatewayPayerReversalResponseCode` | string | UDIR payer reversal response code, in older/non-trimmed response modes when enabled. |
| `customerMobileNumber` | string | Customer mobile number, in older/non-trimmed response modes. |
| `complaintRaisedGatewayComplaintId` | string | Complaint id when complaint enrichment is enabled by a caller. Not expected from this S2S route because it sets complaint enrichment to false. |
| `complaintRaisedGatewayReferenceId` | string | Complaint gateway reference id when complaint enrichment is enabled by a caller. |
| `complaintRaisedGatewayResponseCode` | string | Complaint response code when complaint enrichment is enabled by a caller. |
| `complaintRaisedGatewayResponseMessage` | string | Complaint response message when complaint enrichment is enabled by a caller. |
| `complaintRaisedGatewayResponseStatus` | string | Complaint response status when complaint enrichment is enabled by a caller. |
| `complaintRemarks` | string | Complaint remarks when complaint enrichment is enabled by a caller. |
| `queryReferenceId` | string | Complaint query reference id when complaint enrichment is enabled by a caller. |
| `crn` | string | Complaint reference number when complaint enrichment is enabled by a caller. |
| `reqAdjFlag` | string | Requested adjustment flag when complaint enrichment is enabled by a caller. |
| `reqAdjCode` | string | Requested adjustment code when complaint enrichment is enabled by a caller. |
| `reqAdjAmount` | string | Requested adjustment amount when complaint enrichment is enabled by a caller. |
| `adjFlag` | string | Adjustment flag when complaint enrichment is enabled by a caller. |
| `adjCode` | string | Adjustment code when complaint enrichment is enabled by a caller. |
| `adjAmount` | string | Adjustment amount when complaint enrichment is enabled by a caller. |
| `autoUpdateNote` | string | UDIR auto-update note in older/non-trimmed response modes when enabled. |

## Failure Responses

Failure responses use the same response transport as success responses. If the response is encrypted or signed, decrypt/verify it first, then read `status`, `responseCode`, and `responseMessage`.

HTTP status depends on the layer that rejects the request. Request-body validation uses the standard failure body but may be returned through Newton's API error wrapper with HTTP 200. Merchant auth, IP, and access failures commonly use HTTP 401. Business validation commonly uses HTTP 400. Clients should key business handling off the decrypted body, not HTTP status alone.

### Request Validation Failures

Missing `limit`/`offset` in customer-scoped mode:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"limit & offset should be present.\""
}
```

Missing `startTimestamp`/`endTimestamp` when `merchantCustomerId` is omitted:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"startTimestamp & endTimestamp should be present.\""
}
```

Invalid `limit` or `offset`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"Value is not valid\""
}
```

Invalid date:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"date value not valid\""
}
```

Invalid timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"timestamp value not valid\""
}
```

Empty list for `status` or `accountTypes`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ListValidation \"Field is empty\""
}
```

Unsupported status, for example `EXPIRED`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed EXPIRED\""
}
```

Invalid `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

### Business Validation Failures

Pull listing is not enabled and `merchantCustomerId` is omitted:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantCustomerId is mandatory"
}
```

`requestType` is sent in a sub-merchant list-transaction request:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Request type is not applicable for submerchant list transactions"
}
```

Pull-listing range has `startTimestamp` after `endTimestamp`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid startTimestamp or endTimestamp."
}
```

Pull-listing timestamp window is too large:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Difference in startTimestamp and endTimestamp must be less than or equal to 1 days"
}
```

Pull-listing pagination is mandatory for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Limit and Offset is mandatory"
}
```

Pull-listing `limit` exceeds the merchant maximum:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "limit must be less than or equal to 100"
}
```

Customer, merchant customer, or related lookup failures are returned as validation/business failures. Exact messages can vary by the lookup that failed, for example:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid MerchantCustomer not found"
}
```

### Authentication, Signature, API Access, and IP Failures

Missing merchant headers, missing raw body/timestamp headers, invalid signature, expired timestamp, or invalid IP restriction:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not enabled for a disabled merchant/sub-merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If the request is signed or encrypted and `iat` is missing, the pre-auth validation path can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

### Encryption and Envelope Failures

Malformed JWE/JWS envelopes, an invalid key id, decryption failure, or a payload that cannot be decoded into the List Transactions request type is rejected before business logic runs. Depending on the exact failure point, the response may be an encrypted error response or a plain error response with one of the standard failure codes:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid request payload"
}
```

or:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### Downstream and Internal Failures

Database/query failures while fetching transactions return an internal server error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Unexpected missing stored transaction fields, such as missing UPI response id, payer VPA, payee VPA, or self-initiated flag while mapping a stored transaction, can also surface as internal errors. These are retryable only after checking with Newton support, because they indicate inconsistent stored transaction data or infrastructure failure rather than a client request issue.

## Client Handling Guidance

- Treat `payload.txnList: []` with `SUCCESS` as a valid empty result.
- Do not retry validation, auth, IP, or API access failures without changing the request/configuration.
- Retry internal errors with exponential backoff and an idempotent reconciliation job. Keep the same date/timestamp window and pagination parameters during retry.
- For pull listing, use small timestamp windows and avoid very wide ranges. The default maximum window is 1 day unless merchant configuration changes it.
- Store and compare `gatewayTransactionId` and `gatewayReferenceId` for reconciliation.
- If `udfParameters` is used for client correlation, send a compact JSON-object string and avoid restricted characters.
- For newer S2S integrations, expect trimmed transaction objects on `x-api-version > 5`; do not require fields that are documented as conditional or older/non-trimmed only.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:329)
- Route handler and merchant signature verification call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2277)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:640)
- S2S request/response types and request validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1499)
- S2S request/response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:944)
- Product logic and pull/customer listing branches: [src/Newton/Product/Merchant/Transactions/ListTransaction.hs](../../src/Newton/Product/Merchant/Transactions/ListTransaction.hs:31)
- List transaction business validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:262)
- Common validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:222)
- Date/timestamp defaults and range validation: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:4336)
- Transaction response mapping: [src/Newton/Utils/Transformers/Transformer7.hs](../../src/Newton/Utils/Transformers/Transformer7.hs:117)
- Response transaction type: [src/Newton/Types/API/Transaction.hs](../../src/Newton/Types/API/Transaction.hs:17)
- S2S envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:11)
- Merchant signature, API access, and IP validation: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:39)
- Transaction query logic: [src/Newton/Storage/QueriesMiddleware/Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:440)
