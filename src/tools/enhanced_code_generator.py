"""
Enhanced Code Example Generator

Generates production-ready SDK code in multiple languages
with authentication, error handling, and best practices.
"""

import json
from typing import Dict, Any, List
from ..utils.database import database
from .code_templates.python_sdk import generate_python_sdk
from .code_templates.nodejs_sdk import generate_nodejs_sdk
from .code_templates.java_sdk import generate_java_sdk, generate_java_webhook_handler, get_maven_dependencies
from .code_templates.go_sdk import generate_go_sdk, generate_go_webhook_handler, get_go_mod
from .code_templates.php_sdk import generate_php_sdk, generate_php_webhook_handler, get_composer_json


class CodeGenerator:
    """Multi-language code example generator."""
    
    SUPPORTED_LANGUAGES = {
        "python": {
            "name": "Python",
            "extension": ".py",
            "generator": generate_python_sdk,
            "requirements": ["requests>=2.25.0"],
            "install": "pip install requests"
        },
        "nodejs": {
            "name": "Node.js",
            "extension": ".js",
            "generator": generate_nodejs_sdk,
            "requirements": ["axios"],
            "install": "npm install axios"
        },
        "java": {
            "name": "Java",
            "extension": ".java",
            "generator": generate_java_sdk,
            "requirements": ["okhttp", "jackson-databind"],
            "install": get_maven_dependencies()
        },
        "go": {
            "name": "Go",
            "extension": ".go",
            "generator": generate_go_sdk,
            "requirements": [],
            "install": get_go_mod()
        },
        "php": {
            "name": "PHP",
            "extension": ".php",
            "generator": generate_php_sdk,
            "requirements": ["ext-curl", "ext-json"],
            "install": get_composer_json()
        }
    }
    
    async def generate_code_example(
        self,
        endpoint_id: str,
        language: str,
        include_comments: bool = True,
        include_error_handling: bool = True,
        include_tests: bool = False
    ) -> Dict[str, Any]:
        """
        Generate code example for an endpoint.
        
        Args:
            endpoint_id: API endpoint identifier
            language: Target programming language
            include_comments: Include inline documentation
            include_error_handling: Include error handling code
            include_tests: Include unit test template
        
        Returns:
            Generated code with metadata
        """
        if database._pool is None:
            await database.connect()
        
        conn = database.pool
        
        # Validate language
        lang_config = self.SUPPORTED_LANGUAGES.get(language.lower())
        if not lang_config:
            available = ", ".join(self.SUPPORTED_LANGUAGES.keys())
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Unsupported language: {language}\n\nAvailable languages: {available}"
                }],
                "isError": True
            }
        
        # Check if generator is implemented
        if not lang_config["generator"]:
            return {
                "content": [{
                    "type": "text",
                    "text": f"⚠️ Code generator for {language} is not yet implemented.\n\nSupported languages:\n- python\n- nodejs"
                }],
                "isError": True
            }
        
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
            
            # Build endpoint data
            endpoint_data = {
                "endpoint_id": endpoint_id,
                "method": spec['method'],
                "path": spec['path'],
                "description": spec['description'],
                "request_fields": [dict(f) for f in fields],
                "include_comments": include_comments,
                "include_error_handling": include_error_handling
            }
            
            # Generate code
            code = lang_config["generator"](endpoint_id, endpoint_data)
            
            # Build response
            sections = [
                f"# {lang_config['name']} SDK: {endpoint_id}",
                f"\n**Endpoint:** {spec['method']} {spec['path']}",
                f"\n## Installation",
                f"```bash\n{lang_config['install']}\n```",
                f"\n## Dependencies",
                "```\n" + "\n".join(lang_config['requirements']) + "\n```"
            ]
            
            if include_tests:
                test_code = self._generate_test_template(endpoint_id, language, fields)
                sections.extend([
                    f"\n## SDK Code ({lang_config['extension']})",
                    f"```{language}\n{code}\n```",
                    f"\n## Unit Test Template",
                    f"```{language}\n{test_code}\n```"
                ])
            else:
                sections.extend([
                    f"\n## Code ({lang_config['extension']})",
                    f"```{language}\n{code}\n```"
                ])
            
            # Add usage notes
            sections.extend([
                f"\n## Usage Notes",
                f"1. Replace `your_api_key_here` with your actual API key",
                f"2. Replace `your_api_secret_here` with your API secret (if required)",
                f"3. Set `{endpoint_id.upper().replace('.', '_')}_BASE_URL` environment variable",
                f"4. Handle errors appropriately for production use"
            ])
            
            return {
                "content": [{
                    "type": "text",
                    "text": "\n".join(sections)
                }],
                "isError": False
            }
    
    def _generate_test_template(
        self, 
        endpoint_id: str, 
        language: str, 
        fields: List[Dict]
    ) -> str:
        """Generate unit test template."""
        if language == "python":
            return self._generate_python_test(endpoint_id, fields)
        elif language == "nodejs":
            return self._generate_nodejs_test(endpoint_id, fields)
        return "# Tests not yet implemented for this language"
    
    def _generate_python_test(self, endpoint_id: str, fields: List[Dict]) -> str:
        """Generate Python unit test template."""
        method_name = endpoint_id.replace('.', '_')
        
        test = f'''"""Unit tests for {endpoint_id}"""

import unittest
from unittest.mock import Mock, patch
from your_sdk import {method_name}


class Test{method_name.title()}(unittest.TestCase):
    """Test cases for {endpoint_id}"""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = YourClient(
            api_key="test_key",
            api_secret="test_secret",
            base_url="https://sandbox-api.example.com"
        )
    
    @patch('your_sdk.requests.Session.request')
    def test_{method_name}_success(self, mock_request):
        """Test successful API call."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {{
            "status": "SUCCESS",
            "data": {{"id": "test_123"}}
        }}
        mock_request.return_value = mock_response
        
        # Act
        result = self.client.{method_name}(
            # Add required parameters here
        )
        
        # Assert
        self.assertEqual(result['status'], 'SUCCESS')
    
    @patch('your_sdk.requests.Session.request')
    def test_{method_name}_error(self, mock_request):
        """Test API error handling."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {{
            "error": "INVALID_REQUEST",
            "message": "Invalid parameter"
        }}
        mock_request.return_value = mock_response
        
        # Act & Assert
        with self.assertRaises(APIError) as context:
            self.client.{method_name}(
                # Add invalid parameters here
            )
        
        self.assertEqual(context.exception.error_code, 'INVALID_REQUEST')


if __name__ == '__main__':
    unittest.main()
'''
        return test
    
    def _generate_nodejs_test(self, endpoint_id: str, fields: List[Dict]) -> str:
        """Generate Node.js test template."""
        method_name = endpoint_id.replace('.', '_')
        
        test = f'''/**
 * Unit tests for {endpoint_id}
 */

const {{ {method_name} }} = require('./your-sdk');
const axios = require('axios');

// Mock axios
jest.mock('axios');

describe('{method_name}', () => {{
    let client;
    
    beforeEach(() => {{
        client = new YourClient({{
            apiKey: 'test_key',
            apiSecret: 'test_secret',
            baseUrl: 'https://sandbox-api.example.com'
        }});
    }});
    
    afterEach(() => {{
        jest.clearAllMocks();
    }});
    
    test('should succeed with valid request', async () => {{
        // Arrange
        const mockResponse = {{
            data: {{
                status: 'SUCCESS',
                data: {{ id: 'test_123' }}
            }}
        }};
        axios.create.mockReturnValue({{
            request: jest.fn().mockResolvedValue(mockResponse)
        }});
        
        // Act
        const result = await client.{method_name}({{
            // Add required parameters
        }});
        
        // Assert
        expect(result.data.status).toBe('SUCCESS');
    }});
    
    test('should handle API errors', async () => {{
        // Arrange
        const mockError = new Error('Request failed');
        mockError.response = {{
            status: 400,
            data: {{
                error: 'INVALID_REQUEST',
                message: 'Invalid parameter'
            }}
        }};
        axios.create.mockReturnValue({{
            request: jest.fn().mockRejectedValue(mockError)
        }});
        
        // Act & Assert
        await expect(
            client.{method_name}({{ /* invalid params */ }})
        ).rejects.toThrow('INVALID_REQUEST');
    }});
}});
'''
        return test


# Singleton instance
code_generator = CodeGenerator()


async def get_enhanced_code_example(
    endpoint_id: str,
    language: str,
    include_comments: bool = True,
    include_error_handling: bool = True,
    include_tests: bool = False
) -> Dict[str, Any]:
    """Generate enhanced code example with full SDK."""
    return await code_generator.generate_code_example(
        endpoint_id=endpoint_id,
        language=language,
        include_comments=include_comments,
        include_error_handling=include_error_handling,
        include_tests=include_tests
    )
