# Add Sub-Merchant API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/sub/add`

## Overview

Add Sub-Merchant is a server-to-server API used by an aggregator parent merchant to onboard a child merchant under its Newton configuration.

The API creates or reuses the sub-merchant merchant record, customer record, VPA, account mapping, callback configuration, merchant-info record, and optional sub-merchant feature configuration. The sub-merchant uses the parent merchant's API key and parent account rails, while retaining its own merchant id, channel id, VPA, MCC, business metadata, enabled flag, and callback routing.

Use this API when an aggregator platform needs to onboard a store, seller, outlet, franchisee, or other sub-merchant before sending payment, mandate, refund, status, or list traffic on behalf of that sub-merchant.

## Business Use Case

Add Sub-Merchant helps aggregators:

- Create a sub-merchant under an already-onboarded parent merchant.
- Assign a dedicated UPI VPA to the sub-merchant.
- Store display, legal, ownership, MCC, address, PAN, GSTIN, Aadhaar, MID, SID, and TID metadata.
- Copy parent callbacks when sub-merchant-specific callbacks are not supplied.
- Enable or disable the sub-merchant at creation time.
- Configure sub-merchant behavior such as direct-pay blocking, SMS notification, allowed payer account types, and allowed APIs for disabled sub-merchants.
- Retry onboarding safely when the same sub-merchant has already completed onboarding.

## Integration Flow

1. Newton onboards the parent merchant as an aggregator.
2. The parent merchant allocates a unique `subMerchantId`, `subMerchantChannelId`, and VPA for the child merchant.
3. The parent merchant calls `add` with the sub-merchant business, address, identity, and configuration details.
4. Newton validates the decrypted business payload and verifies the S2S signature/encryption envelope.
5. Newton verifies the parent merchant is an aggregator.
6. Newton validates the MCC and VPA, checks for an existing sub-merchant, and checks that the VPA is not owned by another customer.
7. For a new sub-merchant, Newton creates the merchant, customer, VPA, account mapping, merchant-account mapping, callbacks, optional default entity, merchant-info row, and optional merchant configurations.
8. For an already-onboarded duplicate sub-merchant, Newton returns the existing sub-merchant details with `action: "FETCHED"` for API versions above 1.
9. The merchant decrypts the response and stores the returned `merchantId`, `merchantChannelId`, `subMerchantId`, `subMerchantChannelId`, VPA, account, callback, and action details.

Important identifiers:

- `merchantId` and `merchantChannelId`: Parent merchant identifiers, sent in headers and returned in the payload.
- `subMerchantId` and `subMerchantChannelId`: Child merchant identifiers, sent in the decrypted body and returned in the payload.
- `vpa`: UPI VPA assigned to the sub-merchant. It must be valid and must not already belong to a different customer.
- `action`: `ADDED` means Newton created/onboarded the sub-merchant in this call. `FETCHED` means the same completed sub-merchant already existed and was returned idempotently.

## Endpoint

```http
POST /api/{apiVersion}/merchants/sub/add
```

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string/integer path segment | Yes | API version in the URL. The route also reads `x-api-version` internally for response and backward-compatibility behavior. Use the version shared during onboarding. |

### Headers

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Send `application/json`. |
| `x-merchant-id` | Yes | Parent merchant id. Used to resolve and authenticate the parent merchant. |
| `x-merchant-channel-id` | Yes | Parent merchant channel id. Used with `x-merchant-id` to resolve the parent merchant. |
| `x-timestamp` | Yes | Request timestamp used by signature verification and replay checks. |
| `x-merchant-signature` | Conditional | Required for plain-text S2S payloads outside configured checksum-bypass environments. The signature is verified over merchant ids, optional sub-merchant headers, timestamp, and raw body. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP in this header must be in the merchant allowlist. |
| `x-api-version` | Recommended | Used by shared helpers for version-specific behavior. For `add`, API version `0` returns duplicate onboarding as `DUPLICATE_REQUEST`; later versions return `action: "FETCHED"`. |
| `x-request-id` | No | Optional request id. Newton generates one if omitted and returns it as `x-requestid`. |
| `x-session-id` | No | Optional session id. Defaults to the request id when omitted and is returned as `x-sessionid`. |

