# Send Money API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/transactions/sendMoney`

## Overview

Send Money is a merchant server-to-server API for initiating an outgoing UPI debit from a registered customer account.

The merchant backend calls this API after the customer has been onboarded, device-bound, and has an active VPA/account with Newton. Newton validates the merchant, customer, device fingerprint, payer VPA, debit account, request identifiers, and feature-specific business rules, then initiates the UPI payment through the configured PSP/NPCI flow.

The API supports multiple payment modes through `transactionType`:

- `P2P_PAY`: pay another customer VPA.
- `P2M_PAY`: pay a merchant VPA and create/update a merchant order.
- `SCAN_PAY`: pay from scanned QR details.
- `INTENT_PAY`: pay from an intent payload.
- `SELF_PAY`: pay another account belonging to the same customer, where supported.

The HTTP/API envelope returns `status: "SUCCESS"` when Newton accepted and processed the API call. The actual UPI outcome is in `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.gatewayResponseMessage`.

## Business Use Case

Use this API when the merchant backend needs to debit a customer's linked UPI account for:

- P2P send-money journeys.
- Merchant QR, intent, or collect-to-pay journeys represented as `P2M_PAY`, `SCAN_PAY`, or `INTENT_PAY`.
- Self-account transfer or credit-card/self-pay journeys represented as `SELF_PAY`.
- UPI Lite top-up, transfer-out, deregistration, and auto-top-up related debits, when enabled.
- International QR payment journeys, when enabled for the merchant and customer.
- GST QR, invoice, split, and convenience-fee payment journeys, when configured.
- Contextual offer payments, when the merchant is enabled for those use cases.

## Integration Flow

1. Merchant completes customer onboarding, device binding, VPA creation, and account linking through the relevant Newton APIs.
2. Merchant obtains or stores the payer VPA, debit account identifier, and device fingerprint for the customer.
3. Merchant generates a unique `upiRequestId` for this payment attempt and a merchant-facing `merchantRequestId`.
4. Merchant sends the signed/encrypted S2S request.
5. Newton verifies the request envelope, merchant headers, signature, timestamp, API access, optional IP allowlist, and merchant-customer mapping.
6. Newton validates the decrypted business payload.
7. Newton validates the customer device, payer VPA ownership/status, debit account, and mode-specific payment rules.
8. Newton initiates the payment and returns a gateway outcome in the response payload.
9. Merchant stores `upiRequestId`, `merchantRequestId`, `gatewayReferenceId`, `gatewayResponseStatus`, and `gatewayResponseCode` for reconciliation and status checks.

Important identifiers:

- `upiRequestId`: Newton/UPI transaction id supplied by the merchant. This is the primary duplicate check for the payment attempt.
- `merchantRequestId`: Merchant order/reference id. For `P2M_PAY`, this also identifies the merchant order and controls retry behavior for retriable failures.
- `gatewayReferenceId`: UPI response/reference id returned by the PSP/NPCI path.
- `bankAccountUniqueId` or `accountReferenceId`: Customer debit account selector. At least one is required for normal integrations.

## Endpoint

```http
POST /api/{apiVersion}/merchants/transactions/sendMoney
```

Payloads use the standard Newton server-to-server encrypted request and response envelope. The examples below show the decrypted business payload for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Use `application/json`. |
| `x-api-version` | Recommended | Use the version shared during onboarding. Use a version greater than `1` if the client expects `purpose` in the response. |
| `x-merchant-id` | Yes | Merchant id assigned by Newton. |
| `x-merchant-channel-id` | Yes | Merchant channel id assigned by Newton. |
| `x-sub-merchant-id` | Conditional | Required only when calling as a configured sub-merchant. |
| `x-sub-merchant-channel-id` | Conditional | Required with `x-sub-merchant-id`. |
| `x-merchant-signature` | Yes for unsigned business payload envelopes | Request signature over merchant ids, timestamp, and raw request body, using the signing strategy shared during onboarding. |
| `x-timestamp` | Yes | Request timestamp. Newton validates freshness except in specific non-production checksum-bypass setups. |
| `x-forwarded-for` | Conditional | Required when the merchant has `whitelistedIps` configured. The first IP in the header must be allowlisted. |
| `Authorization` | Conditional | Accepted by the middleware when configured for the merchant integration. Follow the onboarding instructions for your environment. |

### Authentication and Encryption

The route accepts the standard Newton S2S request envelope:

- Signed payload: JWS-style body with `payload`, `signature`, and `protected`.
- Encrypted payload: JWE-style body with `protected`, `encryptedKey`, `iv`, `cipherText`, and `tag`.
- Plain decrypted JSON only in environments/configurations where Newton explicitly allows it.

For signed or encrypted requests, send `iat` inside the decrypted business payload. Newton validates this issued-at timestamp before signature verification. Authentication and envelope failures happen before business validation.

Example encrypted envelope shape:

```json
{
  "protected": "base64url-protected-header",
  "encryptedKey": "base64url-encrypted-key",
  "iv": "base64url-iv",
  "cipherText": "base64url-ciphertext",
  "tag": "base64url-tag"
}
```

## Request

### Required Minimum

