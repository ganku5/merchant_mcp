# Fetch Accounts API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/fetch`

## Overview

Fetch Accounts is a server-to-server API used to discover a customer's bank accounts for one bank through the UPI/NPCI list-account flow.

The merchant calls this API after the customer profile and device binding exist in Newton. The request identifies the customer, registered device fingerprint, bank, and optional account-discovery mode. Newton verifies the S2S envelope and merchant signature, checks the customer/device context, calls the bank/NPCI list-account path, stores or refreshes discovered account records according to merchant configuration, and returns account identifiers that can be used in later account-management APIs.

Use this API before flows such as Add Account, Generate OTP, Set MPIN, Check Balance, biometric activation, pay, collect, or mandate creation when the merchant needs the customer's available UPI accounts for a selected bank.

Payloads use the standard Newton server-to-server encrypted request and response envelope. Examples below show decrypted business payloads for readability.

## Business Use Case

Fetch Accounts helps merchants:

- Discover bank accounts linked to the customer's registered mobile number at a selected bank.
- Let the customer choose an account to link with a VPA.
- Retrieve `bankAccountUniqueId` and, when enabled, `referenceId` for downstream account APIs.
- Discover OTP, MPIN, ATM PIN, Aadhaar, credit-line, MCC, and credential metadata returned by the bank.
- Refresh locally cached account state after device binding, account linking, MPIN setup, or bank-side account changes.
- Get VPA suggestions for the customer after account discovery.

This API does not link the account to a VPA, generate an OTP, set MPIN, fetch balance, or move money. Use the returned account identifiers with the relevant follow-up API for those actions.

## Integration Flow

1. Merchant registers or resolves the customer with Newton and obtains `merchantCustomerId`.
2. Customer completes device binding so Newton has an active device for the merchant customer.
3. Merchant gets the selected bank's `bankCode` from the bank-listing or onboarding flow.
4. Merchant backend creates a unique `upiRequestId` and calls Fetch Accounts with the customer's registered `deviceFingerPrint`.
5. Newton verifies the encrypted/signed S2S envelope, merchant headers, `iat`, API enablement, customer profile, device binding, request validation, and rate limit.
6. Newton validates the submitted device fingerprint against the registered device, calls the bank/NPCI list-account path, and stores or refreshes discovered account records according to merchant configuration.
7. Merchant decrypts the response and reads `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage` to determine the actual bank/NPCI result.
8. On successful account discovery, merchant stores the returned account identifiers and uses them in Add Account, OTP, MPIN, balance, payment, or mandate flows.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton.
- `bankCode`: Bank IIN/code for the account provider to query.
- `upiRequestId`: Merchant-generated UPI request id for this fetch attempt. Returned as `gatewayTransactionId`.
- `bankAccountUniqueId`: Merchant-facing account hash or migrated account identifier returned in each account object.
- `referenceId`: Newton account reference id, returned only when enabled/configured for the merchant or PSP mode.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/fetch
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. Use `3` or higher if the integration needs `account.accBIN` when available. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within Newton's accepted timestamp window. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding. Required for signed/production traffic when the request is not already accepted as a signed/encrypted envelope. |
| `x-sub-merchant-id` | Optional. Required only for configured sub-merchant routing. |
| `x-sub-merchant-channel-id` | Optional. Required only for configured sub-merchant routing. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. The request body can be sent in the configured encrypted JWE or signed JWS envelope. Plain decrypted JSON payloads are accepted only in environments/configurations where unsigned payloads are explicitly enabled.

For signed or encrypted S2S requests, include `iat` in the decrypted business payload. Newton validates `iat` during signature/envelope handling before the product logic runs.

### Path and Version Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route version segment. Use the value shared during onboarding. |
| `x-api-version` | header | integer string | Recommended | Response shaping version. Missing or non-numeric values fall back to `0`. |

### Version Behavior