Do not send `x-sub-merchant-id` or `x-sub-merchant-channel-id` for this add call unless Newton onboarding specifically tells you to. The sub-merchant being created is identified in the decrypted request body. If sub-merchant headers are supplied, they are included in signature input and may cause an existing sub-merchant context to be loaded.

## Authentication, Encryption, and Signing

The route accepts the standard Newton S2S encrypted/signed/plain envelope, but production integrations should use the strategy configured during onboarding.

Request envelope options:

| Envelope | JSON shape | Verification behavior |
| --- | --- | --- |
| JWE encrypted payload | `{"protected":"...","encryptedKey":"...","iv":"...","cipherText":"...","tag":"..."}` | Newton decrypts the JWE, expects the decrypted content to be a JWS signed body, verifies the JWS, then parses the business payload. |
| JWS signed payload | `{"payload":"...","signature":"...","protected":"..."}` | Newton verifies the JWS using the merchant key and parses the base64url payload as the business payload. |
| Plain payload | Business fields at top level | Newton verifies `x-merchant-signature` over the raw body and required headers. This is normally used only when configured. |

For encrypted or signed requests, the decrypted business payload must include `iat`; the middleware rejects missing or stale `iat`. For plain requests, `iat` is accepted but not used by the route-level signature validator.

Responses use the same route response transport:

- If the merchant strategy is `JWS`, Newton returns a signed response body.
- If the merchant strategy is `JWS_AND_JWE`, Newton signs and encrypts the response body.
- Otherwise Newton returns the decrypted response JSON and an `X-Response-Signature` header.

The examples below show decrypted business payloads for readability.

## Request

Route request type: `API.EncRequest TfS2S.AddSubMerchantRequest`

Business payload type: `TfS2S.AddSubMerchantRequest`

Type source: [AddSubMerchantRequest](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2823)

### Minimum Request

```json
{
  "subMerchantId": "STORE123",
  "subMerchantChannelId": "APP",
  "vpa": "store123@upi",
  "mcc": "5411",
  "merchantName": "Store 123 Private Limited",
  "marketingName": "Store 123",
  "city": "Bengaluru",
  "address": "12 Market Road",
  "state": "Karnataka",
  "pinCode": "560001",
  "mobileNumber": "919876543210",
  "mid": "STORE123MID",
  "sid": "STORE123SID",
  "tid": "STORE123TID",
  "merchantType": "SMALL",
  "merchantGenre": "ONLINE",
  "onBoardingType": "AGGREGATOR",
  "brand": "Store 123",
  "legal": "Store 123 Private Limited",
  "franchise": "Store 123",
  "type": "PRIVATE",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### New Sub-Merchant With Explicit Callbacks

`callbackUrls` is a string containing a JSON array. Each array item has `type`, `url`, and optional `query`.

```json
{
  "subMerchantId": "STORE124",
  "subMerchantChannelId": "APP",
  "vpa": "store124@upi",
  "mcc": "5812",
  "callbackUrls": "[{\"type\":\"MERCHANT_CREDITED_VIA_PAY\",\"url\":\"https://merchant.example/callbacks/pay\",\"query\":\"source=submerchant\"},{\"type\":\"MERCHANT_CREDITED_VIA_COLLECT\",\"url\":\"https://merchant.example/callbacks/collect\"}]",
  "merchantName": "Store 124 Foods Private Limited",
  "marketingName": "Store 124 Foods",
  "displayName": "Store 124",
  "city": "Mumbai",
  "address": "4 Food Street",
  "state": "Maharashtra",
  "pinCode": "400001",
  "countryCode": "91",
  "mobileNumber": "9876543210",
  "ownerName": "Asha Rao",
  "partner1": "Ravi Rao",
  "partner2": "Meera Rao",
  "mccDescription": "Eating places and restaurants",
  "gstin": "27ABCDE1234F1Z5",
  "panNumber": "ABCDE1234F",
  "aadhaarNumber": "123456789012",
  "mid": "STORE124MID",
  "sid": "STORE124SID",
  "tid": "STORE124TID",
  "merchantType": "SMALL",
  "merchantGenre": "OFFLINE",
  "onBoardingType": "AGGREGATOR",
  "brand": "Store 124 Foods",
  "legal": "Store 124 Foods Private Limited",
  "franchise": "Store 124",
  "type": "PRIVATE",
  "enabled": "true",
  "udfParameters": "{\"storeRef\":\"S124\"}",
  "iat": "2026-07-02T10:15:30+05:30",
  "agentPhoneNumbers": [
    "919812345678"
  ],
  "agentEmails": [
    "ops.store124@example.com"
  ]
}
```

### New Sub-Merchant With Feature Configuration

```json
{
  "subMerchantId": "STORE125",
  "subMerchantChannelId": "APP",
  "vpa": "store125@upi",
  "mcc": "5999",
  "merchantName": "Store 125 Retail Private Limited",
  "marketingName": "Store 125",
  "city": "Delhi",
  "address": "22 Retail Avenue",
  "state": "Delhi",
  "pinCode": "110001",
  "mobileNumber": "919812345679",
  "mid": "STORE125MID",
  "sid": "STORE125SID",
  "tid": "STORE125TID",
  "merchantType": "LARGE",
  "merchantGenre": "ONLINE",
  "onBoardingType": "AGGREGATOR",
  "brand": "Store 125",
  "legal": "Store 125 Retail Private Limited",
  "franchise": "Store 125",
  "type": "PRIVATE",
  "enabled": "false",
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
          "vpaHandles": [
            "upi",
            "okaxis"
          ]
        }
      ]
    },
    {
      "config": "ALLOW_TXN_STATUS",
      "action": "ADD"
    },
    {
      "config": "ALLOW_REFUND",
      "action": "ADD"
    }
  ],
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Retry for an Already-Onboarded Sub-Merchant

