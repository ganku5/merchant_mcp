# VPA Accounts API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpaAccounts`

## Overview

VPA Accounts is a server-to-server API used to manage the customer-side relationship between a Newton merchant customer, customer VPAs, and discovered bank accounts.

The merchant calls this action-based API after the customer profile already exists in Newton. Depending on `action`, Newton can add a VPA, add an account to the merchant-customer profile, link an account to one or more VPAs, set the outward/default account, set the primary account for VPA mappings, delete a VPA, delete an account, or fetch the current customer VPA/account snapshot.

Use this API when the merchant backend needs to keep Newton's local customer VPA/account state in sync with the merchant app. This API does not collect payment, approve collect requests, fetch balance, set MPIN, generate OTP, or initiate a bank/NPCI debit.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

VPA Accounts helps merchants:

- Create or reuse a customer VPA under a merchant customer profile.
- Add an already discovered bank account to the merchant customer.
- Link a bank account as the primary account for one VPA or all customer VPAs.
- Mark an account as the outward/default account for future debit flows.
- Delete VPAs or accounts when the customer removes them from the merchant app.
- Fetch the latest Newton-side account, VPA, UPI number, device, and delegate-link state for the customer.
- Support delegate and IoT VPA variants where a VPA can be created without immediately creating a normal VPA-account primary mapping.

This API updates Newton storage and returns the resulting customer snapshot. It does not directly call NPCI for account discovery, balance, credential, or payment authorization.

## Integration Flow

1. Merchant registers or resolves the customer with Newton and obtains `merchantCustomerId`.
2. Merchant discovers or stores the customer's bank-account identifier from onboarding/account APIs.
3. Merchant chooses the required VPA-account operation and sends `action` with the required fields and optional `flags`.
4. Newton verifies the encrypted/signed S2S request, merchant headers, timestamp, API access, merchant customer, and customer context.
5. Newton validates request shape, optional VPA format, and action-specific rules.
6. Newton performs the requested local VPA/account operation.
7. Newton returns a `SUCCESS` response with a VPA/account snapshot, plus action-dependent optional details.
8. Merchant stores the returned `bankAccountUniqueId`, `vpas[].primaryBankAccountUniqueId`, `defaultBankAccountUniqueId`, and optional device/UPI-number/delegate details for follow-up APIs.

Important identifiers:

- `merchantCustomerId`: Merchant's customer id. It scopes authentication lookup and all VPA/account operations.
- `bankAccountUniqueId`: Merchant-facing account hash or migrated account identifier returned by account APIs.
- `customerVpa`: Customer VPA to add, delete, link, or use as the primary-account mapping target.
- `action`: The operation Newton should run.
- `flags`: Optional modifiers for selected actions.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpaAccounts
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | `4` recommended for new integrations. Controls response fields such as `accounts[].bioAuthEnabled`; request validation for this API is not versioned. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within 30 minutes of Newton's clock. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding. Required for unsigned-payload traffic that relies on merchant signature verification. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. Signed/encrypted calls must include valid merchant headers, timestamp, signature or encrypted/signed envelope, and API access for `manageVpaAccount-{ACTION}` where `{ACTION}` is the request action.

The decrypted business payload should include `iat` for signed/encrypted requests. Plain unsigned test payloads can omit `iat` only when that request mode is enabled for the environment.

### Path and Version Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route version segment. Use the value shared during onboarding. |
| `x-api-version` | header | integer string | Recommended | Response-field version. Missing or non-numeric values fall back through Newton's shared version resolver. |

### Response Version Behavior

The request validator for this endpoint does not branch on `x-api-version`, but the account response transformer does gate a few fields:

| `x-api-version` | Response behavior |
| --- | --- |
| Missing, invalid, or `0` | Base payload fields. `accounts[].allowedMCC`, `accounts[].notallowedMCC`, and `accounts[].bioAuthEnabled` are omitted. |
| `1`, `2`, or `3` | Base fields plus `accounts[].allowedMCC` and `accounts[].notallowedMCC` when the account has MCC restrictions. |
| `4` and above | Version `1` fields plus `accounts[].bioAuthEnabled` when biometric consent data exists. |

Other optional fields such as `upiNumbers`, `deviceDetails`, `delegateInfo`, `accounts[].lrn`, and `accounts[].payerAccountHash` are driven by action, stored data, and merchant configuration rather than this endpoint's response-version gate.

## Request

Route request type: `API.EncRequest API.ManageVpaAccountsRequest`

Decrypted business payload type: `API.ManageVpaAccountsRequest`

### Required Minimum by Action

`merchantCustomerId` and `action` are always required at type level.

