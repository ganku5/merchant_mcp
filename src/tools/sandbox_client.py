"""
Sandbox Client for Real API Testing

Enables actual sandbox API calls with merchant credentials
for realistic testing scenarios.
"""

import json
import asyncio
import aiohttp
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class SandboxMode(Enum):
    """Sandbox operation modes."""
    MOCK = "mock"          # Fast mock responses
    SANDBOX = "sandbox"    # Real sandbox API calls
    RECORD = "record"      # Record real responses for replay


@dataclass
class SandboxConfig:
    """Configuration for sandbox testing."""
    base_url: str = "https://sandbox-api.ibmb.example.com"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    merchant_id: Optional[str] = None
    timeout: int = 30
    mode: SandboxMode = SandboxMode.SANDBOX
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class TestResult:
    """Result of a sandbox test."""
    success: bool
    status_code: int
    request: Dict[str, Any]
    response: Dict[str, Any]
    latency_ms: float
    timestamp: str
    annotations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class SandboxClient:
    """Client for sandbox API testing."""
    
    # Mock responses for development/testing
    MOCK_RESPONSES = {
        "ibmb.merchant.transaction.init": {
            "result": "SUCCESS",
            "responseCode": "SUCCESS",
            "responseMessage": "Transaction initiated successfully",
            "payload": {
                "merchantRequestId": "20240901234ABCDE5678",
                "intentExpiry": "300",
                "amount": "1000.00",
                "currency": "INR",
                "url": "nb://pay?ver=1.0&mode=INTENT&..."
            }
        },
        "ibmb.merchant.transaction.status": {
            "result": "SUCCESS",
            "responseCode": "SUCCESS",
            "txnStatus": "PENDING",
            "txnResponseCode": "PENDING",
            "txnResponseMessage": "Transaction is being processed",
            "amount": "1000.00",
            "currency": "INR",
            "transactionId": "TXNBANK987654321"
        }
    }
    
    # Transaction state machine for status simulation
    TRANSACTION_STATES = {
        "INITIATED": ["PENDING"],
        "PENDING": ["SUCCESS", "FAILED"],
        "SUCCESS": [],
        "FAILED": []
    }
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self._transaction_states: Dict[str, str] = {}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(
        self,
        endpoint_id: str,
        payload: Dict[str, Any],
        annotate: bool = True
    ) -> TestResult:
        """
        Test an endpoint in sandbox.
        
        Args:
            endpoint_id: API endpoint to test
            payload: Request payload
            annotate: Add field-level annotations
        
        Returns:
            Detailed test result with annotations
        """
        start_time = time.time()
        
        if self.config.mode == SandboxMode.MOCK:
            response = await self._mock_call(endpoint_id, payload)
            status_code = 200
        else:
            response, status_code = await self._real_call(endpoint_id, payload)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Build result
        result = TestResult(
            success=status_code < 400,
            status_code=status_code,
            request={
                "endpoint": endpoint_id,
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat()
            },
            response=response,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Add annotations
        if annotate:
            result.annotations = self._annotate_response(endpoint_id, response)
            result.warnings = self._check_warnings(endpoint_id, payload, response)
            result.errors = self._check_errors(endpoint_id, payload, response)
        
        return result
    
    async def _mock_call(
        self,
        endpoint_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate mock response."""
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        base_response = self.MOCK_RESPONSES.get(endpoint_id, {
            "result": "SUCCESS",
            "responseCode": "SUCCESS"
        }).copy()
        
        # Merge with request data for realism
        if "payload" in base_response and payload:
            base_response["payload"].update({
                k: v for k, v in payload.items()
                if k in base_response["payload"]
            })
        
        return base_response
    
    async def _real_call(
        self,
        endpoint_id: str,
        payload: Dict[str, Any]
    ) -> tuple[Dict[str, Any], int]:
        """Make real API call to sandbox."""
        # Map endpoint_id to URL path
        path_map = {
            "ibmb.merchant.transaction.init": "/api/merchants/v1/transaction/initiate",
            "ibmb.merchant.transaction.status": "/api/merchants/v1/transaction/status"
        }
        
        path = path_map.get(endpoint_id)
        if not path:
            return {"error": "Endpoint not mapped for sandbox"}, 404
        
        url = f"{self.config.base_url}{path}"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.config.api_key or "",
            "X-Merchant-ID": self.config.merchant_id or ""
        }
        
        # Retry logic
        for attempt in range(self.config.max_retries):
            try:
                async with self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout
                ) as resp:
                    response_data = await resp.json()
                    return response_data, resp.status
                    
            except asyncio.TimeoutError:
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    return {"error": "Request timeout"}, 504
                    
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    return {"error": str(e)}, 500
        
        return {"error": "Max retries exceeded"}, 503
    
    def _annotate_response(
        self,
        endpoint_id: str,
        response: Dict[str, Any]
    ) -> List[str]:
        """Add field-level annotations to response."""
        annotations = []
        
        if endpoint_id == "ibmb.merchant.transaction.init":
            if response.get("result") == "SUCCESS":
                annotations.append(
                    "✅ Transaction initiated. Save 'merchantRequestId' for status checks."
                )
                
                payload = response.get("payload", {})
                if "url" in payload:
                    annotations.append(
                        f"🔗 Deeplink URL generated: {payload['url'][:50]}..."
                    )
                    annotations.append(
                        "⏰ Intent expires in " + payload.get('intentExpiry', '300') + " seconds"
                    )
        
        elif endpoint_id == "ibmb.merchant.transaction.status":
            status = response.get("txnStatus")
            if status == "PENDING":
                annotations.append(
                    "⏳ Transaction still processing. Poll again in 5-10 seconds."
                )
            elif status == "SUCCESS":
                annotations.append(
                    "✅ Transaction completed. Save 'transactionId' for reconciliation."
                )
            elif status == "FAILED":
                annotations.append(
                    f"❌ Transaction failed: {response.get('txnResponseMessage')}"
                )
        
        return annotations
    
    def _check_warnings(
        self,
        endpoint_id: str,
        payload: Dict[str, Any],
        response: Dict[str, Any]
    ) -> List[str]:
        """Check for warnings."""
        warnings = []
        
        # Check latency
        if hasattr(response, 'latency_ms') and response.latency_ms > 2000:
            warnings.append(
                f"⚠️ High latency detected ({response.latency_ms:.0f}ms). Consider optimizing."
            )
        
        # Check for missing optional fields that might help
        if endpoint_id == "ibmb.merchant.transaction.init":
            if not payload.get("additionalInfo"):
                warnings.append(
                    "💡 Consider adding 'additionalInfo' for merchant-defined metadata."
                )
        
        return warnings
    
    def _check_errors(
        self,
        endpoint_id: str,
        payload: Dict[str, Any],
        response: Dict[str, Any]
    ) -> List[str]:
        """Check for errors."""
        errors = []
        
        result = response.get("result", "")
        if result == "FAILURE":
            error_code = response.get("responseCode", "UNKNOWN")
            error_msg = response.get("responseMessage", "Unknown error")
            errors.append(f"❌ API Error {error_code}: {error_msg}")
        
        return errors
    
    async def run_test_suite(
        self,
        endpoint_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> List[TestResult]:
        """Run multiple test cases for an endpoint."""
        results = []
        
        for test_case in test_cases:
            result = await self.test_endpoint(
                endpoint_id,
                test_case.get("payload", {})
            )
            results.append(result)
        
        return results
    
    def format_result(self, result: TestResult) -> str:
        """Format test result for display."""
        sections = [
            f"## Test Result: {'✅ Success' if result.success else '❌ Failed'}",
            f"**Status Code:** {result.status_code}",
            f"**Latency:** {result.latency_ms:.2f}ms",
            ""
        ]
        
        if result.annotations:
            sections.append("### Annotations")
            for ann in result.annotations:
                sections.append(f"- {ann}")
            sections.append("")
        
        if result.warnings:
            sections.append("### Warnings")
            for warn in result.warnings:
                sections.append(f"- {warn}")
            sections.append("")
        
        if result.errors:
            sections.append("### Errors")
            for err in result.errors:
                sections.append(f"- {err}")
            sections.append("")
        
        sections.extend([
            "### Response",
            f"```json\n{json.dumps(result.response, indent=2)}\n```"
        ])
        
        return "\n".join(sections)


# Convenience functions
async def test_in_sandbox(
    endpoint_id: str,
    payload: Dict[str, Any],
    api_key: Optional[str] = None,
    mode: str = "sandbox"
) -> Dict[str, Any]:
    """Test API call in sandbox with annotations."""
    config = SandboxConfig(
        api_key=api_key,
        mode=SandboxMode(mode) if mode in ["mock", "sandbox", "record"] else SandboxMode.MOCK
    )
    
    async with SandboxClient(config) as client:
        result = await client.test_endpoint(endpoint_id, payload)
        
        formatted = client.format_result(result)
        
        return {
            "content": [{
                "type": "text",
                "text": formatted
            }],
            "isError": not result.success
        }
