"""
Enhanced Guides & Documentation - Phase 4 Implementation

Interactive guides and documentation features:
- Personalized step-by-step integration guides
- Mermaid flow diagram generation
- Visual API flow engine
- FAQ per step
- Progress tracking
"""

import json
import re
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..utils.database import database
from ..utils.llm import llm_client


class UserRole(Enum):
    """User roles for guide personalization."""
    BACKEND_DEVELOPER = "backend_developer"
    FRONTEND_DEVELOPER = "frontend_developer"
    FULLSTACK_DEVELOPER = "fullstack_developer"
    DEVOPS_ENGINEER = "devops_engineer"
    PRODUCT_MANAGER = "product_manager"


class TechStack(Enum):
    """Technology stacks for code examples."""
    NODEJS_EXPRESS = "nodejs_express"
    PYTHON_FLASK = "python_flask"
    PYTHON_DJANGO = "python_django"
    PYTHON_FASTAPI = "python_fastapi"
    JAVA_SPRING = "java_spring"
    GO = "go"
    PHP = "php"
    RUBY = "ruby"


class ExperienceLevel(Enum):
    """Experience levels for guide complexity."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass
class GuideStep:
    """A single step in an integration guide."""
    step_number: int
    title: str
    description: str
    objectives: List[str]
    code_examples: Dict[str, str] = field(default_factory=dict)
    commands: List[str] = field(default_factory=list)
    expected_output: str = ""
    validation_checks: List[str] = field(default_factory=list)
    faq: List[Dict[str, str]] = field(default_factory=list)
    next_step_hint: str = ""
    estimated_minutes: int = 5
    difficulty: str = "easy"


@dataclass
class IntegrationGuide:
    """Complete integration guide."""
    title: str
    description: str
    use_case: str
    role: UserRole
    tech_stack: TechStack
    experience_level: ExperienceLevel
    total_estimated_minutes: int
    steps: List[GuideStep]
    prerequisites: List[str] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)


class InteractiveGuideEngine:
    """Engine for generating personalized integration guides."""
    
    # Guide templates by use case
    USE_CASE_TEMPLATES = {
        "upi_payment": {
            "title": "UPI Payment Integration",
            "description": "Accept UPI payments via collect or intent flow",
            "steps": [
                {
                    "title": "Setup and Authentication",
                    "description": "Configure your environment and authenticate with IBMB APIs",
                    "objectives": [
                        "Obtain API credentials from dashboard",
                        "Set up environment variables",
                        "Test authentication endpoint"
                    ],
                    "commands": [
                        "export IBMB_API_KEY=your_api_key_here",
                        "export IBMB_MERCHANT_ID=your_merchant_id",
                        "export IBMB_BASE_URL=https://api.ibmb.example.com"
                    ],
                    "validation_checks": [
                        "Environment variables are set",
                        "Can ping API health endpoint"
                    ],
                    "faq": [
                        {
                            "question": "Where do I find my API key?",
                            "answer": "Log in to your IBMB dashboard → Settings → API Keys"
                        },
                        {
                            "question": "Is there a sandbox environment?",
                            "answer": "Yes, use https://sandbox-api.ibmb.example.com for testing"
                        }
                    ],
                    "estimated_minutes": 10
                },
                {
                    "title": "Create Your First Transaction",
                    "description": "Initiate a UPI payment transaction",
                    "objectives": [
                        "Understand transaction request payload",
                        "Generate a unique merchantRequestId",
                        "Make your first transaction.init call"
                    ],
                    "validation_checks": [
                        "Response contains intent URL or collect notification sent",
                        "Transaction status is INITIATED",
                        "merchantRequestId is returned"
                    ],
                    "faq": [
                        {
                            "question": "What's the difference between COLLECT and PAY?",
                            "answer": "COLLECT: You request money from customer. PAY: Customer sends money directly."
                        },
                        {
                            "question": "How long is the intent URL valid?",
                            "answer": "Typically 5 minutes (300 seconds), configurable per merchant"
                        }
                    ],
                    "estimated_minutes": 15
                },
                {
                    "title": "Handle Payment Status",
                    "description": "Track and handle transaction status updates",
                    "objectives": [
                        "Set up webhook endpoint",
                        "Implement status polling fallback",
                        "Handle all transaction states"
                    ],
                    "validation_checks": [
                        "Webhook receives order.charged event",
                        "Status polling works correctly",
                        "All state transitions handled"
                    ],
                    "faq": [
                        {
                            "question": "Should I use webhooks or polling?",
                            "answer": "Use both! Webhooks for real-time updates, polling as fallback."
                        },
                        {
                            "question": "How often should I poll?",
                            "answer": "Every 5 seconds, maximum 60 times (5 minutes total)"
                        }
                    ],
                    "estimated_minutes": 20
                },
                {
                    "title": "Go Live",
                    "description": "Complete integration checklist and deploy to production",
                    "objectives": [
                        "Run integration check",
                        "Verify webhook signature verification",
                        "Deploy to production"
                    ],
                    "validation_checks": [
                        "All integration checks pass",
                        "Production credentials configured",
                        "Monitoring and alerts set up"
                    ],
                    "faq": [
                        {
                            "question": "What should I monitor?",
                            "answer": "Webhook delivery rate, API response times, transaction success rate"
                        }
                    ],
                    "estimated_minutes": 15
                }
            ]
        },
        "mandate_setup": {
            "title": "UPI Mandate Integration",
            "description": "Set up recurring payments via UPI Autopay",
            "steps": [
                {
                    "title": "Understand Mandate Flow",
                    "description": "Learn about UPI mandates and their lifecycle",
                    "objectives": [
                        "Understand mandate vs one-time payment",
                        "Learn about mandate states",
                        "Review compliance requirements"
                    ],
                    "estimated_minutes": 10
                },
                {
                    "title": "Create Mandate",
                    "description": "Create a new mandate authorization request",
                    "objectives": [
                        "Build mandate creation payload",
                        "Specify recurrence rules",
                        "Handle mandate approval flow"
                    ],
                    "estimated_minutes": 20
                },
                {
                    "title": "Execute Recurring Payments",
                    "description": "Trigger payments against approved mandates",
                    "objectives": [
                        "Schedule mandate executions",
                        "Handle execution notifications",
                        "Manage mandate modifications"
                    ],
                    "estimated_minutes": 15
                }
            ]
        },
        "refund_processing": {
            "title": "Refund Processing",
            "description": "Handle refunds for completed payments",
            "steps": [
                {
                    "title": "Initiate Refund",
                    "description": "Create a refund request for a completed transaction",
                    "objectives": [
                        "Validate original transaction",
                        "Create refund request",
                        "Handle partial vs full refunds"
                    ],
                    "estimated_minutes": 10
                },
                {
                    "title": "Track Refund Status",
                    "description": "Monitor refund processing and notify customer",
                    "objectives": [
                        "Listen for refund webhooks",
                        "Update order status",
                        "Notify customer of refund completion"
                    ],
                    "estimated_minutes": 15
                }
            ]
        }
    }
    
    # Code snippets by tech stack
    CODE_SNIPPETS = {
        TechStack.NODEJS_EXPRESS: {
            "transaction_init": """
