# Change MPIN API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/changeMpin`

## Overview

Change MPIN is a server-to-server API used to change the UPI MPIN for a customer's already linked bank account.

The merchant calls this API after the customer has completed device binding and account linking, and after the merchant app has collected the UPI common-library credential block for the current MPIN and the new MPIN. Newton validates the S2S envelope, merchant/customer context, linked account, VPA ownership, device fingerprint, and credential payload, then sends an account update request to the bank/NPCI path with update type `change`.

Use this API when the customer knows their existing MPIN and wants to change it. Do not use it for first-time MPIN setup, forgot-MPIN, OTP/card-based reset, or account linking flows.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

## Business Use Case

Change MPIN helps merchants:

- Let a registered customer change the UPI MPIN for a linked bank account from the merchant app.
- Keep the MPIN change tied to a known Newton merchant customer, linked account, customer VPA, device binding, and UPI request id.
- Verify that the request came from the customer's registered device, with optional fallback fingerprint support during device-fingerprint migration.
- Surface the actual bank/NPCI outcome through gateway response fields while keeping Newton's API wrapper response consistent.
- Reconcile customer support and audit trails using `upiRequestId`, returned as `gatewayTransactionId`.

## Integration Flow

1. Merchant ensures the customer is registered with Newton, device-bound, and has the target account linked to the customer VPA.
2. Merchant app initiates the UPI common-library change-MPIN flow and collects a `credBlock` containing both current MPIN and new MPIN credentials.
3. Merchant backend creates a unique `upiRequestId` for this MPIN-change attempt.
4. Merchant backend calls `changeMpin` using the configured encrypted/signed S2S envelope.
5. Newton decrypts/verifies the request, validates the merchant signature and request freshness, and loads the merchant customer/customer context.
6. Newton validates the request body, resolves the linked account, verifies `customerVpa`, validates the submitted device fingerprint, and calls the downstream account-update path.
7. Merchant decrypts the response and reads `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` to determine whether the MPIN was changed.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton.
- `customerVpa`: Customer VPA that must belong to the merchant customer and linked account context.
- `bankAccountUniqueId`: Merchant-facing linked account identifier/account hash returned by account APIs.
- `accountReferenceId`: Newton account reference id returned by account APIs, or a migrated-account reference in specific GPay ICICI flows.
- `upiRequestId`: Merchant-generated UPI request id for this MPIN-change attempt. Returned as `gatewayTransactionId`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/changeMpin
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding, when required by the configured envelope. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding, when required by the configured envelope. |
| `x-timestamp` | 13-digit epoch milliseconds, when required by the configured signature process. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Production integrations should send the configured encrypted and/or signed request envelope. Plain JSON examples in this guide are decrypted business payloads only.

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
  "upiRequestId": "CMPIN123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"newcred\":{\"type\":\"PIN\",\"subType\":\"NMPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

