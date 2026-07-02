# Add Account API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/add`

## Overview

Add Account is a server-to-server API used to link an already discovered customer bank account to a customer VPA in Newton.

The merchant calls this API after the customer profile exists in Newton and the account to link is already known from account discovery/onboarding APIs. Newton validates the merchant, customer, VPA, and account context; creates or reuses the requested customer VPA; updates the VPA-account mapping; optionally marks the selected account as the customer's outward/default account; and returns the customer's current VPA-account state.

Use this API when the customer selects a bank account that should be usable with a VPA in the merchant UPI experience. Do not use it to discover accounts, fetch balance, set MPIN, or perform a UPI payment authorization.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Add Account helps merchants:

- Link a selected bank account to a new or existing customer VPA.
- Set the selected bank account as the default outward account for the customer.
- Set the linked account as the primary account for one VPA or for all of the customer's VPAs.
- Add a secondary/non-primary account mapping without disturbing an existing primary VPA-account mapping.
- Refresh the merchant backend's customer account cache from the returned `vpaAccounts` snapshot.

This API updates Newton's local customer/VPA/account mapping. It does not call NPCI or the bank for balance, MPIN, OTP, debit, or collect authorization.

## Integration Flow

1. Merchant registers or resolves the customer with Newton and obtains `merchantCustomerId`.
2. Merchant fetches or stores the customer's account identifiers from the account discovery/linking flow.
3. Merchant chooses the `customerVpa` to associate with the account.
4. Merchant calls Add Account with either `bankAccountUniqueId` or `accountReferenceId`, plus the desired default/primary mapping flags for the selected API version.
5. Newton verifies the S2S envelope, signature, timestamp, merchant headers, API enablement, merchant customer, customer, account, and VPA rules.
6. Newton creates/reuses the VPA, synchronizes the account mapping, updates default flags when requested, and returns the updated VPA-account list.
7. Merchant stores the returned `vpaAccounts`, `primaryVpa` when returned by the selected response version, and account identifiers for later balance, mandate, or payment flows.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. This scopes the customer profile.
- `bankAccountUniqueId`: Merchant-facing account hash or migrated account identifier returned by account APIs.
- `accountReferenceId`: Newton account reference id returned by account APIs.
- `customerVpa`: Customer VPA to create/reuse and link to the selected account.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/add
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | `4` recommended for new integrations. Controls request-version rules and response fields for this API. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within 30 minutes of Newton's clock. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding. Required for signed/encrypted production traffic. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. Signed/encrypted calls must include valid merchant headers, timestamp, signature, and encrypted/signed request envelope. The decrypted business payload should include `iat` for signed/encrypted requests. Plain-text unsigned test payloads can omit `iat` only when that mode is enabled for the environment.

### Path and Version Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route version segment. Use the value shared during onboarding. |
| `x-api-version` | header | integer string | Recommended | Add Account request/response version. Missing or non-numeric values fall back to `1` for multibank-enabled merchants and `0` otherwise. |

### Add Account Version Behavior

| `x-api-version` | Request behavior | Response behavior |
| --- | --- | --- |
| `0`, or missing/non-numeric for non-multibank merchants | `setDefault` defaults to `true`; `primaryAccountMapping` defaults to `ONE_TO_ALL`. Legacy behavior. | `payload.primaryVpa` is omitted. `account.accBIN` is omitted. |
| `1`, or missing/non-numeric for multibank-enabled merchants | `setAsDefaultBank` is mandatory. `true` maps to `setDefault=true` and `primaryAccountMapping=ONE_TO_ALL`; `false` maps to `setDefault=false` and `primaryAccountMapping=NONE`. | `payload.primaryVpa` is omitted. `account.accBIN` is omitted. |
| `2` | `setDefault` and `primaryAccountMapping` are mandatory. | `payload.primaryVpa` is omitted. `account.accBIN` is omitted. |
| `3` | `setDefault` and `primaryAccountMapping` are mandatory. | `payload.primaryVpa` is included when available. `account.accBIN` is omitted. |
| `4` | `setDefault` and `primaryAccountMapping` are mandatory. Recommended for new integrations. | `payload.primaryVpa` is included when available. `account.accBIN` is included when available, usually for credit accounts. |
| Greater than `4` | Not supported by current Add Account transformer. | Returns an internal-server-error body. |

