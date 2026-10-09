import unittest

from jobapply.models import Job
from jobapply.scraper import cap_per_company


class LimitTests(unittest.TestCase):
    def test_caps_each_company_at_ten(self):
        jobs = [Job("ashby", str(i), f"Role {i}", "Acme", published_at=f"2026-09-{i + 1:02d}T00:00:00+00:00") for i in range(12)]
        jobs += [Job("ashby", "other", "Role", "Other")]
        capped = cap_per_company(jobs)
        self.assertEqual(sum(job.company == "Acme" for job in capped), 10)
        self.assertEqual(sum(job.company == "Other" for job in capped), 1)
