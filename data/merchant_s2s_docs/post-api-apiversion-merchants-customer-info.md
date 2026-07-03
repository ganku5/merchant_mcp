# Customer Info API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/info`

## Overview

Customer Info is a server-to-server API used to fetch Newton's current view of an onboarded merchant customer.

The merchant calls this API with a `merchantCustomerId`. Newton returns the customer's mobile number, bound device details when available, VPA-account mappings, UPI numbers, primary VPA, partner app details for eligible P2M SDK parent merchants, and delegate-link information for supported API versions.

Use this API when the merchant backend needs to refresh customer profile state before showing UPI accounts, initiating customer-side UPI actions, reconciling account/VPA state after onboarding or account management, or validating what Newton has stored for a customer before a follow-up customer workflow.

## Business Use Case

Customer Info helps merchants:

- Confirm that a `merchantCustomerId` exists and is active for the calling merchant.
- Fetch the bank accounts and VPAs linked to a customer profile.
- Discover which VPA is primary/default for UPI payment experiences.
- Refresh bound device metadata and package name after onboarding or activation.
- Retrieve UPI numbers mapped to the customer where supported.
- Retrieve UPI Lite fields on account objects where supported.
- Retrieve partner merchant/app information for enabled P2M SDK parent merchants.
- Retrieve delegate VPAs and linked delegate relationships where supported.

Call this API after customer onboarding/activation, after add-account or VPA-management operations, before rendering a customer account selector, or when a merchant backend needs a server-authoritative customer profile snapshot.

This API is a read/fetch operation. It does not create or mutate customer, account, VPA, or delegate records.

## Integration Flow

1. Merchant backend identifies the Newton `merchantCustomerId` for the customer.
2. Merchant creates the encrypted or signed Newton S2S request envelope.
3. Merchant calls `POST /api/{apiVersion}/merchants/customer/info` with merchant authentication headers and `x-api-version`.
4. Newton decrypts/verifies the request envelope, resolves the merchant and merchant customer, verifies the merchant signature, and checks merchant API allow/block configuration.
5. Newton validates the business payload and fetches customer, device, VPA-account, account, UPI Lite, UPI number, biometric consent, partner, and delegate-link data.
6. Newton returns an encrypted/signed response envelope.
7. Merchant decrypts the response and uses `status`, `responseCode`, and `payload` to update its local customer profile cache or continue the customer journey.

Important identifiers:

- `merchantCustomerId`: Merchant's customer identifier. It scopes authentication, lookup, and the returned customer profile.
- `merchantId` and `merchantChannelId`: Newton merchant identifiers returned in the response payload for the resolved merchant.
- `vpaAccounts[].account.bankAccountUniqueId`: Stable account identifier clients should prefer for follow-up account operations when present.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/info
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Current 13-digit epoch timestamp in milliseconds. Must be within the accepted timestamp window. |
| `x-merchant-signature` | Signature over the configured request signing payload. Required for unsigned/plain envelopes and standard production S2S signing. |
| `x-api-version` | Send the version shared during onboarding. Send `4` or higher if the integration expects all currently version-gated fields documented below. |

Optional headers may include `x-sub-merchant-id`, `x-sub-merchant-channel-id`, and `x-forwarded-for` when configured for the merchant.

Authentication and encryption follow the standard Newton S2S integration process shared during onboarding. The route accepts the common encrypted/signed request envelope types; production integrations should send the signed or encrypted form configured for the merchant. For encrypted/signed payloads, the decrypted business payload must include `iat`; Newton validates it as a timestamp. For the request header timestamp, Newton validates `x-timestamp` separately.

If `x-api-version` is omitted or is not a valid integer, Newton treats this endpoint as version `0`. Version `0` omits several newer response fields.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | Route path segment used by the gateway. Response field gating for this API is controlled by the `x-api-version` header. |

## Request

### Required Minimum

```json
{
  "merchantCustomerId": "CUST10001"
}
```

### With Issued-At and UDF Metadata

Use this shape when the configured envelope/signature flow requires the issued-at timestamp or when the merchant wants Newton to echo request metadata.

