# Update Sub-Merchant API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/sub/update`

## Overview

Update Sub-Merchant is a Newton server-to-server API used by an aggregator or parent merchant to update an already onboarded sub-merchant.

Use this API after `POST /api/{apiVersion}/merchants/sub/add` when sub-merchant metadata changes, when the sub-merchant must be enabled or disabled, when callback URLs must be updated, or when sub-merchant level configuration such as direct-pay blocking, SMS notification, payer account types, or allowed APIs must change.

The API is patch-style: `subMerchantId` and `subMerchantChannelId` identify the existing sub-merchant, and only fields supplied in the request are updated. Omitted optional fields keep their existing stored values unless a feature-specific rule below says otherwise.

## Business Use Case

Aggregator merchants use this API to:

- Update sub-merchant profile and business metadata.
- Enable or disable a sub-merchant without deleting it.
- Update callbacks used for transaction, mandate, refund, dispute, delegate, and other Newton callback events.
- Restrict or expand API access for a disabled sub-merchant through `configurations`.
- Update payer account type rules for sub-merchant UPI acceptance.
- Update sub-merchant agent contact details used by configured notification flows.

This API does not change the sub-merchant VPA, primary account number, or IFSC. The response returns the existing primary VPA and account details after the update.

## Integration Flow

1. Parent merchant identifies the sub-merchant by `subMerchantId` and `subMerchantChannelId`.
2. Parent merchant sends the fields to be changed in the encrypted or signed S2S request envelope.
3. Newton validates the merchant, signature, timestamp, IP allow-list, API access rules, and request body.
4. Newton confirms the caller is an aggregator and that the sub-merchant belongs to the parent merchant.
5. Newton updates merchant metadata, merchant info, callbacks, and configurations as applicable.
6. Newton returns the updated sub-merchant identifiers, VPA/account summary, MCC, enabled flag, callback list, and echoed `udfParameters`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/sub/update
```

Payloads use the standard Newton S2S encrypted request and response envelope. Examples in this guide show decrypted business payloads for readability.

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment shared during onboarding. No update-specific behavior change was found in product logic for this endpoint. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Use `application/json`. |
| `x-merchant-id` | Yes | Parent merchant id assigned by Newton. |
| `x-merchant-channel-id` | Yes | Parent merchant channel id assigned by Newton. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness after signature/envelope verification. |
| `x-raw-body` | Yes | Raw request body captured by the gateway/middleware. It is part of signature verification for unsigned/plain payloads. |
| `x-merchant-signature` | Conditional | Required for plain unsigned JSON transport. Signature is verified over merchant ids, optional sub-merchant ids, timestamp, and raw body. |
| `Authorization` | Conditional | Used by configured signed/encrypted transport flows when shared during onboarding. |
| `x-forwarded-for` | Conditional | Required when the parent merchant has IP allow-listing configured. The first IP in the header must be allow-listed. |
| `x-sub-merchant-id` | No for this API | Do not use this to identify the sub-merchant being updated. Send the target sub-merchant in the body. |
| `x-sub-merchant-channel-id` | No for this API | Do not use this to identify the sub-merchant being updated. Send the target sub-merchant in the body. |

### Authentication, Signing, and Encryption

Newton accepts the standard S2S request envelope variants:

- Encrypted payload.
- Signed payload.
- Plain unsigned business payload, only when the merchant is configured for signature verification and sends `x-merchant-signature`.

For signed or encrypted payloads, the decrypted business payload must include `iat`; Newton rejects the request if `iat` is absent or not a valid timestamp. For plain unsigned payloads, `iat` is optional.

For plain unsigned payloads, the signature material is:

```text
x-merchant-id + x-merchant-channel-id + x-sub-merchant-id + x-sub-merchant-channel-id + x-timestamp + x-raw-body
```

The sub-merchant header parts are empty strings when the headers are not present. The API also checks merchant blocked APIs, merchant/sub-merchant allowed APIs, and IP restrictions before product logic runs.

## Request

### Minimum Request

```json
{
  "subMerchantId": "SUBMERCHANT001",
  "subMerchantChannelId": "ONLINE"
}
```

A minimum request is valid and behaves as a no-op update, except it still returns the current sub-merchant response and may refresh related cache entries.

### Enable or Disable a Sub-Merchant

```json
{
  "subMerchantId": "SUBMERCHANT001",
  "subMerchantChannelId": "ONLINE",
  "enabled": "false",
  "udfParameters": "{\"requestId\":\"SM-UPD-1001\"}"
}
```

### Update Profile, Callbacks, and Configurations

`callbackUrls` is a string containing a JSON array, not a nested JSON array field.

```json
{
  "subMerchantId": "SUBMERCHANT001",
  "subMerchantChannelId": "ONLINE",
  "merchantName": "Newton Test Store",
  "marketingName": "Newton Store",
  "displayName": "Newton Store Indiranagar",
  "mcc": "5411",
  "city": "Bengaluru",
  "address": "12 MG Road",
  "state": "Karnataka",
  "pinCode": "560001",
  "countryCode": "+91",
  "mobileNumber": "919876543210",
  "callbackUrls": "[{\"type\":\"MERCHANT_CREDITED_VIA_PAY\",\"url\":\"https://merchant.example/callbacks/pay\",\"query\":\"mutation Callback($input: CallbackInput!) { callback(input: $input) }\"}]",
  "configurations": [
    {
      "config": "BLOCK_DIRECT_PAY",
      "value": "true"
    },
    {
      "config": "ENABLE_SMS_NOTIFICATION",
      "value": "true"
    },
    {
      "config": "PAYER_ACC_TYPES_ALLOWED",
      "action": "ADD",
      "value": [
        {
          "accType": "SAVINGS",
          "limit": 5000,
          "limitType": "SMALL",
          "vpaHandles": ["okaxis", "upi"]
        }
      ]
    }
  ],
  "agentPhoneNumbers": ["919876543210"],
  "agentEmails": ["ops@example.com"],
  "iat": "2026-07-02T10:15:30+05:30"
}
```

## Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `subMerchantId` | string | Yes | No default. | Merchant-scoped sub-merchant id to update. Max 256 characters. Allowed characters: letters, numbers, space, underscore, plus, dot, hyphen. |
| `subMerchantChannelId` | string | Yes | No default. | Merchant-scoped channel id for the sub-merchant. Same validation as `subMerchantId`. |
| `mcc` | string | No | Existing MCC is retained. | Four-digit numeric MCC. Product logic also validates MCC through the configured MCC validator. |
| `enabled` | string | No | Existing enabled state is retained. | Boolean string, `true` or `false`, case-insensitive. When changed, Newton also updates the sub-merchant VPA active/status flags, associated VPA-account active flags, and account/merchant-account active flags. |
| `callbackUrls` | string | No | Existing callbacks are retained. An empty string also leaves callbacks unchanged. | Stringified JSON array of callback URL objects. Each object has `type`, `url`, and optional `query`. Existing callback rows are updated by callback `type`; new types are created. |
| `merchantName` | string | No | Existing value is retained. | Legal/display merchant name stored in merchant info. Length 1 to 100. Also updates account name unless `displayName` is supplied. |
| `marketingName` | string | No | Existing value is retained. | Marketing name. Length 1 to 50. |
| `displayName` | string | No | Existing value is retained. | Customer-facing display name. Length 1 to 100. If supplied, account name updates use this instead of `merchantName`. |
| `city` | string | No | Existing value is retained. | City. Length 1 to 50. |
| `address` | string | No | Existing value is retained. | Address. Length 1 to 200. |
| `state` | string | No | Existing value is retained. | State. Length 1 to 50. |
| `pinCode` | string | No | Existing value is retained. | Six-digit numeric postal code. |
| `countryCode` | string | No | Existing value is retained. | Optional country code used while validating `mobileNumber`. Max 7 characters. Must be numeric with optional leading `+`. |
| `mobileNumber` | string | No | Existing value is retained. | Numeric mobile number. If `countryCode` is omitted, exactly 12 digits are expected. If `countryCode` is supplied, length must be less than 19 digits. |
| `ownerName` | string | No | Existing value is retained. | Owner name. Length 1 to 50. |
| `partner1` | string | No | Existing value is retained. | Partner/contact field. Length 1 to 50. |
| `partner2` | string | No | Existing value is retained. | Partner/contact field. Length 1 to 50. |
| `mccDescription` | string | No | Existing value is retained. | MCC description. Length 1 to 255. |
| `gstin` | string | No | Existing value is retained. | GSTIN or tax identifier. Length 1 to 20. No GSTIN checksum validation was found for this endpoint. |
| `panNumber` | string | No | Existing value is retained. | PAN value. Must be exactly 10 uppercase alphanumeric characters. If present, Newton generates or updates the merchant identifier code in the sub-merchant store when it differs from the existing value. |
| `aadhaarNumber` | string | No | Existing value is retained. | Aadhaar value. Code accepts either 12 numeric digits or an 8-character masked form, although the masked regex in source appears restrictive. |
| `mid` | string | No | Existing MID is retained. | MID in sub-merchant info. Length 1 to 20. |
| `sid` | string | No | Existing SID is retained. | SID in sub-merchant info. Length 1 to 20. |
| `tid` | string | No | Existing TID is retained. | TID in sub-merchant info. Length 1 to 20. |
| `merchantType` | string | No | Existing value is retained. | Allowed values: `SMALL`, `LARGE`. |
| `merchantGenre` | string | No | Existing value is retained. | Allowed values: `ONLINE`, `OFFLINE`. |
| `onBoardingType` | string | No | Existing value is retained. | Allowed values: `BANK`, `AGGREGATOR`. |
| `brand` | string | No | Existing value is retained. | Brand name. Must be alphanumeric with spaces only and length 1 to 99. |
| `legal` | string | No | Existing value is retained. | Legal name. Must be alphanumeric with spaces only and length 1 to 99. |
| `franchise` | string | No | Existing value is retained. | Franchise name. Must be alphanumeric with spaces only and length 1 to 99. |
| `type` | string | No | Existing value is retained. | Ownership type. Allowed values: `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. |
| `configurations` | array | No | Existing configurations are retained. | Sub-merchant configuration changes. See nested reference below. |
| `udfParameters` | string | No | Omitted from response when absent. | Stringified JSON object for merchant metadata. Must parse as a JSON object and must not contain restricted characters such as `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. Echoed in response. |
| `iat` | string | Conditional | Optional for plain unsigned payloads. | Required for signed/encrypted payloads. Must be a valid timestamp accepted by Newton timestamp validation. |
| `agentPhoneNumbers` | array of strings | No | Existing values are retained. | Agent phone numbers. Each number is validated like `mobileNumber` without `countryCode`, so exactly 12 numeric digits are expected. Empty array is accepted by validation but is converted internally to `["Empty list"]`. |
| `agentEmails` | array of strings | No | Existing values are retained. | Agent email addresses. Each item must pass email validation. |

## Nested Request Objects

### `callbackUrls`

`callbackUrls` is sent as a stringified JSON array. Newton decodes it into callback objects.

```json
"[{\"type\":\"MERCHANT_CREDITED_VIA_PAY\",\"url\":\"https://merchant.example/callbacks/pay\",\"query\":\"mutation Callback($input: CallbackInput!) { callback(input: $input) }\"}]"
```

Decoded callback object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string | Yes | Newton callback type, for example `MERCHANT_CREDITED_VIA_PAY`, `MERCHANT_CREDITED_VIA_COLLECT`, `MANDATE_STATUS_UPDATE`, `CUSTOMER_ONLINE_REFUND`, `MERCHANT_DEBITED_VIA_REFUND`, `MERCHANT_COMPLAINT_RAISED`, `DELEGATE_LINK_STATUS`, or another Newton callback type enabled for the merchant. Unknown Newton callback values parse as `UNDEFINED`. |
| `url` | string | Yes | Merchant callback endpoint URL. No URL-format validator was found beyond JSON decoding for this API. |
| `query` | string | No | Optional GraphQL query or callback query text stored with the callback. |

Callback update behavior:

- If `callbackUrls` is omitted, existing callbacks are returned unchanged.
- If `callbackUrls` is an empty string, existing callbacks are returned unchanged.
- If a decoded callback `type` already exists for the sub-merchant, Newton updates its `url` and `query`.
- If a decoded callback `type` does not exist, Newton creates it.
- The response `payload.callbackUrls` is also a stringified JSON array.

### `configurations[]`

Each configuration object must contain a supported `config` value. Unknown values fail JSON parsing with `UNKNOWN_CONFIG`.

| `config` | Request shape | Behavior |
| --- | --- | --- |
| `BLOCK_DIRECT_PAY` | `{ "config": "BLOCK_DIRECT_PAY", "value": "true" }` | Stores `blockDirectPay` in the sub-merchant store. `value` is interpreted as a boolean string. |
| `ENABLE_SMS_NOTIFICATION` | `{ "config": "ENABLE_SMS_NOTIFICATION", "value": "true" }` | Upserts merchant configuration `enableSmsNotification` for the sub-merchant. |
| `PAYER_ACC_TYPES_ALLOWED` | `{ "config": "PAYER_ACC_TYPES_ALLOWED", "action": "ADD", "value": [...] }` | Adds or removes allowed payer account type rules. `action` is optional; supported behavior is `ADD` or `REMOVE`. If no existing config exists and `action` is `REMOVE`, no new config is created. |
| `ALLOW_TXN_STATUS` | `{ "config": "ALLOW_TXN_STATUS", "action": "ADD" }` | Adds/removes the transaction-status API group in `allowedApiNames` when the sub-merchant is disabled. |
| `ALLOW_REFUND` | `{ "config": "ALLOW_REFUND", "action": "ADD" }` | Adds/removes the refund API group in `allowedApiNames` when the sub-merchant is disabled. |
| `ALLOW_TXN_LIST` | `{ "config": "ALLOW_TXN_LIST", "action": "ADD" }` | Adds/removes list-transactions access in `allowedApiNames` when the sub-merchant is disabled. |
| `ALLOW_LIST_MANDATE` | `{ "config": "ALLOW_LIST_MANDATE", "action": "ADD" }` | Adds/removes list-mandate access in `allowedApiNames` when the sub-merchant is disabled. |
| `ALLOW_MANDATE_STATUS` | `{ "config": "ALLOW_MANDATE_STATUS", "action": "ADD" }` | Adds/removes mandate-status access in `allowedApiNames` when the sub-merchant is disabled. |

Important behavior for `ALLOW_*` configs:

- When the updated sub-merchant is enabled, Newton resets `allowedApiNames` to an empty list, meaning the sub-merchant is not restricted by this allow-list.
- When the updated sub-merchant is disabled, Newton applies `ADD` and `REMOVE` actions to the relevant API groups.
- If `enabled` changes and no `ALLOW_*` config is provided, Newton upserts `allowedApiNames` as an empty list.

#### `PAYER_ACC_TYPES_ALLOWED.value[]`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `accType` | string | Yes | Account type, for example `SAVINGS`, as configured for the merchant. |
| `limit` | number | No | Optional limit for this account type. |
| `limitType` | string | No | Optional limit type. Allowed values in storage type are `SMALL` and `LARGE`. |
| `vpaHandles` | array of strings | No | Optional allowed VPA handles for the account type. |

## Validation Rules

Newton applies request validation before product updates:

- `subMerchantId` and `subMerchantChannelId` are mandatory and must pass merchant id format validation.
- `mcc`, if supplied, must be four numeric digits and must pass product MCC validation.
- `enabled`, if supplied, must be `true` or `false`.
- `callbackUrls`, if supplied and non-empty, must be a string containing a JSON array of callback URL objects.
- Length limits apply to all profile fields as listed in the field reference.
- `pinCode` must be exactly six numeric digits.
- `countryCode` must be numeric with optional leading `+` and max length 7.
- `mobileNumber` length depends on whether `countryCode` is supplied.
- `panNumber` must be exactly 10 uppercase alphanumeric characters.
- `aadhaarNumber` accepts only the formats implemented in validation.
- `merchantType`, `merchantGenre`, `onBoardingType`, and `type` must match their allowed values exactly.
- `brand`, `legal`, and `franchise` allow only letters, numbers, and spaces, with length 1 to 99.
- `agentPhoneNumbers` entries must be 12-digit numeric strings.
- `agentEmails` entries must pass email validation.
- `udfParameters` must be a stringified JSON object and must pass restricted-character validation.

Product/business validations:

- The caller must resolve to a valid parent merchant.
- The parent merchant must be configured as an aggregator.
- The target sub-merchant must exist under the parent merchant, matched by `subMerchantId` and `subMerchantChannelId`.
- The sub-merchant primary merchant account must exist.
- The sub-merchant merchant-info row must exist.
- If merchant IP allow-listing is configured, the request IP must be allow-listed.
- If blocked APIs or allowed APIs are configured, this API must be permitted for the caller.

## Success Response

Newton returns the standard encrypted S2S response envelope. After decryption, the business response has this shape:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "PARENTMERCHANT",
    "merchantChannelId": "ONLINE",
    "subMerchantId": "SUBMERCHANT001",
    "subMerchantChannelId": "ONLINE",
    "vpa": "submerchant001@upi",
    "maskedAccountNumber": "XXXXXX1234",
    "ifsc": "HDFC0000001",
    "mcc": "5411",
    "enabled": "true",
    "callbackUrls": "[{\"type\":\"MERCHANT_CREDITED_VIA_PAY\",\"url\":\"https://merchant.example/callbacks/pay\",\"query\":\"mutation Callback($input: CallbackInput!) { callback(input: $input) }\"}]",
    "agentPhoneNumbers": ["919876543210"]
  },
  "udfParameters": "{\"requestId\":\"SM-UPD-1001\"}"
}
```

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful updates. |
| `responseCode` | string | `SUCCESS` for successful updates. |
| `responseMessage` | string | `SUCCESS` for successful updates. |
| `payload` | object | Updated sub-merchant summary. |
| `udfParameters` | string | Echoes request `udfParameters` when supplied. Omitted otherwise. |

