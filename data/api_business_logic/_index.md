# Server-to-Server API Integration Guides

This folder contains `119` merchant server-to-server API guides generated from the S2S route definitions.

- Shared conventions: [_shared-conventions.md](_shared-conventions.md)
- Detailed register intent guide in this folder: [post-api-apiversion-merchants-transactions-registerintent.md](post-api-apiversion-merchants-transactions-registerintent.md)

## Coverage

- `cbs`: 1 APIs
- `merchants/accounts`: 8 APIs
- `merchants/banks`: 1 APIs
- `merchants/blockUnblockEntity`: 1 APIs
- `merchants/cbs`: 1 APIs
- `merchants/complaints`: 4 APIs
- `merchants/contacts`: 2 APIs
- `merchants/context`: 1 APIs
- `merchants/creditCard`: 4 APIs
- `merchants/customer`: 12 APIs
- `merchants/device`: 2 APIs
- `merchants/disputes`: 3 APIs
- `merchants/international`: 2 APIs
- `merchants/mandates`: 19 APIs
- `merchants/npci`: 4 APIs
- `merchants/outage`: 1 APIs
- `merchants/preApproved`: 1 APIs
- `merchants/signURL`: 1 APIs
- `merchants/smsService`: 1 APIs
- `merchants/sub`: 5 APIs
- `merchants/transactions`: 24 APIs
- `merchants/upiNumber`: 4 APIs
- `merchants/vaes`: 1 APIs
- `merchants/validateURL`: 1 APIs
- `merchants/voucher`: 1 APIs
- `merchants/vpaAccounts`: 1 APIs
- `merchants/vpas`: 9 APIs
- `merchants/wallet`: 3 APIs
- `npci`: 1 APIs

## cbs

| API | Method | Endpoint |
| --- | --- | --- |
| [Status](post-api-apiversion-cbs-transactions-status.md) | `POST` | `/api/{apiVersion}/cbs/transactions/status` |

## merchants/accounts

| API | Method | Endpoint |
| --- | --- | --- |
| [Add](post-api-apiversion-merchants-accounts-add.md) | `POST` | `/api/{apiVersion}/merchants/accounts/add` |
| [Balance](post-api-apiversion-merchants-accounts-balance.md) | `POST` | `/api/{apiVersion}/merchants/accounts/balance` |
| [Bio Auth](post-api-apiversion-merchants-accounts-bioauth.md) | `POST` | `/api/{apiVersion}/merchants/accounts/bioAuth` |
| [Change Mpin](post-api-apiversion-merchants-accounts-changempin.md) | `POST` | `/api/{apiVersion}/merchants/accounts/changeMpin` |
| [Delete](post-api-apiversion-merchants-accounts-delete.md) | `POST` | `/api/{apiVersion}/merchants/accounts/delete` |
| [Fetch](post-api-apiversion-merchants-accounts-fetch.md) | `POST` | `/api/{apiVersion}/merchants/accounts/fetch` |
| [Otp](post-api-apiversion-merchants-accounts-otp.md) | `POST` | `/api/{apiVersion}/merchants/accounts/otp` |
| [Set Mpin](post-api-apiversion-merchants-accounts-setmpin.md) | `POST` | `/api/{apiVersion}/merchants/accounts/setMpin` |

## merchants/banks

| API | Method | Endpoint |
| --- | --- | --- |
| [Banks](get-api-apiversion-merchants-banks.md) | `GET` | `/api/{apiVersion}/merchants/banks` |

## merchants/blockUnblockEntity

| API | Method | Endpoint |
| --- | --- | --- |
| [Block Unblock Entity](post-api-apiversion-merchants-blockunblockentity.md) | `POST` | `/api/{apiVersion}/merchants/blockUnblockEntity` |

## merchants/cbs

| API | Method | Endpoint |
| --- | --- | --- |
| [Balance](post-api-apiversion-merchants-cbs-balance.md) | `POST` | `/api/{apiVersion}/merchants/cbs/balance` |

## merchants/complaints

| API | Method | Endpoint |
| --- | --- | --- |
| [List](post-api-apiversion-merchants-complaints-list.md) | `POST` | `/api/{apiVersion}/merchants/complaints/list` |
| [Raise](post-api-apiversion-merchants-complaints-raise.md) | `POST` | `/api/{apiVersion}/merchants/complaints/raise` |
| [Resolve](post-api-apiversion-merchants-complaints-resolve.md) | `POST` | `/api/{apiVersion}/merchants/complaints/resolve` |
| [Status](post-api-apiversion-merchants-complaints-status.md) | `POST` | `/api/{apiVersion}/merchants/complaints/status` |

