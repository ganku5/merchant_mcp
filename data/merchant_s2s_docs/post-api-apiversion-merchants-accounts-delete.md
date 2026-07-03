# Delete Account API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/accounts/delete`

## Overview

Delete Account is a server-to-server API used to remove a customer's linked UPI bank account from the merchant customer's Newton profile.

The merchant calls this API after the customer has chosen to remove a linked account, close a UPI profile, or refresh their account list. Newton validates the encrypted S2S request, merchant configuration, customer profile, linked-account state, mandate state, and UPI Lite state. When deletion is allowed, Newton deletes the active VPA-account mappings for the selected account, deactivates the account mapping, and returns the customer's remaining VPA-account state.

Use this API only after the customer has completed the merchant-side action that authorizes account removal.

This endpoint does not send an NPCI/bank request. The result is a Newton business/profile-management result, so clients should read the top-level `status`, `responseCode`, and `responseMessage`. There are no `gatewayResponseStatus`, `gatewayResponseCode`, or `gatewayResponseMessage` fields in this API's success payload.

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

## Business Use Case

Delete Account helps merchants:

- Remove an account the customer no longer wants to use in the merchant's UPI experience.
- Keep local customer-profile state aligned with Newton after account-management or deregistration journeys.
- Remove VPA-account mappings for the selected account while preserving other linked accounts and VPAs.
- Prevent deletion when the account still has active mandates.
- Prevent deletion when the account has active UPI Lite state.
- Enforce merchant-configured restrictions for default-account and last-account deletion in multibank flows.
- Reconcile the remaining `vpaAccounts` after deletion.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton. This scopes the delete operation.
- `bankAccountUniqueId`: Merchant-facing account identifier/account hash returned by account APIs. Recommended for new integrations.
- `accountReferenceId`: Newton account reference id returned by account APIs. Use this when your integration stores account reference ids instead of account hashes.

## Integration Flow

1. Merchant ensures the customer is registered with Newton and has an account selected for deletion.
2. Merchant identifies the account using `bankAccountUniqueId` or `accountReferenceId` from account fetch/add/customer-info responses.
3. Merchant calls this endpoint using the standard Newton S2S envelope and signature process.
4. Newton decrypts/verifies the request and loads merchant, merchant-customer, and customer context from `merchantCustomerId`.
5. Newton validates request fields and resolves the account. If both account identifiers are supplied, `bankAccountUniqueId` takes precedence.
6. Newton applies deletion rules: inactive account, default account, last account, active mandate, and UPI Lite checks.
7. Newton deletes active VPA-account mappings for the account and deactivates the account mapping.
8. Newton returns the remaining VPA-account mappings for the customer.

## Endpoint

```http
POST /api/{apiVersion}/merchants/accounts/delete
```

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use the version shared during onboarding. This endpoint does not currently have response-version branching. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within Newton's configured clock-skew window. |
| `x-merchant-signature` | Required for plaintext/unsigned envelope integrations. Signature input includes merchant ids, timestamp, and raw body. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Depending on merchant configuration, the request body can be plaintext, JWS, or JWE. Signed/encrypted calls must include a valid payload `iat`; plaintext signed calls must include the configured merchant signature headers.

Newton responses follow the merchant's configured response strategy. A plaintext response is returned with a response signature header; JWS or JWS-and-JWE merchants receive signed or signed-and-encrypted response envelopes.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version in the route. Use the value shared during onboarding. |

## Handler Path

This endpoint is wired directly in the core S2S routes to `MerchantV2.deleteAccountRoute`. It does not use the generic manage-VPA-account `DELETE_ACCOUNT` transformer path. That adjacent transformer path exists for newer manage-VPA-account/linking APIs and has different request shapes and rules.

The direct handler path is:

1. `Core.ServerToServerAPIs` accepts `EncRequest DeleteAccountRequest`.
2. `Core.deleteAccount` decrypts/parses the envelope with `getReqBody`.
3. `merchantSignatureVerificationV2` validates `iat`, merchant headers, signature/envelope mode, merchant API access, IP allowlist if configured, and loads merchant/customer context.
4. The handler clears cached customer KV data for `merchantCustomerId`.
5. `MerchantV2.deleteAccountRoute` validates and performs deletion.
6. `Transformer9.mkDeleteAccountResponse` builds the business response.

## Request

### Required Minimum

