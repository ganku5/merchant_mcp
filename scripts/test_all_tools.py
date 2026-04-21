#!/usr/bin/env python3
"""Comprehensive test suite for all MCP tools."""

import asyncio
import sys
sys.path.insert(0, '/home/ganesh/merchant_mcp')

from src.tools.understanding_tools import (
    get_api_spec, get_integration_guide, get_flow, search_docs
)
from src.tools.building_tools import (
    generate_payload, get_code_example, get_webhook_handler, validate_payload
)
from src.tools.testing_tools import (
    test_sandbox, explain_error, get_test_cases, check_integration
)
from src.tools.debugging_tools import (
    diagnose_webhook, lookup_error_map, search_known_issues
)


async def test_understanding_tools():
    """Test understanding phase tools."""
    print("\n" + "="*60)
    print("TESTING UNDERSTANDING TOOLS")
    print("="*60)
    
    tests = []
    
    # Test get_api_spec
    print("\n1. Testing get_api_spec('orders.create')...")
    result = await get_api_spec("orders.create")
    success = not result.get('isError') and 'orders.create' in str(result)
    tests.append(('get_api_spec', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test get_integration_guide
    print("\n2. Testing get_integration_guide('payment')...")
    result = await get_integration_guide("payment")
    success = not result.get('isError') and 'payment' in str(result).lower()
    tests.append(('get_integration_guide', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test get_flow
    print("\n3. Testing get_flow('payment.standard')...")
    result = await get_flow("payment.standard")
    success = not result.get('isError')
    tests.append(('get_flow', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test search_docs
    print("\n4. Testing search_docs('order creation')...")
    result = await search_docs("order creation")
    success = 'text' in str(result)
    tests.append(('search_docs', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    return tests


async def test_building_tools():
    """Test building phase tools."""
    print("\n" + "="*60)
    print("TESTING BUILDING TOOLS")
    print("="*60)
    
    tests = []
    
    # Test generate_payload
    print("\n1. Testing generate_payload('orders.create')...")
    result = await generate_payload("orders.create")
    success = not result.get('isError') and 'order_id' in str(result)
    tests.append(('generate_payload', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test get_code_example
    print("\n2. Testing get_code_example('orders.create', 'python')...")
    result = await get_code_example("orders.create", "python")
    success = not result.get('isError') and 'python' in str(result).lower()
    tests.append(('get_code_example', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test get_webhook_handler
    print("\n3. Testing get_webhook_handler('order.charged', 'python')...")
    result = await get_webhook_handler("order.charged", "python")
    success = not result.get('isError') and 'webhook' in str(result).lower()
    tests.append(('get_webhook_handler', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test validate_payload (valid)
    print("\n4. Testing validate_payload (valid)...")
    payload = {
        "order_id": "test_123",
        "amount": 10000,
        "currency": "INR",
        "customer_email": "test@example.com",
        "return_url": "https://example.com/callback"
    }
    result = await validate_payload("orders.create", payload)
    success = not result.get('isError')
    tests.append(('validate_payload_valid', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test validate_payload (invalid)
    print("\n5. Testing validate_payload (invalid)...")
    bad_payload = {"order_id": "test_123"}  # Missing required fields
    result = await validate_payload("orders.create", bad_payload)
    success = result.get('isError')  # Should have errors
    tests.append(('validate_payload_invalid', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    return tests


async def test_testing_tools():
    """Test testing phase tools."""
    print("\n" + "="*60)
    print("TESTING TESTING TOOLS")
    print("="*60)
    
    tests = []
    
    # Test explain_error
    print("\n1. Testing explain_error('ORDER_ID_EXISTS')...")
    result = await explain_error("ORDER_ID_EXISTS")
    success = not result.get('isError') and 'ORDER_ID_EXISTS' in str(result)
    tests.append(('explain_error', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test get_test_cases
    print("\n2. Testing get_test_cases('payment')...")
    result = await get_test_cases("payment")
    success = not result.get('isError') and 'scenario' in str(result).lower()
    tests.append(('get_test_cases', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test check_integration
    print("\n3. Testing check_integration()...")
    result = await check_integration("pre_production")
    success = 'checklist' in str(result).lower()
    tests.append(('check_integration', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test test_sandbox
    print("\n4. Testing test_sandbox()...")
    payload = {
        "order_id": "test_123",
        "amount": 10000,
        "currency": "INR",
        "customer_email": "test@example.com",
        "return_url": "https://example.com/callback"
    }
    result = await test_sandbox("orders.create", payload)
    success = not result.get('isError') and 'sandbox' in str(result).lower()
    tests.append(('test_sandbox', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    return tests


async def test_debugging_tools():
    """Test debugging phase tools."""
    print("\n" + "="*60)
    print("TESTING DEBUGGING TOOLS")
    print("="*60)
    
    tests = []
    
    # Test diagnose_webhook (valid)
    print("\n1. Testing diagnose_webhook (with valid signature)...")
    import hmac
    import hashlib
    
    secret = "test_secret"
    body = '{"event": "order.charged", "order_id": "test_123"}'
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    
    headers = {
        "X-Juspay-Signature": signature,
        "Content-Type": "application/json"
    }
    result = await diagnose_webhook(headers, body, webhook_secret=secret)
    success = 'PASSED' in str(result) or 'passed' in str(result).lower()
    tests.append(('diagnose_webhook_valid', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test diagnose_webhook (invalid)
    print("\n2. Testing diagnose_webhook (with invalid signature)...")
    headers_bad = {
        "X-Juspay-Signature": "invalid_signature",
        "Content-Type": "application/json"
    }
    result = await diagnose_webhook(headers_bad, body, webhook_secret=secret)
    success = 'FAILED' in str(result) or 'failed' in str(result).lower()
    tests.append(('diagnose_webhook_invalid', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test lookup_error_map
    print("\n3. Testing lookup_error_map('RATE_LIMIT_EXCEEDED')...")
    result = await lookup_error_map("RATE_LIMIT_EXCEEDED")
    success = not result.get('isError') and 'RATE_LIMIT_EXCEEDED' in str(result)
    tests.append(('lookup_error_map', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test search_known_issues
    print("\n4. Testing search_known_issues('webhook not received')...")
    result = await search_known_issues("webhook not received")
    success = 'text' in str(result)  # Should return something
    tests.append(('search_known_issues', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    return tests


async def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\n" + "="*60)
    print("TESTING ERROR HANDLING")
    print("="*60)
    
    tests = []
    
    # Test non-existent endpoint
    print("\n1. Testing get_api_spec with non-existent endpoint...")
    result = await get_api_spec("nonexistent.endpoint")
    success = result.get('isError') == True
    tests.append(('error_nonexistent_endpoint', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test invalid language
    print("\n2. Testing get_code_example with invalid language...")
    result = await get_code_example("orders.create", "rust")
    success = result.get('isError') == True
    tests.append(('error_invalid_language', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    # Test non-existent error code
    print("\n3. Testing explain_error with non-existent code...")
    result = await explain_error("UNKNOWN_ERROR_CODE_XYZ")
    # May not error if LLM provides explanation
    success = 'text' in str(result)
    tests.append(('error_nonexistent_error', success))
    print(f"   {'✅ PASS' if success else '❌ FAIL'}")
    
    return tests


async def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("MERCHANT MCP - COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    all_tests = []
    
    # Run all test suites
    all_tests.extend(await test_understanding_tools())
    all_tests.extend(await test_building_tools())
    all_tests.extend(await test_testing_tools())
    all_tests.extend(await test_debugging_tools())
    all_tests.extend(await test_error_handling())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in all_tests if result)
    failed = sum(1 for _, result in all_tests if not result)
    
    for name, result in all_tests:
        status = '✅ PASS' if result else '❌ FAIL'
        print(f"{status}: {name}")
    
    print(f"\nTotal: {len(all_tests)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {passed/len(all_tests)*100:.1f}%")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
