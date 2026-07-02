# Manage VPA Accounts API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpaAccounts`

Note: this document file name contains `preapproved`, but the mounted route in code is `merchants/vpaAccounts`. Integrate with the source endpoint above.

## Overview

Manage VPA Accounts is a Newton server-to-server API for maintaining a customer's UPI VPA and bank-account links after the customer has already been onboarded.

Use this API when your backend needs to add a customer VPA, link an existing customer bank account to one or more VPAs, set the primary or default account, delete a VPA or account, or fetch the current customer account/VPA state.

Payloads use the standard Newton server-to-server encrypted or signed request and response envelope shared during onboarding. Examples in this guide show the decrypted business payload for readability.

## Business Use Case

Manage VPA Accounts helps merchants:

- Add a new customer VPA and map it to a bank account.
- Add an existing bank account to the merchant customer's account list.
- Link a bank account to all customer VPAs or to one specified VPA.
- Set the outward default bank account for the customer.
- Set the primary bank account for one VPA or all VPAs.
- Delete a VPA, including its VPA-account mappings.
- Delete a bank account, optionally deleting VPAs for which that account is primary.
- Fetch customer mobile number, VPAs, bank accounts, UPI numbers, device details, and delegate-link information.
- Support delegate VPA and IoT VPA flows where those features are enabled for the merchant.

## Integration Flow

1. Merchant backend identifies the Newton `merchantCustomerId` and the action to perform.
2. Merchant backend prepares the decrypted business payload described below.
3. Merchant wraps the payload in the Newton S2S encrypted or signed envelope and sends required merchant headers.
4. Newton decrypts/parses the payload, validates merchant signature or envelope, timestamp, API access, IP restrictions, and merchant-customer context.
5. Newton validates action-specific request fields.
6. Newton applies the requested VPA/account operation and returns the updated customer state.
7. Merchant decrypts/verifies the response envelope and persists returned `bankAccountUniqueId`, `vpa`, and default/primary state as needed.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpaAccounts
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment. Newton also reads `x-api-version` for response-field gating in some account fields. |

### Headers, Auth, Encryption, and Signing

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-api-version` | Recommended | API version header used by shared transformers for version-gated response fields. Use the value shared during onboarding. |
| `x-merchant-id` | Yes | Merchant identifier. Used to load merchant configuration. |
| `x-merchant-channel-id` | Yes | Merchant channel id. Used with `x-merchant-id` to resolve the merchant. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness, except for limited non-production checksum bypass cases. |
| `x-merchant-signature` | Conditional | Required for unsigned payload mode. Signature is calculated over `x-merchant-id + x-merchant-channel-id + optional sub-merchant ids + x-timestamp + raw request body` using the merchant API key and configured signature strategy. |
| `x-merchant-checksum` | Conditional | Legacy/non-production checksum path. Use only if enabled for your merchant/environment. |
| `x-forwarded-for` | Conditional | Required when merchant config has `whitelistedIps`; the first IP in this header must be allowlisted. |
| `Authorization` | Conditional | Present when your onboarding profile uses it. The middleware reads it but this route's primary merchant verification uses the merchant headers above. |

Newton accepts three envelope shapes through `EncRequest`:

| Envelope | JSON fields | Notes |
| --- | --- | --- |
| Encrypted payload | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag` | Standard JWE-style encrypted S2S payload. |
| Signed payload | `payload`, `signature`, `protected` | Standard JWS-style signed S2S payload. |
| Unsigned payload | business payload fields directly | Only for configured flows/environments. Requires `x-merchant-signature` validation. |

Responses use `EncResponse` and may be encrypted, signed, plain, or an error response depending on the merchant configuration and failure layer. The response examples below show the decrypted business JSON.

## Actions

`action` is required and must be one of:

| Action | Purpose |
| --- | --- |
| `ADD_VPA` | Add or idempotently reuse a VPA for the merchant customer. For normal VPAs, also create/update the VPA primary account mapping. |
| `ADD_ACCOUNT` | Add an existing customer bank account to the merchant customer's account list. |
| `LINK_VPA_ACCOUNT` | Link an existing bank account to all VPAs or to one specified VPA. Can also set the default account. |
| `DELETE_VPA` | Delete a customer VPA and its VPA-account mappings. |
| `DELETE_ACCOUNT` | Delete/deactivate an account from the merchant customer, subject to default, primary, mandate, UPI Lite, and delegate-link rules. |
| `PRIMARY_ACCOUNT` | Set an account as primary for a specified VPA, or for all VPAs when `customerVpa` is omitted. |
| `DEFAULT_ACCOUNT` | Set an account as the customer's outward default account. |
| `CUSTOMER_INFO` | Fetch the current account/VPA/customer state. |