const axios = require('axios');
const crypto = require('crypto');

async function initiateTransaction(payload) {
  const apiKey = process.env.IBMB_API_KEY;
  const baseUrl = process.env.IBMB_BASE_URL;
  
  try {
    const response = await axios.post(
      `${baseUrl}/api/merchants/v1/transaction/initiate`,
      payload,
      {
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Transaction failed:', error.response?.data);
    throw error;
  }
}
""",
            "webhook_handler": """
const crypto = require('crypto');

app.post('/webhook', express.raw({type: 'application/json'}), (req, res) => {
  const signature = req.headers['x-juspay-signature'];
  const secret = process.env.WEBHOOK_SECRET;
  
  const expected = crypto
    .createHmac('sha256', secret)
    .update(req.body)
    .digest('hex');
  
  if (!crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  )) {
    return res.status(401).send('Invalid signature');
  }
  
  const event = JSON.parse(req.body);
  // Process event...
  res.status(200).send('OK');
});
"""
        },
        TechStack.PYTHON_FASTAPI: {
            "transaction_init": """
import os
import httpx
from fastapi import HTTPException

API_KEY = os.getenv("IBMB_API_KEY")
BASE_URL = os.getenv("IBMB_BASE_URL")

async def initiate_transaction(payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/merchants/v1/transaction/initiate",
            json=payload,
            headers={"X-API-Key": API_KEY}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json()
            )
        
        return response.json()
""",
            "webhook_handler": """
import hmac
import hashlib
from fastapi import Request, HTTPException

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

@app.post("/webhook")
async def webhook_handler(request: Request):
    body = await request.body()
    signature = request.headers.get("x-juspay-signature")
    
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    event = json.loads(body)
    # Process event...
    return {"status": "ok"}
"""
        },
        TechStack.PYTHON_FLASK: {
            "transaction_init": """
import os
import requests
from flask import current_app

API_KEY = os.getenv("IBMB_API_KEY")
BASE_URL = os.getenv("IBMB_BASE_URL")

def initiate_transaction(payload):
    response = requests.post(
        f"{BASE_URL}/api/merchants/v1/transaction/initiate",
        json=payload,
        headers={"X-API-Key": API_KEY}
    )
    response.raise_for_status()
    return response.json()
""",
            "webhook_handler": """
import hmac
import hashlib
from flask import request, abort

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data()
    signature = request.headers.get("X-Juspay-Signature")
    
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        abort(401)
    
    event = request.get_json()
    # Process event...
    return "OK", 200
"""
        }
    }
    
    def __init__(self):
        self.user_progress: Dict[str, Dict[str, Any]] = {}
    
    def generate_guide(
        self,
        use_case: str,
        role: UserRole = UserRole.BACKEND_DEVELOPER,
        tech_stack: TechStack = TechStack.PYTHON_FASTAPI,
        experience_level: ExperienceLevel = ExperienceLevel.INTERMEDIATE
    ) -> IntegrationGuide:
        """Generate a personalized integration guide."""
        
        template = self.USE_CASE_TEMPLATES.get(use_case)
        if not template:
            raise ValueError(f"Unknown use case: {use_case}")
        
        # Build steps from template
        steps = []
        total_minutes = 0
        
        for i, step_template in enumerate(template["steps"], 1):
            # Customize step based on tech stack
            code_examples = {}
            if tech_stack in self.CODE_SNIPPETS:
                snippets = self.CODE_SNIPPETS[tech_stack]
                if i == 2 and "transaction_init" in snippets:  # Step 2 usually has init
                    code_examples["transaction_initiation"] = snippets["transaction_init"]
                if i == 3 and "webhook_handler" in snippets:  # Step 3 usually has webhook
                    code_examples["webhook_handler"] = snippets["webhook_handler"]
            
            step = GuideStep(
                step_number=i,
                title=step_template["title"],
                description=step_template["description"],
                objectives=step_template.get("objectives", []),
                code_examples=code_examples,
                commands=step_template.get("commands", []),
                expected_output=step_template.get("expected_output", ""),
                validation_checks=step_template.get("validation_checks", []),
                faq=step_template.get("faq", []),
                next_step_hint=template["steps"][i]["title"] if i < len(template["steps"]) else "Integration Complete!",
                estimated_minutes=step_template.get("estimated_minutes", 10),
                difficulty=self._calculate_difficulty(experience_level, i)
            )
            
            steps.append(step)
            total_minutes += step.estimated_minutes
        
        # Adjust for experience level
        if experience_level == ExperienceLevel.ADVANCED:
            total_minutes = int(total_minutes * 0.7)  # Faster for advanced
        elif experience_level == ExperienceLevel.BEGINNER:
            total_minutes = int(total_minutes * 1.5)  # Slower for beginners
        
        return IntegrationGuide(
            title=template["title"],
            description=template["description"],
            use_case=use_case,
            role=role,
            tech_stack=tech_stack,
            experience_level=experience_level,
            total_estimated_minutes=total_minutes,
            steps=steps,
            prerequisites=self._get_prerequisites(use_case),
            completion_criteria=self._get_completion_criteria(use_case)
        )
    
    def _calculate_difficulty(self, experience: ExperienceLevel, step_number: int) -> str:
        """Calculate step difficulty based on experience and position."""
        base_difficulties = {
            ExperienceLevel.BEGINNER: ["easy", "easy", "medium", "medium"],
            ExperienceLevel.INTERMEDIATE: ["easy", "medium", "medium", "hard"],
            ExperienceLevel.ADVANCED: ["easy", "medium", "hard", "hard"]
        }
        
        difficulties = base_difficulties.get(experience, ["medium"])
        idx = min(step_number - 1, len(difficulties) - 1)
        return difficulties[idx]
    
    def _get_prerequisites(self, use_case: str) -> List[str]:
        """Get prerequisites for a use case."""
        common = [
            "IBMB merchant account activated",
            "API credentials obtained from dashboard",
            "Development environment set up"
        ]
        
        specifics = {
            "upi_payment": ["Understanding of UPI payments", "Webhook endpoint URL ready"],
            "mandate_setup": ["Signed mandate agreement with IBMB", "Compliance review completed"],
            "refund_processing": ["Active merchant account with transaction history"]
        }
        
        return common + specifics.get(use_case, [])
    
    def _get_completion_criteria(self, use_case: str) -> List[str]:
        """Get completion criteria for a use case."""
        return [
            "All integration checks passing",
            "Test transactions successful in sandbox",
            "Webhook handling verified",
            "Error handling implemented",
            "Documentation reviewed with team"
        ]


class MermaidFlowGenerator:
    """Generates Mermaid diagrams for API flows."""
    
    FLOW_TEMPLATES = {
        "payment_standard": {
            "title": "Standard Payment Flow",
            "description": "Complete flow for a standard UPI payment",
            "diagram": """
sequenceDiagram
    participant C as Customer
    participant M as Merchant<br/>Server
    participant J as Juspay/IBMB
    participant U as UPI App
    
    C->>M: Initiate Payment
    M->>J: POST /transaction/initiate
    J-->>M: Response with Intent URL
    M-->>C: Redirect to UPI App
    C->>U: Complete Payment
    U->>J: Payment Confirmation
    J->>M: Webhook: order.charged
    M-->>C: Payment Success Page
            """
        },
        "payment_collect": {
            "title": "UPI Collect Flow",
            "description": "Merchant-initiated collect request flow",
            "diagram": """
sequenceDiagram
    participant C as Customer
    participant M as Merchant
    participant J as Juspay/IBMB
    participant B as Bank/UPI
    
    M->>J: POST /transaction/initiate<br/>(upiTxnType: COLLECT)
    J->>B: Send Collect Request
    B->>C: Push Notification
    C->>B: Approve Payment
    B->>J: Payment Confirmation
    J->>M: Webhook: order.charged
    M->>J: GET /transaction/status
    J-->>M: Transaction Details
            """
        },
        "mandate_creation": {
            "title": "Mandate Creation Flow",
            "description": "UPI Autopay mandate setup flow",
            "diagram": """
sequenceDiagram
    participant C as Customer
    participant M as Merchant
    participant J as Juspay/IBMB
    participant B as NPCI/Bank
    
    M->>J: POST /mandate/create
    J-->>M: Mandate Auth URL
    M->>C: Redirect for Authorization
    C->>J: Authenticate Mandate
    J->>B: Register Mandate
    B-->>J: Mandate Approved
    J->>M: Webhook: mandate.activated
            """
        },
        "refund_flow": {
            "title": "Refund Processing Flow",
            "description": "Complete refund processing flow",
            "diagram": """
sequenceDiagram
    participant C as Customer
    participant M as Merchant
    participant J as Juspay/IBMB
    participant B as Bank
    
    C->>M: Request Refund
    M->>J: POST /refund
    J->>B: Initiate Refund
    B-->>J: Refund Accepted
    J-->>M: Refund Created (PENDING)
    B->>B: Process Refund
    B->>J: Refund Complete
    J->>M: Webhook: refund.processed
    M->>C: Refund Completed
            """
        },
        "state_machine": {
            "title": "Transaction State Machine",
            "description": "Transaction state transitions",
            "diagram": """
stateDiagram-v2
    [*] --> INITIATED: transaction.init
    INITIATED --> PENDING: Payment Started
    PENDING --> SUCCESS: Payment Complete
    PENDING --> FAILED: Payment Failed
    SUCCESS --> [*]
    FAILED --> [*]
    
    note right of INITIATED
        Intent URL generated
        Customer redirected
    end note
    
    note right of SUCCESS
        Webhook sent
        Fulfill order
    end note
            """
        }
    }
    
    def generate_flow_diagram(self, flow_type: str, include_timings: bool = False) -> Dict[str, Any]:
        """Generate a Mermaid diagram for a flow type."""
        
        template = self.FLOW_TEMPLATES.get(flow_type)
        if not template:
            # Try to generate dynamically
            return self._generate_dynamic_flow(flow_type)
        
        diagram = template["diagram"]
        
        if include_timings:
            diagram = self._add_timing_annotations(diagram)
        
        return {
            "title": template["title"],
            "description": template["description"],
            "mermaid_code": diagram.strip(),
            "rendered_url": f"https://mermaid.live/edit#pako:{self._encode_diagram(diagram)}",
            "embed_code": f"```mermaid\n{diagram.strip()}\n```"
        }
    
    def _generate_dynamic_flow(self, endpoint_id: str) -> Dict[str, Any]:
        """Generate a flow diagram dynamically for an endpoint."""
        # Map endpoint to flow
        flow_mapping = {
            "ibmb.merchant.transaction.init": "payment_standard",
            "ibmb.merchant.transaction.status": "payment_standard"
        }
        
        mapped_flow = flow_mapping.get(endpoint_id)
        if mapped_flow:
            return self.generate_flow_diagram(mapped_flow)
        
        # Generate generic flow
        return {
            "title": f"Flow for {endpoint_id}",
            "description": "Generic API flow",
            "mermaid_code": f"""
sequenceDiagram
    participant M as Merchant
    participant API as IBMB API
    
    M->>API: POST {endpoint_id}
    API-->>M: Response
            """.strip(),
            "rendered_url": None,
            "embed_code": None
        }
    
    def _add_timing_annotations(self, diagram: str) -> str:
        """Add timing annotations to a diagram."""
        # This is a simplified version - in practice would parse and modify AST
        return diagram + "\n    %% Timing: ~2-5 seconds for webhook delivery"
    
    def _encode_diagram(self, diagram: str) -> str:
        """Encode diagram for Mermaid Live URL."""
        import base64
        compressed = base64.b64encode(diagram.encode()).decode()
        return compressed[:50]  # Truncated for demo
    
    def generate_decision_tree(self, flow_type: str) -> str:
        """Generate a decision tree for error handling."""
        
        trees = {
            "payment_error": """
flowchart TD
    A[Payment Initiated] --> B{Response Status}
    B -->|200 SUCCESS| C[Redirect Customer]
    B -->|400 Validation Error| D[Check Payload]
    B -->|401 Unauthorized| E[Check API Key]
    B -->|429 Rate Limited| F[Retry with Backoff]
    B -->|500 Server Error| G[Retry Immediately]
    
    C --> H{Webhook Received?}
    H -->|Yes| I[Process Payment]
    H -->|No after 5min| J[Mark as Timeout]
    
    D --> K[Fix Fields & Retry]
    E --> L[Update Credentials]
    F --> M[Wait & Retry]
    G --> N[Alert Ops Team]
            """,
            "webhook_error": """
flowchart TD
    A[Webhook Received] --> B{Signature Valid?}
    B -->|Yes| C{Known Event?}
    B -->|No| D[Reject 401]
    
    C -->|Yes| E[Process Event]
    C -->|No| F[Log Unknown]
    
    E --> G{Processing Success?}
    G -->|Yes| H[Return 200]
    G -->|No| I[Retry Later]
    
    D --> J[Alert Security]
    F --> K[Review Event Type]
    I --> L[Dead Letter Queue]
            """
        }
        
        return trees.get(flow_type, "%% No decision tree available")


class OnboardingWizard:
    """Interactive onboarding wizard for new merchants."""
    
    def __init__(self):
        self.steps = [
            "account_setup",
            "environment_config",
            "first_api_call",
            "webhook_setup",
            "testing",
            "go_live"
        ]
    
    def get_current_step(self, merchant_id: str, completed_steps: List[str]) -> Dict[str, Any]:
        """Determine current onboarding step for a merchant."""
        
        for step in self.steps:
            if step not in completed_steps:
                return self._get_step_details(step)
        
        return {
            "step": "complete",
            "message": "🎉 Onboarding complete! You're ready for production."
        }
    
    def _get_step_details(self, step: str) -> Dict[str, Any]:
        """Get details for a specific onboarding step."""
        
        details = {
            "account_setup": {
                "title": "Account Setup",
                "description": "Complete your merchant account setup",
                "tasks": [
                    "Verify email address",
                    "Complete KYC documentation",
                    "Set up two-factor authentication"
                ],
                "next_actions": [
                    "Go to dashboard to upload KYC documents",
                    "Configure notification preferences"
                ]
            },
            "environment_config": {
                "title": "Environment Configuration",
                "description": "Set up your development environment",
                "tasks": [
                    "Generate sandbox API keys",
                    "Configure webhook endpoint (ngrok for local)",
                    "Install SDK or set up HTTP client"
                ],
                "next_actions": [
                    "Use test_sandbox tool to verify connectivity",
                    "Run first test transaction"
                ]
            },
            "first_api_call": {
                "title": "First API Call",
                "description": "Make your first API call successfully",
                "tasks": [
                    "Generate test payload",
                    "Call transaction.init endpoint",
                    "Verify response structure"
                ],
                "next_actions": [
                    "Use generate_payload tool for sample data",
                    "Validate payload before sending"
                ]
            },
            "webhook_setup": {
                "title": "Webhook Setup",
                "description": "Configure webhook handling",
                "tasks": [
                    "Create webhook endpoint",
                    "Implement signature verification",
                    "Test webhook delivery"
                ],
                "next_actions": [
                    "Use get_webhook_handler for code template",
                    "Use diagnose_webhook to troubleshoot"
                ]
            },
            "testing": {
                "title": "Integration Testing",
                "description": "Complete full integration test suite",
                "tasks": [
                    "Run happy path test scenarios",
                    "Test error handling",
                    "Verify webhook processing"
                ],
                "next_actions": [
                    "Use generate_test_suite for test cases",
                    "Use run_integration_check for validation"
                ]
            },
            "go_live": {
                "title": "Go Live",
                "description": "Prepare for production deployment",
                "tasks": [
                    "Switch to production credentials",
                    "Configure production webhooks",
                    "Set up monitoring and alerts"
                ],
                "next_actions": [
                    "Run final integration check",
                    "Review security checklist"
                ]
            }
        }
        
        return {
            "step": step,
            **details.get(step, {})
        }
    
    def estimate_completion(self, completed_steps: List[str]) -> Dict[str, Any]:
        """Estimate time to complete onboarding."""
        
        step_times = {
            "account_setup": 30,
            "environment_config": 20,
            "first_api_call": 30,
            "webhook_setup": 45,
            "testing": 60,
            "go_live": 30
        }
        
        remaining = [s for s in self.steps if s not in completed_steps]
        total_minutes = sum(step_times.get(s, 30) for s in remaining)
        
        progress = len(completed_steps) / len(self.steps)
        
        return {
            "completed_steps": len(completed_steps),
            "total_steps": len(self.steps),
            "progress_percent": round(progress * 100),
            "remaining_steps": remaining,
            "estimated_minutes_remaining": total_minutes,
            "estimated_completion": f"~{total_minutes} minutes" if total_minutes < 60 else f"~{total_minutes // 60}h {total_minutes % 60}m"
        }


# ===== MCP Tool Functions =====

async def get_interactive_guide(
    use_case: str,
    role: str = "backend_developer",
    tech_stack: str = "python_fastapi",
    experience_level: str = "intermediate",
    step_number: int = None
) -> dict:
    """
    Get personalized, step-by-step integration guide.
    
    Args:
        use_case: Integration use case (upi_payment, mandate_setup, refund_processing)
        role: Your role (backend_developer, frontend_developer, fullstack_developer, devops_engineer)
        tech_stack: Your technology stack (nodejs_express, python_fastapi, python_flask, python_django, java_spring, go, php)
        experience_level: Your experience level (beginner, intermediate, advanced)
        step_number: Specific step to view (None for full guide)
    
    Returns:
        Interactive guide with code examples, commands, and FAQs
    """
    
    try:
        role_enum = UserRole(role)
        stack_enum = TechStack(tech_stack)
        exp_enum = ExperienceLevel(experience_level)
    except ValueError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ Invalid parameter: {e}\n\nValid options:\nRoles: {[r.value for r in UserRole]}\nStacks: {[s.value for s in TechStack]}\nLevels: {[e.value for e in ExperienceLevel]}"
            }],
            "isError": True
        }
    
    engine = InteractiveGuideEngine()
    
    try:
        guide = engine.generate_guide(use_case, role_enum, stack_enum, exp_enum)
    except ValueError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"❌ {e}\n\nAvailable use cases: {list(engine.USE_CASE_TEMPLATES.keys())}"
            }],
            "isError": True
        }
    
    # Build response
    sections = [
        f"# {guide.title}",
        f"\n{guide.description}",
        f"\n**For:** {guide.role.value.replace('_', ' ').title()}",
        f"**Stack:** {guide.tech_stack.value.replace('_', ' ').title()}",
        f"**Level:** {guide.experience_level.value.title()}",
        f"**Total Time:** ~{guide.total_estimated_minutes} minutes",
    ]
    
    # Prerequisites
    sections.append(f"\n## 📋 Prerequisites")
    for prereq in guide.prerequisites:
        sections.append(f"- [ ] {prereq}")
    
    # Steps
    steps_to_show = [guide.steps[step_number - 1]] if step_number else guide.steps
    
    for step in steps_to_show:
        sections.append(f"\n---\n")
        sections.append(f"## Step {step.step_number}: {step.title}")
        sections.append(f"⏱️ {step.estimated_minutes} min | Difficulty: {step.difficulty.title()}")
        sections.append(f"\n{step.description}")
        
        # Objectives
        if step.objectives:
            sections.append(f"\n### Learning Objectives")
            for obj in step.objectives:
                sections.append(f"- {obj}")
        
        # Commands
        if step.commands:
            sections.append(f"\n### Commands")
            sections.append("```bash")
            for cmd in step.commands:
                sections.append(cmd)
            sections.append("```")
        
        # Code examples
        if step.code_examples:
            sections.append(f"\n### Code Examples")
            for name, code in step.code_examples.items():
                sections.append(f"\n**{name.replace('_', ' ').title()}:**")
                sections.append(f"```{tech_stack.split('_')[0] if '_' in tech_stack else tech_stack}")
                sections.append(code.strip())
                sections.append("```")
        
        # Validation
        if step.validation_checks:
            sections.append(f"\n### ✅ Validation Checklist")
            for check in step.validation_checks:
                sections.append(f"- [ ] {check}")
        
        # FAQ
        if step.faq:
            sections.append(f"\n### ❓ FAQ")
            for faq in step.faq:
                sections.append(f"\n**Q: {faq['question']}**")
                sections.append(f"A: {faq['answer']}")
        
        # Next step hint
        if step.next_step_hint:
            sections.append(f"\n👉 **Next:** {step.next_step_hint}")
    
    # Completion criteria
    sections.append(f"\n---\n")
    sections.append(f"## 🎯 Completion Criteria")
    for criterion in guide.completion_criteria:
        sections.append(f"- [ ] {criterion}")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "guide_metadata": {
            "use_case": use_case,
            "role": role,
            "tech_stack": tech_stack,
            "experience_level": experience_level,
            "total_steps": len(guide.steps),
            "total_minutes": guide.total_estimated_minutes
        }
    }


async def generate_flow_diagram(
    flow_type: str,
    format: str = "mermaid",
    include_timings: bool = False
) -> dict:
    """
    Generate visual API flow diagram.
    
    Args:
        flow_type: Type of flow (payment_standard, payment_collect, mandate_creation, refund_flow, state_machine)
        format: Output format - 'mermaid', 'svg', 'png', 'embed'
        include_timings: Include timing annotations on the diagram
    
    Returns:
        Mermaid diagram code and rendering links
    """
    
    generator = MermaidFlowGenerator()
    result = generator.generate_flow_diagram(flow_type, include_timings)
    
    sections = [
        f"# {result['title']}",
        f"\n{result['description']}"
    ]
    
    if format == "mermaid":
        sections.append(f"\n## Mermaid Code")
        sections.append(result['embed_code'])
    
    elif format == "embed":
        sections.append(f"\n## Embed Code")
        sections.append("Copy this into Markdown:")
        sections.append(result['embed_code'])
    
    sections.append(f"\n## 🔗 Live Editor")
    if result.get('rendered_url'):
        sections.append(f"[Open in Mermaid Live Editor]({result['rendered_url']})")
    else:
        sections.append("Copy the Mermaid code above to https://mermaid.live")
    
    # Rendered preview description
    sections.append(f"\n## 📊 Diagram Preview")
    sections.append("The diagram shows the interaction between:")
    
    if "payment" in flow_type:
        sections.append("- Customer (end user)")
        sections.append("- Merchant Server (your backend)")
        sections.append("- Juspay/IBMB (payment processor)")
        sections.append("- UPI App (Google Pay, PhonePe, etc.)")
    elif "mandate" in flow_type:
        sections.append("- Customer")
        sections.append("- Merchant")
        sections.append("- Juspay/IBMB")
        sections.append("- NPCI/Bank")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "diagram": {
            "title": result['title'],
            "mermaid_code": result['mermaid_code'],
            "live_editor_url": result.get('rendered_url'),
            "embed_code": result['embed_code']
        }
    }


async def generate_error_decision_tree(
    flow_type: str = "payment"
) -> dict:
    """
    Generate decision tree for error handling.
    
    Args:
        flow_type: Type of flow ('payment', 'webhook')
    
    Returns:
        Decision tree diagram and error handling guide
    """
    
    generator = MermaidFlowGenerator()
    
    tree_key = f"{flow_type}_error"
    diagram = generator.generate_decision_tree(tree_key)
    
    sections = [
        f"# Error Handling Decision Tree: {flow_type.title()}",
        f"\n```mermaid\n{diagram}\n```"
    ]
    
    # Add explanation
    sections.append(f"\n## How to Use This Tree")
    sections.append("1. Start from the top with the trigger event")
    sections.append("2. Follow the arrows based on your situation")
    sections.append("3. Take the action at the final node")
    
    if flow_type == "payment":
        sections.append(f"\n## Common Error Responses")
        sections.append("| HTTP Status | Meaning | Action |")
        sections.append("|------------|---------|--------|")
        sections.append("| 400 | Bad Request | Check request payload |")
        sections.append("| 401 | Unauthorized | Verify API key |")
        sections.append("| 429 | Rate Limited | Implement backoff |")
        sections.append("| 500 | Server Error | Retry or contact support |")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "decision_tree": diagram
    }


async def get_onboarding_wizard(
    merchant_id: str,
    completed_steps: list = None
) -> dict:
    """
    Get personalized onboarding wizard with current step and progress.
    
    Args:
        merchant_id: Your merchant identifier
        completed_steps: List of steps already completed
                       (account_setup, environment_config, first_api_call, webhook_setup, testing, go_live)
    
    Returns:
        Current step details, progress, and recommended next actions
    """
    
    wizard = OnboardingWizard()
    completed = completed_steps or []
    
    current = wizard.get_current_step(merchant_id, completed)
    progress = wizard.estimate_completion(completed)
    
    sections = [
        f"# 🚀 Onboarding Wizard",
        f"\n**Progress:** {progress['progress_percent']}% ({progress['completed_steps']}/{progress['total_steps']} steps)",
        f"**Estimated Time Remaining:** {progress['estimated_completion']}"
    ]
    
    # Progress bar
    filled = "█" * (progress['progress_percent'] // 10)
    empty = "░" * (10 - progress['progress_percent'] // 10)
    sections.append(f"\n[{filled}{empty}] {progress['progress_percent']}%")
    
    if current.get('step') == "complete":
        sections.append(f"\n## 🎉 {current['message']}")
    else:
        sections.append(f"\n## Current Step: {current['title']}")
        sections.append(f"\n{current.get('description', '')}")
        
        # Tasks
        if current.get('tasks'):
            sections.append(f"\n### Tasks to Complete")
            for task in current['tasks']:
                sections.append(f"- [ ] {task}")
        
        # Next actions
        if current.get('next_actions'):
            sections.append(f"\n### Recommended Next Actions")
            for i, action in enumerate(current['next_actions'], 1):
                sections.append(f"{i}. {action}")
    
    # Remaining steps overview
    if progress['remaining_steps']:
        sections.append(f"\n---\n")
        sections.append(f"### Remaining Steps")
        for step in progress['remaining_steps']:
            step_details = wizard._get_step_details(step)
            sections.append(f"- {step_details.get('title', step)}")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "onboarding": {
            "merchant_id": merchant_id,
            "current_step": current.get('step'),
            "progress_percent": progress['progress_percent'],
            "completed_steps": completed,
            "remaining_steps": progress['remaining_steps'],
            "estimated_completion": progress['estimated_completion']
        }
    }


async def get_step_by_step_walkthrough(
    endpoint_id: str,
    action: str = "overview"
) -> dict:
    """
    Get step-by-step walkthrough for a specific API endpoint.
    
    Args:
        endpoint_id: API endpoint (e.g., 'ibmb.merchant.transaction.init')
        action: What you want to do - 'overview', 'generate_payload', 'handle_response', 'troubleshoot'
    
    Returns:
        Detailed walkthrough with examples for the specific action
    """
    
    walkthroughs = {
        "ibmb.merchant.transaction.init": {
            "overview": {
                "title": "Transaction Initiation Overview",
                "steps": [
                    "Generate a unique merchantRequestId",
                    "Construct the request payload with payee/payer details",
                    "Set amount (in paise) and currency",
                    "Choose upiTxnType: COLLECT or PAY",
                    "Add optional fields like description, additionalInfo",
                    "Send POST request to /api/merchants/v1/transaction/initiate",
                    "Handle SUCCESS response - save merchantRequestId and intent URL",
                    "Handle FAILURE response - check error code and retry if needed"
                ],
                "key_points": [
                    "merchantRequestId must be unique per transaction",
                    "Amount is in smallest currency unit (paise for INR)",
                    "Intent URL expires after intentExpiry seconds (default 300)",
                    "Always save merchantRequestId for status checks"
                ]
            },
            "generate_payload": {
                "title": "Generating Transaction Payload",
                "example": """{
  \"payeeVpaHandle\": \"merchant@juspay\",
  \"payeeName\": \"My Store\",
  \"payerVpaHandle\": \"customer@upi\",
  \"amount\": \"1000.00\",
  \"currency\": \"INR\",
  \"merchantRequestId\": \"ORDER_123456\",
  \"merchantId\": \"MERCHANT001\",
  \"upiTxnType\": \"COLLECT\",
  \"description\": \"Payment for Order #123456\"
}""",
                "field_explanations": {
                    "payeeVpaHandle": "Merchant's VPA where money will be received",
                    "payerVpaHandle": "Customer's VPA (for COLLECT) or destination VPA (for PAY)",
                    "amount": "Amount in decimal format (1000.00 = ₹1000)",
                    "merchantRequestId": "Your unique identifier for this transaction",
                    "upiTxnType": "COLLECT (request money) or PAY (send money)"
                }
            },
            "handle_response": {
                "title": "Handling Transaction Response",
                "success_response": """{
  \"result\": \"SUCCESS\",
  \"responseCode\": \"SUCCESS\",
  \"responseMessage\": \"Transaction initiated\",
  \"payload\": {
    \"merchantRequestId\": \"ORDER_123456\",
    \"intentExpiry\": \"300\",
    \"url\": \"upi://pay?pa=...\"
  }
}""",
                "actions": [
                    "Save merchantRequestId to your database",
                    "For COLLECT: Display QR code or prompt user to check UPI app",
                    "For PAY: Redirect user to intent URL (or deep link)",
                    "Start polling for status or wait for webhook"
                ]
            },
            "troubleshoot": {
                "title": "Troubleshooting Transaction Init",
                "common_issues": [
                    {
                        "symptom": "Error: INVALID_VPA_FORMAT",
                        "cause": "VPA doesn't match expected format (user@provider)",
                        "fix": "Validate VPA format before sending"
                    },
                    {
                        "symptom": "Error: DUPLICATE_REQUEST_ID",
                        "cause": "merchantRequestId was used before",
                        "fix": "Generate new unique request ID"
                    },
                    {
                        "symptom": "Response missing 'url' field",
                        "cause": "Transaction type might not require intent URL",
                        "fix": "Check upiTxnType is correct"
                    }
                ]
            }
        }
    }
    
    endpoint_walkthrough = walkthroughs.get(endpoint_id)
    if not endpoint_walkthrough:
        return {
            "content": [{
                "type": "text",
                "text": f"Walkthrough not available for {endpoint_id}.\n\nTry: get_api_spec('{endpoint_id}') for documentation."
            }],
            "isError": True
        }
    
    action_content = endpoint_walkthrough.get(action)
    if not action_content:
        available = list(endpoint_walkthrough.keys())
        return {
            "content": [{
                "type": "text",
                "text": f"Action '{action}' not available. Choose from: {available}"
            }],
            "isError": True
        }
    
    sections = [f"# {action_content['title']}"]
    
    if 'steps' in action_content:
        sections.append(f"\n## Steps")
        for i, step in enumerate(action_content['steps'], 1):
            sections.append(f"{i}. {step}")
    
    if 'key_points' in action_content:
        sections.append(f"\n## Key Points")
        for point in action_content['key_points']:
            sections.append(f"- {point}")
    
    if 'example' in action_content:
        sections.append(f"\n## Example")
        sections.append(f"```json\n{action_content['example']}\n```")
    
    if 'field_explanations' in action_content:
        sections.append(f"\n## Field Explanations")
        for field, explanation in action_content['field_explanations'].items():
            sections.append(f"- **{field}:** {explanation}")
    
    if 'success_response' in action_content:
        sections.append(f"\n## Success Response")
        sections.append(f"```json\n{action_content['success_response']}\n```")
    
    if 'actions' in action_content:
        sections.append(f"\n## Next Actions")
        for action_item in action_content['actions']:
            sections.append(f"- {action_item}")
    
    if 'common_issues' in action_content:
        sections.append(f"\n## Common Issues")
        for issue in action_content['common_issues']:
            sections.append(f"\n### {issue['symptom']}")
            sections.append(f"**Cause:** {issue['cause']}")
            sections.append(f"**Fix:** {issue['fix']}")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "endpoint": endpoint_id,
        "action": action
    }


async def explain_concept(
    concept: str,
    depth: str = "overview"
) -> dict:
    """
    Explain payment integration concepts in detail.
    
    Args:
        concept: Concept to explain (idempotency, webhooks, upi_intent, signature_verification, etc.)
        depth: Detail level - 'overview', 'technical', 'implementation'
    
    Returns:
        Detailed explanation with examples
    """
    
    concepts = {
        "idempotency": {
            "title": "Idempotency in Payment APIs",
            "overview": "Idempotency ensures that making the same API call multiple times has the same effect as making it once. This prevents duplicate transactions.",
            "technical": """
