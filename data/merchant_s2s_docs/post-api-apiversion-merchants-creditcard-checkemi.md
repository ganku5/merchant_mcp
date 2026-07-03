# Check EMI API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/creditCard/checkEmi`

## Overview

Check EMI is a Newton server-to-server API for checking credit-card EMI options before the merchant asks the customer to select or foreclose an EMI.

The merchant calls this API with a Newton-linked credit-card account, customer/device identifiers, transaction context, payer/payee details, and an EMI transaction type. Newton validates the merchant, customer, linked device, and account, then sends a `ReqEmi` check request to NPCI. Newton returns either the available EMI offers for `DURING`/`POST` conversion or foreclosure details for `FORECLOSE`.

Use this API after the customer has been onboarded, device-bound, and linked to a credit-card account in Newton. Do not use it to select an offer; call `selectEmi` after the customer chooses one of the offers returned here.

## Business Use Case

Check EMI helps merchants:

- Show eligible EMI offers for a credit-card purchase before the customer authorizes the EMI selection.
- Check whether a completed credit-card transaction is eligible for post-transaction EMI conversion.
- Check foreclosure details for an existing EMI before asking the customer to confirm foreclosure.
- Validate the credit-card account, device fingerprint, payee, MCC, and transaction context before starting the customer-facing EMI step.
- Preserve a merchant-side audit trail with `upiRequestId`, `merchantCustomerId`, and optional `udfParameters`.

Supported `emiTxnType` values:

| `emiTxnType` | Use case | Response expected |
| --- | --- | --- |
| `DURING` | EMI check during a purchase or payment journey. | EMI offer list. |
| `POST` | EMI check for a previously completed transaction. | EMI offer list. |
| `FORECLOSE` | EMI foreclosure check for an existing EMI id. | Foreclosure details. |

## Integration Flow

1. Merchant identifies the Newton `merchantCustomerId`, linked credit-card `bankAccountUniqueId`, and the active device fingerprint for the customer.
2. Merchant chooses the `emiTxnType`.
3. Merchant calls `checkEmi` with a fresh `upiRequestId` and the transaction context required for that EMI type.
4. Newton decrypts/verifies the request, checks merchant API access, validates the customer and device, resolves the linked account, and confirms that the account is a credit account.
5. Newton sends a `CHECK` `ReqEmi` request to NPCI.
6. Merchant decrypts/verifies the response.
7. If `payload.gatewayResponseStatus` is `SUCCESS`, use the returned offer or foreclosure details to continue the customer journey. If it is `FAILURE`, do not call `selectEmi` for that check.

Important identifiers:

- `upiRequestId`: Merchant-generated transaction id for this check. It is sent to NPCI and returned as `payload.gatewayTransactionId`.
- `merchantCustomerId`: Merchant's customer identifier registered with Newton. It is also used during signature verification context setup.
- `bankAccountUniqueId`: Credit-card account mapping identifier for this merchant customer.
- `foreCloseEmiId`: Existing EMI id required only for `FORECLOSE`.

## Endpoint