## Request

### Minimum Fetch Request

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "CUSTOMER_INFO",
  "iat": "1720000000000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Must be non-empty, up to 256 characters, and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. Used for merchant-customer and customer lookup before business logic runs. |
| `action` | string | Yes | No default. | Operation to perform. Allowed values are listed in [Actions](#actions). |
| `bankAccountUniqueId` | string | Conditional | No default. | Account identifier/hash returned by Newton account APIs. Required for `LINK_VPA_ACCOUNT`, `DELETE_ACCOUNT`, `ADD_ACCOUNT`, `PRIMARY_ACCOUNT`, and `DEFAULT_ACCOUNT`. Required for normal `ADD_VPA`; can be omitted for `ADD_VPA` only when `flags` contains `DelegateVpa` or `IotVpa`. Must be non-empty when supplied. |
| `customerVpa` | string | Conditional | No default. | Customer VPA. Required for `ADD_VPA` and `DELETE_VPA`. Required for `LINK_VPA_ACCOUNT` when using `SetAccountAsPrimaryForVpa`. Optional for `PRIMARY_ACCOUNT`; if omitted, Newton sets the primary account for all customer VPAs. Must be 3 to 255 characters and match `^[a-zA-Z0-9.-]{1,}@[a-zA-Z0-9.-]{1,}$`. |
| `flags` | array of strings | No | Omitted behaves as an empty list, except `DELETE_ACCOUNT` may use merchant config `isDeleteVpaWithAccount` as its fallback for deleting linked VPAs. | Action modifiers. Allowed values are listed below. |
| `udfParameters` | string | No | Omitted from response if omitted. | Merchant-defined JSON-object string. It must parse as a JSON object and must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. Echoed in the response. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used for encrypted/signed payload timestamp validation. For non-unsigned envelope modes, Newton requires this field and validates it as a timestamp. |

### Flags

| Flag | Allowed actions | Description |
| --- | --- | --- |
| `SetAccountAsPrimaryForVpa` | `LINK_VPA_ACCOUNT` | Link `bankAccountUniqueId` as primary for the specified `customerVpa`. Requires `customerVpa`. Cannot be combined with `SetAccountAsPrimaryForAllVpas`. |
| `SetAccountAsPrimaryForAllVpas` | `LINK_VPA_ACCOUNT` | Link `bankAccountUniqueId` as primary for every existing customer VPA. Cannot be combined with `SetAccountAsPrimaryForVpa`. |
| `SetAccountAsDefault` | `LINK_VPA_ACCOUNT` | Set `bankAccountUniqueId` as the outward default account while linking it. The code also sets the account as default automatically when it is the first merchant-customer account. |
| `DeleteLinkedVpas` | `DELETE_ACCOUNT` | If the account is primary for one or more VPAs, delete those VPAs and their mappings while deleting the account. Without this flag, deletion is rejected when the account is primary and the customer has other accounts. If omitted, merchant config `isDeleteVpaWithAccount` may enable the same behavior. |
| `DelegateVpa` | `ADD_VPA`, `LINK_VPA_ACCOUNT` | Marks a delegate VPA flow. For `ADD_VPA`, Newton adds/creates the VPA but skips the normal VPA-account mapping requirement. |
| `IotVpa` | `ADD_VPA` | Marks an IoT VPA flow. For `ADD_VPA`, Newton adds/creates the VPA but skips the normal VPA-account mapping requirement. |

Rules:

- `CUSTOMER_INFO` does not support any flags.
- `DelegateVpa` is rejected for every action except `ADD_VPA` and `LINK_VPA_ACCOUNT`.
- `DeleteLinkedVpas` is rejected for every action except `DELETE_ACCOUNT`.
- `SetAccountAsDefault`, `SetAccountAsPrimaryForVpa`, and `SetAccountAsPrimaryForAllVpas` are rejected for every action except `LINK_VPA_ACCOUNT`.
- `SetAccountAsPrimaryForVpa` and `SetAccountAsPrimaryForAllVpas` cannot be sent together.
- If `LINK_VPA_ACCOUNT` sends `customerVpa`, it must also send either `SetAccountAsPrimaryForVpa` or `SetAccountAsPrimaryForAllVpas`.

## Request Examples

### Add VPA and Link to Account

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ADD_VPA",
  "bankAccountUniqueId": "bankacc_hash_001",
  "customerVpa": "customer123@upi",
  "iat": "1720000000000",
  "udfParameters": "{\"source\":\"checkout\"}"
}
```

Newton validates VPA syntax and customer VPA rules, checks VPA availability, creates or reuses the VPA, and creates/updates the primary VPA-account mapping for the supplied account.

### Add Delegate VPA

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ADD_VPA",
  "customerVpa": "delegate.customer123@upi",
  "flags": ["DelegateVpa"],
  "iat": "1720000000000"
}
```

