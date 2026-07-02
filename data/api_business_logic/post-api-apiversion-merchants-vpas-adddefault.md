# Add Default VPA API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/addDefault`

## Overview

Add Default VPA is a server-to-server API used to add or reactivate a customer VPA and link it to the account mappings of an existing customer primary VPA.

The merchant calls this API after the customer profile, at least one VPA, and account mappings already exist in Newton. Newton validates the merchant/customer context, validates the new VPA, checks whether the VPA can be claimed, creates or reuses the VPA, copies the account mappings from `customerPrimaryVpa` to `customerVpa`, and optionally deletes the previous primary VPA for multibank flows.

Use this API when the merchant wants a customer VPA to become usable with the same linked accounts as an existing primary VPA. Do not use it to discover accounts, fetch balance, set MPIN, or initiate a payment.

## Business Use Case

Add Default VPA helps merchants:

- Add a new customer VPA and attach it to the customer's existing linked bank account mappings.
- Re-activate a previously inactive VPA when Newton's VPA-claim rules allow it.
- Set or preserve the customer's primary VPA relationship while copying default account mappings.
- Replace a primary VPA in multibank flows by deleting the old primary VPA and making the new VPA primary.
- Keep the merchant backend in sync with the VPA-account mappings returned by Newton after the update.

## Integration Flow

1. Merchant registers or resolves the customer with Newton and obtains `merchantCustomerId`.
2. Merchant identifies an existing customer VPA to use as `customerPrimaryVpa`. This VPA must already exist on the customer's Newton profile.
3. Merchant chooses the VPA to add or update as `customerVpa`.
4. Merchant calls Add Default VPA using the standard Newton encrypted/signed S2S request process.
5. Newton verifies the envelope, merchant headers, signature, timestamp, API enablement, merchant customer, and customer profile.
6. Newton validates the request fields, VPA format, mobile-number VPA rules, and VPA availability.
7. Newton creates or reactivates `customerVpa`, copies the relevant account mappings, and optionally deletes `customerPrimaryVpa`.
8. Newton returns the VPA-account mappings for the VPA updated by this call, plus `primaryVpa` for response versions greater than `0`.
9. Merchant updates its customer profile cache from the response.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. This scopes the customer profile.
- `customerPrimaryVpa`: Existing VPA on the customer's profile. Newton uses it as the source primary VPA for account mappings.
- `customerVpa`: VPA to add, reactivate, or update with the source VPA's account mappings.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/addDefault
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use `1` or higher if the client needs `payload.primaryVpa` in the response. Missing or non-numeric values are treated as `0`. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | 13-digit epoch milliseconds, within the allowed clock-skew window. |
| `x-merchant-signature` | Signature generated using the signing method shared during onboarding. Required for signed production traffic unless another onboarded signing mode is enabled. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Signed/encrypted calls must include valid merchant headers, timestamp, signature, and encrypted/signed request envelope. The decrypted business payload should include `iat` for signed/encrypted requests. Plain-text unsigned test payloads can omit `iat` only when that request mode is enabled for the environment.

### Path and Version Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `apiVersion` | path | string | Yes | Route version segment. Use the value shared during onboarding. |
| `x-api-version` | header | integer string | Recommended | Response version selector for this API. Missing or non-numeric values fall back to `0`. |

### Request and Response Envelope

The route accepts `API.EncRequest AddDefaultVpaRequest`. Depending on onboarding configuration, the outer request body can be:

```json
{
  "protected": "base64url-jwe-header",
  "encryptedKey": "base64url-encrypted-key",
  "iv": "base64url-iv",
  "cipherText": "base64url-ciphertext",
  "tag": "base64url-auth-tag"
}
```

or a signed payload:

```json
{
  "payload": "base64url-json-payload",
  "signature": "base64url-signature",
  "protected": "base64url-jws-header"
}
```

The decrypted business payload is the JSON object documented in the Request section. Successful and failed responses use the same encrypted/signed response transport configured for the merchant; examples in this guide show the decrypted business body.

## Request

### Required Minimum

For a normal add/update where the old primary VPA is not deleted:

```json
{
  "merchantCustomerId": "CUST12345",
  "customerPrimaryVpa": "cust.primary@bank",
  "customerVpa": "cust.new@bank",
  "iat": "1735689600000"
}
```

