import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from senpilot.intake import Request
from senpilot.mail import IncomingMail
from senpilot.uarb import RetrievalError, retrieve_uarb
from senpilot.worker import process_incoming


def result_for(workspace: Path):
    path = workspace / "downloads" / "01_document.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"%PDF-1.4\nexample")
    return {
        "matter_number": "M12205",
        "requested_type": "Other Documents",
        "title": "Example matter",
        "matter_type": "Application",
        "category": "Water",
        "initial_filing_date": "2025-04-07",
        "final_filing_date": None,
        "counts": {"Exhibits": 1, "Key Documents": 0, "Other Documents": 1,
                   "Transcripts": 0, "Recordings": 0},
        "documents": [{"site_document_id": "123", "title": "Example document",
                       "date": None, "extension": "pdf", "original_filename": "document.pdf",
                       "source_url": None, "path": str(path), "error_code": None}],
    }


class UarbBridgeTests(unittest.TestCase):
    def test_browser_result_maps_to_worker_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            def fake_run(command, **kwargs):
                (workspace / "result.json").write_text(json.dumps(result_for(workspace)))

            with patch("senpilot.uarb.subprocess.run", side_effect=fake_run):
                result = retrieve_uarb(Request("M12205", "Other Documents"), workspace)
            self.assertEqual(result.summary.counts["Exhibits"], 1)
            self.assertEqual(result.downloads[0].path.name, "01_document.pdf")

    def test_wrong_matter_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)

            def fake_run(command, **kwargs):
                data = result_for(workspace)
                data["matter_number"] = "M99999"
                (workspace / "result.json").write_text(json.dumps(data))

            with patch("senpilot.uarb.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(RetrievalError, "retrieved_matter_mismatch"):
                    retrieve_uarb(Request("M12205", "Other Documents"), workspace)

    def test_path_outside_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "work"
            workspace.mkdir()
            outside = Path(directory) / "outside.pdf"
            outside.write_bytes(b"%PDF-1.4")

            def fake_run(command, **kwargs):
                data = result_for(workspace)
                data["documents"][0]["path"] = str(outside)
                (workspace / "result.json").write_text(json.dumps(data))

            with patch("senpilot.uarb.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(RetrievalError, "download_path_outside_workspace"):
                    retrieve_uarb(Request("M12205", "Other Documents"), workspace)

    def test_bridge_to_zip_reply_without_network(self):
        class Mailbox:
            seen = []

            def mark_seen(self, uid):
                self.seen.append(uid)

        class Sender:
            messages = []

            def send(self, message):
                self.messages.append(message)

        def fake_run(command, **kwargs):
            workspace = Path(command[4]).parent
            (workspace / "result.json").write_text(json.dumps(result_for(workspace)))

        mailbox, sender = Mailbox(), Sender()
        incoming = IncomingMail(b"12", "<in@example.com>", "user@example.com",
                                Request("M12205", "Other Documents"))
        with patch("senpilot.uarb.subprocess.run", side_effect=fake_run):
            process_incoming(incoming, mailbox, sender, retrieve_uarb, "agent@example.com")
        self.assertEqual(mailbox.seen, [b"12"])
        self.assertEqual(len(list(sender.messages[0].iter_attachments())), 1)
        self.assertIn("Example matter", sender.messages[0].get_body().get_content())


if __name__ == "__main__":
    unittest.main()