## merchants/contacts

| API | Method | Endpoint |
| --- | --- | --- |
| [List](post-api-apiversion-merchants-contacts-list.md) | `POST` | `/api/{apiVersion}/merchants/contacts/list` |
| [Manage](post-api-apiversion-merchants-contacts-manage.md) | `POST` | `/api/{apiVersion}/merchants/contacts/manage` |

## merchants/context

| API | Method | Endpoint |
| --- | --- | --- |
| [Fetch](post-api-apiversion-merchants-context-fetch.md) | `POST` | `/api/{apiVersion}/merchants/context/fetch` |

## merchants/creditCard

| API | Method | Endpoint |
| --- | --- | --- |
| [Check Emi](post-api-apiversion-merchants-creditcard-checkemi.md) | `POST` | `/api/{apiVersion}/merchants/creditCard/checkEmi` |
| [Emi Status](post-api-apiversion-merchants-creditcard-emistatus.md) | `POST` | `/api/{apiVersion}/merchants/creditCard/emiStatus` |
| [Fetch Bill](post-api-apiversion-merchants-creditcard-fetchbill.md) | `POST` | `/api/{apiVersion}/merchants/creditCard/fetchBill` |
| [Select Emi](post-api-apiversion-merchants-creditcard-selectemi.md) | `POST` | `/api/{apiVersion}/merchants/creditCard/selectEmi` |

## merchants/customer

| API | Method | Endpoint |
| --- | --- | --- |
| [Activate](post-api-apiversion-merchants-customer-activate.md) | `POST` | `/api/{apiVersion}/merchants/customer/activate` |
| [Add](post-api-apiversion-merchants-customer-add.md) | `POST` | `/api/{apiVersion}/merchants/customer/add` |
| [Bind Device](post-api-apiversion-merchants-customer-binddevice.md) | `POST` | `/api/{apiVersion}/merchants/customer/bindDevice` |
| [Decline](post-api-apiversion-merchants-customer-binddevice-decline.md) | `POST` | `/api/{apiVersion}/merchants/customer/bindDevice/decline` |
| [List Pending Links](post-api-apiversion-merchants-customer-delegates-listpendinglinks.md) | `POST` | `/api/{apiVersion}/merchants/customer/delegates/listPendingLinks` |
| [Manage Link](post-api-apiversion-merchants-customer-delegates-managelink.md) | `POST` | `/api/{apiVersion}/merchants/customer/delegates/manageLink` |
| [Deregister](post-api-apiversion-merchants-customer-deregister.md) | `POST` | `/api/{apiVersion}/merchants/customer/deregister` |
| [Get Sms Token](post-api-apiversion-merchants-customer-getsmstoken.md) | `POST` | `/api/{apiVersion}/merchants/customer/getSmsToken` |
| [Info](post-api-apiversion-merchants-customer-info.md) | `POST` | `/api/{apiVersion}/merchants/customer/info` |
| [Onboard](post-api-apiversion-merchants-customer-onboard.md) | `POST` | `/api/{apiVersion}/merchants/customer/onboard` |
| [Init](post-api-apiversion-merchants-customer-registration-init.md) | `POST` | `/api/{apiVersion}/merchants/customer/registration/init` |
| [Manage](post-api-apiversion-merchants-customer-secondarydevice-manage.md) | `POST` | `/api/{apiVersion}/merchants/customer/secondaryDevice/manage` |

## merchants/device

| API | Method | Endpoint |
| --- | --- | --- |
| [Activate](post-api-apiversion-merchants-device-activate.md) | `POST` | `/api/{apiVersion}/merchants/device/activate` |
| [Bind](post-api-apiversion-merchants-device-bind.md) | `POST` | `/api/{apiVersion}/merchants/device/bind` |

## merchants/disputes

| API | Method | Endpoint |
| --- | --- | --- |
| [Fetch](post-api-apiversion-merchants-disputes-fetch.md) | `POST` | `/api/{apiVersion}/merchants/disputes/fetch` |
| [List](post-api-apiversion-merchants-disputes-list.md) | `POST` | `/api/{apiVersion}/merchants/disputes/list` |
| [Update](post-api-apiversion-merchants-disputes-update.md) | `POST` | `/api/{apiVersion}/merchants/disputes/update` |

## merchants/international

| API | Method | Endpoint |
| --- | --- | --- |
| [Manage Activation](post-api-apiversion-merchants-international-manageactivation.md) | `POST` | `/api/{apiVersion}/merchants/international/manageActivation` |
| [Validate Qr](post-api-apiversion-merchants-international-validateqr.md) | `POST` | `/api/{apiVersion}/merchants/international/validateQr` |

