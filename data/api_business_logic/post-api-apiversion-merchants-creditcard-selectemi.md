# Select EMI API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/creditCard/selectEmi`

## Overview

Select EMI is a Newton merchant server-to-server API used after a customer has selected a credit-card EMI offer or confirmed an EMI foreclosure.

The merchant calls this API with the Newton-linked credit-card account, customer/device identifiers, original transaction context, payer/payee details, customer consent, and either selected EMI offer data or foreclosure details. Newton validates the merchant, customer, bound device, linked credit account, and request rules, then sends a `SELECT` `ReqEmi` request to NPCI.

Use this API only after the customer has completed the preceding EMI decision step, usually from a successful `checkEmi` response. Do not use it to list offers. Use `checkEmi` first, then pass the selected offer or confirmed foreclosure values to `selectEmi`.

## Business Use Case

Select EMI helps merchants:

- Apply the EMI offer selected by the customer during a purchase or after a completed credit-card transaction.
- Submit the MPIN credential block required for post-transaction EMI conversion or EMI foreclosure.
- Foreclose an existing EMI after the customer has reviewed foreclosure amount, penalty, principal, and interest details.
- Correlate the selection with the original transaction, prior `checkEmi` request where required, and the merchant customer.
- Receive the issuer/NPCI `emiId` when the EMI operation is applied.
- Reconcile ambiguous or delayed selection outcomes through the `emiStatus` API.

Supported `emiTxnType` values:

| `emiTxnType` | Use case | Main payload required |
| --- | --- | --- |
| `DURING` | Select an EMI offer during a purchase/payment journey. | Original transaction id and amount, selected `emiData`, payer/payee VPA, MCC, consent, device fingerprint. |
| `POST` | Convert a completed transaction to EMI after a successful post-transaction EMI check. | Original transaction id, amount, timestamp, prior `checkEmiUpiRequestId`, selected `emiData`, `credBlock`, payer/payee VPA, MCC, consent, device fingerprint. |
| `FORECLOSE` | Foreclose an existing EMI. | Original transaction id and amount, `forecloseDetails`, `credBlock`, payer/payee VPA, MCC, consent, device fingerprint. |

## Integration Flow

1. Merchant identifies the Newton `merchantCustomerId`, linked credit-card `bankAccountUniqueId`, and active device fingerprint.
2. Merchant calls `checkEmi` to fetch eligible offers or foreclosure details.
3. Merchant shows the selected offer or foreclosure quote to the customer and captures explicit customer consent.
4. For `POST` and `FORECLOSE`, merchant obtains the customer MPIN credential block from the approved client/UPI credential flow.
5. Merchant calls `selectEmi` with a fresh `upiRequestId` for the selection operation.
6. Newton decrypts/verifies the S2S envelope, checks merchant API access, resolves the merchant customer, validates the linked device and account, confirms the account is a credit account, fetches the original transaction record, and sends `ReqEmi` with request type `SELECT`.
7. Merchant decrypts/verifies the response and checks the nested gateway fields. Treat the EMI as applied only when the nested payload is successful and contains an `emiId`.
8. If the select response is ambiguous or does not contain an `emiId`, call `emiStatus` with the same select `upiRequestId`.

Important identifiers:

- `upiRequestId`: Merchant-generated id for this select operation. Newton sends it to NPCI and returns it as `payload.gatewayTransactionId`. Use the same value as `selectEmiUpiRequestId` when calling `emiStatus`.
- `originalTxnUpiRequestId`: Newton UPI request id of the original payment/transaction. Newton looks this up before sending `ReqEmi` for all select variants.
- `checkEmiUpiRequestId`: UPI request id of the earlier `checkEmi` call. Required only for `POST` selection.
- `bankAccountUniqueId`: Merchant-customer account mapping for the linked credit-card account.
- `emiId`: EMI identifier returned by issuer/NPCI when the selection or foreclosure is applied.

## Endpoint

```http
POST /api/{apiVersion}/merchants/creditCard/selectEmi
```

