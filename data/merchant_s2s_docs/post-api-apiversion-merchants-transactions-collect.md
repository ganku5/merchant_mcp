# Collect Approve/Decline API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/collect`

## Overview

Collect is a server-to-server API used to approve or decline an existing pending UPI collect request for a merchant customer.

A collect request is first created by a payee and reaches Newton as a pending transaction. The merchant backend calls this API with the pending transaction id, payer and payee VPAs, amount, customer profile, device fingerprint, and either an approval credential or a decline action. Newton validates that the pending collect transaction matches the request and then sends the approve or decline action to NPCI.

Use this API when the merchant controls the customer authorization journey from its backend and needs to accept or reject a collect request on behalf of an onboarded merchant customer.

## Business Use Case

Collect approve/decline helps merchants:

- Authorize a pending collect debit from a registered customer account.
- Decline a pending collect request without collecting payment.
- Validate that the collect request still exists and is pending before acting on it.
- Bind approval to the expected payer VPA, payee VPA, amount, customer, device, and payer account.
- Support mandate collect approval when the pending transaction is linked to a mandate.
- Support UPI Lite, biometric credential, and pre-approved amount-block flows where enabled.
- Return final gateway response codes and transaction status for reconciliation.

## Integration Flow

1. Merchant obtains or lists pending collect requests for a merchant customer.
2. Merchant asks the customer to approve or decline the collect request.
3. For approval, merchant collects the appropriate credential block or uses an enabled pre-approved amount-block flow.
4. Merchant calls `collect` with `requestType = "APPROVE"` or `requestType = "DECLINE"`.
5. Newton verifies the encrypted/signed request, merchant access, customer profile, device fingerprint, and request payload.
6. Newton finds the matching pending collect transaction using `upiRequestId`, payer VPA, payee VPA, amount, payer role, and pending status.
7. Newton resolves the payer account and sends the approve/decline request to NPCI.
8. Newton returns a success API envelope containing the transaction's gateway status, response code, and response message. A successful API call can still contain a failed or declined gateway result in `payload.gatewayResponseStatus`.

Important identifiers:

- `merchantCustomerId`: Merchant customer/profile id for the payer.
- `merchantRequestId`: Merchant-generated reference for this approval or decline attempt. It is stored in transaction metadata; the code does not enforce idempotency on this field for this API.
- `upiRequestId`: Original collect transaction id. This becomes `payload.gatewayTransactionId` in the response.
- `bankAccountUniqueId` or `accountReferenceId`: Payer account selector. For many Newton PSP flows either may be supplied; for some ICICI/GPay flows `accountReferenceId` and `ifsc` are required.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/collect
```

Payloads use the standard Newton server-to-server encrypted or signed request/response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. Required for merchant signature verification. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. Required for merchant signature verification. |
| `x-merchant-signature` | Signature over merchant id, channel id, optional sub-merchant ids, timestamp, and raw request body for plain signed requests. |
| `x-timestamp` | 13-digit request timestamp used for freshness checks. |
| `x-forwarded-for` | Required when the merchant has IP whitelisting configured; the first IP must be whitelisted. |
| `x-request-id` | Optional client request id for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

Optional sub-merchant headers `x-sub-merchant-id` and `x-sub-merchant-channel-id` are included in signature verification when supplied.

### Authentication, Signing, and Encryption

The route accepts Newton's standard `EncRequest` envelope:

- Encrypted request (`JWE`) for encrypted integrations.
- Signed request (`JWS`) for signed integrations.
- Plain JSON business payload only where explicitly enabled for the merchant/environment.

For encrypted or signed payloads, the decrypted payload must include `iat`; Newton validates it as a timestamp before continuing. For plain unsigned payloads, merchant signature verification uses `x-merchant-signature`, `x-timestamp`, and the raw request body.

Before product logic runs, Newton verifies:

- Merchant identity from `x-merchant-id` and `x-merchant-channel-id`.
- Merchant signature or encrypted/signed payload integrity.
- Request timestamp freshness.
- API access configuration. If the API is blocked or not allowed for the merchant, the request is rejected.
- IP whitelisting when `whitelistedIps` is configured for the merchant.
- Merchant customer and customer lookup using `merchantCustomerId`.

Responses use `EncResponse`. Depending on merchant response strategy, Newton returns a signed response, encrypted response, or plain unsigned response with a response signature header.

## Request

### Approve Collect

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a9f5c0c3c9a0e3f1",
  "merchantRequestId": "COLLECTAPPROVE123",
  "payerVpa": "customer@psp",
  "payeeVpa": "merchant@psp",
  "amount": "100.00",
  "upiRequestId": "COLLECTTXN123456",
  "requestType": "APPROVE",
  "bankAccountUniqueId": "acc_hash_123",
  "credBlock": "{\"cred\":{\"data\":{\"encryptedBase64String\":\"...\"}}}",
  "currency": "INR",
  "remarks": "Collect payment",
  "iat": "1720000000000"
}
```

