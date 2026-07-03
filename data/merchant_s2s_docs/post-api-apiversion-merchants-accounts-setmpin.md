# Set MPIN API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/setMpin`

## Overview

Set MPIN is a server-to-server API used to set or reset the UPI MPIN for a customer's linked bank account.

The merchant calls this API after the customer is registered, device-bound, has a target bank account available in Newton, and has completed the OTP/common-library credential capture needed for MPIN setup or reset. Newton verifies the S2S envelope, merchant/customer context, linked account, optional customer VPA, registered device fingerprint, and credential payload, then sends an account update request to the bank/NPCI path with update type `set`.

Use this API after a successful Generate OTP flow, when the customer has entered the bank OTP and new MPIN through the UPI common library. Do not use it to trigger OTP, change a known existing MPIN, fetch balance, link an account, or authorize a payment.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Set MPIN helps merchants:

- Let a registered customer set or reset the UPI MPIN for a linked bank account from the merchant app.
- Complete first-time MPIN setup after account discovery/linking and OTP generation.
- Complete forgot-MPIN or reset-MPIN journeys where the bank requires OTP, card details, ATM PIN, or Aadhaar credential data.
- Keep the MPIN setup tied to a known Newton merchant customer, linked account, registered device, optional customer VPA, and UPI request id.
- Surface the actual bank/NPCI outcome through gateway response fields while returning a consistent Newton S2S response wrapper.
- Reconcile customer support and audit trails using `upiRequestId`, returned as `gatewayTransactionId`.

On a successful bank/NPCI response, Newton also updates local account state to mark MPIN as set, disables biometric auth for that account if it was enabled, and clears the merchant-customer `setMpinRequired` flag when that flag is present.

## Integration Flow

1. Merchant ensures the customer is registered with Newton, device-bound, and has the target bank account available from account discovery/linking APIs.
2. Merchant triggers the OTP required for set/reset MPIN, normally by calling the Generate OTP API.
3. Merchant app starts the UPI common-library set/reset MPIN credential flow and collects a `credBlock` containing the bank OTP credential and new MPIN credential.
4. Merchant backend creates a unique `upiRequestId` for this Set MPIN attempt.
5. Merchant backend calls `setMpin` using the configured encrypted/signed S2S envelope.
6. Newton decrypts/verifies the envelope, validates merchant signature and request freshness, and loads the merchant customer/customer context.
7. Newton validates the request body, resolves the linked account, validates `customerVpa` when supplied, verifies the device fingerprint, parses the credential block, and calls the downstream account-update path.
8. Merchant decrypts the response and reads `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` to determine whether the MPIN was set.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton.
- `bankAccountUniqueId`: Merchant-facing linked account identifier/account hash returned by account APIs.
- `accountReferenceId`: Newton account reference id returned by account APIs, or a migrated-account reference in specific GPay ICICI flows.
- `customerVpa`: Optional customer VPA used to validate VPA ownership when supplied.
- `upiRequestId`: Merchant-generated UPI request id for this Set MPIN attempt. Returned as `gatewayTransactionId`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/setMpin
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, when required by the configured signature process. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding, when your configured request mode uses header-level merchant signatures. JWS/JWE request modes verify the signature through the envelope itself. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. The route accepts Newton's `EncRequest` envelope: signed JWS, encrypted JWE containing a signed payload, or plain JSON only where the merchant configuration permits it. Production integrations should send the configured encrypted and/or signed request envelope. Plain JSON examples in this guide are decrypted business payloads only.

For signed/encrypted requests, `iat` in the decrypted business payload and `x-timestamp` in the request headers are validated for freshness. Timestamps must be 13-digit epoch milliseconds and within the configured freshness window.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Request

### Required Minimum

For new integrations, identify the linked account with `bankAccountUniqueId` or `accountReferenceId`. Send `customerVpa` when the Set MPIN attempt is tied to a specific VPA and you want Newton to validate that VPA under the customer context.

