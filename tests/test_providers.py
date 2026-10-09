import unittest

from jobapply.scraper import extract_ashby_urls


class ProviderTests(unittest.TestCase):
    def test_extracts_provider_result_link(self):
        self.assertEqual(
            extract_ashby_urls("https://jobs.ashbyhq.com/acme/role-123"),
            ["https://jobs.ashbyhq.com/acme/role-123"],
        )