## Request

### Required Minimum

For new integrations using `x-api-version: 4`, send either `bankAccountUniqueId` or `accountReferenceId`.

Using `bankAccountUniqueId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "customerVpa": "cust.pay@bank",
  "setDefault": "true",
  "primaryAccountMapping": "ONE_TO_ONE",
  "iat": "1735689600000"
}
```

Using `accountReferenceId`:

```json
{
  "merchantCustomerId": "CUST12345",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "cust.pay@bank",
  "setDefault": "true",
  "primaryAccountMapping": "ONE_TO_ONE",
  "iat": "1735689600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Length must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `accountReferenceId` | string | Conditional | No default. | Newton account reference id returned by account APIs. Send this or `bankAccountUniqueId`. For ICICI/GPay modes, use the account-reference form returned by that flow; `accountReferenceId` is mandatory there. |
| `bankAccountUniqueId` | string | Conditional | No default. | Account hash or migrated account identifier returned by account APIs. Send this or `accountReferenceId`. |
| `customerVpa` | string | Yes | No default. | Customer VPA to link to the selected account. Must be 3 to 255 characters and match `local@handle` format. Newton also applies merchant/customer VPA rules during processing. |
| `setDefault` | string | Required for `x-api-version` `2`, `3`, and `4` | For version `0`, defaults to `true`. For version `1`, derived from `setAsDefaultBank`. No default for versions `2` to `4`. | Boolean string, `"true"` or `"false"`. When `"true"`, Newton marks this account as the customer's outward/default account. |
| `primaryAccountMapping` | string enum | Required for `x-api-version` `2`, `3`, and `4` | For version `0`, defaults to `ONE_TO_ALL`. For version `1`, derived from `setAsDefaultBank`. No default for versions `2` to `4`. | Controls which VPA-account mappings become primary. Allowed values: `ONE_TO_ONE`, `ONE_TO_ALL`, `NONE`. |
| `setAsDefaultBank` | string | Required only for `x-api-version: 1` | Ignored by versions `0`, `2`, `3`, and `4`. | Legacy boolean string. `"true"` sets the account as default and primary for all VPAs. `"false"` links without changing primary mappings. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Unsigned/plain test payloads skip IAT validation only when that request type is enabled. | Issued-at timestamp used for request freshness validation. Send a 13-digit epoch-milliseconds value within 30 minutes of Newton's clock. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in the success response. Must parse as a JSON object string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

Send only one account identifier where possible. If both `bankAccountUniqueId` and `accountReferenceId` are sent, the resolver can choose differently by PSP/merchant mode, so using one identifier avoids ambiguity.

### `primaryAccountMapping`

| Value | Behavior |
| --- | --- |
| `ONE_TO_ONE` | Link the selected account to `customerVpa` and make it the primary/default mapping for that VPA only. |
| `ONE_TO_ALL` | Link the selected account across the customer's VPAs and make it primary for all of them. |
| `NONE` | Link the selected account without making it primary. Existing primary mappings are preserved. Use only when the VPA already exists with a primary account mapping; a first mapping for a new VPA is rejected. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `accountReferenceId` and `bankAccountUniqueId`: one of these should always be sent. If both are omitted, Newton returns `BAD_REQUEST`.
- `setDefault`: controls the outward/default account. It does not by itself control the VPA primary mapping for versions `2` to `4`; use `primaryAccountMapping` for that.
- `primaryAccountMapping`: controls VPA-account primary mapping. `NONE` is not valid when creating the first mapping for a VPA.
- `setAsDefaultBank`: legacy version `1` field. For new integrations, use `setDefault` and `primaryAccountMapping` instead.
- `customerVpa`: stored and compared using normalized/lower-case VPA values where required by Newton's VPA uniqueness rules.
- `udfParameters`: echoed only on success and only when supplied.

### Validation Notes

- `merchantCustomerId` must be 1 to 256 characters and match Newton's merchant-customer-id format.
- `accountReferenceId` and `bankAccountUniqueId`, when supplied, must be non-empty.
- `customerVpa` must match the basic VPA format and also pass merchant/customer VPA rules. Mobile-number based VPAs can be checked against the customer's registered mobile number and configured VPA handle.
- `setDefault` and `setAsDefaultBank` must be string booleans: `"true"` or `"false"`.
- `primaryAccountMapping` must be one of `ONE_TO_ONE`, `ONE_TO_ALL`, or `NONE`.
- `udfParameters` must be a JSON object encoded as a string and must pass the allowed-character check.
- `x-api-version` controls which default/primary fields are mandatory. Missing required version fields returns `BAD_REQUEST`.

## Request Examples

### Link Account to One VPA and Set as Default

Use this when the customer selected one VPA and this account should be primary only for that VPA.

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "BANKACC123",
  "customerVpa": "cust.pay@bank",
  "setDefault": "true",
  "primaryAccountMapping": "ONE_TO_ONE",
  "iat": "1735689600000",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Link Account as Primary for All Customer VPAs

Use this when the account should become the primary mapping for every VPA in the customer's Newton profile.

```json
{
  "merchantCustomerId": "CUST12345",
  "accountReferenceId": "ACCOUNT_REF_123",
  "customerVpa": "cust.primary@bank",
  "setDefault": "true",
  "primaryAccountMapping": "ONE_TO_ALL",
  "iat": "1735689600000"
}
```

### Link a Secondary Account Without Changing Primary Mapping

Use this only when `customerVpa` already exists and already has a primary account mapping.

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "BANKACC456",
  "customerVpa": "cust.primary@bank",
  "setDefault": "false",
  "primaryAccountMapping": "NONE",
  "iat": "1735689600000"
}
```

