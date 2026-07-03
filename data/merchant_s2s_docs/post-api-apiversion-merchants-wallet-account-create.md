# Create Wallet Account API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/wallet/account/create`

## Overview

Create Wallet Account is a merchant server-to-server API used to create or update a wallet-style account record for an already onboarded Newton merchant customer.

The merchant sends the Newton merchant customer id and a PPI account object containing the wallet/account number, customer name, account type, and KYC status. Newton resolves the merchant and customer from the authenticated request, builds the account using wallet configuration stored for the merchant, upserts the account for that customer, creates or reactivates the merchant-customer-account mapping, and returns the created account details plus optional VPA suggestions.

Use this API when the merchant backend already has a Newton `merchantCustomerId` and needs to seed or refresh that customer's wallet account before later VPA linking, account fetch, payment, mandate, or UPI number flows. This endpoint only creates/updates the account mapping; it does not link the account to a customer VPA. Use `POST /api/{apiVersion}/merchants/wallet/account/createAndLink` when account creation and VPA linking must happen in the same call.

## Business Use Case

Create Wallet Account helps merchants:

- Create a PPI wallet or wallet-like account record for an existing merchant customer.
- Update the stored customer name and KYC status when the same account is sent again.
- Ensure the account is active and mapped to the merchant customer.
- Receive account metadata in Newton's common account response format for follow-up calls.
- Receive suggested VPAs that can be shown during a subsequent VPA creation or linking journey.
- Trigger downstream account sync for remitter-switch-enabled merchants.

## Integration Flow

1. Merchant onboards or identifies an existing Newton customer and stores the `merchantCustomerId`.
2. Merchant prepares the decrypted business payload with `merchantCustomerId` and `account`.
3. Merchant wraps the payload in the standard Newton S2S encrypted or signed request envelope and sends merchant authentication headers.
4. Newton verifies the envelope, merchant identity, request timestamp/signature, API enablement, optional IP allowlisting, and merchant customer ownership.
5. Newton validates the decrypted business payload.
6. Newton creates or updates the account using merchant wallet configuration such as `ifsc`, `bankCode`, and `bankName`.
7. Newton creates or reactivates the merchant-customer-account mapping.
8. Merchant decrypts the response and stores the returned account identifiers for follow-up calls.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier registered with Newton. This API does not create the merchant customer.
- `account.accountNumber`: Wallet/account number used with the merchant-configured IFSC to compute the account hash and account unique id.
- `payload.account.referenceId`: Newton account reference id when returned for the merchant configuration.
- `payload.account.bankAccountUniqueId`: Newton account hash/unique id for the created account.

## Endpoint

```http
POST /api/{apiVersion}/merchants/wallet/account/create
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-api-version` | Use the version shared during onboarding. This API's business payload is not version-branched in the current route. |
| `x-timestamp` | Required by merchant signature verification. Must be a valid current timestamp. |
| `x-raw-body` | Required by merchant signature verification. Newton uses it while verifying the request signature. |
| `x-merchant-signature` | Required for plain/unsigned payload mode. Signed or encrypted envelopes are verified by their own envelope signature/decryption path. |

Optional sub-merchant headers, when enabled for the merchant:

| Header | Value |
| --- | --- |
| `x-sub-merchant-id` | Sub-merchant id. |
| `x-sub-merchant-channel-id` | Sub-merchant channel id. |

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. The route accepts `JWE`, `JWS`, and plain JSON envelope shapes at the type level, but production merchant integrations should use the onboarding-approved envelope.

### Request and Response Envelope

The decrypted examples in this guide show only the business payload. On the wire, the request body is one of the standard untagged S2S envelope shapes:

| Envelope mode | JSON fields | Notes |
| --- | --- | --- |
| Encrypted request (`JWE`) | `protected`, `encryptedKey`, `iv`, `cipherText`, `tag` | Newton decrypts the business payload and then validates `iat` from the decrypted payload. |
| Signed request (`JWS`) | `payload`, `signature`, `protected` | Newton verifies the envelope signature and then validates `iat` from the decoded payload. |
| Plain request | Business payload fields directly | Supported by the route type and useful in controlled environments. It still goes through merchant header and request-signature verification. |

