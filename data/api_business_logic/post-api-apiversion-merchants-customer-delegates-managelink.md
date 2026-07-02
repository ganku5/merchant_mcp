# Manage Delegate Link API Integration Guide

Source endpoint: `POST /api/{apiVersion}/merchants/customer/delegates/manageLink`

## Overview

Manage Delegate Link is a server-to-server API for creating and maintaining UPI delegate links between a primary customer and a secondary user.

In this guide:

- `delegator` means the primary customer who owns the UPI account or mandate.
- `delegatee` means the secondary user or device that can use the delegated relationship.
- `PARTIAL` link means a delegate relationship without a backing full-delegation mandate.
- `FULL` link means a delegate relationship backed by a UPI mandate with a configured amount limit and validity.

Use this API after the customer and device are onboarded with Newton and the relevant VPAs are available. The API covers the full lifecycle: raise a link request, approve or decline a pending request, check status, delink, update a full delegation, convert between partial and full delegation, check full-delegation usage, and mark an expired pending link.

Payloads use the standard Newton S2S encrypted or signed request and response envelope shared during onboarding. Examples below show the decrypted business payload only.

## Business Use Case

Manage Delegate Link helps merchants:

- Allow a primary user to delegate UPI activity to a secondary user or secondary device.
- Create a partial delegate link that can later be used with delegate payment APIs.
- Create a full delegate link backed by a UPI mandate, including limit, validity, mandate name, document, and relationship details.
- Let the delegatee approve or decline a pending delegate link.
- Poll or synchronize the link state when the previous action is pending.
- Revoke an existing delegate link.
- Update a full delegate mandate amount or validity.
- Convert a linked full delegation to partial, or a linked partial delegation to full.
- Check full-delegation usage for the current configured cycle.

Typical lifecycle:

1. Merchant creates or verifies both customer VPAs.
2. Merchant calls `manageLink` with `action: "LINK"` and `initiatedBy: "DELEGATOR"`.
3. If the link is pending, merchant asks the delegatee to approve or decline.
4. Merchant calls `manageLink` with `APPROVE`, `DECLINE`, or `CHECK`, or waits for the normal callback/status flow where applicable.
5. Merchant uses `delegatePay` only after the link is successfully linked.
6. Merchant calls `DELINK`, `UPDATE`, conversion, or `CHECK_BALANCE` as needed during the link lifecycle.

## Endpoint

```http
POST /api/{apiVersion}/merchants/customer/delegates/manageLink
```

Recommended headers:

| Header | Required | Description |
| --- | --- | --- |
| `Content-Type` | Yes | `application/json`. |
| `x-merchant-id` | Yes | Merchant id shared during onboarding. |
| `x-merchant-channel-id` | Yes | Merchant channel id shared during onboarding. |
| `x-timestamp` | Yes | Request timestamp used by merchant signature verification. |
| `x-merchant-signature` | Conditional | Required for unsigned S2S payloads. For JWS/JWE flows, signature validation follows the configured envelope strategy. |
| `x-request-id` | No | Merchant request trace id. Newton generates one if omitted. |
| `x-session-id` | No | Merchant session trace id. Defaults to `x-request-id` when omitted. |
| `x-forwarded-for` | Conditional | Required when the merchant has IP allow-listing configured. |
| `x-psp-encryption` | Optional | Overrides the response strategy when enabled for the merchant, for example `JWS` or `JWS_AND_JWE`. |

Path parameter:

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `apiVersion` | string | Yes | API version from the route, for example `4`. |

Authentication and encryption:

- The route first decrypts or verifies the `EncRequest`.
- For JWS/JWE requests, include `iat` in the decrypted business payload; Newton validates it as a timestamp before product logic.
- The route then performs merchant signature, timestamp, API allow-list/block-list, merchant customer lookup, and IP allow-list checks.
- Responses are signed or encrypted according to the merchant's configured response strategy. The examples below show decrypted response bodies.

## Actions

