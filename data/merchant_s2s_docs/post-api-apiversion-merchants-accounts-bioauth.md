# Bio Auth API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/bioAuth`

## Overview

Bio Auth is a server-to-server API used to enable, disable, or rotate biometric authentication consent for a customer's linked UPI account.

The merchant calls this API after the customer has completed device binding and account linking. For enablement and credential rotation, the merchant app collects UPI common-library credential data and sends it to Newton through the encrypted S2S envelope. Newton validates the merchant, customer, device, linked account, biometric-consent state, and request credentials, then sends an NPCI `ReqActivation` request for the requested biometric action.

Use this API when a customer opts in to biometric UPI authorization, opts out of biometric authorization, or refreshes biometric credentials for an already enabled account.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

## Business Use Case

Bio Auth helps merchants:

- Enable biometric authorization for a linked UPI account after the customer explicitly consents.
- Disable biometric authorization when the customer opts out or removes biometric use for the account.
- Rotate biometric credentials when the app or common-library flow refreshes biometric credential material.
- Keep account-listing and customer-profile flows aligned with whether biometric authorization is enabled for an account.
- Capture an auditable `upiRequestId` for each enable, disable, or rotate attempt.

Supported actions:

| Action | Use when | Credential requirement |
| --- | --- | --- |
| `ENABLE` | Customer is enabling biometric UPI authorization for the account. | `credBlock` is required and must contain both `mpincred` and `biocred`. |
| `DISABLE` | Customer is disabling biometric UPI authorization for the account. | `credBlock` is not required and is ignored for downstream biometric credentials. |
| `ROTATE` | Customer's biometric credential material must be refreshed while biometric auth is enabled. | `credBlock` is required and must contain `biocred`. If `mpincred` is also present, Newton ignores it for the NPCI rotate credential set. |

Important state rules:

- `ENABLE` is the first action for an account with no biometric consent record.
- `DISABLE` and `ROTATE` require biometric auth to have been enabled for the same merchant customer and account.
- `DISABLE` on an already disabled account returns a business failure in the gateway fields.
- `ROTATE` on a disabled account returns a business failure in the gateway fields.

## Integration Flow

1. Merchant ensures the customer is registered with Newton, has an active device binding, and has a linked UPI account.
2. Merchant selects the linked account using `bankAccountUniqueId` from account-listing/linking APIs.
3. For `ENABLE` or `ROTATE`, merchant app collects credential data from the UPI common library.
4. Merchant backend creates a unique `upiRequestId` and calls this API with the customer, device, account, action, and credential details.
5. Newton decrypts/verifies the S2S envelope, validates merchant configuration and request freshness, and loads the merchant customer profile.
6. Newton validates request fields, registered device fingerprint, linked account, optional VPA ownership, and biometric-consent state.
7. Newton sends the biometric activation request to NPCI and returns the NPCI/business result in `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton.
- `bankAccountUniqueId`: Account hash or migrated account identifier returned by account APIs.
- `upiRequestId`: Merchant-generated UPI request id for this bio-auth attempt. It is returned as `gatewayTransactionId`.
- `customerVpa`: Optional payer VPA. Send it when the credential flow is tied to a specific customer VPA.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/bioAuth
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within 30 minutes of Newton's clock. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Depending on the configured envelope, the request body can be plaintext, JWS, or JWE. Signed/encrypted calls must include a valid payload `iat`, and unsigned/plaintext S2S calls must include the configured merchant signature headers such as `x-merchant-signature`.

Newton responses are returned according to the merchant's configured response strategy. For plaintext response strategy, Newton returns an unsigned business body with `X-Response-Signature`. For JWS or JWS-and-JWE strategy, the business body is signed or signed and encrypted.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Request

### Required Minimum

For `ENABLE`, send the linked account, action, purpose, and a stringified `credBlock` containing both MPIN and biometric credentials:

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ENABLE",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BIOAUTH123456",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "purpose": "BR",
  "customerVpa": "customer@bank",
  "iat": "1735689600000",
  "clVersion": "2.0",
  "remarks": "Enable biometric auth",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"biocred\":{\"type\":\"BIOMETRIC\",\"subType\":\"BIOMETRIC\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

For `DISABLE`, `credBlock` can be omitted:

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DISABLE",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BIOAUTH123457",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "purpose": "BR",
  "customerVpa": "customer@bank",
  "iat": "1735689600000",
  "remarks": "Disable biometric auth"
}
```

For `ROTATE`, send biometric credentials:

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ROTATE",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BIOAUTH123458",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "purpose": "BR",
  "customerVpa": "customer@bank",
  "iat": "1735689600000",
  "clVersion": "2.0",
  "remarks": "Rotate biometric credential",
  "credBlock": "{\"biocred\":{\"type\":\"BIOMETRIC\",\"subType\":\"BIOMETRIC\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters and follow Newton merchant-customer-id format. |
