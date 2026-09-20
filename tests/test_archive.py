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

    def test_partial_download_creates_zip_with_safe_unique_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_bytes(b"%PDF-1.4\nfirst")
            second.write_bytes(b"%PDF-1.4\nsecond")
            result = build_archive("M12205", "Other Documents", [
                Download(row("123", "../record.pdf"), first),
                Download(row("123", "../record.pdf"), second),
                Download(row("bad"), None, "download_timeout"),
            ], root / "result.zip")
            self.assertEqual(result.downloaded_count, 2)
            self.assertEqual(result.failures, ["bad: download_timeout"])
            with zipfile.ZipFile(root / "result.zip") as archive:
                self.assertEqual(archive.namelist(), ["01_record.pdf", "02_record.pdf"])
                self.assertEqual(archive.read("01_record.pdf"), first.read_bytes())

    def test_empty_and_html_downloads_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "good.pdf"
            good.write_bytes(b"%PDF-1.4\nvalid")
            empty = root / "empty.pdf"
            empty.write_bytes(b"")
            html = root / "error.pdf"
            html.write_bytes(b"<!doctype html><title>Error</title>")
            result = build_archive("M12205", "Exhibits", [
                Download(row("1"), good), Download(row("2"), empty), Download(row("3"), html),
            ], root / "result.zip")
            self.assertEqual(result.downloaded_count, 1)
            self.assertEqual(result.failures, ["2: empty_file", "3: html_response"])

    def test_no_files_does_not_create_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.zip"
            with self.assertRaisesRegex(ValueError, "no_verified_files"):
                build_archive("M12205", "Exhibits", [Download(row(), None)], destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