### `payload`

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Parent merchant id. |
| `merchantChannelId` | string | Parent merchant channel id. |
| `subMerchantId` | string | Sub-merchant id from the request. |
| `subMerchantChannelId` | string | Sub-merchant channel id from the request. |
| `vpa` | string | Existing primary sub-merchant VPA, decrypted for the response. |
| `maskedAccountNumber` | string | Existing masked primary account number on the sub-merchant merchant account. |
| `ifsc` | string | Existing IFSC on the sub-merchant merchant account. |
| `mcc` | string | Updated or existing sub-merchant MCC. |
| `enabled` | string | Updated or existing enabled state as `true` or `false`. |
| `callbackUrls` | string | Stringified JSON array of callbacks after the update. |
| `agentPhoneNumbers` | array of strings | Returned from the request when supplied. Omitted when absent. |
| `configurations` | array | Not returned by this update response; product code sets it to `null`/omits it. Use Sub-Merchant Info to fetch stored configuration parameters where supported. |

`agentEmails` is accepted and stored but is not present in the update response type.

## Failure Scenarios

Failure responses use the same S2S response transport as success responses when the failure occurs after response encryption can be applied. Authentication, JSON decoding, or envelope failures may be returned by the gateway/middleware before business payload decryption is possible.

### Request Validation Failure