For new integrations, send `merchantCustomerId` plus one account identifier. `bankAccountUniqueId` is preferred:

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "ACC_HASH_OR_MIGRATED_ID",
  "iat": "1735689600000"
}
```

If your integration stores Newton account reference ids:

```json
{
  "merchantCustomerId": "CUST12345",
  "accountReferenceId": "ACCOUNT_REF_123",
  "iat": "1735689600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `bankAccountUniqueId` | string | Conditional | No default. If both account identifiers are omitted, deletion is rejected. If both are supplied, this field is used and `accountReferenceId` is ignored for lookup. | Linked account identifier/account hash returned by account APIs. Recommended for new integrations. |
| `accountReferenceId` | string | Conditional | No default. Used only when `bankAccountUniqueId` is omitted. If both identifiers are omitted, deletion is rejected. | Newton account reference id returned by account APIs. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Plaintext test payloads in development may not require it; signed/JWS/JWE calls do. | Issued-at timestamp used by signature/envelope validation. Send a 13-digit Unix timestamp in milliseconds within the allowed clock-skew window. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in the success response. The value must parse as a JSON object string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `bankAccountUniqueId` and `accountReferenceId`: one of these must be supplied. This is enforced during account lookup, not by the request type validator, so the failure response is `BAD_REQUEST` with message `bankAccountUniqueId or accountReferenceId is mandatory`.
- `bankAccountUniqueId`: takes precedence when both account identifiers are supplied.
- `iat`: required before product logic for signed or encrypted envelopes. Missing `iat` on JWS/JWE requests is rejected before account deletion starts.
- `udfParameters`: echoed on success only when supplied.

### Nested Request Objects

There are no nested JSON objects in the decrypted request body. `udfParameters`, when used, is a JSON object encoded as a string.

### Validation Notes

- `merchantCustomerId` must pass the Newton merchant-customer-id validator.
- `bankAccountUniqueId` and `accountReferenceId` must be non-empty when supplied.
- `udfParameters` must be a JSON object string and pass the allowed-character check.
- The account must belong to the merchant customer resolved from `merchantCustomerId`.
- For P2M SDK enabled merchants, lookup is performed against the customer account table. Otherwise, lookup is performed against the merchant-customer-account mapping.

## Request Examples

### Delete by Bank Account Unique Id

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "8f23c1d7e4b9...",
  "iat": "1735689600000",
  "udfParameters": "{\"reason\":\"customer_removed_account\",\"sessionId\":\"SESSION123\"}"
}
```

### Delete by Account Reference Id

```json
{
  "merchantCustomerId": "CUST12345",
  "accountReferenceId": "ACCREF123",
  "iat": "1735689600000"
}
```

## Deletion Rules

- In multibank-enabled mode, an active default account cannot be deleted unless merchant store config `allowDeletionOfDefaultAccount` is `true`.
- In multibank-enabled mode, the customer's last active account cannot be deleted unless `allowDeletionOfDefaultAccount` is `true`.
- In non-multibank mode, retrying deletion for an already inactive account returns `INVALID_DATA` with message `Account already deleted`.
- In multibank mode, if the resolved account is already inactive, Newton skips deletion and returns the current remaining account state.
- If the account has active mandates, deletion is rejected with response code `JPDL`.
- If the account has active UPI Lite state for the customer's device, deletion is rejected with response code `JPLA`.
- Deletion requires at least one active VPA-account mapping to be removed. If no mapping is deleted, Newton returns `INVALID_DATA` with message `Account not deleted`.
- The API removes VPA-account mappings for the account. It does not delete the VPA records themselves.

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API/business status. Success value is `SUCCESS`. |
| `responseCode` | string | Machine-readable response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Human-readable response message. Success value is `SUCCESS`. |
| `payload` | object | Delete-account result. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

### Interpreting Status

This API has no gateway fields because it does not call NPCI/bank rails. Treat the top-level wrapper as the business result:

- `status = "SUCCESS"` and `responseCode = "SUCCESS"` means Newton accepted and completed the profile/account deletion workflow, or returned the current state for an already inactive account in an allowed multibank path.
- `status = "FAILURE"` means no successful deletion should be assumed. Read `responseCode` and `responseMessage` for client handling.
- HTTP status can be `200` for many business failures because the application returns an encrypted error body. Auth/envelope failures can return `401` or `400` before the normal business response is produced.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier. |
| `merchantCustomerId` | string | Merchant customer id for the customer profile on which the account was deleted. |
| `customerMobileNumber` | string | Customer mobile number stored on the Newton customer profile. |
| `vpaAccounts` | array | Remaining active VPA-account mappings after deletion. Empty array means no active VPA-account mappings remain in the returned profile state. |

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA still linked after account deletion. |
| `account` | object | Account details for this remaining VPA-account mapping. |
| `isDefault` | boolean | Defined by the shared response type, but omitted by this endpoint's current transformer because delete account calls `mkVpaAccounts` with default-flag output disabled. |

### `vpaAccounts[].account`

The exact account fields returned depend on merchant configuration, account type, multibank mode, and feature enablement. Optional fields are omitted when unavailable.

| Field | Type | Returned behavior |
| --- | --- | --- |
| `bankCode` | string | Always returned for each remaining account. |
| `bankName` | string | Always returned for each remaining account. |
| `maskedAccountNumber` | string | Always returned. |
| `mpinLength` | string | Always returned. |
| `mpinSet` | string | Always returned as `"true"` or `"false"`, with merchant/iOS set-MPIN config applied where enabled. |
| `referenceId` | string | Returned when account reference id is exposed for the merchant flow. In multibank mode it can be omitted unless `includeAccountReferenceId` is enabled; ICICI mode can return migrated id or account id. |
| `type` | string | Account type, for example `SAVINGS`, `CURRENT`, `CREDIT`, or another value stored for the account. |
| `branchName` | string | Returned for non-multibank flows. Omitted in multibank mode. |
| `bankAccountUniqueId` | string | Returned when account hash or migrated id is available. Use this value for future account APIs. |
| `ifsc` | string | Account IFSC. |
| `isPrimary` | string | Returned only when merchant store config `isPrimaryInDeleteAccountResponse` is enabled. Value is `"true"` or `"false"`. |
| `name` | string | Account holder name when available. |
| `otpLength` | string | OTP length expected for the account. Defaults by transformer behavior to `"6"` when credential metadata is unavailable. |
| `atmPinLength` | string | Returned only when merchant store config `enableFormat2` is enabled. Defaults by transformer behavior to `"4"` when credential metadata is unavailable. |
| `kycStatus` | string | Returned when stored for the account. |
| `accountNumber` | string | Returned only when the merchant flow/configuration permits account-number output. The value is encrypted or masked according to merchant configuration. |
| `accBIN` | string | Returned for applicable credit-card/credit accounts when derivable. |
| `bankAccountHash` | string | Returned when TPV account-hash output is enabled for the merchant. |
| `accSubType` | string | Returned for applicable account subtypes, such as credit-line related account types. |
| `bioAuthEnabled` | string | Returned as `"true"` or `"false"` for each account. If no biometric consent record exists for the account, Newton returns `"false"`. |
| `payerAccountHash` | string | Returned when merchant configuration `enablePayerAccountHash` is enabled. |

Fields from the shared account type that are not populated by this endpoint's current transformer are omitted, including `aadhaarEnabled`, `isAadhaarNumberAvailable`, `allowedMCC`, `notallowedMCC`, `lrn`, `isInitialTopUpDone`, `liteDetails`, `bioAuthConsentUrl`, and `credsAllowed`.

## Success Response Examples

### Account Deleted, Other Mappings Remain

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
        "vpa": "cust.primary@bank",
        "account": {
          "bankCode": "123456",
          "bankName": "Example Bank",
          "maskedAccountNumber": "XXXXXX1234",
          "mpinLength": "6",
          "mpinSet": "true",
          "referenceId": "ACCREF456",
          "type": "SAVINGS",
          "branchName": "MUMBAI",
          "bankAccountUniqueId": "ACC_HASH_REMAINING",
          "ifsc": "EXAM0001234",
          "name": "Customer Name",
          "otpLength": "6",
          "bioAuthEnabled": "false"
        }
      }
    ]
  },
  "udfParameters": "{\"reason\":\"customer_removed_account\",\"sessionId\":\"SESSION123\"}"
}
```