### Legacy Version 1 Request

For `x-api-version: 1`, send `setAsDefaultBank`.

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "BANKACC123",
  "customerVpa": "cust.pay@bank",
  "setAsDefaultBank": "true",
  "iat": "1735689600000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API business status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Updated merchant customer VPA-account state. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. |

Add Account does not return bank/NPCI gateway status fields. On success, interpret the operation from the top-level `status`, `responseCode`, and the returned `payload.vpaAccounts` snapshot.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number, trimmed before response when available. |
| `vpaAccounts` | array | Current active VPA-account mappings visible to this merchant customer after the add operation. |
| `primaryVpa` | string | Returned only when `x-api-version > 2` and a primary VPA is available. Omitted for response versions `0`, `1`, and `2`. |

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA for this mapping. |
| `account` | object | Account details for the linked account. |
| `isDefault` | boolean | Whether this account is the primary/default mapping for the VPA. Use this field for Add Account responses; `account.isPrimary` is generally omitted by this flow. |

### `vpaAccounts[].account`

The exact account fields returned depend on merchant configuration, account type, multibank mode, account data, and response version. Optional fields are omitted when unavailable.

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Bank/IIN code for the account. |
| `bankName` | string | Bank display name. |
| `maskedAccountNumber` | string | Masked account number for display. |
| `mpinLength` | string | MPIN length expected for the account. |
| `mpinSet` | string | Whether MPIN is set for the account. Can be forced to `"false"` for configured iOS MPIN setup flows. |
| `referenceId` | string | Account reference id. In multibank flows this can be omitted unless the merchant is configured to include it. |
| `type` | string | Account type, for example `SAVINGS`, `CURRENT`, or `CREDIT`. |
| `branchName` | string | Branch name when available. Omitted in multibank responses. |
| `bankAccountUniqueId` | string | Account hash or migrated account id to use in later account APIs. |
| `ifsc` | string | Account IFSC when available. |
| `name` | string | Account holder name when available. |
| `otpLength` | string | OTP length expected for the account. |
| `atmPinLength` | string | ATM PIN length when format-2 response is enabled for the merchant. |
| `kycStatus` | string | KYC status when available. |
| `accountNumber` | string | Encrypted account number when enabled for the merchant response. |
| `accBIN` | string | Account BIN when available and `x-api-version > 3`. Usually relevant for credit accounts. |
| `aadhaarEnabled` | string | Aadhaar enablement flag when returned for applicable flows. |
| `isAadhaarNumberAvailable` | string | Aadhaar-number availability flag when returned for applicable flows. |
| `bankAccountHash` | string | TPV bank-account hash when TPV is enabled for the merchant. |
| `accSubType` | string | Account subtype, for example credit-line subtype. |
| `allowedMCC` | array of strings | Allowed MCC list for applicable accounts. |
| `notallowedMCC` | array of strings | Blocked MCC list for applicable accounts. |
| `lrn` | string | UPI Lite reference number when available. |
| `isInitialTopUpDone` | string | UPI Lite initial top-up status when available. |
| `liteDetails` | object | UPI Lite details when requested and available. |
| `bioAuthConsentUrl` | string | Bio-auth consent URL when available. |
| `bioAuthEnabled` | string | Bio-auth enablement flag for this account, commonly `"true"` or `"false"`. |
| `credsAllowed` | string | Credential allowance information when available. |
| `payerAccountHash` | string | Hash of account number without IFSC when enabled for the merchant. |

