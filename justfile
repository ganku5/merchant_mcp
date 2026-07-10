# List all available commands
@default:
    just --list

# Run the MCP server (usage: just run [port])
@run port="8000":
    uv run python -m uvicorn src.server.mcp_server:app --host 0.0.0.0 --port {{port}} --reload

# Run tests
@test:
    uv run pytest

# Lock dependencies
@lock:
    uv lock

# Sync dependencies
@sync:
    uv sync

# Build with nix
@nix-build:
    nix build .#default

# Build Docker image with nix
@docker:
    nix build .#dockerImage --no-link --print-out-paths

# Enter dev shell
@shell:
    nix develop