Payloads use the standard Newton S2S request and response envelope. The examples below show decrypted business payloads for readability.

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | Use `application/json`. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-timestamp` | Yes | 13-digit epoch milliseconds. Must be within the accepted request freshness window. |
| `x-merchant-signature` | Conditional | Required for legacy/plain payload signing. JWS/JWE integrations verify the signed payload instead. |
| `x-api-version` | Recommended | Use the version shared during onboarding. |
| `x-request-id` | Recommended | Merchant request correlation id. Newton echoes or generates it in the response headers. |
| `x-session-id` | Recommended | Merchant session correlation id. Defaults to `x-request-id` when omitted. |
| `x-sub-merchant-id` | Conditional | Send only when the integration is configured for sub-merchants. |
| `x-sub-merchant-channel-id` | Conditional | Send only when the integration is configured for sub-merchants. |

### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version path segment configured for the merchant integration. |

## Authentication and Encryption

Newton accepts the S2S encrypted/signed envelope configured during onboarding:

- `JWS_AND_JWE`: request body is encrypted as JWE and contains a signed JWS payload.
- `JWS`: request body is a signed JWS payload.
- Legacy/plain integrations: request body is plain JSON and must be protected by the configured merchant signature headers.

For JWS/JWE requests, include `iat` in the decrypted business payload. The route validates `iat` and `x-timestamp` as 13-digit epoch millisecond timestamps within the accepted freshness window.

The route first resolves the merchant from headers, decrypts/verifies the `EncRequest`, validates the merchant signature or signed/encrypted payload, checks blocked/allowed API configuration for `selectEmiS2S`, validates IP allowlisting when configured, and then resolves the merchant customer from `merchantCustomerId`.

Responses use the corresponding configured response protection. Legacy/plain response mode includes an `X-Response-Signature` header along with `x-requestid` and `x-sessionid`; JWS/JWE response mode returns a signed or encrypted body.

## Request

### Required Minimum by Variant

`DURING` selection:

```json
{
  "upiRequestId": "SELEMI000000000000000001",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "DURING",
  "originalTxnUpiRequestId": "PAYTXN000000000000000001",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "userConsent": "Y",
  "emiData": {
    "seqNum": "1",
    "offerId": "OFFER-3M-001",
    "tenure": "3",
    "amount": "12000.00",
    "intRatePct": "12.00",
    "intRateAmt": "360.00",
    "totalAmt": "12360.00",
    "discountAmt": "0.00",
    "procFee": "99.00"
  },
  "deviceFingerPrint": "device-fingerprint-hash",
  "iat": "1783000000000"
}
```

`POST` selection:

```json
{
  "upiRequestId": "SELEMI000000000000000002",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "POST",
  "originalTxnUpiRequestId": "PAYTXN000000000000000001",
  "originalTxnAmt": "12000.00",
  "originalTxnTs": "2026-07-02T10:15:30+05:30",
  "checkEmiUpiRequestId": "CHKEMI000000000000000001",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"type\":\"PIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"<encrypted-mpin>\",\"ki\":\"<key-index>\",\"hmac\":\"<hmac>\"}}}",
  "userConsent": "Y",
  "emiData": {
    "seqNum": "1",
    "offerId": "OFFER-3M-001",
    "tenure": "3",
    "amount": "12000.00",
    "intRatePct": "12.00",
    "intRateAmt": "360.00",
    "totalAmt": "12360.00",
    "discountAmt": "0.00",
    "procFee": "99.00"
  },
  "deviceFingerPrint": "device-fingerprint-hash",
  "iat": "1783000000000"
}
```

`FORECLOSE` selection:

```json
{
  "upiRequestId": "SELEMI000000000000000003",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "FORECLOSE",
  "originalTxnUpiRequestId": "PAYTXN000000000000000001",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"type\":\"PIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"<encrypted-mpin>\",\"ki\":\"<key-index>\",\"hmac\":\"<hmac>\"}}}",
  "userConsent": "Y",
  "forecloseDetails": {
    "emiId": "EMI123456789",
    "forecloseAmt": "8120.00",
    "penaltyAmt": "120.00",
    "principalAmt": "8000.00",
    "intRatePct": "12.00"
  },
  "deviceFingerPrint": "device-fingerprint-hash",
  "iat": "1783000000000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `upiRequestId` | string | Yes | No default. | Merchant-generated id for this select request. Must be 1 to 35 alphanumeric characters. Returned as `payload.gatewayTransactionId`; use it as `selectEmiUpiRequestId` for `emiStatus`. |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must match the authenticated merchant customer context. Max 256 characters. |
| `emiTxnType` | string | Yes | No default. | Allowed values: `DURING`, `POST`, `FORECLOSE`. |
| `originalTxnUpiRequestId` | string | Yes | No default. | Original Newton UPI request id/payment transaction id. Newton fetches the original self-initiated transaction to send original RRN and response code to NPCI. |
| `originalTxnAmt` | string | Yes | No default. | Original transaction amount sent to NPCI as the EMI amount context. Send the same amount used in the EMI check or original payment. |
| `originalTxnTs` | string | Conditional | Required for `POST`. Optional for `DURING` and `FORECLOSE`; forwarded to NPCI when supplied. | Original transaction timestamp sent as `orgTxnDate`. |
| `checkEmiUpiRequestId` | string | Conditional | Required for `POST`. Omit for `DURING` and `FORECLOSE` unless instructed by Newton. | UPI request id from the earlier `checkEmi` call, sent to NPCI as `orgChkTxnId`. |
| `payerVpa` | string | Yes | No client-facing default. | Customer/payer VPA. Must be non-empty and should be the VPA/account context used for the EMI check. |
| `bankAccountUniqueId` | string | Yes | No default. | Linked credit-card account mapping for the merchant customer. Must resolve to an active `CREDIT` account. |
| `payeeVpa` | string | Yes | No default. | Merchant/payee VPA. Must be non-empty and should match the payee context used for the EMI check. |
| `mcc` | string | Yes | No default. | Merchant category code. Must be exactly 4 digits. |
| `credBlock` | string | Conditional | Required for `POST` and `FORECLOSE`; omitted for normal `DURING` selection. | JSON string containing the MPIN credential block generated by the approved credential flow. Newton decodes this string and forwards the `mpincred` as NPCI PIN/MPIN credentials. |
| `userConsent` | string | Yes | No default. | Must be `"Y"`. Newton validates consent and sends EMI consent to NPCI for select requests. |
| `emiData` | object | Conditional | Required for `DURING` and `POST`; omit for `FORECLOSE`. | Selected EMI offer details, normally copied from the `checkEmi` response item chosen by the customer. |
| `forecloseDetails` | object | Conditional | Required for `FORECLOSE`; omit for `DURING` and `POST`. | Foreclosure values confirmed by the customer, normally copied from the `checkEmi` foreclosure response. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint for the bound customer device. Must match the stored fingerprint, unless `fallbackDeviceFingerPrint` matches. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate fingerprint accepted for device match checks. |
| `remarks` | string | No | If omitted, Newton sends `ReqEmi` as the downstream NPCI note. | Customer/merchant-facing note. Must be 1 to 255 characters when supplied. |
| `udfParameters` | string | No | Omitted from response when absent. | JSON-object string for merchant metadata. Echoed in the response when supplied. |
| `iat` | string | Conditional | Required for JWS/JWE requests. Not required for plain payload mode. | Issued-at timestamp used by S2S request freshness validation. Use 13-digit epoch milliseconds. |
| `clVersion` | string | No | No default. | Client library/version value forwarded to NPCI when supplied. Must be non-empty when present. |

### Conditional Rules

| `emiTxnType` | Required transaction context | Required operation data |
| --- | --- | --- |
| `DURING` | `originalTxnUpiRequestId`, `originalTxnAmt`, `payerVpa`, `payeeVpa`, `mcc`. | `emiData.seqNum`, `emiData.offerId`, `emiData.tenure`, `emiData.amount`, `emiData.intRatePct`, `emiData.intRateAmt`, `emiData.totalAmt`, `emiData.discountAmt`, `emiData.procFee`. |
| `POST` | `originalTxnUpiRequestId`, `originalTxnAmt`, `originalTxnTs`, `checkEmiUpiRequestId`, `payerVpa`, `payeeVpa`, `mcc`, `credBlock`. | Same required `emiData` fields as `DURING`. |
| `FORECLOSE` | `originalTxnUpiRequestId`, `originalTxnAmt`, `payerVpa`, `payeeVpa`, `mcc`, `credBlock`. | `forecloseDetails.emiId`, `forecloseDetails.forecloseAmt`, `forecloseDetails.penaltyAmt`, `forecloseDetails.principalAmt`, `forecloseDetails.intRatePct`. |

### Nested Request Objects

Nested objects do not have field-level defaults unless called out below. Optional object fields are omitted from JSON when absent, but the product validation requires many of them depending on `emiTxnType`.

#### `emiData`

Use `emiData` for `DURING` and `POST` selection. Send the exact selected offer values returned by `checkEmi` where possible.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `seqNum` | string | Yes for `DURING` and `POST` | Offer sequence number from `checkEmi`. Must be non-empty for selection. |
| `offerId` | string | Yes for `DURING` and `POST` | Offer id selected by the customer. Must be non-empty for selection. |
| `tenure` | string | Yes for `DURING` and `POST` | EMI tenure selected by the customer. |
| `amount` | string | Yes for `DURING` and `POST` | EMI amount from the selected offer. |
| `intRatePct` | string | Yes for `DURING` and `POST` | Interest rate percentage from the selected offer. |
| `intRateAmt` | string | Yes for `DURING` and `POST` | Interest amount from the selected offer. |
| `totalAmt` | string | Yes for `DURING` and `POST` | Total amount from the selected offer. |
| `discountAmt` | string | Yes for `DURING` and `POST` | Discount amount from the selected offer. Send `"0.00"` if the selected offer has no discount and that is the value returned by `checkEmi`. |
| `procFee` | string | Yes for `DURING` and `POST` | Processing fee from the selected offer. Send `"0.00"` if the selected offer has no processing fee and that is the value returned by `checkEmi`. |
| `imei` | string | No | Forwarded to NPCI when supplied. Omitted when absent. |

#### `forecloseDetails`

Use `forecloseDetails` only for `FORECLOSE` selection. Send the values confirmed by the customer from the preceding foreclosure check.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `emiId` | string | Yes for `FORECLOSE` | EMI id to foreclose. |
| `forecloseAmt` | string | Yes for `FORECLOSE` | Foreclosure amount confirmed by the customer. |
| `penaltyAmt` | string | Yes for `FORECLOSE` | Penalty amount confirmed by the customer. |
| `principalAmt` | string | Yes for `FORECLOSE` | Principal amount confirmed by the customer. |
| `intRatePct` | string | Yes for `FORECLOSE` | Interest rate percentage confirmed by the customer. |

#### `credBlock`

`credBlock` is a string field, not a JSON object field. The string value must itself contain JSON generated by the approved credential capture flow. Newton decodes that string into a `CredBlock` and requires `mpincred` for this EMI select path.

Expanded before JSON-string escaping, the minimum expected shape is:

```json
{
  "mpincred": {
    "subType": "MPIN",
    "type": "PIN",
    "data": {
      "code": "NPCI",
      "encryptedBase64String": "<encrypted-mpin>",
      "ki": "<key-index>",
      "hmac": "<hmac>"
    }
  }
}
```

Do not handcraft or log real credential values. Use the credential block exactly as produced by the approved client/UPI credential library.

### Defaults and Omitted Field Behavior

- `remarks`: downstream note defaults to `ReqEmi`.
- `udfParameters`: no processing default; echoed back only when supplied.
- `iat`: no business default. Required for signed/encrypted envelope validation even though it is optional in the business type.
- `clVersion`: no default; not sent to NPCI when omitted.
- `fallbackDeviceFingerPrint`: no default; only used as an alternate device match candidate when supplied.
- `emiData`: no default. Required for `DURING` and `POST`; omitted for `FORECLOSE`.
- `forecloseDetails`: no default. Required for `FORECLOSE`; omitted for `DURING` and `POST`.
- `credBlock`: no default. Required for `POST` and `FORECLOSE`; normally omitted for `DURING`.
- Response fields with absent `Maybe` values, such as `emiId` and `udfParameters`, are omitted rather than returned as `null`.

### Validation Notes

Newton applies both request-shape validation and EMI-specific business validation:

- `upiRequestId`: 1 to 35 alphanumeric characters.
- `merchantCustomerId`: non-empty, max 256 characters, restricted character set, and must match the merchant customer resolved during signature verification.
- `emiTxnType`: must parse as `DURING`, `POST`, or `FORECLOSE`.
- `bankAccountUniqueId`, `deviceFingerPrint`, `credBlock`, and `clVersion`: must be non-empty when supplied or required.
- `mcc`: exactly 4 digits.
- `userConsent`: exactly `"Y"`.
- `remarks`: 1 to 255 characters, letters/numbers/spaces/hyphen.
- `udfParameters`: must be a JSON-object string and must pass text character validation.
- Conditional `emiData` and `forecloseDetails` fields must be present and non-empty for their variants.
- `originalTxnUpiRequestId` must resolve to an original self-initiated Newton transaction; otherwise selection fails before NPCI.
- `bankAccountUniqueId` must map to an active account for the merchant customer.
- The resolved account must be a credit-card/`CREDIT` account.
- `deviceFingerPrint` or `fallbackDeviceFingerPrint` must match the bound customer's stored device fingerprint.
- The API must be enabled for the merchant; blocked or unallowed API configuration fails before product logic.

## Request Examples

### During-Purchase Selection With Metadata

```json
{
  "upiRequestId": "SELEMI000000000000000011",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "DURING",
  "originalTxnUpiRequestId": "PAYTXN000000000000000011",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "userConsent": "Y",
  "emiData": {
    "seqNum": "1",
    "offerId": "OFFER-3M-001",
    "tenure": "3",
    "amount": "12000.00",
    "intRatePct": "12.00",
    "intRateAmt": "360.00",
    "totalAmt": "12360.00",
    "discountAmt": "0.00",
    "procFee": "99.00"
  },
  "deviceFingerPrint": "device-fingerprint-hash",
  "fallbackDeviceFingerPrint": "previous-device-fingerprint-hash",
  "remarks": "Select EMI for order ORDER12345",
  "udfParameters": "{\"orderId\":\"ORDER12345\",\"offerId\":\"OFFER-3M-001\"}",
  "iat": "1783000000000",
  "clVersion": "2.0"
}
```

### Post-Transaction EMI Conversion

```json
{
  "upiRequestId": "SELEMI000000000000000012",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "POST",
  "originalTxnUpiRequestId": "PAYTXN000000000000000012",
  "originalTxnAmt": "12000.00",
  "originalTxnTs": "2026-07-02T10:15:30+05:30",
  "checkEmiUpiRequestId": "CHKEMI000000000000000012",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"type\":\"PIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"<encrypted-mpin>\",\"ki\":\"<key-index>\",\"hmac\":\"<hmac>\"}}}",
  "userConsent": "Y",
  "emiData": {
    "seqNum": "2",
    "offerId": "OFFER-6M-001",
    "tenure": "6",
    "amount": "12000.00",
    "intRatePct": "14.00",
    "intRateAmt": "840.00",
    "totalAmt": "12840.00",
    "discountAmt": "0.00",
    "procFee": "199.00"
  },
  "deviceFingerPrint": "device-fingerprint-hash",
  "remarks": "Post transaction EMI conversion",
  "udfParameters": "{\"orderId\":\"ORDER12345\",\"attempt\":\"1\"}",
  "iat": "1783000000000"
}
```

### EMI Foreclosure

```json
{
  "upiRequestId": "SELEMI000000000000000013",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "FORECLOSE",
  "originalTxnUpiRequestId": "PAYTXN000000000000000013",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "credBlock": "{\"mpincred\":{\"subType\":\"MPIN\",\"type\":\"PIN\",\"data\":{\"code\":\"NPCI\",\"encryptedBase64String\":\"<encrypted-mpin>\",\"ki\":\"<key-index>\",\"hmac\":\"<hmac>\"}}}",
  "userConsent": "Y",
  "forecloseDetails": {
    "emiId": "EMI123456789",
    "forecloseAmt": "8120.00",
    "penaltyAmt": "120.00",
    "principalAmt": "8000.00",
    "intRatePct": "12.00"
  },
  "deviceFingerPrint": "device-fingerprint-hash",
  "remarks": "Foreclose EMI",
  "iat": "1783000000000"
}
```

## Response

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Newton API processing status. For a processed downstream response, this is `SUCCESS` even when NPCI/business status is failure. |
| `responseCode` | string | Newton response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Newton response message. Success value is `SUCCESS`. |
| `payload` | object | Select EMI result. Present for successful Newton processing. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `gatewayResponseStatus` | string | Downstream EMI result status, usually `SUCCESS` or `FAILURE`. Use this with `gatewayResponseCode` and `emiId`; do not rely only on the top-level `status`. |
| `gatewayResponseCode` | string | NPCI/downstream response code. Defaults to `00` when no downstream code is available. |
| `gatewayResponseMessage` | string | `Your EMI operation is successfully applied.` when `gatewayResponseCode` is `00`; otherwise the mapped downstream message. |
| `emiId` | string | EMI id returned by issuer/NPCI when the EMI operation is applied. Omitted when not available. |
| `gatewayTransactionId` | string | Same value as request `upiRequestId`. Use it as `selectEmiUpiRequestId` for `emiStatus`. |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id supplied in the request. |

### Success Response: EMI Applied

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your EMI operation is successfully applied.",
    "emiId": "EMI1234567890",
    "gatewayTransactionId": "SELEMI000000000000000011",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345"
  },
  "udfParameters": "{\"orderId\":\"ORDER12345\",\"offerId\":\"OFFER-3M-001\"}"
}
```

### Success Response: Foreclosure Applied

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your EMI operation is successfully applied.",
    "emiId": "EMI123456789",
    "gatewayTransactionId": "SELEMI000000000000000013",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345"
  }
}
```