Using `bankAccountUniqueId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "SMPIN123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

Using `accountReferenceId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "SMPIN123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

For migrated-account flows where `accountReferenceId` is not a Newton account reference id, also send `ifsc`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "SMPIN123456791",
  "iat": "1735689600000",
  "accountReferenceId": "MIGRATED_ACCOUNT_ID",
  "ifsc": "EXAM0001234",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters and follow Newton merchant-customer-id format. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint returned/derived during device binding. Newton validates it against the customer's registered device. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate fingerprint accepted during device matching, typically used during device-fingerprint migration or fallback flows. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this Set MPIN attempt. Must be 1 to 35 alphanumeric characters. Returned as `gatewayTransactionId`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by S2S signature/encryption verification and request freshness checks. Required for signed/encrypted production requests, even though the business type is nullable. |
| `bankAccountUniqueId` | string | Conditional | No default. | Linked account identifier/account hash returned by account APIs. Send this or `accountReferenceId` for Newton/non-ICICI integrations. If account-id migration is enabled, Newton resolves the value before account lookup and returns the merchant-facing account id in the response. |
| `accountReferenceId` | string | Conditional | No default. | Newton account reference id returned by account APIs. Send this or `bankAccountUniqueId` for Newton/non-ICICI integrations. Required for GPay ICICI flows. In specific migrated GPay ICICI flows, this can carry a migrated account id and must be paired with `ifsc`. |
| `ifsc` | string | Conditional | No default. | Required for migrated GPay ICICI account lookup when `accountReferenceId` represents a migrated account id instead of a Newton account reference id. |
| `customerVpa` | string | No | If omitted, Newton does not perform VPA ownership validation and omits `payload.customerVpa` in the success response. | Customer VPA to validate against the customer/merchant-customer context. Send when the Set MPIN request is tied to a specific VPA. |
| `credBlock` | string | Yes | No default. | JSON string containing UPI credential data generated by the UPI common-library set/reset MPIN flow. Must include `mpincred` for the new MPIN and `otpcred` for the OTP credential. |
| `card` | string | Conditional | No default. Omitted means no separate card value is sent downstream. | Last six digits of the debit card for banks that require card details during set/reset MPIN. Must be exactly 6 numeric digits when supplied. Pair with `expiry` when the bank requires card/expiry details. |
| `expiry` | string | Conditional | No default. Omitted means no separate expiry value is sent downstream. | Card expiry in `MMYY` form for banks that require card details during set/reset MPIN. Must be exactly 4 numeric digits when supplied. Pair with `card` when the bank requires card/expiry details. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the success response. |
| `clVersion` | string | No | No default. | Common-library version associated with credential capture, when available. Passed to the downstream account-update path. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `bankAccountUniqueId` and `accountReferenceId`: one of these identifiers is required for normal account lookup. For GPay ICICI flows, `accountReferenceId` is mandatory. Missing account identifiers return a bad-request failure in Newton flows, and migrated ICICI lookup failures can surface as an internal integration error.
- `accountReferenceId` and `ifsc`: for GPay ICICI migrated-account flows, `accountReferenceId` is mandatory and `ifsc` is mandatory when the reference is a migrated account id rather than a Newton account id.
- `customerVpa`: optional for this API. When supplied, Newton validates the VPA format and verifies that the VPA exists under the customer/merchant-customer context. When omitted, the response omits `payload.customerVpa`.
- `fallbackDeviceFingerPrint`: omitted means only `deviceFingerPrint` is checked.
- `card` and `expiry`: optional at API validation level. If the issuing bank requires card/expiry details and they are not supplied through request fields or the credential block, the downstream set/reset MPIN call can fail.
- `credBlock`: required. Newton parses this string after request validation; malformed JSON or missing required credentials are rejected before a successful Set MPIN response is produced.
- `iat`: required by the S2S signature/encryption layer for signed/encrypted production requests.
- `udfParameters`: echoed only on success when supplied.
- `clVersion`: omitted means Newton sends no common-library version in the downstream account-update request.

