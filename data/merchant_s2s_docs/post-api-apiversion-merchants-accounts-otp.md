# Generate OTP API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/otp`

## Overview

Generate OTP is a server-to-server API used to trigger the bank/NPCI OTP required for setting or resetting a customer's UPI MPIN on a linked bank account.

The merchant calls this API after the customer is registered, device-bound, and has a bank account available in Newton. Newton verifies the encrypted/signed S2S request, merchant/customer context, linked account, optional VPA, registered device fingerprint, and OTP request variant, then sends a `ReqOtp` request to the downstream bank/NPCI path.

Use this API when the customer is about to set or reset MPIN and needs the bank-issued OTP. Do not use it for changing an existing MPIN when the customer already knows the current MPIN; use Change MPIN for that flow.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Generate OTP helps merchants:

- Trigger the OTP that the customer's bank sends for first-time MPIN setup or MPIN reset.
- Keep the OTP request tied to a known Newton merchant customer, registered device, linked bank account, and UPI request id.
- Support card/expiry-based OTP request flows where the bank requires debit-card details.
- Support common-library card-detail credential flows through `credBlock`.
- Support Aadhaar OTP variants for enabled onboarding/reset journeys, including bank-only, UIDAI-only, and bank-plus-UIDAI OTP request modes.
- Surface the actual bank/NPCI result through gateway response fields while returning a consistent Newton S2S response envelope.
- Reconcile customer support and audit trails using `upiRequestId`, returned as `gatewayTransactionId`.

## Integration Flow

1. Merchant ensures the customer is registered with Newton, device-bound, and has the target account available from account discovery/linking APIs.
2. Merchant app starts the UPI common-library set/reset MPIN flow and determines the bank-required OTP mode.
3. Merchant backend creates a unique `upiRequestId` for this OTP attempt.
4. Merchant backend calls Generate OTP using the configured encrypted/signed S2S envelope.
5. Newton decrypts/verifies the envelope, validates merchant signature and request freshness, and loads the merchant customer/customer context.
6. Newton validates the request body, resolves the linked account, optionally verifies the customer VPA, verifies the device fingerprint, validates Aadhaar OTP parameters when present, and calls the downstream OTP path.
7. Merchant decrypts the response and reads `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` to decide whether the customer can continue to Set MPIN.
8. If OTP generation succeeded, the customer enters or the common library auto-reads the OTP and the merchant proceeds with the Set MPIN API.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton.
- `bankAccountUniqueId`: Merchant-facing linked account identifier/account hash returned by account APIs.
- `accountReferenceId`: Newton account reference id returned by account APIs, or a migrated-account reference in specific GPay ICICI flows.
- `customerVpa`: Optional customer VPA used to verify VPA ownership when supplied.
- `upiRequestId`: Merchant-generated UPI request id for this OTP attempt. Returned as `gatewayTransactionId`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/otp
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, when required by the configured signature process. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding. Required for signed/encrypted production traffic. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. Production integrations should send the configured encrypted and/or signed request envelope. Plain JSON examples in this guide are decrypted business payloads only.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the version shared during onboarding. |

## Request

### Required Minimum

For new integrations, identify the linked account with `bankAccountUniqueId` or `accountReferenceId`.

Using `bankAccountUniqueId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "OTP123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID"
}
```

Using `accountReferenceId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "OTP123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123"
}
```

For card/expiry based banks, send the last six card digits and expiry:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "registered-device-fingerprint",
  "upiRequestId": "OTP123456791",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "card": "123456",
  "expiry": "1228"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters and follow Newton merchant-customer-id format. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint returned/derived during device binding. Newton validates it against the customer's registered device. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate fingerprint accepted during device matching, typically used during device-fingerprint migration or fallback flows. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this OTP attempt. Must be 1 to 35 alphanumeric characters. Returned as `gatewayTransactionId`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by S2S signature verification and request freshness checks. Required for signed/encrypted production requests, even though the business type is nullable. |
