# registerIntent generated docs

This folder contains the generated merchant facing documentation sample for registerIntent

Generated using the API context generator with newton repo as the source of truth

Command used

PYTHONPATH=. python -m context_generator.orchestrator \
  --repo-path "$NEWTON_REPO" \
  --api registerIntent \
  --config context_generator/configs/merchant_mcp.json \
  --out context_generator/generated/registerIntent_final_generate2

Files

- register-intent.md generated merchant facing API doc
- register-intent.review.json reviewer result
- docs_s2s.zip zip artifact for MCP ingestion
