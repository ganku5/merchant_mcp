# Create And Link Wallet Account API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/wallet/account/createAndLink`

## Overview

Create And Link Wallet Account is a server-to-server API used to create or update a customer's wallet/PPI account record in Newton and link it to a customer VPA in one call.

The merchant calls this API after the merchant customer is already onboarded or bound in Newton. Newton validates the S2S envelope, merchant customer, customer profile, requested VPA, wallet account payload, and merchant wallet configuration. It then creates or updates the wallet account, creates or reactivates the merchant-customer account mapping, links the account to the requested VPA through the Add Account flow, and returns the customer's current VPA-account state.

Use this API when the merchant system is the source of a wallet/PPI account and wants Newton to store that account and immediately make it usable with a customer VPA. Do not use this API for bank account discovery, OTP, MPIN setup, balance enquiry, or UPI payment authorization.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Create And Link Wallet Account helps merchants:

- Create a wallet/PPI-style account record for an existing merchant customer.
- Refresh the wallet account holder name or KYC status when the same wallet account already exists for the customer.
- Link the wallet account to a customer VPA in the same request.
- Optionally make the wallet account the customer's outward/default account.
- Optionally make the wallet account primary for all of the customer's VPAs by sending `setAsDefaultBank: "true"`.
- Keep the merchant backend in sync by reading the returned `vpaAccounts` snapshot.

This API updates Newton's local customer, account, merchant-customer-account, VPA, and VPA-account mapping state. It does not perform a balance check, debit, credit, OTP, MPIN, or NPCI account-discovery call.

## Integration Flow

1. Merchant completes the customer onboarding or binding flow and has a valid `merchantCustomerId`.
2. Merchant chooses the wallet/PPI account details and the customer VPA that should be linked.
3. Merchant calls `createAndLink` with the wallet account object, `customerVpa`, and `setAsDefaultBank`.
4. Newton verifies the encrypted/signed S2S envelope, merchant headers, timestamp, signature, API enablement, and request `iat`.
5. Newton resolves the merchant, merchant customer, and customer profile from `merchantCustomerId`.
6. Newton validates the request fields and applies merchant/customer VPA rules.
7. Newton creates or updates the wallet account using merchant-configured wallet bank details, then creates or reactivates the merchant-customer-account mapping.
8. Newton internally links the created account to the VPA through the Add Account product flow.
9. Newton returns the updated `vpaAccounts` list and `primaryVpa` when available.
10. Merchant stores the returned account identifiers and VPA-account state for later account, mandate, or transaction flows.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. This must resolve to an active Newton merchant-customer profile.
- `account.accountNumber`: Merchant-provided wallet/PPI account number or account reference value. Newton stores it encrypted and computes the wallet account hash from this value plus merchant-configured IFSC.
- `customerVpa`: Customer VPA to create/reuse and link to the wallet account.
- `payload.vpaAccounts[].account.referenceId`: Newton account reference id to use in APIs that accept `accountReferenceId`.
- `payload.vpaAccounts[].account.bankAccountUniqueId`: Merchant-facing account hash or migrated account id to use in APIs that accept `bankAccountUniqueId`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/wallet/account/createAndLink
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. This API's request shape is not version-switched in code, but the header is part of the standard S2S contract. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within 30 minutes of Newton's clock. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding. Required for signed/encrypted production traffic. |

Authentication and encryption follow the standard Newton S2S process shared during onboarding. Signed/encrypted calls must include valid merchant headers, timestamp, signature, and encrypted/signed request envelope. The decrypted business payload should include `iat` for signed/encrypted requests. Plain-text unsigned test payloads can omit `iat` only when that mode is enabled for the environment.

### Path and Version Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route version segment. Use the value shared during onboarding. |
| `x-api-version` | header | integer string | Recommended | Standard Newton S2S version header. Current `createAndLink` transformer does not branch on this value. |

### Request and Response Envelope

At the route boundary, the request type is `API.EncRequest CreateWalletAndLinkVpaRequest` and the response type is `API.EncResponse CreateWalletAndLinkVpaResponse`.

Depending on onboarding configuration, the outer request body can be:

