"""Configuration management."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

ENV_FILE = Path("/home/ganesh/context_mcp/load.env")


class Config:
    """Application configuration."""
    
    # Database
    DATABASE_URL: str = "postgresql://postgres@localhost:5432/mcp_product_context"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "mcp_product_context"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    
    # LLM
    LLM_MODEL: str = "kimi-latest"
    LITELLM_LLM_API_BASE: str = ""
    LITELLM_LLM_API_KEY: str = ""
    AGENT_RESPONSE_BACKEND: str = "opencode"
    OPENCODE_BIN_DIR: str = "/home/ganesh/.opencode/bin"
    OPENCODE_CLI_COMMAND: str = "opencode run --dir /tmp/merchant_mcp_opencode --model litellm/kimi-latest --no-replay {prompt}"
    OPENCODE_CLI_TIMEOUT_SECONDS: int = 600
    OPENCODE_WORKDIR: str = "/tmp/merchant_mcp_opencode"
    
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
                        elif key == "AGENT_RESPONSE_BACKEND":
                            cls.AGENT_RESPONSE_BACKEND = value
                        elif key == "OPENCODE_BIN_DIR":
                            cls.OPENCODE_BIN_DIR = value
                        elif key == "OPENCODE_CLI_COMMAND":
                            cls.OPENCODE_CLI_COMMAND = value
                        elif key == "OPENCODE_CLI_TIMEOUT_SECONDS":
                            cls.OPENCODE_CLI_TIMEOUT_SECONDS = int(value)
                        elif key == "OPENCODE_WORKDIR":
                            cls.OPENCODE_WORKDIR = value
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
        
        cls._apply_database_url()
        cls._apply_database_env_overrides()

        # Override with actual environment variables if set
        for attr in dir(cls):
            if not attr.startswith("_"):
                env_val = os.environ.get(attr)
                if env_val:
                    if isinstance(getattr(cls, attr), int):
                        setattr(cls, attr, int(env_val))
                    else:
                        setattr(cls, attr, env_val)

        cls._apply_database_url()

    @classmethod
    def _apply_database_url(cls):
        """Derive asyncpg connection fields from DATABASE_URL when present."""
        if not cls.DATABASE_URL:
            return

        parsed = urlparse(cls.DATABASE_URL)
        if parsed.scheme not in {"postgres", "postgresql"}:
            return

        if parsed.hostname:
            cls.DB_HOST = parsed.hostname
        if parsed.port:
            cls.DB_PORT = parsed.port
        if parsed.path and parsed.path != "/":
            cls.DB_NAME = parsed.path.lstrip("/")
        if parsed.username:
            cls.DB_USER = unquote(parsed.username)
        if parsed.password:
            cls.DB_PASSWORD = unquote(parsed.password)

    @classmethod
    def _apply_database_env_overrides(cls):
        """Let explicit DB_* environment variables override DATABASE_URL parts."""
        for attr in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            env_val = os.environ.get(attr)
            if env_val is None:
                continue

            if attr == "DB_PORT":
                cls.DB_PORT = int(env_val)
            else:
                setattr(cls, attr, env_val)


Config.load_env_file()