For a normal outgoing payment, send at least:

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a1b2c3d4-device-fingerprint",
  "merchantRequestId": "ORDER12345",
  "payerVpa": "customer@bank",
  "payeeVpa": "payee@bank",
  "amount": "100.00",
  "upiRequestId": "TXN1234567890",
  "bankAccountUniqueId": "acc_hash_or_token",
  "remarks": "Payment for order",
  "currency": "INR",
  "transactionType": "P2P_PAY",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

You may send `accountReferenceId` instead of `bankAccountUniqueId` when that is the account identifier issued to your integration.

### Field Reference

Fields not listed with a default have no application default; omitted optional fields are not used for that feature.

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Must identify an active Newton merchant-customer record under the merchant in the headers. Max 256 characters. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint for the registered customer device. Must be non-empty and match the device on record. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate device fingerprint accepted during device validation. |
| `merchantRequestId` | string | Yes | No default. | Merchant order/reference id. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. |
| `payerVpa` | string | Yes | Newton lowercases this before processing. | Customer VPA to debit. Must belong to the merchant customer and be active for outgoing debit. |
| `payerUpiNumber` | string | No | No default. | Payer UPI number, when applicable. Must pass UPI number validation when supplied. |
| `payeeVpa` | string | Yes | No default. For international transactions, downstream payee details can be resolved from stored QR validation data, but this field is still required and validated. | Payee VPA. For `P2M_PAY`, Newton uses it to resolve the merchant/sub-merchant account. |
| `payeeBankAccountUniqueId` | string | Conditional | Returned only for `x-api-version > 0` when supplied. | Payee account identifier for self-pay or account-specific payee journeys. If supplied with `SELF_PAY`, it must be non-empty. |
| `payeeUpiNumber` | string | No | No default. | Payee UPI number. The request validator checks `upiNumber` and `payeeUpiNumber` when supplied. |
| `payeeName` | string | No | No default. | Payee display name. Validation is intentionally not enforced for compatibility with some partner flows. |
| `payeeAccNumRef` | string | No | No default. | International payee account number/reference. Resolved payment details can override this for international QR flows. |
| `payeeAccType` | string | No | No default. | International payee account type. |
| `payeeAccIfsc` | string | No | No default. | International payee IFSC. Must be non-empty when supplied. |
| `upiNumber` | string | No | No default. | Payee UPI number used by the generic payment request. Must pass UPI number validation when supplied. |
| `amount` | string | Yes | No default. | Debit amount. Must be greater than `0.00` and formatted with two decimals, for example `100.00`. |
| `minAmount` | string | No | No default. | Minimum amount, when used by a QR/intent flow. Must be greater than `0.00` and formatted with two decimals. |
| `upiRequestId` | string | Yes | No default. | Merchant-supplied UPI transaction id. 1 to 35 alphanumeric characters. Duplicate values are rejected. |
| `bankAccountUniqueId` | string | Conditional | No default. | Customer debit account hash/token. Send either this or `accountReferenceId` for normal integrations. |
| `accountReferenceId` | string | Conditional | No default. | Customer debit account id/reference. Send either this or `bankAccountUniqueId`. Required for GPay ICICI migrated-user flows; `ifsc` may also be required there. |
| `ifsc` | string | Conditional | No default. | Required with some migrated account-reference flows. Must be non-empty when supplied. |
| `credBlock` | string | Conditional | No default. | UPI credential block. Required when the payment mode needs credentials. For biometric credential requests, `clVersion` and `timestamp` are also required. |
| `isAmountBlocked` | boolean | No | No default. | Used for PPI/pre-approved debit flows where amount blocking is supported. |
| `remarks` | string | Yes | No default. Newton URL-decodes remarks before sending downstream. | Payment note. 1 to 255 characters. Must begin with an alphanumeric or hyphen after optional spaces and may contain letters, numbers, spaces, and hyphen. |
| `currency` | string | Yes | No default. | Currency for the transaction. New Indian UPI integrations normally send `INR`. |
| `transactionType` | string | Yes | No default. | One of `P2M_PAY`, `P2P_PAY`, `SCAN_PAY`, `INTENT_PAY`, `SELF_PAY`. Controls the business path. |
| `transactionReference` | string | Conditional | No default. | Context reference. Required with contextual offers. Also used in some self-pay or credit-card bill-payment flows. Must be non-empty when supplied. |
| `refUrl` | string | No | Newton URL-decodes it. May be defaulted downstream from PSP config when absent. | Merchant reference URL. |
| `refCategory` | string | No | Defaults to configured NPCI reference category when omitted. | Merchant reference category. |
| `mcc` | string | Conditional | No default. | Payee/merchant MCC. Must be 4 digits when supplied. Required for many P2M, QR, offer, and special-purpose flows. |
| `udfParameters` | string | No | Echoed in the response when supplied. | JSON-object string for merchant-defined metadata. Must parse as a JSON object and must not contain disallowed special characters. |
| `customerConsentType` | string | No | No default. | GST/customer consent identifier type. Allowed values: `PAN`, `AADHAAR`, `AADHAARTOKEN`, `PASSPORT`, `VOTERID`, `DRIVINGLICENSE`, `GSTIN`. |
| `qVer` | string | No | No default. | QR version for GST QR/QR payment details. |
| `qrTs` | string | No | No default. | QR timestamp. For non-international QR payments, if supplied it must not be in the future. |
| `qrMedium` | string | No | No default. | QR medium. |
| `qrExpireTs` | string | No | No default. | QR expiry timestamp. For non-international QR payments, if supplied it must not be in the past. |
| `query` | string | No | No default. | QR query string/details. |
| `qrVerToken` | string | No | No default. | International QR verification token or QR verification token where applicable. |
| `qrStan` | string | No | No default. | QR STAN/reference where applicable. |
| `invoiceName` | string | No | No default. | GST invoice name. Must be non-empty when supplied. |
| `invoiceNum` | string | No | No default. | GST invoice number. Must be non-empty when supplied. |
| `invoiceDate` | string | No | No default. | GST invoice date. |
| `split` | string | No | No default. | GST amount split string. Newton converts it into downstream split data. |
| `splitDetails` | array | No | No default. | Convenience-fee/tip split details. Must be configured for the merchant. Empty arrays are rejected. |
| `gstinNumber` | string | No | No default. | GSTIN. Must be non-empty when supplied. |
| `mid` | string | No | No default. | Merchant MID for QR/P2M merchant metadata. Must be non-empty when supplied. |
| `msid` | string | No | No default. | Merchant store/sub-id for QR/P2M merchant metadata. Must be non-empty when supplied. |
| `mtid` | string | No | No default. | Merchant terminal id for QR/P2M merchant metadata. Must be non-empty when supplied. |
| `mSubCode` | string | No | No default. | Merchant sub-code for merchant metadata. |
| `mType` | string | No | No default. | Merchant type for merchant metadata. |
| `mGenre` | string | No | No default. | Merchant genre/channel for merchant metadata. |
| `mOnBoardingType` | string | No | No default. | Merchant onboarding type for merchant metadata. |
| `mRegId` | string | No | No default. | Merchant registration id for merchant metadata. |
| `mPinCode` | string | No | No default. | Merchant pincode for merchant metadata. |
| `mTier` | string | No | No default. | Merchant tier for merchant metadata. |
| `mLoc` | string | No | No default. | Merchant location for merchant metadata. |
| `mInstCode` | string | No | No default. | Merchant institution code for merchant metadata. |
| `mBrand` | string | No | No default. | Merchant brand for merchant metadata. |
| `mLegal` | string | No | No default. | Merchant legal name for merchant metadata. |
| `mFranchise` | string | No | No default. | Merchant franchise name for merchant metadata. |
| `mOwnershipType` | string | No | No default. | Merchant ownership type for merchant metadata. |
| `initiationMode` | string | Conditional | No default. | NPCI initiation mode. Must be exactly 2 alphanumeric characters when supplied. Required by many QR/intent/special-purpose flows. |
| `purpose` | string | Conditional | No default. Returned only when `x-api-version > 1`. | NPCI purpose code. Must be exactly 2 uppercase alphanumeric characters when supplied. Controls UPI Lite, ICCW, international, and other feature behavior. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used for signed/encrypted request validation. Required for signed/encrypted S2S requests. |
| `baseAmount` | string | Conditional | No default. | Base/foreign currency amount for international/static QR flows. Must be non-empty when supplied. |
| `baseCurr` | string | Conditional | No default. | Base/foreign currency for international QR flows. |
| `fx` | string | No | Resolved from validated international QR data when available. | Foreign exchange rate for international payments. |
| `mkup` | string | No | Resolved from validated international QR data when available. | Markup for international payments. |
| `iQrPayLoad` | string | No | No default. | International QR payload. Must be non-empty when supplied. |
| `iConCode` | string | No | No default. | International country code. |
| `iNetInstId` | string | No | No default. | International network/institution id. |
| `originalTransactionUpiRequestId` | string | Conditional | No default. | Required for international payments. Used to fetch the prior validated international QR details. Must pass `upiRequestId` validation. |
| `location` | string | No | No default. | Payer/device location. Must be non-empty when supplied. |
| `geocode` | string | No | No default. | Latitude/longitude as `lat,long`. Latitude must be within 90 and longitude within 180. |
| `ip` | string | No | No default. | Customer/device IP address. Must be valid IPv4 or IPv6 when supplied. |
| `capability` | string | No | No default. | Device capability string. Length must be 1 to 99 when supplied. |
| `initiatingChannel` | string | No | Downstream flows treat omitted channel as mobile where a default is needed. | Allowed values: `MOB`, `IOTVOICE`. |
| `lrn` | string | Conditional | No default. | Lite reference number. Required for UPI Lite top-up, deregistration, transfer-out, and related purpose-code flows. |
| `timestamp` | string | Conditional | No default. | ISO timestamp validated when merchant config enables `checkIsValidISOTimestamp`. Required for biometric credential requests. |
| `ctxtCode` | object/string enum | Conditional | No default. | Contextual payment code. Required with offer payments. Serialized downstream as text. |
| `prodCode` | string | Conditional | No default. | Contextual product code. Max 99 characters when supplied. |
| `offerId` | string | Conditional | No default. | Contextual offer id. Max 10 characters when supplied. |
| `preAuthTokensParam` | object | No | No default. | Pre-authorization token parameters for enabled flows. |
| `clVersion` | string | Conditional | No default. | Customer library/version. Required for biometric credential requests. Must be non-empty when supplied. |