| Envelope mode | Outer body shape | Notes |
| --- | --- | --- |
| JWE encrypted payload | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag` | Production encrypted mode. Newton decrypts the JWE and then verifies the nested signed body when present. |
| JWS signed payload | `payload`, `signature`, `protected` | The `payload` is base64url-encoded business JSON. |
| Plain JSON payload | Business fields directly | Used only for enabled non-production/test integrations. |

The JSON examples in this guide are the decrypted business payloads, not the encrypted JWE/JWS wrapper.

## Request

### Required Minimum

For a new wallet account that should become the default outward account and primary account for all customer VPAs:

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "987654321012",
    "name": "Customer Name",
    "type": "PPIWALLET",
    "kycStatus": "FULL"
  },
  "customerVpa": "cust.wallet@bank",
  "setAsDefaultBank": "true",
  "iat": "1735689600000"
}
```

For an existing VPA where the wallet account should be linked without changing primary/default mapping:

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "987654321012",
    "name": "Customer Name",
    "type": "PPIWALLET",
    "kycStatus": "MIN"
  },
  "customerVpa": "cust.wallet@bank",
  "setAsDefaultBank": "false",
  "iat": "1735689600000"
}
```

Do not use `setAsDefaultBank: "false"` for a first-time VPA link. Internally this maps to Add Account's `primaryAccountMapping = NONE`, and the flow rejects a first entry for the VPA.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Length must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `account` | object | Yes | No default. | Wallet/PPI account details to create or update. See `account` below. |
| `customerVpa` | string | Yes | No default. | Customer VPA to create/reuse and link to the wallet account. Must be 3 to 255 characters and match `local@handle` format. Product validation also enforces merchant-configured VPA handle and mobile-number VPA rules. |
| `setAsDefaultBank` | string | Yes | No default. | Boolean string. Accepted values are `"true"` and `"false"`; validation is case-insensitive, but send lowercase for consistency. `"true"` makes the wallet account outward/default and primary for all customer VPAs. `"false"` links without changing default/primary mappings and is valid only when the VPA already exists. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Unsigned/plain test payloads skip IAT validation only when that request type is enabled. | Issued-at timestamp used for request freshness validation. Send a 13-digit epoch-milliseconds value within 30 minutes of Newton's clock. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in the success response. Must parse as a JSON object string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### `account`

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `accountNumber` | string | Yes | No default. | Wallet/PPI account number or merchant account reference to store in Newton. Must be non-empty. This endpoint does not apply a numeric-only or max-length validator to this field, but account hashing and masking use the value exactly as supplied. |
| `name` | string | Yes | No default. | Account holder or wallet customer display name. Must be non-empty. If the same wallet account already exists for this customer, Newton updates the stored name. |
| `type` | string enum | Yes | No default. | Wallet account type. Allowed values: `PPIWALLET`, `BANKWALLET`, `CREDIT`. |
| `kycStatus` | string enum | Yes | No default. | Wallet account KYC status. Allowed values: `MIN`, `FULL`. If the same wallet account already exists for this customer, Newton updates the stored KYC status. |

### `setAsDefaultBank` Behavior

| Value | Internal mapping | Behavior |
| --- | --- | --- |
| `"true"` | `setDefault = true`, `primaryAccountMapping = ONE_TO_ALL` | Marks the created wallet account as the outward/default account and makes it the primary account mapping for all VPAs belonging to the customer and merchant customer. Recommended for first-time create-and-link. |
| `"false"` | `setDefault = false`, `primaryAccountMapping = NONE` | Creates/updates the wallet account and links it without making it default or primary. The target VPA must already exist; otherwise Newton returns `NONE is not allowed for first entry`. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `iat`: required for encrypted/signed S2S traffic. For expired requests, regenerate `iat`, `x-timestamp`, and the S2S signature/envelope before retrying.
- `udfParameters`: echoed only on success and only when supplied.
- `account.accountNumber`: stored encrypted. The response normally returns a masked account number and account identifiers, not the raw value. If account-number response encryption is enabled for the merchant, `account.accountNumber` may be returned as an encrypted value.
- `account.name` and `account.kycStatus`: update the existing wallet account when the same account hash already exists for the customer.
- Merchant-configured wallet bank fields: `ifsc`, `bankCode`, and `bankName` are not request fields. Newton reads them from merchant configuration. Missing configuration causes an internal-server-error response.
- Credential defaults from merchant configuration: `mpinSet` defaults to `false`; `aadharEnabled` defaults to `false`; `mpinLength` defaults to `"0"`; OTP length defaults to `"6"`; ATM PIN length defaults to `"4"` when relevant. Merchant `mobRegFormat` can populate `credsAllowed`.

### Validation Notes

- `merchantCustomerId` must pass Newton's merchant-customer-id format and length rules.
- `account.accountNumber` and `account.name` must be non-empty.
- `account.type` must be one of `PPIWALLET`, `BANKWALLET`, or `CREDIT`.
- `account.kycStatus` must be one of `MIN` or `FULL`.
- `customerVpa` must pass both the common VPA validator and the product-level merchant/customer VPA rules.
- `setAsDefaultBank` must be a boolean string: `"true"` or `"false"`.
- `udfParameters` must be a JSON object encoded as a string and must pass the allowed-character check.
- For signed/encrypted traffic, `iat` and `x-timestamp` must be 13-digit epoch-milliseconds values inside the 30-minute freshness window.

## Request Examples

### Create Wallet Account and Set as Default

Use this for first-time wallet account creation where the account should become the default outward account and primary mapping for all customer VPAs.

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "987654321012",
    "name": "Customer Name",
    "type": "PPIWALLET",
    "kycStatus": "FULL"
  },
  "customerVpa": "cust.wallet@bank",
  "setAsDefaultBank": "true",
  "iat": "1735689600000",
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Update Existing Wallet Account Name or KYC and Relink

If the account hash already exists for the customer, Newton updates the stored name and KYC status and then runs the link flow.

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "987654321012",
    "name": "Updated Customer Name",
    "type": "PPIWALLET",
    "kycStatus": "FULL"
  },
  "customerVpa": "cust.wallet@bank",
  "setAsDefaultBank": "true",
  "iat": "1735689600000"
}
```