| Action | Who calls it | Use when | Main result |
| --- | --- | --- | --- |
| `LINK` | `DELEGATOR` only | Raise a new partial or full delegate link request. | Creates a `LINK_PENDING` link and sends the relevant delegate or mandate flow. |
| `APPROVE` | `DELEGATEE` | Approve a pending link request. | Moves the link to `LINKED` when successful. |
| `DECLINE` | `DELEGATEE` | Decline a pending link request. | Moves the link to `DECLINED` or keeps full-conversion state according to the flow. |
| `CHECK` | `DELEGATOR` or `DELEGATEE` | Check or synchronize the current pending link result. | Returns `SUCCESS`, `PENDING`, or `FAILURE` in `payload.gatewayResponseStatus`. |
| `DELINK` | `DELEGATOR` or `DELEGATEE` | Remove an already linked relationship. | For full links, Newton revokes the backing mandate before delegate delink sync. |
| `UPDATE` | `DELEGATOR` or `DELEGATEE` | Update a full linked mandate amount or validity. | Initiates a mandate update. Partial links are rejected. |
| `CHECK_BALANCE` | `DELEGATOR` or `DELEGATEE` | Fetch full-delegation usage for the current cycle. | Returns `amountUsed`, `currentCycleEnd`, and full-delegation limit fields when available. |
| `CONVERT_TO_PARTIAL` | `DELEGATOR` only | Convert a linked full delegate to partial. | Revokes the full mandate and syncs the delegate update. |
| `CONVERT_TO_FULL` | `DELEGATOR` only | Convert a linked partial delegate to full. | Creates a full-delegation mandate and syncs the delegate update. |
| `MARK_LINK_EXPIRED` | `DELEGATOR` only | Mark a pending or failed link expired after the configured waiting window. | Marks partial links expired directly; full links use mandate revoke/update logic. |

## Request

Business request type: `ManageDelegateLinkS2SRequest`

### Base Fields

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `action` | string enum | Yes | No default. | One of `LINK`, `DELINK`, `APPROVE`, `DECLINE`, `CHECK`, `UPDATE`, `CHECK_BALANCE`, `CONVERT_TO_PARTIAL`, `CONVERT_TO_FULL`, `MARK_LINK_EXPIRED`. |
| `delegatorVpa` | string | Yes | No default. | Primary user's VPA. Must be 3 to 255 characters and match the VPA format. |
| `delegateeVpa` | string | Yes | No default. | Secondary user's VPA. Must be 3 to 255 characters and match the VPA format. Must not equal `delegatorVpa`. |
| `deviceFingerPrint` | string | Yes | No default. | Device fingerprint for the customer/device involved in the action. Newton validates this against the stored primary or secondary device where applicable. |
| `initiatedBy` | string enum | Yes | No default. | `DELEGATOR` or `DELEGATEE`. Controls which VPA is used to find the link and which side is initiating the NPCI/mandate action. |
| `merchantCustomerId` | string | Yes | No default. | Merchant's customer identifier. Max 256 characters. Used to load the Newton merchant customer and customer records. |
| `upiRequestId` | string | Yes | No default. | Merchant/UPI request id for this action. Max 35 alphanumeric characters. For `APPROVE` and `DECLINE`, it must match the pending link request id. |
| `linkType` | string enum | Yes | No default. | `PARTIAL` or `FULL`. Must match the stored link type for non-link actions, except supported conversion flows. |
| `currency` | string | Yes | No default. | Currency for the flow. Use `INR` unless Newton has explicitly enabled another value for the merchant. |
| `merchantRequestId` | string | Yes | No default. | Merchant reference id. Max 35 characters. Allowed characters: letters, numbers, hyphen, dot, underscore. Echoed in response. |
| `delegateeName` | string | Yes | No default. | Display name of the delegatee/secondary user. Must be non-empty. |

### Optional and Conditional Fields

