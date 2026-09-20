from pathlib import Path
import unittest

from senpilot.archive import Document, Download
from senpilot.intake import Request
from senpilot.mail import IncomingMail
from senpilot.reply import MatterSummary
from senpilot.worker import RetrievalResult, process_incoming


def summary(count=1):
    return MatterSummary(
        "M12205", "Test matter", "Application", "Water", "2025-04-07", None,
        {"Exhibits": 0, "Key Documents": 0, "Other Documents": count,
         "Transcripts": 0, "Recordings": 0},
    )


class FakeMailbox:
    def __init__(self):
        self.seen = []

    def mark_seen(self, uid):
        self.seen.append(uid)


class FakeSender:
    def __init__(self, fail=False):
        self.messages = []
        self.fail = fail

    def send(self, message):
        if self.fail:
            raise RuntimeError("smtp_failed")
        self.messages.append(message)


class WorkerTests(unittest.TestCase):
    def test_valid_request_sends_zip_then_marks_seen(self):
        mailbox = FakeMailbox()
        sender = FakeSender()
        incoming = IncomingMail(b"1", "<in@example.com>", "user@example.com",
                                Request("M12205", "Other Documents"))

        def retrieve(request, workspace: Path):
            path = workspace / "document.pdf"
            path.write_bytes(b"%PDF-1.4\nfile")
            document = Document("1", "Document", None, "pdf", "document.pdf", None)
            return RetrievalResult(summary(), [Download(document, path)])

        process_incoming(incoming, mailbox, sender, retrieve, "agent@example.com")
        self.assertEqual(mailbox.seen, [b"1"])
        self.assertEqual(len(list(sender.messages[0].iter_attachments())), 1)
        self.assertIn("Downloaded 1 of 1", sender.messages[0].get_body().get_content())

    def test_ambiguous_request_sends_clarification(self):
        mailbox = FakeMailbox()
        sender = FakeSender()
        incoming = IncomingMail(b"2", "", "user@example.com", None, "Specify a category.")
        process_incoming(incoming, mailbox, sender, lambda *_: self.fail("retrieval called"),
                         "agent@example.com")
        self.assertEqual(mailbox.seen, [b"2"])
        self.assertIn("Specify a category", sender.messages[0].get_content())

    def test_zero_results_omits_zip(self):
        mailbox = FakeMailbox()
        sender = FakeSender()
        incoming = IncomingMail(b"3", "", "user@example.com",
                                Request("M12205", "Other Documents"))
        process_incoming(incoming, mailbox, sender, lambda *_: RetrievalResult(summary(0), []),
                         "agent@example.com")
        self.assertEqual(list(sender.messages[0].iter_attachments()), [])
        self.assertIn("No files were selected", sender.messages[0].get_content())

    def test_failed_send_does_not_mark_seen(self):
        mailbox = FakeMailbox()
        incoming = IncomingMail(b"4", "", "user@example.com", None, "Clarify.")
        with self.assertRaisesRegex(RuntimeError, "smtp_failed"):
            process_incoming(incoming, mailbox, FakeSender(fail=True), lambda *_: self.fail(),
                             "agent@example.com")
        self.assertEqual(mailbox.seen, [])


if __name__ == "__main__":
    unittest.main()