### Link Without Changing Default Mapping

Use this only when `customerVpa` already exists for the customer and merchant customer.

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "987654321099",
    "name": "Customer Name",
    "type": "PPIWALLET",
    "kycStatus": "MIN"
  },
  "customerVpa": "cust.wallet@bank",
  "setAsDefaultBank": "false",
  "iat": "1735689600000"
}
```

### Bank Wallet Account

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "BANKWALLET000123",
    "name": "Customer Name",
    "type": "BANKWALLET",
    "kycStatus": "FULL"
  },
  "customerVpa": "cust.bankwallet@bank",
  "setAsDefaultBank": "true",
  "iat": "1735689600000"
}
```

## Processing Behavior

Newton processes `createAndLink` as a combined wallet-create and Add Account operation:

1. Decrypts/verifies the `EncRequest` envelope and decodes the business payload.
2. Validates `iat`, merchant headers, `x-timestamp`, `x-merchant-signature`, IP allowlist, API blocked/allowed configuration, and API enablement.
3. Resolves merchant, active merchant customer, and customer profile using `merchantCustomerId`.
4. Optionally updates VPA activity tracking for `customerVpa` when that platform feature is enabled.
5. Runs request validation for `merchantCustomerId`, `account`, `customerVpa`, `setAsDefaultBank`, and `udfParameters`.
6. Applies merchant/customer VPA rules. Mobile-number VPAs must match the customer's registered mobile number, and the VPA handle must match the merchant/configured VPA domain rules.
7. Builds a wallet account using request account data and merchant configuration:
   - `ifsc`, `bankCode`, and `bankName` come from merchant configuration.
   - `accountHash` is computed from `account.accountNumber` plus the first four characters of configured IFSC.
   - `maskedAccountNumber` is generated as `XXXX` plus the last four characters of `account.accountNumber`.
   - Account number and name are encrypted before persistence.
   - `type` is stored from `account.type`.
   - `kycStatus` is stored from `account.kycStatus`.
8. Creates the account or updates the existing account with the same account hash for the customer.
9. Creates or reactivates the merchant-customer-account mapping for the account.
10. Internally calls Add Account with the new account id/hash and the requested `customerVpa`.
11. If `setAsDefaultBank` is `"true"`, resets existing default account flags, marks this account as outward/default, and makes it primary for all customer VPAs.
12. If `setAsDefaultBank` is `"false"`, links the account as non-primary and does not change the outward/default account.
13. Creates or reuses the VPA, synchronizes VPA-account mappings, refreshes customer/account-linked flags, and returns the current VPA-account snapshot.
14. If remitter switch account sync is enabled for the merchant, Newton initiates an account-sync call to Turing after the DB updates. A failure in this post-link call can surface as `INTERNAL_SERVER_ERROR`; reconcile the customer account state before retrying.