### Approve Collect With Amount Block / Pre-Approved Credential

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a9f5c0c3c9a0e3f1",
  "merchantRequestId": "COLLECTAPPROVE124",
  "payerVpa": "customer@psp",
  "payeeVpa": "merchant@psp",
  "amount": "100.00",
  "upiRequestId": "COLLECTTXN123457",
  "requestType": "APPROVE",
  "accountReferenceId": "ACCREF123",
  "isAmountBlocked": true,
  "currency": "INR",
  "iat": "1720000000000"
}
```

### Decline Collect

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a9f5c0c3c9a0e3f1",
  "merchantRequestId": "COLLECTDECLINE123",
  "payerVpa": "customer@psp",
  "payeeVpa": "merchant@psp",
  "amount": "100.00",
  "upiRequestId": "COLLECTTXN123456",
  "requestType": "DECLINE",
  "bankAccountUniqueId": "acc_hash_123",
  "currency": "INR",
  "iat": "1720000000000"
}
```

### Mandate Collect Approval

Use `collectType = "MANDATE"` only when the pending transaction is a mandate collect transaction.

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a9f5c0c3c9a0e3f1",
  "merchantRequestId": "MANDATECOLLECTAPPROVE123",
  "payerVpa": "customer@psp",
  "payeeVpa": "merchant@psp",
  "amount": "100.00",
  "upiRequestId": "MANDATECOLLECTTXN123",
  "collectType": "MANDATE",
  "requestType": "APPROVE",
  "accountReferenceId": "ACCREF123",
  "credBlock": "{\"cred\":{\"data\":{\"encryptedBase64String\":\"...\"}}}",
  "currency": "INR",
  "iat": "1720000000000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer/profile id. Must identify an active customer for the merchant. Max 256 characters. Allowed characters: letters, numbers, `.`, `_`, `+`, `/`, `=`, `-`; the first character must be alphanumeric, `+`, `/`, or `=`. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint for the registered device. Newton compares this and `fallbackDeviceFingerPrint` with the stored device fingerprint/SSID. Must be non-empty. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Secondary device fingerprint accepted by the device validation step. |
