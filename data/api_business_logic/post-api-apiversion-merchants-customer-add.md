# Add Customer API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/add`

## Overview

Add Customer is a server-to-server API used to onboard a merchant customer into Newton with a bank account and a receive-only customer VPA.

The merchant calls this API after it already knows the customer's mobile number, account details, and the VPA that should be reserved for the customer. Newton creates or reuses the merchant-customer profile, creates or reuses the customer and account records, links the account to the requested VPA, and returns the VPA-account mapping that the merchant should store for future UPI workflows.

Use this API for server-side customer/account provisioning flows where the merchant is not using the device-binding or account-fetch journey to discover the customer's bank account.

## Business Use Case

Add Customer helps merchants:

- Create a Newton merchant customer profile from a merchant-owned `merchantCustomerId`.
- Store customer mobile and account details provided by the merchant backend.
- Link a receive-only VPA to the customer's account.
- Reuse an existing customer/account/VPA mapping when the same identifiers are sent again.
- Move a merchant customer id or customer mobile/account association only when the caller explicitly opts in with `deregisterOldCustomer: true`.
- Onboard FASTAG VPAs by using `feature: "FASTAG"` and a `netc.` VPA prefix.

Call this API when the merchant backend has completed its own customer/account verification and wants Newton to create the UPI profile data needed for later receive, account, VPA, or customer-info APIs.

## Integration Flow

1. Merchant validates the customer and account in its own system.
2. Merchant chooses a stable `merchantCustomerId` and the customer VPA to be created.
3. Merchant calls Add Customer with customer, account, and optional bank metadata.
4. Newton validates the request, authenticates the merchant, checks merchant configuration, and verifies that receive-only VPA creation is enabled.
5. Newton creates or finds the merchant customer, customer, account, merchant-customer-account link, VPA, and VPA-account link.
6. Newton returns the linked `vpaAccounts`, `primaryVpa`, and merchant/customer identifiers.
7. Merchant stores the returned VPA-account mapping and uses `merchantCustomerId` for follow-up APIs.

Important identifiers:

- `merchantCustomerId`: Merchant-generated customer identifier. This is the stable id used to find or create the Newton merchant-customer profile.
- `mobileNumber`: Customer mobile number used to find or create the Newton customer profile under the merchant.
- `accountNumber` plus `ifsc`: Used to derive the account hash/unique id. If the same account is sent again for the same customer, the account is reused.
- `vpa`: Customer VPA to create/link. This must be available and must belong to the merchant's configured VPA domain.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/add
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Current request timestamp used for merchant signature validation. |
| `x-merchant-signature` | Signature over merchant id, channel id, timestamp, and raw body, as shared during onboarding. |
| `x-api-version` | Optional standard S2S version header. This route does not currently branch on this value. |
| `x-request-id` | Optional request id for tracing. Newton generates one when omitted. |
| `x-session-id` | Optional session id for tracing. Defaults to `x-request-id` when omitted. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Path version segment. The current handler captures this at the API group level and does not apply endpoint-specific behavior from it. Use the value assigned during onboarding. |

## Authentication and Payload Handling

