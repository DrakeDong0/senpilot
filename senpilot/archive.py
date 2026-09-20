"""Package up to ten successfully downloaded UARB files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile

from .intake import CATEGORIES


MAX_DOCUMENTS = 10


@dataclass(frozen=True)
class Document:
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


@dataclass(frozen=True)
class ArchiveResult:
    downloaded_count: int
    failures: list[str]


def select_documents(rows: list[Document]) -> list[Document]:
    return rows[:MAX_DOCUMENTS]


def _safe_name(value: str | None, fallback: str) -> str:
    value = (value or "").replace("\\", "/").split("/")[-1]
    value = re.sub(r"[^A-Za-z0-9._ -]", "_", value).strip(" .")
    return value[:100].rstrip(" .") or fallback


def build_archive(
    matter_number: str,
    category: str,
    downloads: list[Download],
    destination: Path,
) -> ArchiveResult:
    """Create a ZIP from valid files; report any skipped downloads."""
    if not re.fullmatch(r"M[0-9]{5}", matter_number):
        raise ValueError("invalid_matter")
    if category not in CATEGORIES:
        raise ValueError("invalid_category")
    if len(downloads) > MAX_DOCUMENTS:
        raise ValueError("too_many_documents")

    valid = []
    failures = []
    for ordinal, download in enumerate(downloads, 1):
        label = download.document.site_document_id or download.document.title or f"record {ordinal}"
        try:
            if download.error_code:
                raise ValueError(download.error_code)
            if download.path is None or not download.path.is_file():
                raise ValueError("missing_file")
            data = download.path.read_bytes()
            if not data:
                raise ValueError("empty_file")
            if data[:512].lstrip().lower().startswith((b"<!doctype html", b"<html")):
                raise ValueError("html_response")
            extension = (download.document.extension or "").lower().lstrip(".")
            if extension and download.path.suffix.lower().lstrip(".") != extension:
                raise ValueError("unexpected_extension")
            name = _safe_name(download.document.original_filename or download.path.name, f"document_{ordinal}")
            valid.append((f"{ordinal:02d}_{name}", data))
        except (OSError, ValueError) as error:
            failures.append(f"{label}: {error if isinstance(error, ValueError) else 'file_read_error'}")

    if not valid:
        raise ValueError("no_verified_files")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in valid:
            archive.writestr(name, data)
    return ArchiveResult(downloaded_count=len(valid), failures=failures)
