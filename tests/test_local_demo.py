from email import policy
from email.parser import BytesParser
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from senpilot.local_demo import prepare_local_reply


class LocalDemoTests(unittest.TestCase):
    def test_end_to_end_offline_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "request.eml"
            incoming.write_text(
                "From: requester@example.com\nTo: agent@example.com\n"
                "Message-ID: <request-1@example.com>\nSubject: M12205 Other Documents\n\n"
                "Please send the files.\n", encoding="utf-8",
            )
            (root / "document.pdf").write_bytes(b"%PDF-1.4\nfixture")
            fixture = root / "snapshot.json"
            fixture.write_text(json.dumps({
                "matter_number": "M12205",
                "requested_type": "Other Documents",
                "title": "Fixture matter",
                "matter_type": "Application",
                "category": "Water",
                "initial_filing_date": "2025-04-07",
                "final_filing_date": None,
                "counts": {
                    "Exhibits": 2, "Key Documents": 1, "Other Documents": 1,
                    "Transcripts": 0, "Recordings": 0,
                },
                "documents": [{
                    "site_document_id": "doc-1", "title": "Fixture document", "date": "2025-04-07",
                    "extension": "pdf", "original_filename": "document.pdf",
                    "source_url": None, "path": "document.pdf",
                }],
            }), encoding="utf-8")
            reply_path, archive_path = prepare_local_reply(
                incoming, fixture, root / "output", "agent@example.com",
            )
            self.assertIsNotNone(archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(len(archive.namelist()), 2)
            reply = BytesParser(policy=policy.default).parsebytes(reply_path.read_bytes())
            self.assertEqual(reply["To"], "requester@example.com")
            self.assertEqual(len(list(reply.iter_attachments())), 1)
            self.assertIn("Total across these five categories: 4", reply.get_body().get_content())

    def test_mismatched_fixture_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "request.eml").write_text(
                "From: requester@example.com\nSubject: M12205 Exhibits\n\nPlease send.\n",
                encoding="utf-8",
            )
            (root / "snapshot.json").write_text(json.dumps({
                "matter_number": "M99999", "requested_type": "Exhibits",
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixture_matter_mismatch"):
                prepare_local_reply(
                    root / "request.eml", root / "snapshot.json", root / "output",
                    "agent@example.com",
                )
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