For `DelegateVpa`, `bankAccountUniqueId` is not required and Newton does not create the normal VPA-account mapping in `ADD_VPA`.

### Add IoT VPA

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ADD_VPA",
  "customerVpa": "device.customer123@upi",
  "flags": ["IotVpa"],
  "iat": "1720000000000"
}
```

For `IotVpa`, `bankAccountUniqueId` is not required and Newton stores the VPA with the IoT marker.

### Add Account

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ADD_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "iat": "1720000000000"
}
```

Newton finds the existing customer account by `bankAccountUniqueId`, creates the merchant-customer account mapping if needed, and returns the updated account/VPA state.

### Link Account to All VPAs

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "LINK_VPA_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "flags": ["SetAccountAsPrimaryForAllVpas"],
  "iat": "1720000000000"
}
```

Newton creates or updates the primary mapping from every existing customer VPA to the supplied account.

### Link Account to One VPA and Set Default

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "LINK_VPA_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "customerVpa": "customer123@upi",
  "flags": ["SetAccountAsPrimaryForVpa", "SetAccountAsDefault"],
  "iat": "1720000000000"
}
```

Newton creates the VPA if needed, sets the supplied account as primary for that VPA, and sets it as the outward default account.

### Delete VPA

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DELETE_VPA",
  "customerVpa": "customer123@upi",
  "iat": "1720000000000"
}
```

Newton rejects the request if the VPA has active mandates or active delegate links. If allowed, it deletes the VPA, deletes its VPA-account mappings, and asynchronously deletes related UPI numbers.

### Delete Account Only

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DELETE_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "iat": "1720000000000"
}
```

Newton rejects deletion if the account is a protected default account, has active mandates, has active UPI Lite records, or is primary for a VPA while other accounts remain.

### Delete Account and Linked Primary VPAs

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DELETE_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "flags": ["DeleteLinkedVpas"],
  "iat": "1720000000000"
}
```

If the account is primary for VPAs, Newton deletes those VPAs and their VPA-account mappings before deleting the account. Active mandates, UPI Lite state, and active delegate links still block deletion.

### Set Primary Account for One VPA

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "PRIMARY_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "customerVpa": "customer123@upi",
  "iat": "1720000000000"
}
```

Newton verifies the VPA is already linked to the customer, then sets the supplied account as primary for that VPA.

### Set Primary Account for All VPAs

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "PRIMARY_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "iat": "1720000000000"
}
```

When `customerVpa` is omitted, Newton sets the supplied account as primary for all customer VPAs. If the customer has no VPAs, the request fails with `VPA_NOT_LINKED`.

### Set Default Account

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DEFAULT_ACCOUNT",
  "bankAccountUniqueId": "bankacc_hash_002",
  "iat": "1720000000000"
}
```

Newton sets the supplied account as the outward default account and returns the updated default `bankAccountUniqueId`.

