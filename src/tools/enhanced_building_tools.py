"""
Enhanced Building Tools for Production-Ready MCP.

Provides intelligent payload generation, multi-language code examples,
deep validation, and production-ready webhook handlers.
"""

import json
import re
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from ..utils.database import database


class SmartDefaultsProvider:
    """Provides intelligent default values based on field types and constraints."""
    
    # Smart defaults by type
    TYPE_DEFAULTS = {
        "string": {
            "default": "sample_value",
            "email": "user@example.com",
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "url": "https://example.com/callback",
            "phone": "+919876543210",
            "date": "2024-01-15",
            "datetime": "2024-01-15T10:30:00+05:30",
            "timestamp": "1705310400000",
            "currency": "INR",
            "country": "IN",
            "language": "en"
        },
        "number": {
            "default": 100,
            "integer": 42,
            "float": 99.99,
            "double": 99.99,
            "decimal": "99.99",
            "percentage": 15.5,
            "amount": 1000.00
        },
        "boolean": {
            "default": True,
            "flag": False
        },
        "array": {
            "default": [],
            "strings": ["item1", "item2"],
            "numbers": [1, 2, 3],
            "objects": [{"id": 1}, {"id": 2}]
        },
        "object": {
            "default": {}
        }
    }
    
    # Domain-specific defaults
    DOMAIN_DEFAULTS = {
        "amount": "1000.00",
        "currency": "INR",
        "order_id": lambda: f"order_{datetime.now().strftime('%Y%m%d')}_{random.randint(1000, 9999)}",
        "transaction_id": lambda: f"txn_{random.randint(10000000, 99999999)}",
        "reference_id": lambda: f"ref_{random.randint(10000000, 99999999)}",
        "request_id": lambda: f"req_{random.randint(10000000, 99999999)}",
        "customer_id": lambda: f"cust_{random.randint(10000, 99999)}",
        "merchant_id": "MERCHANT123",
        "vpa": "customer@upi",
        "card_number": "4111111111111111",
        "cvv": "123",
        "expiry": "12/25",
        "otp": "123456",
        "mpin": "1234",
        "geocode": "12.9716,77.5946",
        "ip_address": "192.168.1.1"
    }
    
    @classmethod
    def get_default(cls, field_type: str, field_name: str = "", constraints: Dict = None) -> Any:
        """Get smart default based on type and field name."""
        constraints = constraints or {}
        
        # Check domain-specific patterns in field name
        field_lower = field_name.lower()
        for pattern, value in cls.DOMAIN_DEFAULTS.items():
            if pattern in field_lower:
                return value() if callable(value) else value
        
        # Check type-specific defaults
        type_defaults = cls.TYPE_DEFAULTS.get(field_type, {})
        
        # Check for enum constraints
        if constraints.get("enum"):
            return constraints["enum"][0]
        
        # Check for pattern (generate matching string)
        if field_type == "string" and constraints.get("pattern"):
            return cls._generate_from_pattern(constraints["pattern"])
        
        # Return default for type
        return type_defaults.get("default")
    
    @classmethod
    def _generate_from_pattern(cls, pattern: str) -> str:
        """Generate string matching regex pattern."""
        # Simplified pattern matching
        if "UUID" in pattern.upper() or "^[0-9a-f" in pattern:
            return "550e8400-e29b-41d4-a716-446655440000"
        elif "timestamp" in pattern.lower() or "^\\d{13}$" in pattern:
            return "1705310400000"
        elif "amount" in pattern.lower():
            return "1000.00"
        elif "email" in pattern.lower():
            return "user@example.com"
        elif "ip" in pattern.lower():
            return "192.168.1.1"
        elif "^\\d" in pattern:  # Numeric pattern
            length = pattern.count("\\d") if "{" not in pattern else 10
            return "".join(random.choices(string.digits, k=min(length, 10)))
        else:
            return "sample_value"