| Field | Type | Required | Default / omitted behavior | Description |
| --- | --- | --- | --- | --- |
| `expiry` | string | Required for `LINK` | No schema default for `LINK`; product logic rejects missing `expiry`. For full mandate creation outside `LINK`, Newton may fall back to configured `maxExpiryForLink`. | Expiry in minutes. Must be parseable as an integer and not exceed merchant delegate configuration. |
| `linkingUpiRequestId` | string | No | Generated or falls back by action. | Optional delegate-link transaction id. For partial `LINK`, it becomes the stored linked UPI request id when supplied, otherwise `upiRequestId` is used. For full `LINK`, full `DELINK`, and conversions, Newton can generate a separate id when omitted. |
| `amount` | string | Conditional | No default. | Required for full `LINK` and `CONVERT_TO_FULL`. For `UPDATE`, send `amount` or `validityEnd`. Format must be two decimals, for example `5000.00`, and greater than zero. |
| `bankAccountUniqueId` | string | Conditional | If omitted, Newton tries to infer the delegator account from the delegator VPA where possible. | Account identifier used to find the account for full delegation. Full link and conversion-to-full require an account. |
| `accountReferenceId` | string | Conditional | Same as `bankAccountUniqueId`. | Alternate account identifier for account lookup. |
| `clVersion` | string | No | Not passed when omitted. | CL version associated with credential data, if applicable. |
| `credBlock` | string | Conditional | Not passed when omitted. | Opaque credential block used for full-delegation mandate authorization when required by the flow. |
| `mandateName` | string | Conditional | No default. | Required for full `LINK` and `CONVERT_TO_FULL`. Returned from the backing mandate on success. |
| `mcc` | string | No | Not passed when omitted. | MCC. Must pass MCC validation when supplied. Delegate NPCI P2P payloads use configured P2P values internally. |
| `delegateeMobileNumber` | string | Required for `LINK` | No default. | Delegatee mobile number. Must be numeric and 12 digits. For normal delegate flow, it cannot match the delegator mobile. For IoT purpose `BH`, it must match the delegator mobile. |
| `refUrl` | string | No | Falls back to Newton/NPCI configured reference URL in response and downstream payloads. | Merchant reference URL. |
| `remarks` | string | No | Defaults to `remarks`. | Note used for link, history, mandate, and downstream request payloads. |
| `shareToPayee` | string boolean | No | Not set when omitted. | `"true"` or `"false"`. Used for full-delegation mandate creation and returned when the mandate succeeds. |
| `udfParameters` | JSON-object string | No | Omitted from response when omitted. | Merchant-defined metadata as a JSON object encoded in a string. Echoed in the top-level response and payload when supplied. |
| `validityEnd` | date string | Conditional | No default. | Required for full `LINK` and `CONVERT_TO_FULL`. For `UPDATE`, send `validityEnd` or `amount`. Use `YYYY/MM/DD`, for example `2026/09/30`; the date must be within merchant-configured full-delegation validity bounds. |
| `refCategory` | string | No | Not passed when omitted. | Reference category. Must pass ref-category validation when supplied. |
| `purpose` | string enum | No | Defaults to `59` when `linkType` is `FULL`, otherwise `87`. | Allowed values: `87`, `59`, `BH`. `BH` is the IoT payment purpose and changes mobile/document validation behavior. |
| `transactionReference` | string | No | Not passed when omitted. | Optional transaction reference used in mandate update flows. Validated with merchant request id rules. |
| `iat` | string | Conditional | No default. | Required for signed/encrypted S2S envelopes. Must be a valid timestamp according to the Newton S2S timestamp rules. |
| `location` | string | No | Not passed when omitted. | Optional location text. Must be non-empty if supplied. |
| `geocode` | string | No | Not passed when omitted. | Latitude and longitude as `lat,long`; latitude <= 90 and longitude <= 180. |
| `ip` | string | No | Not passed when omitted. | IPv4 or IPv6 address. |
| `capability` | string | No | Not passed when omitted. | Capability string, 1 to 99 characters. |
| `documentType` | string enum | Conditional | No default. | Required for full `LINK` and `CONVERT_TO_FULL`, except IoT purpose `BH`. Allowed values: `AADHAAR`, `PASSPORT`, `VOTERID`, `NREGA`, `LICENSE`. |
| `documentId` | string | Conditional | No default. | Required with `documentType` for full delegation, except IoT purpose `BH`. Must be 8 to 18 characters. |
| `relation` | string | Conditional | No default. | Required for full delegation, except IoT purpose `BH`. Also stored during conversion-to-full. |
| `secondaryDeviceId` | string | Conditional | Not passed when omitted. | Secondary device identifier for IoT delegate links. When present, Newton sends an IoT device link instead of a mobile link. |

### Action-Specific Requirements

| Action | Additional requirements and behavior |
| --- | --- |
| `LINK` with `PARTIAL` | `initiatedBy` must be `DELEGATOR`. Send `expiry` and `delegateeMobileNumber`. Newton creates or updates a pending delegate link and sends `ReqDelegateAdd`. A successful immediate response usually means the link request was raised, not that the delegatee has approved it. |
| `LINK` with `FULL` | Same as partial link, plus `amount`, `validityEnd`, `mandateName`, account details, and document/relation fields unless `purpose` is `BH`. Newton creates the delegate link and a backing UPI mandate. |
| `APPROVE` / `DECLINE` | `initiatedBy` must be `DELEGATEE`. The link must be pending, not expired, and `upiRequestId` must match the original pending link request id. |
| `CHECK` | Existing link is required. Newton checks the latest pending link history and may synchronize with NPCI or mandate status. |
| `DELINK` | Existing link must be `LINKED`. Full delink revokes the backing mandate before delegate delink sync. `linkingUpiRequestId` can be supplied as the separate delegate-link id for full delink; otherwise Newton generates one. |
| `UPDATE` | Existing link must be `LINKED` and `FULL`. Send at least one of `amount` or `validityEnd`. Partial links are rejected. |
| `CHECK_BALANCE` | Existing link must be `FULL`; partial links are rejected. Returns full-delegation usage when the backing mandate is available. |
| `CONVERT_TO_PARTIAL` | Existing link must be `LINKED` and `FULL`, with an authorization mandate present. `initiatedBy` must be `DELEGATOR`. |
| `CONVERT_TO_FULL` | Existing link must be `LINKED` and not already full. `initiatedBy` must be `DELEGATOR`. Send the same full-delegation fields required for a full `LINK`. |
| `MARK_LINK_EXPIRED` | Existing link must be `LINK_PENDING` or `FAILURE`. `initiatedBy` must be `DELEGATOR`. The configured waiting window after request expiry must have passed. |