Invalid request fields fail before product logic. Example for invalid `enabled`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "BoolStringValidation \"Parameter is not true or false\""
}
```

Example for invalid callback JSON:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"callbackUrls type not supported\""
}
```

Example for invalid MCC length:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mcc length is not 4\""
}
```

### Invalid or Unknown Configuration

Unknown `config` values fail JSON parsing for `ConfigurationBody`. Depending on where parsing fails in the envelope flow, the client may receive a bad-request style response rather than the business response shape.

Client-facing example:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UNKNOWN_CONFIG"
}
```

### Authentication, Signature, Timestamp, or Encryption Failure

Missing merchant headers, invalid signature, invalid encrypted/signed payload `iat`, stale `x-timestamp`, invalid envelope, or missing `x-raw-body` fail before product logic.

Common decrypted/decoded bodies include:

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

### IP Restriction Failure

If the parent merchant has `whitelistedIps` configured and the first IP in `x-forwarded-for` is absent or not allow-listed:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

### API Not Enabled or Not Allowed

If this API is blocked for the parent merchant, or the effective allowed API list does not include update sub-merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

### Parent Merchant Is Not an Aggregator

The update route requires the parent merchant to be configured as an aggregator. If not:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_MERCHANT",
  "responseMessage": "INVALID_MERCHANT"
}
```

### Sub-Merchant Not Found or Does Not Belong to Parent

If `subMerchantId` and `subMerchantChannelId` do not match a sub-merchant under the authenticated parent merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_MERCHANT",
  "responseMessage": "INVALID_MERCHANT"
}
```

