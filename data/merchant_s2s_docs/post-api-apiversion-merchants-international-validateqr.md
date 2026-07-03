# Validate QR API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/international/validateQr`

## Overview

Validate QR is a server-to-server API used in an international UPI payment journey after a customer scans an international QR and before the merchant starts the pay request.

The merchant sends the scanned QR payload, the customer/device context, and a merchant-generated UPI request id. Newton validates the request, verifies the merchant customer and bound device, sends a `ReqValQr` request to NPCI, and returns the resolved payee, QR, merchant, account, and foreign-exchange details that are available for the QR.

Use this API when your backend needs to confirm an international QR and prepare the information required for the subsequent international pay call. Do not use it as a domestic QR parser or as a transaction status API.

Payloads use the standard Newton server-to-server encrypted/signed request and response envelope shared during onboarding. The examples below show decrypted business payloads for readability.

## Business Use Case

Validate QR helps merchants:

- Validate an international QR before showing final payment details to the customer.
- Confirm the payee VPA, merchant identity, QR metadata, payee account hash/type/IFSC, and FX conversion details returned by NPCI.
- Create Newton's short-lived validation context for the later international pay request.
- Distinguish a processed API call from a gateway-level QR validation failure.
- Avoid initiating an international pay call when the QR has been rejected by NPCI or the customer/device context is invalid.

Typical sequence:

1. Customer scans an international UPI QR in the merchant app.
2. Merchant backend calls `validateQr` with the scanned `qrPayLoad`, `merchantCustomerId`, `deviceFingerPrint`, `upiRequestId`, and `initiationMode`.
3. Newton authenticates the merchant request and validates that the merchant customer and bound device match the request.
4. Newton sends NPCI `ReqValQr` with transaction type `IntlQr` and purpose `11`.
5. Newton returns `payload.gatewayResponseStatus`.
6. If `payload.gatewayResponseStatus` is `SUCCESS`, store `payload.txnId` and use the returned payment details for the later international pay request.
7. If `payload.gatewayResponseStatus` is `FAILURE`, do not proceed to pay for that QR unless the customer rescans or the failure is explicitly transient.

Important identifiers:

- `upiRequestId`: Merchant-generated request id for this validate-QR attempt. It must be 1 to 35 alphanumeric characters.
- `payload.txnId`: Newton/NPCI transaction id for the validated QR. Store and use this value for the follow-up international payment journey.
- `merchantCustomerId`: Merchant's customer identifier. Newton uses it to find the active merchant customer and bound device.
- `deviceFingerPrint`: Device fingerprint that must match the customer device registered with Newton.

## Endpoint

```http
POST /api/{apiVersion}/merchants/international/validateQr
```

The route segment is case-sensitive: use `validateQr`.

Recommended headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `x-api-version` | `2` or higher recommended for new integrations, so `purposeCode` and `initiationMode` can be returned when available. |
| `x-merchant-id` | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Merchant channel id shared during onboarding. |
| `x-timestamp` | Request timestamp used by the S2S signature flow. |
| `x-merchant-signature` | Required for plain S2S payload/signature mode. For JWS/JWE payloads, integrity is validated through the envelope. |
| `x-request-id` | Optional but recommended for tracing. Newton generates one if omitted. |
| `x-session-id` | Optional. Defaults to `x-request-id` when omitted. |
| `x-psp-encryption` | Optional response override. Supported values include `JWS` and `JWS_AND_JWE`, subject to onboarding/key configuration. |

Authentication, request signing, encryption, and response verification follow the standard Newton S2S process configured for your merchant. Depending on onboarding, the request body can be a plain signed payload, JWS, or JWS wrapped in JWE. Response bodies can be plain with `X-Response-Signature`, JWS, or JWS+JWE.

## Request

