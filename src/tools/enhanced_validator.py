"""
Enhanced Payload Validator

Deep validation with business rules, cross-field validation,
and actionable suggestions.
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from ..utils.database import database


class ValidationRule:
    """Base class for validation rules."""
    
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity
    
    def validate(self, value: Any, payload: Dict) -> Tuple[bool, Optional[str]]:
        """Validate value. Returns (is_valid, error_message)."""
        raise NotImplementedError


class PatternRule(ValidationRule):
    """Regex pattern validation."""
    
    def __init__(self, field: str, pattern: str, message: str):
        super().__init__(field, message)
        self.pattern = re.compile(pattern)
    
    def validate(self, value: Any, payload: Dict) -> Tuple[bool, Optional[str]]:
        if not value:
            return True, None
        if not self.pattern.match(str(value)):
            return False, self.message
        return True, None


class RangeRule(ValidationRule):
    """Numeric range validation."""
    
    def __init__(self, field: str, min_val: Optional[float] = None, 
                 max_val: Optional[float] = None, message: str = ""):
        super().__init__(field, message or f"Must be between {min_val} and {max_val}")
        self.min_val = min_val
        self.max_val = max_val
    
    def validate(self, value: Any, payload: Dict) -> Tuple[bool, Optional[str]]:
        try:
            num = float(value)
            if self.min_val is not None and num < self.min_val:
                return False, f"Must be >= {self.min_val}"
            if self.max_val is not None and num > self.max_val:
                return False, f"Must be <= {self.max_val}"
            return True, None
        except (ValueError, TypeError):
            return False, "Must be a number"


class DependencyRule(ValidationRule):
    """Cross-field dependency validation."""
    
    def __init__(self, field: str, depends_on: str, condition: str, message: str):
        super().__init__(field, message)
        self.depends_on = depends_on
        self.condition = condition
    
    def validate(self, value: Any, payload: Dict) -> Tuple[bool, Optional[str]]:
        dep_value = self._get_nested_value(payload, self.depends_on)
        
        # Evaluate condition
        if self.condition == "exists":
            if dep_value and not value:
                return False, f"Required when {self.depends_on} is present"
        elif self.condition == "equals":
            # Simplified - actual implementation would parse condition
            pass
        
        return True, None
    
    def _get_nested_value(self, payload: Dict, path: str) -> Any:
        """Get value from nested path (e.g., 'payer.vpa')."""
        parts = path.split('.')
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


class BusinessRuleEngine:
    """Engine for evaluating business rules."""
    
    # Predefined business rules for IBMB
    IBMB_RULES = {
        "ibmb.merchant.transaction.init": [
            {
                "field": "amount",
                "rule": "range",
                "min": 1.0,
                "max": 1000000.0,
                "message": "Amount must be between 1.00 and 1,000,000.00"
            },
            {
                "field": "merchantRequestId",
                "rule": "pattern",
                "pattern": r"^[0-9]{4}[0-9]{4}[A-Z0-9]{11}$",
                "message": "Reference ID must be 20 characters: YYYYJJJ4 (Julian date) + 11 alphanumeric"
            },
            {
                "field": "payer.vpa",
                "rule": "dependency",
                "depends_on": "paymentMode",
                "condition": "equals:UPI",
                "message": "payer.vpa is required when paymentMode is UPI"
            },
            {
                "field": "initiationMode",
                "rule": "enum",
                "values": ["QR", "INTENT", "REDIRECTION"],
                "message": "Must be one of: QR, INTENT, REDIRECTION"
            }
        ],
        "ibmb.axis.sdk.fetch": [
            {
                "field": "url",
                "rule": "pattern",
                "pattern": r"^(nb://|https://).*",
                "message": "URL must start with nb:// or https://"
            },
            {
                "field": "loginToken",
                "rule": "required",
                "message": "loginToken is required for authentication"
            }
        ]
    }
    
    @classmethod
    def get_rules(cls, endpoint_id: str) -> List[Dict]:
        """Get business rules for endpoint."""
        return cls.IBMB_RULES.get(endpoint_id, [])
    
    @classmethod
    def evaluate(cls, endpoint_id: str, payload: Dict) -> List[Dict]:
        """Evaluate all business rules for payload."""
        violations = []
        rules = cls.get_rules(endpoint_id)
        
        for rule_def in rules:
            field = rule_def.get("field")
            value = cls._get_nested_value(payload, field)
            rule_type = rule_def.get("rule")
            
            if rule_type == "required":
                if not value:
                    violations.append({
                        "field": field,
                        "severity": "error",
                        "message": rule_def.get("message", f"{field} is required"),
                        "suggestion": f"Provide a value for {field}"
                    })
            
            elif rule_type == "pattern":
                if value:
                    pattern = rule_def.get("pattern", "")
                    if not re.match(pattern, str(value)):
                        violations.append({
                            "field": field,
                            "severity": "error",
                            "message": rule_def.get("message", f"Invalid format for {field}"),
                            "suggestion": f"Ensure {field} matches pattern: {pattern}"
                        })
            
            elif rule_type == "range":
                if value:
                    try:
                        num = float(value)
                        min_val = rule_def.get("min")
                        max_val = rule_def.get("max")
                        
                        if min_val is not None and num < min_val:
                            violations.append({
                                "field": field,
                                "severity": "error",
                                "message": f"{field} must be >= {min_val}",
                                "suggestion": f"Increase {field} to at least {min_val}"
                            })
                        
                        if max_val is not None and num > max_val:
                            violations.append({
                                "field": field,
                                "severity": "error",
                                "message": f"{field} must be <= {max_val}",
                                "suggestion": f"Decrease {field} to at most {max_val}"
                            })
                    except (ValueError, TypeError):
                        violations.append({
                            "field": field,
                            "severity": "error",
                            "message": f"{field} must be a number",
                            "suggestion": f"Convert {field} to a numeric value"
                        })
            
            elif rule_type == "enum":
                if value:
                    allowed = rule_def.get("values", [])
                    if str(value) not in allowed:
                        violations.append({
                            "field": field,
                            "severity": "error",
                            "message": rule_def.get("message", f"Invalid value for {field}"),
                            "suggestion": f"Use one of: {', '.join(allowed)}"
                        })
            
            elif rule_type == "dependency":
                depends_on = rule_def.get("depends_on")
                dep_value = cls._get_nested_value(payload, depends_on)
                
                if dep_value and not value:
                    violations.append({
                        "field": field,
                        "severity": "error",
                        "message": rule_def.get("message", f"{field} required when {depends_on} is present"),
                        "suggestion": f"Add {field} or remove {depends_on}"
                    })
        
        return violations
    
    @classmethod
    def _get_nested_value(cls, payload: Dict, path: str) -> Any:
        """Get value from nested path."""
        parts = path.split('.')
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


class EnhancedValidator:
    """Enhanced payload validator with deep validation."""
    
    async def validate_payload(
        self,
        endpoint_id: str,
        payload: Dict[str, Any],
        strict: bool = False
    ) -> Dict[str, Any]:
        """
        Validate payload against schema and business rules.
        
        Args:
            endpoint_id: API endpoint identifier
            payload: Payload to validate
            strict: If True, warnings become errors
        
        Returns:
            Validation report with errors, warnings, and suggestions
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
            
            # Perform validation
            errors = []
            warnings = []
            suggestions = []
            
            # 1. Schema validation (required fields, types)
            for field in fields:
                field_path = field['field_name'] if not field.get('parent_path') else f"{field['parent_path']}.{field['field_name']}"
                field_value = self._get_nested_value(payload, field_path)
                requirement = field.get('requirement', 'optional')
                
                # Check required fields
                if requirement == 'mandatory' and field_value is None:
                    errors.append({
                        "field": field_path,
                        "severity": "error",
                        "code": "REQUIRED_FIELD_MISSING",
                        "message": f"{field['field_name']} is required",
                        "suggestion": f"Add '{field['field_name']}' to your payload"
                    })
                
                # Check conditional fields
                elif requirement == 'conditional' and field_value is None:
                    condition_desc = field.get('condition_description', '')
                    warnings.append({
                        "field": field_path,
                        "severity": "warning",
                        "code": "CONDITIONAL_FIELD_EMPTY",
                        "message": f"{field['field_name']} may be required: {condition_desc}",
                        "suggestion": f"Include if condition is met: {condition_desc}"
                    })
                
                # Type validation
                if field_value is not None:
                    field_type = field.get('field_type', 'string')
                    type_errors = self._validate_type(field_path, field_value, field_type, field)
                    errors.extend(type_errors)
            
            # 2. Business rules validation
            business_violations = BusinessRuleEngine.evaluate(endpoint_id, payload)
            for v in business_violations:
                if v["severity"] == "error":
                    errors.append(v)
                else:
                    warnings.append(v)
            
            # 3. Cross-field validation
            cross_field_issues = self._validate_cross_fields(endpoint_id, payload)
            errors.extend(cross_field_issues)
            
            # 4. Generate suggestions
            suggestions = self._generate_suggestions(errors, warnings, fields)
            
            # Build response
            is_valid = len(errors) == 0
            
            if strict:
                is_valid = is_valid and len(warnings) == 0
                errors.extend([{**w, "severity": "error"} for w in warnings])
                warnings = []
            
            sections = [
                f"# Payload Validation: {endpoint_id}",
                f"\n**Status:** {'✅ Valid' if is_valid else '❌ Invalid'}",
                f"**Errors:** {len(errors)}",
                f"**Warnings:** {len(warnings)}"
            ]
            
            if errors:
                sections.append("\n## Errors (Must Fix)")
                for i, e in enumerate(errors, 1):
                    sections.append(f"\n{i}. **{e['field']}** - {e['code']}")
                    sections.append(f"   - {e['message']}")
                    sections.append(f"   - 💡 Suggestion: {e.get('suggestion', 'Review field requirements')}")
            
            if warnings:
                sections.append("\n## Warnings (Should Fix)")
                for i, w in enumerate(warnings, 1):
                    sections.append(f"\n{i}. **{w['field']}** - {w.get('code', 'WARNING')}")
                    sections.append(f"   - {w['message']}")
                    sections.append(f"   - 💡 Suggestion: {w.get('suggestion', 'Consider addressing')}")
            
            if suggestions:
                sections.append("\n## Improvement Suggestions")
                for s in suggestions:
                    sections.append(f"\n- {s}")
            
            # Add example valid payload
            sections.append("\n## Example Valid Payload")
            from .enhanced_building_tools import payload_generator
            example = await payload_generator.generate_payload(endpoint_id)
            example_text = example.get("content", [{}])[0].get("text", "")
            sections.append(example_text.split("## Payload")[1] if "## Payload" in example_text else "")
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }],
                "isError": not is_valid
            }
    
    def _validate_type(self, field_path: str, value: Any, field_type: str, field_def: Dict) -> List[Dict]:
        """Validate value against expected type."""
        errors = []
        
        if field_type == "string":
            if not isinstance(value, str):
                errors.append({
                    "field": field_path,
                    "severity": "error",
                    "code": "TYPE_MISMATCH",
                    "message": f"Expected string, got {type(value).__name__}",
                    "suggestion": f"Convert {field_path} to a string"
                })
            else:
                # Check constraints
                constraints = field_def.get('constraints', {})
                if isinstance(constraints, str):
                    try:
                        constraints = json.loads(constraints)
                    except:
                        constraints = {}
                
                if constraints.get('minLength') and len(value) < constraints['minLength']:
                    errors.append({
                        "field": field_path,
                        "severity": "error",
                        "code": "MIN_LENGTH_VIOLATION",
                        "message": f"Minimum length is {constraints['minLength']}",
                        "suggestion": f"Make {field_path} at least {constraints['minLength']} characters"
                    })
                
                if constraints.get('maxLength') and len(value) > constraints['maxLength']:
                    errors.append({
                        "field": field_path,
                        "severity": "error",
                        "code": "MAX_LENGTH_VIOLATION",
                        "message": f"Maximum length is {constraints['maxLength']}",
                        "suggestion": f"Shorten {field_path} to at most {constraints['maxLength']} characters"
                    })
        
        elif field_type in ["number", "integer"]:
            try:
                float(value)
            except (ValueError, TypeError):
                errors.append({
                    "field": field_path,
                    "severity": "error",
                    "code": "TYPE_MISMATCH",
                    "message": f"Expected number, got {type(value).__name__}",
                    "suggestion": f"Convert {field_path} to a numeric value"
                })
        
        elif field_type == "boolean":
            if not isinstance(value, bool) and str(value).lower() not in ['true', 'false']:
                errors.append({
                    "field": field_path,
                    "severity": "error",
                    "code": "TYPE_MISMATCH",
                    "message": f"Expected boolean, got {type(value).__name__}",
                    "suggestion": f"Convert {field_path} to true/false"
                })
        
        elif field_type == "array":
            if not isinstance(value, list):
                errors.append({
                    "field": field_path,
                    "severity": "error",
                    "code": "TYPE_MISMATCH",
                    "message": f"Expected array, got {type(value).__name__}",
                    "suggestion": f"Convert {field_path} to an array []"
                })
        
        elif field_type == "object":
            if not isinstance(value, dict):
                errors.append({
                    "field": field_path,
                    "severity": "error",
                    "code": "TYPE_MISMATCH",
                    "message": f"Expected object, got {type(value).__name__}",
                    "suggestion": f"Convert {field_path} to an object {{}}"
                })
        
        return errors
    
    def _validate_cross_fields(self, endpoint_id: str, payload: Dict) -> List[Dict]:
        """Validate relationships between fields."""
        issues = []
        
        # Check for common IBMB patterns
        if "amount" in payload and "currency" in payload:
            amount = payload.get("amount")
            currency = payload.get("currency")
            
            if amount and currency:
                try:
                    amt = float(amount)
                    if amt > 0 and currency not in ["INR", "USD", "EUR"]:
                        issues.append({
                            "field": "currency",
                            "severity": "warning",
                            "code": "UNUSUAL_CURRENCY",
                            "message": f"Currency '{currency}' may not be supported",
                            "suggestion": "Verify currency is supported by your merchant account"
                        })
                except ValueError:
                    pass
        
        return issues
    
    def _generate_suggestions(self, errors: List[Dict], warnings: List[Dict], fields: List[Dict]) -> List[str]:
        """Generate improvement suggestions."""
        suggestions = []
        
        error_fields = {e['field'] for e in errors}
        warning_fields = {w['field'] for w in warnings}
        
        # Suggest adding optional fields that improve API call
        for field in fields:
            if field.get('requirement') == 'optional':
                field_name = field['field_name']
                if field_name not in error_fields and field_name not in warning_fields:
                    if 'idempotency' in field_name.lower() or 'reference' in field_name.lower():
                        suggestions.append(
                            f"Consider adding '{field_name}' for idempotency and easier tracking"
                        )
        
        return suggestions
    
    def _get_nested_value(self, payload: Dict, path: str) -> Any:
        """Get value from nested path."""
        parts = path.split('.')
        current = payload
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


# Singleton instance
validator = EnhancedValidator()


async def validate_enhanced_payload(
    endpoint_id: str,
    payload: Dict[str, Any],
    strict: bool = False
) -> Dict[str, Any]:
    """Enhanced payload validation with business rules."""
    return await validator.validate_payload(endpoint_id, payload, strict)
