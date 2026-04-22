"""Test all 15 MCP tools."""

import asyncio
import json
import sys
import os

sys.path.insert(0, '/home/ganesh/merchant_mcp')

from src.utils.database import database

# Import all tools
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


async def test_tool(name, func, *args, **kwargs):
    """Test a single tool."""
    try:
        result = await func(*args, **kwargs)
        if isinstance(result, dict):
            if result.get("isError"):
                return False, f"Error: {result.get('content', [{}])[0].get('text', 'Unknown error')}"
            content = result.get("content", [{}])[0].get("text", "")[:200]
        else:
            content = str(result)[:200]
        return True, content
    except Exception as e:
        return False, f"Exception: {str(e)}"


async def main():
    await database.connect()
    print("✅ Database connected\n")
    
    results = []
    
    # ============ Understanding Tools ============
    print("=== Understanding Tools ===")
    
    # 1. get_api_spec
    success, msg = await test_tool("get_api_spec", get_api_spec, "orders.create")
    results.append(("get_api_spec", success, msg))
    print(f"1. get_api_spec: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 2. get_integration_guide
    success, msg = await test_tool("get_integration_guide", get_integration_guide, "payment", "python")
    results.append(("get_integration_guide", success, msg))
    print(f"2. get_integration_guide: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 3. get_flow
    success, msg = await test_tool("get_flow", get_flow, "payment.standard")
    results.append(("get_flow", success, msg))
    print(f"3. get_flow: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 4. search_docs
    success, msg = await test_tool("search_docs", search_docs, "how to create order", 3)
    results.append(("search_docs", success, msg))
    print(f"4. search_docs: {'✅' if success else '❌'} {msg[:100]}...")
    
    # ============ Building Tools ============
    print("\n=== Building Tools ===")
    
    # 5. generate_payload
    success, msg = await test_tool("generate_payload", generate_payload, "orders.create", {}, False)
    results.append(("generate_payload", success, msg))
    print(f"5. generate_payload: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 6. get_code_example
    success, msg = await test_tool("get_code_example", get_code_example, "orders.create", "python")
    results.append(("get_code_example", success, msg))
    print(f"6. get_code_example: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 7. get_webhook_handler
    success, msg = await test_tool("get_webhook_handler", get_webhook_handler, "order.charged", "python")
    results.append(("get_webhook_handler", success, msg))
    print(f"7. get_webhook_handler: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 8. validate_payload (with complete payload)
    test_payload = {
        "order_id": "test_001",
        "amount": 10000,
        "currency": "INR",
        "customer_email": "test@example.com",
        "return_url": "https://example.com/callback"
    }
    success, msg = await test_tool("validate_payload", validate_payload, "orders.create", test_payload)
    results.append(("validate_payload", success, msg))
    print(f"8. validate_payload: {'✅' if success else '❌'} {msg[:100]}...")
    
    # ============ Testing Tools ============
    print("\n=== Testing Tools ===")
    
    # 9. test_sandbox
    test_payload = {"order_id": "test_001", "amount": 10000, "currency": "INR", "customer_email": "test@test.com", "return_url": "https://example.com/callback"}
    success, msg = await test_tool("test_sandbox", test_sandbox, "orders.create", test_payload, None)
    results.append(("test_sandbox", success, msg))
    print(f"9. test_sandbox: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 10. explain_error
    success, msg = await test_tool("explain_error", explain_error, "ORDER_ID_EXISTS")
    results.append(("explain_error", success, msg))
    print(f"10. explain_error: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 11. get_test_cases
    success, msg = await test_tool("get_test_cases", get_test_cases, "payment", "essential")
    results.append(("get_test_cases", success, msg))
    print(f"11. get_test_cases: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 12. check_integration
    success, msg = await test_tool("check_integration", check_integration, "pre_production")
    results.append(("check_integration", success, msg))
    print(f"12. check_integration: {'✅' if success else '❌'} {msg[:100]}...")
    
    # ============ Debugging Tools ============
    print("\n=== Debugging Tools ===")
    
    # 13. diagnose_webhook
    test_headers = {"content-type": "application/json", "x-juspay-signature": "test_sig"}
    test_body = '{"event": "order.charged", "order_id": "test_001"}'
    success, msg = await test_tool("diagnose_webhook", diagnose_webhook, test_headers, test_body)
    results.append(("diagnose_webhook", success, msg))
    print(f"13. diagnose_webhook: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 14. lookup_error_map
    success, msg = await test_tool("lookup_error_map", lookup_error_map, "ORDER_ID_EXISTS")
    results.append(("lookup_error_map", success, msg))
    print(f"14. lookup_error_map: {'✅' if success else '❌'} {msg[:100]}...")
    
    # 15. search_known_issues
    success, msg = await test_tool("search_known_issues", search_known_issues, "webhook not received")
    results.append(("search_known_issues", success, msg))
    print(f"15. search_known_issues: {'✅' if success else '❌'} {msg[:100]}...")
    
    await database.close()
    
    # Summary
    print("\n=== Summary ===")
    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print("\nFailed tools:")
        for name, success, msg in results:
            if not success:
                print(f"  - {name}: {msg}")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