| Action | Minimum request fields | Typical use |
| --- | --- | --- |
| `ADD_VPA` | `merchantCustomerId`, `action`, `customerVpa`, and usually `bankAccountUniqueId` | Create/reuse a customer VPA and, for normal VPAs, create/update its primary account mapping. |
| `DELETE_VPA` | `merchantCustomerId`, `action`, `customerVpa` | Delete one customer VPA and its VPA-account mappings. |
| `ADD_ACCOUNT` | `merchantCustomerId`, `action`, `bankAccountUniqueId` | Add an account to the merchant-customer account list without changing VPA primary mappings. |
| `CUSTOMER_INFO` | `merchantCustomerId`, `action` | Fetch the current VPA/account snapshot. |
| `DELETE_ACCOUNT` | `merchantCustomerId`, `action`, `bankAccountUniqueId` | Remove an account from the merchant customer, subject to default/primary/mandate/Lite/delegate restrictions. |
| `PRIMARY_ACCOUNT` | `merchantCustomerId`, `action`, `bankAccountUniqueId` | Make an account primary for one VPA when `customerVpa` is sent, or for all customer VPAs when omitted. |
| `DEFAULT_ACCOUNT` | `merchantCustomerId`, `action`, `bankAccountUniqueId` | Make an account the outward/default account. |
| `LINK_VPA_ACCOUNT` | `merchantCustomerId`, `action`, `bankAccountUniqueId`; add `customerVpa` plus a primary flag when creating or mapping a VPA | Link a bank account into the merchant customer and optionally map it as primary for a VPA or all VPAs. |

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. This endpoint's request validator only checks that it is non-empty; middleware uses it to resolve the merchant customer and customer. |
| `action` | string enum | Yes | No default. | Operation to perform. Allowed values: `ADD_VPA`, `DELETE_VPA`, `ADD_ACCOUNT`, `CUSTOMER_INFO`, `DELETE_ACCOUNT`, `PRIMARY_ACCOUNT`, `DEFAULT_ACCOUNT`, `LINK_VPA_ACCOUNT`. |
| `bankAccountUniqueId` | string | Conditional | No default. | Account hash or migrated account identifier returned by account APIs. Required by validation for `LINK_VPA_ACCOUNT` and `DELETE_ACCOUNT`; required by product logic for `ADD_ACCOUNT`, normal `ADD_VPA`, `PRIMARY_ACCOUNT`, and `DEFAULT_ACCOUNT`. |
| `customerVpa` | string | Conditional | No default. | Customer VPA. Required for `ADD_VPA`, `DELETE_VPA`, and `LINK_VPA_ACCOUNT` when `SetAccountAsPrimaryForVpa` is sent. Optional for `PRIMARY_ACCOUNT`; if omitted, Newton updates all customer VPAs. |
| `flags` | array of string enums | No | No default. Omit when no modifier is needed. | Optional modifiers. Allowed values: `SetAccountAsPrimaryForVpa`, `SetAccountAsPrimaryForAllVpas`, `SetAccountAsDefault`, `DeleteLinkedVpas`, `DelegateVpa`, `IotVpa`. |
| `udfParameters` | string | No | Omitted from response if not supplied. | JSON-object string for merchant metadata. Echoed in the success response. Must parse as a JSON object string and pass Newton's allowed-character check. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Unsigned plain test payloads skip IAT validation only when that request type is enabled. | Issued-at timestamp used for request freshness validation. Send a 13-digit epoch-milliseconds value within 30 minutes of Newton's clock. |

### Actions

| Action | Processing behavior |
| --- | --- |
| `ADD_VPA` | Validates and creates/reuses `customerVpa`. For a normal VPA, `bankAccountUniqueId` is required and Newton creates or updates the primary VPA-account mapping for that VPA. With `DelegateVpa` or `IotVpa`, Newton creates the VPA but skips the normal account-primary mapping step. |
| `DELETE_VPA` | Validates `customerVpa`, blocks deletion when active delegate links or active mandates exist, soft-deletes the VPA and its VPA-account mappings, and asynchronously removes related UPI-number mappings. |
| `ADD_ACCOUNT` | Finds the account by `bankAccountUniqueId`, creates/reuses the merchant-customer-account record, and returns the current VPA/account state. It does not create a VPA or VPA-account mapping. |
| `CUSTOMER_INFO` | Read-only fetch of accounts, VPAs, VPA-account mappings, active UPI Lite records, UPI numbers, device details, and delegate info for the merchant customer. |
| `DELETE_ACCOUNT` | Soft-deletes the merchant-customer-account record after validating default-account, primary-account, mandate, UPI Lite, and delegate-link restrictions. `DeleteLinkedVpas` can allow deleting primary linked VPAs with the account. |
| `PRIMARY_ACCOUNT` | Makes `bankAccountUniqueId` primary for `customerVpa` when supplied. If `customerVpa` is omitted, makes the account primary for all customer VPAs. |
| `DEFAULT_ACCOUNT` | Makes `bankAccountUniqueId` the outward/default account for the merchant customer. |
| `LINK_VPA_ACCOUNT` | Creates/reuses the account relationship, optionally creates `customerVpa`, optionally sets the account as outward/default, and optionally maps it as primary for one VPA or all VPAs. |

