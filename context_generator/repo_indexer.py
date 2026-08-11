import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Set, Any

from context_generator.schemas import RepoSnippet, RepoContext, to_dict


DEFAULT_EXTENSIONS = {
    ".hs", ".lhs", ".yaml", ".yml", ".json", ".dhall", ".cabal", ".sql", ".md"
}


def api_keywords(api: str) -> List[str]:
    base = api.strip()
    variants = {
        base,
        base.lower(),
        base.upper(),
        base[:1].upper() + base[1:],
        re.sub(r"([a-z])([A-Z])", r"\1-\2", base).lower(),
        re.sub(r"([a-z])([A-Z])", r"\1_\2", base).lower(),
    }

    low = base.lower()

    if "register" in low and "intent" in low:
        variants.update([
            "registerIntent",
            "RegisterIntent",
            "register intent",
            "transactions/registerIntent",
            "merchantRequestId",
            "intent",
            "TPV",
        ])

    if "refund" in low:
        variants.update([
            "refund",
            "Refund",
            "onlineRefund",
            "merchantRequestId",
            "refundTransaction",
            "RefundTransaction",
        ])

    if "mandate" in low:
        variants.update([
            "mandate",
            "Mandate",
            "UMN",
            "umn",
        ])

    return sorted(x for x in variants if x)


def run_rg(repo_path: str, term: str) -> List[str]:
    try:
        result = subprocess.run(
            [
                "rg",
                "-n",
                "--hidden",
                "--glob", "!dist-newstyle",
                "--glob", "!.git",
                "--glob", "!node_modules",
                term,
                repo_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=25,
        )
        if result.returncode not in (0, 1):
            return []
        return result.stdout.splitlines()
    except Exception:
        return []


def read_context_lines(path: str, line_no: int, before: int = 12, after: int = 20) -> str:
    try:
        lines = Path(path).read_text(errors="ignore").splitlines()
        start = max(0, line_no - before - 1)
        end = min(len(lines), line_no + after)

        numbered = []
        for idx in range(start, end):
            numbered.append(f"{idx + 1}: {lines[idx]}")
        return "\n".join(numbered)
    except Exception as e:
        return f"<failed to read {path}: {e}>"


def _matches_any(path: str, patterns: List[str]) -> bool:
    path_obj = Path(path)
    return any(path_obj.match(pattern) for pattern in patterns)


def _is_excluded(path: str, patterns: List[str]) -> bool:
    return _matches_any(path, patterns)


def build_repo_context(
    repo_path: str,
    api: str,
    max_files: int = 20,
    max_snippets_per_file: int = 4,
    config: Dict[str, Any] | None = None,
) -> RepoContext:
    config = config or {}
    repo_path = str(Path(repo_path).expanduser().resolve())

    configured_keywords = config.get("contract_keywords", [])
    keywords = list(dict.fromkeys(api_keywords(api) + configured_keywords))

    include_globs = config.get("include_globs", [])
    exclude_globs = config.get("exclude_globs", [])
    priority_path_keywords = config.get("priority_path_keywords", [])
    deprioritize_path_keywords = config.get("deprioritize_path_keywords", [])
    contract_keywords = config.get("contract_keywords", [])

    matches_by_file: Dict[str, Dict[str, Set[int]]] = {}

    for term in keywords:
        for line in run_rg(repo_path, term):
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue

            path, line_no_str, _content = parts
            rel_path = os.path.relpath(path, repo_path)

            if include_globs and not _matches_any(rel_path, include_globs):
                continue

            if _is_excluded(rel_path, exclude_globs):
                continue

            ext = Path(path).suffix

            if ext and ext not in DEFAULT_EXTENSIONS:
                continue

            try:
                line_no = int(line_no_str)
            except ValueError:
                continue

            matches_by_file.setdefault(path, {}).setdefault(term, set()).add(line_no)

    scored = []

    for path, term_map in matches_by_file.items():
        score = sum(len(lines) for lines in term_map.values()) + (len(term_map) * 5)

        lower_path = path.lower()
        normalized_path = lower_path.replace("/", "").replace("_", "").replace("-", "")
        api_lower = api.lower()
        api_norm = api_lower.replace("-", "").replace("_", "")

        # Strong priority: API-specific files.
        if api_norm in normalized_path:
            score += 80

        # Strong priority: Server-to-server API surface.
        if "servertoserver" in normalized_path:
            score += 40

        # Important docs evidence files.
        if "typesapiservertoserver" in normalized_path:
            score += 50

        if "servicestransformerservertoserver" in normalized_path:
            score += 50

        if "typesdomainconstants" in normalized_path:
            score += 35

        if "productmerchanttransactionsv2" in normalized_path:
            score += 35

        # Repo-specific priority boosts.
        for keyword in priority_path_keywords:
            if keyword.lower() in lower_path:
                score += 1000

        for keyword in deprioritize_path_keywords:
            if keyword.lower() in lower_path:
                score -= 500

        matched_text = " ".join(term_map.keys()).lower()
        for keyword in contract_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in lower_path or keyword_lower in matched_text:
                score += 10

        # Generic boosts.
        for boost in [
            "route", "api", "type", "types", "validation", "service",
            "error", "config", "merchant", "transaction", "refund", "mandate"
        ]:
            if boost in lower_path:
                score += 3

        # Deprioritize huge shared utility files unless file itself is API-specific.
        if "utils/" in lower_path and api_norm not in normalized_path:
            score -= 30

        if "deregisterintent" in normalized_path and api_norm == "registerintent":
            score -= 100

        if "changelog" in lower_path:
            score -= 30

        scored.append((score, path, term_map))

    scored.sort(reverse=True, key=lambda x: x[0])

    files: List[RepoSnippet] = []

    for _score, path, term_map in scored[:max_files]:
        snippets = []
        used_lines = []

        for _term, lines in term_map.items():
            for line_no in sorted(lines):
                if len(snippets) >= max_snippets_per_file:
                    break

                if any(abs(line_no - old) < 10 for old in used_lines):
                    continue

                snippets.append(read_context_lines(path, line_no))
                used_lines.append(line_no)

            if len(snippets) >= max_snippets_per_file:
                break

        files.append(
            RepoSnippet(
                path=os.path.relpath(path, repo_path),
                matched_terms=sorted(term_map.keys()),
                snippets=snippets,
            )
        )

    return RepoContext(
        api=api,
        repo_path=repo_path,
        keywords=keywords,
        files=files,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--api", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    ctx = build_repo_context(args.repo_path, args.api)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(to_dict(ctx), indent=2))
        print(args.out)
    else:
        print(json.dumps(to_dict(ctx), indent=2))


if __name__ == "__main__":
    main()