```http
POST /api/{apiVersion}/merchants/creditCard/checkEmi
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
| `x-request-id` | Recommended | Merchant request correlation id. Newton echoes/generates it in the response headers. |
| `x-session-id` | Recommended | Merchant session correlation id. Defaults to `x-request-id` when omitted. |

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

Responses use the corresponding configured response protection. Legacy/plain response mode includes an `X-Response-Signature` header. JWS/JWE response mode returns a signed or encrypted body instead.

## Request

### Required Minimum by Variant

`DURING` check:

```json
{
  "upiRequestId": "CHKEMI000000000000000000000001",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "DURING",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "deviceFingerPrint": "device-fingerprint-hash",
  "iat": "1783000000000"
}
```

`POST` check:

```json
{
  "upiRequestId": "CHKEMI000000000000000000000002",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "POST",
  "originalTxnUpiRequestId": "PAYTXN000000000000000000000001",
  "originalTxnAmt": "12000.00",
  "originalTxnTs": "2026-07-02T10:15:30+05:30",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "deviceFingerPrint": "device-fingerprint-hash",
  "iat": "1783000000000"
}
```

`FORECLOSE` check:

```json
{
  "upiRequestId": "CHKEMI000000000000000000000003",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "FORECLOSE",
  "originalTxnUpiRequestId": "PAYTXN000000000000000000000001",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "foreCloseEmiId": "EMI123456789",
  "deviceFingerPrint": "device-fingerprint-hash",
  "iat": "1783000000000"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `upiRequestId` | string | Yes | No default. | Merchant-generated id for this check. Must be 1 to 35 alphanumeric characters. Returned as `payload.gatewayTransactionId`. |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must match the authenticated merchant customer context. Max 256 characters. |
| `emiTxnType` | string | Yes | No default. | Allowed values: `DURING`, `POST`, `FORECLOSE`. |
| `originalTxnUpiRequestId` | string | Conditional | Omit only for `DURING`. | Required for `POST` and `FORECLOSE`. Identifies the original payment/transaction for the EMI check. |
| `originalTxnAmt` | string | Yes | No default. | Original/current transaction amount sent to NPCI as the EMI amount context. Required for all check variants. |
| `originalTxnTs` | string | Conditional | Omit for `DURING`. Optional for `FORECLOSE`; forwarded if supplied. | Required for `POST`. Original transaction timestamp sent as `orgTxnDate`. |
| `payerVpa` | string | Yes | No client-facing default. | Customer/payer VPA. Must be a valid VPA. |
| `bankAccountUniqueId` | string | Yes | No default. | Linked credit-card account mapping for the merchant customer. Must resolve to an active `CREDIT` account. |
| `payeeVpa` | string | Yes | No default. | Merchant/payee VPA. Must be a valid merchant VPA. |
| `mcc` | string | Yes | No default. | Merchant category code. Must be exactly 4 digits. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint for the bound customer device. Must match the stored fingerprint, unless `fallbackDeviceFingerPrint` matches. |
| `fallbackDeviceFingerPrint` | string | No | No default. | Alternate fingerprint accepted for device match checks. |
| `foreCloseEmiId` | string | Conditional | Omit except for `FORECLOSE`. | Required for `FORECLOSE`. Mapped to the foreclosure `emiId` sent to NPCI. |
| `remarks` | string | No | If omitted, Newton sends `ReqEmi` as the NPCI note. | Customer/merchant-facing note. Must be 1 to 255 characters when supplied. |
| `udfParameters` | string | No | Omitted from response when absent. | JSON-object string for merchant metadata. Echoed in the response when supplied. |
| `iat` | string | Conditional | Required for JWS/JWE requests. Not required for plain payload mode. | Issued-at timestamp used by S2S request freshness validation. Use 13-digit epoch milliseconds. |
| `clVersion` | string | No | No default. | Client library/version value forwarded to NPCI when supplied. |

### Conditional Rules

| `emiTxnType` | Required transaction context |
| --- | --- |
| `DURING` | `originalTxnAmt`, `payerVpa`, `payeeVpa`, `mcc`. `originalTxnUpiRequestId` and `originalTxnTs` are not required. |
| `POST` | `originalTxnUpiRequestId`, `originalTxnAmt`, `originalTxnTs`, `payerVpa`, `payeeVpa`, `mcc`. |
| `FORECLOSE` | `originalTxnUpiRequestId`, `originalTxnAmt`, `payerVpa`, `payeeVpa`, `mcc`, `foreCloseEmiId`. |

Fields used by `selectEmi`, such as `credBlock`, selected `emiData`, `checkEmiUpiRequestId`, and `userConsent`, are not part of the `checkEmi` request.

### Nested Request Objects

There are no nested request objects in `checkEmi`. `foreCloseEmiId` is a top-level field; Newton internally maps it to the foreclosure EMI id sent to NPCI.

### Validation Notes

Newton applies both request-shape validation and EMI-specific business validation:

- `upiRequestId`: 1 to 35 alphanumeric characters.
- `merchantCustomerId`: non-empty, max 256 characters, restricted character set.
- `payerVpa` and `payeeVpa`: valid VPA format, 3 to 255 characters.
- `bankAccountUniqueId`, `deviceFingerPrint`, and `clVersion`: non-empty when supplied/required.
- `mcc`: exactly 4 digits.
- `remarks`: 1 to 255 characters, letters/numbers/spaces/hyphen.
- `udfParameters`: must be a JSON-object string and must pass text character validation.
- `bankAccountUniqueId` must map to an active account for the merchant customer.
- The resolved account must be a credit-card/`CREDIT` account.
- `deviceFingerPrint` or `fallbackDeviceFingerPrint` must match the bound customer's stored device fingerprint.
- The API must be enabled for the merchant; blocked or unallowed API configuration fails before product logic.

## Request Examples

### During-Purchase EMI Offer Check

```json
{
  "upiRequestId": "CHKEMI000000000000000000000001",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "DURING",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "deviceFingerPrint": "device-fingerprint-hash",
  "fallbackDeviceFingerPrint": "previous-device-fingerprint-hash",
  "remarks": "EMI options for order ORDER12345",
  "udfParameters": "{\"orderId\":\"ORDER12345\",\"cartId\":\"CART987\"}",
  "iat": "1783000000000",
  "clVersion": "2.0"
}
```

### Post-Transaction EMI Offer Check

```json
{
  "upiRequestId": "CHKEMI000000000000000000000002",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "POST",
  "originalTxnUpiRequestId": "PAYTXN000000000000000000000001",
  "originalTxnAmt": "12000.00",
  "originalTxnTs": "2026-07-02T10:15:30+05:30",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "deviceFingerPrint": "device-fingerprint-hash",
  "remarks": "Post transaction EMI check",
  "udfParameters": "{\"orderId\":\"ORDER12345\"}",
  "iat": "1783000000000"
}
```

### Foreclosure Check

```json
{
  "upiRequestId": "CHKEMI000000000000000000000003",
  "merchantCustomerId": "CUST12345",
  "emiTxnType": "FORECLOSE",
  "originalTxnUpiRequestId": "PAYTXN000000000000000000000001",
  "originalTxnAmt": "12000.00",
  "payerVpa": "customer@bank",
  "bankAccountUniqueId": "ACC_HASH_CC_001",
  "payeeVpa": "merchant@bank",
  "mcc": "5411",
  "foreCloseEmiId": "EMI123456789",
  "deviceFingerPrint": "device-fingerprint-hash",
  "remarks": "Foreclosure quote",
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
| `payload` | object | Check EMI result. |
| `udfParameters` | string | Echoed from request when supplied. Omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `gatewayResponseStatus` | string | Downstream EMI result status, usually `SUCCESS` or `FAILURE`. Use this field, not only top-level `status`, to decide the EMI outcome. |
| `gatewayResponseCode` | string | NPCI/downstream response code. Defaults to `00` only when no downstream code is available. |
| `gatewayResponseMessage` | string | `Your Check EMI call is successful.` when `gatewayResponseCode` is `00`; otherwise the mapped downstream message. |
| `gatewayTransactionId` | string | Same value as request `upiRequestId`. Use it to correlate this check with any following `selectEmi` call. |
| `merchantId` | string | Merchant id configured with Newton. |
| `merchantChannelId` | string | Merchant channel id configured with Newton. |
| `merchantCustomerId` | string | Merchant customer id supplied in the request. |
| `termsConditions` | string | Terms/conditions or reference URL returned by NPCI when available. Omitted when absent. |
| `emiLimitAmount` | string | EMI limit amount returned by NPCI when available. Omitted when absent. |
| `emiOfferList` | array | EMI offers returned for `DURING` or `POST` checks. Omitted for `FORECLOSE` and failure responses. Clients should tolerate null entries because the response type permits them. |
| `forecloseDetails` | object | Foreclosure quote/details returned for `FORECLOSE`. Omitted for `DURING`, `POST`, and failure responses. |

### `emiOfferList[]`

| Field | Type | Description |
| --- | --- | --- |
| `seqNum` | string | Offer sequence number from NPCI. |
| `offerId` | string | Offer id to pass to `selectEmi` as part of the selected EMI data. |
| `tenure` | string | EMI tenure. |
| `amount` | string | EMI amount associated with the offer. |
| `intRatePct` | string | Interest rate percentage. |
| `intRateAmt` | string | Interest amount. |
| `totalAmt` | string | Total amount payable under the offer. |
| `discountAmt` | string | Discount amount, if any. |
| `procFee` | string | Processing fee, if any. |
| `imei` | string | Type field exists, but check EMI responses usually omit it. |

### `forecloseDetails`

| Field | Type | Description |
| --- | --- | --- |
| `emiId` | string | EMI id. |
| `forecloseAmt` | string | Foreclosure amount. |
| `penaltyAmt` | string | Penalty amount, if any. |
| `principalAmt` | string | Principal amount. |
| `intRatePct` | string | Interest rate percentage. |

### Success Response With EMI Offers

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your Check EMI call is successful.",
    "gatewayTransactionId": "CHKEMI000000000000000000000001",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "termsConditions": "https://merchant.example/emi/terms",
    "emiLimitAmount": "50000.00",
    "emiOfferList": [
      {
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
      {
        "seqNum": "2",
        "offerId": "OFFER-6M-001",
        "tenure": "6",
        "amount": "12000.00",
        "intRatePct": "14.00",
        "intRateAmt": "840.00",
        "totalAmt": "12840.00",
        "discountAmt": "0.00",
        "procFee": "199.00"
      }
    ]
  },
  "udfParameters": "{\"orderId\":\"ORDER12345\",\"cartId\":\"CART987\"}"
}
```

### Success Response With Foreclosure Details

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your Check EMI call is successful.",
    "gatewayTransactionId": "CHKEMI000000000000000000000003",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345",
    "termsConditions": "https://merchant.example/emi/foreclose-terms",
    "forecloseDetails": {
      "emiId": "EMI123456789",
      "forecloseAmt": "8120.00",
      "penaltyAmt": "120.00",
      "principalAmt": "8000.00",
      "intRatePct": "12.00"
    }
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
    "gatewayTransactionId": "CHKEMI000000000000000000000001",
    "merchantId": "MERCHANT123",
    "merchantChannelId": "CHANNEL123",
    "merchantCustomerId": "CUST12345"
  }
}
```

## Response Interpretation

- Treat top-level `status = "FAILURE"` as a Newton/API failure. The check was not completed successfully.
- Treat top-level `status = "SUCCESS"` with `payload.gatewayResponseStatus = "SUCCESS"` as a successful EMI check.
- Treat top-level `status = "SUCCESS"` with `payload.gatewayResponseStatus = "FAILURE"` as a completed check with a downstream/business decline. Do not call `selectEmi` from that response.
- For `DURING` and `POST`, show `emiOfferList` to the customer and pass the selected offer details to `selectEmi`.
- For `FORECLOSE`, show `forecloseDetails` to the customer and continue only after customer confirmation.
- Optional fields are omitted, not returned as `null`, when their Haskell `Maybe` value is absent.

## Error Handling

Failure responses use the same S2S response protection as success responses. The examples below show decrypted response bodies. When `payload` is empty, it is omitted.

Depending on where validation fails, the HTTP status can be `200`, `400`, `401`, or `500`; clients should read `status`, `responseCode`, and `responseMessage` from the decrypted body.

### Failure Scenarios

| Scenario | Example decrypted response body | Client handling |
| --- | --- | --- |
| Request field validation fails, such as empty `bankAccountUniqueId`, invalid `upiRequestId`, invalid VPA, invalid MCC, invalid remarks, or invalid `udfParameters` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"LengthValidation \"bankAccountUniqueId field is empty\""}` | Fix the request. Do not retry unchanged. |
| `emiTxnType` is invalid or cannot be parsed | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"EnumValidation \"Enum match failed \\\"INSTALLMENT\\\"\""}` | Send only `DURING`, `POST`, or `FORECLOSE`. |
| Missing conditional fields for `POST` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Original-Txn-Id is required in case of POST-CHECK; Original-Txn-Timestamp is required in case of POST-CHECK"}` | Add the original transaction id and timestamp. |
| Missing `foreCloseEmiId` for `FORECLOSE` | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Foreclose-Emi-Id is required in case of FORECLOSE-CHECK"}` | Add the EMI id to be foreclosed. |
| Missing or stale `iat`/`x-timestamp` for signed/encrypted requests | `{"status":"FAILURE","responseCode":"REQUEST_EXPIRED","responseMessage":"REQUEST_EXPIRED"}` | Regenerate the timestamp, signature/envelope, and request. |
| Timestamp is not a 13-digit epoch millisecond value | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Timestamp must be a 13-digit number"}` | Fix timestamp generation. |
| JWS verification, JWE decryption, missing key id/private key, or malformed protected payload fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Check keys, `kid`, encryption mode, body canonicalization, and onboarding configuration. |
| Legacy/plain signature headers are missing or signature verification fails | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Recompute signature over the exact request body and timestamp. |
| Merchant configuration blocks or does not allow `checkEmiS2S` | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"API NOT ENABLED"}` | Enable the API for the merchant/channel before retrying. |
| Merchant IP allowlist rejects the request | `{"status":"FAILURE","responseCode":"UNAUTHORIZED","responseMessage":"UNAUTHORIZED"}` | Call from an allowlisted IP or update merchant configuration. |
| `merchantCustomerId` does not match the authenticated merchant customer context | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid merchantCustomerId"}` | Use the customer id registered under the same merchant/channel. |
| Device id is missing on the merchant customer record or device lookup fails | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Invalid DeviceId cannot be null for merchantCustomer"}` or `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Re-bind/recover the customer device before retrying. |
| Device fingerprint does not match the bound device | `{"status":"FAILURE","responseCode":"DEVICE_FINGERPRINT_MISMATCH","responseMessage":"DEVICE_FINGERPRINT_MISMATCH"}` | Send the active device fingerprint or fallback fingerprint. |
| `bankAccountUniqueId` is not linked to the merchant customer or account lookup fails | `{"status":"FAILURE","responseCode":"INVALID_DATA","responseMessage":"Account not found"}` | Refresh linked accounts and use the credit-card account mapping returned by Newton. |
| Linked account is not a credit-card account | `{"status":"FAILURE","responseCode":"BAD_REQUEST","responseMessage":"Account type should be CREDIT"}` | Use a linked credit-card account. |
| NPCI returns an EMI business failure, such as ineligible card, amount not eligible, MCC not eligible, invalid/missing EMI id, or foreclosure not possible | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseStatus":"FAILURE","gatewayResponseCode":"CP","gatewayResponseMessage":"Amount not eligible for EMI conversion","gatewayTransactionId":"CHKEMI000000000000000000000001","merchantId":"MERCHANT123","merchantChannelId":"CHANNEL123","merchantCustomerId":"CUST12345"}}` | Treat as a completed business decline. Do not retry unless the customer changes amount/account/context. |
| NPCI immediate error returns a mapped error code rather than timing out | `{"status":"SUCCESS","responseCode":"SUCCESS","responseMessage":"SUCCESS","payload":{"gatewayResponseStatus":"FAILURE","gatewayResponseCode":"U09","gatewayResponseMessage":"NPCI service is not reachable at the moment (U09)","gatewayTransactionId":"CHKEMI000000000000000000000001","merchantId":"MERCHANT123","merchantChannelId":"CHANNEL123","merchantCustomerId":"CUST12345"}}` | Retry only if the code is known to be transient for your integration. |
| NPCI is unreachable or the check request times out | `{"status":"FAILURE","responseCode":"SERVICE_UNAVAILABLE_NPCI_U09","responseMessage":"NPCI service is not reachable at the moment (U09)"}` | Retry with bounded backoff if the customer is still in the journey. |
| NPCI returns an unexpected result value | `{"status":"FAILURE","responseCode":"INVALID_NPCI_RESULT","responseMessage":"Unexpected result from NPCI in RespEmi: PENDING_REVIEW"}` | Treat as technical failure and escalate with `upiRequestId`. |
| Decode failure, missing async response, database/cache/encryption failure, or other unexpected server failure | `{"status":"FAILURE","responseCode":"INTERNAL_SERVER_ERROR","responseMessage":"INTERNAL_SERVER_ERROR"}` | Retry transiently with backoff; escalate if persistent. |