### Fetch Customer Info

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "CUSTOMER_INFO",
  "iat": "1720000000000"
}
```

Newton returns current accounts, VPA primary mappings, UPI numbers, device details, and delegate info when present.

## Success Response

### Response Example

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "customerMobileNumber": "919876543210",
    "vpas": [
      {
        "vpa": "customer123@upi",
        "primaryBankAccountUniqueId": "bankacc_hash_001"
      }
    ],
    "accounts": [
      {
        "bankCode": "123456",
        "bankName": "Example Bank",
        "maskedAccountNumber": "XXXXXX7890",
        "mpinLength": "6",
        "mpinSet": "true",
        "type": "SAVINGS",
        "branchName": "MG Road",
        "bankAccountUniqueId": "bankacc_hash_001",
        "ifsc": "EXAM0001234",
        "name": "Example Bank Account",
        "otpLength": "6",
        "atmPinLength": "4",
        "aadhaarEnabled": "false",
        "bioAuthEnabled": "false"
      }
    ],
    "defaultBankAccountUniqueId": "bankacc_hash_001",
    "upiNumbers": [
      {
        "upiNumber": "9876543210",
        "upiNumberStatus": "ACTIVE",
        "vpa": "customer123@upi"
      }
    ],
    "deviceDetails": {
      "deviceFingerPrint": "device-fingerprint",
      "deviceId": "device-id",
      "manufacturer": "Example",
      "model": "Model1",
      "version": "14",
      "os": "ANDROID",
      "ssid": "ssid-value",
      "packageName": "com.example.app"
    },
    "delegateInfo": {
      "delegateVpas": ["delegate.customer123@upi"],
      "delegateLinks": [
        {
          "vpa": "customer123@upi",
          "linkedVpa": "delegate.customer123@upi",
          "linkedName": "Delegate User",
          "linkedMobileNumber": "919999999999"
        }
      ]
    }
  },
  "udfParameters": "{\"source\":\"checkout\"}"
}
```

Fields with no data are omitted from JSON because response serialization omits `Nothing` values.