### Flags

| Flag | Valid with | Behavior |
| --- | --- | --- |
| `SetAccountAsPrimaryForVpa` | `LINK_VPA_ACCOUNT` | Requires `customerVpa`. Creates/reuses that VPA and makes `bankAccountUniqueId` primary for that VPA only. Cannot be combined with `SetAccountAsPrimaryForAllVpas`. |
| `SetAccountAsPrimaryForAllVpas` | `LINK_VPA_ACCOUNT` | Makes `bankAccountUniqueId` primary for all existing customer VPAs. Cannot be combined with `SetAccountAsPrimaryForVpa`. |
| `SetAccountAsDefault` | `LINK_VPA_ACCOUNT` | Sets `bankAccountUniqueId` as the outward/default account. |
| `DeleteLinkedVpas` | `DELETE_ACCOUNT` | When deleting a primary account, also delete the VPAs that are primarily linked to that account, unless blocked by active delegate links or other restrictions. |
| `DelegateVpa` | `ADD_VPA`, `LINK_VPA_ACCOUNT` | Accepted by validation for these actions. Current product logic uses it on `ADD_VPA`, where Newton skips normal VPA-account primary mapping. |
| `IotVpa` | Intended for `ADD_VPA` | For `ADD_VPA`, Newton creates an IoT-style VPA and skips normal VPA-account primary mapping. Current request validation does not reject this flag on other actions, but those actions do not use it. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `bankAccountUniqueId`: no default. Newton can resolve a migrated account id to the active bank account unique id before validation/processing. Missing values fail either request validation or action logic depending on `action`.
- `customerVpa`: no default. For `PRIMARY_ACCOUNT`, omission means "apply this primary account to all customer VPAs." For `LINK_VPA_ACCOUNT`, omission is allowed only when not trying to create/map one specific VPA.
- `flags`: omitted behaves like an empty modifier list. For `DELETE_ACCOUNT`, if `DeleteLinkedVpas` is omitted, Newton falls back to merchant configuration `isDeleteVpaWithAccount`.
- `SetAccountAsDefault`: for `LINK_VPA_ACCOUNT`, the selected account is also set as default when this flag is sent. If the customer has no merchant-customer-account records yet, the first linked account can become default by behavior even without the flag.
- `udfParameters`: echoed only on success and only when supplied.
- `payload` in failures is omitted when the error has no payload.

### Validation Notes

- `merchantCustomerId` must be non-empty.
- `action` must be one of the supported enum values.
- `bankAccountUniqueId`, when supplied, must be non-empty.
- `customerVpa`, when supplied, must be 3 to 255 characters and match `local@handle` with letters, numbers, dots, or hyphens on both sides of `@`.
- `customerVpa` is also validated against merchant/customer VPA rules. Mobile-number based VPAs must match the customer's registered mobile number. The VPA handle must match the configured merchant/default VPA domain.
- `LINK_VPA_ACCOUNT` and `DELETE_ACCOUNT` require `bankAccountUniqueId` at request-validation time.
- `DELETE_VPA` requires `customerVpa` at request-validation time.
- `CUSTOMER_INFO` does not support a non-empty `flags` array.
- `SetAccountAsPrimaryForVpa` and `SetAccountAsPrimaryForAllVpas` are mutually exclusive.
- `SetAccountAsPrimaryForVpa` requires `customerVpa`.
- `SetAccountAsDefault`, `SetAccountAsPrimaryForVpa`, and `SetAccountAsPrimaryForAllVpas` are valid only for `LINK_VPA_ACCOUNT`.
- `DeleteLinkedVpas` is valid only for `DELETE_ACCOUNT`.
- `DelegateVpa` is valid only for `ADD_VPA` and `LINK_VPA_ACCOUNT`.
- `udfParameters` must be a JSON object encoded as a string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick.

## Request Examples

### Add a Normal VPA and Primary Account Mapping

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ADD_VPA",
  "bankAccountUniqueId": "BANKACC123",
  "customerVpa": "cust.pay@bank",
  "iat": "1735689600000",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Add a Delegate VPA Without Normal Account Mapping

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ADD_VPA",
  "customerVpa": "cust.delegate@bank",
  "flags": [
    "DelegateVpa"
  ],
  "iat": "1735689600000"
}
```

### Link an Account and Make It Primary for One VPA

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "LINK_VPA_ACCOUNT",
  "bankAccountUniqueId": "BANKACC123",
  "customerVpa": "cust.pay@bank",
  "flags": [
    "SetAccountAsPrimaryForVpa",
    "SetAccountAsDefault"
  ],
  "iat": "1735689600000"
}
```

