import unittest

from senpilot.intake import ClarificationNeeded, Request, parse_request


class IntakeTests(unittest.TestCase):
    def test_assignment_example(self):
        self.assertEqual(
            parse_request("Documents for M12205", "Please get Other Documents."),
            Request("M12205", "Other Documents"),
        )

    def test_case_whitespace_and_singular_alias(self):
        self.assertEqual(
            parse_request("m12205", "Could you send a KEY   DOCUMENT?"),
            Request("M12205", "Key Documents"),
        )

    def test_repeated_same_values_are_unambiguous(self):
        self.assertEqual(
            parse_request("M12205 Exhibits", "M12205 exhibit please"),
            Request("M12205", "Exhibits"),
        )

    def test_quoted_old_request_is_ignored(self):
        self.assertEqual(
            parse_request("", "M12205 recordings\nOn Monday, Alex wrote:\nM11111 transcripts"),
            Request("M12205", "Recordings"),
        )

    def test_invalid_or_ambiguous_requests(self):
        for subject, body in (
            ("M12205", "Please send files"),
            ("M12205 M11111", "Exhibits"),
            ("M12205", "Exhibits and Transcripts"),
            ("M1220", "Exhibits"),
            ("M122050", "Exhibits"),
            ("XM12205", "Exhibits"),
        ):
            with self.subTest(subject=subject, body=body):
                with self.assertRaises(ClarificationNeeded):
                    parse_request(subject, body)


if __name__ == "__main__":
    unittest.main()