### Required Minimum

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLQR10001",
  "qrPayLoad": "upi://pay?pa=store@example&pn=Singapore%20Store&am=10.00&cu=SGD",
  "initiationMode": "12"
}
```

### Field Reference

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `merchantCustomerId` | string | Yes | No default. | Merchant customer id registered with Newton. Must be 1 to 256 characters and match Newton's merchant-customer id format. Newton uses it during merchant signature verification to load the merchant customer and customer. |
| `deviceFingerPrint` | string | Yes | No default. | Fingerprint of the customer's bound device. Must be non-empty and must match the device stored for the merchant customer. This API does not accept a fallback fingerprint. |
| `upiRequestId` | string | Yes | No default. | Merchant-generated id for this validate-QR attempt. Must be 1 to 35 alphanumeric characters. Used for tracing and to derive or supply the Newton/NPCI transaction id. |
| `qrPayLoad` | string | Yes | No default. | Scanned international QR payload. Must be non-empty. Preserve the exact QR payload string read from the QR. The field name is `qrPayLoad` with a capital `L`. |
| `initiationMode` | string | Yes | No default. | UPI initiation mode from the QR/payment context. Newton forwards it to NPCI and uses it to classify dynamic QR modes. Dynamic modes in code are `15`, `16`, `17`, `22`, `23`, and `24`; other values are treated as non-dynamic for Newton's internal validation context. |
| `networkInstitutionId` | string | No | Omitted from the NPCI institution block when not supplied. | Network institution id associated with the international QR, if available separately from the QR payload. |
| `note` | string | No | Defaults in the downstream NPCI request to `ReqValQr`. | Optional note for the validate-QR request. |
| `udfParameters` | string | No | Omitted from the response if omitted. | Merchant-defined metadata as a JSON-object string. It must parse as a JSON object and must not contain characters rejected by Newton's UDF validator. Echoed in the response when supplied. |
| `iat` | string | Conditional | No default. | Issued-at timestamp used by signed/encrypted request body flows. Required for JWS/JWE payloads because Newton validates it before processing. Plain S2S signature mode ignores this field. |

### Nested Request Objects

This request has no nested business objects. Send `udfParameters` as a JSON-object string, not as an object.

### Validation Notes

- Missing required JSON fields can be rejected before business validation because the request type requires them.
- `merchantCustomerId` must be non-empty, at most 256 characters, and match Newton's merchant-customer id regex.
- `deviceFingerPrint` and `qrPayLoad` must be non-empty.
- `upiRequestId` must be 1 to 35 alphanumeric characters.
- `udfParameters`, when supplied, must be a JSON object encoded as a string.
- `initiationMode`, `networkInstitutionId`, `note`, and `iat` are not semantically validated by the request type beyond JSON type/presence rules, but they are used by downstream authentication or NPCI request construction.

## Request Examples

### Static QR

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLQR10001",
  "qrPayLoad": "upi://pay?pa=sgstore@intl&pn=Singapore%20Store&cu=SGD",
  "initiationMode": "12",
  "udfParameters": "{\"scanId\":\"SCAN10001\"}"
}
```

### Dynamic QR With Network Institution Id

```json
{
  "merchantCustomerId": "CUST10001",
  "deviceFingerPrint": "e7a9c7f7b54a0b9f4c0e77bde7b1e3a7",
  "upiRequestId": "INTLQR10002",
  "qrPayLoad": "upi://pay?pa=sgstore@intl&pn=Singapore%20Store&am=10.00&cu=SGD&tr=INV12345",
  "initiationMode": "15",
  "networkInstitutionId": "SGNET001",
  "note": "International QR validation",
  "iat": "2026-07-02T10:15:30Z",
  "udfParameters": "{\"scanId\":\"SCAN10002\",\"invoiceId\":\"INV12345\"}"
}
```

## Response

### How To Interpret Status

There are two status layers:

- Top-level `status`, `responseCode`, and `responseMessage` describe whether Newton processed the API request wrapper and built a validate-QR response.
- `payload.gatewayResponseStatus`, `gatewayResponseCode`, and `gatewayResponseMessage` describe the QR validation result from NPCI or downstream handling.

A valid API response can therefore have top-level `status: "SUCCESS"` and `payload.gatewayResponseStatus: "FAILURE"`. Clients must check `payload.gatewayResponseStatus` before proceeding to pay.

