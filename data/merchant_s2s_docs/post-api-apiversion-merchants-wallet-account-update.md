# Update Wallet Account API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/wallet/account/update`

## Overview

Update Wallet Account is a merchant server-to-server API used to update an existing wallet-style account record for an already onboarded Newton merchant customer.

The merchant sends the Newton `merchantCustomerId`, the account's `bankAccountUniqueId`, and the fields that should be refreshed. Current product logic can update the stored account holder `name`, the wallet account `kycStatus`, or both. Newton resolves the merchant and customer from the authenticated request, looks up the active account linked to the customer, applies the requested updates, and returns the refreshed account in Newton's common account response format.

Use this API when the merchant backend already created the wallet account through `create`, `createAndLink`, account fetch, or another approved wallet provisioning flow and later needs to refresh the customer's wallet display name or KYC state.

Important limitation: although the S2S request type accepts `accountReferenceId`, the current update transformer does not pass that field into product lookup. For this endpoint, send `bankAccountUniqueId` as the account selector.

## Business Use Case

Update Wallet Account helps merchants:

- Move a wallet account from minimum KYC to full KYC after merchant KYC completion.
- Refresh the account holder display name stored against an existing PPI wallet account.
- Keep Newton's account record aligned with the merchant's wallet/customer system without recreating or relinking the account.
- Receive the refreshed account object for follow-up account, VPA, payment, mandate, UPI number, or balance flows.
- Echo merchant-defined `udfParameters` so the update can be correlated with the merchant's own workflow/session.

This API does not create a wallet account, link a VPA, set a default bank account, update MPIN/credentials, or perform a CBS/wallet balance action.

## Integration Flow

1. Merchant onboards or identifies an existing Newton customer and stores the `merchantCustomerId`.
2. Merchant creates or fetches the wallet account and stores `payload.account.bankAccountUniqueId`.
3. Merchant prepares the decrypted business payload with `merchantCustomerId`, `bankAccountUniqueId`, and `name` and/or `kycStatus`.
4. Merchant wraps the payload in the standard Newton S2S encrypted or signed request envelope and sends merchant authentication headers.
5. Newton verifies the envelope, merchant identity, request timestamp/signature, API enablement, optional IP allowlisting, and merchant-customer ownership.
6. Newton validates the decrypted business payload.
7. Newton looks up the existing active account for the resolved customer and account selector.
8. Newton updates the account fields requested in the payload.
9. Merchant decrypts the response and stores the returned account identifiers/current account state.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton. This API does not create the merchant customer.
- `bankAccountUniqueId`: Account hash/unique id returned by Newton in account responses. For this API, this is the effective account selector.
- `payload.account.referenceId`: Newton account reference id returned when merchant response configuration allows it. Do not use it as the only selector for this update API.

## Endpoint

```http
POST /api/{apiVersion}/merchants/wallet/account/update
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API route version segment. The route itself is mounted under `/api/{apiVersion}`. |

### Headers

Use the headers and key material shared during Newton S2S onboarding.

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type: application/json` | Yes | Request body is JSON. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. Used to resolve the authenticated merchant. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-sub-merchant-id` | Conditional | Required only for configured sub-merchant flows. |
| `x-sub-merchant-channel-id` | Conditional | Required only for configured sub-merchant flows. |
| `x-api-version` | Recommended | Response-version selector used by common middleware and downstream helpers. This API's business fields are not directly version-branched in the current route. |
| `x-timestamp` | Yes | Current 13-digit epoch milliseconds timestamp used for merchant signature and replay validation. Must be within 30 minutes of Newton server time. |
| `x-raw-body` | Yes | Raw request body string used by merchant signature verification for plain/unsigned payload mode. The current middleware expects it on this route. |
| `x-merchant-signature` | Conditional | Required for plain/unsigned business payload transport. JWS/JWE transports are verified by their own envelope signature/decryption path. |
| `x-forwarded-for` | Conditional | Required when the merchant is configured with `whitelistedIps`; Newton checks the first IP in the comma-separated value. |
| `Authorization` | Conditional | Send only when required by the merchant's onboarding profile. |
| `x-request-id` | No | Optional tracing id. Newton generates one when omitted. |

### Authentication and Payload Handling

The route accepts Newton's standard `EncRequest` transport:

| Transport mode | Request body shape | Authentication behavior |
| --- | --- | --- |
| Plain business JSON | Decrypted business payload directly. | Allowed only when configured. Newton verifies `x-merchant-signature` over merchant ids, optional sub-merchant ids, `x-timestamp`, and `x-raw-body`. |
| JWS | `payload`, `signature`, and `protected`. | Newton extracts `kid` from `protected`, verifies the JWS signature, base64url-decodes `payload`, and parses the business JSON. |
| JWE | `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`. | Newton decrypts the JWE, expects a signed JWS payload inside it, then verifies and parses that signed payload. |

For JWS/JWE requests, include `iat` in the decrypted business payload. Newton validates `iat` as a 13-digit epoch milliseconds timestamp within the same 30-minute freshness window. For plain unsigned payloads, `iat` is not required by this route, but `x-timestamp` is still required and checked.

The route authenticates against the API name `updateWalletS2S`. Merchant configuration can block or allow APIs by this name.

## Request

Route request type: `API.EncRequest TfS2S.UpdateWalletRequest`.

Business payload type: `TfS2S.UpdateWalletRequest`.

### Required Minimum

Update the account holder name:

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "5fbbf8f0d5f5b9d6d4a5d3c2e1a0b987",
  "name": "Asha Kumar"
}
```