### Account Deleted, No Remaining VPA-Account Mappings

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
    "vpaAccounts": []
  }
}
```

## Failure Handling

Failure responses use the same response-envelope strategy as the rest of the S2S integration when they are produced after the response strategy is available. The examples below show decrypted bodies.

### Validation Failure: Missing Account Identifier

Returned when both `bankAccountUniqueId` and `accountReferenceId` are omitted.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "bankAccountUniqueId or accountReferenceId is mandatory"
}
```

### Validation Failure: Invalid Merchant Customer Id

Returned when the request body validator rejects `merchantCustomerId`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

### Validation Failure: Invalid UDF Parameters

Returned when `udfParameters` is not a JSON object string or contains disallowed characters.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

### Auth or Signature Failure

Returned when merchant headers are missing, the merchant signature is invalid, the merchant id/channel id is unknown, or configured IP checks fail.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the API is blocked or not in the merchant's allowed API list, the response message is more specific:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### Encryption or Payload Failure

Malformed JWS/JWE, payload parse failures, missing `kid`, or missing `iat` for signed/encrypted calls are rejected before account deletion. Depending on where verification fails, clients can receive `BAD_REQUEST`, `INVALID_DATA`, or `UNAUTHORIZED`.

Example missing `iat` on a signed/encrypted request:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

### Lookup Failure: Merchant Customer Not Found

Returned when the merchant is valid but `merchantCustomerId` does not resolve to an active profile for that merchant.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