### Nested Request Objects

#### `splitDetails[]`

Use `splitDetails` only when the merchant is configured for convenience-fee, tip, or similar split components.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `name` | string | Yes | Split component name configured for the merchant. Must be non-empty. Duplicate names are rejected. |
| `value` | string | Yes | Split amount in two-decimal format. Must be greater than `0.00`. |

Validation rules:

- `splitDetails` must not be an empty array.
- Every `name` must be present in the merchant's configured `allowedSplitTypes`.
- Duplicate split names are rejected.
- The payer account type must be allowed for each split type in merchant configuration.
- If the account type is not allowed, Newton returns `JPCFEE`.

#### `ctxtCode`

`ctxtCode` is typed as a contextual-payment code object in the API type and is serialized downstream as text. Use it only when your integration is enabled for contextual offer payments.

Because the exact code set is controlled by product configuration, use only values shared during onboarding.

## Request Examples

### P2P Send Money

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a1b2c3d4-device-fingerprint",
  "merchantRequestId": "P2PORDER123",
  "payerVpa": "customer@bank",
  "payeeVpa": "friend@bank",
  "amount": "100.00",
  "upiRequestId": "P2PTXN123456789",
  "bankAccountUniqueId": "acc_hash_or_token",
  "remarks": "Dinner split",
  "currency": "INR",
  "transactionType": "P2P_PAY",
  "refUrl": "https://merchant.example/payments/P2PORDER123",
  "iat": "2026-07-02T10:30:00+05:30"
}
```

### P2M QR/Intent Pay With Merchant Metadata

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a1b2c3d4-device-fingerprint",
  "fallbackDeviceFingerPrint": "fallback-device-fingerprint",
  "merchantRequestId": "ORDER12345",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant-store@bank",
  "amount": "250.00",
  "upiRequestId": "P2MTXN123456789",
  "accountReferenceId": "acc_ref_123",
  "remarks": "Order payment",
  "currency": "INR",
  "transactionType": "P2M_PAY",
  "mcc": "5411",
  "initiationMode": "01",
  "purpose": "00",
  "refUrl": "https://merchant.example/orders/ORDER12345",
  "refCategory": "00",
  "mid": "MID123",
  "msid": "STORE123",
  "mtid": "TERM123",
  "udfParameters": "{\"cartId\":\"CART123\"}",
  "iat": "2026-07-02T10:31:00+05:30"
}
```