### Nested Request Objects

This API has no JSON nested request objects. `udfParameters` is a JSON object encoded as a string, and `credBlock` is an opaque credential-block string.

## Request Examples

### Partial Link Request

```json
{
  "action": "LINK",
  "delegatorVpa": "primary.user@okbank",
  "delegateeVpa": "secondary.user@okbank",
  "deviceFingerPrint": "dfp-primary-001",
  "expiry": "30",
  "initiatedBy": "DELEGATOR",
  "merchantCustomerId": "MCUST12345",
  "upiRequestId": "DLINKREQ1234567890",
  "linkType": "PARTIAL",
  "currency": "INR",
  "merchantRequestId": "DLINK-ORDER-001",
  "delegateeName": "Secondary User",
  "delegateeMobileNumber": "919876543210",
  "remarks": "Delegate link request",
  "refUrl": "https://merchant.example/delegates/DLINK-ORDER-001",
  "udfParameters": "{\"caseId\":\"CASE-001\"}",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Full Link Request

```json
{
  "action": "LINK",
  "delegatorVpa": "primary.user@okbank",
  "delegateeVpa": "secondary.user@okbank",
  "deviceFingerPrint": "dfp-primary-001",
  "expiry": "30",
  "initiatedBy": "DELEGATOR",
  "merchantCustomerId": "MCUST12345",
  "upiRequestId": "DFULLREQ1234567890",
  "linkingUpiRequestId": "DFULLLINK1234567890",
  "linkType": "FULL",
  "amount": "5000.00",
  "bankAccountUniqueId": "BAU-987654321",
  "currency": "INR",
  "mandateName": "Family delegated payments",
  "mcc": "0000",
  "merchantRequestId": "DFULL-ORDER-001",
  "delegateeName": "Secondary User",
  "delegateeMobileNumber": "919876543210",
  "validityEnd": "2026/09/30",
  "documentType": "AADHAAR",
  "documentId": "XXXX12345678",
  "relation": "FAMILY",
  "shareToPayee": "true",
  "purpose": "59",
  "remarks": "Full delegate link request",
  "iat": "2026-07-02T10:15:30+05:30"
}
```

### Delegatee Approval

```json
{
  "action": "APPROVE",
  "delegatorVpa": "primary.user@okbank",
  "delegateeVpa": "secondary.user@okbank",
  "deviceFingerPrint": "dfp-secondary-001",
  "initiatedBy": "DELEGATEE",
  "merchantCustomerId": "MCUST12345",
  "upiRequestId": "DLINKREQ1234567890",
  "linkType": "PARTIAL",
  "currency": "INR",
  "merchantRequestId": "DLINK-APPROVE-001",
  "delegateeName": "Secondary User",
  "remarks": "Delegate approved",
  "iat": "2026-07-02T10:20:30+05:30"
}
```

### Check Pending Link

```json
{
  "action": "CHECK",
  "delegatorVpa": "primary.user@okbank",
  "delegateeVpa": "secondary.user@okbank",
  "deviceFingerPrint": "dfp-primary-001",
  "initiatedBy": "DELEGATOR",
  "merchantCustomerId": "MCUST12345",
  "upiRequestId": "DLINKREQ1234567890",
  "linkType": "PARTIAL",
  "currency": "INR",
  "merchantRequestId": "DLINK-CHECK-001",
  "delegateeName": "Secondary User",
  "iat": "2026-07-02T10:25:30+05:30"
}
```

### Full Link Update

```json
{
  "action": "UPDATE",
  "delegatorVpa": "primary.user@okbank",
  "delegateeVpa": "secondary.user@okbank",
  "deviceFingerPrint": "dfp-primary-001",
  "initiatedBy": "DELEGATOR",
  "merchantCustomerId": "MCUST12345",
  "upiRequestId": "DFULLUPD1234567890",
  "linkType": "FULL",
  "amount": "7500.00",
  "validityEnd": "2026/10/31",
  "currency": "INR",
  "merchantRequestId": "DFULL-UPDATE-001",
  "delegateeName": "Secondary User",
  "transactionReference": "DFULL-UPDATE-001",
  "remarks": "Update full delegate limit",
  "iat": "2026-07-02T10:30:30+05:30"
}
```

### Full Delink

```json
{
  "action": "DELINK",
  "delegatorVpa": "primary.user@okbank",
  "delegateeVpa": "secondary.user@okbank",
  "deviceFingerPrint": "dfp-primary-001",
  "initiatedBy": "DELEGATOR",
  "merchantCustomerId": "MCUST12345",
  "upiRequestId": "DFULLDELINK1234567890",
  "linkingUpiRequestId": "DFULLDELSYNC1234567890",
  "linkType": "FULL",
  "currency": "INR",
  "merchantRequestId": "DFULL-DELINK-001",
  "delegateeName": "Secondary User",
  "remarks": "Remove delegated access",
  "iat": "2026-07-02T10:35:30+05:30"
}
```

### Convert Partial To Full

```json
{
  "action": "CONVERT_TO_FULL",
  "delegatorVpa": "primary.user@okbank",
  "delegateeVpa": "secondary.user@okbank",
  "deviceFingerPrint": "dfp-primary-001",
  "initiatedBy": "DELEGATOR",
  "merchantCustomerId": "MCUST12345",
  "upiRequestId": "DCONVFULL1234567890",
  "linkingUpiRequestId": "DCONVFULLSYNC1234567890",
  "linkType": "FULL",
  "amount": "5000.00",
  "bankAccountUniqueId": "BAU-987654321",
  "currency": "INR",
  "mandateName": "Family delegated payments",
  "merchantRequestId": "DCONV-FULL-001",
  "delegateeName": "Secondary User",
  "validityEnd": "2026/09/30",
  "documentType": "AADHAAR",
  "documentId": "XXXX12345678",
  "relation": "FAMILY",
  "remarks": "Convert to full delegation",
  "iat": "2026-07-02T10:40:30+05:30"
}
```

## Response

Business response type: `ManageDelegateLinkS2SResponse`

### Top-Level Response

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | Transport/business wrapper status. For successful route execution this is `SUCCESS`. Do not use this alone as final link status. |
| `responseCode` | string | Wrapper response code. Success value is `SUCCESS`. |
| `responseMessage` | string | Wrapper message. Success value is `SUCCESS`. |
| `payload` | object | Action result payload. Present on successful route execution. |
| `udfParameters` | string | Echo of request `udfParameters`, omitted when not supplied. |

### Payload Fields

| Field | Type | Description |
| --- | --- | --- |
| `action` | string | Requested action. |
| `delegatorVpa` | string | Primary user's VPA from the request. |
| `delegateeVpa` | string | Secondary user's VPA from the request. |
| `deviceFingerPrint` | string | Device fingerprint from the request. |
| `merchantId` | string | Newton merchant id. |
| `merchantChannelId` | string | Newton merchant channel id. |
| `merchantCustomerId` | string | Merchant customer id from the request. |
| `merchantRequestId` | string | Merchant request id from the request. |
| `gatewayTransactionId` | string | Always the request `upiRequestId`. Use this for reconciliation of this API action. |
| `gatewayReferenceId` | string | NPCI customer reference / link reference when available. |
| `gatewayResponseCode` | string | Action response code. `00` or omitted internally maps to successful raise/completion; `01` means pending; other codes should be interpreted with `gatewayResponseStatus` and `gatewayResponseMessage`. |
| `gatewayResponseStatus` | string | Action-level status: commonly `SUCCESS`, `PENDING`, `FAILURE`, or `DECLINED`. This is the primary field for client handling. |
| `gatewayResponseMessage` | string | Human-readable action result message. |
| `linkStatus` | string | Stored link status when a link record is found: `LINK_PENDING`, `LINKED`, `DELINKED`, `DECLINED`, `EXPIRED`, or `FAILURE`. |
| `linkType` | string | Stored link type when available: `PARTIAL` or `FULL`. |
| `linkedUpiRequestId` | string | Stored delegate-link request id. This may be `linkingUpiRequestId`, `upiRequestId`, or a Newton-generated id depending on action/link type. |
| `amountUsed` | string | Full-delegation amount used in the current cycle. Returned when the mandate data and usage are available, especially for `CHECK_BALANCE`. |
| `currentCycleEnd` | string | Current full-delegation cycle end date when the backing mandate is available. |
| `limit` | string | Full-delegation mandate amount limit when the backing mandate succeeds. |
| `umn` | string | UPI mandate number for successful full delegation. |
| `validityEnd` | string | Mandate validity end date from the successful full-delegation mandate. |
| `mandateName` | string | Mandate name from the successful full-delegation mandate. |
| `shareToPayee` | string | Mandate share-to-payee value returned as `"true"` or `"false"` when available. |
| `expiry` | string | Request expiry value when present in the request. |
| `bankAccountUniqueId` | string | Account identifier echoed from request when supplied. |
| `accountReferenceId` | string | Account reference echoed from request when supplied. |
| `currency` | string | Currency from the request. |
| `mcc` | string | MCC from the request when supplied. |
| `delegateeName` | string | Delegatee name from the request. |
| `refUrl` | string | Request `refUrl` or Newton/NPCI configured default. |
| `remarks` | string | Request remarks or the default `remarks`. |
| `refCategory` | string | Request reference category when supplied. |
| `transactionReference` | string | Request transaction reference when supplied. |
| `secondaryDeviceId` | string | Request secondary device id when supplied. |
| `udfParameters` | string | Request UDF metadata when supplied. |

Fields whose values are `null` or unavailable are omitted from the JSON response.

### Success Examples

#### Link Request Raised

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "action": "LINK",
    "delegatorVpa": "primary.user@okbank",
    "delegateeVpa": "secondary.user@okbank",
    "deviceFingerPrint": "dfp-primary-001",
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "gatewayReferenceId": "123456789012",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your LINK action has been raised successfully",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "DLINKREQ1234567890",
    "initiatedBy": "DELEGATOR",
    "linkStatus": "LINK_PENDING",
    "linkType": "PARTIAL",
    "linkedUpiRequestId": "DLINKREQ1234567890",
    "merchantCustomerId": "MCUST12345",
    "currency": "INR",
    "merchantRequestId": "DLINK-ORDER-001",
    "delegateeName": "Secondary User",
    "refUrl": "https://merchant.example/delegates/DLINK-ORDER-001",
    "remarks": "Delegate link request",
    "udfParameters": "{\"caseId\":\"CASE-001\"}"
  },
  "udfParameters": "{\"caseId\":\"CASE-001\"}"
}
```