### Link an Account as Primary for All VPAs

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "LINK_VPA_ACCOUNT",
  "bankAccountUniqueId": "BANKACC456",
  "flags": [
    "SetAccountAsPrimaryForAllVpas"
  ],
  "iat": "1735689600000"
}
```

### Add an Account Without Changing VPA Mappings

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "ADD_ACCOUNT",
  "bankAccountUniqueId": "BANKACC456",
  "iat": "1735689600000"
}
```

### Set Primary Account for All VPAs

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "PRIMARY_ACCOUNT",
  "bankAccountUniqueId": "BANKACC456",
  "iat": "1735689600000"
}
```

### Set Default Account

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DEFAULT_ACCOUNT",
  "bankAccountUniqueId": "BANKACC456",
  "iat": "1735689600000"
}
```

### Fetch Customer VPA and Account State

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "CUSTOMER_INFO",
  "iat": "1735689600000"
}
```

### Delete a VPA

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DELETE_VPA",
  "customerVpa": "cust.pay@bank",
  "iat": "1735689600000"
}
```

### Delete an Account and Its Primary Linked VPAs

```json
{
  "merchantCustomerId": "CUST12345",
  "action": "DELETE_ACCOUNT",
  "bankAccountUniqueId": "BANKACC456",
  "flags": [
    "DeleteLinkedVpas"
  ],
  "iat": "1735689600000"
}
```

## Processing Behavior

### Common Processing

For every action, Newton:

1. Decrypts or validates the server-to-server envelope.
2. Verifies merchant headers, signature, `iat`, `x-timestamp`, IP allowlist, and API access for `manageVpaAccount-{ACTION}`.
3. Resolves `merchantCustomerId` to a merchant customer and customer.
4. Resolves migrated account ids for `bankAccountUniqueId` where applicable.
5. Runs request validation.
6. Applies merchant/customer VPA rules when `customerVpa` is supplied.
7. Runs the action-specific product logic.
8. Decrypts PII for the response and returns the action's account/VPA snapshot.

### VPA Creation and Availability

For `ADD_VPA` and `LINK_VPA_ACCOUNT` with `customerVpa`, Newton normalizes and hashes the VPA before checking availability.

- A VPA already assigned to another active merchant customer is rejected.
- A normalized VPA collision, such as a dot/case variant already existing for another merchant customer, is rejected.
- A deactivated VPA can be reclaimed only when the configured reclaim rules allow it.
- A blocked deactivated VPA is treated as unavailable.
- If the merchant customer has no device id, a newly created normal VPA can be stored as receive-only/restricted-pay. `IotVpa` can create an enabled IoT VPA path.

### Account Linking and Defaulting

`bankAccountUniqueId` is resolved against the customer account table. `ADD_ACCOUNT` and `LINK_VPA_ACCOUNT` create or reuse the merchant-customer-account record for the selected account. `SetAccountAsDefault` on `LINK_VPA_ACCOUNT`, or first-account behavior, can set the account as outward/default.

`PRIMARY_ACCOUNT` and primary flags on `LINK_VPA_ACCOUNT` create or update VPA-account primary mappings. If `PRIMARY_ACCOUNT` receives `customerVpa`, only that VPA is updated. If `customerVpa` is omitted, all customer VPAs are updated.

### Delete Behavior

`DELETE_VPA` fails when the VPA has active delegate links or active mandates. On success, Newton soft-deletes the VPA and its VPA-account mappings and starts asynchronous UPI-number cleanup.

`DELETE_ACCOUNT` fails when deletion would violate configured account restrictions:

- Default account deletion is blocked when `allowDeletionOfDefaultAccount` is not enabled and the customer has another active account.
- Active mandates on the account block deletion.
- Active UPI Lite state on the account blocks deletion.
- A primary account for a VPA is blocked when there are other accounts unless `DeleteLinkedVpas` or merchant configuration `isDeleteVpaWithAccount` allows deleting linked VPAs too.
- When linked VPAs are being deleted with the account, active delegate links on those VPAs block deletion.

The account delete path soft-deletes the merchant-customer-account mapping. It does not physically delete the bank account record. The response `accounts` list is built from the remaining active accounts. When `DELETE_ACCOUNT` also deletes linked VPAs, the delete path does not refetch the VPA list after deletion, so call `CUSTOMER_INFO` after success if your client needs a freshly reconciled VPA list.

