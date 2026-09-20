import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from senpilot.archive import Document, Download, build_archive, select_documents


def row(document_id="123", filename="record.pdf"):
    return Document(document_id, "Filed record", "2026-09-20", "pdf", filename, None)


class ArchiveTests(unittest.TestCase):
    def test_selection_preserves_order_and_caps_at_ten(self):
        rows = [row(str(i)) for i in range(12)]
        self.assertEqual([r.site_document_id for r in select_documents(rows)], [str(i) for i in range(10)])

    def test_partial_download_has_safe_names_hashes_and_valid_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_bytes(b"%PDF-1.4\nfirst")
            second.write_bytes(b"%PDF-1.4\nsecond")
            downloads = [
                Download(row("123", "../record.pdf"), first),
                Download(row("123", "../record.pdf"), second),
                Download(row("bad"), None, "download_timeout"),
            ]
            archive_path = root / "result.zip"
            manifest = build_archive("M12205", "Other Documents", downloads, archive_path)
            self.assertEqual(manifest["downloaded_count"], 2)
            self.assertEqual(manifest["documents"][2]["error_code"], "download_timeout")
            with zipfile.ZipFile(archive_path) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertEqual(len(names), 3)
                self.assertEqual(len(set(names)), 3)
                self.assertTrue(all(".." not in name and "/" not in name for name in names))
                stored = json.loads(archive.read("manifest.json"))
                self.assertEqual(stored, manifest)
                for record in stored["documents"][:2]:
                    data = archive.read(record["archive_filename"])
                    self.assertEqual(record["sha256"], hashlib.sha256(data).hexdigest())
                    self.assertEqual(record["bytes"], len(data))

    def test_invalid_files_are_not_packaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "good.pdf"
            good.write_bytes(b"%PDF-1.4\nvalid")
            empty = root / "empty.pdf"
            empty.write_bytes(b"")
            html = root / "error.pdf"
            html.write_bytes(b"<!doctype html><title>Error</title>")
            wrong = root / "wrong.txt"
            wrong.write_text("plain text")
            manifest = build_archive(
                "M12205", "Exhibits",
                [Download(row("1"), good), Download(row("2"), empty),
                 Download(row("3"), html), Download(row("4"), wrong)],
                root / "result.zip",
            )
            self.assertEqual(manifest["downloaded_count"], 1)
            self.assertEqual(
                [item["error_code"] for item in manifest["documents"][1:]],
                ["empty_file", "html_response", "unexpected_extension"],
            )

    def test_no_verified_files_does_not_create_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.zip"
            with self.assertRaisesRegex(ValueError, "no_verified_files"):
                build_archive("M12205", "Exhibits", [Download(row(), None)], destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