The route first resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`, verifies the request payload, and then runs merchant signature verification for the `addCustomer` API.

For this endpoint, the request type does not include an `iat` field. The current signature middleware is invoked without an `iat`, so the supported request mode visible in code is the plain decrypted business JSON body protected by the S2S header signature. The response is signed or encrypted according to the merchant's configured response strategy. Examples below show decrypted business bodies.

Authentication and access checks can fail before product logic runs:

- Missing merchant headers fail authentication.
- Invalid merchant id/channel id fails merchant lookup/authentication.
- Missing or mismatched `x-merchant-signature` fails signature verification.
- Blocked or not-allowed API configuration fails with `UNAUTHORIZED` / `API NOT ENABLED`.
- Invalid request JWS/JWE wrapping can fail before business validation; confirm with Newton before using a JWS/JWE request wrapper for this specific endpoint.

## Request

### Required Minimum

For a merchant whose `bankCode`, `bankName`, and `ifsc` are configured by Newton:

```json
{
  "merchantCustomerId": "CUST10001",
  "name": "Asha Sharma",
  "mobileNumber": "919876543210",
  "accountNumber": "123456789012",
  "accountType": "SAVINGS",
  "vpa": "asha.sharma@merchantupi"
}
```

For integrations without configured bank defaults, send the bank fields explicitly:

```json
{
  "merchantCustomerId": "CUST10001",
  "name": "Asha Sharma",
  "mobileNumber": "919876543210",
  "accountNumber": "123456789012",
  "accountType": "SAVINGS",
  "vpa": "asha.sharma@merchantupi",
  "bankName": "HDFC Bank",
  "bankCode": "HDFC",
  "ifsc": "HDFC0001234"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's stable customer id. Must be 1 to 256 characters. Allowed characters are letters, numbers, `.`, `_`, `+`, `/`, `=`, and `-`; the first character must be alphanumeric, `+`, `/`, or `=`. |
| `name` | string | Yes | No default. No explicit validator in this request type, but it is encrypted and stored as the account holder/customer name. | Customer/account holder name. |
| `countryCode` | string | No | If omitted, `mobileNumber` must be exactly 12 numeric digits. | Optional country code. When supplied, it must be numeric with an optional `+` and at most 7 characters. |
| `mobileNumber` | string | Yes | No default. | Customer mobile number. If `countryCode` is omitted, send a 12-digit numeric value such as `919876543210`. If `countryCode` is supplied, the value must be numeric and shorter than 19 digits. |
| `bankName` | string | Conditional | Falls back to merchant configuration key `bankName`. If both request and config are missing, processing fails. | Bank display name stored on the account and returned in `vpaAccounts[].account.bankName`. |
| `bankCode` | string | Conditional | Falls back to merchant configuration key `bankCode`. If both request and config are missing, processing fails. | Bank IIN/code stored on the account. If supplied, it must be non-empty. |
| `branchName` | string | No | Not stored when omitted. Non-multibank response account `branchName` uses the environment default branch name when no branch is stored; multibank response mode omits it. | Branch display name. |
| `ifsc` | string | Conditional | Falls back to merchant configuration key `ifsc`. If both request and config are missing, processing fails. | Account IFSC used with `accountNumber` to derive the account hash/unique id. |
| `kycStatus` | string | No | No default. Omitted from response account when absent. | KYC status for PPI/wallet style accounts. Allowed JSON values from the type are `MIN` and `FULL`. |
| `accountNumber` | string | Yes | No default. | Customer account number. Must be non-empty. Newton encrypts it for storage and uses it with `ifsc` to derive account hashes. |
| `accountType` | string | Yes | No default. No request-level enum validation is applied here. | Account type stored on the account and returned as `vpaAccounts[].account.type`, for example `SAVINGS`, `CURRENT`, or another onboarded account type. |
| `vpa` | string | Yes | No default. | Customer VPA to create/link. Must be 3 to 255 characters and match `prefix@handle`; product logic also requires the merchant/default VPA domain and VPA availability. |
| `feature` | string | No | Normal non-FASTAG VPA flow. | Optional feature flag. Currently supported request value is `FASTAG`. FASTAG requires a NETC-style VPA such as `netc.MH01AB1234@merchantupi`. |
| `deregisterOldCustomer` | boolean | No | Omitted behaves like `false` when an existing conflicting customer or merchant-customer association is found. | Set `true` only when the merchant intentionally wants Newton to delink the old association and continue onboarding the new one. |
| `udfParameters` | string | No | Omitted from the success response when absent. | Merchant-defined metadata as a JSON-object string. It must parse as a JSON object and cannot contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. Echoed in the success response. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are simply not stored or returned when omitted.

- `bankName`, `bankCode`, and `ifsc`: fallback to merchant configuration. Omit them only if Newton has configured defaults for the merchant.
- `branchName`: no storage default. Non-multibank response rendering substitutes the configured default branch name when the account has no branch; multibank response mode omits branch name.
- `kycStatus`: no default. Returned only when stored.
- `feature`: omitted uses the normal VPA flow. `FASTAG` switches validation and response filtering to FASTAG VPAs.
- `deregisterOldCustomer`: omitted behaves like `false`; conflicting associations are rejected instead of delinked.
- `udfParameters`: echoed only when supplied and valid.
- `mpinSet`, `mpinLength`, `otpLength`, `atmPinLength`, Aadhaar flags, and credential metadata in the response account are derived from merchant configuration, not from request fields.

### Validation Notes

Newton applies request validation before product logic:

- `merchantCustomerId` length and character rules.
- `countryCode` length and numeric format when supplied.
- `mobileNumber` length and numeric format. Without `countryCode`, it must be exactly 12 digits.
- `bankCode` must be non-empty when supplied.
- `accountNumber` must be non-empty.
- `vpa` must match the standard VPA pattern; for `feature: "FASTAG"`, it must start with `netc.`.
- `udfParameters` must be a JSON-object string and pass the restricted-character check.

Product logic then applies additional checks:

- Merchant must be enabled for receive-only VPA creation.
- VPA must match the merchant/default VPA domain.
- Mobile-number-based VPAs must match the customer's mobile number.
- VPA must be available for this customer/merchant-customer combination.
- Existing conflicting customer or merchant-customer associations require `deregisterOldCustomer: true`.

## Request Examples

### Standard Customer With Explicit Bank Details

```json
{
  "merchantCustomerId": "CUST10001",
  "name": "Asha Sharma",
  "mobileNumber": "919876543210",
  "accountNumber": "123456789012",
  "accountType": "SAVINGS",
  "vpa": "asha.sharma@merchantupi",
  "bankName": "HDFC Bank",
  "bankCode": "HDFC",
  "branchName": "Mumbai Main",
  "ifsc": "HDFC0001234",
  "kycStatus": "FULL",
  "udfParameters": "{\"customerTier\":\"gold\",\"source\":\"crm\"}"
}
```

### Customer Using Merchant-Configured Bank Defaults

Use this only when Newton has configured `bankName`, `bankCode`, and `ifsc` for the merchant.

```json
{
  "merchantCustomerId": "CUST10002",
  "name": "Rahul Verma",
  "countryCode": "+91",
  "mobileNumber": "9876543210",
  "accountNumber": "001122334455",
  "accountType": "CURRENT",
  "vpa": "rahul.verma@merchantupi",
  "deregisterOldCustomer": true
}
```

### FASTAG Customer

```json
{
  "merchantCustomerId": "FASTAG10001",
  "name": "Meera Iyer",
  "mobileNumber": "919812345678",
  "accountNumber": "998877665544",
  "accountType": "SAVINGS",
  "vpa": "netc.vehicle123@merchantupi",
  "feature": "FASTAG",
  "bankName": "HDFC Bank",
  "bankCode": "HDFC",
  "ifsc": "HDFC0001234",
  "kycStatus": "MIN"
}
```

## Processing Behavior

Add Customer is a create-or-reuse flow, not a blind insert.

- Newton finds or creates the merchant-customer profile by `merchantCustomerId` and merchant.
- Newton encrypts `name`, `mobileNumber`, and `accountNumber` before storing PII.
- Newton finds or creates the customer by mobile number/mobile hash under the merchant.
- Newton finds or creates the account by account hash for the customer.
- Newton always prepares the account as the outward default account for this flow.
- Newton creates or updates the merchant-customer-account link.
- If the merchant-customer is inactive, unbound, or bound to a different customer, Newton updates the merchant-customer profile and then links the VPA.
- If linking fails after a new merchant-customer registration update, Newton rolls back the VPA, VPA-account, merchant-customer-account, and merchant-customer binding changes attempted in that registration path.

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Add-customer result. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when the request omitted it. |

Treat the operation as successful only when `status` is `SUCCESS` and `responseCode` is `SUCCESS`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured in Newton. |
| `merchantChannelId` | string | Merchant channel id configured in Newton. |
| `merchantCustomerId` | string | Echoes the merchant customer id from the request. |
| `customerMobileNumber` | string | Customer mobile number after Newton's response formatting. It is omitted only if response PII is unavailable. |
| `vpaAccounts` | array | VPA-account mappings currently linked for the customer/merchant-customer and matching the requested feature. |
| `primaryVpa` | string | Primary VPA found from the linked VPA records. Omitted when no primary VPA can be derived. |

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA linked to the account. |
| `account` | object | Account details for this VPA mapping. |
| `isDefault` | boolean | Reflects the primary/default VPA-account mapping when included. |

### `vpaAccounts[].account`

Most account fields are returned only when the underlying account/configuration has a value. Clients should store fields they need for later API calls, especially `referenceId`, `bankAccountUniqueId`, `ifsc`, and `type`.

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Bank code/IIN stored for the account. |
| `bankName` | string | Bank display name. |
| `maskedAccountNumber` | string | Masked account number generated by Newton, usually the last four digits prefixed with `X`. |
| `mpinLength` | string | MPIN length from merchant configuration, defaulting by behavior to `4` when not configured. |
| `mpinSet` | string | `true` or `false` as a string, derived from stored account/configuration state. |
| `referenceId` | string | Newton account reference id. May be omitted for some multibank configurations. |
| `type` | string | Account type stored from request `accountType`. |
| `branchName` | string | Stored branch name or configured default branch name in non-multibank response mode. Omitted in multibank response mode. |
| `bankAccountUniqueId` | string | Account hash/unique id derived from the account details. |
| `ifsc` | string | Account IFSC. |
| `isPrimary` | string | Included only in flows that enable this flag. This route does not explicitly enable it. |
| `name` | string | Account holder name after PII decryption for response. |
| `otpLength` | string | OTP length from credentials/configuration, defaulting by behavior to `6`. |
| `atmPinLength` | string | Present when format-2 credential metadata is enabled. |
| `kycStatus` | string | `MIN` or `FULL`, when supplied/stored. |
| `accountNumber` | string | Optional encrypted account number for merchants configured to receive unmasked account details. Omitted otherwise. |
| `accBIN` | string | Account BIN when available for the account type/flow. |
| `bankAccountHash` | string | Returned when TPV/account-hash response behavior is enabled for the merchant. |
| `accSubType`, `allowedMCC`, `notallowedMCC` | string / array | Credit-line or MCC metadata when present. |
| `lrn`, `isInitialTopUpDone`, `liteDetails` | string / object | UPI Lite metadata when available. |
| `bioAuthConsentUrl`, `bioAuthEnabled`, `credsAllowed`, `payerAccountHash` | string | Optional capability/configuration fields when enabled. |

## Success Response Example

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "WEB",
    "merchantCustomerId": "CUST10001",
    "customerMobileNumber": "919876543210",
    "vpaAccounts": [
      {
        "vpa": "asha.sharma@merchantupi",
        "account": {
          "bankCode": "HDFC",
          "bankName": "HDFC Bank",
          "maskedAccountNumber": "XXXXXXXX9012",
          "mpinLength": "4",
          "mpinSet": "false",
          "referenceId": "acc_7b9f8c1",
          "type": "SAVINGS",
          "branchName": "Mumbai Main",
          "bankAccountUniqueId": "bank-account-unique-id",
          "ifsc": "HDFC0001234",
          "name": "Asha Sharma",
          "otpLength": "6",
          "kycStatus": "FULL"
        },
        "isDefault": true
      }
    ],
    "primaryVpa": "asha.sharma@merchantupi"
  },
  "udfParameters": "{\"customerTier\":\"gold\",\"source\":\"crm\"}"
}
```

## Error Handling

Failure bodies include `status: "FAILURE"` plus a concrete `responseCode` and diagnostic `responseMessage` after decoding/decryption where applicable. The examples below show common response bodies.

Some authentication or malformed-envelope failures happen before the normal route response wrapper. Clients should still parse the response body when present and use `status`, `responseCode`, and `responseMessage` as the primary handling signals.

### Validation Failure

Invalid request fields are returned as `BAD_REQUEST`. The message is a joined list of validation errors from the request validator.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mobile length is not equal to 12\", RegexValidation \"customerVpa regex failed\""
}
```