### P2M With Convenience Fee

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a1b2c3d4-device-fingerprint",
  "merchantRequestId": "ORDER12346",
  "payerVpa": "customer@bank",
  "payeeVpa": "merchant-store@bank",
  "amount": "100.00",
  "upiRequestId": "P2MTXN123456790",
  "bankAccountUniqueId": "acc_hash_or_token",
  "remarks": "Order payment",
  "currency": "INR",
  "transactionType": "P2M_PAY",
  "mcc": "5411",
  "splitDetails": [
    {
      "name": "CCONFEE",
      "value": "5.00"
    }
  ],
  "iat": "2026-07-02T10:32:00+05:30"
}
```

### UPI Lite Top-Up

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a1b2c3d4-device-fingerprint",
  "merchantRequestId": "LITE12345",
  "payerVpa": "customer@bank",
  "payeeVpa": "customer@bank",
  "amount": "500.00",
  "upiRequestId": "LITETXN123456789",
  "accountReferenceId": "acc_ref_123",
  "credBlock": "encrypted-credential-block",
  "remarks": "UPI Lite top-up",
  "currency": "INR",
  "transactionType": "P2P_PAY",
  "purpose": "41",
  "lrn": "LRN1234567890",
  "iat": "2026-07-02T10:33:00+05:30"
}
```

### International QR Payment

```json
{
  "merchantCustomerId": "CUST12345",
  "deviceFingerPrint": "a1b2c3d4-device-fingerprint",
  "merchantRequestId": "INTLORDER123",
  "payerVpa": "customer@bank",
  "payeeVpa": "foreignmerchant@bank",
  "amount": "820.00",
  "upiRequestId": "INTLTXN123456789",
  "bankAccountUniqueId": "acc_hash_or_token",
  "remarks": "International QR payment",
  "currency": "INR",
  "transactionType": "SCAN_PAY",
  "purpose": "83",
  "originalTransactionUpiRequestId": "VALQRTXN1234567",
  "baseCurr": "USD",
  "baseAmount": "10.00",
  "iat": "2026-07-02T10:34:00+05:30"
}
```

## Validation and Business Rules

### Request Validation

Newton validates the decrypted request before payment processing:

- Missing required JSON fields fail request parsing or business validation.
- `merchantCustomerId` must be 1 to 256 characters and match the configured merchant.
- `merchantRequestId` must be 1 to 35 characters and match `^[-._]*([a-zA-Z0-9][-._]*)+$`.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `payerVpa` and `payeeVpa` must be 3 to 255 characters and match `local@handle` VPA format.
- `amount`, `minAmount`, and `splitDetails[].value` must be two-decimal strings greater than `0.00`.
- `remarks` must be 1 to 255 characters and match Newton's allowed remarks pattern.
- `transactionType` must be one of `P2M_PAY`, `P2P_PAY`, `SCAN_PAY`, `INTENT_PAY`, `SELF_PAY`.
- Optional text fields validated with `lengthValidation` must not be empty when supplied.
- `mcc` must be exactly 4 digits when supplied.
- `initiationMode` must be exactly 2 alphanumeric characters when supplied.
- `purpose` must be exactly 2 uppercase alphanumeric characters when supplied.
- `geocode` must be `latitude,longitude` and within valid coordinate ranges.
- `ip` must be valid IPv4 or IPv6 when supplied.
- `capability` must be 1 to 99 characters when supplied.
- `prodCode` must be at most 99 characters.
- `offerId` must be at most 10 characters.
- `udfParameters` must be a JSON-object string and must pass the configured special-character restriction.

### Account, Device, and VPA Validation

After payload validation, Newton validates:

- The merchant from `x-merchant-id` and `x-merchant-channel-id`.
- The optional sub-merchant from sub-merchant headers.
- The merchant is allowed to call `sendMoneyS2S` and is not blocked for this API.
- The `merchantCustomerId` maps to a merchant customer and customer under the merchant.
- The customer has a device on record and `deviceFingerPrint` or `fallbackDeviceFingerPrint` matches that device.
- The `payerVpa` belongs to the customer and merchant customer.
- The payer VPA status allows outgoing debit.
- The debit account exists, belongs to the customer, and is active for the merchant customer.
- For normal integrations, one of `bankAccountUniqueId` or `accountReferenceId` must be supplied.
- For GPay ICICI migrated-account flows, `accountReferenceId` is required and `ifsc` is required when the account reference is a migrated id.

### Payment Behavior

For `P2M_PAY`:

- Newton resolves `payeeVpa` to a configured merchant or sub-merchant account.
- If the merchant config requires same-entity payment, the payee merchant must belong to the same merchant entity/group.
- Newton checks for an existing merchant order with the same `merchantRequestId`.
- Newton creates or updates a merchant order and merchant transaction attempt.
- The response can include `retryAllowed`, `maxLimit`, and `retryExpiry` for configured retry flows.

For `P2P_PAY`, `SCAN_PAY`, `INTENT_PAY`, and `SELF_PAY`:

- Newton validates the payer VPA and debit account.
- Newton validates special-purpose behavior such as UPI Lite, ICCW, international QR, or contextual offers when the related fields are present.
- The transaction is initiated directly through the send-money payment path without merchant-order retry semantics unless a feature-specific path adds them.

### Duplicate and Idempotency Behavior

`upiRequestId` is the transaction-level duplicate key.

- If a transaction already exists with the same `upiRequestId`, Newton returns `DUPLICATE_REQUEST`.
- Retrying a timed-out HTTP call with the same `upiRequestId` can therefore return a duplicate even if the original transaction is still pending or later succeeds.
- Use the transaction status API or callbacks to resolve the final outcome after a network timeout or ambiguous response.

For `P2M_PAY`, `merchantRequestId` is also checked against existing merchant orders:

- If a non-retriable or already terminal merchant order exists for the same `merchantRequestId`, Newton returns `DUPLICATE_REQUEST`.
- If the existing merchant order is in a retriable failure state and retry is enabled, Newton validates retry eligibility and may update the order for retry.
- If retry validation fails, Newton returns a payment-style response with `retryAllowed: false` and a JP-prefixed `gatewayResponseCode` such as `JP51`, `JP52`, or `JP53`.
- A retry attempt should use a new `upiRequestId` while reusing the same `merchantRequestId` only when retrying the same P2M merchant order under Newton's retry rules.

### Split and Convenience Fee

When `splitDetails` is supplied:

- The merchant must have `allowedSplitTypes` configured.
- The request must not send an empty list.
- Each split `name` must be allowed and unique.
- The debit account type must be allowed for the requested split type.
- Newton filters response `splitDetails` to configured split types before returning them.

### Contextual Offers

If any of `ctxtCode`, `prodCode`, or `offerId` is supplied:

- `mcc` must not be `0000`.
- `ctxtCode`, `offerId`, and `transactionReference` must all be present.
- `prodCode` is optional in the validation condition, but if supplied it must be at most 99 characters.

### Biometric Credential Requests

When `credBlock` is detected as a biometric credential block:

- `clVersion` must be present and non-empty.
- `timestamp` must be present and non-empty.

### QR Timestamp Rules

For non-international QR payments:

- `qrTs`, when supplied, must not be later than the current time.
- `qrExpireTs`, when supplied, must not be earlier than the current time.

### UPI Lite

UPI Lite behavior is controlled mainly by `purpose` and `lrn`.