### Response Envelope

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | API processing status. For processed validate-QR responses, this is `SUCCESS`. |
| `responseCode` | string | API processing code. For processed validate-QR responses, this is `SUCCESS`. |
| `responseMessage` | string | API processing message. For processed validate-QR responses, this is `SUCCESS`. |
| `payload` | object | Validate-QR business result. Present on processed validate-QR responses. |
| `udfParameters` | string | Echoed from the request when supplied. Omitted otherwise. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `txnId` | string | Newton/NPCI transaction id for the validate-QR result. Store this for the later international pay request. |
| `gatewayResponseStatus` | string | QR validation result, usually `SUCCESS` or `FAILURE`. Proceed only when this is `SUCCESS`. |
| `gatewayResponseCode` | string | `00` on gateway success. On gateway failure, this is the mapped NPCI/downstream error code when available. |
| `gatewayResponseMessage` | string | Human-readable message mapped from `gatewayResponseCode`, or `SUCCESS`. |
| `paymentDetails` | object | Resolved payee/QR/merchant/account/FX details. Always present as an object in the S2S payload; nested fields are omitted when unavailable or suppressed by configuration. |

### `paymentDetails`

| Field | Type | Description |
| --- | --- | --- |
| `payeeName` | string | Payee display name returned by NPCI. |
| `payeeAddr` | string | Payee VPA/address returned by NPCI. |
| `payeeCode` | string | Payee MCC or code returned by NPCI. |
| `payeeType` | string | Payee type returned by NPCI. |
| `purposeCode` | string | Purpose code returned by NPCI. Returned for `x-api-version > 0`; some PSP modes also return it on legacy version `0`. |
| `initiationMode` | string | Initiation mode returned by NPCI. Returned for `x-api-version > 1`. |
| `qr` | object | QR metadata from NPCI. Omitted on gateway failure and may be omitted by configuration. |
| `merchant` | object | International merchant metadata from NPCI. Omitted on gateway failure and may be omitted by configuration. |
| `account` | object | Payee account hash/type/IFSC details. Omitted when account details are unavailable or suppressed. The S2S response does not return the raw or encrypted account number. |
| `fxList` | array | FX quote/conversion details returned by NPCI. Omitted when NPCI does not return FX details. |

### `paymentDetails.qr`

| Field | Type | Description |
| --- | --- | --- |
| `qrPayload` | string | QR payload returned by NPCI from the institution block. |
| `countryCode` | string | Country code associated with the QR. |
| `networkInstitutionId` | string | Network institution id associated with the QR. |
| `version` | string | QR version. |
| `timestamp` | string | QR timestamp from NPCI. |
| `medium` | string | QR medium. |
| `expireTs` | string | QR expiry timestamp, when NPCI returns one. Newton currently stores it in validation context but does not reject the validate-QR call solely because this timestamp is past. |
| `query` | string | Query value from QR metadata, when supplied. |
| `verificationToken` | string | Verification token from QR metadata, when supplied. |
| `stan` | string | STAN from QR metadata, when supplied. |

### `paymentDetails.merchant`

| Field | Type | Description |
| --- | --- | --- |
| `subCode` | string | Merchant sub-code. |
| `mid` | string | International merchant id. |
| `sid` | string | Store/sub-merchant id. |
| `tid` | string | Terminal id. |
| `merchantType` | string | Merchant type returned by NPCI. |
| `genre` | string | Merchant genre/channel. |
| `onBoardingType` | string | Merchant onboarding type. |
| `registrationId` | string | Merchant registration id. |
| `pincode` | string | Merchant pincode. |
| `tier` | string | Merchant tier. |
| `location` | string | Merchant location. |
| `instCode` | string | Merchant institution code. |
| `brand` | string | Merchant brand name. |
| `legal` | string | Merchant legal name. |
| `franchise` | string | Merchant franchise name. |
| `ownershipType` | string | Ownership type. |
| `invoiceDate` | string | Invoice date, when returned. |
| `invoiceName` | string | Invoice name, when returned. |
| `invoiceNum` | string | Invoice number, when returned. |

### `paymentDetails.account`

| Field | Type | Description |
| --- | --- | --- |
| `accNumHash` | string | SHA-256 hash of the payee account number returned by NPCI. |
| `accType` | string | Payee account type. |
| `ifsc` | string | Payee account IFSC. |