## Retry, Idempotency, and Client Handling

`checkEmi` does not use a separate `merchantRequestId` idempotency key. The request `upiRequestId` is the transaction id sent to NPCI and returned as `gatewayTransactionId`.

Recommended handling:

- Generate a unique `upiRequestId` for each logical EMI check and store it with the merchant order/customer/account context.
- Do not reuse a successful `upiRequestId` for a different amount, account, customer, payee, MCC, or `emiTxnType`.
- If the client receives a decrypted response, handle it by body status. Do not retry top-level `SUCCESS` with `payload.gatewayResponseStatus = "FAILURE"` unless the customer changes the request context or the code is known to be transient.
- Retry network failures, client timeouts with no decrypted body, `SERVICE_UNAVAILABLE_NPCI_*`, and transient `INTERNAL_SERVER_ERROR` with exponential backoff and jitter.
- Because there is no explicit idempotency record for this API, repeated retries can result in another downstream `ReqEmi` attempt. Avoid rapid retry loops.
- Do not retry validation, authentication, merchant-configuration, account, or device-fingerprint failures without correcting the underlying data.
- Call `selectEmi` only after a successful `checkEmi` response with the selected `emiOfferList[]` item or confirmed `forecloseDetails`.

## Source References

- Route type: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:724)
- Route handler and auth/signature middleware call: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4137)
- S2S transformer route, customer/device/account checks: [src/Newton/Services/Transformer/ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:502)
- Request, response, `EmiTxnType`, `EmiData`, and `ForecloseDetails` types: [src/Newton/Services/Transformer/ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:1691)
- S2S request-to-core and core-to-response transformers: [src/Newton/Services/Transformer/ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:584)
- Credit-card EMI core flow, NPCI call, response mapping, conditional validation, and credit-account check: [src/Newton/Product/Merchant/CreditCard/Emi.hs](../../src/Newton/Product/Merchant/CreditCard/Emi.hs:35)
- EMI offer, foreclosure, and downstream error helpers: [src/Newton/Product/Merchant/CreditCard/Helper.hs](../../src/Newton/Product/Merchant/CreditCard/Helper.hs:37)
- S2S request body extraction and merchant payload verification: [src/Newton/Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40), [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:74)
- Merchant signature, API allow/block, timestamp, and IP validation: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Shared request validation helpers: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251), [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:125)
- Merchant/customer/account/device lookup and device/customer checks: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:218), [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- Shared error body constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:7)
