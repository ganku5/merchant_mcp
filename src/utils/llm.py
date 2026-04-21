"""LLM client using LiteLLM."""

import os
from typing import AsyncIterator, Optional
import litellm

from .config import Config


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
        
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_base=Config.LITELLM_LLM_API_BASE if Config.LITELLM_LLM_API_BASE else None,
            api_key=Config.LITELLM_LLM_API_KEY if Config.LITELLM_LLM_API_KEY else None
        )
        return response.choices[0].message.content
    
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
        
        response = await litellm.aembedding(
            model=model,
            input=texts,
            api_base=Config.LITELLM_EMBEDDING_API_BASE if Config.LITELLM_EMBEDDING_API_BASE else None,
            api_key=Config.LITELLM_EMBEDDING_API_KEY if Config.LITELLM_EMBEDDING_API_KEY else None
        )
        
        return [item["embedding"] for item in response.data]
    
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
