"""Offline integration harness for a saved request and a retrieval fixture.

The fixture stands in for browser output; this module never contacts UARB or sends mail.
"""

from __future__ import annotations

import argparse
from email import policy
from email.parser import BytesParser
import json
from pathlib import Path

from .archive import Document, Download, build_archive, select_documents
from .intake import parse_request
from .reply import MatterSummary, compose_reply


def prepare_local_reply(
    incoming_path: Path,
    fixture_path: Path,
    output_dir: Path,
    agent_address: str,
    max_attachment_bytes: int = 20 * 1024 * 1024,
) -> tuple[Path, Path | None]:
    """Produce an unsent .eml and optional ZIP from explicitly supplied local data."""
    incoming_path = Path(incoming_path)
    fixture_path = Path(fixture_path)
    output_dir = Path(output_dir)
    incoming = BytesParser(policy=policy.default).parsebytes(incoming_path.read_bytes())
    sender = incoming.get("From")
    if not sender:
        raise ValueError("missing_sender")
    plain = incoming.get_body(preferencelist=("plain",))
    if plain is None:
        raise ValueError("missing_plain_text_body")
    request = parse_request(str(incoming.get("Subject", "")), plain.get_content())

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("matter_number") != request.matter_number:
        raise ValueError("fixture_matter_mismatch")
    if fixture.get("requested_type") != request.requested_type:
        raise ValueError("fixture_category_mismatch")
    summary = MatterSummary(
        matter_number=fixture["matter_number"],
        title=fixture.get("title"),
        matter_type=fixture.get("matter_type"),
        category=fixture.get("category"),
        initial_filing_date=fixture.get("initial_filing_date"),
        final_filing_date=fixture.get("final_filing_date"),
        counts=fixture["counts"],
    )
    entries = fixture.get("documents", [])
    documents = [
        Document(
            entry.get("site_document_id"), entry.get("title"), entry.get("date"),
            entry.get("extension"), entry.get("original_filename"), entry.get("source_url"),
        )
        for entry in entries
    ]
    selected = select_documents(documents)
    downloads = []
    for entry, document in zip(entries[:len(selected)], selected):
        path = entry.get("path")
        resolved_path = None
        if path:
            resolved_path = (fixture_path.parent / path).resolve()
            if not resolved_path.is_relative_to(fixture_path.parent.resolve()):
                raise ValueError("fixture_path_outside_directory")
        downloads.append(Download(
            document,
            resolved_path,
            entry.get("error_code"),
        ))

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = None
    manifest = None
    if downloads:
        candidate = output_dir / f"{request.matter_number}_{request.requested_type.replace(' ', '_')}.zip"
        try:
            manifest = build_archive(request.matter_number, request.requested_type, downloads, candidate)
            archive_path = candidate
        except ValueError as error:
            if str(error) != "no_verified_files":
                raise
    failures = (
        [
            f"{entry['site_document_id'] or entry['title'] or 'unnamed record'}: {entry['error_code']}"
            for entry in manifest["documents"] if entry["status"] == "failed"
        ] if manifest else [
            f"{download.document.site_document_id or download.document.title or 'unnamed record'}: "
            f"{download.error_code or 'file_validation_failed'}"
            for download in downloads
        ]
    )
    reply = compose_reply(
        sender=agent_address,
        recipient=str(sender),
        original_message_id=str(incoming.get("Message-ID", "")),
        summary=summary,
        requested_type=request.requested_type,
        selected_count=len(selected),
        downloaded_count=manifest["downloaded_count"] if manifest else 0,
        failures=failures,
        archive_path=archive_path,
        max_attachment_bytes=max_attachment_bytes,
    )
    reply_path = output_dir / "reply.eml"
    reply_path.write_bytes(reply.as_bytes())
    return reply_path, archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an unsent email reply from local fixture files")
    parser.add_argument("incoming", type=Path, help="Saved request as a plain-text .eml")
    parser.add_argument("fixture", type=Path, help="JSON snapshot with local document paths")
    parser.add_argument("output", type=Path, help="Directory for reply.eml and ZIP")
    parser.add_argument("--agent-address", required=True)
    parser.add_argument("--max-attachment-bytes", type=int, default=20 * 1024 * 1024)
    args = parser.parse_args()
    reply, archive = prepare_local_reply(
        args.incoming, args.fixture, args.output, args.agent_address, args.max_attachment_bytes,
    )
    print(f"Unsent reply: {reply}")
    print(f"ZIP: {archive if archive else 'none'}")


if __name__ == "__main__":
    main()
