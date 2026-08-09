"""Configuration management."""

import os
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

load_dotenv()


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

    # Embeddings
    EMBEDDING_MODEL: str = "openai/embed-marqo-ecommerce-b"
    LITELLM_EMBEDDING_API_BASE: str = ""
    LITELLM_EMBEDDING_API_KEY: str = ""

    # MCP Server
    MCP_PORT: int = 8000
    MCP_TRANSPORT: str = "sse"

    # Web scraping / doc conversion
    WEB_SCRAPER_URLS: str = ""
    WEB_SCRAPER_OUTPUT_DIR: str = "scraped_docs"
    CONVERSION_LLM_MODEL: str = ""
    WEB_SCRAPER_MAX_CRAWL_DEPTH: int = 3
    WEB_SCRAPER_MAX_URLS: int = 200

    @classmethod
    def load(cls):
        """Apply environment overrides on top of defaults."""
        cls._apply_database_url()
        cls._apply_database_env_overrides()

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


Config.load()