The operation is not a pure idempotent create call. Repeating the same request can update account name/KYC and reapply default/primary mapping side effects.

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API business status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Updated merchant customer VPA-account state. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. |

This API does not return bank/NPCI gateway status fields. On success, interpret the operation from the top-level `status`, `responseCode`, and the returned `payload.vpaAccounts` snapshot.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number, trimmed before response when available. |
| `vpaAccounts` | array | Current active VPA-account mappings visible to this merchant customer after the create-and-link operation. |
| `primaryVpa` | string | Customer's primary active VPA when available. Omitted when no primary VPA is available. |

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA for this mapping. |
| `account` | object | Account details for the linked account. |
| `isDefault` | boolean | Whether this account is the primary/default mapping for the VPA. Use this field for create-and-link responses; `account.isPrimary` is generally omitted by this flow. |

### `vpaAccounts[].account`

The exact account fields returned depend on merchant configuration, account type, multibank mode, account data, TPV settings, account-number encryption settings, and optional Lite/BioAuth state. Optional fields are omitted when unavailable.

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Merchant-configured bank/IIN code used for wallet accounts. |
| `bankName` | string | Merchant-configured bank display name used for wallet accounts. |
| `maskedAccountNumber` | string | Masked wallet account number, generated as `XXXX` plus the last four characters of the supplied `account.accountNumber`. |
| `mpinLength` | string | MPIN length from merchant configuration; defaults to `"0"` when not configured. |
| `mpinSet` | string | Whether MPIN is set for the account. Can be forced to `"false"` for configured iOS MPIN setup flows. |
| `referenceId` | string | Newton account reference id. In multibank responses this can be omitted unless the merchant is configured to include it. |
| `type` | string | Account type, for example `PPIWALLET`, `BANKWALLET`, or `CREDIT`. |
| `branchName` | string | Branch name when available. Omitted in multibank responses. |
| `bankAccountUniqueId` | string | Account hash or migrated account id to use in later account APIs. |
| `ifsc` | string | Merchant-configured IFSC used for wallet accounts. |
| `name` | string | Decrypted account holder/wallet customer name. |
| `otpLength` | string | OTP length from `credsAllowed` or default `"6"`. |
| `atmPinLength` | string | ATM PIN length when format-2 response is enabled for the merchant. |
| `kycStatus` | string | Wallet account KYC status, `MIN` or `FULL`. |
| `accountNumber` | string | Encrypted account number when account-number response encryption is enabled for the merchant. Omitted otherwise. |
| `accBIN` | string | Account BIN when available, usually for credit accounts. |
| `aadhaarEnabled` | string | Aadhaar enablement flag when returned for applicable flows. |
| `isAadhaarNumberAvailable` | string | Aadhaar-number availability flag when returned for applicable flows. |
| `bankAccountHash` | string | TPV bank-account hash when TPV is enabled for the merchant. |
| `accSubType` | string | Account subtype when available. |
| `allowedMCC` | array of strings | Allowed MCC list for applicable accounts. |
| `notallowedMCC` | array of strings | Blocked MCC list for applicable accounts. |
| `lrn` | string | UPI Lite reference number when available. |
| `isInitialTopUpDone` | string | UPI Lite initial top-up status when available. |
| `liteDetails` | object | UPI Lite details when requested and available. |
| `bioAuthConsentUrl` | string | Bio-auth consent URL when available. |
| `bioAuthEnabled` | string | Bio-auth enablement flag for this account, commonly `"true"` or `"false"`. |
| `credsAllowed` | string | Credential allowance information when available. For wallet creation, merchant `mobRegFormat` can populate this from configured OTP/MPIN/ATM PIN lengths. |
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
        "vpa": "cust.wallet@bank",
        "isDefault": true,
        "account": {
          "bankCode": "123456",
          "bankName": "Example Wallet Bank",
          "maskedAccountNumber": "XXXX1012",
          "mpinLength": "6",
          "mpinSet": "false",
          "referenceId": "ACCOUNT_REF_123",
          "type": "PPIWALLET",
          "branchName": "Main Branch",
          "bankAccountUniqueId": "BANKACC123",
          "ifsc": "EXAM0001234",
          "name": "Customer Name",
          "otpLength": "6",
          "atmPinLength": "4",
          "kycStatus": "FULL",
          "bioAuthEnabled": "false"
        }
      }
    ],
    "primaryVpa": "cust.wallet@bank"
  },
  "udfParameters": "{\"sessionId\":\"SESSION123\"}"
}
```

### Example Response With Secondary Link

When `setAsDefaultBank` is `"false"`, the returned account can be linked with `isDefault: false`, and the existing primary/default VPA-account mapping remains unchanged.

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
        "vpa": "cust.wallet@bank",
        "isDefault": true,
        "account": {
          "bankCode": "123456",
          "bankName": "Example Wallet Bank",
          "maskedAccountNumber": "XXXX1012",
          "mpinLength": "6",
          "mpinSet": "false",
          "referenceId": "ACCOUNT_REF_123",
          "type": "PPIWALLET",
          "branchName": "Main Branch",
          "bankAccountUniqueId": "BANKACC123",
          "ifsc": "EXAM0001234",
          "name": "Customer Name",
          "otpLength": "6",
          "kycStatus": "FULL"
        }
      },
      {
        "vpa": "cust.wallet@bank",
        "isDefault": false,
        "account": {
          "bankCode": "123456",
          "bankName": "Example Wallet Bank",
          "maskedAccountNumber": "XXXX1099",
          "mpinLength": "6",
          "mpinSet": "false",
          "referenceId": "ACCOUNT_REF_456",
          "type": "PPIWALLET",
          "branchName": "Main Branch",
          "bankAccountUniqueId": "BANKACC456",
          "ifsc": "EXAM0001234",
          "name": "Customer Name",
          "otpLength": "6",
          "kycStatus": "MIN"
        }
      }
    ],
    "primaryVpa": "cust.wallet@bank"
  }
}
```

