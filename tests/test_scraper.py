import unittest

from jobapply.scraper import extract_ashby_urls


class ScraperTests(unittest.TestCase):
    def test_extracts_direct_and_escaped_google_urls(self):
        html = r"""
        <a href="https://jobs.ashbyhq.com/acme/123?ref=google">role</a>
        <div>https:\/\/jobs.ashbyhq.com\/other\/456&amp;ref=x</div>
        <a href="https://example.com/not-ashby">ignore</a>
        """
        self.assertEqual(
            extract_ashby_urls(html),
            ["https://jobs.ashbyhq.com/acme/123", "https://jobs.ashbyhq.com/other/456"],
        )
