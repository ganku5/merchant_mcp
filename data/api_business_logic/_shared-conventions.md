# Server-to-Server API Documentation Conventions

This folder is scoped to Newton merchant server-to-server APIs only. It excludes SDK, admin, ops dashboard, provider callback, internal service-job, NPCI XML, Olive, ICICI, IPO, and clearing-corporation route families.

Payloads use the standard Newton S2S encrypted request and response envelope. The examples in these guides show decrypted business payloads for readability.

Field tables infer required fields from the Haskell type shape: non-`Maybe` fields are required at type level, while `Maybe` fields are optional. Conditional requirements, defaults, and merchant-configuration behavior are documented where known, but product-specific behavior should be verified before sharing a guide externally.

Common failure body after decryption:

```json
{
  "status": "FAILURE",
  "responseCode": "BAD_REQUEST",
  "responseMessage": "RegexValidation \"upiRequestId regex match failed\""
}
```

Other common response codes include `INVALID_DATA`, `DUPLICATE_REQUEST`, `AUTH_FAILURE`, `UNAUTHORIZED`, and `INTERNAL_SERVER_ERROR`.
