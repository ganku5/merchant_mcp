#!/usr/bin/env python3
"""Setup database for merchant MCP."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.db import db
from src.utils.config import Config


async def setup():
    """Initialize database schema."""
    print(f"Connecting to database at {Config.DB_HOST}:{Config.DB_PORT}...")

    try:
        await db.connect()
        print("✓ Connected to database")

        await db.init_schema()
        print("✓ Database schema initialized")

        await db.close()
        print("✓ Setup complete")

    except Exception as e:
        print(f"✗ Setup failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(setup())