## merchants/mandates

| API | Method | Endpoint |
| --- | --- | --- |
| [Approve](post-api-apiversion-merchants-mandates-approve.md) | `POST` | `/api/{apiVersion}/merchants/mandates/approve` |
| [Create](post-api-apiversion-merchants-mandates-create.md) | `POST` | `/api/{apiVersion}/merchants/mandates/create` |
| [Delete Execute Cycle](post-api-apiversion-merchants-mandates-deleteexecutecycle.md) | `POST` | `/api/{apiVersion}/merchants/mandates/deleteExecuteCycle` |
| [Execute](post-api-apiversion-merchants-mandates-execute.md) | `POST` | `/api/{apiVersion}/merchants/mandates/execute` |
| [List](post-api-apiversion-merchants-mandates-list.md) | `POST` | `/api/{apiVersion}/merchants/mandates/list` |
| [List Transactions](post-api-apiversion-merchants-mandates-listtransactions.md) | `POST` | `/api/{apiVersion}/merchants/mandates/listTransactions` |
| [Lite Execute](post-api-apiversion-merchants-mandates-liteexecute.md) | `POST` | `/api/{apiVersion}/merchants/mandates/liteExecute` |
| [Pause](post-api-apiversion-merchants-mandates-pause.md) | `POST` | `/api/{apiVersion}/merchants/mandates/pause` |
| [Port Mandate](post-api-apiversion-merchants-mandates-portmandate.md) | `POST` | `/api/{apiVersion}/merchants/mandates/portMandate` |
| [Status](post-api-apiversion-merchants-mandates-status.md) | `POST` | `/api/{apiVersion}/merchants/mandates/status` |
| [Update](post-api-apiversion-merchants-mandates-update.md) | `POST` | `/api/{apiVersion}/merchants/mandates/update` |
| [Update Interoperability](post-api-apiversion-merchants-mandates-updateinteroperability.md) | `POST` | `/api/{apiVersion}/merchants/mandates/updateInteroperability` |
| [Web Execute](post-api-apiversion-merchants-mandates-webexecute.md) | `POST` | `/api/{apiVersion}/merchants/mandates/webExecute` |
| [Web Execute Cycle](post-api-apiversion-merchants-mandates-webexecutecycle.md) | `POST` | `/api/{apiVersion}/merchants/mandates/webExecuteCycle` |
| [Web Execute Cycle Status](post-api-apiversion-merchants-mandates-webexecutecyclestatus.md) | `POST` | `/api/{apiVersion}/merchants/mandates/webExecuteCycleStatus` |
| [Web Mandate](post-api-apiversion-merchants-mandates-webmandate.md) | `POST` | `/api/{apiVersion}/merchants/mandates/webMandate` |
| [Web Notify](post-api-apiversion-merchants-mandates-webnotify.md) | `POST` | `/api/{apiVersion}/merchants/mandates/webNotify` |
| [Status](post-api-apiversion-merchants-mandates-webnotify-status.md) | `POST` | `/api/{apiVersion}/merchants/mandates/webNotify/status` |
| [Web Update](post-api-apiversion-merchants-mandates-webupdate.md) | `POST` | `/api/{apiVersion}/merchants/mandates/webUpdate` |

## merchants/npci

| API | Method | Endpoint |
| --- | --- | --- |
| [Keys](get-api-apiversion-merchants-npci-keys.md) | `GET` | `/api/{apiVersion}/merchants/npci/keys` |
| [Keys](post-api-apiversion-merchants-npci-keys.md) | `POST` | `/api/{apiVersion}/merchants/npci/keys` |
| [Account](post-api-apiversion-merchants-npci-lite-account.md) | `POST` | `/api/{apiVersion}/merchants/npci/lite/account` |
| [Token](post-api-apiversion-merchants-npci-token.md) | `POST` | `/api/{apiVersion}/merchants/npci/token` |

## merchants/outage

| API | Method | Endpoint |
| --- | --- | --- |
| [Outage](post-api-apiversion-merchants-outage.md) | `POST` | `/api/{apiVersion}/merchants/outage` |

## merchants/preApproved

| API | Method | Endpoint |
| --- | --- | --- |
| [Vpa Accounts](post-api-apiversion-merchants-preapproved-vpaaccounts.md) | `POST` | `/api/{apiVersion}/merchants/preApproved/vpaAccounts` |

## merchants/signURL