class PayloadGenerator:
    """Intelligent payload generator with nested object support."""
    
    def __init__(self):
        self.default_provider = SmartDefaultsProvider()
        self.generated_refs = {}  # Track generated IDs for consistency
    
    async def generate_payload(
        self,
        endpoint_id: str,
        include_optional: bool = False,
        include_conditional: bool = False,
        fill_references: bool = True,
        output_format: str = "json"  # json, python, nodejs, java
    ) -> Dict[str, Any]:
        """
        Generate intelligent payload for an endpoint.
        
        Args:
            endpoint_id: API endpoint identifier
            include_optional: Include optional fields
            include_conditional: Include conditional fields
            fill_references: Generate consistent reference IDs
            output_format: Output format for examples
        
        Returns:
            Generated payload with metadata
        """
        if database._pool is None:
            await database.connect()
        
        conn = database.pool
        
        async with conn.acquire() as db_conn:
            # Get API spec
            spec = await db_conn.fetchrow("""
                SELECT * FROM api_specs_v2 WHERE endpoint_id = $1
                ORDER BY api_version DESC LIMIT 1
            """, endpoint_id)
            
            if not spec:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"❌ Endpoint '{endpoint_id}' not found"
                    }],
                    "isError": True
                }
            
            # Get request fields
            fields = await db_conn.fetch("""
                SELECT * FROM api_fields 
                WHERE spec_id = $1 AND context = 'request'
                ORDER BY parent_path, display_order
            """, spec['spec_id'])
            
            # Build payload tree
            payload = self._build_payload_tree(
                fields, 
                include_optional=include_optional,
                include_conditional=include_conditional
            )
            
            # Generate formatted output
            if output_format == "json":
                formatted = json.dumps(payload, indent=2, ensure_ascii=False)
            else:
                formatted = self._format_for_language(payload, output_format, endpoint_id)
            
            # Build response
            sections = [
                f"# Generated Payload: {endpoint_id}",
                f"\n**Method:** {spec['method']}",
                f"**Path:** {spec['path']}",
                f"\n## Payload ({output_format})",
                f"```{output_format if output_format != 'json' else 'json'}\n{formatted}\n```"
            ]
            
            # Add field explanations
            if fields:
                sections.append("\n## Field Explanations")
                for f in fields:
                    if f['requirement'] == 'mandatory':
                        req_label = "*"
                    elif f['requirement'] == 'conditional':
                        req_label = "†"
                    else:
                        req_label = ""
                    
                    sections.append(f"- **{f['field_name']}**{req_label}: {f.get('description', 'No description')}")
                    
                    # Add constraints info
                    constraints = f.get('constraints', {})
                    if isinstance(constraints, str):
                        try:
                            constraints = json.loads(constraints)
                        except:
                            constraints = {}
                    
                    if constraints.get('pattern'):
                        sections.append(f"  - Pattern: `{constraints['pattern']}`")
                    if constraints.get('enum'):
                        sections.append(f"  - Allowed values: {constraints['enum']}")
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }],
                "isError": False
            }
    
    def _build_payload_tree(
        self, 
        fields: List[Dict], 
        parent_path: str = "",
        include_optional: bool = False,
        include_conditional: bool = False
    ) -> Dict[str, Any]:
        """Build nested payload structure from flat field list."""
        result = {}
        
        for field in fields:
            field_parent = field.get('parent_path', '')
            
            # Skip if not in current parent
            if field_parent != parent_path:
                continue
            
            # Check requirement level
            requirement = field.get('requirement', 'optional')
            if requirement == 'optional' and not include_optional:
                continue
            if requirement == 'conditional' and not include_conditional:
                continue
            
            field_name = field['field_name']
            field_type = field.get('field_type', 'string')
            
            # Get constraints
            constraints = field.get('constraints', {})
            if isinstance(constraints, str):
                try:
                    constraints = json.loads(constraints)
                except:
                    constraints = {}
            
            # Generate value based on type
            if field_type == "object":
                # Recursively build nested object
                child_value = self._build_payload_tree(
                    fields,
                    parent_path=field_name if not parent_path else f"{parent_path}.{field_name}",
                    include_optional=include_optional,
                    include_conditional=include_conditional
                )
                if child_value:  # Only add if has children
                    result[field_name] = child_value
            elif field_type == "array":
                # Build array with sample items
                subtype = field.get('subtype', 'object')
                if subtype == 'object':
                    # Get child fields for array items
                    array_item_path = f"{field_name}[*]"
                    if parent_path:
                        array_item_path = f"{parent_path}.{array_item_path}"
                    
                    child_value = self._build_payload_tree(
                        fields,
                        parent_path=array_item_path,
                        include_optional=include_optional,
                        include_conditional=include_conditional
                    )
                    result[field_name] = [child_value] if child_value else []
                else:
                    # Primitive array
                    result[field_name] = self.default_provider.TYPE_DEFAULTS.get('array', {}).get('strings', [])
            else:
                # Primitive type
                result[field_name] = self.default_provider.get_default(
                    field_type, field_name, constraints
                )
        
        return result
    
    def _format_for_language(self, payload: Dict, language: str, endpoint_id: str) -> str:
        """Format payload for specific programming language."""
        if language == "python":
            return self._format_python(payload, endpoint_id)
        elif language == "nodejs":
            return self._format_nodejs(payload, endpoint_id)
        elif language == "java":
            return self._format_java(payload, endpoint_id)
        else:
            return json.dumps(payload, indent=2)
    
    def _format_python(self, payload: Dict, endpoint_id: str) -> str:
        """Format as Python dictionary with type hints."""
        import_str = "import requests\nimport json\n\n"
        
        # Pretty print with Python syntax
        def python_repr(obj, indent=0):
            if isinstance(obj, dict):
                if not obj:
                    return "{}"
                items = []
                for k, v in obj.items():
                    items.append(f"{' ' * (indent + 4)}'{k}': {python_repr(v, indent + 4)}")
                return "{\n" + ",\n".join(items) + f"\n{' ' * indent}}}"
            elif isinstance(obj, list):
                if not obj:
                    return "[]"
                items = [python_repr(item, indent + 4) for item in obj]
                return "[\n" + ",\n".join(f"{' ' * (indent + 4)}{item}" for item in items) + f"\n{' ' * indent}]"
            elif isinstance(obj, str):
                return repr(obj)
            else:
                return repr(obj)
        
        code = import_str
        code += f"# Payload for {endpoint_id}\n"
        code += f"payload = {python_repr(payload)}\n"
        
        return code
    
    def _format_nodejs(self, payload: Dict, endpoint_id: str) -> str:
        """Format as Node.js/JavaScript object."""
        code = "const axios = require('axios');\n\n"
        code += f"// Payload for {endpoint_id}\n"
        code += f"const payload = {json.dumps(payload, indent=2)};\n"
        return code
    
    def _format_java(self, payload: Dict, endpoint_id: str) -> str:
        """Format as Java Map/object."""
        code = "import java.util.*;\n\n"
        code += f"// Payload for {endpoint_id}\n"
        code += "Map<String, Object> payload = new HashMap<>();\n"
        
        def java_build(obj, var_name="payload", indent=0):
            lines = []
            prefix = " " * indent
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, dict):
                        lines.append(f"{prefix}Map<String, Object> {k} = new HashMap<>();")
                        lines.extend(java_build(v, k, indent))
                        lines.append(f'{prefix}{var_name}.put("{k}", {k});')
                    elif isinstance(v, list):
                        lines.append(f'{prefix}List<Object> {k}List = new ArrayList<>();')
                        for item in v:
                            if isinstance(item, dict):
                                lines.append(f"{prefix}Map<String, Object> item = new HashMap<>();")
                                lines.extend(java_build(item, "item", indent + 4))
                                lines.append(f"{prefix}{k}List.add(item);")
                            else:
                                lines.append(f"{prefix}{k}List.add({repr(item)});")
                        lines.append(f'{prefix}{var_name}.put("{k}", {k}List);')
                    elif isinstance(v, str):
                        lines.append(f'{prefix}{var_name}.put("{k}", "{v}");')
                    else:
                        lines.append(f'{prefix}{var_name}.put("{k}", {v});')
            return lines
        
        lines = java_build(payload)
        code += "\n".join(lines)
        return code


# Create singleton instance
payload_generator = PayloadGenerator()


async def generate_enhanced_payload(
    endpoint_id: str,
    include_optional: bool = False,
    include_conditional: bool = False,
    output_format: str = "json"
) -> Dict[str, Any]:
    """Enhanced payload generator with smart defaults and multi-language support."""
    return await payload_generator.generate_payload(
        endpoint_id=endpoint_id,
        include_optional=include_optional,
        include_conditional=include_conditional,
        output_format=output_format
    )