Idempotency is achieved through the merchantRequestId field. When you send a request:

1. First call: Transaction is created and processed
2. Duplicate call (same merchantRequestId): Returns the same response as first call

This is crucial because:
- Networks are unreliable (retries may happen)
- Users may double-click buttons
- Your server might crash mid-request

The system recognizes duplicates and returns cached responses.""",
            "implementation": """
Implementation best practices:

1. Generate unique IDs:
   ```python
   import uuid
   merchant_request_id = f"ORDER_{uuid.uuid4().hex[:12]}"
   ```

2. Store mapping:
   ```python
   # Save to database
   db.save_transaction(
       order_id=order_id,
       merchant_request_id=merchant_request_id,
       status="pending"
   )
   ```

3. Handle duplicate responses:
   ```python
   if response.get("result") == "SUCCESS":
       if db.is_duplicate(merchant_request_id):
           # Use existing transaction
           pass
   ```

4. Retry safely:
   ```python
   for attempt in range(3):
       try:
           response = api.create_transaction(payload)
           break
       except TimeoutError:
           continue  # Same ID, safe to retry
   ```"""
        },
        "webhooks": {
            "title": "Understanding Webhooks",
            "overview": "Webhooks are HTTP callbacks sent by Juspay to your server when events occur (payment complete, refund processed, etc.).",
            "technical": """