### `paymentDetails.fxList[]`

| Field | Type | Description |
| --- | --- | --- |
| `baseAmount` | string | Foreign/base amount returned by NPCI. |
| `baseCurr` | string | Foreign/base currency. |
| `active` | string | Active flag/status for the FX quote. |
| `fx` | string | FX rate. |
| `mkup` | string | Markup percentage/value from NPCI. |
| `lastModifiedTs` | string | Last modified timestamp for the FX quote. |
| `convertedAmount` | string | INR/converted amount computed by Newton when `baseAmount`, `fx`, and `mkup` are parseable. Omitted if any input is missing or not parseable. |

## Response Examples

### Successful QR Validation

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "txnId": "INTLQR10002",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "paymentDetails": {
      "payeeName": "Singapore Store",
      "payeeAddr": "sgstore@intl",
      "payeeCode": "5812",
      "payeeType": "ENTITY",
      "purposeCode": "11",
      "initiationMode": "15",
      "qr": {
        "qrPayload": "upi://pay?pa=sgstore@intl&pn=Singapore%20Store&am=10.00&cu=SGD&tr=INV12345",
        "countryCode": "SG",
        "networkInstitutionId": "SGNET001",
        "version": "01",
        "timestamp": "2026-07-02T10:15:00+08:00",
        "medium": "MOBILE",
        "expireTs": "2026-07-02T10:30:00+08:00",
        "verificationToken": "VTK123456",
        "stan": "123456"
      },
      "merchant": {
        "mid": "SGMID12345",
        "sid": "STORE001",
        "tid": "TERM001",
        "merchantType": "LARGE",
        "genre": "OFFLINE",
        "onBoardingType": "BANK",
        "registrationId": "REG12345",
        "location": "Singapore",
        "instCode": "SGNET001",
        "brand": "Singapore Store",
        "legal": "Singapore Store Pte Ltd"
      },
      "account": {
        "accNumHash": "4a44dc15364204a80fe80e9039455cc1608281820fe2b24f1e5233ade6af1dd5",
        "accType": "SAVINGS",
        "ifsc": "DBSS0IN0811"
      },
      "fxList": [
        {
          "baseAmount": "10.00",
          "baseCurr": "SGD",
          "active": "Y",
          "fx": "61.25",
          "mkup": "2.00",
          "lastModifiedTs": "2026-07-02T10:10:00+08:00",
          "convertedAmount": "624.75"
        }
      ]
    }
  },
  "udfParameters": "{\"scanId\":\"SCAN10002\",\"invoiceId\":\"INV12345\"}"
}
```

### Successful API Call With QR Rejected By Gateway

In this case the top-level API status is `SUCCESS`, but the QR must not be used for payment because `payload.gatewayResponseStatus` is `FAILURE`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "txnId": "INTLQR10003",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U17",
    "gatewayResponseMessage": "Bank is unreachable. Please try after sometime!",
    "paymentDetails": {}
  }
}
```

### Processed Response With Details Suppressed