Interpretation: the API call succeeded and the link request was raised. Because `linkStatus` is `LINK_PENDING`, the merchant should wait for delegatee approval, callback/status flow, or call `CHECK`.

#### Full Link Pending

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "action": "LINK",
    "delegatorVpa": "primary.user@okbank",
    "delegateeVpa": "secondary.user@okbank",
    "deviceFingerPrint": "dfp-primary-001",
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your LINK action is in pending",
    "gatewayResponseStatus": "PENDING",
    "gatewayTransactionId": "DFULLREQ1234567890",
    "initiatedBy": "DELEGATOR",
    "linkStatus": "LINK_PENDING",
    "linkType": "FULL",
    "linkedUpiRequestId": "DFULLLINK1234567890",
    "merchantCustomerId": "MCUST12345",
    "currency": "INR",
    "merchantRequestId": "DFULL-ORDER-001",
    "delegateeName": "Secondary User",
    "refUrl": "https://merchant.example/delegates/DFULL-ORDER-001",
    "remarks": "Full delegate link request"
  }
}
```

Interpretation: the full-delegation mandate/link creation is still pending. Do not retry `LINK` immediately; call `CHECK` with the same link identifiers or wait for callback/status update.

#### Delegatee Approval Completed

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "action": "APPROVE",
    "delegatorVpa": "primary.user@okbank",
    "delegateeVpa": "secondary.user@okbank",
    "deviceFingerPrint": "dfp-secondary-001",
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "gatewayReferenceId": "123456789012",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your APPROVE action has been raised successfully",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "DLINKREQ1234567890",
    "initiatedBy": "DELEGATEE",
    "linkStatus": "LINKED",
    "linkType": "PARTIAL",
    "linkedUpiRequestId": "DLINKREQ1234567890",
    "merchantCustomerId": "MCUST12345",
    "currency": "INR",
    "merchantRequestId": "DLINK-APPROVE-001",
    "delegateeName": "Secondary User",
    "refUrl": "https://merchant.example/default",
    "remarks": "Delegate approved"
  }
}
```

