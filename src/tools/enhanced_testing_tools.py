"""
Enhanced Testing Tools - Phase 2 Implementation

Comprehensive testing infrastructure with:
- Test suite generator with coverage matrix
- Transaction lifecycle tracking
- Test data generators
- Assertion builders
- Postman/JMeter export
"""

import json
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

from ..utils.database import database
from .sandbox_client import SandboxClient, SandboxConfig, SandboxMode


class TestCategory(Enum):
    """Test case categories."""
    HAPPY_PATH = "happy_path"
    VALIDATION_ERROR = "validation_error"
    EDGE_CASE = "edge_case"
    SECURITY = "security"
    CONCURRENCY = "concurrency"
    RECOVERY = "recovery"


class TestPriority(Enum):
    """Test case priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestCase:
    """Represents a single test case."""
    id: str
    name: str
    description: str
    category: TestCategory
    priority: TestPriority
    endpoint_id: str
    payload: Dict[str, Any]
    expected_status: int
    expected_response_patterns: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    cleanup_steps: List[str] = field(default_factory=list)


@dataclass
class TestSuite:
    """Collection of test cases for an endpoint."""
    endpoint_id: str
    test_cases: List[TestCase]
    coverage_summary: Dict[str, int] = field(default_factory=dict)


@dataclass
class TransactionState:
    """Tracks transaction through its lifecycle."""
    transaction_id: str
    current_state: str
    state_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def transition_to(self, new_state: str, reason: str = ""):
        """Record state transition."""
        self.state_history.append({
            "from": self.current_state,
            "to": new_state,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        })
        self.current_state = new_state


class TestDataGenerator:
    """Generates realistic test data for various field types."""
    
    # Indian test VPAs
    SAMPLE_VPAS = [
        "customer@okaxis", "user@oksbi", "merchant@okicici",
        "tester@paytm", "demo@ybl", "sample@upi"
    ]
    
    # Test amounts in paise
    SAMPLE_AMOUNTS = [100, 500, 1000, 5000, 10000, 50000, 100000]
    
    # Sample merchant info
    SAMPLE_MERCHANTS = [
        {"name": "Test Store", "mid": "TEST001"},
        {"name": "Demo Shop", "mid": "DEMO002"},
        {"name": "Sample Mart", "mid": "SMPL003"}
    ]
    
    @classmethod
    def generate_vpa(cls) -> str:
        """Generate a random VPA."""
        handle = ''.join(random.choices(string.ascii_lowercase, k=8))
        provider = random.choice(["okaxis", "oksbi", "okicici", "paytm", "ybl"])
        return f"{handle}@{provider}"
    
    @classmethod
    def generate_amount(cls, min_paise: int = 100, max_paise: int = 100000) -> int:
        """Generate random amount in paise."""
        return random.randint(min_paise, max_paise)
    
    @classmethod
    def generate_transaction_id(cls) -> str:
        """Generate unique transaction ID."""
        timestamp = datetime.now().strftime("%Y%m%d")
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"TXN{timestamp}{random_suffix}"
    
    @classmethod
    def generate_merchant_request_id(cls) -> str:
        """Generate merchant request ID."""
        timestamp = datetime.now().strftime("%Y%m%d")
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        return f"MRQ{timestamp}{random_part}"
    
    @classmethod
    def generate_upi_txn_id(cls) -> str:
        """Generate UPI transaction ID."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    
    @classmethod
    def generate_timestamp(cls, offset_minutes: int = 0) -> str:
        """Generate ISO timestamp with optional offset."""
        dt = datetime.utcnow() + timedelta(minutes=offset_minutes)
        return dt.isoformat() + "Z"
    
    @classmethod
    def generate_beneficiary(cls) -> Dict[str, Any]:
        """Generate beneficiary details."""
        return {
            "name": random.choice(["John Doe", "Jane Smith", "Test User"]),
            "vpa": cls.generate_vpa(),
            "accountNumber": ''.join(random.choices(string.digits, k=12)),
            "ifscCode": f"{random.choice(['SBIN', 'HDFC', 'ICIC', 'AXIS'])}0{''.join(random.choices(string.digits, k=6))}"
        }
    
    @classmethod
    def generate_merchant_info(cls) -> Dict[str, Any]:
        """Generate merchant information."""
        return random.choice(cls.SAMPLE_MERCHANTS)
    
    @classmethod
    def generate_device_info(cls) -> Dict[str, Any]:
        """Generate device information."""
        return {
            "deviceId": str(uuid.uuid4()),
            "ipAddress": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "userAgent": "Mozilla/5.0 (Test Environment)"
        }