```json
{
  "merchantCustomerId": "CUST10001",
  "iat": "1719830400000",
  "udfParameters": "{\"requestId\":\"REQ-10001\",\"source\":\"profile-refresh\"}"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. Empty string is rejected. | Merchant customer identifier to fetch. It must resolve to an active merchant customer for the calling merchant. |
| `iat` | string | Conditional | No default. Required by encrypted/signed envelope validation when applicable. | Issued-at timestamp validated by the S2S authentication middleware for non-plain envelopes. |
| `udfParameters` | string | No | Omitted from the success response when not supplied. | JSON-object string for merchant-defined metadata. Newton validates that it parses as a JSON object and does not contain blocked special characters. Echoed in the success response. |

### Validation Notes

- `merchantCustomerId` must be non-empty.
- The route uses `merchantCustomerId` during merchant signature verification to resolve the merchant customer and customer context.
- `udfParameters`, when supplied, must be a JSON object encoded as a string, for example `"{\"requestId\":\"REQ-10001\"}"`.
- `udfParameters` validation rejects strings that are not JSON objects and strings containing characters blocked by the shared UDF validator regex.
- Missing JSON fields required by the Haskell type, such as `merchantCustomerId`, fail request decoding before business validation.

## Success Response

Success response type: `TfS2S.FetchCustomerInfoResponse`

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "APP",
    "merchantCustomerId": "CUST10001",
    "customerMobileNumber": "9876543210",
    "deviceDetails": {
      "deviceFingerPrint": "android-fingerprint-1",
      "deviceId": "android-fingerprint-1",
      "manufacturer": "Google",
      "model": "Pixel 8",
      "version": "14",
      "os": "ANDROID",
      "ssid": "wifi-network",
      "packageName": "com.merchant.app"
    },
    "upiNumbers": [
      {
        "upiNumber": "9876543210",
        "upiNumberStatus": "ACTIVE",
        "vpa": "customer@bank",
        "expiry": "2026-12-31 23:59:59"
      }
    ],
    "vpaAccounts": [
      {
        "vpa": "customer@bank",
        "account": {
          "bankCode": "HDFC",
          "bankName": "HDFC Bank",
          "maskedAccountNumber": "XXXXXX1234",
          "mpinLength": "6",
          "mpinSet": "true",
          "referenceId": "acc_123",
          "type": "SAVINGS",
          "bankAccountUniqueId": "acct_hash_123",
          "ifsc": "HDFC0001234",
          "isPrimary": "true",
          "name": "Customer Name",
          "otpLength": "6",
          "bankAccountHash": "tpv_hash_123",
          "lrn": "lite-reference-number",
          "isInitialTopUpDone": "true",
          "bioAuthEnabled": "false"
        },
        "isDefault": true
      }
    ],
    "partners": [
      {
        "subMerchantId": "PARTNER001",
        "subMerchantChannelId": "MOBILE",
        "subMerchantName": "Partner App",
        "dateOfOnboarding": "2026-06-01 10:00:00"
      }
    ],
    "primaryVpa": "customer@bank",
    "delegateInfo": {
      "delegateVpas": [
        "delegate.customer@bank"
      ],
      "delegateLinks": [
        {
          "vpa": "customer@bank",
          "linkedVpa": "family.member@bank",
          "linkedName": "Family Member",
          "linkedMobileNumber": "9123456789",
          "linkType": "FULL",
          "userType": "DELEGATOR",
          "status": "LINKED"
        }
      ]
    }
  },
  "udfParameters": "{\"requestId\":\"REQ-10001\",\"source\":\"profile-refresh\"}"
}
```

Clients should treat `status = "SUCCESS"` and `responseCode = "SUCCESS"` as the successful fetch signal. A successful response can still contain empty arrays or omitted optional fields when the customer has no linked records or the requested API version/merchant configuration does not expose that field.

### Response Envelope Fields

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful fetches. |
| `responseCode` | string | `SUCCESS` for successful fetches. |
| `responseMessage` | string | Human-readable message. Success value is `SUCCESS`. |
| `payload` | object | Customer profile snapshot. Present on success. |
| `udfParameters` | string | Echo of request `udfParameters`. Omitted when request `udfParameters` was omitted. |

### Payload Fields

