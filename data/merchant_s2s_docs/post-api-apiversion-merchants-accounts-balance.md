# Check Balance API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/balance`

## Overview

Check Balance is a server-to-server API used to fetch the latest balance for a customer's linked UPI account.

The merchant calls this API after the customer has completed device binding and account linking. The request includes the customer, linked-account identifier, registered device fingerprint, and a UPI credential block collected from the customer's app. Newton validates the customer and device context, sends a UPI balance enquiry to the bank/NPCI path, and returns the bank result with the account balance when the enquiry succeeds.

Use this API when the merchant backend needs to show or refresh a customer's linked-account balance before a UPI payment, mandate, wallet top-up, credit-line use case, or account-management journey.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

## Business Use Case

Check Balance helps merchants:

- Show the customer the balance of a linked UPI bank account after MPIN or biometric authorization.
- Confirm that the customer selected the expected linked account before a payment or mandate flow.
- Refresh available balance and, where returned by the bank/account type, outstanding amount for credit or credit-line accounts.
- Support biometric balance enquiry for merchants enabled for biometric credential collection.
- Keep an auditable `upiRequestId` for each balance enquiry.

## Integration Flow

1. Merchant ensures the customer is registered with Newton and has an active device binding.
2. Merchant fetches or stores the linked account identifiers from account-listing/linking APIs.
3. Merchant app collects the customer's UPI credential block for balance enquiry.
4. Merchant backend creates a unique `upiRequestId` and calls this API with the customer, account, device, and credential details.
5. Newton verifies the S2S envelope, merchant configuration, timestamp/signature, customer context, and customer-level rate limit.
6. Newton locates the linked account, validates the submitted `deviceFingerPrint` against the registered device, and sends the balance enquiry.
7. Merchant decrypts the response and reads `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` to determine the actual bank/NPCI result.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton.
- `bankAccountUniqueId`: Account hash/migrated account identifier returned by account APIs.
- `accountReferenceId`: Newton account reference id returned by account APIs.
- `upiRequestId`: Merchant-generated UPI request id for this balance enquiry. It is returned as `gatewayTransactionId`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/balance
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within 30 minutes of Newton's clock. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Depending on the configured envelope, send the required signature/encryption headers such as `x-merchant-signature` with the encrypted or signed payload.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Request

### Required Minimum

For new integrations, identify the linked account with `bankAccountUniqueId` or `accountReferenceId`.

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BAL123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

