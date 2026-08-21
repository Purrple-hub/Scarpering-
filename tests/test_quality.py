from __future__ import annotations

import unittest

from crawler.quality import QualityScorer


class TestQualityScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = QualityScorer()

    def test_empty(self):
        self.assertEqual(self.scorer.score("", "", [], 0), 0)

    def test_good_page(self):
        score = self.scorer.score(
            "Great Title",
            "This is a long text " * 100,
            ["Header1", "Header2", "Header3"],
            50,
        )
        self.assertGreaterEqual(score, 8)

    def test_max_score(self):
        score = self.scorer.score("T", "x" * 600, ["h1", "h2", "h3", "h4"], 100)
        self.assertEqual(score, 10)


if __name__ == "__main__":
    unittest.main()