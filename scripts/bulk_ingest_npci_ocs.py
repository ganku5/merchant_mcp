import csv
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

CSV_PATH = Path("bulk_docs/npci_ocs/oc_index.csv")
DOWNLOAD_DIR = Path("bulk_docs/npci_ocs/downloaded")
OCR_DIR = Path("bulk_docs/npci_ocs/ocr")
STATUS_PATH = Path("bulk_docs/npci_ocs/ingestion_status.csv")

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
OCR_DIR.mkdir(parents=True, exist_ok=True)


def slugify(s: str, max_len: int = 90) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:max_len] or "doc"


def make_doc_id(year: str, title: str, url: str) -> str:
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"npci_oc_{year}_{slugify(title, 70)}_{digest}"


def make_filename(year: str, title: str, url: str) -> str:
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    ext = Path(urlparse(url).path).suffix or ".pdf"
    return f"{year}_{slugify(title)}_{digest}{ext}"


def load_success_doc_ids():
    if not STATUS_PATH.exists():
        return set()

    done = set()
    with STATUS_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "success":
                done.add(row.get("doc_id"))
    return done


def append_status(row):
    exists = STATUS_PATH.exists()
    fieldnames = [
        "doc_id", "year", "title", "url", "file_path",
        "ingested_file", "status", "chunks", "embedded", "message"
    ]

    with STATUS_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def run(cmd, timeout=None):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env={**os.environ, "PYTHONPATH": "."},
    )


def download(url: str, out_path: Path):
    if out_path.exists() and out_path.stat().st_size > 0:
        return

    with requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=180) as r:
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 512):
                if chunk:
                    f.write(chunk)


def extract_text_len(pdf_path: Path) -> int:
    result = run(["pdftotext", str(pdf_path), "-"], timeout=120)
    if result.returncode != 0:
        return 0
    return len(result.stdout.strip())


def ocr_pdf(pdf_path: Path, ocr_path: Path):
    if ocr_path.exists() and ocr_path.stat().st_size > 0:
        return

    result = run(
        ["ocrmypdf", "--force-ocr", str(pdf_path), str(ocr_path)],
        timeout=60 * 10,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stdout[-1500:])


def ingest_pdf(file_path: Path, doc_id: str):
    cmd = [
        sys.executable,
        "ingest.py",
        str(file_path),
        "--doc-id",
        doc_id,
        "--type",
        "pdf",
    ]

    env = {**os.environ, "PYTHONPATH": "."}

    proc = subprocess.Popen(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        bufsize=1,
    )

    output_lines = []

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            output_lines.append(line)

        returncode = proc.wait(timeout=60 * 30)

    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\nTIMEOUT: ingest.py exceeded 30 minutes\n")
        returncode = 124

    class Result:
        pass

    result = Result()
    result.returncode = returncode
    result.stdout = "".join(output_lines)
    return result


def parse_chunks(output: str):
    chunks = ""
    embedded = ""

    m = re.search(r"Created\s+(\d+)\s+chunks", output)
    if m:
        chunks = m.group(1)

    m = re.search(r"Stored\s+(\d+)\s+chunks\s+\((\d+)\s+with embeddings\)", output)
    if m:
        chunks = m.group(1)
        embedded = m.group(2)

    return chunks, embedded


def main():
    success_doc_ids = load_success_doc_ids()

    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"total rows: {len(rows)}")
    print(f"already successful: {len(success_doc_ids)}")

    for idx, row in enumerate(rows, start=1):
        year = row["Year"].strip()
        title = row["Title"].strip()
        url = row["URL"].strip()

        if not url or url.lower() == "not available" or not url.startswith("http"):
            print(f"[{idx}/{len(rows)}] skip unavailable URL: {title}")
            continue

        doc_id = make_doc_id(year, title, url)
        raw_path = DOWNLOAD_DIR / make_filename(year, title, url)
        ocr_path = OCR_DIR / f"{raw_path.stem}_ocr.pdf"

        if doc_id in success_doc_ids:
            print(f"[{idx}/{len(rows)}] skip success: {doc_id}")
            continue

        print(f"\n[{idx}/{len(rows)}] {doc_id}")
        print(title)
        print(url)

        try:
            download(url, raw_path)
            print(f"downloaded: {raw_path} ({raw_path.stat().st_size} bytes)")

            text_len = extract_text_len(raw_path)
            print(f"normal text length: {text_len}")

            ingest_path = raw_path
            if raw_path.suffix.lower() == ".pdf" and text_len == 0:
                print("no text layer found, running OCR...")
                ocr_pdf(raw_path, ocr_path)
                ocr_len = extract_text_len(ocr_path)
                print(f"OCR text length: {ocr_len}")
                ingest_path = ocr_path

                if ocr_len == 0:
                    raise RuntimeError("OCR completed but extracted text is still 0")

            result = ingest_pdf(ingest_path, doc_id)
            chunks, embedded = parse_chunks(result.stdout)

            if result.returncode == 0 and "✅ Ingestion complete" in result.stdout and chunks != "0":
                status = "success"
                msg = "ingested"
            else:
                status = "failed"
                msg = result.stdout[-1500:]

            append_status({
                "doc_id": doc_id,
                "year": year,
                "title": title,
                "url": url,
                "file_path": str(raw_path),
                "ingested_file": str(ingest_path),
                "status": status,
                "chunks": chunks,
                "embedded": embedded,
                "message": msg.replace("\n", " ")[:1500],
            })

            print(f"status: {status}, chunks={chunks}, embedded={embedded}")

        except Exception as e:
            append_status({
                "doc_id": doc_id,
                "year": year,
                "title": title,
                "url": url,
                "file_path": str(raw_path),
                "ingested_file": "",
                "status": "failed",
                "chunks": "",
                "embedded": "",
                "message": str(e)[:1500],
            })
            print(f"failed: {e}")

        time.sleep(1)


if __name__ == "__main__":
    main()
