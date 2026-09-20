from pathlib import Path
import tempfile
import unittest
import zipfile

from senpilot.intake import CATEGORIES
from senpilot.reply import AttachmentTooLarge, MatterSummary, compose_reply


def summary(counts=None):
    return MatterSummary(
        "M12205", "Example matter", "Application", "Energy", "2026-01-02", None,
        counts or dict(zip(CATEGORIES, [2, 1, 3, 0, 0])),
    )


class ReplyTests(unittest.TestCase):
    def test_attached_reply_has_factual_counts_and_zip_mime(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "files.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("record.pdf", b"%PDF-1.4")
            message = compose_reply(
                "agent@example.com", "requester@example.com", "<incoming@example.com>",
                summary(), "Other Documents", 2, 1, ["record 42: download_timeout"],
                archive, 1_000_000,
            )
            self.assertEqual(message["In-Reply-To"], "<incoming@example.com>")
            self.assertEqual(len(list(message.iter_attachments())), 1)
            attachment = next(message.iter_attachments())
            self.assertEqual(attachment.get_content_type(), "application/zip")
            self.assertEqual(attachment.get_filename(), "M12205_Other_Documents.zip")
            self.assertEqual(attachment.get_content(), archive.read_bytes())
            body = message.get_body(preferencelist=("plain",)).get_content()
            self.assertIn("Total across these five categories: 6", body)
            self.assertIn("Downloaded 1 of 3 Other Documents", body)
            self.assertIn("Selected 2 files for download; 1 did not succeed", body)
            self.assertIn("record 42: download_timeout", body)

    def test_unavailable_count_omits_grand_total_and_no_results_omits_zip(self):
        counts = dict(zip(CATEGORIES, [2, None, 0, 0, 0]))
        message = compose_reply(
            "agent@example.com", "requester@example.com", "", summary(counts),
            "Other Documents", 0, 0, [], None, 1000,
        )
        self.assertEqual(list(message.iter_attachments()), [])
        body = message.get_content()
        self.assertIn("Key Documents: unavailable", body)
        self.assertIn("Total across these five categories: unavailable", body)
        self.assertIn("no ZIP is attached", body)

    def test_attachment_limit_blocks_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "files.zip"
            archive.write_bytes(b"12345")
            with self.assertRaises(AttachmentTooLarge):
                compose_reply(
                    "agent@example.com", "requester@example.com", "", summary(),
                    "Other Documents", 1, 1, [], archive, 4,
                )

if __name__ == "__main__":
    unittest.main()