Common causes:

- `mobileNumber` is not 12 digits while `countryCode` is omitted.
- `merchantCustomerId` is empty, too long, or contains unsupported characters.
- `vpa` is not in `prefix@handle` format.
- `feature` is `FASTAG` but `vpa` does not start with `netc.`.
- `udfParameters` is not a JSON-object string.

### Authentication, Signature, or API Access Failure

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Common causes:

- Missing `x-merchant-id`, `x-merchant-channel-id`, `x-timestamp`, raw body, or signature headers.
- Invalid merchant id/channel id.
- Signature mismatch.
- Request IP is not whitelisted for the merchant.
- API is blocked or not included in the merchant's allowed API list.

### Invalid Request Envelope

If the body is parsed as JWE/JWS but cannot be decoded, decrypted, or validated, the request can fail before product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Error in finding kId"
}
```

For this endpoint, prefer the onboarded plain business body plus header signature mode unless Newton explicitly confirms a different request wrapper.

### Merchant Configuration Failure

Receive-only VPA creation must be enabled for the merchant.

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_NOT_ALLOWED",
  "responseMessage": "Receive Only VPA not allowed"
}
```

If `bankName`, `bankCode`, or `ifsc` is omitted and the merchant configuration does not contain the corresponding default, processing fails as an internal configuration error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Existing Customer or Merchant-Customer Conflict

