# **JUSPAY × NIUBIZ**

TAPP Switch for TPAP in Peru

*Master S2S TPAP Integration Guide — Onboarding , TPAP Registration, Account Management , Transaction Flows and TAPP Features*

Version 1.0

# Table of Contents

[Table of Contents	2](#heading=)

[**1\. Context & Scope	4**](#1.-context-&-scope)

[1.1 Core Participants	4](#heading=)

[1.2 Terminology Note	5](#heading=)

[2\. TPAP DEFINITION	6](#heading=)

[3\. S2S TPAP Onboarding	6](#heading=)

[**4.TPAP FLOWS	7**](#4.tpap-flows)

[4.1 Registration Flows	7](#heading=)

[Step 1: User Initiates TAPP Registration	7](#step-1:-user-initiates-tapp-registration)

[Step 1.1: Runtime Permission Check & Request	7](#step-1.1:-runtime-permission-check-&-request)

[Step 2: TPAP Requests SMS Token	7](#step-2:-tpap-requests-sms-token)

[Step 3: Juspay PAC Returns SMS Details	7](#step-3:-juspay-pac-returns-sms-details)

[Step 4: TPAP Triggers SMS from User Device	7](#step-4:-tpap-triggers-sms-from-user-device)

[Step 5: VMN Aggregator Sends Inbound Notification	8](#step-5:-vmn-aggregator-sends-inbound-notification)

[Step 6: TPAP Polls bindDevice API	8](#step-6:-tpap-polls-binddevice-api)

[Step 7: bindDevice Response	8](#step-7:-binddevice-response)

[4.2 BCRP Token Generation and Renewal](#4.2-bcrp-token-generation-and-renewal-after-successful-user-registration,-the-tpap-mobile-application-must-obtain-and-securely-store-a-valid-bcrp-token.-this-token-is-mandatory-for-interactions-with-the-common-library.) 

[After successful user registration, the TPAP mobile application must obtain and securely store a valid BCRP token. This token is mandatory for interactions with the Common Library.	8](#4.2-bcrp-token-generation-and-renewal-after-successful-user-registration,-the-tpap-mobile-application-must-obtain-and-securely-store-a-valid-bcrp-token.-this-token-is-mandatory-for-interactions-with-the-common-library.)

[Step 1: Generate a Fresh Challenge	9](#step-1:-generate-a-fresh-challenge)

[Step 2: Request Token Rotation	9](#step-2:-request-token-rotation)

[4.2 Account Management Flows](#4.2-account-management-flows-account-linking)

[Account Linking	10](#4.2-account-management-flows-account-linking)

[Step 1: User Initiates Bank Account Addition	10](#step-1:-user-initiates-bank-account-addition)

[Step 2: TPAP Server Calls FetchAccount API	10](#step-2:-tpap-server-calls-fetchaccount-api)

[Step 3: Juspay PAC Returns Account Details and DPI Suggestions	10](#step-3:-juspay-pac-returns-account-details-and-dpi-suggestions)

[Step 4: TPAP Server Calls LinkVPAAccount API	11](#step-4:-tpap-server-calls-linkvpaaccount-api)

[Step 5: Juspay PAC Returns Success Response	11](#step-5:-juspay-pac-returns-success-response)

[MPIN FLOW	11](#heading=)

[The MPIN is used to securely authorize both financial transactions, such as fund transfers, and non-financial activities, such as balance inquiries, directly from the user's smartphone. It serves as the second authentication factor in the platform's streamlined 1-click Two-Factor Authentication (2FA) framework. In this model, the registered mobile device fingerprint acts as the first factor ("something the user has"), while the MPIN serves as the second factor ("something the user knows"), together providing a secure and seamless authentication experience.	11](#the-mpin-is-used-to-securely-authorize-both-financial-transactions,-such-as-fund-transfers,-and-non-financial-activities,-such-as-balance-inquiries,-directly-from-the-user's-smartphone.-it-serves-as-the-second-authentication-factor-in-the-platform's-streamlined-1-click-two-factor-authentication-\(2fa\)-framework.-in-this-model,-the-registered-mobile-device-fingerprint-acts-as-the-first-factor-\("something-the-user-has"\),-while-the-mpin-serves-as-the-second-factor-\("something-the-user-knows"\),-together-providing-a-secure-and-seamless-authentication-experience.)

[Step 1: Verify MPIN Status	11](#step-1:-verify-mpin-status)

[Step 2: Launch Common Library	11](#step-2:-launch-common-library)

[Step 2: Generate OTP Request	12](#step-2:-generate-otp-request)

[Step 3: OTP Delivery	12](#step-3:-otp-delivery)

[Step 4: Otp Validation and MPIN creation	12](#step-4:-otp-validation-and-mpin-creation)

[Step 5: SetMpin/Reset MPIN	12](#step-5:-setmpin/reset-mpin)

[Step 6: MPIN Setup Completion	12](#step-6:-mpin-setup-completion)

[Step 7: User Notification	12](#step-7:-user-notification)

[4.3  Transaction Flows](#4.3-transaction-flows-here-is-a-comprehensive-table-detailing-the-transaction-apis-available-in-the-juspay-tapp-consumer-stack,-along-with-their-descriptions-and-documentation-links.)

[Here is a comprehensive table detailing the Transaction APIs available in the Juspay TAPP Consumer Stack, along with their descriptions and documentation links.	14](#4.3-transaction-flows-here-is-a-comprehensive-table-detailing-the-transaction-apis-available-in-the-juspay-tapp-consumer-stack,-along-with-their-descriptions-and-documentation-links.)

[6.2 Callbacks (Juspay → Niubiz / Merchant)	16](#heading=)

# **1\. Context & Scope** {#1.-context-&-scope}

Juspay is establishing a TAPP-style real-time payments PAC switch for TPAPs  in Peru. This master document consolidates the integration overview and TPAP-facing documentation update into a single reference for the Niubiz partnership, covering transaction flows, merchant typologies, onboarding routes, the merchant hierarchy model, and the full API/callback reference.

In the Peruvian ecosystem, the TAPP-equivalent national rail is referred to as TAPP, and a Payment Service Provider (PAC) is referred to as a PAC. Juspay operates as the Payer PAC (the TPAP-side PAC) and exposes the TPAP S2S Stack APIs that power issuing. The central national switch is operated by BCRP (Banco Central de Reserva del Perú), which performs routing, debit/credit processing.

##  1.1 Core Participants

| Participant | Role in the Integration |
| :---- | :---- |
| TPAP | Peruvian TPAP enabling TAPP payments for consumers. May leverage Juspay SDK, or integrate as S2S TPAP. |
| Juspay (JUSPAY-NB PAC) | The Payer PAC (TPAP-side PAC). Exposes the Consumer Stack APIs, validates and processes transactions on the rail, and emits callbacks. |
| TAPP / BCRP | The Peruvian TAPP-equivalent rail and central switch (BCRP) that routes transactions, performs DPI validation, and confirms debit/credit between Payer PAC and Payee PAC. |
| Payee (App \+ Payee PAC / TPAP or Merchant accepting TAPP payments) | The receiving customer's TAPP-powered application (TPAP) and their PAC or Merchant receiving payments and their PAC . |

##  


##    1.2 Terminology Note

The Merchant Stack API field names retain TAPP / India-origin conventions (for example VPA, IFSC, MCC, BCRP). These map to Peru-equivalent terms used in merchant-facing documentation as follows:

| Indian Terminology | Peru Equivalent |
| :---- | :---- |
| TAPP | TAPP — the national real-time payments rail |
| PAC | PAC — Payment Service Provider |
| BCRP / TAPP Switch | TAPP Central Switch (BCRP) |
| VPA | DPI — Digital Payment Identifier (handle-based payment address) |
| IFSC | Bank / branch identifier (field retained in the API payload) |
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

# 2\. TPAP DEFINITION 

A TPAP is a mobile application that uses the TAPP network system to facilitate instant, real-time, bank-to-bank money transfers. It allows users to link multiple bank accounts into a single smartphone application and send or receive money seamlessly.

#  3\. S2S TPAP Onboarding

**Onboarding & Integration:** NIUBIZ can onboard the S2S TPAP merchant through the onboarding dashboard. Upon successful onboarding, Juspay will provide the required TPAP credentials, enabling the TPAP to securely access and invoke the Juspay S2S APIs.

**Extensive UAT Testing:** S2S TPAPs must thoroughly validate all payment, transaction, and operational workflows in the staging environment before proceeding to production deployment.

**BCRP Approval & Certification:**  After completing internal testing, the TPAP must undergo the BCRP certification process.

* For **server-to-server (S2S) APIs**, Juspay will execute and support the certification test cases required by BCRP.  
* For **UI/UX compliance**, in the case of **S2S integrations or headless SDK implementations**, the TPAP is responsible for ensuring that the application adheres to the applicable BCRP UI/UX guidelines and requirements.   
* For a **full SDK integration**, where the complete UI/UX flow is provided and managed by Juspay, Juspay will be responsible for ensuring compliance with the certification requirements and will support the TPAP through the end-to-end BCRP certification process with respect to the SDK. Anything outside the scope of SDK needs to be handled by the TPAP.

**Credential Provisioning:** Upon successful certification of the TPAP in the UAT, a valid **@handle** is assigned to the TPAP application for production go-live. The application can then use this handle for user's DPIs.

#   **4.TPAP FLOWS**  {#4.tpap-flows}

## 4.1 Registration Flows

The TAPP registration process uses an SMS-based device binding mechanism to validate that the mobile number being registered is present on the user's device. The flow involves the TPAP application, TPAP backend server, Juspay PAC, and the VMN (Virtual Mobile Number) aggregator. 

**DEVICE BINDING**

### **Step 1: User Initiates TAPP Registration** {#step-1:-user-initiates-tapp-registration}

The user launches the TAPP-powered TPAP application and begins the registration process by providing their mobile number.

#### **Step 1.1: Runtime Permission Check & Request** {#step-1.1:-runtime-permission-check-&-request}

Before communicating with the backend, the TPAP application checks for and, if necessary, requests the following runtime permissions from the user:

* **READ\_PHONE\_STATE**: Required to detect the SIM card(s), fetch the subscriber ID, and determine which slot corresponds to the user's selected mobile number.  
* **SEND\_SMS**: Required to allow the application to automatically send the outbound verification SMS.

⚠️ **Note:** If the user denies these permissions, the app must gracefully display an educational dialog explaining *why* they are mandatory for secure TAPP binding, as registration cannot proceed without them.

### **Step 2: TPAP Requests SMS Token** {#step-2:-tpap-requests-sms-token}

The TPAP backend server invokes the [**getSmsToken** API](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/get-sms-token) on the Juspay PAC platform.

### **Step 3: Juspay PAC Returns SMS Details** {#step-3:-juspay-pac-returns-sms-details}

Juspay PAC generates a unique SMS token and responds with:

* smsContent – the SMS payload to be sent  
* vmn – the Virtual Mobile Number (VMN) managed by the aggregator

### **Step 4: TPAP Triggers SMS from User Device** {#step-4:-tpap-triggers-sms-from-user-device}

Upon receiving the response, the TPAP application is responsible for initiating an SMS from the user's device.

The SMS must:

* Be sent from the SIM/mobile number being registered  
* Be sent to the VMN provided by Juspay PAC  
* Contain the exact smsContent received in the getSmsToken response

### **Step 5: VMN Aggregator Sends Inbound Notification** {#step-5:-vmn-aggregator-sends-inbound-notification}

Once the SMS reaches the VMN, the aggregator communicates with Juspay for the verification process. 

### **Step 6: TPAP Polls bindDevice API** {#step-6:-tpap-polls-binddevice-api}

Immediately after the SMS is triggered from the user device, the TPAP backend starts polling the [**bindDevice** API](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/bind-device) exposed by Juspay PAC.

### **Step 7: bindDevice Response** {#step-7:-binddevice-response}

While Juspay PAC is waiting for the inbound SMS notification or validation is incomplete, the **bindDevice** API returns: Bind device pending. Once the inbound SMS is received and all validations succeed, the **bindDevice** API returns: Bind Device Success

The successful response indicates that the device has been successfully bound and registered.

Decline Bind Device \- To be used for declining the device binding in case of an app toggle by customer before completion of bind device.

###  **4.2 BCRP Token Generation and Renewal**   After successful user registration, the TPAP mobile application must obtain and securely store a valid BCRP token. This token is mandatory for interactions with the Common Library. {#4.2-bcrp-token-generation-and-renewal-after-successful-user-registration,-the-tpap-mobile-application-must-obtain-and-securely-store-a-valid-bcrp-token.-this-token-is-mandatory-for-interactions-with-the-common-library.}

The Common Library validates the BCRP token before processing sensitive operations. Without a valid token, requests such as TAPP PIN capture, balance inquiry, payment authorization, and other secure TAPP operations will not be processed.

**Initial Token Generation**

**Step 1: Generate Challenge**

The TPAP application requests a challenge from the Common Library. This challenge is required for BCRP token generation.

**Step 2: Obtain BCRP Token**

The challenge is sent to Juspay PAC using the Get BCRP Token API with:

tokenRequestType \= INITIAL

The Juspay PAC initiates a request to the BCRP, which generates and returns a valid token. The PAC then relays this token back to the TPAP.

**Token Renewal**

BCRP tokens remain valid for 90 days from the date of issuance. To avoid disruption of services, the TPAP should renew the token before it expires.

### **Step 1: Generate a Fresh Challenge** {#step-1:-generate-a-fresh-challenge}

Prior to renewal, the TPAP application obtains a new challenge from the Common Library.

### **Step 2: Request Token Rotation** {#step-2:-request-token-rotation}

The TPAP invokes the **Get BCRP Token** API again, this time specifying:

tokenRequestType \= ROTATE

The Juspay PAC initiates a request to the BCRP, which generates and returns a valid token. The PAC then relays this token back to the TPAP.

| API Name | Description | Documentation Link |
| :---- | :---- | :---- |
| **Get SMS Token** | Starts the device binding process and returns an SMS token. | [Get SMS Token](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/get-sms-token) |
| **Bind Device** | The next step in the flow after getting the SMS token. | [Bind Device](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/bind-device) |
| **Delink Customer** | Deletes all the VPAs and accounts of the customer while preserving device binding. | [Delink Customer](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/delink-customer) |
| **Decline Device Binding** | This api is to be used for declining the device binding in case of an app toggle by customer. | [Decline Device Binding](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/decline-device-binding) |
| **Get BCRP Token** | A step in the Registration APIs flow. | [Get BCRP Token](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/get-npci-token) |
| **Deregister Customer** | A step in the Registration APIs flow. | [*Deregister Customer*](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/deregister-customer) |

## 

## 

## 

## 

## 

## **4.2 Account Management Flows**   **Account Linking** {#4.2-account-management-flows-account-linking}

The Bank Account Fetch and VPA Linking flow enables a TPAP user to link a bank account and associate it with a Virtual Payment Address (VPA/DPI). The flow involves interactions between the TPAP Server, Juspay PAC, and BCRP to retrieve account information and complete the DPI-to-account mapping.

###  **Step 1: User Initiates Bank Account Addition** {#step-1:-user-initiates-bank-account-addition}

The user navigates to the TPAP application and selects the option to add a bank account. The user chooses the bank for which account details need to be fetched.

### **Step 2: TPAP Server Calls [FetchAccount API](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/fetch-account)** {#step-2:-tpap-server-calls-fetchaccount-api}

Upon receiving the user's request, the TPAP Server invokes the FetchAccount API on Juspay PAC to retrieve bank account details associated with the selected bank for the user.

### **Step 3: Juspay PAC Returns Account Details and DPI Suggestions** {#step-3:-juspay-pac-returns-account-details-and-dpi-suggestions}

Juspay PAC relays the account information received from BCRP back to the TPAP Server through the FetchAccount API response.

The response contains:

* Bank Account Unique ID (BUID)  
* Account details  
* Suggested VPA (DPI) options that can be linked to the account

### **Step 4: TPAP Server Calls [LinkVPAAccount API](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/link-vpa-account)** {#step-4:-tpap-server-calls-linkvpaaccount-api}

The TPAP application allows the user to select one of the suggested VPA (DPI) values.

Based on the user's selection, the TPAP Server invokes the LinkVPAAccount API on Juspay PAC to link the selected VPA to the chosen bank account.

### **Step 5: Juspay PAC Returns Success Response** {#step-5:-juspay-pac-returns-success-response}

Juspay PAC validates the request and creates the mapping between the DPI and the bank account.

A successful LinkVPAAccount Response is returned to the TPAP Server, confirming that the DPI has been linked successfully.

## 

## **MPIN FLOW**

## The MPIN is used to securely authorize both financial transactions, such as fund transfers, and non-financial activities, such as balance inquiries, directly from the user's smartphone. It serves as the second authentication factor in the platform's streamlined 1-click Two-Factor Authentication (2FA) framework. In this model, the registered mobile device fingerprint acts as the first factor ("something the user has"), while the MPIN serves as the second factor ("something the user knows"), together providing a secure and seamless authentication experience. {#the-mpin-is-used-to-securely-authorize-both-financial-transactions,-such-as-fund-transfers,-and-non-financial-activities,-such-as-balance-inquiries,-directly-from-the-user's-smartphone.-it-serves-as-the-second-authentication-factor-in-the-platform's-streamlined-1-click-two-factor-authentication-(2fa)-framework.-in-this-model,-the-registered-mobile-device-fingerprint-acts-as-the-first-factor-("something-the-user-has"),-while-the-mpin-serves-as-the-second-factor-("something-the-user-knows"),-together-providing-a-secure-and-seamless-authentication-experience.}

### **Step 1: Verify MPIN Status** {#step-1:-verify-mpin-status}

After account linking, TPAP checks the MPIN status received in the FetchAccount response.  
If MPIN is not configured for the selected bank account, TPAP enables the Set MPIN journey.

### **Step 2: Launch Common Library** {#step-2:-launch-common-library}

The Common Library (CL) screen is launched. The user enters:

* Last 6 digits of the debit card  
* Expiry  
* ATM pin

The Common Library securely captures these credentials and generates an encrypted CredBlock.

### **Step 2: [Generate OTP](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/generate-otp) Request** {#step-2:-generate-otp-request}

The TPAP Server sends a Generate OTP request to Juspay PAC.

### **Step 3: OTP Delivery** {#step-3:-otp-delivery}

The user's bank sends an OTP directly to the user's registered mobile number.

### **Step 4: Otp Validation and MPIN creation** {#step-4:-otp-validation-and-mpin-creation}

The TPAP has to invoke CL where the user will be prompted to give OTP and New MPIN as input. 

###  **Step 5: [SetMpin/Reset MPIN](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/setreset-mpin)**  {#step-5:-setmpin/reset-mpin}

The TPAP should initiate the setMpin api with the credblock received in the previous step

### **Step 6: MPIN Setup Completion** {#step-6:-mpin-setup-completion}

If all validations are successful, the bank stores the MPIN and returns a success response.

### **Step 7: User Notification** {#step-7:-user-notification}

TPAP displays a confirmation message indicating that MPIN setup has been completed successfully.

The user can now perform MPIN-protected operations such as:

* Balance Inquiry  
* Payment Authorization  
* TAPP Transactions  
* Other secure TAPP operations


## 

## 

| API Name | Description | Documentation Link |
| :---- | :---- | :---- |
| Fetch Accounts | Fetches the list of bank accounts associated with the customer's mobile number directly from the switch/BCRP. | [Fetch Accounts](https://www.google.com/search?q=https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/fetch-accounts) |
| Is VPA Available | Checks if a specific Virtual Payment Address (VPA) handle requested by the user is available for creation. | [Is VPA Available](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/is-vpa-available) |
| Add VPA | Creates a new Virtual Payment Address (VPA) or TAPP handle for the customer. | [Add VPA](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/add-vpa) |
| Link VPA Account | Adds an account and optionally a VPA, managing the core linking between the selected bank account and the TAPP handle. | [Link VPA Account](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/link-vpa-account) |
| Generate OTP | Initiates the authentication process by generating an OTP (sent by the bank) required for setting or resetting the TAPP PIN. | [Generate OTP](https://www.google.com/search?q=https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/generate-otp) |
| Set/Reset MPIN | Allows the user to securely set a new TAPP PIN or reset a forgotten one using the OTP and debit card details. | [Set/Reset MPIN](https://www.google.com/search?q=https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/set-reset-mpin) |
| Change MPIN | Allows a user who knows their current TAPP PIN to change it to a new one. | [Change MPIN](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/change-mpin) |
| Check Balance | Fetches the real-time account balance for a linked bank account (requires MPIN authentication). | [Check Balance](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/check-balance) |
| Delete Account | Unlinks and removes a specific bank account from the user's registered TAPP profile. | [Delete Account](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/delete-account) |
| Delete VPA | Deletes a specific Virtual Payment Address (VPA) handle associated with the user. | [Delete VPA](https://www.google.com/search?q=https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-onboarding/delete-vpa) |

##  

## 

## 

## 

## 

## 

##   **4.3  Transaction Flows**  Here is a comprehensive table detailing the Transaction APIs available in the Juspay TAPP Consumer Stack, along with their descriptions and documentation links.  {#4.3-transaction-flows-here-is-a-comprehensive-table-detailing-the-transaction-apis-available-in-the-juspay-tapp-consumer-stack,-along-with-their-descriptions-and-documentation-links.}

| API Name | Description | Documentation Link |
| :---- | :---- | :---- |
| **Verify VPA 360** | Resolves and verifies the name and details of the entity associated with a specific Virtual Payment Address (VPA). | [Verify VPA 360](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/verifyvpa360) |
| **Send Money** | Used for completing outgoing payment scenarios, including P2P (Peer-to-Peer), P2M (Peer-to-Merchant), Intent, and Scan & Pay transactions. | [Send Money](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/send-money) |
| **Approve/Decline a Collect Request** | Allows a customer to either authorize (pay) or reject an incoming collect request they have received. | [Approve/Decline a Collect Request](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/approvedecline-a-collect-request) |
| **Transactions Status 360** | Fetches the real-time, definitive status of a specific TAPP transaction from the switch. | [Transactions Status 360](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/transactions-status-360) |
| **List Pending Collect Requests** | Retrieves a list of all currently active and pending collect requests waiting for the user's approval. | [List Pending Collect Requests](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/list-pending-collect-requests) |
| **List Transactions** | Fetches the transaction history for the user within your merchant application. | [List Transactions](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/list-transactions) |
| **Block and Spam a VPA** | Blocks a specific VPA from sending future collect requests to the user, with an option to mark them as spam. | [Block and Spam a VPA](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/block-and-spam-a-vpa) |
| **Unblock VPA** | Unblocks a previously blocked VPA, allowing them to send collect requests again. | [Unblock VPA](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/unblock-vpa) |
| **List Blocked VPAs** | Retrieves the full list of all VPAs that the user has currently blocked. | [List Blocked VPAs](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/list-blocked-vpas) |

##          

#   

# 

# 

# 

# 

# 

#     

## 6.2 Callbacks (Juspay → Niubiz / Merchant)

## 

| Callback Name & Link | Event Type | Description |
| :---- | :---- | :---- |
| [Incoming Collect Request to Customer](https://www.google.com/search?q=https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/incoming-collect-request-to-customer) | COLLECT\_REQUEST\_RECEIVED | Triggered when a customer receives a collect request from any TAPP user. This allows the merchant server to push a notification so the customer can take action (Approve/Decline). |
| [Outgoing Collect Request from Customer](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/outgoing-collect-request-from-customer) | COLLECT\_REQUEST\_SENT | Triggered when a customer successfully initiates and sends a collect request to another TAPP user. |
| [Incoming Money to Customer \- Pay](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/incoming-money-to-customer--pay) | CUSTOMER\_CREDITED\_VIA\_PAY | Triggered when the customer receives an incoming payment sent by another TAPP user via standard push methods (e.g., P2P\_PAY, SCAN\_PAY, INTENT\_PAY). |
| [Incoming Money to Customer \- Collect Status](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/incoming-money-to-customer--collect-status) | CUSTOMER\_CREDITED\_VIA\_COLLECT | Triggered when the customer has sent a collect request, and the status updates because the recipient approved, declined, or let it expire. |
| [Outgoing Money from a Customer](https://juspay.io/pe/docs/upi-consumer-stack-pe/docs/customer-transactions/outgoing-money-from-a-customer) | CUSTOMER\_DEBITED\_VIA\_PAY / CUSTOMER\_DEBITED\_VIA\_COLLECT | Triggered when the customer makes an outgoing payment (such as paying for a merchant order or approving a collect request). |

Reference: full request / response , header specifications and api encryption strategy are documented here  \- [API-GUIDE](https://juspay.io/pe/docs/upi-merchant-stack-pe/docs/submerchants/list-specific-sub-merchant-info)