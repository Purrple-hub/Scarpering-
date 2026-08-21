from __future__ import annotations

import json
import os
import tempfile
import unittest

from crawler.settings import Settings


class TestSettings(unittest.TestCase):
    def test_defaults(self):
        s = Settings()
        self.assertEqual(s.max_depth, 3)
        self.assertEqual(s.max_pages, 1000)
        self.assertEqual(s.output_dir, "crawled_data")

    def test_from_config(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"max_depth": 7, "output_dir": "custom_out"}, f)
            path = f.name
        try:
            s = Settings.from_config(path)
            self.assertEqual(s.max_depth, 7)
            self.assertEqual(s.output_dir, "custom_out")
        finally:
            os.unlink(path)

    def test_env_override(self):
        os.environ["CRAWLER_MAX_PAGES"] = "42"
        try:
            s = Settings.from_config()
            self.assertEqual(s.max_pages, 42)
        finally:
            del os.environ["CRAWLER_MAX_PAGES"]

    def test_to_dict_roundtrip(self):
        s = Settings(seed_urls=["https://example.com"], max_depth=5)
        d = s.to_dict()
        s2 = Settings(**d)
        self.assertEqual(s.max_depth, s2.max_depth)
        self.assertEqual(s.seed_urls, s2.seed_urls)


if __name__ == "__main__":
    unittest.main()