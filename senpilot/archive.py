"""Validate retrieved documents and package verified files for email delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

from .intake import CATEGORIES


MAX_DOCUMENTS = 10
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_INPUT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class Document:
    """One row from the requested matter's selected category."""

    site_document_id: str | None
    title: str | None
    date: str | None
    extension: str | None
    original_filename: str | None
    source_url: str | None


@dataclass(frozen=True)
class Download:
    document: Document
    path: Path | None
    error_code: str | None = None


def select_documents(rows: list[Document]) -> list[Document]:
    """Select at most ten rows in the site's supplied order."""
    return rows[:MAX_DOCUMENTS]


def _safe_name(value: str | None, fallback: str) -> str:
    value = (value or "").replace("\\", "/").split("/")[-1]
    value = re.sub(r"[^A-Za-z0-9._ -]", "_", value).strip(" .")
    return (value[:100].rstrip(" .") or fallback)


def _read_verified(path: Path, expected_extension: str | None) -> tuple[bytes, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing_file")
    size = path.stat().st_size
    if size == 0:
        raise ValueError("empty_file")
    if size > MAX_FILE_BYTES:
        raise ValueError("file_too_large")
    data = path.read_bytes()
    if data[:512].lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError("html_response")
    extension = (expected_extension or "").lower().lstrip(".")
    if extension and path.suffix.lower().lstrip(".") != extension:
        raise ValueError("unexpected_extension")
    return data, hashlib.sha256(data).hexdigest()


def build_archive(
    matter_number: str,
    category: str,
    downloads: list[Download],
    destination: Path,
) -> dict:
    """Write a checked ZIP and return its manifest; fail if no file is valid."""
    if not re.fullmatch(r"M[0-9]{5}", matter_number):
        raise ValueError("invalid_matter")
    if category not in CATEGORIES:
        raise ValueError("invalid_category")
    if len(downloads) > MAX_DOCUMENTS:
        raise ValueError("too_many_documents")

    records = []
    valid = []
    total_bytes = 0
    for ordinal, download in enumerate(downloads, 1):
        doc = download.document
        record = {
            "site_document_id": doc.site_document_id,
            "title": doc.title,
            "date": doc.date,
            "extension": doc.extension,
            "source_url": doc.source_url,
            "original_filename": doc.original_filename,
            "archive_filename": None,
            "bytes": None,
            "sha256": None,
            "status": "failed",
            "error_code": download.error_code,
        }
        if not record["error_code"]:
            try:
                if download.path is None:
                    raise ValueError("missing_file")
                data, digest = _read_verified(download.path, doc.extension)
                if total_bytes + len(data) > MAX_ARCHIVE_INPUT_BYTES:
                    raise ValueError("archive_input_too_large")
                total_bytes += len(data)
                name = _safe_name(doc.original_filename or download.path.name, f"document_{ordinal}")
                archive_name = f"{ordinal:02d}_{_safe_name(doc.site_document_id, 'record')}_{name}"
                record.update(
                    archive_filename=archive_name,
                    bytes=len(data),
                    sha256=digest,
                    status="downloaded",
                )
                valid.append((archive_name, data))
            except (OSError, ValueError) as error:
                record["error_code"] = str(error) if isinstance(error, ValueError) else "file_read_error"
        records.append(record)

    if not valid:
        raise ValueError("no_verified_files")

    manifest = {
        "matter_number": matter_number,
        "category": category,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "selected_count": len(downloads),
        "downloaded_count": len(valid),
        "documents": records,
    }
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in valid:
            archive.writestr(name, data)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("zip_integrity_failed")
    return manifest