| `merchantRequestId` | string | Yes | No default. | Merchant-generated reference for this collect action. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `payerVpa` | string | Yes | No default. | Customer/payer VPA. Must match the pending collect transaction. Format: `local@handle`, 3 to 255 characters. |
| `payeeVpa` | string | Yes | No default. | Payee VPA from the pending collect request. Must match the pending collect transaction. Format: `local@handle`, 3 to 255 characters. |
| `payeeName` | string | No | No default. | Optional payee display name. Must be non-empty if supplied. It is accepted by the API type but not used by the current collect approve/decline route. |
| `amount` | string | Yes | No default. | Collect amount. Must be greater than `0.00` and formatted exactly as two decimals, for example `100.00`. Must match the pending collect transaction. |
| `upiRequestId` | string | Yes | No default. | Original collect transaction id. Must be 1 to 35 alphanumeric characters and identify a pending collect transaction. |
| `collectType` | string | No | Omitted behaves as normal transaction collect. | Allowed values: `TRANSACTION`, `MANDATE`. Send `MANDATE` only for pending mandate collect transactions. If `MANDATE` is sent for a non-mandate transaction, the request fails. |
| `requestType` | string | Yes | No default. | `APPROVE` or `DECLINE`. |
| `bankAccountUniqueId` | string | Conditional | For non-P2M-SDK flows with a known primary VPA-account mapping, Newton may resolve the account from `payerVpa` when both account selectors are omitted. Otherwise no default. | Payer account hash/unique id. Use this or `accountReferenceId` as instructed during onboarding. Must be non-empty if supplied. |
| `accountReferenceId` | string | Conditional | No default. | Payer account reference/id. Required for some ICICI/GPay flows. Must be non-empty if supplied. |
| `ifsc` | string | Conditional | No default. | Required for some migrated ICICI/GPay account-reference flows. Must be non-empty if supplied. |
| `credBlock` | string | Conditional | No default. | Required for normal `APPROVE` requests unless `isAmountBlocked = true` is used for an enabled pre-approved flow. Must be a JSON string containing a valid MPIN credential, supported UPI Lite ARQC credential, or biometric credential. |
| `isAmountBlocked` | boolean | Conditional | Omitted behaves as not pre-approved. | For pre-approved/amount-blocked approval. If `APPROVE` is sent, at least one of `credBlock` or `isAmountBlocked` must be present. `true` causes Newton to build a pre-approved credential internally. |
| `purpose` | string | Conditional | No default. | UPI purpose code. Required by some credential paths; UPI Lite ARQC credentials are accepted only for supported purpose codes such as `43`, `44`, `46`, and `50`. |
| `currency` | string | Yes | No default. | Currency value supplied by the merchant, normally `INR`. Validation only requires a non-empty string. |
| `udfParameters` | string | No | No default. Echoed in response if supplied. | Merchant-defined metadata as a JSON-object string. Must parse as a JSON object and must not contain characters rejected by validation (`/`, `$`, `-`, `*`, `!`, `%`, `~`, backtick). |
| `customerConsentType` | string | No | No default. | Optional consent type stored in transaction metadata and sent to NPCI. Allowed JSON enum values: `PAN`, `AADHAAR`, `AADHAARTOKEN`, `PASSPORT`, `VOTERID`, `DRIVINGLICENSE`, `GSTIN`. |
| `iat` | string | Conditional | Required for encrypted/signed payloads. | Issued-at timestamp used during envelope validation. |
| `location` | string | No | No default. | Device/location metadata sent to NPCI. Must be non-empty if supplied. |
| `geocode` | string | No | No default. | Latitude and longitude in `lat,long` format. Latitude must be within `-90` to `90`; longitude within `-180` to `180`. |
| `ip` | string | No | No default. | Device/customer IP sent to NPCI. Must be valid IPv4 or IPv6 if supplied. |
| `capability` | string | No | No default. | Device capability string sent to NPCI. Must be 1 to 99 characters. |
| `preAuthTokensParam` | object | No | No default. | Optional pre-auth token object forwarded in transaction metadata for approval flows. |
| `timestamp` | string | Conditional | No default. | Required when `credBlock` contains a biometric credential. Passed to NPCI for approval. |
| `refCategory` | string | No | Defaults to configured NPCI reference category when omitted. | Reference category sent to NPCI for approval. Must be non-empty if supplied. |
| `refUrl` | string | No | No default. | Reference URL sent to NPCI for approval. Must be non-empty if supplied. |
| `clVersion` | string | Conditional | No default. | Required when `credBlock` contains a biometric credential. Must be non-empty if supplied. |
| `remarks` | string | No | For approval, NPCI request remarks default to `Payment via {pspName}UPI` when omitted. For decline, remarks are not used. | Customer/payment note. Must be 1 to 255 characters, start with an alphanumeric or hyphen after optional spaces, and contain only letters, numbers, spaces, and hyphen. |

## Validation Rules

### Request Matching

Newton looks up the original transaction by all of these values:

- `upiRequestId`.
- `payerVpa`.
- `payeeVpa`.
- `amount`.
- Payer role.
- Pending status.
- Non-self-initiated collect transaction.

If no matching record is found, the response is `INVALID_DATA` with `Original record not found`. If the record exists but is no longer pending, the request is rejected as an already processed collect authorization.

### Approval Rules

- `requestType` must be `APPROVE`.
- At least one of `credBlock` or `isAmountBlocked` must be present.
- If a normal `credBlock` is supplied, it must decode to a supported NPCI credential structure.
- If `isAmountBlocked = true` and no `credBlock` is supplied, Newton generates a pre-approved credential internally.
- If biometric credential data is supplied, both `timestamp` and `clVersion` are mandatory.
- If UPI Lite ARQC credential data is supplied, `purpose` must be one of the supported Lite purpose codes.
- The payer VPA must belong to the customer and be active/valid for outgoing money.
- The payee VPA must not be blocked by the customer when block/spam validation is enabled.
- If the payer account type is `UOD` and the collect is treated as P2P (`payeeMcc = "0000"`), the transaction is rejected.