For a multibank replacement where the previous primary VPA should be deleted:

```json
{
  "merchantCustomerId": "CUST12345",
  "customerPrimaryVpa": "cust.old@bank",
  "customerVpa": "cust.new@bank",
  "deleteCustomerPrimaryVpa": "true",
  "iat": "1735689600000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Length must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `customerVpa` | string | Yes | No default. | VPA to add, reactivate, or update. Newton lower-cases/normalizes it for storage and uniqueness checks. It must be non-empty, match the configured VPA format, and be available to claim for this customer. |
| `customerPrimaryVpa` | string | Yes | No default. | Existing customer VPA used as the source primary VPA for account mappings. It must already exist on the customer's Newton profile. |
| `deleteCustomerPrimaryVpa` | string | Conditional | Omitted behaves as `"false"` for most merchants. For multibank-enabled merchants that are not in stagger-to-multibank mode, this field is mandatory. | Boolean string, accepted case-insensitively as `"true"` or `"false"`. When `"true"` and `customerVpa` differs from `customerPrimaryVpa`, Newton deletes `customerPrimaryVpa` after moving/copying its account mappings to `customerVpa`. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Unsigned/plain test payloads skip IAT validation only when that request type is enabled. | Issued-at timestamp used for request freshness validation. Send a 13-digit epoch-milliseconds value within the allowed clock-skew window. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in the success response. Must parse as a JSON object string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `deleteCustomerPrimaryVpa`: Omitted is treated as `false` unless the merchant is in the multibank configuration branch where the field is mandatory. When it is `false`, Newton does not delete `customerPrimaryVpa`.
- `iat`: Required by the signature/timestamp middleware for signed or encrypted S2S traffic, even though the Haskell request type is nullable.
- `udfParameters`: Echoed only on success and only when supplied.
- `x-api-version`: Missing or non-numeric values are treated as `0`, which omits `payload.primaryVpa`.

### Processing Behavior

- Newton loads the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- Newton validates API enablement, blocked/allowed API configuration, IP whitelist configuration when present, the request timestamp, and the request signature.
- Newton loads the merchant customer and customer profile using `merchantCustomerId`.
- Newton clears cached profile/KV data for `merchantCustomerId` before calling the product logic.
- `customerVpa` must pass Newton's VPA format rules. For mobile-number-based VPAs, Newton compares the VPA prefix with the customer's registered mobile number and the merchant's configured VPA handle.
- `customerPrimaryVpa` must resolve to an existing VPA for the same customer profile. It is the source used to identify account mappings.
- `customerVpa` must be available to claim. A VPA already active for another merchant customer is rejected. A deactivated VPA can be claimed only when Newton's old/deactivated VPA rules allow it. A blocked deactivated VPA is treated as unavailable.
- Newton creates or reactivates `customerVpa` as needed. If the merchant customer has no device id, the created VPA can be stored in a restricted/receive-only status.
- If `deleteCustomerPrimaryVpa = "true"` and `customerVpa` is different from `customerPrimaryVpa`, Newton checks for active mandates and active delegate links before deleting `customerPrimaryVpa`.
- Newton copies or updates the source VPA's account mappings onto `customerVpa`. The response `vpaAccounts` array represents the VPA-account mappings returned for the VPA updated by this call, not necessarily every VPA on the customer profile.
- `payload.primaryVpa` is included only when `x-api-version > 0` and a primary VPA is available.

### Request Examples

#### Add a New VPA Using Existing Primary VPA Account Mappings

Use this when `cust.primary@bank` already exists and `cust.new@bank` should be linked to the same account mappings.

```json
{
  "merchantCustomerId": "CUST12345",
  "customerPrimaryVpa": "cust.primary@bank",
  "customerVpa": "cust.new@bank",
  "iat": "1735689600000",
  "udfParameters": "{\"source\":\"profile_update\"}"
}
```

#### Replace the Existing Primary VPA in a Multibank Flow

Use this only when your merchant configuration requires or allows primary VPA deletion during the add-default flow.

```json
{
  "merchantCustomerId": "CUST12345",
  "customerPrimaryVpa": "cust.old@bank",
  "customerVpa": "cust.new@bank",
  "deleteCustomerPrimaryVpa": "true",
  "iat": "1735689600000"
}
```

#### Reconfirm the Same Primary VPA

Use this when the same VPA should be reprocessed as the default/primary VPA source and target.

```json
{
  "merchantCustomerId": "CUST12345",
  "customerPrimaryVpa": "cust.primary@bank",
  "customerVpa": "cust.primary@bank",
  "deleteCustomerPrimaryVpa": "false",
  "iat": "1735689600000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Add Default VPA result. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier. |
| `merchantCustomerId` | string | Merchant customer id for the profile updated by this call. |
| `customerMobileNumber` | string | Present only for multibank-enabled merchants. Returned as the trimmed customer mobile number. |
| `vpaAccounts` | array | VPA-account mappings returned for the VPA updated by this call. Each item contains the VPA, linked account details, and default flag when available. |
| `primaryVpa` | string | Present only when `x-api-version > 0` and a primary VPA is available. Omitted for response version `0`. |

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA linked or updated by the call. |
| `account` | object | Account details for this VPA-account mapping. |
| `isDefault` | boolean | Whether this VPA-account mapping is the default mapping, when available. |

### `vpaAccounts[].account`

The exact account fields returned depend on merchant configuration, account type, multibank mode, and feature enablement. Optional fields are omitted when unavailable.

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Bank code for the linked account. |
| `bankName` | string | Bank display name. |
| `maskedAccountNumber` | string | Masked bank account number. |
| `mpinLength` | string | MPIN length expected for the account. |
| `mpinSet` | string | Whether MPIN is set for the account, as returned by Newton. |
| `referenceId` | string | Account reference id, when available. |
| `type` | string | Account type, when available. |
| `branchName` | string | Branch name, when available. |
| `bankAccountUniqueId` | string | Merchant-facing unique account identifier, when available. |
| `ifsc` | string | Account IFSC, when available. |
| `isPrimary` | string | Whether this is the primary account for the VPA, when returned. |
| `name` | string | Account holder name, when available. |
| `otpLength` | string | OTP length expected for the account. |
| `atmPinLength` | string | ATM PIN length, when available. |
| `kycStatus` | string | KYC status, when available. |
| `accountNumber` | string | Account number, when available for the merchant flow. |
| `accBIN` | string | Account BIN, when available. |
| `aadhaarEnabled` | string | Aadhaar enablement flag, when available. |
| `isAadhaarNumberAvailable` | string | Aadhaar-number availability flag, when available. |
| `bankAccountHash` | string | Bank account hash, when available. |
| `accSubType` | string | Account subtype, for example credit-line related subtype when available. |
| `allowedMCC` | array of strings | Allowed MCC list for applicable accounts. |
| `notallowedMCC` | array of strings | Blocked MCC list for applicable accounts. |
| `lrn` | string | Lite reference number, when available for supported flows. |
| `isInitialTopUpDone` | string | UPI Lite initial top-up status, when available. |
| `liteDetails` | object | UPI Lite details, when requested and available. |
| `bioAuthConsentUrl` | string | Bio-auth consent URL, when available. |
| `bioAuthEnabled` | string | Bio-auth enablement flag, when available. |
| `credsAllowed` | string | Credential allowance flag/details, when available. |
| `payerAccountHash` | string | Hash of the payer account number without IFSC, when available. |

### Example Success Response

For `x-api-version: 1` or higher:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "vpaAccounts": [
      {
        "vpa": "cust.new@bank",
        "isDefault": true,
        "account": {
          "bankCode": "123456",
          "bankName": "Example Bank",
          "maskedAccountNumber": "XXXXXX1234",
          "mpinLength": "6",
          "mpinSet": "true",
          "referenceId": "ACCREF123",
          "type": "SAVINGS",
          "bankAccountUniqueId": "BANKACC123",
          "ifsc": "EXAM0001234",
          "otpLength": "6"
        }
      }
    ],
    "primaryVpa": "cust.primary@bank"
  },
  "udfParameters": "{\"source\":\"profile_update\"}"
}
```

### Multibank Replacement Success Response

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
        "vpa": "cust.new@bank",
        "isDefault": true,
        "account": {
          "bankCode": "123456",
          "bankName": "Example Bank",
          "maskedAccountNumber": "XXXXXX1234",
          "mpinLength": "6",
          "mpinSet": "true",
          "referenceId": "ACCREF123",
          "type": "SAVINGS",
          "bankAccountUniqueId": "BANKACC123",
          "ifsc": "EXAM0001234",
          "otpLength": "6"
        }
      }
    ],
    "primaryVpa": "cust.new@bank"
  }
}
```