## Failure Responses

Failure responses use the same encrypted response transport as successful responses. The examples below show decrypted business bodies.

Most failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "BoolStringValidation \"Parameter is not true or false\""
}
```

When `payload` is empty, it is omitted from the JSON response. Depending on where validation fails, HTTP status can be `200`, `400`, `401`, or `500`; clients should read `status`, `responseCode`, and `responseMessage` from the decrypted body. Parser and validator messages include field-specific details generated by the Haskell/Aeson validation layer, so exact wording can vary by failing field and envelope mode.

### Authentication, Encryption, and Merchant Configuration

Missing merchant headers, invalid merchant credentials, IP allowlist failure, missing signature, or signature mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

JWS/JWE key lookup, entity-type, signature, or encrypted-envelope verification failure can also return:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Create And Link Wallet Account API disabled, blocked, or not allowed for the merchant:

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
  "responseMessage": "Error in $: key \"merchantCustomerId\" not found"
}
```

Missing merchant wallet configuration such as `ifsc`, `bankCode`, or `bankName`:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
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

Invalid `merchantCustomerId` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId length is not in between 1 and 256\""
}
```

Invalid `merchantCustomerId` characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Empty `account.accountNumber`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"accountNumber field is empty\""
}
```

Empty `account.name`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"name field is empty\""
}
```

Invalid `account.type` enum:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.account.type: parsing Newton.Types.Intermediate.PPIAccountType failed"
}
```

Invalid `account.kycStatus` enum:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $.account.kycStatus: parsing Newton.Types.Storage.Account.KYCStatus failed"
}
```

Invalid `customerVpa` length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"customerVpa length is not between 3 and 255\""
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

Invalid merchant/customer VPA rule, such as wrong merchant handle or mobile-number VPA mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "vpa is not valid"
}
```

Invalid boolean string in `setAsDefaultBank`:

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

### Customer, VPA, and Account State

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

Customer profile linked to the merchant customer is not found:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Customer not found"
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

`setAsDefaultBank` is `"false"` for the first mapping of a VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "NONE is not allowed for first entry"
}
```

Created wallet account cannot be found during the internal Add Account step:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

Wallet account upsert fails:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Wallet Account not created"
}
```

### Storage, Encryption, Turing Sync, and Unexpected Failures

Database update failure, encryption/key-service failure, response construction failure, or unexpected server failure:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

If remitter switch account sync is enabled and the post-link Turing account-sync call fails, the same generic internal-server-error body can be returned:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Because the sync call happens after local account/linking updates, treat this as a reconcile-before-retry scenario.

## Client Handling, Retry, and Idempotency

