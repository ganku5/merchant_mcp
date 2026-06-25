# **JUSPAY × NIUBIZ**

TAPP Switch for Merchants in Peru

*Master Integration Guide — Transaction Flows, Payment Modes, Merchant Onboarding, Hierarchy & API Reference*

# Table of Contents

[Table of Contents	2](#heading=)

[1\. Context & Scope	3](#heading=)

[1.1 Core Participants	3](#heading=)

[1.2 Terminology Note	3](#heading=)

[2\. Merchant Types & Acceptance Channels	4](#heading=)

[2.1 Online Merchants	4](#heading=)

[2.2 Offline Merchants	4](#heading=)

[3\. Merchant Integration Models	4](#heading=)

[3.1 Integration through Niubiz	4](#heading=)

[Advantages	4](#heading=)

[Limitations	5](#heading=)

[Which Merchants Benefit	5](#heading=)

[3.2 Direct Integration with Juspay	5](#heading=)

[Advantages	5](#heading=)

[Limitations	5](#heading=)

[Which Merchants Benefit	5](#heading=)

[4\. Merchant Transaction Flows	6](#heading=)

[4.1 TAPP Intent (Push) Payment Flow — Direct Integration	6](#heading=)

[4.2 TAPP Web Collect Payment Flow — Direct Integration	6](#heading=)

[4.3 Merchant Integration through Niubiz	7](#heading=)

[A. TAPP Intent (Push) — via Niubiz	7](#heading=)

[B. TAPP Web Collect (Pull) — via Niubiz	8](#heading=)

[4.4 Static QR Payment Flow — via Niubiz	8](#heading=)

[4.5 Dynamic QR Payment Flow — via Niubiz	9](#heading=)

[Onboarding (Steps 1–3)	9](#heading=)

[Transaction Flow (Steps 4–9)	9](#heading=)

[5\. Merchant Hierarchy within Juspay	9](#heading=)

[5.1 Merchant / Sub-Merchant Model	9](#heading=)

[Illustrative Example — A Peruvian Commerce Group	10](#heading=)

[5.2 Niubiz Onboarded as a banking\_entity	10](#heading=)

[6\. Juspay API Reference	10](#heading=)

[6.1 Transaction APIs	10](#heading=)

[6.2 Callbacks (Juspay → Niubiz / Merchant)	11](#heading=)

[6.3 Merchant Management APIs (used by Niubiz as banking\_entity)	11](#heading=)

# **1\. Context & Scope**

Juspay is establishing a UPI-style real-time payments switch for merchants in Peru. This master document consolidates the integration overview and merchant-facing documentation update into a single reference for the Niubiz partnership, covering transaction flows, merchant typologies, onboarding routes, the merchant hierarchy model, and the full API/callback reference.

In the Peruvian ecosystem, the UPI-equivalent national rail is referred to as TAPP, and a Payment Service Provider (PSP) is referred to as a PAC. Juspay operates as the Payee PAC (the merchant-side PSP) and exposes the Merchant Stack APIs that power acquiring. The central national switch is operated by BCRP, which performs routing, debit/credit processing, and DPI (Digital Payment Identifier) validation across the network.

##  1.1 Core Participants

| Participant | Role in the Integration |
| :---- | :---- |
| Merchant | Peruvian merchants accepting payments may integrate directly with Juspay, or be onboarded and served through Niubiz. |
| Niubiz | The Aggregator/Bank equivalent. Integrates with Juspay's PAC, manages merchant onboarding and integration, receives transaction callbacks, and relays them to the appropriate merchant. |
| Juspay Payee PAC | The Payee PAC exposes the Merchant Stack APIs, validates and processes transactions on the rail, and emits callbacks. |
| TAPP & BCRP | The Peruvian UPI-equivalent rail and central switch (BCRP) that routes transactions, performs DPI validation, and confirms debit/credit between Payer PAC and Payee PAC. |
| Payer (Payer PAC \+ TPAP) | The paying customer's TAPP-powered application (TPAP) and their PAC, which authorises and submits the payment. |

##    

##    1.2 Terminology Note

The Merchant Stack API field names retain UPI / India-origin conventions (for example VPA, IFSC, MCC, NPCI). These map to Peru-equivalent terms used in merchant-facing documentation as follows:

| Indian Terminology | Peru Equivalent |
| :---- | :---- |
| UPI | TAPP — the national real-time payments rail |
| PSP | PAC — Payment Service Provider |
| NPCI \- UPI Switch | TAPP Central Switch (BCRP) |
| VPA | DPI — Digital Payment Identifier (handle-based payment address) |
| IFSC | Branch identifier similar to BIC |
| MCC | Merchant Category Code |

#  

# 

# 

# 

# 

# 

# 

# 

# 

# 

# 2\. Merchant Types & Acceptance Channels

Merchants on the TAPP network fall into two broad categories, each with integration and acceptance patterns.

##  2.1 Online Merchants

An online merchant sells goods or services through a website, online platform, or mobile application and accepts digital payments. Examples include platforms such as Temu, Ripley, and Saga Falabella, where customers browse and purchase products and pay using TAPP-powered payment applications (TPAPs).   
\**A brick & mortar store which has a POS machine connected to the internet is also considered an online merchant*

Online merchants typically integrate TAPP into checkout flows using one of three methods:

* TAPP Intent — the merchant app automatically opens the user's preferred TPAP with the exact amount pre-filled; the user authorises by entering their TAPP PIN.

* Collect Request — the user enters their DPI on the website; the merchant sends a payment request notification to the user's TPAP app, where the user authorises with their TAPP PIN.

* Dynamic QR Code — the website generates a one-time, amount-specific QR code; the user scans it with a TPAP and authorises with their TAPP PIN.

## 2.2 Offline Merchants

An offline merchant sells goods or services through a physical store, outlet, or in-person setup and accepts TAPP payments. They don’t have devices connected to the internet. Examples in Peru can include local neighbourhood stores.

Offline merchants generally a static QR for their payments collection:

* Static QR Code — a printed sticker at the counter. The customer scans it in a TPAP app, manually enters the amount and TAPP PIN, and the merchant acknowledges the transaction via a soundbox notification.

# 3\. Merchant Integration Models

Merchants can integrate with the Juspay-Niubiz ecosystem in two ways to accept TAPP payments: through Niubiz, or directly with Juspay. The choice depends on transaction volume, technical capability, and feature requirements.

##  3.1 Integration through Niubiz

The merchant integrates with Niubiz for payment processing. Niubiz, in turn, invokes the relevant Juspay APIs and is responsible for communicating transaction status and completion updates back to the merchant. Niubiz is the single point of contact for its merchants.

###  Advantages

* Simplified tech effort across products — the merchant integrates and maintains a single set of Niubiz APIs/SDKs, reducing development time and engineering overhead.

* Lower maintenance — underlying changes to Juspay APIs are handled by Niubiz, shielding the merchant from ongoing technical updates.

### Limitations

* Reduced feature control — the merchant can only use the Juspay features and workflows that Niubiz chooses to expose.

* Increased latency & dependency — transaction status passes Juspay → Niubiz → Merchant, introducing an extra hop; downtime or lag at Niubiz directly affects the merchant even if Juspay is operating normally.

### Which Merchants Benefit

Large local retailers & supermarkets 

These businesses run large physical operations alongside growing e-commerce platforms. Because Niubiz dominates the physical POS terminal market in Peru, the Niubiz-managed integration lets these conglomerates unify TAPP acceptance across their POS estate.

Traditional mid/small-sized local businesses (brick-and-mortar going digital) 

These merchants need standard digital payment capability (a dynamic QR or a simple mobile checkout link) but lack the engineering capacity to build and maintain independent payment integrations.

## 3.2 Direct Integration with Juspay

The merchant integrates directly with Juspay and invokes Juspay APIs for payment processing and transaction management.

### Advantages

* Full access to advanced features — including advanced routing and the complete Juspay capability suite.

* Optimised performance & speed — direct API communication reduces network hops, leading to faster processing and better success rates.

### Limitations

* High engineering overhead — requires a more complex development phase and a dedicated technical team to manage, test, and maintain the integration.

### Which Merchants Benefit

High-volume e-commerce & marketplace platforms 

Merchants processing tens of thousands of transactions daily typically prefer direct integration for faster access to new features and greater control over transaction management, and have the technical resources to manage the integration independently.

# 4\. Merchant Transaction Flows

Three primary flows are supported across the network: Intent (push), Collect (pull), and QR-based payments (Static and dynamic). In all flows except the Static QR flow, the order is registered first with Juspay, so that the PAC accepts only registered orders — avoiding 'direct-pay' transactions that arrive without order context and cause reconciliation and refund issues.

Pre-requisite: Merchant Onboarding

* Merchant Onboarding Request — the merchant approaches Niubiz to enable TAPP payment acceptance.

* Merchant Onboarding Initiation — Niubiz onboards the merchant on the Juspay PAC platform onboarding APIs or dashboard.

* Merchant Registration — Juspay PAC registers the merchant and returns merchant credentials to Niubiz for future API interactions.

### A. TAPP Intent and Dynamic QR (Push) 

* The customer chooses to pay at the merchant application; the merchant asks Niubiz to initiate the order.  
* Niubiz calls Juspay's Register Intent API, passing the order reference as merchantRequestId.  
* Juspay returns an orderId (TR) and gatewayTransactionId (TID), along with payee details.  
* Niubiz / the merchant constructs the Intent deep link or dynamic QR from the response parameters  
* The merchant presents the QR / deep link; the customer's TPAP app opens and the customer confirms payment  
* The Payer PAC submits the payment, which routes through TAPP/BCRP to Juspay (Payee PAC). Juspay allows only the registered order to pass through.  
* On credit, Juspay fires the Pay Callback (MERCHANT\_CREDITED\_VIA\_PAY) to Niubiz, which relays it to the merchant.  
* At any point Niubiz may call Transaction Status 360 for the real-time status.

### B. TAPP Web Collect (Pull)

* The customer enters their DPI at the merchant's site or app; the merchant passes the collect request to Niubiz.  
* Niubiz calls Juspay's Verify VPA 360 to confirm the DPI is valid and resolve the holder's details.  
* If valid, Niubiz calls Juspay's Web Collect 360 to raise a collect request for the amount.  
* Juspay posts the request to TAPP/BCRP, which delivers a collect notification to the Payer PAC / TPAP app.  
* The customer approves or declines within the expiry window; BCRP routes the result back to Juspay.  
* Juspay completes the transaction (if approved) and fires the Collect Callback (MERCHANT\_CREDITED\_VIA\_COLLECT) to Niubiz, which relays it to the merchant.  
* If the customer does not act within the expiry, Niubiz can poll Transaction Status 360 at intervals.

###  C. Static QR Payment Flow

In the Static QR model, a merchant gets onboarded with Niubiz to accept TAPP payments. Niubiz performs merchant onboarding with the Juspay PAC platform, generates a Static QR using the merchant's DPI, and distributes it to the merchant. Customers scan the QR with any TAPP-powered TPAP, manually enter the amount, and authorise with their TAPP PIN. Transaction confirmations are delivered to the merchant through Niubiz.

* Static QR Generation — Niubiz generates a Static QR using the merchant's DPI and shares it for display at the store, invoice, or checkout counter.  
* Customer Payment — the customer scans the Static QR; the merchant DPI is fetched automatically; the customer enters the amount and authorises via a TAPP-enabled TPAP.  
* Transaction Processing — the TPAP PSP initiates the transaction; BCRP validates and routes it to Juspay PAC, which receives the confirmation from BCRP.  
* Merchant Credit Notification — Juspay PAC triggers the Merchant\_Credited\_Via\_Pay callback to Niubiz, which processes it and informs the merchant that payment has been received.

Merchant notifications can be delivered via SMS alerts, emails or other merchant notification channels.

| Note Merchants can be onboarded either as an Individual Parent Merchant or as a Sub-Merchant under an existing Parent Merchant managed by Niubiz. |
| :---- |

###     

### 

###   

#  5\. Merchant Hierarchy within Juspay

##  5.1 Merchant / Sub-Merchant Model

Juspay supports a two-level hierarchy: a parent Merchant (aggregator-onboarded) with multiple Sub-merchants. This lets a large enterprise enable its different lines of business, franchises, or branches — online or offline — to acquire payments under one parent relationship.

Each sub-merchant carries its own identity (subMerchantId, subMerchantChannelId), payment address (DPI), MCC, and callback URLs, and is flagged as ONLINE or OFFLINE via merchantGenre. Each transacts independently and its callbacks are stamped with the sub-merchant identifiers.

Consider InRetail Perú (illustrative) as the parent merchant. It operates several lines of business, each onboarded as a sub-merchant:

| Sub-Merchant | Genre | Notes |
| :---- | :---- | :---- |
| Plaza Vea (supermarkets) | OFFLINE | Many physical stores; each store / terminal carries its own sid / tid. |
| Inkafarma (pharmacy) | OFFLINE | Pharmacy chain, own DPI and MCC. |
| Oechsle (department stores) | ONLINE \+ OFFLINE | Physical stores plus an online storefront. |
| plazavea.com.pe (e-commerce) | ONLINE | Web checkout, separate sub-merchant identity and callback URL. |

All four sub-merchants roll up to the single parent merchant identity (merchantId / merchantChannelId), enabling consolidated relationship management while keeping per-line-of-business settlement, MCC, and reporting distinct.

##        

## 5.2 Niubiz Onboarded as a banking\_entity

Niubiz is onboarded manually during stack setup as a banking\_entity in Juspay's system. This grants Niubiz access to the admin / management APIs, enabling it to programmatically manage its entire merchant estate:

* Merchant onboarding — Add Merchant API creates a new merchant (account, DPI, MCC, genre, callback URLs).

* Merchant updates — Update Merchant API enables a merchant and changes attributes such as MCC, callback URLs, and configurations.

* The same APIs can be used for adding or updating a sub-merchant.

##  6\. Juspay API Reference 

All Merchant Stack APIs are server-to-server, application/json, POST. Requests are signed (JWS — signature / payload / protected) and carry the x-merchant-id and x-merchant-channel-id headers issued at onboarding; sub-merchant-mode calls additionally carry x-sub-merchant-id and x-sub-merchant-channel-id.

## 6.1 Transaction APIs

| API | Endpoint (POST) | What It Does |
| :---- | :---- | :---- |
| Register Intent \- [Spec Link](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/transactions/register-intent) | /merchants/transactions/registerIntent | Registers an order before generating an Intent deep link / dynamic QR. Returns orderId (TR) and gatewayTransactionId (TID) used to build the URI, and lets the PAC reject unregistered direct-pay attempts. Also supports TPV (account-hash validation) and split settlement. |
| Verify VPA 360 \- [Spec Link](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/transactions/verify-vpa-360) | /merchants/vpas/validity360 | Validates a payer DPI and resolves the holder's name and details before a collect; also indicates whether the address belongs to a merchant. Called first in the Collect flow. |
| Web Collect 360 \-[Spec Link](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/transactions/web-collect-360)  | /merchants/transactions/webCollect360 | Sends a collect (pull) request to the payer's DPI for a given amount, with a configurable expiry. Core API of the Collect flow. |
| Transaction Status 360 \- [Spec Link](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/transactions/transaction-status-360) | /merchants/transactions/status360 | Returns the real-time status of a Pay or Collect transaction; the response mirrors the corresponding callback. Used for polling when a callback has not yet arrived or on customer drop-off. |

## 

## 6.2 Callbacks (Juspay → Niubiz / Merchant)

| Callback | Event Type | What It Does |
| :---- | :---- | :---- |
| Pay Callback \- [Spec Link](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/transactions/pay-callback) | MERCHANT\_CREDITED\_VIA\_PAY | Asynchronous notification fires when a customer pays via Intent, Dynamic, Static QR flow. Carries amount, RRN (gatewayReferenceId), payer & payee DPI, timestamps, and — where applicable — subMerchantId / subMerchantChannelId. |
| Collect Callback \- [Spec Link](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/transactions/collect-callback) | MERCHANT\_CREDITED\_VIA\_COLLECT | Asynchronous notification fired when a collect request is approved, declined, or expired. Carries the same core fields plus collect-specific data such as expiry, with a final status of SUCCESS or FAILURE. |

Relay model: For merchants integrated through Niubiz, one or more callback URLs can be configured per merchant/sub-merchant. Niubiz can also forward each callback to the appropriate merchant based on the `merchantId`/`subMerchantId` present in the payload. For directly integrated merchants, callbacks are sent directly to the Merchant App/Server through the configured callback endpoint(s).

Reference: full request / response , header specifications and api encryption strategy are documented here  \- [API-GUIDE](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/submerchants/list-specific-sub-merchant-info)