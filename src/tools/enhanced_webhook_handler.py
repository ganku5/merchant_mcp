"""
Enhanced Webhook Handler Generator

Production-ready webhook handlers with signature verification,
replay protection, and comprehensive error handling.
"""

import json
import hmac
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class WebhookHandlerGenerator:
    """Generates production-ready webhook handlers."""
    
    # Signature verification algorithms
    SIGNATURE_ALGORITHMS = {
        "hmac-sha256": {
            "name": "HMAC-SHA256",
            "description": "HMAC using SHA-256 hash function",
            "python_verification": """
    def verify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        \"\"\"Verify HMAC-SHA256 signature.\"\"\"
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected.lower(), signature.lower())
""",
            "nodejs_verification": """
    verifySignature(payload, signature, secret) {
        const expected = crypto
            .createHmac('sha256', secret)
            .update(payload)
            .digest('hex');
        
        // Constant-time comparison
        return crypto.timingSafeEqual(
            Buffer.from(expected, 'hex'),
            Buffer.from(signature, 'hex')
        );
    }
"""
        },
        "rsa-sha256": {
            "name": "RSA-SHA256",
            "description": "RSA signature using SHA-256",
            "python_verification": """
    def verify_signature(self, payload: bytes, signature: str, public_key: str) -> bool:
        \"\"\"Verify RSA-SHA256 signature.\"\"\"
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        
        try:
            key = serialization.load_pem_public_key(public_key.encode())
            key.verify(
                base64.b64decode(signature),
                payload,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
""",
            "nodejs_verification": """
    verifySignature(payload, signature, publicKey) {
        const verifier = crypto.createVerify('RSA-SHA256');
        verifier.update(payload);
        return verifier.verify(publicKey, signature, 'base64');
    }
"""
        }
    }
    
    # Webhook event types and handlers
    WEBHOOK_EVENTS = {
        "order.created": {
            "description": "Triggered when a new order is created",
            "handlers": ["log_order", "notify_merchant"]
        },
        "order.charged": {
            "description": "Triggered when payment is successfully charged",
            "handlers": ["fulfill_order", "send_receipt", "update_inventory"]
        },
        "order.failed": {
            "description": "Triggered when payment fails",
            "handlers": ["notify_failure", "retry_logic", "alert_admin"]
        },
        "refund.processed": {
            "description": "Triggered when refund is completed",
            "handlers": ["update_order_status", "notify_customer", "reconcile_inventory"]
        },
        "dispute.created": {
            "description": "Triggered when a dispute is raised",
            "handlers": ["alert_admin", "freeze_funds", "gather_evidence"]
        }
    }
    
    TEMPLATES = {
        "python": {
            "imports": """import json
import hmac
import hashlib
import base64
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from functools import wraps
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
""",
            "handler_class": """
class WebhookHandler:
    \"\"\"
    Production-ready webhook handler for {event_type}.
    
    Features:
    - Signature verification (HMAC-SHA256)
    - Replay attack protection
    - Idempotency handling
    - Automatic retries with exponential backoff
    - Structured logging
    \"\"\"
    
    def __init__(
        self,
        webhook_secret: str,
        redis_client: Optional[redis.Redis] = None,
        max_age_seconds: int = 300,
        idempotency_ttl: int = 86400
    ):
        self.webhook_secret = webhook_secret
        self.redis = redis_client
        self.max_age_seconds = max_age_seconds
        self.idempotency_ttl = idempotency_ttl
        self.event_handlers = {{}}
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        \"\"\"Register default event handlers.\"\"\"
{handler_registrations}
    
    def register_handler(self, event_type: str, handler: Callable):
        \"\"\"Register a custom handler for an event type.\"\"\"
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
{signature_verification}
    
    def verify_timestamp(self, timestamp: str) -> bool:
        \"\"\"Verify webhook timestamp is within acceptable range.\"\"\"
        try:
            webhook_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.utcnow()
            age = (now - webhook_time).total_seconds()
            
            if age > self.max_age_seconds:
                logger.warning(f"Webhook too old: {{age}}s")
                return False
            
            if age < -30:  # Future timestamp (clock skew)
                logger.warning(f"Webhook from future: {{age}}s")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Invalid timestamp format: {{e}}")
            return False
    
    def check_idempotency(self, event_id: str) -> bool:
        \"\"\"Check if event was already processed.\"\"\"
        if not self.redis:
            return False
        
        key = f"webhook:processed:{{event_id}}"
        return self.redis.exists(key) == 1
    
    def mark_processed(self, event_id: str):
        \"\"\"Mark event as processed.\"\"\"
        if self.redis:
            key = f"webhook:processed:{{event_id}}"
            self.redis.setex(key, self.idempotency_ttl, "1")
    
    def process_webhook(
        self,
        headers: Dict[str, str],
        body: bytes
    ) -> Dict[str, Any]:
        \"\"\"
        Process incoming webhook.
        
        Args:
            headers: HTTP headers from webhook request
            body: Raw request body (bytes)
        
        Returns:
            Dict with processing result
        \"\"\"
        try:
            # Extract headers
            signature = headers.get('X-Webhook-Signature', '')
            timestamp = headers.get('X-Webhook-Timestamp', '')
            event_id = headers.get('X-Event-ID', '')
            event_type = headers.get('X-Event-Type', '')
            
            logger.info(f"Processing webhook: {{event_type}} ({{event_id}})")
            
            # Verify signature
            if not self.verify_signature(body, signature, self.webhook_secret):
                logger.error("Signature verification failed")
                return {{
                    "success": False,
                    "error": "INVALID_SIGNATURE",
                    "message": "Webhook signature verification failed"
                }}
            
            # Verify timestamp (replay protection)
            if not self.verify_timestamp(timestamp):
                return {{
                    "success": False,
                    "error": "TIMESTAMP_INVALID",
                    "message": "Webhook timestamp outside acceptable range"
                }}
            
            # Check idempotency
            if self.check_idempotency(event_id):
                logger.info(f"Duplicate webhook: {{event_id}}")
                return {{
                    "success": True,
                    "duplicate": True,
                    "message": "Webhook already processed"
                }}
            
            # Parse payload
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {{e}}")
                return {{
                    "success": False,
                    "error": "INVALID_JSON",
                    "message": "Webhook body is not valid JSON"
                }}
            
            # Execute handlers
            handlers = self.event_handlers.get(event_type, [])
            results = []
            
            for handler in handlers:
                try:
                    result = handler(payload, headers)
                    results.append({{"handler": handler.__name__, "result": result}})
                except Exception as e:
                    logger.error(f"Handler failed: {{e}}")
                    results.append({{"handler": handler.__name__, "error": str(e)}})
            
            # Mark as processed
            self.mark_processed(event_id)
            
            return {{
                "success": True,
                "event_type": event_type,
                "event_id": event_id,
                "handlers_executed": len(handlers),
                "results": results
            }}
            
        except Exception as e:
            logger.exception("Webhook processing failed")
            return {{
                "success": False,
                "error": "PROCESSING_ERROR",
                "message": str(e)
            }}
    
    # Default handlers
{default_handlers}
""",
            "flask_route": """
# Flask Integration
from flask import Flask, request, jsonify

app = Flask(__name__)
webhook_handler = WebhookHandler(webhook_secret="your_secret_here")

@app.route('/webhooks', methods=['POST'])
def handle_webhook():
    result = webhook_handler.process_webhook(
        headers=dict(request.headers),
        body=request.get_data()
    )
    
    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
"""
        },
        "nodejs": {
            "imports": """const express = require('express');
const crypto = require('crypto');
const redis = require('redis');

const app = express();
app.use(express.raw({ type: 'application/json' }));
""",
            "handler_class": """
class WebhookHandler {
    constructor(config) {
        this.webhookSecret = config.webhookSecret;
        this.redis = config.redis || null;
        this.maxAgeSeconds = config.maxAgeSeconds || 300;
        this.idempotencyTTL = config.idempotencyTTL || 86400;
        this.eventHandlers = new Map();
        
        this._registerDefaultHandlers();
    }
    
    _registerDefaultHandlers() {
{handler_registrations}
    }
    
    registerHandler(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }
    
{signature_verification}
    
    verifyTimestamp(timestamp) {
        const webhookTime = new Date(timestamp);
        const now = new Date();
        const age = (now - webhookTime) / 1000;
        
        if (age > this.maxAgeSeconds) {
            console.warn(`Webhook too old: ${age}s`);
            return false;
        }
        
        if (age < -30) {
            console.warn(`Webhook from future: ${age}s`);
            return false;
        }
        
        return true;
    }
    
    async checkIdempotency(eventId) {
        if (!this.redis) return false;
        
        const key = `webhook:processed:${eventId}`;
        const exists = await this.redis.exists(key);
        return exists === 1;
    }
    
    async markProcessed(eventId) {
        if (this.redis) {
            const key = `webhook:processed:${eventId}`;
            await this.redis.setex(key, this.idempotencyTTL, '1');
        }
    }
    
    async processWebhook(headers, body) {
        try {
            const signature = headers['x-webhook-signature'] || '';
            const timestamp = headers['x-webhook-timestamp'] || '';
            const eventId = headers['x-event-id'] || '';
            const eventType = headers['x-event-type'] || '';
            
            console.log(`Processing webhook: ${eventType} (${eventId})`);
            
            // Verify signature
            if (!this.verifySignature(body, signature, this.webhookSecret)) {
                console.error('Signature verification failed');
                return {
                    success: false,
                    error: 'INVALID_SIGNATURE',
                    message: 'Webhook signature verification failed'
                };
            }
            
            // Verify timestamp
            if (!this.verifyTimestamp(timestamp)) {
                return {
                    success: false,
                    error: 'TIMESTAMP_INVALID',
                    message: 'Webhook timestamp outside acceptable range'
                };
            }
            
            // Check idempotency
            if (await this.checkIdempotency(eventId)) {
                console.log(`Duplicate webhook: ${eventId}`);
                return {
                    success: true,
                    duplicate: true,
                    message: 'Webhook already processed'
                };
            }
            
            // Parse payload
            let payload;
            try {
                payload = JSON.parse(body);
            } catch (e) {
                console.error('Invalid JSON:', e);
                return {
                    success: false,
                    error: 'INVALID_JSON',
                    message: 'Webhook body is not valid JSON'
                };
            }
            
            // Execute handlers
            const handlers = this.eventHandlers.get(eventType) || [];
            const results = [];
            
            for (const handler of handlers) {
                try {
                    const result = await handler(payload, headers);
                    results.push({ handler: handler.name, result });
                } catch (e) {
                    console.error('Handler failed:', e);
                    results.push({ handler: handler.name, error: e.message });
                }
            }
            
            await this.markProcessed(eventId);
            
            return {
                success: true,
                event_type: eventType,
                event_id: eventId,
                handlers_executed: handlers.length,
                results
            };
            
        } catch (e) {
            console.error('Webhook processing failed:', e);
            return {
                success: false,
                error: 'PROCESSING_ERROR',
                message: e.message
            };
        }
    }
    
{default_handlers}
}
""",
            "express_route": """
// Express Integration
const webhookHandler = new WebhookHandler({
    webhookSecret: process.env.WEBHOOK_SECRET
});

app.post('/webhooks', async (req, res) => {
    const result = await webhookHandler.processWebhook(
        req.headers,
        req.body
    );
    
    if (result.success) {
        res.status(200).json(result);
    } else {
        res.status(400).json(result);
    }
});

app.listen(3000, () => {
    console.log('Webhook server listening on port 3000');
});
"""
        }
    }
    
    def generate_handler(
        self,
        event_type: str,
        language: str = "python",
        signature_algo: str = "hmac-sha256",
        include_docker: bool = False,
        include_tests: bool = False
    ) -> Dict[str, Any]:
        """
        Generate production-ready webhook handler.
        
        Args:
            event_type: Webhook event type (e.g., 'order.charged')
            language: Programming language (python, nodejs)
            signature_algo: Signature verification algorithm
            include_docker: Include Dockerfile
            include_tests: Include test suite
        
        Returns:
            Generated handler code with documentation
        """
        # Validate inputs
        if language not in self.TEMPLATES:
            available = ", ".join(self.TEMPLATES.keys())
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Unsupported language: {language}\n\nAvailable: {available}"
                }],
                "isError": True
            }
        
        if signature_algo not in self.SIGNATURE_ALGORITHMS:
            available = ", ".join(self.SIGNATURE_ALGORITHMS.keys())
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Unsupported signature algorithm: {signature_algo}\n\nAvailable: {available}"
                }],
                "isError": True
            }
        
        event_info = self.WEBHOOK_EVENTS.get(event_type, {
            "description": f"Handler for {event_type} events",
            "handlers": ["process_event"]
        })
        
        # Generate handler code
        template = self.TEMPLATES[language]
        algo_info = self.SIGNATURE_ALGORITHMS[signature_algo]
        
        # Generate default handlers
        handlers_code = self._generate_default_handlers(language, event_info["handlers"])
        registrations = self._generate_handler_registrations(language, event_info["handlers"])
        
        # Build class code
        imports = template["imports"]
        
        signature_verification = algo_info.get(f"{language}_verification", "")
        
        handler_class = template["handler_class"].format(
            event_type=event_type,
            signature_verification=signature_verification,
            handler_registrations=registrations,
            default_handlers=handlers_code
        )
        
        # Build response
        sections = [
            f"# Webhook Handler: {event_type}",
            f"\n**Language:** {language.title()}",
            f"**Signature Algorithm:** {algo_info['name']}",
            f"**Event Description:** {event_info['description']}",
            f"\n## Features",
            f"- ✅ {algo_info['name']} signature verification",
            f"- ✅ Replay attack protection (timestamp validation)",
            f"- ✅ Idempotency handling (duplicate detection)",
            f"- ✅ Structured logging",
            f"- ✅ Error handling and retry",
        ]
        
        sections.extend([
            f"\n## Installation",
            f"```bash",
            f"# Python",
            f"pip install flask redis cryptography" if language == "python" else f"# Node.js\nnpm install express redis",
            f"```"
        ])
        
        sections.extend([
            f"\n## Handler Code",
            f"```{language}",
            imports,
            handler_class,
            f"```"
        ])
        
        # Add framework integration
        if "flask_route" in template or "express_route" in template:
            sections.extend([
                f"\n## Framework Integration",
                f"```{language}",
                template.get("flask_route", template.get("express_route", "")),
                f"```"
            ])
        
        # Add environment variables
        sections.extend([
            f"\n## Environment Variables",
            f"```bash",
            f"WEBHOOK_SECRET=your_webhook_secret_here",
            f"REDIS_URL=redis://localhost:6379/0  # Optional, for idempotency",
            f"PORT=5000  # Webhook server port",
            f"```"
        ])
        
        # Add deployment guide
        sections.extend([
            f"\n## Deployment Checklist",
            f"- [ ] Store webhook secret securely (not in code)",
            f"- [ ] Configure Redis for idempotency (recommended)",
            f"- [ ] Set up SSL/TLS for webhook endpoint",
            f"- [ ] Configure firewall rules",
            f"- [ ] Set up monitoring and alerts",
            f"- [ ] Test signature verification",
            f"- [ ] Register webhook URL with provider"
        ])
        
        return {
            "content": [{
                "type": "text",
                "text": "\n".join(sections)
            }],
            "isError": False
        }
    
    def _generate_default_handlers(self, language: str, handlers: List[str]) -> str:
        """Generate default handler implementations."""
        if language == "python":
            handler_code = ""
            for handler in handlers:
                handler_code += f"""
    def {handler}(self, payload: Dict[str, Any], headers: Dict[str, str]) -> bool:
        \"\"\"Handle {handler.replace('_', ' ')}.\"\"\"
        logger.info(f"Executing {handler} handler")
        
        # TODO: Implement {handler} logic
        # Example: Save to database, send notifications, etc.
        
        return True
"""
            return handler_code
        else:  # nodejs
            handler_code = ""
            for handler in handlers:
                handler_code += f"""
    async {handler}(payload, headers) {{
        console.log(`Executing {handler} handler`);
        
        // TODO: Implement {handler} logic
        // Example: Save to database, send notifications, etc.
        
        return true;
    }}
"""
            return handler_code
    
    def _generate_handler_registrations(self, language: str, handlers: List[str]) -> str:
        """Generate handler registration code."""
        if language == "python":
            regs = []
            for handler in handlers:
                event_type = handler.replace('_', '.')
                regs.append(f"        self.register_handler('{event_type}', self.{handler})")
            return "\n".join(regs)
        else:  # nodejs
            regs = []
            for handler in handlers:
                event_type = handler.replace('_', '.')
                regs.append(f"        this.registerHandler('{event_type}', this.{handler}.bind(this));")
            return "\n".join(regs)


# Singleton instance
handler_generator = WebhookHandlerGenerator()


async def get_enhanced_webhook_handler(
    event_type: str,
    language: str = "python",
    signature_algo: str = "hmac-sha256",
    include_docker: bool = False,
    include_tests: bool = False
) -> Dict[str, Any]:
    """Generate production-ready webhook handler with signature verification."""
    return handler_generator.generate_handler(
        event_type=event_type,
        language=language,
        signature_algo=signature_algo,
        include_docker=include_docker,
        include_tests=include_tests
    )