If the merchant-customer id is already linked to another customer, or the same customer is already linked to another merchant-customer profile, the route refuses to proceed unless `deregisterOldCustomer` is `true`.

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_DEREGISTER_CUSTOMER",
  "responseMessage": "Deregister customer to continue onboarding"
}
```

Client handling:

- Do not retry the same request unchanged if the customer association is not meant to move.
- If the move is intentional, retry once with `deregisterOldCustomer: true`.
- If the move is not intentional, call the customer-info flow for the known `merchantCustomerId` and reconcile the merchant's mapping.

### Invalid or Unavailable VPA

The request-level VPA regex can pass while product validation still rejects the VPA because the handle/domain is not allowed, the mobile-number prefix does not match the customer, or the VPA is unavailable.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "vpa is not valid"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid Customer Vpa"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Normalized VPA already exists"
}
```

Client handling:

- Correct the VPA prefix/handle and retry with the same `merchantCustomerId`.
- Do not keep retrying an unavailable or already-normalized VPA; choose a new VPA or reconcile the existing owner.

### Lookup or Persistence Failure

Lookup or persistence failures that are not tied to a client-correctable field can surface as:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

If the merchant asks Newton to deregister an old association and the old active customer/profile cannot be loaded, the delinking helper can surface an invalid-data business error:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