Use the same identifiers and VPA from the original request. For API versions above 1, Newton returns the existing sub-merchant with `action: "FETCHED"` when onboarding has already completed.

```json
{
  "subMerchantId": "STORE123",
  "subMerchantChannelId": "APP",
  "vpa": "store123@upi",
  "mcc": "5411",
  "merchantName": "Store 123 Private Limited",
  "marketingName": "Store 123",
  "city": "Bengaluru",
  "address": "12 Market Road",
  "state": "Karnataka",
  "pinCode": "560001",
  "mobileNumber": "919876543210",
  "mid": "STORE123MID",
  "sid": "STORE123SID",
  "tid": "STORE123TID",
  "merchantType": "SMALL",
  "merchantGenre": "ONLINE",
  "onBoardingType": "AGGREGATOR",
  "brand": "Store 123",
  "legal": "Store 123 Private Limited",
  "franchise": "Store 123",
  "type": "PRIVATE",
  "iat": "2026-07-02T10:20:30+05:30"
}
```

## Field Reference

Fields not listed as optional must be present in the decrypted business payload. Optional fields have no default unless explicitly described.

| Field | Type | Required | Default / omitted behavior | Validation and description |
| --- | --- | --- | --- | --- |
| `subMerchantId` | string | Yes | No default. | Sub-merchant merchant id under the parent. 1 to 256 chars. Allowed characters: letters, numbers, space, underscore, plus, dot, hyphen. |
| `subMerchantChannelId` | string | Yes | No default. | Sub-merchant channel id under the parent. Same format as `subMerchantId`. |
| `vpa` | string | Yes | No default. | UPI VPA assigned to the sub-merchant. Must pass merchant VPA validation and product-level VPA validity. Must not already belong to a different customer. |
| `accountNumber` | string | No | Not stored in the created account. The current add flow creates the sub-merchant account from the parent aggregator account. | Optional aggregator-populated account number. If supplied, digits only and length <= 18. |
| `ifsc` | string | No | Not stored in the created account. The current add flow creates the sub-merchant account from the parent aggregator account. | Optional aggregator-populated IFSC. If supplied, exactly 11 chars matching `^[A-Z]{4}0[A-Z0-9]{6}$`. |
| `mcc` | string | Yes | No default. | Four-digit MCC. Also validated by product-level MCC validation. Stored as merchant MCC and sub-code. |
| `callbackUrls` | string | No | If omitted or an empty string, Newton copies parent merchant callbacks to the sub-merchant. On duplicate fetch, existing sub-merchant callbacks are returned. | Stringified JSON array of callback objects. Must parse as `[{"type": "...", "url": "...", "query": "..."}]`. |
| `merchantName` | string | Yes | No default. | Legal/display merchant name used in merchant info and store metadata. Length 1 to 100. If `displayName` is omitted, this name is used for the sub-merchant account name. |
| `marketingName` | string | Yes | No default. | Marketing name. Length 1 to 50. |
| `displayName` | string | No | If omitted, account name falls back to `merchantName`. | Display name for the sub-merchant. Length 1 to 100 when supplied. |
| `city` | string | Yes | No default. | City. Length 1 to 50. |
| `address` | string | Yes | No default. | Address. Length 1 to 200. |
| `state` | string | Yes | No default. | State. Length 1 to 50. |
| `pinCode` | string | Yes | No default. | Six numeric digits. |
| `countryCode` | string | No | If omitted, `mobileNumber` must be 12 digits. | Optional country code. Length <= 7; optional leading plus; remaining chars numeric. |
| `mobileNumber` | string | Yes | No default. | If `countryCode` is omitted, must be exactly 12 numeric digits, typically `91` plus the 10-digit mobile number. If `countryCode` is supplied, must be numeric and length < 19. Stored in merchant-info. The actual customer mobile for the sub-merchant is generated by Newton. |
| `ownerName` | string | Conditional | No default. | Required when effective API version is below 2. Optional for later versions. Length 1 to 50 when supplied. |
| `partner1` | string | Conditional | No default. | Required when effective API version is below 2. Optional for later versions. Length 1 to 50 when supplied. |
| `partner2` | string | Conditional | No default. | Required when effective API version is below 2. Optional for later versions. Length 1 to 50 when supplied. |
| `mccDescription` | string | No | Stored as an empty string in merchant info if omitted. | MCC description. Length 1 to 255 when supplied. |
| `gstin` | string | No | No default. | GSTIN or tax identifier. Length 1 to 20 when supplied. No GSTIN checksum/format validation is applied here. |
| `panNumber` | string | No | If omitted, Newton does not derive a merchant identifier code from PAN. | PAN. Exactly 10 uppercase alphanumeric characters when supplied. Used to derive `merchantIdentifierCode` when possible. |
| `aadhaarNumber` | string | No | No default. | Either 12 numeric digits or the masked form accepted by code for length 8. |
| `mid` | string | Yes | No default. | Merchant MID. Alphanumeric only, length 1 to 20. Stored in merchant info. |
| `sid` | string | Yes | No default. | Merchant SID. Alphanumeric only, length 1 to 20. Stored in merchant info. |
| `tid` | string | Yes | No default. | Merchant TID. Alphanumeric only, length 1 to 20. Stored in merchant info. |
| `merchantType` | string | Yes | No default. | Allowed values: `SMALL`, `LARGE`. |
| `merchantGenre` | string | Yes | No default. | Allowed values: `ONLINE`, `OFFLINE`. |
| `onBoardingType` | string | Yes | No default. | Allowed values: `BANK`, `AGGREGATOR`. |
| `brand` | string | Yes | No default. | Brand name. Alphanumeric plus spaces only; length 1 to 99. |
| `legal` | string | Yes | No default. | Legal name. Alphanumeric plus spaces only; length 1 to 99. |
| `franchise` | string | Yes | No default. | Franchise name. Alphanumeric plus spaces only; length 1 to 99. |
| `type` | string | Yes | No default. | Ownership type. Allowed values: `PROPRIETARY`, `PARTNERSHIP`, `PRIVATE`, `PUBLIC`, `OTHERS`. |
| `enabled` | string | No | If omitted, the sub-merchant is created enabled. | Boolean string. Allowed values are case-insensitive `true` and `false`. Controls merchant enabled status and allowed API behavior. |
| `configurations` | array of objects | No | If omitted, no explicit sub-merchant configuration is created. Parent/store defaults still apply where product logic uses them. | Optional feature and API configuration objects. See the configuration reference below. |
| `udfParameters` | string | No | Echoed in the success response when supplied. Not included in the core product request. | Must be a JSON-object string and must not contain `/`, `$`, `-`, `*`, `!`, `%`, `~`, or backtick. |
| `iat` | string | Conditional | No default. | Required for JWS/JWE envelopes. Timestamp must pass Newton timestamp validation. |
| `agentPhoneNumbers` | array of strings | No | No default. | Optional agent phone numbers. Each value is validated with the domestic 12-digit mobile validation. Due to current validator behavior, an empty array validates to `["Empty list"]`; send the field only when you have real values. |
| `agentEmails` | array of strings | No | No default. | Optional agent email addresses. Each value must pass email validation. |