| `x-api-version` | Response behavior |
| --- | --- |
| Missing, non-numeric, or `0` | Base response version. `account.bankAccountHash`, `account.bioAuthConsentUrl`, `account.credsAllowed`, and `account.accBIN` are omitted. |
| `1` | `account.bankAccountHash` may be included when TPV is enabled for the merchant. `account.bioAuthConsentUrl`, `account.credsAllowed`, and `account.accBIN` are omitted. |
| `2` | `account.bankAccountHash`, `account.bioAuthConsentUrl`, and `account.credsAllowed` may be included when available. `account.accBIN` is omitted. |
| `3` and above | Same as version `2`, and `account.accBIN` may be included when available, usually for credit-card or credit-line accounts. |

## Request

### Required Minimum

For new signed/encrypted integrations:

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "FACCT123456789",
  "deviceFingerPrint": "registered-device-fingerprint",
  "bankCode": "123456",
  "iat": "1735689600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Length must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `upiRequestId` | string | Yes | No default. | Unique UPI request id for this fetch attempt. Must be 1 to 35 alphanumeric characters. Returned as `payload.gatewayTransactionId`. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint returned or derived during device binding. Newton validates it against the customer's registered device. Must be non-empty. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Optional alternate fingerprint accepted during device matching, typically used during device-fingerprint migration or fallback flows. |
| `bankCode` | string | Yes | No default. | Bank IIN/code for the account provider to query. Must be non-empty and must exist in Newton's bank cache/configuration. |
| `accountType` | string enum | No | If omitted, Newton does not send an account-type filter and returns the eligible account types returned by the bank/NPCI path. | Optional account type filter for the list-account call. Common values include `SAVINGS`, `CURRENT`, `DEFAULT`, `NRE`, `NRO`, `CREDIT`, `PPIWALLET`, `BANKWALLET`, `SOD`, `UOD`, `UPICREDIT`, `CREDITLINE`, and configured credit-line variants such as `CL01`. |
| `iat` | string | Conditional | No default. | Issued-at timestamp in epoch milliseconds. Required for signed/encrypted S2S requests because Newton validates it as part of request freshness. Plain unsigned test payloads can omit it only when that mode is enabled. |
| `aadhaarConsent` | string | No | Omitted behaves as `"false"`. | Boolean string, `"true"` or `"false"`. Send `"true"` only when the customer has consented to Aadhaar OTP related account discovery. When true, account responses may include Aadhaar-related flags. |
| `purpose` | string | No | Defaults to `"00"`. | Two-character purpose code sent to the list-account path. Must be uppercase alphanumeric when supplied. |
| `remarks` | string | No | No default. | Customer-facing or audit note sent to the downstream list-account path. Must be 1 to 255 characters when supplied and match Newton's remarks format. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | Merchant-defined metadata. The fetch validator does not parse this field; send a JSON-object string if the merchant needs structured metadata. Echoed unchanged in a successful Newton response. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `aadhaarConsent`: omitted behaves as false. Aadhaar response flags are omitted unless this is true and the bank/NPCI response supports them.
- `purpose`: omitted becomes `"00"` before Newton calls the list-account path.
- `accountType`: omitted means no account-type filter is applied by Newton for this request.
- `fallbackDeviceFingerPrint`: omitted means only `deviceFingerPrint` is accepted during device validation.
- `udfParameters`: echoed only in normal Newton success responses and only when supplied.
- Merchant configuration controls whether Newton creates or refreshes merchant-customer-account records during account fetch. The client cannot set this in the request. The response still contains discovered accounts when the bank/NPCI path succeeds, but default/reference fields can vary by merchant and PSP configuration.
- If the merchant is configured to block credit-card account discovery for issuing banks, a credit-card bank fetch can be rejected before the NPCI call.

### Nested Request Objects

Fetch Accounts has no nested request object. All business fields are top-level fields in the decrypted payload.

### Validation Notes

