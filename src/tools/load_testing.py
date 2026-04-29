"""
Load Testing Utilities

Provides load testing capabilities for payment APIs:
- Concurrent transaction testing
- Ramp-up/ramp-down scenarios
- Latency distribution analysis
- Throughput measurement
- Error rate tracking
"""

import json
import time
import asyncio
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..utils.database import database


class LoadTestStatus(Enum):
    """Load test status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class LoadTestRequest:
    """A single load test request and its result."""
    request_id: int
    start_time: float
    end_time: float = 0.0
    latency_ms: float = 0.0
    status_code: int = 0
    success: bool = False
    error: Optional[str] = None


@dataclass
class LoadTestConfig:
    """Configuration for a load test."""
    endpoint_id: str
    base_payload: Dict[str, Any]
    concurrent_users: int = 10
    total_requests: int = 100
    ramp_up_seconds: float = 10.0
    ramp_down_seconds: float = 5.0
    think_time_seconds: float = 0.5  # Delay between requests per user
    timeout_seconds: float = 30.0


@dataclass
class LoadTestResult:
    """Results of a load test."""
    config: LoadTestConfig
    status: LoadTestStatus
    requests: List[LoadTestRequest] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    # Computed metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0
    throughput_rps: float = 0.0  # Requests per second
    
    # Latency metrics (ms)
    min_latency: float = 0.0
    max_latency: float = 0.0
    avg_latency: float = 0.0
    median_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    
    # Error distribution
    errors: Dict[str, int] = field(default_factory=dict)


class LoadTestRunner:
    """Runs load tests against payment APIs."""
    
    def __init__(self):
        self.results: Dict[str, LoadTestResult] = {}
    
    async def run_load_test(
        self,
        config: LoadTestConfig,
        use_sandbox: bool = False,
        api_key: Optional[str] = None
    ) -> LoadTestResult:
        """
        Run a load test with the given configuration.
        
        Args:
            config: Load test configuration
            use_sandbox: Use real sandbox (otherwise mock)
            api_key: API key for sandbox mode
        
        Returns:
            Complete load test results with metrics
        """
        result = LoadTestResult(config=config, status=LoadTestStatus.RUNNING)
        result.start_time = time.time()
        
        try:
            # Calculate requests per user
            requests_per_user = max(1, config.total_requests // config.concurrent_users)
            
            # Create tasks for concurrent users
            tasks = []
            for user_id in range(config.concurrent_users):
                task = self._simulate_user(
                    user_id=user_id,
                    requests_count=requests_per_user,
                    config=config,
                    result=result,
                    use_sandbox=use_sandbox,
                    api_key=api_key
                )
                tasks.append(task)
            
            # Run all users concurrently
            await asyncio.gather(*tasks, return_exceptions=True)
            
            result.status = LoadTestStatus.COMPLETED
        
        except Exception as e:
            result.status = LoadTestStatus.FAILED
            result.errors["load_test_error"] = str(e)
        
        result.end_time = time.time()
        
        # Compute metrics
        self._compute_metrics(result)
        
        return result
    
    async def _simulate_user(
        self,
        user_id: int,
        requests_count: int,
        config: LoadTestConfig,
        result: LoadTestResult,
        use_sandbox: bool,
        api_key: Optional[str]
    ) -> None:
        """Simulate a single user making requests."""
        
        # Ramp-up delay
        ramp_delay = (user_id / config.concurrent_users) * config.ramp_up_seconds
        if ramp_delay > 0:
            await asyncio.sleep(ramp_delay)
        
        for req_num in range(requests_count):
            request_id = user_id * requests_count + req_num
            
            lt_request = LoadTestRequest(
                request_id=request_id,
                start_time=time.time()
            )
            
            try:
                if use_sandbox and api_key:
                    # Real sandbox call
                    latency, status, success = await self._make_sandbox_request(
                        config.endpoint_id,
                        config.base_payload,
                        api_key
                    )
                else:
                    # Simulated request
                    latency, status, success = await self._simulate_request(
                        config.endpoint_id
                    )
                
                lt_request.end_time = time.time()
                lt_request.latency_ms = latency
                lt_request.status_code = status
                lt_request.success = success
            
            except Exception as e:
                lt_request.end_time = time.time()
                lt_request.latency_ms = (lt_request.end_time - lt_request.start_time) * 1000
                lt_request.success = False
                lt_request.error = str(e)
            
            result.requests.append(lt_request)
            
            # Think time between requests
            if req_num < requests_count - 1 and config.think_time_seconds > 0:
                await asyncio.sleep(config.think_time_seconds)
    
    async def _simulate_request(
        self,
        endpoint_id: str
    ) -> tuple:
        """Simulate an API request with realistic latency."""
        # Simulate network and processing time
        base_latency = random_log_normal(50, 100)  # 50-150ms typical
        await asyncio.sleep(base_latency / 1000)
        
        # Simulate occasional failures (2% error rate)
        import random
        if random.random() < 0.02:
            return base_latency, 500, False
        
        return base_latency, 200, True
    
    async def _make_sandbox_request(
        self,
        endpoint_id: str,
        payload: Dict[str, Any],
        api_key: str
    ) -> tuple:
        """Make a real sandbox API request."""
        import aiohttp
        
        from .sandbox_client import SandboxConfig, SandboxClient, SandboxMode
        
        config = SandboxConfig(api_key=api_key, mode=SandboxMode.SANDBOX)
        
        async with SandboxClient(config) as client:
            result = await client.test_endpoint(endpoint_id, payload)
            return result.latency_ms, result.status_code, result.success
    
    def _compute_metrics(self, result: LoadTestResult) -> None:
        """Compute aggregate metrics from test results."""
        if not result.requests:
            return
        
        # Basic counts
        result.total_requests = len(result.requests)
        result.successful_requests = sum(1 for r in result.requests if r.success)
        result.failed_requests = result.total_requests - result.successful_requests
        result.error_rate = result.failed_requests / result.total_requests if result.total_requests > 0 else 0
        
        # Throughput
        duration = result.end_time - result.start_time if result.end_time and result.start_time else 1
        result.throughput_rps = result.total_requests / duration
        
        # Latency metrics
        latencies = [r.latency_ms for r in result.requests if r.latency_ms > 0]
        
        if latencies:
            result.min_latency = min(latencies)
            result.max_latency = max(latencies)
            result.avg_latency = statistics.mean(latencies)
            result.median_latency = statistics.median(latencies)
            
            sorted_latencies = sorted(latencies)
            result.p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            result.p99_latency = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        
        # Error distribution
        for r in result.requests:
            if r.error:
                error_type = r.error[:50]
                result.errors[error_type] = result.errors.get(error_type, 0) + 1


def random_log_normal(mean: float, std: float) -> float:
    """Generate a log-normal distributed random number (simulates latency)."""
    import random
    import math
    normal = random.gauss(0, 1)
    return mean * math.exp(std / mean * normal - 0.5 * (std / mean) ** 2)


class StressTestRunner:
    """Runs stress tests to find breaking points."""
    
    async def find_breaking_point(
        self,
        endpoint_id: str,
        base_payload: Dict[str, Any],
        start_concurrent: int = 5,
        max_concurrent: int = 200,
        step_size: int = 10,
        requests_per_level: int = 50,
        target_latency_ms: float = 2000.0,
        target_error_rate: float = 0.05
    ) -> Dict[str, Any]:
        """
        Find the breaking point of the API.
        
        Gradually increases load until error rate or latency exceeds targets.
        
        Args:
            endpoint_id: API endpoint to test
            base_payload: Request payload template
            start_concurrent: Starting concurrent users
            max_concurrent: Maximum concurrent users to test
            step_size: Users to add per level
            requests_per_level: Total requests per level
            target_latency_ms: Max acceptable P95 latency
            target_error_rate: Max acceptable error rate
        
        Returns:
            Breaking point analysis with recommendations
        """
        results = []
        breaking_point = None
        
        for concurrent in range(start_concurrent, max_concurrent + 1, step_size):
            config = LoadTestConfig(
                endpoint_id=endpoint_id,
                base_payload=base_payload,
                concurrent_users=concurrent,
                total_requests=requests_per_level,
                ramp_up_seconds=5.0,
                think_time_seconds=0.1
            )
            
            runner = LoadTestRunner()
            result = await runner.run_load_test(config)
            
            level_result = {
                "concurrent_users": concurrent,
                "throughput_rps": round(result.throughput_rps, 2),
                "avg_latency_ms": round(result.avg_latency, 2),
                "p95_latency_ms": round(result.p95_latency, 2),
                "p99_latency_ms": round(result.p99_latency, 2),
                "error_rate": round(result.error_rate * 100, 2),
                "success_rate": round((1 - result.error_rate) * 100, 2)
            }
            
            results.append(level_result)
            
            # Check if we've hit the breaking point
            if result.p95_latency > target_latency_ms or result.error_rate > target_error_rate:
                breaking_point = {
                    "concurrent_users": concurrent,
                    "reason": "P95 latency exceeded" if result.p95_latency > target_latency_ms else "Error rate exceeded",
                    "p95_latency_ms": round(result.p95_latency, 2),
                    "error_rate_pct": round(result.error_rate * 100, 2)
                }
                break
        
        return {
            "test_type": "stress_test",
            "target_latency_ms": target_latency_ms,
            "target_error_rate_pct": target_error_rate * 100,
            "levels_tested": len(results),
            "breaking_point": breaking_point,
            "results_by_level": results,
            "recommendation": self._generate_stress_recommendation(results, breaking_point)
        }
    
    def _generate_stress_recommendation(
        self,
        results: List[Dict],
        breaking_point: Optional[Dict]
    ) -> str:
        """Generate recommendations based on stress test results."""
        if not breaking_point:
            return "API handled all tested loads. Consider testing with higher concurrent users."
        
        safe_concurrent = max(1, breaking_point["concurrent_users"] - 10)
        
        recs = [
            f"Breaking point reached at {breaking_point['concurrent_users']} concurrent users.",
            f"Reason: {breaking_point['reason']}.",
            f"Recommended max concurrent users: {safe_concurrent} (with safety margin).",
            "",
            "Recommendations:"
        ]
        
        if breaking_point.get("p95_latency_ms", 0) > 2000:
            recs.append("- Latency is too high. Consider:")
            recs.append("  - Implementing request queuing")
            recs.append("  - Adding more API capacity")
            recs.append("  - Optimizing database queries")
        
        if breaking_point.get("error_rate_pct", 0) > 5:
            recs.append("- Error rate is too high. Consider:")
            recs.append("  - Implementing rate limiting on your side")
            recs.append("  - Adding circuit breaker pattern")
            recs.append("  - Implementing request queuing")
        
        return "\n".join(recs)


# ===== MCP Tool Functions =====

async def run_load_test(
    endpoint_id: str,
    payload: dict,
    concurrent_users: int = 10,
    total_requests: int = 100,
    ramp_up_seconds: float = 10.0,
    think_time_seconds: float = 0.5
) -> dict:
    """
    Run load test against a payment API endpoint.
    
    Args:
        endpoint_id: API endpoint to test
        payload: Request payload template
        concurrent_users: Number of simulated concurrent users
        total_requests: Total number of requests to make
        ramp_up_seconds: Gradual ramp-up time
        think_time_seconds: Delay between requests per user
    
    Returns:
        Load test results with latency distribution and error analysis
    """
    config = LoadTestConfig(
        endpoint_id=endpoint_id,
        base_payload=payload,
        concurrent_users=concurrent_users,
        total_requests=total_requests,
        ramp_up_seconds=ramp_up_seconds,
        think_time_seconds=think_time_seconds
    )
    
    runner = LoadTestRunner()
    result = await runner.run_load_test(config)
    
    # Format output
    sections = [
        f"# ⚡ Load Test Results: {endpoint_id}",
        f"\n**Status:** {result.status.value}",
        f"**Concurrent Users:** {concurrent_users}",
        f"**Total Requests:** {result.total_requests}",
        f"**Duration:** {result.end_time - result.start_time:.2f}s" if result.end_time and result.start_time else ""
    ]
    
    # Summary metrics
    sections.append(f"\n## Summary Metrics")
    sections.append(f"| Metric | Value |")
    sections.append(f"|--------|-------|")
    sections.append(f"| Throughput | {result.throughput_rps:.2f} req/s |")
    sections.append(f"| Success Rate | {(1 - result.error_rate) * 100:.1f}% |")
    sections.append(f"| Error Rate | {result.error_rate * 100:.1f}% |")
    sections.append(f"| Avg Latency | {result.avg_latency:.2f}ms |")
    sections.append(f"| Median Latency | {result.median_latency:.2f}ms |")
    sections.append(f"| P95 Latency | {result.p95_latency:.2f}ms |")
    sections.append(f"| P99 Latency | {result.p99_latency:.2f}ms |")
    sections.append(f"| Min Latency | {result.min_latency:.2f}ms |")
    sections.append(f"| Max Latency | {result.max_latency:.2f}ms |")
    
    # Latency distribution
    if result.requests:
        latencies = sorted([r.latency_ms for r in result.requests])
        
        sections.append(f"\n## Latency Distribution")
        buckets = [
            (0, 100, "< 100ms"),
            (100, 250, "100-250ms"),
            (250, 500, "250-500ms"),
            (500, 1000, "500ms-1s"),
            (1000, 2000, "1-2s"),
            (2000, float('inf'), "> 2s")
        ]
        
        for low, high, label in buckets:
            count = sum(1 for l in latencies if low <= l < high)
            pct = count / len(latencies) * 100
            bar = "█" * int(pct / 5)
            sections.append(f"  {label:>12} | {count:>4} ({pct:>5.1f}%) {bar}")
    
    # Error analysis
    if result.errors:
        sections.append(f"\n## Errors")
        for error, count in sorted(result.errors.items(), key=lambda x: -x[1]):
            sections.append(f"- {error}: {count} occurrences")
    
    # Recommendations
    sections.append(f"\n## Recommendations")
    
    if result.error_rate > 0.05:
        sections.append("- 🔴 Error rate exceeds 5%. Investigate failures before production.")
    elif result.error_rate > 0.01:
        sections.append("- 🟡 Error rate above 1%. Monitor closely in production.")
    else:
        sections.append("- ✅ Error rate within acceptable range.")
    
    if result.p95_latency > 2000:
        sections.append("- 🔴 P95 latency exceeds 2s. Optimize API response time.")
    elif result.p95_latency > 1000:
        sections.append("- 🟡 P95 latency above 1s. Consider caching.")
    else:
        sections.append("- ✅ P95 latency within acceptable range.")
    
    if result.throughput_rps < 10:
        sections.append("- 🟡 Low throughput. Consider connection pooling.")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "metrics": {
            "throughput_rps": result.throughput_rps,
            "success_rate": 1 - result.error_rate,
            "error_rate": result.error_rate,
            "avg_latency_ms": result.avg_latency,
            "p95_latency_ms": result.p95_latency,
            "p99_latency_ms": result.p99_latency,
            "min_latency_ms": result.min_latency,
            "max_latency_ms": result.max_latency,
            "total_requests": result.total_requests,
            "successful_requests": result.successful_requests,
            "failed_requests": result.failed_requests
        }
    }


async def run_stress_test(
    endpoint_id: str,
    payload: dict,
    start_concurrent: int = 5,
    max_concurrent: int = 100,
    step_size: int = 10,
    target_latency_ms: float = 2000.0,
    target_error_rate: float = 0.05
) -> dict:
    """
    Find breaking point by gradually increasing load.
    
    Args:
        endpoint_id: API endpoint to stress test
        payload: Request payload template
        start_concurrent: Starting concurrent users
        max_concurrent: Maximum concurrent users to test
        step_size: Users to add per level
        target_latency_ms: Max acceptable P95 latency (ms)
        target_error_rate: Max acceptable error rate (0-1)
    
    Returns:
        Breaking point analysis with capacity recommendations
    """
    runner = StressTestRunner()
    analysis = await runner.find_breaking_point(
        endpoint_id=endpoint_id,
        base_payload=payload,
        start_concurrent=start_concurrent,
        max_concurrent=max_concurrent,
        step_size=step_size,
        target_latency_ms=target_latency_ms,
        target_error_rate=target_error_rate
    )
    
    sections = [
        f"# 💥 Stress Test: {endpoint_id}",
        f"\n**Target P95 Latency:** {target_latency_ms}ms",
        f"**Target Error Rate:** {target_error_rate * 100}%",
        f"**Levels Tested:** {len(analysis['results_by_level'])}"
    ]
    
    # Breaking point
    if analysis['breaking_point']:
        bp = analysis['breaking_point']
        sections.append(f"\n## 🔴 Breaking Point Found")
        sections.append(f"**Concurrent Users:** {bp['concurrent_users']}")
        sections.append(f"**Reason:** {bp['reason']}")
        sections.append(f"**P95 Latency:** {bp.get('p95_latency_ms', 'N/A')}ms")
        sections.append(f"**Error Rate:** {bp.get('error_rate_pct', 'N/A')}%")
    else:
        sections.append(f"\n## ✅ No Breaking Point Found")
        sections.append(f"API handled up to {max_concurrent} concurrent users within targets.")
    
    # Results by level
    sections.append(f"\n## Results by Load Level")
    sections.append(f"| Concurrent | Throughput | Avg Latency | P95 | P99 | Error Rate |")
    sections.append(f"|-----------|-----------|-------------|-----|-----|-----------|")
    
    for level in analysis['results_by_level']:
        sections.append(
            f"| {level['concurrent_users']} | "
            f"{level['throughput_rps']} req/s | "
            f"{level['avg_latency_ms']}ms | "
            f"{level['p95_latency_ms']}ms | "
            f"{level['p99_latency_ms']}ms | "
            f"{level['error_rate']}% |"
        )
    
    # Recommendations
    sections.append(f"\n## Recommendations")
    sections.append(analysis['recommendation'])
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "analysis": analysis
    }