### Decline Rules

- `requestType` must be `DECLINE`.
- `credBlock` and `isAmountBlocked` are not required.
- Newton still validates the customer, device fingerprint, pending transaction, payer account, and mandate/account relationship where applicable.

### Mandate Rules

- `collectType = "MANDATE"` is valid only when the pending transaction has a mandate id.
- If `collectType = "MANDATE"` is sent for a non-mandate collect transaction, Newton returns `INVALID_DATA`.
- For mandate transactions, Newton validates the supplied account selector against the mandate's account. For migrated mandates, migrated-account resolution rules may apply.

### Account Selection Rules

- For regular Newton PSP flows, send either `bankAccountUniqueId` or `accountReferenceId` unless your integration is explicitly configured to resolve the account from the payer VPA's primary account mapping.
- For P2M-SDK-enabled merchants, one of `bankAccountUniqueId` or `accountReferenceId` is mandatory.
- For ICICI/GPay migrated-account flows, `accountReferenceId` is mandatory; if it is not a Newton account id, `ifsc` is also mandatory.
- If both `bankAccountUniqueId` and `accountReferenceId` are supplied, code paths prefer `bankAccountUniqueId` in account-mapping lookups.

## Response

### Success Response: Approved

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "COLLECTAPPROVE123",
    "customerMobileNumber": "9876543210",
    "payerVpa": "customer@psp",
    "payeeMcc": "5411",
    "payeeMerchantCustomerId": "PAYEE_CUST_123",
    "payeeVpa": "merchant@psp",
    "payeeName": "Merchant Store",
    "refUrl": "https://www.npci.org.in/",
    "bankAccountUniqueId": "acc_hash_123",
    "bankCode": "HDFC",
    "maskedAccountNumber": "XXXX1234",
    "amount": "100.00",
    "transactionTimestamp": "2024-07-03 10:30:00",
    "gatewayTransactionId": "COLLECTTXN123456",
    "gatewayReferenceId": "423456789012",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "requestType": "APPROVE",
    "collectType": "TRANSACTION",
    "seqNumber": "1",
    "payeeAccType": "SAVINGS",
    "payeeIfsc": "HDFC0000001"
  },
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

### Success Response: Declined

Newton uses the same top-level success envelope when the API successfully submits a decline and updates the transaction.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "COLLECTDECLINE123",
    "customerMobileNumber": "9876543210",
    "payerVpa": "customer@psp",
    "payeeMcc": "5411",
    "payeeVpa": "merchant@psp",
    "payeeName": "Merchant Store",
    "refUrl": "https://www.npci.org.in/",
    "bankAccountUniqueId": "acc_hash_123",
    "bankCode": "HDFC",
    "maskedAccountNumber": "XXXX1234",
    "amount": "100.00",
    "transactionTimestamp": "2024-07-03 10:31:00",
    "gatewayTransactionId": "COLLECTTXN123456",
    "gatewayReferenceId": "423456789013",
    "gatewayResponseStatus": "DECLINED",
    "gatewayResponseCode": "ZA",
    "gatewayResponseMessage": "collect auth rejected",
    "requestType": "DECLINE"
  }
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. Successful route processing returns `SUCCESS`. Check `payload.gatewayResponseStatus` for transaction outcome. |
| `responseCode` | string | API-level response code. Success value is `SUCCESS`. |
| `responseMessage` | string | API-level response message. Success value is `SUCCESS`. |
| `payload` | object | Collect approval/decline transaction details. |
| `udfParameters` | string | Echoed from request when supplied. |