Update KYC status:

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "5fbbf8f0d5f5b9d6d4a5d3c2e1a0b987",
  "kycStatus": "FULL"
}
```

Signed or encrypted production payloads should include a fresh `iat`:

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "5fbbf8f0d5f5b9d6d4a5d3c2e1a0b987",
  "name": "Asha Kumar",
  "kycStatus": "FULL",
  "iat": "1783000000000"
}
```

Generate `iat` and `x-timestamp` at request time. The values above illustrate the required 13-digit epoch-milliseconds format.

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id already registered with Newton for the authenticated merchant. Must be 1 to 256 characters and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. |
| `bankAccountUniqueId` | string | Yes for this API's current product path | No default. If omitted, product lookup fails with `bankAccountUniqueId or accountReferenceId is mandatory`. | Account hash/unique id returned by Newton in `payload.account.bankAccountUniqueId`. Must be non-empty when supplied. This is the effective account selector for this endpoint. |
| `accountReferenceId` | string | No | Accepted and validated when supplied, but not used by the current update product path. | Newton account reference id. Do not send it as the only selector for this endpoint. If both `accountReferenceId` and `bankAccountUniqueId` are sent, lookup still uses `bankAccountUniqueId`. |
| `name` | string | No | If omitted, the stored account name is preserved. | New account holder/customer display name. Current request validation does not reject an empty string, so merchants should omit the field when no name change is intended and should not send empty names. |
| `kycStatus` | string | No | If omitted, the stored KYC status is preserved. | New wallet KYC status. Accepted values are `MIN` and `FULL`. Invalid values fail JSON parsing before business validation. |
| `iat` | string | Conditional | No business default. Required by middleware for signed/encrypted envelopes; ignored by the product logic. Plain unsigned payloads skip the `iat` check. | Issued-at timestamp used by S2S envelope/signature verification. Use 13-digit epoch milliseconds unless Newton onboarding specifies otherwise. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | Merchant-defined metadata as a JSON-object string. It is validated as JSON text and echoed back at the top level of the response. It is not used by wallet account update logic. |

There are no nested business request objects for this API. The only nested request objects are the standard JWS/JWE transport envelopes.

### Defaults and Omitted Field Behavior

- `merchantCustomerId` is required at JSON parsing/type level.
- `bankAccountUniqueId` is optional in the Haskell type but required by the current product lookup path for this route.
- `accountReferenceId` is validated if present, but the transformer drops it when building the core update request.
- `name` has no default. Omission preserves the current stored name. Supplying `name` updates the stored encrypted name and name hash.
- `kycStatus` has no default. Omission preserves the current stored KYC status. Supplying `kycStatus` updates the stored KYC status.
- If both `name` and `kycStatus` are omitted, the route performs no account-field update and returns the current account details.
- `iat` is optional in the Haskell request type, but signed/encrypted envelopes are rejected by middleware when it is missing.
- `udfParameters` has no default. When present, it must be a valid JSON-object string and must not contain characters rejected by the validator.
- The request does not include `merchantId` or `merchantChannelId` in the decrypted business payload. Newton reads them from headers.
- The request does not update `accountNumber`, `ifsc`, `bankCode`, `bankName`, account type, MPIN state, credentials, VPA links, or primary/default status.