- Initial top-up, subsequent top-up, deregistration, and transfer-out purpose codes require `lrn`.
- Initial top-up validates the number of active/allowed Lite accounts.
- Deregistration validates that no active Lite mandate blocks the operation.
- If Lite auto-top-up is active and the Lite balance after payment would fall below the threshold, Newton can create a linked execution transaction.

### International QR

For international payments:

- `purpose` must identify an international transaction according to merchant configuration.
- `originalTransactionUpiRequestId` is required to fetch the validated international QR information.
- Newton validates payee VPA and amount against the stored QR validation data when international checks are enabled.
- `baseCurr` and, for static QR cases, `baseAmount` are used to select or calculate FX details.
- Customer account and international activation records must be valid for the merchant/customer/account.

## Response

### Response Envelope

The successful decrypted business response has this shape:

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API envelope status. Success value is `SUCCESS`. |
| `responseCode` | string | API envelope response code. Success value is `SUCCESS`. |
| `responseMessage` | string | API envelope response message. Success value is `SUCCESS`. |
| `payload` | object | Payment result payload. |
| `udfParameters` | string | Echoed from request when supplied. |

Important: `status: "SUCCESS"` means the API call completed. Always inspect `payload.gatewayResponseStatus`.

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id. |
| `merchantRequestId` | string | Merchant request/order id supplied in the request. |
| `customerMobileNumber` | string | Customer mobile number, trimmed before response. |
| `payerVpa` | string | Payer VPA supplied in the request. |
| `payeeMcc` | string | Payee MCC resolved from transaction data. |
| `payeeMerchantCustomerId` | string | Payee merchant-customer id, when resolved and applicable. Not returned for ICICI PSP mode. |
| `payeeName` | string | Payee name from transaction payee information. |
| `payeeVpa` | string | Payee VPA supplied in the request. |
| `payeeBankAccountUniqueId` | string | Echoed from request only when `x-api-version > 0` and supplied. |
| `refUrl` | string | Reference URL resolved for the transaction. |
| `bankAccountUniqueId` | string | Debit account identifier returned as migrated id or account hash. |
| `bankCode` | string | Debit account bank code. |
| `maskedAccountNumber` | string | Masked debit account number. |
| `amount` | string | Amount supplied in the request. |
| `splitDetails` | array | Filtered split details returned when applicable. |
| `customerIncentive` | string | GST/customer incentive from transaction data, when present. |
| `transactionType` | string | Transaction type supplied in the request. |
| `transactionTimestamp` | string | Newton transaction creation timestamp. |
| `gatewayTransactionId` | string | Same as request `upiRequestId`. |
| `gatewayReferenceId` | string | UPI response/reference id. |
| `gatewayResponseStatus` | string | `SUCCESS`, `PENDING`, `DEEMED`, or `FAILURE`, derived from gateway response code and merchant configuration. |
| `gatewayResponseCode` | string | Gateway/NPCI/Newton transaction response code. `00` means success. `01` can mean pending when pending responses are enabled. `RB` maps to deemed. |
| `gatewayResponseMessage` | string | Gateway/NPCI/Newton response message. |
| `gatewayPayerResponseCode` | string | Payer-side response code, when available. |
| `gatewayPayeeResponseCode` | string | Payee-side response code, when available. |
| `gatewayPayeeReversalResponseCode` | string | Payee-side reversal response code, when available. |
| `gatewayPayerReversalResponseCode` | string | Payer-side reversal response code, when available. |
| `payeeAcType` | string | Payee account type, when version-controlled account data is available. |
| `payeeIfsc` | string | Payee IFSC, when version-controlled account data is available. |
| `riskScore` | string | Risk score, when supplied by the configured PSP/risk path. |
| `payerRevRespCode` | string | Payer reversal response code for ICICI PSP mode, when available. |
| `payeeRevRespCode` | string | Payee reversal response code for ICICI PSP mode, when available. |
| `arpc` | string | ARPC value, when available. |
| `purpose` | string | Purpose code from request. Returned only when `x-api-version > 1`. |
| `retryAllowed` | boolean | Present for P2M retry-enabled flows. Indicates whether retry is enabled/allowed by config for the order response. |
| `maxLimit` | integer | Maximum retry attempts configured for the P2M merchant order, when applicable. |
| `retryExpiry` | integer | Retry window in seconds for the P2M merchant order, when applicable. |

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
    "merchantRequestId": "ORDER12345",
    "customerMobileNumber": "9876543210",
    "payerVpa": "customer@bank",
    "payeeMcc": "5411",
    "payeeName": "Merchant Store",
    "payeeVpa": "merchant-store@bank",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "bankAccountUniqueId": "acc_hash_or_token",
    "bankCode": "123456",
    "maskedAccountNumber": "XXXXXX1234",
    "amount": "250.00",
    "transactionType": "P2M_PAY",
    "transactionTimestamp": "2026-07-02T10:31:05+05:30",
    "gatewayTransactionId": "P2MTXN123456789",
    "gatewayReferenceId": "620112345678",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "purpose": "00",
    "retryAllowed": true,
    "maxLimit": 3,
    "retryExpiry": 180
  },
  "udfParameters": "{\"cartId\":\"CART123\"}"
}
```

### Example Pending Gateway Response

The API envelope can still be successful while the payment is pending:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "ORDER12345",
    "customerMobileNumber": "9876543210",
    "payerVpa": "customer@bank",
    "payeeMcc": "5411",
    "payeeName": "Merchant Store",
    "payeeVpa": "merchant-store@bank",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "bankAccountUniqueId": "acc_hash_or_token",
    "bankCode": "123456",
    "maskedAccountNumber": "XXXXXX1234",
    "amount": "250.00",
    "transactionType": "P2M_PAY",
    "transactionTimestamp": "2026-07-02T10:31:05+05:30",
    "gatewayTransactionId": "P2MTXN123456789",
    "gatewayReferenceId": "620112345678",
    "gatewayResponseStatus": "PENDING",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "PENDING"
  }
}
```