| `action` | string | Yes | No default. | Bio-auth operation. Allowed values: `ENABLE`, `DISABLE`, `ROTATE`. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint returned or derived during device binding. Newton validates it against the customer's registered device. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this bio-auth attempt. Must be 1 to 35 alphanumeric characters. Returned as `gatewayTransactionId`. |
| `bankAccountUniqueId` | string | Yes | No default. | Linked account identifier/account hash returned by account APIs. Newton uses it to resolve the customer's account. |
| `purpose` | string | Yes | No default. | Bio-auth purpose. Only `BR` is accepted by validation and Newton sends `BR` to NPCI. |
| `customerVpa` | string | No | If omitted, Newton constructs the downstream payer VPA from the customer mobile number and the merchant/default VPA handle. | Customer VPA for the linked account. When supplied, Newton normalizes it by trimming and lowercasing, then verifies that it belongs to the customer and merchant customer profile. |
| `credBlock` | string | Conditional | Required for `ENABLE` and `ROTATE`. Not required for `DISABLE`. | Stringified JSON credential block generated by the UPI common library. `ENABLE` requires `mpincred` and `biocred`; `ROTATE` requires `biocred`; `DISABLE` does not send credentials downstream. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the success wrapper when supplied. |
| `iat` | string | Conditional | No default. | Issued-at timestamp in 13-digit epoch milliseconds. Required for signed/encrypted S2S requests because Newton validates it as part of request freshness. Plain-text test payloads do not require it. |
| `clVersion` | string | No | Omitted from the downstream NPCI request when not supplied. | UPI common-library version used for credential capture. Recommended when sending biometric credentials. |
| `remarks` | string | No | If omitted, the downstream NPCI request uses `BioAuth Activation` as the note. | Customer-facing or audit note for the bio-auth action. Must be 1 to 255 characters when supplied. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are simply not stored or returned when omitted.

- `credBlock`: Required by business validation for `ENABLE` and `ROTATE`. For `ENABLE`, the parsed credential data must contain both `mpincred` and `biocred`. For `ROTATE`, it must contain `biocred`. For `DISABLE`, omission is valid.
- `customerVpa`: If supplied, it must belong to the customer and merchant customer profile. If omitted, Newton derives the downstream payer VPA from customer mobile number plus the configured VPA handle.
- `iat`: Required by the signature middleware for signed/encrypted requests, even though the business request type is nullable. Missing `iat` returns an `INVALID_DATA` response.
- `clVersion`: Optional at this API layer. If omitted, Newton does not send a CL version in the NPCI bio-auth activation request.
- `remarks`: Omitted uses `BioAuth Activation` as the downstream note.
- `udfParameters`: Echoed on success only when supplied.

### Nested Request Objects

There are no nested JSON objects in the outer decrypted request body. `credBlock` is a JSON string whose parsed contents are generated by the UPI common library and should not be hand-built by the merchant backend.

For `ENABLE`, the parsed `credBlock` should include both `mpincred` and `biocred`:

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

For `ROTATE`, the parsed `credBlock` should include `biocred`:

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

`DISABLE` does not require credential data.

## Request Examples

### Enable Bio Auth

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ENABLE",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BIOAUTH123456",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "purpose": "BR",
  "customerVpa": "customer@bank",
  "iat": "1735689600000",
  "clVersion": "2.0",
  "remarks": "Enable biometric auth",
  "udfParameters": "{\"journey\":\"bioauth_enable\"}",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"biocred\":{\"type\":\"BIOMETRIC\",\"subType\":\"BIOMETRIC\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Disable Bio Auth

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DISABLE",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BIOAUTH123457",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "purpose": "BR",
  "customerVpa": "customer@bank",
  "iat": "1735689600000",
  "remarks": "Disable biometric auth"
}
```

### Rotate Bio Auth Credential

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ROTATE",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BIOAUTH123458",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "purpose": "BR",
  "customerVpa": "customer@bank",
  "iat": "1735689600000",
  "clVersion": "2.0",
  "remarks": "Rotate biometric credential",
  "credBlock": "{\"biocred\":{\"type\":\"BIOMETRIC\",\"subType\":\"BIOMETRIC\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Disable Without Explicit Customer VPA

Use this only when your integration is comfortable with Newton deriving the downstream payer VPA from the customer's mobile number and configured VPA handle.

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DISABLE",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "BIOAUTH123459",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "purpose": "BR",
  "iat": "1735689600000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API wrapper status. Success value is `SUCCESS` when Newton accepted the API request and produced a bio-auth result payload. |
| `responseCode` | string | Wrapper response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Wrapper response message. Success value is `SUCCESS`. |
| `payload` | object | Bio-auth action result, account details, and gateway/business status. |
| `udfParameters` | string | Echoed from request when supplied. |

The top-level wrapper can be `SUCCESS` even when the bio-auth action failed at NPCI or failed a biometric-consent state rule. Always use the gateway fields inside `payload` for the actual action result:

- `payload.gatewayResponseStatus`
- `payload.gatewayResponseCode`
- `payload.gatewayResponseMessage`

Treat the action as completed only when `payload.gatewayResponseCode` is `00` and `payload.gatewayResponseStatus` is `SUCCESS`. Treat `PENDING` as an indeterminate downstream result and do not assume the account is enabled or rotated until your reconciliation flow confirms the final state.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number associated with the merchant customer. |
| `bankAccountUniqueId` | string | Echoed linked-account identifier from the request. Valid S2S requests should always receive this value; the transformer only falls back to an empty string if the internal core response has no account id. |
| `bankCode` | string | Bank/IIN code for the resolved account. |
| `maskedAccountNumber` | string | Masked account number for display. |
| `gatewayTransactionId` | string | Same value as request `upiRequestId`. |
| `gatewayResponseStatus` | string | `SUCCESS`, `PENDING`, or `FAILURE` for the bio-auth action result. |
| `gatewayResponseCode` | string | NPCI/business result code. Success value is `00`; pending is `01`; bio-auth validation and NPCI codes are returned for failures. |
| `gatewayResponseMessage` | string | Human-readable message mapped from `gatewayResponseCode` or generated from the requested action. |

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
    "maskedAccountNumber": "XXXXXX1234",
    "gatewayTransactionId": "BIOAUTH123456",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your ENABLE action has been completed successfully"
  },
  "udfParameters": "{\"journey\":\"bioauth_enable\"}"
}
```