#### Check Balance For Full Delegation

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "action": "CHECK_BALANCE",
    "amountUsed": "1250.00",
    "currentCycleEnd": "2026/07/31",
    "delegatorVpa": "primary.user@okbank",
    "delegateeVpa": "secondary.user@okbank",
    "deviceFingerPrint": "dfp-primary-001",
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "gatewayResponseCode": "00",
    "gatewayResponseMessage": "Your CHECK_BALANCE action has been raised successfully",
    "gatewayResponseStatus": "SUCCESS",
    "gatewayTransactionId": "DFULLBAL1234567890",
    "initiatedBy": "DELEGATOR",
    "linkStatus": "LINKED",
    "linkType": "FULL",
    "linkedUpiRequestId": "DFULLLINK1234567890",
    "limit": "5000.00",
    "merchantCustomerId": "MCUST12345",
    "umn": "HDFC123456789012",
    "currency": "INR",
    "mandateName": "Family delegated payments",
    "merchantRequestId": "DFULL-BAL-001",
    "delegateeName": "Secondary User",
    "refUrl": "https://merchant.example/default",
    "shareToPayee": "true",
    "validityEnd": "2026/09/30"
  }
}
```

## Error Handling

Failures may be returned as:

- A decrypted error body with `status: "FAILURE"` when request/auth/business validation fails.
- A successful top-level response with `payload.gatewayResponseStatus: "PENDING"` or `"FAILURE"` when the API ran but the downstream delegate or mandate action is pending or failed.
- An HTTP error status for auth, encryption, validation, or unexpected exceptions. Some validation helpers can also return an error body over HTTP 200; always parse the decrypted body.

### Format Validation Failure

Example: `amount` is not in two-decimal format.

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"amount regex match failed\""
}
```