On gateway success (`gatewayResponseCode = "00"`), Newton marks the account MPIN as set locally, disables biometric auth for the account if enabled, and clears `setMpinRequired` in merchant-customer store when it was `true`. These state changes are not returned as separate response fields.

### Nested Request Objects

`credBlock` is sent as a JSON string. Its contents are generated by the UPI common library/credential capture flow and should not be manually constructed by the merchant backend.

For Set MPIN, the parsed object must include both `mpincred` and `otpcred`:

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
  },
  "otpcred": {
    "type": "OTP",
    "subType": "SMS",
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

Optional credential entries are passed through to the downstream account-update path when present:

| Credential key | Required | Description |
| --- | --- | --- |
| `mpincred` | Yes | New MPIN credential generated by the UPI common library. |
| `otpcred` | Yes | OTP credential generated from the OTP captured for this set/reset MPIN attempt. |
| `atmpincred` | No | ATM PIN credential for banks/flows that require ATM PIN validation. |
| `carddetailscred` | No | Common-library card-detail credential for banks/flows that require encrypted card details. |
| `aadhaarcred` | No | Aadhaar credential for Aadhaar-enabled set/reset MPIN flows. |

Each credential object follows the common credential shape:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | Yes | Credential type produced by the common library, for example `PIN` or `OTP`. |
| `subType` | string | Yes | Credential subtype, for example `MPIN`, `SMS`, `ATMPIN`, or a bank/common-library-specific subtype. |
| `data.code` | string | Yes | Credential provider/code, commonly `NPCI`. |
| `data.encryptedBase64String` | string | Yes | Encrypted credential payload returned by the common library. |
| `data.ki` | string | Yes | Key identifier returned by the common library. |
| `data.hmac` | string | No | HMAC returned by the common library when available. |
| `data.pid` | string | No | PID value returned by the common library when available. |
| `data.skey` | string | No | Session key value returned by the common library when available. |
| `data.type` | string | No | Optional nested type value returned by some common-library credential variants. |

The actual decrypted request carries `credBlock` as an escaped JSON string:

```json
{
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Validation Notes

- `merchantCustomerId` must be 1 to 256 characters. The first character must be a letter, number, plus, slash, or equals sign. Subsequent characters may also include dot, underscore, plus, slash, equals, and hyphen.
- `deviceFingerPrint`, `credBlock`, and optional account/reference fields must be non-empty when supplied.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `customerVpa`, when supplied, must be 3 to 255 characters and match `local@handle` format.
- `card`, when supplied, must be exactly 6 numeric digits.
- `expiry`, when supplied, must be exactly 4 numeric digits.
- `udfParameters` must be a JSON object encoded as a string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick.
- Newton validates the submitted `deviceFingerPrint` against the registered device fingerprint, with `fallbackDeviceFingerPrint` accepted as an alternate when supplied.
- Newton validates that `customerVpa`, when supplied, exists and belongs to the customer/merchant-customer context.
- Newton parses `credBlock` as a credential JSON string and requires `mpincred` and `otpcred`. Malformed or incomplete credential blocks are rejected before a successful Set MPIN response is produced.

## Request Examples

### Set MPIN With Account Unique Id

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "fallbackDeviceFingerPrint": "a31c2d9e8b...",
  "upiRequestId": "SMPIN123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\",\"hmac\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\",\"hmac\":\"...\"}}}",
  "clVersion": "2.0",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Set MPIN With Account Reference Id

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "SMPIN123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Migrated Account Reference With IFSC

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "SMPIN123456791",
  "iat": "1735689600000",
  "accountReferenceId": "MIGRATED_ACCOUNT_ID",
  "ifsc": "EXAM0001234",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Card/Expiry Assisted Set MPIN

Use this when the bank requires last-six card digits and expiry in addition to the OTP and new MPIN credentials.

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "SMPIN123456792",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "card": "123456",
  "expiry": "1228",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"carddetailscred\":{\"type\":\"CARD\",\"subType\":\"CARDDETAILS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Aadhaar or ATM-PIN Assisted Set MPIN

Use this only for enabled flows where the prior OTP/common-library step returned Aadhaar or ATM PIN credentials.

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "SMPIN123456793",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"otpcred\":{\"type\":\"OTP\",\"subType\":\"SMS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"atmpincred\":{\"type\":\"PIN\",\"subType\":\"ATMPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"aadhaarcred\":{\"type\":\"AADHAAR\",\"subType\":\"AADHAAR\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API wrapper status. Success value is `SUCCESS`. |
| `responseCode` | string | Wrapper response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Wrapper response message. Success value is `SUCCESS`. |
| `payload` | object | Set MPIN result and account details. Present on success wrapper responses. |
| `udfParameters` | string | Echoed from request when supplied. |

The top-level `status` can be `SUCCESS` even when the bank/NPCI Set MPIN operation failed. Always use the gateway fields inside `payload` for the actual MPIN result:

- `payload.gatewayResponseStatus`
- `payload.gatewayResponseCode`
- `payload.gatewayResponseMessage`

Treat the MPIN as set only when `payload.gatewayResponseStatus` is `SUCCESS` and `payload.gatewayResponseCode` is `00`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id for the customer whose Set MPIN request was processed. |
| `customerMobileNumber` | string | Customer mobile number from the Newton customer profile. |
| `bankAccountUniqueId` | string | Merchant-facing linked account identifier returned for the resolved account. If account-id migration is enabled and the account has a migrated id, Newton can return that migrated id; otherwise it returns the account hash. |
| `bankCode` | string | Bank code/IIN for the linked account. |
| `customerVpa` | string | Echoed from request when supplied. Omitted when request `customerVpa` is omitted. |
| `maskedAccountNumber` | string | Masked linked account number. |
| `gatewayTransactionId` | string | Same value as request `upiRequestId`. Use it for reconciliation and support. |
| `gatewayResponseStatus` | string | `SUCCESS` when gateway response code is `00`; otherwise `FAILURE`. |
| `gatewayResponseCode` | string | Bank/NPCI response code. `00` means the MPIN setup/reset succeeded. If the downstream response has no error code, Newton uses `JP91`. |
| `gatewayResponseMessage` | string | Newton's mapped or downstream message for the gateway response code. If no message is available, Newton defaults to `Set Mpin failed`. |
| `uidaiErrorCode` | string | UIDAI error code returned by the downstream path for Aadhaar-enabled failures. Omitted when absent. |

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
    "gatewayTransactionId": "SMPIN123456789",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Set/Reset MPIN successful"
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Success Response With `customerVpa` Omitted

When request `customerVpa` is omitted, the success payload omits `customerVpa` because response serialization drops empty optional fields.

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
    "maskedAccountNumber": "XXXXXX1234",
    "gatewayTransactionId": "SMPIN123456791",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Set/Reset MPIN successful"
  }
}
```

### Gateway Business Failure Response

For gateway business failures, the wrapper can still be successful because Newton completed request processing and received a bank/NPCI result. In this case, the MPIN was not set.

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
    "gatewayTransactionId": "SMPIN123456789",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "RM",
    "gatewayResponseMessage": "INVALID MPIN ( VIOLATION OF POLICIES WHILE SETTING/CHANGING MPIN )"
  }
}
```

For Aadhaar-enabled failures, `uidaiErrorCode` can be present when returned by the downstream path:

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
    "gatewayTransactionId": "SMPIN123456793",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JP91",
    "gatewayResponseMessage": "Set Mpin failed",
    "uidaiErrorCode": "300"
  }
}
```

