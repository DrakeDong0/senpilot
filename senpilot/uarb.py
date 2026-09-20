"""Bridge the Playwright retrieval script to the Python email worker."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from .archive import Document, Download
from .intake import CATEGORIES, Request
from .reply import MatterSummary
from .worker import RetrievalError, RetrievalResult


def retrieve_uarb(request: Request, workspace: Path) -> RetrievalResult:
    """Run one isolated browser job and validate its result before composing mail."""
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    output = workspace / "result.json"
    script = Path(__file__).resolve().parent.parent / "scripts" / "retrieve-uarb.mjs"
    command = [
        "node", str(script), request.matter_number, request.requested_type,
        str(workspace / "downloads"), str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        detail = (getattr(error, "stderr", "") or "").strip()
        raise RetrievalError(detail or "UARB browser job failed") from error
    try:
        result = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RetrievalError("UARB result is missing or invalid") from error

    if result.get("matter_number") != request.matter_number:
        raise RetrievalError("retrieved_matter_mismatch")
    if result.get("requested_type") != request.requested_type:
        raise RetrievalError("retrieved_category_mismatch")
    counts = result.get("counts")
    if not isinstance(counts, dict) or set(counts) != set(CATEGORIES):
        raise RetrievalError("invalid_category_counts")
    if any(value is not None and (type(value) is not int or value < 0) for value in counts.values()):
        raise RetrievalError("invalid_category_counts")
    rows = result.get("documents")
    if not isinstance(rows, list) or len(rows) > 10:
        raise RetrievalError("invalid_document_rows")
    requested_count = counts[request.requested_type]
    if requested_count is not None and len(rows) > requested_count:
        raise RetrievalError("document_count_mismatch")

    downloads = []
    download_root = (workspace / "downloads").resolve()
    for row in rows:
        if not isinstance(row, dict):
            raise RetrievalError("invalid_document_row")
        file_path = None
        if row.get("path"):
            if not isinstance(row["path"], str):
                raise RetrievalError("invalid_download_path")
            file_path = Path(row["path"]).resolve()
            if not file_path.is_relative_to(download_root) or not file_path.is_file():
                raise RetrievalError("download_path_outside_workspace")
        document = Document(
            row.get("site_document_id"), row.get("title"), row.get("date"),
            row.get("extension"), row.get("original_filename"), row.get("source_url"),
        )
        downloads.append(Download(document, file_path, row.get("error_code")))

    summary = MatterSummary(
        matter_number=result["matter_number"],
        title=result.get("title"),
        matter_type=result.get("matter_type"),
        category=result.get("category"),
        initial_filing_date=result.get("initial_filing_date"),
        final_filing_date=result.get("final_filing_date"),
        counts=counts,
    )
    return RetrievalResult(summary, downloads)