Webhook flow:
1. Event occurs (e.g., payment succeeds)
2. Juspay sends POST request to your webhook URL
3. Your server processes the event
4. Your server returns HTTP 200

Key characteristics:
- Asynchronous (don't block on them)
- At-least-once delivery (may be duplicated)
- Must be acknowledged within 5 seconds
- Include signature for verification""",
            "implementation": """
Setting up webhooks:

1. Create endpoint:
   ```python
   @app.route("/webhook", methods=["POST"])
   def webhook():
       # Verify signature
       # Process event
       return "OK", 200
   ```

2. Configure in dashboard:
   - URL: https://yourdomain.com/webhook
   - Events: Select needed events
   - Secret: Copy verification secret

3. Handle events:
   ```python
   event_type = request.json.get("event")
   
   if event_type == "order.charged":
       fulfill_order(request.json)
   elif event_type == "refund.processed":
       process_refund(request.json)
   ```

4. Retry logic:
   - Juspay retries on non-2xx responses
   - Exponential backoff: 1s, 2s, 4s, 8s...
   - Max retries: ~10 over ~24 hours"""
        },
        "signature_verification": {
            "title": "Webhook Signature Verification",
            "overview": "Signatures ensure webhooks came from Juspay and weren't tampered with. Always verify signatures before processing.",
            "technical": """
Signature mechanism:
1. Juspay computes HMAC-SHA256 of request body using shared secret
2. Sends signature in X-Juspay-Signature header
3. Your server recomputes signature and compares

Security properties:
- Authenticity: Only Juspay can generate valid signatures
- Integrity: Tampered payloads will fail verification
- Non-repudiation: Proof webhook came from Juspay

Always use constant-time comparison to prevent timing attacks.""",
            "implementation": """
Verification implementation:

Python:
```python
import hmac
import hashlib

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

def verify_signature(body, signature):
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body if isinstance(body, bytes) else body.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)
```

Node.js:
```javascript
const crypto = require('crypto');

function verifySignature(body, signature) {
    const expected = crypto
        .createHmac('sha256', process.env.WEBHOOK_SECRET)
        .update(body)
        .digest('hex');
    
    return crypto.timingSafeEqual(
        Buffer.from(signature),
        Buffer.from(expected)
    );
}
```

Important: Use raw body, not parsed JSON!"""
        }
    }
    
    concept_data = concepts.get(concept)
    if not concept_data:
        available = list(concepts.keys())
        return {
            "content": [{
                "type": "text",
                "text": f"Concept '{concept}' not found.\n\nAvailable concepts: {available}"
            }],
            "isError": True
        }
    
    sections = [f"# {concept_data['title']}"]
    
    if depth == "overview" and 'overview' in concept_data:
        sections.append(f"\n{concept_data['overview']}")
    elif depth == "technical" and 'technical' in concept_data:
        sections.append(f"\n{concept_data['technical']}")
    elif depth == "implementation" and 'implementation' in concept_data:
        sections.append(f"\n{concept_data['implementation']}")
    else:
        # Show all depths
        if 'overview' in concept_data:
            sections.append(f"\n## Overview\n{concept_data['overview']}")
        if 'technical' in concept_data:
            sections.append(f"\n## Technical Details\n{concept_data['technical']}")
        if 'implementation' in concept_data:
            sections.append(f"\n## Implementation Guide\n{concept_data['implementation']}")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "concept": concept,
        "depth": depth
    }
