"""Compose factual MIME replies from verified retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
import re

from .intake import CATEGORIES


@dataclass(frozen=True)
class MatterSummary:
    matter_number: str
    title: str | None
    matter_type: str | None
    category: str | None
    initial_filing_date: str | None
    final_filing_date: str | None
    counts: dict[str, int | None]


class AttachmentTooLarge(ValueError):
    pass


def compose_reply(
    sender: str,
    recipient: str,
    original_message_id: str,
    summary: MatterSummary,
    requested_type: str,
    selected_count: int,
    downloaded_count: int,
    failures: list[str],
    archive_path: Path | None,
    max_attachment_bytes: int,
) -> EmailMessage:
    """Build an unsent message; counts and successes must come from verified data."""
    if requested_type not in CATEGORIES or set(summary.counts) != set(CATEGORIES):
        raise ValueError("invalid_categories")
    if not re.fullmatch(r"M[0-9]{5}", summary.matter_number):
        raise ValueError("invalid_matter")
    if any(value is not None and value < 0 for value in summary.counts.values()):
        raise ValueError("invalid_count")
    if not 0 <= downloaded_count <= selected_count <= 10:
        raise ValueError("invalid_download_count")
    if downloaded_count and archive_path is None:
        raise ValueError("missing_archive")
    if not downloaded_count and archive_path is not None:
        raise ValueError("unexpected_archive")
    if "\n" in sender + recipient + original_message_id or "\r" in sender + recipient + original_message_id:
        raise ValueError("invalid_header")

    archive_data = None
    if archive_path is not None:
        archive_path = Path(archive_path)
        if archive_path.stat().st_size > max_attachment_bytes:
            raise AttachmentTooLarge("attachment_too_large")
        archive_data = archive_path.read_bytes()
        if len(archive_data) > max_attachment_bytes:
            raise AttachmentTooLarge("attachment_too_large")

    lines = [
        f"{summary.matter_number}: {summary.title or 'title not listed'}.",
        f"Type: {summary.matter_type or 'not listed'}; category: {summary.category or 'not listed'}.",
        f"Initial filing: {summary.initial_filing_date or 'not listed'}; final filing: {summary.final_filing_date or 'not listed'}.",
        "",
        "Database document counts:",
    ]
    for category in CATEGORIES:
        value = summary.counts[category]
        lines.append(f"- {category}: {value if value is not None else 'unavailable'}")
    if all(value is not None for value in summary.counts.values()):
        lines.append(f"Total across these five categories: {sum(summary.counts.values())}")
    else:
        lines.append("Total across these five categories: unavailable")
    requested_total = summary.counts[requested_type]
    lines.extend([
        "",
        f"Requested category: {requested_type} ({requested_total if requested_total is not None else 'count unavailable'} records).",
        f"Downloaded {downloaded_count} of {selected_count} selected files.",
    ])
    if archive_data is not None:
        lines.append("The downloaded files are attached in a ZIP.")
    elif selected_count == 0:
        lines.append("No files were selected; no ZIP is attached.")
    else:
        lines.append("No files were verified; no ZIP is attached.")
    if failures:
        lines.extend(["", "Failed downloads:", *[f"- {failure}" for failure in failures]])

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"Documents for {summary.matter_number} — {requested_type}"
    if original_message_id:
        message["In-Reply-To"] = original_message_id
        message["References"] = original_message_id
    message.set_content("\n".join(lines))
    if archive_data is not None:
        message.add_attachment(
            archive_data,
            maintype="application",
            subtype="zip",
            filename=f"{summary.matter_number}_{requested_type.replace(' ', '_')}.zip",
        )
    return message
