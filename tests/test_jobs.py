from pathlib import Path
import tempfile
import unittest

from senpilot.jobs import JobStore


class JobStoreTests(unittest.TestCase):
    def test_duplicate_delivery_and_uncertain_send_do_not_resend(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.sqlite"
            store = JobStore(path)
            self.assertTrue(store.receive("in-1", "requester@example.com"))
            self.assertFalse(store.receive("in-1", "requester@example.com"))
            store.mark_ready("in-1")
            self.assertTrue(store.reserve_send("in-1"))
            self.assertFalse(JobStore(path).reserve_send("in-1"))
            self.assertEqual(store.get("in-1")["state"], "sending")
            store.mark_sent("in-1", "out-1")
            self.assertFalse(store.reserve_send("in-1"))
            self.assertEqual(store.get("in-1")["outbound_message_id"], "out-1")
            self.assertEqual(store.get("in-1")["attempt"], 1)

    def test_invalid_transition_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory) / "jobs.sqlite")
            store.receive("in-1", "requester@example.com")
            with self.assertRaisesRegex(ValueError, "invalid_state_transition"):
                store.mark_sent("in-1", "out-1")
            store.mark_ready("in-1")
            with self.assertRaisesRegex(ValueError, "invalid_state_transition"):
                store.mark_ready("in-1")


if __name__ == "__main__":
    unittest.main()