- `merchantCustomerId` must be 1 to 256 characters and match Newton's merchant-customer-id format.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `deviceFingerPrint` and `bankCode` must be non-empty.
- `aadhaarConsent`, when supplied, must be `"true"` or `"false"`; matching is case-insensitive in validation.
- `purpose`, when supplied, must be exactly 2 uppercase alphanumeric characters.
- `remarks`, when supplied, must be 1 to 255 characters and match the allowed remarks format.
- `accountType`, when supplied, must parse as one of Newton's configured account type enum values.
- Newton validates `deviceFingerPrint` against the registered device fingerprint, with `fallbackDeviceFingerPrint` accepted as an alternate when supplied.

## Request Examples

### Standard Account Discovery

Use this after the customer has selected a bank and the merchant wants all eligible UPI accounts for that bank.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "FACCT123456789",
  "deviceFingerPrint": "f5d1c4c7d3e4a9b0",
  "bankCode": "123456",
  "iat": "1735689600000",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Discovery With Fallback Fingerprint and Account Type

Use this during a device-fingerprint migration or when the merchant wants to restrict discovery to one account type.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "FACCT123456790",
  "deviceFingerPrint": "f5d1c4c7d3e4a9b0",
  "fallbackDeviceFingerPrint": "a31c2d9e8b7f6540",
  "bankCode": "123456",
  "accountType": "SAVINGS",
  "purpose": "00",
  "remarks": "Account discovery",
  "iat": "1735689600000"
}
```

### Aadhaar-Consent Account Discovery

Use this only when the customer has explicitly consented to Aadhaar OTP related discovery.

```json
{
  "merchantCustomerId": "CUST12345",
  "upiRequestId": "FACCT123456791",
  "deviceFingerPrint": "f5d1c4c7d3e4a9b0",
  "bankCode": "123456",
  "aadhaarConsent": "true",
  "purpose": "00",
  "remarks": "Aadhaar consent account discovery",
  "iat": "1735689600000"
}
```

## Response

When the request is accepted by Newton and product logic completes normally, the top-level response is a Newton success envelope. The actual bank/NPCI discovery result is inside `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

### Success Response Shape

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "FACCT123456789",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Accounts fetched successfully",
    "accounts": [
      {
        "bankCode": "123456",
        "bankName": "Example Bank",
        "maskedAccountNumber": "XXXXXX1234",
        "mpinLength": "6",
        "mpinSet": "false",
        "type": "SAVINGS",
        "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
        "ifsc": "EXAM0001234",
        "name": "A CUSTOMER",
        "otpLength": "6",
        "atmPinLength": "4",
        "accountNumber": "encrypted-account-number",
        "bankAccountHash": "TPV_ACCOUNT_HASH"
      }
    ],
    "vpaSuggestions": [
      "cust12345@upi"
    ]
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Response Envelope Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton API processing status. For normal product responses this is `SUCCESS`, even if the bank/NPCI list-account result failed. |
| `responseCode` | string | Newton top-level response code. Normal product responses use `SUCCESS`. |
| `responseMessage` | string | Newton top-level response message. Normal product responses use `SUCCESS`. |
| `payload` | object | Fetch account response payload. Present in normal product responses. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from Newton's merchant configuration. |
| `merchantChannelId` | string | Merchant channel id from Newton's merchant configuration. |
| `merchantCustomerId` | string | Echoed merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number registered with Newton, returned decrypted in the business payload. |
| `gatewayTransactionId` | string | Echoed `upiRequestId` from the request. |
| `gatewayResponseStatus` | string | Bank/NPCI business result interpreted by Newton. `SUCCESS` means accounts were fetched. `FAILURE` means the request completed but account discovery failed or returned a known gateway/business code. |
| `gatewayResponseCode` | string | `00` on successful account fetch. Otherwise the bank/NPCI/Newton-mapped business code, for example `XH`, `JPXH`, `JPNTO`, or another mapped code. |
| `gatewayResponseMessage` | string | `Accounts fetched successfully` on success. On failure, a mapped message for `gatewayResponseCode`, or `Fetch accounts failed` when no mapped message exists. |
| `accounts` | array of objects | Discovered accounts. Omitted when Newton has no account list to return. Returned as an empty array when the gateway explicitly returns no matching remitter accounts with code `XH`. |
| `vpaSuggestions` | array of strings | Suggested VPAs for the customer when available. Omitted when suggestions are not available. |