### `callbackUrls` String Reference

`callbackUrls` is not a nested JSON array in the request body; it is a JSON array serialized as a string.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `type` | string enum | Yes | Newton callback type. Common values include `MERCHANT_CREDITED_VIA_PAY`, `MERCHANT_CREDITED_VIA_COLLECT`, `CUSTOMER_ONLINE_REFUND`, `CUSTOMER_OFFLINE_REFUND`, `MANDATE_STATUS_UPDATE`, and the other Newton callback enums supported by the platform. Unknown values parse as `UNDEFINED`; use only values shared during onboarding. |
| `url` | string | Yes | Callback URL for that callback type. The add API validates only that the stringified array parses as callback objects; URL reachability is not checked here. |
| `query` | string | No | Optional query string stored with the callback. |

If `callbackUrls` is omitted or sent as `""`, the sub-merchant inherits copies of the parent merchant callbacks. If the duplicate-idempotent path is used, the response returns existing sub-merchant callbacks and does not rewrite them.

### `configurations[]` Reference

Each `configurations` item has a `config` discriminator.

| `config` | Request fields | Description |
| --- | --- | --- |
| `BLOCK_DIRECT_PAY` | `value`: boolean string | Updates the sub-merchant store flag `blockDirectPay`. |
| `ENABLE_SMS_NOTIFICATION` | `value`: boolean string | Upserts merchant configuration key `enableSmsNotification`. |
| `PAYER_ACC_TYPES_ALLOWED` | `value`: array of allowed account type objects; optional `action`: `ADD` or `REMOVE` | Upserts or modifies merchant configuration key `payerAccTypesAllowed`. If the key is absent and default-account-type fallback is enabled, Newton starts from the default/parent allowed account types before applying the action. |
| `ALLOW_TXN_STATUS` | `action`: `ADD` or `REMOVE` | Adds or removes transaction-status APIs from the sub-merchant `allowedApiNames` config when the sub-merchant is disabled. |
| `ALLOW_REFUND` | `action`: `ADD` or `REMOVE` | Adds or removes refund APIs from `allowedApiNames` when the sub-merchant is disabled. |
| `ALLOW_TXN_LIST` | `action`: `ADD` or `REMOVE` | Adds or removes list-transactions API access from `allowedApiNames` when the sub-merchant is disabled. |
| `ALLOW_LIST_MANDATE` | `action`: `ADD` or `REMOVE` | Adds or removes list-mandate API access from `allowedApiNames` when the sub-merchant is disabled. |
| `ALLOW_MANDATE_STATUS` | `action`: `ADD` or `REMOVE` | Adds or removes mandate-status API access from `allowedApiNames` when the sub-merchant is disabled. |

