#!/usr/bin/env python3
"""
Update API specifications with CORRECT JWE/JWS flow.
Based on IBMB document structure.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.database import database


async def update_api_specs():
    """Update API specs with correct JWE flow."""
    await database.connect()
    
    async with database.pool.acquire() as conn:
        # Update transaction init endpoint with CORRECT flow
        await conn.execute("""
            UPDATE endpoint_specs
            SET 
                request_schema = $1::jsonb,
                spec_data = COALESCE(spec_data, '{}'::jsonb) || $2::jsonb,
                description = CASE 
                    WHEN description LIKE '%WRAPPER%' THEN description
                    ELSE 'Initiate IBMB transaction. SECURITY: Payload must be signed (JWS RS256), wrapped in JSON, then encrypted (JWE RSA-OAEP-256+A256GCM). See api_auth_jwe document.'
                END
            WHERE endpoint_id = 'ibmb.merchant.transaction.init'
        """, 
            json.dumps({
                "type": "object",
                "required": ["ciphertext", "iv", "tag", "protected"],
                "properties": {
                    "ciphertext": {
                        "type": "string",
                        "description": "Base64Url encoded encrypted JWS wrapper JSON"
                    },
                    "iv": {
                        "type": "string", 
                        "description": "Base64Url encoded 96-bit initialization vector"
                    },
                    "tag": {
                        "type": "string",
                        "description": "Base64Url encoded 128-bit GCM authentication tag"
                    },
                    "protected": {
                        "type": "string",
                        "description": "Base64Url encoded JWE protected header (contains alg and enc)"
                    },
                    "encrypted_key": {
                        "type": "string",
                        "description": "Optional: Base64Url encoded encrypted Content Encryption Key (CEK)"
                    }
                },
                "description": "JWE JSON Serialized output containing encrypted JWS wrapper"
            }),
            json.dumps({
                "security": {
                    "encryption_required": True,
                    "content_type": "application/json",
                    "process": [
                        "1. Create original JSON payload with transaction details",
                        "2. Sign payload with JWS using YOUR private key (RS256)",
                        "   - Output: JWS Compact Serialization string (header.payload.signature)",
                        "3. Wrap JWS string in JSON structure:",
                        "   {\"payload\": \"<base64_header>.<base64_payload>\", \"signature\": \"<base64_signature>\"}",
                        "4. Encrypt this JSON wrapper with JWE using IBMB public key:",
                        "   - Algorithm: RSA-OAEP-256 for key encryption",
                        "   - Encryption: A256GCM for content",
                        "   - Output: JWE JSON with ciphertext, iv, tag, protected",
                        "5. Send JWE JSON with Content-Type: application/json"
                    ],
                    "input_format": {
                        "jws_compact": "Base64Url(header).Base64Url(payload).Base64Url(signature)",
                        "jws_wrapper_json": {"payload": "string", "signature": "string"}
                    },
                    "output_format": {
                        "jwe_json": {
                            "ciphertext": "Base64Url encrypted JWS wrapper",
                            "iv": "Base64Url 96-bit nonce",
                            "tag": "Base64Url 128-bit auth tag",
                            "protected": "Base64Url JWE header",
                            "encrypted_key": "Base64Url encrypted CEK (optional)"
                        }
                    },
                    "algorithms": {
                        "jws_signing": "RS256 (RSA-PSS with SHA-256)",
                        "jwe_key_encryption": "RSA-OAEP-256",
                        "jwe_content_encryption": "A256GCM"
                    },
                    "headers": {
                        "Content-Type": "application/json (NOT jose+json)",
                        "x-merchant-id": "Your merchant ID",
                        "x-merchant-channel-id": "Channel (WEB/APP)",
                        "x-trace-id": "UUID for request tracing",
                        "x-session-id": "UUID for session",
                        "x-timestamp": "Unix epoch milliseconds"
                    }
                },
                "curl_example": {
                    "description": "Send JWE encrypted transaction request",
                    "command": """curl -X POST https://api.ibmb.example.com/api/merchants/v1/transaction/initiate \\
  -H "Content-Type: application/json" \\
  -H "x-merchant-id: YOUR_MERCHANT_ID" \\
  -H "x-merchant-channel-id: CHANNEL_WEB" \\
  -H "x-trace-id: $(uuidgen)" \\
  -H "x-session-id: $(uuidgen)" \\
  -H "x-timestamp: $(date +%s%3N)" \\
  -d '{
    "ciphertext": "UBwuwXkMQGkJjB8A4prrHXog...",
    "iv": "Esg7qrFIO9w2n-H0Uru3M3",
    "tag": "dhaK4eTQYho3MBXocH5...",
    "protected": "eyJhbGciOiJSU0EtT0FFUC0yNTYi..."
  }'"""
                }
            })
        )
        
        print("✅ Updated API spec with CORRECT JWE flow")
        
        # Update error codes to reflect correct flow
        await conn.execute("""
            UPDATE error_codes
            SET 
                description = 'Request body must be JWE JSON format: {ciphertext, iv, tag, protected}. The plaintext must be a JWS wrapper JSON containing {payload, signature}.',
                fix_suggestions = '["Sign your payload with JWS (RS256) to get compact string", "Wrap JWS in JSON: {payload, signature}", "Encrypt JSON wrapper with JWE (RSA-OAEP-256 + A256GCM)", "Send JWE JSON output with Content-Type: application/json"]'
            WHERE error_code = 'ENCRYPTION_REQUIRED'
        """)
        
        print("✅ Updated error code descriptions")
        
        # Update integration flow
        await conn.execute("""
            UPDATE integration_flows
            SET steps = $1::jsonb,
                description = 'Complete payment flow. MANDATORY: Sign with JWS → Wrap in JSON → Encrypt with JWE → Send JWE JSON. Content-Type: application/json.',
                prerequisites = ARRAY['RSA key pair (2048-bit)', 'IBMB public key', 'JWE/JWS library', 'Test: Sign → Wrap → Encrypt flow']
            WHERE flow_id = 'ibmb.payment.standard'
        """,
            json.dumps([
                {
                    "step_number": 0,
                    "name": "Sign Payload with JWS",
                    "description": "Sign original JSON payload with YOUR private key (RS256). Output: Compact string header.payload.sig",
                    "critical": True,
                    "output": "JWS Compact Serialization"
                },
                {
                    "step_number": 1,
                    "name": "Wrap JWS in JSON",
                    "description": "Convert JWS compact string to JSON wrapper: {payload: 'base64_part', signature: 'sig_part'}",
                    "critical": True,
                    "output": "JWS Wrapper JSON"
                },
                {
                    "step_number": 2,
                    "name": "Encrypt with JWE",
                    "description": "Encrypt JWS wrapper JSON using IBMB public key. Alg: RSA-OAEP-256, Enc: A256GCM",
                    "critical": True,
                    "output": "JWE JSON {ciphertext, iv, tag, protected}"
                },
                {
                    "step_number": 3,
                    "name": "Send Encrypted Request",
                    "description": "POST /txns with Content-Type: application/json and JWE JSON body",
                    "endpoint": "ibmb.merchant.txns",
                    "method": "POST",
                    "critical": True
                }
            ])
        )
        
        print("✅ Updated integration flow")
        
    await database.close()
    print("\n" + "="*70)
    print("Updated with CORRECT JWE flow:")
    print("  JWS Compact → JSON Wrapper → JWE Encryption → JWE JSON")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(update_api_specs())