### `accounts[]` Fields

Fields with no value are omitted from the JSON response.

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Bank code/IIN for the discovered account. |
| `bankName` | string | Bank display name. |
| `maskedAccountNumber` | string | Masked account number returned/stored for display. |
| `mpinLength` | string | MPIN length required for the account. |
| `mpinSet` | string | `"true"` if MPIN is set for the account, otherwise `"false"`. Merchant/customer configuration can force this to `"false"` for some app flows. |
| `referenceId` | string | Newton account reference id. For S2S account fetch this is often omitted unless the merchant/PSP mode enables account reference ids. |
| `type` | string | Account type, for example `SAVINGS`, `CURRENT`, `CREDIT`, or a credit-line type. |
| `branchName` | string | Branch name. Generally omitted for this S2S multibank response path. |
| `bankAccountUniqueId` | string | Merchant-facing account hash or migrated identifier. Prefer this identifier for follow-up S2S account APIs when available. |
| `ifsc` | string | Account IFSC. |
| `isPrimary` | string | Primary/default flag. Generally omitted for this S2S fetch path; primary mappings are established by account-linking APIs. |
| `name` | string | Account holder name after Newton sanitization. |
| `otpLength` | string | OTP length for bank OTP flows. Defaults to the credential length returned by the bank, or `6` when not present in the account credential metadata. |
| `atmPinLength` | string | ATM PIN length for supported set-MPIN formats. Defaults to the credential length returned by the bank, or `4` when not present in the account credential metadata. |
| `kycStatus` | string | KYC status when returned for the account, for example `MIN` or `FULL`. |
| `accountNumber` | string | Encrypted account number when returned by merchant configuration. This is not a raw account number. |
| `accBIN` | string | Account BIN when available. Omitted unless `x-api-version >= 3`. Usually relevant for credit-card or credit-line accounts. |
| `aadhaarEnabled` | string | `"true"` or `"false"` when `aadhaarConsent` is true and Aadhaar metadata is available. Omitted otherwise. |
| `isAadhaarNumberAvailable` | string | `"true"` or `"false"` when `aadhaarConsent` is true and Newton can determine Aadhaar availability. Omitted otherwise. |
| `bankAccountHash` | string | TPV account hash when TPV is enabled for the merchant and `x-api-version > 0`. |
| `accSubType` | string | Account subtype, usually for credit-line accounts. |
| `allowedMCC` | array of strings | MCC allow-list for credit-line account usage when returned by NPCI/bank. |
| `notallowedMCC` | array of strings | MCC deny-list for credit-line account usage when returned by NPCI/bank. |
| `lrn` | string | UPI Lite reference number. Normally omitted by this S2S fetch path because lite details are not requested here. |
| `isInitialTopUpDone` | string | UPI Lite initial top-up flag. Normally omitted by this S2S fetch path. |
| `liteDetails` | object | UPI Lite details. Normally omitted by this S2S fetch path. |
| `bioAuthConsentUrl` | string | Biometric-auth consent URL when returned by the bank/NPCI response and `x-api-version > 1`. |
| `bioAuthEnabled` | string | Biometric-auth enabled flag. Normally omitted by this fetch path. |
| `credsAllowed` | string | Credential metadata returned by NPCI/bank when available and `x-api-version > 1`. |
| `payerAccountHash` | string | Account-number-only hash when `enablePayerAccountHash` is enabled for the merchant. |

### Gateway Failure in a Normal Newton Response

If Newton reaches the product path and receives a known bank/NPCI/business failure, the top-level response can still be `SUCCESS`. In this case, use `payload.gatewayResponseStatus` for business handling.