### Downstream or Unexpected Failure

This API does not call NPCI directly. Its downstream dependencies are merchant/key configuration, request/response signing or encryption, PII encryption, Redis, and database persistence. Transient dependency failures can surface as `INTERNAL_SERVER_ERROR`; malformed crypto envelopes can surface as `UNAUTHORIZED` or `INVALID_DATA`.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry, Idempotency, and Client Handling

This API does not accept a merchant request id or explicit idempotency key. The practical idempotency keys are the stable business identifiers in the payload:

- `merchantCustomerId`
- `mobileNumber`
- `accountNumber` plus `ifsc`
- `vpa`

Safe retry guidance:

- If the client times out before receiving a response, retry with the exact same payload and headers regenerated for the new timestamp/signature.
- After a `SUCCESS`, store the returned `vpaAccounts` and do not retry with different customer/account data for the same `merchantCustomerId` unless you intend to update/relink the customer.
- Retry `INTERNAL_SERVER_ERROR` only with the same payload. If the retry also fails, reconcile using customer-info or operational support before changing identifiers.
- Do not retry validation, auth, merchant-configuration, or VPA-unavailable errors without correcting the underlying input/configuration.
- Use `deregisterOldCustomer: true` only for an intentional migration of an existing association. It can delink the previous customer/merchant-customer relationship.

## Source References

- API group and version capture: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:114)
- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:285)
- Handler and signature middleware call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1963)
- S2S transformer route: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:854)
- Request and response types/validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4200)
- Core request and response payload types: [src/Newton/Product/Merchant/Customer/Types.hs](../../src/Newton/Product/Merchant/Customer/Types.hs:332)
- Request/response transformer helpers: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1599)
- Product add-customer flow: [src/Newton/Product/Merchant/Customer/AddCustomer.hs](../../src/Newton/Product/Merchant/Customer/AddCustomer.hs:48)
- Core add-account flow used by Add Customer: [src/Newton/Product/Merchant/Account/AddAccount.hs](../../src/Newton/Product/Merchant/Account/AddAccount.hs:46)
- Account storage transformer and bank/config defaults: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2480)
- Add-account response transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1675)
- VPA-account response transformer: [src/Newton/Utils/Transformers/Transformer4.hs](../../src/Newton/Utils/Transformers/Transformer4.hs:223)
- Account response field construction: [src/Newton/Utils/Transformers/Transformer.hs](../../src/Newton/Utils/Transformers/Transformer.hs:438)
- Validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Request validation error wrapper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Merchant payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature verification: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response wrapping/signing/encryption: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:34)
- VPA business validation and availability: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2701) and [src/Newton/Utils/BusinessLogic/VpaHelper.hs](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:197)
- VPA availability checks: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:737)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43)