Other possible gateway failure codes depend on the bank/NPCI response. For example, `ZM` maps to incorrect UPI PIN/credential entry and `JP91` maps to a generic transaction or Set/Reset MPIN failure. Clients should display a user-safe failure message and let the customer restart the OTP and credential-capture flow where appropriate.

## Failure Responses

Failure responses use the same configured S2S response transport as success responses. `payload` is usually omitted when empty. HTTP status can vary by layer: many business validation failures are returned with an encrypted response body and HTTP 200, fingerprint mismatch uses HTTP 400, request freshness can use HTTP 400, and authentication/decryption failures use HTTP 401. Clients should inspect the decrypted `status`, `responseCode`, and `responseMessage` whenever a response body is available.

### Validation Failure

Occurs when the decrypted business payload fails Newton validation, such as empty `credBlock`, invalid `merchantCustomerId`, invalid `upiRequestId`, invalid `customerVpa`, malformed `udfParameters`, or invalid `card`/`expiry` length.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"credBlock field is empty\""
}
```

Invalid card length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ExactLengthValidation \"card field should be of length 6\""
}
```

Client handling: fix the payload and retry only after regenerating the S2S signature/envelope. If the customer already completed OTP/credential capture, prefer starting a fresh Set MPIN attempt with a fresh `upiRequestId` and credential block.

