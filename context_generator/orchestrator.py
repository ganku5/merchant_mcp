import json
from pathlib import Path

from context_generator.repo_indexer import build_repo_context
from context_generator.workers.api_worker import run_api_worker
from context_generator.reviewer import review_doc
from context_generator.zip_builder import build_zip
from context_generator.sanitizer import sanitize_markdown
from context_generator.config_loader import load_config


def run_orchestrator(repo_path: str, api: str, out_dir: str, config_path: str = ""):
    config = load_config(config_path)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Building repo context for API: {api}")
    ctx = build_repo_context(repo_path=repo_path, api=api, config=config)

    ctx_path = out / f"{api}.repo_context.json"
    ctx_json = {
        "api": ctx.api,
        "repo_path": ctx.repo_path,
        "keywords": ctx.keywords,
        "files": [
            {
                "path": f.path,
                "matched_terms": f.matched_terms,
                "snippets": f.snippets,
            }
            for f in ctx.files
        ],
    }
    ctx_path.write_text(json.dumps(ctx_json, indent=2))

    print(f"[2/5] Found {len(ctx.files)} relevant files")

    print("[3/5] Running API worker")
    doc = run_api_worker(ctx, out_dir, config=config)

    print("[4/6] Sanitizing generated doc")
    sanitize_markdown(doc["markdown_path"])

    print("[5/6] Reviewing generated doc")
    review = review_doc(doc["markdown_path"], doc["evidence_path"], out_dir, config=config)
    doc["review_path"] = review["review_path"]
    doc["review_status"] = review["status"]

    print("[6/6] Building docs zip")
    zip_path = build_zip(out_dir, [doc])

    print("")
    print("Done.")
    print(f"Repo context: {ctx_path}")
    print(f"Markdown doc: {doc['markdown_path']}")
    print(f"Evidence: {doc['evidence_path']}")
    print(f"Review: {doc['review_path']}")
    print(f"Zip: {zip_path}")

    return {
        "context_path": str(ctx_path),
        "doc": doc,
        "zip_path": zip_path,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--api", required=True)
    parser.add_argument("--out", default="context_generator/generated")
    parser.add_argument("--config", default="", help="Repo-specific context generator config JSON")
    args = parser.parse_args()

    run_orchestrator(
        repo_path=args.repo_path,
        api=args.api,
        out_dir=args.out,
        config_path=args.config,
    )


if __name__ == "__main__":
    main()