### Payload Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id. |
| `merchantChannelId` | string | Merchant channel id. |
| `merchantCustomerId` | string | Merchant customer/profile id. |
| `merchantRequestId` | string | Merchant reference supplied in the request. |
| `customerMobileNumber` | string | Customer mobile number, trimmed before returning. |
| `payerVpa` | string | Payer VPA from the transaction. |
| `payeeMcc` | string | Payee MCC resolved from the transaction and MCC-version rules. |
| `payeeMerchantCustomerId` | string | Payee merchant customer id when available. |
| `payeeVpa` | string | Payee VPA from the transaction. |
| `payeeName` | string | Payee display name from transaction payee info when available. |
| `refUrl` | string | Reference URL resolved from the transaction/configuration. |
| `bankAccountUniqueId` | string | Payer account hash or migrated account id returned for the resolved account. |
| `bankCode` | string | Payer account bank code. |
| `maskedAccountNumber` | string | Masked payer account number. |
| `amount` | string | Amount from the request. |
| `customerIncentive` | string | GST/customer incentive value when present on the transaction. |
| `transactionTimestamp` | string | Transaction timestamp. Format is merchant-configuration dependent. |
| `gatewayTransactionId` | string | Original collect `upiRequestId`. |
| `gatewayReferenceId` | string | Gateway/NPCI response id (`upiResponseId`) stored on the transaction. |
| `gatewayResponseStatus` | string | Mapped transaction result: `SUCCESS` for code `00`, `DECLINED` for `ZA`, `PENDING` for `01`, `DEEMED` for `RB`, otherwise `FAILURE`. |
| `gatewayResponseCode` | string | Gateway response code resolved from NPCI response and Newton mapping rules. |
| `gatewayResponseMessage` | string | Gateway response message resolved from NPCI response and Newton mapping rules. |
| `requestType` | string | `APPROVE` or `DECLINE`, echoed from the request. |
| `collectType` | string | `TRANSACTION` or `MANDATE` when supplied. Omitted when absent in the request. |
| `seqNumber` | string | Mandate/transaction sequence number when present. |
| `gatewayPayerResponseCode` | string | Payer-side response code when available. |
| `gatewayPayeeResponseCode` | string | Payee-side response code when available. |
| `gatewayPayeeReversalResponseCode` | string | Payee reversal response code when available. |
| `gatewayPayerReversalResponseCode` | string | Payer reversal response code when available. |
| `payeeAccType` | string | Payee account type when available through version-controlled transaction/account resolution. |
| `payeeIfsc` | string | Payee IFSC when available through version-controlled transaction/account resolution. |
| `riskScore` | string | Risk score when merchant/PSP response-code mapping supplies one. |

## Failure Scenarios

Failure responses are returned in the same configured response envelope when possible. The examples below show decrypted bodies. Some validation layers return HTTP 400 or 401; many business failures use HTTP 200 with a failure body.

### Validation Failure

Examples include malformed amount, invalid VPA, invalid enum value, invalid `upiRequestId`, invalid geocode/IP, invalid `udfParameters`, empty optional fields, or unsupported remarks format.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "amount regex match failed",
  "payload": null
}
```

Another example for invalid request type:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Enum match failed \"PAY\"",
  "payload": null
}
```

### Missing Approval Credential

For `APPROVE`, at least one of `credBlock` or `isAmountBlocked` must be present.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "credblock mandatory",
  "payload": null
}
```

### Invalid Credential Data

If `credBlock` is absent, malformed, inconsistent with `isAmountBlocked`, or a UPI Lite credential is sent with an unsupported purpose code, Newton rejects the request.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid credBlock",
  "payload": null
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid credBlock/isAmountBlocked passed",
  "payload": null
}
```

Biometric approvals must include `timestamp` and `clVersion`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "timestamp cannot be empty for biometric credential requests",
  "payload": null
}
```

### Authentication, Signature, Timestamp, or IP Failure

Authentication can fail when merchant headers are missing, signature verification fails, encrypted/signed payload validation fails, `iat`/`x-timestamp` is invalid, or source IP is not whitelisted.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

When the API is blocked or not allowed for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED",
  "payload": null
}
```

### Merchant Customer, Customer, Device, or Account Failure

If `merchantCustomerId` does not resolve to a valid customer for the merchant, or the customer/account relation is invalid, Newton returns an invalid-data style failure.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found",
  "payload": null
}
```

If the device fingerprint does not match the customer's registered device:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Device fingerprint mismatch",
  "payload": null
}
```

If an account selector is required but neither selector is supplied:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory",
  "payload": null
}
```

### Pending Transaction Not Found or Already Processed

If no pending collect transaction matches the request:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Original record not found",
  "payload": null
}
```