| `bankAccountUniqueId` | string | Conditional | No default. | Linked account identifier/account hash returned by account APIs. Send this or `accountReferenceId` for new integrations. If account-id migration is enabled, Newton resolves the value before account lookup and returns the merchant-facing account id in the response. |
| `accountReferenceId` | string | Conditional | No default. | Newton account reference id returned by account APIs. Send this or `bankAccountUniqueId` for new integrations. In specific migrated GPay ICICI flows, this can carry a migrated account id and should be paired with `ifsc`. |
| `ifsc` | string | Conditional | No default. | Used with account lookup in migrated-account flows where `accountReferenceId` is not enough to identify the account. |
| `customerVpa` | string | No | If omitted, Newton resolves the account without VPA validation. | Customer VPA to validate against the customer/account context. Send when the OTP request is tied to a specific VPA. |
| `card` | string | Conditional | No default. | Last six digits of the debit card used by banks that require card details for OTP generation. Must be exactly 6 numeric digits when supplied. Pair with `expiry`. |
| `expiry` | string | Conditional | No default. | Card expiry in `MMYY` form for card/expiry based OTP requests. Must be exactly 4 numeric digits when supplied. Pair with `card`. |
| `otpRequestType` | string enum | No | If omitted, Newton sends the normal bank OTP request. | OTP request variant. Allowed values: `BANK`, `UIDAI`, `BANK-UIDAI`. `BANK` performs a bank OTP request. `UIDAI` and `BANK-UIDAI` require `aadhaarNo`. Any supplied non-`BANK` Aadhaar variant also writes Aadhaar OTP credential metadata for downstream Set MPIN. |
| `aadhaarNo` | string | Conditional | No default. | First six digits of Aadhaar for Aadhaar OTP flows. Required when `otpRequestType` is `UIDAI` or `BANK-UIDAI`. Must be exactly 6 numeric digits and match the Aadhaar value Newton cached during the Aadhaar setup flow. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant-defined metadata. Echoed back in the success response. |
| `credBlock` | string | Conditional | No default. | JSON string containing common-library card-detail credentials. Use this instead of plain `card`/`expiry` when the common library returns card details as an encrypted credential block. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `bankAccountUniqueId` and `accountReferenceId`: send at least one for P2M SDK/new integrations. In some non-P2M flows Newton can derive the primary account from `customerVpa` when both identifiers are omitted, but relying on that fallback makes the request less explicit.
- `customerVpa`: optional for this API. When supplied, Newton validates that the VPA exists and belongs to the customer/merchant-customer context.
- `fallbackDeviceFingerPrint`: omitted means only `deviceFingerPrint` is checked.
- `card` and `expiry`: omitted means Newton does not send `FORMAT2` card registration details. If the customer's bank requires card details, OTP generation can fail downstream.
- `credBlock`: omitted means Newton does not send common-library card-detail credentials. Do not send both `card`/`expiry` and card details inside `credBlock`; the downstream transformer treats that as an internal inconsistency.
- `otpRequestType`: omitted means normal bank OTP behavior. If either `aadhaarNo` or an Aadhaar `otpRequestType` is supplied, Newton applies Aadhaar validation rules.
- `iat`: required by the S2S signature/encryption layer for signed production requests.
- `udfParameters`: echoed only on success when supplied.

### OTP Request Variants

| Variant | Request fields | Downstream behavior |
| --- | --- | --- |
| Normal bank OTP | No `otpRequestType`; account id fields; optional `customerVpa` | Sends a normal `ReqOtp` for bank OTP. |
| Card/expiry OTP | `card` and `expiry` | Sends registration details with mobile number, last-six card digits, and expiry. |
| Common-library card credential OTP | `credBlock` containing `carddetailscred` | Sends card details as NPCI credential data with `ATM_REDIRECT` registration details. |
| Bank-only explicit OTP | `otpRequestType: "BANK"` | Sends `ReqOtp` subtype `BANK`. Does not require `aadhaarNo`. |
| UIDAI Aadhaar OTP | `otpRequestType: "UIDAI"` and `aadhaarNo` | Validates cached Aadhaar digits, writes Aadhaar OTP credential metadata, and sends Aadhaar OTP request. |
| Bank plus UIDAI Aadhaar OTP | `otpRequestType: "BANK-UIDAI"` and `aadhaarNo` | Validates cached Aadhaar digits, writes Aadhaar OTP credential metadata, and requests both bank/UIDAI mode where supported. |

### Nested Request Objects

`credBlock` is sent as a JSON string. Its contents are generated by the UPI common library/credential capture flow and should not be manually constructed by the merchant backend.

For this API, Newton reads `carddetailscred` from the parsed credential block:

```json
{
  "carddetailscred": {
    "type": "CARD",
    "subType": "CARDDETAILS",
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

The actual decrypted request still carries `credBlock` as an escaped JSON string:

```json
{
  "credBlock": "{\"carddetailscred\":{\"type\":\"CARD\",\"subType\":\"CARDDETAILS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\"}}}"
}
```

### Validation Notes

- `merchantCustomerId` must be 1 to 256 characters. The first character must be a letter, number, plus, slash, or equals sign. Subsequent characters may also include dot, underscore, and hyphen.
- `deviceFingerPrint`, optional account/reference fields, optional `ifsc`, and optional `credBlock` must be non-empty when supplied.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `customerVpa`, when supplied, must be 3 to 255 characters and match `local@handle` format.
- `card`, when supplied, must be exactly 6 numeric digits.
- `expiry`, when supplied, must be exactly 4 numeric digits.
- `otpRequestType`, when supplied, must be one of `BANK`, `UIDAI`, or `BANK-UIDAI`.
- `aadhaarNo`, when supplied, must be exactly 6 numeric digits.
- `udfParameters` must be a JSON object encoded as a string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick.
- Newton validates the submitted `deviceFingerPrint` against the registered device fingerprint, with `fallbackDeviceFingerPrint` accepted as an alternate when supplied.
- For Aadhaar OTP, `aadhaarNo` and `otpRequestType` must be supplied together unless `otpRequestType` is `BANK`. Newton validates the supplied Aadhaar digits against the value cached during the Aadhaar flow and can block the user after repeated wrong attempts.

## Request Examples

### Normal Bank OTP

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "fallbackDeviceFingerPrint": "a31c2d9e8b...",
  "upiRequestId": "OTP123456789",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### OTP With Account Reference Id

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "OTP123456790",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "customer@bank"
}
```

### Card / Expiry OTP

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "OTP123456791",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "card": "123456",
  "expiry": "1228"
}
```

### Common-Library Card Credential OTP

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "OTP123456792",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "credBlock": "{\"carddetailscred\":{\"type\":\"CARD\",\"subType\":\"CARDDETAILS\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"...\",\"ki\":\"...\",\"hmac\":\"...\"}}}"
}
```

### Aadhaar UIDAI OTP

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "OTP123456793",
  "iat": "1735689600000",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "customer@bank",
  "otpRequestType": "UIDAI",
  "aadhaarNo": "123456"
}
```

### Explicit Bank OTP Subtype

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "f5d1c4c7d3...",
  "upiRequestId": "OTP123456794",
  "iat": "1735689600000",
  "accountReferenceId": "ACCOUNT_REF_123",
  "otpRequestType": "BANK"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton API wrapper status. Successful route completion returns `SUCCESS`, even if the bank/NPCI OTP result inside `payload` is a failure. |
| `responseCode` | string | Newton wrapper response code. Successful route completion returns `SUCCESS`. |
| `responseMessage` | string | Newton wrapper response message. Successful route completion returns `SUCCESS`. |
| `payload` | object | Generate OTP result and bank/NPCI outcome. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when request omitted it. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id for the integration. |
| `merchantChannelId` | string | Merchant channel id for the integration. |
| `merchantCustomerId` | string | Merchant customer id for the customer. |
| `customerMobileNumber` | string | Customer mobile number associated with the Newton customer profile. |
| `bankAccountUniqueId` | string | Merchant-facing account id. For migrated-account deployments, Newton returns the migrated id when applicable; otherwise it returns the account hash. |
| `bankCode` | string | Bank IIN/code for the linked account. |
| `customerVpa` | string | Echoed only when supplied in the request. Omitted otherwise. |
| `mobRegFormat` | string | Mobile registration/credential format to use in the next common-library step. Usually `FORMAT1`, `FORMAT2`, or `FORMAT3`; Aadhaar flows prefer `FORMAT3` when the bank supports it. |
| `mpinLength` | string | MPIN length expected for the account/bank. |
| `otpLength` | string | OTP length expected for the account/bank. Defaults to `6` when account credential metadata does not specify it. |
| `atmPinLength` | string | ATM PIN/card PIN length expected for the account/bank. Defaults to `4` when account credential metadata does not specify it. |
| `maskedAccountNumber` | string | Masked account number for display/reconciliation. |
| `gatewayTransactionId` | string | Echo of request `upiRequestId`. Use this to correlate the OTP attempt and the subsequent Set MPIN call. |
| `gatewayResponseCode` | string | Gateway/NPCI code derived from downstream result. `00` means downstream success; missing codes are normalized to `JP91`; any other code indicates downstream/business failure. |
| `gatewayResponseStatus` | string | Downstream OTP generation status. `SUCCESS` means OTP generation succeeded. Values such as `FAILURE`, `Immediate Failure`, or `TimeOut` mean the customer should not proceed as if OTP was generated. |
| `gatewayResponseMessage` | string | Human-readable downstream result. Defaults to `Generate otp failed` when no downstream message is available. |
| `uidaiErrorCode` | string | UIDAI error code when returned for Aadhaar OTP failures. Omitted otherwise. |

### Success Response Example: OTP Generated

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
    "mobRegFormat": "FORMAT2",
    "mpinLength": "4",
    "otpLength": "6",
    "atmPinLength": "4",
    "maskedAccountNumber": "XXXXXX1234",
    "gatewayTransactionId": "OTP123456789",
    "gatewayResponseCode": "00",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseMessage": "OTP generation successful"
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Success Response Example: Downstream Rejected OTP

Newton can return wrapper `SUCCESS` because the API call completed, while the bank/NPCI result is a business failure. In this case, do not continue to Set MPIN until the customer retries and receives a successful OTP result.

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
    "mobRegFormat": "FORMAT2",
    "mpinLength": "4",
    "otpLength": "6",
    "atmPinLength": "4",
    "maskedAccountNumber": "XXXXXX1234",
    "gatewayTransactionId": "OTP123456795",
    "gatewayResponseCode": "U30",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseMessage": "Invalid request"
  }
}
```

