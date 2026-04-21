#!/usr/bin/env python3
"""Quick test of MCP tools without full ingestion."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, '/home/ganesh/merchant_mcp')

import asyncpg

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'merchant_mcp',
    'user': 'postgres',
}


async def test():
    """Quick test setup."""
    print("Testing Merchant MCP Setup...")
    print("=" * 50)
    
    # Test database connection
    print("\n1. Database Connection")
    try:
        pool = await asyncpg.create_pool(**DB_CONFIG)
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 'Connected!' as status")
            print(f"   ✓ {result}")
        await pool.close()
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return 1
    
    # Check files to ingest
    print("\n2. IBMB Files Found")
    ibmb_folder = Path("/home/ganesh/Downloads/ibmb")
    if ibmb_folder.exists():
        pdf_files = list(ibmb_folder.glob("*.pdf"))
        for pdf in pdf_files:
            size_mb = pdf.stat().st_size / (1024 * 1024)
            print(f"   • {pdf.name} ({size_mb:.1f} MB)")
    
    # Test LiteLLM configuration
    print("\n3. LiteLLM Configuration")
    from src.utils.config import Config
    print(f"   • LLM Model: {Config.LLM_MODEL}")
    print(f"   • Embedding Model: {Config.EMBEDDING_MODEL}")
    print(f"   • API Base: {Config.LITELLM_LLM_API_BASE[:30]}...")
    
    print("\n" + "=" * 50)
    print("Setup verified! Ready for ingestion.")
    print("\nTo run full ingestion:")
    print("  python3 scripts/simple_ingest.py")
    print("\nTo start MCP server:")
    print("  python3 -m src.server.server")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test())
    sys.exit(exit_code)