If the collect transaction is already approved or declined, code uses the invalid collect authorization response:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Transaction has been already approved/rejected",
  "payload": null
}
```

### Invalid Mandate Collect Type

If `collectType = "MANDATE"` is sent for a transaction that is not linked to a mandate:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Data, ActionType MANDATE passed for a non-mandate transaction",
  "payload": null
}
```

### Blocked Payee or Disallowed Account Type

If the customer has blocked the payee VPA and block/spam validation is enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "VPA_BLOCKED",
  "responseMessage": "Transaction not allowed to blocked vpa's. Unblock first and try again.",
  "payload": null
}
```

If the payer account is an overdraft account and the transaction is not permitted:

```json
{
  "status": "FAILURE",
  "responseCode": "JPSA",
  "responseMessage": "TRANSACTION NOT PERMITTED FOR THIS A/C TYPE (OD)",
  "payload": null
}
```

### Limit, Risk, or Sherlock Failure

Newton checks transaction limits and risk/sherlock responses before forwarding approval. Some failures are returned as custom failure bodies with the gateway/risk response code and message.

```json
{
  "status": "FAILURE",
  "responseCode": "RISK_DECLINED",
  "responseMessage": "Transaction declined by risk checks",
  "payload": null
}
```

The exact `responseCode` and `responseMessage` depend on the downstream risk result.

### NPCI Timeout or Downstream Failure

If NPCI or the gateway times out for ICICI multibank mode, Newton returns a service-unavailable transaction error.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U69",
  "responseMessage": "UPI service is not reachable at the moment for transactional apis",
  "payload": null
}
```

For NPCI acknowledgement errors after a decline, Newton may mark the transaction failed and return a successful API response whose `payload.gatewayResponseStatus` is `FAILURE` and whose gateway code/message contain the NPCI result. Clients must always inspect `payload.gatewayResponseStatus`, not only top-level `status`.

### Internal Error

Unexpected missing stored data, decryption failure, malformed internal transaction info, or downstream exceptions can produce:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

## Idempotency, Retries, and Client Handling

- Treat `upiRequestId` as the primary transaction identifier. Store it with the merchant order and with the final `gatewayReferenceId`.
- `merchantRequestId` is required but this route does not perform duplicate suppression on it. Do not retry with a new `merchantRequestId` unless your reconciliation system deliberately wants a new attempt reference.
- Because the API acts on a pending collect transaction, approvals and declines are not safely repeatable after success. A second call normally fails because the transaction is no longer pending.
- If the client times out before receiving a response, query transaction status using the status API for the same `upiRequestId` before retrying.
- Retry only transient transport or `SERVICE_UNAVAILABLE_*` failures, and use the same `upiRequestId`, `merchantCustomerId`, payer/payee VPAs, amount, and account selector.
- For top-level `SUCCESS`, use `payload.gatewayResponseStatus` as the transaction result:
  - `SUCCESS`: payment approved successfully.
  - `DECLINED`: collect request was declined.
  - `PENDING`: wait and poll status.
  - `DEEMED`: reconcile using status/check flows and callbacks.
  - `FAILURE`: do not retry blindly; inspect `gatewayResponseCode` and `gatewayResponseMessage`.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:457)
- Route handler and auth pipeline: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2656)
- Request and response types/validation: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:778)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:43)
- Request envelope and response envelope: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Response envelope signing/encryption: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Main collect approve/decline business logic: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:569)
- Approval wrapper and credential handling: [src/Newton/Product/MerchantTransactionsSDKV2.hs](../../src/Newton/Product/MerchantTransactionsSDKV2.hs:547)
- NPCI collect pay/decline execution and pending-state check: [src/Newton/Product/TransactionV2.hs](../../src/Newton/Product/TransactionV2.hs:219)
- Response transformer and gateway status mapping: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:897)
- Approval payload transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:4335)
- Credential parser/default pre-approved credential behavior: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:2123)
- Pending collect transaction lookup: [src/Newton/Storage/QueriesMiddleware/Transaction.hs](../../src/Newton/Storage/QueriesMiddleware/Transaction.hs:744)
- Account resolution rules: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:541)
- Payee block validation: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2791)
- Common validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:34)