Common format validation failures include invalid action enum, invalid VPA format, empty `deviceFingerPrint`, invalid `merchantCustomerId`, invalid `upiRequestId`, invalid `linkType`, invalid amount format, invalid MCC, invalid 12-digit mobile number, invalid boolean string for `shareToPayee`, invalid JSON-object string for `udfParameters`, invalid date, invalid purpose, invalid geocode/IP, invalid document type, or invalid document id length.

### Authentication, Encryption, And Merchant Configuration Failures

Invalid signature, invalid decryption, missing timestamp, missing merchant headers, or IP allow-list failure:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "UNAUTHORIZED"
}
```

API blocked or not allowed for the merchant:

```json
{
  "status": "FAILURE",
  "responseCode": "UNAUTHORIZED",
  "responseMessage": "API NOT ENABLED"
}
```

Encrypted payload cannot be parsed after decryption:

```json
{
  "status": "FAILURE",
  "responseCode": "INVALID_DATA",
  "responseMessage": "Error in $: expected object"
}
```

### Business Validation Failures

Same delegator and delegatee VPA:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Delegator Delegatee Vpa cannot be same"
}
```

Device fingerprint or device record failure:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Device not found for delegate flow"
}
```

Full link without an account:

```json
{
  "status": "FAILURE",
  "responseCode": "ACCOUNT_NOT_FOUND",
  "responseMessage": "Account not found"
}
```

Existing active link:

```json
{
  "status": "FAILURE",
  "responseCode": "JPAL",
  "responseMessage": "Active Linking already present"
}
```

Existing pending link still within expiry:

```json
{
  "status": "FAILURE",
  "responseCode": "JPLP",
  "responseMessage": "Previous link in pending state within expiry"
}
```

Pending full link expired but still inside the configured waiting window:

```json
{
  "status": "FAILURE",
  "responseCode": "JPEX",
  "responseMessage": "Previous request expired wait for 30 min after expiry to initiate new one"
}
```

Delegatee tries to approve a non-pending link:

```json
{
  "status": "FAILURE",
  "responseCode": "JP_DL_NP",
  "responseMessage": "Link is not in pending state"
}
```

Delegatee approval after request expiry:

```json
{
  "status": "FAILURE",
  "responseCode": "REQUEST_EXPIRED",
  "responseMessage": "REQUEST_EXPIRED"
}
```

Daily delegate-link request limit exceeded:

```json
{
  "status": "FAILURE",
  "responseCode": "JPLX",
  "responseMessage": "Daily limit exceeded for delegate linking requests to this user"
}
```

Full-link field missing:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Mandate Name must be present for FULL Linking"
}
```

Update called for a partial or pending link:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "Invalid action for linkType"
}
```

### Downstream Pending Or Failure

When NPCI or mandate processing is pending, the route can still return a top-level success with action-level pending:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "action": "LINK",
    "delegatorVpa": "primary.user@okbank",
    "delegateeVpa": "secondary.user@okbank",
    "deviceFingerPrint": "dfp-primary-001",
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "gatewayResponseCode": "01",
    "gatewayResponseMessage": "Your LINK action is in pending",
    "gatewayResponseStatus": "PENDING",
    "gatewayTransactionId": "DFULLREQ1234567890",
    "initiatedBy": "DELEGATOR",
    "linkStatus": "LINK_PENDING",
    "linkType": "FULL",
    "linkedUpiRequestId": "DFULLLINK1234567890",
    "merchantCustomerId": "MCUST12345",
    "currency": "INR",
    "merchantRequestId": "DFULL-ORDER-001",
    "delegateeName": "Secondary User",
    "refUrl": "https://merchant.example/default",
    "remarks": "Full delegate link request"
  }
}
```

Mandate or NPCI failure can also be returned in the payload:

```json
{
  "status": "SUCCESS",
  "responseCode": "SUCCESS",
  "responseMessage": "SUCCESS",
  "payload": {
    "action": "CONVERT_TO_FULL",
    "delegatorVpa": "primary.user@okbank",
    "delegateeVpa": "secondary.user@okbank",
    "deviceFingerPrint": "dfp-primary-001",
    "merchantId": "MERCHANT001",
    "merchantChannelId": "APP",
    "gatewayResponseCode": "JPCF",
    "gatewayResponseMessage": "NPCI Connection Failure",
    "gatewayResponseStatus": "FAILURE",
    "gatewayTransactionId": "DCONVFULL1234567890",
    "initiatedBy": "DELEGATOR",
    "linkStatus": "LINKED",
    "linkType": "PARTIAL",
    "linkedUpiRequestId": "DLINKREQ1234567890",
    "merchantCustomerId": "MCUST12345",
    "currency": "INR",
    "merchantRequestId": "DCONV-FULL-001",
    "delegateeName": "Secondary User",
    "refUrl": "https://merchant.example/default",
    "remarks": "Convert to full delegation"
  }
}
```