| Field | Type | Version / condition | Description |
| --- | --- | --- | --- |
| `merchantId` | string | Always on success. | Calling merchant id. |
| `merchantChannelId` | string | Always on success. | Calling merchant channel id. |
| `merchantCustomerId` | string | Always on success. | The requested merchant customer id. |
| `customerMobileNumber` | string | Always on success. | Customer mobile number, trimmed before returning. |
| `deviceDetails` | object | Omitted when the merchant customer has no bound device. | Bound device metadata and decrypted device identifiers. |
| `upiNumbers` | array | Returned only when `x-api-version > 0`. Empty array means no UPI numbers were found. Omitted for version `0`. | UPI numbers mapped to the customer. |
| `vpaAccounts` | array | Always on success. Empty array means no active VPA-account mappings were found. | VPA-to-account mappings for this customer. |
| `partners` | array | Only for enabled P2M SDK parent merchants. Omitted otherwise. | Partner/sub-merchant apps associated with the same customer profile. |
| `primaryVpa` | string | Returned only when `x-api-version > 1` and a primary VPA is available. | Customer's primary VPA. |
| `delegateInfo` | object | Returned only when `x-api-version > 2` and delegate info is available. | Delegate VPAs and linked delegate relationships. |

### `deviceDetails`

| Field | Type | Description |
| --- | --- | --- |
| `deviceFingerPrint` | string | Decrypted/derived device fingerprint used for the bound device. |
| `deviceId` | string | Decrypted bound device id. In this response it is sourced from the same decrypted fingerprint value used by the device payload builder. |
| `manufacturer` | string | Device manufacturer. |
| `model` | string | Device model. |
| `version` | string | OS/app device version value stored during binding. |
| `os` | string | Device operating system. |
| `ssid` | string | Decrypted device SSID. |
| `packageName` | string | Merchant app package name stored on the merchant customer. |

If the merchant customer references a device but required device fields are missing in storage, the API can fail with an internal error instead of returning partial `deviceDetails`.

### `upiNumbers[]`

| Field | Type | Description |
| --- | --- | --- |
| `upiNumber` | string | Decrypted UPI number. |
| `upiNumberStatus` | string | UPI number status mapped from Newton's internal status. |
| `vpa` | string | Decrypted VPA to which the UPI number is mapped. |
| `expiry` | string | Expiry timestamp when available. Omitted otherwise. |

Newton verifies that each UPI number maps to a VPA belonging to the expected customer/merchant-customer context. A mismatch returns `INVALID_DATA`.

### `vpaAccounts[]`

| Field | Type | Description |
| --- | --- | --- |
| `vpa` | string | Customer VPA. |
| `account` | object | Account details for the VPA mapping. |
| `isDefault` | boolean | Whether this VPA-account mapping is the default mapping when available. |

### `vpaAccounts[].account`

