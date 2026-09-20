"""Connect incoming mail, document retrieval, ZIP creation, and replies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from .archive import Download, build_archive, select_documents
from .intake import Request
from .mail import IncomingMail, Mailbox, MailSender
from .reply import AttachmentTooLarge, MatterSummary, compose_clarification, compose_reply


@dataclass(frozen=True)
class RetrievalResult:
    summary: MatterSummary
    downloads: list[Download]


Retriever = Callable[[Request, Path], RetrievalResult]


def process_incoming(
    incoming: IncomingMail,
    mailbox: Mailbox,
    sender: MailSender,
    retrieve: Retriever,
    agent_address: str,
    max_attachment_bytes: int = 20 * 1024 * 1024,
) -> None:
    """Send one reply, then mark its inbound email read only after send succeeds."""
    if incoming.request is None:
        reply = compose_clarification(
            agent_address, incoming.sender, incoming.message_id,
            incoming.clarification or "Please specify one matter and document type.",
        )
        sender.send(reply)
        mailbox.mark_seen(incoming.uid)
        return

    request = incoming.request
    with TemporaryDirectory(prefix="senpilot-") as directory:
        workspace = Path(directory)
        result = retrieve(request, workspace)
        if result.summary.matter_number != request.matter_number:
            raise ValueError("retrieved_matter_mismatch")
        selected = select_documents(result.downloads)
        archive_path = None
        downloaded_count = 0
        failures = []
        if selected:
            archive_path = workspace / f"{request.matter_number}_{request.requested_type.replace(' ', '_')}.zip"
            try:
                archive_result = build_archive(
                    request.matter_number, request.requested_type, selected, archive_path,
                )
                downloaded_count = archive_result.downloaded_count
                failures = archive_result.failures
            except ValueError as error:
                if str(error) != "no_verified_files":
                    raise
                archive_path = None
                failures = ["All selected downloads failed or were empty."]
        try:
            reply = compose_reply(
                agent_address, incoming.sender, incoming.message_id, result.summary,
                request.requested_type, len(selected), downloaded_count, failures,
                archive_path, max_attachment_bytes,
            )
        except AttachmentTooLarge:
            reply = compose_clarification(
                agent_address, incoming.sender, incoming.message_id,
                "The requested ZIP exceeds the email attachment size limit, so I could not attach the files.",
            )
        sender.send(reply)
        mailbox.mark_seen(incoming.uid)


def run_once(
    mailbox: Mailbox,
    sender: MailSender,
    retrieve: Retriever,
    agent_address: str,
    max_attachment_bytes: int = 20 * 1024 * 1024,
) -> int:
    """Process the currently unseen inbox messages once; return the processed count."""
    messages = mailbox.fetch_unseen()
    for incoming in messages:
        process_incoming(incoming, mailbox, sender, retrieve, agent_address, max_attachment_bytes)
    return len(messages)
