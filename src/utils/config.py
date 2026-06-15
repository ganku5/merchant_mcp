"""Configuration management."""

import os
from pathlib import Path

ENV_FILE = Path(os.getenv("MCP_ENV_FILE", "load.env"))


class Config:
    """Application configuration."""
    
    # Database
    DATABASE_URL: str = "postgresql://postgres@localhost:5432/merchant_mcp"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "merchant_mcp"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    
    # LLM
    LLM_MODEL: str = "kimi-latest"
    LITELLM_LLM_API_BASE: str = ""
    LITELLM_LLM_API_KEY: str = ""
    
    # Embeddings
    EMBEDDING_MODEL: str = "openai/embed-marqo-ecommerce-b"
    LITELLM_EMBEDDING_API_BASE: str = ""
    LITELLM_EMBEDDING_API_KEY: str = ""
    
    # MCP Server
    MCP_PORT: int = 8000
    MCP_TRANSPORT: str = "sse"
    
    @classmethod
    def load_env_file(cls):
        """Load environment variables from env file."""
        if ENV_FILE.exists():
            with open(ENV_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[7:]  # Remove 'export '
                    if "=" in line and not line.startswith("#"):
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key == "DATABASE_URL":
                            cls.DATABASE_URL = value
                        elif key == "LLM_MODEL":
                            cls.LLM_MODEL = value
                        elif key == "EMBEDDING_MODEL":
                            cls.EMBEDDING_MODEL = value
                        elif key == "LITELLM_LLM_API_BASE":
                            cls.LITELLM_LLM_API_BASE = value
                        elif key == "LITELLM_LLM_API_KEY":
                            cls.LITELLM_LLM_API_KEY = value
                        elif key == "LITELLM_EMBEDDING_API_BASE":
                            cls.LITELLM_EMBEDDING_API_BASE = value
                        elif key == "LITELLM_EMBEDDING_API_KEY":
                            cls.LITELLM_EMBEDDING_API_KEY = value
                        elif key == "MCP_PORT":
                            cls.MCP_PORT = int(value)
                        elif key == "DB_HOST":
                            cls.DB_HOST = value
                        elif key == "DB_PORT":
                            cls.DB_PORT = int(value)
                        elif key == "DB_NAME":
                            cls.DB_NAME = value
                        elif key == "DB_USER":
                            cls.DB_USER = value
                        elif key == "DB_PASSWORD":
                            cls.DB_PASSWORD = value
        
        # Override with actual environment variables if set
        for attr in dir(cls):
            if not attr.startswith("_"):
                env_val = os.environ.get(attr)
                if env_val:
                    if isinstance(getattr(cls, attr), int):
                        setattr(cls, attr, int(env_val))
                    else:
                        setattr(cls, attr, env_val)


Config.load_env_file()