Notes:

- `BLOCK_DIRECT_PAY` is also written into the sub-merchant store metadata.
- API-allow configs affect `allowedApiNames` only when `enabled` is false. If `enabled` is true, product logic resets `allowedApiNames` to `[]`.
- For `PAYER_ACC_TYPES_ALLOWED`, `action` values other than `ADD` or `REMOVE` leave the existing value unchanged.
- Unknown `config` values fail JSON parsing with `UNKNOWN_CONFIG`.

### `PAYER_ACC_TYPES_ALLOWED.value[]` Reference

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `accType` | string | Yes | Payer account type name, for example `SAVINGS`, as configured for the merchant. |
| `limit` | number | No | Optional limit for this account type. |
| `limitType` | string enum | No | Allowed values: `SMALL`, `LARGE`. |
| `vpaHandles` | array of strings | No | Optional list of VPA handles allowed for this account type. |

## Defaults and Omitted Field Behavior

- `enabled`: omitted means the sub-merchant is created as enabled.
- `callbackUrls`: omitted or empty string means Newton copies the parent merchant callbacks.
- `displayName`: omitted means the sub-merchant account name uses `merchantName`.
- `mccDescription`: omitted is stored as an empty string in merchant-info.
- `accountNumber` and `ifsc`: validated if supplied, but the current add flow creates the sub-merchant account from the parent aggregator account and returns the parent-derived masked account and IFSC.
- `countryCode`: omitted makes `mobileNumber` follow the 12-digit domestic format.
- `ownerName`, `partner1`, and `partner2`: required only for API versions below 2.
- `configurations`: omitted means no explicit sub-merchant merchant-configuration rows are created by this request.
- `udfParameters`: omitted means no `udfParameters` in the response.
- `action`: not a request field; response-only.