### Lookup Failure: Account Not Found

Returned when the supplied account identifier does not resolve for the customer/merchant-customer context.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

### Business Failure: Default Account Restricted

Returned in multibank mode when deleting an active default account is not allowed by merchant configuration.

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_DEFAULT_ACCOUNT",
  "responseMessage": "Default account of the customer cannot be deleted"
}
```

### Business Failure: Last Account Restricted

Returned in multibank mode when deleting the customer's last active account is not allowed by merchant configuration.

```json
{
  "status": "FAILURE",
  "responseCode": "OPERATION_RESTRICTED_LAST_ACCOUNT",
  "responseMessage": "Last account of the customer cannot be deleted"
}
```

### Business Failure: Account Already Deleted

Returned for non-multibank flows when the account mapping is already inactive.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account already deleted"
}
```

### Business Failure: Active Mandates

Returned when active mandates exist for the account. Revoke or let the mandates complete before retrying deletion.

```json
{
  "status": "FAILURE",
  "responseCode": "JPDL",
  "responseMessage": "You have active mandate(s). Please try again after all the mandates are executed or revoked"
}
```

### Business Failure: Active UPI Lite Account

Returned when the account has active UPI Lite state.

```json
{
  "status": "FAILURE",
  "responseCode": "JPLA",
  "responseMessage": "LITE_ACCOUNT_ACTIVE"
}
```

### Business Failure: No VPA-Account Mapping Deleted

Returned when the account was resolved but no active VPA-account mapping was deleted.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not deleted"
}
```

### Downstream Storage, Cache, or Decryption Failure

This endpoint does not call NPCI. Downstream failures for this route are Newton-side storage, cache, PII decryption, or response-building failures. These generally surface as internal errors.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Unexpected Error

Treat unexpected `INTERNAL_SERVER_ERROR` responses as unknown outcome unless the failure clearly happened before deletion validation. Reconcile with account fetch/customer-info before retrying destructive account-management actions.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry, Idempotency, and Client Handling

This API does not accept a merchant idempotency key such as `merchantRequestId`. Client behavior should be state-based:

- On `SUCCESS`, update the merchant-side customer profile from `payload.vpaAccounts`.
- If the HTTP call times out or the response cannot be decrypted, fetch the customer's current account/VPA state before retrying. The delete might already have completed.
- Do not retry validation failures without correcting the request.
- Do not retry `UNAUTHORIZED` or `API NOT ENABLED` until credentials, headers, IP allowlist, or merchant API configuration are fixed.
- Do not retry `OPERATION_RESTRICTED_DEFAULT_ACCOUNT`, `OPERATION_RESTRICTED_LAST_ACCOUNT`, `JPDL`, or `JPLA` until the blocking account, mandate, Lite, or merchant-config condition changes.
- Retrying an already-completed delete is not guaranteed to return the same response. Non-multibank flows can return `Account already deleted`; multibank flows can return the current remaining state for an inactive account.
- For transient `INTERNAL_SERVER_ERROR`, retry only after checking current state or after a short backoff if state lookup is unavailable.

## Source References

- Route type: [Core.ServerToServerAPIs](../../src/Newton/App/Routes/Core.hs:231)
- Endpoint handler: [Core.deleteAccount](../../src/Newton/App/Routes/Core.hs:1906)
- S2S request/response types and validator: [DeleteAccountRequest and DeleteAccountResponse](../../src/Newton/Types/API/ServerToServer/Account.hs:288)
- Product route and deletion rules: [MerchantV2.deleteAccountRoute](../../src/Newton/Product/MerchantV2.hs:645)
- Account lookup precedence: [Utils.DB.getActiveOrInactiveMerchantCustomerAccount/getActiveOrInactiveAccount](../../src/Newton/Utils/DB.hs:673)
- Request validation wrapper: [Utils.validateRequestBody](../../src/Newton/Utils/Utils.hs:251)
- Field validators: [Validation.Common](../../src/Newton/Validation/Common.hs:168)
- Response transformer: [Transformer9.mkDeleteAccountResponse](../../src/Newton/Utils/Transformers/Transformer9.hs:2089)
- `vpaAccounts` transformer: [Transformer4.mkVpaAccounts](../../src/Newton/Utils/Transformers/Transformer4.hs:223)
- Account/VPAAccount response types: [Newton.Types.API.Account](../../src/Newton/Types/API/Account.hs:12)
- S2S signature and merchant-config middleware: [MerchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Response signing/encryption wrapper: [RoutesHelper.flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Error helpers/constants: [Newton.Constants.APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:43)
- Adjacent generic S2S transformer path, not used by this endpoint: [ServerToServer.Core vpaAccountTransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:562)
