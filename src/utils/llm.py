"""LLM client using LiteLLM."""

import os
import json
import logging
from datetime import datetime
from typing import AsyncIterator, Optional
import litellm

from .config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log directory for LLM interactions
LOG_DIR = os.path.join(os.path.dirname(__file__), "../../logs")
os.makedirs(LOG_DIR, exist_ok=True)

LLM_LOG_FILE = os.path.join(LOG_DIR, "llm_requests.log")
EMBEDDING_LOG_FILE = os.path.join(LOG_DIR, "embedding_requests.log")


def _log_llm_request(log_data: dict):
    """Log LLM request/response to file."""
    try:
        with open(LLM_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log LLM request: {e}")


def _log_embedding_request(log_data: dict):
    """Log embedding request/response to file."""
    try:
        with open(EMBEDDING_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log embedding request: {e}")


class LLMClient:
    """LiteLLM client for chat and embeddings."""
    
    def __init__(self):
        # Set LiteLLM environment variables
        if Config.LITELLM_LLM_API_BASE:
            os.environ["LITELLM_API_BASE"] = Config.LITELLM_LLM_API_BASE
        if Config.LITELLM_LLM_API_KEY:
            os.environ["LITELLM_API_KEY"] = Config.LITELLM_LLM_API_KEY
    
    async def chat(self, messages: list[dict], temperature: float = 0.3,
                   max_tokens: Optional[int] = None) -> str:
        """Send chat completion request."""
        # Use openai/ prefix for LiteLLM proxy compatibility
        model = Config.LLM_MODEL
        if '/' not in model and Config.LITELLM_LLM_API_BASE:
            model = f"openai/{model}"
        
        request_id = datetime.now().isoformat()
        
        # Log request
        _log_llm_request({
            "timestamp": request_id,
            "type": "request",
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages
        })
        
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_base=Config.LITELLM_LLM_API_BASE if Config.LITELLM_LLM_API_BASE else None,
                api_key=Config.LITELLM_LLM_API_KEY if Config.LITELLM_LLM_API_KEY else None
            )
            content = response.choices[0].message.content
            
            # Log response
            _log_llm_request({
                "timestamp": datetime.now().isoformat(),
                "type": "response",
                "request_id": request_id,
                "model": model,
                "content": content,
                "finish_reason": response.choices[0].finish_reason,
                "usage": response.usage.dict() if response.usage else None
            })
            
            return content
            
        except Exception as e:
            # Log error
            _log_llm_request({
                "timestamp": datetime.now().isoformat(),
                "type": "error",
                "request_id": request_id,
                "model": model,
                "error": str(e)
            })
            raise
    
    async def chat_stream(self, messages: list[dict], temperature: float = 0.3
                         ) -> AsyncIterator[str]:
        """Stream chat completion."""
        response = await litellm.acompletion(
            model=Config.LLM_MODEL,
            messages=messages,
            temperature=temperature,
            stream=True,
            api_base=Config.LITELLM_LLM_API_BASE if Config.LITELLM_LLM_API_BASE else None,
            api_key=Config.LITELLM_LLM_API_KEY if Config.LITELLM_LLM_API_KEY else None
        )
        
        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts."""
        # Use openai/ prefix for LiteLLM proxy compatibility
        model = Config.EMBEDDING_MODEL
        if '/' not in model and Config.LITELLM_EMBEDDING_API_BASE:
            model = f"openai/{model}"
        
        request_id = datetime.now().isoformat()
        
        # Log request (truncate text for readability)
        _log_embedding_request({
            "timestamp": request_id,
            "type": "request",
            "model": model,
            "num_texts": len(texts),
            "texts_preview": [t[:200] + "..." if len(t) > 200 else t for t in texts]
        })
        
        try:
            response = await litellm.aembedding(
                model=model,
                input=texts,
                api_base=Config.LITELLM_EMBEDDING_API_BASE if Config.LITELLM_EMBEDDING_API_BASE else None,
                api_key=Config.LITELLM_EMBEDDING_API_KEY if Config.LITELLM_EMBEDDING_API_KEY else None
            )
            
            embeddings = [item["embedding"] for item in response.data]
            
            # Log response
            _log_embedding_request({
                "timestamp": datetime.now().isoformat(),
                "type": "response",
                "request_id": request_id,
                "model": model,
                "num_embeddings": len(embeddings),
                "embedding_dims": len(embeddings[0]) if embeddings else 0,
                "usage": response.usage.dict() if response.usage else None
            })
            
            return embeddings
            
        except Exception as e:
            # Log error
            _log_embedding_request({
                "timestamp": datetime.now().isoformat(),
                "type": "error",
                "request_id": request_id,
                "model": model,
                "error": str(e)
            })
            raise
    
    async def extract_json(self, prompt: str, schema: dict) -> dict:
        """Extract structured JSON using LLM."""
        messages = [
            {
                "role": "system",
                "content": "You are a precise data extraction assistant. Extract structured data according to the provided schema. Return only valid JSON."
            },
            {
                "role": "user",
                "content": f"Extract data according to this schema:\n{schema}\n\nText to extract from:\n{prompt}"
            }
        ]
        
        response = await self.chat(messages, temperature=0.1)
        
        # Clean up response to extract JSON
        import json
        try:
            # Try to find JSON in markdown code blocks
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            else:
                json_str = response
            
            return json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}\nResponse: {response}")


# Global LLM client
llm_client = LLMClient()