## Success Response

Route response type: `RespHeaders (API.EncResponse TfS2S.AddSubMerchantResponse)`

Business response type: `TfS2S.AddSubMerchantResponse`

Type source: [AddSubMerchantResponse](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2926)

Success response body examples below show the decrypted business response. Depending on merchant response strategy, this body may be returned inside a JWS or JWE envelope, or returned as plain JSON with `X-Response-Signature`.

### New Sub-Merchant Added

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "PARENTMID",
    "merchantChannelId": "PARENTCH",
    "subMerchantId": "STORE123",
    "subMerchantChannelId": "APP",
    "vpa": "store123@upi",
    "maskedAccountNumber": "XXXXXXXX1234",
    "ifsc": "HDFC0000001",
    "mcc": "5411",
    "enabled": "true",
    "callbackUrls": "[{\"type\":\"MERCHANT_CREDITED_VIA_PAY\",\"url\":\"https://merchant.example/callbacks/pay\"}]",
    "action": "ADDED"
  },
  "udfParameters": "{\"storeRef\":\"S123\"}"
}
```

### Existing Completed Sub-Merchant Fetched

For API versions above 1, a retry with an already-onboarded sub-merchant returns success with `action: "FETCHED"`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "PARENTMID",
    "merchantChannelId": "PARENTCH",
    "subMerchantId": "STORE123",
    "subMerchantChannelId": "APP",
    "vpa": "store123@upi",
    "maskedAccountNumber": "XXXXXXXX1234",
    "ifsc": "HDFC0000001",
    "mcc": "5411",
    "enabled": "true",
    "callbackUrls": "[{\"type\":\"MERCHANT_CREDITED_VIA_PAY\",\"url\":\"https://merchant.example/callbacks/pay\"}]",
    "action": "FETCHED"
  }
}
```

For effective API version `0`, the same duplicate completed sub-merchant path returns `DUPLICATE_REQUEST` instead of the fetched success response. For effective API version `1`, code suppresses the `action` field in the success response because the action is added only above version `0`.

### Response Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `SUCCESS` for successful add/fetch responses. |
| `responseCode` | string | `SUCCESS` for successful add/fetch responses. |
| `responseMessage` | string | `SUCCESS` for successful add/fetch responses. |
| `payload` | object | Sub-merchant result payload. |
| `udfParameters` | string | Echo of request `udfParameters` when supplied. Omitted otherwise. |

### `payload` Field Reference

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Parent merchant id. |
| `merchantChannelId` | string | Parent merchant channel id. |
| `subMerchantId` | string | Sub-merchant id from the request. |
| `subMerchantChannelId` | string | Sub-merchant channel id from the request. |
| `vpa` | string | Decrypted sub-merchant VPA. |
| `maskedAccountNumber` | string | Masked account number from the primary merchant account created from the parent aggregator account. |
| `ifsc` | string | IFSC from the primary merchant account created from the parent aggregator account. |
| `mcc` | string | Stored MCC for the sub-merchant. |
| `enabled` | string | `true` or `false` as text. |
| `callbackUrls` | string | Stringified JSON array of callbacks now associated with the sub-merchant. |
| `action` | string | `ADDED` for newly completed onboarding, `FETCHED` for an already-completed duplicate returned idempotently. Omitted for some older API-version behavior. |
| `agentPhoneNumbers` | array of strings | Echoed from request when supplied. |
| `configurations` | array of objects | Always omitted in add responses by the current response mapper. Configurations can be fetched through sub-merchant info flows where enabled. |

## Error Handling

Failure bodies use the shared Newton error shape after decryption. Depending on the layer that fails and the configured response strategy, the body may be an encrypted/signed error response or a direct JSON error with HTTP 400, 401, 500, or, for several product/business failures, HTTP 200. Always inspect `status`, `responseCode`, and `responseMessage` after decrypting/parsing the response.

