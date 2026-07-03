# Delete VPA API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/vpas/deleteVpa`

## Overview

Delete VPA is a server-to-server API used to remove a customer's UPI VPA from the merchant customer's Newton profile.

The merchant calls this API when a customer deletes a VPA, changes their preferred VPA, deregisters a UPI profile, or otherwise needs a VPA unlinked from the accounts held against the merchant customer. Newton deletes the requested VPA and its account mappings, updates the replacement primary VPA where applicable, and returns the remaining VPA-account state for the customer.

Use this API only after the customer has completed the merchant-side action that authorizes the VPA removal.

## Business Use Case

Delete VPA helps merchants:

- Remove a customer VPA that should no longer be usable in the merchant UPI experience.
- Keep the customer's VPA-account list in sync after profile management or deregistration flows.
- Promote another existing customer VPA as primary when the deleted VPA was primary.
- Block deletion when the VPA still has active mandates or active delegate links.
- Reconcile the customer's remaining VPA-account mappings after deletion.

## Integration Flow

1. Merchant identifies the `merchantCustomerId` and the `customerVpa` to delete.
2. If required for the merchant configuration, merchant also selects a different existing `customerPrimaryVpa` to become primary after deletion.
3. Merchant calls `deleteVpa` using the standard Newton encrypted S2S request and signature process.
4. Newton validates the request, merchant signature, merchant customer profile, VPA ownership, and deletion rules.
5. Newton deletes the VPA and active VPA-account mappings when deletion is allowed.
6. Newton returns the remaining VPA-account mappings and, for response versions greater than `0`, the current `primaryVpa` when available.
7. Merchant updates its customer profile cache from the response.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. This scopes the customer profile used for the delete operation.
- `customerVpa`: The VPA to delete.
- `customerPrimaryVpa`: The VPA to mark as primary after deletion where required or desired.

## Endpoint