| Field | Type | Version / condition | Description |
| --- | --- | --- | --- |
| `bankCode` | string | Always when account is returned. | Bank code. |
| `bankName` | string | Always when account is returned. | Bank name. |
| `maskedAccountNumber` | string | Always when account is returned. | Masked account number safe for display. |
| `mpinLength` | string | Always when account is returned. | MPIN credential length. |
| `mpinSet` | string | Always when account is returned. | `"true"` or `"false"` indicating whether MPIN is set. |
| `referenceId` | string | Merchant/PSP mode dependent. | Account reference id. For some multibank flows this can be omitted. |
| `type` | string | Usually present. | Account type, for example savings/current/credit-line value stored by the bank. |
| `branchName` | string | Non-multibank dependent. | Branch name when exposed by the response transformer. |
| `bankAccountUniqueId` | string | When account hash/migrated id exists. | Stable bank-account unique id for follow-up APIs. |
| `ifsc` | string | Usually present. | Account IFSC. |
| `isPrimary` | string | Mapping dependent. | `"true"` when the account is primary for the VPA mapping. |
| `name` | string | Usually present. | Account holder name. |
| `otpLength` | string | Always when account is returned. | OTP credential length. Defaults by behavior to `"6"` when credential metadata does not override it. |
| `atmPinLength` | string | Merchant format/config dependent. | ATM PIN credential length when `enableFormat2` is enabled. |
| `kycStatus` | string | Bank/account dependent. | Account KYC status when available. |
| `accountNumber` | string | Merchant config dependent. | Encrypted account number when configured to return it. |
| `accBIN` | string | Bank/account dependent. | Account BIN when available. |
| `aadhaarEnabled` | string | Flow/config dependent. | Aadhaar OTP support indicator when applicable. |
| `isAadhaarNumberAvailable` | string | Flow/config dependent. | Aadhaar-number availability indicator when applicable. |
| `bankAccountHash` | string | Returned only when `x-api-version > 0` and TPV hash generation is enabled/available. | Account hash with IFSC, used by TPV integrations. |
| `accSubType` | string | Account dependent. | Account subtype, including credit-line subtype when applicable. |
| `allowedMCC` | array of strings | Account dependent. | MCC allow-list when available for the account. |
| `notallowedMCC` | array of strings | Account dependent. | MCC deny-list when available for the account. |
| `lrn` | string | Returned only when `x-api-version > 2` and UPI Lite reference is available. | UPI Lite reference number. |
| `isInitialTopUpDone` | string | Returned only when `x-api-version > 2` and UPI Lite status is available. | `"true"`, `"false"`, or status-like value such as `"topup_txn_pending"`. |
| `liteDetails` | object | Not populated by this S2S route's current transformer because it calls the core route with lite details disabled. | Detailed UPI Lite object used by other flows. |
| `bioAuthConsentUrl` | string | Merchant/account dependent. | Biometric-auth consent URL when available. |
| `bioAuthEnabled` | string | Returned only when `x-api-version > 3` and biometric consent data exists. | Biometric-auth enablement indicator for the account. |
| `credsAllowed` | string | Merchant/account dependent. | Credential metadata when available. |
| `payerAccountHash` | string | Merchant config dependent. | Account-number-only hash when `enablePayerAccountHash` is enabled. |

Optional account fields are omitted rather than returned as `null`.

### `partners[]`

| Field | Type | Description |
| --- | --- | --- |
| `subMerchantId` | string | Partner/sub-merchant id. |
| `subMerchantChannelId` | string | Partner/sub-merchant channel id. |
| `subMerchantName` | string | Partner brand/name when available. |
| `dateOfOnboarding` | string | Customer onboarding/activation time for that partner merchant when available. |

### `delegateInfo`

| Field | Type | Description |
| --- | --- | --- |
| `delegateVpas` | array of strings | Delegate VPAs linked to the merchant customer. |
| `delegateLinks` | array of objects | Linked delegate relationships. Omitted only when unavailable. |

Delegate link objects include decrypted VPA/name/mobile fields plus non-PII link metadata stored for the relationship. Common fields include `vpa`, `linkedVpa`, `linkedName`, `linkedMobileNumber`, `linkType`, `userType`, and `status`.

### Versioned Response Behavior

The response transformer gates some fields using `x-api-version`:

| `x-api-version` | Additional fields included when data exists |
| --- | --- |
| Missing, invalid, or `0` | Base fields only. `upiNumbers`, `primaryVpa`, `delegateInfo`, `bankAccountHash`, `lrn`, `isInitialTopUpDone`, and `bioAuthEnabled` are omitted. |
| `1` | `upiNumbers`, `vpaAccounts[].account.bankAccountHash`. |
| `2` | Version `1` fields plus `primaryVpa`. |
| `3` | Version `2` fields plus `delegateInfo`, `vpaAccounts[].account.lrn`, and `vpaAccounts[].account.isInitialTopUpDone`. |
| `4` and above | Version `3` fields plus `vpaAccounts[].account.bioAuthEnabled`. |

Send the onboarded `x-api-version` explicitly. Do not infer absence of a gated field as absence of the underlying business data unless the request used a version that supports the field.

## Failure Handling

Failure responses use the same encrypted/signed response transport where the request is far enough along for Newton to build the configured response envelope. Some authentication, decoding, and timestamp failures can return an HTTP error status such as `400` or `401`; business validation failures in this service are often returned with HTTP `200` and a decrypted failure body.

Clients should handle both:

- HTTP status for transport/auth/decode failures.
- Decrypted `status`, `responseCode`, and `responseMessage` for Newton business outcomes.

