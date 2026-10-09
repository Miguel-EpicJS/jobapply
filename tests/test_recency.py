import unittest
from datetime import datetime, timezone

from jobapply.models import Job
from jobapply.scraper import published_within


class RecencyTests(unittest.TestCase):
    def test_keeps_only_the_last_fourteen_days(self):
        now = datetime(2026, 9, 17, tzinfo=timezone.utc)
        jobs = [
            Job("ashby", "recent", "Recent", "Acme", published_at="2026-09-10T08:49:37.626+00:00"),
            Job("ashby", "old", "Old", "Acme", published_at="2022-01-22T08:49:37.626+00:00"),
            Job("ashby", "missing", "Missing", "Acme"),
        ]
        self.assertEqual([job.external_id for job in published_within(jobs, 14, now)], ["recent"])