### Aadhaar Failure Response Example

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
    "mobRegFormat": "FORMAT3",
    "mpinLength": "4",
    "otpLength": "6",
    "atmPinLength": "4",
    "maskedAccountNumber": "XXXXXX1234",
    "gatewayTransactionId": "OTP123456793",
    "gatewayResponseCode": "400",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseMessage": "'OTP' VALIDATION FAILED",
    "uidaiErrorCode": "400"
  }
}
```

## Error Handling

Failures use the same S2S response transport as success responses. Depending on where the failure occurs, the decrypted response can be an error body instead of `GenerateOtpResponse`, and some legacy/business validations are returned with HTTP `200` plus `status: "FAILURE"`.

Error bodies include `status`, `responseCode`, and `responseMessage`; examples below show the concrete validation, authentication, and downstream values clients should handle.

### Validation Failure

Request-body validation failures are returned as `BAD_REQUEST` with a validation summary.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\", ExactLengthValidation \"card field should be of length 6\""
}
```

Common causes:

- Missing or invalid `merchantCustomerId`.
- Empty `deviceFingerPrint`.
- Non-alphanumeric or longer-than-35 `upiRequestId`.
- Invalid `customerVpa` format.
- `card` not exactly 6 digits.
- `expiry` not exactly 4 digits.
- `otpRequestType` outside `BANK`, `UIDAI`, `BANK-UIDAI`.
- `aadhaarNo` not exactly 6 digits.
- `udfParameters` is not a JSON object string.

### Authentication, Signature, or Encryption Failure

If the envelope cannot be decrypted, the JWS signature fails, required merchant headers are missing, or merchant checksum/signature verification fails, Newton returns an auth error.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

or:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Client handling:

- Do not retry with the same payload unchanged.
- Verify `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, `x-merchant-signature`, key id, encryption/signing keys, and raw body used for signing.
- Ensure decrypted business payload `iat`, when required by onboarding, is current and matches the signed request freshness rules.

### Merchant Configuration or API Access Failure

The route checks merchant configuration before product logic. If the API is blocked or not enabled for the merchant/sub-merchant, the call fails before OTP generation.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling:

- Confirm the merchant is onboarded for Generate OTP S2S and the correct channel id is used.
- If using sub-merchant headers, confirm the sub-merchant is configured for this API.

### Device Fingerprint Mismatch

Newton validates the supplied fingerprint against the registered device fingerprint. If neither `deviceFingerPrint` nor `fallbackDeviceFingerPrint` matches, the request is rejected.

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

Client handling:

- Do not proceed to Set MPIN.
- Re-run or repair device binding before retrying.
- Use `fallbackDeviceFingerPrint` only for planned fingerprint migration/fallback flows.

### Account or VPA Lookup Failure

If Newton cannot resolve the target account or the supplied VPA does not belong to the customer context, the route fails before calling NPCI.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "bankAccountUniqueId is invalid"
}
```

Other possible messages include `AccountReferenceId is invalid`, `Invalid merchantCustomerId`, or VPA lookup/ownership errors.

Client handling:

- Refresh the customer's account list and use the latest `bankAccountUniqueId` or `accountReferenceId`.
- Confirm the account belongs to the same `merchantCustomerId`.
- If sending `customerVpa`, confirm it is already linked/owned in Newton for that customer.