If your integration uses `accountReferenceId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "CMPIN123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"newcred\":{\"type\":\"PIN\",\"subType\":\"NMPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

For migrated-account flows where `accountReferenceId` is not a Newton account reference id, also send `ifsc`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "CMPIN123456791",
  "iat": "1735689600000",
  "accountReferenceId": "MIGRATED_ACCOUNT_ID",
  "ifsc": "EXAM0001234",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"newcred\":{\"type\":\"PIN\",\"subType\":\"NMPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters and follow Newton merchant-customer-id format. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint returned/derived during device binding. Newton validates it against the customer's registered device. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate fingerprint accepted during device matching, typically used during device-fingerprint migration or fallback flows. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this MPIN-change attempt. Must be 1 to 35 alphanumeric characters. Returned as `gatewayTransactionId`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp in 13-digit epoch milliseconds. Required for signed/encrypted S2S requests because Newton validates it as part of request freshness. Plain-text test payloads do not require it unless configured. |
| `bankAccountUniqueId` | string | Recommended | No default. | Linked account identifier/account hash returned by account APIs. Send this or `accountReferenceId` for new integrations. If account-id migration is enabled, Newton resolves the value before account lookup and returns the merchant-facing account id in the response. |
| `accountReferenceId` | string | Recommended | No default. | Newton account reference id returned by account APIs. Send this or `bankAccountUniqueId` for new integrations. In specific migrated GPay ICICI flows, this can carry a migrated account id and must be paired with `ifsc`. |
| `ifsc` | string | Conditional | No default. | Required for specific migrated-account flows where `accountReferenceId` represents a migrated account id instead of a Newton account reference id. |
| `customerVpa` | string | Yes | No default. | Customer VPA for the linked account. Newton verifies that this VPA belongs to the merchant customer/customer context. |
| `credBlock` | string | Yes | No default. | JSON string containing UPI credential data generated by the UPI common-library change-MPIN flow. Must include `mpincred` for the current MPIN and `newcred` for the new MPIN. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the success response. |
| `clVersion` | string | No | No default. | Common-library version associated with credential capture, when available. Passed to the downstream account-update path. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `bankAccountUniqueId` and `accountReferenceId`: at least one is recommended for new integrations. Some non-P2M flows can derive the primary account from `customerVpa` when both identifiers are omitted, but P2M SDK enabled merchants require one of these identifiers.
- `accountReferenceId` and `ifsc`: for GPay ICICI migrated-account flows, `accountReferenceId` is mandatory and `ifsc` is mandatory when the reference is a migrated account id rather than a Newton account id.
- `fallbackDeviceFingerPrint`: omitted means only `deviceFingerPrint` is checked.
- `iat`: required by the S2S signature/encryption layer for signed production requests, even though the business request type is nullable.
- `udfParameters`: echoed only on success when supplied.
- `clVersion`: omitted means Newton sends no common-library version in the downstream account-update request.

### Nested Request Objects

`credBlock` is sent as a JSON string. Its contents are generated by the UPI common library/credential capture flow and should not be manually constructed by the merchant backend.

For Change MPIN, the parsed object must include both `mpincred` and `newcred`:

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
  "newcred": {
    "type": "PIN",
    "subType": "NMPIN",
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

- `merchantCustomerId` must be 1 to 256 characters. The first character must be a letter, number, plus, slash, or equals sign. Subsequent characters may also include dot, underscore, and hyphen.
- `deviceFingerPrint`, `customerVpa`, `credBlock`, and optional account/reference fields must be non-empty when supplied.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `udfParameters` must be a JSON object encoded as a string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick.
- Newton validates the submitted `deviceFingerPrint` against the registered device fingerprint, with `fallbackDeviceFingerPrint` accepted as an alternate when supplied.
- Newton validates that `customerVpa` exists and belongs to the merchant customer/customer context.
- Newton parses `credBlock` as a credential JSON string and requires `mpincred` and `newcred`. Malformed or incomplete credential blocks are rejected before a successful MPIN-change response is produced.

## Request Examples

### Change MPIN With Account Unique Id

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "fallbackDeviceFingerPrint": "a31c2d9e8b...",
  "upiRequestId": "CMPIN123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\",\"hmac\":\"...\"}},\"newcred\":{\"type\":\"PIN\",\"subType\":\"NMPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\",\"hmac\":\"...\"}}}",
  "clVersion": "2.0",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Change MPIN With Account Reference Id

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "CMPIN123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"newcred\":{\"type\":\"PIN\",\"subType\":\"NMPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Migrated Account Reference With IFSC

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "CMPIN123456791",
  "iat": "1735689600000",
  "accountReferenceId": "MIGRATED_ACCOUNT_ID",
  "ifsc": "EXAM0001234",
  "customerVpa": "customer@bank",
  "credBlock": "{\"mpincred\":{\"type\":\"PIN\",\"subType\":\"MPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}},\"newcred\":{\"type\":\"PIN\",\"subType\":\"NMPIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API wrapper status. Success value is `SUCCESS`. |
| `responseCode` | string | Wrapper response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Wrapper response message. Success value is `SUCCESS`. |
| `payload` | object | Change-MPIN result and account details. Present on success wrapper responses. |
| `udfParameters` | string | Echoed from request when supplied. |

The top-level `status` can be `SUCCESS` even when the bank/NPCI MPIN change failed. Always use the gateway fields inside `payload` for the actual MPIN-change result:

- `payload.gatewayResponseStatus`
- `payload.gatewayResponseCode`
- `payload.gatewayResponseMessage`

Treat the MPIN as changed only when `payload.gatewayResponseStatus` is `SUCCESS` and `payload.gatewayResponseCode` is `00`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id for the customer whose MPIN-change request was processed. |
| `customerMobileNumber` | string | Customer mobile number from the Newton customer profile. |
| `bankAccountUniqueId` | string | Merchant-facing linked account identifier returned for the resolved account. |
| `bankCode` | string | Bank code/IIN for the linked account. |
| `customerVpa` | string | Customer VPA from the request. |
| `maskedAccountNumber` | string | Masked linked account number. |
| `gatewayTransactionId` | string | Same value as request `upiRequestId`. Use it for reconciliation and support. |
| `gatewayResponseStatus` | string | `SUCCESS` when gateway response code is `00`; otherwise `FAILURE`. |
| `gatewayResponseCode` | string | Bank/NPCI response code. `00` means the MPIN change succeeded. Other codes are business or technical failures from the gateway path. |
| `gatewayResponseMessage` | string | Newton's mapped message for the gateway response code. If no error code is returned, success defaults to `Change mpin is successful`. |

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
    "gatewayTransactionId": "CMPIN123456789",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your transaction is successful"
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Gateway Business Failure Response

For gateway business failures, the wrapper can still be successful because Newton completed request processing and received a bank/NPCI result. In this case, the MPIN was not changed.

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
    "gatewayTransactionId": "CMPIN123456789",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "ZM",
    "gatewayResponseMessage": "UPI PIN entered for the transaction was incorrect"
  }
}
```