Unexpected internal errors use the common internal error body:

```json
{
  "status": "FAILURE",
  "responseCode": "INTERNAL_SERVER_ERROR",
  "responseMessage": "INTERNAL_SERVER_ERROR"
}
```

## Client Handling And Retry Guidance

- Treat `payload.gatewayResponseStatus` and `payload.linkStatus` as the action result. Top-level `status: "SUCCESS"` only means the API route completed.
- If `gatewayResponseStatus` is `PENDING` or `gatewayResponseCode` is `01`, do not replay the mutating action immediately. Call `CHECK` with the same link identifiers or wait for the configured callback/status flow.
- `merchantRequestId` is validated and echoed, but this route does not use it as a generic idempotency key. Use unique `upiRequestId` values per new mutating action.
- If a network timeout occurs and the client does not receive a decryptable response, first call `CHECK` or `listPendingLinks` before creating a new `LINK`.
- Retrying `LINK` while a link is pending can return `JPLP`. Retrying while a link is already active can return `JPAL`.
- For validation, auth, encryption, merchant configuration, and IP allow-list failures, fix the request or configuration before retrying.
- For `REQUEST_EXPIRED`, let the customer initiate a new link request only after the old pending state is resolved. For full links inside the configured post-expiry waiting window, Newton returns `JPEX`; after the window, use `MARK_LINK_EXPIRED` where appropriate.
- For `DELINK`, `UPDATE`, and conversion flows, check current link state before retrying. These actions require an existing linked relationship and may interact with mandate revoke/update downstream systems.

## Source References

- API route prefix: [Core.hs](../../src/Newton/App/Routes/Core.hs:112)
- `manageLink` route type: [Core.hs](../../src/Newton/App/Routes/Core.hs:757)
- S2S route handler and merchant signature verification: [Core.hs](../../src/Newton/App/Routes/Core.hs:5140)
- S2S request verification helper: [Utils/Routes.hs](../../src/Newton/Utils/Routes.hs:40)
- S2S response signing/encryption wrapper: [RoutesHelper.hs](../../src/Newton/App/Routes/RoutesHelper.hs:35)
- Merchant signature, timestamp, IP, and API allow-list checks: [MerchantSignatureVerificationV2.hs](../../src/Newton/App/Middlewares/Authentication/MerchantSignatureVerificationV2.hs:56)
- Request type and validators: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4348)
- Response type: [ServerToServer/Types.hs](../../src/Newton/Services/Transformer/ServerToServer/Types.hs:4449)
- S2S transformer route: [ServerToServer/Core.hs](../../src/Newton/Services/Transformer/ServerToServer/Core.hs:773)
- S2S core request/response transformers: [ServerToServer/Helper.hs](../../src/Newton/Services/Transformer/ServerToServer/Helper.hs:1432)
- Delegate actions and document types: [Delegates/Types.hs](../../src/Newton/Product/Merchant/Delegates/Types.hs:389)
- Core delegate response payload: [Delegates/Types.hs](../../src/Newton/Product/Merchant/Delegates/Types.hs:475)
- Product action dispatcher and default remarks: [ManageLink.hs](../../src/Newton/Product/Merchant/Delegates/ManageLink.hs:55)
- Product business validations: [ManageLink.hs](../../src/Newton/Product/Merchant/Delegates/ManageLink.hs:120)
- Link expiry validation and pending-window handling: [ManageLink.hs](../../src/Newton/Product/Merchant/Delegates/ManageLink.hs:269)
- Link, delink, approve/decline, update, conversion, and response construction: [ManageLink.hs](../../src/Newton/Product/Merchant/Delegates/ManageLink.hs:302)
- Delegate DB lookup path: [Delegates/DB.hs](../../src/Newton/Product/Merchant/Delegates/DB.hs:55)
- Delegate DB request transformer and mandate transformers: [Delegates/Transformer.hs](../../src/Newton/Product/Merchant/Delegates/Transformer.hs:803)
- Validation error response helper: [Utils.hs](../../src/Newton/Utils/Utils.hs:251)
- Common validation rules: [Validation/Common.hs](../../src/Newton/Validation/Common.hs:137)
- Delegate/business error constants: [APIErrorCode.hs](../../src/Newton/Constants/APIErrorCode.hs:151), [Delegate.hs](../../src/Newton/Constants/ErrorCodes/Delegate.hs:24)