## Response Versioning

The route reads `x-api-version` for a few response fields.

| Version behavior | Description |
| --- | --- |
| `x-api-version <= 0` | `payload.payeeBankAccountUniqueId` is omitted even if supplied in the request. |
| `x-api-version > 0` | `payload.payeeBankAccountUniqueId` can be returned when supplied. |
| `x-api-version <= 1` | `payload.purpose` is omitted. |
| `x-api-version > 1` | `payload.purpose` is returned when supplied in the request. |

## Error Handling

Failure responses use the same encrypted response transport as successful responses unless the failure occurs before response encryption can be applied. The examples below show decrypted bodies.

Most business failures follow this shape:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"merchantRequestId length not between 1 and 35\""
}
```

Clients should read `status`, `responseCode`, and `responseMessage`; HTTP status can be `200`, `400`, `401`, `422`, or `500` depending on the layer where the failure occurred.

### Authentication, API Access, and Envelope Failures

| Scenario | Decrypted response body |
| --- | --- |
| Missing or invalid merchant headers, merchant not found, invalid merchant/customer mapping, JWS verification failure, JWE decryption failure, invalid IP allowlist, or invalid timestamp | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` |
| API blocked or not allowed for merchant/sub-merchant | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` |
| SDK-style/envelope authentication failure where auth-failure response is used | `{"status":"FAILURE","responseCode":"AUTH_FAILURE","responseMessage":"AUTH_FAILURE"}` |
| Signed/encrypted request missing `iat` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"IAT is empty"}` |
| Encrypted payload parses but decrypted content is invalid JSON for the expected body | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Error in $: key \"upiRequestId\" not found"}` |

### Request Validation Failures

| Scenario | Decrypted response body |
| --- | --- |
| Generic request validation failure | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` |
| `merchantRequestId` empty, too long, or invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantRequestId length not between 1 and 35\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchant request id regex failed\""}` |
| `merchantCustomerId` empty, too long, or invalid characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"merchantCustomerId length is not in between 1 and 256\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"merchantCustomerId is not alphanumeric\""}` |
| Invalid payer VPA | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"payerVpa regex failed\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"payerVpa length is not between 3 and 255\""}` |
| Invalid payee VPA | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"payeeVpa regex failed\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"payeeVpa length is not between 3 and 255\""}` |
| Amount not in two-decimal format | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"amount regex match failed\""}` |
| Amount is `0.00` or negative | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"amount is not greater than 0.0\""}` |
| Invalid `upiRequestId` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"upiRequestId regex match failed\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"upiRequestId length is not between 1 and 35\""}` |
| Invalid `remarks` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"remarks regex match failed\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"remarks length is not between 1 and 255\""}` |
| Invalid `transactionType` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"EnumValidation \"Enum match failed WALLET_PAY\""}` |
| Invalid `mcc` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"mcc length is not 4\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"mcc regex match failed\""}` |
| Invalid `initiationMode` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"InitiationMode length is not 2\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"initiationMode regex match failed\""}` |
| Invalid `purpose` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"Purpose Code length is not 2\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"Purpose Code regex match failed\""}` |
| Invalid `udfParameters` JSON string | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"UnexpectedType \"JSON Text parse failed for udfParameters\""}` |
| Invalid `geocode` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"geocode not valid\""}` or `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"Incorrect latitude/longitude value\""}` |
| Invalid `ip` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"ValueValidation \"ip not valid\""}` |
| `capability` empty or more than 99 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"capability field length is not between 1 and 99\""}` |
| `offerId` more than 10 characters | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"Length of OFFER123456789 not between 1 and 10\""}` |

### Business and Product Validation Failures

| Scenario | Decrypted response body |
| --- | --- |
| Duplicate `upiRequestId` transaction | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| Duplicate `merchantRequestId` for a non-retriable/terminal P2M merchant order | `{"status":"FAILURE","responseCode":"DUPLICATE_REQUEST","responseMessage":"DUPLICATE_REQUEST"}` |
| Missing debit account selector for normal account lookup | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"bankAccountUniqueId or accountReferenceId is mandatory"}` |
| Device fingerprint mismatch | `{"status":"FAILURE","responseCode":"DEVICE_FINGERPRINT_MISMATCH","responseMessage":"DEVICE_FINGERPRINT_MISMATCH"}` |
| Biometric credential request missing `clVersion` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"clVersion cannot be empty for biometric credential requests"}` |
| Biometric credential request missing `timestamp` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"timestamp cannot be empty for biometric credential requests"}` |
| `splitDetails` is an empty array | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"splitDetails should not be an empty list"}` |
| Split type unsupported or duplicated | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Not a valid split type / Duplicate split type"}` |
| Split account type not configured or not allowed | `{"status":"FAILURE","responseCode":"JPCFEE","responseMessage":"Invalid split details / Missing convenience fee splits"}` |
| Offer fields sent with MCC `0000` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Payee MCC cannot be 0000"}` |
| Offer fields incomplete | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Insufficient Offer Details"}` |
| Invalid non-international QR timestamp | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid qrTs"}` |
| Expired non-international QR | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid qrExpireTs"}` |
| Invalid global VPA IFSC-style payee VPA | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"payee vpa is not valid"}` |
| Partner app attempts blocked P2P flow | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Invalid MCC"}` |
| UPI Lite account not found | `{"status":"FAILURE","responseCode":"JPLA","responseMessage":"Lite Account not found"}` |
| Active Lite mandate blocks deregistration | `{"status":"FAILURE","responseCode":"JPLM","responseMessage":"You have active lite mandate(s). Please retry after revoking all lite mandates."}` |
| International payment missing original validation transaction | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"getInternationalTxnInfo - originalTransactionUpiRequestId"}` |
| International QR validation data not found | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"verifyInternationalTxnInfo - intlTxnInfo not found in redis"}` |
| International QR payee VPA or amount mismatch | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"International QR payee VPA mismatch"}` |
| P2M payee merchant VPA is not valid for the merchant/entity | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid Merchant VPA"}` |