### Version 0 Success Response

When `x-api-version` is missing, `0`, or non-numeric, `primaryVpa` is omitted even when Newton has a primary VPA.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "vpaAccounts": [
      {
        "vpa": "cust.new@bank",
        "isDefault": true,
        "account": {
          "bankCode": "123456",
          "bankName": "Example Bank",
          "maskedAccountNumber": "XXXXXX1234",
          "mpinLength": "6",
          "mpinSet": "true",
          "referenceId": "ACCREF123",
          "type": "SAVINGS",
          "otpLength": "6"
        }
      }
    ]
  }
}
```

## Response Versioning

| `x-api-version` | Response behavior |
| --- | --- |
| `0`, missing, or non-numeric | Legacy response. `payload.primaryVpa` is omitted. |
| `1` or higher | Includes `payload.primaryVpa` when a primary VPA is available. |

The path parameter `{apiVersion}` is still required by the route. The `x-api-version` header controls response-version behavior for this API.

## Error Handling

Failure responses use the same encrypted response transport as successful responses. The examples below show the decrypted business body.

Most failure bodies follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"customerVpa field is empty\""
}
```

The exact `responseMessage` can vary for JSON parser errors, signature/encryption errors, and lower-level database/cache failures because those messages are produced by the failing layer. Validation failures from the request validator are serialized from Haskell validation constructors such as `LengthValidation`, `RegexValidation`, `BoolStringValidation`, and `UnexpectedType`. When `payload` is empty, it is omitted from the JSON response.