Other possible gateway failure codes depend on the bank/NPCI response. For example, `RM` maps to invalid MPIN policy while setting/changing MPIN. Clients should display a user-safe failure message and let the customer retry through a fresh credential-capture flow where appropriate.

## Error Handling

Failure responses use the same configured S2S response transport as success responses. HTTP status can vary by layer. Validation and some business errors are returned with an encrypted error body; device fingerprint mismatch uses an HTTP 400 path; authentication failures use an HTTP 401 path. Clients should inspect the decrypted `status`, `responseCode`, and `responseMessage` whenever a response body is available.

### Validation Failure

Occurs when the decrypted business payload fails Newton validation, such as empty `credBlock`, invalid `merchantCustomerId`, invalid `upiRequestId`, or malformed `udfParameters`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"credBlock field is empty\"",
  "payload": null
}
```

Client handling: fix the payload and retry only after regenerating the S2S signature/envelope. If the request already reached credential capture, prefer creating a fresh `upiRequestId`.

### Authentication, Signature, or Encryption Failure

Occurs when the S2S envelope cannot be verified, the request is signed with the wrong key, the merchant/customer context does not match the verified key/session, or request freshness checks fail.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

Checksum/signature mismatch responses can also use:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_CHECKSUM",
  "responseMessage": "Checksum mismatch",
  "payload": null
}
```

Client handling: do not ask the customer to re-enter MPIN until the server-side auth issue is fixed. Regenerate `iat`, timestamp, signature, and encrypted payload before retrying.

### Merchant Configuration or Context Failure

Occurs when the merchant/customer context loaded by the verification layer is not allowed for the request, for example a package-name/OS combination blocked by merchant configuration, a key profile mismatch, or a missing merchant customer/device context.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED",
  "payload": null
}
```

If the customer profile exists but the registered device id is missing, the error may be returned as invalid data:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid DeviceId cannot be null for merchantCustomer",
  "payload": null
}
```

Client handling: treat this as an integration/configuration or customer-registration issue. Re-run device binding or contact Newton support depending on the cause.

### Account or VPA Lookup Failure

Occurs when Newton cannot resolve the linked account or the customer VPA under the merchant customer context.

Missing account identifiers in flows that require them:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory",
  "payload": null
}
```

Unknown or inactive account:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found",
  "payload": null
}
```