### Downstream and Gateway Failures

When the PSP/NPCI path returns a business failure, Newton can still return a successful API envelope with a failed gateway payload:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "merchantRequestId": "ORDER12345",
    "customerMobileNumber": "9876543210",
    "payerVpa": "customer@bank",
    "payeeMcc": "5411",
    "payeeVpa": "merchant-store@bank",
    "refUrl": "https://merchant.example/orders/ORDER12345",
    "bankAccountUniqueId": "acc_hash_or_token",
    "bankCode": "123456",
    "maskedAccountNumber": "XXXXXX1234",
    "amount": "250.00",
    "transactionType": "P2M_PAY",
    "transactionTimestamp": "2026-07-02T10:31:05+05:30",
    "gatewayTransactionId": "P2MTXN123456789",
    "gatewayReferenceId": "620112345678",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U30",
    "gatewayResponseMessage": "Debit has failed"
  }
}
```

Timeout/service-unavailable handling can also return a failure body:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "UPI service is not reachable at the moment for transactional apis"
}
```

If pending responses are disabled and the gateway response code is `01`, Newton returns:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

Unexpected server, database, encryption, or cache failures can return:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Retry and Client Handling Guidance

- Treat `payload.gatewayResponseStatus`, not only top-level `status`, as the payment outcome.
- For `gatewayResponseStatus: "SUCCESS"`, mark the payment successful.
- For `gatewayResponseStatus: "PENDING"` or `"DEEMED"`, do not create a new payment attempt immediately. Poll transaction status or wait for callbacks.
- For HTTP/network timeout where no decrypted body is available, query status using the same `upiRequestId` before retrying.
- Do not reuse an `upiRequestId` for a new logical payment. A duplicate `upiRequestId` is rejected.
- For non-P2M flows, use a fresh `upiRequestId` for any new attempt after confirming the previous attempt failed.
- For `P2M_PAY`, reuse `merchantRequestId` only when retrying the same merchant order and Newton has indicated retry is allowed or your onboarding flow supports P2M retry. Use a fresh `upiRequestId` for the retry attempt.
- Store `gatewayReferenceId` and gateway response codes for reconciliation with callbacks/status APIs.
- Preserve and log decrypted failure bodies; validation errors can include field-specific messages needed to correct the request.

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:500)
- Route handler and middleware sequence: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:2768)
- Request and response types: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:407)
- Request validation instance: [src/Newton/Types/API/ServerToServer/Transaction.hs](../../src/Newton/Types/API/ServerToServer/Transaction.hs:509)
- S2S envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:64)
- Merchant signature, API access, timestamp, and IP checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:47)
- Send Money S2S product route: [src/Newton/Product/MerchantTransactionsV2.hs](../../src/Newton/Product/MerchantTransactionsV2.hs:743)
- Generic request transformer: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:1071)
- Response transformer: [src/Newton/Utils/Transformers/Transformer6.hs](../../src/Newton/Utils/Transformers/Transformer6.hs:291)
- Shared send-money execution path and duplicate checks: [src/Newton/Product/MerchantTransactionsSDKV2.hs](../../src/Newton/Product/MerchantTransactionsSDKV2.hs:825)
- P2M merchant-order duplicate and retry handling: [src/Newton/Product/MerchantTransactionsSDKV2.hs](../../src/Newton/Product/MerchantTransactionsSDKV2.hs:340)
- Split validation: [src/Newton/Utils/ApiValidation.hs](../../src/Newton/Utils/ApiValidation.hs:193)
- Common field validation rules: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:292)
- Error body constructors: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:7)
