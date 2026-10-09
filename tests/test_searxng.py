import unittest

from jobapply.scraper import extract_ashby_urls


class SearxngTests(unittest.TestCase):
    def test_extracts_searxng_result_url(self):
        payload_url = "https://jobs.ashbyhq.com/example/role-123"
        self.assertEqual(extract_ashby_urls(payload_url), [payload_url])