For `DISABLE` or `ROTATE`, the same response shape is returned and the success message includes the requested action.

### Example Pending Response

When NPCI returns pending code `01`, the wrapper is still `SUCCESS`, but the action result is pending:

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
    "gatewayTransactionId": "BIOAUTH123456",
    "gatewayResponseStatus": "PENDING",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your ENABLE action is in pending"
  }
}
```

### Example Business or Gateway Failure Response

When the request is accepted but the biometric action fails, the top-level wrapper remains `SUCCESS`; the gateway fields carry the failure.

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
    "gatewayTransactionId": "BIOAUTH123458",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "O2",
    "gatewayResponseMessage": "Biometric Setting failed"
  }
}
```

## Failure Responses

Failure responses use the same encrypted response transport as success responses. Failures can occur before the bio-auth product logic runs, during product validation, or after the downstream NPCI call. HTTP status can vary by layer; clients should read `status`, `responseCode`, and `responseMessage` from the decrypted body, and should read gateway fields when a `payload` is present.

### Authentication, Encryption, and Merchant Configuration

Missing or invalid S2S headers, signature mismatch, invalid IP allowlist, invalid merchant credentials, JWS verification failure, or JWE decryption failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Encrypted payload cannot be decrypted or cannot be authenticated by the configured key material:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Bio Auth API is disabled, blocked, or not present in the merchant's allowed API configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Signed/encrypted request is missing payload `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

`iat` or `x-timestamp` is not a 13-digit millisecond timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

`iat` or `x-timestamp` is outside the allowed clock-skew window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

### Request Validation Failures

Request body cannot be decoded as JSON or does not match the expected envelope/body type:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Request"
}
```

`merchantCustomerId` is empty or longer than 256 characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

`upiRequestId` contains unsupported characters or is longer than 35 characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\""
}
```

`deviceFingerPrint` is empty:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"deviceFingerPrint field is empty\""
}
```

`purpose` is not `BR`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed \\\"BH\\\"\""
}
```

`customerVpa` is malformed:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\""
}
```

`udfParameters` is not a valid JSON-object string or contains disallowed special characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

`ENABLE` or `ROTATE` is submitted without `credBlock`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "validateBioAuthRequest: credBlock required for ENABLE action"
}
```

`ENABLE` is submitted with a `credBlock` that does not contain both MPIN and biometric credentials:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Both MPIN and biometric credentials required for bioAuth ENABLE"
}
```

`ROTATE` is submitted with a `credBlock` that does not contain biometric credentials:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Biometric credential required for bioAuth ROTATE"
}
```

Submitted `deviceFingerPrint` does not match the registered device:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

### Customer, Account, and VPA Lookup Failures

Merchant customer profile cannot be found for `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Merchant customer has no active customer/device binding:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

`customerVpa` is supplied but does not belong to the customer and merchant customer profile:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Vpa not found"
}
```

Linked account cannot be resolved for `bankAccountUniqueId`. Depending on where the lookup fails, this can surface as an account-not-found response or an internal lookup failure:

```json
{
  "status": "FAILURE",
  "responseCode": "ACCOUNT_NOT_FOUND",
  "responseMessage": "Account not found"
}
```

or:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Bio Auth State and Downstream Failures

Some business and downstream failures return a `SUCCESS` wrapper with failed gateway fields. Clients must inspect `payload.gatewayResponseStatus` and `payload.gatewayResponseCode`.

`DISABLE` or `ROTATE` is called before bio-auth has been enabled for the account:

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
    "gatewayTransactionId": "BIOAUTH123457",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JPBNE",
    "gatewayResponseMessage": "BioAuth must be enabled first before performing this action"
  }
}
```

`DISABLE` is called when bio-auth is already disabled:

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
    "gatewayTransactionId": "BIOAUTH123457",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JPBAD",
    "gatewayResponseMessage": "BioAuth is already disabled for this account"
  }
}
```

`ROTATE` is called while bio-auth is disabled:

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
    "gatewayTransactionId": "BIOAUTH123458",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JPBRD",
    "gatewayResponseMessage": "Cannot rotate BioAuth credentials when BioAuth is disabled"
  }
}
```

NPCI reports that the customer is not eligible for biometric authentication:

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
    "gatewayTransactionId": "BIOAUTH123456",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "O1",
    "gatewayResponseMessage": "Customer not eligible for biometric authentication feature"
  }
}
```

NPCI or the issuer bank reports biometric setting failure or central blocking:

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
    "gatewayTransactionId": "BIOAUTH123456",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "O4",
    "gatewayResponseMessage": "Biometric service disabled - Central blocking by the issuer bank"
  }
}
```

For configured biometric disable error codes such as `O2` or `O4`, Newton may also mark local biometric consent disabled with reason `NPCI_ERROR`.

Downstream timeout or an unmapped NPCI error code can be returned as a gateway failure:

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
    "gatewayTransactionId": "BIOAUTH123456",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U09",
    "gatewayResponseMessage": "BioAuth operation failed"
  }
}
```

Unexpected server, database, encryption, downstream decode, or cache failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Idempotency

This API does not take a separate merchant idempotency key. Treat `upiRequestId` as the unique operation identifier for each bio-auth attempt.

- Generate a new `upiRequestId` for each new enable, disable, or rotate attempt.
- Do not infer action success from top-level `status`. Use `payload.gatewayResponseCode == "00"` and `payload.gatewayResponseStatus == "SUCCESS"`.
- For `PENDING`, hold the customer journey in a pending state or reconcile through your agreed account/profile refresh flow before showing biometric auth as enabled or rotated.
- For validation, authentication, merchant-configuration, device, VPA, or account lookup failures, correct the request or configuration before retrying.
- For gateway/downstream failures, retry only after backoff and customer re-authorization where credentials are involved. For `ENABLE` and `ROTATE`, collect fresh credential material if the previous common-library credential block is no longer valid.
- Repeated `DISABLE` after the account is already disabled returns a business failure (`JPBAD`), not an idempotent success.
- Repeated `ENABLE` is not documented as an idempotent no-op; it can initiate another downstream bio-auth activation attempt.

## Source References

- Route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:190)
- Route handler, request decryption, signature flow, monitoring, and customer cache invalidation: [bioAuthActivationS2S](../../src/Newton/App/Routes/Core.hs:1774)
- S2S transformer route: [bioAuthActivationS2STransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:806)
- S2S request and response types and validators: [BioAuthActivationS2SRequest](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:5044)
- S2S core request/response transformers: [mkBioAuthActivationS2SCoreRequest](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1675)
- Product flow, account/customer/device lookup, state validation, and NPCI call: [Newton.Product.Merchant.Account.BioAuth](../../src/Newton/Product/Merchant/Account/BioAuth.hs:33)
- Core request/response and action types: [Newton.Product.Merchant.Account.Types](../../src/Newton/Product/Merchant/Account/Types.hs:194)
- Bio-auth response builder and consent updates: [Newton.Product.Merchant.Account.Helper](../../src/Newton/Product/Merchant/Account/Helper.hs:492)
- NPCI `ReqActivation` payload and credential mapping: [getBioAuthActivationPayload](../../src/Newton/Utils/NpciTransformer.hs:1447)
- Bio-auth credential parsing and validation errors: [getCredBlockforBioAuth](../../src/Newton/Utils/Transformers/Transformer.hs:2225)
- Biometric consent storage helper: [BiometricConsent middleware](../../src/Newton/Storage/QueriesMiddleware/BiometricConsent.hs:18)
- Biometric consent table and disabled reasons: [BiometricConsent storage type](../../src/Newton/Types/Storage/BiometricConsent.hs:25)
- Common request validators: [Common.hs](../../src/Newton/Validation/Common.hs:137)
- Merchant signature, API enablement, timestamp, and IP allowlist checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request/response envelope and response signing/encryption: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48), [flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:38)
- API error response constants and bio-auth code mappings: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:1114)