Clients should read `status`, `responseCode`, and `responseMessage` from the body. Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, or `500`; the body is the stable integration contract.

### Add Default VPA Failure Bodies

Use the body pattern shown in the `Response body` column for each scenario.

| Scenario | Response body |
| --- | --- |
| Request body cannot be decoded as a supported JSON/envelope shape | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Request"}` |
| Signed payload or decrypted JWE payload cannot be parsed as the request type | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: key \"customerVpa\" not found"}` |
| JWE decryption fails, JWS verification fails, required merchant headers are missing, merchant signature is invalid, or IP whitelist validation fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Add Default VPA API is blocked or not allowed for the merchant configuration | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| Signed/encrypted request is missing `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| `iat` or `x-timestamp` is not a 13-digit millisecond timestamp | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` |
| `iat` or `x-timestamp` is outside the allowed clock-skew window | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` |
| `customerVpa` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"customerVpa field is empty\""}` |
| `customerPrimaryVpa` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"customerPrimaryVpa field is empty\""}` |
| `merchantCustomerId` is empty or longer than 256 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` |
| `merchantCustomerId` contains unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| `deleteCustomerPrimaryVpa` is supplied with a value other than a boolean string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"BoolStringValidation \"Parameter is not true or false\""}` |
| `udfParameters` is not a valid JSON-object string or contains disallowed characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| Merchant customer profile cannot be found for `merchantCustomerId` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"User profile not found"}` |
| Merchant customer has no customer/device binding | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer"}` |
| Customer record linked to the merchant customer cannot be found | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Customer not found"}` |
| Multibank configuration requires `deleteCustomerPrimaryVpa` and it is omitted | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"deleteCustomerPrimaryVpa is mandatory for Multibank"}` |
| `customerVpa` does not match Newton's configured VPA format rules | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"vpa is not valid"}` |
| A mobile-number VPA does not match the customer's registered mobile number or is not allowed for the merchant mode | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Mobile number used as customerVpa is not valid"}` |
| `customerPrimaryVpa` is not found on the customer's profile | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid customerVpa"}` |
| A normalized form of `customerVpa` already exists for another merchant customer | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Normalized VPA already exists"}` |
| `customerVpa` is already active for another merchant customer, is blocked, or otherwise cannot be claimed | `{"status":"FAILURE","responseCode":"VPA_NOT_AVAILABLE","responseMessage":"CustomerVpa not available"}` |
| `deleteCustomerPrimaryVpa = "true"` and the VPA being deleted has active mandates | `{"status":"FAILURE","responseCode":"JPDL","responseMessage":"You have active mandate(s). Please try again after all the mandates are executed or revoked"}` |
| `deleteCustomerPrimaryVpa = "true"` and the merchant customer has active delegate links | `{"status":"FAILURE","responseCode":"JPADL","responseMessage":"You have active DelegateLink(s). Please try again after all the links are delinked"}` |
| Unexpected server, database, encryption, Passetto, or cache failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