Unknown JSON fields are ignored by normal record parsing, but required fields and validators still apply.

## Request Examples

### Update Name Only

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "5fbbf8f0d5f5b9d6d4a5d3c2e1a0b987",
  "name": "Asha Kumar",
  "iat": "1783000000000"
}
```

### Update KYC Status Only

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "5fbbf8f0d5f5b9d6d4a5d3c2e1a0b987",
  "kycStatus": "FULL",
  "iat": "1783000000000"
}
```

### Update Name and KYC Status With Merchant Metadata

```json
{
  "merchantCustomerId": "CUST67890",
  "bankAccountUniqueId": "2cf0ef61a7f5dd26d8a97640a22b2f98",
  "name": "Rahul Sharma",
  "kycStatus": "FULL",
  "iat": "1783000000000",
  "udfParameters": "{\"walletProgram\":\"GOLD\",\"source\":\"kyc-service\"}"
}
```

### No-Op Refresh

This request returns the current account details without changing `name` or `kycStatus`. Use it only when a refresh of the common account response is intentional.

```json
{
  "merchantCustomerId": "CUST12345",
  "bankAccountUniqueId": "5fbbf8f0d5f5b9d6d4a5d3c2e1a0b987",
  "iat": "1783000000000"
}
```

### Account Reference Id Alone Is Not Enough

The request type accepts this shape, but the current product path does not use `accountReferenceId` for lookup. It is expected to fail with `bankAccountUniqueId or accountReferenceId is mandatory`.

```json
{
  "merchantCustomerId": "CUST12345",
  "accountReferenceId": "acc_9f2c4a7b1d",
  "name": "Asha Kumar",
  "iat": "1783000000000"
}
```

## Validation and Processing Behavior

### Request Validation

Newton performs these validations after the payload is decrypted or otherwise verified:

- `merchantCustomerId` must be non-empty, at most 256 characters, and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`.
- `bankAccountUniqueId`, when supplied, must be non-empty.
- `accountReferenceId`, when supplied, must be non-empty.
- `kycStatus`, when supplied, must parse as `MIN` or `FULL`.
- `udfParameters`, when supplied, must be a JSON-object string and must pass Newton's restricted-character regex. It must parse as a JSON object and must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or the backtick character.
- `name` is not checked by this request validator. Supplying an empty string is not rejected by validation and can update the stored name to an empty value.

When request validation fails, Newton returns `BAD_REQUEST` with a comma-joined list of serialized validation errors. The exact `responseMessage` can contain one or more field errors depending on the submitted payload.

### Authentication and Merchant Context

Before product validation, Newton:

- Resolves the merchant from `x-merchant-id` and `x-merchant-channel-id`.
- Resolves and validates optional sub-merchant headers.
- Verifies JWS/JWE payloads or merchant signature for plain payloads.
- Validates `iat` for JWS/JWE requests.
- Validates `x-timestamp` for all request modes, except configured checksum bypass behavior in limited non-production environments.
- Checks merchant `blockedApiNames` and `allowedApiNames` for API name `updateWalletS2S`.
- Checks `x-forwarded-for` against `whitelistedIps` when configured.
- Resolves `merchantCustomerId` under the authenticated merchant and resolves the linked active customer.

### Product Processing

On a valid request, Newton:

1. Reads the authenticated merchant, merchant customer, and customer from middleware context.
2. Looks up the account using `bankAccountUniqueId` and the resolved merchant/customer context.
3. For standard Newton merchant flows, requires the account to be linked through an active merchant-customer-account mapping. For P2M SDK enabled flows, lookup can use the resolved customer account directly.
4. If `name` is supplied and `kycStatus` is omitted, encrypts the new name, computes the name hash, and preserves the existing KYC status.
5. If `kycStatus` is supplied and `name` is omitted, decrypts the existing name to recompute the name hash and updates KYC status.
6. If both `name` and `kycStatus` are supplied, encrypts the new name, computes the name hash, and updates KYC status.
7. If neither field is supplied, skips the database update and uses the existing account record.
8. Decrypts account PII for response shaping.
9. Builds the common account response using merchant configuration such as multibank response behavior, `includeAccountReferenceId`, `enableFormat2`, TPV/account-hash settings, payer-account-hash settings, unmasked account response settings, and the configured default branch name.

### Idempotency and Duplicate Handling

This API does not take `merchantRequestId` and does not implement order-style idempotency.

Repeated calls with the same `merchantCustomerId`, `bankAccountUniqueId`, `name`, and `kycStatus` are effectively state-setting updates. They should converge to the same stored account state and are not expected to return `DUPLICATE_REQUEST` from the wallet product path.

Recommended client behavior:

- Retry network timeouts with the same payload when the intended state is unchanged.
- Do not use `accountReferenceId` alone for this API; store and send `bankAccountUniqueId`.
- Do not send `name` when there is no name change.
- Do not send empty `name` values. Omit the field instead.
- Store the refreshed `payload.account.bankAccountUniqueId` and, when returned, `payload.account.referenceId` for follow-up APIs.

## Response

Route response type: `RespHeaders (API.EncResponse TfS2S.UpdateWalletResponse)`.

Business response type: `TfS2S.UpdateWalletResponse`.

### Response Envelope

After decryption, a successful response has this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Refreshed wallet account details. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id from the request/authenticated context. |
| `account` | object | Updated or refreshed account in Newton's common account response format. |

### `payload.account` Fields

The account object is shared with other account APIs, so some fields are configuration-dependent and may be omitted.

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Bank code/IIN stored on the wallet account. |
| `bankName` | string | Bank name stored on the wallet account. |
| `maskedAccountNumber` | string | Masked account number stored for the account. |
| `mpinLength` | string | MPIN length stored for the account. Wallet-created accounts commonly derive this from merchant wallet configuration. |
| `mpinSet` | string | `"true"` or `"false"` based on the stored account MPIN state and merchant customer response configuration. |
| `referenceId` | string | Newton account reference id. Omitted for multibank-style response behavior unless merchant configuration enables `includeAccountReferenceId`; for ICICI mode it can use migrated id behavior. |
| `type` | string | Account type stored for the account, for example `PPIWALLET`, `BANKWALLET`, or `CREDIT`. |
| `branchName` | string | Omitted when multibank response behavior is enabled. Otherwise populated from account branch name or the configured default branch name. |
| `bankAccountUniqueId` | string | Newton account hash/unique id. Use this value in later update requests. |
| `ifsc` | string | IFSC stored for the account. |
| `isPrimary` | string | Omitted by this route because the response is built without a merchant-customer-account object. |
| `name` | string | Decrypted account holder/customer display name after the update. |
| `otpLength` | string | OTP credential length derived from stored account credential metadata. Defaults to `"6"` when not present in `credsAllowed`. |
| `atmPinLength` | string | ATM PIN credential length. Present when `enableFormat2` response behavior is enabled for the merchant. |
| `kycStatus` | string | Wallet KYC status after the update, `MIN` or `FULL`. |
| `accountNumber` | string | Encrypted account number when merchant unmasked-account response is enabled. Omitted when unmasked-account response is not enabled. |
| `accBIN` | string | Present for credit-account use cases when a BIN can be derived. |
| `bankAccountHash` | string | Present when TPV/account-hash response behavior is enabled for the merchant. |
| `payerAccountHash` | string | Present when `enablePayerAccountHash` is enabled for the merchant. |
| `accSubType` | string | Returned only when the stored account record has an account subtype. |
| `aadhaarEnabled`, `isAadhaarNumberAvailable`, `allowedMCC`, `notallowedMCC`, `lrn`, `isInitialTopUpDone`, `liteDetails`, `bioAuthConsentUrl`, `bioAuthEnabled`, `credsAllowed` | mixed | Omitted by this route because the update response is not built in Aadhaar OTP, UPI Lite, MCC-list, biometric, or explicit `credsAllowed` response mode. |

### Example Success Response

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST12345",
    "account": {
      "bankCode": "999999",
      "bankName": "Newton Wallet Bank",
      "maskedAccountNumber": "XXXX0001",
      "mpinLength": "4",
      "mpinSet": "false",
      "referenceId": "acc_9f2c4a7b1d",
      "type": "PPIWALLET",
      "bankAccountUniqueId": "5fbbf8f0d5f5b9d6d4a5d3c2e1a0b987",
      "ifsc": "NWLT0000001",
      "name": "Asha Kumar",
      "otpLength": "6",
      "atmPinLength": "4",
      "kycStatus": "FULL"
    }
  }
}
```