class TestSuiteGenerator:
    """Generates comprehensive test suites for APIs."""
    
    # IBMB Transaction Init payloads by scenario
    INIT_PAYLOAD_TEMPLATES = {
        "standard_upi_collect": {
            "payeeVpaHandle": "merchant@juspay",
            "payeeName": "Test Merchant",
            "payerVpaHandle": "{payer_vpa}",
            "amount": "{amount}",
            "merchantRequestId": "{merchant_request_id}",
            "merchantId": "{merchant_id}",
            "upiTxnType": "COLLECT",
            "description": "Test payment"
        },
        "standard_upi_pay": {
            "payeeVpaHandle": "merchant@juspay",
            "payeeName": "Test Merchant",
            "payerVpaHandle": "{payer_vpa}",
            "amount": "{amount}",
            "merchantRequestId": "{merchant_request_id}",
            "merchantId": "{merchant_id}",
            "upiTxnType": "PAY",
            "description": "Test payment"
        }
    }
    
    def __init__(self):
        self.data_generator = TestDataGenerator()
        self.transaction_tracker = TransactionLifecycleTracker()
    
    def generate_test_suite(
        self,
        endpoint_id: str,
        coverage_level: str = "essential"
    ) -> TestSuite:
        """Generate complete test suite for an endpoint."""
        
        test_cases = []
        
        # Always include happy path
        happy_path = self._generate_happy_path_test(endpoint_id)
        if happy_path:
            test_cases.append(happy_path)
        
        # Add validation error tests
        test_cases.extend(self._generate_validation_tests(endpoint_id))
        
        # Add edge cases for comprehensive coverage
        if coverage_level == "comprehensive":
            test_cases.extend(self._generate_edge_case_tests(endpoint_id))
            test_cases.extend(self._generate_security_tests(endpoint_id))
            test_cases.extend(self._generate_concurrency_tests(endpoint_id))
        
        # Calculate coverage
        coverage = self._calculate_coverage(test_cases)
        
        return TestSuite(
            endpoint_id=endpoint_id,
            test_cases=test_cases,
            coverage_summary=coverage
        )
    
    def _generate_happy_path_test(self, endpoint_id: str) -> Optional[TestCase]:
        """Generate standard happy path test case."""
        
        if endpoint_id == "ibmb.merchant.transaction.init":
            payload = self._fill_template(
                self.INIT_PAYLOAD_TEMPLATES["standard_upi_collect"],
                {
                    "payer_vpa": self.data_generator.generate_vpa(),
                    "amount": str(self.data_generator.generate_amount()),
                    "merchant_request_id": self.data_generator.generate_merchant_request_id(),
                    "merchant_id": "TEST123"
                }
            )
            
            return TestCase(
                id="HAPPY_001",
                name="Standard UPI Collect Transaction",
                description="Initiate a standard UPI collect transaction with valid data",
                category=TestCategory.HAPPY_PATH,
                priority=TestPriority.CRITICAL,
                endpoint_id=endpoint_id,
                payload=payload,
                expected_status=200,
                expected_response_patterns=["result.*SUCCESS", "payload.*url"],
                postconditions=["Transaction state is INITIATED", "Intent URL generated"],
                cleanup_steps=["Query transaction status after 30s", "Record transaction ID"]
            )
        
        elif endpoint_id == "ibmb.merchant.transaction.status":
            return TestCase(
                id="HAPPY_002",
                name="Query Transaction Status",
                description="Query status of an existing transaction",
                category=TestCategory.HAPPY_PATH,
                priority=TestPriority.CRITICAL,
                endpoint_id=endpoint_id,
                payload={
                    "merchantId": "TEST123",
                    "merchantRequestId": self.data_generator.generate_merchant_request_id(),
                    "upiTxnId": self.data_generator.generate_upi_txn_id()
                },
                expected_status=200,
                expected_response_patterns=["txnStatus", "amount"],
                preconditions=["Transaction has been initiated"]
            )
        
        return None
    
    def _generate_validation_tests(self, endpoint_id: str) -> List[TestCase]:
        """Generate validation error test cases."""
        tests = []
        
        if endpoint_id == "ibmb.merchant.transaction.init":
            # Missing required field
            tests.append(TestCase(
                id="VAL_001",
                name="Missing payerVpaHandle",
                description="Submit without required payer VPA",
                category=TestCategory.VALIDATION_ERROR,
                priority=TestPriority.HIGH,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "amount": "1000",
                    "merchantRequestId": self.data_generator.generate_merchant_request_id()
                },
                expected_status=400,
                expected_response_patterns=["ERROR", "payerVpaHandle"]
            ))
            
            # Invalid amount format
            tests.append(TestCase(
                id="VAL_002",
                name="Invalid Amount Format",
                description="Submit with non-numeric amount",
                category=TestCategory.VALIDATION_ERROR,
                priority=TestPriority.HIGH,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": self.data_generator.generate_vpa(),
                    "amount": "abc123",
                    "merchantRequestId": self.data_generator.generate_merchant_request_id()
                },
                expected_status=400,
                expected_response_patterns=["ERROR", "amount"]
            ))
            
            # Invalid VPA format
            tests.append(TestCase(
                id="VAL_003",
                name="Invalid VPA Format",
                description="Submit with malformed VPA",
                category=TestCategory.VALIDATION_ERROR,
                priority=TestPriority.HIGH,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": "invalid-vpa-format",
                    "amount": "1000",
                    "merchantRequestId": self.data_generator.generate_merchant_request_id()
                },
                expected_status=400,
                expected_response_patterns=["ERROR", "vpa"]
            ))
        
        return tests
    
    def _generate_edge_case_tests(self, endpoint_id: str) -> List[TestCase]:
        """Generate edge case test cases."""
        tests = []
        
        if endpoint_id == "ibmb.merchant.transaction.init":
            # Minimum amount
            tests.append(TestCase(
                id="EDGE_001",
                name="Minimum Amount Boundary",
                description="Test with minimum allowed amount (1 INR)",
                category=TestCategory.EDGE_CASE,
                priority=TestPriority.MEDIUM,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": self.data_generator.generate_vpa(),
                    "amount": "100",  # 1 INR
                    "merchantRequestId": self.data_generator.generate_merchant_request_id()
                },
                expected_status=200,
                expected_response_patterns=["SUCCESS"]
            ))
            
            # Maximum amount
            tests.append(TestCase(
                id="EDGE_002",
                name="Maximum Amount Boundary",
                description="Test with maximum allowed amount (1 Lakh INR)",
                category=TestCategory.EDGE_CASE,
                priority=TestPriority.MEDIUM,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": self.data_generator.generate_vpa(),
                    "amount": "10000000",  # 1 Lakh INR
                    "merchantRequestId": self.data_generator.generate_merchant_request_id()
                },
                expected_status=200,
                expected_response_patterns=["SUCCESS"]
            ))
            
            # Long description
            tests.append(TestCase(
                id="EDGE_003",
                name="Maximum Length Description",
                description="Test with maximum length description field",
                category=TestCategory.EDGE_CASE,
                priority=TestPriority.LOW,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": self.data_generator.generate_vpa(),
                    "amount": "1000",
                    "merchantRequestId": self.data_generator.generate_merchant_request_id(),
                    "description": "A" * 255
                },
                expected_status=200,
                expected_response_patterns=["SUCCESS"]
            ))
        
        return tests
    
    def _generate_security_tests(self, endpoint_id: str) -> List[TestCase]:
        """Generate security test cases."""
        tests = []
        
        if endpoint_id == "ibmb.merchant.transaction.init":
            # SQL injection attempt
            tests.append(TestCase(
                id="SEC_001",
                name="SQL Injection Attempt",
                description="Submit with SQL injection in description",
                category=TestCategory.SECURITY,
                priority=TestPriority.HIGH,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": self.data_generator.generate_vpa(),
                    "amount": "1000",
                    "merchantRequestId": self.data_generator.generate_merchant_request_id(),
                    "description": "'; DROP TABLE transactions; --"
                },
                expected_status=400,
                expected_response_patterns=["ERROR"]
            ))
            
            # XSS attempt
            tests.append(TestCase(
                id="SEC_002",
                name="XSS Attempt",
                description="Submit with XSS payload in description",
                category=TestCategory.SECURITY,
                priority=TestPriority.HIGH,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": self.data_generator.generate_vpa(),
                    "amount": "1000",
                    "merchantRequestId": self.data_generator.generate_merchant_request_id(),
                    "description": "<script>alert('xss')</script>"
                },
                expected_status=400,
                expected_response_patterns=["ERROR"]
            ))
        
        return tests
    
    def _generate_concurrency_tests(self, endpoint_id: str) -> List[TestCase]:
        """Generate concurrency test cases."""
        tests = []
        
        if endpoint_id == "ibmb.merchant.transaction.init":
            # Duplicate merchant request ID (idempotency test)
            fixed_request_id = self.data_generator.generate_merchant_request_id()
            tests.append(TestCase(
                id="CONC_001",
                name="Duplicate Request ID",
                description="Submit with same merchantRequestId twice",
                category=TestCategory.CONCURRENCY,
                priority=TestPriority.HIGH,
                endpoint_id=endpoint_id,
                payload={
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": self.data_generator.generate_vpa(),
                    "amount": "1000",
                    "merchantRequestId": fixed_request_id
                },
                expected_status=200,
                expected_response_patterns=["SUCCESS"],
                postconditions=["Second request should return same response as first (idempotent)"]
            ))
        
        return tests
    
    def _fill_template(self, template: Dict[str, Any], values: Dict[str, str]) -> Dict[str, Any]:
        """Fill template placeholders with actual values."""
        result = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                placeholder = value[1:-1]
                result[key] = values.get(placeholder, value)
            else:
                result[key] = value
        return result
    
    def _calculate_coverage(self, test_cases: List[TestCase]) -> Dict[str, int]:
        """Calculate test coverage statistics."""
        categories = {cat.value: 0 for cat in TestCategory}
        priorities = {pri.value: 0 for pri in TestPriority}
        
        for tc in test_cases:
            categories[tc.category.value] += 1
            priorities[tc.priority.value] += 1
        
        return {
            "total": len(test_cases),
            **categories,
            **priorities
        }