## Response

Route response type: `RespHeaders (API.EncResponse API.ManageVpaAccountsResponse)`

Decrypted business response type: `API.ManageVpaAccountsResponse`

### Success Response Example

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
    "vpas": [
      {
        "vpa": "cust.pay@bank",
        "primaryBankAccountUniqueId": "BANKACC123"
      }
    ],
    "accounts": [
      {
        "bankCode": "123456",
        "bankName": "Example Bank",
        "maskedAccountNumber": "XXXXXX1234",
        "mpinLength": "6",
        "mpinSet": "true",
        "type": "SAVINGS",
        "branchName": "Main Branch",
        "bankAccountUniqueId": "BANKACC123",
        "ifsc": "EXAM0001234",
        "name": "Customer Name",
        "otpLength": "6",
        "atmPinLength": "4",
        "aadhaarEnabled": "false",
        "bioAuthEnabled": "false"
      }
    ],
    "defaultBankAccountUniqueId": "BANKACC123"
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Customer Info Response With Optional Data

`CUSTOMER_INFO` can include `upiNumbers` and `deviceDetails` when stored for the merchant customer. `delegateInfo` can be present on any action response when delegate data exists.

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
    "vpas": [
      {
        "vpa": "cust.pay@bank",
        "primaryBankAccountUniqueId": "BANKACC123"
      },
      {
        "vpa": "cust.delegate@bank",
        "primaryBankAccountUniqueId": "BANKACC123"
      }
    ],
    "accounts": [
      {
        "bankCode": "123456",
        "bankName": "Example Bank",
        "maskedAccountNumber": "XXXXXX1234",
        "mpinLength": "6",
        "mpinSet": "true",
        "type": "SAVINGS",
        "bankAccountUniqueId": "BANKACC123",
        "ifsc": "EXAM0001234",
        "name": "Customer Name",
        "otpLength": "6",
        "atmPinLength": "4",
        "aadhaarEnabled": "false",
        "lrn": "LRN123456",
        "bioAuthEnabled": "false",
        "payerAccountHash": "PAYERHASH123"
      }
    ],
    "defaultBankAccountUniqueId": "BANKACC123",
    "upiNumbers": [
      {
        "expiry": "2026-12-31 23:59:59",
        "upiNumber": "9876543210",
        "upiNumberStatus": "ACTIVE",
        "vpa": "cust.pay@bank"
      }
    ],
    "deviceDetails": {
      "deviceFingerPrint": "DEVICE-FINGERPRINT-123",
      "deviceId": "DEVICE-FINGERPRINT-123",
      "manufacturer": "ExamplePhone",
      "model": "Model X",
      "version": "14",
      "os": "ANDROID",
      "ssid": "DEVICE-SSID-123",
      "packageName": "com.example.merchant"
    },
    "delegateInfo": {
      "delegateVpas": [
        "cust.delegate@bank"
      ],
      "delegateLinks": [
        {
          "vpa": "cust.pay@bank",
          "linkedVpa": "family.member@bank",
          "linkedName": "Family Member",
          "linkedMobileNumber": "9123456789",
          "linkType": "FULL",
          "userType": "DELEGATEE",
          "status": "LINKED"
        }
      ]
    }
  }
}
```

The optional `delegateLinks` object is built from stored delegate-link metadata. Exact link fields can vary with delegate-link type and stored state; clients should preserve unknown fields if they cache the object.

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Present on success. Omitted on most failures. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied and the operation succeeds. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id associated with the request headers. |
| `merchantChannelId` | string | Merchant channel id associated with the request headers. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number after PII decryption. |
| `vpas` | array of objects | Current primary VPA-account mappings that can be resolved from stored VPA-account records. |
| `accounts` | array of objects | Current active accounts for the merchant customer after PII decryption and response transformation. |
| `defaultBankAccountUniqueId` | string | Bank-account unique id for the account marked default/outward when available. Omitted when no default account can be resolved. |
| `upiNumbers` | array of objects | UPI-number mappings. Returned when the action path supplies UPI-number details, currently `CUSTOMER_INFO`. |
| `deviceDetails` | object | Registered device details. Returned when the action path supplies a device, currently `CUSTOMER_INFO`, and required stored device fields are present. |
| `delegateInfo` | object | Delegate VPA and delegate-link details when available for the merchant customer. |

### `vpas[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA. |
| `primaryBankAccountUniqueId` | string | Primary bank-account unique id for this VPA mapping. Uses the migrated id when available, otherwise the account hash. |

### `accounts[]`

| Field | Type | Version / condition | Description |
| --- | --- | --- | --- |
| `bankCode` | string | Always when account is returned. | Bank code. |
| `bankName` | string | Always when account is returned. | Bank name. |
| `maskedAccountNumber` | string | Always when account is returned. | Masked account number safe for display. |
| `mpinLength` | string | Always when account is returned. | MPIN credential length. |
| `mpinSet` | string | Always when account is returned. | `"true"` or `"false"`. Can be forced to `"false"` by merchant config `setMpinRequiredForIos`. |
| `referenceId` | string | Not populated by this endpoint's current response transformer. | Reserved account reference id field in the shared account type. |
| `type` | string | Always when account is returned. | Account type stored for the account, for example `SAVINGS`, `CURRENT`, or credit-account values. |
| `branchName` | string | Account dependent. | Branch name when available. |
| `bankAccountUniqueId` | string | When account hash/migrated id exists. | Stable identifier for follow-up APIs. |
| `ifsc` | string | Always when account is returned. | Account IFSC. |
| `isPrimary` | string | Not populated by this endpoint's account list. | Primary mapping is represented in `vpas[].primaryBankAccountUniqueId`. |
| `name` | string | Always when account is returned. | Account holder name. |
| `otpLength` | string | Always when account is returned. | OTP credential length. Defaults by behavior to `"6"` when credential metadata does not override it. |
| `atmPinLength` | string | Always when account is returned. | ATM PIN credential length. Defaults by behavior to `"4"` when credential metadata does not override it. |
| `kycStatus` | string | Account dependent. | KYC status when available. |
| `accountNumber` | string | Not returned by this endpoint's current response transformer. | Raw account number is intentionally omitted. |
| `accBIN` | string | Credit-account dependent. | Account BIN computed for credit-card/credit-account transactions when available. |
| `aadhaarEnabled` | string | Always when account is returned. | `"true"` or `"false"` indicating Aadhaar OTP support. |
| `isAadhaarNumberAvailable` | string | Not populated by this endpoint's current response transformer. | Reserved shared account field. |
| `bankAccountHash` | string | Not populated by this endpoint's current response transformer. | Reserved shared account field; use `bankAccountUniqueId`. |
| `accSubType` | string | Account dependent. | Account subtype, including credit-line subtype when applicable. |
| `allowedMCC` | array of strings | Returned only when `x-api-version > 0` and MCC allow-list data exists. | Account MCC allow-list. |
| `notallowedMCC` | array of strings | Returned only when `x-api-version > 0` and MCC deny-list data exists. | Account MCC deny-list. |
| `lrn` | string | UPI Lite dependent. | Lite reference number from active UPI Lite or merchant-customer-account records when available. |
| `isInitialTopUpDone` | string | Not populated by this endpoint's current response transformer. | Reserved shared account field. |
| `liteDetails` | object | Not populated by this endpoint's current response transformer. | Reserved shared account field. |
| `bioAuthConsentUrl` | string | Not populated by this endpoint's current response transformer. | Reserved shared account field. |
| `bioAuthEnabled` | string | Returned only when `x-api-version > 3`. | `"true"` or `"false"` based on biometric consent records. |
| `credsAllowed` | string | Not populated by this endpoint's current response transformer. | Reserved shared account field. |
| `payerAccountHash` | string | Merchant config dependent. | Account-number-only hash when `enablePayerAccountHash` is enabled. |

Optional account fields are omitted rather than returned as `null`.

### `upiNumbers[]`

| Field | Type | Description |
| --- | --- | --- |
| `expiry` | string | UPI-number expiry timestamp when available. |
| `upiNumber` | string | Customer UPI number after PII decryption. |
| `upiNumberStatus` | string | Merchant-facing status such as `ACTIVE`. |
| `vpa` | string | VPA linked to the UPI number. |

### `deviceDetails`

| Field | Type | Description |
| --- | --- | --- |
| `deviceFingerPrint` | string | Device fingerprint value built from stored SSID/fingerprint. |
| `deviceId` | string | Stored decrypted device fingerprint used as device id in this payload. |
| `manufacturer` | string | Device manufacturer. |
| `model` | string | Device model. |
| `version` | string | Device OS/app version field stored for the device. |
| `os` | string | Operating system. |
| `ssid` | string | Device SSID. |
| `packageName` | string | Merchant app package name stored on the merchant customer. |

### `delegateInfo`

| Field | Type | Description |
| --- | --- | --- |
| `delegateVpas` | array of strings | Delegate VPAs for the merchant customer. |
| `delegateLinks` | array of objects | Linked delegate relationships when available. |

Delegate link objects include decrypted VPA/name/mobile fields plus stored link metadata. Common fields include `vpa`, `linkedVpa`, `linkedName`, `linkedMobileNumber`, `linkType`, `userType`, and `status`.

## Failure Responses

Failure responses use the same encrypted response transport when Newton reaches the response-envelope layer. The examples below show decrypted business bodies.

Most failures follow this shape:

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

The action-specific API name is blocked or not allowed for the merchant, for example `manageVpaAccount-ADD_VPA`:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Malformed decrypted payload JSON or an unknown enum value can return a parse failure. Parser text can vary by runtime, but the body shape is:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.action: parsing ManageVpaAccountAction failed, expected one of ADD_VPA, DELETE_VPA, ADD_ACCOUNT, CUSTOMER_INFO, DELETE_ACCOUNT, PRIMARY_ACCOUNT, DEFAULT_ACCOUNT, LINK_VPA_ACCOUNT"
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

`iat` or `x-timestamp` is outside the freshness window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

### Request Validation

Empty `merchantCustomerId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId field is empty\""
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

`customerVpa` too short or too long:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"customerVpa length is not between 3 and 255\""
}
```

`DELETE_VPA` without `customerVpa`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"customerVpa is mandatory for DELETE_VPA\""
}
```

`LINK_VPA_ACCOUNT` without `bankAccountUniqueId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"bankAccountUniqueId is mandatory forLINK_VPA_ACCOUNT\""
}
```

The missing space before `LINK_VPA_ACCOUNT` is the current validator text.

`DELETE_ACCOUNT` without `bankAccountUniqueId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"bankAccountUniqueId is mandatory forDELETE_ACCOUNT\""
}
```

Empty `bankAccountUniqueId` when supplied:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"bankAccountUniqueId field is empty\""
}
```

