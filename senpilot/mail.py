"""Small IMAP/SMTP adapter for receiving requests and sending prepared replies."""

from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
import imaplib
import os
import smtplib

from .intake import ClarificationNeeded, Request, parse_request


@dataclass(frozen=True)
class IncomingMail:
    uid: bytes
    message_id: str
    sender: str
    request: Request | None
    clarification: str | None = None


def parse_incoming(uid: bytes, raw_message: bytes) -> IncomingMail:
    """Extract the sender and request from a plain-text email."""
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    sender = parseaddr(str(message.get("From", "")))[1]
    if not sender:
        raise ValueError("missing_sender")
    body = message.get_body(preferencelist=("plain",))
    if body is None:
        raise ValueError("missing_plain_text_body")
    try:
        request = parse_request(str(message.get("Subject", "")), body.get_content())
        clarification = None
    except ClarificationNeeded as error:
        request = None
        clarification = str(error)
    return IncomingMail(uid, str(message.get("Message-ID", "")), sender, request, clarification)


class Mailbox:
    def __init__(self, host: str, username: str, password: str, port: int = 993):
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def fetch_unseen(self) -> list[IncomingMail]:
        """Fetch unseen messages without marking them read."""
        results = []
        with imaplib.IMAP4_SSL(self.host, self.port) as client:
            client.login(self.username, self.password)
            status, _ = client.select("INBOX", readonly=True)
            if status != "OK":
                raise RuntimeError("imap_select_failed")
            status, data = client.uid("search", None, "UNSEEN")
            if status != "OK":
                raise RuntimeError("imap_search_failed")
            for uid in data[0].split():
                status, parts = client.uid("fetch", uid, "(BODY.PEEK[])")
                if status != "OK":
                    raise RuntimeError("imap_fetch_failed")
                raw = next((part[1] for part in parts if isinstance(part, tuple)), None)
                if raw is None:
                    raise RuntimeError("imap_empty_message")
                results.append(parse_incoming(uid, raw))
        return results

    def mark_seen(self, uid: bytes) -> None:
        """Mark a message read after its reply has been sent."""
        with imaplib.IMAP4_SSL(self.host, self.port) as client:
            client.login(self.username, self.password)
            status, _ = client.select("INBOX")
            if status != "OK":
                raise RuntimeError("imap_select_failed")
            status, _ = client.uid("store", uid, "+FLAGS", "(\\Seen)")
            if status != "OK":
                raise RuntimeError("imap_mark_seen_failed")


class MailSender:
    def __init__(self, host: str, username: str, password: str, port: int = 465):
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def send(self, message: EmailMessage) -> None:
        """Send an already composed reply over authenticated SMTP/TLS."""
        if not message.get("To") or not message.get("From"):
            raise ValueError("missing_mail_address")
        with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as client:
            client.login(self.username, self.password)
            client.send_message(message)


def mailbox_from_env() -> Mailbox:
    """Read mail connection settings only when constructing the adapter."""
    return Mailbox(
        os.environ["SENPILOT_IMAP_HOST"],
        os.environ["SENPILOT_EMAIL_USER"],
        os.environ["SENPILOT_EMAIL_PASSWORD"],
        int(os.environ.get("SENPILOT_IMAP_PORT", "993")),
    )


def sender_from_env() -> MailSender:
    return MailSender(
        os.environ["SENPILOT_SMTP_HOST"],
        os.environ["SENPILOT_EMAIL_USER"],
        os.environ["SENPILOT_EMAIL_PASSWORD"],
        int(os.environ.get("SENPILOT_SMTP_PORT", "465")),
    )