| API | Method | Endpoint |
| --- | --- | --- |
| [Sign Url](post-api-apiversion-merchants-signurl.md) | `POST` | `/api/{apiVersion}/merchants/signURL` |

## merchants/smsService

| API | Method | Endpoint |
| --- | --- | --- |
| [Sms Service](post-api-apiversion-merchants-smsservice.md) | `POST` | `/api/{apiVersion}/merchants/smsService` |

## merchants/sub

| API | Method | Endpoint |
| --- | --- | --- |
| [Add](post-api-apiversion-merchants-sub-add.md) | `POST` | `/api/{apiVersion}/merchants/sub/add` |
| [Info](post-api-apiversion-merchants-sub-info.md) | `POST` | `/api/{apiVersion}/merchants/sub/info` |
| [List](post-api-apiversion-merchants-sub-list.md) | `POST` | `/api/{apiVersion}/merchants/sub/list` |
| [Migrate](post-api-apiversion-merchants-sub-migrate.md) | `POST` | `/api/{apiVersion}/merchants/sub/migrate` |
| [Update](post-api-apiversion-merchants-sub-update.md) | `POST` | `/api/{apiVersion}/merchants/sub/update` |

## merchants/transactions

| API | Method | Endpoint |
| --- | --- | --- |
| [Bank Status Check](post-api-apiversion-merchants-transactions-bankstatuscheck.md) | `POST` | `/api/{apiVersion}/merchants/transactions/bankStatusCheck` |
| [Collect](post-api-apiversion-merchants-transactions-collect.md) | `POST` | `/api/{apiVersion}/merchants/transactions/collect` |
| [Delegate Pay](post-api-apiversion-merchants-transactions-delegatepay.md) | `POST` | `/api/{apiVersion}/merchants/transactions/delegatePay` |
| [List Pending](post-api-apiversion-merchants-transactions-delegates-listpending.md) | `POST` | `/api/{apiVersion}/merchants/transactions/delegates/listPending` |
| [Deregister Intent](post-api-apiversion-merchants-transactions-deregisterintent.md) | `POST` | `/api/{apiVersion}/merchants/transactions/deregisterIntent` |
| [List](post-api-apiversion-merchants-transactions-list.md) | `POST` | `/api/{apiVersion}/merchants/transactions/list` |
| [List Pending](post-api-apiversion-merchants-transactions-listpending.md) | `POST` | `/api/{apiVersion}/merchants/transactions/listPending` |
| [Litesync](post-api-apiversion-merchants-transactions-litesync.md) | `POST` | `/api/{apiVersion}/merchants/transactions/litesync` |
| [Online Refund](post-api-apiversion-merchants-transactions-onlinerefund.md) | `POST` | `/api/{apiVersion}/merchants/transactions/onlineRefund` |
| [Pending](post-api-apiversion-merchants-transactions-pending.md) | `POST` | `/api/{apiVersion}/merchants/transactions/pending` |
| [Push To Vpa](post-api-apiversion-merchants-transactions-pushtovpa.md) | `POST` | `/api/{apiVersion}/merchants/transactions/pushToVpa` |
| [Status](post-api-apiversion-merchants-transactions-pushtovpa-status.md) | `POST` | `/api/{apiVersion}/merchants/transactions/pushToVpa/status` |
| [Refund](post-api-apiversion-merchants-transactions-refund.md) | `POST` | `/api/{apiVersion}/merchants/transactions/refund` |
| [Status](post-api-apiversion-merchants-transactions-refund-status.md) | `POST` | `/api/{apiVersion}/merchants/transactions/refund/status` |
| [Refund360](post-api-apiversion-merchants-transactions-refund360.md) | `POST` | `/api/{apiVersion}/merchants/transactions/refund360` |
| [Register Intent](post-api-apiversion-merchants-transactions-registerintent.md) | `POST` | `/api/{apiVersion}/merchants/transactions/registerIntent` |
| [Request Money](post-api-apiversion-merchants-transactions-requestmoney.md) | `POST` | `/api/{apiVersion}/merchants/transactions/requestMoney` |
| [Send Money](post-api-apiversion-merchants-transactions-sendmoney.md) | `POST` | `/api/{apiVersion}/merchants/transactions/sendMoney` |
| [Split](post-api-apiversion-merchants-transactions-settlement-split.md) | `POST` | `/api/{apiVersion}/merchants/transactions/settlement/split` |
| [Status](post-api-apiversion-merchants-transactions-status.md) | `POST` | `/api/{apiVersion}/merchants/transactions/status` |
| [Status360](post-api-apiversion-merchants-transactions-status360.md) | `POST` | `/api/{apiVersion}/merchants/transactions/status360` |
| [Status V2](post-api-apiversion-merchants-transactions-statusv2.md) | `POST` | `/api/{apiVersion}/merchants/transactions/statusV2` |
| [Web Collect](post-api-apiversion-merchants-transactions-webcollect.md) | `POST` | `/api/{apiVersion}/merchants/transactions/webCollect` |
| [Web Collect360](post-api-apiversion-merchants-transactions-webcollect360.md) | `POST` | `/api/{apiVersion}/merchants/transactions/webCollect360` |

