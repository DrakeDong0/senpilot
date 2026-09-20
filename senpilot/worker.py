"""Connect incoming mail, document retrieval, ZIP creation, and replies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from typing import Callable

from .archive import Download, build_archive, select_documents
from .intake import Request
from .mail import IncomingMail, Mailbox, MailSender
from .reply import (AttachmentTooLarge, MatterSummary, compose_clarification,
                    compose_reply, compose_retrieval_failure)


class RetrievalError(RuntimeError):
    """The site retrieval could not establish a verified result."""


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
        try:
            result = retrieve(request, workspace)
        except RetrievalError:
            reply = compose_retrieval_failure(
                agent_address, incoming.sender, incoming.message_id,
                request.matter_number, request.requested_type,
            )
            sender.send(reply)
            mailbox.mark_seen(incoming.uid)
            return
        if result.summary.matter_number != request.matter_number:
            raise ValueError("retrieved_matter_mismatch")
        selected = select_documents(result.downloads)
        archive_path = None
        downloaded_count = 0
        failures = []
        if selected:
            candidate = workspace / f"{request.matter_number}_{request.requested_type.replace(' ', '_')}.zip"
            archive_result = build_archive(
                request.matter_number, request.requested_type, selected, candidate,
            )
            downloaded_count = archive_result.downloaded_count
            failures = archive_result.failures
            archive_path = candidate if downloaded_count else None
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
    """Process the currently unseen messages in the configured folder once."""
    messages = mailbox.fetch_unseen()
    for incoming in messages:
        process_incoming(incoming, mailbox, sender, retrieve, agent_address, max_attachment_bytes)
    return len(messages)


def run_forever(
    mailbox: Mailbox,
    sender: MailSender,
    retrieve: Retriever,
    agent_address: str,
    poll_interval_seconds: float = 60,
    stop: Event | None = None,
    max_attachment_bytes: int = 20 * 1024 * 1024,
) -> None:
    """Poll the mailbox until stopped; each pass handles currently unseen mail."""
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_must_be_positive")
    stop = stop or Event()
    while not stop.is_set():
        run_once(mailbox, sender, retrieve, agent_address, max_attachment_bytes)
        stop.wait(poll_interval_seconds)
