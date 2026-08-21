from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.crawler import UnifiedAsyncCrawler
from crawler.settings import Settings


class TestUnifiedAsyncCrawler(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(seed_urls=["https://example.com"])
        self.crawler = UnifiedAsyncCrawler(self.settings, bridge=None)

    def test_normalize_url(self):
        self.assertEqual(
            self.crawler.normalize_url("example.com/path"),
            "https://example.com/path",
        )
        self.assertEqual(
            self.crawler.normalize_url("http://example.com"),
            "http://example.com",
        )

    def test_parse_html(self):
        html = b"""
        <html><head><title>Test Page</title></head>
        <body>
            <h1>Heading</h1>
            <p>Some content here</p>
            <a href="/link1">Link1</a>
            <a href="https://external.com/x">External</a>
        </body></html>
        """
        page = self.crawler._parse_html("https://example.com/page", html, depth=1)
        self.assertEqual(page["title"], "Test Page")
        self.assertIn("Heading", page["content"])
        self.assertIn("https://example.com/link1", page["links"])
        self.assertIn("https://external.com/x", page["links"])
        self.assertEqual(page["depth"], 1)

    def test_enqueue_links_follow_external_false(self):
        self.settings.seed_urls = ["https://example.com"]
        self.settings.follow_external = False
        self.crawler.settings = self.settings
        self.crawler._enqueue_links(
            ["https://example.com/internal", "https://other.com/external"], current_depth=0
        )
        urls = []
        while not self.crawler.queue.empty():
            _, _, url = self.crawler.queue.get_nowait()
            urls.append(url)
        self.assertIn("https://example.com/internal", urls)
        self.assertNotIn("https://other.com/external", urls)


if __name__ == "__main__":
    unittest.main()