### Authentication, Signature, or Encryption Failure

Occurs when the S2S envelope cannot be verified, the request is signed with the wrong key, required merchant headers are missing, decryption fails, the verified key/session does not match the merchant/customer context, or the source IP is not whitelisted.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: do not ask the customer to re-enter OTP/MPIN until the server-side auth issue is fixed. Regenerate `iat`, timestamp, signature, and encrypted payload before retrying.

### Timestamp or Request Freshness Failure

Occurs when `x-timestamp` or `iat` is missing, malformed, or outside the accepted freshness window for the configured signed/encrypted request mode.

Malformed timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

Expired timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Client handling: regenerate the request envelope with current timestamps. Do not replay old signed or encrypted payloads.

### Merchant Configuration or Context Failure

Occurs when the merchant/customer context loaded by the verification layer is not allowed for the request, for example the API is disabled for the merchant, the merchant profile is disabled and `allowedApiNames` does not include this API, package-name/OS configuration blocks the customer, key profile checks fail, or the merchant customer/device context is missing.

API disabled or not allowed:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Missing active device/customer binding:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Missing device id on the merchant customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid DeviceId cannot be null for merchantCustomer"
}
```

Client handling: treat this as an integration/configuration or customer-registration issue. Re-run device binding or contact Newton support depending on the cause.

### Account or VPA Lookup Failure

Occurs when Newton cannot resolve the linked account or the optional customer VPA under the merchant customer context.

Missing account identifiers:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory"
}
```

Unknown or inactive account:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

Unknown or mismatched VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Vpa not found"
}
```

GPay ICICI migrated-account requests require `accountReferenceId`, and migrated references also require `ifsc`. Some of those missing migrated-flow inputs are currently surfaced as an internal integration error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: refresh the customer's linked account/VPA list before retrying. Do not continue with stale account identifiers.

### Device Fingerprint Mismatch

Occurs when neither `deviceFingerPrint` nor `fallbackDeviceFingerPrint` matches the registered device fingerprint.

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

Client handling: re-run device binding or use the correct registered device fingerprint. Do not retry the same credential block repeatedly.

### Credential Block Parsing or Missing Credentials

Occurs when `credBlock` is not valid JSON for Newton's credential block type, or when required `mpincred`/`otpcred` values are absent. The current implementation maps these credential-shape failures to an internal error response.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: collect a fresh Set MPIN credential block from the UPI common library. Verify that the escaped string contains both `mpincred` and `otpcred` before sending.

### Downstream Timeout or Unreachable Service

Occurs when the downstream bank/NPCI account-update path times out. Newton returns a failure wrapper instead of a success payload when the timeout is identified before a gateway business result can be returned.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U20",
  "responseMessage": "NPCI service is not reachable at the moment (U20)"
}
```