Unknown or mismatched VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Vpa not found",
  "payload": null
}
```

Client handling: refresh the customer's linked account/VPA list before retrying. Do not continue with stale account identifiers.

### Device Fingerprint Mismatch

Occurs when neither `deviceFingerPrint` nor `fallbackDeviceFingerPrint` matches the registered device fingerprint.

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH",
  "payload": null
}
```

Client handling: re-run device binding or use the correct registered device fingerprint. Do not retry the same credential block repeatedly.

### Credential Block Parsing or Missing Credentials

Occurs when `credBlock` is not valid JSON for Newton's credential block type, or when required `mpincred`/`newcred` values are absent. The current implementation maps these credential-shape failures to an internal error response.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR",
  "payload": null
}
```

Client handling: collect a fresh change-MPIN credential block from the UPI common library. Verify that the escaped string contains both `mpincred` and `newcred` before sending.

### Downstream Timeout or Unreachable Service

Occurs when the downstream bank/NPCI account-update path times out. Newton returns a failure wrapper instead of a success payload when the timeout is identified before a gateway business result can be returned.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U20",
  "responseMessage": "NPCI service is not reachable at the moment (U20)",
  "payload": null
}
```

Client handling: outcome may be unknown if the request reached the bank/NPCI path. Do not assume the MPIN changed. Reconcile using `upiRequestId` if needed and ask the customer to retry later with a fresh credential-capture flow.

### Bad Downstream Response

Occurs when the downstream path reports an error but does not provide an error code that Newton can map.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI",
  "payload": null
}
```

Client handling: treat as a technical failure. Do not show success to the customer. Retry later with a fresh `upiRequestId` and credential block if the customer still wants to change the MPIN.

## Retry, Idempotency, and Client Handling

- Generate a unique `upiRequestId` for each customer-initiated Change MPIN attempt. Newton returns the same value as `gatewayTransactionId`.
- This API does not create a merchant-side idempotency record for the MPIN change. Do not rely on automatic duplicate suppression.
- If the response contains `payload.gatewayResponseStatus = "SUCCESS"` and `payload.gatewayResponseCode = "00"`, treat the MPIN as changed.
- If the response contains top-level `SUCCESS` but `payload.gatewayResponseStatus = "FAILURE"`, treat the MPIN as not changed. For customer-entered or policy failures such as `ZM` or `RM`, let the customer initiate a new change-MPIN attempt instead of retrying the same credential block.
- If the call fails before a decrypted response is available, or returns `SERVICE_UNAVAILABLE_*`/`BAD_RESPONSE_FROM_NPCI`, the final bank outcome may be unknown. Use `upiRequestId` for support/reconciliation and prefer a fresh credential-capture flow for any new attempt.
- For validation, authentication, encryption, or configuration failures, fix the integration issue and regenerate the encrypted/signed request. A stale `iat` or signature should not be replayed.
- UPI credential blocks can be time-bound and single-use from the client-library perspective. Do not repeatedly replay the same `credBlock`.

## Source References

- S2S route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:274)
- S2S route handler and middleware chain: [Core.hs](../../src/Newton/App/Routes/Core.hs:1925)
- Request/response envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- Request, response, and request validation types: [Account.hs](../../src/Newton/Types/API/ServerToServer/Account.hs:58)
- Request body validation error behavior: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Common validators for non-empty fields, UDF, merchant customer id, and UPI request id: [Common.hs](../../src/Newton/Validation/Common.hs:168)
- S2S payload/envelope verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature/timestamp verification: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Merchant/customer context checks in auth middleware: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:740)
- Change MPIN product flow: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:839)
- Device fingerprint validation: [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Account/VPA mapping lookup: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:133)
- Account lookup behavior and migrated-account conditions: [DB.hs](../../src/Newton/Utils/DB.hs:540)
- Account-id migration helper: [Utils.hs](../../src/Newton/Utils/Utils.hs:5524)
- Credential block shape: [CredBlock.hs](../../src/Newton/Types/API/CredBlock.hs:47)
- Downstream Change MPIN wrapper and credential extraction: [MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:2383)
- Downstream response validation: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:866)
- S2S response transformer: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2264)
- Error response helpers and constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:15)
- Gateway response code mapping: [ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:19)