### Top-Level Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful operations. |
| `responseCode` | string | `SUCCESS` for successful operations. |
| `responseMessage` | string | `SUCCESS` for successful operations. |
| `payload` | object | Updated customer VPA/account state. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters`, when supplied. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id from Newton merchant configuration. |
| `merchantChannelId` | string | Merchant channel id from Newton merchant configuration. |
| `merchantCustomerId` | string | Echo of request `merchantCustomerId`. |
| `customerMobileNumber` | string | Customer mobile number after PII decryption. |
| `vpas` | array of objects | Primary VPA-account mappings. Each entry contains a VPA and its primary bank account unique id. |
| `accounts` | array of objects | Customer bank accounts currently mapped to the merchant customer. Sensitive full account number is not returned. |
| `defaultBankAccountUniqueId` | string | Bank account unique id for the account marked default, when one is available. |
| `upiNumbers` | array of objects | Returned for flows that fetch UPI number data, especially `CUSTOMER_INFO`. Omitted when not loaded. |
| `deviceDetails` | object | Returned when device data is loaded, especially `CUSTOMER_INFO`. Omitted otherwise. |
| `delegateInfo` | object | Delegate VPA/link information when present. Omitted when no delegate info exists. |

### `payload.vpas[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA. |
| `primaryBankAccountUniqueId` | string | Account unique id/hash currently primary for this VPA. |

### `payload.accounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Bank code from the stored account. |
| `bankName` | string | Bank name. |
| `maskedAccountNumber` | string | Masked account number. |
| `mpinLength` | string | MPIN credential length. Code expects this value to be present in storage. |
| `mpinSet` | string | `"true"` or `"false"`. If merchant config/device store says MPIN must be set on iOS, Newton can force this to `"false"`. |
| `referenceId` | string | Always omitted in this response mapper. |
| `type` | string | Account type, for example `SAVINGS`, `CURRENT`, `DEFAULT`, `NRE`, `NRO`, `CREDIT`, `PPIWALLET`, `BANKWALLET`, `SOD`, `UOD`, `UPICREDIT`, `CREDITLINE`, `CREDITLINE01` through `CREDITLINE10`, `CL01`, `CL011` through `CL015`, or `CL02` through `CL10`. |
| `branchName` | string | Branch name when stored. |
| `bankAccountUniqueId` | string | Migrated id if present, otherwise account hash. Use this value in later `bankAccountUniqueId` requests. |
| `ifsc` | string | Account IFSC. |
| `isPrimary` | string | Always omitted in this response mapper; primary mapping is represented in `payload.vpas[].primaryBankAccountUniqueId`. |
| `name` | string | Account holder/name value from storage. |
| `otpLength` | string | SMS credential length from account credentials; defaults to `"6"` when not found in credentials. |
| `atmPinLength` | string | ATM PIN credential length from account credentials; defaults to `"4"` when not found in credentials. |
| `kycStatus` | string | Account KYC status when stored. |
| `accountNumber` | string | Omitted. Full account number is not returned. |
| `accBIN` | string | Account BIN for credit-card-style account types when derivable. |
| `aadhaarEnabled` | string | `"true"` or `"false"` from stored account state. |
| `isAadhaarNumberAvailable` | string | Always omitted in this response mapper. |
| `bankAccountHash` | string | Always omitted in this response mapper. |
| `accSubType` | string | Credit-line account subtype when stored. |
| `allowedMCC` | array of strings | Version-gated MCC allowlist for credit-line or restricted accounts. |
| `notallowedMCC` | array of strings | Version-gated MCC denylist for credit-line or restricted accounts. |
| `lrn` | string | UPI Lite reference number when mapped to the account. |
| `isInitialTopUpDone` | string | Always omitted in this response mapper. |
| `liteDetails` | object | Always omitted in this response mapper. |
| `bioAuthConsentUrl` | string | Always omitted in this response mapper. |
| `bioAuthEnabled` | string | Version-gated `"true"` or `"false"` based on stored biometric consent. |
| `credsAllowed` | string | Always omitted in this response mapper. |
| `payerAccountHash` | string | Returned only when merchant config `enablePayerAccountHash` is enabled. |

### `payload.upiNumbers[]`

| Field | Type | Description |
| --- | --- | --- |
| `expiry` | string | Expiry timestamp when present. |
| `upiNumber` | string | UPI number. |
| `upiNumberStatus` | string | UPI number status text, for example `ACTIVE` or pending states mapped by the customer helper. |
| `vpa` | string | VPA associated with the UPI number. |

### `payload.deviceDetails`

| Field | Type | Description |
| --- | --- | --- |
| `deviceFingerPrint` | string | Device fingerprint after PII decryption. |
| `deviceId` | string | Newton device id. |
| `manufacturer` | string | Device manufacturer. |
| `model` | string | Device model. |
| `version` | string | OS/app version value stored for the device. |
| `os` | string | Device OS. |
| `ssid` | string | Device SSID after PII decryption. |
| `packageName` | string | Merchant customer's package name. |

### `payload.delegateInfo`

| Field | Type | Description |
| --- | --- | --- |
| `delegateVpas` | array of strings | Delegate VPAs for the merchant customer. |
| `delegateLinks` | array of objects | Active or stored delegate-link details when present. |

### `payload.delegateInfo.delegateLinks[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Delegator VPA. |
| `linkedVpa` | string | Linked delegatee VPA. |
| `linkedName` | string | Linked customer display name when stored. |
| `linkedMobileNumber` | string | Linked customer's mobile number after PII decryption. |
| `fullDelegationDetails` | object | Included by delegate-link code when full delegation metadata is present. |

## Failure Responses and Client Handling

Failure responses usually use the same encrypted/signed response transport as success responses. If the failure occurs before Newton can build the configured envelope, HTTP status and outer wrapping can vary by deployment. The examples below show the underlying decrypted JSON shape.

### Validation Failures

Newton returns `BAD_REQUEST` for field-validation failures after decrypting the payload.

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| Empty `merchantCustomerId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId field is empty\""}` | Fix the request. Do not retry unchanged. |
| Invalid `customerVpa` syntax | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"customerVpa regex failed\""}` | Ask the customer to provide a valid VPA and retry with corrected input. |
| `DELETE_VPA` without `customerVpa` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"customerVpa is mandatory for DELETE_VPA\""}` | Send `customerVpa`. |
| `LINK_VPA_ACCOUNT` or `DELETE_ACCOUNT` without `bankAccountUniqueId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"bankAccountUniqueId is mandatory forLINK_VPA_ACCOUNT\""}` | Send a `bankAccountUniqueId` returned by Newton. The code concatenates `for` and the action without a space. |
| `CUSTOMER_INFO` with flags | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"no flags supported for action CUSTOMER_INFO\""}` | Remove `flags`. |
| Invalid flag/action combination | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"invalid flag DeleteLinkedVpas for action ADD_VPA\""}` | Use the flag only with its allowed action. |
| Both primary flags are sent | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"invalid flags: only one of SetAccountAsPrimaryForVpa or SetAccountAsPrimaryForAllVpas can be passed\""}` | Send only one primary-linking flag. |
| `SetAccountAsPrimaryForVpa` without `customerVpa` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"customerVpa is mandatory for flag SetAccountAsPrimaryForVpa\""}` | Send `customerVpa`. |
| Invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` | Send a valid JSON-object string using allowed characters. |

### Auth, Envelope, API Access, and IP Failures

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| Missing merchant headers, missing raw body, missing timestamp, bad signature, or timestamp outside allowed skew | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Recompute headers/signature, verify timestamp freshness, and retry only after fixing auth material. |
| API blocked or not allowed for merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Contact Newton onboarding/support to enable the requested action, such as `manageVpaAccount-DELETE_ACCOUNT`, for the merchant profile. |
| IP not allowlisted or missing `x-forwarded-for` when `whitelistedIps` is configured | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Send traffic from an allowlisted IP and include `x-forwarded-for` as configured. |
| Encrypted/signed payload missing `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` | Include a valid `iat` in the decrypted business payload and rebuild the envelope. |

### Lookup and Context Failures

These failures happen after merchant auth, when Newton resolves customer, merchant customer, account, VPA, and device records.

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| Unknown or inactive `merchantCustomerId` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid merchantSignatureVerificationV2"}` | Verify the customer has been onboarded for the same merchant/channel. Exact message can vary by lookup helper. |
| `bankAccountUniqueId` does not match a customer account | `{"status":"FAILURE","responseCode":"ACCOUNT_NOT_FOUND","responseMessage":"Account not found"}` | Refresh customer account state and use a returned `bankAccountUniqueId`. |
| `PRIMARY_ACCOUNT` for a VPA not linked to the customer | `{"status":"FAILURE","responseCode":"VPA_NOT_LINKED","responseMessage":"customerVpa passed is not linked with customer"}` | Fetch customer info, then retry with one of the returned VPAs or add the VPA first. |
| `PRIMARY_ACCOUNT` with no `customerVpa` when the customer has no VPAs | `{"status":"FAILURE","responseCode":"VPA_NOT_LINKED","responseMessage":"no vpas linked with customer"}` | Add a VPA before setting primary account. |
| Required merchant-customer/account context is missing in storage | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"Internal Server Error"}` | Refresh customer state, verify the customer was onboarded successfully, and raise to Newton if the record exists on your side but cannot be resolved. |

### Business-Rule Failures

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| VPA is unavailable or belongs to another merchant customer | `{"status":"FAILURE","responseCode":"VPA_NOT_AVAILABLE","responseMessage":"CustomerVpa not available"}` | Ask the customer for another VPA or fetch current linked VPAs. Do not retry the same new VPA unchanged. |
| VPA already exists with a different primary account | `{"status":"FAILURE","responseCode":"DUPLICATE_VPA","responseMessage":"customerVpa passed is already added"}` | Treat as a conflict. Fetch customer info and decide whether to link/change primary account. |
| `LINK_VPA_ACCOUNT` sends `customerVpa` without a primary flag | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"primary account flags is mandatory if customerVpa is passed"}` | Add `SetAccountAsPrimaryForVpa` or `SetAccountAsPrimaryForAllVpas`. |
| Deleting a VPA with active delegate links | `{"status":"FAILURE","responseCode":"JPADL","responseMessage":"You have active DelegateLink(s). Please try again after all the links are delinked"}` | Delink active delegate links first. |
| Deleting a VPA or account with active mandates | `{"status":"FAILURE","responseCode":"JPDL","responseMessage":"You have active mandate(s). Please try again after all the mandates are executed or revoked"}` | Wait for mandates to execute/revoke, then retry. |
| Deleting a default account when config does not allow it | `{"status":"FAILURE","responseCode":"OPERATION_RESTRICTED_DEFAULT_ACCOUNT","responseMessage":"Default account of the customer cannot be deleted"}` | Set another default account first, or request merchant config change. |
| Deleting an account that is primary for a VPA while other accounts remain | `{"status":"FAILURE","responseCode":"OPERATION_RESTRICTED_PRIMARY_ACCOUNT","responseMessage":"Primary account of the vpa cannot be deleted"}` | Send `DeleteLinkedVpas`, change the VPA's primary account, or delete other accounts as appropriate. |
| Deleting an account with active UPI Lite state | `{"status":"FAILURE","responseCode":"JPLA","responseMessage":"LITE_ACCOUNT_ACTIVE"}` | Deactivate/close UPI Lite for that account before deletion. |