The response uses the same family of response envelope shapes. After decryption or signature verification, clients receive either the success body shown in this guide or an error body with `status`, `responseCode`, and `responseMessage`.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API route version segment. The route itself is mounted under `/api/{apiVersion}`. |

## Request

### Required Minimum

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "900000000001",
    "name": "Asha Kumar",
    "type": "PPIWALLET",
    "kycStatus": "MIN"
  }
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id already registered with Newton for the authenticated merchant. Must be 1 to 256 characters and match `^[a-zA-Z0-9+/=][a-zA-Z0-9._+/=-]*$`. |
| `account` | object | Yes | No default. | Wallet/PPI account details to create or update. See `account` field reference below. |
| `iat` | string | Conditional | No business default. Required by middleware for signed/encrypted envelopes; ignored by the product logic. Plain unsigned payloads skip the `iat` check. | Issued-at timestamp used by S2S envelope/signature verification. Use the format specified during onboarding. |
| `udfParameters` | string | No | Omitted from the response if not supplied. | Merchant-defined metadata as a JSON-object string. It is validated as JSON text and echoed back at the top level of the response. It is not used by wallet account creation logic. |

### `account`

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `accountNumber` | string | Yes | No default. | Wallet/account number. Current validator only requires a non-empty value for this API. Newton combines it with the merchant-configured `ifsc` to compute `bankAccountUniqueId`/account hash. |
| `name` | string | Yes | No default. | Account holder/customer display name. Current validator only requires a non-empty value. If the account already exists for the customer, Newton updates the stored name. |
| `type` | string | Yes | No default. Invalid values fail JSON parsing before business validation. | Account type accepted by the code: `PPIWALLET`, `BANKWALLET`, or `CREDIT`. Use the type approved for your wallet product during onboarding. |
| `kycStatus` | string | Yes | No default. Invalid values fail JSON parsing before business validation. | KYC status accepted by the code: `MIN` or `FULL`. If the account already exists for the customer, Newton updates the stored KYC status. |

### Defaults and Omitted Field Behavior

- `merchantCustomerId` and `account` are required at JSON parsing/type level.
- `account.accountNumber`, `account.name`, `account.type`, and `account.kycStatus` are required at JSON parsing/type level.
- `iat` is optional in the Haskell request type, but signed/encrypted envelopes are rejected by middleware when it is missing.
- `udfParameters` has no default. When present, it must be a valid JSON-object string and must not contain characters rejected by the validator.
- The request does not include `merchantId` or `merchantChannelId` in the decrypted business payload. Newton reads them from headers.
- The request does not include `ifsc`, `bankCode`, or `bankName`. Newton reads them from merchant configuration.
- The request does not include a VPA. This API does not link the account to a VPA.

### Request Examples

#### Minimum PPI Wallet Account

```json
{
  "merchantCustomerId": "CUST12345",
  "account": {
    "accountNumber": "900000000001",
    "name": "Asha Kumar",
    "type": "PPIWALLET",
    "kycStatus": "MIN"
  }
}
```

#### Full-KYC Wallet Account With Merchant Metadata

```json
{
  "merchantCustomerId": "CUST67890",
  "account": {
    "accountNumber": "900000000999",
    "name": "Rahul Sharma",
    "type": "PPIWALLET",
    "kycStatus": "FULL"
  },
  "iat": "1782997200000",
  "udfParameters": "{\"walletProgram\":\"GOLD\",\"source\":\"merchantBackend\"}"
}
```

#### Bank-Wallet Type

```json
{
  "merchantCustomerId": "CUSTBANK001",
  "account": {
    "accountNumber": "910000000111",
    "name": "Neha Rao",
    "type": "BANKWALLET",
    "kycStatus": "FULL"
  }
}
```

## Validation and Processing Behavior

### Request Validation

Newton performs these validations after the payload is decrypted or otherwise verified:

- `merchantCustomerId` must be non-empty, at most 256 characters, and match the merchant customer id regex.
- `account.accountNumber` must be non-empty.
- `account.name` must be non-empty.
- `account.type` must parse as `PPIWALLET`, `BANKWALLET`, or `CREDIT`.
- `account.kycStatus` must parse as `MIN` or `FULL`.
- `udfParameters`, when supplied, must be a JSON-object string and must pass the configured character regex.

The code does not apply the common bank-account numeric regex to `account.accountNumber` in this API. Merchants should still send the exact account-number format agreed during wallet onboarding because Newton uses the value to compute the account hash.

### Product Processing

On a valid request, Newton:

1. Reads the authenticated merchant, merchant customer, and customer from middleware context.
2. Reads merchant wallet configuration keys: `ifsc`, `bankCode`, and `bankName`.
3. Reads optional wallet credential configuration such as `mpinSet`, `aadharEnabled`, `mpinLength`, `otpCredLength`, `atmPinCredLength`, `aadharOtpCredLength`, and `mobRegFormat`.
4. Computes the account hash from `account.accountNumber` and the configured IFSC.
5. Builds an account record with active status, masked account number, configured bank metadata, requested account type, requested name, and requested KYC status.
6. Encrypts sensitive account fields for storage.
7. Updates an existing account with the same account hash and customer id, or creates a new account if none exists.
8. Creates or reactivates the merchant-customer-account mapping for the account.
9. If remitter switch is enabled for the merchant, starts an account-sync call to Turing.
10. Builds the response account object and VPA suggestions.

### Idempotency and Duplicate Handling

This API does not take `merchantRequestId` and does not implement order-style idempotency.

Repeated calls with the same `merchantCustomerId` and the same `account.accountNumber` for the same merchant-configured IFSC are effectively upserts: Newton updates the stored account name and KYC status, ensures the account is active, and ensures the merchant-customer-account mapping exists. A duplicate request is therefore not expected to return `DUPLICATE_REQUEST` from the wallet product path.

Recommended client behavior:

- Retry network timeouts with the same payload when the intended state is the same.
- Do not use this API to create the merchant customer; call the customer onboarding/activation flow first.
- Store `payload.account.bankAccountUniqueId` and, when returned, `payload.account.referenceId` for follow-up APIs.
- Use the companion create-and-link API if the next step must atomically link the account to a VPA.

## Response

### Response Envelope

After decryption, a successful response has this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API status. Success value is `SUCCESS`. |
| `responseCode` | string | Response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Response message. Success value is `SUCCESS`. |
| `payload` | object | Created or updated wallet account details. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `account` | object | Created or updated account in Newton's common account response format. |
| `vpaSuggestions` | array of strings | Suggested VPAs for the customer. Present when the suggestion helper returns values; omitted when not available. |

### `payload.account` Fields

The account object is shared with other account APIs, so some fields are configuration-dependent and may be omitted.