Invalid flag for an action:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"invalid flag SetAccountAsDefault for action ADD_VPA\""
}
```

Both primary flags sent together:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"invalid flags: only one of SetAccountAsPrimaryForVpa or SetAccountAsPrimaryForAllVpas can be passed\""
}
```

`SetAccountAsPrimaryForVpa` without `customerVpa`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"customerVpa is mandatory for flag SetAccountAsPrimaryForVpa\""
}
```

Flags supplied for `CUSTOMER_INFO`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "ValueValidation \"no flags supported for action CUSTOMER_INFO\""
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

### Merchant Customer, Customer, Account, and VPA Lookup

Merchant/customer lookup failure, missing middleware context, storage inconsistency, or PII decryption failure can surface as different messages depending on where the lookup fails. Common examples include:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

Account not found for the customer or merchant customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

`ADD_VPA`, normal path, without an account:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId is mandatory"
}
```

`PRIMARY_ACCOUNT` without a resolvable account:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid setPrimaryAccount - bankAccountUniqueId"
}
```

`DEFAULT_ACCOUNT` without `bankAccountUniqueId`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId is mandatory"
}
```

`PRIMARY_ACCOUNT` for a VPA not linked to the customer:

```json
{
  "status": "FAILURE",
  "responseCode": "VPA_NOT_LINKED",
  "responseMessage": "customerVpa passed is not linked with customer"
}
```