- This API does not take a merchant-generated idempotency key. Treat the operation target as `merchantCustomerId` plus `account.accountNumber`, merchant-configured IFSC, `customerVpa`, and `setAsDefaultBank`.
- Retrying the exact same request can be safe for network timeouts because the account is found by account hash and updated/reused, but it still reapplies default/primary mapping side effects.
- Retrying with a different `name` or `kycStatus` intentionally updates the existing wallet account for that customer.
- Retrying with a different `setAsDefaultBank` can change the customer's default account and VPA-account primary mappings. Store the body used for every attempt.
- If the client times out before receiving a response, first fetch the latest customer/account or VPA-account state when available. If the expected account/VPA mapping is present, do not blindly replay with different flags.
- For `REQUEST_EXPIRED` or timestamp errors, regenerate `iat`, `x-timestamp`, and the signature/encrypted envelope, then retry with the same business payload.
- For validation, auth, API enablement, merchant-customer, customer, VPA, or merchant configuration failures, correct the request or configuration before retrying.
- For `INTERNAL_SERVER_ERROR` after a possible Turing sync failure, reconcile local account/link state before retrying because the database changes may already have been committed.
- Do not look for gateway fields such as `gatewayResponseCode`; this API does not perform a bank/NPCI authorization.

## Source References

- Route definition: [Core.hs](../../src/Newton/App/Routes/Core.hs:1260)
- Route handler and signature flow: [createWalletAndLinkVpaS2S](../../src/Newton/App/Routes/Core.hs:4796)
- Handler wiring: [Server.hs](../../src/Newton/App/Server.hs:611)
- S2S transformer route: [Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:847)
- S2S request, response, and validators: [Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4148)
- S2S core request/response mapping: [Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1586)
- Core wallet request/response types: [Types.hs](../../src/Newton/Product/Merchant/Wallet/Types.hs:24)
- Wallet create-and-link product flow: [CreateWalletAndLinkVpa.hs](../../src/Newton/Product/Merchant/Wallet/CreateWalletAndLinkVpa.hs:27)
- Wallet account construction and response helper: [Helper.hs](../../src/Newton/Product/Merchant/Wallet/Helper.hs:38), [Helper.hs](../../src/Newton/Product/Merchant/Wallet/Helper.hs:83)
- Wallet account request object and enum values: [Intermediate.hs](../../src/Newton/Types/Intermediate.hs:821)
- KYC enum values: [Account.hs](../../src/Newton/Types/Storage/Account.hs:70)
- Request validation helpers: [Common.hs](../../src/Newton/Validation/Common.hs:125), [Common.hs](../../src/Newton/Validation/Common.hs:215), [Common.hs](../../src/Newton/Validation/Common.hs:275), [Common.hs](../../src/Newton/Validation/Common.hs:311)
- Encrypted/signed request and response envelope: [RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:96)
- Merchant signature, API enablement, IP, and IAT checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Timestamp freshness validation: [DateTime.hs](../../src/Newton/Utils/DateTime.hs:108)
- VPA activity tracker middleware: [VpaActivityTracker.hs](../../src/Newton/App/Middlewares/VpaActivityTracker.hs:17)
- VPA format and customer/mobile validation: [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2704), [BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2726)
- Add Account product flow used internally: [AddAccount.hs](../../src/Newton/Product/Merchant/Account/AddAccount.hs:42)
- Add Account core response type: [Account.hs](../../src/Newton/Types/API/Core/Account.hs:11)
- VPA create/sync helpers and primary VPA lookup: [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:179), [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:197), [VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:424)
- Default account and VPA-account sync updates: [AccountV2.hs](../../src/Newton/Product/AccountV2.hs:845)
- Merchant/customer/account lookup and `NONE` mapping validation: [DB.hs](../../src/Newton/Utils/DB.hs:503), [DB.hs](../../src/Newton/Utils/DB.hs:540), [DB.hs](../../src/Newton/Utils/DB.hs:791)
- Response account construction: [Transformer4.hs](../../src/Newton/Utils/Transformers/Transformer4.hs:223), [Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:438), [Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1675)
- Turing remitter switch account sync: [Core.hs](../../src/Newton/External/Turing/Core.hs:142)
- Error response constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:61), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124), [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
- API service name constants: [Constants.hs](../../src/Newton/Types/Domain/Constants.hs:114), [Constants.hs](../../src/Newton/Types/Domain/Constants.hs:887)