| Field | Type | Description |
| --- | --- | --- |
| `bankCode` | string | Merchant-configured bank code/IIN for this wallet program. |
| `bankName` | string | Merchant-configured bank name for this wallet program. |
| `maskedAccountNumber` | string | Masked account number, built as `XXXX` plus the last four characters of `account.accountNumber`. |
| `mpinLength` | string | Merchant-configured MPIN length. Defaults to `"0"` when not configured. |
| `mpinSet` | string | `"true"` or `"false"` based on merchant configuration. Defaults by code to `"false"` when `mpinSet` is not configured. |
| `referenceId` | string | Newton account reference id. In this route, it can be omitted for multibank-style response behavior unless merchant configuration enables `includeAccountReferenceId`. |
| `type` | string | Account type stored for the account, for example `PPIWALLET`. |
| `branchName` | string | Usually omitted by this route because the response is built in multibank mode. |
| `bankAccountUniqueId` | string | Newton account hash/unique id computed from account number and configured IFSC. |
| `ifsc` | string | Merchant-configured IFSC used for the wallet account. |
| `isPrimary` | string | Usually omitted by this route because account creation does not set primary status. |
| `name` | string | Account holder/customer name from the request. |
| `otpLength` | string | OTP credential length. Defaults to `"6"` when not configured. |
| `atmPinLength` | string | ATM PIN credential length. Present when `enableFormat2` response behavior is enabled for the merchant. |
| `kycStatus` | string | Requested KYC status, `MIN` or `FULL`. |
| `accountNumber` | string | Encrypted account number when merchant unmasked-account response is enabled. Omitted when unmasked-account response is not enabled. |
| `accBIN` | string | Present for credit-account use cases when a BIN can be derived. |
| `bankAccountHash` | string | Present when TPV/account-hash response behavior is enabled for the merchant. |
| `credsAllowed` | string | JSON string describing allowed credentials when merchant `mobRegFormat` configuration produces one. |
| `payerAccountHash` | string | Present when `enablePayerAccountHash` is enabled for the merchant. |
| `aadhaarEnabled`, `isAadhaarNumberAvailable`, `accSubType`, `allowedMCC`, `notallowedMCC`, `lrn`, `isInitialTopUpDone`, `liteDetails`, `bioAuthConsentUrl`, `bioAuthEnabled` | mixed | Common account fields used by other account products. They are generally omitted by this wallet-create route unless populated by shared account transformation/configuration. |

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
      "kycStatus": "MIN"
    },
    "vpaSuggestions": [
      "asha.kumar@wallet",
      "asha9001@wallet"
    ]
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
  "udfParameters": "{\"walletProgram\":\"GOLD\",\"source\":\"merchantBackend\"}"
}
```

## Error Handling

Failure responses use the same encrypted response transport as successful responses when the request reaches the S2S envelope layer. The examples below show decrypted bodies.

Most failures follow one of these shapes:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"accountNumber field is empty\""
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

When `payload` is empty, it is omitted from the JSON response. HTTP status can be `200`, `400`, `401`, or `500` depending on the layer that rejects the request. Clients should use `status`, `responseCode`, and `responseMessage` from the decrypted body as the integration contract.

### Create Wallet Account Failure Bodies

The exact parser text for malformed JSON or enum parsing can vary by runtime library version. The examples below use the concrete body pattern returned by the code and representative parser messages.

| Scenario | Response body |
| --- | --- |
| Missing required JSON field such as `merchantCustomerId`, `account`, `account.accountNumber`, `account.name`, `account.type`, or `account.kycStatus` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $: key \"merchantCustomerId\" not found"}` |
| `account.type` is not one of `PPIWALLET`, `BANKWALLET`, `CREDIT` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $.account.type: expected one of PPIWALLET, BANKWALLET, CREDIT"}` |
| `account.kycStatus` is not `MIN` or `FULL` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Error in $.account.kycStatus: expected one of MIN, FULL"}` |
| `merchantCustomerId` is empty or longer than 256 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` |
| `merchantCustomerId` has invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| `account.accountNumber` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"accountNumber field is empty\""}` |
| `account.name` is empty | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"name field is empty\""}` |
| Multiple validation failures in the same request | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\", LengthValidation \"accountNumber field is empty\", LengthValidation \"name field is empty\""}` |
| `udfParameters` is not a valid JSON-object string or contains rejected characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| Missing `x-merchant-id`, `x-merchant-channel-id`, `x-raw-body`, `x-timestamp`, or required signature material | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| Merchant headers do not resolve to an enabled merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| JWS signature verification fails, merchant request signature mismatches, or IP allowlisting rejects the request | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| API is blocked or not allowed for the merchant or sub-merchant configuration | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| Signed/encrypted envelope is missing `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` |
| Timestamp is malformed | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid timestamp format"}` |
| Timestamp is outside the accepted current-time window | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Timestamp difference with actual current time"}` |
| `merchantCustomerId` does not belong to the authenticated merchant, is inactive, or is not found | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"User profile not found"}` |
| Merchant customer exists but has no active customer binding | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"No active device binding for merchantCustomer"}` |
| Customer linked to the merchant customer is inactive or not found | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Customer not found"}` |
| Required merchant wallet configuration such as `ifsc`, `bankCode`, or `bankName` is missing | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Passetto/hash configuration is incomplete while sensitive-field hashing is enabled | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Account upsert returns no row after insert | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Wallet Account not created"}` |
| Account or merchant-customer-account database update fails unexpectedly | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |
| Merchant-customer-account reactivation unexpectedly cannot find the row it just selected | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Account not found"}` |
| Response account-number encryption is enabled but the required merchant encryption key is missing | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid getEncryptedAccountNumber : encryptionKey not found"}` |
| Optional remitter-switch account sync to Turing fails | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` |

### Client Handling Guidance

- Treat `SUCCESS` as final success and persist the returned account identifiers.
- Treat `BAD_REQUEST` as non-retryable until the request payload is corrected.
- Treat `UNAUTHORIZED` and `AUTH_FAILURE` as non-retryable until headers, keys, signature, timestamp, or API enablement are corrected.
- Treat `INVALID_DATA` as non-retryable when it identifies merchant/customer/account state, such as `User profile not found` or `Customer not found`.
- Retry `INTERNAL_SERVER_ERROR` only with bounded retries and the same payload. Since this API upserts by account hash and customer id, retrying the same payload is safe for the same desired account state.
- If the client times out after sending the request, retry with the same `merchantCustomerId` and `account` values, then reconcile using `bankAccountUniqueId` or a follow-up account fetch.

## Source References

- Route type: [Newton.App.Routes.Core.WalletS2SAPIs](../../src/Newton/App/Routes/Core.hs:1260)
- Route handler: [Newton.App.Routes.Core.createWalletS2S](../../src/Newton/App/Routes/Core.hs:4815)
- Request and response types: [Newton.Services.Transformer.ServerToServer.Types.CreateWalletRequest/CreateWalletResponse](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4046)
- S2S transformer: [Newton.Services.Transformer.ServerToServer.Core.createWalletTransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:833)
- S2S helper mapping: [Newton.Services.Transformer.ServerToServer.Helper.mkCoreCreateWalletRequest/mkCreateWalletResponse](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1560)
- Product route: [Newton.Product.Merchant.Wallet.CreateWallet.coreCreateWalletRoute](../../src/Newton/Product/Merchant/Wallet/CreateWallet.hs:23)
- Product request/response payloads: [Newton.Product.Merchant.Wallet.Types](../../src/Newton/Product/Merchant/Wallet/Types.hs:56)
- Wallet account helper and merchant configuration behavior: [Newton.Product.Merchant.Wallet.Helper](../../src/Newton/Product/Merchant/Wallet/Helper.hs:41)
- PPI account request type and validation: [Newton.Types.Intermediate.PPIAccount](../../src/Newton/Types/Intermediate.hs:821)
- KYC status enum: [Newton.Types.Storage.Account.KYCStatus](../../src/Newton/Types/Storage/Account.hs:70)
- Request validation helper: [Newton.Utils.Utils.validateRequestBody](../../src/Newton/Utils/Utils.hs:251)
- Merchant payload verification: [Newton.App.Middlewares.Authentication.MerchantPayloadVerification.merchantPayloadVerificationS2S](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Request/response envelope type: [Newton.Types.API.RequestBody.EncRequest/EncResponse](../../src/Newton/Types/API/RequestBody.hs:48)
- Merchant signature verification: [Newton.App.Middlewares.Authentication.MerchantSignatureVerificationV2.merchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Merchant customer and customer lookup: [Newton.Utils.DB.findMerchantCustomer/findCustomer](../../src/Newton/Utils/DB.hs:106)
- Account upsert: [Newton.Storage.QueriesMiddleware.Account.updateNameAndKycStatusOrCreateOneByAccountHash](../../src/Newton/Storage/QueriesMiddleware/Account.hs:38)
- Merchant-customer-account mapping: [Newton.Product.Merchant.Account.Helper.findOrCreateMerchantCustomerAccounts](../../src/Newton/Product/Merchant/Account/Helper.hs:373)
- Response account-number encryption: [Newton.Utils.Utils.getEncryptedAccountNumber](../../src/Newton/Utils/Utils.hs:2614)
- Error constants: [Newton.Constants.APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:43)