### Missing Merchant Account or Merchant Info

If the sub-merchant exists but required storage rows are missing, update cannot complete.

Merchant info missing:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid MerchantInfo details"
}
```

Primary merchant account missing generally maps to an internal server error:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Internal or Storage Failure

Database update failures, callback update failures, configuration parsing failures from stored data, encryption/decryption failures, or cache invalidation failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Idempotency, Retries, and Client Handling

This API does not use a merchant request id or an idempotency key. Re-sending the exact same update is generally safe because product logic compares existing values and update helpers avoid changing rows when values are already identical.

Recommended client behavior:

- Treat `status = SUCCESS` and `responseCode = SUCCESS` as the source of truth, not only HTTP status.
- For validation, authorization, API access, IP restriction, and invalid merchant failures, do not retry unchanged. Fix the request or merchant configuration first.
- For internal errors or network timeouts, retry with the same body only after checking whether the previous call may have succeeded. If available, call Sub-Merchant Info to reconcile the final stored state.
- When updating callbacks, send the complete set of callback types you want to modify. Omitted callback types remain unchanged.
- When disabling a sub-merchant and changing `ALLOW_*` configurations, confirm downstream API access expectations with Newton onboarding because allowed API groups are derived from server-side API names.

## Source References

- Route and auth invocation: [src/Newton/App/Routes/SubMerchant.hs](../../src/Newton/App/Routes/SubMerchant.hs:18)
- Request/response types and validation: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2741)
- Transformer route and core mapping: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:666), [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1034)
- Product update flow: [src/Newton/Product/Merchant/SubMerchant/SubMerchant.hs](../../src/Newton/Product/Merchant/SubMerchant/SubMerchant.hs:67)
- Sub-merchant update helpers, configurations, callbacks, and response construction: [src/Newton/Product/Merchant/SubMerchant/Helper.hs](../../src/Newton/Product/Merchant/SubMerchant/Helper.hs:130)
- Merchant-info update behavior: [src/Newton/Storage/QueriesMiddleware/MerchantInfo.hs](../../src/Newton/Storage/QueriesMiddleware/MerchantInfo.hs:86)
- Merchant ownership lookup and update: [src/Newton/Storage/QueriesMiddleware/Merchant.hs](../../src/Newton/Storage/QueriesMiddleware/Merchant.hs:79)
- S2S envelope and merchant payload verification: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Signature, timestamp, IP, blocked API, and allowed API checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
