import tempfile
import unittest
from pathlib import Path

from jobapply.models import Job
from jobapply.storage import JobStore


class StorageTests(unittest.TestCase):
    def test_upsert_and_status(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory) / "jobs.db")
            job = Job("ashby", "abc", "AI Engineer", "Example", url="https://example.test")
            self.assertEqual(store.upsert_many([job]), (1, 0))
            self.assertEqual(store.upsert_many([job]), (0, 1))
            saved = store.list()[0]
            self.assertEqual(saved["title"], "AI Engineer")
            self.assertTrue(store.set_status(saved["id"], "interested"))
            self.assertEqual(store.get(saved["id"])["status"], "interested")
            store.close()


if __name__ == "__main__":
    unittest.main()