No remitter account at the selected bank:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "FACCT123456792",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "XH",
    "gatewayResponseMessage": "Remitter account does not exist",
    "accounts": []
  }
}
```

Credit-line accounts found but credit-line linking is not enabled for the merchant:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "FACCT123456793",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JPXH",
    "gatewayResponseMessage": "UPI Credit Line account linking not enabled"
  }
}
```

Downstream timeout/failure with a mapped gateway code:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "gatewayTransactionId": "FACCT123456794",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "JPNTO",
    "gatewayResponseMessage": "NPCI timeout"
  }
}
```

## Error Handling

Failures before normal product-response creation use the same encrypted/signed response transport configured for the integration. After decryption, the body generally follows Newton's standard error shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"Field is empty\""
}
```

The exact `responseCode` and `responseMessage` depend on the validation or business rule that failed. HTTP status can vary by validation layer. Always parse the decrypted body first, then use HTTP status for transport-level troubleshooting.

### Concrete Failure Scenarios

Validation failure, for example empty `deviceFingerPrint`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"deviceFingerPrint field is empty\""
}
```

Missing `iat` on a signed/encrypted request:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

Missing or invalid merchant headers/signature, invalid request IP for an IP-whitelisted merchant, or signature mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not allowed for the merchant configuration:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Unknown or inactive customer profile for the merchant customer id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Customer profile exists but no active device is bound:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Device fingerprint mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

Unknown `bankCode`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Bank not found"
}
```

Merchant configuration blocks account fetch for the selected credit-card bank:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Fetch Account on Credit Card is not allowed"
}
```

NPCI service unavailable with no usable gateway code:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Unexpected decode, Redis, encryption, or internal processing error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Client Handling and Retry Guidance

- Treat top-level `status = SUCCESS` as "Newton processed the request," not necessarily "accounts were found." Use `payload.gatewayResponseStatus` for the account-discovery result.
- Proceed to Add Account, OTP, MPIN, balance, or transaction flows only when `payload.gatewayResponseStatus = SUCCESS` and at least one usable account is present.
- Generate a unique `upiRequestId` for every fetch attempt. Newton returns it as `gatewayTransactionId`, but this endpoint does not use it as a deduplication/idempotency key.
- Retry with backoff for transient transport failures, `SERVICE_UNAVAILABLE_NPCI_*`, and retryable downstream timeout codes such as `JPNTO` or `JPCF`.
- Do not retry unchanged requests for validation, auth/signature, API enablement, device-fingerprint mismatch, missing device binding, unknown bank, or merchant-configuration failures. Fix the request, customer setup, device binding, bank selection, or merchant configuration first.
- For `XH`, show a customer-friendly "no accounts found for this bank/mobile" outcome and let the customer choose another bank or confirm their bank-registered mobile number.
- For `JPXH`, do not present credit-line accounts as linkable until the merchant is enabled for that account type.
- Refresh and store account identifiers from the latest successful response. Bank account metadata can change after MPIN setup, bank-side updates, or re-discovery.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:183)
- Route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1753)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:796)
- S2S request/response types and validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:3463)
- S2S core request/response mapping: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1484)
- Account fetch product route: [src/Newton/Product/Merchant/Account/FetchAccount.hs](../../src/Newton/Product/Merchant/Account/FetchAccount.hs:46)
- Account fetch response helper: [src/Newton/Product/Merchant/Account/Helper.hs](../../src/Newton/Product/Merchant/Account/Helper.hs:74)
- Fetch account core and gateway response types: [src/Newton/Product/Merchant/Account/Types.hs](../../src/Newton/Product/Merchant/Account/Types.hs:38)
- Public account response type: [src/Newton/Types/API/Account.hs](../../src/Newton/Types/API/Account.hs:12)
- Account response transformer: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:438)
- Request validators: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- S2S envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Standard error helpers: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