Client handling: outcome may be unknown if the request reached the bank/NPCI path. Do not assume the MPIN was set. Reconcile using `upiRequestId` if needed and ask the customer to retry later with a fresh OTP and credential-capture flow.

### Bad Downstream Response

Occurs when the downstream path reports an error but does not provide an error code that Newton can map.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

If NPCI returns a failed Set MPIN response without an error code, Newton can also return:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid error details"
}
```

Client handling: treat as a technical failure. Do not show success to the customer. Retry later with a fresh OTP, `upiRequestId`, and credential block if the customer still wants to set/reset MPIN.

### Unexpected Error

Unexpected missing internal values, malformed migrated-account state, or unhandled downstream decode failures are returned as internal errors.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: treat as a technical failure and contact Newton support with `merchantCustomerId`, `upiRequestId`, timestamp, and request id if available.

## Retry, Idempotency, and Client Handling

- Generate a unique `upiRequestId` for each customer-initiated Set MPIN attempt. Newton returns the same value as `gatewayTransactionId`.
- This API does not create a merchant-side idempotency record for the MPIN setup/reset. Do not rely on automatic duplicate suppression.
- If the response contains `payload.gatewayResponseStatus = "SUCCESS"` and `payload.gatewayResponseCode = "00"`, treat the MPIN as set/reset. Newton also updates local account state for MPIN-set handling.
- If the response contains top-level `SUCCESS` but `payload.gatewayResponseStatus = "FAILURE"`, treat the MPIN as not set. For credential, OTP, Aadhaar, card, or policy failures, let the customer restart the OTP and common-library credential-capture flow.
- If the call fails before a decrypted response is available, or returns `SERVICE_UNAVAILABLE_*`/`BAD_RESPONSE_FROM_NPCI`, the final bank outcome may be unknown. Use `upiRequestId` for support/reconciliation and prefer a fresh OTP/credential-capture flow for any new attempt.
- For validation, authentication, encryption, timestamp, or merchant-configuration failures, fix the integration issue and regenerate the encrypted/signed request. A stale `iat`, timestamp, signature, or encrypted payload should not be replayed.
- UPI credential blocks and OTPs can be time-bound and single-use from the common-library and bank perspective. Do not repeatedly replay the same `credBlock`.

## Source References

- S2S route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:518)
- S2S route handler and middleware chain: [Core.hs](../../src/Newton/App/Routes/Core.hs:2881)
- S2S request body extraction: [Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- Request/response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:37)
- Request, response, and request validation types: [Account.hs](../../src/Newton/Types/API/ServerToServer/Account.hs:354)
- Request body validation error behavior: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Customer VPA validator: [Common.hs](../../src/Newton/Validation/Common.hs:137)
- UDF parameters validator: [Common.hs](../../src/Newton/Validation/Common.hs:275)
- Merchant customer id validator: [Common.hs](../../src/Newton/Validation/Common.hs:311)
- UPI request id validator: [Common.hs](../../src/Newton/Validation/Common.hs:575)
- S2S payload/envelope verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature and timestamp verification: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp freshness validation: [DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Set MPIN product flow: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1247)
- Device fingerprint validation: [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Account/VPA mapping lookup: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:133)
- Account lookup behavior and migrated-account conditions: [DB.hs](../../src/Newton/Utils/DB.hs:540)
- Account-id migration helper: [Utils.hs](../../src/Newton/Utils/Utils.hs:5524)
- Credential block shape: [CredBlock.hs](../../src/Newton/Types/API/CredBlock.hs:10)
- Downstream Set MPIN wrapper and credential extraction: [MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:2517)
- Downstream response validation: [MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:1907)
- NPCI Set MPIN account-update flow: [AccountV2.hs](../../src/Newton/Product/AccountV2.hs:729)
- S2S response transformer: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1816)
- Gateway response status/code mapping: [Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:1049)
- Error response helpers and constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:15)
- Gateway response code mapping: [ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:19)
