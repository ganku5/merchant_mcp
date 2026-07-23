import json
import zipfile
from pathlib import Path
from typing import List, Dict, Any


def build_zip(out_dir: str, docs: List[Dict[str, Any]]) -> str:
    out = Path(out_dir)
    zip_path = out / "docs_s2s.zip"

    manifest = {
        "docs_count": len(docs),
        "docs": docs,
    }

    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for doc in docs:
            md_path = Path(doc["markdown_path"])
            z.write(md_path, f"server-to-server-apis/{md_path.name}")

        z.write(manifest_path, "manifest.json")

    return str(zip_path)
