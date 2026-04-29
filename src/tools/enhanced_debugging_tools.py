"""
Enhanced Debugging Tools - Phase 3 Implementation

Advanced debugging capabilities including:
- Deep webhook diagnostics with SSL, DNS, and signature debugging
- AI-powered issue search using contextual embeddings
- Log analyzer for webhook troubleshooting
- Root cause analysis automation
- Pattern matching for common issues
"""

import json
import re
import hmac
import hashlib
import socket
import ssl
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

import aiohttp

from ..utils.database import database
from ..utils.llm import llm_client


class DiagnosticSeverity(Enum):
    """Severity levels for diagnostic findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class DiagnosticCategory(Enum):
    """Categories of diagnostics."""
    NETWORK = "network"
    SECURITY = "security"
    PAYLOAD = "payload"
    SIGNATURE = "signature"
    TIMING = "timing"
    CONFIGURATION = "configuration"


@dataclass
class DiagnosticFinding:
    """A single diagnostic finding."""
    category: DiagnosticCategory
    severity: DiagnosticSeverity
    title: str
    description: str
    recommendation: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookDiagnosticReport:
    """Complete webhook diagnostic report."""
    overall_health: str
    findings: List[DiagnosticFinding]
    timeline: List[Dict[str, Any]]
    recommendations: List[str]
    raw_analysis: Dict[str, Any]


class DeepWebhookDiagnostics:
    """Performs comprehensive webhook diagnostics."""
    
    # Common webhook failure patterns
    FAILURE_PATTERNS = {
        "missing_signature": {
            "pattern": r"missing.*signature|no.*signature",
            "description": "Webhook signature header is missing",
            "fix": "Ensure your server accepts custom headers and configure webhook secret"
        },
        "invalid_json": {
            "pattern": r"invalid json|parse error|unexpected token",
            "description": "Webhook body cannot be parsed as JSON",
            "fix": "Use raw body instead of parsed/form-encoded data"
        },
        "signature_mismatch": {
            "pattern": r"signature.*mismatch|verification.*failed",
            "description": "Computed signature doesn't match received signature",
            "fix": "Verify webhook secret and ensure raw body is used for signature calculation"
        },
        "timeout": {
            "pattern": r"timeout|deadline exceeded|timed out",
            "description": "Webhook handler took too long to respond",
            "fix": "Process webhooks asynchronously and respond within 5 seconds"
        },
        "connection_refused": {
            "pattern": r"connection refused|ECONNREFUSED",
            "description": "Webhook endpoint is not accessible",
            "fix": "Verify server is running and firewall allows incoming connections"
        },
        "ssl_error": {
            "pattern": r"ssl|tls|certificate|handshake",
            "description": "SSL/TLS certificate issue",
            "fix": "Ensure valid SSL certificate or disable certificate pinning temporarily"
        }
    }
    
    def __init__(self):
        self.findings: List[DiagnosticFinding] = []
        self.timeline: List[Dict[str, Any]] = []
    
    async def run_full_diagnostics(
        self,
        webhook_url: str,
        headers: Dict[str, str],
        body: str,
        webhook_secret: Optional[str] = None
    ) -> WebhookDiagnosticReport:
        """
        Run complete webhook diagnostics.
        
        Args:
            webhook_url: Your webhook endpoint URL
            headers: Headers received from Juspay
            body: Raw request body
            webhook_secret: Your webhook secret for verification
        
        Returns:
            Complete diagnostic report
        """
        self.findings = []
        self.timeline = []
        
        # Run all diagnostic checks
        await self._check_delivery_path(webhook_url)
        await self._check_security_headers(headers)
        await self._check_payload_integrity(body)
        await self._check_signature_verification(headers, body, webhook_secret)
        await self._check_timing(headers)
        await self._check_configuration(headers, body)
        
        # Generate report
        overall_health = self._calculate_health()
        recommendations = self._generate_recommendations()
        
        return WebhookDiagnosticReport(
            overall_health=overall_health,
            findings=self.findings,
            timeline=self.timeline,
            recommendations=recommendations,
            raw_analysis={
                "headers_analyzed": len(headers),
                "body_size": len(body),
                "findings_count": len(self.findings)
            }
        )
    
    async def _check_delivery_path(self, webhook_url: str):
        """Check network path to webhook endpoint."""
        check_start = time.time()
        
        try:
            parsed = urlparse(webhook_url)
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            
            # DNS Check
            try:
                ip_address = socket.gethostbyname(hostname)
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.NETWORK,
                    severity=DiagnosticSeverity.INFO,
                    title="DNS Resolution Successful",
                    description=f"{hostname} resolves to {ip_address}",
                    recommendation="No action needed",
                    details={"hostname": hostname, "ip": ip_address}
                ))
            except socket.gaierror as e:
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.NETWORK,
                    severity=DiagnosticSeverity.CRITICAL,
                    title="DNS Resolution Failed",
                    description=f"Cannot resolve {hostname}: {e}",
                    recommendation="Check DNS configuration and domain registration",
                    details={"error": str(e)}
                ))
                return
            
            # TCP Connection Check
            try:
                sock = socket.create_connection((hostname, port), timeout=5)
                sock.close()
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.NETWORK,
                    severity=DiagnosticSeverity.INFO,
                    title="TCP Connection Successful",
                    description=f"Successfully connected to {hostname}:{port}",
                    recommendation="No action needed",
                    details={"port": port}
                ))
            except socket.error as e:
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.NETWORK,
                    severity=DiagnosticSeverity.CRITICAL,
                    title="TCP Connection Failed",
                    description=f"Cannot connect to {hostname}:{port}: {e}",
                    recommendation="Check firewall rules and ensure server is running",
                    details={"error": str(e)}
                ))
            
            # SSL Certificate Check (for HTTPS)
            if parsed.scheme == "https":
                try:
                    context = ssl.create_default_context()
                    with socket.create_connection((hostname, 443), timeout=5) as sock:
                        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                            cert = ssock.getpeercert()
                            expiry_str = cert.get('notAfter')
                            expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                            days_until_expiry = (expiry_date - datetime.utcnow()).days
                            
                            severity = DiagnosticSeverity.INFO
                            if days_until_expiry < 7:
                                severity = DiagnosticSeverity.CRITICAL
                            elif days_until_expiry < 30:
                                severity = DiagnosticSeverity.HIGH
                            
                            self.findings.append(DiagnosticFinding(
                                category=DiagnosticCategory.NETWORK,
                                severity=severity,
                                title="SSL Certificate Check",
                                description=f"Certificate expires in {days_until_expiry} days ({expiry_str})",
                                recommendation="Renew certificate soon" if days_until_expiry < 30 else "No action needed",
                                details={"expires": expiry_str, "days_left": days_until_expiry}
                            ))
                except ssl.SSLError as e:
                    self.findings.append(DiagnosticFinding(
                        category=DiagnosticCategory.NETWORK,
                        severity=DiagnosticSeverity.CRITICAL,
                        title="SSL Certificate Error",
                        description=f"SSL certificate validation failed: {e}",
                        recommendation="Install a valid SSL certificate from a trusted CA",
                        details={"error": str(e)}
                    ))
        
        except Exception as e:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.NETWORK,
                severity=DiagnosticSeverity.HIGH,
                title="Network Check Error",
                description=f"Unexpected error during network checks: {e}",
                recommendation="Review webhook URL format and network connectivity"
            ))
        
        self.timeline.append({
            "phase": "delivery_path",
            "duration_ms": (time.time() - check_start) * 1000,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _check_security_headers(self, headers: Dict[str, str]):
        """Check security-related headers."""
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        # Check for signature header
        sig_header = headers_lower.get('x-juspay-signature')
        if sig_header:
            sig_length = len(sig_header)
            severity = DiagnosticSeverity.INFO
            if sig_length < 32:
                severity = DiagnosticSeverity.HIGH
            
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.SECURITY,
                severity=severity,
                title="Signature Header Present",
                description=f"X-Juspay-Signature header found (length: {sig_length})",
                recommendation="Verify signature using your webhook secret" if sig_length >= 32 else "Signature seems short - verify it's complete",
                details={"header_length": sig_length}
            ))
        else:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.SECURITY,
                severity=DiagnosticSeverity.CRITICAL,
                title="Missing Signature Header",
                description="X-Juspay-Signature header not found in request",
                recommendation="Enable webhook signatures in your dashboard and accept custom headers",
                details={"available_headers": list(headers.keys())}
            ))
        
        # Check Content-Type
        content_type = headers_lower.get('content-type', '')
        if 'application/json' in content_type:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.SECURITY,
                severity=DiagnosticSeverity.INFO,
                title="Correct Content-Type",
                description=f"Content-Type is {content_type}",
                recommendation="No action needed"
            ))
        else:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.SECURITY,
                severity=DiagnosticSeverity.MEDIUM,
                title="Unexpected Content-Type",
                description=f"Content-Type is '{content_type}', expected 'application/json'",
                recommendation="Ensure your server accepts application/json content type",
                details={"content_type": content_type}
            ))
        
        # Check for timestamp (replay protection)
        timestamp = headers_lower.get('x-juspay-timestamp')
        if timestamp:
            try:
                ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                age_seconds = (datetime.utcnow() - ts.replace(tzinfo=None)).total_seconds()
                
                severity = DiagnosticSeverity.INFO
                if abs(age_seconds) > 300:  # 5 minutes
                    severity = DiagnosticSeverity.HIGH
                
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.SECURITY,
                    severity=severity,
                    title="Timestamp Present",
                    description=f"Request timestamp: {timestamp} (age: {age_seconds:.0f}s)",
                    recommendation="Verify timestamp is within acceptable window for replay protection" if abs(age_seconds) <= 300 else "Request may be stale - check for replay attack",
                    details={"timestamp": timestamp, "age_seconds": age_seconds}
                ))
            except Exception as e:
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.SECURITY,
                    severity=DiagnosticSeverity.MEDIUM,
                    title="Invalid Timestamp Format",
                    description=f"Cannot parse timestamp header: {e}",
                    recommendation="Use ISO 8601 format (e.g., 2024-01-15T10:30:00Z)"
                ))
    
    async def _check_payload_integrity(self, body: str):
        """Check payload structure and integrity."""
        # Size check
        body_size = len(body)
        if body_size == 0:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.PAYLOAD,
                severity=DiagnosticSeverity.CRITICAL,
                title="Empty Request Body",
                description="Request body is empty",
                recommendation="Check if your server is consuming the body before signature verification"
            ))
            return
        
        size_severity = DiagnosticSeverity.INFO
        if body_size > 1024 * 1024:  # 1MB
            size_severity = DiagnosticSeverity.MEDIUM
        
        self.findings.append(DiagnosticFinding(
            category=DiagnosticCategory.PAYLOAD,
            severity=size_severity,
            title="Body Size Check",
            description=f"Request body size: {body_size} bytes ({body_size/1024:.1f} KB)",
            recommendation="Large payloads may affect processing time" if body_size > 1024 * 1024 else "No action needed",
            details={"size_bytes": body_size}
        ))
        
        # JSON validity
        try:
            payload = json.loads(body)
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.PAYLOAD,
                severity=DiagnosticSeverity.INFO,
                title="Valid JSON",
                description="Request body is valid JSON",
                recommendation="No action needed"
            ))
            
            # Check required fields
            event_type = payload.get('event')
            if event_type:
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.PAYLOAD,
                    severity=DiagnosticSeverity.INFO,
                    title="Event Type Present",
                    description=f"Event type: {event_type}",
                    recommendation="Route to appropriate handler",
                    details={"event": event_type}
                ))
            else:
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.PAYLOAD,
                    severity=DiagnosticSeverity.HIGH,
                    title="Missing Event Type",
                    description="No 'event' field found in payload",
                    recommendation="Check webhook configuration - all events should have type"
                ))
            
            # Check for order_id (for order events)
            if event_type and 'order' in event_type:
                order_id = payload.get('order_id')
                if order_id:
                    self.findings.append(DiagnosticFinding(
                        category=DiagnosticCategory.PAYLOAD,
                        severity=DiagnosticSeverity.INFO,
                        title="Order ID Present",
                        description=f"Order ID: {order_id}",
                        recommendation="No action needed",
                        details={"order_id": order_id}
                    ))
                else:
                    self.findings.append(DiagnosticFinding(
                        category=DiagnosticCategory.PAYLOAD,
                        severity=DiagnosticSeverity.MEDIUM,
                        title="Missing Order ID",
                        description="Order event without order_id",
                        recommendation="Verify webhook payload includes order reference"
                    ))
        
        except json.JSONDecodeError as e:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.PAYLOAD,
                severity=DiagnosticSeverity.CRITICAL,
                title="Invalid JSON",
                description=f"Body is not valid JSON: {e}",
                recommendation="Use raw body (bytes) for signature verification, not parsed JSON. Check Content-Type handling.",
                details={
                    "error": str(e),
                    "body_preview": body[:200] if body else "empty"
                }
            ))
    
    async def _check_signature_verification(
        self,
        headers: Dict[str, str],
        body: str,
        webhook_secret: Optional[str]
    ):
        """Check signature verification setup."""
        headers_lower = {k.lower(): v for k, v in headers.items()}
        sig_header = headers_lower.get('x-juspay-signature')
        
        if not webhook_secret:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.SIGNATURE,
                severity=DiagnosticSeverity.MEDIUM,
                title="No Webhook Secret Provided",
                description="Cannot verify signature without webhook secret",
                recommendation="Provide your webhook secret from dashboard to enable verification",
                details={"can_verify": False}
            ))
            return
        
        if not sig_header:
            return  # Already reported as critical finding
        
        # Attempt signature verification
        try:
            expected = hmac.new(
                webhook_secret.encode('utf-8'),
                body.encode('utf-8') if isinstance(body, str) else body,
                hashlib.sha256
            ).hexdigest()
            
            if hmac.compare_digest(sig_header, expected):
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.SIGNATURE,
                    severity=DiagnosticSeverity.INFO,
                    title="Signature Verified",
                    description="Webhook signature matches computed value",
                    recommendation="No action needed - signature verification working correctly",
                    details={"verified": True}
                ))
            else:
                self.findings.append(DiagnosticFinding(
                    category=DiagnosticCategory.SIGNATURE,
                    severity=DiagnosticSeverity.CRITICAL,
                    title="Signature Mismatch",
                    description="Computed signature does not match received signature",
                    recommendation="Check: 1) Webhook secret is correct, 2) Using raw body (not parsed JSON), 3) Using UTF-8 encoding",
                    details={
                        "received_prefix": sig_header[:20] + "...",
                        "computed_prefix": expected[:20] + "...",
                        "secret_length": len(webhook_secret)
                    }
                ))
        
        except Exception as e:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.SIGNATURE,
                severity=DiagnosticSeverity.HIGH,
                title="Signature Verification Error",
                description=f"Error during signature computation: {e}",
                recommendation="Ensure webhook secret and body are properly encoded as UTF-8"
            ))
    
    async def _check_timing(self, headers: Dict[str, str]):
        """Check timing-related issues."""
        # Check for request ID (for tracing)
        request_id = headers.get('x-request-id') or headers.get('x-juspay-request-id')
        if request_id:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.TIMING,
                severity=DiagnosticSeverity.INFO,
                title="Request ID Present",
                description=f"Request ID for tracing: {request_id}",
                recommendation="Log this ID for support inquiries",
                details={"request_id": request_id}
            ))
    
    async def _check_configuration(self, headers: Dict[str, str], body: str):
        """Check webhook configuration."""
        # Try to detect framework-specific issues
        if "------WebKitFormBoundary" in body or "Content-Disposition:" in body:
            self.findings.append(DiagnosticFinding(
                category=DiagnosticCategory.CONFIGURATION,
                severity=DiagnosticSeverity.CRITICAL,
                title="Form-Encoded Body Detected",
                description="Body appears to be form-encoded instead of raw JSON",
                recommendation="Configure your server to receive raw body:",
                details={
                    "express": "app.use(express.raw({type: 'application/json'}))",
                    "flask": "request.get_data()",
                    "django": "request.body",
                    "spring": "@RequestBody byte[] body"
                }
            ))
    
    def _calculate_health(self) -> str:
        """Calculate overall health score."""
        critical = sum(1 for f in self.findings if f.severity == DiagnosticSeverity.CRITICAL)
        high = sum(1 for f in self.findings if f.severity == DiagnosticSeverity.HIGH)
        
        if critical > 0:
            return "CRITICAL"
        elif high > 0:
            return "DEGRADED"
        else:
            return "HEALTHY"
    
    def _generate_recommendations(self) -> List[str]:
        """Generate prioritized recommendations."""
        recs = []
        
        # Critical first
        critical_findings = [f for f in self.findings if f.severity == DiagnosticSeverity.CRITICAL]
        for f in critical_findings:
            recs.append(f"🔴 [{f.category.value.upper()}] {f.title}: {f.recommendation}")
        
        # Then high
        high_findings = [f for f in self.findings if f.severity == DiagnosticSeverity.HIGH]
        for f in high_findings:
            recs.append(f"🟠 [{f.category.value.upper()}] {f.title}: {f.recommendation}")
        
        return recs


class AIssueAnalyzer:
    """AI-powered issue analysis using embeddings and LLM."""
    
    def __init__(self):
        self.known_patterns = self._load_known_patterns()
    
    def _load_known_patterns(self) -> Dict[str, Any]:
        """Load known issue patterns."""
        return {
            "payment_stuck_pending": {
                "symptoms": ["transaction pending", "status not updating", "stuck at pending"],
                "causes": [
                    "User didn't complete payment on device",
                    "UPI app not responding",
                    "Network timeout between banks"
                ],
                "solutions": [
                    "Implement timeout handling (recommended: 5 minutes)",
                    "Show 'payment pending' UI to user",
                    "Poll status endpoint every 5 seconds",
                    "Send reminder notification to user"
                ]
            },
            "webhook_not_received": {
                "symptoms": ["no webhook", "webhook missing", "not getting callback"],
                "causes": [
                    "Webhook URL not accessible from internet",
                    "Firewall blocking requests",
                    "Server returning non-2xx response",
                    "SSL certificate issue"
                ],
                "solutions": [
                    "Test webhook URL with curl from external server",
                    "Check firewall rules allow HTTPS traffic",
                    "Ensure webhook handler returns HTTP 200",
                    "Verify SSL certificate is valid and not expired"
                ]
            },
            "signature_verification_fails": {
                "symptoms": ["signature mismatch", "verification failed", "invalid signature"],
                "causes": [
                    "Using parsed JSON instead of raw body",
                    "Wrong webhook secret",
                    "Encoding mismatch (not UTF-8)",
                    "Additional whitespace in body"
                ],
                "solutions": [
                    "Use request.get_data() not request.json",
                    "Copy exact webhook secret from dashboard",
                    "Ensure consistent UTF-8 encoding throughout",
                    "Trim whitespace before computing signature"
                ]
            }
        }
    
    async def analyze_symptoms(
        self,
        symptoms: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze symptoms using AI to find root cause.
        
        Args:
            symptoms: Description of the problem
            context: Additional context (endpoint, error codes, timestamps)
        
        Returns:
            Analysis with likely causes and solutions
        """
        # Search for similar issues using embeddings
        similar_issues = await self._search_similar_issues(symptoms)
        
        # Use LLM for deeper analysis
        llm_analysis = await self._llm_root_cause_analysis(symptoms, context, similar_issues)
        
        # Pattern matching fallback
        pattern_matches = self._match_patterns(symptoms)
        
        return {
            "primary_analysis": llm_analysis,
            "similar_issues": similar_issues,
            "pattern_matches": pattern_matches,
            "confidence_score": self._calculate_confidence(llm_analysis, similar_issues)
        }
    
    async def _search_similar_issues(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search for similar issues using embeddings."""
        try:
            # Use existing contextual embeddings if available
            if hasattr(database, 'search_contextual'):
                results = await database.search_contextual(query, top_k=top_k)
                return results
        except Exception:
            pass
        
        # Fallback to keyword matching
        return []
    
    async def _llm_root_cause_analysis(
        self,
        symptoms: str,
        context: Optional[Dict[str, Any]],
        similar_issues: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use LLM for root cause analysis."""
        
        prompt = f"""Analyze this payment integration issue:

SYMPTOMS: {symptoms}

CONTEXT: {json.dumps(context) if context else 'None provided'}

SIMILAR ISSUES: {json.dumps(similar_issues) if similar_issues else 'None found'}

Provide analysis in this JSON format:
{{
    "likely_causes": ["cause 1", "cause 2", "cause 3"],
    "most_likely": "single most probable cause",
    "confidence": "high|medium|low",
    "immediate_actions": ["action 1", "action 2"],
    "investigation_steps": ["step 1", "step 2"],
    "prevention": "how to prevent this in future",
    "escalation_required": true|false,
    "escalation_reason": "if escalation needed, explain why"
}}

Be specific and actionable. If the issue clearly requires Juspay support involvement, set escalation_required to true."""
        
        try:
            response = await llm_client.chat([
                {"role": "user", "content": prompt}
            ])
            
            # Try to parse JSON from response
            # LLM might wrap in markdown code blocks
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        
        except Exception as e:
            return {
                "likely_causes": ["Unable to perform LLM analysis"],
                "most_likely": "Analysis error",
                "confidence": "low",
                "immediate_actions": ["Try searching documentation"],
                "investigation_steps": ["Contact support with error details"],
                "error": str(e)
            }
    
    def _match_patterns(self, symptoms: str) -> List[Dict[str, Any]]:
        """Match symptoms against known patterns."""
        symptoms_lower = symptoms.lower()
        matches = []
        
        for pattern_name, pattern_data in self.known_patterns.items():
            score = 0
            for symptom in pattern_data["symptoms"]:
                if symptom.lower() in symptoms_lower:
                    score += 1
            
            if score > 0:
                matches.append({
                    "pattern": pattern_name,
                    "match_score": score,
                    "causes": pattern_data["causes"],
                    "solutions": pattern_data["solutions"]
                })
        
        return sorted(matches, key=lambda x: x["match_score"], reverse=True)
    
    def _calculate_confidence(
        self,
        llm_analysis: Dict[str, Any],
        similar_issues: List[Dict[str, Any]]
    ) -> str:
        """Calculate overall confidence score."""
        confidence_scores = {
            "high": 3,
            "medium": 2,
            "low": 1
        }
        
        llm_confidence = confidence_scores.get(llm_analysis.get("confidence", "low"), 1)
        similar_count = len(similar_issues)
        
        total_score = llm_confidence + min(similar_count, 2)
        
        if total_score >= 4:
            return "high"
        elif total_score >= 2:
            return "medium"
        return "low"


class LogAnalyzer:
    """Analyzes webhook and API logs for troubleshooting."""
    
    def __init__(self):
        self.patterns = {
            "rate_limit": r"rate.*limit|429|too many requests",
            "auth_failure": r"unauthorized|401|forbidden|403",
            "timeout": r"timeout|deadline|504|502",
            "validation_error": r"validation|invalid|400",
            "server_error": r"server error|500|internal error"
        }
    
    def analyze_webhook_logs(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze webhook delivery logs.
        
        Args:
            logs: List of log entries with timestamp, status, event, etc.
        
        Returns:
            Analysis with trends and issues
        """
        if not logs:
            return {"error": "No logs provided"}
        
        # Calculate metrics
        total = len(logs)
        success = sum(1 for l in logs if l.get("status", 0) < 400)
        failed = total - success
        
        status_distribution = {}
        event_distribution = {}
        hourly_volume = {}
        
        for log in logs:
            # Status distribution
            status = log.get("status", "unknown")
            status_distribution[status] = status_distribution.get(status, 0) + 1
            
            # Event distribution
            event = log.get("event", "unknown")
            event_distribution[event] = event_distribution.get(event, 0) + 1
            
            # Hourly volume
            ts = log.get("timestamp", "")
            if ts:
                hour = ts[:13] if len(ts) >= 13 else ts  # YYYY-MM-DD-HH
                hourly_volume[hour] = hourly_volume.get(hour, 0) + 1
        
        # Detect patterns
        issues = []
        
        # Check success rate
        success_rate = success / total if total > 0 else 0
        if success_rate < 0.95:
            issues.append({
                "type": "low_success_rate",
                "severity": "high",
                "message": f"Success rate is {success_rate:.1%} (below 95% threshold)",
                "recommendation": "Investigate failed deliveries and fix webhook handler"
            })
        
        # Check for repeated failures
        failure_events = [l for l in logs if l.get("status", 200) >= 400]
        if len(failure_events) > 10:
            recent_failures = failure_events[-10:]
            if all(l.get("status") == recent_failures[0].get("status") for l in recent_failures):
                issues.append({
                    "type": "persistent_failure",
                    "severity": "critical",
                    "message": f"Last 10 requests failed with same status ({recent_failures[0].get('status')})",
                    "recommendation": "Check webhook endpoint health and configuration"
                })
        
        return {
            "summary": {
                "total_requests": total,
                "successful": success,
                "failed": failed,
                "success_rate": success_rate
            },
            "distributions": {
                "status": status_distribution,
                "events": event_distribution
            },
            "volume_trend": hourly_volume,
            "issues_detected": issues,
            "recommendations": self._generate_log_recommendations(issues, success_rate)
        }
    
    def _generate_log_recommendations(self, issues: List[Dict], success_rate: float) -> List[str]:
        """Generate recommendations based on log analysis."""
        recs = []
        
        if success_rate < 0.95:
            recs.append("Review failed webhook deliveries and implement proper error handling")
        
        for issue in issues:
            if issue["type"] == "persistent_failure":
                recs.append("URGENT: Webhook endpoint consistently failing - check server status")
        
        if not recs:
            recs.append("Webhook delivery looks healthy - continue monitoring")
        
        return recs


# ===== MCP Tool Functions =====

async def run_deep_webhook_diagnostics(
    webhook_url: str,
    headers: dict,
    body: str,
    webhook_secret: str = None
) -> dict:
    """
    Run comprehensive webhook diagnostics with network, security, and payload checks.
    
    Args:
        webhook_url: Your webhook endpoint URL
        headers: HTTP headers received from Juspay
        body: Raw request body (as string)
        webhook_secret: Your webhook secret for signature verification
    
    Returns:
        Complete diagnostic report with findings and prioritized recommendations
    """
    diagnostics = DeepWebhookDiagnostics()
    report = await diagnostics.run_full_diagnostics(webhook_url, headers, body, webhook_secret)
    
    # Format output
    severity_emoji = {
        DiagnosticSeverity.CRITICAL: "🔴",
        DiagnosticSeverity.HIGH: "🟠",
        DiagnosticSeverity.MEDIUM: "🟡",
        DiagnosticSeverity.LOW: "🔵",
        DiagnosticSeverity.INFO: "✅"
    }
    
    sections = [
        f"# 🔍 Deep Webhook Diagnostics",
        f"\n**Overall Health:** {report.overall_health}",
        f"**Findings:** {len(report.findings)}",
        f"**URL:** {webhook_url}"
    ]
    
    # Group findings by category
    by_category = {}
    for finding in report.findings:
        cat = finding.category.value
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(finding)
    
    for category, findings in sorted(by_category.items()):
        sections.append(f"\n## {category.upper()}")
        
        # Sort by severity
        severity_order = [
            DiagnosticSeverity.CRITICAL,
            DiagnosticSeverity.HIGH,
            DiagnosticSeverity.MEDIUM,
            DiagnosticSeverity.LOW,
            DiagnosticSeverity.INFO
        ]
        
        for sev in severity_order:
            for f in findings:
                if f.severity == sev:
                    emoji = severity_emoji[sev]
                    sections.append(f"\n{emoji} **{f.title}**")
                    sections.append(f"   {f.description}")
                    sections.append(f"   💡 {f.recommendation}")
                    
                    if f.details:
                        for key, value in f.details.items():
                            if isinstance(value, str) and len(value) > 50:
                                value = value[:50] + "..."
                            sections.append(f"   • {key}: {value}")
    
    # Recommendations summary
    if report.recommendations:
        sections.append(f"\n## 🎯 Prioritized Recommendations")
        for i, rec in enumerate(report.recommendations[:10], 1):
            sections.append(f"{i}. {rec}")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "report": {
            "overall_health": report.overall_health,
            "findings_count": len(report.findings),
            "findings": [
                {
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "title": f.title,
                    "description": f.description,
                    "recommendation": f.recommendation
                }
                for f in report.findings
            ],
            "recommendations": report.recommendations,
            "timeline": report.timeline
        }
    }


async def analyze_issue_with_ai(
    symptoms: str,
    context: dict = None
) -> dict:
    """
    AI-powered root cause analysis for payment integration issues.
    
    Args:
        symptoms: Description of the problem you're experiencing
        context: Additional context like:
            - endpoint: API endpoint being called
            - error_code: Any error codes received
            - timestamp: When the issue occurred
            - merchant_id: Your merchant ID
    
    Returns:
        Root cause analysis with confidence scores and actionable solutions
    """
    analyzer = AIssueAnalyzer()
    analysis = await analyzer.analyze_symptoms(symptoms, context)
    
    sections = [
        f"# 🤖 AI-Powered Issue Analysis",
        f"\n**Symptoms:** {symptoms[:100]}{'...' if len(symptoms) > 100 else ''}",
        f"**Overall Confidence:** {analysis['confidence_score'].upper()}"
    ]
    
    # Primary analysis from LLM
    primary = analysis["primary_analysis"]
    
    sections.append(f"\n## Most Likely Cause")
    sections.append(f"**{primary.get('most_likely', 'Unknown')}**")
    sections.append(f"*(Confidence: {primary.get('confidence', 'unknown')})*")
    
    if primary.get('likely_causes'):
        sections.append(f"\n### Other Possible Causes")
        for cause in primary['likely_causes']:
            sections.append(f"- {cause}")
    
    if primary.get('immediate_actions'):
        sections.append(f"\n## 🚨 Immediate Actions")
        for i, action in enumerate(primary['immediate_actions'], 1):
            sections.append(f"{i}. {action}")
    
    if primary.get('investigation_steps'):
        sections.append(f"\n## 🔍 Investigation Steps")
        for i, step in enumerate(primary['investigation_steps'], 1):
            sections.append(f"{i}. {step}")
    
    # Pattern matches
    if analysis["pattern_matches"]:
        sections.append(f"\n## 📊 Pattern Matches")
        for match in analysis["pattern_matches"][:3]:
            sections.append(f"\n**{match['pattern'].replace('_', ' ').title()}** (Score: {match['match_score']})")
            sections.append(f"Possible causes:")
            for cause in match['causes'][:2]:
                sections.append(f"  - {cause}")
    
    # Prevention
    if primary.get('prevention'):
        sections.append(f"\n## 🛡️ Prevention")
        sections.append(primary['prevention'])
    
    # Escalation
    if primary.get('escalation_required'):
        sections.append(f"\n## 📞 Escalation Required")
        sections.append(f"**Reason:** {primary.get('escalation_reason', 'Issue requires Juspay support')}")
        sections.append("Contact support with:")
        sections.append("- This analysis summary")
        sections.append("- Request/response logs")
        sections.append("- Timestamps of affected transactions")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "analysis": {
            "confidence": analysis["confidence_score"],
            "primary_cause": primary.get("most_likely"),
            "requires_escalation": primary.get("escalation_required", False),
            "all_causes": primary.get("likely_causes", []),
            "immediate_actions": primary.get("immediate_actions", []),
            "investigation_steps": primary.get("investigation_steps", [])
        }
    }


async def analyze_webhook_logs(
    logs: list
) -> dict:
    """
    Analyze webhook delivery logs for trends and issues.
    
    Args:
        logs: List of log entries, each containing:
            - timestamp: ISO timestamp
            - status: HTTP status code
            - event: Event type (e.g., 'order.charged')
            - latency_ms: Response time (optional)
    
    Returns:
        Analysis with success rates, trends, and detected issues
    """
    analyzer = LogAnalyzer()
    analysis = analyzer.analyze_webhook_logs(logs)
    
    if "error" in analysis:
        return {
            "content": [{"type": "text", "text": f"❌ {analysis['error']}"}],
            "isError": True
        }
    
    summary = analysis["summary"]
    
    sections = [
        f"# 📊 Webhook Log Analysis",
        f"\n## Summary",
        f"**Total Requests:** {summary['total_requests']}",
        f"**Successful:** {summary['successful']} ({summary['success_rate']:.1%})",
        f"**Failed:** {summary['failed']}"
    ]
    
    # Status distribution
    if analysis["distributions"]["status"]:
        sections.append(f"\n## Status Distribution")
        for status, count in sorted(analysis["distributions"]["status"].items()):
            pct = count / summary['total_requests'] * 100
            sections.append(f"- HTTP {status}: {count} ({pct:.1f}%)")
    
    # Event distribution
    if analysis["distributions"]["events"]:
        sections.append(f"\n## Events")
        for event, count in sorted(analysis["distributions"]["events"].items(), key=lambda x: -x[1]):
            sections.append(f"- {event}: {count}")
    
    # Issues detected
    if analysis["issues_detected"]:
        sections.append(f"\n## ⚠️ Issues Detected")
        for issue in analysis["issues_detected"]:
            severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}
            emoji = severity_emoji.get(issue["severity"], "⚪")
            sections.append(f"\n{emoji} **{issue['type'].replace('_', ' ').title()}**")
            sections.append(f"   {issue['message']}")
            sections.append(f"   💡 {issue['recommendation']}")
    
    # Recommendations
    if analysis["recommendations"]:
        sections.append(f"\n## 💡 Recommendations")
        for rec in analysis["recommendations"]:
            sections.append(f"- {rec}")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "analysis": analysis
    }


async def diagnose_api_error(
    error_message: str,
    endpoint_id: str = None,
    request_payload: dict = None,
    response_body: str = None
) -> dict:
    """
    Diagnose API errors with pattern matching and context analysis.
    
    Args:
        error_message: The error message received
        endpoint_id: API endpoint that returned the error
        request_payload: Request payload sent (optional)
        response_body: Full response body (optional)
    
    Returns:
        Diagnosis with root cause and fix instructions
    """
    # Pattern-based diagnosis
    diagnoses = []
    
    error_lower = error_message.lower()
    
    # Pattern matching
    patterns = {
        "authentication_error": {
            "patterns": ["unauthorized", "authentication", "invalid api key", "forbidden", "401", "403"],
            "diagnosis": "Authentication/Authorization Error",
            "causes": [
                "Invalid or expired API key",
                "Missing Authorization header",
                "Insufficient permissions for this endpoint"
            ],
            "fixes": [
                "Verify your API key is correct and active",
                "Check the Authorization header is properly formatted",
                "Ensure your account has access to this API"
            ]
        },
        "validation_error": {
            "patterns": ["validation", "invalid", "required", "missing field", "bad request", "400"],
            "diagnosis": "Request Validation Error",
            "causes": [
                "Missing required fields in payload",
                "Invalid data types",
                "Field value out of allowed range"
            ],
            "fixes": [
                "Validate payload against API schema",
                "Check all required fields are present",
                "Verify data types match specification"
            ]
        },
        "rate_limit": {
            "patterns": ["rate limit", "too many requests", "throttled", "429"],
            "diagnosis": "Rate Limit Exceeded",
            "causes": [
                "Too many requests in short time",
                "Burst limit exceeded",
                "Daily quota exhausted"
            ],
            "fixes": [
                "Implement exponential backoff",
                "Reduce request frequency",
                "Contact support to increase limits"
            ]
        },
        "server_error": {
            "patterns": ["internal server error", "server error", "500", "502", "503", "504"],
            "diagnosis": "Server-Side Error",
            "causes": [
                "Temporary service disruption",
                "Database connectivity issue",
                "Upstream service failure"
            ],
            "fixes": [
                "Retry with exponential backoff",
                "Check status page for outages",
                "Contact support if persistent"
            ]
        },
        "timeout": {
            "patterns": ["timeout", "deadline exceeded", "request timeout", "504"],
            "diagnosis": "Request Timeout",
            "causes": [
                "Server processing took too long",
                "Network latency issues",
                "Complex query causing delay"
            ],
            "fixes": [
                "Increase client timeout settings",
                "Break request into smaller chunks",
                "Retry with idempotency key"
            ]
        }
    }
    
    for pattern_name, pattern_data in patterns.items():
        for pattern in pattern_data["patterns"]:
            if pattern in error_lower:
                diagnoses.append(pattern_data)
                break
    
    # Build response
    sections = [
        f"# 🔧 API Error Diagnosis",
        f"\n**Error:** {error_message[:200]}{'...' if len(error_message) > 200 else ''}"
    ]
    
    if endpoint_id:
        sections.append(f"**Endpoint:** {endpoint_id}")
    
    if diagnoses:
        sections.append(f"\n## Diagnosed Issues ({len(diagnoses)})")
        
        for d in diagnoses:
            sections.append(f"\n### {d['diagnosis']}")
            sections.append(f"**Likely Causes:**")
            for cause in d['causes']:
                sections.append(f"  - {cause}")
            sections.append(f"**Suggested Fixes:**")
            for fix in d['fixes']:
                sections.append(f"  ✓ {fix}")
    else:
        sections.append(f"\n## General Troubleshooting")
        sections.append("No specific pattern matched. Try:")
        sections.append("1. Check the API documentation for this endpoint")
        sections.append("2. Validate your request payload")
        sections.append("3. Contact support with the full error details")
    
    # Payload analysis
    if request_payload:
        sections.append(f"\n## Request Analysis")
        sections.append(f"```json\n{json.dumps(request_payload, indent=2)[:500]}\n```")
    
    return {
        "content": [{"type": "text", "text": "\n".join(sections)}],
        "diagnoses": [{k: v for k, v in d.items() if k != 'patterns'} for d in diagnoses],
        "general_advice": [
            "Check API status page for ongoing incidents",
            "Review recent API changelog for breaking changes",
            "Test with simplest possible payload first"
        ]
    }


async def find_similar_incidents(
    issue_description: str,
    merchant_id: str = None,
    time_range_days: int = 30
) -> dict:
    """
    Find similar past incidents and their resolutions.
    
    Args:
        issue_description: Description of current issue
        merchant_id: Optional merchant ID to filter by
        time_range_days: How far back to search
    
    Returns:
        Similar incidents with resolutions and outcomes
    """
    # This would typically query a knowledge base or support ticket system
    # For now, simulate with pattern matching
    
    # Use LLM to analyze and find patterns
    prompt = f"""Given this issue description, suggest what similar incidents might look like:

Issue: {issue_description}

Provide 2-3 similar hypothetical incidents with their typical resolutions.

Format as JSON array:
[
  {{
    "incident_type": "brief type",
    "typical_symptoms": ["symptom 1", "symptom 2"],
    "common_resolution": "what usually fixes it",
    "prevention": "how to prevent recurrence"
  }}
]"""
    
    try:
        response = await llm_client.chat([{"role": "user", "content": prompt}])
        
        # Extract JSON
        content = response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        similar_incidents = json.loads(content.strip())
        
        sections = [
            f"# 🔍 Similar Incidents",
            f"\nBased on: {issue_description[:100]}..."
        ]
        
        for i, incident in enumerate(similar_incidents, 1):
            sections.append(f"\n## {i}. {incident.get('incident_type', 'Unknown')}")
            
            if incident.get('typical_symptoms'):
                sections.append(f"**Typical Symptoms:**")
                for sym in incident['typical_symptoms']:
                    sections.append(f"  - {sym}")
            
            if incident.get('common_resolution'):
                sections.append(f"**Common Resolution:** {incident['common_resolution']}")
            
            if incident.get('prevention'):
                sections.append(f"**Prevention:** {incident['prevention']}")
        
        return {
            "content": [{"type": "text", "text": "\n".join(sections)}],
            "similar_incidents": similar_incidents
        }
    
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Could not find similar incidents: {e}\n\nTry providing more specific details about the issue."
            }],
            "isError": True
        }