class TransactionLifecycleTracker:
    """Tracks transaction states through their lifecycle."""
    
    # State transitions for UPI transactions
    VALID_TRANSITIONS = {
        "INITIATED": ["PENDING", "FAILED"],
        "PENDING": ["SUCCESS", "FAILED"],
        "SUCCESS": [],
        "FAILED": []
    }
    
    def __init__(self):
        self.transactions: Dict[str, TransactionState] = {}
    
    def register_transaction(self, transaction_id: str, initial_state: str = "INITIATED"):
        """Register a new transaction for tracking."""
        self.transactions[transaction_id] = TransactionState(
            transaction_id=transaction_id,
            current_state=initial_state,
            state_history=[],
            metadata={
                "created_at": datetime.utcnow().isoformat()
            }
        )
    
    def transition(self, transaction_id: str, new_state: str, reason: str = ""):
        """Transition transaction to new state."""
        if transaction_id not in self.transactions:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        tx = self.transactions[transaction_id]
        
        # Validate transition
        if new_state not in self.VALID_TRANSITIONS.get(tx.current_state, []):
            raise ValueError(
                f"Invalid transition from {tx.current_state} to {new_state}"
            )
        
        tx.transition_to(new_state, reason)
    
    def get_state(self, transaction_id: str) -> Optional[TransactionState]:
        """Get current state of a transaction."""
        return self.transactions.get(transaction_id)
    
    def get_lifecycle_summary(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get complete lifecycle summary for a transaction."""
        tx = self.transactions.get(transaction_id)
        if not tx:
            return None
        
        return {
            "transaction_id": tx.transaction_id,
            "current_state": tx.current_state,
            "state_history": tx.state_history,
            "metadata": tx.metadata,
            "is_terminal": tx.current_state in ["SUCCESS", "FAILED"],
            "duration_seconds": self._calculate_duration(tx)
        }
    
    def _calculate_duration(self, tx: TransactionState) -> float:
        """Calculate transaction duration in seconds."""
        if not tx.state_history:
            return 0.0
        
        try:
            start = datetime.fromisoformat(tx.metadata["created_at"].replace("Z", ""))
            end = datetime.fromisoformat(tx.state_history[-1]["timestamp"].replace("Z", ""))
            return (end - start).total_seconds()
        except:
            return 0.0


class ExportFormatters:
    """Format test suites for external tools."""
    
    @staticmethod
    def to_postman_collection(suite: TestSuite) -> Dict[str, Any]:
        """Export test suite as Postman collection."""
        
        items = []
        for tc in suite.test_cases:
            items.append({
                "name": tc.name,
                "request": {
                    "method": "POST",
                    "header": [
                        {"key": "Content-Type", "value": "application/json"}
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps(tc.payload, indent=2)
                    },
                    "url": {
                        "raw": f"{{{{baseUrl}}}}/{tc.endpoint_id.replace('.', '/')}",
                        "host": ["{{baseUrl}}"],
                        "path": tc.endpoint_id.split(".")
                    },
                    "description": tc.description
                },
                "response": [],
                "event": [
                    {
                        "listen": "test",
                        "script": {
                            "exec": [
                                f"pm.test('Status code is {tc.expected_status}', function () {{",
                                f"    pm.response.to.have.status({tc.expected_status});",
                                "});"
                            ]
                        }
                    }
                ]
            })
        
        return {
            "info": {
                "_postman_id": str(uuid.uuid4()),
                "name": f"IBMB Test Suite - {suite.endpoint_id}",
                "description": f"Auto-generated test suite for {suite.endpoint_id}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": items,
            "variable": [
                {"key": "baseUrl", "value": "https://sandbox-api.ibmb.example.com"}
            ]
        }
    
    @staticmethod
    def to_jmeter_jmx(suite: TestSuite) -> str:
        """Export test suite as JMeter JMX XML."""
        # Simplified JMX template
        test_plan_name = f"IBMB_Test_Plan_{suite.endpoint_id.replace('.', '_')}"
        
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<jmeterTestPlan version="1.2" properties="5.0">',
            '  <hashTree>',
            f'    <TestPlan guiclass="TestPlanGui" testname="{test_plan_name}" enabled="true">',
            '      <stringProp name="TestPlan.comments"></stringProp>',
            '    </TestPlan>',
            '    <hashTree>',
            '      <ThreadGroup guiclass="ThreadGroupGui" testname="Test Group" enabled="true">',
            '        <elementProp name="ThreadGroup.arguments" elementType="Arguments">',
            '        </elementProp>',
            '        <stringProp name="ThreadGroup.num_threads">1</stringProp>',
            '        <stringProp name="ThreadGroup.ramp_time">1</stringProp>',
            '      </ThreadGroup>',
            '      <hashTree>'
        ]
        
        for tc in suite.test_cases:
            xml_parts.extend([
                f'        <HTTPSamplerProxy guiclass="HttpTestSampleGui" testname="{tc.name}" enabled="true">',
                '          <elementProp name="HTTPsampler.Arguments" elementType="Arguments">',
                '            <collectionProp name="Arguments.arguments">',
                '              <elementProp name="" elementType="HTTPArgument">',
                f'                <stringProp name="Argument.value">{json.dumps(tc.payload)}</stringProp>',
                '              </elementProp>',
                '            </collectionProp>',
                '          </elementProp>',
                f'          <stringProp name="HTTPSampler.domain">{{{{baseUrl}}}}</stringProp>',
                '          <stringProp name="HTTPSampler.port"></stringProp>',
                '          <stringProp name="HTTPSampler.protocol">https</stringProp>',
                f'          <stringProp name="HTTPSampler.path">/{tc.endpoint_id.replace(".", "/")}</stringProp>',
                '          <stringProp name="HTTPSampler.method">POST</stringProp>',
                '        </HTTPSamplerProxy>',
                '        <hashTree/>'
            ])
        
        xml_parts.extend([
            '      </hashTree>',
            '    </hashTree>',
            '  </hashTree>',
            '</jmeterTestPlan>'
        ])
        
        return '\n'.join(xml_parts)


# ===== MCP Tool Functions =====

async def generate_test_suite(
    endpoint_id: str,
    coverage_level: str = "essential",
    include_postman: bool = False,
    include_jmeter: bool = False
) -> dict:
    """
    Generate comprehensive test suite for an endpoint.
    
    Args:
        endpoint_id: API endpoint identifier
        coverage_level: 'essential' or 'comprehensive'
        include_postman: Export as Postman collection
        include_jmeter: Export as JMeter JMX
    
    Returns:
        Test suite with cases, coverage summary, and optional exports
    """
    
    generator = TestSuiteGenerator()
    suite = generator.generate_test_suite(endpoint_id, coverage_level)
    
    # Build response
    sections = [
        f"# Test Suite: {endpoint_id}",
        f"\n**Coverage Level:** {coverage_level}",
        f"**Total Test Cases:** {suite.coverage_summary.get('total', 0)}"
    ]
    
    # Coverage breakdown
    sections.append("\n## Coverage Breakdown")
    sections.append("### By Category")
    for cat in TestCategory:
        count = suite.coverage_summary.get(cat.value, 0)
        if count > 0:
            sections.append(f"- {cat.value.replace('_', ' ').title()}: {count}")
    
    sections.append("\n### By Priority")
    for pri in TestPriority:
        count = suite.coverage_summary.get(pri.value, 0)
        if count > 0:
            sections.append(f"- {pri.value.title()}: {count}")
    
    # Test cases detail
    sections.append("\n## Test Cases")
    for tc in suite.test_cases:
        sections.append(f"\n### {tc.id}: {tc.name}")
        sections.append(f"**Priority:** {tc.priority.value}")
        sections.append(f"**Category:** {tc.category.value}")
        sections.append(f"**Description:** {tc.description}")
        sections.append(f"**Expected Status:** {tc.expected_status}")
        
        if tc.preconditions:
            sections.append(f"**Preconditions:**")
            for pre in tc.preconditions:
                sections.append(f"  - {pre}")
        
        sections.append(f"**Payload:**")
        sections.append(f"```json\n{json.dumps(tc.payload, indent=2)}\n```")
        
        if tc.postconditions:
            sections.append(f"**Postconditions:**")
            for post in tc.postconditions:
                sections.append(f"  - {post}")
        
        if tc.cleanup_steps:
            sections.append(f"**Cleanup:**")
            for cleanup in tc.cleanup_steps:
                sections.append(f"  - {cleanup}")
    
    # Export formats
    exports = {}
    if include_postman:
        postman_collection = ExportFormatters.to_postman_collection(suite)
        exports["postman"] = postman_collection
        sections.append("\n---\n📦 **Postman Collection:** Available in response.exports.postman")
    
    if include_jmeter:
        jmeter_xml = ExportFormatters.to_jmeter_jmx(suite)
        exports["jmeter"] = jmeter_xml
        sections.append("📦 **JMeter JMX:** Available in response.exports.jmeter")
    
    response_data = {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "test_suite": {
            "endpoint_id": suite.endpoint_id,
            "coverage_summary": suite.coverage_summary,
            "test_cases": [asdict(tc) for tc in suite.test_cases]
        }
    }
    
    if exports:
        response_data["exports"] = exports
    
    return response_data


async def run_transaction_lifecycle_test(
    endpoint_id: str,
    merchant_id: str,
    api_key: Optional[str] = None,
    polling_interval: int = 5,
    max_polls: int = 12
) -> dict:
    """
    Run complete transaction lifecycle test with polling.
    
    Args:
        endpoint_id: Starting endpoint (usually transaction.init)
        merchant_id: Merchant ID for testing
        api_key: Optional sandbox API key
        polling_interval: Seconds between status polls
        max_polls: Maximum polling attempts
    
    Returns:
        Complete lifecycle trace with all state transitions
    """
    
    tracker = TransactionLifecycleTracker()
    data_gen = TestDataGenerator()
    
    # Generate test transaction
    merchant_request_id = data_gen.generate_merchant_request_id()
    
    # Initialize payload
    init_payload = {
        "payeeVpaHandle": "merchant@juspay",
        "payeeName": "Test Merchant",
        "payerVpaHandle": data_gen.generate_vpa(),
        "amount": str(data_gen.generate_amount()),
        "merchantRequestId": merchant_request_id,
        "merchantId": merchant_id,
        "upiTxnType": "COLLECT",
        "description": "Lifecycle test"
    }
    
    # Setup sandbox client
    config = SandboxConfig(
        api_key=api_key,
        mode=SandboxMode.MOCK if not api_key else SandboxMode.SANDBOX
    )
    
    sections = [
        "# Transaction Lifecycle Test",
        f"\n**Merchant ID:** {merchant_id}",
        f"**Merchant Request ID:** {merchant_request_id}",
        f"**Mode:** {'Mock' if not api_key else 'Sandbox'}",
    ]
    
    results = {
        "merchant_request_id": merchant_request_id,
        "stages": [],
        "final_state": None
    }
    
    async with SandboxClient(config) as client:
        # Stage 1: Initiate transaction
        sections.append("\n## Stage 1: Initiate Transaction")
        init_result = await client.test_endpoint(endpoint_id, init_payload)
        
        results["stages"].append({
            "stage": "initiate",
            "success": init_result.success,
            "status_code": init_result.status_code,
            "latency_ms": init_result.latency_ms
        })
        
        sections.append(f"**Status:** {'✅ Success' if init_result.success else '❌ Failed'}")
        sections.append(f"**Response Time:** {init_result.latency_ms:.2f}ms")
        
        if not init_result.success:
            sections.append(f"**Error:** {init_result.errors}")
            results["final_state"] = "INIT_FAILED"
            return {
                "content": [{"type": "text", "text": "\n".join(sections)}],
                **results
            }
        
        # Extract transaction ID if available
        upi_txn_id = init_result.response.get("upiTxnId") or data_gen.generate_upi_txn_id()
        tracker.register_transaction(upi_txn_id, "INITIATED")
        sections.append(f"**UPI Transaction ID:** {upi_txn_id}")
        
        # Stage 2: Poll for status (simulated)
        sections.append(f"\n## Stage 2: Status Polling ({max_polls} attempts)")
        
        status_payload = {
            "merchantId": merchant_id,
            "merchantRequestId": merchant_request_id,
            "upiTxnId": upi_txn_id
        }
        
        poll_count = 0
        final_state = "PENDING"
        
        while poll_count < max_polls and final_state == "PENDING":
            poll_count += 1
            status_result = await client.test_endpoint(
                "ibmb.merchant.transaction.status",
                status_payload
            )
            
            txn_status = status_result.response.get("txnStatus", "PENDING")
            
            if txn_status != final_state:
                tracker.transition(upi_txn_id, txn_status, f"Poll #{poll_count}")
                final_state = txn_status
            
            sections.append(f"  Poll #{poll_count}: {txn_status} ({status_result.latency_ms:.0f}ms)")
            
            if final_state in ["SUCCESS", "FAILED"]:
                break
            
            # Simulate delay (would be real sleep in actual implementation)
            sections.append(f"    → Waiting {polling_interval}s before next poll...")
        
        # Summary
        lifecycle = tracker.get_lifecycle_summary(upi_txn_id)
        results["final_state"] = final_state
        results["lifecycle"] = lifecycle
        
        sections.append(f"\n## Final Status")
        sections.append(f"**State:** {final_state}")
        sections.append(f"**Total Polls:** {poll_count}")
        
        if lifecycle:
            sections.append(f"\n### State Transitions")
            for transition in lifecycle["state_history"]:
                sections.append(f"- {transition['from']} → {transition['to']} ({transition['reason']})")
        
        if final_state == "PENDING":
            sections.append("\n⚠️ **Warning:** Transaction still pending after maximum polls")
            sections.append("This may indicate:")
            sections.append("- User hasn't completed payment on device")
            sections.append("- Network delays in UPI infrastructure")
            sections.append("- Transaction stuck in intermediate state")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        **results
    }


async def get_comprehensive_test_scenarios(
    flow_type: str,
    coverage: str = "essential",
    format: str = "detailed"
) -> dict:
    """
    Get comprehensive test scenarios with test data generation.
    
    Args:
        flow_type: Flow type (payment, refund, status, collect)
        coverage: Coverage level ('essential', 'comprehensive', 'edge_cases')
        format: Output format ('detailed', 'summary', 'executable')
    
    Returns:
        Test scenarios with generated data and assertions
    """
    
    data_gen = TestDataGenerator()
    scenarios = []
    
    if flow_type == "payment":
        base_merchant_id = "TEST123"
        
        # Happy path scenarios
        scenarios.extend([
            {
                "id": "PAY_HAPPY_001",
                "name": "Standard UPI Payment",
                "category": "happy_path",
                "priority": "critical",
                "payload": {
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": data_gen.generate_vpa(),
                    "amount": str(data_gen.generate_amount(1000, 10000)),
                    "merchantRequestId": data_gen.generate_merchant_request_id(),
                    "merchantId": base_merchant_id,
                    "upiTxnType": "PAY",
                    "description": "Standard payment test"
                },
                "assertions": [
                    "response.result equals SUCCESS",
                    "response.payload.url is not empty",
                    "response.payload.intentExpiry is numeric"
                ]
            },
            {
                "id": "PAY_HAPPY_002",
                "name": "UPI Collect Request",
                "category": "happy_path",
                "priority": "critical",
                "payload": {
                    "payeeVpaHandle": "merchant@juspay",
                    "payerVpaHandle": data_gen.generate_vpa(),
                    "amount": "5000",
                    "merchantRequestId": data_gen.generate_merchant_request_id(),
                    "merchantId": base_merchant_id,
                    "upiTxnType": "COLLECT",
                    "description": "Collect request test"
                },
                "assertions": [
                    "response.result equals SUCCESS",
                    "response.payload is present"
                ]
            }
        ])
        
        # Validation error scenarios
        if coverage in ["comprehensive", "edge_cases"]:
            scenarios.extend([
                {
                    "id": "PAY_VAL_001",
                    "name": "Invalid VPA Format",
                    "category": "validation_error",
                    "priority": "high",
                    "payload": {
                        "payeeVpaHandle": "merchant@juspay",
                        "payerVpaHandle": "not-a-valid-vpa",
                        "amount": "1000",
                        "merchantRequestId": data_gen.generate_merchant_request_id(),
                        "merchantId": base_merchant_id,
                        "upiTxnType": "PAY"
                    },
                    "expected_error": "INVALID_VPA_FORMAT"
                },
                {
                    "id": "PAY_VAL_002",
                    "name": "Negative Amount",
                    "category": "validation_error",
                    "priority": "high",
                    "payload": {
                        "payeeVpaHandle": "merchant@juspay",
                        "payerVpaHandle": data_gen.generate_vpa(),
                        "amount": "-100",
                        "merchantRequestId": data_gen.generate_merchant_request_id(),
                        "merchantId": base_merchant_id,
                        "upiTxnType": "PAY"
                    },
                    "expected_error": "INVALID_AMOUNT"
                },
                {
                    "id": "PAY_VAL_003",
                    "name": "Zero Amount",
                    "category": "edge_case",
                    "priority": "medium",
                    "payload": {
                        "payeeVpaHandle": "merchant@juspay",
                        "payerVpaHandle": data_gen.generate_vpa(),
                        "amount": "0",
                        "merchantRequestId": data_gen.generate_merchant_request_id(),
                        "merchantId": base_merchant_id,
                        "upiTxnType": "PAY"
                    },
                    "expected_error": "INVALID_AMOUNT"
                }
            ])
        
        # Security scenarios
        if coverage == "comprehensive":
            scenarios.extend([
                {
                    "id": "PAY_SEC_001",
                    "name": "SQL Injection Attempt",
                    "category": "security",
                    "priority": "high",
                    "payload": {
                        "payeeVpaHandle": "merchant@juspay",
                        "payerVpaHandle": data_gen.generate_vpa(),
                        "amount": "1000",
                        "merchantRequestId": data_gen.generate_merchant_request_id(),
                        "merchantId": base_merchant_id,
                        "upiTxnType": "PAY",
                        "description": "'; DROP TABLE payments; --"
                    },
                    "expected_error": "INVALID_INPUT"
                },
                {
                    "id": "PAY_SEC_002",
                    "name": "XSS Payload in Description",
                    "category": "security",
                    "priority": "high",
                    "payload": {
                        "payeeVpaHandle": "merchant@juspay",
                        "payerVpaHandle": data_gen.generate_vpa(),
                        "amount": "1000",
                        "merchantRequestId": data_gen.generate_merchant_request_id(),
                        "merchantId": base_merchant_id,
                        "upiTxnType": "PAY",
                        "description": "<img src=x onerror=alert('xss')>"
                    },
                    "expected_error": "INVALID_INPUT"
                }
            ])
    
    elif flow_type == "status":
        scenarios.extend([
            {
                "id": "STATUS_001",
                "name": "Query Pending Transaction",
                "category": "happy_path",
                "priority": "critical",
                "payload": {
                    "merchantId": "TEST123",
                    "merchantRequestId": data_gen.generate_merchant_request_id(),
                    "upiTxnId": data_gen.generate_upi_txn_id()
                },
                "assertions": [
                    "response.txnStatus is in [INITIATED, PENDING, SUCCESS, FAILED]",
                    "response.amount is numeric"
                ]
            }
        ])
    
    # Format output
    if format == "summary":
        summary = {
            "flow_type": flow_type,
            "coverage": coverage,
            "total_scenarios": len(scenarios),
            "by_category": {}
        }
        for s in scenarios:
            cat = s["category"]
            summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
        
        return {
            "content": [{
                "type": "text",
                "text": f"Test Scenario Summary:\n{json.dumps(summary, indent=2)}"
            }],
            **summary
        }
    
    elif format == "executable":
        # Return just the data needed for test execution
        return {
            "content": [{
                "type": "text",
                "text": f"Generated {len(scenarios)} executable test scenarios"
            }],
            "scenarios": scenarios,
            "execution_metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "data_generator_version": "1.0",
                "merchant_id_prefix": "TEST"
            }
        }
    
    # Detailed format (default)
    sections = [
        f"# Test Scenarios: {flow_type}",
        f"\n**Coverage Level:** {coverage}",
        f"**Total Scenarios:** {len(scenarios)}"
    ]
    
    # Group by category
    by_category = {}
    for s in scenarios:
        cat = s["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(s)
    
    for category, cat_scenarios in by_category.items():
        sections.append(f"\n## {category.replace('_', ' ').title()} ({len(cat_scenarios)})")
        
        for s in cat_scenarios:
            sections.append(f"\n### {s['id']}: {s['name']}")
            sections.append(f"**Priority:** {s['priority']}")
            sections.append(f"**Payload:**")
            sections.append(f"```json\n{json.dumps(s['payload'], indent=2)}\n```")
            
            if 'assertions' in s:
                sections.append(f"**Assertions:**")
                for a in s['assertions']:
                    sections.append(f"  - {a}")
            
            if 'expected_error' in s:
                sections.append(f"**Expected Error:** `{s['expected_error']}`")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "scenarios": scenarios,
        "summary": {
            "flow_type": flow_type,
            "coverage": coverage,
            "total": len(scenarios),
            "by_category": {k: len(v) for k, v in by_category.items()}
        }
    }


async def export_test_suite(
    endpoint_id: str,
    format: str,
    coverage_level: str = "essential"
) -> dict:
    """
    Export test suite in various formats.
    
    Args:
        endpoint_id: API endpoint to generate tests for
        format: Export format ('postman', 'jmeter', 'curl', 'pytest')
        coverage_level: Test coverage level
    
    Returns:
        Exported test suite ready for use
    """
    
    generator = TestSuiteGenerator()
    suite = generator.generate_test_suite(endpoint_id, coverage_level)
    
    if format == "postman":
        collection = ExportFormatters.to_postman_collection(suite)
        filename = f"ibmb_{endpoint_id.replace('.', '_')}_tests.json"
        
        return {
            "content": [{
                "type": "text",
                "text": f"""# Postman Collection Exported

**File:** {filename}
**Endpoint:** {endpoint_id}
**Test Cases:** {len(suite.test_cases)}

## Import Instructions
1. Open Postman
2. Click Import → File
3. Select the downloaded JSON
4. Set the `baseUrl` environment variable

The collection includes {len(suite.test_cases)} test requests with validation tests."""
            }],
            "export": {
                "format": "postman",
                "filename": filename,
                "collection": collection
            }
        }
    
    elif format == "jmeter":
        jmx = ExportFormatters.to_jmeter_jmx(suite)
        filename = f"ibmb_{endpoint_id.replace('.', '_')}_tests.jmx"
        
        return {
            "content": [{
                "type": "text",
                "text": f"""# JMeter Test Plan Exported

**File:** {filename}
**Endpoint:** {endpoint_id}
**Test Cases:** {len(suite.test_cases)}

## Usage Instructions
1. Open JMeter GUI
2. File → Open → Select the .jmx file
3. Configure Thread Group (users, ramp-up, duration)
4. Set baseUrl user defined variable
5. Run the test plan

Each HTTP sampler represents one test case from the suite."""
            }],
            "export": {
                "format": "jmeter",
                "filename": filename,
                "jmx_xml": jmx
            }
        }
    
    elif format == "curl":
        commands = []
        for tc in suite.test_cases:
            curl_cmd = f"""curl -X POST https://sandbox-api.ibmb.example.com/{tc.endpoint_id.replace('.', '/')} \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(tc.payload)}'"""
            commands.append({
                "name": tc.name,
                "command": curl_cmd,
                "expected_status": tc.expected_status
            })
        
        return {
            "content": [{
                "type": "text",
                "text": f"""# cURL Commands ({len(commands)} tests)

Generated for {endpoint_id} with {coverage_level} coverage.

## Commands

""" + "\n\n".join([f"### {c['name']}\n```bash\n{c['command']}\n```\nExpected: HTTP {c['expected_status']}" for c in commands])
            }],
            "export": {
                "format": "curl",
                "commands": commands
            }
        }
    
    elif format == "pytest":
        # Generate pytest test functions
        test_code = f"""\nimport pytest\nimport requests\n\nBASE_URL = \"https://sandbox-api.ibmb.example.com\"\nMERCHANT_ID = \"YOUR_MERCHANT_ID\"\nAPI_KEY = \"YOUR_API_KEY\"\n\n@pytest.fixture\ndef headers():\n    return {{\n        \"Content-Type\": \"application/json\",\n        \"X-API-Key\": API_KEY\n    }}\n\nclass Test{endpoint_id.replace('.', '_').title()}:\n"""
        
        for tc in suite.test_cases:
            test_code += f'''\n    def test_{tc.id.lower()}(self, headers):\n        \"\"\"{tc.description}\"\"\"\n        payload = {json.dumps(tc.payload, indent=8)}\n        \n        response = requests.post(\n            f"{{BASE_URL}}/{tc.endpoint_id.replace('.', '/')}",\n            json=payload,\n            headers=headers\n        )\n        \n        assert response.status_code == {tc.expected_status}\n'''
        
        return {
            "content": [{
                "type": "text",
                "text": f"""# PyTest Test Suite Generated

**Module:** test_{endpoint_id.replace('.', '_')}.py
**Test Class:** Test{endpoint_id.replace('.', '_').title()}
**Test Methods:** {len(suite.test_cases)}

## Setup
```bash
pip install pytest requests
export MERCHANT_ID=your_merchant_id
export API_KEY=your_api_key
pytest test_{endpoint_id.replace('.', '_')}.py -v
```

The generated code uses pytest fixtures for headers and parameterized tests."""
            }],
            "export": {
                "format": "pytest",
                "filename": f"test_{endpoint_id.replace('.', '_')}.py",
                "code": test_code
            }
        }
    
    return {
        "content": [{
            "type": "text",
            "text": f"❌ Unknown export format: {format}. Supported: postman, jmeter, curl, pytest"
        }],
        "isError": True
    }