### `account.liteDetails`

Returned only for UPI Lite enabled flows when Lite details are requested and available.

| Field | Type | Description |
| --- | --- | --- |
| `lrn` | string | Lite reference number when visible for the current device/context. |
| `status` | string | UPI Lite status, for example `ACTIVE` or `PENDING_ACTIVATION`. |
| `pendingUpiRequestId` | string | Pending Lite request id when available. |
| `autoTopupStatus` | string | Auto top-up status when available. |
| `autoTopupInfo` | object | Auto top-up configuration/info when available. |

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
    "vpaAccounts": [
      {
        "vpa": "cust.pay@bank",
        "isDefault": true,
        "account": {
          "bankCode": "123456",
          "bankName": "Example Bank",
          "maskedAccountNumber": "XXXXXX1234",
          "mpinLength": "6",
          "mpinSet": "true",
          "referenceId": "ACCOUNT_REF_123",
          "type": "SAVINGS",
          "branchName": "Main Branch",
          "bankAccountUniqueId": "BANKACC123",
          "ifsc": "EXAM0001234",
          "name": "Customer Name",
          "otpLength": "6",
          "atmPinLength": "4",
          "bioAuthEnabled": "false"
        }
      }
    ],
    "primaryVpa": "cust.pay@bank"
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Example Credit Account Response With `accBIN`

`accBIN` is returned only when available and the response version is greater than `3`.

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
    "vpaAccounts": [
      {
        "vpa": "cust.credit@bank",
        "isDefault": true,
        "account": {
          "bankCode": "654321",
          "bankName": "Example Credit Bank",
          "maskedAccountNumber": "XXXXXXXX1111",
          "mpinLength": "6",
          "mpinSet": "true",
          "referenceId": "CREDIT_ACC_REF_123",
          "type": "CREDIT",
          "bankAccountUniqueId": "CREDITACC123",
          "ifsc": "EXAM0004321",
          "name": "Customer Name",
          "otpLength": "6",
          "accBIN": "411111",
          "accSubType": "CREDIT_CARD"
        }
      }
    ],
    "primaryVpa": "cust.credit@bank"
  }
}
```

## Failure Responses

Failure responses use the same encrypted response transport as successful responses. The examples below show the decrypted business body.

Most failure bodies follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "customerVpa is mandatory"
}
```

The exact `responseCode` and `responseMessage` depend on the validation or business rule that failed. When `payload` is empty, it is omitted from the JSON response. Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, or `500`; clients should read `status`, `responseCode`, and `responseMessage` from the decrypted body.

### Authentication, Encryption, and Merchant Configuration

Missing merchant headers, invalid merchant credentials, IP allowlist failure, missing signature, or signature mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

JWS/JWE key, entity-type, or encrypted-envelope verification failure can also return:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Add Account API disabled, blocked, or not allowed for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Malformed decrypted payload JSON or invalid encrypted-payload JSON:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error while parsing encryptedPayload"
}
```

### Timestamp and Freshness

Signed/encrypted request is missing `iat`:

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

Invalid `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

Invalid `customerVpa` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"customerVpa regex failed\""
}
```

Empty `accountReferenceId` or `bankAccountUniqueId` when the field is supplied:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"Field is empty\""
}
```