Generic decrypted error shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "reason",
  "payload": null
}
```

Because `payload` is omitted when `null` by the JSON encoder, many actual responses look like:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "reason"
}
```

### Validation Failure

Request validation failures occur before product logic. The response code is `BAD_REQUEST`; the message is a comma-separated rendering of all field-level validation errors collected for the request.

Example: invalid `mcc`.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"mcc length is not 4\""
}
```

Example: invalid enum.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "EnumValidation \"Enum match failed RETAIL\""
}
```

Client handling: fix the request and do not retry unchanged. Validate enum casing, string lengths, `callbackUrls` JSON-string format, and `mobileNumber`/`countryCode` combinations before sending.

### Missing Legacy Owner/Partner Fields

For effective API versions below 2, `ownerName`, `partner1`, and `partner2` are mandatory.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Either of ownerName,partner1,partner2 is/are missing"
}
```

Client handling: either send all three fields or use an API version where this legacy rule is not applicable, as agreed during onboarding.

### Authentication, Signature, or Encryption Failure

The auth layer can reject missing merchant headers, missing raw body/timestamp, invalid JWS, failed JWE decrypt, missing `kid`, missing or stale `iat`, invalid `x-merchant-signature`, stale `x-timestamp`, or malformed encrypted/signed payloads.

Typical unauthorized shape:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

For a JWE that decrypts but does not parse, the body can be:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: key \"payload\" not found"
}
```

Client handling: do not retry blindly. Rebuild the exact raw body and signature, verify key ids, verify timestamp freshness, include `iat` for JWS/JWE payloads, and confirm the merchant id/channel id match the signing key.

### API Disabled or Merchant API Not Allowed

If the API is blocked for the merchant or not present in the merchant/sub-merchant allowed API list, Newton returns 401 with:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Client handling: treat this as configuration/onboarding failure. Contact Newton or update merchant configuration; do not retry unchanged.

### IP Restriction Failure

If merchant `whitelistedIps` is configured, the first value in `x-forwarded-for` must be in that list. Missing or non-allowlisted IP returns unauthorized.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Client handling: send from an allowlisted egress IP and ensure forwarding headers are preserved by your gateway.

### Parent Merchant Is Not an Aggregator

Only aggregator parent merchants can add sub-merchants.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_MERCHANT",
  "responseMessage": "INVALID_MERCHANT"
}
```

Client handling: verify you are calling with the aggregator parent merchant headers. This is not retryable without configuration changes.

### Invalid VPA Syntax or Product-Level VPA Check

If the VPA fails product-level validity checks:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Vpa Check Failed : Invalid Vpa"
}
```

Client handling: fix the VPA and retry with a valid VPA assigned to the sub-merchant.

### VPA Already Exists for Another Customer

If the requested VPA already exists and is not owned by the same duplicate sub-merchant customer:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_VPA",
  "responseMessage": "INVALID_VPA"
}
```

Client handling: choose a different VPA or reconcile ownership with Newton. Retrying unchanged will keep failing.

### Duplicate Completed Sub-Merchant on Version 0

For effective API version `0`, a completed duplicate returns a duplicate error instead of `action: "FETCHED"`.

```json
{
  "status": "FAILURE",
  "responseCode": "DUPLICATE_REQUEST",
  "responseMessage": "DUPLICATE_REQUEST"
}
```

Client handling: if you are on version 0, treat this as "already onboarded" only after reconciling with sub-merchant info/list APIs or your own stored success state. Newer integrations should use a version that returns `FETCHED`.

### Parent Merchant, Merchant Info, Account, or Database Lookup Failure

Several internal lookups can fail:

- Parent merchant not found from `x-merchant-id` and `x-merchant-channel-id`.
- Parent account not found when creating the sub-merchant account.
- Primary merchant account not found on duplicate fetch.
- Merchant-info row not present when the duplicate candidate exists but onboarding was incomplete.
- Database create/update/find-or-create failures.

The exact error depends on the failing helper. Common shapes include:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_MERCHANT",
  "responseMessage": "INVALID_MERCHANT"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid account details"
}
```

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry only if the failure is clearly transient or Newton confirms a partial write has been cleaned up. For lookup/configuration errors, reconcile merchant setup first.