`PRIMARY_ACCOUNT` when the customer has no linked VPAs and no `customerVpa` was supplied:

```json
{
  "status": "FAILURE",
  "responseCode": "VPA_NOT_LINKED",
  "responseMessage": "no vpas linked with customer"
}
```

### VPA Format, Availability, and Duplicate State

VPA fails merchant/customer handle rules or mobile-number VPA does not match the customer mobile number:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "vpa is not valid"
}
```

`ADD_VPA` for an unavailable or blocked VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "VPA_NOT_AVAILABLE",
  "responseMessage": "CustomerVpa not available"
}
```

`LINK_VPA_ACCOUNT` VPA creation path for an unavailable VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Customer Vpa"
}
```

Normalized VPA collision:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Normalized VPA already exists"
}
```

`ADD_VPA` when the VPA is already added with a different primary account:

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_VPA",
  "responseMessage": "customerVpa passed is already added"
}
```

`LINK_VPA_ACCOUNT` with `customerVpa` but without a primary mapping flag:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "primary account flags is mandatory if customerVpa is passed"
}
```

### Delete Restrictions

`DELETE_VPA`, or `DELETE_ACCOUNT` with linked VPA deletion, when an active delegate link exists:

```json
{
  "status": "FAILURE",
  "responseCode": "JPADL",
  "responseMessage": "You have active DelegateLink(s). Please try again after all the links are delinked"
}
```

`DELETE_VPA` or `DELETE_ACCOUNT` when active mandates exist:

```json
{
  "status": "FAILURE",
  "responseCode": "JPDL",
  "responseMessage": "You have active mandate(s). Please try again after all the mandates are executed or revoked"
}
```