Invalid boolean string in `setDefault` or `setAsDefaultBank`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "BoolStringValidation \"Parameter is not true or false\""
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

`x-api-version: 1` without `setAsDefaultBank`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "setAsDefaultBank mandatory for api version 1"
}
```

`x-api-version: 2`, `3`, or `4` without `setDefault` or `primaryAccountMapping`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "setDefault and primaryAccountMapping mandatory for api version 4"
}
```

Unsupported `x-api-version` greater than `4`:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Missing account identifier:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory"
}
```

### Customer, VPA, and Account Lookup

Merchant customer profile not found or inactive:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Merchant customer has no active customer binding:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Linked account not found, inactive, or not scoped to the merchant customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

VPA fails merchant/customer rules, such as invalid handle or mobile-number VPA mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "vpa is not valid"
}
```

Requested VPA cannot be claimed for this customer/merchant customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Customer Vpa"
}
```

Normalized VPA already exists for another VPA form:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Normalized VPA already exists"
}
```

`primaryAccountMapping` is `NONE` for the first mapping of a VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "NONE is not allowed for first entry"
}
```

### Storage, Encryption, and Unexpected Failures

Add Account has no direct NPCI/bank downstream call. Failures after business validation are typically storage, cache, encryption/key-service, or unexpected server failures. These generally return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Treat this as retryable only after checking whether the first request actually succeeded by reading the latest customer/VPA-account state.

## Client Handling, Retry, and Idempotency

- Add Account does not take a merchant-generated idempotency key. Treat the operation target as `merchantCustomerId` plus the selected account identifier, `customerVpa`, `setDefault`, and `primaryAccountMapping`.
- Retrying the exact same business request is generally safe: existing VPA-account rows are updated/reactivated rather than blindly duplicated, and default/primary flags are set to the requested state.
- Retrying with different `setDefault` or `primaryAccountMapping` values can intentionally mutate the customer's profile. Store the body used for each attempt.
- If the client times out before receiving the response, either retry the same business request with fresh S2S envelope timestamps/signature or fetch the customer/account state and reconcile from `vpaAccounts`.
- For `REQUEST_EXPIRED` or timestamp errors, regenerate `iat`, `x-timestamp`, and the signature/encrypted envelope, then retry with the same business intent.
- For validation, auth, API enablement, customer, VPA, or account lookup failures, correct the request or merchant configuration before retrying.
- Do not look for gateway fields such as `gatewayResponseCode`; this API does not perform a bank/NPCI authorization.

## Source References

- Route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:194)
- Route handler and signature flow: [addAccount](../../src/Newton/App/Routes/Core.hs:1793)
- S2S transformer and version fallback: [addAccountTransformer](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:199)
- Request, response, enum, and validators: [Vpa.hs](../../src/Newton/Types/API/ServerToServer/Vpa.hs:24)
- Core request/response types: [Account.hs](../../src/Newton/Types/API/Core/Account.hs:11)
- S2S request/response transformers: [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:65)
- Product flow: [AddAccount.hs](../../src/Newton/Product/Merchant/Account/AddAccount.hs:42)
- Account lookup and mandatory account-id errors: [DB.hs](../../src/Newton/Utils/DB.hs:540)
- `NONE` primary-mapping validation: [DB.hs](../../src/Newton/Utils/DB.hs:791)
- VPA create/sync helpers: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:179)
- Default account and VPA-account sync updates: [AccountV2.hs](../../src/Newton/Product/AccountV2.hs:845)
- Response account construction: [Transformer4.hs](../../src/Newton/Utils/Transformers/Transformer4.hs:215), [Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:438), [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1675)
- API version parsing: [Utils.hs](../../src/Newton/Utils/Utils.hs:960)
- Request validation helpers: [Common.hs](../../src/Newton/Validation/Common.hs:125), [Common.hs](../../src/Newton/Validation/Common.hs:256), [Common.hs](../../src/Newton/Validation/Common.hs:311)
- S2S envelope and signature middleware: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96), [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp freshness validation: [DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- Error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151)
- API path/API name constants: [Constants.hs](../../src/Newton/Types/Domain/Constants.hs:886), [Constants.hs](../../src/Newton/Types/Domain/Constants.hs:2402)