Some deployments suppress QR, merchant, or account blocks while still returning core payee and FX details. Missing optional fields are omitted, not returned as `null`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "txnId": "INTLQR10004",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "SUCCESS",
    "paymentDetails": {
      "payeeName": "Singapore Store",
      "payeeAddr": "sgstore@intl",
      "payeeCode": "5812",
      "payeeType": "ENTITY",
      "purposeCode": "11",
      "initiationMode": "15",
      "fxList": [
        {
          "baseAmount": "10.00",
          "baseCurr": "SGD",
          "active": "Y",
          "fx": "61.25",
          "mkup": "2.00",
          "convertedAmount": "624.75"
        }
      ]
    }
  }
}
```

## Defaults and Omitted Field Behavior

- `note`: defaults to `ReqValQr` in the downstream NPCI request when omitted.
- `networkInstitutionId`: omitted from the NPCI institution block when not supplied.
- `udfParameters`: omitted from the response when not supplied.
- `iat`: no default. Required for JWS/JWE payloads; not used for plain S2S signature mode.
- `purposeCode`: omitted on legacy `x-api-version: 0` unless the PSP mode returns it.
- `initiationMode`: omitted from response unless `x-api-version > 1`.
- `qr`, `merchant`, `account`, and `fxList`: omitted when NPCI does not return them, when validation fails, or when Newton configuration suppresses them.
- `paymentDetails`: remains present as an object in processed S2S responses. On gateway failure it can be `{}`.

Successful validation stores Newton's international QR context under the returned transaction id for a configured TTL. The default `INTERNATIONAL_QR_DEFAULT_EXPIRY_SEC` is `86400` seconds unless changed for the environment. The follow-up international pay call can fail if the stored validation context is missing or expired.

## Retry and Client Handling

- Treat `payload.txnId` as the value to store for the follow-up international payment.
- Proceed to international pay only when top-level `status` is `SUCCESS` and `payload.gatewayResponseStatus` is `SUCCESS`.
- Do not retry validation failures such as invalid fields, invalid device fingerprint, API not enabled, or merchant/customer lookup failures without changing the request or configuration.
- Retry transient downstream failures such as `SERVICE_UNAVAILABLE_NPCI_NA`, `SERVICE_UNAVAILABLE_NPCI_U09`, HTTP 5xx, or network timeouts with bounded exponential backoff.
- If the client did not receive any response, retry the same logical request with the same `upiRequestId` and same QR payload where possible. This endpoint does not implement a separate merchant idempotency key.
- If the customer rescans a QR, starts a fresh checkout, or scans a different QR, generate a new `upiRequestId`.
- Do not repeatedly call `validateQr` after receiving a gateway business failure unless the failure is transient and the customer is still in the same scan/payment attempt.

## Error Handling

Failure responses use the same S2S response transport configured for the merchant. The examples below show decrypted bodies.

### Request Validation Failures

Validation failures usually return a Newton error response body with `status: "FAILURE"`. HTTP status can vary by validation layer; parse the decrypted body whenever one is present.

Empty `qrPayLoad`:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "LengthValidation \"qrPayLoad field is empty\""
}
```

Invalid `upiRequestId` characters:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\""
}
```

Invalid `merchantCustomerId` format:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"merchantCustomerId is not alphanumeric\""
}
```

Invalid `udfParameters` string:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "UnexpectedType \"JSON Text parse failed for udfParameters\""
}
```

### Auth, Signature, and Encryption Failures

Missing merchant headers, missing signature material, signature mismatch, invalid JWS signature, invalid JWE decryption, IP whitelist failure, or timestamp failure can stop the request before validate-QR business logic runs.

Example unauthorized body:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

Example auth-failure body:

```json
{
  "status": "FAILURE",
  "responseCode": "AUTH_FAILURE",
  "responseMessage": "AUTH_FAILURE"
}
```

Signed/encrypted payload missing `iat`:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid IAT is empty"
}
```

### Merchant Configuration Failures

If the API is blocked for the merchant, or an allow-list exists and does not include `validateInternationalQrS2S`, Newton rejects the call before product logic.

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

If the UPI international feature is disabled in the environment, the current product code returns an internal error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Merchant Customer, Customer, and Device Failures

If `merchantCustomerId` does not resolve to an active customer for the merchant, or the customer/device binding is incomplete, Newton returns a failure before calling NPCI. Exact messages depend on the failed lookup.

Example inactive or missing device binding:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "No active device binding for merchantCustomer"
}
```

Example missing stored device id:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Invalid DeviceId cannot be null for merchantCustomer"
}
```

Example fingerprint mismatch:

```json
{
  "status": "FAILURE",
  "responseCode": "DEVICE_FINGERPRINT_MISMATCH",
  "responseMessage": "DEVICE_FINGERPRINT_MISMATCH"
}
```

### Gateway and Business Failures

When NPCI returns a `RespValQr` with result `FAILURE`, Newton returns a processed API response with top-level `SUCCESS` and a gateway failure in `payload`.

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "txnId": "INTLQR10005",
    "gatewayResponseStatus": "FAILURE",
    "gatewayResponseCode": "U17",
    "gatewayResponseMessage": "Bank is unreachable. Please try after sometime!",
    "paymentDetails": {}
  }
}
```

When the downstream immediate failure contains NPCI error details, the same processed-response shape is used with `gatewayResponseStatus: "FAILURE"` and the mapped error code/message.

### Downstream Timeout or Service Unavailable

NPCI timeout:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_NA",
  "responseMessage": "NPCI service is not reachable at the moment (NA)"
}
```