### Example Success Response With `udfParameters`

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST67890",
    "account": {
      "bankCode": "999999",
      "bankName": "Newton Wallet Bank",
      "maskedAccountNumber": "XXXX0999",
      "type": "PPIWALLET",
      "bankAccountUniqueId": "2cf0ef61a7f5dd26d8a97640a22b2f98",
      "ifsc": "NWLT0000001",
      "name": "Rahul Sharma",
      "otpLength": "6",
      "kycStatus": "FULL"
    }
  },
  "udfParameters": "{\"walletProgram\":\"GOLD\",\"source\":\"kyc-service\"}"
}
```

## Error Handling

Failure responses use the same encrypted response transport as successful responses when the request reaches the S2S envelope layer. The examples below show decrypted bodies.

Most failures follow one of these shapes:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

When `payload` is empty, it is omitted from the JSON response. HTTP status can be `200`, `400`, `401`, or `500` depending on the layer that rejects the request. Clients should use `status`, `responseCode`, and `responseMessage` from the decrypted body as the integration contract.

### Update Wallet Account Failure Bodies

The exact parser text for malformed JSON, missing JSON fields, or enum parsing can vary by runtime library version. The examples below use the concrete response body pattern returned by the code and representative parser messages.

| Scenario | Response body |
| --- | --- |
| Missing required JSON field `merchantCustomerId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $: key \"merchantCustomerId\" not found"}` |
| `kycStatus` is not `MIN` or `FULL` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $.kycStatus: expected one of MIN, FULL"}` |
| `merchantCustomerId` is empty or longer than 256 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` |
| `merchantCustomerId` has invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| `bankAccountUniqueId` is supplied as an empty string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"Field is empty\""}` |
| `accountReferenceId` is supplied as an empty string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"Field is empty\""}` |
| Multiple validation failures in the same request | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\", LengthValidation \"Field is empty\""}` |
| `udfParameters` is not a valid JSON-object string or contains rejected characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| `bankAccountUniqueId` is omitted | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"bankAccountUniqueId or accountReferenceId is mandatory"}` |
| Only `accountReferenceId` is sent as account selector | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"bankAccountUniqueId or accountReferenceId is mandatory"}` |
| Missing `x-merchant-id`, `x-merchant-channel-id`, `x-raw-body`, `x-timestamp`, or required signature material | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Merchant headers do not resolve to an enabled merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| JWS signature verification fails, JWE decryption fails, merchant request signature mismatches, or IP allowlisting rejects the request | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| JWS `protected` header is missing `kid` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Error in finding KID"}` |
| JWE `protected` header is missing `kid` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Error in finding kId"}` |
| JWE decrypts but the inner signed payload cannot be parsed | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: key \"payload\" not found"}` |
| API is blocked or not allowed for the merchant or sub-merchant configuration | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| Signed/encrypted envelope is missing `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| `iat` or `x-timestamp` is not a 13-digit epoch-milliseconds timestamp | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` |
| `iat` or `x-timestamp` is outside the accepted current-time window | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` |
| `merchantCustomerId` does not belong to the authenticated merchant, is inactive, or is not found | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"User profile not found"}` |
| Merchant customer exists but has no active customer binding | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer"}` |
| Customer linked to the merchant customer is inactive or not found | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Customer not found"}` |
| `bankAccountUniqueId` does not resolve to an account for the resolved customer/merchant-customer mapping | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Account not found"}` |
| Account mapping exists but the account record is inactive or cannot be used as an active account | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Account update fails unexpectedly while writing name/KYC status | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Passetto, account-name encryption/decryption, or name-hash configuration is incomplete | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Response account formatting needs `mpinLength` but the stored account has no MPIN length | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Response account-number encryption is enabled but the required merchant encryption key is missing | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid getEncryptedAccountNumber : encryptionKey not found"}` |
| Database, cache, configuration, decrypt, or other unexpected server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