### Business Failure Returned in a Success Envelope

NPCI can return a business failure after Newton has successfully processed the API call. In that case the top-level status remains `SUCCESS`, while `payload.gatewayResponseStatus` is `FAILURE`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "C3",
    "gatewayResponseMessage": "Invalid credit card/Card not eligible for EMI",
    "gatewayTransactionId": "SELEMI000000000000000011",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345"
  }
}
```

### Ambiguous Downstream Timeout Response

For select flows, an NPCI timeout can be converted into a processed Newton response with nested `gatewayResponseStatus = "FAILURE"` and no `emiId`. Because the payload code can default to `00` when no NPCI code is available, clients must not treat `gatewayResponseCode = "00"` alone as success.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your EMI operation is successfully applied.",
    "gatewayTransactionId": "SELEMI000000000000000012",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345"
  }
}
```

Treat this as unknown or pending, not as EMI applied. Call `emiStatus` with `selectEmiUpiRequestId = "SELEMI000000000000000012"`.

## Response Interpretation

First check the outer response:

- If outer `status` is `FAILURE`, the request did not complete at the Newton/API layer. Fix the validation, authentication, configuration, account/device, or downstream availability issue shown in `responseCode` and `responseMessage`.
- If outer `status` is `SUCCESS`, Newton processed the request enough to return a business payload. Then inspect `payload.gatewayResponseStatus`, `payload.gatewayResponseCode`, and `payload.emiId`.