NPCI timeout with a downstream timeout code:

```json
{
  "status": "FAILURE",
  "responseCode": "SERVICE_UNAVAILABLE_NPCI_U09",
  "responseMessage": "NPCI service is not reachable at the moment (U09)"
}
```

### Unexpected Errors

Unexpected server, database, cache, encryption, NPCI response parsing, or decode failures return an internal error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

### Related Pay-Time Failure

The validate-QR call stores validation context for the later international pay request. If that context expires or is missing by the time the pay request is made, the later payment flow can return:

```json
{
  "status": "FAILURE",
  "responseCode": "JPI03",
  "responseMessage": "International QR expired / ValidateQr request expired"
}
```

## Source References

- Route definition: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:697)
- S2S route handler: [src/Newton/App/Routes/Core.hs](../../src/Newton/App/Routes/Core.hs:4011)
- S2S API wiring: [src/Newton/App/Server.hs](../../src/Newton/App/Server.hs:325)
- S2S request, validation, response, and nested response types: [src/Newton/Types/API/ServerToServer/International.hs](../../src/Newton/Types/API/ServerToServer/International.hs:99)
- General international response types: [src/Newton/Types/UpiInternational.hs](../../src/Newton/Types/UpiInternational.hs:107)
- S2S product route and device validation: [src/Newton/Product/MerchantV2.hs](../../src/Newton/Product/MerchantV2.hs:1329)
- S2S-to-general request transformer: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:2449)
- S2S response transformer and versioned fields: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:1938)
- General validate-QR response builder: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:4583)
- NPCI `ReqValQr` product flow and response handling: [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:272)
- NPCI error handling for validate QR: [src/Newton/Product/UpiInternational.hs](../../src/Newton/Product/UpiInternational.hs:477)
- Payment details extraction from `RespValQr`: [src/Newton/Utils/Transformers/Transformer9.hs](../../src/Newton/Utils/Transformers/Transformer9.hs:4755)
- Length validation helper: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:168)
- UDF validation helper: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:275)
- Merchant customer id validation helper: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:311)
- UPI request id validation helper: [src/Newton/Validation/Common.hs](../../src/Newton/Validation/Common.hs:575)
- Validation failure response helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- S2S request/response envelope types: [src/Newton/Types/API/RequestBody.hs](../../src/Newton/Types/API/RequestBody.hs:48)
- S2S payload verification: [src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs](../../src/Newton/App/Middlewares/Authentication/MerchantPayloadVerification.hs:69)
- Merchant signature verification and API allow/block checks: [src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- S2S response signing/encryption wrapper: [src/Newton/App/Routes/RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:31)
- Response signature strategy header handling: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:5411)
- Merchant customer, customer, and device lookup helpers: [src/Newton/Utils/DB.hs](../../src/Newton/Utils/DB.hs:106)
- Device fingerprint comparison: [src/Newton/Utils/BusinessLogic/BusinessLogic.hs](../../src/Newton/Utils/BusinessLogic/BusinessLogic.hs:387)
- International QR context Redis write: [src/Newton/Utils/Redis.hs](../../src/Newton/Utils/Redis.hs:841)
- International QR TTL configuration default: [src/Newton/Config/Config.hs](../../src/Newton/Config/Config.hs:2466)
- Dynamic QR initiation-mode helper: [src/Newton/Utils/Utils.hs](../../src/Newton/Utils/Utils.hs:3893)
- Generic service-unavailable and success constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:16)
- Generic bad-request/internal-server-error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:124)
- Device fingerprint mismatch constant: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:97)
- Auth and API-not-enabled constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:250)
- International QR/pay-time error constants: [src/Newton/Constants/APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:1011)
- NPCI error-code mapping used for gateway messages: [src/Newton/Constants/ErrorCodes.hs](../../src/Newton/Constants/ErrorCodes.hs:776)