## merchants/upiNumber

| API | Method | Endpoint |
| --- | --- | --- |
| [Availability](post-api-apiversion-merchants-upinumber-availability.md) | `POST` | `/api/{apiVersion}/merchants/upiNumber/availability` |
| [Create](post-api-apiversion-merchants-upinumber-create.md) | `POST` | `/api/{apiVersion}/merchants/upiNumber/create` |
| [Fetch](post-api-apiversion-merchants-upinumber-fetch.md) | `POST` | `/api/{apiVersion}/merchants/upiNumber/fetch` |
| [Update](post-api-apiversion-merchants-upinumber-update.md) | `POST` | `/api/{apiVersion}/merchants/upiNumber/update` |

## merchants/vaes

| API | Method | Endpoint |
| --- | --- | --- |
| [Fetch](post-api-apiversion-merchants-vaes-fetch.md) | `POST` | `/api/{apiVersion}/merchants/vaes/fetch` |

## merchants/validateURL

| API | Method | Endpoint |
| --- | --- | --- |
| [Validate Url](post-api-apiversion-merchants-validateurl.md) | `POST` | `/api/{apiVersion}/merchants/validateURL` |

## merchants/voucher

| API | Method | Endpoint |
| --- | --- | --- |
| [Create](post-api-apiversion-merchants-voucher-create.md) | `POST` | `/api/{apiVersion}/merchants/voucher/create` |

## merchants/vpaAccounts

| API | Method | Endpoint |
| --- | --- | --- |
| [Vpa Accounts](post-api-apiversion-merchants-vpaaccounts.md) | `POST` | `/api/{apiVersion}/merchants/vpaAccounts` |

## merchants/vpas

| API | Method | Endpoint |
| --- | --- | --- |
| [Add Default](post-api-apiversion-merchants-vpas-adddefault.md) | `POST` | `/api/{apiVersion}/merchants/vpas/addDefault` |
| [Availability](post-api-apiversion-merchants-vpas-availability.md) | `POST` | `/api/{apiVersion}/merchants/vpas/availability` |
| [List](post-api-apiversion-merchants-vpas-block-list.md) | `POST` | `/api/{apiVersion}/merchants/vpas/block/list` |
| [Block And Spam](post-api-apiversion-merchants-vpas-blockandspam.md) | `POST` | `/api/{apiVersion}/merchants/vpas/blockAndSpam` |
| [Delete Vpa](post-api-apiversion-merchants-vpas-deletevpa.md) | `POST` | `/api/{apiVersion}/merchants/vpas/deleteVpa` |
| [Resolution](post-api-apiversion-merchants-vpas-resolution.md) | `POST` | `/api/{apiVersion}/merchants/vpas/resolution` |
| [Unblock](post-api-apiversion-merchants-vpas-unblock.md) | `POST` | `/api/{apiVersion}/merchants/vpas/unblock` |
| [Validity](post-api-apiversion-merchants-vpas-validity.md) | `POST` | `/api/{apiVersion}/merchants/vpas/validity` |
| [Validity360](post-api-apiversion-merchants-vpas-validity360.md) | `POST` | `/api/{apiVersion}/merchants/vpas/validity360` |

## merchants/wallet

| API | Method | Endpoint |
| --- | --- | --- |
| [Create](post-api-apiversion-merchants-wallet-account-create.md) | `POST` | `/api/{apiVersion}/merchants/wallet/account/create` |
| [Create And Link](post-api-apiversion-merchants-wallet-account-createandlink.md) | `POST` | `/api/{apiVersion}/merchants/wallet/account/createAndLink` |
| [Update](post-api-apiversion-merchants-wallet-account-update.md) | `POST` | `/api/{apiVersion}/merchants/wallet/account/update` |

## npci

| API | Method | Endpoint |
| --- | --- | --- |
| [List Psp](get-api-apiversion-npci-listpsp.md) | `GET` | `/api/{apiVersion}/npci/listPsp` |