`DELETE_ACCOUNT` for a default account when default deletion is not allowed:

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_DEFAULT_ACCOUNT",
  "responseMessage": "Default account of the customer cannot be deleted"
}
```

`DELETE_ACCOUNT` for a primary VPA account when linked VPA deletion is not enabled:

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_PRIMARY_ACCOUNT",
  "responseMessage": "Primary account of the vpa cannot be deleted"
}
```

`DELETE_ACCOUNT` when the account has active UPI Lite state:

```json
{
  "status": "FAILURE",
  "responseCode": "JPLA",
  "responseMessage": "LITE_ACCOUNT_ACTIVE"
}
```

### Internal, Storage, and Crypto Failures

Unexpected storage, cache, key-service, Passetto encryption/decryption, or missing required stored PII fields can surface as:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- This API has no `merchantRequestId` idempotency key. Treat `merchantCustomerId`, `action`, `bankAccountUniqueId`, and `customerVpa` as your client-side correlation tuple.
- After any successful state-changing action, store the returned `vpas`, `accounts`, and `defaultBankAccountUniqueId` as Newton's latest response snapshot. For `DELETE_ACCOUNT` with linked VPA deletion, refresh with `CUSTOMER_INFO` before treating the VPA list as final.
- For uncertain client-side timeouts, call `CUSTOMER_INFO` before retrying a state-changing request. This avoids creating a conflicting local state based on stale assumptions.
- Do not retry validation, auth, API enablement, malformed VPA, unavailable VPA, account-not-found, active mandate, active delegate-link, active Lite, or delete-restriction failures without changing the request or resolving the underlying state.
- Retry only transient transport, storage, cache, or crypto/internal failures when your client did not receive a usable business body. Use the same action and identifiers.
- `ADD_VPA` can be effectively idempotent when the same VPA and same primary account already exist, but can return `DUPLICATE_VPA` when the VPA is already tied to a different primary account.
- `DELETE_VPA` and `DELETE_ACCOUNT` are state dependent. Refresh with `CUSTOMER_INFO` if the first attempt's outcome is unknown.
- For `DELETE_ACCOUNT`, remove or revoke active mandates, deactivate UPI Lite, and delink delegate links before retrying when those restrictions are returned.
- For `LINK_VPA_ACCOUNT`, send explicit primary/default flags. Avoid relying on omitted `flags` unless the intended operation is only to add/reuse the account relationship and fetch the snapshot.

## Source References

- Route type: [Core.hs](../../src/Newton/App/Routes/Core.hs:709)
- Route handler and auth call: [Core.hs](../../src/Newton/App/Routes/Core.hs:5069)
- Merchant signature, timestamp, API access, and merchant-customer setup: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request action, flags, request/response types, and request validation: [VpaAccountManagment.hs](../../src/Newton/Types/API/ServerToServer/VpaAccountManagment.hs:30), [VpaAccountManagment.hs](../../src/Newton/Types/API/ServerToServer/VpaAccountManagment.hs:50), [VpaAccountManagment.hs](../../src/Newton/Types/API/ServerToServer/VpaAccountManagment.hs:145), [VpaAccountManagment.hs](../../src/Newton/Types/API/ServerToServer/VpaAccountManagment.hs:185)
- Action dispatcher: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:556)
- Add VPA, primary account, and default account logic: [ManageVpaAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/ManageVpaAccount.hs:35)
- Link VPA/account logic: [LinkVpaAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/LinkVpaAccount.hs:30)
- Add account logic: [AddAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/AddAccount.hs:24)
- Customer info logic: [CustomerInfo.hs](../../src/Newton/Product/Merchant/VpaAccount/CustomerInfo.hs:26)
- Delete VPA logic: [DeleteVpa.hs](../../src/Newton/Product/Merchant/VpaAccount/DeleteVpa.hs:36)
- Delete account logic: [DeleteAccount.hs](../../src/Newton/Product/Merchant/VpaAccount/DeleteAccount.hs:34)
- Response assembly: [Helper.hs](../../src/Newton/Product/Merchant/Delegates/Helper.hs:786), [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:5158), [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:5173), [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:5247)
- Shared account and VPA data types: [Account.hs](../../src/Newton/Types/API/Account.hs:10)
- Validation helpers: [Common.hs](../../src/Newton/Validation/Common.hs:125), [Common.hs](../../src/Newton/Validation/Common.hs:168), [Common.hs](../../src/Newton/Validation/Common.hs:275)
- VPA business rules and availability: [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2705), [DB.hs](../../src/Newton/Utils/DB.hs:737)
- Error constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:518), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:527), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:536), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:707), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:716), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:725), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:734)
- UPI Lite delete restriction error: [Utils.hs](../../src/Newton/Utils/Utils.hs:5150)