Authentication, signature, and encryption failures can occur before the Add Default VPA business payload is processed. These failures use the standard Newton S2S error body, for example:

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

## Retry and Client Handling

This API does not take a merchant-generated idempotency key. Treat the target operation as the tuple of `merchantCustomerId`, `customerPrimaryVpa`, `customerVpa`, and `deleteCustomerPrimaryVpa`.

- Retry only when the first attempt failed because of a timeout, network failure, `SERVICE_UNAVAILABLE`, `GATEWAY_TIMEOUT`, or an unknown transport outcome.
- If the first attempt may have succeeded, first refresh the customer profile or inspect the latest VPA-account state before retrying a replacement request with `deleteCustomerPrimaryVpa = "true"`.
- Repeating the same request can be safe when `customerVpa` already belongs to the same merchant customer and the account mappings still exist; Newton can reuse the existing VPA record and reapply mappings.
- Do not retry validation failures without changing the request. Examples include invalid VPA format, invalid `merchantCustomerId`, invalid `udfParameters`, missing `iat`, and invalid boolean strings.
- Do not retry `VPA_NOT_AVAILABLE` until the merchant has selected another VPA or the underlying VPA-claim condition has changed.
- For `JPDL` or `JPADL`, complete/revoke active mandates or delink active delegate links before retrying the delete-primary replacement flow.
- Store the successful response and update the merchant cache from `payload.vpaAccounts` and `payload.primaryVpa` when returned.

## Source References

- Route definition: [ServerToServerAPIs](../../src/Newton/App/Routes/Core.hs:325)
- Route handler and signature flow: [addDefaultVpa](../../src/Newton/App/Routes/Core.hs:3262)
- S2S transformer: [addDefaultVpaS2STransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:290)
- Product add-default rules: [Newton.Product.Merchant.Vpa.AddVpa.checkAndAddVpa](../../src/Newton/Product/Merchant/Vpa/AddVpa.hs:42)
- Request and response types: [AddDefaultVpaRequest](../../src/Newton/Types/API/ServerToServer/Vpa.hs:135), [AddDefaultVpaResponse](../../src/Newton/Types/API/ServerToServer/Vpa.hs:171)
- Response builder: [mkAddDefaultVpaResponse](../../src/Newton/Utils/Transformers/Transformer7.hs:91)
- Response version transformer: [mkAddDefaultVpaResponse](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:344)
- Primary VPA and account-mapping helpers: [findPrimaryVpa](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:514), [deleteVpaAndUpdatePrimaryVpa](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:267), [checkAndUpdatePrimaryVpa](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:303), [addVpaAccountsForDefaultVpa](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:431), [satisfiesSecondaryVpaRules](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:535)
- VPA format and availability logic: [satisfiesVpaRules](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:2726), [isVpaAvailable](../../src/Newton/Utils/DB.hs:737), [findOrCreateVpa](../../src/Newton/Utils/DB.hs:705)
- Authentication and envelope middleware: [merchantPayloadVerificationS2S](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69), [merchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request validators and error helpers: [AddDefaultVpaRequest validation](../../src/Newton/Types/API/ServerToServer/Vpa.hs:159), [common validation](../../src/Newton/Validation/Common.hs:168), [API error constants](../../src/Newton/Constants/APIErrorCode.hs:43)
- Nested account response types: [Account and VPAAccount](../../src/Newton/Types/API/Account.hs:12)