### Client Handling Guidance

- Treat `SUCCESS` as final success and persist the returned account identifiers/current account state.
- Treat `BAD_REQUEST` as non-retryable until the request payload or envelope timestamp is corrected.
- Treat `UNAUTHORIZED`, `AUTH_FAILURE`, and `API NOT ENABLED` as non-retryable until headers, keys, signature, timestamp, IP allowlist, or merchant API configuration are corrected.
- Treat `INVALID_DATA` as non-retryable when it identifies merchant/customer/account state, such as `User profile not found`, `Customer not found`, or `Account not found`.
- Retry `REQUEST_EXPIRED` only by generating a fresh request envelope, `iat`, `x-timestamp`, and signature.
- Retry `INTERNAL_SERVER_ERROR` only with bounded backoff and the same intended state. Because this API sets account fields rather than creates a transaction, retrying the same payload is safe when the intended `name` and/or `kycStatus` have not changed.
- If the client times out after sending the request, retry with the same payload, then reconcile using account fetch/customer-info and `bankAccountUniqueId`.
- Do not retry with `accountReferenceId` alone; use `bankAccountUniqueId` returned by Newton account APIs.

## Source References

- Route type: [Newton.App.Routes.Core.WalletS2SAPIs](../../src/Newton/App/Routes/Core.hs:1255)
- Route handler: [Newton.App.Routes.Core.updateWalletS2S](../../src/Newton/App/Routes/Core.hs:4833)
- Request and response types: [Newton.Services.Transformer.ServerToServer.Types.UpdateWalletRequest/UpdateWalletResponse](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4094)
- S2S transformer: [Newton.Services.Transformer.ServerToServer.Core.updateWalletTransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:840)
- S2S helper mapping: [Newton.Services.Transformer.ServerToServer.Helper.mkCoreUpdateWalletRequest/mkUpdateWalletResponse](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1573)
- Product route and update behavior: [Newton.Product.Merchant.Wallet.UpdateWallet](../../src/Newton/Product/Merchant/Wallet/UpdateWallet.hs:25)
- Product request/response payloads: [Newton.Product.Merchant.Wallet.Types](../../src/Newton/Product/Merchant/Wallet/Types.hs:85)
- Wallet helper response construction and context lookup: [Newton.Product.Merchant.Wallet.Helper](../../src/Newton/Product/Merchant/Wallet/Helper.hs:67)
- KYC status enum: [Newton.Types.Storage.Account.KYCStatus](../../src/Newton/Types/Storage/Account.hs:70)
- Common account response type: [Newton.Types.API.Account.Account](../../src/Newton/Types/API/Account.hs:10)
- Request validation helper: [Newton.Utils.Utils.validateRequestBody](../../src/Newton/Utils/Utils.hs:251)
- Field validators: [Newton.Validation.Common](../../src/Newton/Validation/Common.hs:174)
- Merchant payload verification: [Newton.App.Middlewares.Authentication.MerchantPayloadVerification.merchantPayloadVerificationS2S](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature verification: [Newton.App.Middlewares.Authentication.MerchantSignatureVerificationV2.merchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:45)
- Merchant customer and customer lookup: [Newton.Utils.DB.findMerchantCustomer/findCustomerFromMerchantCustomer](../../src/Newton/Utils/DB.hs:106)
- Account lookup: [Newton.Utils.DB.getAccount/getMerchantCustomerAccount](../../src/Newton/Utils/DB.hs:540)
- Account update query: [Newton.Storage.QueriesMiddleware.Account.updatePPIAccount](../../src/Newton/Storage/QueriesMiddleware/Account.hs:312)
- Account response formatting: [Newton.Utils.Transformers.Transformer.getApiAccount](../../src/Newton/Utils/Transformers/Transformer.hs:438)
- Response account-number encryption: [Newton.Utils.Utils.getEncryptedAccountNumber](../../src/Newton/Utils/Utils.hs:2614)
- Error constants: [Newton.Constants.APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:43)