### Downstream, Storage, and Unexpected Failures

This endpoint is primarily database/Passetto/internal-helper driven. It does not make an NPCI transactional call for the core VPA/account mutation, but it can fail on storage, Redis/cache, PII encryption/decryption, or async helper setup.

| Scenario | Example decrypted body | Client handling |
| --- | --- | --- |
| Internal lookup/decryption/storage error | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"Internal Server Error"}` | Retry with backoff if the operation is safe for your action, then raise to Newton if it persists. |
| Timeout/service unavailability from shared infrastructure | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE","responseMessage":"UPI service is not reachable at the moment"}` | Retry with exponential backoff and jitter. |
| Malformed envelope or JSON parse failure before business payload is available | HTTP `400` or `401` with an error body that may not be encrypted | Fix serialization/encryption/signing. Do not retry unchanged. |

## Retry and Idempotency Guidance

- This request does not have a `merchantRequestId`; use the current customer state returned by the API as your idempotency anchor.
- `ADD_VPA` is partly idempotent. If the VPA already exists for the same merchant customer and the same account is primary, Newton returns success. If the same VPA is tied to another account or merchant customer, Newton returns `DUPLICATE_VPA` or `VPA_NOT_AVAILABLE`.
- `ADD_ACCOUNT`, `LINK_VPA_ACCOUNT`, `PRIMARY_ACCOUNT`, and `DEFAULT_ACCOUNT` are safe to retry after network timeouts because the target state is deterministic.
- `DELETE_VPA` is mostly safe to retry. If the VPA is already inactive/deleted, the route returns the current remaining state.
- `DELETE_ACCOUNT` is stateful. Retry only after checking the latest `CUSTOMER_INFO` response, especially when using `DeleteLinkedVpas`, because linked VPAs may have been deleted on the first attempt.
- Do not retry validation, auth, API-disabled, or business-rule failures unchanged.
- For transient `INTERNAL_SERVER_ERROR`, service-unavailable, or timeout responses, use bounded exponential backoff with jitter and reconcile with `CUSTOMER_INFO` before issuing another mutation.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:707)
- Route handler, auth, and transformer call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:5069)
- Envelope request/response types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:10)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:31)
- Request, response, action, flag, and validation types: [src/Newton/Types/API/ServerToServer/VpaAccountManagment.hs](../../src/Newton/Types/API/ServerToServer/VpaAccountManagment.hs:29)
- Dispatcher and shared route flow: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:556)
- `ADD_VPA`, `PRIMARY_ACCOUNT`, and `DEFAULT_ACCOUNT` logic: [src/Newton/Product/Merchant/VpaAccount/ManageVpaAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/ManageVpaAccount.hs:38)
- `ADD_ACCOUNT` logic: [src/Newton/Product/Merchant/VpaAccount/AddAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/AddAccount.hs:24)
- `LINK_VPA_ACCOUNT` logic: [src/Newton/Product/Merchant/VpaAccount/LinkVpaAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/LinkVpaAccount.hs:34)
- `DELETE_VPA` logic: [src/Newton/Product/Merchant/VpaAccount/DeleteVpa.hs](../../src/Newton/Product/Merchant/VpaAccount/DeleteVpa.hs:35)
- `DELETE_ACCOUNT` logic: [src/Newton/Product/Merchant/VpaAccount/DeleteAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/DeleteAccount.hs:37)
- `CUSTOMER_INFO` logic: [src/Newton/Product/Merchant/VpaAccount/CustomerInfo.hs](../../src/Newton/Product/Merchant/VpaAccount/CustomerInfo.hs:26)
- Response decryption and assembly: [src/Newton/Product/Merchant/Delegates/Helper.hs](../../src/Newton/Product/Merchant/Delegates/Helper.hs:772)
- Response mapper and account/VPA response fields: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:5158)
- Account and VPA response object types: [src/Newton/Types/API/Account.hs](../../src/Newton/Types/API/Account.hs:12)
- UPI number and device response object types: [src/Newton/Product/Merchant/Customer/Types.hs](../../src/Newton/Product/Merchant/Customer/Types.hs:112)
- Delegate response object types: [src/Newton/Product/Merchant/Delegates/Types.hs](../../src/Newton/Product/Merchant/Delegates/Types.hs:312)
- Common request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Validation failure response mapping: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Shared success and business error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
