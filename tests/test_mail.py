from email.message import EmailMessage
import unittest
from unittest.mock import patch

from senpilot.mail import MailSender, Mailbox, parse_incoming


class MailTests(unittest.TestCase):
    def test_parse_plain_text_request(self):
        message = EmailMessage()
        message["From"] = "Requester <requester@example.com>"
        message["Message-ID"] = "<abc@example.com>"
        message["Subject"] = "M12205"
        message.set_content("Please send Other Documents.")
        incoming = parse_incoming(b"7", message.as_bytes())
        self.assertEqual(incoming.sender, "requester@example.com")
        self.assertEqual(incoming.request.matter_number, "M12205")
        self.assertEqual(incoming.request.requested_type, "Other Documents")

    def test_fetch_uses_peek_and_does_not_mark_read(self):
        message = EmailMessage()
        message["From"] = "requester@example.com"
        message["Subject"] = "M12205 Exhibits"
        message.set_content("Please send them.")
        with patch("senpilot.mail.imaplib.IMAP4_SSL") as factory:
            client = factory.return_value.__enter__.return_value
            client.select.return_value = ("OK", [])
            client.uid.side_effect = [
                ("OK", [b"7"]),
                ("OK", [(b"7 (BODY[]", message.as_bytes())]),
            ]
            found = Mailbox("imap.example.com", "agent", "secret").fetch_unseen()
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].uid, b"7")
            client.uid.assert_any_call("fetch", b"7", "(BODY.PEEK[])")
            self.assertEqual(client.select.call_args.kwargs, {"readonly": True})

    def test_ambiguous_request_can_be_clarified(self):
        message = EmailMessage()
        message["From"] = "requester@example.com"
        message["Subject"] = "M12205"
        message.set_content("Please send files.")
        incoming = parse_incoming(b"8", message.as_bytes())
        self.assertIsNone(incoming.request)
        self.assertIn("one document type", incoming.clarification)

    def test_send_uses_authenticated_smtp(self):
        message = EmailMessage()
        message["From"] = "agent@example.com"
        message["To"] = "requester@example.com"
        message.set_content("Reply")
        with patch("senpilot.mail.smtplib.SMTP_SSL") as factory:
            client = factory.return_value.__enter__.return_value
            MailSender("smtp.example.com", "agent", "secret").send(message)
            client.login.assert_called_once_with("agent", "secret")
            client.send_message.assert_called_once_with(message)


if __name__ == "__main__":
    unittest.main()