Treat the EMI operation as applied only when:

- outer `status` is `SUCCESS`;
- `payload.gatewayResponseStatus` is `SUCCESS`;
- `payload.gatewayResponseCode` is `00`; and
- `payload.emiId` is present.

When `emiId` is absent:

- If `gatewayResponseStatus` is `FAILURE`, do not mark EMI as applied even when `gatewayResponseCode` is `00`.
- If the response is ambiguous, pending, or the client timed out without a decrypted body, call `emiStatus` using the select `upiRequestId`.
- If `gatewayResponseCode` is a terminal issuer/NPCI error code, mark the EMI operation as failed according to your business rules and show the mapped failure reason where appropriate.

## Error Handling

Failure responses use the same S2S response protection as success responses. The examples below show decrypted response bodies. When `payload` is empty, it is omitted.

Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, or `500`; clients should read `status`, `responseCode`, and `responseMessage` from the decrypted body.

### Failure Scenarios

| Scenario | Example decrypted response body | Client handling |
| --- | --- | --- |
| Request field validation fails, such as invalid `upiRequestId`, empty `bankAccountUniqueId`, invalid MCC, invalid consent, invalid remarks, or invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"upiRequestId regex match failed\""}` | Fix the request. Do not retry unchanged. |
| `emiTxnType` is invalid or cannot be parsed | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"EnumValidation \"Enum match failed \\\"INSTALLMENT\\\"\""}` | Send only `DURING`, `POST`, or `FORECLOSE`. |
| `userConsent` is missing or not `"Y"` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"RegexValidation \"User-consent should be Y\""}` | Capture explicit consent and send `userConsent = "Y"`. |
| Missing selected offer fields for `DURING` or `POST` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Emi-Offer-Id is required in case of DURING-SELECT; Emi-Tenure is required in case of DURING-SELECT"}` | Pass the complete selected `emiData` from `checkEmi`. |
| Missing `checkEmiUpiRequestId` for `POST` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Check-Txn-Id is required in case of POST-SELECT"}` | Send the UPI request id of the earlier post-transaction `checkEmi`. |
| Missing `credBlock` for `POST` or `FORECLOSE` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Cred-Block is required in case of POST-SELECT"}` | Generate and send a valid MPIN credential block. |
| Missing foreclosure fields for `FORECLOSE` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Foreclose-Emi-Id is required in case of FORECLOSE-SELECT; Foreclose-Amt is required in case of FORECLOSE-SELECT"}` | Pass the complete `forecloseDetails` returned/confirmed from foreclosure check. |
| Missing or stale `iat`/`x-timestamp` for signed/encrypted requests | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` | Regenerate the timestamp, signature/envelope, and request. |
| JWS/JWE request omits `iat` | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid IAT is empty"}` | Include `iat` as a 13-digit epoch millisecond timestamp inside the decrypted payload. |
| Timestamp is not a 13-digit epoch millisecond value | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` | Fix timestamp generation. |
| JWS verification, JWE decryption, missing key id/private key, or malformed protected payload fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Check keys, `kid`, encryption mode, body canonicalization, and onboarding configuration. |
| Legacy/plain signature headers are missing or signature verification fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Recompute signature over the exact request body and timestamp. |
| Merchant configuration blocks or does not allow `selectEmiS2S` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Enable the API for the merchant/channel before retrying. |
| Merchant IP allowlist rejects the request | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Call from an allowlisted IP or update merchant configuration. |
| `merchantCustomerId` does not match the authenticated merchant customer context | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid merchantCustomerId"}` | Use the customer id registered under the same merchant/channel. |
| Device id is missing on the merchant customer record or device lookup fails | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid DeviceId cannot be null for merchantCustomer"}` or `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Re-bind or recover the customer device before retrying. |
| Device fingerprint does not match the bound device | `{"status":"FAILURE","responseCode":"DEVICE_FINGERPRINT_MISMATCH","responseMessage":"DEVICE_FINGERPRINT_MISMATCH"}` | Send the active device fingerprint or fallback fingerprint. |
| `bankAccountUniqueId` is not linked to the merchant customer or account lookup fails | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Account not found"}` | Refresh linked accounts and use the credit-card account mapping returned by Newton. |
| Linked account is not a credit-card account | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Account type should be CREDIT"}` | Use a linked credit-card account. |
| `originalTxnUpiRequestId` does not resolve to an original transaction record | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Original record not found"}` | Verify the original transaction id and use the original Newton payment transaction. |
| `credBlock` is malformed JSON or does not contain `mpincred` | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Regenerate the credential block through the approved credential flow. Do not handcraft it. |
| NPCI returns an EMI business failure, such as ineligible card, amount not eligible, MCC not eligible, invalid/missing EMI id, EMI already created, or EMI already foreclosed | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseStatus":"FAILURE","gatewayResponseCode":"CP","gatewayResponseMessage":"Amount not eligible for EMI conversion","gatewayTransactionId":"SELEMI000000000000000011","merchantId":"MERCHANT123","merchantChannelId":"CHANNEL123","merchantCustomerId":"CUST12345"}}` | Treat as a completed business decline. Do not retry unchanged unless the customer changes amount/account/context. |
| NPCI immediate error returns a mapped error code rather than timing out | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseStatus":"FAILURE","gatewayResponseCode":"U09","gatewayResponseMessage":"NPCI service is not reachable at the moment (U09)","gatewayTransactionId":"SELEMI000000000000000011","merchantId":"MERCHANT123","merchantChannelId":"CHANNEL123","merchantCustomerId":"CUST12345"}}` | Retry only if the code is known to be transient for your integration; otherwise reconcile or fail the EMI selection. |
| NPCI timeout in the select flow returns no final EMI id | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseStatus":"FAILURE","gatewayResponseCode":"00","gatewayResponseMessage":"Your EMI operation is successfully applied.","gatewayTransactionId":"SELEMI000000000000000012","merchantId":"MERCHANT123","merchantChannelId":"CHANNEL123","merchantCustomerId":"CUST12345"}}` | Treat as ambiguous/pending. Call `emiStatus` before retrying `selectEmi`. |
| NPCI returns an unexpected result value | `{"status":"FAILURE","responseCode":"INVALID_NPCI_RESULT","responseMessage":"Unexpected result from NPCI in RespEmi: PENDING_REVIEW"}` | Treat as technical failure and escalate with `upiRequestId`. |
| Decode failure, missing async response, database/cache/encryption failure, or other unexpected server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry transiently with backoff only when no downstream select outcome is possible; otherwise reconcile using `emiStatus`. |

