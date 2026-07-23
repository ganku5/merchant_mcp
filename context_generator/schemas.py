from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass
class RepoSnippet:
    path: str
    matched_terms: List[str]
    snippets: List[str]


@dataclass
class RepoContext:
    api: str
    repo_path: str
    keywords: List[str]
    files: List[RepoSnippet]


@dataclass
class GeneratedDoc:
    api: str
    doc_id: str
    markdown_path: str
    evidence_path: str
    review_path: Optional[str] = None


def to_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj)