If your integration uses `accountReferenceId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BAL123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

For biometric balance enquiry, also send `customerVpa`, `timestamp`, and `clVersion`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BAL123456791",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "customer@bank",
  "timestamp": "1735689600000",
  "clVersion": "2.0",
  "credBlock": "{\"biocred\":{\"type\":\"BIOMETRIC\",\"subType\":\"BIOMETRIC\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters and follow Newton merchant-customer-id format. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint returned/derived during device binding. Newton validates it against the customer's registered device. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate fingerprint accepted during device matching, typically used during device-fingerprint migration or fallback flows. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this balance enquiry. Must be 1 to 35 alphanumeric characters. Returned as `gatewayTransactionId`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp in 13-digit epoch milliseconds. Required for encrypted/signed S2S requests because Newton validates it as part of request freshness. Plain-text test payloads do not require it. |
| `bankAccountUniqueId` | string | Recommended | No default. | Linked account identifier/account hash returned by account APIs. Send this or `accountReferenceId` for new integrations. |
| `accountReferenceId` | string | Recommended | No default. | Newton account reference id returned by account APIs. Send this or `bankAccountUniqueId` for new integrations. |
| `ifsc` | string | Conditional | No default. | Required for specific migrated-account flows when `accountReferenceId` represents a migrated account id instead of a Newton account reference id. |
| `customerVpa` | string | Conditional | No default. | Customer VPA for the linked account. Required when `credBlock` contains biometric credentials. If account identifiers are omitted in supported non-P2M flows, Newton can use this VPA to select the primary linked account for that VPA. |
| `credBlock` | string | Yes | No default. | JSON string containing UPI credential data. For normal balance enquiry include `mpincred`; for biometric balance enquiry include `biocred`. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the response. |
| `timestamp` | string | Conditional | No default. | Required when `credBlock` contains biometric credentials. This is the credential/client timestamp passed to the balance enquiry path. |
| `clVersion` | string | Conditional | No default. | Required when `credBlock` contains biometric credentials. Represents the common library version used for credential capture. |
| `refCategory` | string | No | Defaults to Newton's configured NPCI reference category when omitted. | NPCI reference category to send for the balance enquiry. |
| `refUrl` | string | No | No default. | Merchant reference URL to send with the balance enquiry. |
| `remarks` | string | No | If omitted, the downstream balance enquiry uses `Check Balance` as the note. | Customer-facing or audit note for the balance enquiry. Must be 1 to 255 characters when supplied. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are simply not stored/returned when omitted.

- `bankAccountUniqueId` and `accountReferenceId`: at least one is recommended. For P2M SDK enabled merchants, one of these identifiers is mandatory. For some non-P2M flows, if both are omitted and `customerVpa` is supplied, Newton selects the primary account linked to that VPA.
- `ifsc`: required only for migrated-account flows where the account is resolved by migrated id and IFSC.
- `customerVpa`, `timestamp`, and `clVersion`: required together when `credBlock` contains `biocred`.
- `refCategory`: falls back to the configured NPCI reference category when omitted.
- `remarks`: omitted uses `Check Balance` in the downstream balance enquiry.
- `udfParameters`: omitted from the response when not supplied.

### Nested Request Objects

`credBlock` is sent as a JSON string. Its contents are generated by the UPI common library/credential capture flow and should not be manually constructed by the merchant backend.

For MPIN balance enquiry, the parsed object should include `mpincred`:

```json
{
  "mpincred": {
    "type": "PIN",
    "subType": "MPIN",
    "data": {
      "code": "NPCI",
      "encryptedBase64String": "...",
      "ki": "...",
      "hmac": "...",
      "pid": "...",
      "skey": "..."
    }
  }
}
```

For biometric balance enquiry, the parsed object should include `biocred`:

```json
{
  "biocred": {
    "type": "BIOMETRIC",
    "subType": "BIOMETRIC",
    "data": {
      "code": "NPCI",
      "encryptedBase64String": "...",
      "ki": "...",
      "hmac": "...",
      "pid": "...",
      "skey": "..."
    }
  }
}
```

### Validation Notes

- `merchantCustomerId` must be 1 to 256 characters and match Newton's merchant customer id format.
- `deviceFingerPrint`, `credBlock`, and optional account/reference fields must be non-empty when supplied.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `udfParameters` must be a JSON object encoded as a string and must pass allowed-character validation.
- `remarks` must be 1 to 255 characters and match the allowed remarks format.
- If `credBlock` cannot be parsed as the expected credential JSON, Newton returns `BAD_REQUEST`.
- If `credBlock` contains `biocred`, `clVersion`, `customerVpa`, and `timestamp` are required.
- Newton validates the submitted `deviceFingerPrint` against the registered device fingerprint, with `fallbackDeviceFingerPrint` accepted as an alternate when supplied.

## Request Examples

### MPIN Balance Enquiry

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "fallbackDeviceFingerPrint": "a31c2d9e8b...",
  "upiRequestId": "BAL123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\",\"hmac\":\"...\"}}}",
  "remarks": "Balance enquiry",
  "refUrl": "https://merchant.example/customers/CUST12345/accounts",
  "refCategory": "00",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Biometric Balance Enquiry

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "BAL123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "customer@bank",
  "credBlock": "{\"biocred\":{\"type\":\"BIOMETRIC\",\"subType\":\"BIOMETRIC\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\",\"hmac\":\"...\"}}}",
  "timestamp": "1735689600000",
  "clVersion": "2.0",
  "remarks": "Biometric balance enquiry"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API transport/business wrapper status. Success value is `SUCCESS`. |
| `responseCode` | string | Wrapper response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Wrapper response message. Success value is `SUCCESS`. |
| `payload` | object | Balance enquiry result and account details. |
| `udfParameters` | string | Echoed from request when supplied. |

The top-level `status` can be `SUCCESS` even when the bank/NPCI balance enquiry failed. Always use the gateway fields inside `payload` for the actual enquiry result:

- `payload.gatewayResponseStatus`
- `payload.gatewayResponseCode`
- `payload.gatewayResponseMessage`

Read `payload.balance` only when `payload.gatewayResponseCode` is `00` and `payload.gatewayResponseStatus` is `SUCCESS`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id resolved by Newton. |
| `customerMobileNumber` | string | Customer mobile number associated with the merchant customer. |
| `bankAccountUniqueId` | string | Account identifier returned for the resolved account. If the account has a migrated id, Newton returns the migrated id; otherwise it returns the account hash. |
| `bankCode` | string | Bank/IIN code for the resolved account. |
| `customerVpa` | string | Echoed from request when supplied. |
| `maskedAccountNumber` | string | Masked account number for display. |
| `balance` | string | Available balance returned by the bank/NPCI path. Present only on successful gateway response when returned by the account type/bank. |
| `outstandingAmount` | string | Outstanding amount returned by the bank/NPCI path for supported account types. Present only on successful gateway response when returned. |
| `gatewayTransactionId` | string | Same value as request `upiRequestId`. |
| `gatewayResponseStatus` | string | `SUCCESS` when `gatewayResponseCode` is `00`; otherwise `FAILURE`. |
| `gatewayResponseCode` | string | Bank/NPCI result code. Success value is `00`. |
| `gatewayResponseMessage` | string | Human-readable message mapped from `gatewayResponseCode`. |

### Example Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
    "bankCode": "123456",
    "customerVpa": "customer@bank",
    "maskedAccountNumber": "XXXXXX1234",
    "balance": "12500.50",
    "outstandingAmount": "250.00",
    "gatewayTransactionId": "BAL123456789",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your transaction is successful"
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Example Gateway Failure Response

When the request was accepted but the bank/NPCI balance enquiry returned an error code, the top-level wrapper remains `SUCCESS`; the gateway fields carry the failure.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "9876543210",
    "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
    "bankCode": "123456",
    "customerVpa": "customer@bank",
    "maskedAccountNumber": "XXXXXX1234",
    "gatewayTransactionId": "BAL123456789",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U16",
    "gatewayResponseMessage": "Check Balance failed"
  }
}
```

