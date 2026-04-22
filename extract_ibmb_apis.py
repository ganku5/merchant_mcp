#!/usr/bin/env python3
"""
Extract IBMB API specifications from documents and create JSON files.
"""

import pdfplumber
import json
import os
import re
from pathlib import Path

IBMB_DOCS_DIR = "/home/ganesh/Downloads/ibmb"
OUTPUT_DIR = "/home/ganesh/merchant_mcp/api_specs/ibmb"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF."""
    print(f"Reading: {pdf_path}")
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n\n--- Page {i+1} ---\n\n"
                text += page_text
    return text


def parse_api_specifications(text):
    """Parse API specifications from extracted text."""
    apis = []
    
    # Look for API sections (typically start with "API Name:" or similar)
    # Split by API boundaries
    api_sections = re.split(r'\n(?=(?:API Name|API Endpoint|Resource|Service)\s*:)', text, flags=re.IGNORECASE)
    
    for section in api_sections[1:]:  # Skip first empty section
        api = parse_api_section(section)
        if api:
            apis.append(api)
    
    return apis


def parse_api_section(section_text):
    """Parse a single API section."""
    lines = section_text.strip().split('\n')
    if not lines:
        return None
    
    api = {
        "endpoint_id": "",
        "method": "POST",
        "path": "",
        "api_version": "v1",
        "description": "",
        "summary": "",
        "headers": {"request": [], "response": []},
        "request_fields": [],
        "response_fields": [],
        "conditions": [],
        "samples": []
    }
    
    # Extract API name/endpoint
    first_line = lines[0]
    if ':' in first_line:
        parts = first_line.split(':', 1)
        api_name = parts[1].strip() if len(parts) > 1 else parts[0].strip()
        api["endpoint_id"] = api_name.lower().replace(' ', '.').replace('_', '.')
        api["summary"] = api_name
    
    # Parse remaining content
    current_section = None
    field_stack = []  # For nested fields
    
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        
        # Detect sections
        lower = line.lower()
        if any(keyword in lower for keyword in ['endpoint:', 'path:', 'url:']):
            path_match = re.search(r'(https?://[^\s]+|/[^\s]+)', line)
            if path_match:
                api["path"] = path_match.group(1)
            continue
        
        if 'method:' in lower:
            method_match = re.search(r'(GET|POST|PUT|DELETE|PATCH)', line.upper())
            if method_match:
                api["method"] = method_match.group(1)
            continue
        
        if any(keyword in lower for keyword in ['description:', 'overview:', 'purpose:']):
            api["description"] = line.split(':', 1)[1].strip() if ':' in line else line
            continue
        
        # Request headers section
        if any(k in lower for k in ['request header', 'input header', 'header (request)']):
            current_section = 'request_headers'
            continue
        
        # Response headers section
        if any(k in lower for k in ['response header', 'output header', 'header (response)']):
            current_section = 'response_headers'
            continue
        
        # Request body/fields section
        if any(k in lower for k in ['request body', 'input parameter', 'request parameter', 'request field']):
            current_section = 'request_fields'
            field_stack = []
            continue
        
        # Response body/fields section
        if any(k in lower for k in ['response body', 'output parameter', 'response parameter', 'response field', 'success response']):
            current_section = 'response_fields'
            field_stack = []
            continue
        
        # Error responses section
        if any(k in lower for k in ['error response', 'error code', 'failure response']):
            current_section = 'error_responses'
            continue
        
        # Sample/example section
        if any(k in lower for k in ['example', 'sample request', 'sample response']):
            current_section = 'samples'
            continue
        
        # Parse content based on current section
        if current_section == 'request_headers' and line.startswith('-') or ':' in line:
            header = parse_header_line(line)
            if header:
                api["headers"]["request"].append(header)
        
        elif current_section == 'response_headers' and line.startswith('-') or ':' in line:
            header = parse_header_line(line)
            if header:
                api["headers"]["response"].append(header)
        
        elif current_section in ('request_fields', 'response_fields'):
            field = parse_field_line(line, field_stack)
            if field:
                target = api["request_fields"] if current_section == 'request_fields' else api["response_fields"]
                target.append(field)
    
    # Generate endpoint_id from path if not set
    if not api["endpoint_id"] and api["path"]:
        path_parts = api["path"].strip('/').split('/')
        api["endpoint_id"] = 'ibmb.' + '.'.join(path_parts[-2:] if len(path_parts) >= 2 else path_parts)
    
    return api if api["endpoint_id"] or api["path"] else None


def parse_header_line(line):
    """Parse a header line."""
    line = line.lstrip('- ').strip()
    if not line:
        return None
    
    header = {
        "name": "",
        "required": True,
        "description": ""
    }
    
    # Pattern: Header-Name: description or Header-Name (required): description
    match = re.match(r'^([^:(]+)(?:\s*\(([^)]+)\))?\s*:?\s*(.*)', line)
    if match:
        header["name"] = match.group(1).strip()
        modifiers = match.group(2) or ""
        header["description"] = match.group(3).strip()
        
        if modifiers:
            header["required"] = "optional" not in modifiers.lower()
    else:
        header["name"] = line
    
    return header


def parse_field_line(line, field_stack):
    """Parse a field line, handling nesting."""
    line = line.lstrip('- ').strip()
    if not line:
        return None
    
    # Determine indentation/nesting level
    leading_spaces = len(line) - len(line.lstrip())
    depth = leading_spaces // 2
    
    # Adjust stack to current depth
    while len(field_stack) > depth:
        field_stack.pop()
    
    field = {
        "field_name": "",
        "field_type": "string",
        "requirement": "optional",
        "description": "",
        "parent_path": ".".join(field_stack) if field_stack else ""
    }
    
    # Try to extract field name and type
    # Patterns:
    # - fieldName (string): description
    # - fieldName*: description (required)
    # - fieldName†: description (conditional)
    # - fieldName [type]: description
    
    match = re.match(r'^([^[(:{]+)([*†])?(?:\s*\[([^]]+)\])?(?:\s*\(([^)]+)\))?\s*:?\s*(.*)', line)
    if match:
        field["field_name"] = match.group(1).strip()
        requirement_marker = match.group(2)
        explicit_type = match.group(3)
        modifiers = match.group(4) or ""
        description = match.group(5).strip()
        
        if explicit_type:
            field["field_type"] = explicit_type.lower()
        elif modifiers:
            field["field_type"] = modifiers.lower()
        
        if requirement_marker == '*':
            field["requirement"] = "mandatory"
        elif requirement_marker == '†':
            field["requirement"] = "conditional"
        elif "required" in modifiers.lower():
            field["requirement"] = "mandatory"
        
        field["description"] = description
    else:
        field["field_name"] = line
    
    # Add to stack for nested processing
    full_name = f"{field['parent_path']}.{field['field_name']}" if field['parent_path'] else field['field_name']
    field_stack.append(field['field_name'])
    
    return field


def enhance_ibmb_apis(apis, error_codes_file):
    """Enhance API specs with error codes and additional metadata."""
    # Load error codes
    error_codes = []
    with open(error_codes_file, 'r') as f:
        next(f)  # Skip header
        for line in f:
            line = line.strip()
            if ',' in line and not line.startswith('//'):
                parts = line.split(',', 1)
                code = parts[0].strip()
                desc = parts[1].strip() if len(parts) > 1 else ""
                error_codes.append({
                    "error_code": code,
                    "http_status": 400,
                    "description": desc
                })
    
    # Enhance each API
    for api in apis:
        # Add standard IBMB headers
        if not api["headers"]["request"]:
            api["headers"]["request"] = [
                {
                    "name": "Content-Type",
                    "required": True,
                    "description": "Must be application/json",
                    "default_value": "application/json"
                },
                {
                    "name": "X-Request-ID",
                    "required": True,
                    "description": "Unique request identifier",
                    "pattern": "^[a-zA-Z0-9-]{20,50}$"
                }
            ]
        
        # Add common response headers
        if not api["headers"]["response"]:
            api["headers"]["response"] = [
                {
                    "name": "Content-Type",
                    "required": True,
                    "description": "Will be application/json"
                }
            ]
        
        # Add error responses
        if not api.get("error_responses"):
            api["error_responses"] = error_codes[:20]  # First 20 error codes
        
        # Set version
        api["api_version"] = "v1"
    
    return apis


def create_common_structure():
    """Create common IBMB structures."""
    
    # Common Head structure
    head_fields = [
        {"field_name": "ver", "field_type": "string", "requirement": "mandatory", "description": "Message version (e.g., '1.0')"},
        {"field_name": "ts", "field_type": "string", "format": "iso8601", "requirement": "mandatory", "description": "Timestamp in ISO 8601 format with timezone"},
        {"field_name": "msgId", "field_type": "string", "requirement": "mandatory", "description": "Unique message ID (max 35 chars)"},
        {"field_name": "orgId", "field_type": "string", "requirement": "mandatory", "description": "Organization ID (alphanumeric, 5 chars)"},
        {"field_name": "prodType", "field_type": "string", "requirement": "mandatory", "description": "Product type - must be 'IBMB'"},
        {"field_name": "orgType", "field_type": "string", "requirement": "mandatory", "description": "Organization type - 'PA' or 'BANK'"}
    ]
    
    # Common Transaction structure
    txn_fields = [
        {"field_name": "txnId", "field_type": "string", "requirement": "mandatory", "description": "Transaction ID (20 chars alphanumeric)"},
        {"field_name": "refId", "field_type": "string", "requirement": "mandatory", "description": "Reference ID (20 chars alphanumeric)"},
        {"field_name": "initiationMode", "field_type": "string", "requirement": "mandatory", "description": "Initiation mode - SDK or REDIRECTION"},
        {"field_name": "txnTs", "field_type": "string", "format": "iso8601", "requirement": "mandatory", "description": "Transaction timestamp"},
        {"field_name": "txnAmt", "field_type": "string", "requirement": "mandatory", "description": "Transaction amount (numeric, max 3 decimal places)"},
        {"field_name": "cur", "field_type": "string", "requirement": "mandatory", "description": "Currency code (e.g., 'INR')"},
        {"field_name": "note", "field_type": "string", "requirement": "optional", "description": "Transaction note (max 255 chars)"},
        {"field_name": "expiry", "field_type": "integer", "requirement": "optional", "description": "Expiry time in seconds"}
    ]
    
    # Common Payer/Payee structure
    payer_fields = [
        {"field_name": "vpa", "field_type": "string", "requirement": "conditional", "condition_description": "Required for UPI payments", "description": "Virtual Payment Address"},
        {"field_name": "name", "field_type": "string", "requirement": "optional", "description": "Payer/Payee name"},
        {"field_name": "mobile", "field_type": "string", "requirement": "optional", "description": "Mobile number"}
    ]
    
    return {
        "head": head_fields,
        "transaction": txn_fields,
        "payer": payer_fields
    }


def save_api_specs(apis):
    """Save API specifications to JSON files."""
    for i, api in enumerate(apis):
        # Clean endpoint_id for filename
        filename_base = api["endpoint_id"].replace('.', '_')
        if not filename_base:
            filename_base = f"api_{i+1}"
        
        filename = f"{filename_base}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(api, f, indent=2)
        
        print(f"Saved: {filepath}")


def main():
    """Main extraction process."""
    # Find IBMB API spec PDF
    api_spec_pdf = os.path.join(IBMB_DOCS_DIR, "[Axis] IBMB Bank Server API Specifications.pdf")
    error_codes_csv = os.path.join(IBMB_DOCS_DIR, "IBMB Error Codes with Description v 3 2.xlsx - IBMB to PA & Bank.csv")
    
    if not os.path.exists(api_spec_pdf):
        print(f"Error: API spec PDF not found: {api_spec_pdf}")
        return
    
    # Extract text from PDF
    print("=" * 60)
    print("EXTRACTING IBMB API SPECIFICATIONS")
    print("=" * 60)
    
    text = extract_text_from_pdf(api_spec_pdf)
    
    # Save raw text for inspection
    raw_text_file = os.path.join(OUTPUT_DIR, "_raw_extracted_text.txt")
    with open(raw_text_file, 'w') as f:
        f.write(text[:50000])  # First 50K chars for inspection
    print(f"Saved raw text to: {raw_text_file}")
    
    # Parse APIs
    print("\nParsing API specifications...")
    apis = parse_api_specifications(text)
    print(f"Found {len(apis)} potential APIs")
    
    # Enhance with error codes
    if os.path.exists(error_codes_csv):
        print("\nEnhancing with error codes...")
        apis = enhance_ibmb_apis(apis, error_codes_csv)
    
    # Save individual API specs
    print("\nSaving API specifications...")
    save_api_specs(apis)
    
    # Also save combined file
    combined_file = os.path.join(OUTPUT_DIR, "_all_ibmb_apis.json")
    with open(combined_file, 'w') as f:
        json.dump(apis, f, indent=2)
    print(f"\nSaved combined file: {combined_file}")
    
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Total APIs extracted: {len(apis)}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
