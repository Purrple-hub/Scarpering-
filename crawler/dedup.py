from __future__ import annotations

import hashlib
import math
from collections import OrderedDict, defaultdict, deque


class BloomFilter:
    def __init__(self, capacity: int, error_rate: float = 0.01) -> None:
        self.size = max(1, int(-capacity * math.log(error_rate) / (math.log(2) ** 2)))
        self.k = max(1, int(self.size / capacity * math.log(2)))
        self.bits = bytearray(self.size)

    def _hashes(self, item: str):
        h1 = hashlib.sha256(item.encode()).digest()
        h2 = hashlib.md5(item.encode()).digest()
        for i in range(self.k):
            yield (int.from_bytes(h1, "big") + i * int.from_bytes(h2, "big")) % self.size

    def add(self, item: str) -> None:
        for pos in self._hashes(item):
            self.bits[pos] = 1

    def __contains__(self, item: str) -> bool:
        return all(self.bits[pos] for pos in self._hashes(item))


class ScalableBloomFilter:
    def __init__(self, initial_capacity: int = 10000, error_rate: float = 0.01) -> None:
        self.error_rate = error_rate
        self.initial_capacity = initial_capacity
        self.filters: list[BloomFilter] = [BloomFilter(initial_capacity, error_rate)]
        self.current_count = 0

    def add(self, item: str) -> None:
        if self.current_count >= self.initial_capacity:
            self.filters.append(BloomFilter(self.initial_capacity, self.error_rate))
            self.current_count = 0
        self.filters[-1].add(item)
        self.current_count += 1

    def __contains__(self, item: str) -> bool:
        return any(item in f for f in self.filters)


class ExactDedup:
    def __init__(self, max_size: int = 10000) -> None:
        self.cache: OrderedDict[str, None] = OrderedDict()
        self.max_size = max_size

    def add(self, content_hash: str) -> None:
        self.cache[content_hash] = None
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def __contains__(self, content_hash: str) -> bool:
        return content_hash in self.cache


class Simhash:
    def __init__(self, bits: int = 64) -> None:
        self.bits = bits

    def _hash(self, token: str) -> int:
        return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")

    def compute(self, tokens: list[str]) -> int:
        vector = [0] * self.bits
        for token in tokens:
            h = self._hash(token)
            for i in range(self.bits):
                vector[i] += 1 if (h >> i) & 1 else -1
        fp = 0
        for i, val in enumerate(vector):
            if val > 0:
                fp |= 1 << i
        return fp

    @staticmethod
    def hamming(a: int, b: int, bits: int = 64) -> int:
        return (a ^ b).bit_count()


class MinHash:
    def __init__(self, num_perm: int = 128) -> None:
        self.num_perm = num_perm

    def compute(self, tokens: list[str]) -> list[int]:
        if not tokens:
            return [0] * self.num_perm
        sig = []
        for i in range(self.num_perm):
            min_val = float("inf")
            for token in tokens:
                h = int.from_bytes(
                    hashlib.blake2b(f"{i}:{token}".encode(), digest_size=8).digest(), "big"
                )
                if h < min_val:
                    min_val = h
            sig.append(min_val)
        return sig

    @staticmethod
    def jaccard(a: list[int], b: list[int]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        return sum(x == y for x, y in zip(a, b)) / len(a)


class MinHashLSH:
    def __init__(self, num_perm: int = 128, bands: int = 16, max_docs: int = 5000) -> None:
        self.num_perm = num_perm
        self.bands = bands
        self.rows = max(1, num_perm // bands)
        self.max_docs = max_docs
        self.buckets: dict[tuple, set[str]] = defaultdict(set)
        self.sigs: dict[str, list[int]] = {}
        self.doc_order: deque[str] = deque()

    def _band_keys(self, sig: list[int]) -> list[tuple]:
        keys = []
        for b in range(self.bands):
            start = b * self.rows
            end = start + self.rows
            keys.append((b, tuple(sig[start:end])))
        return keys

    def insert(self, doc_id: str, sig: list[int]) -> None:
        if len(self.doc_order) >= self.max_docs:
            old = self.doc_order.popleft()
            old_sig = self.sigs.pop(old, None)
            if old_sig is not None:
                for key in self._band_keys(old_sig):
                    self.buckets[key].discard(old)
        self.doc_order.append(doc_id)
        self.sigs[doc_id] = sig
        for key in self._band_keys(sig):
            self.buckets[key].add(doc_id)

    def query(self, sig: list[int]) -> set[str]:
        candidates: set[str] = set()
        for key in self._band_keys(sig):
            candidates.update(self.buckets.get(key, set()))
        return candidates


class SmartDeduplicator:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.url_bloom = ScalableBloomFilter()
        self.exact = ExactDedup()
        self.simhash = Simhash(settings.simhash_bits)
        self.minhash = MinHash(settings.minhash_perms)
        self.lsh = MinHashLSH(settings.minhash_perms, settings.minhash_bands, settings.lsh_max_docs)
        self.seen_urls: set[str] = set()

    def tokenize(self, text: str) -> list[str]:
        return text.lower().split()

    def is_duplicate(self, url: str, content: str, html: str) -> tuple[bool, str]:
        if not self.settings.enable_dedup:
            return False, ""
        if url in self.url_bloom or url in self.seen_urls:
            return True, "url_bloom"
        self.url_bloom.add(url)
        self.seen_urls.add(url)

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if content_hash in self.exact:
            return True, "exact_content"
        self.exact.add(content_hash)

        tokens = self.tokenize(content)
        if len(tokens) < 20:
            return False, ""

        sim_fp = self.simhash.compute(tokens)
        min_sig = self.minhash.compute(tokens)

        candidates = self.lsh.query(min_sig)
        for doc_id in candidates:
            old_sig = self.lsh.sigs.get(doc_id)
            if old_sig is None:
                continue
            jac = self.minhash.jaccard(min_sig, old_sig)
            if jac >= self.settings.near_dup_threshold:
                return True, "minhash_near_dup"

        self.lsh.insert(content_hash, min_sig)
        return False, ""