#!/usr/bin/env python3
"""
Populate integration_flows table with actual flows from IBMB documents.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.database import database


FLOWS = [
    {
        "flow_id": "ibmb.payment.standard",
        "name": "Standard Payment Flow",
        "use_case": "payment",
        "description": "Complete payment transaction flow from initiation to completion",
        "steps": [
            {
                "step_number": 1,
                "name": "Transaction Initialization",
                "description": "Merchant initiates transaction via POST /txns with encrypted payload (JWE)",
                "endpoint": "ibmb.merchant.txns",
                "method": "POST",
                "critical": True
            },
            {
                "step_number": 2,
                "name": "Customer Authentication",
                "description": "Customer authenticates via NetBanking credentials on bank page",
                "endpoint": "bank.netbanking.login",
                "method": "REDIRECT",
                "critical": True
            },
            {
                "step_number": 3,
                "name": "Payment Authorization",
                "description": "Customer authorizes payment amount on bank confirmation page",
                "endpoint": "bank.netbanking.confirm",
                "method": "POST",
                "critical": True
            },
            {
                "step_number": 4,
                "name": "Webhook Notification",
                "description": "Receive transaction status webhook from IBMB",
                "endpoint": "merchant.webhook",
                "method": "WEBHOOK",
                "critical": False
            },
            {
                "step_number": 5,
                "name": "Status Verification",
                "description": "Verify final transaction status via GET /txns/{txnId}",
                "endpoint": "ibmb.merchant.txns.status",
                "method": "GET",
                "critical": True
            }
        ],
        "prerequisites": [
            "Valid IBMB merchant credentials",
            "JWE encryption keys configured",
            "Webhook endpoint registered",
            "IP whitelisting completed"
        ],
        "estimated_duration_minutes": 5,
        "version": "v1",
        "source_doc_id": "ibmb_acquiring_merchant_guide"
    },
    {
        "flow_id": "ibmb.merchant.onboarding",
        "name": "Merchant Onboarding Flow",
        "use_case": "payment",
        "description": "Process for Payment Aggregators to onboard new merchants to IBMB",
        "steps": [
            {
                "step_number": 1,
                "name": "Login to PA Portal",
                "description": "PA admin logs in to IBMB Back Office Portal",
                "endpoint": "pa.portal.login",
                "method": "WEB",
                "critical": True
            },
            {
                "step_number": 2,
                "name": "Navigate to Merchant Management",
                "description": "Go to Participant Management → Merchant",
                "endpoint": "pa.portal.merchant",
                "method": "WEB",
                "critical": True
            },
            {
                "step_number": 3,
                "name": "Initiate Onboarding",
                "description": "Click '+ Add Merchant' button to start onboarding",
                "endpoint": "pa.portal.merchant.add",
                "method": "WEB",
                "critical": True
            },
            {
                "step_number": 4,
                "name": "Fill Merchant Details",
                "description": "Enter legal name, brand name, GSTIN, PAN, MCC, merchant type, ownership",
                "endpoint": "pa.portal.merchant.details",
                "method": "FORM",
                "critical": True
            },
            {
                "step_number": 5,
                "name": "Enter Settlement Information",
                "description": "Configure settlement type (DIRECTTOPA/DIRECTTOMERCHANT), bank account, IFSC",
                "endpoint": "pa.portal.merchant.settlement",
                "method": "FORM",
                "critical": True
            },
            {
                "step_number": 6,
                "name": "Maker Submission",
                "description": "PA maker submits for checker approval",
                "endpoint": "pa.portal.merchant.submit",
                "method": "POST",
                "critical": True
            },
            {
                "step_number": 7,
                "name": "Checker Approval",
                "description": "PA checker reviews and approves/rejects the application",
                "endpoint": "pa.portal.merchant.approve",
                "method": "POST",
                "critical": True
            },
            {
                "step_number": 8,
                "name": "IBMB Admin Approval",
                "description": "IBMB admin performs final approval",
                "endpoint": "ibmb.admin.merchant.final_approve",
                "method": "POST",
                "critical": True
            }
        ],
        "prerequisites": [
            "PA admin credentials with maker/checker roles",
            "Merchant KYC documents (GST, PAN, bank proof)",
            "Merchant website/app details",
            "Signed agreement with IBMB"
        ],
        "estimated_duration_minutes": 30,
        "version": "v1",
        "source_doc_id": "ibmb_pa_portal_manual"
    },
    {
        "flow_id": "ibmb.security.jwe_implementation",
        "name": "JWE Security Implementation Flow",
        "use_case": "payment",
        "description": "Implement JWE (JSON Web Encryption) and JWS for secure API communication",
        "steps": [
            {
                "step_number": 1,
                "name": "Key Exchange",
                "description": "Exchange RSA public keys with IBMB via PA Portal or SDK",
                "endpoint": "ibmb.key.exchange",
                "method": "PORTAL/SDK",
                "critical": True
            },
            {
                "step_number": 2,
                "name": "Generate Content Encryption Key (CEK)",
                "description": "Generate random 256-bit AES key for payload encryption",
                "endpoint": "local.crypto",
                "method": "LOCAL",
                "critical": True
            },
            {
                "step_number": 3,
                "name": "Encrypt Payload with AES-GCM",
                "description": "Encrypt sensitive data using AES-GCM with generated CEK and IV",
                "endpoint": "local.crypto",
                "method": "LOCAL",
                "critical": True
            },
            {
                "step_number": 4,
                "name": "Encrypt CEK with RSA-OAEP",
                "description": "Wrap the AES key using IBMB's RSA public key with RSA-OAEP",
                "endpoint": "local.crypto",
                "method": "LOCAL",
                "critical": True
            },
            {
                "step_number": 5,
                "name": "Construct JWE Token",
                "description": "Assemble JWE header, encrypted CEK, IV, ciphertext, and auth tag",
                "endpoint": "local.crypto",
                "method": "LOCAL",
                "critical": True
            },
            {
                "step_number": 6,
                "name": "Sign with JWS (Optional)",
                "description": "Create JWS signature using merchant's private key for additional integrity",
                "endpoint": "local.crypto",
                "method": "LOCAL",
                "critical": False
            },
            {
                "step_number": 7,
                "name": "Send Encrypted Request",
                "description": "Transmit JWE-encrypted payload to IBMB API endpoint",
                "endpoint": "ibmb.api.any",
                "method": "POST",
                "critical": True
            }
        ],
        "prerequisites": [
            "RSA key pair (2048-bit)",
            "IBMB public key (X.509 format)",
            "Crypto library supporting AES-GCM and RSA-OAEP",
            "Understanding of JWE compact serialization"
        ],
        "estimated_duration_minutes": 120,
        "version": "v1",
        "source_doc_id": "api_auth_jwe"
    },
    {
        "flow_id": "ibmb.refund.standard",
        "name": "Refund Processing Flow",
        "use_case": "refund",
        "description": "Process refunds for completed transactions",
        "steps": [
            {
                "step_number": 1,
                "name": "Verify Original Transaction",
                "description": "Confirm original txn was successful and within refund window",
                "endpoint": "ibmb.merchant.txns.status",
                "method": "GET",
                "critical": True
            },
            {
                "step_number": 2,
                "name": "Initiate Refund",
                "description": "Call POST /refunds with original txn ID and refund amount",
                "endpoint": "ibmb.merchant.refunds",
                "method": "POST",
                "critical": True
            },
            {
                "step_number": 3,
                "name": "Receive Webhook",
                "description": "Wait for refund status webhook notification",
                "endpoint": "merchant.webhook",
                "method": "WEBHOOK",
                "critical": False
            },
            {
                "step_number": 4,
                "name": "Verify Refund Status",
                "description": "Poll GET /refunds/{refundId} until status is confirmed",
                "endpoint": "ibmb.merchant.refunds.status",
                "method": "GET",
                "critical": True
            }
        ],
        "prerequisites": [
            "Original successful transaction",
            "Refund amount ≤ original amount",
            "Within refund window (typically 180 days)"
        ],
        "estimated_duration_minutes": 3,
        "version": "v1",
        "source_doc_id": "ibmb_acquiring_merchant_guide"
    },
    {
        "flow_id": "ibmb.status.check",
        "name": "Transaction Status Check Flow",
        "use_case": "payment",
        "description": "Check status of transactions via API or webhook",
        "steps": [
            {
                "step_number": 1,
                "name": "Method Selection",
                "description": "Choose between real-time API check or webhook notification",
                "endpoint": "decision",
                "method": "NA",
                "critical": False
            },
            {
                "step_number": 2,
                "name": "API Status Check",
                "description": "Call GET /txns/{txnId} with merchant txn ID",
                "endpoint": "ibmb.merchant.txns.status",
                "method": "GET",
                "critical": True
            },
            {
                "step_number": 3,
                "name": "Parse Response",
                "description": "Handle status: PENDING, SUCCESS, FAILED, CANCELLED",
                "endpoint": "local.parser",
                "method": "LOCAL",
                "critical": True
            },
            {
                "step_number": 4,
                "name": "Retry Logic (if needed)",
                "description": "Implement exponential backoff for PENDING status",
                "endpoint": "local.logic",
                "method": "LOCAL",
                "critical": False
            }
        ],
        "prerequisites": [
            "Valid merchant transaction ID",
            "API credentials for authentication"
        ],
        "estimated_duration_minutes": 1,
        "version": "v1",
        "source_doc_id": "ibmb_acquiring_merchant_guide"
    },
    {
        "flow_id": "ibmb.dispute.handling",
        "name": "Dispute Management Flow",
        "use_case": "payment",
        "description": "Handle chargebacks and disputes raised by customers",
        "steps": [
            {
                "step_number": 1,
                "name": "Receive Dispute Notification",
                "description": "Get dispute webhook from IBMB with case ID and details",
                "endpoint": "merchant.webhook.dispute",
                "method": "WEBHOOK",
                "critical": True
            },
            {
                "step_number": 2,
                "name": "Review Dispute",
                "description": "Check dispute details in PA Portal under Dispute section",
                "endpoint": "pa.portal.dispute.view",
                "method": "WEB",
                "critical": True
            },
            {
                "step_number": 3,
                "name": "Accept or Challenge",
                "description": "Decision: Accept dispute (auto-refund) or challenge with evidence",
                "endpoint": "decision",
                "method": "NA",
                "critical": True
            },
            {
                "step_number": 4,
                "name": "Submit Evidence (if challenging)",
                "description": "Upload proof of delivery, invoices, customer communication",
                "endpoint": "pa.portal.dispute.evidence",
                "method": "POST",
                "critical": True
            },
            {
                "step_number": 5,
                "name": "Track Resolution",
                "description": "Monitor dispute status via portal or status API",
                "endpoint": "pa.portal.dispute.status",
                "method": "GET",
                "critical": True
            }
        ],
        "prerequisites": [
            "Dispute webhook endpoint configured",
            "Access to PA Portal dispute section",
            "Documentation of transactions and deliveries"
        ],
        "estimated_duration_minutes": 30,
        "version": "v1",
        "source_doc_id": "ibmb_pa_portal_manual"
    }
]


async def populate_flows():
    """Insert flows into database."""
    await database.connect()
    
    async with database.pool.acquire() as conn:
        # Check existing flows
        existing = await conn.fetchval("SELECT COUNT(*) FROM integration_flows")
        print(f"Existing flows: {existing}")
        
        inserted = 0
        for flow in FLOWS:
            # Convert steps to JSON
            flow_data = {
                "flow_id": flow["flow_id"],
                "name": flow["name"],
                "steps": flow["steps"],
                "use_case": flow["use_case"],
                "description": flow["description"],
                "prerequisites": flow["prerequisites"],
                "estimated_duration_minutes": flow["estimated_duration_minutes"]
            }
            
            try:
                await conn.execute("""
                    INSERT INTO integration_flows (
                        flow_id, name, use_case, description, steps,
                        prerequisites, estimated_duration_minutes,
                        version, flow_data, source_doc_id
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (flow_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        use_case = EXCLUDED.use_case,
                        description = EXCLUDED.description,
                        steps = EXCLUDED.steps,
                        prerequisites = EXCLUDED.prerequisites,
                        estimated_duration_minutes = EXCLUDED.estimated_duration_minutes,
                        version = EXCLUDED.version,
                        flow_data = EXCLUDED.flow_data,
                        source_doc_id = EXCLUDED.source_doc_id,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    flow["flow_id"],
                    flow["name"],
                    flow["use_case"],
                    flow["description"],
                    json.dumps(flow["steps"]),
                    json.dumps(flow["prerequisites"]),
                    flow["estimated_duration_minutes"],
                    flow["version"],
                    json.dumps(flow_data),
                    flow.get("source_doc_id")
                )
                inserted += 1
                print(f"✓ {flow['flow_id']}: {flow['name']}")
            except Exception as e:
                print(f"✗ {flow['flow_id']}: {e}")
        
        # Verify count
        total = await conn.fetchval("SELECT COUNT(*) FROM integration_flows")
        print(f"\nTotal flows in database: {total}")
        print(f"Inserted/Updated: {inserted}")
    
    await database.close()


if __name__ == "__main__":
    print("="*60)
    print("Populating Integration Flows")
    print("="*60)
    asyncio.run(populate_flows())
    print("="*60)