Generic failure body shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "validation message"
}
```

The `payload` field is omitted when the error payload is `Nothing`.

### Request Validation Failure

Empty `merchantCustomerId` fails the request validator.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantCustomerId field is empty\""
}
```

Invalid `udfParameters` fails validation before lookup business logic.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

Client handling: fix the request. Do not retry unchanged.

### Authentication, Signature, or Encryption Failure

Missing merchant headers, invalid request signature, invalid JWS/JWE, invalid key id, or an unrecognized merchant can fail before product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

If the merchant is blocked from this API or its allow-list does not include `fetchCustomerInfo`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If `x-timestamp` is not a 13-digit epoch-millisecond timestamp:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Timestamp must be a 13-digit number"
}
```

If `x-timestamp` or encrypted/signed payload `iat` is outside the accepted timestamp window:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Client handling: regenerate the request envelope, timestamp, and signature. For `API NOT ENABLED`, contact Newton onboarding/support; retries will not help until configuration changes.

### Merchant Customer Lookup or Business Failure

When `merchantCustomerId` does not resolve to an active merchant customer for the calling merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "User profile not found"
}
```

If a resolved context does not match the request customer id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid merchantCustomerId"
}
```

If stored UPI number data points to a VPA that does not belong to the expected customer/merchant-customer mapping:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Vpa mapping missing for upiNumber"
}
```

Client handling: verify that the merchant is using the same `merchantCustomerId` issued/onboarded for this merchant, and refresh local customer mapping. Do not retry unchanged unless the failure is caused by a known eventual-consistency delay immediately after onboarding.

### Downstream or Storage Failure

This API reads multiple storage-backed resources: merchant customer, customer, device, VPA-account mappings, accounts, VPAs, UPI Lite records, UPI number mappings, biometric consent records, partner merchant records, and delegate-link records. Storage or decryption failures can surface as internal errors.

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

If an account/VPA lookup expected by a mapping cannot be found, Newton may return an invalid-data failure such as:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Account not found"
}
```

Client handling: retry transient `INTERNAL_SERVER_ERROR` responses with backoff. For persistent `INVALID_DATA`, treat the local profile as stale and re-run the appropriate onboarding/account refresh workflow or contact Newton support.

### Unexpected Error

Unexpected exceptions, missing required stored device fields, or unhandled decryption/storage errors generally return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with exponential backoff and alert/support if the error persists for the same customer.

## Retry, Idempotency, and Client Handling

- This API is read-only and does not use a merchant idempotency key.
- It is safe to retry after transient transport errors, timeouts, or `INTERNAL_SERVER_ERROR`.
- Do not retry unchanged for validation failures, `UNAUTHORIZED`, `API NOT ENABLED`, or clear `INVALID_DATA` lookup failures.
- Regenerate `x-timestamp`, `iat`, and the signature/encrypted envelope on every retry.
- Cache success responses only as a profile snapshot. Account, VPA, UPI Lite, UPI number, and delegate state can change after other customer workflows.
- Treat omitted optional fields according to API version and merchant configuration. For example, omitted `primaryVpa` on version `0` or `1` does not prove the customer has no primary VPA.
- Use `bankAccountUniqueId` or `referenceId` from returned account objects for follow-up account APIs as specified by the target API guide and merchant configuration.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:279)
- Route handler and auth flow: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:1945)
- S2S transformer: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:191)
- Product/customer-info flow: [src/Newton/Product/Merchant/Customer/GetInfo.hs](../../src/Newton/Product/Merchant/Customer/GetInfo.hs:37)
- Request, response, UPI number, device, and partner types: [src/Newton/Product/Merchant/Customer/Types.hs](../../src/Newton/Product/Merchant/Customer/Types.hs:24)
- Generic response payload and API-version gating: [src/Newton/Services/Transformer/Generic/Helper.hs](../../src/Newton/Services/Transformer/Generic/Helper.hs:15)
- S2S response wrapper: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:58)
- Response payload type: [src/Newton/Services/Transformer/Generic/Types.hs](../../src/Newton/Services/Transformer/Generic/Types.hs:80)
- Account response type: [src/Newton/Types/API/Account.hs](../../src/Newton/Types/API/Account.hs:12)
- Request validation helpers: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- Merchant signature and merchant API configuration checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request envelope verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Error response constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:37)