## Retry, Idempotency, and Client Handling

`selectEmi` does not use a separate `merchantRequestId` idempotency key. The request `upiRequestId` is the transaction id sent to NPCI and returned as `gatewayTransactionId`.

Recommended handling:

- Generate a unique `upiRequestId` for each logical EMI selection or foreclosure and store it with the merchant order/customer/account context.
- Do not reuse a successful `upiRequestId` for a different amount, account, customer, payee, MCC, selected offer, or `emiTxnType`.
- Treat top-level `SUCCESS` as API processing success only. Mark EMI as applied only when the nested payload is successful and contains `emiId`.
- If the client receives no decrypted body after sending `selectEmi`, do not immediately send another selection with a new id. First call `emiStatus` with the same select `upiRequestId`.
- If `selectEmi` returns top-level `SUCCESS` but no `emiId`, call `emiStatus` before retrying. This includes nested `gatewayResponseStatus = "FAILURE"` with `gatewayResponseCode = "00"`.
- Do not retry validation, authentication, merchant-configuration, account, original-transaction, device-fingerprint, or credential-block failures without correcting the underlying data.
- Do not retry terminal business declines such as ineligible card, amount not eligible, MCC not eligible, invalid EMI id, or foreclosure not possible unless the customer changes the request context.
- Retry transient technical failures with bounded exponential backoff and jitter only when the request failed before downstream selection or after `emiStatus` confirms no selection was applied.
- Store `upiRequestId`, `originalTxnUpiRequestId`, `checkEmiUpiRequestId` where applicable, selected `emiData` or `forecloseDetails`, `gatewayResponseCode`, `gatewayResponseStatus`, and `emiId` for reconciliation.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:720)
- Server route wiring: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:329)
- Route handler and merchant signature middleware call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4155)
- Encrypted request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S response headers and response signing/encryption strategy: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:31)
- `EmiTxnType`, `EmiData`, and `ForecloseDetails` shared S2S types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1691)
- Select EMI request, validation, response, and response payload types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1847)
- S2S transformer route, merchant-customer/device/account checks: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:524)
- S2S request-to-core and core-to-response transformers: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:648)
- Credit-card EMI core flow, NPCI `ReqEmi` call, original transaction lookup, and response mapping: [src/Newton/Product/Merchant/CreditCard/Emi.hs](../../src/Newton/Product/Merchant/CreditCard/Emi.hs:35)
- Select/check/foreclose conditional validation and credit-account check: [src/Newton/Product/Merchant/CreditCard/Emi.hs](../../src/Newton/Product/Merchant/CreditCard/Emi.hs:215)
- EMI data, foreclosure, and downstream error helpers: [src/Newton/Product/Merchant/CreditCard/Helper.hs](../../src/Newton/Product/Merchant/CreditCard/Helper.hs:20)
- Product-layer core request/response types: [src/Newton/Product/Merchant/CreditCard/Types.hs](../../src/Newton/Product/Merchant/CreditCard/Types.hs:51)
- S2S request body extraction and merchant payload verification: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:70)
- Merchant signature, API allow/block, timestamp, and IP validation: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Shared request validation helpers: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- Merchant/customer/account/device lookup and device/customer checks: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:218), [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:540), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Credential block type and parsing shape: [src/Newton/Types/API/CredBlock.hs](../../src/Newton/Types/API/CredBlock.hs:47)
- Shared success/error body constants and credit-card NPCI error mappings: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:43), [src/Newton/Constants/ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:90)