### Aadhaar Parameter or Validation Failure

If only one of `aadhaarNo` and Aadhaar `otpRequestType` is supplied, Newton returns `BAD_REQUEST`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "otpRequestType parameter is missing"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "aadhaarNoFromUser parameter is missing"
}
```

If cached Aadhaar verification data is missing or the first six digits do not match:

```json
{
  "status": "FAILURE",
  "responseCode": "JPAM",
  "responseMessage": "Validation timeout for Aadhaar Number. Please try again."
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "JPAW",
  "responseMessage": "Incorrect Aadhaar Number. User is now blocked for next 24hrs."
}
```

If the user is already blocked from Aadhaar OTP:

```json
{
  "status": "FAILURE",
  "responseCode": "JPAUB",
  "responseMessage": "User is blocked from using Aadhaar to SET/RESET MPIN."
}
```

Client handling:

- Ask the customer to restart the Aadhaar verification/setup step if the cached value expired.
- Do not retry repeatedly with the same wrong Aadhaar digits.
- If blocked, fall back to a non-Aadhaar MPIN setup/reset path or wait for the configured block period.

### Downstream Timeout or NPCI Failure

If NPCI times out, Newton returns a service-unavailable error body.

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_Z9",
  "responseMessage": "NPCI service is not reachable at the moment (Z9)"
}
```

If NPCI returns an invalid error response with no usable code:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_RESPONSE_FROM_NPCI",
  "responseMessage": "Invalid response from NPCI"
}
```

If NPCI returns a normal business decline, the wrapper can still be `SUCCESS`; inspect `payload.gatewayResponseStatus` and `payload.gatewayResponseCode` as shown above.

### Unexpected Error

Malformed `credBlock`, impossible downstream credential combinations, missing required decrypted PII, or unexpected decode failures can produce an internal error.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling:

- Do not assume OTP was generated.
- Check whether `credBlock` is valid JSON generated by the common library.
- Retry only after correcting request data, or contact Newton support with `upiRequestId`, merchant id, and timestamp if the request appears valid.

## Retry, Idempotency, and Client Handling

- Treat each OTP generation attempt as a unique attempt and use a fresh `upiRequestId` for each customer retry. The code does not provide idempotent replay semantics for this API.
- Do not call Set MPIN unless `payload.gatewayResponseStatus` is `SUCCESS` and `payload.gatewayResponseCode` is `00`.
- If top-level `status` is `SUCCESS` but `payload.gatewayResponseStatus` is not `SUCCESS`, show a retryable bank/NPCI failure to the customer and create a new OTP request only when the customer retries.
- For timeouts or service-unavailable errors, retry with backoff and a new `upiRequestId`; avoid tight retry loops because banks can rate-limit OTP generation.
- For validation, auth, merchant config, account lookup, device fingerprint, and Aadhaar mismatch errors, fix the underlying issue before retrying.
- Store `gatewayTransactionId`, `gatewayResponseCode`, `gatewayResponseStatus`, and `gatewayResponseMessage` for support and reconciliation.
- OTP delivery is performed by the customer's bank/UPI ecosystem. Newton does not return the OTP value in this API response.

## Source References

- Route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:510)
- S2S handler: [Core.hs](../../src/Newton/App/Routes/Core.hs:2862)
- Server wiring: [Server.hs](../../src/Newton/App/Server.hs:294)
- Request envelope types: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- S2S signature verification: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request and response types: [Account.hs](../../src/Newton/Types/API/ServerToServer/Account.hs:447)
- Request validation helpers: [Common.hs](../../src/Newton/Validation/Common.hs:168)
- Product handler: [MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1214)
- Shared OTP trigger logic: [MerchantSDKV2.hs](../../src/Newton/Product/MerchantSDKV2.hs:2156)
- Account/VPA lookup: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:133)
- Account resolver behavior: [DB.hs](../../src/Newton/Utils/DB.hs:566)
- Device fingerprint validation: [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- NPCI OTP request flow: [AccountV2.hs](../../src/Newton/Product/AccountV2.hs:623)
- NPCI OTP transformer: [NpciTransformer.hs](../../src/Newton/Utils/NpciTransformer.hs:141)
- Response transformer: [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2027)
- Gateway response mapping and credential lengths: [Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:1049), [Utils.hs](../../src/Newton/Utils/Utils.hs:407)
- Error constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
- UIDAI error mapping: [UidaiErrorCodes.hs](../../src/Newton/Constants/UidaiErrorCodes.hs:5)
