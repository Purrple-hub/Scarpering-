from __future__ import annotations

import hashlib
import unittest

from crawler.dedup import (
    BloomFilter,
    ExactDedup,
    MinHash,
    MinHashLSH,
    ScalableBloomFilter,
    Simhash,
    SmartDeduplicator,
)
from crawler.settings import Settings


class TestBloomFilter(unittest.TestCase):
    def test_add_contains(self):
        bf = BloomFilter(capacity=100, error_rate=0.01)
        bf.add("hello")
        self.assertIn("hello", bf)
        self.assertNotIn("world", bf)

    def test_error_handling_empty_input(self):
        bf = BloomFilter(capacity=10, error_rate=0.01)
        try:
            bf.add("")
            self.assertIn("", bf)
        except Exception as exc:
            self.fail(f"Empty string caused unexpected error: {exc}")


class TestScalableBloomFilter(unittest.TestCase):
    def test_scaling(self):
        sbf = ScalableBloomFilter(initial_capacity=10, error_rate=0.01)
        for i in range(25):
            sbf.add(f"url-{i}")
        self.assertIn("url-5", sbf)
        self.assertIn("url-20", sbf)
        self.assertNotIn("missing", sbf)

    def test_large_scale(self):
        sbf = ScalableBloomFilter(initial_capacity=5, error_rate=0.01)
        # insert enough items to force multiple internal filters
        for i in range(200):
            sbf.add(f"item-{i}")

        # Verify all inserted items are present (no false negatives)
        for i in range(200):
            self.assertIn(f"item-{i}", sbf)

        # Verify scaling actually happened
        self.assertGreater(len(sbf.filters), 1)

        # Do NOT assert absence of arbitrary keys here.
        # Bloom filters are probabilistic; under high load with many
        # small sub-filters, false positives become likely.


class TestExactDedup(unittest.TestCase):
    def test_cache_eviction(self):
        ed = ExactDedup(max_size=2)
        ed.add("a")
        ed.add("b")
        self.assertIn("a", ed)
        ed.add("c")
        self.assertNotIn("a", ed)

    def test_duplicate_add(self):
        ed = ExactDedup(max_size=10)
        ed.add("x")
        ed.add("x")
        self.assertIn("x", ed)
        try:
            ed.add("x")
        except Exception as exc:
            self.fail(f"Duplicate add raised: {exc}")


class TestSimhash(unittest.TestCase):
    def test_similar_text(self):
        sh = Simhash(64)
        a = sh.compute("the quick brown fox".split())
        b = sh.compute("the quick brown fox".split())
        c = sh.compute("the quick brown cat".split())
        self.assertEqual(a, b)
        self.assertLess(Simhash.hamming(a, c), 10)

    def test_empty_tokens(self):
        sh = Simhash(64)
        try:
            fp = sh.compute([])
            self.assertEqual(fp, 0)
        except Exception as exc:
            self.fail(f"Empty tokens caused error: {exc}")


class TestMinHash(unittest.TestCase):
    def test_jaccard(self):
        mh = MinHash(128)
        a = mh.compute("hello world foo bar".split())
        b = mh.compute("hello world foo bar".split())
        c = mh.compute("hello world foo baz".split())
        self.assertGreater(mh.jaccard(a, b), 0.9)
        self.assertGreater(mh.jaccard(a, c), 0.6)

    def test_jaccard_empty_sigs(self):
        mh = MinHash(128)
        self.assertEqual(mh.jaccard([], []), 0.0)
        self.assertEqual(mh.jaccard([1, 2], []), 0.0)


class TestMinHashLSH(unittest.TestCase):
    def test_insert_query(self):
        lsh = MinHashLSH(num_perm=128, bands=16, max_docs=100)
        mh = MinHash(128)
        sig = mh.compute("some document tokens".split())
        lsh.insert("doc1", sig)
        candidates = lsh.query(sig)
        self.assertIn("doc1", candidates)

    def test_candidate_not_present(self):
        lsh = MinHashLSH(num_perm=128, bands=16, max_docs=100)
        mh = MinHash(128)
        sig = mh.compute("another set of tokens".split())
        candidates = lsh.query(sig)
        self.assertNotIn("nonexistent", candidates)


class TestSmartDeduplicator(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(enable_dedup=True, near_dup_threshold=0.8)
        self.dedup = SmartDeduplicator(self.settings)

    def test_exact_duplicate(self):
        content = "This is a test page with enough words to pass the token threshold. " * 10
        is_dup, reason = self.dedup.is_duplicate("http://a.com/1", content, "<html></html>")
        self.assertFalse(is_dup)
        is_dup, reason = self.dedup.is_duplicate("http://a.com/1", content, "<html></html>")
        self.assertTrue(is_dup)
        self.assertIn("url", reason)

    def test_near_duplicate_detection(self):
        base = " ".join([f"word{i}" for i in range(100)])
        content1 = base + " " + "unique ending one"
        content2 = base + " " + "unique ending two"
        self.assertFalse(self.dedup.is_duplicate("http://a.com/1", content1, "")[0])
        is_dup, _ = self.dedup.is_duplicate("http://a.com/2", content2, "")
        self.assertTrue(is_dup)

    def test_short_content_skipped(self):
        short = "hello"
        is_dup, reason = self.dedup.is_duplicate("http://b.com/1", short, "")
        self.assertFalse(is_dup)
        is_dup2, _ = self.dedup.is_duplicate("http://b.com/1", short, "")
        self.assertTrue(is_dup2)

    def tearDown(self):
        self.dedup.url_bloom = None
        self.dedup.exact = None
        self.dedup.lsh = None
        del self.dedup


if __name__ == "__main__":
    unittest.main()