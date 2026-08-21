from __future__ import annotations

import unittest

from selectolax.parser import HTMLParser

from crawler.discovery import extract_links_from_html, parse_sitemap


class TestParseSitemap(unittest.TestCase):
    def test_normal_sitemap(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>"""
        page_urls, nested = parse_sitemap(xml)
        self.assertEqual(
            page_urls,
            ["https://example.com/page1", "https://example.com/page2"],
        )
        self.assertEqual(nested, [])

    def test_sitemap_index(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
            <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
        </sitemapindex>"""
        page_urls, nested = parse_sitemap(xml)
        self.assertEqual(page_urls, [])
        self.assertEqual(
            nested,
            ["https://example.com/sitemap-1.xml", "https://example.com/sitemap-2.xml"],
        )

    def test_malformed_xml_fallback(self):
        xml = """<urlset><url><loc>https://example.com/a</loc></url><url><loc>https://example.com/b</loc></url></urlset>"""
        page_urls, nested = parse_sitemap(xml)
        self.assertEqual(
            page_urls,
            ["https://example.com/a", "https://example.com/b"],
        )
        self.assertEqual(nested, [])


class TestExtractLinksFromHtml(unittest.TestCase):
    def test_anchor_and_json(self):
        html = b"""
        <html><body>
            <a href="/page1">Page1</a>
            <a href="https://example.com/page2">Page2</a>
            <script id="__NEXT_DATA__" type="application/json">
                {"props":{"pageProps":{"links":[{"url":"/internal1"}],"url":"/internal2"}}}
            </script>
            <script type="application/ld+json">
                {"@type":"WebPage","url":"https://example.com/jsonld"}
            </script>
        </body></html>
        """
        parser = HTMLParser(html)
        links = extract_links_from_html(parser, "https://example.com")
        self.assertIn("https://example.com/page1", links)
        self.assertIn("https://example.com/page2", links)
        self.assertIn("https://example.com/internal1", links)
        self.assertIn("https://example.com/internal2", links)
        self.assertIn("https://example.com/jsonld", links)

    def test_iframe_and_meta_refresh(self):
        html = b"""
        <html><body>
            <iframe src="/frame"></iframe>
            <meta http-equiv="refresh" content="0; url=/redirected">
        </body></html>
        """
        parser = HTMLParser(html)
        links = extract_links_from_html(parser, "https://example.com")
        self.assertIn("https://example.com/frame", links)
        self.assertIn("https://example.com/redirected", links)


if __name__ == "__main__":
    unittest.main()