In gateway failures, `balance` and `outstandingAmount` are omitted.

## Failure Responses

Failure responses use the same encrypted response transport as success responses. After decryption, clients should inspect `status`, `responseCode`, and `responseMessage`; when a `payload` is present, also inspect its gateway response fields.

### Authentication, Encryption, and Merchant Configuration

Missing or invalid S2S headers, signature mismatch, failed JWS/JWE verification, decryption failure, invalid IP allowlist, or invalid merchant credentials:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API disabled or not allowed for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Malformed decrypted payload JSON:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"merchantCustomerId\" not found"
}
```

### Timestamp and Freshness

Missing `iat` for signed/encrypted payloads:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

`iat` or `x-timestamp` is not a 13-digit epoch-milliseconds value:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

`iat` or `x-timestamp` is outside the 30-minute freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

### Request Validation

Invalid required fields, empty fields, invalid `merchantCustomerId`, invalid `upiRequestId`, invalid `remarks`, or invalid `udfParameters`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "merchantCustomerId length is not in between 1 and 256, upiRequestId regex match failed"
}
```

The response message contains the validation errors joined into a single string. Treat the exact message as diagnostic text and fix the corresponding request fields.

Invalid `credBlock` JSON:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "credBlock not valid"
}
```

Biometric credential request without `clVersion`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "clVersion cannot be empty for biometric credential requests"
}
```

Biometric credential request without `customerVpa`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "customerVpa cannot be empty for biometric credential requests"
}
```

Biometric credential request without `timestamp`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "timestamp cannot be empty for biometric credential requests"
}
```

Missing linked-account identifier when the flow cannot resolve an account from `customerVpa`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory"
}
```

### Customer, Device, VPA, and Account Lookup

No active device binding or missing customer/device context for the merchant customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Submitted `deviceFingerPrint` does not match the registered device and does not match `fallbackDeviceFingerPrint`:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

Linked account not found or not active for the customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

Biometric activity tracking cannot resolve the account:

```json
{
  "status": "FAILURE",
  "responseCode": "ACCOUNT_NOT_FOUND",
  "responseMessage": "Account not found"
}
```

Invalid VPA/account association can also return an `INVALID_DATA` response from shared VPA/account lookup helpers. In those cases, retry only after correcting the customer VPA or linked-account identifiers.

### Rate Limiting

When customer-level balance enquiry rate limiting is configured and the customer exceeds the threshold:

```json
{
  "status": "FAILURE",
  "responseCode": "RATE_LIMIT_EXCEEDED",
  "responseMessage": "checkBalance requests reached maximum daily threshold limit"
}
```

### Bank/NPCI Transport Failures

NPCI timeout:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "NPCI service is not reachable at the moment (U09)"
}
```

The suffix in `responseCode` and the value in parentheses come from the timeout code returned by the downstream path. If no code is available, Newton uses `NA`.

Invalid or incomplete NPCI response:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

Unexpected internal error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Client Handling

- Treat `upiRequestId` as unique per balance enquiry. Store it with the customer/account balance-check attempt.
- Do not infer balance success from top-level `status`. Use `payload.gatewayResponseCode == "00"` and `payload.gatewayResponseStatus == "SUCCESS"`.
- Display/store `balance` and `outstandingAmount` only when they are present in a successful gateway response.
- For retryable transport failures such as NPCI timeout, retry with a new `upiRequestId` unless your reconciliation process explicitly requires reusing the original id.
- For validation, device, account, or merchant-configuration failures, correct the request/configuration before retrying.

## Source References

- Route type and handler: [Core.hs](../../src/Newton/App/Routes/Core.hs:295)
- Route flow: [Core.hs](../../src/Newton/App/Routes/Core.hs:1981)
- Request and response types: [Account.hs](../../src/Newton/Types/API/ServerToServer/Account.hs:146)
- S2S product flow: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:890)
- Shared balance flow and gateway validation: [MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:2316)
- S2S response transformer: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2218)
- Request validators: [Common.hs](../../src/Newton/Validation/Common.hs:168)
- Error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:25)