```http
POST /api/{apiVersion}/merchants/vpas/deleteVpa
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | Use `1` or higher if the client needs `payload.primaryVpa` in the response. Missing or non-numeric values are treated as `0`. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. Signed/encrypted calls must include valid request timestamps and signature headers as configured for the merchant.

## Request

### Required Minimum

For non-multibank merchants where `customerPrimaryVpa` is required, send:

```json
{
  "merchantCustomerId": "CUST12345",
  "customerVpa": "oldvpa@bank",
  "customerPrimaryVpa": "newprimary@bank",
  "iat": "1719835200000"
}
```

For multibank-enabled merchants, `customerPrimaryVpa` can be omitted when Newton can proceed without an explicit replacement:

```json
{
  "merchantCustomerId": "CUST12345",
  "customerVpa": "oldvpa@bank",
  "iat": "1719835200000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Newton uses it to load the merchant customer profile and scope the VPA deletion. Length must be 1 to 256 characters. Allowed characters are letters, numbers, dot, underscore, plus, slash, equals, and hyphen, with the first character limited to letters, numbers, plus, slash, or equals. |
| `customerVpa` | string | Yes | No default. | Customer VPA to delete. Must be non-empty and must belong to the merchant customer profile. |
| `customerPrimaryVpa` | string | Conditional | No default for non-multibank, non-ICICI flows where it is required. For multibank or ICICI flows, omission is allowed. | Existing customer VPA to set or keep as primary after deleting `customerVpa`. When deleting the current primary VPA and the customer has more than one VPA, send a different existing VPA. |
| `iat` | string | Yes for signed/encrypted S2S calls | No default. Missing `iat` is rejected before deletion logic. | Issued-at timestamp used for request signature validation. Send a 13-digit Unix timestamp in milliseconds within the allowed clock-skew window. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | JSON-object string for merchant-defined metadata. Echoed in the success response. The value must parse as a JSON object string and must not contain disallowed special characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |

### Defaults and Omitted Field Behavior

Fields not listed here have no default and are not stored or returned when omitted.

- `customerPrimaryVpa`: Required for non-multibank merchants when the merchant PSP mode is not ICICI. For multibank-enabled merchants, an already-deleted `customerVpa` is treated as a successful no-op and Newton returns the remaining profile state. For allowed flows where it is omitted and deletion proceeds, Newton may select another customer VPA as primary where applicable.
- `iat`: Required by the signature middleware for signed/encrypted requests, even though the business request type is nullable. Missing `iat` returns an `INVALID_DATA` response.
- `udfParameters`: Echoed on success only when supplied.
- `x-api-version`: If the header is missing or not an integer, Newton uses response version `0`, which omits `payload.primaryVpa`.

### Deletion and Primary VPA Rules

- `customerVpa` is deleted only from the profile identified by `merchantCustomerId`.
- The deleted VPA's active VPA-account mappings are also removed.
- The response returns the remaining active VPA-account mappings for the customer.
- If the deleted VPA is the only VPA for the merchant customer, the customer profile is marked as no longer account-linked.
- If the VPA has active mandates, deletion is rejected. Revoke or let the mandates complete before retrying.
- If the merchant customer has active delegate links, deletion is rejected. Delink them before retrying.
- If the current primary VPA is being deleted while other VPAs exist, do not set `customerPrimaryVpa` to the same value as `customerVpa`.

## Request Examples

### Delete VPA and Set Replacement Primary VPA

```json
{
  "merchantCustomerId": "CUST12345",
  "customerVpa": "cust.old@bank",
  "customerPrimaryVpa": "cust.primary@bank",
  "iat": "1719835200000",
  "udfParameters": "{\"reason\":\"customer_profile_update\"}"
}
```

### Multibank Delete Without Explicit Replacement

```json
{
  "merchantCustomerId": "CUST12345",
  "customerVpa": "cust.old@bank",
  "iat": "1719835200000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Delete VPA result. Present on success. |
| `udfParameters` | string | Echoed from request when supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant identifier configured with Newton. |
| `merchantChannelId` | string | Merchant channel identifier. |
| `merchantCustomerId` | string | Merchant customer id for the profile on which the VPA was deleted. |
| `customerMobileNumber` | string | Present only for multibank-enabled merchants. Returned as the trimmed customer mobile number. |
| `vpaAccounts` | array | Remaining active VPA-account mappings after deletion. Each item contains the VPA, linked account details, and default flag when available. |
| `primaryVpa` | string | Present only when `x-api-version > 0` and a primary VPA is available. Omitted for response version `0`. |

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA still linked after deletion. |
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
        "vpa": "cust.primary@bank",
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
  "udfParameters": "{\"reason\":\"customer_profile_update\"}"
}
```

### Multibank Success Response

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
    "vpaAccounts": [],
    "primaryVpa": "cust.primary@bank"
  }
}
```

## Response Versioning

Use `x-api-version: 1` or higher for new integrations that need the replacement/current primary VPA in the response.

| `x-api-version` | Response behavior |
| --- | --- |
| `0`, missing, or non-numeric | Legacy response. `payload.primaryVpa` is omitted. |
| `1` or higher | Includes `payload.primaryVpa` when a primary VPA is available. |

The path parameter `{apiVersion}` is still required by the route. The `x-api-version` header controls response-version behavior for this API.

## Retry and Idempotency

This API does not take a merchant-generated idempotency key. Treat `merchantCustomerId` plus `customerVpa` as the operation target.

- For multibank-enabled merchants, retrying a delete for a VPA that is already deleted can return `SUCCESS` with the remaining profile state.
- For non-multibank merchants, retrying a delete for an already-deleted VPA returns `INVALID_DATA` with `customerVpa already deleted`.
- For retry safety, store the successful response and update your customer profile cache from the latest `vpaAccounts` array.

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

The exact `responseCode` and `responseMessage` depend on the validation or business rule that failed. When `payload` is empty, it is omitted from the JSON response.

Clients should read `status`, `responseCode`, and `responseMessage` from the body. Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, or `500`; the body is the stable integration contract.

### Delete VPA Failure Bodies

Use the body pattern shown in the `Response body` column for each scenario.

| Scenario | Response body |
| --- | --- |
| Request body cannot be decoded as JSON | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Request"}` |
| `customerVpa` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"customerVpa field is empty\""}` |
| `customerPrimaryVpa` is sent as an empty string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"Field is empty\""}` |
| `merchantCustomerId` is empty or longer than 256 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` |
| `merchantCustomerId` contains unsupported characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| `udfParameters` is not a valid JSON-object string or contains disallowed characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| Signed/encrypted request is missing `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| `iat` or request timestamp is not a 13-digit millisecond timestamp | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` |
| `iat` or request timestamp is outside the allowed clock-skew window | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` |
| Merchant customer profile cannot be found for `merchantCustomerId` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"User profile not found"}` |
| Merchant customer has no active customer/device binding | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer"}` |
| `customerVpa` does not exist for the customer profile | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Vpa not found"}` |
| Non-multibank, non-ICICI request omits `customerPrimaryVpa` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"customerPrimaryVpa is mandatory"}` |
| Non-multibank request deletes a VPA that is already deleted | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"customerVpa already deleted"}` |
| `customerPrimaryVpa` is supplied but is not present on the customer profile | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"invalid customerPrimaryVpa"}` |
| Deleting a primary VPA while asking Newton to keep the same VPA as primary and the customer has another VPA | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Cannot delete primary Vpa"}` |
| The VPA has active mandates | `{"status":"FAILURE","responseCode":"JPDL","responseMessage":"You have active mandate(s). Please try again after all the mandates are executed or revoked"}` |
| The merchant customer has active delegate links | `{"status":"FAILURE","responseCode":"JPADL","responseMessage":"You have active DelegateLink(s). Please try again after all the links are delinked"}` |
| Delete VPA API is not enabled for the merchant or is blocked by merchant configuration | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| Signature, IP whitelist, required signature header, or merchant-authentication validation fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Unexpected server, database, encryption, or cache failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

Authentication, signature, and encryption failures can occur before the delete-VPA business payload is processed. These failures use the standard Newton S2S error body, for example:

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

## Source References

- Route definition: [ServerToServerAPIs](../../src/Newton/App/Routes/Core.hs:299)
- Route handler and signature flow: [deleteVpa](../../src/Newton/App/Routes/Core.hs:2139)
- S2S transformer: [deleteVpaS2STransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:298)
- Product deletion rules: [Newton.Product.Merchant.Vpa.DeleteVpa](../../src/Newton/Product/Merchant/Vpa/DeleteVpa.hs:41)
- Primary VPA and delete helper: [deleteVpaAndUpdatePrimaryVpa](../../src/Newton/Utils/BusinessLogic/VpaHelper.hs:267)
- Request and response types: [DeleteVpaRequest](../../src/Newton/Types/API/ServerToServer/Vpa.hs:204), [DeleteVpaResponse](../../src/Newton/Types/API/ServerToServer/Vpa.hs:238)
- Response builder: [mkDeleteVpaResponse](../../src/Newton/Utils/Transformers/Transformer9.hs:5219)
- Nested account response types: [Account and VPAAccount](../../src/Newton/Types/API/Account.hs:12)
- Request validators and error helpers: [VPA validators](../../src/Newton/Types/API/ServerToServer/Vpa.hs:227), [common validation](../../src/Newton/Validation/Common.hs:168), [API error constants](../../src/Newton/Constants/APIErrorCode.hs:43)