### Invalid Configuration Object

Unknown `config` values fail JSON parsing before request validation completes. Invalid `PAYER_ACC_TYPES_ALLOWED` values can also fail parsing.

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: UNKNOWN_CONFIG"
}
```

Client handling: send only supported `config` values and match the required shape for each discriminator.

### Downstream or Unexpected Error

This add flow is mostly internal to Newton storage, encryption, callback/config helpers, and Redis/entity side effects. It does not call NPCI for sub-merchant creation. Unexpected storage, Passetto encryption/decryption, key, JSON conversion, or Redis side-effect failures may return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

Client handling: retry with backoff only when the request is safe to replay with the same `subMerchantId`, `subMerchantChannelId`, and `vpa`. If you receive an ambiguous timeout or 5xx, first call the sub-merchant info/list API or retry this add API on a version that can return `FETCHED`.

## Retry and Idempotency Guidance

Use `subMerchantId` plus `subMerchantChannelId` as the merchant-scoped idempotency identity for this API.

Recommended retry behavior:

- On network timeout or no response, retry with the exact same `subMerchantId`, `subMerchantChannelId`, and `vpa`.
- On success with `action: "ADDED"`, store the returned payload as the source of truth.
- On success with `action: "FETCHED"`, treat the call as idempotently successful and reconcile the returned callbacks/account fields with your records.
- On `DUPLICATE_REQUEST` for API version `0`, reconcile using sub-merchant info/list APIs before deciding whether onboarding is complete.
- On validation, auth, API disabled, non-aggregator, IP restriction, invalid VPA, or VPA already exists errors, do not retry unchanged.
- If a retry finds an existing sub-merchant whose onboarding was not completed, code may continue the onboarding path using existing partial records. Keep identifiers stable across retries.

Avoid changing request identity fields between retries. Sending the same VPA with a different sub-merchant identity can fail as `INVALID_VPA` once the original attempt has created the VPA/customer association.

## Source References

- API mount in core route tree: [NewtonAPIs includes SubMerchantAPIs](../../src/Newton/App/Routes/Core.hs:112)
- Server handler mount: [coreApiHandler](../../src/Newton/App/Server.hs:96) and [coreSubMerchantApiHandler](../../src/Newton/App/Server.hs:346)
- Route and handler: [SubMerchantAPIs/addSubMerchant](../../src/Newton/App/Routes/SubMerchant.hs:18)
- Request/response types and validation: [AddSubMerchantRequest](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2823), [AddSubMerchantResponse](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2926), [ConfigurationBody](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:2741)
- Transformer route: [addSubMerchantTransformerRoute](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:653)
- Request/response mapping: [mkAddSubMerchantCoreRequest and mkaddSubMerchantResponseS2S](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:970)
- Product flow: [coreAddSubMerchantRoute](../../src/Newton/Product/Merchant/SubMerchant/SubMerchant.hs:37)
- Product helpers and duplicate/VPA/account/callback/config logic: [SubMerchant.Helper](../../src/Newton/Product/Merchant/SubMerchant/Helper.hs:58)
- Core request/response product types: [AddSubMerchantCoreRequest](../../src/Newton/Product/Merchant/SubMerchant/Types.hs:13)
- Merchant and merchant-info storage payloads: [getSubMerchantPayload](../../src/Newton/Storage/QueriesMiddleware/Merchant.hs:136), [getMerInfoPayload](../../src/Newton/Storage/QueriesMiddleware/MerchantInfo.hs:20)
- Validation helpers: [Newton.Validation.Common](../../src/Newton/Validation/Common.hs:215)
- Envelope types: [EncRequest and EncResponse](../../src/Newton/Types/API/RequestBody.hs:48)
- Request decryption/parsing: [getReqBody](../../src/Newton/Utils/Routes.hs:40) and [merchantPayloadVerificationS2S](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Route response wrapping/signing/encryption: [flowWithTrace](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Merchant signature, API allowlist, and IP checks: [merchantSignatureVerificationV2](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Shared error body type and constants: [ErrorResponse](../../src/Newton/Types/API/Common.hs:12), [APIErrorCode](../../src/Newton/Constants/APIErrorCode.hs:43)
